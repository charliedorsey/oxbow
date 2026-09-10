# Changelog

Oxbow follows semantic versioning once the public `v0.1` line is released. Release candidates freeze intended product behavior closely enough that outside-user feedback can be evaluated against a stable object.

## 0.1.0rc2 — 2026-09-09

Witness packet v2 release candidate.

- Added `oxbow-witness-packet-v2` while retaining packet v1 compatibility inside the unchanged `oxbow-witness-stream-v1` container.
- Added typed read status (`observation`, `interpretation`, `candidate`, `promoted`, `abstention`) and scope (`local`, `cross_packet`, `population`).
- Added portable `basis` references to source, source anchors, earlier packets/reads, or opaque external referents.
- Added source coverage declarations (`full`, `selective`, `reconstructed`, `mixed`) and required reconstruction provenance for reconstructed/mixed records.
- Added structured overhang with `open`, `blocked`, `deferred`, and `watch` states while preserving the existing plain-text derived-index shape.
- Added packet-level claim boundaries plus conditional per-read boundaries for stronger status/scope.
- Added optional weather, compact audit exceptions/flags, and append-only lineage.
- Added `quick`, `standard`, and `deep` drafting profiles over one stable v2 packet contract, plus `--packet-version v1` for legacy drafting.
- Added backward-reference validation for cross-packet basis and lineage during append without rewriting prior records.
- Extended the small built-in schema checker only for the JSON-Schema features used by shipped Witness schemas; no runtime dependency was added.
- Updated the synthetic handoff example, generated Witness guidance, trust/continuity docs, and installed-package selftest for v2.

### Release gate still open

`0.1.0rc2` is intentionally not the final `0.1.0`. At least one person outside the development loop must run the documented handoff flow without coaching and report what was confusing before the final public v0.1 release. The outside-user test now explicitly asks whether the richer Witness fields improve understanding or merely feel like form-filling.

## 0.1.0rc1 — 2026-09-08

Initial public release candidate.

- Added `oxbow init` for a minimal, editable handoff skeleton.
- Added direct corpus-to-`.oxb.py` shipping and optional inert `.oxb` twins.
- Added non-executing trusted inspection commands: `info`, `ls`, `cat`, `read-first`, `tour`, `verify`, and `extract`.
- Locked the public wire profile to `rsb1-v5-public-kernel-1`: opaque file bytes plus raw LZMA2 preset 6, exact manifest reconciliation, bounded decoding, safe paths, and default symlink rejection.
- Separated wire validity, integrity, handoff conformance, and signature authenticity.
- Added detached Ed25519 signing and fail-closed `verify --mode act` with a pinned public key.
- Added a fresh neutral Witness v0.1 packet/stream format with append-only records, packet-ID validation, source/read separation, overhang, self-witness caveats, and third-party-context handling notes.
- Added the synthetic `examples/tiny-handoff/` corpus and frozen v0.1 compatibility/security fixtures.
- Added public continuity, trust, security, history, wire-spec, and outside-user-test documentation.
- Moved Rosetta compatibility evidence outside the installed package and kept FirstLight integration-only.
- Removed historical research machinery and operator-specific corpus/context from the canonical public product tree.
