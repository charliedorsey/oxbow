# Changelog

Oxbow follows semantic versioning once the public `v0.1` line is released. This release candidate freezes the intended public wire profile and product path so outside-user feedback can be evaluated against a stable object.

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

### Release gate still open

`0.1.0rc1` is intentionally not the final `0.1.0`. At least one person outside the development loop must run the documented handoff flow without coaching and report what was confusing before the final public v0.1 release.
