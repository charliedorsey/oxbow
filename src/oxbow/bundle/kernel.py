#!/usr/bin/env python3
"""Small, defensive Oxbow correctness kernel.

Phase B deliberately makes the default public wire boring:

* RSB1 version 5 framing is retained for continuity with the recovered lineage.
* The public encoder emits ONE section named ``files``.
* Every payload file is stored in the binary pool.
* Paths, offsets, and concatenated bytes use raw LZMA2 preset 6 only.
* No file type is silently dropped by the encoder.
* No specialist Rosetta-era codec can be emitted by this module.

The recovered historical decoder remains in ``compat/rosetta_v5/reference_decoder.py`` for archaeology and
later compatibility work. Public build/verify/extract uses this module instead.
It accepts only the deliberately small public-kernel subset, which makes bounded
untrusted decoding possible without inheriting the historical decoder's much
larger attack surface.
"""
from __future__ import annotations

import hashlib
import json
import lzma
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

MAGIC = b"RSB1"
VERSION = 5
PUBLIC_SECTION = "files"
MANIFEST_PATH = "manifests/MANIFEST.generated.json"
MANIFEST_FORMAT = "oxbow-manifest-v1"
WIRE_PROFILE = "rsb1-v5-public-kernel-1"
CONFORMANCE_PROFILE = "oxbow-conformance-v1"

# Conformance is intentionally separate from wire validity and integrity.  The
# old draft spec named USER_PATH.md as mandatory, while the later 69-file core
# did not ship one. Phase B resolves that contradiction conservatively: a handoff
# needs a factual first door, a layout, and a navigable start/tour surface.
REQUIRED_ROOT_DOCS = ("READ_FIRST.md", "BUNDLE_LAYOUT.md")
TOUR_ROOT_DOCS = ("START_HERE.md",)


class KernelError(ValueError):
    """Malformed, unsupported, unsafe, or over-limit public-kernel bundle."""


class SourceError(ValueError):
    """Unsafe or unstable source tree."""


@dataclass(frozen=True)
class Limits:
    max_bundle_bytes: int = 256 * 1024 * 1024
    max_files: int = 10_000
    max_total_raw_bytes: int = 512 * 1024 * 1024
    max_file_bytes: int = 128 * 1024 * 1024
    max_path_bytes: int = 4096
    max_section_name_bytes: int = 64


DEFAULT_LIMITS = Limits()


@dataclass
class BundleView:
    files: List[Tuple[str, bytes]]
    payload_bytes: int
    raw_bytes: int

    @property
    def mapping(self) -> Dict[str, bytes]:
        return dict(self.files)


@dataclass
class SourceScan:
    files: List[Tuple[str, bytes]]
    excluded: List[Dict[str, object]]
    raw_bytes: int


def _wv(n: int, out: bytearray) -> None:
    if n < 0:
        raise ValueError("negative varint")
    while n >= 128:
        out.append((n & 127) | 128)
        n >>= 7
    out.append(n)


def _rv(data: bytes, off: int, *, max_value: int = (1 << 63) - 1) -> Tuple[int, int]:
    n = 0
    shift = 0
    for _ in range(10):
        if off >= len(data):
            raise KernelError("truncated varint")
        b = data[off]
        off += 1
        n |= (b & 127) << shift
        if n > max_value:
            raise KernelError("varint exceeds allowed range")
        if not (b & 128):
            return n, off
        shift += 7
    raise KernelError("varint is too long")


def _take(data: bytes, pos: int, n: int, what: str) -> Tuple[bytes, int]:
    if n < 0 or pos < 0 or pos + n > len(data):
        raise KernelError("truncated %s" % what)
    return data[pos:pos + n], pos + n


def _lzc6(data: bytes) -> bytes:
    return lzma.compress(
        data,
        format=lzma.FORMAT_RAW,
        filters=[{"id": lzma.FILTER_LZMA2, "preset": 6}],
    )


