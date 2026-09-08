import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from oxbow.bundle import kernel
from oxbow.bundle.wrapper import render, write_wrapper

ROOT = Path(__file__).resolve().parents[1]


def files():
    return [
        ("READ_FIRST.md", b"# Read first\n\nSynthetic wrapper fixture.\n"),
        ("BUNDLE_LAYOUT.md", b"# Layout\n\nSynthetic.\n"),
        ("START_HERE.md", b"# Start\n\nOpen work/state.txt.\n"),
        ("work/state.txt", b"state=ready\n"),
        ("binary/blob.bin", bytes(range(256)) * 4),
    ]


class WrapperTests(unittest.TestCase):
    def test_render_is_deterministic(self):
        payload = kernel.build_bundle_bytes(files())
        a = render(payload, name="demo")
        b = render(payload, name="demo")
        self.assertEqual(a, b)
        self.assertIn("_PAYLOAD_SHA256 = '%s'" % hashlib.sha256(payload).hexdigest(), a)

    def test_standalone_wrapper_full_flow(self):
        payload = kernel.build_bundle_bytes(files())
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            wrapper = td / "demo.oxb.py"
            write_wrapper(payload, wrapper, name="demo", self_check=True)

            cp = subprocess.run([sys.executable, str(wrapper), "--verify"], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            result = json.loads(cp.stdout)
            self.assertTrue(result["ok"])
            self.assertTrue(result["wrapper"]["ok"])
            self.assertTrue(result["integrity"]["ok"])

            cp = subprocess.run([sys.executable, str(wrapper), "--read-first"], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0)
            self.assertIn("Synthetic wrapper fixture", cp.stdout)

            cp = subprocess.run([sys.executable, str(wrapper), "--list"], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0)
            self.assertIn("binary/blob.bin", cp.stdout)

            cp = subprocess.run([sys.executable, str(wrapper), "--doc", "work/state.txt"], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0)
            self.assertEqual(cp.stdout, "state=ready\n")

            raw = td / "twin.oxb"
            cp = subprocess.run([sys.executable, str(wrapper), "--payload-out", str(raw)], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual(raw.read_bytes(), payload)

            out = td / "extract"
            cp = subprocess.run([sys.executable, str(wrapper), "--extract", str(out)], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual((out / "binary/blob.bin").read_bytes(), bytes(range(256)) * 4)

    def test_ship_directly_to_wrapper(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "src"
            src.mkdir()
            for path, blob in files():
                p = src / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(blob)
            wrapper = td / "project.oxb.py"
            twin = td / "project.oxb"
            cp = subprocess.run(
                [sys.executable, "-m", "oxbow.cli", "ship", str(src), "-o", str(wrapper), "--data-out", str(twin)],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue(wrapper.exists())
            self.assertTrue(twin.exists())
            self.assertTrue(kernel.verify_bundle_bytes(twin.read_bytes())["ok"])
            info = subprocess.run([sys.executable, str(wrapper), "--info"], capture_output=True, text=True)
            self.assertEqual(info.returncode, 0, info.stderr)
            self.assertEqual(json.loads(info.stdout)["name"], "project")

    def test_lower_level_build_then_wrap_cli(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            src = td / "src"
            src.mkdir()
            for path, blob in files():
                p = src / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(blob)
            payload = td / "two-step.oxb"
            wrapper = td / "two-step.oxb.py"
            build = subprocess.run(
                [sys.executable, "-m", "oxbow.bundle.cli", "build", str(src), "-o", str(payload)],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            wrap = subprocess.run(
                [sys.executable, "-m", "oxbow.bundle.cli", "wrap", str(payload), "-o", str(wrapper), "--name", "two-step"],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertEqual(wrap.returncode, 0, wrap.stdout + wrap.stderr)
            self.assertTrue(wrapper.exists())
            cp = subprocess.run([sys.executable, str(wrapper), "--verify"], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertTrue(json.loads(cp.stdout)["ok"])

    def test_trusted_cli_reads_wrapper_without_executing_it(self):
        payload = kernel.build_bundle_bytes(files())
        with tempfile.TemporaryDirectory() as td:
            wrapper = Path(td) / "safe.oxb.py"
            write_wrapper(payload, wrapper, self_check=False)
            cp = subprocess.run(
                [sys.executable, "-m", "oxbow.bundle.cli", "verify", str(wrapper)],
                cwd=str(ROOT), capture_output=True, text=True,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            doc = json.loads(cp.stdout)
            self.assertTrue(doc["ok"])
            self.assertFalse(doc["wrapper_source"]["executed"])
            self.assertFalse(doc["wrapper_source"]["authenticated"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
