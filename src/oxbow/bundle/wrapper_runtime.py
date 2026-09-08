#!/usr/bin/env python3
"""Standalone runtime embedded in generated .oxb.py handoff files.

This module intentionally depends only on the Python standard library. The
payload is data; this runtime provides bounded parsing, integrity verification,
orientation, document access, tours, and safe extraction for the locked public
Oxbow wire profile.
"""
from __future__ import print_function

import argparse
import base64
import hashlib
import json
import lzma
import os
import re
import sys
from pathlib import Path, PurePosixPath

_BUNDLE_NAME = "__OXBOW_BUNDLE_NAME__"
_FILES = __OXBOW_FILES__
_RAW_BYTES = __OXBOW_RAW_BYTES__
_PACKED_BYTES = __OXBOW_PACKED_BYTES__
_PAYLOAD_SHA256 = "__OXBOW_PAYLOAD_SHA256__"
_PAYLOAD_B85 = "__OXBOW_PAYLOAD_B85__"

MAGIC = b"RSB1"
VERSION = 5
WIRE_PROFILE = "rsb1-v5-public-kernel-1"
CONFORMANCE_PROFILE = "oxbow-conformance-v1"
MANIFEST_PATH = "manifests/MANIFEST.generated.json"
MANIFEST_FORMAT = "oxbow-manifest-v1"
PUBLIC_SECTION = "files"
REQUIRED_ROOT_DOCS = ("READ_FIRST.md", "BUNDLE_LAYOUT.md")
TOUR_ROOT_DOCS = ("START_HERE.md",)

MAX_BUNDLE_BYTES = 256 * 1024 * 1024
MAX_FILES = 10000
MAX_TOTAL_RAW_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_PATH_BYTES = 4096
MAX_SECTION_NAME_BYTES = 64


class BundleError(ValueError):
    pass


def _rv(data, off, max_value=(1 << 63) - 1):
    n = 0
    shift = 0
    for _ in range(10):
        if off >= len(data):
            raise BundleError("truncated varint")
        b = data[off]
        off += 1
        n |= (b & 127) << shift
        if n > max_value:
            raise BundleError("varint exceeds allowed range")
        if not (b & 128):
            return n, off
        shift += 7
    raise BundleError("varint is too long")


def _take(data, pos, n, what):
    if n < 0 or pos < 0 or pos + n > len(data):
        raise BundleError("truncated %s" % what)
    return data[pos:pos + n], pos + n


def _lzd6_bounded(data, max_output, what):
    dec = lzma.LZMADecompressor(
        format=lzma.FORMAT_RAW,
        filters=[{"id": lzma.FILTER_LZMA2, "preset": 6}],
    )
    out = bytearray()
    feed = data
    try:
        while True:
            remaining = max_output + 1 - len(out)
            if remaining <= 0:
                raise BundleError("%s exceeds decompression limit" % what)
            chunk = dec.decompress(feed, max_length=remaining)
            out.extend(chunk)
            feed = b""
            if len(out) > max_output:
                raise BundleError("%s exceeds decompression limit" % what)
            if dec.eof:
                if dec.unused_data:
                    raise BundleError("%s has trailing compressed data" % what)
                break
            if dec.needs_input:
                raise BundleError("truncated %s compressed stream" % what)
    except lzma.LZMAError as exc:
        raise BundleError("invalid %s compressed stream: %s" % (what, exc))
    return bytes(out)


def _validate_path(path):
    if not isinstance(path, str) or not path:
        raise BundleError("empty or non-text bundle path")
    if "\x00" in path or "\\" in path:
        raise BundleError("unsafe bundle path: %s" % path)
    try:
        pb = path.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise BundleError("bundle path is not valid UTF-8")
    if len(pb) > MAX_PATH_BYTES:
        raise BundleError("bundle path exceeds limit")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path) or ":" in path:
        raise BundleError("absolute, drive, or colon path is not portable: %s" % path)
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise BundleError("non-canonical bundle path: %s" % path)
    pp = PurePosixPath(path)
    if pp.is_absolute() or str(pp) != path:
        raise BundleError("non-canonical bundle path: %s" % path)
    return path


