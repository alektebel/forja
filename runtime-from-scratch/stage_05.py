"""Runtime From Scratch — stage 5: Mark-sweep: the wavefront, and nothing
reachable freed.

The first collector, and still the shape every tracing collector keeps: mark
from the roots, sweep the unmarked. The world's heap holds the mark bit on
every object's header (`marked`, clear at birth) and counts what the collector
marks and frees in its ledger, so the stage's answers are comparisons against
the world's numbers — the swept set is whatever `heap.free` accepted, and the
counts are the ledger's own.

The discipline is the GC chapter's, read as an algorithm over the provided
heap: the roots darken first (gray, in the tri-colour language this stage
borrows before stage 7 needs it literally), the gray worklist drains until
nothing gray remains (every white a gray mentions darkens; the gray itself
goes black), and only then does the sweep walk the heap and free what stayed
white. The invariant is the one no collector may break — law 14, nothing
reachable is ever freed — and the world grades it itself:
`heap.validate_reachability()` answers the reachable set after any collection,
and `freed ∩ reachable == ∅` is the whole test.

The three heap programs give the collector its three verdicts: `conslist` dies
whole (the cascade the sweep finds in one pass), `shared` dies whole too but
only because the wavefront goes through *both* parents, and `cycle` is the
mark-sweep's triumph — reference counting cannot free it, the wavefront walks
in one side and out the other, and exactly two pairs and two boxes are swept.

DESIGN DECISION — Why does `sweep` free through `heap.free` instead of a sweep
list the stage keeps?
Because the ledger only counts what the heap frees, and the stage's answer is
the ledger's. A stage that kept its own freed list would have to copy the
ledger to be believed; freeing through the heap makes the record and the act
the same event. It also makes a double-sweep impossible to do quietly: the
heap refuses a second `free` of the same object, which is the boundary the
check asserts.

DESIGN DECISION — Why does the sweep skip a moved object's old body?
Because the old body is a ghost the heap has already reclaimed: `heap.move`
wrote the forwarding pointer and the live data into the twin, and `heap.free`
of the ghost would free *through* the forwarding — killing the twin. The
chapter's copying discipline leaves the old semispace to be bulk-cleared;
here the ghost stays until a copying collector owns it (stage 10), and the
sweep's rule is simple and honest: free what is live, unmarked, and not a
forwarding shell.

DESIGN DECISION — Why must the marks be *cleared* before the sweep returns?
Because the mark bit is one bit, and a collector that leaves it set has made
the next collection start from a lie — every object already "marked" survives
a sweep that trusts it. The chapter's discipline is per-collection colour
state: white at the start of marking, black at the end, and the sweep is what
returns the heap to a clean white for the next one. The check asserts the
after-state (every surviving object's `marked` is clear), because the next
stage's collector will be graded against the same heap.

DESIGN DECISION — Why does `collect_mark_sweep` answer the *world's* numbers
and not the stage's own tally?
Because the tally is the one thing a buggy collector gets wrong in exactly the
way that is hardest to see: a mark that visits an object twice, a sweep that
frees one fewer object than it claims. The record's numbers come from
`heap.stats()` — taken before and after — so a stage whose claim and whose
act disagree is caught by comparing its own record against the heap it
acted on.


TODO: implement the functions this stage names; the docstrings above are the contract.
"""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS
from stage_04 import HEAP_KEYS, HEAP_PROGRAMS, demand_of

MARK_KEYS = ('marked', 'swept', 'freed_bytes')


def mark_roots(heap):
    """The roots' objects, marked and collected: the wavefront's first row.

    Answers the set of ids the roots name (through forwarding, as `heap.follow`
    resolves it), each with `marked` set — and the ledger's `marks` counts
    them. A root naming a freed object is the mutator's mistake and refuses
    through `heap.deref`."""

    raise NotImplementedError("stage 5: implement mark_roots()")


def trace(heap, marked):
    """The gray worklist, drained: every white a marked object mentions is
    marked, until nothing new is.

    `marked` is the set of ids already reached (the roots' row); the answer is
    the whole reachable set, every member with `marked` set. A slot naming a
    freed object is a dangling reference and refuses through `heap.deref`."""

    raise NotImplementedError("stage 5: implement trace()")


def sweep(heap, marked):
    """Every live object the mark did not reach is freed; the marks are then
    cleared, so the next collection starts from white. A moved object's old
    body is already reclaimed — its free went through the forwarding, and
    sweeping the ghost again is the heap's refused double free.

    Answers `MARK_KEYS` — how many objects the mark reached, how many the
    sweep freed, and the bytes the ledger says went away — with the counts
    read off `heap.stats()`, not tallied by the stage."""

    raise NotImplementedError("stage 5: implement sweep()")


def collect_mark_sweep(heap):
    """The whole collector: mark the roots, trace to exhaustion, sweep the
    rest, clear the marks; answer the world's numbers.

    The record is `MARK_KEYS`, and the check that grades it holds two more
    facts than the record carries: `validate_reachability()` after the
    collection is empty of everything the sweep freed (law 14), and every
    surviving object's `marked` is clear (the next collection starts honest)."""

    raise NotImplementedError("stage 5: implement collect_mark_sweep()")
