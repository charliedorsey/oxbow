#!/usr/bin/env python3
"""Top-level Oxbow CLI."""
from __future__ import annotations

import sys


def _help():
    print(
        "oxbow <command> ...\n\n"
        "Start / ship:\n"
        "  init      create a minimal handoff skeleton\n"
        "  ship      build a corpus into .oxb or self-extracting .oxb.py\n"
        "  pack      alias for ship\n\n"
        "Inspect (does not execute .oxb.py wrappers):\n"
        "  info      summarize a bundle\n"
        "  ls        list bundled paths\n"
        "  cat       print one bundled document\n"
        "  read-first print READ_FIRST.md\n"
        "  tour      print the default or named tour\n"
        "  verify    verify wire, exact manifest, conformance, and optional signature\n"
        "  extract   safely extract into a new/empty directory\n\n"
        "Other:\n"
        "  witness   init/draft/validate/append/rebuild portable session records\n"
        "  bundle    lower-level bundle/build/wrap/sign/profile commands\n"
        "  seed      inspect/run optional carried capability from an extracted tree\n"
        "  selftest  run the installed-package smoke gate\n"
    )


def _bundle_alias(command, rest):
    from oxbow.bundle.cli import main as m
    mapping = {
        "info": "info",
        "ls": "list",
        "cat": "doc",
        "read-first": "read-first",
        "tour": "tour",
        "verify": "verify",
        "extract": "extract",
    }
    return m([mapping[command]] + rest)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        _help()
        return 0
    command, rest = argv[0], argv[1:]
    if command == "init":
        from oxbow.project import main as m
        return m(rest)
    if command in ("ship", "pack"):
        from oxbow.bundle.ship import main as m
        return m(rest)
    if command in ("info", "ls", "cat", "read-first", "tour", "verify", "extract"):
        return _bundle_alias(command, rest)
    if command == "bundle":
        from oxbow.bundle.cli import main as m
        return m(rest)
    if command == "witness":
        from oxbow.witness.cli import main as m
        return m(rest)
    if command == "seed":
        from oxbow.seeds import main as m
        return m(rest)
    if command == "selftest":
        from oxbow.selftest import main as m
        return m()
    print("unknown command '%s' (run `oxbow --help`)" % command, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
