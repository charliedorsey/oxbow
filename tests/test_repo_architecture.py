import os
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepoArchitectureTests(unittest.TestCase):
    def test_no_generic_top_level_python_packages_remain(self):
        for name in ("bundle", "core", "codecs", "witness", "firstlight", "falsify", "gauge"):
            self.assertFalse((ROOT / name).is_dir(), name)

    def test_compat_is_not_under_installable_src_namespace(self):
        self.assertTrue((ROOT / "compat" / "rosetta_v5" / "reference_decoder.py").exists())
        self.assertFalse((ROOT / "src" / "oxbow" / "compat").exists())

    def test_no_inherited_witness_reference_fixture_is_public(self):
        self.assertFalse((ROOT / "src" / "oxbow" / "witness" / "reference").exists())

    def test_no_historical_rosetta_packer_or_specialist_codec_tree(self):
        self.assertFalse((ROOT / "compat" / "rosetta_v5" / "taproot").exists())
        self.assertFalse((ROOT / "compat" / "rosetta_v5" / "codecs").exists())

    def test_firstlight_is_integration_document_only(self):
        files = [p for p in (ROOT / "integrations" / "firstlight").rglob("*") if p.is_file()]
        self.assertEqual([p.name for p in files], ["README.md"])

    def test_public_tree_has_no_private_operator_tokens(self):
        blocked = [
            "Char" + "lie",
            "Dor" + "sey",
            "Power" + "School",
            "Bir" + "die",
            "baby" + "_elm",
            "state of " + "Char" + "lie",
            "\\b" + "C" + "ow" + "\\b",
        ]
        patterns = re.compile("|".join(blocked), re.I)
        hits = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.name == "LICENSE" or ".git" in path.parts:
                continue
            # Prebuilt wrappers contain base85-encoded payload bytes, where an
            # accidental text-token match has no semantic meaning. The prebuilt
            # test suite decodes each payload and applies this privacy check to
            # its actual source content instead.
            if "prebuilt" in path.parts and path.name.endswith(".oxb.py"):
                continue
            # Build backends may materialize legal metadata from LICENSE into
            # generated build/egg-info trees. Those are not canonical source.
            if "build" in path.parts or "dist" in path.parts or any(part.endswith(".egg-info") for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if patterns.search(text):
                hits.append(str(path.relative_to(ROOT)))
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
