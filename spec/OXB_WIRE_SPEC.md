# Oxbow public wire specification v0.1

Status: release-candidate specification for the canonical public writer/reader in `src/oxbow/bundle/kernel.py`.

This document specifies the deliberately small public profile named:

`rsb1-v5-public-kernel-1`

Historical Rosetta readers understand a larger RSB1 v5 family. That larger family is **not** the public v0.1 Oxbow profile. A conforming public Oxbow writer emits only the subset below; the canonical public reader rejects the historical global pools and specialist codecs rather than trying to decode them.

## 1. Goals

The public profile optimizes in this order:

1. exact lossless preservation of selected regular files;
2. bounded/safe decoding;
3. deterministic writer output for the same file set;
4. inspectable manifest integrity;
5. compression size.

The profile uses one codec only: **raw LZMA2, preset 6**.

## 2. Primitive integer encoding

Every integer described as `varint` is an unsigned base-128 little-endian varint (ULEB128 style):

- seven payload bits per byte;
- bit 7 set means another byte follows;
- least-significant group first.

The canonical reader accepts at most ten bytes per varint and applies a context-specific maximum value.

## 3. Top-level payload

A public payload is:

```text
4 bytes   ASCII "RSB1"
1 byte    version = 5

repeat 3 times: historical global-pool descriptor
  varint  item_count      MUST be 0
  varint  offset_len      MUST be 0
  bytes   offset_stream   empty
  varint  codec_len       MUST be 0
  bytes   codec_stream    empty

varint    section_count   MUST be 1

section:
  varint  name_len
  bytes   UTF-8 name      MUST be "files"
  varint  text_count      MUST be 0
  varint  binary_count    N
  varint  gpx_count       MUST be 0
  varint  path_count      MUST equal N
  varint  path_codec_len
  bytes   path_codec

  if N > 0:
    varint  offset_codec_len
    bytes   offset_codec
    varint  data_codec_len
    bytes   data_codec

EOF        no trailing bytes
```

The three empty global-pool descriptors are retained only so current output stays structurally readable by the recovered RSB1 v5 reference decoder. They carry no public data.

## 4. Compression codec

`path_codec`, `offset_codec`, and `data_codec` are each encoded with Python/standard LZMA semantics equivalent to:

```python
lzma.compress(
    raw,
    format=lzma.FORMAT_RAW,
    filters=[{"id": lzma.FILTER_LZMA2, "preset": 6}],
)
```

A reader MUST bound decompressed output rather than calling an unbounded decompressor on attacker-controlled input.

No other codec tag or codec competition exists in the public v0.1 writer.

## 5. Path table

After LZMA2 decompression, `path_codec` contains exactly `N` rows concatenated with no header:

```text
1 byte    pool_id       MUST be 1 (local binary pool)
varint    path_len
bytes     UTF-8 path
varint    binary_index
```

Path requirements:

- nonempty Unicode text encodable as UTF-8;
- no NUL;
- forward slash `/` is the only separator;
- no backslash;
- no absolute path;
- no drive-qualified prefix such as `C:`;
- no colon anywhere;
- no empty component;
- no `.` or `..` component;
- normalized POSIX spelling must equal the stored spelling;
- at most 4096 UTF-8 bytes under the default limits;
- no duplicate paths.

The set of `binary_index` values MUST be exactly the permutation `0..N-1`.

The canonical writer sorts source files lexicographically by stored path before encoding, assigns indexes in that order, and therefore produces deterministic path order. The canonical reader does not depend on sorted input; it depends on the exact index permutation.

## 6. Offset table

After decompression, `offset_codec` contains exactly `N + 1` varints.

The canonical writer encodes:

```text
0
len(file_0)
len(file_1)
...
len(file_N-1)
```

The reader cumulative-sums those values to recover absolute offsets:

```text
0
offset_end_file_0
offset_end_file_1
...
offset_end_file_N-1
```

Requirements:

- first cumulative offset is zero;
- offsets are monotonic;
- each adjacent difference is within the per-file limit;
- final cumulative offset equals decompressed `data_codec` length;
- no trailing bytes remain in the decompressed offset stream.

## 7. File data

After decompression, `data_codec` is the direct concatenation of every file's exact bytes in binary-index order.