def _payload():
    encoded = "".join(_PAYLOAD_B85.split()).encode("ascii")
    if len(encoded) > int(MAX_BUNDLE_BYTES * 1.4) + 1024:
        raise BundleError("embedded base85 payload exceeds input limit")
    try:
        data = base64.b85decode(encoded)
    except Exception as exc:
        raise BundleError("invalid embedded base85 payload: %s" % exc)
    if len(data) > MAX_BUNDLE_BYTES:
        raise BundleError("embedded payload exceeds bundle-byte limit")
    got = hashlib.sha256(data).hexdigest()
    if got != _PAYLOAD_SHA256:
        raise BundleError("embedded payload sha256 does not match wrapper header")
    return data


def _decode_offsets(raw, count):
    pos = 0
    arr = []
    cumulative = 0
    for _ in range(count + 1):
        delta, pos = _rv(raw, pos, MAX_TOTAL_RAW_BYTES)
        cumulative += delta
        if cumulative > MAX_TOTAL_RAW_BYTES:
            raise BundleError("offset table exceeds raw-byte limit")
        arr.append(cumulative)
    if pos != len(raw) or not arr or arr[0] != 0:
        raise BundleError("invalid offset table")
    for a, b in zip(arr, arr[1:]):
        if b < a or b - a > MAX_FILE_BYTES:
            raise BundleError("invalid or over-limit file offset")
    return arr


def _decode_paths(raw, count):
    pos = 0
    rows = []
    seen = set()
    for _ in range(count):
        if pos >= len(raw):
            raise BundleError("truncated path table")
        pool = raw[pos]
        pos += 1
        if pool != 1:
            raise BundleError("public wrapper permits only local binary pool")
        ln, pos = _rv(raw, pos, MAX_PATH_BYTES)
        pb, pos = _take(raw, pos, ln, "path")
        try:
            path = pb.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise BundleError("bundle path is not valid UTF-8")
        _validate_path(path)
        if path in seen:
            raise BundleError("duplicate bundle path: %s" % path)
        seen.add(path)
        idx, pos = _rv(raw, pos, max(0, MAX_FILES - 1))
        rows.append((path, idx))
    if pos != len(raw):
        raise BundleError("path table has trailing bytes")
    return rows


def _parse(data):
    if len(data) > MAX_BUNDLE_BYTES:
        raise BundleError("payload exceeds bundle-byte limit")
    if len(data) < 5 or data[:4] != MAGIC or data[4] != VERSION:
        raise BundleError("not an RSB1 v5 payload")
    pos = 5
    for i in range(3):
        n, pos = _rv(data, pos, MAX_FILES)
        olen, pos = _rv(data, pos, MAX_BUNDLE_BYTES)
        _, pos = _take(data, pos, olen, "global offset stream")
        clen, pos = _rv(data, pos, MAX_BUNDLE_BYTES)
        _, pos = _take(data, pos, clen, "global codec stream")
        if n != 0 or olen != 0 or clen != 0:
            raise BundleError("unsupported legacy/global pool %d" % i)

    nsec, pos = _rv(data, pos, 2)
    if nsec != 1:
        raise BundleError("public wrapper requires exactly one section")
    name_len, pos = _rv(data, pos, MAX_SECTION_NAME_BYTES)
    name_b, pos = _take(data, pos, name_len, "section name")
    try:
        name = name_b.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise BundleError("section name is not valid UTF-8")
    if name != PUBLIC_SECTION:
        raise BundleError("unsupported section %r" % name)

    nt, pos = _rv(data, pos, MAX_FILES)
    nb, pos = _rv(data, pos, MAX_FILES)
    ng, pos = _rv(data, pos, MAX_FILES)
    np_, pos = _rv(data, pos, MAX_FILES)
    if nt != 0 or ng != 0 or nb != np_:
        raise BundleError("public wrapper permits one binary record per path only")

    plen, pos = _rv(data, pos, MAX_BUNDLE_BYTES)
    pcode, pos = _take(data, pos, plen, "path table codec")
    max_path_table = min(MAX_TOTAL_RAW_BYTES, max(1, np_) * (MAX_PATH_BYTES + 32))
    praw = _lzd6_bounded(pcode, max_path_table, "path table")
    rows = _decode_paths(praw, np_)

    if nb:
        olen, pos = _rv(data, pos, MAX_BUNDLE_BYTES)
        ocode, pos = _take(data, pos, olen, "offset table codec")
        oraw = _lzd6_bounded(ocode, min(MAX_TOTAL_RAW_BYTES, (nb + 1) * 10), "offset table")
        offsets = _decode_offsets(oraw, nb)
        clen, pos = _rv(data, pos, MAX_BUNDLE_BYTES)
        ccode, pos = _take(data, pos, clen, "file data codec")
        concat = _lzd6_bounded(ccode, MAX_TOTAL_RAW_BYTES, "file data")
    else:
        offsets = [0]
        concat = b""

    if pos != len(data):
        raise BundleError("payload has trailing bytes")
    if offsets[-1] != len(concat):
        raise BundleError("offset table does not reconcile with decoded bytes")
    indexes = [idx for _, idx in rows]
    if sorted(indexes) != list(range(nb)):
        raise BundleError("binary indexes are not an exact 0..N-1 permutation")

    files = []
    for path, idx in rows:
        files.append((path, concat[offsets[idx]:offsets[idx + 1]]))
    return files


