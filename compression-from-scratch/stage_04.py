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

DESIGN DECISION — why Package-Merge rather than an ad-hoc demotion?
Because Package-Merge is the one algorithm that provably answers the
optimal length-limited code: minimum total cost subject to Kraft's sum
exactly one at the limit. A demotion heuristic oscillates around the
equality; Package-Merge lands on it by construction.
"""

import stage_03 as _s3


class EncodeError(ValueError):
    """Raised for anything the *encoder* got wrong — the caller's mistake."""


def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def limit_lengths(lengths, max_width):
    """Widths that fit the limit and still decode: Kraft's sum back at one.

    The move is the textbook Package-Merge: the symbols' Huffman weights
    (their own frequencies' due, taken from the input widths as
    2^-width) are the leaves; L rounds of pair-and-merge follow; the
    cheapest `2n - 2` packages of the last round decide each symbol's
    width as one plus its package appearances. The result is the optimal
    length-limited code: Kraft's sum exactly one at `max_width`.

    An over-subscribed input (Kraft above one before any limit), a
    max_width that cannot hold the live symbol count, and negative
    widths are refused, naming the offender."""
    if not isinstance(max_width, int) or isinstance(max_width, bool) \
            or max_width < 1:
        _refuse("bad_max_width", max_width)
    if not isinstance(lengths, tuple) or len(lengths) != 256:
        _refuse("bad_lengths", len(lengths) if isinstance(lengths, tuple)
                else type(lengths).__name__)
    if any((not isinstance(w, int) or isinstance(w, bool) or w < 0)
           for w in lengths):
        bad = [w for w in lengths
               if not isinstance(w, int) or isinstance(w, bool) or w < 0]
        _refuse("bad_length", bad[0])
    live = [(w, s) for s, w in enumerate(lengths) if w]
    if live:
        top = max(w for w, _s in live)
        used = sum(1 << (top - w) for w, _s in live)
        if used > (1 << top):
            _refuse("Kraft", used, top)
    if not live:
        return tuple(lengths)
    if len(live) == 1:
        out = [0] * 256
        out[live[0][1]] = 1
        return tuple(out)
    if len(live) > (1 << max_width):
        _refuse("too_many_symbols", len(live), max_width)
    # already a complete code at or under the limit: pass through whole
    top = max(w for w, _s in live)
    used = sum(1 << (top - w) for w, _s in live)
    if top <= max_width and used == (1 << top):
        return tuple(lengths)
    # --- the textbook Package-Merge over n leaves, L = max_width rounds
    n = len(live)
    # the leaf weight: the symbol's Huffman cost — its own width's
    # reciprocal, scaled to integers.  The original widths already price
    # each symbol's code; a package's weight is the sum of its members'.
    scale = max(top, max_width, 1)
    leaves = sorted(((1 << (scale - w), s) for (w, s) in live),
                    key=lambda pair: (pair[0], pair[1]))
    # round 1's list is the leaves themselves, held as (weight, [syms])
    current = [(w, [s]) for (w, s) in leaves]
    for _level in range(max_width - 1):
        pairs = [(current[i][0] + current[i + 1][0],
                  current[i][1] + current[i + 1][1])
                 for i in range(0, len(current) - 1, 2)]
        # merge the pairs with a fresh copy of the leaves, cheapest first
        fresh = [(w, [s]) for (w, s) in leaves]
        combined = sorted(pairs + fresh, key=lambda p: (p[0], p[1]))
        current = combined[:2 * n]
    # the cheapest 2n - 2 packages of the final list decide the widths:
    # each symbol's width is one plus how many chosen packages hold it
    chosen = current[:2 * n - 2]
    counts = [0] * 256
    for _w, syms in chosen:
        for s in syms:
            counts[s] += 1
    out = [0] * 256
    for _w, s in leaves:
        out[s] = counts[s]
    return tuple(out)
