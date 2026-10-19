"""Compression From Scratch — stage 1: The bit writer: LSB-first, widths that fit.

`BitWriter` is the whole course's floor: every format after this one is
bits in a byte, and the order those bits land is the format's own. RFC 1951
writes LSB-first — a value's low bit is the stream's next bit — and the
world pins that order here. `write_bits` and the `BitWriter.append` it
backs refuse a value that does not fit the width it is given, because a
writer that silently truncates is a writer that corrupts silently, and a
corruptor is the one thing a byte format must never be.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why LSB-first and not the bit order a human reads?
Because RFC 1951 says so, and the course's later stages are judged by a
decoder that reads what the RFC says: a Huffman code's first bit is the
code's low bit in the stream. Pinning the order here — one place, one
law — is what lets every later stage stop asking.

DESIGN DECISION — why refuse a value wider than its width instead of
masking?
Because masking is a silent corruption: the format is exact, and a value
that does not fit means the caller has already misunderstood the format —
a Huffman code that claims width 5 but holds 6 bits is not a code, it is
a bug wearing one. The refusal names the value and the width; the fix is
the caller's.

DESIGN DECISION — why does `bytes()` pad the last byte with zeros?
Because the stream's length is a byte count, not a bit count: the padding
is never read (the decoders track bit positions), so what it holds is
convention, and the zero is the convention that makes two runs of the
same encoding byte-identical — the determinism the whole course is
judged on.
"""

class BitWriter:
    """Bits into bytes, LSB-first: the course's own order."""


def write_bits(data, value, width):
    """Bits overwritten into an existing buffer, the value's width kept."""
    raise NotImplementedError("stage 1: implement write_bits()")


def bit_length_of(n):
    """How many bits a non-negative int needs: the width `append` checks."""
    raise NotImplementedError("stage 1: implement bit_length_of()")
