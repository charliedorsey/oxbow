import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from oxbow.witness.stream import Unlawful as StreamUnlawful, append_packet, new_stream, rebuild_index, validate_stream
from oxbow.witness.validate import Invalid, Unlawful, check_boundaries, packet_version, validate_packet

ROOT = Path(__file__).resolve().parents[1]
V1_SCHEMA = json.loads((ROOT / "src/oxbow/witness/schemas/portable_packet.schema.json").read_text())
V2_SCHEMA = json.loads((ROOT / "src/oxbow/witness/schemas/portable_packet_v2.schema.json").read_text())
ENV = dict(os.environ)


def v1_packet(**updates):
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


def v2_packet(packet_id="pkt_2026-01-02_synthetic", **updates):
    p = {
        "format": "oxbow-witness-packet-v2",
        "packet_id": packet_id,
        "packet_type": "session",
        "source": {
            "description": "A synthetic task was reviewed and one question remained open.",
            "coverage": "full",
            "anchors": [
                {
                    "anchor_id": "a_task",
                    "ref": "notes/task.md",
                    "description": "The synthetic task note."
                }
            ],
        },
        "reads": [
            {
                "read_id": "r_status",
                "name": "status",
                "status": "interpretation",
                "scope": "local",
                "value": "ready",
                "basis": ["source:a_task"],
            }
        ],
        "overhang": [
            {
                "overhang_id": "o_question",
                "item": "Resolve the synthetic open question.",
                "status": "open",
                "next_test": "Run the synthetic discriminator."
            }
        ],
        "claim_boundary": "This synthetic packet does not establish behavior outside the test fixture.",
        "self_witness": {
            "drafter_was_party": True,
            "caveat": "The synthetic drafter observed only this one test session."
        },
        "third_party_context": {"present": False, "handling_note": "none"},
    }
    p.update(updates)
    return p


def validate_v2(p):
    validate_packet(p, V2_SCHEMA)
    return check_boundaries(p)


def run_cli(*args, cwd=ROOT):
    return subprocess.run(
        [sys.executable, "-m", "oxbow.cli", *args],
        cwd=str(cwd), env=ENV, capture_output=True, text=True,
    )


