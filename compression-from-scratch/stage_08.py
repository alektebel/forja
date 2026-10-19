"""Compression From Scratch — stage 8: FSE: the table the format builds.

FSE (finite-state entropy) is ANS's table form: a distribution becomes
a table of states, the encoder walks states forward, the decoder walks
them back — and the table IS the format, transmitted as the counts it
normalizes. `fse_build_table` normalizes counts to the state count and
lays the table; `fse_encode` and `fse_decode` walk it — the stage's own
decoder, because FSE's decode is the format.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why is the decoder stage code rather than a reference?
Because FSE's decode is not a side of the format but the format itself:
the table the encoder walks is the table the decoder walks backwards,
and a reference decoder would be the same code twice. The check holds
the round-trip and the table's normalization — both halves.

DESIGN DECISION — why must the normalized counts sum exactly to the
state count?
Because the table's arithmetic — where each symbol's states sit — is
defined by that sum: a distribution that normalizes to more states than
the table holds is a table the decoder cannot walk. The check holds the
sum on every corpus.

DESIGN DECISION — why spread the states by the formula rather than
sort?
Because the spread is what makes the decoder's single table walk
possible: symbol states interleaved so the next state's low bits are
the next symbol's. Sorting would give a simpler table and a decoder
that cannot run backwards — the one property FSE exists for.
"""

def fse_build_table(counts, max_state):
    """The distribution normalized to the state count, the states spread."""
    raise NotImplementedError("stage 8: implement fse_build_table()")


def fse_encode(data, counts):
    """The states walked forward: (bytes, counts)."""
    raise NotImplementedError("stage 8: implement fse_encode()")


def fse_decode(data, counts, size):
    """The states walked back: the format's own decode."""
    raise NotImplementedError("stage 8: implement fse_decode()")
