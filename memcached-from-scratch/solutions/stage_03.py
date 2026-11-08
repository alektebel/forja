"""Memcached From Scratch — stage 3: per-page LRU, and the hot key that dies.

The finished implementation. The reasoning — why a full class recycles a
whole page instead of one slot, why the victim is the page whose *own* LRU
front is oldest, why an expired read frees its slot before answering, and
why the class here is `len(value)` instead of stage 2's ladder — lives in
the DESIGN DECISION blocks of `stage_03.py`.
"""

from world import CacheError


class Item:
    """One stored value with the two facts eviction and TTL need: the tick it
    was last touched and the tick it dies (0 meaning never)."""

    __slots__ = ("key", "value", "flags", "exptime", "touched")

    def __init__(self, key, value, flags, exptime, touched):
        self.key = key
        self.value = value
        self.flags = flags
        self.exptime = exptime
        self.touched = touched

    def __repr__(self):
        return "Item(%r, exp=%d)" % (self.key, self.exptime)


class Page:
    """One page of one class: `capacity` slots, and its own LRU order."""

    def __init__(self, cls, index, capacity):
        self.cls = cls
        self.index = index
        self.capacity = capacity
        self.items = {}   # slot -> Item
        self.order = []   # slots, oldest-touched first

    def full(self):
        return len(self.items) == self.capacity

    def free_slot(self):
        for slot in range(self.capacity):
            if slot not in self.items:
                return slot
        raise CacheError("page %d/%d reports no free slot" % (self.cls, self.index))

    def put(self, key, value, flags, exptime, now):
        slot = self.free_slot()
        self.items[slot] = Item(key, value, flags, exptime, now)
        self.order.append(slot)
        return slot

    def touch(self, slot, stamp):
        self.order.remove(slot)
        self.order.append(slot)
        self.items[slot].touched = stamp

    def drop(self, slot):
        """Free one slot: an expired or deleted item, not a victim."""
        item = self.items.pop(slot)
        self.order.remove(slot)
        return item

    def clear(self):
        """Recycle the whole page: every item on it dies at once."""
        doomed = [self.items[s] for s in self.order]
        self.items = {}
        self.order = []
        return doomed

    def lru_stamp(self):
        """The age of this page's *oldest* item — what the class compares."""
        if not self.order:
            return None
        return self.items[self.order[0]].touched


class LruSlab:
    """A slab store whose eviction is per page — the thing that makes the
    eviction order look random from the outside.

    Invariants: an item lives in exactly one page; `get` of an expired item
    frees the slot and answers a miss; when a class is full, the victim is
    the page whose own LRU front is oldest, and that page dies *wholesale*,
    no matter how often any single item on it was read.
    """

    def __init__(self, capacity_per_page, max_pages_per_class):
        if isinstance(capacity_per_page, bool) or capacity_per_page <= 0:
            raise CacheError("capacity_per_page %r: a positive int"
                             % (capacity_per_page,))
        if isinstance(max_pages_per_class, bool) or max_pages_per_class <= 0:
            raise CacheError("max_pages_per_class %r: a positive int"
                             % (max_pages_per_class,))
        self._cap = capacity_per_page
        self._max_pages = max_pages_per_class
        self._pages = {}    # cls -> list of Page
        self._by_key = {}   # key -> (page, slot)
        self.evicted_pages = 0
        self.evicted_items = 0
        self.expired_freed = 0

    def store(self, key, value, now, flags=0, exptime=0):
        if not isinstance(key, str) or not key:
            raise CacheError("store(%r): a key is a non-empty string" % key)
        if not isinstance(value, str):
            raise CacheError("store('%s'): a value is text" % key)
        if exptime and now >= exptime:
            raise CacheError("store('%s'): exptime %d is not after now %d"
                             % (key, exptime, now))
        if key in self._by_key:
            page, slot = self._by_key[key]
            item = page.items[slot]
            item.value = value
            item.flags = flags
            item.exptime = exptime
            page.touch(slot, now)
            return
        cls = len(value) or 1  # the toy ladder: one class per byte length
        page = self._find_room(cls, now)
        self._by_key[key] = (page, page.put(key, value, flags, exptime, now))

    def _find_room(self, cls, now):
        pages = self._pages.setdefault(cls, [])
        for page in pages:
            if not page.full():
                return page
        if len(pages) < self._max_pages:
            page = Page(cls, len(pages), self._cap)
            pages.append(page)
            return page
        # No room anywhere: recycle the page whose *own* LRU front is oldest.
        # Everything on it dies at once — a read-heavy key and its stale
        # neighbours share a page and a fate.
        victim = min((p for p in pages if p.lru_stamp() is not None),
                     key=lambda p: p.lru_stamp())
        for doomed in victim.clear():
            self._by_key.pop(doomed.key)
            self.evicted_items += 1
        self.evicted_pages += 1
        # The recycler's first tenant is young, or the next eviction would
        # pick this page again on the strength of an item it no longer holds.
        return victim

    def get(self, key, now, mark=True):
        loc = self._by_key.get(key)
        if loc is None:
            return None
        page, slot = loc
        item = page.items[slot]
        if item.exptime and now >= item.exptime:
            page.drop(slot)
            self._by_key.pop(key)
            self.expired_freed += 1
            return None
        if mark:
            page.touch(slot, now)
        return item

    def delete(self, key):
        loc = self._by_key.pop(key, None)
        if loc is None:
            return False
        loc[0].drop(loc[1])
        return True

    def live(self):
        return len(self._by_key)

    def stats(self):
        return {"pages": {c: len(ps) for c, ps in self._pages.items()},
                "live": self.live(),
                "evicted_pages": self.evicted_pages,
                "evicted_items": self.evicted_items,
                "expired_freed": self.expired_freed}


if __name__ == "__main__":
    # 2 slots per page, 2 pages per class: a full class recycles a whole
    # page, and the recycled page's oldest tenant sets its age.
    slab = LruSlab(capacity_per_page=2, max_pages_per_class=2)
    slab.store("p1:a", "x", now=1)
    slab.store("p1:b", "x", now=2)
    slab.store("hot", "x", now=3)           # first item of page 2
    slab.store("p2:c", "x", now=100)
    for t in range(200, 300):
        slab.get("hot", t)                  # 100 reads: 'hot' is beloved
    slab.store("newcomer", "x", now=400)    # full: page 1 recycles wholesale
    print("died with the page:", sorted(k for k in ("p1:a", "p1:b")
                                        if slab.get(k, 401) is None))
    slab.store("p1:d", "x", now=500)        # fills the recycled page again
    slab.store("newcomer2", "x", now=600)   # full: page 2 recycles next
    print("hot key evicted by its own page:", slab.get("hot", 601) is None)
    print("stats:", slab.stats())
    slab.store("dies@700", "y", now=650, exptime=700)  # a hole remains on page 1
    print("expiry read before:", slab.get("dies@700", 699) is not None,
          "| after:", slab.get("dies@700", 700) is None,
          "| slot freed:", slab.stats()["expired_freed"] == 1)