def _manifest_records(doc):
    errors = []
    out = []
    if not isinstance(doc, dict):
        return out, ["manifest root is not an object"]
    records = doc.get("files")
    seen = set()
    if not isinstance(records, list):
        return out, ["manifest files is not a list"]
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            errors.append("manifest record %d is not an object" % i)
            continue
        path = rec.get("path")
        size = rec.get("bytes")
        sha = rec.get("sha256")
        if not isinstance(path, str) or not isinstance(sha, str):
            errors.append("manifest record %d lacks path/sha256" % i)
            continue
        if not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
            errors.append("manifest record %d has invalid sha256" % i)
            continue
        if size is not None and (not isinstance(size, int) or size < 0):
            errors.append("manifest record %d has invalid bytes" % i)
            continue
        if path in seen:
            errors.append("duplicate manifest path: %s" % path)
            continue
        seen.add(path)
        out.append((path, size, sha.lower()))
    return out, errors


def _verify_integrity(files):
    mapping = dict(files)
    if MANIFEST_PATH not in mapping:
        return {"ok": False, "error": "manifest missing", "checked": 0}
    try:
        doc = json.loads(mapping[MANIFEST_PATH].decode("utf-8"))
    except Exception as exc:
        return {"ok": False, "error": "manifest unreadable: %s" % exc, "checked": 0}
    records, errors = _manifest_records(doc)
    if doc.get("format") != MANIFEST_FORMAT:
        errors.append("manifest format must be %s" % MANIFEST_FORMAT)
    expected = {}
    for path, size, sha in records:
        try:
            _validate_path(path)
        except BundleError as exc:
            errors.append("unsafe manifest path %s: %s" % (path, exc))
            continue
        if path == MANIFEST_PATH:
            errors.append("manifest must not list itself")
            continue
        expected[path] = (size, sha)
    actual = dict((p, b) for p, b in files if p != MANIFEST_PATH)
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    mismatched = []
    checked = 0
    for path in sorted(set(expected) & set(actual)):
        size, sha = expected[path]
        blob = actual[path]
        bad = []
        if size is not None and len(blob) != size:
            bad.append("bytes")
        if hashlib.sha256(blob).hexdigest() != sha:
            bad.append("sha256")
        if bad:
            mismatched.append({"path": path, "fields": bad})
        checked += 1
    ok = not errors and not missing and not unexpected and not mismatched
    return {
        "ok": ok,
        "checked": checked,
        "expected": len(expected),
        "actual": len(actual),
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
        "manifest_errors": errors,
    }


