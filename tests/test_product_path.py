import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from oxbow.project import init_project

ROOT = Path(__file__).resolve().parents[1]
ENV = dict(os.environ)


def run(*args, cwd=ROOT):
    return subprocess.run(
        [sys.executable, "-m", "oxbow.cli", *args],
        cwd=str(cwd), env=ENV, capture_output=True, text=True,
    )


class ProductPathTests(unittest.TestCase):
    def test_init_creates_front_doors_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "handoff"
            written = init_project(root, name="Synthetic test")
            self.assertTrue((root / "READ_FIRST.md").exists())
            self.assertTrue((root / "START_HERE.md").exists())
            self.assertTrue((root / "BUNDLE_LAYOUT.md").exists())
            self.assertTrue((root / "HANDOFF.md").exists())
            self.assertTrue((root / "witness/stream.json").exists())
            self.assertGreaterEqual(len(written), 6)
            with self.assertRaises(ValueError):
                init_project(root, name="Synthetic test")

    def test_tiny_example_full_top_level_flow(self):
        example = ROOT / "examples" / "tiny-handoff"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            wrapper = td / "tiny.oxb.py"
            cp = run("ship", str(example), "-o", str(wrapper))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

            for args in (
                ("verify", str(wrapper)),
                ("info", str(wrapper)),
                ("ls", str(wrapper)),
                ("tour", str(wrapper)),
                ("cat", str(wrapper), "HANDOFF.md"),
            ):
                cp = run(*args)
                self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

            self.assertIn("Tiny relay demo", run("cat", str(wrapper), "HANDOFF.md").stdout)
            self.assertIn("requirements.md", run("ls", str(wrapper)).stdout)
            info = json.loads(run("info", str(wrapper)).stdout)
            self.assertTrue(info["integrity_ok"])
            self.assertTrue(info["conformance_ok"])

            dest = td / "unpacked"
            cp = run("extract", str(wrapper), "-d", str(dest))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertEqual(
                (dest / "data/tasks.txt").read_bytes(),
                (example / "data/tasks.txt").read_bytes(),
            )

    def test_action_mode_requires_signature_and_pinned_key(self):
        example = ROOT / "examples" / "tiny-handoff"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            key = td / "key.json"
            cp = run("bundle", "keygen", "-o", str(key))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            bundle = td / "signed.oxb"
            cp = run("ship", str(example), "-o", str(bundle), "--key", str(key))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            sig = Path(str(bundle) + ".sig")
            pub = json.loads(key.read_text())["public_key"]

            self.assertNotEqual(run("verify", str(bundle), "--mode", "act").returncode, 0)
            self.assertNotEqual(
                run("verify", str(bundle), "--mode", "act", "--sig", str(sig)).returncode,
                0,
            )
            cp = run(
                "verify", str(bundle), "--mode", "act",
                "--sig", str(sig), "--pubkey", pub,
            )
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            doc = json.loads(cp.stdout)
            self.assertTrue(doc["authenticity"]["ok"])

    def test_wrapper_aliases_ls_and_cat(self):
        example = ROOT / "examples" / "tiny-handoff"
        with tempfile.TemporaryDirectory() as td:
            wrapper = Path(td) / "tiny.oxb.py"
            cp = run("ship", str(example), "-o", str(wrapper))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            cp = subprocess.run([sys.executable, str(wrapper), "--ls"], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertIn("HANDOFF.md", cp.stdout)
            cp = subprocess.run([sys.executable, str(wrapper), "--cat", "HANDOFF.md"], capture_output=True, text=True)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertIn("Tiny relay demo", cp.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
