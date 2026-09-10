# Oxbow trust model

Oxbow separates four questions that are easy to collapse into one word such as “verified.”

## 1. Wire validity

Question: **Is this a supported Oxbow payload that can be parsed within the public resource limits?**

The public reader accepts the locked `rsb1-v5-public-kernel-1` profile only. It rejects unsupported global pools, unsafe paths, duplicate paths, malformed varints, trailing bytes, over-limit output, and unsupported section structure.

Wire validity says nothing about who produced the payload.

## 2. Manifest integrity

Question: **Does the payload contain exactly the files its generated manifest claims, with the declared lengths and SHA-256 hashes?**

Integrity fails on:

- a missing manifest record;
- an unexpected unmanifested payload file;
- a missing payload file;
- a size mismatch;
- a SHA-256 mismatch;
- duplicate/unsafe manifest paths.

Integrity says the packaged file tree is internally exact. **Integrity is not truth.**

## 3. Handoff conformance

Question: **Does the object have enough orientation to function as an Oxbow handoff rather than merely as an archive?**

The current conformance profile requires:

- `READ_FIRST.md`;
- `BUNDLE_LAYOUT.md`;
- `START_HERE.md` or another recognized tour surface.

`oxbow init` additionally creates `HANDOFF.md` as the default operator-maintained state surface.

Conformance does not authenticate an author.

## 4. Authenticity

Question: **Was this exact inert payload signed by the holder of a public key I independently trust?**

Oxbow uses detached Ed25519 signatures over the inert `.oxb` payload bytes.

A signature document carries its public key for convenience, but an embedded or adjacent key is not automatically trusted. Identity requires an independent trust path for that key.

Strong path:

```bash
oxbow verify handoff.oxb \
  --mode act \
  --sig handoff.oxb.sig \
  --pubkey <public-key-obtained-independently>
```

`--mode act` fails closed unless both a signature and a pinned public key are supplied.

## `.oxb.py` boundary

A `.oxb.py` is executable Python. The canonical generator embeds the exact inert `.oxb` payload plus a small stdlib-only runtime and self-verifies it at build time.

For an untrusted wrapper, do **not** infer that a valid embedded payload makes arbitrary surrounding Python safe. A trusted Oxbow CLI can inspect the embedded payload without executing the wrapper:

```bash
oxbow verify untrusted.oxb.py
oxbow cat untrusted.oxb.py READ_FIRST.md
```

The CLI explicitly reports that wrapper source was not executed or authenticated.

Detached signatures produced for `.oxb.py` cover the embedded inert payload bytes, not arbitrary wrapper source.

## Read mode vs act mode

Read-only inspection can be useful without author authentication. Oxbow therefore permits unsigned verification in `--mode read` and reports authenticity as unestablished.

A bundle that will drive tools, writes, external calls, deployments, or other consequential actions should be held to a stronger local policy. `--mode act` is the provided fail-closed starting point; it requires a valid detached signature and an independently pinned public key.

This is a policy boundary, not a claim that signatures make content safe or correct.

## Witness trust boundary

Witness is another place where the word "verified" can overreach.

Packet validation can establish that a record has the declared v1/v2 shape and satisfies Oxbow's structural boundaries. For packet v2, that includes things such as portable ids, typed read status/scope, nonempty basis references, local source-anchor resolution, reconstruction provenance, and backward packet/read lineage during append.

It does **not** establish that:

- the source account is factually accurate;
- a declared `basis` actually supports the read;
- a `promoted` read is true;
- a population-scope read has enough evidence;
- the drafter's self-witness caveat is complete;
- a third-party handling note satisfies privacy law or policy.

`source.coverage=full` means full declared source for that Witness record, not complete coverage of reality.

A cross-packet basis or lineage edge says that the new record points to an earlier record. It does not create memory or prove that the same model instance persisted across sessions.

The intended use is modest but useful: make claims easier to catch, scope, challenge, and correct without pretending that structure itself adjudicates truth.
