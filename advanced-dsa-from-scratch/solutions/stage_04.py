"""The Fibonacci heap, part two: consolidation — the lazy merge's bill.

La Rocca, ch. 2 / CLRS ch. 19.3 — extract-min is where the Fibonacci heap
pays for stage 3's O(1) unions: the popped root's children are orphaned
into the root ring, and then the ring is CONSOLIDATED — roots are bucketed
by degree and whenever two land in the same bucket the larger key becomes
the smaller key's first child. One pass, and afterwards every root degree
is distinct, which is the invariant the amortized analysis counts on.

DESIGN DECISION — the popped root's children join the root ring by ONE
splice (`_join(z, z.child)`), not a loop inserting each child: the loop is
O(deg) splices of singletons, the splice is O(1) whatever the degree, and
the whole point of this heap is that restructuring happens once in
consolidation, not once per child. The parent-clearing scan has to walk
the merged ring either way, so the loop buys nothing.

DESIGN DECISION — the bucket table is sized from the degree bound the
heap's own invariant guarantees (`FIB_MIN[d] <= n`), not from the root
count: a degree-d root owns a subtree of at least FIB_MIN[d] nodes, so d
can never exceed ~1.44 log2 n — and a consolidation that miscounted a
degree lands on the refusal instead of writing past an array sized by luck.

This stage does exactly one thing: consolidation makes extract-min
correct and cheap-amortised. decrease-key — the other half of why the
deferral pays — is stage 5.
"""

from graphs import FIB_MIN
from stage_03 import FibError, _join, _cut, _ring
from stage_03 import FibHeap as _MergeOnlyHeap


def _degree_bound(n):
    """Largest d with FIB_MIN[d] <= n. `n` must be the WATERMARK — the most
    nodes the heap ever held, never the live count: degree d was created when
    the subtree held >= FIB_MIN[d] nodes, and cuts and extractions only shrink
    what is alive; guarding on the live count refuses legal heaps (CLRS 19.4)."""
    d = 0
    while d + 1 < len(FIB_MIN) and FIB_MIN[d + 1] <= n:
        d += 1
    return d


class FibHeap(_MergeOnlyHeap):
    """stage 3's lazy merge, plus the bill: `extract_min` and `consolidate`.
    Inheriting the ring machinery IS the lesson — extract-min is the only
    new mechanism in this file, and stage 5 adds one more on top."""

    def _link(self, child, parent):
        """`child`'s tree becomes `parent`'s first child. The comparison
        that picked the pair was counted by the walk before the call."""
        _cut(child)                       # out of the root ring
        if parent.child is None:
            parent.child = child
        else:
            _join(parent.child, child)
        child.parent = parent
        child.mark = False
        parent.degree += 1

    def consolidate(self):
        """Bucket roots by degree; merge every pair that lands together.
        One key comparison per merge, counted in `work`."""
        if self.min is None:
            return None
        buckets = [None] * (_degree_bound(self.high) + 1)
        for x in _ring(self.min):
            while True:
                d = x.degree
                if d >= len(buckets):
                    raise FibError("a root of degree %d exceeds the bound "
                                   "for a heap that held %d nodes — a tree "
                                   "grew without consolidating"
                                   % (d, self.high))
                if buckets[d] is None:
                    break
                y = buckets[d]
                buckets[d] = None
                self.work += 1
                if y.key < x.key:         # x keeps the smaller key; the
                    x, y = y, x           # loser is the tree that hangs
                self._link(y, x)
            buckets[x.degree] = x
        new_min = None
        for x in buckets:                 # degree order: deterministic rings
            if x is None:
                continue
            _cut(x)                       # out of whatever ring it is in
            if new_min is None:
                new_min = x
            else:
                _join(new_min, x)
                self.work += 1
                if x.key < new_min.key:
                    new_min = x
        self.min = new_min
        return new_min

    def extract_min(self):
        """The whole bill: orphan the min's children in one splice, cut the
        min out of the ring while its neighbours still know it, consolidate.
        Returns the popped node (payload and all — Dijkstra needs the node
        identities, not just the keys)."""
        if self.min is None:
            raise FibError("extract_min of an empty heap")
        z = self.min
        if z.child is not None:
            kids = _ring(z.child)
            _join(z, z.child)             # children into the root ring
            for x in kids:
                x.parent = None
                x.mark = False   # a root never carries a mark (stage 5's law)
        # read the neighbour BEFORE the cut: after it every node is its own
        # left, so "was the ring more than z?" can only be asked now
        self.min = z.left if z.left is not z else None
        _cut(z)
        self.n -= 1
        z.child = None
        z.degree = 0
        z.mark = False
        if self.min is not None:
            self.consolidate()
        return z

    def pop(self):
        return self.extract_min().key


def degrees(heap):
    """The sorted root degrees — the invariant the check pins: distinct."""
    return sorted(root.degree for root in heap.roots())


def measure():
    """The measured bars for this stage: consolidation's price on the
    worst case the lazy merge can hand it — 1024 roots, then every pop
    in order. extract-min is the whole bill, paid once, and the bar says
    how big the bill is."""
    from stage_01 import KEYS
    heap = FibHeap(KEYS[:1024])
    work0 = heap.work
    out = []
    while len(heap):
        out.append(heap.pop())
    assert out == sorted(KEYS[:1024]), "consolidation lost or reordered a key"
    return {"fib_consolidate_work": heap.work - work0}


if __name__ == "__main__":
    print("stage 4 — consolidation:", measure())
