"""The stage 8 solution: the log first, the barrier, then the answer."""

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


#: one log record's frame: a length byte, then the record's own bytes — the
#: same law the table pages keep (tables.page_rows reads this shape).
_LOG_META = 0


class WAL:
    """The log: one record per op, one commit record per transaction."""

    def __init__(self, pager):
        """The log over its own pager; page 0 is the log's meta page."""
        self._pager = pager
        self._page = _LOG_META + 1    # the log's first data page
        self._offset = 1              # past the count byte
        self._lsn = {}                # xid -> first record's LSN
        try:
            meta = self._pager.read(_LOG_META)
            first, at = self._read_varint(meta, 0)
            if first:
                self._page = first
                self._offset = self._tail(first)
            else:
                self._persist()
        except pg.PageError:
            self._persist()

    # --- the record format: length byte + record bytes, per page a count ---
    @staticmethod
    def _read_varint(data, at):
        value = 0
        while True:
            byte = data[at]
            value = (value << 7) | (byte & 0x7F)
            at += 1
            if not byte & 0x80:
                return value, at

    @staticmethod
    def _write_varint(value, out):
        while value >= 0x80:
            out.insert(0, 0x80 | (value & 0x7F))
            value >>= 7
        out.insert(0, value)

    def _tail(self, page):
        """Where the write cursor sits: past the last complete record."""
        raw = self._pager.read(page)
        at = 1
        for _ in range(raw[0]):
            rec_len = raw[at]
            at += 1 + rec_len
        return at

    def _persist(self):
        """The log's meta page: the first data page, packed.

        A page number is at most 127 — one varint byte, placed, not
        inserted."""
        meta = bytearray(pg.PAGE_SIZE)
        meta[0] = self._page
        self._pager.write(_LOG_META, bytes(meta))

    def append(self, record):
        """One log record in, its LSN out."""
        xid, table, op, payload = record
        if not isinstance(xid, int) or xid < 1:
            _refuse("no_xid", xid)
        body = pg.Pager.encode((xid, table, op) + tuple(payload or ()))
        if 1 + len(body) > pg.PAGE_SIZE - self._offset - 1 and self._offset:
            self._rotate()
        raw = bytearray(self._pager.read(self._page))
        raw[0] += 1
        raw[self._offset] = len(body)
        for i, byte in enumerate(body):
            raw[self._offset + 1 + i] = byte
        lsn = self._page * pg.PAGE_SIZE + self._offset
        if xid not in self._lsn:
            self._lsn[xid] = lsn
        self._offset += 1 + len(body)
        self._pager.write(self._page, bytes(raw))
        return lsn

    def _rotate(self):
        """A fresh page when the cursor's page cannot hold the record."""
        self._page = self._pager.allocate()
        self._offset = 1
        self._persist()

    def commit(self, xid):
        """The commit record in, its LSN out."""
        lsn = self.append((xid, "-", "commit", ()))
        return lsn


def commit(db, xid):
    """The rule: append the commit record, sync the log, then answer."""
    wal = db.get("wal") if isinstance(db, dict) else getattr(db, "wal", None)
    if not isinstance(wal, WAL):
        _refuse("no_wal", db)
    barriers = wal._pager.disk.counters()["barriers"]
    lsn = wal._lsn.get(xid)
    commit_lsn = wal.commit(xid)
    wal._pager.sync()
    durable = wal._pager.disk.counters()["barriers"]
    if durable <= barriers:
        _refuse("no_sync", xid)
    return {"lsn": lsn, "commit_lsn": commit_lsn, "durable": durable}
