#!/usr/bin/env python3
"""Build the committed GitHub-ready Oxbow ``.oxb.py`` artifacts.

The public prebuilt wrappers are generated only from tracked repository source
(or the small bootstrap set introduced by this patch before it is first
committed), plus one generated ``PREBUILT_PROFILE.md`` file. Untracked working
notes are never swept into a prebuilt bundle.

Run from any directory:

    python3 tools/build_prebuilt.py
    python3 tools/build_prebuilt.py --check
    python3 tools/build_prebuilt.py --check-bytes

``--check`` rebuilds all three wrappers and requires semantic payload equality
plus canonical generated-wrapper structure. Compressed OXB bytes may differ
across Python/liblzma environments while decoding to the same files.

``--check-bytes`` is the stronger same-toolchain release-host check: it requires
byte-for-byte equality with the committed wrappers.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from oxbow.bundle import kernel
from oxbow.bundle.cli import _load_public_payload
from oxbow.bundle.wrapper import write_wrapper

PREBUILT = ROOT / "prebuilt"
PROFILE_NOTE = "PREBUILT_PROFILE.md"

# These are new tracked source files introduced by the prebuilt patch itself.
# ``git apply`` creates them before they are added to the index, so include them
# explicitly during that one bootstrap window. Once committed they are already
# returned by ``git ls-files``. Generated files under prebuilt/ are never added
# through this escape hatch.
BOOTSTRAP_TRACKED = {
    ".gitattributes",
    "tests/test_prebuilt.py",
    "tools/build_prebuilt.py",
}

TINY_FILES = {
    "BUNDLE_LAYOUT.md",
    "KNOWN_SEAMS.md",
    "README.md",
    "READ_FIRST.md",
    "SECURITY.md",
    "START_HERE.md",
    "STATUS.md",
    "docs/CONTINUITY_BOUNDARY.md",
    "docs/TRUST_MODEL.md",
    "src/oxbow/witness/WITNESS_FORMAT.md",
    "src/oxbow/witness/schemas/portable_packet_v2.schema.json",
}

STANDARD_ROOT_FILES = {
    "BUNDLE_LAYOUT.md",
    "CHANGELOG.md",
    "KNOWN_SEAMS.md",
    "LICENSE",
    "MANIFEST.in",
    "README.md",
    "READ_FIRST.md",
    "SECURITY.md",
    "START_HERE.md",
    "STATUS.md",
    "pyproject.toml",
}

STANDARD_PREFIXES = (
    "docs/",
    "examples/",
    "integrations/",
    "spec/",
    "src/oxbow/",
)

ARTIFACTS = (
    ("tiny", "oxbow-tiny.oxb.py"),
    ("standard", "oxbow-standard.oxb.py"),
    ("full", "oxbow-full.oxb.py"),
)

PROFILE_DESCRIPTIONS = {
    "tiny": {
        "includes": (
            "Front-door documentation, continuity/trust guidance, Witness v2 "
            "format/schema, and the complete synthetic tiny-handoff example."
        ),
        "excludes": (
            "Package implementation, repository tests, compatibility archaeology, "
            "development tooling, CI metadata, and generated prebuilt artifacts."
        ),
        "use": "Smallest useful Oxbow orientation object for a model or human reader.",
    },
    "standard": {
        "includes": (
            "Public documentation, wire specification, installable Oxbow source, "
            "examples, integration documentation, and package metadata."
        ),
        "excludes": (
            "Repository tests and frozen fixtures, compatibility archaeology, "
            "development tooling, CI metadata, and generated prebuilt artifacts."
        ),
        "use": "Recommended default for understanding, inspecting, or working with Oxbow.",
    },
    "full": {
        "includes": "Every tracked public repository file except prebuilt/ itself.",
        "excludes": "Only generated prebuilt/ artifacts, to prevent recursive bundling.",
        "use": "Deep development, audit, or full-repository model handoff.",
    },
}


class PrebuiltError(RuntimeError):
    pass


def _project_version() -> str:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init = (ROOT / "src/oxbow/__init__.py").read_text(encoding="utf-8")
    pm = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.M)
    im = re.search(r'^__version__\s*=\s*"([^"]+)"', init, re.M)
    if not pm or not im:
        raise PrebuiltError("could not read package version from pyproject/__init__")
    if pm.group(1) != im.group(1):
        raise PrebuiltError(
            "package version mismatch: pyproject=%s __init__=%s"
            % (pm.group(1), im.group(1))
        )
    return pm.group(1)


def _tracked_paths() -> List[str]:
    try:
        cp = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PrebuiltError("git ls-files failed: %s" % exc)

    paths = set(
        p.decode("utf-8", errors="strict")
        for p in cp.stdout.split(b"\0")
        if p
    )
    for rel in BOOTSTRAP_TRACKED:
        if (ROOT / rel).is_file():
            paths.add(rel)

    out = []
    for rel in sorted(paths):
        p = ROOT / rel
        if rel.startswith("prebuilt/"):
            continue
        if not p.is_file() or p.is_symlink():
            raise PrebuiltError("tracked prebuilt source is not a regular file: %s" % rel)
        kernel.validate_bundle_path(rel)
        out.append(rel)
    return out


def _select(profile: str, tracked: Sequence[str]) -> List[str]:
    if profile == "full":
        selected = list(tracked)
    elif profile == "standard":
        selected = [
            rel
            for rel in tracked
            if rel in STANDARD_ROOT_FILES
            or any(rel.startswith(prefix) for prefix in STANDARD_PREFIXES)
        ]
    elif profile == "tiny":
        selected = [
            rel
            for rel in tracked
            if rel in TINY_FILES or rel.startswith("examples/tiny-handoff/")
        ]
    else:
        raise PrebuiltError("unknown prebuilt profile: %s" % profile)

    required = {"READ_FIRST.md", "START_HERE.md", "BUNDLE_LAYOUT.md"}
    missing = sorted(required - set(selected))
    if missing:
        raise PrebuiltError(
            "%s profile is missing required handoff front doors: %s"
            % (profile, ", ".join(missing))
        )
    return sorted(selected)


def _profile_note(profile: str, version: str, selected_count: int) -> str:
    meta = PROFILE_DESCRIPTIONS[profile]
    return (
        "# Oxbow prebuilt: %s\n\n"
        "This file identifies the generated profile carried inside this prebuilt Oxbow wrapper.\n\n"
        "- Oxbow package version: `%s`\n"
        "- Selected tracked source files: `%d`\n"
        "- Intended use: %s\n\n"
        "## Includes\n\n%s\n\n"
        "## Excludes\n\n%s\n\n"
        "## Start here\n\n"
        "Read `START_HERE.md`, then follow the source pointers relevant to your task. References there or in `README.md` to the repository `prebuilt/` directory describe the GitHub distribution surface; this bundle intentionally does not contain other prebuilt wrappers.\n\n"
        "This prebuilt is generated from public repository source. Its embedded manifest can verify "
        "payload integrity, but integrity is not truth and the executable wrapper source is not "
        "authenticated merely because its embedded payload verifies.\n"
        % (
            profile,
            version,
            selected_count,
            meta["use"],
            meta["includes"],
            meta["excludes"],
        )
    )


def _stage_files(stage: Path, selected: Sequence[str], profile: str, version: str) -> None:
    for rel in selected:
        src = ROOT / rel
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
    (stage / PROFILE_NOTE).write_text(
        _profile_note(profile, version, len(selected)),
        encoding="utf-8",
    )


def _build_one(
    profile: str,
    artifact_name: str,
    tracked: Sequence[str],
    version: str,
) -> Tuple[bytes, bytes, Dict[str, int]]:
    selected = _select(profile, tracked)
    with tempfile.TemporaryDirectory(prefix="oxbow-prebuilt-%s-" % profile) as td:
        td = Path(td)
        stage = td / "stage"
        stage.mkdir()
        _stage_files(stage, selected, profile, version)

        scan = kernel.scan_source(stage)
        payload = kernel.build_bundle_bytes(scan.files)
        verification = kernel.verify_bundle_bytes(payload)
        if not verification.get("ok"):
            raise PrebuiltError("%s payload failed verification: %r" % (profile, verification))

        wrapper = td / artifact_name
        write_wrapper(payload, wrapper, name="oxbow-%s" % profile, self_check=True)
        data = wrapper.read_bytes()
        return data, payload, {
            "source_files": len(selected),
            "payload_files": len(kernel.parse(payload).files),
            "raw_bytes": scan.raw_bytes,
            "payload_bytes": len(payload),
            "wrapper_bytes": len(data),
        }


def _checksums(blobs: Dict[str, bytes]) -> bytes:
    lines = [
        "%s  %s" % (hashlib.sha256(blobs[name]).hexdigest(), name)
        for _profile, name in ARTIFACTS
    ]
    return ("\n".join(lines) + "\n").encode("ascii")


def _write_owned(path: Path, data: bytes, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-%d" % os.getpid())
    tmp.write_bytes(data)
    if executable:
        try:
            tmp.chmod(0o755)
        except OSError:
            pass
    os.replace(str(tmp), str(path))


def _verified_mapping(payload: bytes, label: str) -> Dict[str, bytes]:
    verification = kernel.verify_bundle_bytes(payload)
    if not verification.get("ok"):
        raise PrebuiltError("%s failed Oxbow verification: %r" % (label, verification))
    return kernel.parse(payload).mapping


def _mapping_drift(committed: Dict[str, bytes], generated: Dict[str, bytes]) -> str:
    committed_paths = set(committed)
    generated_paths = set(generated)
    missing = sorted(generated_paths - committed_paths)
    unexpected = sorted(committed_paths - generated_paths)
    changed = sorted(
        path
        for path in committed_paths & generated_paths
        if committed[path] != generated[path]
    )
    parts = []
    if missing:
        parts.append("missing=" + ",".join(missing[:5]))
    if unexpected:
        parts.append("unexpected=" + ",".join(unexpected[:5]))
    if changed:
        parts.append("changed=" + ",".join(changed[:5]))
    return "; ".join(parts) or "payload mappings differ"


def _normalized_wrapper_shell(data: bytes) -> str:
    """Mask only compressor-dependent generated fields in wrapper source."""
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PrebuiltError("prebuilt wrapper is not UTF-8 text: %s" % exc)

    substitutions = (
        (r"(?m)^_PACKED_BYTES = [0-9]+$", "_PACKED_BYTES = <payload-bytes>"),
        (
            r"(?m)^_PAYLOAD_SHA256 = ['\"][0-9a-f]{64}['\"]$",
            "_PAYLOAD_SHA256 = <payload-sha256>",
        ),
        (
            r"(?ms)^_PAYLOAD_B85 = '''\n.*?\n'''$",
            "_PAYLOAD_B85 = <payload-b85>",
        ),
    )
    for pattern, replacement in substitutions:
        text, count = re.subn(pattern, replacement, text, count=1)
        if count != 1:
            raise PrebuiltError("generated wrapper field not found for normalization")
    return text


def _semantic_check(
    blobs: Dict[str, bytes],
    payloads: Dict[str, bytes],
) -> List[str]:
    failures = []
    committed_blobs: Dict[str, bytes] = {}

    for _profile, artifact_name in ARTIFACTS:
        path = PREBUILT / artifact_name
        if not path.is_file():
            failures.append("missing %s" % path.relative_to(ROOT))
            continue

        committed_blob = path.read_bytes()
        committed_blobs[artifact_name] = committed_blob
        try:
            committed_payload = _load_public_payload(str(path))
            committed_map = _verified_mapping(
                committed_payload,
                "committed %s" % path.relative_to(ROOT),
            )
            generated_map = _verified_mapping(
                payloads[artifact_name],
                "regenerated %s" % artifact_name,
            )
            if committed_map != generated_map:
                failures.append(
                    "semantic drift %s (%s)"
                    % (path.relative_to(ROOT), _mapping_drift(committed_map, generated_map))
                )
            if _normalized_wrapper_shell(committed_blob) != _normalized_wrapper_shell(blobs[artifact_name]):
                failures.append("generated wrapper shell drift %s" % path.relative_to(ROOT))
        except (OSError, PrebuiltError, kernel.KernelError) as exc:
            failures.append("cannot verify %s: %s" % (path.relative_to(ROOT), exc))

    sums = PREBUILT / "SHA256SUMS"
    if not sums.is_file():
        failures.append("missing prebuilt/SHA256SUMS")
    elif len(committed_blobs) == len(ARTIFACTS):
        committed_checksums = _checksums(committed_blobs)
        if sums.read_bytes() != committed_checksums:
            failures.append("prebuilt/SHA256SUMS does not match committed wrapper bytes")
    return failures


def _byte_check(blobs: Dict[str, bytes]) -> List[str]:
    failures = []
    for _profile, artifact_name in ARTIFACTS:
        path = PREBUILT / artifact_name
        if not path.is_file():
            failures.append("missing %s" % path.relative_to(ROOT))
        elif path.read_bytes() != blobs[artifact_name]:
            failures.append("byte drift %s" % path.relative_to(ROOT))
    sums = PREBUILT / "SHA256SUMS"
    expected_checksums = _checksums(blobs)
    if not sums.is_file():
        failures.append("missing prebuilt/SHA256SUMS")
    elif sums.read_bytes() != expected_checksums:
        failures.append("byte drift prebuilt/SHA256SUMS")
    return failures


def build_all(check: bool = False, check_bytes: bool = False) -> int:
    version = _project_version()
    tracked = _tracked_paths()
    blobs: Dict[str, bytes] = {}
    payloads: Dict[str, bytes] = {}
    stats: Dict[str, Dict[str, int]] = {}

    for profile, artifact_name in ARTIFACTS:
        blob, payload, stat = _build_one(profile, artifact_name, tracked, version)
        blobs[artifact_name] = blob
        payloads[artifact_name] = payload
        stats[profile] = stat

    if check or check_bytes:
        failures = _byte_check(blobs) if check_bytes else _semantic_check(blobs, payloads)
        if failures:
            for msg in failures:
                print("FAIL: %s" % msg, file=sys.stderr)
            if check_bytes:
                print(
                    "Exact wrapper bytes differ. Rebuild on the release toolchain with: "
                    "python3 tools/build_prebuilt.py",
                    file=sys.stderr,
                )
            else:
                print(
                    "Semantic prebuilt contents are out of date. Run: "
                    "python3 tools/build_prebuilt.py",
                    file=sys.stderr,
                )
            return 1
    else:
        PREBUILT.mkdir(parents=True, exist_ok=True)
        for _profile, artifact_name in ARTIFACTS:
            _write_owned(PREBUILT / artifact_name, blobs[artifact_name], executable=True)
        _write_owned(PREBUILT / "SHA256SUMS", _checksums(blobs))

    if check_bytes:
        verb = "verified byte-for-byte"
    elif check:
        verb = "verified semantically"
    else:
        verb = "built"
    print("prebuilt artifacts %s for Oxbow %s" % (verb, version))
    for profile, artifact_name in ARTIFACTS:
        stat = stats[profile]
        print(
            "  %-8s %7d bytes  %3d tracked source files  -> %s"
            % (profile, stat["wrapper_bytes"], stat["source_files"], artifact_name)
        )
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    checks = ap.add_mutually_exclusive_group()
    checks.add_argument(
        "--check",
        action="store_true",
        help="require semantic payload equality and canonical generated-wrapper structure",
    )
    checks.add_argument(
        "--check-bytes",
        action="store_true",
        help="same-toolchain release check requiring exact committed wrapper bytes",
    )
    args = ap.parse_args(argv)
    try:
        return build_all(check=args.check, check_bytes=args.check_bytes)
    except (OSError, PrebuiltError, kernel.KernelError) as exc:
        print("prebuilt build failed: %s" % exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
