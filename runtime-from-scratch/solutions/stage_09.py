"""The stage 9 solution: the nursery, promotion, and the generational run."""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS
from stage_04 import HEAP_KEYS, HEAP_PROGRAMS, demand_of
from stage_05 import MARK_KEYS
from stage_06 import RC_KEYS
from stage_07 import COLOURS, INC_KEYS
from stage_08 import BARRIER_KEYS

GEN_KEYS = ('nursery', 'promoted', 'collected', 'ledger')

_OLD = "old"          # the older generation's name; every object is born in
                     # NURSERY, and promotion is the move that leaves it


def _young(heap):
    """The nursery's population: every live, un-forwarded object born in
    NURSERY — a moved object's old body is not nursery population."""
    return [oid for oid in heap.live_ids()
            if heap.deref(oid).generation == hp.NURSERY
            and heap.deref(oid).forwarded is None]


def promote(heap, obj):
    """One young survivor moves to the older generation, via the heap's move."""
    before = heap.stats()
    new_id = heap.move(obj.id, _OLD)
    after = heap.stats()
    return {"nursery": len(_young(heap)),
            "promoted": (new_id,),
            "collected": tuple(),
            "ledger": {"moves": after["moves"] - before["moves"],
                       "freed": dict(after["freed"])}}


def nursery_collect(heap, threshold):
    """Mark the young from the roots, free the young garbage, promote."""
    nursery = _young(heap)
    record = {"nursery": len(nursery), "promoted": tuple(),
              "collected": tuple(), "ledger": heap.stats()}
    if len(nursery) < threshold:
        return record                      # the nursery is not full: no work
    # mark from the roots, restricted to the young generation: an old object
    # is not walked, and an old object's slots contribute nothing
    young = set(nursery)
    marked = set()
    worklist = []
    for root in heap.roots:
        oid = heap.follow(root)
        if oid == hp.NULL_ID or oid not in young:
            continue
        if oid not in marked:
            marked.add(oid)
            worklist.append(oid)
    while worklist:
        oid = worklist.pop(0)
        for slot in heap.deref(oid).slots:
            if slot == hp.NULL_ID:
                continue
            child = heap.follow(slot)
            if child == hp.NULL_ID or child not in young:
                continue
            if child not in marked:
                marked.add(child)
                worklist.append(child)
    before = heap.stats()
    collected = []
    promoted = []
    for oid in nursery:                    # the young garbage dies first
        if oid not in marked:
            heap.free(oid)
            collected.append(oid)
    for oid in sorted(marked):             # the survivors promote
        promoted.append(heap.move(oid, _OLD))
    heap.collections += 1
    after = heap.stats()
    return {"nursery": len(nursery),
            "promoted": tuple(promoted),
            "collected": tuple(collected),
            "ledger": {"moves": after["moves"] - before["moves"],
                       "freed": dict(after["freed"]),
                       "collections": after["collections"]}}


def run_generational(module, heap, threshold=4):
    """The named heap program against a generational heap: the build runs,
    and when the nursery is at the threshold, a collection fires — the
    survivors promote, the garbage dies, and the record answers GEN_KEYS."""
    if module not in HEAP_PROGRAMS:
        raise bc.BytecodeError(
            "%r is not a heap program (the shapes are %s)"
            % (module, ", ".join(HEAP_PROGRAMS)))
    from stage_04 import build
    build(module, heap)
    return nursery_collect(heap, threshold)
