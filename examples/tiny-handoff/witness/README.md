# Witness write-back

Witness is an optional append-only record for carrying a compact account of a work session into a later handoff. It checks **form and declared provenance boundaries, not truth or evidential sufficiency**.

The normal operator flow is:

```bash
oxbow witness draft --stream witness/stream.json --out witness/prompt.md
# give prompt.md to the model that just did the work; save its JSON as packet.json
oxbow witness validate packet.json
oxbow witness append packet.json --stream witness/stream.json
```

Packet v2 is the default. Reads have explicit status, scope, and basis; overhang is structured; and every packet states a claim boundary. Source anchors, weather, audit, and lineage are optional.

The tiny example intentionally uses a boring middleweight packet: one source anchor, one local interpretation, and one unresolved item. It does not use weather, audit, or lineage because they add nothing here.

Use `--depth quick`, `--depth standard`, or `--depth deep` to change drafting guidance while keeping one v2 packet contract. Legacy packet v1 remains valid through `--packet-version v1`.

A `basis` is a declared referent, not proof. A `promoted` read records workstream standing, not truth. Records are append-only. Corrections are new records; old records are not rewritten. The stream's `derived_index` is rebuildable and never outranks the records.
