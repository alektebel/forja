"""The Fibonacci heap, part one: the lazy merge.

La Rocca, ch. 2 / CLRS ch. 19 — the mechanism that makes Fibonacci heaps
what they are: `insert` and `union` do NO restructuring at all. The roots
live in one circular doubly linked list, a node's children live in a
circular doubly linked list of their own, and `min` is a pointer into the
root ring. Union splices two rings; insert drops one node into the ring.
One key comparison per operation, at most — restructuring is deferred to
extract-min (stage 4), and the deferral is paid for by cascading cuts
(stage 5).

DESIGN DECISION — the ring join cuts one edge in each ring and crosses the
ends over (`a→b`, `u→r`), not the swap-neighbours idiom: the idiom keeps
forward traversal legal and quietly breaks `x.left`, so a heap whose links
stopped being inverses still pops correctly and only the integrity walk
below can see it. Four pointer writes instead of four swaps is the cost.

DESIGN DECISION — a node's `degree` is its own child count, kept as a
field, not computed: consolidate needs it per root repeatedly, and the
alternative was a child-ring walk per node per pass. A field can go stale —
exactly the bug stage 5's cascading cut provokes — so `is_well_formed`
recomputes it against the child ring every time, WITHOUT recursing: a
corrupted ring makes a recursive or unbounded walk spin until the
interpreter stops it, and a check must report corruption, not become it.
That is why there are two ring walkers below: `_ring` for the hot paths
that run on a heap believed healthy, `_ring_safe` for the one walk that
must terminate on a heap that is not.

DESIGN DECISION — `high` (the watermark) is heap state, not a comment:
`FIB_MIN[d] <= subtree(x)` was true the day x REACHED degree d; cuts and
extractions only shrink what is alive, so no live count bounds a root's
degree — only the most nodes the heap ever held does (CLRS 19.4). Stage 4
sizes its bucket table from `high`, and a degree that outruns it is the
refusal that means "a tree grew without consolidating".

This stage does exactly one thing: the merge is lazy. Peek is free because
min is a pointer, and the checks prove after every union that the right and
left links are inverses at every root — the property a one-way splice
breaks while forward traversal still looks fine.
"""


class FibError(Exception):
    """Refusal: a call that would leave the ring lying about itself."""


class FibNode:
    """One node: key, degree, child ring, parent, mark, and its ring links."""

    __slots__ = ("key", "degree", "child", "parent", "mark", "left", "right",
                 "payload")

    def __init__(self, key, payload=None):
        if isinstance(key, bool) or not isinstance(key, int):
            raise FibError("keys are ints, not %r" % (key,))
        self.key = key
        self.payload = payload
        self.degree = 0
        self.child = None
        self.parent = None
        self.mark = False
        self.left = self
        self.right = self

    def __repr__(self):
        return "FibNode(%d, deg=%d%s)" % (
            self.key, self.degree, ", mark" if self.mark else "")


def _join(a, b):
    """Merge the ring of `a` with the ring of `b`; they must be disjoint.
    `b` lands right after `a`. Works when either ring is a singleton."""
    r = a.right
    u = b.left
    a.right, b.left = b, a
    u.right, r.left = r, u


def _cut(node):
    """Take `node` out of its ring; the node is a singleton ring afterwards.
    Cutting the only member of a ring is a no-op on a ring, not a corruption."""
    p, q = node.left, node.right
    p.right, q.left = q, p
    node.left = node.right = node


def _ring(node):
    """Every node of the ring `node` is in, from `node`, once around.
    Assumes the links close — `is_well_formed` is the guard that makes that
    assumption cheap; on a corrupt heap this walk can spin, by design, so it
    is never the check's own walker."""
    if node is None:
        return []
    out = [node]
    x = node.right
    while x is not node:
        out.append(x)
        x = x.right
    return out


def _ring_safe(node):
    """`_ring` that cannot hang: walk right links, and if the chain wanders
    instead of closing on `node`, return None — corruption reported as a
    value, not as a crash the checker would only see as a timeout."""
    if node is None:
        return None
    out = [node]
    seen = {id(node)}
    x = node.right
    while x is not node:
        if id(x) in seen:
            return None
        seen.add(id(x))
        out.append(x)
        x = x.right
    return out