def _lzd6_bounded(data: bytes, max_output: int, what: str) -> bytes:
    """Raw LZMA2 preset-6 decode with a hard output ceiling.

    ``lzma.decompress`` has no output ceiling. The incremental decoder does, so
    this routine cannot inflate an attacker-controlled stream beyond the caller's
    declared resource budget.
    """
    if max_output < 0:
        raise KernelError("negative decompression limit")
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
                raise KernelError("%s exceeds decompression limit" % what)
            chunk = dec.decompress(feed, max_length=remaining)
            out.extend(chunk)
            feed = b""
            if len(out) > max_output:
                raise KernelError("%s exceeds decompression limit" % what)
            if dec.eof:
                if dec.unused_data:
                    raise KernelError("%s has trailing compressed data" % what)
                break
            if dec.needs_input:
                raise KernelError("truncated %s compressed stream" % what)
    except lzma.LZMAError as exc:
        raise KernelError("invalid %s compressed stream: %s" % (what, exc))
    return bytes(out)


def validate_bundle_path(path: str, limits: Limits = DEFAULT_LIMITS) -> str:
    if not isinstance(path, str):
        raise KernelError("bundle path is not text")
    if not path:
        raise KernelError("empty bundle path")
    if "\x00" in path:
        raise KernelError("NUL in bundle path")
    if "\\" in path:
        raise KernelError("backslashes are not allowed in bundle paths")
    try:
        encoded = path.encode("utf-8", errors="strict")
    except UnicodeEncodeError:
        raise KernelError("bundle path is not valid Unicode/UTF-8")
    if len(encoded) > limits.max_path_bytes:
        raise KernelError("bundle path exceeds %d bytes" % limits.max_path_bytes)
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise KernelError("absolute or drive-qualified bundle path: %s" % path)
    if ":" in path:
        raise KernelError("colon is not allowed in portable bundle paths: %s" % path)
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise KernelError("non-canonical bundle path: %s" % path)
    pp = PurePosixPath(path)
    if pp.is_absolute() or str(pp) != path:
        raise KernelError("non-canonical bundle path: %s" % path)
    return path


def _encode_offsets(blobs: Sequence[bytes]) -> bytes:
    raw = bytearray()
    total = 0
    _wv(0, raw)
    for blob in blobs:
        total += len(blob)
        _wv(len(blob), raw)  # delta encoding; cumulative sum reconstructs offsets
    return _lzc6(bytes(raw))


def _encode_paths(paths: Sequence[str]) -> bytes:
    raw = bytearray()
    for idx, path in enumerate(paths):
        raw.append(1)  # local binary pool
        pb = path.encode("utf-8")
        _wv(len(pb), raw)
        raw.extend(pb)
        _wv(idx, raw)
    return _lzc6(bytes(raw))


def encode_files(files: Sequence[Tuple[str, bytes]], limits: Limits = DEFAULT_LIMITS) -> bytes:
    """Encode exactly the supplied files using the locked public codec subset."""
    ordered = sorted(files, key=lambda x: x[0])
    if len(ordered) > limits.max_files:
        raise KernelError("file count exceeds limit")
    seen = set()
    total = 0
    for path, blob in ordered:
        validate_bundle_path(path, limits)
        if path in seen:
            raise KernelError("duplicate bundle path: %s" % path)
        seen.add(path)
        if not isinstance(blob, (bytes, bytearray)):
            raise KernelError("file payload for %s is not bytes" % path)
        if len(blob) > limits.max_file_bytes:
            raise KernelError("file exceeds per-file limit: %s" % path)
        total += len(blob)
        if total > limits.max_total_raw_bytes:
            raise KernelError("bundle raw bytes exceed limit")

    paths = [p for p, _ in ordered]
    blobs = [bytes(b) for _, b in ordered]
    concat = b"".join(blobs)
    paths_code = _encode_paths(paths)
    offsets_code = _encode_offsets(blobs)
    data_code = _lzc6(concat)

    out = bytearray(MAGIC)
    out.append(VERSION)

    # Public-kernel profile forbids global pools. Each pool still has the v5
    # count/offset-len/code-len framing so the recovered reference decoder can
    # read the output byte-identically.
    for _ in range(3):
        _wv(0, out)
        _wv(0, out)
        _wv(0, out)

    _wv(1, out)  # one section
    name = PUBLIC_SECTION.encode("utf-8")
    _wv(len(name), out)
    out.extend(name)
    _wv(0, out)              # nt: no text pool
    _wv(len(blobs), out)     # nb: every file is binary/exact
    _wv(0, out)              # ng: no GPX pool
    _wv(len(paths), out)     # path records
    _wv(len(paths_code), out)
    out.extend(paths_code)

    if blobs:
        _wv(len(offsets_code), out)
        out.extend(offsets_code)
        _wv(len(data_code), out)
        out.extend(data_code)

    if len(out) > limits.max_bundle_bytes:
        raise KernelError("encoded bundle exceeds payload limit")
    return bytes(out)


