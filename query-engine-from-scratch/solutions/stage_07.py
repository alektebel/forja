"""The stage 7 solution: frames held, pins kept, the LRU that respects them."""

import disk as dk
import pages as pg
import tables as tb
import ops

BUFFER_KEYS = ("hits", "misses", "evictions", "dirty")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


class BufferPool:
    """frames pages, LRU over the unpinned, dirty pages written back."""

    def __init__(self, pager, frames):
        """The pool over a pager, holding at most `frames` pages."""
        if frames < 1:
            _refuse("no_frames", frames)
        self._pager = pager
        self._frames = frames
        self._pages = {}          # page -> bytes (the frame's contents)
        self._order = []          # unpinned pages, least-recently-used first
        self._pinned = set()
        self._dirty = set()
        self.record = {"hits": 0, "misses": 0, "evictions": 0, "dirty": 0}

    def fetch(self, page):
        """A page's bytes: a hit from the pool, a miss from the pager."""
        if page in self._pages:
            self.record["hits"] += 1
            if page not in self._pinned:
                self._order.remove(page)
                self._order.append(page)
            return self._pages[page]
        self.record["misses"] += 1
        data = self._pager.read(page)
        self._hold(page, data)
        return data

    def pin(self, page):
        """Pin a page: it will not be evicted while pinned."""
        self.fetch(page)
        if page in self._order:
            self._order.remove(page)
        self._pinned.add(page)

    def unpin(self, page, dirty=False):
        """Unpin a page; `dirty` marks the frame for write-back."""
        if page not in self._pinned:
            _refuse("not_pinned", page)
        self._pinned.discard(page)
        if dirty:
            self._dirty.add(page)
        self._order.append(page)

    def _hold(self, page, data):
        """Take a frame for the page, evicting the LRU unpinned if full."""
        while len(self._pages) >= self._frames and page not in self._pages:
            victim = None
            for candidate in list(self._order):
                if candidate not in self._pinned:
                    victim = candidate
                    break
            if victim is None:
                _refuse("all_pinned", self._frames)
            self._evict(victim)
        self._pages[page] = data
        if page not in self._pinned:
            self._order.append(page)

    def _evict(self, page):
        """Write back a dirty page, then forget it."""
        if page in self._dirty:
            self._pager.write(page, self._pages[page])
            self._dirty.discard(page)
            self.record["dirty"] += 1
        self.record["evictions"] += 1
        self._order.remove(page)
        del self._pages[page]


def run_buffered(plan, pager, frames):
    """A plan through the pool: the executor's keys plus the buffer's."""
    import stage_06
    pool = BufferPool(pager, frames)
    # the executor's pipeline runs with every page fetch through the pool:
    # wrap the pager so the executor's reads are pool reads
    class _Pooled:
        def __init__(self, pool):
            self._pool = pool
            self.disk = pager.disk

        def read(self, page):
            return self._pool.fetch(page)

        def write(self, page, data):
            pager.write(page, data)

        def sync(self):
            pager.sync()

        def allocate(self):
            return pager.allocate()
    buffered = _Pooled(pool)
    # the executor's scans read the world's pinned pages through the pool;
    # the plan's pages-read record is the executor's own arithmetic
    answer = stage_06.execute(plan, buffered)
    record = dict(answer)
    record.update(pool.record)
    return record
