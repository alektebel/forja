"""The pages: the heap file a pager keeps on the disk, and the record format
inside it.

A page is `PAGE_SIZE` bytes — exactly two sectors, so one page write is one
buffered sector pair and a torn page is a torn sector. The pager is *provided*:
it is the storage layer's honest floor, the part a query engine may assume, so
that the course's stages spend their ten steps on parsing, planning, indexing,
buffering, committing and recovering rather than on a second disk driver. What
the pager provides is deliberately narrow:

  * a page is bytes, and `Pager.read`/`Pager.write` are the only ways in —
    everything a stage builds (a B+tree, a WAL, a table scan) lives on these
    pages, addresses by page number, `0` reserved for the pager's own meta
    page;
  * a page write is buffered until `Pager.sync`, and `Pager.sync` is the only
    barrier. A stage that promises a fact without syncing has promised
    nothing, and the crash schedule will prove it;
  * the **record format** is fixed, because a format you can be exactly wrong
    about is the world's to decide: a record is a tuple of ints, serialized as
    one length byte, then per column one tag byte (`0` = NULL, `1` = int, with
    the value in the following bytes, big-endian, one byte per 7 bits — a
    varint), and the whole record must fit in a page. `encode`/`decode` are
    the format's law, and a check can hold any stage's bytes against them.

The page numbers a file uses are the world's to allocate: `Pager.allocate`
hands out the next free page and `Pager.free` returns one to the freelist
(a singly-linked chain of page numbers rooted in the meta page, `0`-terminated).
The freelist is small and the file is small — `PAGES` pages — so a wrong
freelist is visible before it is expensive.

Nothing here knows what a table, a row or a query is. `tables.py` decides that;
this module only promises that a page written and synced survives a crash.
"""

import disk as dk

PAGE_SIZE = dk.SECTOR * 2      # 256 bytes: a page is two sectors
PAGES = 128                    # the file's whole extent: 128 pages, 32 KiB
META_PAGE = 0                  # page 0: the pager's own (freelist head, next)
NULL = 0                       # a NULL page reference (a B+tree leaf's sibling)

TAG_NULL = 0
TAG_INT = 1
TAG_STR = 2


class PageError(ValueError):
    """Raised for anything the *caller* of the pager got wrong."""


