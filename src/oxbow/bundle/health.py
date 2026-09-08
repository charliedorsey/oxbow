#!/usr/bin/env python3
"""Check whether an unpacked handoff is coherent enough to ship.

`verify` answers whether packed bytes match the manifest. `health` examines an
unpacked source tree before packing: front doors, unfinished init stubs, witness
stream freshness, and common stale build artifacts.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

FORMAT_DOCS = ("READ_FIRST.md", "START_HERE.md", "BUNDLE_LAYOUT.md", "HANDOFF.md")
TODO_MARKER = "OXBOW-TODO"


class Report:
    def __init__(self, quiet=False):
        self.quiet = quiet
        self.fails = self.notes = self.passes = 0

    def ok(self, msg):
        self.passes += 1
        if not self.quiet:
            print("  ✓ %s" % msg)

    def note(self, msg):
        self.notes += 1
        if not self.quiet:
            print("  – %s" % msg)

    def fail(self, msg):
        self.fails += 1
        print("  ✗ %s" % msg)


def _check_docs(root: Path, report: Report):
    missing = [p for p in FORMAT_DOCS if not (root / p).is_file()]
    if missing:
        report.fail("front-door files missing: %s" % ", ".join(missing))
        return
    report.ok("front-door files present (%d)" % len(FORMAT_DOCS))
    handoff = (root / "HANDOFF.md").read_text(encoding="utf-8", errors="replace")
    if TODO_MARKER in handoff:
        report.note("HANDOFF.md still contains the init TODO marker; edit it before external use")
    elif len(handoff.strip()) < 120:
        report.note("HANDOFF.md is unusually short (%d chars)" % len(handoff.strip()))
    else:
        report.ok("HANDOFF.md appears edited")


def _check_witness(root: Path, report: Report):
    p = root / "witness" / "stream.json"
    if not p.exists():
        report.note("no witness/stream.json — Witness is optional")
        return
    try:
        from oxbow.witness.stream import rebuild_index, validate_stream
        stream = json.loads(p.read_text(encoding="utf-8"))
        validate_stream(stream)
        fresh = rebuild_index(stream)
    except Exception as exc:
        report.fail("witness/stream.json is invalid: %s" % exc)
        return
    if stream.get("derived_index") != fresh:
        report.fail("witness derived_index is stale — run `oxbow witness rebuild --stream witness/stream.json`")
    else:
        report.ok("Witness stream valid; derived index current (%d record(s))" % len(stream.get("records") or []))


def _check_manifest(root: Path, report: Report):
    p = root / "manifests" / "MANIFEST.generated.json"
    if not p.exists():
        report.note("no generated manifest in source tree — normal before packing")
        return
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        records = doc.get("files") or []
    except Exception as exc:
        report.fail("generated manifest is unreadable: %s" % exc)
        return
    missing = [r.get("path") for r in records if r.get("path") and not (root / r["path"]).exists()]
    if missing:
        report.fail("generated manifest lists %d path(s) missing from extracted tree" % len(missing))
    else:
        report.ok("generated manifest paths are present (%d source record(s))" % len(records))


def _check_caches(root: Path, report: Report):
    junk = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        if ".git" in rel.parts:
            dirnames[:] = []
            continue
        for fn in filenames:
            if fn == ".DS_Store" or fn.endswith((".pyc", ".pyo")):
                junk.append(str(rel / fn))
    if junk:
        report.note("%d cache/OS metadata file(s) present; packing policy will exclude them" % len(junk))
    else:
        report.ok("no obvious cache/OS metadata in source tree")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oxbow bundle health")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--verbose", action="store_true")  # retained for CLI compatibility
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    r = Report(a.quiet)
    print("== Oxbow health: %s ==" % root)
    _check_docs(root, r)
    _check_witness(root, r)
    _check_manifest(root, r)
    _check_caches(root, r)
    verdict = "HEALTHY" if r.fails == 0 else "PROBLEMS"
    print("OXBOW HEALTH: %s — %d ok, %d note(s), %d failing" % (verdict, r.passes, r.notes, r.fails))
    return 1 if r.fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
