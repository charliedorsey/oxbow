import hashlib
import importlib.util
import io
import json
import random
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from oxbow.bundle import kernel

ROOT = Path(__file__).resolve().parents[1]


def _load_reference_decoder():
    path = ROOT / "compat" / "rosetta_v5" / "reference_decoder.py"
    spec = importlib.util.spec_from_file_location("oxbow_rosetta_reference_decoder", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def orientation_files():
    return [
        ("READ_FIRST.md", b"# Read first\nThis is a synthetic handoff fixture.\n"),
        ("BUNDLE_LAYOUT.md", b"# Bundle layout\nSynthetic fixture layout.\n"),
        ("START_HERE.md", b"# Start here\nInspect, verify, then work.\n"),
    ]


def unsafe_payload(files):
    ordered = list(files)
    paths = [p for p, _ in ordered]
    blobs = [b for _, b in ordered]
    paths_code = kernel._encode_paths(paths)
    offsets_code = kernel._encode_offsets(blobs)
    data_code = kernel._lzc6(b"".join(blobs))
    out = bytearray(kernel.MAGIC)
    out.append(kernel.VERSION)
    for _ in range(3):
        kernel._wv(0, out); kernel._wv(0, out); kernel._wv(0, out)
    kernel._wv(1, out)
    name = kernel.PUBLIC_SECTION.encode()
    kernel._wv(len(name), out); out.extend(name)
    kernel._wv(0, out); kernel._wv(len(blobs), out); kernel._wv(0, out); kernel._wv(len(paths), out)
    kernel._wv(len(paths_code), out); out.extend(paths_code)
    if blobs:
        kernel._wv(len(offsets_code), out); out.extend(offsets_code)
        kernel._wv(len(data_code), out); out.extend(data_code)
    return bytes(out)


class KernelRoundTripTests(unittest.TestCase):
    def test_mixed_binary_types_are_not_dropped(self):
        zbuf = io.BytesIO()
        with zipfile.ZipFile(zbuf, "w") as zf:
            zf.writestr("inside.txt", "zip payload")
        rng = random.Random(7)
        files = orientation_files() + [
            ("images/pixel.png", b"\x89PNG\r\n\x1a\n" + bytes(range(32))),
            ("docs/sample.pdf", b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"),
            ("archives/sample.zip", zbuf.getvalue()),
            ("audio/sample.wav", b"RIFF" + b"\x00" * 44),
            ("images/photo.jpg", b"\xff\xd8\xff\xe0" + b"synthetic" + b"\xff\xd9"),
            ("data/random.bin", bytes(rng.randrange(256) for _ in range(8192))),
        ]
        payload = kernel.build_bundle_bytes(files)
        got = kernel.parse(payload).mapping
        for path, blob in files:
            self.assertEqual(got[path], blob)
        result = kernel.verify_bundle_bytes(payload)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["integrity"]["unexpected"], [])
        self.assertEqual(result["integrity"]["missing"], [])

    def test_reference_decoder_reads_public_kernel_output(self):
        legacy_decode = _load_reference_decoder()
        files = orientation_files() + [("data/x.bin", bytes(range(256)) * 8)]
        payload = kernel.build_bundle_bytes(files)
        legacy = dict(legacy_decode.iter_files(payload))
        public = kernel.parse(payload).mapping
        self.assertEqual(legacy, public)

    def test_manifest_requires_exact_tree(self):
        files = orientation_files() + [("extra.txt", b"extra")]
        manifest_records = []
        for path, blob in orientation_files():
            manifest_records.append({
                "path": path,
                "bytes": len(blob),
                "sha256": hashlib.sha256(blob).hexdigest(),
            })
        man = json.dumps({"format": kernel.MANIFEST_FORMAT, "files": manifest_records}).encode()
        payload = kernel.encode_files(files + [(kernel.MANIFEST_PATH, man)])
        result = kernel.verify_bundle_bytes(payload)
        self.assertTrue(result["wire"]["ok"])
        self.assertFalse(result["integrity"]["ok"])
        self.assertEqual(result["integrity"]["unexpected"], ["extra.txt"])

    def test_duplicate_manifest_record_fails_integrity(self):
        base = orientation_files()
        p, b = base[0]
        rec = {"path": p, "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
        rest = [
            {"path": rp, "bytes": len(rb), "sha256": hashlib.sha256(rb).hexdigest()}
            for rp, rb in base[1:]
        ]
        man = json.dumps({"format": kernel.MANIFEST_FORMAT, "files": [rec, rec] + rest}).encode()
        payload = kernel.encode_files(base + [(kernel.MANIFEST_PATH, man)])
        result = kernel.verify_bundle_bytes(payload)
        self.assertFalse(result["integrity"]["ok"])
        self.assertTrue(any("duplicate manifest path" in x for x in result["integrity"]["manifest_errors"]))

    def test_wire_integrity_conformance_are_separate(self):
        payload = kernel.build_bundle_bytes([("note.txt", b"hello")])
        result = kernel.verify_bundle_bytes(payload)
        self.assertTrue(result["wire"]["ok"])
        self.assertTrue(result["integrity"]["ok"])
        self.assertFalse(result["conformance"]["ok"])
        self.assertFalse(result["ok"])


class HostileInputTests(unittest.TestCase):
    def test_decoder_rejects_parent_escape(self):
        with self.assertRaises(kernel.KernelError):
            kernel.parse(unsafe_payload([("../escape.txt", b"x")]))

    def test_decoder_rejects_absolute_and_windows_paths(self):
        for path in ("/tmp/escape", "C:/escape.txt", "a\\b.txt", "a//b.txt"):
            with self.subTest(path=path):
                with self.assertRaises(kernel.KernelError):
                    kernel.parse(unsafe_payload([(path, b"x")]))

    def test_decoder_rejects_duplicate_paths(self):
        with self.assertRaises(kernel.KernelError):
            kernel.parse(unsafe_payload([("same.txt", b"a"), ("same.txt", b"b")]))

    def test_decoder_rejects_trailing_bytes(self):
        with self.assertRaises(kernel.KernelError):
            kernel.parse(kernel.build_bundle_bytes(orientation_files()) + b"junk")

    def test_decoder_rejects_truncated_varint(self):
        with self.assertRaises(kernel.KernelError):
            kernel.parse(b"RSB1\x05\x80")

    def test_resource_limit_blocks_large_inflation(self):
        payload = kernel.build_bundle_bytes(orientation_files() + [("big.bin", b"A" * (1024 * 1024))])
        limits = kernel.Limits(
            max_bundle_bytes=8 * 1024 * 1024,
            max_files=100,
            max_total_raw_bytes=64 * 1024,
            max_file_bytes=64 * 1024,
            max_path_bytes=4096,
        )
        with self.assertRaises(kernel.KernelError):
            kernel.parse(payload, limits)

    def test_extract_refuses_nonempty_destination(self):
        view = kernel.parse(kernel.build_bundle_bytes(orientation_files()))
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "out"
            dest.mkdir()
            (dest / "existing.txt").write_text("do not overwrite")
            with self.assertRaises(kernel.KernelError):
                kernel.extract_view(view, dest)


class SourceBoundaryTests(unittest.TestCase):
    def test_selected_symlink_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            root.mkdir()
            outside = Path(td) / "secret.txt"
            outside.write_text("outside")
            try:
                (root / "link.txt").symlink_to(outside)
            except OSError:
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(kernel.SourceError):
                kernel.scan_source(root)

    def test_selected_symlink_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            root.mkdir()
            outside = Path(td) / "outside"
            outside.mkdir()
            (outside / "secret.txt").write_text("outside")
            try:
                (root / "linked").symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(kernel.SourceError):
                kernel.scan_source(root)

    def test_cli_default_exclusions_are_visible_in_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            root.mkdir()
            for path, blob in orientation_files():
                (root / path).write_bytes(blob)
            (root / ".DS_Store").write_bytes(b"junk")
            out = Path(td) / "bundle.oxb"
            report = Path(td) / "report.json"
            cp = subprocess.run(
                [sys.executable, "-m", "oxbow.bundle.cli", "build", str(root), "-o", str(out), "--report", str(report)],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            doc = json.loads(report.read_text())
            self.assertEqual(doc["excluded_files"], 1)
            self.assertEqual(doc["excluded"][0]["path"], ".DS_Store")

    def test_ship_emits_inert_oxb_and_verifies(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            root.mkdir()
            for path, blob in orientation_files():
                (root / path).write_bytes(blob)
            (root / "work.txt").write_text("synthetic work")
            out = Path(td) / "release.oxb"
            cp = subprocess.run(
                [sys.executable, "-m", "oxbow.bundle.ship", str(root), "-o", str(out)],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual(out.read_bytes()[:4], kernel.MAGIC)
            self.assertTrue(kernel.verify_bundle_bytes(out.read_bytes())["ok"])

    def test_cli_rejects_output_inside_source_tree(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            root.mkdir()
            for path, blob in orientation_files():
                (root / path).write_bytes(blob)
            out = root / "self.oxb"
            cp = subprocess.run(
                [sys.executable, "-m", "oxbow.bundle.cli", "build", str(root), "-o", str(out)],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertNotEqual(cp.returncode, 0)
            self.assertIn("outside the source tree", cp.stderr)


class SignatureLayerTests(unittest.TestCase):
    def test_cli_reports_authenticity_separately(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "src"
            root.mkdir()
            for path, blob in orientation_files():
                (root / path).write_bytes(blob)
            oxb = Path(td) / "x.oxb"
            key = Path(td) / "key.json"
            run = lambda *args: subprocess.run(
                [sys.executable, "-m", "oxbow.bundle.cli", *args],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertEqual(run("build", str(root), "-o", str(oxb)).returncode, 0)
            self.assertEqual(run("keygen", "-o", str(key)).returncode, 0)
            self.assertEqual(run("sign", str(oxb), "--key", str(key)).returncode, 0)
            r = run("verify", str(oxb), "--sig", str(oxb) + ".sig")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            doc = json.loads(r.stdout)
            self.assertTrue(doc["wire"]["ok"])
            self.assertTrue(doc["integrity"]["ok"])
            self.assertTrue(doc["conformance"]["ok"])
            self.assertTrue(doc["authenticity"]["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
