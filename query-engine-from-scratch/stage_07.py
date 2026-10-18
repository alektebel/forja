"""Query Engine From Scratch — stage 7: The buffer: pinning, eviction, and
the page you did not keep.

The executor read every page through the pager; the buffer pool is the layer
that decides which pages are worth keeping. `BufferPool` holds `frames`
pages: `fetch` answers a page's bytes — a hit from the pool, a miss from the
pager (and the disk's counter moves, which is how the check counts) — and
`pin`/`unpin` are the discipline: a pinned page is never evicted, an unpinned
dirty page is written back, and eviction is LRU over the unpinned. The
arithmetic the check lives on: a plan over a table smaller than the pool
answers with zero evictions and every page read exactly once; a pool of one
frame running a join is the fixture that makes pinning *real* — without it
the inner table's page is evicted between outer rows and the misses explode,
with it the record says one read.

DESIGN DECISION — Why is `run_buffered` a stage way in rather than wrapping
the executor by hand?
Because the buffer's record is the stage's answer, not a side effect the
caller reassembles: EXEC_KEYS plus BUFFER_KEYS from one call, so the check's
arithmetic (zero evictions below capacity, one read pinned) is held against
the same record the proof will see. An executor wrapped ad hoc would let the
hit/miss counters and the actual page traffic drift apart.

DESIGN DECISION — Why does `unpin` carry the dirty flag rather than the pool
tracking writes?
Because dirtiness is a property of how the page was *used*, and the user of
the frame knows; a pool that guessed would write back pages that never
changed (harmless, but the record would say dirty when nothing was) or miss
one that did (fatal, and silent). The flag is the discipline's contract:
pin, use, unpin dirty only if you wrote.

DESIGN DECISION — Why LRU over the unpinned rather than a global LRU?
Because a pinned page is in use *right now* — evicting it corrupts the
operator above the pool. The recency order is shared, but eviction skips
whatever is pinned; a pool of one frame running a join keeps the inner
page's frame exactly because pinning outranks recency.
"""

import disk as dk
import pages as pg
import tables as tb
import ops

BUFFER_KEYS = ("hits", "misses", "evictions", "dirty")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


class BufferPool:
    """`frames` pages, LRU over the unpinned, the counter the check reads."""

    def __init__(self, pager, frames):
        """The pool over one pager, holding `frames` pages."""
        raise NotImplementedError("stage 7: implement BufferPool.__init__()")

    def fetch(self, page):
        """A page's bytes: a hit from the pool, a miss from the pager.

        A miss reads the pager (the disk's counter moves), caches, and
        evicts LRU-over-unpinned when the pool is full. Refuses a page the
        pager does not hold."""

        raise NotImplementedError("stage 7: implement BufferPool.fetch()")

    def pin(self, page):
        """Hold a page's frame: eviction skips it until it is unpinned."""

        raise NotImplementedError("stage 7: implement BufferPool.pin()")

    def unpin(self, page, dirty=False):
        """Release a frame; a dirty page is written back on eviction."""

        raise NotImplementedError("stage 7: implement BufferPool.unpin()")

    def record(self):
        """BUFFER_KEYS: hits, misses, evictions, dirty count."""

        raise NotImplementedError("stage 7: implement BufferPool.record()")


def run_buffered(pager, tree, plan_record, frames):
    """A plan through the pool: EXEC_KEYS plus BUFFER_KEYS.

    Runs the executor's pipeline with every page read through the pool, and
    answers the executor's keys plus the buffer's record."""

    raise NotImplementedError("stage 7: implement run_buffered()")
