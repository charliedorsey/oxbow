# Oxbow Witness format v0.1

Witness is an optional append-only session record for carrying compact work-state evidence into later handoffs.

Its scope is deliberately narrow:

> **Witness checks form and declared provenance boundaries. It does not verify factual truth.**

## Packet

A model or human drafter emits one packet after a work session. The required fields are:

- `packet_id` — portable id beginning `pkt_`;
- `packet_type` — a free genre label;
- `source.description` — what happened or what material was provided;
- `reads[]` — interpretations, each named explicitly;
- `overhang[]` — unresolved work, present even when empty;
- `self_witness` — whether the drafter was a party and, if so, a caveat;
- `third_party_context` — whether non-operator/non-drafter people are represented and a handling note.

`source` and `reads` have different rights. A report belongs in `source`; a diagnosis, interpretation, or implication belongs in `reads`.

The third-party field is a flag, not a compliance system. If third-party context is present, the handling note should say what review/redaction/consent-or-public-source status is actually known. Do not fabricate permission.

## Stream

A stream is:

```json
{
  "format": "oxbow-witness-stream-v1",
  "stream_id": "wtn_...",
  "name": "project",
  "created_at": "...Z",
  "records": [],
  "derived_index": {}
}
```

Each append adds one record containing the packet nearly verbatim plus:

- `record_id`;
- `ingest_order`;
- `ingest_timestamp`.

Prior records are not rewritten. Corrections are new packets.

`derived_index` is a rebuildable view over `records`. If the two disagree, `records` win.

## Normal flow

```bash
oxbow witness draft --stream witness/stream.json --out witness/prompt.md
# give the prompt to the model that just did the work; save returned JSON as packet.json
oxbow witness validate packet.json
oxbow witness append packet.json --stream witness/stream.json
oxbow witness show --stream witness/stream.json
```

## Validation boundary

The validator enforces packet shape, packet-id namespace, overhang presence, self-witness disclosure, and the third-party handling note. It also warns when `source.description` appears to contain interpretation.

It cannot establish that an account is accurate. Integrity is not truth; neither is a well-formed Witness packet.
