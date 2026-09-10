#!/usr/bin/env python3
"""`oxbow witness ...` — portable append-only session records."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from oxbow.witness.stream import Unlawful as StreamUnlawful, append_packet, new_stream, rebuild_index, validate_stream
from oxbow.witness.validate import Invalid, Unlawful, V2_FORMAT, check_boundaries, packet_version, validate_packet

HERE = Path(__file__).resolve().parent
V1_SCHEMA = HERE / "schemas" / "portable_packet.schema.json"
V2_SCHEMA = HERE / "schemas" / "portable_packet_v2.schema.json"

DRAFT_PREAMBLE_V1 = """# Write one Oxbow Witness packet for the work session you just participated in

Return one JSON object and nothing else.

Witness is a handoff record, not a verdict. It checks form and declared provenance boundaries, not factual truth.

Rules:
1. `source.description` reports what happened or what material was provided. Put interpretations in `reads`.
2. `overhang` lists what remains genuinely open. Use an empty list only if nothing remains open.
3. `self_witness.drafter_was_party` states whether you participated in the session. If true, name a real limitation in `caveat`.
4. `third_party_context.present` is true if the record contains material about or from a person who is not the operator/drafter. If true, use `handling_note` to flag review, redaction, consent/public-source status, or uncertainty. Do not fabricate consent.
5. Do not compare this session to other Witness records. Cross-session analysis belongs outside the append-only stream.
6. Use a packet id beginning `pkt_`, for example `pkt_2026-09-08_release_review`.
"""

DRAFT_PREAMBLE_V2 = """# Write one Oxbow Witness v2 packet for the work session you just participated in

Return one JSON object and nothing else.

Witness is a handoff record, not a verdict. It checks form and declared provenance boundaries, not factual truth or evidential sufficiency.

Core rules:
1. `source.description` reports what happened or what material was provided. Put diagnoses, implications, hypotheses, and conclusions in `reads`.
2. Every read has a `status`, `scope`, and at least one `basis` reference. A basis records what the drafter points to; Oxbow does not certify that the referent supports the claim.
3. Read status is one of: `observation`, `interpretation`, `candidate`, `promoted`, `abstention`. `promoted` means promoted by this workstream, not certified true by Oxbow.
4. Read scope is one of: `local`, `cross_packet`, `population`. Candidate/promoted reads and cross-packet/population reads need an explicit `boundary`.
5. Basis grammar: `source`, `source:<anchor_id>`, `packet:<packet_id>`, `packet:<packet_id>#<read_id>`, or `external:<opaque referent>`.
6. `source.coverage` is one of: `full`, `selective`, `reconstructed`, `mixed`. Here `full` means full declared source for this Witness, not omniscient coverage of reality. Reconstructed/mixed coverage needs a provenance note explaining the reconstruction.
7. `overhang` preserves genuinely unresolved work. Status is one of: `open`, `blocked`, `deferred`, `watch`.
8. Use an `abstention` read when the material does not earn a conclusion. Preserve important contradictory or rare evidence under `audit.preserved_exceptions` when useful.
9. `weather`, `audit`, and `lineage` are optional. Omit them when they carry no information.
10. `self_witness.drafter_was_party` states whether you participated in the session. If true, name a real limitation in `caveat`.
11. `third_party_context.present` is true if the record contains material about or from a person who is not the operator/drafter. If true, use `handling_note` to state only the review/redaction/consent/public-source status actually known. Do not fabricate permission.
12. Cross-packet reads are lawful only when the earlier packet content is actually available to the drafter. Cite the earlier packet in `basis`. Packet IDs by themselves are navigation, not evidence.
13. Corrections append. Do not rewrite earlier Witness records.
14. Use a packet id beginning `pkt_`, for example `pkt_2026-09-09_release_review`.
"""

DEPTH_GUIDANCE = {
    "quick": """## Draft depth: quick

Keep this small. A concise source, a few typed reads, structured overhang, the packet claim boundary, self-witness, and third-party handling are enough. `basis: [\"source\"]` is valid when finer anchors add no value. Omit anchors, weather, audit, and lineage unless they materially improve the handoff.
""",
    "standard": """## Draft depth: standard

Use source anchors for consequential claims when a useful local referent exists. Prefer specific basis references over `source` when they improve catchability. Include weather only when the condition of the work matters. Use lineage when this packet continues, corrects, or materially relates to an earlier available packet. Preserve exceptions and explicit abstentions when they prevent overclaiming.
""",
    "deep": """## Draft depth: deep

