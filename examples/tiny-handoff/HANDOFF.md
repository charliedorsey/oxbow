# Handoff — Tiny relay demo

## Purpose

Build a tiny command-line tool that reads a newline-delimited task file and emits stable JSON records. This corpus is synthetic and exists only to demonstrate an Oxbow handoff.

## Current state

The parser accepts `title | owner | status` lines and normalizes whitespace. The sample fixture is working. No packaging or network behavior is required.

## Decisions already made

- The first design used CSV. That decision was superseded because commas in task titles made the format awkward for the tiny fixture.
- The current input separator is a literal pipe (`|`). See `decisions/002-pipe-format.md`.
- Unknown status values are preserved rather than silently coerced.

## Open questions

- Should blank owner values become `null` or remain an empty string?
- Should comments beginning with `#` be supported?

## Next useful actions

1. Read `requirements.md`.
2. Inspect the superseded and current decisions.
3. Run or reason about `src/normalize.py` against `data/tasks.txt`.
4. If you change a decision, record the change explicitly rather than rewriting the old decision file.

## Source pointers

- `requirements.md`
- `decisions/001-csv-format.md`
- `decisions/002-pipe-format.md`
- `src/normalize.py`
- `data/tasks.txt`
