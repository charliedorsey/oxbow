#!/usr/bin/env python3
"""Validation for Oxbow Witness packets.

Witness validates structure and declared provenance boundaries. It does not
adjudicate factual truth, evidential sufficiency, or author identity.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "null": type(None),
}

V2_FORMAT = "oxbow-witness-packet-v2"

_INFERENCE_PATTERNS = [
    (r"\b(because|as a result|consequently|therefore|thus|hence)\b", "causal conjunction"),
    (r"\b(suggest|indicate|imply|reveal|demonstrate|prove|confirm)\w*\b", "evidential verb"),
    (r"\b(seems?|appears?)\s+(to|like|as if)\b", "hedged inference"),
    (r"\b(the takeaway|the lesson|the reason|the effect)\s+(was|is)\b", "interpretive framing"),
    (r"\bwhich (means|meant|suggests|reveals)\b", "relative inference"),
]
_INFERENCE_PATTERNS = [(re.compile(p, re.I), label) for p, label in _INFERENCE_PATTERNS]
_PACKET_ID = re.compile(r"^pkt_[A-Za-z0-9][A-Za-z0-9_.-]{2,127}$")
_LOCAL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_PACKET_BASIS = re.compile(
    r"^packet:(pkt_[A-Za-z0-9][A-Za-z0-9_.-]{2,127})(?:#([A-Za-z0-9][A-Za-z0-9_.-]{0,127}))?$"
)
_SOURCE_BASIS = re.compile(r"^source:([A-Za-z0-9][A-Za-z0-9_.-]{0,127})$")


class Invalid(Exception):
    """Packet does not satisfy its JSON shape contract."""


class Unlawful(Exception):
    """Packet satisfies shape but violates a Witness boundary."""


def _check(node, schema, path="$"):
    """Validate the small JSON-Schema subset used by shipped Witness schemas."""
    if "const" in schema and node != schema["const"]:
        raise Invalid(f"{path}: expected constant {schema['const']!r}")

    if "enum" in schema and node not in schema["enum"]:
        raise Invalid(f"{path}: expected one of {schema['enum']!r}, got {node!r}")

    t = schema.get("type")
    if t:
        cls = _TYPES[t]
        if t in ("integer", "number") and isinstance(node, bool):
            raise Invalid(f"{path}: expected {t}, got bool")
        if not isinstance(node, cls):
            raise Invalid(f"{path}: expected {t}, got {type(node).__name__}")

    if isinstance(node, str):
        if "minLength" in schema and len(node) < schema["minLength"]:
            raise Invalid(f"{path}: string shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(node) > schema["maxLength"]:
            raise Invalid(f"{path}: string longer than maxLength {schema['maxLength']}")
        if "pattern" in schema and re.search(schema["pattern"], node) is None:
            raise Invalid(f"{path}: string does not match required pattern")

    if t == "object":
        for req in schema.get("required", []):
            if req not in node:
                raise Invalid(f"{path}: missing required field '{req}'")
        for key, sub in schema.get("properties", {}).items():
            if key in node:
                _check(node[key], sub, f"{path}.{key}")
    elif t == "array":
        if "minItems" in schema and len(node) < schema["minItems"]:
            raise Invalid(f"{path}: array shorter than minItems {schema['minItems']}")
        if "maxItems" in schema and len(node) > schema["maxItems"]:
            raise Invalid(f"{path}: array longer than maxItems {schema['maxItems']}")
        item = schema.get("items")
        if item:
            for i, el in enumerate(node):
                _check(el, item, f"{path}[{i}]")


def validate_packet(packet: dict, schema: dict) -> None:
    _check(packet, schema)


def packet_version(packet: dict) -> str:
    """Return ``v1`` or ``v2``; reject explicit unknown packet formats."""
    fmt = packet.get("format")
    if fmt is None:
        return "v1"
    if fmt == V2_FORMAT:
        return "v2"
    raise Unlawful("unsupported Witness packet format: %r" % fmt)


def parse_basis_ref(value: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Parse one v2 basis reference.

    Returns ``(kind, primary, secondary)`` where kind is one of ``source``,
    ``source_anchor``, ``packet``, or ``external``. Packet references return
    packet id as primary and optional read id as secondary.
    """
    if value == "source":
        return ("source", None, None)
    m = _SOURCE_BASIS.fullmatch(value)
    if m:
        return ("source_anchor", m.group(1), None)
    m = _PACKET_BASIS.fullmatch(value)
    if m:
        return ("packet", m.group(1), m.group(2))
    if value.startswith("external:") and value[len("external:"):].strip():
        return ("external", value[len("external:"):], None)
    raise Unlawful(
        "invalid basis reference %r; use source, source:<anchor>, "
        "packet:<packet_id>[#<read_id>], or external:<referent>" % value
    )


