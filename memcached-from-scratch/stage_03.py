"""Memcached From Scratch — stage 3: per-page LRU, and the hot key that dies.

Stage 2 allocated slots; this stage puts items in them and decides who dies
when the memory runs out. The daemon's LRU is not per item — it is per
PAGE, and a full class recycles one page wholesale. That single design
choice is why memcached evictions look random from the outside.

DESIGN DECISION — why evict a whole page instead of the oldest item?
    The tempting alternative is a global LRU list: evict exactly the
    longest-unseen item, textbook-correct. Its cost is the list itself: one
    linked node per item, updated on EVERY read, for millions of items —
    memory and CPU the daemon refuses to spend. A per-page LRU touches only
    the page's slot list, and reclaiming a page is O(1) bookkeeping. The
    price: one hot key sharing a page with stale neighbours dies with them.

DESIGN DECISION — why is the victim the page whose OWN front is oldest?
    The tempting alternative is to recycle the globally oldest page. Its
    cost is that "age of a page" has no meaning independent of its items:
    what the class compares is the oldest touch ON EACH PAGE, and the page
    whose front is stalest is the page whose *typical* item is stalest.
    A read re-touches one item and moves it to its page's young end — so a
    page touched only through one hot key ages around that key's own
    touches, and replace-reorders which page dies next.

DESIGN DECISION — why does an expired read FREE its slot before answering?
    The tempting alternative is to answer the miss and leave the corpse for
    the sweeper. Its cost is the accounting the daemon's `expired_unfetched`
    exists to count: a dead item holding a slot nobody will ever read again
    is memory stolen from live ones. The read that discovers the death
    buries it right there — `expired_freed` is that reader's counter.

DESIGN DECISION — why is exptime an ABSOLUTE tick here, 0 meaning never?
    The tempting alternative is storing a TTL and subtracting. Its cost is
    every read needing the store-time tick too: the item must answer "am I
    dead at now?" from data it carries alone, because after a restart the
    daemon has only the stamps in shared memory. `exptime` is arrival + ttl,
    and the death test is one comparison: now >= exptime.

TODO: implement `Item.__init__`, `__repr__`, `Page.full`, `free_slot`,
`put`, `touch`, `drop`, `clear`, `lru_stamp` and `LruSlab.__init__`,
`store`, `get`, `delete`, `live`, `stats`.
"""

from world import CacheError


class Item:
    """One stored value with the two facts eviction and TTL need: the tick
    it was last touched and the tick it dies (0 meaning never)."""

    __slots__ = ("key", "value", "flags", "exptime", "touched")

    def __init__(self, key, value, flags, exptime, touched):
        raise NotImplementedError("stage 3: implement Item.__init__()")

    def __repr__(self):
        raise NotImplementedError("stage 3: implement Item.__repr__()")


class Page:
    """One page of one class: `capacity` slots, and its own LRU order."""

    def __init__(self, cls, index, capacity):
        raise NotImplementedError("stage 3: implement Page.__init__()")

    def full(self):
        """True when every slot holds an item."""
        raise NotImplementedError("stage 3: implement Page.full()")

    def free_slot(self):
        """The lowest-numbered empty slot; refuse a page that reports no
        free slot while it is not full."""
        raise NotImplementedError("stage 3: implement Page.free_slot()")

    def put(self, key, value, flags, exptime, now):
        """Place an item in a free slot and append its slot to the page's
        young end; return the slot number."""
        raise NotImplementedError("stage 3: implement Page.put()")

    def touch(self, slot, stamp):
        """A read: move the slot to the page's young end and stamp the
        item's `touched`."""
        raise NotImplementedError("stage 3: implement Page.touch()")

    def drop(self, slot):
        """Free one slot — an expired or deleted item, not a victim; return
        the item."""
        raise NotImplementedError("stage 3: implement Page.drop()")

    def clear(self):
        """Recycle the whole page: every item on it dies at once; return
        them in LRU order."""
        raise NotImplementedError("stage 3: implement Page.clear()")

    def lru_stamp(self):
        """The touch tick of this page's OLDEST item — what the class
        compares when picking a victim; None for an empty page."""
        raise NotImplementedError("stage 3: implement Page.lru_stamp()")


class LruSlab:
    """A slab store whose eviction is per page — the thing that makes the
    eviction order look random from the outside.

    Invariants: an item lives in exactly one page; `get` of an expired item
    frees the slot and answers a miss; when a class is full, the victim is
    the page whose own LRU front is oldest, and that page dies *wholesale*,
    no matter how often any single item on it was read.
    """

    def __init__(self, capacity_per_page, max_pages_per_class):
        raise NotImplementedError("stage 3: implement LruSlab.__init__()")

    def store(self, key, value, now, flags=0, exptime=0):
        """Store or replace: an existing key's item is overwritten in place
        and re-touched; a new key lands in `len(value)`'s class (the toy
        ladder — one class per byte length). `exptime` is an ABSOLUTE tick,
        0 never, and must be after `now`."""
        raise NotImplementedError("stage 3: implement LruSlab.store()")

    def get(self, key, now, mark=True):
        """The live Item or None. An expired item frees its slot, counts
        `expired_freed`, and answers None. `mark=False` reads WITHOUT
        re-touching — the way to look at the LRU without changing it."""
        raise NotImplementedError("stage 3: implement LruSlab.get()")

    def delete(self, key):
        """True if a key died, False if there was nothing to delete."""
        raise NotImplementedError("stage 3: implement LruSlab.delete()")

    def live(self):
        """Items standing right now."""
        raise NotImplementedError("stage 3: implement LruSlab.live()")

    def stats(self):
        """{"pages": cls -> count, "live", "evicted_pages", "evicted_items",
        "expired_freed"} — stage 9 reads its eviction numbers from here."""
        raise NotImplementedError("stage 3: implement LruSlab.stats()")
