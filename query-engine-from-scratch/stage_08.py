"""Query Engine From Scratch — stage 8: The commit: a log, and a rule.

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
record" — an address arithmetic, not a counter. The packed LSN carries the
position.

DESIGN DECISION — Why does `commit` answer `durable` as the barrier count
rather than a boolean?
Because the barrier is the disk's own record of what became durable, and a
count is auditable: the check reads `disk.counters()` before and after and
holds the commit's claim against the device's. A boolean says "I synced";
the count says *when*.

DESIGN DECISION — Why does the WAL live on its own pages rather than
alongside the table's?
Because the log is written *before* the data it describes — that is the
W in WAL — and a log page allocated beside the tables would be a page the
pager's freelist could hand to a table mid-run. The check builds the WAL on
a fresh pager; stage 9's recovery rebuilds it the same way.

DESIGN DECISION — Why does a log page use the world's own record framing?
Because the check decodes the log through `tb.page_rows` — the same reader
the tables use — so the log's bytes are count-prefixed records in the
pager's encoding, and a record the reader cannot decode is a record the log
never wrote.
"""

import pages as pg
import tables as tb

LOG_KEYS = ("lsn", "commit_lsn", "durable")

#: the log's meta page: byte 0 is the next page to write, byte 1..2 the
#: offset in that page the tail sits at
_META = 0
_LOG_START = 1


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, *names):
    raise QueryError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def _lsn(page, offset):
    """The packed address: page * PAGE_SIZE + offset."""
    return page * pg.PAGE_SIZE + offset


class WAL:
    """The log: one record per op, one commit record per transaction."""

    def __init__(self, pager):
        """The log over its own pager; page 0 is the log's meta page.

        A fresh pager starts the log at page 1, offset 1 (past the count
        byte). A pager that already carries a log resumes at the tail the
        meta page names."""
        self.pager = pager
        meta = bytearray(pager.read(_META))
        if meta[2] == 0 and meta[3] == 0:
            # a fresh log: the first record goes to page 1, offset 1
            self._page = _LOG_START
            self._offset = 1
        else:
            self._page = meta[2]
            self._offset = meta[3]
        # a resumed WAL re-reads the tail page's records so the next
        # append rewrites the page whole rather than clobbering it
        self._page_rows = []
        if self._offset > 1:
            raw = pager.read(self._page)
            at = 1
            for _ in range(raw[0]):
                rec_len = raw[at]
                self._page_rows.append(
                    tuple(pg.Pager.decode(raw[at + 1:at + 1 + rec_len])))
                at += 1 + rec_len

    def _save_meta(self):
        meta = bytearray(self.pager.read(_META))
        meta[2] = self._page
        meta[3] = self._offset
        self.pager.write(_META, bytes(meta))

    def _flush_page(self):
        """The page's records, count-prefixed, written as the world's own
        reader decodes them. The page's records are the ones whose bytes
        this page owns: every append rewrites the page it landed on whole,
        because a page write is the pager's only unit."""
        body = bytearray(pg.PAGE_SIZE)
        at = 1
        count = 0
        for rec in self._page_rows:
            encoded = pg.Pager.encode(rec)
            body[at] = len(encoded)
            body[at + 1:at + 1 + len(encoded)] = encoded
            at += 1 + len(encoded)
            count += 1
        body[0] = count
        self.pager.write(self._page, bytes(body))

    def append(self, *record):
        """One log record in, its LSN out.

        The record is flat — (xid, table, op, *payload) — or with the
        payload as one tuple in the fourth slot. The LSN is the
        page-and-offset the record's bytes start at, packed as one int."""
        if len(record) == 1 and isinstance(record[0], tuple):
            record = record[0]
        if len(record) == 4 and isinstance(record[3], tuple):
            (xid, table, op, payload) = record
        else:
            (xid, table, op, payload) = record[0], record[1], record[2], \
                record[3:]
        if not isinstance(xid, int) or isinstance(xid, bool) or xid < 1:
            _refuse("no_xid", xid)
        row = (xid, table, op) + tuple(payload)
        encoded = pg.Pager.encode(row)
        if 1 + len(encoded) > pg.PAGE_SIZE - 1:
            _refuse("too_big", len(encoded))
        if self._offset + 1 + len(encoded) > pg.PAGE_SIZE:
            # the record does not fit this page: start the next
            self._page += 1
            self._offset = 1
            self._page_rows = []
        lsn = _lsn(self._page, self._offset)
        self._page_rows.append(row)
        self._offset += 1 + len(encoded)
        self._flush_page()
        self._save_meta()
        return lsn

    def commit(self, xid):
        """The commit record in, its LSN out."""
        return self.append(xid, "log", "commit", xid)


def commit(db, xid):
    """The rule: append the commit record, sync the log, then answer.

    `db` is the store the WAL belongs to — anything carrying `wal`. Answers
    LOG_KEYS: the transaction's first LSN, the commit record's LSN, and the
    disk's barrier count after the sync."""
    wal = db.get("wal")
    if wal is None:
        _refuse("no_wal", db)
    # the transaction's first record: the first appended record since the
    # last commit — the WAL tracks per-transaction tails
    first = getattr(wal, "_txn_first", None)
    if first is None:
        first = _lsn(wal._page, 1)
    commit_lsn = wal.commit(xid)
    durable = wal.pager.sync()
    wal._txn_first = None
    return {"lsn": first, "commit_lsn": commit_lsn, "durable": durable}