class PublicWitnessTests(unittest.TestCase):
    def test_v1_packet_validates_and_appends_unchanged(self):
        p = v1_packet()
        self.assertEqual(packet_version(p), "v1")
        validate_packet(p, V1_SCHEMA)
        self.assertEqual(check_boundaries(p), [])
        stream = new_stream("synthetic", stream_id="wtn_synthetic")
        out = append_packet(stream, p)
        self.assertEqual(len(out["records"]), 1)
        self.assertEqual(out["records"][0]["record_id"], "rec_2026-01-01_synthetic")
        self.assertEqual(out["records"][0]["packet"], p)
        self.assertEqual(out["derived_index"], rebuild_index(out))

    def test_v2_packet_validates_and_appends(self):
        p = v2_packet()
        self.assertEqual(packet_version(p), "v2")
        self.assertEqual(validate_v2(p), [])
        out = append_packet(new_stream("synthetic", stream_id="wtn_synthetic"), p)
        self.assertEqual(out["records"][0]["packet"], p)
        self.assertEqual(
            out["derived_index"]["open_overhang_by_record"]["rec_2026-01-02_synthetic"],
            ["Resolve the synthetic open question."],
        )

    def test_append_does_not_mutate_prior_stream(self):
        stream = new_stream("synthetic", stream_id="wtn_synthetic")
        before = copy.deepcopy(stream)
        append_packet(stream, v2_packet())
        self.assertEqual(stream, before)

    def test_duplicate_packet_refused(self):
        stream = append_packet(new_stream("synthetic"), v2_packet())
        with self.assertRaises(StreamUnlawful):
            append_packet(stream, v2_packet())

    def test_packet_id_namespace_enforced(self):
        p = v1_packet(packet_id="seg_2026-01-01_bad")
        validate_packet(p, V1_SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

    def test_unknown_explicit_packet_format_refused(self):
        p = v2_packet(format="oxbow-witness-packet-v9")
        with self.assertRaises(Unlawful):
            packet_version(p)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

    def test_third_party_context_requires_handling_note(self):
        for p, schema in (
            (v1_packet(third_party_context={"present": True, "handling_note": ""}), V1_SCHEMA),
            (v2_packet(third_party_context={"present": True, "handling_note": ""}), V2_SCHEMA),
        ):
            validate_packet(p, schema)
            with self.assertRaises(Unlawful):
                check_boundaries(p)

    def test_self_witness_party_requires_caveat(self):
        for p, schema in (
            (v1_packet(self_witness={"drafter_was_party": True, "caveat": ""}), V1_SCHEMA),
            (v2_packet(self_witness={"drafter_was_party": True, "caveat": ""}), V2_SCHEMA),
        ):
            validate_packet(p, schema)
            with self.assertRaises(Unlawful):
                check_boundaries(p)

    def test_source_inference_is_warning_not_truth_judgment(self):
        p = v2_packet(source={
            "description": "The task passed, therefore the design is correct.",
            "coverage": "full",
            "anchors": [],
        })
        p["reads"][0]["basis"] = ["source"]
        validate_packet(p, V2_SCHEMA)
        warnings = check_boundaries(p)
        self.assertTrue(any("interpretation" in w for w in warnings))

    def test_schema_checker_enforces_v2_const_enum_minimums_and_patterns(self):
        bad = v2_packet(format="wrong")
        with self.assertRaises(Invalid):
            validate_packet(bad, V2_SCHEMA)

        bad = v2_packet()
        bad["source"]["coverage"] = "omniscient"
        with self.assertRaises(Invalid):
            validate_packet(bad, V2_SCHEMA)

        bad = v2_packet()
        bad["reads"][0]["basis"] = []
        with self.assertRaises(Invalid):
            validate_packet(bad, V2_SCHEMA)

        bad = v2_packet(packet_id="pkt_x")
        with self.assertRaises(Invalid):
            validate_packet(bad, V2_SCHEMA)

        bad = v2_packet(packet_type="")
        with self.assertRaises(Invalid):
            validate_packet(bad, V2_SCHEMA)

    def test_duplicate_local_ids_refused(self):
        p = v2_packet()
        p["source"]["anchors"].append(copy.deepcopy(p["source"]["anchors"][0]))
        validate_packet(p, V2_SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

        p = v2_packet()
        p["reads"].append(copy.deepcopy(p["reads"][0]))
        validate_packet(p, V2_SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

        p = v2_packet()
        p["overhang"].append(copy.deepcopy(p["overhang"][0]))
        validate_packet(p, V2_SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

    def test_missing_source_anchor_refused(self):
        p = v2_packet()
        p["reads"][0]["basis"] = ["source:missing"]
        validate_packet(p, V2_SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

    def test_invalid_basis_grammar_refused(self):
        p = v2_packet()
        p["reads"][0]["basis"] = ["whatever:this-is"]
        validate_packet(p, V2_SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

    def test_stronger_read_status_or_scope_requires_boundary(self):
        cases = [
            ("candidate", "local"),
            ("promoted", "local"),
            ("interpretation", "population"),
        ]
        for status, scope in cases:
            with self.subTest(status=status, scope=scope):
                p = v2_packet()
                p["reads"][0]["status"] = status
                p["reads"][0]["scope"] = scope
                validate_packet(p, V2_SCHEMA)
                with self.assertRaises(Unlawful):
                    check_boundaries(p)
                p["reads"][0]["boundary"] = "The claim stops at the declared synthetic material."
                self.assertEqual(check_boundaries(p), [])

    def test_cross_packet_scope_requires_packet_basis(self):
        p = v2_packet()
        p["reads"][0].update({
            "scope": "cross_packet",
            "boundary": "Only the cited records are in scope.",
            "basis": ["source:a_task"],
        })
        validate_packet(p, V2_SCHEMA)
        with self.assertRaises(Unlawful):
            check_boundaries(p)

    def test_reconstructed_and_mixed_coverage_require_provenance(self):
        for coverage in ("reconstructed", "mixed"):
            with self.subTest(coverage=coverage):
                p = v2_packet()
                p["source"]["coverage"] = coverage
                validate_packet(p, V2_SCHEMA)
                with self.assertRaises(Unlawful):
                    check_boundaries(p)
                p["source"]["provenance_notes"] = ["Some material was reconstructed from session notes."]
                self.assertEqual(check_boundaries(p), [])

    def test_v2_can_cite_whole_prior_v1_packet(self):
        stream = append_packet(new_stream("synthetic"), v1_packet())
        p = v2_packet()
        p["reads"][0].update({
            "scope": "cross_packet",
            "basis": ["source:a_task", "packet:pkt_2026-01-01_synthetic"],
            "boundary": "Only the current source and cited prior packet are in scope.",
        })
        validate_v2(p)
        out = append_packet(stream, p)
        validate_stream(out)
        self.assertEqual(len(out["records"]), 2)

    def test_v2_can_cite_prior_v2_read(self):
        first = v2_packet(packet_id="pkt_first")
        first["overhang"] = []
        validate_v2(first)
        stream = append_packet(new_stream("synthetic"), first)

        second = v2_packet(packet_id="pkt_second")
        second["reads"][0].update({
            "scope": "cross_packet",
            "basis": ["packet:pkt_first#r_status"],
            "boundary": "Only the cited prior read is combined here.",
        })
        validate_v2(second)
        out = append_packet(stream, second)
        validate_stream(out)
        self.assertEqual(len(out["records"]), 2)

    def test_missing_or_future_packet_basis_refused(self):
        p = v2_packet()
        p["reads"][0].update({
            "scope": "cross_packet",
            "basis": ["packet:pkt_not_here"],
            "boundary": "Only the cited packet would be in scope.",
        })
        validate_v2(p)
        with self.assertRaises(StreamUnlawful):
            append_packet(new_stream("synthetic"), p)

    def test_missing_read_ref_and_read_ref_to_v1_refused(self):
        first = v2_packet(packet_id="pkt_first")
        validate_v2(first)
        stream = append_packet(new_stream("synthetic"), first)
        second = v2_packet(packet_id="pkt_second")
        second["reads"][0].update({
            "scope": "cross_packet",
            "basis": ["packet:pkt_first#missing"],
            "boundary": "Only the cited prior read would be in scope.",
        })
        validate_v2(second)
        with self.assertRaises(StreamUnlawful):
            append_packet(stream, second)

        stream = append_packet(new_stream("synthetic"), v1_packet())
        second["reads"][0]["basis"] = ["packet:pkt_2026-01-01_synthetic#status"]
        with self.assertRaises(StreamUnlawful):
            append_packet(stream, second)

    def test_lineage_resolves_backward_and_correction_does_not_rewrite_parent(self):
        first = v2_packet(packet_id="pkt_first")
        validate_v2(first)
        stream = append_packet(new_stream("synthetic"), first)
        before = copy.deepcopy(stream["records"][0])

        second = v2_packet(packet_id="pkt_second")
        second["lineage"] = {
            "parents": ["pkt_first"],
            "corrects": ["pkt_first"],
            "related": [],
            "what_this_adds": ["A synthetic correction."],
        }
        validate_v2(second)
        out = append_packet(stream, second)
        self.assertEqual(out["records"][0], before)
        validate_stream(out)

        bad = v2_packet(packet_id="pkt_bad")
        bad["lineage"] = {
            "parents": ["pkt_future"],
            "corrects": [],
            "related": [],
            "what_this_adds": [],
        }
        validate_v2(bad)
        with self.assertRaises(StreamUnlawful):
            append_packet(out, bad)

    def test_record_format_is_enforced(self):
        stream = append_packet(new_stream("synthetic"), v1_packet())
        stream["records"][0]["format"] = "not-a-witness-record"
        with self.assertRaises(StreamUnlawful):
            validate_stream(stream)

    def test_mixed_v1_v2_stream_keeps_plain_text_derived_index(self):
        stream = append_packet(new_stream("synthetic"), v1_packet())
        stream = append_packet(stream, v2_packet())
        validate_stream(stream)
        idx = rebuild_index(stream)
        self.assertEqual(idx, stream["derived_index"])
        self.assertEqual(
            idx["open_overhang_by_record"]["rec_2026-01-02_synthetic"],
            ["Resolve the synthetic open question."],
        )
        self.assertTrue(all(isinstance(x, str) for x in idx["open_overhang_by_record"]["rec_2026-01-02_synthetic"]))

    def test_derived_index_staleness_is_detectable(self):
        stream = append_packet(new_stream("synthetic"), v2_packet())
        stream["derived_index"]["record_count"] = 99
        validate_stream(stream)
        self.assertNotEqual(stream["derived_index"], rebuild_index(stream))

    def test_draft_depths_are_distinct_and_all_request_v2(self):
        outputs = {}
        for depth in ("quick", "standard", "deep"):
            cp = run_cli("witness", "draft", "--depth", depth)
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertIn('"format": "oxbow-witness-packet-v2"', cp.stdout)
            self.assertIn("Draft depth: %s" % depth, cp.stdout)
            outputs[depth] = cp.stdout
        self.assertNotEqual(outputs["quick"], outputs["standard"])
        self.assertNotEqual(outputs["standard"], outputs["deep"])
        self.assertNotIn('"audit"', outputs["quick"])
        self.assertIn('"audit"', outputs["deep"])

    def test_v2_draft_stream_state_lists_recent_packet_ids_as_navigation_only(self):
        with tempfile.TemporaryDirectory() as td:
            stream = append_packet(new_stream("synthetic"), v1_packet())
            path = Path(td) / "stream.json"
            path.write_text(json.dumps(stream))
            cp = run_cli("witness", "draft", "--stream", str(path))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertIn("pkt_2026-01-01_synthetic", cp.stdout)
            self.assertIn("lineage targets only", cp.stdout)
            self.assertIn("Do not infer facts from a packet name", cp.stdout)

    def test_legacy_v1_draft_remains_available(self):
        cp = run_cli("witness", "draft", "--packet-version", "v1")
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertIn('"title": "oxbow_witness_packet_v1"', cp.stdout)
        self.assertNotIn("oxbow-witness-packet-v2", cp.stdout)
        cp = run_cli("witness", "draft", "--packet-version", "v1", "--depth", "deep")
        self.assertEqual(cp.returncode, 2)

    def test_cli_auto_detects_v2_for_validate_and_append(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            packet_path = td / "packet.json"
            packet_path.write_text(json.dumps(v2_packet()))
            stream_path = td / "stream.json"
            stream_path.write_text(json.dumps(new_stream("synthetic")))

            cp = run_cli("witness", "validate", str(packet_path))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            self.assertIn("schema: ok", cp.stdout)

            cp = run_cli("witness", "append", str(packet_path), "--stream", str(stream_path))
            self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
            out = json.loads(stream_path.read_text())
            self.assertEqual(out["records"][0]["packet"]["format"], "oxbow-witness-packet-v2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
