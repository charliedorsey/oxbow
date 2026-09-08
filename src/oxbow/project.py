"""Create a small, editable Oxbow handoff skeleton."""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def _title(name: str) -> str:
    name = name.strip()
    return name or "Untitled handoff"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "handoff"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _templates(name: str, *, witness: bool = True):
    title = _title(name)
    docs = {
        "READ_FIRST.md": f"""# Read first\n\nThis directory is an **Oxbow handoff** for **{title}**. It is meant to help a fresh AI instance or human reader pick up existing work without pretending to have lived the earlier trajectory.\n\n## Boundary\n\n- Treat files in this handoff as **source**, not memory.\n- Do not claim continuity with a prior model instance.\n- Preserve distinctions between reported facts, operator-authored state, inference, and open questions.\n- Verification can establish that bytes arrived intact. It cannot establish that the contents are factually true.\n\n## First actions\n\n1. If you received an `.oxb.py`, verify it before relying on it: `python HANDOFF.oxb.py --verify`.\n2. Read `START_HERE.md`.\n3. Read `HANDOFF.md` for the current working state.\n4. Pull deeper corpus material only as the task requires. Do not inventory everything unless the task calls for it.\n\n**Carry the work, not the model.**\n""",
        "START_HERE.md": """# Start here\n\nUse this order unless the task itself gives you a better reason not to:\n\n1. `READ_FIRST.md` — boundary and trust posture.\n2. `HANDOFF.md` — current purpose, state, decisions, and open questions.\n3. The specific source files named by `HANDOFF.md` or by the current task.\n4. `BUNDLE_LAYOUT.md` if you need to understand the object itself.\n5. `witness/README.md` only if you are asked to leave a portable session record.\n\nThe whole corpus does not deserve equal attention on every turn. Orient first, then read what the work requires.\n""",
        "BUNDLE_LAYOUT.md": """# Bundle layout\n\nOxbow does not require a domain-specific directory structure. The root documents are the interface; everything else is the operator's corpus.\n\n- `READ_FIRST.md` — factual first door and continuity boundary.\n- `START_HERE.md` — recommended reading sequence.\n- `HANDOFF.md` — editable working-state summary maintained by the operator.\n- `BUNDLE_LAYOUT.md` — this file.\n- `witness/` — optional append-only session records and write-back guidance.\n- everything else — source material, working files, tools, or artifacts chosen by the operator.\n\nDuring packing, Oxbow adds `manifests/MANIFEST.generated.json`. The manifest describes the packed source tree and is used for exact integrity verification.\n\nDerived indexes never outrank source records. Integrity never implies factual truth.\n""",
        "HANDOFF.md": f"""# Handoff — {title}\n\n> OXBOW-TODO: Replace the prompts below with the smallest truthful state a new reader needs. Delete this TODO line when the handoff is ready.\n\n## Purpose\n\nWhat is this work trying to accomplish?\n\n## Current state\n\nWhat exists now? What is working, broken, provisional, or waiting?\n\n## Decisions already made\n\nRecord decisions that a new reader should not casually reopen. Link to source evidence where useful.\n\n## Open questions\n\nWhat is genuinely unresolved?\n\n## Next useful actions\n\nWhat would move the work forward?\n\n## Source pointers\n\nName the files or directories most likely to matter first.\n""",
    }
    if witness:
        docs["witness/README.md"] = """# Witness write-back\n\nWitness is an optional append-only record for carrying a compact account of a work session into a later handoff. It checks **form and declared provenance boundaries, not truth**.\n\nThe normal operator flow is:\n\n```bash\noxbow witness draft --stream witness/stream.json --out witness/prompt.md\n# give prompt.md to the model that just did the work; save its JSON as packet.json\noxbow witness validate packet.json\noxbow witness append packet.json --stream witness/stream.json\n```\n\nA packet must separate `source` (what happened / what was provided) from `reads` (interpretations), preserve `overhang` (what remains open), state whether the drafter was a party to the session, and explicitly flag third-party context when present.\n\nRecords are append-only. Corrections are new records; old records are not rewritten. The stream's `derived_index` is rebuildable and never outranks the records.\n"""
        stream = {
            "format": "oxbow-witness-stream-v1",
            "stream_id": "wtn_%s" % uuid.uuid4().hex,
            "name": title,
            "created_at": _utc_now(),
            "records": [],
            "derived_index": {
                "record_count": 0,
                "packet_ids": [],
                "open_overhang_by_record": {},
                "records_with_third_party_context": [],
            },
        }
        docs["witness/stream.json"] = json.dumps(stream, indent=2, sort_keys=True) + "\n"
    return docs


def init_project(root: Path, *, name: Optional[str] = None, witness: bool = True):
    root = Path(root)
    if root.exists() and root.is_symlink():
        raise ValueError("target directory may not be a symlink")
    if root.exists() and not root.is_dir():
        raise ValueError("target exists and is not a directory: %s" % root)
    root.mkdir(parents=True, exist_ok=True)
    display = name or root.name or "Untitled handoff"
    templates = _templates(display, witness=witness)
    conflicts = [root / rel for rel in templates if (root / rel).exists()]
    if conflicts:
        raise ValueError(
            "refusing to overwrite existing Oxbow front-door file(s): %s"
            % ", ".join(str(p) for p in conflicts)
        )
    written = []
    for rel, body in templates.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        written.append(p)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oxbow init", description="create a minimal Oxbow handoff skeleton")
    ap.add_argument("directory")
    ap.add_argument("--name", help="display name written into the handoff documents")
    ap.add_argument("--no-witness", action="store_true", help="do not create the optional witness stream/guidance")
    a = ap.parse_args(argv)
    try:
        root = Path(a.directory)
        written = init_project(root, name=a.name, witness=not a.no_witness)
    except (OSError, ValueError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print("initialized Oxbow handoff -> %s" % Path(a.directory))
    for p in written:
        print("  + %s" % p.relative_to(Path(a.directory)))
    print("next: edit HANDOFF.md, add your corpus, then `oxbow ship %s -o HANDOFF.oxb.py`" % a.directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
