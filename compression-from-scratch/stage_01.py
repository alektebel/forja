"""Compression From Scratch — stage 1: The bit writer: LSB-first, widths that fit.

`BitWriter` is the whole course's floor: every format after this one is
bits in a byte, and the order those bits land is the format's own. RFC 1951
writes LSB-first — a value's low bit is the stream's next bit — and the
world pins that order here. `write_bits` and the `BitWriter.append` it
backs refuse a value that does not fit the width it is given, because a
writer that silently truncates is a writer that corrupts silently, and a
corruptor is the one thing a byte format must never be.

DESIGN DECISION — why LSB-first and not the bit order a human reads?
Because RFC 1951 says so, and the course's later stages are judged by a
decoder that reads what the RFC says: a Huffman code's first bit is the
code's low bit in the stream. Pinning the order here — one place, one
law — is what lets every later stage stop asking.

DESIGN DECISION — why refuse a value wider than its width instead of
masking?
Because masking is a silent corruption: the format is exact, and a value
that does not fit means the caller has already misunderstood the format.
The refusal names the value and the width; the fix is the caller's.

DESIGN DECISION — why does `bytes()` pad the last byte with zeros?
Because the stream's length is a byte count, not a bit count: the padding
is never read (the decoders track bit positions), so what it holds is
convention, and the zero is the convention that makes two runs of the
same encoding byte-identical — the determinism the whole course is
judged on.
"""


class EncodeError(ValueError):
    """Raised for anything the *encoder* got wrong — the caller's mistake."""


def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def bit_length_of(n):
    """How many bits a non-negative int needs: the width `append` checks."""
    if not isinstance(n, int) or isinstance(n, bool):
        _refuse("not an int", n)
    if n < 0:
        _refuse("negative", n)
    return n.bit_length()


class BitWriter:
    """Bits into bytes, LSB-first: the course's own order."""

    def __init__(self):
        self._bits = []          # the stream, one entry per bit, LSB-first
        self._bit_count = 0      # how many bits are owed to full bytes

    def append(self, value, width):
        """One value's low `width` bits, LSB-first into the stream.

        Refuses a value that does not fit the width, a negative value, and
        a width that is not a non-negative int — naming the offender."""
        if not isinstance(width, int) or isinstance(width, bool) or width < 0:
            _refuse("bad_width", width)
        if not isinstance(value, int) or isinstance(value, bool):
            _refuse("not_an_int", value)
        if value < 0:
            _refuse("negative", value)
        if width == 0:
            if value != 0:
                _refuse("no_room", value, 0)
            return self
        if value >> width:
            _refuse("over_width", value, width)
        for i in range(width):
            self._bits.append((value >> i) & 1)
        return self

    def bytes(self):
        """The stream as bytes, the last byte zero-padded — a copy, so a
        later append never changes what an earlier read saw."""
        out = bytearray()
        for i in range(0, len(self._bits), 8):
            byte = 0
            for j, bit in enumerate(self._bits[i:i + 8]):
                byte |= bit << j
            out.append(byte)
        return bytes(out)


def write_bits(data, value, width):
    """Bits overwritten into an existing buffer, the value's width kept.

    The buffer's first `width` bits — LSB-first — are replaced by the
    value's; the bits past the width and the buffer's length are untouched.
    Refuses a width past the buffer's size and a value that does not fit."""
    if not isinstance(width, int) or isinstance(width, bool) or width < 0:
        _refuse("bad_width", width)
    if not isinstance(value, int) or isinstance(value, bool):
        _refuse("not_an_int", value)
    if value < 0:
        _refuse("negative", value)
    if width == 0:
        if value != 0:
            _refuse("no_room", value, 0)
        return bytes(data)
    if value >> width:
        _refuse("over_width", value, width)
    if width > len(data) * 8:
        _refuse("no_room", width, len(data) * 8)
    out = bytearray(data)
    for i in range(width):
        bit = (value >> i) & 1
        byte_i = i // 8
        bit_i = i % 8
        if bit:
            out[byte_i] |= 1 << bit_i
        else:
            out[byte_i] &= ~(1 << bit_i) & 0xFF
    return bytes(out)
