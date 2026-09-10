# Oxbow Witness packet v2

Witness is an optional append-only session record for carrying compact work-state evidence into later handoffs.

Its scope remains deliberately narrow:

> **Witness checks form and declared provenance boundaries. It does not verify factual truth or evidential sufficiency.**

Packet v2 restores more of the epistemic structure that is useful in long-running work without recreating a multi-document research apparatus. Packet v1 remains valid and may coexist with v2 inside the same stream.

## Design law

> **Restore epistemic rights, not ontology.**

A Witness should preserve the difference between report, interpretation, candidate conclusion, promoted working conclusion, abstention, exception, unresolved work, and declared provenance. It should not require a domain-specific theory of topology, roles, surfaces, or confidence scores.

## Packet versions

### Packet v1

A packet with no `format` field is treated as legacy packet v1 and is validated against `schemas/portable_packet.schema.json`.

### Packet v2

A packet declaring:

```json
{
  "format": "oxbow-witness-packet-v2"
}
```

is validated against `schemas/portable_packet_v2.schema.json` plus the boundary rules described below.

An explicit unknown packet format is refused rather than guessed.

## Packet v2 core

The required top-level fields are:

- `format` — exactly `oxbow-witness-packet-v2`;
- `packet_id` — portable id beginning `pkt_`;
- `packet_type` — free genre label;
- `source` — report plus declared coverage/provenance;
- `reads[]` — typed interpretations or structured readings;
- `overhang[]` — structured unresolved work;
- `claim_boundary` — what this packet does not establish;
- `self_witness` — whether the drafter was a party and, if so, a caveat;
- `third_party_context` — whether non-operator/non-drafter people are represented and a handling note.

Optional sections are:

- `weather[]` — compact descriptions of conditions that materially shaped the work;
- `audit` — uncertainty, preserved exceptions, and lightweight flags;
- `lineage` — declared relationships to earlier packets.

## Source and coverage

`source.description` reports what happened or what material was provided. Diagnoses, implications, and conclusions belong in `reads`.

`source.coverage` is one of:

- `full` — full declared source for this Witness;
- `selective` — a deliberately selected subset;
- `reconstructed` — reconstructed after the fact rather than read directly from a full source;
- `mixed` — a mixture of direct and reconstructed material.

`full` does **not** mean omniscient coverage of reality. It only describes the declared source set for this record.

`reconstructed` and `mixed` require a nonempty provenance note explaining the reconstruction boundary.

A source may also carry anchors:

```json
{
  "anchor_id": "a1",
  "ref": "notes/design-review.md#decision-4",
  "description": "The decision that replaced the earlier retry strategy."
}
```

Anchors are local addresses. Oxbow checks that local anchor references resolve inside the packet; it does not inspect the referenced external file or decide whether the anchor supports a later claim.

## Reads

A v2 read has:

```json
{
  "read_id": "r1",
  "name": "design_direction",
  "status": "interpretation",
  "scope": "local",
  "value": "The smaller retry surface is the current working direction.",
  "basis": ["source:a1"],
  "boundary": "This is a design interpretation, not a production reliability result.",
  "notes": []
}
```

### Read status

`status` is one of:

- `observation` — a direct structured read of the declared source;
- `interpretation` — an inference about what the source means;
- `candidate` — a hypothesis or pattern worth carrying but not promoted;
- `promoted` — a conclusion explicitly promoted by the workstream;
- `abstention` — an explicit refusal to infer beyond the available basis.

`promoted` records project standing. **It is not a truth verdict from Oxbow.**

### Read scope

`scope` is one of:

- `local` — about the current packet/source;
- `cross_packet` — combines the current work with one or more earlier Witness packets;
- `population` — claims about a wider population or class beyond the local/cross-packet material.

`candidate` and `promoted` reads require an explicit `boundary`.

`cross_packet` and `population` reads also require an explicit `boundary`.

A `cross_packet` read must include at least one earlier `packet:` basis reference.

## Basis references

Every v2 read has at least one `basis` reference.

The portable grammar is:

```text
source
source:<anchor_id>
packet:<packet_id>
packet:<packet_id>#<read_id>
external:<opaque referent>
```

Examples:

```json
"basis": ["source"]
```

```json
"basis": ["source:a3"]
```

```json
"basis": ["packet:pkt_release_review#r2"]
```

```json
"basis": ["external:docs/benchmark_report.md"]
```

`source:<anchor_id>` must resolve to an anchor in the current packet.

When a packet is appended to a stream, `packet:` references must point backward to an already-present packet. A read-level `#read_id` reference must resolve to a v2 read. A whole-packet reference may point to either a v1 or v2 packet.

`external:` is intentionally opaque. Oxbow records the declared referent but does not fetch, authenticate, or evaluate it.

