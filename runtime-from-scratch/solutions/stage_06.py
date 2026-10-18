"""The stage 6 solution: the decrement, the cascade, and the honest survivor."""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS
from stage_04 import HEAP_KEYS, HEAP_PROGRAMS, demand_of
from stage_05 import MARK_KEYS

RC_KEYS = ('freed', 'survivors', 'cycles')


def _incref(heap, oid):
    """One more reference to `oid` came to be (the mutator's side of the deal)."""
    heap.deref(oid).refcount += 1


def decref(heap, oid):
    """One reference to `oid` went away: count it down, free at zero, cascade."""
    freed = []
    cycles = []

    def drop(oid):
        obj = heap.deref(oid)
        if obj.refcount <= 0:
            raise bc.BytecodeError(
                "decref of %r whose count is already zero" % (oid,))
        obj.refcount -= 1
        if obj.refcount > 0:
            return
        # the object dies: its slots' decrements are the cascade
        freed.append(oid)
        children = [heap.follow(s) for s in obj.slots if s != hp.NULL_ID]
        heap.free(oid)
        for child in children:
            drop(child)

    drop(oid)
    survivors = [o for o in heap.live_ids() if o not in freed]
    return {"freed": tuple(freed), "survivors": tuple(survivors),
            "cycles": tuple(cycles)}


def collect_refcount(heap):
    """The whole-program verdict: every root lets go, the cascades run."""
    before = heap.stats()
    freed = []
    for root in list(heap.roots):
        record = decref(heap, root)
        freed.extend(record["freed"])
    heap.roots.clear()
    after = heap.stats()
    survivors = tuple(heap.live_ids())
    return {"freed": tuple(freed), "survivors": survivors,
            "cycles": tuple(unreachable_cycles(heap))}


def unreachable_cycles(heap):
    """The groups of live objects unreachable from the roots."""
    reachable = heap.validate_reachability()
    garbage = [o for o in heap.live_ids() if o not in reachable]
    if not garbage:
        return []
    # group the garbage: two objects are one group when a slot path leads
    # from one to the other without leaving the garbage
    groups = []
    seen = set()
    garbage_set = set(garbage)
    for start in garbage:
        if start in seen:
            continue
        group = set()
        worklist = [start]
        while worklist:
            oid = worklist.pop()
            if oid in group or oid not in garbage_set:
                continue
            group.add(oid)
            obj = heap.deref(oid)
            for slot in obj.slots:
                if slot != hp.NULL_ID:
                    worklist.append(heap.follow(slot))
        # the component may touch groups found earlier: merge them — the
        # garbage is grouped by *connectivity*, not by discovery order
        merged = [g for g in groups if g and set(g) & group]
        groups = [g for g in groups if not (set(g) & group)]
        whole = set().union(group, *merged) if merged else group
        seen |= whole
        groups.append(tuple(sorted(whole)))
    return groups
