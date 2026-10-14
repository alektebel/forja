"""Durable Execution From Scratch — stage 3: Replay, and the tail that was never finished

A run is not the process that started it; it is the log on disk. Stage 1 fixed
what a line *is*, and this stage is the only reader that log will ever have: the
text a disk holds becomes lines, the lines fold into a state table, and one
question tells a log that was finished from one whose last append never did.
Three functions, and the rule that decides them all — a state is a function of
the lines and nothing else, not of how many times they were read and not of the
process that wrote them.

    ReplayError  what a line this reader cannot believe raises
    replay       the lines a disk holds, parsed, in order
    state_of     the state table a replay yields, id-sorted and fresh
    torn         where a half-written tail sits, or None — a question, no repair

DESIGN DECISION — why is a torn tail refused by `replay` instead of dropped?
    Because a line is only a line once it is terminated. `write_line` owns the
    `"\\n"`, so a text whose last piece was never terminated holds half a
    record: it may even look complete, because a crash can land between a line's
    text and its terminator, and it is not a line either way. Dropping it
    silently is the failure this stage names — the reader would fold a log it
    quietly truncated and report a state built on a write that never finished.
    It is refused, naming its index and its text, and nothing is repaired: a
    reader that writes is not a reader.

DESIGN DECISION — why does `torn` take the journal's raw lines and not the
parsed ones?
    Because the question is about the terminator, and a parsed line has already
    forgotten it: every field bag a replay hands back belongs to a line that
    *was* finished. Where the unfinished tail sits is a property of the text, so
    `torn` reads the text — a str, or the pieces `split("\\n")` produced — and
    says which piece is the tail. A journal that ended with its terminator
    splits to a final empty piece, and a blank tail is not torn: it is what a
    finished journal looks like.

DESIGN DECISION — why does the newest claim decide a job's state instead of the
last line that names it?
    Because a state is a fold of *decisions*, and most lines are not decisions.
    A `beat` renames a deadline; an `intent` and an `effect` are about a key;
    none of them says who holds the job or how an attempt ended. The fold walks
    the lines in order and keeps the last decision per job: a `claim` makes it
    `running`, a `result` makes it `done` or `failed`, a `retry` re-issues it as
    `pending`. A reader that took the last line, or the first claim it saw,
    would answer about a beat instead of about the lease — the mistake this
    stage exists to catch.

DESIGN DECISION — why may an `expire` only end a running lease, and only its
own owner's?
    Because an expiry is the fingerprint of the owner that stopped answering,
    not a state anyone may assert. A job whose owner wrote its `result` is
    finished, and a later `expire` line cannot reach back past that; a `retry`
    has already re-issued the job, so the old owner's death is old news; and the
    owner has to match because the lease belongs to the line that took it.

TODO: implement `ReplayError`, `replay`, `state_of` and `torn`.
"""

from disk import DEFAULT_JOURNAL
from stage_01 import DurableError


class ReplayError(DurableError):
    """A line, a tail or a path a replay refuses.

    The refusal names the offender: the index of the line and its text, the
    path a disk refused, or the value a caller handed where a journal's lines
    belong.
    """


def replay(disk, path=DEFAULT_JOURNAL):
    """The lines the disk holds at `path`, parsed, in order.

    The text is split on the terminator `write_line` owns; a final non-empty
    piece is a tail that was never finished and is refused, naming its index and
    its text, and a line that does not parse is refused the same way.
    """
    raise NotImplementedError("stage 3: implement replay()")


def state_of(lines):
    """The state table a replay yields, id-sorted and fresh.

    Every job the lines name is in the table, and no job the log never named is
    invented into it; the newest decision about a job decides its status, and a
    `done`/`failed` state is a `{"status", "text"}` record only when the
    deciding result carried the worker's detail.
    """
    raise NotImplementedError("stage 3: implement state_of()")


def torn(lines):
    """Where a half-written tail sits in a journal's lines, or `None`.

    `lines` is a journal's text or the pieces it splits into; the answer is the
    index of the final piece when it was never terminated, counted from zero. It
    is a question: it reads and changes nothing.
    """
    raise NotImplementedError("stage 3: implement torn()")
