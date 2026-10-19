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
one direction it can be — write back what it was told changed — and the
crash stages will hold the truth of that claim against the log.

DESIGN DECISION — Why does `run_buffered` answer the buffer's record beside
the executor's rather than hiding it in counters?
Because the two records are the stage's argument: the executor's pages-read
claim and the buffer's hits/misses are checkable against each other and
against the disk's own counters — a pool that answers rows but loses its
record is a pool nobody can audit, and the check's central arithmetic (zero
evictions under the pool's size; one read under the pin) is an arithmetic
over that record.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

BUFFER_KEYS = ("hits", "misses", "evictions", "dirty")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


class BufferPool:
    """frames pages, LRU over the unpinned, dirty pages written back."""

    def __init__(self, pager, frames):
        """The pool over a pager, holding at most `frames` pages."""
        raise NotImplementedError("stage 7: implement BufferPool()")

    def fetch(self, page):
        """A page's bytes: a hit from the pool, a miss from the pager."""
        raise NotImplementedError("stage 7: implement BufferPool.fetch()")

    def pin(self, page):
        """Pin a page: it will not be evicted while pinned."""
        raise NotImplementedError("stage 7: implement BufferPool.pin()")

    def unpin(self, page, dirty=False):
        """Unpin a page; `dirty` marks the frame for write-back."""
        raise NotImplementedError("stage 7: implement BufferPool.unpin()")


def run_buffered(plan, pager, frames):
    """A plan through the pool: the executor's keys plus the buffer's.

    Answers EXEC_KEYS and BUFFER_KEYS — the rows by law 13, the pages, the
    operator chain, and the buffer's own record: hits, misses, evictions,
    dirty."""

    raise NotImplementedError("stage 7: implement run_buffered()")
