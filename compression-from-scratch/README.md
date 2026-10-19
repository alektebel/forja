# Compression From Scratch

Build the compressors real formats ship — in pure standard-library Python,
with no floats, no `random`, no `zlib`, and the reference decoders as judges.

A compressed stream is a byte format you can be exactly wrong about, and it
is judged on a ratio. The world is provided as data (`corpus.py` — five
deterministic corpora, `TEXT` 1874 bytes, `JSON_LIKE` 8033, `BINARY` 2608,
`RANDOM` 1024 from a fixed LCG, `EMPTY`, and `BARS`, the ratio ceilings that
are law; `inflate.py` — a strict RFC 1951 decoder, verified against zlib on
every corpus; `lz4ref.py` — a strict LZ4 block decoder; `zstdref.py` — a
frame reader with the real magic, the block kinds and a four-lane checksum).
The codecs on top of that data are what you write.

A bit writer whose first bit is the low bit of the first value; a run-length
format whose marker can never lie; a canonical Huffman code rebuilt from
lengths alone; the package-merge that pulls an over-wide code back under the
limit with Kraft's sum exactly one; LZ77, where the window size is the whole
trade (TEXT 105→98 per-mille from 256 to 4096); LZ4's block with its nibbles
and 255-extensions; DEFLATE's three block kinds and the per-block choice that
stores noise rather than inflating it; FSE's state table you build and walk
backwards; a frame with a header, block kinds, and a checksum; and the
proof — every codec, every corpus, one verdict against the world's own bars,
with one bit flipped to see whether the checksum notices.

No `zlib` behind a stage: the compressed formats are what the student writes,
the reference decoders are what grades it, and the judge is the check's, never
the student's. Every ratio is ints the whole way (`compressed * 1000 //
original` against `corpus.BARS`), so a stage's answer has a ground truth that
no float ever rounded.

## The ten stages

| N | File | Title |
|---|---|---|
| 1 | `stage_01.py` | The bit writer: LSB-first, widths that fit |
| 2 | `stage_02.py` | Run-length: the format that cannot fail |
| 3 | `stage_03.py` | Canonical Huffman: codes from lengths |
| 4 | `stage_04.py` | The length limit: a code that fits the writer |
| 5 | `stage_05.py` | LZ77: the window and the matches |
| 6 | `stage_06.py` | LZ4's block format: nibbles and extensions |
| 7 | `stage_07.py` | DEFLATE: stored, static, dynamic |
| 8 | `stage_08.py` | FSE: the table the format builds |
| 9 | `stage_09.py` | The frame: a header, blocks, and a checksum |
| 10 | `stage_10.py` | The proof: every codec, every corpus, one verdict |

Stage 10 is the capstone: `prove` runs every codec over a corpus — the ratio,
the judge's verdict, the round-trip's exactness, and a flipped bit the frame's
checksum must notice — and `audit` grades the whole against `corpus.BARS`.

## Measured verification

| What | Command | Result |
|---|---|---|
| the stages | `python3 .h7-dev/check_NN.py` (1..10) | ten `PASS` (27+…+88 facts), and ten exits 2 against the templates |
| the mutations | `python3 .h7-dev/mutate_all.py` | `TOTAL 121/121`, `MISSED OR BROKEN: 0` |
| the ladder and the laws | `python3 .h7-dev/audit_course.py` | `AUDITED: 10, PROBLEMS: 0` |
| the provided world | `python3 .h7-dev/verify_provided.py` | `PROVIDED: 63, PROBLEMS: 0` |
| the whole course as one module | `python3 .h7-dev/smoke.py`, `run_assembled.py` | `SMOKE: PASS`, `ASSEMBLED: 10/10` |
| the tests the course ships | `python3 .h7-dev/count_tests.py compression-from-scratch` | 163, per stage `[15, 32, 11, 14, 21, 11, 10, 19, 20, 10]` |
| the judges | stages 6/7/9's reference decodes | `lz4ref`, `inflate`, `zstdref` accept the stage's bytes on every corpus |

Measured, per-mille against the bar: RLE on BINARY 110 vs 700; Huffman on
TEXT 545 vs 650; LZ4 on TEXT 94 vs 550; DEFLATE's dynamic block on TEXT 85
vs 450 (and stored holding RANDOM, where compression has nothing to win);
the frame's compressed mode on TEXT 94 vs 450. FSE — whose decoder is stage
code, so the round-trip is the judge — lands TEXT 1874→1017.

The provided world is pinned by digest:

| File | sha256 |
|---|---|
| `corpus.py` | `3eff4354d39fc920775a7d703ec9344c7bf4170a9dd09c7cdf625aa875fbf58d` |
| `inflate.py` | `b3fc0be41aca55f053a2c85eb8d8ccae3cee9d70662a6244b7cab5abe82803b3` |
| `lz4ref.py` | `295b048c4256add65fda02c42e15824f4f49d4effe591b9a6a656867f6dc22a3` |
| `zstdref.py` | `8755d92d32ea2496cda770ef39a23e41eca4e33f5c1dea2f1af68a10acc3b5f3` |

## The laws a stage is held to

- Standard library only; no `open(`, no `zlib`/`gzip`/`bz2`/`lzma`, no
  `random`, no float literal, no module-level mutable state; a ratio is ints
  the whole way. The one noise corpus is a fixed LCG in `corpus.py`.
- A stage imports the world and earlier stages only, never a later one; the
  reference decoders are world modules — importable, never rewritten.
- The world is never edited to make a stage pass; the four digests are
  pinned, and `inflate` was verified against zlib at three levels plus
  stored before the first stage was written.
- A caller's mistake raises (`EncodeError`, stage 1's, reused course-wide),
  naming the offender; a decoder refuses a truncated stream rather than
  inventing bytes, and a frame refuses when the checksum disagrees.
- The first docstring paragraph is the stage's own title line, every public
  function is a docstring plus exactly one `raise NotImplementedError`, and
  the file carries its `DESIGN DECISION` blocks and a `TODO: implement` line.

## Running it

    python3 codecraft/cli.py run compression-from-scratch

The ten stages are graded in order; the later ones compose the earlier ones
(that is what the ladder law is for), and stage 1's writer is what stage 3
spells its codes through, stage 5's pairs are what stage 6 pays in nibbles
and stage 7 in Huffman, and stage 9's frame is what stage 10's proof judges.