The public profile assigns no type-specific semantics. Text, images, PDFs, archives, audio, zero-byte files, and arbitrary binary files are all opaque bytes at this layer.

A writer MUST NOT silently omit a selected regular file because of its extension or content.

## 8. Generated manifest

The canonical writer reserves:

`manifests/MANIFEST.generated.json`

The source tree may not supply that path.

Before encoding, the writer creates an UTF-8 JSON document:

```json
{
  "format": "oxbow-manifest-v1",
  "wire_profile": "rsb1-v5-public-kernel-1",
  "files": [
    {
      "path": "relative/path",
      "bytes": 123,
      "sha256": "64 lowercase hex characters"
    }
  ]
}
```

Records describe every selected source file and do **not** list the manifest itself. The generated manifest is then added to the payload as one additional file.

The canonical reader's integrity layer requires exact reconciliation:

- every manifest path exists in the payload;
- no unmanifested payload path exists other than the manifest itself;
- byte length matches when declared;
- SHA-256 matches;
- manifest paths are portable/safe and unique;
- the manifest does not list itself.

Manifest integrity is separate from wire validity and from factual truth.

## 9. Handoff conformance

A wire-valid, manifest-exact payload is an Oxbow v0.1 handoff only if it also satisfies `oxbow-conformance-v1`.

Required root documents:

- `READ_FIRST.md`
- `BUNDLE_LAYOUT.md`

And at least one recognized start/tour surface:

- `START_HERE.md`, or
- a top-level `TOUR*.md`, or
- a direct child `tours/<name>.md`.

`oxbow init` creates `HANDOFF.md` as the default working-state surface, but `HANDOFF.md` is not part of the minimum wire conformance requirement so intentionally different handoff interfaces can still conform.

## 10. Default resource limits

The canonical public reader currently enforces:

| Limit | Default |
|---|---:|
| payload bytes | 256 MiB |
| file count | 10,000 |
| total decompressed raw bytes | 512 MiB |
| one file | 128 MiB |
| path UTF-8 bytes | 4,096 |
| section-name bytes | 64 |

A compatible implementation may choose lower local ceilings. It must not claim to have decoded a payload it truncated to satisfy a limit.

## 11. Source-tree policy before encoding

The canonical writer:

- accepts a directory root only;
- refuses a symlink as the source root;
- walks without following symlink directories;
- refuses a selected symlink file or selected symlink directory;
- accepts regular files only;
- verifies a file did not change identity/size while being read;
- reports profile/policy exclusions;
- refuses to write the bundle/report inside the source tree;
- rejects the reserved generated-manifest path.

Profile exclusions occur before wire encoding and are reported by the build report. The wire format itself has no hidden file-type drop rule.

## 12. Extraction policy

A conforming safe extractor SHOULD implement at least the canonical protections:

- validate every stored path before creating it;
- extract only into a new or empty destination;
- reject a symlink destination;
- refuse overwrite of any target path;
- resolve each created parent and confirm containment within the extraction root.

The `.oxb.py` generated runtime uses the same public limits/path rules as the installed canonical reader.

## 13. `.oxb` versus `.oxb.py`

`.oxb` is the inert RSB1 payload specified here.

`.oxb.py` is not a different wire format. It is executable Python that embeds the exact `.oxb` bytes as base85 plus a standalone reader/verifier/extractor. The canonical wrapper contains an expected SHA-256 and expected payload metadata and verifies those against the embedded bytes.

A detached Oxbow signature covers the inert `.oxb` payload bytes, including when the operator shipped them inside `.oxb.py`. It does not authenticate arbitrary surrounding Python source.

## 14. Authenticity

Authenticity is not encoded into RSB1 itself.

The public CLI can produce a detached JSON signature document using Ed25519. Identity-bearing verification additionally requires the recipient to pin the expected public key through an independent trust path.

See `docs/TRUST_MODEL.md`.

## 15. Compatibility

The public v0.1 encoder intentionally emits a subset of historical RSB1 v5. The repository carries a frozen historical reference decoder under `compat/rosetta_v5/` only as compatibility evidence.

A future Oxbow version may add a new explicitly named wire profile. It must not silently change the meaning of `rsb1-v5-public-kernel-1`.
