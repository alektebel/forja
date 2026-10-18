"""The stage 5 solution: mark from the roots, trace to exhaustion, sweep."""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS
from stage_04 import HEAP_KEYS, HEAP_PROGRAMS, demand_of

MARK_KEYS = ('marked', 'swept', 'freed_bytes')


def _set_mark(heap, oid, marked):
    """Mark one object, once: the set is the record, the bit is the state."""
    obj = heap.deref(oid)
    if oid not in marked:
        obj.marked = hp.MARK_SET
        heap.marks += 1
        marked.add(oid)
    return obj


def mark_roots(heap):
    """The roots' objects, marked and collected."""
    marked = set()
    for root in heap.roots:
        oid = heap.follow(root)
        if oid != hp.NULL_ID:
            _set_mark(heap, oid, marked)
    return marked


def trace(heap, marked):
    """The gray worklist, drained."""
    worklist = sorted(marked)
    while worklist:
        oid = worklist.pop()
        obj = heap.deref(oid)
        for slot in obj.slots:
            if slot == hp.NULL_ID:
                continue
            child = heap.follow(slot)
            if child != hp.NULL_ID and child not in marked:
                _set_mark(heap, child, marked)
                worklist.append(child)
    return marked


def sweep(heap, marked):
    """Every live object the mark did not reach is freed; marks cleared."""
    before = heap.stats()
    for oid in heap.live_ids():
        if oid in marked:
            continue
        obj = heap.deref(oid)
        if obj.forwarded is not None:
            continue        # a moved object's old body is already reclaimed
        heap.free(oid)
    for oid in marked:
        obj = heap.deref(oid)
        obj.marked = hp.MARK_CLEAR
    heap.marks = 0
    after = heap.stats()
    return {"marked": len(marked),
            "swept": sum(after["freed"].values())
            - sum(before["freed"].values()),
            "freed_bytes": after["bytes_freed"] - before["bytes_freed"]}


def collect_mark_sweep(heap):
    """The whole collector: mark, trace, sweep, clear."""
    marked = mark_roots(heap)
    trace(heap, marked)
    return sweep(heap, marked)
