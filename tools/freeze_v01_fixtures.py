#!/usr/bin/env python3
"""Regenerate v0.1 release fixtures.

Run only when intentionally changing the wire/release fixture set. The signing
seed is public test material and must never be used for real trust decisions.
"""
from __future__ import annotations

import hashlib
import json
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from oxbow.bundle import ed25519, kernel
from oxbow.bundle.wrapper import write_wrapper

OUT = ROOT / "tests" / "fixtures" / "v0.1"
EXAMPLE = ROOT / "examples" / "tiny-handoff"
TEST_SEED = bytes.fromhex("1f" * 32)


def unsafe_payload(files):
    paths = [p for p, _ in files]
    blobs = [b for _, b in files]
    paths_code = kernel._encode_paths(paths)
    offsets_code = kernel._encode_offsets(blobs)
    data_code = kernel._lzc6(b"".join(blobs))
    out = bytearray(kernel.MAGIC)
    out.append(kernel.VERSION)
    for _ in range(3):
        kernel._wv(0, out); kernel._wv(0, out); kernel._wv(0, out)
    kernel._wv(1, out)
    name = kernel.PUBLIC_SECTION.encode("utf-8")
    kernel._wv(len(name), out); out.extend(name)
    kernel._wv(0, out); kernel._wv(len(blobs), out); kernel._wv(0, out); kernel._wv(len(paths), out)
    kernel._wv(len(paths_code), out); out.extend(paths_code)
    if blobs:
        kernel._wv(len(offsets_code), out); out.extend(offsets_code)
        kernel._wv(len(data_code), out); out.extend(data_code)
    return bytes(out)


def orientation_files():
    return [
        ("READ_FIRST.md", b"# Read first\n\nSynthetic release fixture.\n"),
        ("BUNDLE_LAYOUT.md", b"# Layout\n\nSynthetic release fixture.\n"),
        ("START_HERE.md", b"# Start\n\nInspect the fixture.\n"),
    ]


def sign_doc(payload, sk, pk):
    sig = ed25519.sign(payload, sk, pk)
    return {
        "format": "oxbow-sig-v1",
        "algo": "ed25519",
        "public_key": pk.hex(),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "signature": sig.hex(),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for p in OUT.iterdir():
        if p.name not in ("README.md",):
            if p.is_file() or p.is_symlink():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)

    scan = kernel.scan_source(EXAMPLE)
    tiny = kernel.build_bundle_bytes(scan.files)
    (OUT / "tiny-handoff.oxb").write_bytes(tiny)
    write_wrapper(tiny, OUT / "tiny-handoff.oxb.py", name="tiny-handoff", self_check=True)

    (OUT / "tiny-handoff-signed.oxb").write_bytes(tiny)
    sk, pk = ed25519.keygen(TEST_SEED)
    (OUT / "tiny-handoff-signed.oxb.sig").write_text(
        json.dumps(sign_doc(tiny, sk, pk), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "TEST_PUBLIC_KEY.txt").write_text(pk.hex() + "\n", encoding="ascii")

    rng = random.Random(701)
    binary = orientation_files() + [
        ("binary/random.bin", bytes(rng.randrange(256) for _ in range(16384))),
        ("binary/zero.bin", b""),
        ("images/sample.png", b"\x89PNG\r\n\x1a\n" + bytes(range(128))),
        ("docs/sample.pdf", b"%PDF-1.4\n% synthetic fixture\n%%EOF\n"),
        ("audio/sample.wav", b"RIFF" + b"\x00" * 256),
        ("archives/sample.zip", b"PK\x03\x04" + bytes(range(64))),
    ]
    (OUT / "binary-heavy.oxb").write_bytes(kernel.build_bundle_bytes(binary))

    (OUT / "invalid-parent-path.oxb").write_bytes(
        unsafe_payload([("../escape.txt", b"x")])
    )
    (OUT / "invalid-duplicate-path.oxb").write_bytes(
        unsafe_payload([("same.txt", b"a"), ("same.txt", b"b")])
    )

    checks = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name not in ("SHA256SUMS.txt", "README.md"):
            checks.append("%s  %s" % (hashlib.sha256(p.read_bytes()).hexdigest(), p.name))
    (OUT / "SHA256SUMS.txt").write_text("\n".join(checks) + "\n", encoding="ascii")
    print("froze %d fixture files in %s" % (len(checks), OUT))


if __name__ == "__main__":
    main()
