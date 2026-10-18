"""Runtime From Scratch — stage 7: Tri-colour incremental marking, and the
gray worklist.

Stage 5's collector is stop-the-world: the wavefront runs to exhaustion and
the program waits. The real chapter's answer is to cut the work into
*budgeted* slices — each `increment` call spends a few units of marking work
(one unit: pop a gray from the worklist, darken every white it mentions,
blacken it) and returns the program to the mutator between slices. The
tri-colour abstraction is what makes the interleaving safe: *white* is not
reached yet, *gray* is reached but its children are not darkened yet, *black*
is reached and finished, and the worklist is exactly the set of grays.

Two disciplines this stage must hold, and the check holds them:

* **Determinism across pause boundaries.** Two increments of budget 1 must
  land exactly where one increment of budget 2 landed — the grays after each
  step, the marks spent, everything. A pause is a recorded event, not a
  lost place; `pauses` names how many the record saw.
* **The same verdict as stage 5.** `finish_marking` drains the worklist,
  sweeps, and answers the same `MARK_KEYS` shape the stop-the-world collector
  produced — over `shared` and over `cycle`, the incremental collector must
  free exactly what the stop-the-world one freed. If the two collectors can
  disagree about which objects die, one of them is wrong and the record says
  which.

DESIGN DECISION — Why is the colour table a dict keyed by id, owned by the
stage, and not a field on the object?
Because the heap is the world, not the collector: the object's header already
carries the mark bit stage 5 used (a stop-the-world collector needs one bit),
and the tri-colour abstraction needs a *third* state. Adding it to the
provided heap would let the world drift toward this stage's collector; the
colour table keeps the abstraction in the stage where it lives, and
`init_tricolour` hands it to whoever is driving the interleaving.

DESIGN DECISION — Why is one unit "pop a gray, darken its children, blacken
it" and not "darken one child"?
Because the unit is the pause granularity the chapter records: the mutator
runs between pops, and the invariant "a black object's children are gray or
black" holds at every pause boundary. Per-child units would let a pause land
mid-object, where the invariant is unstatable.


TODO: implement the functions this stage names; the docstrings above are the contract.

DESIGN DECISION — Why does `finish_marking` sweep the colours it drained
rather than trusting stage 5's sweep?
Because the incremental mark's marked set is the colour table's blacks, not
stage 5's bit-set: the two collectors share the shape of their answer, not
their state. Reusing stage 5's sweep would mean writing stage 5's marks — the
world's read-only rule, held here too.
"""

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


def init_tricolour(heap):
    """The colour table at the start of a mark: every object white, the
    objects the roots name gray.

    Answers `{"colours": {id: COLOURS[...]}, "grays": [the gray ids in work
    order]}` — the chapter's steps 1 and 2, and the worklist `increment`
    drains."""

    raise NotImplementedError("stage 7: implement init_tricolour()")


def increment(heap, budget):
    """Spend up to `budget` units of marking work, answering INC_KEYS.

    One unit: pop a gray, darken every white it mentions, blacken it. The
    record names the phases the work went through, the marks spent, and the
    pauses this collector has taken so far."""

    raise NotImplementedError("stage 7: implement increment()")


def finish_marking(heap):
    """Drain the worklist and sweep, answering the MARK_KEYS shape stage 5
    produced — the incremental collector's verdict must be the stop-the-world
    one's."""

    raise NotImplementedError("stage 7: implement finish_marking()")
