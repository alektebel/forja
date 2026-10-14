"""stage_02.py — the write that was not synced did not happen.

Durable Execution From Scratch — stage 2: The write that was not synced did not happen

Stage 1 fixed what a line of the journal *is*. This stage fixes which lines the
course is allowed to believe. A line handed to `append` is a *prediction*: this
program can read it back, and a crash throws it away. A line handed to `commit`
is a *fact*: written, then synced, so the process that comes after the crash
finds it. `lost` says what a crash at this moment would cost — a question, not a
kill — and `survives` says whether a given line is already a fact.

    append    write a line to the world's journal, and do not sync it
    commit    write the line and SYNC it — the only door the course believes
    lost      what a crash would discard right now, without crashing
    survives  is that line already durable? (a whole-line question)

DESIGN DECISION — why two functions, `append` and `commit`, instead of one write
with a `sync=True` flag? Because a flag is a place to hide the decision, and this
decision is the course. `commit(disk, entry)` reads as "make this a fact" and
`append(disk, entry)` reads as "predict this", at every call site, with no
keyword to forget and no default to misread; a journal whose reader cannot tell
which lines were synced is exactly the run this course refuses.

DESIGN DECISION — why does `lost` derive the tail from `read` and `synced`
instead of calling `disk.crash()`? Because a crash is a kill and a question is
not: a caller asks what a crash would cost *in order to decide*, and a `lost`
that crashed the disk it was asked about would leave the caller holding a journal
it did not choose to abandon. `lost` is a reading — for every path the disk
reports as volatile, the text the program can see beyond what a crash would keep
— and it equals `disk.crash()` on the append-only journal this course writes,
which is why a check can assert the two against each other.

DESIGN DECISION — why is `survives` a whole-line question and not a search for
the text? Because `text in disk.synced(...)` makes every *prefix* of a durable
line durable: `survives(disk, "3 claim")` would answer True, and a replay that
believed it would report a claim line nobody wrote — an owner and a deadline
invented by a substring match. The synced text is split into the lines it
actually finished (each followed by its terminator) and the text must be one of
them. A trailing line that never got a terminator is not a line yet: that tail is
stage 3's `torn`, and answering True for it would hand recovery half a line and
call it durable.

DESIGN DECISION — why does `commit` refuse before it syncs? Because a refusal
must not make anything durable. `commit` writes through `append`, which writes
through stage 1's `write_line`, so a broken entry is refused before a byte is
staged — and, the sync happening after, a call that failed cannot flush whatever
the previous call left pending. A `commit` that synced first, or in a `finally`,
would turn a typo in one entry into a durability decision about another, and the
caller would learn about it a stage later.

DESIGN DECISION — why may the text handed to `survives` carry its terminator?
Because a line's terminator belongs to the journal, not to the record: stage 1's
`write_line` appends `text + "\\n"`, so a caller holding the bytes it appended
holds the same line. One trailing terminator is the same line spelled with its
journal's punctuation; anything more is a text that spans lines, and the
comparison stays by line.

TODO: implement `append`, `commit`, `lost` and `survives`.
"""

from disk import DEFAULT_JOURNAL, Disk
from stage_01 import JournalError, write_line


def _world(disk):
    """The world's disk, or a refusal naming what was handed instead.

    Every function here reads or writes a disk; handing a stage something else
    is a mistake that must surface where it was made, with the object itself in
    the message, instead of as an `AttributeError` three calls further down.
    """
    if not isinstance(disk, Disk):
        raise JournalError(
            "a stage reads and writes the world's Disk, got %r" % (disk,))
    return disk


def append(disk, entry):
    """Append one line to the world's journal, and sync nothing.

    `entry` is stage 1's journal entry: a broken one is refused there, naming
    the offender, before a byte is written. The journal's new length is
    returned — the length `read` reports, which is *not* the length a crash
    would keep.
    """
    return write_line(_world(disk), entry)


def commit(disk, entry):
    """Append one line to the world's journal and SYNC it: the door the course
    believes.

    Returns the journal's new length. Everything the disk was holding becomes
    durable here and not only this line, because a sync is a barrier: a caller
    that appended a line and then committed another has made both facts.
    """
    length = append(disk, entry)
    disk.sync()
    return length


def lost(disk):
    """What a crash at this moment would discard, without crashing.

    The same tuple `disk.crash()` returns — `((path, text), ...)`, path by path
    in sorted order, a path with nothing to lose left out — computed as a
    reading: for every path the disk reports as volatile, the text the program
    can see beyond what a crash would keep. On the append-only journal this
    stage writes that is exactly the unsynced tail; a staged rewrite (stage 8's
    checkpoint) was never durable, so all of it is lost.
    """
    _world(disk)
    discarded = []
    for path in disk.volatile():
        durable = disk.synced(path)
        visible = disk.read(path)
        text = visible[len(durable):] if visible.startswith(durable) else visible
        if text:
            discarded.append((path, text))
    return tuple(discarded)


def _kept(text):
    """The lines `text` finished: every piece before a terminator.

    `"a\\nb\\n"` is two lines, `"a\\nb"` is one and a torn tail (the tail never
    got its terminator — stage 3's `torn`), and `""` is none. One split and one
    drop say all three, because the last piece is either the empty string that
    follows a terminator or the tail that never got one.
    """
    return tuple(text.split("\n")[:-1])


def survives(disk, text):
    """Is `text` already durable — a fact a crash would keep?

    `text` is a line's text (stage 1's `line()`), with or without the terminator
    the journal adds, and it must be one of the lines the *synced* journal
    finished: a whole-line question, not a substring search. A blank text is not
    a line's text and is refused naming it, because answering False would claim
    there is such a line and it is not durable.
    """
    _world(disk)
    if not isinstance(text, str) or not text.strip():
        raise JournalError(
            "the text to look for must be a non-empty str, got %r" % (text,))
    if text.endswith("\n"):
        text = text[:-1]
    return text in _kept(disk.synced(DEFAULT_JOURNAL))
