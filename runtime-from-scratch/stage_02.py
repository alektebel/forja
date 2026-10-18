"""Runtime From Scratch — stage 2: The value stack, and what each opcode costs.

Stage 1 applied opcodes as they came; this stage owns the *semantics table* —
one function per opcode family, the value stack as the only state, and the
accounting that turns a program's shape into its step total. The distinction
matters because the later collectors read the stage's records as data: a check
that wants to prove a runtime asked for nothing it did not need needs the
semantics split from the loop, so a mutation in the loop cannot hide inside the
semantics or the other way round.

The boundary this stage pins is the stack itself: an arithmetic op with too few
operands is a refusal naming the mnemonic, a `PICK` past the bottom is a refusal
naming the depth, and `steps_of` is the stage's own arithmetic reproducing the
world's measured totals before stage 3 composes them into control flow.

DESIGN DECISION — Why one `step` function over a table of per-opcode handlers?
Because the world's reference loop is one dispatch chain (`if op == ... elif
...`), and every difference between this stage's semantics and the reference's
is a disagreement about a fact the world already measured. A handler table
would let each opcode drift into its own helper with its own conventions; one
function keeps them side by side where an ordering mistake (`a OP b` vs
`b OP a`) is visible as the next line instead of a file apart.

DESIGN DECISION — Why does `step` mutate the stack in place and answer None?
Because the loop owns the instruction pointer and the stack is the executed
state, not a returned intermediate. A `step` that answered a new stack would
make the loop copy it per dispatch (an allocation per step the reference loop
does not make, and the step counts would still have to match it), and would
leave the answer-carrying opcodes (the jumps, stage 3's subject) with no room
to answer anything else. In-place with `None` is what makes `execute`'s answer
(the next `ip`) the only answer a dispatch produces.

DESIGN DECISION — Why is `steps_of` a separate surface and not `run(...)["steps"]`?
Because stage 3 composes this stage's arithmetic with control flow, and what it
needs from stage 2 is the *cost of a module's straight line* — the number a
stage-3 loop has to reproduce before any jump changes it. A stage that reached
into `run`'s record for it would depend on the loop, not the semantics, and the
mutation battery for stage 3 would then have to distinguish a loop bug from a
semantics bug through one record instead of two.


TODO: implement the functions this stage names; the docstrings above are the contract.
"""

import bytecode as bc
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS

ARITH = (bc.OP_ADD, bc.OP_SUB, bc.OP_MUL, bc.OP_NEG, bc.OP_EQ, bc.OP_LT,
         bc.OP_GT, bc.OP_NOT)

STACK_OPS = (bc.OP_POP, bc.OP_DUP, bc.OP_PICK, bc.OP_ROT3)


def step(module, op, arg, stack):
    """One opcode's semantics on the value stack, in place.

    Answers None (the loop owns `ip`; stage 3's control flow is where an answer
    begins). An `ARITH` op with too few operands raises `BytecodeError` naming
    the mnemonic; a `PICK` past the bottom raises naming the depth; a frame
    operation raises naming it, exactly as stage 1 refuses them."""

    raise NotImplementedError("stage 2: implement step()")


def steps_of(module, limit=10000):
    """The step total of `module`: dispatch until `HALT`, counting every
    dispatch, `HALT` included — the stage's own arithmetic, which must land on
    the world's measured pin for every frame-free program."""

    raise NotImplementedError("stage 2: implement steps_of()")
