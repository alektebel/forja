"""Compression From Scratch — the reference inflate: RFC 1951, strict.

The judge for the DEFLATE stages: a decoder that accepts exactly what
RFC 1951 allows and refuses everything else. It reads LSB-first (the
format's own bit order), answers the bytes and how many bits it consumed,
and never guesses: a length that outruns the output, a distance that
reaches before the window's start, a code whose Kraft sum is not one, a
stored block whose LEN disagrees with its NLEN — each is a refusal naming
what the format forbids.

This module is provided; its digest is pinned in `.h7-dev/verify_provided.py`
and it is never edited to make a stage pass.
"""

import zlib


class InflateError(ValueError):
    """The decoder's one refusal: what the format forbids."""


class BitReader:
    """LSB-first bits over bytes: the format's own order."""

    def __init__(self, data, bit_offset=0):
        self._data = data
        self._pos = bit_offset

    def read(self, width):
        """`width` bits, LSB-first, as an int."""
        if self._pos + width > len(self._data) * 8:
            raise InflateError("inflate: the stream ends mid-value "
                               "(wanted %d bits at bit %d)"
                               % (width, self._pos))
        value = 0
        for i in range(width):
            byte = self._data[(self._pos + i) // 8]
            if (byte >> ((self._pos + i) % 8)) & 1:
                value |= 1 << i
        self._pos += width
        return value

    def align(self):
        """Skip to the next byte boundary."""
        self._pos = (self._pos + 7) & ~7

    @property
    def pos(self):
        return self._pos


def _build(lengths):
    """Canonical Huffman decode tables from per-symbol code lengths.

    Answers (counts, symbols): `counts[w]` is how many codes have width w,
    `symbols` is the symbols in the canonical order (by width, then by
    symbol). Kraft's sum must be exactly one or the refusal names it.
    """
    counts = [0] * 16
    for width in lengths:
        if width:
            counts[width] += 1
    used = 0
    left = 1
    for width in range(1, 16):
        left = (left << 1) - counts[width]
        if left < 0:
            raise InflateError("inflate: the code is over-subscribed "
                               "(Kraft's sum exceeds one)")
        used += counts[width]
    if used > 1 and left != 0:
        raise InflateError("inflate: the code is under-subscribed "
                           "(Kraft's sum below one)")
    offsets = [0] * 16
    for width in range(1, 15):
        offsets[width + 1] = offsets[width] + counts[width]
    symbols = [0] * used
    order = sorted((width, symbol) for symbol, width in enumerate(lengths)
                   if width)
    for index, (width, symbol) in enumerate(order):
        symbols[offsets[width]] = symbol
        offsets[width] += 1
    return counts, symbols


def _decode_one(reader, counts, symbols):
    """One symbol off the stream, walking the canonical code's widths."""
    code = 0
    first = 0
    index = 0
    for width in range(1, 16):
        code |= reader.read(1)
        count = counts[width]
        if code - first < count:
            return symbols[index + (code - first)]
        index += count
        first = (first + count) << 1
        code <<= 1
    raise InflateError("inflate: a code wider than fifteen bits")


_LENGTH_BASE = (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
                35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258)
_LENGTH_EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0)
_DIST_BASE = (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
              257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
              8193, 12289, 16385, 24577)
_DIST_EXTRA = (0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
               7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13)


def _fixed_trees():
    literal_counts, literal_symbols = _build([8] * 144 + [9] * 112
                                             + [7] * 24 + [8] * 8)
    distance_counts, distance_symbols = _build([5] * 32)
    return (literal_counts, literal_symbols), (distance_counts,
                                               distance_symbols)


_FIXED = None


def inflate(data):
    """A DEFLATE stream decoded: `(bytes, bits_consumed)`.

    Reads the stream's blocks — stored, fixed, dynamic — until the final
    one, and answers what they wrote. Strict: everything RFC 1951 refuses,
    this refuses.
    """
    global _FIXED
    if _FIXED is None:
        _FIXED = _fixed_trees()
    reader = BitReader(data)
    out = bytearray()
    while True:
        final = reader.read(1)
        kind = reader.read(2)
        if kind == 0:
            reader.align()
            header_at = reader.pos // 8
            if header_at + 4 > len(data):
                raise InflateError("inflate: a stored block's header is "
                                   "cut off")
            length = data[header_at] | (data[header_at + 1] << 8)
            nlen = data[header_at + 2] | (data[header_at + 3] << 8)
            if length ^ 0xFFFF != nlen:
                raise InflateError("inflate: a stored block's LEN is not "
                                   "NLEN's complement")
            start = (header_at + 4) * 8
            if start + length * 8 > len(data) * 8:
                raise InflateError("inflate: a stored block's bytes are "
                                   "cut off")
            out += data[header_at + 4:header_at + 4 + length]
            reader = BitReader(data, start + length * 8)
        elif kind in (1, 2):
            if kind == 1:
                literal_tree, distance_tree = _FIXED
            else:
                literal_tree, distance_tree = _dynamic(reader)
            _block(reader, out, literal_tree, distance_tree)
        else:
            raise InflateError("inflate: block kind 3 is reserved")
        if final:
            break
    return bytes(out), reader.pos


def _dynamic(reader):
    """A dynamic block's two trees, read from the code-length code."""
    hlit = reader.read(5) + 257
    hdist = reader.read(5) + 1
    hclen = reader.read(4) + 4
    order = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1,
             15)
    cl_lengths = [0] * 19
    for i in range(hclen):
        cl_lengths[order[i]] = reader.read(3)
    cl_tree = _build(cl_lengths)
    lengths = []
    while len(lengths) < hlit + hdist:
        symbol = _decode_one(reader, *cl_tree)
        if symbol < 16:
            lengths.append(symbol)
        elif symbol == 16:
            if not lengths:
                raise InflateError("inflate: a repeat with no previous "
                                   "length")
            lengths.extend([lengths[-1]] * (3 + reader.read(2)))
        elif symbol == 17:
            lengths.extend([0] * (3 + reader.read(3)))
        else:
            lengths.extend([0] * (11 + reader.read(7)))
    if len(lengths) > hlit + hdist:
        raise InflateError("inflate: the code lengths overrun HLIT+HDIST")
    literal_lengths = lengths[:hlit]
    distance_lengths = lengths[hlit:]
    if literal_lengths[256] == 0:
        raise InflateError("inflate: the end-of-block symbol has no code")
    return _build(literal_lengths), _build(distance_lengths)


def _block(reader, out, literal_tree, distance_tree):
    """One Huffman-coded block: literals, matches, the end-of-block."""
    while True:
        symbol = _decode_one(reader, *literal_tree)
        if symbol < 256:
            out.append(symbol)
        elif symbol == 256:
            return
        else:
            index = symbol - 257
            if index >= len(_LENGTH_BASE):
                raise InflateError("inflate: a length symbol past the "
                                   "table")
            length = _LENGTH_BASE[index]
            if _LENGTH_EXTRA[index]:
                length += reader.read(_LENGTH_EXTRA[index])
            dist_symbol = _decode_one(reader, *distance_tree)
            if dist_symbol >= len(_DIST_BASE):
                raise InflateError("inflate: a distance symbol past the "
                                   "table")
            distance = _DIST_BASE[dist_symbol]
            if _DIST_EXTRA[dist_symbol]:
                distance += reader.read(_DIST_EXTRA[dist_symbol])
            if distance > len(out):
                raise InflateError("inflate: a distance of %d reaches "
                                   "before the output's start" % (distance,))
            for _ in range(length):
                out.append(out[-distance])
