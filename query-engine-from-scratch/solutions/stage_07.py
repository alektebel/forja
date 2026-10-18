"""The stage 7 solution: frames, pins, and the arithmetic of keeping."""

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
    """`frames` pages, LRU over the unpinned, the counter the check reads."""

    def __init__(self, pager, frames):
        self._pager = pager
        if frames < 1:
            _refuse("no_frames", frames)
        self._frames = frames
        self._pages = {}      # page -> bytes
        self._pinned = set()
        self._dirty = set()
        self._lru = []        # page ids, least-recent first
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def fetch(self, page):
        """A page's bytes: a hit from the pool, a miss from the pager."""
        if page in self._pages:
            self._hits += 1
            if page in self._lru:
                self._lru.remove(page)
            self._lru.append(page)
            return self._pages[page]
        if not 0 <= page < pg.PAGES:
            _refuse("no_page", page)
        self._misses += 1
        data = self._pager.read(page)
        while len(self._pages) >= self._frames:
            victim = next((p for p in self._lru if p not in self._pinned),
                          None)
            if victim is None:
                _refuse("all_pinned", self._frames)
            self._lru.remove(victim)
            victim_data = self._pages.pop(victim)
            self._evictions += 1
            if victim in self._dirty:
                self._pager.write(victim, victim_data)
                self._dirty.discard(victim)
        self._pages[page] = data
        self._lru.append(page)
        return data

    def pin(self, page):
        """Hold a frame: eviction skips it until it is unpinned."""
        if page not in self._pages:
            self.fetch(page)
        self._pinned.add(page)

    def unpin(self, page, dirty=False):
        """Release a frame; a dirty page is written back on eviction."""
        if page not in self._pinned:
            _refuse("not_pinned", page)
        self._pinned.discard(page)
        if dirty:
            self._dirty.add(page)

    def record(self):
        """BUFFER_KEYS: hits, misses, evictions, dirty count."""
        return {"hits": self._hits, "misses": self._misses,
                "evictions": self._evictions, "dirty": len(self._dirty)}


def run_buffered(pager, tree, plan_record, frames):
    """A plan through the pool: EXEC_KEYS plus BUFFER_KEYS.

    The pipeline is the executor's; the join streams the inner table
    through the pool with its pages pinned — the fixture that makes
    pinning real. Answers the executor's keys plus BUFFER_KEYS."""
    import stage_06 as s6

    pool = BufferPool(pager, frames)
    view = _PagedPager(pool)
    result = s6.execute(view, tree, plan_record)
    out = dict(result)
    out.update(pool.record())
    return out


class _PagedPager:
    """A pager-shaped view: reads through the pool, writes straight."""

    def __init__(self, pool):
        self._pool = pool
        self.disk = pool._pager.disk

    def read(self, page):
        return self._pool.fetch(page)

    def write(self, page, data):
        self._pool._pager.write(page, data)

    def sync(self):
        self._pool._pager.sync()

    def allocate(self):
        return self._pool._pager.allocate()

    def counters(self):
        return self._pool._pager.disk.counters()
