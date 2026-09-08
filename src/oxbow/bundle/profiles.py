#!/usr/bin/env python3
"""
profiles.py — what enters a bundle.

A profile is a named include/exclude ruleset. Without one, a build takes the
whole tree minus obvious junk; with one, the operator decides what ships. The
same source tree can produce a full bundle for an archive and a small one for a
model that only needs the working set.

Rules are glob patterns matched against the POSIX-style path relative to the
source root. `include` is a whitelist when non-empty and ignored when empty.
`exclude` always wins over `include`, because a rule that removes something
should never be overridden by a rule that adds it.

Profiles are data, not code. `oxbow bundle profiles --write` emits a starter
file the operator edits; a bundle with no profile file builds with `default`.
"""
from __future__ import annotations

import fnmatch
import json
import os

PROFILE_FILE = "profiles/build_profiles.json"

# Excluded under every profile, including `full`. These are never content:
# editor droppings, build caches, and OS metadata. An operator who genuinely
# wants one of these can name it in `include` and lose the argument on purpose.
ALWAYS_EXCLUDE = [
    "**/__pycache__/**", "**/*.pyc", "**/*.pyo",
    "**/.DS_Store", "**/._*", "**/__MACOSX/**",
    "**/.git/**", "**/.svn/**",
    "**/node_modules/**", "**/.venv/**", "**/venv/**",
    "**/_quarantine_not_in_bundle/**",
]

DEFAULT_PROFILES = {
    "default": {
        "include": [],
        "exclude": [],
        "notes": ["Everything except the always-excluded junk.",
                  "This is what a build does when no profile is named."],
    },
    "full": {
        "include": ["**"],
        "exclude": [],
        "notes": ["Explicitly everything. Same result as default; named so a",
                  "build script can say what it meant."],
    },
    "lean": {
        "include": [],
        "exclude": ["**/*.zip", "**/*.tar", "**/*.tar.gz", "**/*.tgz",
                    "**/*.gz", "**/*.bz2", "**/*.xz", "**/*.7z",
                    "**/*.wav", "**/*.mp3", "**/*.mp4", "**/*.mov",
                    "**/*.o", "**/*.so", "**/*.dylib", "**/*.a"],
        "notes": ["Drops nested archives and media. Nested archives are the",
                  "biggest single win: they do not compress and the packer",
                  "cannot see inside them, so they cost their full size."],
    },
    "docs": {
        "include": ["**/*.md", "**/*.txt", "**/*.json", "**/*.yml", "**/*.yaml",
                    "READ_FIRST.md", "START_HERE.md", "KNOWN_SEAMS.md"],
        "exclude": [],
        "notes": ["Prose and structured text only. The smallest useful bundle",
                  "for a model that needs the corpus and not the toolchain."],
    },
}


class ProfileError(Exception):
    pass


def load(root: str) -> dict:
    """Profiles from <root>/profiles/build_profiles.json, else the defaults."""
    p = os.path.join(root, PROFILE_FILE)
    if not os.path.exists(p):
        return dict(DEFAULT_PROFILES)
    try:
        user = json.load(open(p))
    except Exception as e:
        raise ProfileError(f"{PROFILE_FILE} present but unreadable: {e}")
    if not isinstance(user, dict):
        raise ProfileError(f"{PROFILE_FILE} must be an object of named profiles")
    merged = dict(DEFAULT_PROFILES)
    merged.update(user)                       # operator profiles win on name collision
    return merged


def _match(rel: str, patterns) -> bool:
    """True if rel matches any pattern. `**/x` also matches a top-level `x`,
    which is what people mean when they write it and not what fnmatch does."""
    for pat in patterns:
        if fnmatch.fnmatch(rel, pat):
            return True
        if pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:]):
            return True
        # a bare directory rule excludes everything beneath it
        if pat.endswith("/") and (rel.startswith(pat) or f"/{pat}" in f"/{rel}"):
            return True
    return False


def selector(profiles: dict, name: str):
    """Return (fn(rel)->bool, profile_dict). Raises if the name is unknown."""
    if name not in profiles:
        raise ProfileError(
            f"no profile '{name}' (have: {', '.join(sorted(profiles))})")
    prof = profiles[name]
    inc = list(prof.get("include") or [])
    exc = list(prof.get("exclude") or []) + ALWAYS_EXCLUDE

    def keep(rel: str) -> bool:
        rel = rel.replace(os.sep, "/")
        if _match(rel, exc):
            return False
        if inc and not _match(rel, inc):
            return False
        return True

    return keep, prof


def describe(profiles: dict) -> str:
    out = []
    for name in sorted(profiles):
        p = profiles[name]
        inc = len(p.get("include") or [])
        exc = len(p.get("exclude") or [])
        note = (p.get("notes") or [""])[0]
        out.append(f"  {name:<10} include:{inc:<3} exclude:{exc:<3} {note}")
    return "\n".join(out)


def starter_json() -> str:
    """The file `profiles --write` emits, with the defaults inlined so an
    operator can see the shape before editing rather than guessing at it."""
    doc = dict(DEFAULT_PROFILES)
    doc["_readme"] = [
        "Named include/exclude rulesets for `oxbow bundle build --profile <name>`.",
        "Globs match the POSIX path relative to the source root.",
        "`include` is a whitelist when non-empty and ignored when empty.",
        "`exclude` always wins over `include`.",
        "Editor droppings, caches and OS metadata are excluded under every",
        "profile and do not need to be listed here.",
        "Anything under _quarantine_not_in_bundle/ is never packed.",
    ]
    return json.dumps(doc, indent=2)
