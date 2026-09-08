import copy
import json
import tempfile
import unittest
from pathlib import Path

from oxbow.witness.stream import Unlawful as StreamUnlawful, append_packet, new_stream, rebuild_index, validate_stream
from oxbow.witness.validate import Invalid, Unlawful, check_boundaries, validate_packet

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "src/oxbow/witness/schemas/portable_packet.schema.json").read_text())


def packet(**updates):
    p = {
        "packet_id": "pkt_2026-01-01_synthetic",
        "packet_type": "session",
        "source": {"description": "A synthetic task was reviewed and one question remained open."},
        "reads": [{"name": "status", "value": "ready"}],
        "overhang": ["Resolve the synthetic open question."],
        "self_witness": {
            "drafter_was_party": True,
            "caveat": "The synthetic drafter observed only this one test session."
        },
        "third_party_context": {"present": False, "handling_note": "none"},
    }
    p.update(updates)
    return p


class PublicWitnessTests(unittest.TestCase):
    def test_packet_validates_and_appends(self):
        p = packet()
        validate_packet(p, SCHEMA)
        self.assertEqual(check_boundaries(p), [])
        stream = new_stream("synthetic", stream_id="wtn_synthetic")
        out = append_packet(stream, p)
        self.assertEqual(len(out["records"]), 1)
        self.assertEqual(out["records"][0]["record_id"], "rec_2026-01-01_synthetic")
        self.assertEqual(out["derived_index"], rebuild_index(out))

    def test_append_does_not_mutate_prior_stream(self):
        stream = new_stream("synthetic", stream_id="wtn_synthetic")
        before = copy.deepcopy(stream)
        append_packet(stream, packet())
        self.assertEqual(stream, before)

    def test_duplicate_packet_refused(self):
        stream = append_packet(new_stream("synthetic"), packet())
        with self.assertRaises(StreamUnlawful):
            append_packet(stream, packet())

    def test_packet_id_namespace_enforced(self):
        p = packet(packet_id="seg_2026-01-01_bad")
        validate_packet(p, SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

    def test_third_party_context_requires_handling_note(self):
        p = packet(third_party_context={"present": True, "handling_note": ""})
        validate_packet(p, SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

    def test_self_witness_party_requires_caveat(self):
        p = packet(self_witness={"drafter_was_party": True, "caveat": ""})
        validate_packet(p, SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

    def test_source_inference_is_warning_not_truth_judgment(self):
        p = packet(source={"description": "The task passed, therefore the design is correct."})
        validate_packet(p, SCHEMA)
        warnings = check_boundaries(p)
        self.assertTrue(any("interpretation" in w for w in warnings))

    def test_derived_index_staleness_is_detectable(self):
        stream = append_packet(new_stream("synthetic"), packet())
        stream["derived_index"]["record_count"] = 99
        validate_stream(stream)
        self.assertNotEqual(stream["derived_index"], rebuild_index(stream))


if __name__ == "__main__":
    unittest.main(verbosity=2)
