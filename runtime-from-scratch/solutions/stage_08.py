"""The stage 8 solution: the barrier, and the remembered set as extra roots."""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS
from stage_04 import HEAP_KEYS, HEAP_PROGRAMS, demand_of
from stage_05 import MARK_KEYS
from stage_06 import RC_KEYS
from stage_07 import COLOURS, INC_KEYS
import stage_07 as _s7

BARRIER_KEYS = ('remembered', 'darkened')


def _colour(oid):
    """The object's colour as the barrier sees it: the stage 7 table's word,
    and white for anything the table does not know (an unmarked heap)."""
    return _s7._STATE["colours"].get(oid, "white")


def needs_barrier(obj, value):
    """Black source storing a white value is the danger."""
    return _colour(obj.id) == "black" and _colour(value) == "white"


def write(heap, obj, i, value, remembered):
    """The store, through the barrier: darken the source (back to gray, back
    on the worklist) and remember the white value for the next mark."""
    darkened = 0
    if needs_barrier(obj, value):
        _s7._STATE["colours"][obj.id] = "gray"
        _s7._STATE["worklist"].append(obj.id)
        remembered = list(remembered) + [value]
        darkened = 1
    heap.set_slot(obj.id, i, value)
    return {"remembered": tuple(remembered), "darkened": darkened}


def collect_incremental(heap, remembered):
    """The mark, resumed with the remembered set as extra roots; then sweep.

    The collector's desk is wherever the mutator left it — the colours and
    the worklist stage 7's increments were spending. The remembered set
    seeds the resume: the barrier's whites are gray before the drain."""
    before = heap.stats()
    # the desk as the mutator left it; anything unknown is white
    colours = {oid: "white" for oid in heap.live_ids()}
    colours.update(_s7._STATE["colours"])
    worklist = list(_s7._STATE["worklist"])
    marks = 0
    for value in remembered:
        if value == hp.NULL_ID or colours.get(value) != "white":
            continue
        colours[value] = "gray"
        worklist.append(value)
    while worklist:
        oid = worklist.pop(0)
        if colours.get(oid) == "black":
            continue
        obj = heap.deref(oid)
        for slot in obj.slots:
            if slot == hp.NULL_ID:
                continue
            child = heap.follow(slot)
            if child != hp.NULL_ID and colours.get(child, "white") == "white":
                colours[child] = "gray"
                worklist.append(child)
                marks += 1
        colours[oid] = "black"
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
    _s7._STATE["colours"] = {}
    _s7._STATE["worklist"] = []
    after = heap.stats()
    return {"phases": tuple(sorted(marked)), "marks": marks, "pauses": 1}
