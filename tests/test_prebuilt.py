import hashlib
import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from oxbow import __version__
from oxbow.bundle import kernel
from oxbow.bundle.cli import _load_public_payload

ROOT = Path(__file__).resolve().parents[1]
PREBUILT = ROOT / "prebuilt"
ARTIFACTS = {
    "tiny": PREBUILT / "oxbow-tiny.oxb.py",
    "standard": PREBUILT / "oxbow-standard.oxb.py",
    "full": PREBUILT / "oxbow-full.oxb.py",
}


def mapping(profile):
    payload = _load_public_payload(str(ARTIFACTS[profile]))
    return kernel.parse(payload).mapping


class PrebuiltTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.maps = {name: mapping(name) for name in ARTIFACTS}

    def test_all_three_artifacts_and_checksums_exist(self):
        for path in ARTIFACTS.values():
            self.assertTrue(path.is_file(), path)
        sums = PREBUILT / "SHA256SUMS"
        self.assertTrue(sums.is_file())
        expected = {}
        for line in sums.read_text(encoding="ascii").splitlines():
            digest, name = line.split("  ", 1)
            expected[name] = digest
        self.assertEqual(set(expected), {p.name for p in ARTIFACTS.values()})
        for path in ARTIFACTS.values():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected[path.name])

    def test_generator_reproduces_committed_artifacts_byte_for_byte(self):
        cp = subprocess.run(
            [sys.executable, str(ROOT / "tools/build_prebuilt.py"), "--check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn("prebuilt artifacts verified", cp.stdout)

    def test_standalone_and_trusted_nonexecuting_verification(self):
        for name, path in ARTIFACTS.items():
            cp = subprocess.run(
                [sys.executable, str(path), "--verify"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(cp.returncode, 0, "%s: %s%s" % (name, cp.stdout, cp.stderr))
            self.assertTrue(json.loads(cp.stdout)["ok"])

            cp = subprocess.run(
                [sys.executable, "-m", "oxbow.bundle.cli", "verify", str(path)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
            self.assertEqual(cp.returncode, 0, "%s: %s%s" % (name, cp.stdout, cp.stderr))
            doc = json.loads(cp.stdout)
            self.assertTrue(doc["ok"])
            self.assertFalse(doc["wrapper_source"]["executed"])
            self.assertFalse(doc["wrapper_source"]["authenticated"])

    def test_every_profile_identifies_itself_and_current_version(self):
        for name, files in self.maps.items():
            self.assertIn("PREBUILT_PROFILE.md", files)
            note = files["PREBUILT_PROFILE.md"].decode("utf-8")
            self.assertIn("# Oxbow prebuilt: %s" % name, note)
            self.assertIn("Oxbow package version: `%s`" % __version__, note)
            self.assertIn("START_HERE.md", files)
            self.assertIn("READ_FIRST.md", files)
            self.assertIn("BUNDLE_LAYOUT.md", files)

    def test_tiny_profile_is_small_but_has_witness_and_complete_example(self):
        files = self.maps["tiny"]
        self.assertIn("src/oxbow/witness/WITNESS_FORMAT.md", files)
        self.assertIn("src/oxbow/witness/schemas/portable_packet_v2.schema.json", files)
        self.assertIn("examples/tiny-handoff/HANDOFF.md", files)
        self.assertIn("examples/tiny-handoff/witness/stream.json", files)
        self.assertNotIn("src/oxbow/bundle/kernel.py", files)
        self.assertNotIn("tests/test_witness_public.py", files)
        self.assertNotIn("tools/build_prebuilt.py", files)
        self.assertFalse(any(p.startswith("compat/") for p in files))

    def test_standard_profile_has_product_source_without_dev_surface(self):
        files = self.maps["standard"]
        for rel in (
            "README.md",
            "docs/TRUST_MODEL.md",
            "spec/OXB_WIRE_SPEC.md",
            "src/oxbow/bundle/kernel.py",
            "src/oxbow/bundle/wrapper_runtime.py",
            "src/oxbow/witness/schemas/portable_packet_v2.schema.json",
            "examples/tiny-handoff/HANDOFF.md",
            "integrations/firstlight/README.md",
            "pyproject.toml",
        ):
            self.assertIn(rel, files)
        self.assertFalse(any(p.startswith("tests/") for p in files))
        self.assertFalse(any(p.startswith("tools/") for p in files))
        self.assertFalse(any(p.startswith("compat/") for p in files))
        self.assertFalse(any(p.startswith(".github/") for p in files))
        self.assertFalse(any(p.startswith("prebuilt/") for p in files))

    def test_full_profile_is_the_public_repo_without_prebuilt_recursion(self):
        files = self.maps["full"]
        for rel in (
            ".gitattributes",
            ".github/workflows/gate.yml",
            "compat/rosetta_v5/reference_decoder.py",
            "src/oxbow/bundle/kernel.py",
            "tests/test_prebuilt.py",
            "tests/fixtures/v0.1/tiny-handoff.oxb",
            "tools/build_prebuilt.py",
        ):
            self.assertIn(rel, files)
        self.assertFalse(any(p.startswith("prebuilt/") for p in files))

        cp = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            check=True,
            stdout=subprocess.PIPE,
        )
        expected = {
            p.decode("utf-8")
            for p in cp.stdout.split(b"\0")
            if p and not p.decode("utf-8").startswith("prebuilt/")
        }
        # New files created by `git apply` are not in the index until the user
        # runs git add. The generator treats these known patch files as intended
        # tracked source during that bootstrap window too.
        expected.update(
            rel
            for rel in (".gitattributes", "tests/test_prebuilt.py", "tools/build_prebuilt.py")
            if (ROOT / rel).is_file()
        )
        actual = set(files) - {kernel.MANIFEST_PATH, "PREBUILT_PROFILE.md"}
        self.assertEqual(actual, expected)

    def test_decoded_semantic_payloads_have_no_private_operator_tokens(self):
        blocked = [
            "Char" + "lie",
            "Dor" + "sey",
            "Power" + "School",
            "Bir" + "die",
            "baby" + "_elm",
            "state of " + "Char" + "lie",
            "\\b" + "C" + "ow" + "\\b",
        ]
        pattern = re.compile("|".join(blocked), re.I)
        hits = []
        for profile, files in self.maps.items():
            for rel, blob in files.items():
                if rel == "LICENSE":
                    continue
                if rel.endswith(".oxb.py"):
                    # Base85 wrapper text is an encoding surface, not semantic
                    # source. Its embedded payload is covered by the frozen
                    # fixture tests; scan ordinary decoded source here.
                    continue
                try:
                    text = blob.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                if pattern.search(text):
                    hits.append("%s:%s" % (profile, rel))
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