> **A basis records where a claim points. It does not establish that the referent supports the claim.**

## Weather

`weather` is optional. Use it when the condition of the work matters to a later reader:

```json
{
  "label": "drift_and_correction",
  "basis": ["source:a2"],
  "reason": "A previously attractive explanation was rejected during the session."
}
```

Weather is context, not evidence. Do not use it as a disguised confidence score or personality diagnosis.

## Overhang

V2 overhang is structured:

```json
{
  "overhang_id": "o1",
  "item": "Determine whether the fallback should remain enabled.",
  "status": "open",
  "next_test": "Run the failure-path fixture against the current branch."
}
```

Status is one of:

- `open`;
- `blocked`;
- `deferred`;
- `watch`.

`next_test` is optional.

There is deliberately no `done` status. Completed work belongs in a later source/read; `overhang` is for what remains unresolved.

The stream's derived index continues to expose plain overhang text so packet v1 and packet v2 records share one stable index shape.

## Claim boundary

Every v2 packet has a nonempty packet-level `claim_boundary`.

This is not boilerplate. It names what the packet as a whole does **not** establish.

Examples:

- a research packet may record a derived identity without claiming independent verification;
- a hiring debrief may record perceived rapport without claiming hiring intent;
- a release review may record passing fixtures without claiming absence of defects.

Reads with stronger status or scope may additionally carry their own `boundary`.

## Audit

`audit` is optional and intentionally small:

```json
{
  "uncertainty_notes": [],
  "preserved_exceptions": [
    {
      "description": "One fixture behaved differently from the dominant pattern.",
      "basis": ["source:a4"]
    }
  ],
  "flags": [
    {
      "code": "recursive_self_witness",
      "severity": "caution",
      "note": "The drafter is also the subject of several interpretations."
    }
  ]
}
```

Severity is only `info` or `caution`.

There are no confidence percentages, validity grades, or aggregate epistemic scores. The audit gives uncertainty and rare contradictory evidence a legal address; it does not automate judgment.

## Lineage

`lineage` is optional:

```json
{
  "parents": ["pkt_prior_session"],
  "corrects": [],
  "related": [],
  "what_this_adds": [
    "The earlier retry assumption was replaced after a new failure-path test."
  ]
}
```

`parents`, `corrects`, and `related` must point backward to earlier packets when the packet is appended to a stream.

A correction never rewrites the earlier record. The new packet points back to it.

Lineage records a declared relationship between records. It is not model memory or proof of causal continuity.

## Self-witness and third-party context

The existing boundaries remain.

If `self_witness.drafter_was_party` is true, the caveat must state a real limitation created by that position.

If `third_party_context.present` is true, `handling_note` must state only the review, redaction, consent/public-source status, or uncertainty actually known. Do not fabricate permission.

The third-party field is a flag, not a compliance system.

## Drafting depths

Packet v2 uses one stable wire contract with three prompt profiles:

```bash
oxbow witness draft --depth quick --stream witness/stream.json --out witness/prompt.md
oxbow witness draft --depth standard --stream witness/stream.json --out witness/prompt.md
oxbow witness draft --depth deep --stream witness/stream.json --out witness/prompt.md
```

`standard` is the default.

- `quick` keeps anchors/weather/audit/lineage out unless they materially help;
- `standard` encourages catchable anchors, structured overhang, useful weather, abstention, and lineage where warranted;
- `deep` encourages richer cross-packet basis, preserved exceptions, uncertainty notes, and population abstention for long or consequential sessions.

All three emit `oxbow-witness-packet-v2`. Richness comes from optional population of one stable contract, not from inventing a new schema dialect.

Legacy v1 drafting remains available:

```bash
oxbow witness draft --packet-version v1 --stream witness/stream.json --out witness/prompt.md
```

## Stream

The stream format remains:

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

Each append adds one `oxbow-witness-record-v1` record containing the packet nearly verbatim plus:

- `record_id`;
- `ingest_order`;
- `ingest_timestamp`.

Packet v1 and packet v2 may coexist in one stream.

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

Standalone validation checks packet shape and local boundaries. Stream append additionally resolves backward packet/read references and lineage targets.

## Validation boundary

The validator can enforce declared structure such as:

- packet/version shape;
- portable IDs;
- read status and scope vocabulary;
- nonempty basis references;
- local source-anchor resolution;
- backward packet/read references during append;
- stronger-claim boundaries;
- reconstruction provenance;
- self-witness disclosure;
- third-party handling notes;
- append-only lineage.

It cannot establish:

- that the source account is accurate;
- that a basis actually supports the read;
- that a `promoted` conclusion is true;
- that a population claim has enough evidence;
- that a third-party handling note satisfies law or policy;
- that a receiving model will interpret the record correctly.

Integrity is not truth; neither is a well-formed Witness packet.
