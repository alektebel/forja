"""The Fibonacci heap, part three: decrease-key and the cascading cut.

La Rocca, ch. 2 / CLRS ch. 19.4 — the mechanism that keeps the lazy merge
from collapsing: `decrease_key` cuts the node off its parent and moves it
to the root ring in O(1); if its parent was already MARKED (had lost a
child before), the parent cuts itself too, and its parent follows — until
an unmarked parent (which becomes marked and the cascade stops) or a root
(which never carries a mark). The cascade is the amortized argument made
visible: the potential is (#roots + 2·#marked), a cut destroys at most one
mark and creates at most one, and consolidation's distinct root degrees
are what bound the debt the deferral can accumulate.

DESIGN DECISION — cutting a node repairs `parent.child` when the node WAS
that entry: the child ring's entry point is not a role, and a parent that
still points at a child who lives in the root ring now has the same node
reachable twice — the corruption `is_well_formed` reports as a double
reach, and the bug a first implementation writes while believing `_cut`
did all the unlinking it needs. One branch, in two places (the cut, and
every cascade hop), or the whole amortized story is a story about a heap
that is quietly a graph.

DESIGN DECISION — decrease-key REFUSES a key that is not smaller, and
refuses a node that is not in this heap. Silently accepting a no-op hides
the Dijkstra bug where an already-settled node is relaxed again; the call
has to fail loudly, and the message names WHICH rule said no, because
"not smaller" and "not mine" are different mistakes.

DESIGN DECISION — membership climbs to the root in O(depth) instead of
walking the heap in O(n): an O(n) decrease-key would break the amortized
promise this stage exists to teach. The climb trusts `is_well_formed`'s
no-cycles verdict and says so in the comment; a parent chain that cycles
is already a corrupt heap, and the walk that reports it is the check, not
this hot path.

DESIGN DECISION — a root that loses a child is NEVER marked: the cascade
climbs until it finds an UNMARKED NON-ROOT to mark, and stops. Marking
roots makes the cascade never stop and the potential bound a lie, and
`marked_nodes` exists to show a marked root as the bug even when every
key still pops in order.

This stage does exactly one thing: the cut rule. Stage 4 made extract-min
correct; stage 5 is why a long Dijkstra run does not collapse the heap.
"""

from stage_03 import FibError, FibNode, _join, _cut, _ring
from stage_04 import FibHeap as _ConsolidatedHeap


class FibHeap(_ConsolidatedHeap):
    """stage 4's extract-min, plus the cut rule: `decrease_key`, `delete`,
    and counters for the cascade the check pins."""

    def __init__(self, items=()):
        super().__init__(items)
        self.cuts = 0            # the first cut of a decrease-key
        self.cascades = 0        # extra cuts an already-marked parent took

    def _walk(self):
        """Every node, roots first then children — the ground truth the
        ledger helpers read. O(n), used for reporting and for `delete`'s
        sanity, never on the hot path of a decrease-key."""
        stack = list(_ring(self.min))
        seen = set()
        order = []
        while stack:
            x = stack.pop()
            if id(x) in seen:
                continue
            seen.add(id(x))
            order.append(x)
            if x.child is not None:
                stack.extend(_ring(x.child))
        return order

    def _belongs(self, node):
        """O(depth): climb the parent chain to the top and check the root
        ring. Trusts `is_well_formed`'s no-cycles verdict, deliberately —
        the alternative is an O(n) walk on the hot path."""
        if not isinstance(node, FibNode):
            return False
        top = node
        while top.parent is not None:
            top = top.parent
        return any(root is top for root in _ring(self.min))

    def _move_up(self, node, parent):
        """One cut: `node` leaves `parent`'s child ring for the root ring,
        repairing the entry pointer if `node` was it. The successor is read
        BEFORE `_cut`, which makes `node` its own ring and destroys it."""
        successor = node.right if node.right is not node else None
        _cut(node)
        node.parent = None
        node.mark = False
        parent.degree -= 1
        if parent.child is node:
            parent.child = successor
        _join(self.min, node)

    def _cut_and_maybe_cascade(self, node):
        """Cut `node` from its parent into the root ring; cascade up the
        already-marked ancestors. `node`'s key was already rewritten."""
        parent = node.parent
        if parent is None:
            return                       # a root: nothing to cut; min moves
        self._move_up(node, parent)
        self.cuts += 1
        while parent.mark and parent.parent is not None:
            grand = parent.parent
            self._move_up(parent, grand)
            self.cascades += 1
            parent = grand
        if parent.parent is not None:
            parent.mark = True           # the first loss: free, and stop

    def decrease_key(self, node, new_key):
        """Cut, relocate, maybe cascade — the O(1)-amortized mechanism."""
        if isinstance(new_key, bool) or not isinstance(new_key, int):
            raise FibError("keys are ints, not %r" % (new_key,))
        if not self._belongs(node):
            raise FibError("decrease_key of a node that is not in this heap")
        if new_key >= node.key:
            raise FibError("decrease_key wants a SMALLER key: %r is not "
                           "below %r" % (new_key, node.key))
        node.key = new_key
        self._cut_and_maybe_cascade(node)
        if node.key < self.min.key:
            self.min = node
        return node

    def delete(self, node):
        """The textbook reduction — two moves, both existing mechanisms:
        sink the key below the min (the min is the floor's only witness,
        so this stays O(1)), then extract-min pays the restructuring it
        already knows."""
        if not self._belongs(node):
            raise FibError("delete of a node that is not in this heap")
        floor = self.min.key - 1
        self.decrease_key(node, floor)
        return self.extract_min()


def marked_nodes(heap):
    """The cascade's ledger: every marked NON-root in the heap. A root
    here is the bug the stage's rule exists to prevent."""
    return tuple(x for x in heap._walk()
                 if x.parent is not None and x.mark)


def potential(heap):
    """#roots + 2·#marked — the amortized account the check reads before
    and after a cascade to prove the marks paid for the cuts."""
    nodes = heap._walk()
    roots = sum(1 for x in nodes if x.parent is None)
    marked = sum(1 for x in nodes if x.parent is not None and x.mark)
    return roots + 2 * marked


def measure():
    """The measured bars for this stage: the cascade's price on the fixed
    stream — consolidate first (extract 64 so keys live inside trees),
    then decrease-key through the trees, then drain. `cuts` and `cascades`
    are the ledger; an insert-only phase would leave every node a root and
    measure zero cuts, which is exactly the mistake this script avoids."""
    from graphs import COINS
    heap = FibHeap()
    handles = {}
    for i in range(512):
        k = COINS[i % len(COINS)] * 4096 + i      # i in the low bits: unique
        handles[k] = heap.insert(k, k)
    for _ in range(64):
        node = heap.extract_min()
        handles.pop(node.key)
    for i in range(256):
        key = sorted(handles, reverse=True)[i % len(handles)]
        node = handles.pop(key)
        nd = -1 - i                              # below every live key
        heap.decrease_key(node, nd)
        handles[nd] = node
    out = []
    while len(heap):
        out.append(heap.pop())
    assert out == sorted(out), "the cut rule broke the drain order"
    assert heap.is_well_formed()
    return {"fib_cuts": heap.cuts, "fib_cascades": heap.cascades,
            "fib_drain_work": heap.work}


if __name__ == "__main__":
    print("stage 5 — cascading cut:", measure())
