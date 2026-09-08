# Compatibility boundary

Current Oxbow does not use Rosetta-era packers or specialist codecs on its public path.

`rosetta_v5/reference_decoder.py` is retained as a frozen technical reference so tests can prove that the deliberately small public RSB1 v5 subset remains readable by the recovered decoder lineage.

The historical Rosetta packer, corpus-specific codec fixtures, personal corpus, Rooms, user state, and historical Witness material are intentionally not present in this public tree.

Compatibility code is not installed with the `oxbow` package and must not become the teaching implementation for new contributors.
