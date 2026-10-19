"""Compression From Scratch — the corpora and the ratio bars.

The world the codecs are judged on: five byte strings, each a shape a
compressor meets in the wild — repetitive prose, structured records, runs
with a tail of noise, genuine noise, and nothing — plus the ratio bars
(`BARS`), the per-corpus per-codec ceilings a stage must clear. A ratio is
ints the whole way: `compressed * 1000 // original`, compared against the
bar. No floats anywhere in this course.

Determinism is the world's law: the one pseudo-random corpus is driven by
`RANDOM_SEED` through a fixed LCG, so two runs of anything against this
world produce the same bytes.
"""

import hashlib


def _lcg(seed, n):
    """A fixed LCG: the one source of noise the world owns."""
    out = bytearray()
    state = seed
    for _ in range(n):
        state = (state * 6364136223846793005 + 1442695040888963407) \
            & ((1 << 64) - 1)
        out.append((state >> 33) & 0xFF)
    return bytes(out)


TEXT = (b"The quick brown fox jumps over the lazy dog. " * 8 +
        b"Compression is a byte format you can be exactly wrong about; "
        b"the ratio is the judge, and the decoder is the authority. " * 6 +
        b"the quick brown fox " * 40)

JSON_LIKE = b"".join(
    b'{"id": %d, "name": "record-%03d", "value": %d, "tags": ["a", "b"]}\n'
    % (i, i, i * 7) for i in range(120))

BINARY = (b"".join(bytes([i % 7]) * (16 + (i * 13) % 48)
                   for i in range(64)) + _lcg(7, 96))

RANDOM = _lcg(12345, 1024)
RANDOM_SEED = 12345

EMPTY = b""

CORPORA = ("TEXT", "JSON_LIKE", "BINARY", "RANDOM", "EMPTY")

#: (corpus, codec, max compressed per mille) — the bar a stage must clear
BARS = (
    ("BINARY", "rle", 700),
    ("TEXT", "huffman", 650),
    ("TEXT", "lz4", 550),
    ("TEXT", "deflate", 450),
    ("TEXT", "frame", 450),
)


def digest(name):
    """The corpus's sha256: the world's own pin."""
    return hashlib.sha256(getattr(_world, name)).hexdigest()


class _World:
    pass


_world = _World()
for _name in CORPORA:
    setattr(_world, _name, globals()[_name])
