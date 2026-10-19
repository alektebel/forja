"""Compression From Scratch — stage 5: LZ77: the window and the matches.

LZ77 is the idea the byte formats are built on: a repeat is two
numbers — how far back, how long. `lz77_encode` answers the pairs and the
literals; `lz77_decode` rebuilds the bytes, overlapping copies included
(a match longer than its distance is the format repeating itself).
The window size is the whole trade: a bigger window sees more repeats
and costs more bits to name them, and the world's bar is set where the
trade shows.

DESIGN DECISION — why does the decoder handle overlap by copying byte by
byte?
Because the overlap IS the format's most useful case: a run of one byte
repeated a thousand times is a match of length 999 at distance 1, and a
slice-based copy would answer the pre-copy bytes. Byte-by-byte is the
semantics, not an implementation detail.

DESIGN DECISION — why is the window a parameter rather than a constant?
Because the stage's whole lesson is the trade: the check holds the ratio
at two window sizes and the pairs' distance fields' widths follow. A
constant window would hide the one decision a format designer actually
makes.

DESIGN DECISION — why answer literals and pairs in one stream rather
than two tables?
Because the order IS the data: a match's position is where it sits
between literals, and a decoder that read two tables would have no way
to know. The interleaved stream is the format; everything else is
bookkeeping.

THE FORMAT, PINNED — the stream is a tuple whose items are either an
int (one literal byte, 0..255) or a (length, distance) tuple. A distance
is counted in bytes back from the position the pair sits at: distance 1
is the previous byte, and a length longer than its distance copies
byte by byte — `out.append(out[-distance])` length times — so the copy
overlaps itself exactly as a run does. The encoder is greedy: at every
position it takes the longest match the window holds, scanning nearest
first so a tie keeps the smallest distance, advances the pair's
whole length, and falls back to a literal when no match reaches
`min_match`. The window is never crossed: no pair names a distance
beyond it, so a smaller window is always a valid (weaker) view of the
same data. The cost model the ratio is judged on: a literal is one
byte, a pair is three — one for the length, two for the distance.
"""

#: the smallest match that can pay: a pair is two numbers, so a
#: one-byte match spends the format's whole price on one byte
MIN_MATCH_FLOOR = 2


class EncodeError(ValueError):
    """A caller's or a stream's mistake, named."""


def lz77_encode(data, window, min_match, max_match):
    """The literals and (length, distance) pairs the window sees."""
    data = bytes(data)
    if window < 1:
        raise EncodeError(
            "lz77_encode: window %d is no window at all (at least 1)"
            % (window,))
    if min_match < MIN_MATCH_FLOOR:
        raise EncodeError(
            "lz77_encode: min_match %d cannot pay — a match costs two "
            "numbers, so min_match is at least %d"
            % (min_match, MIN_MATCH_FLOOR))
    if max_match < min_match:
        raise EncodeError(
            "lz77_encode: max_match %d is below min_match %d"
            % (max_match, min_match))
    out = []
    i = 0
    n = len(data)
    while i < n:
        limit = max_match
        if limit > n - i:
            limit = n - i
        lo = i - window
        if lo < 0:
            lo = 0
        best_len = 0
        best_dist = 0
        for start in range(i - 1, lo - 1, -1):
            length = 0
            while length < limit and data[start + length] == data[i + length]:
                length += 1
            if length > best_len:
                best_len = length
                best_dist = i - start
                if best_len == limit:
                    break
        if best_len >= min_match:
            out.append((best_len, best_dist))
            i += best_len
        else:
            out.append(data[i])
            i += 1
    return tuple(out)


def lz77_decode(pairs):
    """The pairs rebuilt, overlapping copies byte by byte."""
    out = bytearray()
    for item in pairs:
        if isinstance(item, int):
            if item < 0 or item > 255:
                raise EncodeError(
                    "lz77_decode: literal %d is not a byte" % (item,))
            out.append(item)
            continue
        if not isinstance(item, tuple) or len(item) != 2:
            raise EncodeError(
                "lz77_decode: stream item %r is neither a literal nor a "
                "(length, distance) pair" % (item,))
        length, distance = item
        if not isinstance(length, int) or not isinstance(distance, int):
            raise EncodeError(
                "lz77_decode: pair %r has a non-integer length or distance"
                % (item,))
        if distance < 1:
            raise EncodeError(
                "lz77_decode: a distance of %d reaches nowhere" % (distance,))
        if distance > len(out):
            raise EncodeError(
                "lz77_decode: distance %d reaches back past the stream's "
                "%d bytes" % (distance, len(out)))
        if length < 1:
            raise EncodeError(
                "lz77_decode: a match of length %d copies nothing"
                % (length,))
        for _ in range(length):
            out.append(out[-distance])
    return bytes(out)
