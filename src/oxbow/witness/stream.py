#!/usr/bin/env python3
"""Append-only public Witness stream.

The public v0.1 stream deliberately stores validated packets nearly verbatim.
Records are source; ``derived_index`` is a rebuildable convenience view.
"""
from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

STREAM_FORMAT = "oxbow-witness-stream-v1"
RECORD_FORMAT = "oxbow-witness-record-v1"
_RECORD_ID = re.compile(r"^rec_[A-Za-z0-9][A-Za-z0-9_.-]{2,127}$")


class Unlawful(Exception):
    pass


def utc_now(now=None) -> str:
    value = now or datetime.now(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def new_stream(name: str = "handoff", *, now=None, stream_id: Optional[str] = None) -> dict:
    return {
        "format": STREAM_FORMAT,
        "stream_id": stream_id or ("wtn_" + uuid.uuid4().hex),
        "name": str(name or "handoff"),
        "created_at": utc_now(now),
        "records": [],
        "derived_index": rebuild_index({"records": []}),
    }


def rebuild_index(stream: dict) -> dict:
    records = list(stream.get("records") or [])
    packet_ids = []
    open_by_record = {}
    third_party = []
    for rec in records:
        packet = rec.get("packet") or {}
        pid = packet.get("packet_id")
        if pid:
            packet_ids.append(pid)
        overhang = list(packet.get("overhang") or [])
        if overhang:
            open_by_record[rec.get("record_id", "?")] = overhang
        if (packet.get("third_party_context") or {}).get("present"):
            third_party.append(rec.get("record_id"))
    return {
        "record_count": len(records),
        "packet_ids": packet_ids,
        "open_overhang_by_record": open_by_record,
        "records_with_third_party_context": [x for x in third_party if x],
    }


def validate_stream(stream: dict) -> None:
    if not isinstance(stream, dict) or stream.get("format") != STREAM_FORMAT:
        raise Unlawful("not an %s stream" % STREAM_FORMAT)
    if not isinstance(stream.get("records"), list):
        raise Unlawful("stream records must be a list")
    seen_records = set()
    seen_packets = set()
    for i, rec in enumerate(stream["records"]):
        rid = rec.get("record_id")
        if not isinstance(rid, str) or not _RECORD_ID.fullmatch(rid):
            raise Unlawful("record %d has invalid record_id" % i)
        if rid in seen_records:
            raise Unlawful("duplicate record_id: %s" % rid)
        seen_records.add(rid)
        packet = rec.get("packet") or {}
        pid = packet.get("packet_id")
        if not pid:
            raise Unlawful("record %s has no packet_id" % rid)
        if pid in seen_packets:
            raise Unlawful("duplicate packet_id in stream: %s" % pid)
        seen_packets.add(pid)
        if rec.get("ingest_order") != i + 1:
            raise Unlawful("record %s has non-canonical ingest_order" % rid)


def _record_id(packet_id: str) -> str:
    tail = packet_id[4:] if packet_id.startswith("pkt_") else packet_id
    rid = "rec_" + tail
    if len(rid) > 132:
        rid = rid[:96] + "_" + uuid.uuid5(uuid.NAMESPACE_OID, packet_id).hex[:24]
    return rid


def append_packet(stream: dict, packet: dict, *, now=None) -> dict:
    """Append one packet without rewriting prior records."""
    validate_stream(stream)
    pid = packet.get("packet_id")
    if not isinstance(pid, str) or not pid.startswith("pkt_"):
        raise Unlawful("packet must have a validated pkt_ packet_id")
    if any((r.get("packet") or {}).get("packet_id") == pid for r in stream["records"]):
        raise Unlawful("packet_id already present: %s" % pid)
    rid = _record_id(pid)
    if any(r.get("record_id") == rid for r in stream["records"]):
        raise Unlawful("record_id collision: %s" % rid)

    out = copy.deepcopy(stream)
    out["records"].append({
        "format": RECORD_FORMAT,
        "record_id": rid,
        "ingest_order": len(out["records"]) + 1,
        "ingest_timestamp": utc_now(now),
        "packet": copy.deepcopy(packet),
    })
    out["derived_index"] = rebuild_index(out)
    return out
