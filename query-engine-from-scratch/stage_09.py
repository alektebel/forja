"""Query Engine From Scratch — stage 9: The recovery: redo, undo, discard.


TODO: implement each function; the docstring is the contract.
The commit stage made the log a promise; the recovery is where the promise is
kept. `recover` reads the durable log after a crash and answers three lists:
the committed transactions (those whose commit record is durable), the
rolled-back ones (started, never committed — their work is undone), and the
discarded bytes (the torn tail — a record half-written by the power fail is
discarded, never trusted). `redo` replays the committed transactions'
operations against the tables; `undo` reverses the uncommitted ones'. The
record's `rows` is the recovered state, and the world's `CRASH_SCHEDULE` pins
what that must be — four fixtures, one with a torn log, each with its own
committed/uncommitted split.

`run_crash` runs one fixture end to end: the workload appended to the log,
the crash (`power_fail(tear=fixture["tear"])`), the recovery, the recovered
rows — and the check holds each fixture's answer against the fixture's own
split. The discipline is law 15: nothing uncommitted survives a crash, and
nothing committed is lost to one.

DESIGN DECISION — Why does `recover` answer lists rather than replaying
itself?
Because the decision and the mechanics are different failures: a recovery
that misclassifies a transaction (committed vs rolled-back) is wrong even if
its replay is flawless, and a check that cannot see the classification can
only test the aggregate. The lists are the diagnosis; `redo`/`undo` are the
mechanics; the check holds both.

DESIGN DECISION — Why is a torn record discarded rather than reconstructed?
Because reconstruction is guessing: a half-record's first bytes are real, but
the tail is whatever the power fail left, and a recovery that trusts a torn
tail resurrects a transaction that never was. The discarded count is the
answer's honesty — the `torn-log` fixture's record says one record lost, and
trusting it fails the check by design.

DESIGN DECISION — Why does `run_crash` take the fixture rather than a
fixture index?
Because the fixture is data — the world's own record of a crash — and an
index would make the recovery consult the world's order instead of its
content. The fixture carries its workload, its tear flag, its split; the
recovery reads the log, not the fixture, and the check holds the two
against each other.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

RECOVER_KEYS = ("committed", "rolled_back", "discarded", "rows")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def recover(pager):
    """The durable log after a crash, classified.

    Answers RECOVER_KEYS: `committed` (xids with a durable commit record),
    `rolled_back` (started, never committed), `discarded` (the torn
    records' count), and `rows` — the tables as the log recovers them."""

    raise NotImplementedError("stage 9: implement recover()")


def redo(log, tables):
    """The committed transactions' operations, replayed in order.

    `log` is the decoded record list; `tables` is the name -> rows dict
    replayed against. Answers the tables after the replay."""

    raise NotImplementedError("stage 9: implement redo()")


def undo(log, tables, xids):
    """The uncommitted transactions' operations, reversed.

    Answers the tables after the reversal — the work those xids did is
    gone."""

    raise NotImplementedError("stage 9: implement undo()")


def run_crash(fixture):
    """One fixture end to end: workload, crash, recovery, rows.

    Runs the fixture's transactions through a WAL, crashes the disk
    (`power_fail(tear=fixture["tear"])`), recovers, and answers
    RECOVER_KEYS for the fixture."""

    raise NotImplementedError("stage 9: implement run_crash()")
