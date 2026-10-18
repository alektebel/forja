"""Runtime From Scratch — stage 9: Generations — the nursery, promotion, and
what survives.

The last collector idea, and the one the whole ledger was built to test: most
objects die young. The heap already knows where everything was born — every
`allocate` lands in the nursery generation — and this stage collects the
nursery *alone*: mark from the roots but restricted to the young objects, free
the young garbage, and *promote* the young survivors to the older generation,
where the next nursery collection will not even look at them. The older
generation is collected by nothing in this stage; that is the hypothesis's
bet, and the check holds the stage to it.

`run_generational` is the integration: the provided program runs against a
generational heap — the build allocates, and when the nursery's population
reaches the threshold, a collection fires — and the record answers GEN_KEYS:
the nursery's population at the trigger, the promoted, the collected, and the
ledger. The check replays the trigger against the rooted collection's own
numbers.

The check tests the hypothesis where it lives: over the heap programs, most
objects die young (the program-ended heap collects the whole nursery), the
survivors of one nursery collection are not collected by the next (they were
promoted — the nursery's population is zero and the second record is a
no-work record), and `validate_reachability` holds after *every* collection
the record names — per-collection, not per-run.

DESIGN DECISION — Why does promotion use `heap.move` and not a generation
field write?
Because the world is the referee and `move` is the one primitive it offers
for changing an object's home: it allocates the twin in the destination
generation, copies the payload, and leaves a forwarding pointer so every old
id still answers. A bare `obj.generation = OLD` write would be the stage
mutating the world's headers behind the heap's ledger — law 10's line, held
here too.

DESIGN DECISION — Why is the nursery's mark rooted in the *young* objects the
roots reach, and not in every root?
Because the old generation is off-limits this stage: an old object is not
walked, and an old object's slots contribute nothing to a nursery collection.
The restriction is the stage's whole economy — the mark's cost is
proportional to the young population, not the whole heap.

DESIGN DECISION — Why does a moved object's old body not count as nursery
population?
Because it is a dead body waiting for the copying collector, not a young
object: freeing it would follow the forwarding pointer and kill the twin
(the heap's own rule), and counting it would make the threshold fire on
bodies instead of objects. The nursery's population is live, un-forwarded,
born in NURSERY — the definition the check recomputes on its own.
"""

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


def nursery_collect(heap, threshold):
    """One nursery collection, when the nursery's population has reached the
    threshold: mark the young from the roots, free the young garbage, promote
    the young survivors.

    Answers GEN_KEYS — the nursery's population at the trigger, the promoted,
    the collected, and the ledger the collection produced. Below the threshold
    the record says so and the ledger does not move."""

    raise NotImplementedError("stage 9: implement nursery_collect()")


def promote(heap, obj):
    """One young survivor moves to the older generation, through the heap's
    own move: a twin in the old generation, the old id answering through the
    forwarding pointer.

    Answers GEN_KEYS — one promoted, nothing collected, the ledger's moves
    grown by one."""

    raise NotImplementedError("stage 9: implement promote()")


def run_generational(module, heap, threshold):
    """The named heap program against a generational heap: the build runs,
    and when the nursery is at the threshold, a collection fires.

    `module` is the program's name (as in stage 4's `run_with_heap`); a frame
    program's name refuses. Answers GEN_KEYS."""

    raise NotImplementedError("stage 9: implement run_generational()")
