"""CPU From Scratch — stage 6: the machine and the control unit

DESIGN DECISION — why is a fault data and not an exception?
    A Python exception unwinds out of `step`, so a run over a faulting program
    dies at the first bad address and there is nothing left to compare. Every
    equivalence later in the course (the pipeline retires the same trace, the
    two machines one result) compares `(status, fault, trace)` tuples, and a
    traceback is not one of those. A recorded fault also gives "a faulted
    machine's further steps are no-ops" a meaning: the state is a result, and a
    result does not change when you look at it again.
    Rejected: raising from `step` and letting the caller catch it. Cost: the
    checker holds two machines, one of which raised — the equivalence the whole
    course exists to assert is exactly the case it cannot express.

DESIGN DECISION — why is the program a tuple separate from the data memory?
    The ISA is Harvard: instructions are words indexed by `pc`, data is bytes
    indexed by an address. A single byte-addressed memory holding both would
    make a stray `sw` overwrite an instruction, make the trace depend on the
    data (self-modifying code the course never tests), and turn "a store cannot
    rewrite the program" from a structural fact into a lucky choice of address.
    A tuple cannot be written: the property is a type, not an assertion.
    Rejected: one flat bytearray for instructions and data. Cost: the check that
    a `sw` leaves the program alone becomes a hope about the address stored to,
    and the pipeline's IF and MEM stages touch the same bytes.

DESIGN DECISION — does a retired `halt` move the pc, and does a faulting
instruction retire?
    `pc` means one thing everywhere: the address of the *next* instruction to
    fetch. A `halt` is fetched, decoded and executed like any other word, so it
    retires — one cycle, one trace row, `writes == ()` — and the pc advances
    past it; only then does the status become `"halted"`. A faulting instruction
    is the converse: it does not retire, does not advance the pc, and leaves
    the machine stopped *at* the bad word with `status == "faulted"` and the
    fault naming that pc. If a halted machine's pc pointed at its own `halt`,
    `pc` would mean "the instruction that just ran" for that one case and "the
    next instruction" everywhere else, and two machines comparing traces would
    disagree about where the program ended — or whether the bad instruction ran.
    Rejected: not retiring the `halt`, or retiring the faulting instruction.
    Cost: the trace's last row disappears, or an instruction that never
    executed shows up in it; the pipeline's trace equality in stage 8 then
    needs a special case for exactly the two instructions that matter.

DESIGN DECISION — why does a write to r0 still retire and get traced?
    `r0` is hardwired to zero, so `add zero, t0, t1` has no effect — but it is
    still a fetched, decoded, executed word. Dropping its retirement would make
    the trace a pc sequence with holes, and the pipeline, which must retire the
    *same* trace, would have to reproduce the hole; the number of instructions
    a program retires would depend on which of them wrote r0. The instruction
    retires with `writes == ()`: it happened, it changed nothing.
    Rejected: skipping retirement and the trace row for an rd of 0. Cost: two
    machines disagree about the length of the same program, and the trace stops
    being the list of instructions that ran.

DESIGN DECISION — why does the `max_steps` stop leave `status == "budget"`?
    An infinite loop is not a hardware fault: the program is fine and the
    machine is fine, it just did not finish. If the cap were a fault, a check
    could not tell "the machine broke" (a bad address, a zero divisor) from
    "the machine did not finish", and the only way to test a non-terminating
    program would be to hang the process. `run` stops, records why, and leaves
    `fault is None` — a budget stop is a decision, not a failure.
    Rejected: raising on the step cap, or folding it into `fault`. Cost: a
    check for the infinite `jmp` loop either crashes or times out, and the
    distinction the course needs — faulted vs. unfinished — is gone.

DESIGN DECISION — why does `snapshot()` copy the registers and the memory?
    `Machine.snapshot()` is how two machines are compared, and comparing a
    machine with itself always succeeds. If the snapshot held the live register
    file and the live memory, every equivalence assertion in stages 8-10 would
    be vacuously true. This is the aliasing bug stage 3 names for
    `RegisterFile.snapshot()`, one level up: a snapshot is a value, so it is a
    copy, and mutating it cannot reach back into the machine.
    Rejected: returning the live `registers`/`memory` objects. Cost: the
    "two machines, one result" spine reads as passing while testing nothing.

TODO: implement `Machine`, `step`, `run` and `reset`.
"""

from collections import namedtuple

import isa

#: every way an instruction can fail. `"illegal"` is an unknown opcode,
#: `"arith"` a division or remainder by zero, `"address"` a data access the
#: memory refuses, and `"fetch"` a pc outside the program.
FAULT_KINDS = ("illegal", "arith", "address", "fetch")

#: the states a machine can be in: `"running"` is the only one `step` acts in;
#: `"halted"` means the program ran to its `halt`; `"faulted"` means it failed
#: and `fault` explains it; `"budget"` means a step cap was reached.
STATUSES = ("running", "halted", "faulted", "budget")

#: what went wrong, as data: the kind (one of `FAULT_KINDS`), the pc that was
#: executing when it happened, and a detail that names the word, address or
#: divisor.
Fault = namedtuple("Fault", "kind pc detail")

#: one retired instruction: where it was, the word, how it reads, and its
#: effects in execution order — `("r", index, value)` for a register write and
#: `("m", address, size, value)` for a store.
TraceRow = namedtuple("TraceRow", "pc word text writes")


class Machine:
    """A single-cycle machine: one instruction per cycle, in program order.

    The architectural state is ``registers`` (a `stage_03.RegisterFile`),
    ``memory`` (a `stage_05.Memory`), ``pc``, ``status`` and ``fault``. A run
    adds ``cycles`` and ``retired`` (equal here: the cycle model is one
    instruction per cycle) and ``trace``. ``program`` is a tuple of words and
    never changes; ``initial`` is the register mapping a `reset` restores.

    ``initial`` seeds the register file: a mapping of register name or index to
    value, or a sequence of sixteen values; ``None`` means all zeros. It is how
    a program's inputs get in — the catalogue's programs read ``a0`` (and
    ``a1``/``a2`` for ``memcpy``) and write ``v0``.
    """

    def __init__(self, program, *, data_size=4096, pc=0, initial=None):
        """A machine ready to run ``program`` from word ``pc``."""
        raise NotImplementedError("stage 06: implement Machine()")

    @property
    def program(self):
        """The program's words — a tuple, immutable by construction."""
        raise NotImplementedError("stage 06: implement Machine.program()")

    def snapshot(self):
        """A copy of the whole architectural state, safe to keep and compare."""
        raise NotImplementedError("stage 06: implement Machine.snapshot()")


def step(machine):
    """Fetch, decode and execute one instruction at ``machine.pc``.

    Sets ``status``/``fault`` instead of raising when the instruction faults,
    and does nothing at all once the machine is not running.
    """
    raise NotImplementedError("stage 06: implement step()")


def run(machine, *, max_steps=None):
    """Step until the machine halts, faults, or ``max_steps`` is reached.

    Reaching the cap leaves ``status == "budget"``; returns the machine.
    """
    raise NotImplementedError("stage 06: implement run()")


def reset(machine):
    """Return ``machine`` to its initial architectural state, counters zeroed."""
    raise NotImplementedError("stage 06: implement reset()")
