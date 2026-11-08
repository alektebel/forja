"""The d-way heap: one child scan wider, log_d n levels shallower.

La Rocca, ch. 1 — the generalisation the binary heap is the D=2 case of.
Children of i are D*i+1 .. D*i+D; the parent of i is (i-1)//D. Sift-down
compares the sunk element against D children instead of two, and travels
log_D(n) levels instead of log_2(n): the trade is (D-1) extra comparisons
per level against fewer levels, and which side wins is measurable, not
folklore. The array holds the heap from index 0 — no slot-0 sentinel: a
counted heap with a wasted slot makes every "cmp per pop" bar depend on a
position that is not a key.

DESIGN DECISION — D is an instance attribute defaulting to 4, not a module
constant: the Dijkstra report runs the SAME graph through D=2,3,4,6 and
needs live heaps side by side. One class per arity was the alternative;
that duplicates the sift bodies, and a duplicated sift is two places for
the same off-by-one to hide.

DESIGN DECISION — the child scan walks the FULL window and clamps at the
end, recording one comparison per child actually looked at: the count is
then exactly what the theory predicts, and the bar can pin it. The
"pick the best two then compare" shortcut saves comparisons and makes the
counter lie about the scan it performed.

DESIGN DECISION — keys are ints OR pairs (int, int...), and an optional
shared `pos` dict tracks where each payload sits: the pair form is what
Dijkstra needs to break distance ties deterministically, and position
bookkeeping belongs inside the moves (there are exactly four) — an engine
maintaining the map from outside must rescan O(n) after every sift, which
is a linear scan in the hot loop, or duplicate the sift to patch it. The
dict is passed in, so the caller owns its lifetime.
"""


class DaryError(Exception):
    """Refusal: a D that does not make the heap a heap."""


def _key_ok(key):
    """int, or a tuple of ints — no bools, no floats, no strings."""
    if isinstance(key, bool):
        return False
    if isinstance(key, int):
        return True
    return (isinstance(key, tuple) and len(key) >= 2
            and all(isinstance(x, int) and not isinstance(x, bool)
                    for x in key))


class DaryHeap:
    """A min-heap of arity D over an array; `_a` is the judged structure."""

    def __init__(self, items=(), D=4, pos=None):
        if isinstance(D, bool) or not isinstance(D, int) or D < 2:
            raise DaryError("D must be an int >= 2, not %r" % (D,))
        for item in items:
            if not _key_ok(item):
                raise DaryError("keys are ints or int-tuples, not %r"
                                % (item,))
        self.D = D
        self._a = list(items)
        self._pos = pos          # payload -> index, maintained when not None
        self.cmp = 0
        self.swaps = 0
        if pos is not None:
            for i, item in enumerate(self._a):
                pos[self.payload_of(item)] = i
        if self._a:
            # last index with a child: D*i+1 < n, i.e. i <= (n-2)//D — at
            # D=4 and n=6 the tempting `n//D - 1` skips a real internal node
            for i in range((len(self._a) - 2) // D, -1, -1):
                self._sift_down(i)

    @staticmethod
    def payload_of(item):
        return item[1] if isinstance(item, tuple) else item

    def __len__(self):
        return len(self._a)

    def peek(self):
        if not self._a:
            raise DaryError("peek of an empty heap")
        return self._a[0]

    def _less(self, x, y):
        self.cmp += 1
        return x < y

    def _place(self, i, item):
        self._a[i] = item
        if self._pos is not None:
            self._pos[self.payload_of(item)] = i

    def _sift_up(self, i):
        a, D = self._a, self.D
        item = a[i]
        while i > 0:
            parent = (i - 1) // D
            if not self._less(item, a[parent]):
                break
            self._place(i, a[parent])
            self.swaps += 1
            i = parent
        self._place(i, item)

    def _sift_down(self, i):
        a, D = self._a, self.D
        n = len(a)
        item = a[i]
        while True:
            first = D * i + 1
            if first >= n:
                break
            best = first
            best_key = a[first]
            for c in range(first + 1, min(first + D, n)):
                if self._less(a[c], best_key):
                    best, best_key = c, a[c]
            if not self._less(best_key, item):
                break
            self._place(i, a[best])
            self.swaps += 1
            i = best
        self._place(i, item)

    def push(self, key):
        if not _key_ok(key):
            raise DaryError("keys are ints or int-tuples, not %r" % (key,))
        self._a.append(key)
        if self._pos is not None:
            self._pos[self.payload_of(key)] = len(self._a) - 1
        self._sift_up(len(self._a) - 1)

    def decrease_key(self, payload, new_key):
        """Only meaningful with a `pos` dict and pair keys: lower the key
        of the entry whose payload is `payload` and sift it up. The refusal
        when the payload is not in the heap is the Dijkstra bug catcher."""
        if self._pos is None:
            raise DaryError("decrease_key needs the pos= form of the heap")
        if payload not in self._pos:
            raise DaryError("decrease_key of payload %r: not in this heap"
                            % (payload,))
        i = self._pos[payload]
        if not _key_ok(new_key):
            raise DaryError("keys are ints or int-tuples, not %r" % (new_key,))
        if not new_key < self._a[i]:
            raise DaryError("decrease_key wants a smaller key than %r"
                            % (self._a[i],))
        self._a[i] = new_key
        self._sift_up(i)

    def pop(self):
        if not self._a:
            raise DaryError("pop of an empty heap")
        a = self._a
        top = a[0]
        last = a.pop()
        if self._pos is not None:
            del self._pos[self.payload_of(top)]
        if a:
            self._place(0, last)
            self.swaps += 1
            self._sift_down(0)
        return top


def dary_sort(items, D=4):
    """Sort by building and popping a D-ary heap; returns (out, cmp, swaps)."""
    heap = DaryHeap(items, D=D)
    out = []
    while len(heap):
        out.append(heap.pop())
    return tuple(out), heap.cmp, heap.swaps


from stage_01 import KEYS


def measure():
    """The measured bars for this stage: the same sort the binary heap
    does, at arity 4 — the comparison the theory invites you to count."""
    out, cmp, swaps = dary_sort(KEYS, D=4)
    assert out == tuple(sorted(KEYS)), "dary_sort is not a sort on KEYS"
    return {"dary_sort_cmp": cmp, "dary_sort_swaps": swaps}


if __name__ == "__main__":
    print("stage 2 — d-ary heap:", measure())
