"""Runtime From Scratch — stage 4: The heap: objects, references, and the
ledger.

Stages 1–3 ran programs over a value stack of ints and strings; this stage is
where the heap joins, and with it the difference between *running* a program
and *accounting* for one. The heap programs of `PROGRAMS` — `conslist`,
`shared`, `cycle` — are not bytecode (§2.3): they are heap shapes the runtime
builds by its own means, and the world pins two facts about each of them, the
output and the heap demand. The demand is a dict of `{shape: count}` the
world's ledger must agree with exactly, and the ledger is the world's own
(`heap.stats()`), so the verdict `agree` answers is a comparison the stage
cannot color: either the runtime allocated three pairs and three boxes for
`conslist` or it did not.

The three programs are also, quietly, the collector's testcase set: `conslist`
is a list nobody shares, `shared` is a child two parents point at (refcount 2,
the case an owner-frees scheme breaks), and `cycle` is a→b→a dropped from the
roots together (the case reference counting cannot free). This stage only
builds them and reads the ledger; what to *free* is every later stage's job.

DESIGN DECISION — Why do the heap programs go through `run_with_heap` instead
of a bytecode extension?
Because their cost is not in dispatches but in objects. A bytecode that
allocated would pin an allocation strategy into the ISA (`CALL cons` is a
frame op and a constructor at once), and the step count would then depend on
choices — when to allocate, whether to reuse — that are exactly what stages
5–10 vary. As shapes, the programs pin only what a collector must honor (the
output and the demand), and every stage is free to allocate its own way as
long as the ledger agrees. The world measured the frame-free pins; here the
world only demands.

DESIGN DECISION — Why is `agree` a function of (program, heap) and not a bool
the stage computes once?
Because the comparison is against a moving ledger, and the honest answer is
the one taken at the moment the caller asks. A stage that cached its own
verdict would be graded on a claim about the past; `agree(program, heap)` is
the same few lines every time — read `demand_of`, read `heap.stats()`, compare
the live-per-shape counts — and a collector stage that frees between two calls
gets two different answers, which is the truth.

DESIGN DECISION — Why is the verdict about *live* objects and not allocations?
Because a heap that allocated right and then freed wrong is not agreement, and
a heap that allocated an extra object and freed it is. The ledger answers both
halves (`allocated` and `freed` per shape), and the demand is a statement
about what the program *leaves on the heap*, which is the live count. A stage
that compared the cumulative `allocated` would call a heap with a hole in it
an agreement, and the check's own scenario — free one object, ask again — is
there to make that mistake fail.

DESIGN DECISION — Why does the stage build the shapes through the provided
heap and never a dict of its own?
Because the ledger only counts what the heap sees. A stage that built the
conslist as a Python list of lists would answer the right *output* with a
ledger that says nothing happened, and `agree` would compare the world's
demand against zeroes. Law 11 (the world is never written) has this face too:
the heap is the only allocator in the room, and `heap.allocate` returning ids
the stage stores in slots is the whole mechanism the later collectors trace.


TODO: implement the functions this stage names; the docstrings above are the contract.
"""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS

HEAP_KEYS = ('output', 'steps', 'ledger')

HEAP_PROGRAMS = ('conslist', 'shared', 'cycle')


def demand_of(name):
    """The heap demand `PROGRAMS` pins for `name`: `{shape: count}`, as a
    fresh dict — a name that is not a heap program refuses, naming it."""

    raise NotImplementedError("stage 4: implement demand_of()")


def build(name, heap):
    """The program's shape, built on the provided heap; answers the output.

    `conslist` is the list 1 -> 2 -> 3 (pair holds value-box, next-pair)
    summed; `shared` is two parents over one child over a tail; `cycle` is
    a -> b -> a with both rooted. Every object through `heap.allocate`, every
    reference a slot or a root, every value a box's immutable payload."""

    raise NotImplementedError("stage 4: implement build()")


def run_with_heap(name, heap):
    """The program run against the heap: build, sum, and answer the record.

    Answers `HEAP_KEYS` — the program's output, the steps this runtime spent
    (the stage's own accounting; the world pins no step total here), and the
    ledger as `heap.stats()` answered it after the build."""

    raise NotImplementedError("stage 4: implement run_with_heap()")


def agree(program, heap):
    """Whether the heap's live objects agree with the program's demand: True
    only when every demanded shape's live count is exactly the demand's —
    no shape over-built, none under."""

    raise NotImplementedError("stage 4: implement agree()")
