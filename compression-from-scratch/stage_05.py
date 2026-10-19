"""Compression From Scratch — stage 5: LZ77: the window and the matches.

LZ77 is the idea the byte formats are built on: a repeat is two
numbers — how far back, how long. `lz77_encode` answers the pairs and the
literals; `lz77_decode` rebuilds the bytes, overlapping copies included
(a match longer than its distance is the format repeating itself).
The window size is the whole trade: a bigger window sees more repeats
and costs more bits to name them, and the world's bar is set where the
trade shows.

TODO: implement each function; the docstring is the contract.

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

def lz77_encode(data, window, min_match, max_match):
    """The literals and (length, distance) pairs the window sees."""
    raise NotImplementedError("stage 5: implement lz77_encode()")


def lz77_decode(pairs):
    """The pairs rebuilt, overlapping copies byte by byte."""
    raise NotImplementedError("stage 5: implement lz77_decode()")
