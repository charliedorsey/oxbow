# Bundle layout

Oxbow does not require a domain-specific directory structure. The root documents are the interface; everything else is the operator's corpus.

- `READ_FIRST.md` — factual first door and continuity boundary.
- `START_HERE.md` — recommended reading sequence.
- `HANDOFF.md` — editable working-state summary maintained by the operator.
- `BUNDLE_LAYOUT.md` — this file.
- `witness/` — optional append-only session records and write-back guidance.
- everything else — source material, working files, tools, or artifacts chosen by the operator.

During packing, Oxbow adds `manifests/MANIFEST.generated.json`. The manifest describes the packed source tree and is used for exact integrity verification.

Derived indexes never outrank source records. Integrity never implies factual truth.
