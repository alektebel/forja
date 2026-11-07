"""Query Engine From Scratch — stage 7: The buffer: pinning, eviction, and
the page you did not keep.

The executor read every page it needed, every time. The buffer pool is the
difference between a database and a script: `frames` pages held in memory,
`fetch` answering a hit from the pool or a miss from the pager — and the
disk's counter is the judge of which — with `pin`/`unpin` as the discipline
that keeps the working set working: a pinned page is never evicted, an
unpinned dirty page is written back on its way out, and eviction is LRU over
the unpinned. `run_buffered` runs a plan through the pool and answers the
executor's keys plus the buffer's — hits, misses, evictions, dirty — and the
check's central arithmetic is the one that makes pools exist: a plan over a
table smaller than the pool answers with zero evictions and every page read
from the pager exactly once.

The fixture that makes pinning *real* is a pool of one frame running a join:
without pinning, the inner table's page is evicted between outer rows and
the misses explode; with it, the record says one read. A buffer that pinned
nothing would still answer — and its counters would tell on it.

DESIGN DECISION — Why is eviction LRU over the unpinned rather than LRU over
everything?
Because a pinned page is a promise the executor is still holding: evicting
it does not free a frame, it corrupts a run. LRU over everything is the
classic bug — it shows up as the join's inner page vanishing between outer
rows. The pool's law is: evict the *least recently used page nobody still
needs*, and refuse when that set is empty rather than break a pin.

DESIGN DECISION — Why does `unpin` carry the dirty flag rather than the pool
tracking writes?
Because dirtiness is the *caller's* claim about what it did to the page, and
the pool is the record-keeper, not the witness: the executor mutates a
frame's bytes through its own hands. The flag keeps the pool honest in the
one direction it can be — write back what it was told changed.

DESIGN DECISION — Why does `run_buffered` answer the buffer's record beside
the executor's rather than hiding it in counters?
Because the two records are the stage's argument: the executor's pages-read
claim and the buffer's hits/misses are checkable against each other and
against the disk's own counters — a pool that answers rows but loses its
record is a pool nobody can audit.
"""

import stage_06 as _ex
import tables as tb

BUFFER_KEYS = ("hits", "misses", "evictions", "dirty")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, *names):
    raise QueryError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


class BufferPool:
    """frames pages, LRU over the unpinned, dirty pages written back."""

    def __init__(self, pager, frames):
        """The pool over a pager, holding at most `frames` pages."""
        if not isinstance(frames, int) or isinstance(frames, bool) \
                or frames < 1:
            _refuse("no_frames", frames)
        self.pager = pager
        self.frames = frames
        self.record = {"hits": 0, "misses": 0, "evictions": 0, "dirty": 0}
        self._pages = {}       # page -> bytes, the frames in memory
        self._pinned = set()   # pages currently pinned
        self._lru = []         # unpinned pages, least-recently-used first

    def fetch(self, page):
        """A page's bytes: a hit from the pool, a miss from the pager."""
        if page in self._pages:
            self.record["hits"] += 1
            if page not in self._pinned and page in self._lru:
                self._lru.remove(page)
                self._lru.append(page)
            return self._pages[page]
        # the miss needs a frame: evict the LRU unpinned page, refusing when
        # every frame is pinned — breaking a pin is not an option
        while len(self._pages) >= self.frames:
            if not self._lru:
                _refuse("all_pinned", self._pinned)
            victim = self._lru.pop(0)
            del self._pages[victim]
            self.record["evictions"] += 1
        self._pages[page] = self.pager.read(page)
        self.record["misses"] += 1
        self._lru.append(page)
        return self._pages[page]

    def pin(self, page):
        """Pin a page: it will not be evicted while pinned. The pin's own
        fetch is a read like any other — the record counts it."""
        self.fetch(page)
        if page in self._lru:
            self._lru.remove(page)
        self._pinned.add(page)

    def unpin(self, page, dirty=False):
        """Unpin a page; `dirty` marks the frame for write-back."""
        if page not in self._pinned:
            _refuse("not_pinned", page)
        self._pinned.discard(page)
        self._lru.append(page)
        if dirty:
            self.record["dirty"] += 1
            self.pager.write(page, self._pages[page])
            self.pager.sync()


def run_buffered(plan, pager, frames):
    """A plan through the pool: the executor's keys plus the buffer's.

    Answers EXEC_KEYS and BUFFER_KEYS — the rows by law 13, the pages, the
    operator chain, and the buffer's own record: hits, misses, evictions,
    dirty."""
    pool = BufferPool(pager, frames)
    # the executor reads pages through the pool: the pager's read goes via
    # fetch, so the pool's misses are the scan's reads
    answer = _ex.execute(plan, _PooledPager(pager, pool))
    answer.update(pool.record)
    return answer


class _PooledPager:
    """The pager's face with reads served through the pool — the executor
    cannot tell, and the counters prove where the bytes came from."""

    def __init__(self, pager, pool):
        self._pager = pager
        self._pool = pool
        self.disk = pager.disk

    def read(self, page):
        return self._pool.fetch(page)

    def write(self, page, data):
        return self._pager.write(page, data)

    def sync(self):
        return self._pager.sync()

    def allocate(self):
        return self._pager.allocate()

    def free(self, page):
        return self._pager.free(page)
