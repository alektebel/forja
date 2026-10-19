"""Query Engine From Scratch — stage 8: The commit: a log, and a rule.

TODO: implement each function; the docstring is the contract.
A commit is not a function call; it is a *promise about bytes on disk*: when
`commit` answers, the transaction's records are in a log that a power cut
cannot unwrite. The write-ahead log is the promise's paper: `WAL.append`
serializes one log record — the xid, the table, the op, the row, in the
record format's own encoding — into a fresh log page and answers its LSN,
the page-and-offset address the record lives at. `WAL.commit` appends the
commit record and answers its LSN. `commit(db, xid)` is the rule the whole
stage exists for: append the commit record, **sync the log**, and only then
answer — the record's `durable` is the barrier's own count, and a commit
acknowledged before the barrier is a lie the crash schedule catches in
stage 9.

DESIGN DECISION — Why is the LSN a packed page-and-offset rather than a
running number?
Because the LSN's job is to *address a byte*: stage 9's recovery reads the
log from a LSN, and a torn tail is defined as "bytes past the last complete
record" — an address arithmetic, not a counter. A running LSN would force
the recovery to re-derive every record's position; the packed LSN carries
it.

DESIGN DECISION — Why does `commit` answer `durable` as the barrier count
rather than a boolean?
Because the barrier is the disk's own record of what became durable, and a
count is auditable: the check reads `disk.counters()` before and after and
holds the commit's claim against the device's. A boolean says "I synced";
the count says *when* — and law 15's arithmetic (nothing uncommitted
survives a crash) is stated in barriers, the currency the disk deals in.

DESIGN DECISION — Why does the WAL live on its own pages rather than
alongside the table's?
Because the log is written *before* the data it describes — that is the
W in WAL — and a log page allocated beside the tables would be a page the
pager's freelist could hand to a table mid-run. The check builds the WAL on
a fresh pager; stage 9's recovery rebuilds it the same way, and the crash
schedule tears *this* disk, not the world's.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

LOG_KEYS = ("lsn", "commit_lsn", "durable")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


class WAL:
    """The log: one record per op, one commit record per transaction."""

    def __init__(self, pager):
        """The log over its own pager; page 0 is the log's meta page."""
        raise NotImplementedError("stage 8: implement WAL()")

    def append(self, record):
        """One log record in, its LSN out.

        `record` is (xid, table, op, payload) — the payload the record
        format encodes. The LSN is the page-and-offset the record's bytes
        start at, packed as one int."""

        raise NotImplementedError("stage 8: implement WAL.append()")

    def commit(self, xid):
        """The commit record in, its LSN out."""
        raise NotImplementedError("stage 8: implement WAL.commit()")


def commit(db, xid):
    """The rule: append the commit record, sync the log, then answer.

    `db` is the store the WAL belongs to — anything carrying `wal`. Answers
    LOG_KEYS: the transaction's first LSN, the commit record's LSN, and the
    disk's barrier count after the sync."""

    raise NotImplementedError("stage 8: implement commit()")
