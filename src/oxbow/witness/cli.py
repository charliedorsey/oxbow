#!/usr/bin/env python3
"""`oxbow witness ...` — portable append-only session records."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from oxbow.witness.stream import Unlawful as StreamUnlawful, append_packet, new_stream, rebuild_index, validate_stream
from oxbow.witness.validate import Invalid, Unlawful, check_boundaries, validate_packet

HERE = Path(__file__).resolve().parent
SCHEMA = HERE / "schemas" / "portable_packet.schema.json"

DRAFT_PREAMBLE = """# Write one Oxbow Witness packet for the work session you just participated in

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


def _schema(path: str | Path = SCHEMA):
    return json.loads(Path(path).read_text(encoding="utf-8"))


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


def cmd_draft(a):
    parts = [DRAFT_PREAMBLE, "\n## Required JSON shape\n\n```json\n" + json.dumps(_schema(a.schema), indent=2) + "\n```\n"]
    if a.stream:
        st = json.loads(Path(a.stream).read_text(encoding="utf-8"))
        validate_stream(st)
        parts.append(
            "\n## Stream state (form only)\n\n"
            "Existing record count: %d. Do not compare this session to prior records.\n"
            % len(st["records"])
        )
    out = "\n".join(parts)
    if a.out:
        Path(a.out).write_text(out, encoding="utf-8")
        print("wrote draft prompt -> %s" % a.out)
    else:
        sys.stdout.write(out)
    return 0


def _validate(packet, schema_path):
    validate_packet(packet, _schema(schema_path))
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
    d.add_argument("--schema", default=str(SCHEMA))
    d.set_defaults(fn=cmd_draft)

    v = sub.add_parser("validate", help="check one packet's shape and declared boundaries")
    v.add_argument("packet")
    v.add_argument("--schema", default=str(SCHEMA))
    v.set_defaults(fn=cmd_validate)

    p = sub.add_parser("append", help="validate and append one packet without rewriting prior records")
    p.add_argument("packet")
    p.add_argument("--stream", required=True)
    p.add_argument("--out")
    p.add_argument("--schema", default=str(SCHEMA))
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
