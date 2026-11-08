"""Memcached From Scratch — stage 2: slab classes, and the size that does not fit.

The finished implementation. The reasoning — why the smallest class that
fits, why growth is geometric, why an over-large item is refused instead of
split, why a page count is an int and a bool is not one — lives in the
DESIGN DECISION blocks of `stage_02.py`.
"""

from world import CacheError

#: The class ladder mirrors memcached's own defaults: start at 48 bytes and
#: multiply by 1.25, so the ladder reaches 1 MB in about 60 rungs. The store
#: is configurable because a check cannot wait for a 1 MB demo.
SLAB_START = 48
SLAB_GROWTH = 1.25
SLAB_MAX_ITEM = 1048576
PAGE_BYTES = 1048576  # one page is 1 MB in the real daemon


def _build_classes(start, growth, max_item):
    if isinstance(start, bool) or not isinstance(start, int) or start <= 0:
        raise CacheError("slab start %r: must be a positive int" % (start,))
    if isinstance(max_item, bool) or not isinstance(max_item, int) or max_item <= 0:
        raise CacheError("max item %r: must be a positive int" % (max_item,))
    if not isinstance(growth, (int, float)) or growth <= 1.0:
        raise CacheError("slab growth %r: must be a number above 1.0" % (growth,))
    if start > max_item:
        raise CacheError("slab start %d is above max item %d: the ladder is empty"
                         % (start, max_item))
    classes = []
    size = start
    while size <= max_item:
        n = int(size)
        if not classes or classes[-1] != n:
            classes.append(n)
        size = size * growth
    return tuple(classes)


class Slot:
    """One allocated home for one item: which class, which page, which hole.

    Frozen by convention — stage 3 evicts by it, and an evicted slot must
    name the page and hole it came from or the free list corrupts.
    """

    __slots__ = ("cls", "page", "index")

    def __init__(self, cls, page, index):
        self.cls = cls
        self.page = page
        self.index = index

    def __eq__(self, other):
        return (isinstance(other, Slot) and (self.cls, self.page, self.index) ==
                (other.cls, other.page, other.index))

    def __hash__(self):
        return hash((self.cls, self.page, self.index))

    def __repr__(self):
        return "Slot(cls=%d, page=%d, index=%d)" % (self.cls, self.page, self.index)


class Slab:
    """Items to class sizes to pages, exactly once per key.

    The invariant every later stage leans on: a key owns at most one slot, a
    slot's class is at least the item's byte length, `granted` never exceeds
    `pages * slots_per_page`, and no flat index was ever handed out twice.
    """

    def __init__(self, start=SLAB_START, growth=SLAB_GROWTH,
                 max_item=SLAB_MAX_ITEM, page_bytes=PAGE_BYTES):
        self._classes = _build_classes(start, growth, max_item)
        self._page_bytes = page_bytes
        self._spp = {c: page_bytes // c for c in self._classes}
        if any(v == 0 for v in self._spp.values()):
            raise CacheError("class %d is larger than a page (%d) and holds no slots"
                             % (max(self._classes), page_bytes))
        self._pages = {c: 0 for c in self._classes}
        self._granted = {c: 0 for c in self._classes}
        self._free = {c: [] for c in self._classes}
        self._by_key = {}

    def classes(self):
        return self._classes

    def class_for(self, size):
        if isinstance(size, bool) or not isinstance(size, int):
            raise CacheError("class_for(%r): a size is an int of bytes" % (size,))
        if size < 0:
            raise CacheError("class_for(%d): a size is not negative" % size)
        for c in self._classes:
            if c >= size:
                return c
        raise CacheError("item of %d bytes does not fit: the max class is %d "
                         "and a value is never split" % (size, self._classes[-1]))

    def place(self, key, size):
        if not isinstance(key, str) or not key:
            raise CacheError("place(%r): a key is a non-empty string" % (key,))
        if key in self._by_key:
            raise CacheError("'%s' already owns slot %r; a re-store replaces, "
                             "it does not double-place" % (key, self._by_key[key]))
        cls = self.class_for(size)
        if self._free[cls]:
            flat = self._free[cls].pop()
        else:
            if self._granted[cls] == self._pages[cls] * self._spp[cls]:
                self._pages[cls] += 1
            flat = self._granted[cls]
            self._granted[cls] += 1
        slot = Slot(cls, flat // self._spp[cls], flat % self._spp[cls])
        self._by_key[key] = slot
        return slot

    def remove(self, key):
        try:
            slot = self._by_key.pop(key)
        except KeyError:
            raise CacheError("'%s' holds no slot" % key)
        flat = slot.page * self._spp[slot.cls] + slot.index
        self._free[slot.cls].append(flat)
        return slot

    def slot_of(self, key):
        try:
            return self._by_key[key]
        except KeyError:
            raise CacheError("'%s' holds no slot" % key)

    def live(self):
        return len(self._by_key)

    def stats(self):
        return {
            "pages": dict(self._pages),
            "granted": dict(self._granted),
            "free": {c: len(self._free[c]) for c in self._classes},
        }


if __name__ == "__main__":
    slab = Slab(start=8, growth=2.0, max_item=64, page_bytes=64)
    print("ladder:", slab.classes())
    a = slab.place("user:1", 10)
    b = slab.place("user:2", 5)
    print("user:1 (10B) ->", a, " user:2 (5B) ->", b)
    try:
        slab.place("big", 65)
    except CacheError as err:
        print("refused:", err)
    slab.remove("user:1")
    c = slab.place("user:3", 30)
    print("after a removal, user:3 (30B) ->", c)
    print("stats:", slab.stats())
