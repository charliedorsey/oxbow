#!/usr/bin/env python3
"""Validation for the neutral public Witness packet format.

Witness validates structure and declared provenance boundaries. It does not
adjudicate factual truth.
"""
from __future__ import annotations

import re
from typing import List

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}

_INFERENCE_PATTERNS = [
    (r"\b(because|as a result|consequently|therefore|thus|hence)\b", "causal conjunction"),
    (r"\b(suggest|indicate|imply|reveal|demonstrate|prove|confirm)\w*\b", "evidential verb"),
    (r"\b(seems?|appears?)\s+(to|like|as if)\b", "hedged inference"),
    (r"\b(the takeaway|the lesson|the reason|the effect)\s+(was|is)\b", "interpretive framing"),
    (r"\bwhich (means|meant|suggests|reveals)\b", "relative inference"),
]
_INFERENCE_PATTERNS = [(re.compile(p, re.I), label) for p, label in _INFERENCE_PATTERNS]
_PACKET_ID = re.compile(r"^pkt_[A-Za-z0-9][A-Za-z0-9_.-]{2,127}$")


class Invalid(Exception):
    """Packet does not satisfy the public shape contract."""


class Unlawful(Exception):
    """Packet satisfies shape but violates a Witness boundary."""


def _check(node, schema, path="$"):
    t = schema.get("type")
    if t:
        cls = _TYPES[t]
        if t in ("integer", "number") and isinstance(node, bool):
            raise Invalid(f"{path}: expected {t}, got bool")
        if not isinstance(node, cls):
            raise Invalid(f"{path}: expected {t}, got {type(node).__name__}")
    if t == "object":
        for req in schema.get("required", []):
            if req not in node:
                raise Invalid(f"{path}: missing required field '{req}'")
        for key, sub in schema.get("properties", {}).items():
            if key in node:
                _check(node[key], sub, f"{path}.{key}")
    elif t == "array":
        item = schema.get("items")
        if item:
            for i, el in enumerate(node):
                _check(el, item, f"{path}[{i}]")


def validate_packet(packet: dict, schema: dict) -> None:
    _check(packet, schema)


def check_boundaries(packet: dict) -> List[str]:
    """Return non-fatal source/inference warnings; raise on hard boundaries."""
    pid = packet.get("packet_id", "")
    if not _PACKET_ID.fullmatch(pid):
        raise Unlawful(
            "packet_id must use neutral packet grammar `pkt_<label>` with 3-128 portable characters"
        )

    if not isinstance(packet.get("overhang"), list):
        raise Unlawful("overhang must be present as a list; it may be empty")

    sw = packet.get("self_witness") or {}
    if sw.get("drafter_was_party") and not str(sw.get("caveat", "")).strip():
        raise Unlawful(
            "a drafter who was a party to the session must state a self-witness caveat"
        )

    tp = packet.get("third_party_context") or {}
    if tp.get("present") and not str(tp.get("handling_note", "")).strip():
        raise Unlawful(
            "third_party_context.present=true requires a handling_note describing review/redaction status"
        )

    warnings = []
    desc = str((packet.get("source") or {}).get("description", ""))
    hits = []
    for pat, label in _INFERENCE_PATTERNS:
        for m in pat.finditer(desc):
            hits.append(f"{m.group(0).strip().lower()} ({label})")
    if hits:
        warnings.append(
            "source.description may contain interpretation (found: %s). "
            "Keep reports in `source` and interpretations in `reads`."
            % "; ".join(sorted(set(hits)))
        )
    return warnings
