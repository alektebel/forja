"""Compression From Scratch — stage 6: LZ4's block format: nibbles and extensions.

LZ4's block format is LZ77 with a byte budget: a token whose high
nibble is the literal length and low nibble the match length, 255-bytes
for the extensions, the literals inline, a little-endian two-byte offset —
and the last sequence literals-only. `lz4_block_encode` writes it; the
reference `lz4ref.lz4_block_decode` is the judge, and the ratio bars are
the world's.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why is the reference decoder the judge rather than the
stage's own decoder?
Because LZ4 is a format that exists outside this course, and the one
fact that matters is that the bytes a stage writes are the bytes real
LZ4 means: the reference decoder is that fact, strict where the spec is
strict. A stage's own decoder proves nothing about interop.

DESIGN DECISION — why does the token put both nibbles in one byte?
Because most sequences are small: one byte covers the common case, the
255-extension only when a length exceeds fifteen. The format's economy
is the token's — and the check holds the ratio bar that proves it.

DESIGN DECISION — why must the last sequence end literals-only?
Because a match that names no bytes after it is a match the decoder
cannot bound: the trailing literals are where the format says "this is
the end". The reference refuses anything else, and the encoder that
tries one is refused too.
"""

def lz4_block_encode(data):
    """The block format's tokens, literals, offsets — the last sequence
    literals-only."""
    raise NotImplementedError("stage 6: implement lz4_block_encode()")
