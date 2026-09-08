import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from oxbow.bundle import kernel

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "v0.1"
ENV = dict(os.environ)


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "oxbow.cli", *args],
        cwd=str(ROOT), env=ENV, capture_output=True, text=True,
    )


class ReleaseFixtureTests(unittest.TestCase):
    def test_checksums_are_frozen(self):
        for line in (FIX / "SHA256SUMS.txt").read_text().splitlines():
            sha, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((FIX / name).read_bytes()).hexdigest(), sha, name)

    def test_valid_v01_payloads_open(self):
        for name in ("tiny-handoff.oxb", "tiny-handoff-signed.oxb", "binary-heavy.oxb"):
            with self.subTest(name=name):
                result = kernel.verify_bundle_bytes((FIX / name).read_bytes())
                self.assertTrue(result["ok"], result)

    def test_v01_wrapper_opens_without_installing_itself(self):
        cp = run("verify", str(FIX / "tiny-handoff.oxb.py"))
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        doc = json.loads(cp.stdout)
        self.assertTrue(doc["ok"])
        self.assertFalse(doc["wrapper_source"]["executed"])

    def test_signed_fixture_passes_act_mode(self):
        pub = (FIX / "TEST_PUBLIC_KEY.txt").read_text().strip()
        cp = run(
            "verify", str(FIX / "tiny-handoff-signed.oxb"),
            "--mode", "act",
            "--sig", str(FIX / "tiny-handoff-signed.oxb.sig"),
            "--pubkey", pub,
        )
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)

    def test_invalid_v01_security_fixtures_stay_rejected(self):
        for name in ("invalid-parent-path.oxb", "invalid-duplicate-path.oxb"):
            with self.subTest(name=name):
                cp = run("verify", str(FIX / name))
                self.assertNotEqual(cp.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
