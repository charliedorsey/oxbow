# Start here

If you want the fastest no-install path, download `prebuilt/oxbow-standard.oxb.py` and start with its `PREBUILT_PROFILE.md` and `START_HERE.md`. Tiny and full variants live beside it in `prebuilt/`.

If you are evaluating Oxbow as a user:

1. read the README's five-minute path;
2. inspect `examples/tiny-handoff/`;
3. run `oxbow init` on a throwaway directory;
4. ship it to `.oxb.py`;
5. use the generated wrapper's `--verify`, `--tour`, and `--cat HANDOFF.md` paths.

If you are evaluating implementation correctness:

1. `spec/OXB_WIRE_SPEC.md`;
2. `src/oxbow/bundle/kernel.py`;
3. `tests/`;
4. `SECURITY.md`;
5. `docs/TRUST_MODEL.md`.

Do not begin with historical compatibility code unless compatibility is the task.
