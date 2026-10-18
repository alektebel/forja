"""Runtime From Scratch — stage 1: The dispatch: decode, execute, count.

A bytecode is a tuple of (opcode, operand) pairs and a runtime is the loop that
walks it: read the pair at `ip`, do what the opcode says to the value stack,
answer the next `ip`. This stage is that loop and nothing else — no heap, no
frames, no collection — because the three questions every later stage answers
(how long did it run, what did it leave, who did it touch) are asked here first,
against programs the world already knows the answer for.

The discipline the stage encodes is the LC-3's, in the tutorial's own words:
fetch, decode, execute, and the machine state as the only truth. `decode` is a
boundary check with the mnemonic attached (the world's `OP_NAMES` is what an
error message is made of); `execute` applies one opcode and answers where the
instruction pointer goes next; `run` is the loop with the step counter — the
counter is not decoration, because the world measured every provided program's
step count with its own reference loop, and a runtime that counts differently
has a different loop. Nothing here allocates: the heap programs of `PROGRAMS`
are shapes, not bytecode, and the stages that build the allocator will meet them
when the allocator exists.

DESIGN DECISION — Why does `execute` answer the next `ip` instead of mutating it?
Because the loop is the only place a jump is legal, and a jump is a decision
about `ip`, not about the stack. If `execute` answered nothing, every opcode
would have to know the loop's variable, and `JUMP` would either mutate a mutable
loop-local through a parameter (a second convention for one thing) or the loop
would special-case the jumps (a second dispatch table). One answer — the next
`ip` — makes every opcode a pure function of (module, op, arg, stack), which is
also exactly what the reference loop's semantics are, so the stage and the world
can disagree only where one of them is wrong.

DESIGN DECISION — Why does the step counter count every dispatch, HALT included?
Because the world's reference loop counts that way (`assembler.run_steps`), and
the pins in `PROGRAMS[...]["steps"]` — 6 for `arith`, 7 for `branch`, 31 for
`countdown`, 129 for `fib10` — were measured with that rule. Counting anything
else (say, excluding the HALT, or counting a taken branch twice) makes every
total wrong by a constant the stage did not choose, and the check's assertion
`steps == PROGRAMS[name]["steps"]` would read as an off-by-one instead of what
it is: a different loop.

DESIGN DECISION — Why does `run` refuse a runaway instead of looping forever?
Because the world refuses one (`run_steps` raises past `limit`), for the reason
that matters here: an infinite loop in a *provided* program is a bug in the
world, not something a runtime waits out. A student runtime that silently hangs
on `JUMP` with a wrong target has lost the loop; one that raises
`BytecodeError("runaway ...")` names the loss. The limit is a parameter with the
world's own default, so a later stage that wants a different budget states it
instead of editing this one.

DESIGN DECISION — Why are the frame operations not implemented here?
Because stage 1 has no frames: `CALL` and `RETURN` need a frame stack, and
`LOAD_NAME`/`STORE_NAME` need a scope the loop does not have. The world's
reference loop refuses them by name, and so does this stage — refusing is the
honest answer, and it is what keeps stages 1–3 provably frame-free until stage
2's step arithmetic and stage 3's control flow are done on programs that need
nothing but a value stack.


TODO: implement the functions this stage names; the docstrings above are the contract.
"""

import bytecode as bc

DISPATCH_KEYS = ('stack', 'output', 'steps')

RUNNABLE = ('arith', 'branch', 'countdown', 'fib10')

FRAME_OPS = (bc.OP_LOAD_NAME, bc.OP_STORE_NAME, bc.OP_CALL, bc.OP_RETURN)


def decode(module, ip):
    """The (opcode, operand) pair at `ip`, checked.

    `ip` past the code is a caller's mistake and raises `BytecodeError` naming
    the index and the module's length; a pair whose opcode the ISA does not
    name is a broken module and raises naming the number (the ISA is closed,
    so an unnamed opcode is nobody's operand)."""

    raise NotImplementedError("stage 1: implement decode()")


def execute(module, op, arg, stack):
    """One opcode applied to the value stack, in place; answers the next `ip`.

    The arithmetic is the world's own (`a OP b` with `a` the deeper operand);
    `JUMP` answers `arg`, `JUMP_IF_FALSE` pops and answers `arg` only when the
    value was falsy; `HALT` answers the `ip` the loop reads as stop. A frame
    operation raises `BytecodeError` naming the mnemonic — this stage has no
    frames — and `PICK` past the stack's bottom raises naming the depth."""

    raise NotImplementedError("stage 1: implement execute()")


def run(module, limit=10000):
    """The whole loop: dispatch from `module.entry` until `OP_HALT`.

    Answers `{"stack", "output", "steps"}` — the final stack, the output tuple
    it makes, and the number of dispatches (one per instruction executed,
    `HALT` included). Past `limit` steps it raises `BytecodeError`, because an
    infinite loop is a bug in the program and the runtime says so rather than
    waiting it out."""

    raise NotImplementedError("stage 1: implement run()")