class Pager:
    """The heap file: pages on a disk that loses what was not synced."""

    def __init__(self, disk=None):
        self.disk = disk if disk is not None else dk.Disk()
        if self.disk.sectors < PAGES * 2:
            raise PageError("the file needs %d sectors, the disk has %d"
                            % (PAGES * 2, self.disk.sectors))
        # the meta page: byte 0 is the freelist head (0 = none), byte 1 the
        # next never-allocated page number. It starts durable, written once,
        # because the world's own first barrier is not the course's business.
        self._shadow = {}            # the pager's own unsynced writes: what
        # this pager would read back before a barrier makes them durable
        meta = bytearray(PAGE_SIZE)
        meta[1] = 1                  # pages 1.. are free to allocate
        self.write(META_PAGE, bytes(meta))
        self.sync()

    # --- pages ---------------------------------------------------------------

    def read(self, page):
        """One whole page, as it is durable right now."""
        if not isinstance(page, int) or isinstance(page, bool):
            raise PageError("a page number is an int, not %r" % (page,))
        if not 0 <= page < PAGES:
            raise PageError("page %r is outside this file (0..%d)"
                            % (page, PAGES - 1))
        if page in self._shadow:
            return self._shadow[page]
        raw = self.disk.read(page * 2) + self.disk.read(page * 2 + 1)
        return raw

    def write(self, page, data):
        """Buffer one whole page. Nothing is durable until `sync`."""
        if not isinstance(page, int) or isinstance(page, bool):
            raise PageError("a page number is an int, not %r" % (page,))
        if not 0 <= page < PAGES:
            raise PageError("page %r is outside this file (0..%d)"
                            % (page, PAGES - 1))
        data = bytes(data)
        if len(data) != PAGE_SIZE:
            raise PageError("a page write is %d bytes, not %d"
                            % (PAGE_SIZE, len(data)))
        self._shadow[page] = data
        self.disk.write(page * 2, data[:dk.SECTOR])
        self.disk.write(page * 2 + 1, data[dk.SECTOR:])
        return page

    def sync(self):
        """The one barrier: every buffered page write becomes a fact. The
        shadow empties — from here the durable image and the pager agree."""
        self._shadow = {}
        return self.disk.barrier()

    # --- allocation ----------------------------------------------------------

    def allocate(self):
        """The next page number, freelist first, refusing a full file."""
        head = self.read(META_PAGE)[0]
        if head != 0:
            freed = self.read(head)[0]
            meta = bytearray(self.read(META_PAGE))
            meta[0] = freed
            self.write(META_PAGE, bytes(meta))
            return head
        nxt = self.read(META_PAGE)[1]
        if nxt >= PAGES:
            raise PageError("the file is full (%d pages)" % (PAGES,))
        meta = bytearray(self.read(META_PAGE))
        meta[1] = nxt + 1
        self.write(META_PAGE, bytes(meta))
        return nxt

    def free(self, page):
        """Return a page to the freelist: it becomes the new head."""
        if not isinstance(page, int) or isinstance(page, bool) \
                or not 1 <= page < PAGES:
            raise PageError("a freed page is 1..%d, not %r" % (PAGES - 1, page))
        node = bytearray(PAGE_SIZE)
        node[0] = self.read(META_PAGE)[0]
        self.write(page, bytes(node))
        meta = bytearray(self.read(META_PAGE))
        meta[0] = page
        self.write(META_PAGE, bytes(meta))
        return page

    # --- the record format ---------------------------------------------------

    @staticmethod
    def encode(record):
        """A record is a tuple of ints (or None for NULL), serialized:
        one length byte, then per column a tag byte and a varint value."""
        if not isinstance(record, tuple):
            raise PageError("a record is a tuple, not %r" % (type(record).__name__,))
        out = bytearray([len(record)])
        for column in record:
            if column is None:
                out.append(TAG_NULL)
                continue
            if isinstance(column, str):
                out.append(TAG_STR)
                raw_col = column.encode("ascii")
                if not 1 <= len(raw_col) <= 63:
                    raise PageError("a string column is 1..63 bytes, not %d"
                                    % (len(raw_col),))
                out.append(len(raw_col))
                out.extend(raw_col)
                continue
            if not isinstance(column, int) or isinstance(column, bool):
                raise PageError("a column is an int, a short string or None, "
                                "not %r" % (column,))
            out.append(TAG_INT)
            if column < 0:
                raise PageError("the record format carries non-negative ints; "
                                "%d has no encoding" % (column,))
            value = column
            while True:
                byte = value & 0x7F
                value >>= 7
                if value:
                    byte |= 0x80
                out.append(byte)
                if not value:
                    break
        raw = bytes(out)
        if len(raw) > PAGE_SIZE:
            raise PageError("a record of %d bytes does not fit a page of %d"
                            % (len(raw), PAGE_SIZE))
        return raw

    @staticmethod
    def decode(raw):
        """The record format's other half: bytes in, the tuple out."""
        if len(raw) < 1:
            raise PageError("a record is at least one byte")
        count = raw[0]
        columns = []
        at = 1
        for _ in range(count):
            if at >= len(raw):
                raise PageError("a record ended mid-column")
            tag = raw[at]
            at += 1
            if tag == TAG_NULL:
                columns.append(None)
                continue
            if tag == TAG_STR:
                length = raw[at]
                at += 1
                if length > 63 or at + length > len(raw):
                    raise PageError("a string column ended mid-bytes")
                columns.append(raw[at:at + length].decode("ascii"))
                at += length
                continue
            if tag != TAG_INT:
                raise PageError("unknown column tag %d" % (tag,))
            value = 0
            shift = 0
            while True:
                if at >= len(raw):
                    raise PageError("a varint ended mid-byte")
                byte = raw[at]
                at += 1
                value |= (byte & 0x7F) << shift
                shift += 7
                if not byte & 0x80:
                    break
            columns.append(value)
        return tuple(columns)
