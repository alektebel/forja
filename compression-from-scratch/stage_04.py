"""Compression From Scratch — stage 4: The length limit: a code that fits the writer.

A canonical Huffman code's longest width can reach the symbol count's
depth — and the bit writer, the frame, and every real format cap the
width. `limit_lengths` takes a canonical code's lengths and a maximum
width and answers lengths that still decode: Kraft's sum back at one (a
limited code wastes nothing), the most frequent symbols keeping the
shortest widths, and the round-trip holding on every corpus.

TODO: implement each function; the docstring is the contract.

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

def limit_lengths(lengths, max_width):
    """Widths that fit the limit and still decode: Kraft's sum back at one."""
    raise NotImplementedError("stage 4: implement limit_lengths()")