class FibHeap:
    """The root ring + a min pointer + a count + a watermark."""

    def __init__(self, items=()):
        self.min = None
        self.n = 0
        self.high = 0            # most nodes ever held: what bounds a degree
        self.work = 0            # key comparisons the lazy merge ever made
        for item in items:
            key = item if (isinstance(item, int) or isinstance(item, FibNode)) \
                else item[0]
            payload = None if not isinstance(item, tuple) else item[1]
            if isinstance(item, FibNode):
                self._adopt(item)
            else:
                self.insert(key, payload)

    def __len__(self):
        return self.n

    def _adopt(self, node):
        """Ring an existing node in (stage 4 and 5 reuse this for the
        children they orphan)."""
        if self.min is None:
            self.min = node
        else:
            _join(self.min, node)
            self.work += 1
            if node.key < self.min.key:
                self.min = node
        self.n += 1
        if self.n > self.high:
            self.high = self.n

    def insert(self, key, payload=None):
        """Add a singleton ring to the root ring. One comparison, at most."""
        node = FibNode(key, payload)          # the constructor validates
        self._adopt(node)
        return node

    def union(self, other):
        """Splice `other`'s ring into ours. The new min is one of the two
        old mins, so exactly one comparison between whole heaps."""
        if other is self:
            raise FibError("a heap cannot union with itself")
        if not isinstance(other, FibHeap):
            raise FibError("union wants a FibHeap, not %r" % (other,))
        if other.min is None:
            return self
        if self.min is None:
            self.min = other.min
        else:
            _join(self.min, other.min)
            self.work += 1
            if other.min.key < self.min.key:
                self.min = other.min
        self.n += other.n
        # the watermark is "most nodes EVER held", so the merged count is a
        # live lower bound on it too: max(high, high, n) — 1+1 beats max(1,1)
        if other.high > self.high:
            self.high = other.high
        if self.n > self.high:
            self.high = self.n
        other.min = None
        other.n = 0
        other.high = 0
        return self

    def peek(self):
        if self.min is None:
            raise FibError("peek of an empty heap")
        return self.min.key

    def roots(self):
        """The root ring from min, forward — the judge's window, not a way
        to change anything."""
        return tuple(_ring(self.min))

    def is_well_formed(self):
        """Every promise the structure makes about itself, recomputed on
        ONE bounded walk: each ring closes, the right and left links are
        inverses, min is a real min, no root has a parent, every child ring
        names this parent and has exactly `degree` members, no node is
        reachable twice (the stale-child corruption — a cut node still
        hanging from a parent's ring — reports False here instead of
        recursing forever), and `n` is the number of nodes reachable."""
        if (self.min is None) != (self.n == 0):
            return False
        if self.min is None:
            return True
        around = _ring_safe(self.min)
        if around is None:
            return False
        if any(x.right.left is not x or x.left.right is not x for x in around):
            return False
        if any(x.key < self.min.key for x in around):
            return False
        if any(x.parent is not None for x in around):
            return False
        seen = {id(x) for x in around}
        total = len(around)
        stack = list(around)
        while stack:
            node = stack.pop()
            if node.child is None:
                if node.degree != 0:
                    return False
                continue
            kids = _ring_safe(node.child)
            if kids is None or len(kids) != node.degree:
                return False
            for kid in kids:
                if kid.parent is not node or id(kid) in seen:
                    return False
                seen.add(id(kid))
                total += 1
                stack.append(kid)
        return total == self.n


def measure():
    """The measured bars for this stage: the lazy merge's price on a fixed
    batch — 512 inserts and one union. A merge that stayed lazy costs one
    comparison per adopt and one per union; anything that restructurises
    on insert walks past this bar on sight."""
    from stage_01 import KEYS
    a = FibHeap(KEYS[:512])
    b = FibHeap(KEYS[512:1024])
    before_a, work = a.work, a.work + b.work   # both builders' comparisons
    a.union(b)
    work += a.work - before_a                 # the union's own comparison
    assert a.is_well_formed()
    assert a.n == 1024 and a.peek() == min(KEYS[:1024]), \
        "the lazy merge lost a key or its min"
    return {"fib_merge_work": work}


if __name__ == "__main__":
    print("stage 3 — lazy merge:", measure())