def _decode_offset_table(raw: bytes, count: int, limits: Limits) -> List[int]:
    pos = 0
    arr: List[int] = []
    cumulative = 0
    for _ in range(count + 1):
        delta, pos = _rv(raw, pos, max_value=limits.max_total_raw_bytes)
        cumulative += delta
        if cumulative > limits.max_total_raw_bytes:
            raise KernelError("offset table exceeds raw-byte limit")
        arr.append(cumulative)
    if pos != len(raw):
        raise KernelError("offset table has trailing bytes")
    if not arr or arr[0] != 0:
        raise KernelError("offset table must start at zero")
    for a, b in zip(arr, arr[1:]):
        if b < a:
            raise KernelError("offset table is not monotonic")
        if b - a > limits.max_file_bytes:
            raise KernelError("file exceeds per-file limit")
    return arr


def _decode_path_table(raw: bytes, count: int, limits: Limits) -> List[Tuple[str, int]]:
    pos = 0
    rows: List[Tuple[str, int]] = []
    seen = set()
    for _ in range(count):
        if pos >= len(raw):
            raise KernelError("truncated path table")
        pool = raw[pos]
        pos += 1
        if pool != 1:
            raise KernelError("public kernel permits only the local binary pool")
        ln, pos = _rv(raw, pos, max_value=limits.max_path_bytes)
        pb, pos = _take(raw, pos, ln, "path")
        try:
            path = pb.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise KernelError("bundle path is not valid UTF-8")
        validate_bundle_path(path, limits)
        if path in seen:
            raise KernelError("duplicate bundle path: %s" % path)
        seen.add(path)
        idx, pos = _rv(raw, pos, max_value=max(0, limits.max_files - 1))
        rows.append((path, idx))
    if pos != len(raw):
        raise KernelError("path table has trailing bytes")
    return rows


def parse(data: bytes, limits: Limits = DEFAULT_LIMITS) -> BundleView:
    """Parse the locked public-kernel RSB1 subset with bounded decompression."""
    if len(data) > limits.max_bundle_bytes:
        raise KernelError("payload exceeds bundle-byte limit")
    if len(data) < 5 or data[:4] != MAGIC or data[4] != VERSION:
        raise KernelError("not an RSB1 v5 payload")
    pos = 5

    # Global pools must be empty in the public profile. Rejecting, rather than
    # decoding, is what lets the default reader remain small and bounded.
    for i in range(3):
        n, pos = _rv(data, pos, max_value=limits.max_files)
        olen, pos = _rv(data, pos, max_value=limits.max_bundle_bytes)
        _, pos = _take(data, pos, olen, "global offset stream")
        clen, pos = _rv(data, pos, max_value=limits.max_bundle_bytes)
        _, pos = _take(data, pos, clen, "global codec stream")
        if n != 0 or olen != 0 or clen != 0:
            raise KernelError(
                "unsupported legacy/global pool %d; public kernel accepts only %s"
                % (i, WIRE_PROFILE)
            )

    nsec, pos = _rv(data, pos, max_value=2)
    if nsec != 1:
        raise KernelError("public kernel requires exactly one section")

    name_len, pos = _rv(data, pos, max_value=limits.max_section_name_bytes)
    name_b, pos = _take(data, pos, name_len, "section name")
    try:
        name = name_b.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise KernelError("section name is not valid UTF-8")
    if name != PUBLIC_SECTION:
        raise KernelError("unsupported section %r" % name)

    nt, pos = _rv(data, pos, max_value=limits.max_files)
    nb, pos = _rv(data, pos, max_value=limits.max_files)
    ng, pos = _rv(data, pos, max_value=limits.max_files)
    np_, pos = _rv(data, pos, max_value=limits.max_files)
    if nt != 0 or ng != 0:
        raise KernelError("public kernel permits only the binary pool")
    if nb != np_:
        raise KernelError("public kernel requires one binary record per path")
    if nb > limits.max_files:
        raise KernelError("file count exceeds limit")

    plen, pos = _rv(data, pos, max_value=limits.max_bundle_bytes)
    pcode, pos = _take(data, pos, plen, "path table codec")
    max_path_table = min(
        limits.max_total_raw_bytes,
        max(1, np_) * (limits.max_path_bytes + 32),
    )
    praw = _lzd6_bounded(pcode, max_path_table, "path table")
    rows = _decode_path_table(praw, np_, limits)

    if nb:
        olen, pos = _rv(data, pos, max_value=limits.max_bundle_bytes)
        ocode, pos = _take(data, pos, olen, "offset table codec")
        max_offsets = min(limits.max_total_raw_bytes, (nb + 1) * 10)
        oraw = _lzd6_bounded(ocode, max_offsets, "offset table")
        offsets = _decode_offset_table(oraw, nb, limits)

        clen, pos = _rv(data, pos, max_value=limits.max_bundle_bytes)
        ccode, pos = _take(data, pos, clen, "file data codec")
        concat = _lzd6_bounded(ccode, limits.max_total_raw_bytes, "file data")
    else:
        offsets = [0]
        concat = b""

    if pos != len(data):
        raise KernelError("payload has trailing bytes")
    if offsets[-1] != len(concat):
        raise KernelError("offset table does not reconcile with decoded bytes")

    indexes = [idx for _path, idx in rows]
    if sorted(indexes) != list(range(nb)):
        raise KernelError("binary indexes are not an exact 0..N-1 permutation")

    files: List[Tuple[str, bytes]] = []
    for path, idx in rows:
        blob = concat[offsets[idx]:offsets[idx + 1]]
        files.append((path, blob))
    return BundleView(files=files, payload_bytes=len(data), raw_bytes=len(concat))


