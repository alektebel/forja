"""The stage 7 solution: the gray worklist, budgeted, with the same verdict."""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS
from stage_04 import HEAP_KEYS, HEAP_PROGRAMS, demand_of
from stage_05 import MARK_KEYS
from stage_06 import RC_KEYS

COLOURS = ("white", "gray", "black")
INC_KEYS = ('phases', 'marks', 'pauses')

# the collector's module state: the colour table and the pause count — set by
# init_tricolour, consumed by increment/finish_marking. The *world* (heap)
# stays untouched; this is the collector's own desk.
_STATE = {"colours": {}, "worklist": [], "pauses": 0}


def init_tricolour(heap):
    """Every object white, the objects the roots name gray."""
    colours = {oid: "white" for oid in heap.live_ids()}
    worklist = []
    for root in heap.roots:
        oid = heap.follow(root)
        if oid != hp.NULL_ID and colours[oid] == "white":
            colours[oid] = "gray"
            worklist.append(oid)
    _STATE["colours"] = colours
    _STATE["worklist"] = worklist
    _STATE["pauses"] = 0
    return {"colours": colours, "grays": list(worklist)}


def _unit(heap):
    """One unit of marking work: pop a gray, darken its whites, blacken it."""
    colours = _STATE["colours"]
    worklist = _STATE["worklist"]
    oid = worklist.pop(0)
    obj = heap.deref(oid)
    for slot in obj.slots:
        if slot == hp.NULL_ID:
            continue
        child = heap.follow(slot)
        if child != hp.NULL_ID and colours[child] == "white":
            colours[child] = "gray"
            worklist.append(child)
            heap.marks += 1
    colours[oid] = "black"
    return oid


def increment(heap, budget):
    """Spend up to `budget` units; answer INC_KEYS."""
    phases = []
    marks_before = heap.marks
    for _ in range(budget):
        if not _STATE["worklist"]:
            break
        phases.append(_unit(heap))
    _STATE["pauses"] += 1
    return {"phases": tuple(phases),
            "marks": heap.marks - marks_before,
            "pauses": _STATE["pauses"]}


def finish_marking(heap):
    """Drain the worklist, sweep, answer the MARK_KEYS shape."""
    before = heap.stats()
    while _STATE["worklist"]:
        _unit(heap)
    colours = _STATE["colours"]
    marked = {oid for oid, colour in colours.items() if colour == "black"}
    for oid in heap.live_ids():
        obj = heap.deref(oid)
        if oid in marked:
            continue
        if obj.forwarded is not None:
            continue
        heap.free(oid)
    for oid in marked:
        colours[oid] = "white"
    _STATE["colours"] = {}
    _STATE["worklist"] = []
    after = heap.stats()
    return {"marked": len(marked),
            "swept": sum(after["freed"].values())
            - sum(before["freed"].values()),
            "freed_bytes": after["bytes_freed"] - before["bytes_freed"]}
