#!/usr/bin/env python3
"""Build and ship either inert ``.oxb`` data or a transparent ``.oxb.py`` wrapper."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from oxbow.bundle import kernel
from oxbow.bundle.wrapper import write_wrapper


def _run(args):
    return subprocess.run([sys.executable, "-m", "oxbow.bundle.cli"] + list(args))


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _sig_doc(payload: bytes, key_path: str):
    from oxbow.bundle import ed25519 as E
    import hashlib

    key = json.loads(Path(key_path).read_text())
    sk = bytes.fromhex(key["secret_key"])
    pk = bytes.fromhex(key["public_key"])
    sig = E.sign(payload, sk, pk)
    return {
        "format": "oxbow-sig-v1",
        "algo": "ed25519",
        "public_key": pk.hex(),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "signature": sig.hex(),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oxbow ship")
    ap.add_argument("source", help="source tree to pack")
    ap.add_argument("-o", "--output", required=True, help="output .oxb or .oxb.py path")
    ap.add_argument("--profile", default="default")
    ap.add_argument("--key", help="optional signing key JSON; signature covers payload bytes")
    ap.add_argument("--data-out", help="with .oxb.py output, also keep the inert .oxb twin here")
    ap.add_argument("--report", help="optional build-report JSON path")
    a = ap.parse_args(argv)

    source_arg = Path(a.source)
    if source_arg.is_symlink():
        print("error: source root may not be a symlink", file=sys.stderr)
        return 2
    root = source_arg.resolve()
    out = Path(a.output).resolve()
    if out.exists():
        print("error: output already exists: %s" % out, file=sys.stderr)
        return 2
    if _is_within(out, root):
        print("error: output must be outside the source tree", file=sys.stderr)
        return 2

    wrapper_mode = out.name.endswith(".oxb.py")
    data_mode = out.suffix == ".oxb" and not wrapper_mode
    if not (wrapper_mode or data_mode):
        print("error: output must end in .oxb or .oxb.py", file=sys.stderr)
        return 2
    if a.data_out and not wrapper_mode:
        print("error: --data-out is only valid when shipping .oxb.py", file=sys.stderr)
        return 2

    data_out = Path(a.data_out).resolve() if a.data_out else None
    if data_out:
        if data_out.exists():
            print("error: --data-out already exists: %s" % data_out, file=sys.stderr)
            return 2
        if _is_within(data_out, root):
            print("error: --data-out must be outside the source tree", file=sys.stderr)
            return 2
    report = Path(a.report).resolve() if a.report else None
    if report and _is_within(report, root):
        print("error: --report must be outside the source tree", file=sys.stderr)
        return 2

    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="oxbow-ship-") as td:
        temp_payload = Path(td) / "payload.oxb"
        cmd = ["build", str(root), "-o", str(temp_payload), "--profile", a.profile]
        if report:
            cmd.extend(["--report", str(report)])
        print("[1/4] build hardened payload")
        if _run(cmd).returncode:
            return 1

        print("[2/4] verify wire + exact manifest + handoff conformance")
        if _run(["verify", str(temp_payload)]).returncode:
            return 1

        payload = temp_payload.read_bytes()
        if data_mode:
            print("[3/4] publish inert data payload")
            shutil.copyfile(str(temp_payload), str(out))
        else:
            print("[3/4] generate standalone .oxb.py wrapper and self-verify")
            try:
                write_wrapper(payload, out, self_check=True)
            except Exception as exc:
                print("error: wrapper generation failed: %s" % exc, file=sys.stderr)
                return 1
            if data_out:
                data_out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(str(temp_payload), str(data_out))
                print("      inert twin -> %s" % data_out)

        if a.key:
            print("[4/4] sign embedded/data payload with detached Ed25519 signature")
            try:
                doc = _sig_doc(payload, a.key)
                sig_path = Path(str(out) + ".sig")
                sig_path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
            except Exception as exc:
                try:
                    out.unlink()
                except OSError:
                    pass
                print("error: signing failed: %s" % exc, file=sys.stderr)
                return 1
            if _run(["verify", str(out), "--sig", str(sig_path), "--require-signature"]).returncode:
                return 1
        else:
            print("[4/4] unsigned (authenticity intentionally not claimed)")

    mode = "self-extracting Python wrapper" if wrapper_mode else "inert data"
    print("shipped %s (%d bytes, %s)" % (out, out.stat().st_size, mode))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
