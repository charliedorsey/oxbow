#!/usr/bin/env python3
"""
seeds.py — the seed mechanism.

A seed is a folder inside a bundle that carries optional, runnable capability.
Seeds are inert: a bundle with no seeds builds, verifies and extracts exactly
as it would without this module, and a seed that fails to load never blocks a
bundle operation.

A seed folder contains:

    <seed>/
      SEED.md      required. First heading is the name; first paragraph is the
                   summary shown by `seed list`. Everything else is for the
                   model that decides whether to run it.
      run.py       optional. Must expose main(argv) -> int.

Discovery walks `seeds/` at the bundle root. Nothing is imported until a seed
is explicitly run, so listing seeds costs one file read each and executes
nothing.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys

SEED_DIRNAME = "seeds"


class Seed:
    __slots__ = ("name", "path", "title", "summary", "runnable")

    def __init__(self, name, path, title, summary, runnable):
        self.name, self.path = name, path
        self.title, self.summary, self.runnable = title, summary, runnable

    def __repr__(self):
        return f"<Seed {self.name}{' *' if self.runnable else ''}>"


def _parse_seed_md(text):
    """First `# ` heading is the title; first non-empty, non-heading block is
    the summary. Deliberately forgiving: a seed with a malformed SEED.md still
    lists, it just describes itself poorly."""
    title, summary, lines = None, [], text.splitlines()
    for ln in lines:
        s = ln.strip()
        if title is None and s.startswith("# "):
            title = s[2:].strip()
            continue
        if title is not None:
            if not s:
                if summary:
                    break
                continue
            if s.startswith("#"):
                break
            summary.append(s)
    return title, " ".join(summary)


def discover(root: str) -> list:
    """Return the seeds under <root>/seeds, sorted by name. Never raises."""
    base = os.path.join(root, SEED_DIRNAME)
    if not os.path.isdir(base):
        return []
    out = []
    for name in sorted(os.listdir(base)):
        path = os.path.join(base, name)
        md = os.path.join(path, "SEED.md")
        if not os.path.isdir(path) or not os.path.exists(md):
            continue
        try:
            with open(md, encoding="utf-8") as fh:
                title, summary = _parse_seed_md(fh.read())
        except OSError:
            title, summary = None, ""
        out.append(Seed(name, path, title or name, summary,
                        os.path.exists(os.path.join(path, "run.py"))))
    return out


def run(seed: Seed, argv: list) -> int:
    """Import <seed>/run.py in isolation and call main(argv).

    The seed's own folder goes on sys.path so it can import its siblings, and
    is removed afterwards. A seed that raises returns 1 and a message; it does
    not propagate into the caller.
    """
    if not seed.runnable:
        print(f"seed '{seed.name}' is documentation only (no run.py)")
        return 0
    target = os.path.join(seed.path, "run.py")
    spec = importlib.util.spec_from_file_location(f"_seed_{seed.name}", target)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, seed.path)
    try:
        spec.loader.exec_module(mod)
        fn = getattr(mod, "main", None)
        if fn is None:
            print(f"seed '{seed.name}': run.py exposes no main(argv)")
            return 1
        return int(fn(argv) or 0)
    except Exception as exc:                      # a seed never breaks the bundle
        print(f"seed '{seed.name}' failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        if sys.path and sys.path[0] == seed.path:
            sys.path.pop(0)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oxbow seed")
    ap.add_argument("--root", default=".", help="bundle root (default: cwd)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="list seeds present in the bundle")
    r = sub.add_parser("run", help="run a seed")
    r.add_argument("name")
    r.add_argument("args", nargs=argparse.REMAINDER)

    a = ap.parse_args(argv)
    seeds = discover(a.root)

    if a.cmd == "list":
        if not seeds:
            print("no seeds in this bundle")
            return 0
        width = max(len(s.name) for s in seeds)
        for s in seeds:
            mark = "run" if s.runnable else "doc"
            print(f"  [{mark}] {s.name:<{width}}  {s.summary[:88]}")
        return 0

    match = [s for s in seeds if s.name == a.name]
    if not match:
        print(f"no seed named '{a.name}' (have: {', '.join(s.name for s in seeds) or 'none'})")
        return 2
    return run(match[0], a.args)


if __name__ == "__main__":
    raise SystemExit(main())
