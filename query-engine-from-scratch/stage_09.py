"""Query Engine From Scratch — stage 9: The recovery: redo, undo, discard.

TODO: implement each function; the docstring is the contract.
The commit made a promise; the recovery is how the promise survives the
power cut. `recover` reads the durable log after a crash and answers
RECOVER_KEYS: the committed transactions — those with a durable commit
record —, the rolled-back ones (started, never committed), and the discarded
bytes: the torn tail, whose records are *never trusted*. `redo` replays the
committed transactions' operations against the tables; `undo` reverses the
uncommitted ones' — a transaction that wrote rows but never committed wrote
rows that must vanish. The record's `rows` is the recovered state, and the
world's `CRASH_SCHEDULE` pins what that must be: `clean` keeps everything,
`uncommitted-loss` loses t2's row, `many-uncommitted` keeps t1 and t4 and
loses t2 and t3.

`run_crash` runs one fixture end to end — the workload through a real WAL
(stage 8's), the crash through a real `power_fail` with or without a tear,
the recovery over the durable image — and the check holds each fixture's
answer against the fixture's own committed/uncommitted split. The torn-log
fixture is the one that separates a recovery from a replay: the torn record
is discarded, and a recovery that trusts bytes past the last complete record
resurrects a transaction that never was.

DESIGN DECISION — Why does `recover` classify *transactions* rather than
operations?
Because the unit of durability is the transaction: a commit record makes
every record before it durable, and its absence makes none of them count.
A recovery that classified operations would redo half of an uncommitted
write — worse than losing it, because the caller believed it.

DESIGN DECISION — Why does `undo` reverse operations rather than restore a
snapshot?
Because the log is the only witness: there is no snapshot to restore, and
the uncommitted operations are precisely enumerated — each insert undone by
removal, each update undone by its before-image. The record format's
update carries the old value for exactly this reason; the reversal is
arithmetic over the log, not a second copy of the world.

DESIGN DECISION — Why is a torn tail *discarded* rather than retried?
Because the torn bytes are the crash's own signature: a record whose length
byte says one thing and whose bytes say another is not a record the disk
owes anyone. Retrying would mean trusting bytes the barrier never made
durable — the exact lie law 15 exists to catch. The recovery keeps what the
log can prove and throws the rest away.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

RECOVER_KEYS = ("committed", "rolled_back", "discarded", "rows")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def recover(pager):
    """The durable log, classified: committed, rolled back, discarded.

    Reads every complete record off the log's pages; a transaction is
    committed when its durable commit record is present, rolled back when
    it started and never committed, and the torn tail — bytes the format
    refuses — is discarded, never trusted."""

    raise NotImplementedError("stage 9: implement recover()")


def redo(log, tables):
    """The committed operations, replayed against the tables.

    `log` is recover's classification; `tables` is the recovered state
    being built. Answers the tables the redo touched, with the committed
    operations' effects in log order."""

    raise NotImplementedError("stage 9: implement redo()")


def undo(log, tables, xids):
    """The uncommitted operations, reversed out of the tables.

    `xids` are the rolled-back transactions; answers the tables without
    their effects."""

    raise NotImplementedError("stage 9: implement undo()")


def run_crash(fixture):
    """One fixture end to end: workload, crash, recovery, rows.

    `fixture` is a `CRASH_SCHEDULE` entry. Runs the fixture's transactions
    through a real WAL (stage 8's), crashes the disk the way the fixture
    says (`power_fail(tear=fixture["tear"])`), recovers over the durable
    image, and answers RECOVER_KEYS."""

    raise NotImplementedError("stage 9: implement run_crash()")
