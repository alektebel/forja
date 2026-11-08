"""Memcached From Scratch — stage 2: slab classes, and the size that does not fit.

The daemon never mallocs a value. It owns fixed-size pages, carves each page
into slots of one class, and rounds every item up to the smallest class that
fits. This stage builds the allocator's ledger: the class ladder, the slot
coordinates, holes, pages.

DESIGN DECISION — why the smallest class that FITS, not the nearest?
    The tempting alternative is rounding to whichever class edge is closer.
    Its cost is that a 9-byte item in a class of 8 cannot hold a 9-byte
    item: "nearest" is a allocator that loses values. The rule is a search
    for the first rung >= size, and a size above every rung is an error —
    the last rung is a ceiling, not a suggestion.

DESIGN DECISION — why is a value that does not fit REFUSED instead of split?
    The tempting alternative is chaining two slots. Its cost is every
    reader of the store — LRU, TTL sweep, the stats report — having to know
    that an item may be several slots, which is where memcached landed: the
    1 MB cap, stated as the maximum item size, and values over it belong in
    a different system. A refusal at the class lookup is one place the rule
    lives.

DESIGN DECISION — why growth 1.25 and not 2.0?
    The tempting alternative is doubling, the classic buddy system. Its
    cost is the waste at the top of every rung: a 65 KB item into a 128 KB
    class loses 49%. At 1.25 the ladder is ~60 rungs to 1 MB and the worst
    rounding loss is 20%, paid for in a little more bookkeeping — which is
    exactly the daemon's own `slab_chunk_size` default.

DESIGN DECISION — why does a freed hole get reused before any new page?
    The tempting alternative is always appending to the page's tail —
    simpler, no free lists. Its cost is fragmentation: after a delete storm
    a class holds pages mostly full of holes while the allocator keeps
    asking the OS for more. Holes before pages is the difference between an
    allocator that recycles and one that grows forever.

TODO: implement `Slot.__init__`, `__eq__`, `__hash__`, `__repr__` and
`Slab.__init__`, `classes`, `class_for`, `place`, `remove`, `slot_of`,
`live`, `stats`.
"""

from world import CacheError

#: The class ladder mirrors memcached's own defaults: start at 48 bytes and
#: multiply by 1.25, so the ladder reaches 1 MB in about 60 rungs. The
#: defaults are frozen numbers the checks read; the store is configurable
#: because a check cannot wait for a 1 MB demo.
SLAB_START = 48
SLAB_GROWTH = 1.25
SLAB_MAX_ITEM = 1048576
PAGE_BYTES = 1048576  # one page is 1 MB in the real daemon


class Slot:
    """One allocated home for one item: which class, which page, which hole.

    Frozen by convention — stage 3 evicts by it, and an evicted slot must
    name the page and hole it came from or the free list corrupts.
    """

    __slots__ = ("cls", "page", "index")

    def __init__(self, cls, page, index):
        raise NotImplementedError("stage 2: implement Slot.__init__()")

    def __eq__(self, other):
        raise NotImplementedError("stage 2: implement Slot.__eq__()")

    def __hash__(self):
        raise NotImplementedError("stage 2: implement Slot.__hash__()")

    def __repr__(self):
        raise NotImplementedError("stage 2: implement Slot.__repr__()")


class Slab:
    """The class ladder plus the page/hole ledger for one worker."""

    def __init__(self, start=SLAB_START, growth=SLAB_GROWTH,
                 max_item=SLAB_MAX_ITEM, page_bytes=PAGE_BYTES):
        raise NotImplementedError("stage 2: implement Slab.__init__()")

    def classes(self):
        """The ladder as a tuple of class sizes, smallest first, each rung
        floor(previous * growth), stopping at or under max_item."""
        raise NotImplementedError("stage 2: implement Slab.classes()")

    def class_for(self, size):
        """The smallest class >= size; a size past the last rung is refused
        by name — the size, the ceiling, and the fact that a value is never
        split."""
        raise NotImplementedError("stage 2: implement Slab.class_for()")

    def place(self, key, size):
        """Give `key` its slot in class `class_for(size)`: a freed hole of
        that class first, else the class's next flat index, opening a page
        only when the pages it has are fully granted. The flat index decodes
        to Slot(cls, flat // slots_per_page, flat % slots_per_page)."""
        raise NotImplementedError("stage 2: implement Slab.place()")

    def remove(self, key):
        """Free the key's slot — its flat index back on the class's free
        list — and return it; a key that holds nothing is refused."""
        raise NotImplementedError("stage 2: implement Slab.remove()")

    def slot_of(self, key):
        """The key's current slot; refuse a key that holds nothing."""
        raise NotImplementedError("stage 2: implement Slab.slot_of()")

    def live(self):
        """How many keys hold a slot right now."""
        raise NotImplementedError("stage 2: implement Slab.live()")

    def stats(self):
        """{"pages": cls -> pages held, "granted": cls -> flat indices
        granted, "free": cls -> holes waiting} — granted must never exceed
        pages x slots-per-page."""
        raise NotImplementedError("stage 2: implement Slab.stats()")
