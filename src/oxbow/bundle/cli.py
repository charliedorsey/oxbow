#!/usr/bin/env python3
"""Oxbow bundle CLI for the locked public correctness kernel.

Build emits the deliberately small public RSB1 subset. Read, verify, extract,
and wrapper inspection accept that subset only. Historical Rosetta decoding is
kept outside the installed package under the repository compatibility boundary.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from oxbow.bundle import kernel


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _load_public_payload(path: str) -> bytes:
    """Load raw .oxb or a generated base85 wrapper without executing it.

    Wrapper inspection verifies only the embedded payload. It does not establish
    that arbitrary executable source surrounding that payload is safe to run.
    Historical wrapper-level compression is intentionally unsupported here.
    """
    p = Path(path)
    st = p.stat()
    max_wrapper = kernel.DEFAULT_LIMITS.max_bundle_bytes * 2
    if st.st_size > max_wrapper:
        raise kernel.KernelError("bundle/wrapper exceeds input byte limit")
    b = p.read_bytes()
    if b[:4] == kernel.MAGIC:
        if len(b) > kernel.DEFAULT_LIMITS.max_bundle_bytes:
            raise kernel.KernelError("payload exceeds bundle-byte limit")
        return b
    try:
        text = b.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise kernel.KernelError("not an RSB1 payload or supported text wrapper")
    m = (
        re.search(r"_PAYLOAD_B85\s*=\s*'''(.*?)'''", text, re.S)
        or re.search(r'_PAYLOAD_B85\s*=\s*"""(.*?)"""', text, re.S)
        or re.search(r'_PAYLOAD_B85\s*=\s*"([^"]+)"', text, re.S)
        or re.search(r"_PAYLOAD_B85\s*=\s*'([^']+)'", text, re.S)
    )
    if not m:
        raise kernel.KernelError("not an RSB1 payload and no _PAYLOAD_B85 found")
    encoded = "".join(m.group(1).split()).encode("ascii")
    if len(encoded) > int(kernel.DEFAULT_LIMITS.max_bundle_bytes * 1.4) + 1024:
        raise kernel.KernelError("embedded base85 payload exceeds input limit")
    try:
        payload = base64.b85decode(encoded)
    except Exception as exc:
        raise kernel.KernelError("invalid embedded base85 payload: %s" % exc)
    if len(payload) > kernel.DEFAULT_LIMITS.max_bundle_bytes:
        raise kernel.KernelError("embedded payload exceeds bundle-byte limit")
    if payload[:4] != kernel.MAGIC:
        raise kernel.KernelError(
            "historical compressed wrapper payload is not accepted by the public kernel"
        )
    return payload


def _tour_tracks(files):
    tracks = {}
    for p in files:
        if p.startswith("tours/") and p.endswith(".md") and "/" not in p[len("tours/"):]:
            tracks[p[len("tours/"):-3].lower()] = p
        elif "/" not in p and p.startswith("TOUR") and p.endswith(".md"):
            name = p[:-3].replace("TOUR", "").strip("_- ").lower() or "default"
            tracks[name] = p
    if "default" not in tracks:
        for d in ("START_HERE.md", "READ_FIRST.md", "BUNDLE_LAYOUT.md"):
            if d in files:
                tracks["default"] = d
                break
    return tracks


def _build_report(scan, profile_name, profile, payload, verify):
    included = []
    for path, blob in scan.files:
        included.append({
            "path": path,
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        })
    return {
        "format": "oxbow-build-report-v1",
        "wire_profile": kernel.WIRE_PROFILE,
        "codec_set": ["lzma2-raw-preset6"],
        "profile": profile_name,
        "profile_notes": list(profile.get("notes") or []),
        "included_files": len(included),
        "included_raw_bytes": scan.raw_bytes,
        "excluded_files": len(scan.excluded),
        "included": included,
        "excluded": scan.excluded,
        "payload_bytes": len(payload),
        "verification": verify,
    }


def cmd_build(a):
    from oxbow.bundle import profiles as _profiles

    source_arg = Path(a.source)
    if source_arg.is_symlink():
        raise kernel.SourceError("source root may not be a symlink")
    root = source_arg.resolve()
    out = Path(a.output).resolve()
    report = Path(a.report).resolve() if a.report else out.with_suffix(".report.json")
    if _is_within(out, root):
        raise kernel.SourceError("output must be outside the source tree")
    if _is_within(report, root):
        raise kernel.SourceError("build report must be outside the source tree")

    pname = getattr(a, "profile", None) or "default"
    keep, prof = _profiles.selector(_profiles.load(str(root)), pname)
    scan = kernel.scan_source(root, keep=keep)
    payload = kernel.build_bundle_bytes(scan.files)
    verify = kernel.verify_bundle_bytes(payload)

    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp-%d" % os.getpid())
    tmp.write_bytes(payload)
    os.replace(str(tmp), str(out))

    rep = _build_report(scan, pname, prof, payload, verify)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")

    print(
        "built %s (%d source files + manifest, %d bytes) — wire=%s integrity=%s conformance=%s"
        % (
            out,
            len(scan.files),
            len(payload),
            verify["wire"]["ok"],
            verify["integrity"]["ok"],
            verify["conformance"]["ok"],
        )
    )
    if scan.excluded:
        print(
            "%d source paths excluded by the named profile / always-exclude policy; see %s"
            % (len(scan.excluded), report),
            file=sys.stderr,
        )
    if not verify["conformance"]["ok"]:
        print(
            "bundle bytes are valid and manifest-exact, but the handoff is non-conformant: %s"
            % ", ".join(verify["conformance"].get("missing") or []),
            file=sys.stderr,
        )
    return 0 if verify["ok"] else 1


def cmd_profiles(a):
    from oxbow.bundle import profiles as _profiles

    root = Path(a.root).resolve()
    if a.write:
        dest = root / _profiles.PROFILE_FILE
        if dest.exists():
            print("%s already exists — not overwriting" % dest)
            return 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(_profiles.starter_json())
        print("wrote %s — edit it, then `build --profile <name>`" % dest)
        return 0
    profs = _profiles.load(str(root))
    src = _profiles.PROFILE_FILE if (root / _profiles.PROFILE_FILE).exists() else "built-in defaults"
    print("profiles (%s):" % src)
    print(_profiles.describe(profs))
    return 0


def cmd_health(a):
    from oxbow.bundle.health import main as health_main

    args = [a.root]
    if getattr(a, "quiet", False):
        args.append("--quiet")
    if getattr(a, "verbose", False):
        args.append("--verbose")
    return health_main(args)


def cmd_keygen(a):
    from oxbow.bundle import ed25519 as E

    sk, pk = E.keygen()
    key = {
        "format": "oxbow-key-v1",
        "algo": "ed25519",
        "secret_key": sk.hex(),
        "public_key": pk.hex(),
    }
    Path(a.output).write_text(json.dumps(key, indent=2) + "\n")
    Path(a.output).chmod(0o600)
    print("wrote %s  public_key=%s" % (a.output, pk.hex()))
    print("guard the secret; distribute the public key through a trusted channel.")
    return 0


def _sig_doc(data, key):
    from oxbow.bundle import ed25519 as E

    sk = bytes.fromhex(key["secret_key"])
    pk = bytes.fromhex(key["public_key"])
    sig = E.sign(data, sk, pk)
    return {
        "format": "oxbow-sig-v1",
        "algo": "ed25519",
        "public_key": pk.hex(),
        "payload_sha256": hashlib.sha256(data).hexdigest(),
        "signature": sig.hex(),
    }


def _check_sig(data, doc, expect_pk=None):
    from oxbow.bundle import ed25519 as E

    try:
        if doc.get("algo") != "ed25519":
            return False, "unknown algo"
        pk_hex = doc["public_key"]
        pk = bytes.fromhex(pk_hex)
        if expect_pk and pk_hex.lower() != expect_pk.lower():
            return False, "public key does not match --pubkey"
        if hashlib.sha256(data).hexdigest() != doc.get("payload_sha256"):
            return False, "payload sha256 mismatch"
        ok = E.verify(bytes.fromhex(doc["signature"]), data, pk)
        return ok, ("signature valid" if ok else "SIGNATURE INVALID")
    except Exception as exc:
        return False, "invalid signature document: %s" % exc


def cmd_sign(a):
    key = json.loads(Path(a.key).read_text())
    data = _load_public_payload(a.bundle)
    kernel.parse(data)  # refuse to sign malformed / unsupported public bundles
    doc = _sig_doc(data, key)
    out = a.output or (str(a.bundle) + ".sig")
    Path(out).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print("signed -> %s  (ed25519 over payload bytes; sha256 %s...)" % (out, doc["payload_sha256"][:16]))
    return 0


def cmd_info(a):
    data = _load_public_payload(a.bundle)
    view = kernel.parse(data)
    files = view.mapping
    tracks = _tour_tracks(files)
    verified = kernel.verify_bundle_bytes(data)
    info = {
        "magic": kernel.MAGIC.decode("ascii"),
        "version": kernel.VERSION,
        "wire_profile": kernel.WIRE_PROFILE,
        "payload_bytes": view.payload_bytes,
        "files": len(view.files),
        "raw_bytes": view.raw_bytes,
        "doors": [p for p in ("READ_FIRST.md", "START_HERE.md", "BUNDLE_LAYOUT.md") if p in files],
        "tour_tracks": sorted(tracks),
        "integrity_ok": bool(verified.get("integrity", {}).get("ok")),
        "conformance_ok": bool(verified.get("conformance", {}).get("ok")),
    }
    print(json.dumps(info, indent=2, sort_keys=True))
    return 0


def cmd_list(a):
    data = _load_public_payload(a.bundle)
    for path in sorted(kernel.parse(data).mapping):
        print(path)
    return 0


def cmd_verify(a):
    input_path = Path(a.bundle)
    try:
        prefix = input_path.read_bytes()[:4]
    except OSError:
        prefix = b""
    wrapper_input = prefix != kernel.MAGIC
    try:
        data = _load_public_payload(a.bundle)
        result = kernel.verify_bundle_bytes(data)
    except (OSError, kernel.KernelError) as exc:
        result = {
            "ok": False,
            "wire": {"ok": False, "profile": kernel.WIRE_PROFILE, "error": str(exc)},
            "integrity": {"ok": False, "why": "wire load/parse failed"},
            "conformance": {"ok": False, "why": "wire load/parse failed"},
        }
        data = None

    sig = getattr(a, "sig", None)
    authenticity = {"ok": None, "why": "no signature supplied"}
    if sig and data is not None:
        try:
            doc = json.loads(Path(sig).read_text())
            ok, why = _check_sig(data, doc, getattr(a, "pubkey", None))
            authenticity = {"ok": ok, "why": why, "public_key": doc.get("public_key")}
        except Exception as exc:
            authenticity = {"ok": False, "why": "signature read failed: %s" % exc}
        result["ok"] = bool(result.get("ok") and authenticity["ok"])
    elif sig:
        authenticity = {"ok": False, "why": "bundle could not be parsed"}
        result["ok"] = False

    mode = getattr(a, "mode", "read")
    if mode == "act":
        if not sig:
            authenticity = {"ok": False, "why": "--mode act requires --sig"}
            result["ok"] = False
        elif not getattr(a, "pubkey", None):
            authenticity = {"ok": False, "why": "--mode act requires --pubkey to pin the signer"}
            result["ok"] = False
    if getattr(a, "require_signature", False) and not sig:
        authenticity = {
            "ok": False,
            "why": "--require-signature given but no --sig was supplied",
        }
        result["ok"] = False
    result["authenticity"] = authenticity
    if wrapper_input:
        result["wrapper_source"] = {
            "executed": False,
            "authenticated": False,
            "why": "trusted CLI verified the embedded payload only; executable wrapper source was not run or authenticated",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 1


def cmd_extract(a):
    data = _load_public_payload(a.bundle)
    view = kernel.parse(data)
    integrity = kernel.verify_integrity(view)
    if not integrity["ok"]:
        print(json.dumps({"ok": False, "integrity": integrity}, indent=2, sort_keys=True))
        return 1
    n, by = kernel.extract_view(view, Path(a.dest))
    print("extracted %d files, %d bytes -> %s" % (n, by, a.dest))
    return 0


def cmd_read_first(a):
    data = _load_public_payload(a.bundle)
    files = kernel.parse(data).mapping
    if "READ_FIRST.md" not in files:
        print("READ_FIRST.md not found in bundle")
        return 1
    print(files["READ_FIRST.md"].decode("utf-8", errors="replace"))
    return 0


def cmd_doc(a):
    data = _load_public_payload(a.bundle)
    files = kernel.parse(data).mapping
    if a.path not in files:
        print("%s not found in bundle" % a.path)
        return 1
    sys.stdout.write(files[a.path].decode("utf-8", errors="replace"))
    return 0


def cmd_tour(a):
    data = _load_public_payload(a.bundle)
    files = kernel.parse(data).mapping
    tracks = _tour_tracks(files)
    if not tracks:
        print("This bundle ships no tour/start surface.")
        return 1
    if not a.track:
        if "default" in tracks:
            a.track = "default"
        elif len(tracks) == 1:
            a.track = next(iter(tracks))
        else:
            print("tracks: %s" % ", ".join(sorted(tracks)))
            return 0
    t = a.track.lower()
    if t not in tracks:
        print("no track '%s'. tracks: %s" % (a.track, ", ".join(sorted(tracks))))
        return 1
    print(files[tracks[t]].decode("utf-8", errors="replace"))
    return 0


def cmd_wrap(a):
    from oxbow.bundle.wrapper import write_wrapper

    data = _load_public_payload(a.bundle)
    out = Path(a.output)
    write_wrapper(data, out, name=a.name, self_check=not a.no_self_check)
    status = "standalone verify skipped" if a.no_self_check else "standalone verify passed"
    print("wrapped %s -> %s (%d payload bytes, %s)" % (a.bundle, out, len(data), status))
    if a.key:
        key = json.loads(Path(a.key).read_text())
        doc = _sig_doc(data, key)
        sig = str(out) + ".sig"
        Path(sig).write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
        print("signed embedded payload -> %s" % sig)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oxbow bundle")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("source")
    b.add_argument("-o", "--output", required=True)
    b.add_argument("--report")
    b.add_argument("--profile", default="default")
    b.set_defaults(f=cmd_build)

    for name, func in (("info", cmd_info), ("read-first", cmd_read_first), ("list", cmd_list)):
        p = sub.add_parser(name)
        p.add_argument("bundle")
        p.set_defaults(f=func)

    vf = sub.add_parser("verify")
    vf.add_argument("bundle")
    vf.add_argument("--sig", help="detached signature file (oxbow-sig-v1 JSON)")
    vf.add_argument("--pubkey", help="required public key hex — pin the signer")
    vf.add_argument("--require-signature", action="store_true")
    vf.add_argument("--mode", choices=("read", "act"), default="read",
                    help="read: integrity/conformance may be useful unsigned; act: require signature + pinned public key")
    vf.set_defaults(f=cmd_verify)

    e = sub.add_parser("extract")
    e.add_argument("bundle")
    e.add_argument("-d", "--dest", required=True)
    e.set_defaults(f=cmd_extract)

    pf = sub.add_parser("profiles")
    pf.add_argument("root", nargs="?", default=".")
    pf.add_argument("--write", action="store_true")
    pf.set_defaults(f=cmd_profiles)

    hl = sub.add_parser("health")
    hl.add_argument("root", nargs="?", default=".")
    hl.add_argument("--quiet", action="store_true")
    hl.add_argument("--verbose", action="store_true")
    hl.set_defaults(f=cmd_health)

    dc = sub.add_parser("doc")
    dc.add_argument("bundle")
    dc.add_argument("path")
    dc.set_defaults(f=cmd_doc)

    w = sub.add_parser("wrap")
    w.add_argument("bundle")
    w.add_argument("-o", "--output", required=True)
    w.add_argument("--name")
    w.add_argument("--key", help="optional signing key; signature covers embedded payload bytes")
    w.add_argument("--no-self-check", action="store_true", help="skip executing generated wrapper --verify")
    w.set_defaults(f=cmd_wrap)

    kg = sub.add_parser("keygen")
    kg.add_argument("-o", "--output", required=True)
    kg.set_defaults(f=cmd_keygen)

    sg = sub.add_parser("sign")
    sg.add_argument("bundle")
    sg.add_argument("--key", required=True)
    sg.add_argument("-o", "--output")
    sg.set_defaults(f=cmd_sign)

    t = sub.add_parser("tour")
    t.add_argument("bundle")
    t.add_argument("track", nargs="?")
    t.set_defaults(f=cmd_tour)

    a = ap.parse_args(argv)
    try:
        return a.f(a)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        return 0
    except (kernel.KernelError, kernel.SourceError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
