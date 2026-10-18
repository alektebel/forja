"""Runtime From Scratch — stage 6: Reference counting, and the cycle it
cannot free.

The other family, and the one that trades the wavefront for a counter: every
object carries its refcount in its header, every assignment and every dropped
reference is one decrement, and an object dies the instant its count reaches
zero — no collection, no pause, just the cascade. The stage's discipline is
the cascade: freeing a pair decrements what its slots name, which may free
*them*, which may free what *they* name. `decref` is that recursion, and the
conslist is its testcase: drop the head and all three pairs and all three
boxes go, in the order the cascade says.

The stage's honest limitation is its thesis: a cycle's members point at each
other, so their counts never reach zero from the outside, and `cycle`'s two
pairs and two boxes survive every collection this stage can run. That is not
a bug to hide — it is the asymmetry with stage 5 that justifies tracing
collectors — and `unreachable_cycles` is how the record says so: the groups
of objects that are unreachable from the roots (the collector's own walk can
prove it) and still alive because they count each other.

DESIGN DECISION — Why does `decref` free through `heap.free` and decrement
through the slots, and not keep a free list?
Because the cascade's order is observable and the heap is the referee: the
conslist's cells die head-first, and a check that replays the stage's record
can hold the order against the shape. A free list would defer the deaths and
make the ledger's `freed` counts disagree with the stage's claim; freeing
through the heap makes each death a ledger event in cascade order.

DESIGN DECISION — Why is `unreachable_cycles` a *grouping* and not a bool?
Because "the cycle survived" is one fact about one program; "which objects
count each other and nothing outside" is the general answer, and it is what a
cycle collector (the real world's trial-delete) would consume. The groups are
computed by the stage's own reachability walk — the same walk stage 5's trace
ran — over the objects still alive after the counts have had their say: alive
but unreachable is the definition of garbage RC cannot name. Grouping is by
*connectivity*, not discovery order: two cycles joined by one slot are one
group, and the walk merges whatever it meets twice.

DESIGN DECISION — Why does `collect_refcount` drop the roots instead of
taking a "which roots to drop" argument?
Because the stage's contract is the whole-program verdict: the program ended,
the roots let go, and what dies is what RC can reach *downward*. A partial
drop is stage 9's business (the nursery's survivors), and giving this stage a
drop-set argument would let it answer a question the record could not check
against the programs' pinned shapes.


TODO: implement the functions this stage names; the docstrings above are the contract.
"""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS
from stage_04 import HEAP_KEYS, HEAP_PROGRAMS, demand_of
from stage_05 import MARK_KEYS

RC_KEYS = ('freed', 'survivors', 'cycles')


def decref(heap, oid):
    """One reference to `oid` went away: count it down, free at zero, cascade.

    Answers `RC_KEYS` — what the cascade freed (the ids, in death order), what
    survived, and the cycles it walked into but could not free. Freeing an
    object whose count is already zero is the caller's mistake and refuses
    naming the id; a freed id refuses through `heap.deref` as dangling."""

    raise NotImplementedError("stage 6: implement decref()")


def collect_refcount(heap):
    """The whole-program verdict: every root lets go, the cascades run, and
    what survives is what counted on itself.

    Answers `RC_KEYS` — the freed, the survivors, and the cycles. The ledger's
    `freed` counts are the record's, as in every collector stage."""

    raise NotImplementedError("stage 6: implement collect_refcount()")


def unreachable_cycles(heap):
    """The groups of live objects that are unreachable from the roots and
    alive only because they count each other.

    Answers a list of groups, each a tuple of ids; an empty list means the
    heap holds no garbage RC cannot name. The walk is the stage's own — the
    same slot-following walk stage 5's trace ran — over the objects still in
    the heap, and it never follows a slot out of the garbage."""

    raise NotImplementedError("stage 6: implement unreachable_cycles()")
