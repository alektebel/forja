"""The stage 4 solution: the heap programs as shapes, and the ledger's verdict."""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS

HEAP_KEYS = ('output', 'steps', 'ledger')

HEAP_PROGRAMS = ('conslist', 'shared', 'cycle')


def demand_of(name):
    """The heap demand `PROGRAMS` pins for `name`."""
    if name not in HEAP_PROGRAMS:
        raise bc.BytecodeError(
            "%r is not a heap program (the shapes are %s)"
            % (name, ", ".join(HEAP_PROGRAMS)))
    return dict(bc.PROGRAMS[name]["heap"])


def _cons(heap, value, nxt):
    """pair(box(value), nxt) — the list's cell, built through the heap.
    `nxt` is a cell id or None; the answer is the new cell's id."""
    box = heap.allocate(hp.SHAPE_BOX, value=value)
    cell = heap.allocate(hp.SHAPE_PAIR)
    heap.set_slot(cell, 0, box)
    heap.set_slot(cell, 1, nxt if nxt is not None else hp.NULL_ID)
    return cell


def _sum(heap, head):
    """Walk the list from the head id, adding every box's value."""
    total = 0
    oid = head
    while oid != hp.NULL_ID:
        obj = heap.deref(oid)
        total += heap.value_of(heap.follow(heap.slot(oid, 0)))
        oid = heap.slot(oid, 1)
    return total


def build(name, heap):
    """The program's shape, built on the provided heap; answers the output."""
    if name == "conslist":
        head = None
        for value in (3, 2, 1):          # built tail-first: 1 -> 2 -> 3
            head = _cons(heap, value, head)
        heap.roots.append(head)
        return [_sum(heap, head)]
    if name == "shared":
        # tail -> child <- both parents: the child's refcount is 2, and the
        # demand (§2.3: four pairs, four boxes) is parent1 + parent2 + child
        # + tail, with boxes 2, 3, 4, 0 — the sum the program answers is the
        # parents' boxes plus the child's, 9.
        tail = heap.allocate(hp.SHAPE_PAIR)
        heap.set_slot(tail, 0, heap.allocate(hp.SHAPE_BOX, value=0))
        heap.set_slot(tail, 1, hp.NULL_ID)
        child = heap.allocate(hp.SHAPE_PAIR)
        heap.set_slot(child, 0, heap.allocate(hp.SHAPE_BOX, value=4))
        heap.set_slot(child, 1, tail)
        p1 = heap.allocate(hp.SHAPE_PAIR)
        p2 = heap.allocate(hp.SHAPE_PAIR)
        heap.set_slot(p1, 0, heap.allocate(hp.SHAPE_BOX, value=2))
        heap.set_slot(p1, 1, child)
        heap.set_slot(p2, 0, heap.allocate(hp.SHAPE_BOX, value=3))
        heap.set_slot(p2, 1, child)
        heap.roots.extend([p1, p2])
        total = 2 + 3 + heap.value_of(heap.follow(heap.slot(child, 0)))
        return [total]
    if name == "cycle":
        a = heap.allocate(hp.SHAPE_PAIR)
        b = heap.allocate(hp.SHAPE_PAIR)
        heap.set_slot(a, 0, heap.allocate(hp.SHAPE_BOX, value=1))
        heap.set_slot(a, 1, b)
        heap.set_slot(b, 0, heap.allocate(hp.SHAPE_BOX, value=1))
        heap.set_slot(b, 1, a)
        heap.roots.extend([a, b])
        total = (heap.value_of(heap.follow(heap.slot(a, 0)))
                 + heap.value_of(heap.follow(heap.slot(b, 0))))
        return [total]
    raise bc.BytecodeError(
        "%r is not a heap program (the shapes are %s)"
        % (name, ", ".join(HEAP_PROGRAMS)))


def run_with_heap(name, heap):
    """The program run against the heap: build, sum, answer the record."""
    before = heap.stats()
    output = build(name, heap)
    after = heap.stats()
    pairs = after["allocated"][hp.SHAPE_PAIR] - before["allocated"][hp.SHAPE_PAIR]
    boxes = after["allocated"][hp.SHAPE_BOX] - before["allocated"][hp.SHAPE_BOX]
    steps = pairs + boxes
    return {"output": tuple(output), "steps": steps, "ledger": after}


def agree(program, heap):
    """Whether the heap's *live* objects agree with the program's demand."""
    demand = demand_of(program)
    st = heap.stats()
    for shape, count in demand.items():
        live = st["allocated"].get(shape, 0) - st["freed"].get(shape, 0)
        if live != count:
            return False
    return True