def make_manifest(files: Sequence[Tuple[str, bytes]]) -> bytes:
    records = []
    for path, blob in sorted(files, key=lambda x: x[0]):
        if path == MANIFEST_PATH:
            raise KernelError("source tree may not provide reserved manifest path")
        records.append({
            "path": path,
            "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
        })
    doc = {
        "format": MANIFEST_FORMAT,
        "wire_profile": WIRE_PROFILE,
        "files": records,
    }
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_bundle_bytes(files: Sequence[Tuple[str, bytes]], limits: Limits = DEFAULT_LIMITS) -> bytes:
    clean = list(files)
    if any(path == MANIFEST_PATH for path, _ in clean):
        raise KernelError("source tree contains reserved %s" % MANIFEST_PATH)
    manifest = make_manifest(clean)
    return encode_files(clean + [(MANIFEST_PATH, manifest)], limits)


def _manifest_records(doc: object) -> Tuple[List[Tuple[str, Optional[int], str]], List[str]]:
    errors: List[str] = []
    out: List[Tuple[str, Optional[int], str]] = []
    if not isinstance(doc, dict):
        return out, ["manifest root is not an object"]
    files = doc.get("files")
    seen = set()
    if isinstance(files, list):
        for i, rec in enumerate(files):
            if not isinstance(rec, dict):
                errors.append("manifest record %d is not an object" % i)
                continue
            path = rec.get("path")
            size = rec.get("bytes")
            sha = rec.get("sha256")
            if not isinstance(path, str) or not isinstance(sha, str):
                errors.append("manifest record %d lacks path/sha256" % i)
                continue
            if sha.startswith("sha256:"):
                sha = sha.split(":", 1)[1]
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
    elif isinstance(files, dict):
        for path, val in files.items():
            size: Optional[int] = None
            sha: Optional[str] = None
            if not isinstance(path, str):
                errors.append("manifest dictionary has non-text path")
                continue
            if isinstance(val, str):
                sha = val
            elif isinstance(val, dict):
                size = val.get("bytes")
                sha = val.get("sha256")
            if isinstance(sha, str) and sha.startswith("sha256:"):
                sha = sha.split(":", 1)[1]
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
                errors.append("manifest path %s has invalid sha256" % path)
                continue
            if size is not None and (not isinstance(size, int) or size < 0):
                errors.append("manifest path %s has invalid bytes" % path)
                continue
            if path in seen:
                errors.append("duplicate manifest path: %s" % path)
                continue
            seen.add(path)
            out.append((path, size, sha.lower()))
    else:
        errors.append("manifest files is neither list nor object")
    return out, errors


