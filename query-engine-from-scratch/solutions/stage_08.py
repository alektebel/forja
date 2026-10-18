"""The stage 8 solution: the log, and the rule that makes it a promise."""

import disk as dk
import pages as pg
import tables as tb
import ops

LOG_KEYS = ("lsn", "commit_lsn", "durable")

#: the log's first page: the first one after the world's own.
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

    def append(self, record):
        """One log record in, its LSN out — (page << 8) | offset, packed."""
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
        return lsn

    def commit(self, xid):
        """The commit record in, its LSN out."""
        return self.append((xid, None, _COMMIT, ()))

    def records(self):
        """Every record so far, walked from the log's first page."""
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
            page += 1
        return out


def commit(db, xid):
    """The rule: append the commit record, sync the log, answer."""
    pager, wal = db
    commit_lsn = wal.commit(xid)
    pager.sync()
    return {"lsn": wal._first.get(xid), "commit_lsn": commit_lsn,
            "durable": pager.disk.counters()["barriers"]}