def _tour_tracks(mapping):
    tracks = {}
    for path in mapping:
        if path.startswith("tours/") and path.endswith(".md") and "/" not in path[len("tours/"):]:
            tracks[path[len("tours/"):-3].lower()] = path
        elif "/" not in path and path.startswith("TOUR") and path.endswith(".md"):
            name = path[:-3].replace("TOUR", "").strip("_- ").lower() or "default"
            tracks[name] = path
    if "default" not in tracks:
        for path in ("START_HERE.md", "READ_FIRST.md", "BUNDLE_LAYOUT.md"):
            if path in mapping:
                tracks["default"] = path
                break
    return tracks


def _verify_conformance(files):
    paths = set(p for p, _ in files)
    missing = [p for p in REQUIRED_ROOT_DOCS if p not in paths]
    tours = _tour_tracks(dict(files))
    if not tours:
        missing.append("START_HERE.md or a tour surface")
    return {
        "ok": not missing,
        "profile": CONFORMANCE_PROFILE,
        "required_root_docs": list(REQUIRED_ROOT_DOCS),
        "tour_surfaces": sorted(tours.values()),
        "missing": missing,
    }


def _verify():
    data = _payload()
    wrapper = {
        "ok": hashlib.sha256(data).hexdigest() == _PAYLOAD_SHA256,
        "payload_sha256": hashlib.sha256(data).hexdigest(),
        "note": "internal consistency only; this does not authenticate an author",
    }
    try:
        files = _parse(data)
    except BundleError as exc:
        return {
            "ok": False,
            "wrapper": wrapper,
            "wire": {"ok": False, "profile": WIRE_PROFILE, "error": str(exc)},
            "integrity": {"ok": False, "why": "wire parse failed"},
            "conformance": {"ok": False, "why": "wire parse failed"},
        }
    raw = sum(len(b) for _, b in files)
    wire = {
        "ok": True,
        "magic": "RSB1",
        "version": VERSION,
        "profile": WIRE_PROFILE,
        "payload_bytes": len(data),
        "files": len(files),
        "raw_bytes": raw,
    }
    integrity = _verify_integrity(files)
    conformance = _verify_conformance(files)
    meta_ok = len(files) == _FILES and raw == _RAW_BYTES and len(data) == _PACKED_BYTES
    wrapper["metadata_matches_payload"] = meta_ok
    wrapper["ok"] = bool(wrapper["ok"] and meta_ok)
    return {
        "ok": bool(wrapper["ok"] and wire["ok"] and integrity["ok"] and conformance["ok"]),
        "wrapper": wrapper,
        "wire": wire,
        "integrity": integrity,
        "conformance": conformance,
    }


def _prepare_dest(dest):
    dest = Path(dest)
    if dest.exists():
        if dest.is_symlink():
            raise BundleError("extraction destination may not be a symlink")
        if not dest.is_dir():
            raise BundleError("extraction destination exists and is not a directory")
        try:
            next(dest.iterdir())
        except StopIteration:
            pass
        else:
            raise BundleError("extraction destination must be new or empty")
    else:
        dest.mkdir(parents=True)
    return dest.resolve()


