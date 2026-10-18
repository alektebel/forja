"""Runtime From Scratch — stage 8: The write barrier, and the remembered set.

Stage 7's incremental collector has one deadly window: the collector runs a
slice, the mutator runs, and if the mutator makes a *black* object point at a
*white* one, the mark will never visit the white — the collector saw the
black already, and the sweep will free a live object. That is the chapter's
danger scenario, and the write barrier is the fix: `needs_barrier` answers
whether a store is dangerous (black source, white value), and `write` applies
the cure — darken the source to gray (so the worklist revisits it), or put
the white into the remembered set (so the next mark starts from it). The
remembered set is the extra roots of the next mark; that is the whole trick.

The check plants the danger itself: it runs an incremental collection
interleaved with a mutator write that a *barrier-bypassing* heap would let
free a reachable object — and asserts that with the barrier, nothing
reachable dies. The mutation battery plants the bypass, and the check's
scenario must catch it: `freed ∩ reachable ≠ ∅` is the one invariant no
collector stage may break.

DESIGN DECISION — Why does `write` take the remembered set as an argument
and return it mutated, instead of owning it in stage state?
Because the remembered set belongs to the *mutator's* discipline: it grows
exactly where the program writes, and the next collection consumes it as
extra roots. Stage 7's colour table could live in collector state because
one collector owns it; the remembered set is shared between the mutator's
writes and the collector's next mark, so the check drives both halves and
must be able to hand the set across.

DESIGN DECISION — Why does `write` darken the source rather than always
remembering the value?
Because darkening is the cheaper cure when the source's children were not
darkened yet (the source goes back on the worklist and the mark finishes the
job), and remembering is the cure when the mark has already passed — the
chapter's two-barrier menu. `needs_barrier` names the danger; `write` answers
which cure it applied (`darkened` or `remembered`), and the check holds both
against the record.


TODO: implement the functions this stage names; the docstrings above are the contract.

DESIGN DECISION — Why does the barrier consult the *stage 7* colour table
rather than keeping its own?
Because there is one mark in flight and one set of grays, and two tables would
let the barrier's black disagree with the collector's black — the exact
disagreement the barrier exists to prevent. The mutator and the collector
share the desk, not the judgment.
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

BARRIER_KEYS = ('remembered', 'darkened')


def needs_barrier(obj, value):
    """Whether the store `obj.slot[i] = value` is dangerous: a black source
    storing a white value loses the white to the sweep."""

    raise NotImplementedError("stage 8: implement needs_barrier()")


def write(heap, obj, i, value, remembered):
    """One mutator store, through the barrier: darken the black source or
    remember the white value.

    Applies the store (`heap.set_slot`) and answers BARRIER_KEYS — what the
    barrier did about it. The remembered set is the mutator's and collector's
    shared record: it goes in, and the (possibly longer) set comes back."""

    raise NotImplementedError("stage 8: implement write()")


def collect_incremental(heap, remembered):
    """Stage 7's collector, with the remembered set as the extra mark roots —
    the barrier's whole point, asserted by the check's danger scenario."""

    raise NotImplementedError("stage 8: implement collect_incremental()")
