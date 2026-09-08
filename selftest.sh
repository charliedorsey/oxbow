#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1

# Run test modules in isolated interpreters. Several tests intentionally spawn
# standalone wrapper interpreters; process isolation keeps the repo gate boring
# and prevents one test module's global runtime state from affecting another.
for test_file in "$ROOT"/tests/test_*.py; do
  echo "== $(basename "$test_file") =="
  python3 "$test_file"
done

python3 -m oxbow.selftest
