# v0.1 frozen fixtures

These files are immutable compatibility/security fixtures for the public v0.1 wire profile.

- `tiny-handoff.oxb` — unsigned valid handoff built from the neutral example.
- `tiny-handoff.oxb.py` — deterministic standalone wrapper carrying that exact payload.
- `tiny-handoff-signed.oxb` + `.sig` — the same payload with a detached Ed25519 signature using a **public test-only key**.
- `TEST_PUBLIC_KEY.txt` — public key for the test signature; it establishes no real identity.
- `binary-heavy.oxb` — valid mixed binary/media/archive fixture.
- `invalid-parent-path.oxb` — intentionally malformed traversal-path fixture; readers must reject it.
- `invalid-duplicate-path.oxb` — intentionally malformed duplicate-path fixture; readers must reject it.
- `SHA256SUMS.txt` — frozen byte identities.

`tools/freeze_v01_fixtures.py` is the one intentional regeneration path. Do not regenerate these merely because a later writer changes; future readers should keep opening the old valid fixtures and rejecting the old invalid ones.