def _require_unique_ids(items, key, label):
    seen = set()
    for item in items:
        value = item.get(key)
        if not isinstance(value, str) or not _LOCAL_ID.fullmatch(value):
            raise Unlawful("%s must use portable ids" % label)
        if value in seen:
            raise Unlawful("duplicate %s: %s" % (label, value))
        seen.add(value)
    return seen


def _check_basis_list(basis, anchors, *, label):
    if not isinstance(basis, list) or not basis:
        raise Unlawful("%s requires at least one basis reference" % label)
    parsed = []
    for raw in basis:
        if not isinstance(raw, str):
            raise Unlawful("%s basis references must be strings" % label)
        ref = parse_basis_ref(raw)
        if ref[0] == "source_anchor" and ref[1] not in anchors:
            raise Unlawful("%s references missing source anchor: %s" % (label, ref[1]))
        parsed.append(ref)
    return parsed


def _v2_boundaries(packet: dict) -> None:
    source = packet.get("source") or {}
    coverage = source.get("coverage")
    provenance = source.get("provenance_notes") or []
    if coverage in ("reconstructed", "mixed"):
        if not any(str(note).strip() for note in provenance):
            raise Unlawful(
                "source.coverage=%s requires provenance_notes describing what was reconstructed"
                % coverage
            )

    anchors = _require_unique_ids(source.get("anchors") or [], "anchor_id", "source anchor_id")
    _require_unique_ids(packet.get("reads") or [], "read_id", "read_id")
    _require_unique_ids(packet.get("overhang") or [], "overhang_id", "overhang_id")

    if not str(packet.get("claim_boundary", "")).strip():
        raise Unlawful("v2 packets require a nonempty claim_boundary")

    for read in packet.get("reads") or []:
        rid = read.get("read_id", "?")
        parsed = _check_basis_list(read.get("basis"), anchors, label="read %s" % rid)
        status = read.get("status")
        scope = read.get("scope")
        if status in ("candidate", "promoted") or scope in ("cross_packet", "population"):
            if not str(read.get("boundary", "")).strip():
                raise Unlawful(
                    "read %s requires a nonempty boundary for status=%s scope=%s"
                    % (rid, status, scope)
                )
        if scope == "cross_packet" and not any(ref[0] == "packet" for ref in parsed):
            raise Unlawful("cross_packet read %s requires at least one packet: basis reference" % rid)

    for i, item in enumerate(packet.get("weather") or []):
        _check_basis_list(item.get("basis"), anchors, label="weather[%d]" % i)

    audit = packet.get("audit") or {}
    for i, item in enumerate(audit.get("preserved_exceptions") or []):
        _check_basis_list(item.get("basis"), anchors, label="preserved_exception[%d]" % i)

    lineage = packet.get("lineage") or {}
    for field in ("parents", "corrects", "related"):
        for pid in lineage.get(field) or []:
            if not isinstance(pid, str) or not _PACKET_ID.fullmatch(pid):
                raise Unlawful("lineage.%s contains invalid packet_id: %r" % (field, pid))
            if pid == packet.get("packet_id"):
                raise Unlawful("lineage.%s may not reference the packet itself" % field)


def check_boundaries(packet: dict) -> List[str]:
    """Return non-fatal source/inference warnings; raise on hard boundaries."""
    version = packet_version(packet)

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

    if version == "v2":
        _v2_boundaries(packet)

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
