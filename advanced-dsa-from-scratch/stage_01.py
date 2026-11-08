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
        # TODO: hold the items in one list, then build bottom-up.
        raise NotImplementedError("Heap.__init__")

    def __len__(self):
        # TODO: the heap's size.
        raise NotImplementedError("Heap.__len__")

    def peek(self):
        # TODO: the root; refuse an empty heap.
        raise NotImplementedError("Heap.peek")

    def _less(self, x, y):
        # TODO: one comparison, counted in `cmp`, of two int keys.
        raise NotImplementedError("Heap._less")

    def _sift_up(self, i):
        # TODO: hole-and-place toward the root; one cmp per step.
        raise NotImplementedError("Heap._sift_up")

    def _sift_down(self, i):
        # TODO: choose the smaller child, stop at a leaf, count swaps.
        raise NotImplementedError("Heap._sift_down")

    def push(self, key):
        # TODO: append, then sift up from the last index.
        raise NotImplementedError("Heap.push")

    def pop(self):
        # TODO: save the root, move the last item up, sift down from 0.
        raise NotImplementedError("Heap.pop")


def heapify(items):
    """A heap holding exactly these keys — the bottom-up build, counted."""
    # TODO: the bottom-up build, starting at the last internal node.
    raise NotImplementedError("heapify")


def heap_sort(items):
    """The classic two-phase sort: build, then pop n times; the work is
    what the bar measures."""
    # TODO: build then pop every key; return (out, cmp, swaps).
    raise NotImplementedError("heap_sort")


def measure():
    """The measured bars for this stage: the work of sorting KEYS."""
    # TODO: sort KEYS and report the two counters as the bars.
    raise NotImplementedError("measure")


if __name__ == "__main__":
    print("stage 1 — binary heap:", measure())
