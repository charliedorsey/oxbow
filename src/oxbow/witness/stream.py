#!/usr/bin/env python3
"""Append-only public Witness stream.

The stream stores validated packets nearly verbatim. Records are source;
``derived_index`` is a rebuildable convenience view. Packet v1 and packet v2
may coexist inside the same stream-v1 container.
"""
from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from oxbow.witness.validate import Unlawful as PacketUnlawful, V2_FORMAT, parse_basis_ref

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


def _overhang_texts(packet: dict):
    out = []
    for item in list(packet.get("overhang") or []):
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict) and isinstance(item.get("item"), str):
            out.append(item["item"])
    return out


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
        overhang = _overhang_texts(packet)
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


def _packet_read_ids(packet: dict):
    if packet.get("format") != V2_FORMAT:
        return None
    return {
        read.get("read_id")
        for read in (packet.get("reads") or [])
        if isinstance(read, dict) and isinstance(read.get("read_id"), str)
    }


def _basis_values(packet: dict):
    if packet.get("format") != V2_FORMAT:
        return []
    values = []
    for read in packet.get("reads") or []:
        if isinstance(read, dict):
            values.extend(x for x in (read.get("basis") or []) if isinstance(x, str))
    for weather in packet.get("weather") or []:
        if isinstance(weather, dict):
            values.extend(x for x in (weather.get("basis") or []) if isinstance(x, str))
    for item in (packet.get("audit") or {}).get("preserved_exceptions") or []:
        if isinstance(item, dict):
            values.extend(x for x in (item.get("basis") or []) if isinstance(x, str))
    return values


def _check_backward_refs(packet: dict, prior_packets: dict) -> None:
    """Enforce v2 cross-record references against already-appended packets."""
    if packet.get("format") != V2_FORMAT:
        return

    for raw in _basis_values(packet):
        try:
            kind, pid, read_id = parse_basis_ref(raw)
        except PacketUnlawful as exc:
            raise Unlawful(str(exc))
        if kind != "packet":
            continue
        if pid not in prior_packets:
            raise Unlawful("basis reference must point to an earlier packet: %s" % pid)
        if read_id is not None:
            ids = _packet_read_ids(prior_packets[pid])
            if ids is None:
                raise Unlawful(
                    "basis reference %s#%s targets a v1 packet with no stable read_id"
                    % (pid, read_id)
                )
            if read_id not in ids:
                raise Unlawful("basis reference targets missing read_id: %s#%s" % (pid, read_id))

    lineage = packet.get("lineage") or {}
    for field in ("parents", "corrects", "related"):
        for pid in lineage.get(field) or []:
            if pid not in prior_packets:
                raise Unlawful("lineage.%s must point to an earlier packet: %s" % (field, pid))


def validate_stream(stream: dict) -> None:
    if not isinstance(stream, dict) or stream.get("format") != STREAM_FORMAT:
        raise Unlawful("not an %s stream" % STREAM_FORMAT)
    if not isinstance(stream.get("records"), list):
        raise Unlawful("stream records must be a list")
    seen_records = set()
    prior_packets = {}
    for i, rec in enumerate(stream["records"]):
        if not isinstance(rec, dict) or rec.get("format") != RECORD_FORMAT:
            raise Unlawful("record %d is not an %s record" % (i, RECORD_FORMAT))
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
        if pid in prior_packets:
            raise Unlawful("duplicate packet_id in stream: %s" % pid)
        if rec.get("ingest_order") != i + 1:
            raise Unlawful("record %s has non-canonical ingest_order" % rid)
        _check_backward_refs(packet, prior_packets)
        prior_packets[pid] = packet


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

    prior_packets = {
        (r.get("packet") or {}).get("packet_id"): (r.get("packet") or {})
        for r in stream["records"]
        if (r.get("packet") or {}).get("packet_id")
    }
    _check_backward_refs(packet, prior_packets)

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
