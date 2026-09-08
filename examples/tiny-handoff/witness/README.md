# Witness write-back

Witness is an optional append-only record for carrying a compact account of a work session into a later handoff. It checks **form and declared provenance boundaries, not truth**.

The normal operator flow is:

```bash
oxbow witness draft --stream witness/stream.json --out witness/prompt.md
# give prompt.md to the model that just did the work; save its JSON as packet.json
oxbow witness validate packet.json
oxbow witness append packet.json --stream witness/stream.json
```

A packet must separate `source` (what happened / what was provided) from `reads` (interpretations), preserve `overhang` (what remains open), state whether the drafter was a party to the session, and explicitly flag third-party context when present.

Records are append-only. Corrections are new records; old records are not rewritten. The stream's `derived_index` is rebuildable and never outranks the records.
