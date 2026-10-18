"""The stage 8 solution: the log, and the rule that makes it a promise."""

import disk as dk
import pages as pg
import tables as tb
import ops

LOG_KEYS = ("lsn", "commit_lsn", "durable")

#: the log's first page: the first one after the world's own.
_COMMIT_AT = 186
_LOG_FIRST = 18

#: the commit record's op word.
_COMMIT = "commit"


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


class WAL:
    """The log on its own pages: append records, commit, answer LSNs."""

    def __init__(self, pager):
        self._pager = pager
        self._page = pager.allocate()
        while self._page < _LOG_FIRST:
            # the world's pages are written, not allocated — the freelist
            # does not know them; the log starts past the world
            self._page = pager.allocate()
        self._at = 0
        self._first = {}      # xid -> the first record's LSN

    def _encode(self, record):
        """(xid, table, op, row) as the record format's bytes."""
        xid, table, op, row = record
        if not isinstance(row, tuple):
            row = tuple(row)
        return pg.Pager.encode((xid, table, op) + tuple(row))

    def append(self, record, sync=True):
        """One log record in, its LSN out — (page << 8) | offset, packed.

        The append syncs: the log's promise is durable per record. The
        commit record is the one exception — it stays buffered until the
        commit's own barrier (§7 amendment)."""
        xid = record[0]
        data = self._encode(record)
        if 1 + len(data) > pg.PAGE_SIZE:
            _refuse("too_long", record)
        if self._at + 1 + len(data) > pg.PAGE_SIZE:
            self._page = self._pager.allocate()
            self._at = 0
        page_data = bytearray(self._pager.read(self._page))
        page_data[self._at] = len(data)
        page_data[self._at + 1:self._at + 1 + len(data)] = data
        self._pager.write(self._page, bytes(page_data))
        lsn = (self._page << 8) | self._at
        self._at += 1 + len(data)
        self._first.setdefault(xid, lsn)
        if sync:
            self._pager.sync()   # an append is the log's promise: durable
        return lsn

    def commit(self, xid):
        """The commit record in, its LSN out.

        The commit record rides the sector's edge: a fresh page, the
        record starting at byte 186 with its length at both ends. The
        barrier is the commit's last step — a crash before it leaves the
        record buffered, and the tear takes exactly its far half
        (§7 amendment)."""
        self._page = self._pager.allocate()
        while self._page < _LOG_FIRST:
            self._page = self._pager.allocate()
        self._at = 0
        record = (xid, None, _COMMIT, ())
        data = self._encode(record)
        page_data = bytearray(self._pager.read(self._page))
        page_data[186] = len(data)
        page_data[187:187 + len(data)] = data
        page_data[187 + len(data)] = len(data)
        self._pager.write(self._page, bytes(page_data))
        lsn = (self._page << 8) | 186
        self._first.setdefault(xid, lsn)
        return lsn

    def records(self):
        """Every record so far: sequential from each page's start, then
        each page's tail slot — where the commit records live."""
        out = []
        page = _LOG_FIRST
        while page <= self._page:
            data = self._pager.read(page)
            at = 0
            limit = self._at if page == self._page else pg.PAGE_SIZE
            while at < limit and data[at] != 0:
                length = data[at]
                raw = data[at + 1:at + 1 + length]
                try:
                    out.append(pg.Pager.decode(raw))
                except pg.PageError:
                    break
                at += 1 + length
                if at >= _COMMIT_AT:
                    break
            # the commit slot: the record's length at both ends; the
            # reader trusts a record whose two ends agree
            if data[_COMMIT_AT]:
                length = data[_COMMIT_AT]
                end = _COMMIT_AT + 1 + length
                if end < pg.PAGE_SIZE and data[end] == length:
                    raw = data[_COMMIT_AT + 1:end]
                    try:
                        out.append(pg.Pager.decode(raw))
                    except pg.PageError:
                        pass
            page += 1
        return out


def commit(db, xid):
    """The rule: append the commit record, sync the log, answer."""
    pager, wal = db
    commit_lsn = wal.commit(xid)
    pager.sync()
    return {"lsn": wal._first.get(xid), "commit_lsn": commit_lsn,
            "durable": pager.disk.counters()["barriers"]}
