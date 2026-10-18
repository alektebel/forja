"""Query Engine From Scratch — stage 8: The commit: a log, and a rule.

A transaction is words until the log holds it; the commit is the rule that
makes the words durable: append the commit record, **sync the log**, and only
then answer. `WAL.append` serializes one log record — xid, table, op, row,
the record format's own encoding — into a fresh log page and answers its LSN
(the page number and offset, packed, so a recovery can seek straight to it).
`WAL.commit` appends the commit record and answers its LSN. `commit(db, xid)`
is the whole stage in one call: the record's `durable` is the barrier's own
count, and a commit acknowledged before the barrier is a lie the crash
schedule catches in stage 9 — law 15, nothing uncommitted survives.

DESIGN DECISION — Why is the LSN a packed (page, offset) rather than a bare
counter?
Because a recovery has to *seek*: the LSN names the byte the record lives at,
and a counter would need the whole log walked to find anything. The packed
form is the address the record format already knows how to parse — and the
check holds it by reading the named bytes back and decoding the same record.

DESIGN DECISION — Why does `commit` sync the log rather than the pages?
Because the log is the promise: a synced log with unsynced pages recovers
(redo replays it), but synced pages with an unsynced log recover to a
half-transaction nobody announced. The rule is the log's, and stage 9's
crash fixtures hold it — the committed transaction survives the power fail,
the uncommitted one does not.

DESIGN DECISION — Why is `durable` the barrier's count rather than a boolean?
Because the count is what the device itself recorded — `disk.counters()`
says how many barriers ran — and a boolean would be the stage grading its
own homework. The check reads the device's counters beside the record; a
commit whose `durable` disagrees with the barrier count never happened.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

LOG_KEYS = ("lsn", "commit_lsn", "durable")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


class WAL:
    """The log on its own pages: append records, commit, answer LSNs.

    The log lives on the pages after the world's (`LOG_FIRST`, allocated
    fresh); each record is length-prefixed, the record format's own law, so
    a recovery walks records, not bytes."""

    def __init__(self, pager):
        """The log over one pager, its first page allocated."""
        raise NotImplementedError("stage 8: implement WAL.__init__()")

    def append(self, record):
        """One log record in, its LSN out.

        `record` is `(xid, table, op, row)`; the encoding is the record
        format's. Answers the LSN: `(page << 8) | offset`, packed."""

        raise NotImplementedError("stage 8: implement WAL.append()")

    def commit(self, xid):
        """The commit record in, its LSN out."""

        raise NotImplementedError("stage 8: implement WAL.commit()")

    def records(self):
        """Every record so far, walked from the log's first page."""

        raise NotImplementedError("stage 8: implement WAL.records()")


def commit(db, xid):
    """The rule: append the commit record, sync the log, answer.

    `db` is `(pager, wal)`; the record's `durable` is the barrier's own
    count. A commit acknowledged before the barrier is a lie."""

    raise NotImplementedError("stage 8: implement commit()")