Use the richer optional structure when the session is long, consequential, recursive, or cross-packet. Favor explicit source anchors, multiple basis references, cross-packet reads, lineage, preserved exceptions, uncertainty notes, and population abstentions where warranted. Richness should come from populating this stable packet format, not inventing a new dialect.
""",
}


def _v2_skeleton(depth):
    base = {
        "format": V2_FORMAT,
        "packet_id": "pkt_<portable_label>",
        "packet_type": "<free genre label>",
        "source": {
            "description": "<factual report of what happened or what material was provided>",
            "coverage": "full",
        },
        "reads": [
            {
                "read_id": "r1",
                "name": "<explicit read name>",
                "status": "interpretation",
                "scope": "local",
                "value": "<interpretation or structured value>",
                "basis": ["source"],
            }
        ],
        "overhang": [
            {
                "overhang_id": "o1",
                "item": "<genuinely unresolved work>",
                "status": "open",
            }
        ],
        "claim_boundary": "<what this packet does not establish>",
        "self_witness": {
            "drafter_was_party": True,
            "caveat": "<real limitation created by the drafter's position>",
        },
        "third_party_context": {
            "present": False,
            "handling_note": "none",
        },
    }
    if depth in ("standard", "deep"):
        base["source"]["provenance_notes"] = ["<important provenance note when needed>"]
        base["source"]["anchors"] = [
            {
                "anchor_id": "a1",
                "ref": "<turn, file, section, artifact, or other local pointer>",
                "description": "<what this anchor points to>",
            }
        ]
        base["reads"][0]["basis"] = ["source:a1"]
        base["reads"][0]["boundary"] = "<optional for local interpretation; required for stronger status/scope>"
        base["reads"][0]["notes"] = ["<optional qualification>"]
        base["weather"] = [
            {
                "label": "<compact condition label>",
                "basis": ["source:a1"],
                "reason": "<why the condition matters to this record>",
            }
        ]
        base["overhang"][0]["next_test"] = "<optional next discriminating action>"
        base["lineage"] = {
            "parents": [],
            "corrects": [],
            "related": [],
            "what_this_adds": [],
        }
    if depth == "deep":
        base["audit"] = {
            "uncertainty_notes": ["<uncertainty worth preserving>"],
            "preserved_exceptions": [
                {
                    "description": "<important evidence that does not fit the dominant read>",
                    "basis": ["source:a1"],
                }
            ],
            "flags": [
                {
                    "code": "<open flag code>",
                    "severity": "caution",
                    "note": "<why this flag matters>",
                }
            ],
        }
    return base


def _schema(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _builtin_schema_path(version):
    return V1_SCHEMA if version == "v1" else V2_SCHEMA


def _write_json(path: Path, doc: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cmd_init(a):
    dest = Path(a.stream)
    if dest.exists():
        print("error: stream already exists: %s" % dest, file=sys.stderr)
        return 2
    doc = new_stream(a.name)
    _write_json(dest, doc)
    print("initialized witness stream -> %s" % dest)
    return 0


def _stream_prompt_state(stream, *, allow_cross_packet):
    if not allow_cross_packet:
        return (
            "\n## Stream state (form only)\n\n"
            "Existing record count: %d. Do not compare this session to prior records.\n"
            % len(stream["records"])
        )

    pids = [
        (rec.get("packet") or {}).get("packet_id")
        for rec in stream["records"][-20:]
        if (rec.get("packet") or {}).get("packet_id")
    ]
    lines = [
        "\n## Stream state (lineage navigation only)\n",
        "Existing record count: %d." % len(stream["records"]),
    ]
    if pids:
        lines.append("Recent packet IDs (most recent 20 at most):")
        lines.extend("- %s" % pid for pid in pids)
    else:
        lines.append("No earlier packet IDs are present.")
    lines.append(
        "These IDs establish possible lineage targets only. Do not infer facts from a packet name or its existence. "
        "Use a packet in `basis` only if its actual content was available to you."
    )
    return "\n".join(lines) + "\n"


def cmd_draft(a):
    if a.schema:
        parts = [
            DRAFT_PREAMBLE_V1,
            "\n## Custom required JSON shape\n\n```json\n" + json.dumps(_schema(a.schema), indent=2) + "\n```\n",
        ]
        allow_cross_packet = False
    elif a.packet_version == "v1":
        if a.depth != "standard":
            print("error: --depth applies to packet v2 only", file=sys.stderr)
            return 2
        parts = [
            DRAFT_PREAMBLE_V1,
            "\n## Required JSON shape\n\n```json\n" + json.dumps(_schema(V1_SCHEMA), indent=2) + "\n```\n",
        ]
        allow_cross_packet = False
    else:
        parts = [
            DRAFT_PREAMBLE_V2,
            DEPTH_GUIDANCE[a.depth],
            "\n## Packet skeleton\n\nOptional sections shown by this depth may be omitted when they carry no information.\n\n```json\n"
            + json.dumps(_v2_skeleton(a.depth), indent=2)
            + "\n```\n",
        ]
        allow_cross_packet = True

    if a.stream:
        st = json.loads(Path(a.stream).read_text(encoding="utf-8"))
        validate_stream(st)
        parts.append(_stream_prompt_state(st, allow_cross_packet=allow_cross_packet))
    out = "\n".join(parts)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        print("wrote draft prompt -> %s" % a.out)
    else:
        sys.stdout.write(out)
    return 0


def _validate(packet, schema_path=None):
    if schema_path:
        schema = _schema(schema_path)
    else:
        version = packet_version(packet)
        schema = _schema(_builtin_schema_path(version))
    validate_packet(packet, schema)
    return check_boundaries(packet)


def cmd_validate(a):
    packet = json.loads(Path(a.packet).read_text(encoding="utf-8"))
    try:
        warnings = _validate(packet, a.schema)
    except (Invalid, Unlawful) as exc:
        print("witness: INVALID — %s" % exc)
        return 1
    print("schema: ok")
    print("boundaries: ok" if not warnings else "boundaries: ok, with warnings")
    for warning in warnings:
        print("  ! %s" % warning)
    print("scope: form/provenance checks only; factual truth is not verified")
    return 0


def cmd_append(a):
    packet = json.loads(Path(a.packet).read_text(encoding="utf-8"))
    stream_path = Path(a.stream)
    stream = json.loads(stream_path.read_text(encoding="utf-8"))
    try:
        warnings = _validate(packet, a.schema)
        out = append_packet(stream, packet)
    except (Invalid, Unlawful, StreamUnlawful) as exc:
        print("append REFUSED — %s" % exc)
        return 1
    dest = Path(a.out) if a.out else stream_path
    if a.out and dest.exists():
        print("error: output already exists: %s" % dest, file=sys.stderr)
        return 2
    _write_json(dest, out)
    rec = out["records"][-1]
    print("appended %s as ingest_order %d -> %s" % (rec["record_id"], rec["ingest_order"], dest))
    for warning in warnings:
        print("  ! %s" % warning)
    return 0


def cmd_rebuild(a):
    p = Path(a.stream)
    stream = json.loads(p.read_text(encoding="utf-8"))
    try:
        validate_stream(stream)
    except StreamUnlawful as exc:
        print("rebuild REFUSED — %s" % exc)
        return 1
    old = stream.get("derived_index")
    new = rebuild_index(stream)
    stream["derived_index"] = new
    dest = Path(a.out) if a.out else p
    if a.out and dest.exists():
        print("error: output already exists: %s" % dest, file=sys.stderr)
        return 2
    _write_json(dest, stream)
    print("rebuilt derived_index from %d source record(s) -> %s" % (len(stream["records"]), dest))
    print("  changed" if old != new else "  already current")
    return 0


def cmd_show(a):
    stream = json.loads(Path(a.stream).read_text(encoding="utf-8"))
    try:
        validate_stream(stream)
    except StreamUnlawful as exc:
        print("stream INVALID — %s" % exc)
        return 1
    current = rebuild_index(stream)
    summary = {
        "format": stream.get("format"),
        "stream_id": stream.get("stream_id"),
        "name": stream.get("name"),
        "records": len(stream["records"]),
        "derived_index_current": current == stream.get("derived_index"),
        "open_overhang_records": len(current["open_overhang_by_record"]),
        "third_party_records": len(current["records_with_third_party_context"]),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oxbow witness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    i = sub.add_parser("init", help="create an empty append-only witness stream")
    i.add_argument("--stream", required=True)
    i.add_argument("--name", default="handoff")
    i.set_defaults(fn=cmd_init)

    d = sub.add_parser("draft", help="emit a prompt asking the current model for one packet")
    d.add_argument("--out")
    d.add_argument("--stream")
    d.add_argument("--schema", help="use a custom packet schema instead of the built-in v1/v2 contract")
    d.add_argument("--packet-version", choices=("v1", "v2"), default="v2")
    d.add_argument("--depth", choices=("quick", "standard", "deep"), default="standard")
    d.set_defaults(fn=cmd_draft)

    v = sub.add_parser("validate", help="check one packet's shape and declared boundaries")
    v.add_argument("packet")
    v.add_argument("--schema", help="validate against a custom packet schema")
    v.set_defaults(fn=cmd_validate)

    p = sub.add_parser("append", help="validate and append one packet without rewriting prior records")
    p.add_argument("packet")
    p.add_argument("--stream", required=True)
    p.add_argument("--out")
    p.add_argument("--schema", help="validate against a custom packet schema")
    p.set_defaults(fn=cmd_append)

    r = sub.add_parser("rebuild", help="recompute the derived index from source records")
    r.add_argument("--stream", required=True)
    r.add_argument("--out")
    r.set_defaults(fn=cmd_rebuild)

    s = sub.add_parser("show", help="summarize a witness stream without printing its contents")
    s.add_argument("--stream", required=True)
    s.set_defaults(fn=cmd_show)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
