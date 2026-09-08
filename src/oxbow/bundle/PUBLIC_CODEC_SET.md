# Public codec set — Phase B lock

Status: locked for the public correctness kernel.

The canonical public Oxbow encoder deliberately emits a much smaller wire subset
than the recovered Rosetta/Oxbow development packer.

## What the default encoder may emit

For `RSB1` version 5 payloads produced by `bundle.kernel`:

- zero global pools;
- exactly one section named `files`;
- zero text pools;
- zero GPX pools;
- one local binary record per path;
- raw LZMA2 preset 6 for the path table;
- raw LZMA2 preset 6 for the offset table;
- raw LZMA2 preset 6 for the concatenated file bytes.

That is the entire public codec set for Phase B.

Every selected regular file is treated as opaque bytes. File extension and
content type do not change whether it is eligible to ship. PNG, JPEG, PDF, ZIP,
WAV, compressed archives, random binary, source code, and Markdown all travel
through the same lossless path.

## Why this is intentionally boring

The product job is reliable handoff, not compression research. The historical
packer contains useful specialist codecs and corpus-specific experiments, but
those are not allowed to influence whether a user's file survives a public
build.

A public encoder therefore optimizes for:

1. exact round-trip behavior;
2. a small decoder attack surface;
3. bounded resource use;
4. inspectable conformance;
5. compatibility with the recovered RSB1 v5 reference decoder.

Compression ratio is subordinate to all five.

## Historical codecs

`bundle/taproot/pack_v534.py`, `codecs/`, and the recovered specialist codec
material remain in the Phase B worktree only as migration inputs. They are not
called by the default `bundle build`, `verify`, or `extract` path. Phase C moves
that material to compatibility/history or removes it from the canonical product
surface.

No new codec may enter the public encoder unless all of the following are true:

- its decoder is implemented in the bounded public reader;
- its framing is specified;
- hostile-input limits are defined;
- encoder output self-round-trips byte-identically;
- the recovered/reference decoder behavior is addressed explicitly;
- tests cover malformed as well as valid input;
- it solves a product problem important enough to justify the additional attack
  surface.

Until then, LZMA2 preset 6 is the floor and the ceiling.
