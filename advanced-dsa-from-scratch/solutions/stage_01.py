"""Binary heap: the array, the two sifts, and a counted sort.

La Rocca, ch. 1-2 (heaps) — the shape every later heap in this course is
compared against. A binary min-heap over an array: the parent of i is
(i-1)//2, the children are 2i+1 and 2i+2, and the heap property is
parent <= child. `push` restores it walking UP (the new leaf can only be
too small for its ancestors); `pop` takes the root, moves the LAST element
into the hole, and walks it DOWN (it can only be too big for its children).
DESIGN DECISION — sift-down is hole-and-place, not swap-three-then-descend:
the moved element's path is written once at the end, the shift each level
costs an assignment not three, and the swap counter is exactly the
assignments, so the check can pin it. The alternative (full swaps) is the
same tree but ~3x the recorded work, and the recorded work is the lesson.

DESIGN DECISION — the comparisons are counted, the structure is exposed:
`cmp` counts every key comparison the heap itself made, `swaps` every
move. A heap that returns the right answer can still be doing 2n extra
work per pop (a linear scan for the last element's reinsert, say); only
the counters see that, which is why the bars hang off them.
"""

from graphs import COINS

#: the fixed input every bar on this stage measures: 4096 ints, one byte
#: each from the world's single noise source, so the number is ONE number
#: and not a different number on a different machine.
KEYS = tuple(c * 4 + i % 251 for i, c in enumerate(COINS))


class HeapError(Exception):
    """The heap's refusal: a call that would make it lie about its shape."""


class Heap:
    """A min-heap over an array; `_a` is the array, exposed for the judge."""

    def __init__(self, items=()):
        for item in items:
            if isinstance(item, bool) or not isinstance(item, int):
                raise HeapError("keys are ints, not %r" % (item,))
        self._a = list(items)
        self.cmp = 0
        self.swaps = 0
        if self._a:
            # bottom-up build: sift every internal node down, last-first —
            # O(n), and the proof is that most sifts travel zero levels.
            for i in range(len(self._a) // 2 - 1, -1, -1):
                self._sift_down(i)

    def __len__(self):
        return len(self._a)

    def peek(self):
        if not self._a:
            raise HeapError("peek of an empty heap")
        return self._a[0]

    def _less(self, x, y):
        self.cmp += 1
        return x < y

    def _sift_up(self, i):
        item = self._a[i]
        while i > 0:
            parent = (i - 1) // 2
            if not self._less(item, self._a[parent]):
                break
            self._a[i] = self._a[parent]
            self.swaps += 1
            i = parent
        self._a[i] = item

    def _sift_down(self, i):
        a = self._a
        item = a[i]
        n = len(a)
        while True:
            child = 2 * i + 1
            if child >= n:
                break
            if child + 1 < n and self._less(a[child + 1], a[child]):
                child += 1
            if not self._less(a[child], item):
                break
            a[i] = a[child]
            self.swaps += 1
            i = child
        a[i] = item

    def push(self, key):
        if isinstance(key, bool) or not isinstance(key, int):
            raise HeapError("keys are ints, not %r" % (key,))
        self._a.append(key)
        self._sift_up(len(self._a) - 1)

    def pop(self):
        if not self._a:
            raise HeapError("pop of an empty heap")
        a = self._a
        top = a[0]
        last = a.pop()
        if a:
            a[0] = last
            self.swaps += 1          # the last element into the hole
            self._sift_down(0)
        return top


def heapify(items):
    """A heap holding exactly these keys — the bottom-up build, counted."""
    return Heap(items)


def heap_sort(items):
    """The classic two-phase sort: build, then pop n times; the work is
    what the bar measures."""
    heap = Heap(items)
    out = []
    while len(heap):
        out.append(heap.pop())
    return tuple(out), heap.cmp, heap.swaps


def measure():
    """The measured bars for this stage: the work of sorting KEYS."""
    out, cmp, swaps = heap_sort(KEYS)
    assert out == tuple(sorted(KEYS)), "heap_sort is not a sort on KEYS"
    return {"heap_sort_cmp": cmp, "heap_sort_swaps": swaps}


if __name__ == "__main__":
    print("stage 1 — binary heap:", measure())
