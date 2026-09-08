# Oxbow

## Carry the work, not the model.

Oxbow creates self-orienting handoffs for giving a fresh AI instance an existing corpus, working state, decisions, provenance, and optional tools **without claiming continuity with the model that came before**.

A handoff can ship as:

- `.oxb` — inert data; nothing executes;
- `.oxb.py` — transparent self-extracting Python containing the same inert payload plus a stdlib-only reader/verifier/extractor.

Oxbow preserves bytes and orientation. It does not manufacture memory, identity, or truth.

## Five-minute path

Install from a checkout:

```bash
python -m pip install .
```

Create a handoff skeleton:

```bash
oxbow init my-handoff
```

Edit `my-handoff/HANDOFF.md`, add the corpus you actually want to carry, then ship it:

```bash
oxbow ship my-handoff -o my-handoff.oxb.py
```

The generated wrapper self-verifies before `ship` reports success.

The receiving side needs only Python:

```bash
python my-handoff.oxb.py --verify
python my-handoff.oxb.py --tour
python my-handoff.oxb.py --cat HANDOFF.md
```

That is the core product loop.

A complete neutral example lives at [`examples/tiny-handoff/`](examples/tiny-handoff/).

## Inspect without executing a wrapper

A `.oxb.py` is executable Python. For a wrapper you do not already trust, use a trusted local Oxbow install to inspect the embedded payload **without executing the wrapper source**:

```bash
oxbow verify received.oxb.py
oxbow info received.oxb.py
oxbow ls received.oxb.py
oxbow cat received.oxb.py READ_FIRST.md
oxbow tour received.oxb.py
```

Extraction is explicit and only targets a new or empty directory:

```bash
oxbow extract received.oxb.py -d unpacked
```

The lower-level `oxbow bundle ...` commands remain available for build, wrap, signing, profiles, and health checks.

## What a fresh reader sees

`oxbow init` creates a small interface around the operator's corpus:

- `READ_FIRST.md` — what the handoff is and is not;
- `START_HERE.md` — a recommended reading order;
- `HANDOFF.md` — the operator-maintained working state;
- `BUNDLE_LAYOUT.md` — how the object is organized;
- `witness/` — optional append-only session write-back.

Oxbow does not require a domain-specific folder structure. The front doors orient; the rest of the tree remains the operator's work.

## Continuity boundary

Oxbow can carry:

- source material;
- working state;
- prior decisions;
- provenance;
- tools and artifacts;
- Witness records;
- orientation for the next reader.

It cannot carry:

- model identity;
- hidden model state;
- subjective continuity;
- memories the receiving instance does not actually possess.

**The corpus is source. It is not memory.** A receiving model may have the frame without the trajectory.

See [`docs/CONTINUITY_BOUNDARY.md`](docs/CONTINUITY_BOUNDARY.md).

## Verification and trust are separate layers

`oxbow verify` reports different questions separately:

1. **wire** — is this a supported, bounded Oxbow payload?
2. **integrity** — does the actual file tree exactly match the generated manifest?
3. **conformance** — does the handoff have the required orientation surface?
4. **authenticity** — if a detached signature is supplied, does it verify against the expected key?

Integrity does not imply factual truth. A valid self-extracting wrapper does not establish who authored it. A signature is only identity-bearing when the public key is trusted through some independent channel.

For read-only inspection, unsigned handoffs can still be useful:

```bash
oxbow verify received.oxb --mode read
```

For a bundle that will drive tools or actions, use the fail-closed mode with a detached signature and a pinned public key:

```bash
oxbow verify received.oxb \
  --mode act \
  --sig received.oxb.sig \
  --pubkey <trusted-public-key-hex>
```

See [`docs/TRUST_MODEL.md`](docs/TRUST_MODEL.md) and [`SECURITY.md`](SECURITY.md).

## Witness: carry work back out

Witness is optional. It lets the model or human who just did the work leave one compact, append-only record for a later handoff.

```bash
oxbow witness draft --stream my-handoff/witness/stream.json --out prompt.md
# give prompt.md to the model; save the returned JSON as packet.json
oxbow witness validate packet.json
oxbow witness append packet.json --stream my-handoff/witness/stream.json
```

Witness separates reports from interpretations, preserves unresolved `overhang`, states whether the drafter was a party to the session, and explicitly flags third-party context.

**Witness validates form and declared provenance boundaries, not truth.** Corrections append; prior records are not rewritten. Derived indexes are rebuildable views and never outrank source records.

Format: [`src/oxbow/witness/WITNESS_FORMAT.md`](src/oxbow/witness/WITNESS_FORMAT.md).

## Build safety

The public encoder is deliberately boring:

- every selected regular file is carried byte-for-byte;
- no media/PDF/archive file type is silently dropped;
- selected symlinks are rejected rather than followed;
- bundle paths are portable and traversal-safe;
- decoding has file-count, per-file, total-output, path-length, and payload limits;
- extraction refuses to overwrite a nonempty destination;
- the manifest must match the actual payload tree exactly.

The public wire profile uses one codec floor: raw LZMA2 preset 6. Historical specialist codecs are compatibility archaeology, not default product machinery.

Wire specification: [`spec/OXB_WIRE_SPEC.md`](spec/OXB_WIRE_SPEC.md).

## Optional integrations

Oxbow core does not require a router, embedding model, database, hosted service, or model API. An external system such as FirstLight can advise what context deserves attention first, but it is an integration rather than a dependency. See [`integrations/firstlight/README.md`](integrations/firstlight/README.md).

## History

Oxbow emerged from repeated attempts to make useful work survive context boundaries: summaries, plain text, structured documents, explicit state, purpose-built work environments, routing, and eventually a large personal inheritance system called Rosetta.

The redesign principle is:

> **Rosetta grew. Oxbow was designed.**

The public repository intentionally carries the generalized product, not the private corpus or historical operator context that produced it. See [`docs/HISTORY.md`](docs/HISTORY.md).

## Release status

This tree is a **v0.1 release candidate**. The implementation, clean-install gate, cross-platform CI configuration, frozen fixtures, synthetic example, and documentation are present. The remaining product gate is intentionally non-automatable: at least one outside user should run the documented handoff flow before the project is called a public v0.1 release.

See [`docs/OUTSIDE_USER_TEST.md`](docs/OUTSIDE_USER_TEST.md).
