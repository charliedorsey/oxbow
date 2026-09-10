# Oxbow status

Current state: **v0.1 release candidate rc2 — middleweight Witness v2 built**.

Implemented:

- `oxbow init` handoff skeleton;
- direct corpus -> `.oxb.py` shipping;
- inert `.oxb` twin path;
- top-level `info / ls / cat / read-first / tour / verify / extract` commands;
- bounded public wire kernel and exact manifest reconciliation;
- detached Ed25519 signing and `verify --mode act` fail-closed path;
- append-only Witness stream with packet v1 compatibility and richer packet v2;
- v2 typed reads, basis references, source coverage, structured overhang, claim boundaries, optional weather/audit/lineage, and quick/standard/deep drafting profiles;
- tiny synthetic example;
- public README, history, continuity, trust, security, and wire-spec docs;
- Linux/macOS CI configuration;
- clean-wheel install/test gate;
- frozen v0.1 compatibility/security/example fixtures.

Remaining before calling the project a public `v0.1` release:

- one real outside user must run the documented flow without development-loop coaching and report what was confusing, including whether Witness v2's richer fields improve handoff legibility or mostly feel like form-filling.

That human usability gate is intentionally not replaced by another automated test.
