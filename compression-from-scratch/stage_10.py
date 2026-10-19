"""Compression From Scratch — stage 10: The proof: every codec, every corpus, one verdict.

Nine codecs built; the proof runs them all over one corpus and grades
the course the way the world does: the ratio against `BARS`, the
reference decoders' verdicts, the round-trips' exactness, and the
checksum's notice of the flipped bit. `prove` answers one corpus's
records; `audit` grades them all — `pass` only when everything holds,
and the reasons naming what did not.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why grade the ratio against the world's bars rather
than a self-chosen number?
Because a ratio without a bar is prose: the world's `BARS` are the
ceilings a codec must clear on a corpus it did not choose, and the
audit's verdict is data — `pass` or a reason — never a paragraph.

DESIGN DECISION — why must `audit` re-read the reference decoders'
verdicts rather than the stage's own round-trips?
Because the stage's own decoder agreeing with its own encoder is the
weakest evidence there is: the reference decoders are the course's
judges, and the audit holds their verdicts, not the student's.

DESIGN DECISION — why is the checksum's flipped bit part of the proof?
Because a frame that carries a checksum nobody has ever seen fire is a
frame whose integrity is a hope. The proof flips the bit and holds the
refusal — the one case that proves the checksum is a check.
"""

PROOF_KEYS = ("ratios", "verdicts", "round_trips")
AUDIT_KEYS = ("verdict", "reasons")


def prove(corpus_name):
    """Every codec over one corpus: the ratio, the verdict, the round-trip."""
    raise NotImplementedError("stage 10: implement prove()")


def audit(proofs):
    """The world's grade: pass, or the reasons naming what failed."""
    raise NotImplementedError("stage 10: implement audit()")
