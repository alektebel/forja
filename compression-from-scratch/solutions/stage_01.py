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


class EncodeError(ValueError):
    """A caller's mistake: the refusal names the offender."""


def _fit(value, width):
    # The one refusal both writers share: the value must fit the width
    # it is given, and the width must be one a writer can act on.
    if width < 0:
        raise EncodeError("stage 1: a width of %d bits writes no bits"
                          % (width,))
    if value < 0 or value >> width:
        raise EncodeError("stage 1: value %d does not fit in %d bits"
                          % (value, width))


class BitWriter:
    """Bits into bytes, LSB-first: the course's own order."""

    def __init__(self):
        self._data = bytearray()
        self._nbits = 0

    def append(self, value, width):
        # LSB-first: the value's low bit is the stream's next bit, the
        # order `inflate.BitReader` reads back. Every bit materializes
        # its byte, so a run of zero bits still takes the bytes the
        # stream's length owes.
        _fit(value, width)
        for i in range(width):
            byte = self._nbits >> 3
            while len(self._data) <= byte:
                self._data.append(0)
            if (value >> i) & 1:
                self._data[byte] |= 1 << (self._nbits & 7)
            self._nbits += 1
        return self

    def bytes(self):
        # The stream so far: a copy, zero-padded in the last byte, so
        # the writer can go on appending after a read.
        return bytes(self._data)


def write_bits(data, value, width):
    """Bits overwritten into an existing buffer, the value's width kept."""
    # The stateless half of the writer: the value's bits overwrite the
    # buffer's first `width` bits, LSB-first — the buffer's length is
    # never changed and its remaining bits are never touched. A width
    # the buffer does not hold is a caller's mistake, refused before a
    # single bit moves.
    if width < 0:
        raise EncodeError("stage 1: a width of %d bits writes no bits"
                          % (width,))
    if width > len(data) * 8:
        raise EncodeError("stage 1: width %d does not fit the buffer's "
                          "%d bits" % (width, len(data) * 8))
    _fit(value, width)
    out = bytearray(data)
    for i in range(width):
        bit = 1 << (i & 7)
        if (value >> i) & 1:
            out[i >> 3] |= bit
        else:
            out[i >> 3] &= ~bit & 0xFF
    return bytes(out)


def bit_length_of(n):
    """How many bits a non-negative int needs: the width `append` checks."""
    if n < 0:
        raise EncodeError("stage 1: bit_length_of() needs a non-negative "
                          "int, got %d" % (n,))
    return n.bit_length()