def verify_integrity(view: BundleView) -> Dict[str, object]:
    files = view.mapping
    if MANIFEST_PATH not in files:
        return {
            "ok": False,
            "manifest": MANIFEST_PATH,
            "error": "manifest missing",
            "checked": 0,
            "missing": [],
            "unexpected": sorted(files),
            "mismatched": [],
            "manifest_errors": [],
        }
    try:
        doc = json.loads(files[MANIFEST_PATH].decode("utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "manifest": MANIFEST_PATH,
            "error": "manifest unreadable: %s" % exc,
            "checked": 0,
            "missing": [],
            "unexpected": [],
            "mismatched": [],
            "manifest_errors": [],
        }
    records, manifest_errors = _manifest_records(doc)
    if isinstance(doc, dict) and doc.get("format") != MANIFEST_FORMAT:
        manifest_errors.append(
            "manifest format must be %s" % MANIFEST_FORMAT
        )
    expected: Dict[str, Tuple[Optional[int], str]] = {}
    for path, size, sha in records:
        try:
            validate_bundle_path(path)
        except KernelError as exc:
            manifest_errors.append("unsafe manifest path %s: %s" % (path, exc))
            continue
        if path == MANIFEST_PATH:
            manifest_errors.append("manifest must not list itself")
            continue
        expected[path] = (size, sha)

    actual = {p: b for p, b in view.files if p != MANIFEST_PATH}
    missing = sorted(set(expected) - set(actual))
    unexpected = sorted(set(actual) - set(expected))
    mismatched: List[Dict[str, object]] = []
    checked = 0
    for path in sorted(set(expected) & set(actual)):
        size, sha = expected[path]
        blob = actual[path]
        reasons = []
        if size is not None and len(blob) != size:
            reasons.append("bytes")
        if hashlib.sha256(blob).hexdigest() != sha:
            reasons.append("sha256")
        if reasons:
            mismatched.append({"path": path, "fields": reasons})
        checked += 1

    ok = not manifest_errors and not missing and not unexpected and not mismatched
    return {
        "ok": ok,
        "manifest": MANIFEST_PATH,
        "checked": checked,
        "expected": len(expected),
        "actual": len(actual),
        "missing": missing,
        "unexpected": unexpected,
        "mismatched": mismatched,
        "manifest_errors": manifest_errors,
    }


def verify_conformance(view: BundleView) -> Dict[str, object]:
    paths = set(view.mapping)
    missing = [p for p in REQUIRED_ROOT_DOCS if p not in paths]
    tour_paths = sorted(
        p for p in paths
        if p in TOUR_ROOT_DOCS
        or (p.startswith("tours/") and p.endswith(".md") and "/" not in p[len("tours/"):])
        or ("/" not in p and p.startswith("TOUR") and p.endswith(".md"))
    )
    if not tour_paths:
        missing.append("START_HERE.md or a tour surface")
    return {
        "ok": not missing,
        "profile": CONFORMANCE_PROFILE,
        "required_root_docs": list(REQUIRED_ROOT_DOCS),
        "tour_surfaces": tour_paths,
        "missing": missing,
    }


def verify_bundle_bytes(data: bytes, limits: Limits = DEFAULT_LIMITS) -> Dict[str, object]:
    try:
        view = parse(data, limits)
    except KernelError as exc:
        return {
            "ok": False,
            "wire": {"ok": False, "profile": WIRE_PROFILE, "error": str(exc)},
            "integrity": {"ok": False, "why": "wire parse failed"},
            "conformance": {"ok": False, "why": "wire parse failed"},
        }
    wire = {
        "ok": True,
        "magic": MAGIC.decode("ascii"),
        "version": VERSION,
        "profile": WIRE_PROFILE,
        "payload_bytes": view.payload_bytes,
        "files": len(view.files),
        "raw_bytes": view.raw_bytes,
    }
    integrity = verify_integrity(view)
    conformance = verify_conformance(view)
    return {
        "ok": bool(wire["ok"] and integrity["ok"] and conformance["ok"]),
        "wire": wire,
        "integrity": integrity,
        "conformance": conformance,
    }


def _safe_open_regular(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(path), flags)
    except OSError as exc:
        raise SourceError("cannot open source file %s safely: %s" % (path, exc))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise SourceError("source path is not a regular file: %s" % path)
        chunks = []
        while True:
            chunk = os.read(fd, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(fd)
        if before.st_dev != after.st_dev or before.st_ino != after.st_ino or before.st_size != after.st_size:
            raise SourceError("source file changed while reading: %s" % path)
        blob = b"".join(chunks)
        if len(blob) != after.st_size:
            raise SourceError("source file size changed while reading: %s" % path)
        return blob
    finally:
        os.close(fd)


def scan_source(
    root: Path,
    keep: Optional[Callable[[str], bool]] = None,
    limits: Limits = DEFAULT_LIMITS,
) -> SourceScan:
    """Read a source tree without following symlinks.

    A selected symlink is an error rather than an implicit dereference. Excluded
    regular files are reported, not silently forgotten. Special files are also
    rejected when selected.
    """
    root = Path(root)
    if root.is_symlink():
        raise SourceError("source root may not be a symlink")
    if not root.is_dir():
        raise SourceError("source root is not a directory: %s" % root)
    root = root.resolve()
    keep = keep or (lambda _rel: True)
    files: List[Tuple[str, bytes]] = []
    excluded: List[Dict[str, object]] = []
    total = 0

    for dirpath, dirnames, filenames in os.walk(str(root), topdown=True, followlinks=False):
        dpath = Path(dirpath)
        # Symlink directories are not traversed. If the profile would have kept
        # something beneath one, fail rather than following it accidentally.
        retained_dirs = []
        for name in sorted(dirnames):
            child = dpath / name
            rel = child.relative_to(root).as_posix()
            if child.is_symlink():
                probe = rel + "/__oxbow_probe__"
                if keep(probe):
                    raise SourceError("selected symlink directory is not allowed: %s" % rel)
                excluded.append({"path": rel + "/", "reason": "profile_or_policy_symlink"})
                continue
            retained_dirs.append(name)
        dirnames[:] = retained_dirs

        for name in sorted(filenames):
            p = dpath / name
            rel = p.relative_to(root).as_posix()
            if not keep(rel):
                excluded.append({"path": rel, "reason": "profile_or_policy"})
                continue
            try:
                lst = p.lstat()
            except OSError as exc:
                raise SourceError("cannot stat source path %s: %s" % (rel, exc))
            if stat.S_ISLNK(lst.st_mode):
                raise SourceError("selected symlink file is not allowed: %s" % rel)
            if not stat.S_ISREG(lst.st_mode):
                raise SourceError("selected source path is not a regular file: %s" % rel)
            validate_bundle_path(rel, limits)
            if rel == MANIFEST_PATH:
                raise SourceError("source tree contains reserved %s" % MANIFEST_PATH)
            blob = _safe_open_regular(p)
            if len(blob) > limits.max_file_bytes:
                raise SourceError("source file exceeds per-file limit: %s" % rel)
            total += len(blob)
            if total > limits.max_total_raw_bytes:
                raise SourceError("source tree exceeds raw-byte limit")
            files.append((rel, blob))
            if len(files) > limits.max_files:
                raise SourceError("source tree exceeds file-count limit")

    files.sort(key=lambda x: x[0])
    excluded.sort(key=lambda x: str(x.get("path")))
    return SourceScan(files=files, excluded=excluded, raw_bytes=total)


def prepare_extract_destination(dest: Path) -> Path:
    dest = Path(dest)
    if dest.exists():
        if dest.is_symlink():
            raise KernelError("extraction destination may not be a symlink")
        if not dest.is_dir():
            raise KernelError("extraction destination exists and is not a directory")
        try:
            next(dest.iterdir())
        except StopIteration:
            pass
        else:
            raise KernelError("extraction destination must be new or empty")
    else:
        dest.mkdir(parents=True)
    return dest.resolve()


def extract_view(view: BundleView, dest: Path) -> Tuple[int, int]:
    root = prepare_extract_destination(dest)
    count = 0
    total = 0
    for path, blob in view.files:
        validate_bundle_path(path)
        parts = PurePosixPath(path).parts
        target = root.joinpath(*parts)
        parent = target.parent
        parent.mkdir(parents=True, exist_ok=True)
        # Destination is required to start empty; this extra check protects
        # against a symlink introduced during extraction or by a concurrent actor.
        resolved_parent = parent.resolve()
        if root != resolved_parent and root not in resolved_parent.parents:
            raise KernelError("extraction path escaped destination: %s" % path)
        if target.exists() or target.is_symlink():
            raise KernelError("refusing to overwrite extraction path: %s" % path)
        target.write_bytes(blob)
        count += 1
        total += len(blob)
    return count, total