def _extract(files, dest):
    root = _prepare_dest(dest)
    count = 0
    total = 0
    for path, blob in files:
        _validate_path(path)
        target = root.joinpath(*PurePosixPath(path).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        parent = target.parent.resolve()
        if root != parent and root not in parent.parents:
            raise BundleError("extraction path escaped destination: %s" % path)
        if target.exists() or target.is_symlink():
            raise BundleError("refusing to overwrite extraction path: %s" % path)
        target.write_bytes(blob)
        count += 1
        total += len(blob)
    return count, total


def _info(files, data):
    mapping = dict(files)
    tracks = _tour_tracks(mapping)
    return {
        "name": _BUNDLE_NAME,
        "wrapper": "oxbow-self-extracting-v1",
        "magic": "RSB1",
        "version": VERSION,
        "wire_profile": WIRE_PROFILE,
        "payload_bytes": len(data),
        "files": len(files),
        "raw_bytes": sum(len(b) for _, b in files),
        "doors": [p for p in ("READ_FIRST.md", "START_HERE.md", "BUNDLE_LAYOUT.md") if p in mapping],
        "tour_tracks": sorted(tracks),
        "payload_sha256": hashlib.sha256(data).hexdigest(),
    }


def _orientation(files, data):
    info = _info(files, data)
    print("%s  (Oxbow bundle, self-extracting)" % info["name"])
    print("  %s files, %s bytes raw, %s packed" % (
        format(info["files"], ","), format(info["raw_bytes"], ","), format(info["payload_bytes"], ",")))
    print("  doors: %s" % (", ".join(info["doors"]) or "none"))
    print("  tours: %s" % (", ".join(info["tour_tracks"]) or "none"))
    print()
    print("  --read-first        print the front door")
    print("  --tour [TRACK]      print a guided tour/start surface")
    print("  --verify            verify wrapper, wire, manifest, and handoff conformance")
    print("  --list / --ls       list bundled paths")
    print("  --doc / --cat PATH  print one document as text")
    print("  --extract DIR       unpack everything into a new/empty directory")
    print("  --payload-out PATH  write the inert .oxb data twin")
    print("  --info              machine-readable summary")
    print()
    print("Security note: this file is executable Python. For an untrusted wrapper,")
    print("inspect it with a trusted Oxbow CLI instead of executing it.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Oxbow self-extracting handoff bundle")
    ap.add_argument("--info", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--extract", metavar="DIR")
    ap.add_argument("--read-first", action="store_true")
    ap.add_argument("--doc", metavar="PATH")
    ap.add_argument("--cat", metavar="PATH")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--ls", action="store_true")
    ap.add_argument("--tour", nargs="?", const="default", metavar="TRACK")
    ap.add_argument("--payload-out", metavar="PATH")
    a = ap.parse_args(argv)
    try:
        data = _payload()
        if a.verify:
            result = _verify()
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result.get("ok") else 1
        files = _parse(data)
        mapping = dict(files)
        if a.info:
            print(json.dumps(_info(files, data), indent=2, sort_keys=True))
            return 0
        if a.list or a.ls:
            for path in sorted(mapping):
                print(path)
            return 0
        if a.read_first:
            path = "READ_FIRST.md"
            if path not in mapping:
                print("READ_FIRST.md not found in bundle", file=sys.stderr)
                return 1
            sys.stdout.write(mapping[path].decode("utf-8", errors="replace"))
            return 0
        doc_path = a.doc or a.cat
        if doc_path:
            _validate_path(doc_path)
            if doc_path not in mapping:
                print("%s not found in bundle" % doc_path, file=sys.stderr)
                return 1
            sys.stdout.write(mapping[doc_path].decode("utf-8", errors="replace"))
            return 0
        if a.tour is not None:
            tracks = _tour_tracks(mapping)
            if not tracks:
                print("This bundle ships no tour/start surface.", file=sys.stderr)
                return 1
            track = (a.tour or "default").lower()
            if track not in tracks:
                print("no track '%s'. tracks: %s" % (track, ", ".join(sorted(tracks))), file=sys.stderr)
                return 1
            sys.stdout.write(mapping[tracks[track]].decode("utf-8", errors="replace"))
            return 0
        if a.extract:
            integrity = _verify_integrity(files)
            if not integrity["ok"]:
                print(json.dumps({"ok": False, "integrity": integrity}, indent=2, sort_keys=True), file=sys.stderr)
                return 1
            count, total = _extract(files, a.extract)
            print("extracted %d files, %d bytes -> %s" % (count, total, a.extract))
            return 0
        if a.payload_out:
            p = Path(a.payload_out)
            if p.exists():
                raise BundleError("payload output already exists: %s" % p)
            p.write_bytes(data)
            print("wrote inert payload -> %s" % p)
            return 0
        _orientation(files, data)
        return 0
    except (BundleError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
