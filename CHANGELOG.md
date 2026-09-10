# Changelog

Oxbow follows semantic versioning once the public `v0.1` line is released. Release candidates freeze intended product behavior closely enough that outside-user feedback can be evaluated against a stable object.

## 0.1.0rc4 — 2026-09-09

Portable prebuilt reproducibility check fix.

- Replaced the cross-runtime prebuilt `--check` gate from compressed-wrapper byte equality to semantic payload equality plus canonical generated-wrapper structure.
- The semantic gate still requires every decoded path and file byte to match regenerated source exactly, verifies both committed and regenerated payloads, checks the generated wrapper shell, and requires `SHA256SUMS` to match the committed download bytes.
- Added `tools/build_prebuilt.py --check-bytes` as an explicit stronger same-toolchain release-host check when exact compressed representation matters.
- Documented that Python/liblzma implementations may emit different valid raw-LZMA2 bytes for identical decoded Oxbow contents; compressed-byte identity is not part of the portable Oxbow contract.
- No OXB wire, manifest, wrapper runtime, signing, Witness, or prebuilt profile-selection semantics changed.

### Release gate still open

`0.1.0rc4` remains a release candidate. The outside-user usability gate is unchanged.

## 0.1.0rc3 — 2026-09-09

Prebuilt GitHub distribution release candidate.

- Added top-level `prebuilt/` with tiny, standard, and full self-extracting `.oxb.py` artifacts; standard is the recommended default for direct model handoff.
- Added `PREBUILT_PROFILE.md` inside each generated payload so a receiving reader can identify the profile, package version, intended use, and exclusions from inside the bundle.
- Added `tools/build_prebuilt.py` to generate all three wrappers deterministically from tracked public source and `--check` to require byte-for-byte agreement with committed artifacts.
- Added `prebuilt/SHA256SUMS` as a reproducibility/transport convenience while explicitly preserving the existing distinction between integrity and authentication.
- Defined explicit tiny/standard allowlists and a full profile consisting of every tracked public repository file except `prebuilt/` itself, preventing recursive self-bundling.
- Marked prebuilt wrappers as generated for GitHub language/diff presentation and added repository tests for profile contents, integrity, privacy, trusted non-executing inspection, and reproducibility.
- No OXB wire, wrapper-runtime, signing, manifest, or Witness semantics changed in this release candidate.

### Release gate still open

`0.1.0rc3` remains a release candidate. The outside-user gate from rc2 is unchanged: at least one person outside the development loop should run the documented handoff flow without coaching and report what was confusing before the final public v0.1 release.

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
