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
"""


class EncodeError(ValueError):
    """Raised for anything the *encoder* got wrong — the caller's mistake."""


def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def lz77_encode(data, window, min_match, max_match):
    """The literals and (length, distance) pairs the window sees.

    Greedy longest match at each position: the pair names the length and
    how far back the copy starts, ties going to the nearest (smallest
    distance). A match shorter than `min_match`, or one the window cannot
    see, stays literal. `max_match` caps the pair's length; the copy stops
    at the data's end. The window's, min_match's and max_match's caller
    mistakes are refused before the data is touched."""
    if not isinstance(window, int) or isinstance(window, bool) or window < 1:
        _refuse("bad_window", window)
    if not isinstance(min_match, int) or isinstance(min_match, bool) \
            or min_match < 2:
        _refuse("bad_min_match", min_match)
    if not isinstance(max_match, int) or isinstance(max_match, bool) \
            or max_match < min_match:
        _refuse("bad_max_match", max_match, min_match)
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", type(data).__name__)
    data = bytes(data)
    n = len(data)
    out = []
    i = 0
    while i < n:
        # the longest match the window holds: distance 1..window,
        # length min_match..max_match, the copy free to run past i
        best_len = 0
        best_dist = 0
        low = max(0, i - window)
        for start in range(i - 1, low - 1, -1):   # nearest first: ties
            length = 0
            limit = min(max_match, n - i)
            while length < limit and data[start + length] == data[i + length]:
                length += 1
            if length > best_len:
                best_len = length
                best_dist = i - start
                if best_len >= limit:
                    break
        if best_len >= min_match:
            out.append((best_len, best_dist))
            i += best_len
        else:
            out.append(data[i])
            i += 1
    return tuple(out)


def lz77_decode(pairs):
    """The pairs rebuilt, overlapping copies byte by byte.

    A literal int lands as its byte; a `(length, distance)` pair copies
    `length` bytes from `distance` back — one byte at a time, so a length
    past the distance repeats the stream's own tail. A distance of zero,
    a negative or zero length, a distance past the stream, a literal out
    of the byte range, or any junk item is refused, naming the offender."""
    if not isinstance(pairs, (tuple, list)):
        _refuse("not_a_stream", type(pairs).__name__)
    out = bytearray()
    for item in pairs:
        if isinstance(item, int) and not isinstance(item, bool):
            if not 0 <= item <= 255:
                _refuse("bad_literal", item)
            out.append(item)
        elif isinstance(item, tuple):
            if len(item) != 2:
                _refuse("bad_pair", item)
            (length, distance) = item
            for value, name in ((length, "length"), (distance, "distance")):
                if isinstance(value, float) or not isinstance(value, int) \
                        or isinstance(value, bool):
                    _refuse("bad_" + name, value)
            if length < 1:
                _refuse("bad_length", length)
            if distance < 1:
                _refuse("bad_distance", distance)
            if distance > len(out):
                _refuse("distance_past_stream", distance, len(out))
            for _ in range(length):
                out.append(out[-distance])
        else:
            _refuse("junk_item", item)
    return bytes(out)
