"""Compression From Scratch — stage 4: The length limit: a code that fits the writer.

A canonical Huffman code's longest width can reach the symbol count's
depth — and the bit writer, the frame, and every real format cap the
width. `limit_lengths` takes a canonical code's lengths and a maximum
width and answers lengths that still decode: Kraft's sum back at one (a
limited code wastes nothing), the most frequent symbols keeping the
shortest widths, and the round-trip holding on every corpus.

DESIGN DECISION — why must Kraft's sum return to exactly one?
Because a code under one wastes a prefix it could have used and a code
over one is not decodable at all — the limit's whole art is moving width
from the rare symbols to the frequent ones without leaving either
condition. The check holds the equality on every corpus, not just the
round-trip.

DESIGN DECISION — why cap widths at all when the stage-3 code already
decodes?
Because DEFLATE caps code widths at fifteen and the bit writer at the
byte's own arithmetic: a format that allowed width 256 would need a
decoder that walks 256 levels deep. The limit is where the format meets
the machine, and this stage is where the course pays that cost.

DESIGN DECISION — why adjust the limited code by demotion rather than
rebuild the tree with a constraint?
Because the demotion (move a width from a rare symbol to a frequent one,
again and again until the limit holds) is local, checkable, and
deterministic — and a constrained rebuild is none of those things. The
check proves the demotion's result: Kraft's equality, the frequent
symbols shortest, the round-trip exact.
"""

import stage_03 as s3


class EncodeError(ValueError):
    """A caller's mistake: the refusal names the offender."""


def _kraft_scaled(lengths):
    """Kraft's sum scaled to ints: 0 is exactly one, negative over one
    (undecodable), positive under one (a wasted prefix)."""
    used = 0
    for width in lengths:
        if width > 0:
            used += 1 << (_CEIL - width)
    return (1 << _CEIL) - used


_CEIL = 64


def limit_lengths(lengths, max_width):
    """Widths that fit the limit and still decode: Kraft's sum back at one."""
    if not isinstance(max_width, int) or isinstance(max_width, bool):
        raise EncodeError("stage 4: max_width must be an int, got %r"
                          % (max_width,))
    if max_width < 1:
        raise EncodeError("stage 4: max_width %d leaves no room for a "
                          "code" % (max_width,))
    lengths = tuple(lengths)
    if any(not isinstance(width, int) or isinstance(width, bool)
           for width in lengths):
        raise EncodeError("stage 4: lengths must be ints")
    if any(width < 0 for width in lengths):
        raise EncodeError("stage 4: length %d is negative; a width is "
                          "not" % (min(lengths),))
    if _kraft_scaled(lengths) < 0:
        raise EncodeError("stage 4: Kraft's sum above one; the lengths "
                          "do not decode")
    live = [symbol for symbol, width in enumerate(lengths) if width]
    if not live:
        return lengths
    if len(live) == 1:
        # One symbol alone holds width 1: the only complete code for it.
        only = [0] * len(lengths)
        only[live[0]] = 1
        return tuple(only)
    if len(live) > (1 << max_width):
        raise EncodeError("stage 4: max_width %d holds %d leaves at most; "
                          "the code has %d symbols"
                          % (max_width, 1 << max_width, len(live)))

    # Package-merge, with the original lengths as the frequencies' proxy
    # (a length is all limit_lengths is given, and the code's own order
    # is the law: a shorter original width is a more frequent symbol).
    # Each level doubles the "budget" of leaves the code may spend; the
    # first 2n-2 items of the last level's list are the ones the optimal
    # limited code takes, and a leaf's count among them is its width.
    base = max(lengths[symbol] for symbol in live) + 1
    items = tuple(sorted((1 << (base - lengths[symbol]), symbol, _unit(len(lengths), symbol))
                         for symbol in live))
    current = items
    for _ in range(max_width - 1):
        packages = []
        for at in range(0, len(current) - 1, 2):
            first = current[at]
            second = current[at + 1]
            counts = list(first[2])
            other = second[2]
            for symbol in range(len(counts)):
                counts[symbol] += other[symbol]
            packages.append((first[0] + second[0], min(first[1], second[1]),
                             tuple(counts)))
        merged = sorted(items + tuple(packages),
                        key=lambda item: (item[0], item[1]))
        current = tuple(merged)

    widths = [0] * len(lengths)
    for _freq, _symbol, counts in current[:2 * len(live) - 2]:
        for symbol in range(len(widths)):
            widths[symbol] += counts[symbol]
    if any(width > max_width for width in widths) or \
            _kraft_scaled(widths) != 0:
        raise EncodeError("stage 4: max_width %d cannot hold this code's "
                          "%d symbols" % (max_width, len(live)))
    return tuple(widths)


def _unit(size, symbol):
    counts = [0] * size
    counts[symbol] = 1
    return tuple(counts)
