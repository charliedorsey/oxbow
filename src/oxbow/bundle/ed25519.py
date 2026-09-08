#!/usr/bin/env python3
"""
oxbow.bundle.ed25519 — pure-stdlib Ed25519 (RFC 8032), the classic reference
construction. Deliberately dependency-free so the self-extracting wrapper can
verify its own signature with nothing but python3. Slow-ish and not constant-time:
fine for signing/verifying bundles, NOT a general crypto library. Validated against
an RFC 8032 test vector in bundle/selftest.py — the knife rule applies to crypto
too: unproven, unused.
"""
from __future__ import annotations
import hashlib
import sys

sys.setrecursionlimit(4000)

p = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
d = (-121665 * pow(121666, p - 2, p)) % p
I = pow(2, (p - 1) // 4, p)


def _H(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * pow(d * y * y + 1, p - 2, p)
    x = pow(xx, (p + 3) // 8, p)
    if (x * x - xx) % p != 0:
        x = (x * I) % p
    if x % 2 != 0:
        x = p - x
    return x


By = (4 * pow(5, p - 2, p)) % p
Bx = _xrecover(By)
B = (Bx % p, By % p)


def _edwards(P, Q):
    x1, y1 = P
    x2, y2 = Q
    k = (d * x1 * x2 * y1 * y2) % p
    x3 = ((x1 * y2 + x2 * y1) * pow(1 + k, p - 2, p)) % p
    y3 = ((y1 * y2 + x1 * x2) * pow(1 - k, p - 2, p)) % p
    return (x3, y3)


def _scalarmult(P, e: int):
    Q = (0, 1)
    while e:
        if e & 1:
            Q = _edwards(Q, P)
        P = _edwards(P, P)
        e >>= 1
    return Q


def _encodepoint(P) -> bytes:
    x, y = P
    bits = [(y >> i) & 1 for i in range(255)] + [x & 1]
    return bytes(sum(bits[i * 8 + j] << j for j in range(8)) for i in range(32))


def _decodepoint(s: bytes):
    y = sum(2 ** i * ((s[i // 8] >> (i % 8)) & 1) for i in range(255))
    x = _xrecover(y)
    if x & 1 != (s[31] >> 7) & 1:
        x = p - x
    P = (x, y)
    if not _oncurve(P):
        raise ValueError('point not on curve')
    return P


def _oncurve(P) -> bool:
    x, y = P
    return (-x * x + y * y - 1 - d * x * x * y * y) % p == 0


def _Hint(m: bytes) -> int:
    return int.from_bytes(_H(m), 'little')


def _clamp(h: bytes) -> int:
    return 2 ** 254 + sum(2 ** i * ((h[i // 8] >> (i % 8)) & 1) for i in range(3, 254))


def publickey(sk: bytes) -> bytes:
    a = _clamp(_H(sk))
    return _encodepoint(_scalarmult(B, a))


def sign(m: bytes, sk: bytes, pk: bytes) -> bytes:
    h = _H(sk)
    a = _clamp(h)
    r = _Hint(h[32:64] + m)
    R = _scalarmult(B, r)
    S = (r + _Hint(_encodepoint(R) + pk + m) * a) % L
    return _encodepoint(R) + S.to_bytes(32, 'little')


def verify(sig: bytes, m: bytes, pk: bytes) -> bool:
    if len(sig) != 64 or len(pk) != 32:
        return False
    try:
        R = _decodepoint(sig[:32])
        A = _decodepoint(pk)
    except Exception:
        return False
    S = int.from_bytes(sig[32:], 'little')
    if S >= L:
        return False
    h = _Hint(sig[:32] + pk + m)
    return _scalarmult(B, S) == _edwards(R, _scalarmult(A, h))


def keygen(seed=None):
    import os
    sk = seed if seed is not None else os.urandom(32)
    if len(sk) != 32:
        raise ValueError('seed must be 32 bytes')
    return sk, publickey(sk)
