# Repository layout

- `src/oxbow/` — installable public package.
- `src/oxbow/bundle/` — bounded wire/build/verify/wrap/ship implementation.
- `src/oxbow/witness/` — neutral public append-only Witness format/tooling.
- `examples/tiny-handoff/` — freshly synthetic five-minute example.
- `spec/` — normative public wire specification.
- `docs/` — continuity, trust, history, and outside-user test documentation.
- `tests/` — repository and compatibility gates plus frozen v0.1 fixtures.
- `compat/rosetta_v5/` — frozen historical reference decoder; not installed and not the public untrusted-data reader.
- `integrations/` — optional seams; Oxbow core does not require them.

The repository contains the generalized public product, not the private corpus or historical working environment that preceded it.
