"""Runtime From Scratch — stage 3: Control flow: the jumps, and a program's
step total.

Stage 2 owned the semantics of one opcode at a time; this stage owns the
*decisions* — which instruction runs next when the answer is not simply the
next one. A jump is where a runtime's determinism is most visible: the target
is a number in the code, the condition is a value on the stack, and the same
program on the same input takes the same path every time, which is why the
world's step pins are assertable at all.

The stage's second subject is the *reasoning* about those decisions:
`branch_taken` answers whether the instruction at an `ip` jumps without
executing anything — the question a loop unroller, a tracer or an audit asks —
and `step_totals` is the table that says what every frame-free program costs.
The totals are the world's own numbers (law 13), and this stage is the one that
has to explain them: `branch`'s taken path and skipped path differ, `countdown`
is a loop whose cost is per-iteration arithmetic, and `fib10`'s 129 dispatches
are the shuffle's price.

DESIGN DECISION — Why is `branch_taken` a question about an `ip` and not a
simulator?
Because the answer must not depend on state the question does not name. A
simulator that runs the program to "see" whether a branch is taken has changed
the heap, the ledger and the step count as a side effect of asking; a function
that reads the module's code and the stack it is *given* answers without
touching either. The later audit stage (§4.10) re-reads records against the
ledger, and it needs questions that cost nothing to ask.

DESIGN DECISION — Why does `run_control` exist alongside stage 1's `run`?
Because stage 3 composes stage 2's semantics with the jumps, and the check has
to prove the composition — a `JUMP_IF_FALSE` whose condition was already
consumed by stage 2's semantics, a loop whose back-edge skips the counter —
without re-running the stage-1 loop that would mask the bug behind the same
answer. `run_control` is the same loop with the stage's own jump handling; when
its totals land on the world's pins, the pins prove both stages at once, and a
mutation in either is caught by the same number.

DESIGN DECISION — Why is `OP_LOOP` in the stage's surface as a separate name?
Because it is not, semantically, a different jump — and that is the fact worth
asserting. The world defines it as `JUMP`'s sibling (§2.1: "like JUMP, but the
counted-jump a loop back-edge emits"), and the step count cannot tell them
apart unless the runtime treats them identically. A stage that gave `OP_LOOP`
its own semantics has invented a machine the world's pins do not describe.


TODO: implement the functions this stage names; the docstrings above are the contract.
"""

import bytecode as bc
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_02 import step as _step

JUMPS = (bc.OP_JUMP, bc.OP_JUMP_IF_FALSE, bc.OP_LOOP)


def branch_taken(module, ip, stack):
    """Whether the instruction at `ip` jumps, given the stack as it stands.

    Answers None for an instruction that is not a jump; for `JUMP` and `LOOP`,
    True (they always do); for `JUMP_IF_FALSE`, what the value on top would
    decide — the value is read, not popped. An `ip` past the code refuses,
    exactly as `decode` refuses."""

    raise NotImplementedError("stage 3: implement branch_taken()")


def run_control(module, limit=10000):
    """The composed loop: stage 2's semantics plus this stage's jumps.

    Answers stage 1's `DISPATCH_KEYS` — the final stack, the output, and the
    step count that has to land on the world's pin for every frame-free
    program. Past `limit`, refused."""

    raise NotImplementedError("stage 3: implement run_control()")


def step_totals(names):
    """Each named program's step total, by name, from this stage's own loop.

    `names` is an iterable of `PROGRAMS` keys; the answer is a dict with those
    keys and each program's steps — and a name that is not in `PROGRAMS`
    refuses, naming it."""

    raise NotImplementedError("stage 3: implement step_totals()")
