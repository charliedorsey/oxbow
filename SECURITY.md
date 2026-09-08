# Security policy

Oxbow handles potentially untrusted bundle data. The public v0.1 reader is intentionally small so that its safety boundary is inspectable.

## Supported release line

Security fixes target the current v0.1 release-candidate / v0.1 line. Historical Rosetta compatibility code under `compat/` is reference material and is not the default untrusted-data reader.

## Untrusted bundles

Prefer inert `.oxb` data when possible.

A `.oxb.py` is executable Python. For a wrapper from an untrusted source, inspect its embedded payload with a trusted Oxbow installation rather than executing it:

```bash
oxbow verify received.oxb.py
oxbow info received.oxb.py
oxbow cat received.oxb.py READ_FIRST.md
```

That path extracts the canonical generated payload marker without running wrapper source. It verifies the payload, not arbitrary Python around it.

## Path and filesystem policy

The public reader rejects:

- absolute paths;
- drive-qualified paths;
- backslashes and colon-qualified portable paths;
- empty, `.` or `..` path components;
- duplicate payload paths.

Source packing does not follow selected symlink files or directories. Extraction only targets a new or empty directory and refuses to overwrite an existing path.

No filesystem API can protect against every hostile concurrent actor mutating the destination during extraction; do not extract untrusted bundles into a directory controlled by another process or user.

## Resource limits

The default reader enforces ceilings on:

- input bundle bytes;
- file count;
- total decompressed bytes;
- individual file bytes;
- path bytes;
- section-name bytes.

LZMA decompression is incremental with explicit output ceilings. The public profile does not enable historical specialist codecs.

## Signatures

Detached Ed25519 signatures cover inert payload bytes. A signature proves possession of a private key, not identity by itself. Pin the expected public key through an independent channel for identity-bearing use.

`oxbow verify --mode act` requires both a detached signature and a pinned public key.

## Out of scope

Oxbow v0.1 does not provide:

- encryption or access control;
- sandboxing of arbitrary files carried inside a corpus;
- sandboxing of arbitrary `.oxb.py` source from third parties;
- malware detection;
- factual truth verification;
- prompt-injection prevention guarantees;
- proof that a receiving model will interpret the handoff correctly.

## Reporting a security issue

If the repository host offers private security advisories, use that channel for vulnerabilities that would be unsafe to disclose immediately. Otherwise, open a minimal public issue describing the affected surface without publishing weaponized exploit details, and coordinate disclosure before posting a full proof of concept.
