"""Installed-package smoke gate using only freshly created synthetic data."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from oxbow.bundle import ed25519, kernel
from oxbow.bundle.wrapper import write_wrapper
from oxbow.project import init_project
from oxbow.witness.stream import append_packet, new_stream, rebuild_index
from oxbow.witness.validate import check_boundaries, validate_packet


def _ok(msg):
    print("  ok  %s" % msg)


def main():
    try:
        with tempfile.TemporaryDirectory(prefix="oxbow-selftest-") as td:
            td = Path(td)
            source = td / "handoff"
            init_project(source, name="Synthetic package selftest")
            handoff = source / "HANDOFF.md"
            handoff.write_text(
                "# Handoff — Synthetic package selftest\n\n"
                "## Purpose\nExercise the installed package.\n\n"
                "## Current state\nReady for a round-trip.\n\n"
                "## Decisions already made\nUse only synthetic bytes.\n\n"
                "## Open questions\nNone.\n\n"
                "## Next useful actions\nRun the selftest.\n\n"
                "## Source pointers\nwork/item.bin\n",
                encoding="utf-8",
            )
            (source / "work").mkdir()
            (source / "work" / "item.bin").write_bytes(b"alpha\x00beta\xff")

            scan = kernel.scan_source(source)
            payload = kernel.build_bundle_bytes(scan.files)
            result = kernel.verify_bundle_bytes(payload)
            assert result["ok"], result
            _ok("init + kernel build/manifest/conformance")

            wrapper = td / "synthetic.oxb.py"
            write_wrapper(payload, wrapper, name="synthetic", self_check=True)
            cp = subprocess.run([sys.executable, str(wrapper), "--read-first"], capture_output=True, text=True)
            assert cp.returncode == 0 and "Carry the work, not the model" in cp.stdout
            cp = subprocess.run([sys.executable, str(wrapper), "--cat", "HANDOFF.md"], capture_output=True, text=True)
            assert cp.returncode == 0 and "Exercise the installed package" in cp.stdout
            out = td / "extract"
            cp = subprocess.run([sys.executable, str(wrapper), "--extract", str(out)], capture_output=True, text=True)
            assert cp.returncode == 0, cp.stdout + cp.stderr
            assert (out / "work/item.bin").read_bytes() == b"alpha\x00beta\xff"
            _ok("standalone .oxb.py verify/read/cat/extract")

            sk, pk = ed25519.keygen()
            sig = ed25519.sign(payload, sk, pk)
            assert ed25519.verify(sig, payload, pk)
            assert not ed25519.verify(sig, payload + b"x", pk)
            _ok("Ed25519 positive/negative path")

            schema_path = Path(__file__).parent / "witness" / "schemas" / "portable_packet.schema.json"
            schema = json.loads(schema_path.read_text())
            packet = {
                "packet_id": "pkt_2099-01-01_synthetic",
                "packet_type": "session",
                "source": {"description": "A synthetic package selftest session completed."},
                "reads": [{"name": "status", "value": "ready"}],
                "overhang": [],
                "self_witness": {
                    "drafter_was_party": True,
                    "caveat": "This synthetic drafter only observed the selftest path."
                },
                "third_party_context": {"present": False, "handling_note": "none"},
            }
            validate_packet(packet, schema)
            assert check_boundaries(packet) == []
            stream = new_stream("synthetic", stream_id="wtn_synthetic_selftest")
            stream2 = append_packet(stream, packet)
            assert len(stream2["records"]) == 1
            assert rebuild_index(stream2) == stream2["derived_index"]
            _ok("Witness validate/append/rebuild")

        print("OXBOW SELFTEST: ALL PASS")
        return 0
    except Exception as exc:
        print("OXBOW SELFTEST: FAIL - %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
