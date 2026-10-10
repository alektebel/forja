"""CPU From Scratch — stage 9: forwarding, the load-use stall, the branch flush

DESIGN DECISION — why is the MEM/WB latch not a forwarding source?
    A textbook bypass forwards from both the EX/MEM and the MEM/WB pipeline
    register, and the second one is redundant here and dangerous. WB writes the
    register file at the start of the cycle, before ID reads it, so by the time a
    consumer reaches EX the two-cycle-old value is already in its register; a
    bypass from MEM/WB would therefore only ever fire when the register file is
    *fresher*, and it would overwrite that fresh value with the stale one. The
    bug is invisible until a program writes the same register twice within two
    instructions — the second write is silently replaced by the first. One source
    (EX/MEM: an ALU op's EX result, a load's MEM result) is enough, and it cannot
    go stale.

DESIGN DECISION — why does a load still cost exactly one cycle?
    A `lw`/`lb` has no value until it has passed MEM, so an instruction right
    behind it would read the arithmetic result of the address computation if we
    forwarded from EX, or a stale register if we did not forward at all. It
    stalls in ID for one cycle: by the time it reaches EX the load is in WB and
    has written the register file. Waiting, as stage 8 does, until the write is
    visible costs two cycles here and one, so the load-use case stalls exactly
    once — the count is a fact about the datapath, not a tuning knob.

DESIGN DECISION — why is a control resolved in EX and its two younger fetches
squashed?
    Jumps and branches could be resolved in ID (the target is an immediate, and
    `jz` needs one register) and the fetches behind them thrown away a cycle
    earlier, but that moves an operand comparator and its forwarding path into
    ID and makes every instruction whose operand is a compare stall there — a
    price paid on every cycle to save two in a loop. Resolving in EX keeps the
    hazard logic in one place; the cost is that the two fetches already in ID and
    IF are wrong, and they are dropped rather than retired, which is exactly why
    the architectural trace ends up identical to the single-cycle machine.

DESIGN DECISION — why must the trace be unchanged, and not merely the result?
    The cycle model is exact, so a faster machine is easy to claim and hard to
    prove. This course's thesis is the opposite: a machine that computes
    something else is not a faster machine, whatever its CPI. The acceptance is
    therefore run on the *architectural* output — the same `trace` and
    `fingerprint` as stage 6's `Machine` and stage 8's `Pipeline` — and only then
    does the cycle count mean a speedup at all.

DESIGN DECISION — why does `ForwardingPipeline` subclass stage 8's `Pipeline`
instead of wrapping one?
    A wrapper would hold a slow `Pipeline` and a forwarding control unit, and the
    two would each own a register file, a memory and a trace — two copies of the
    architectural state that can drift, which is the one thing this stage must
    not produce. Subclassing shares the machine's name and surface; the faster
    cycle is written out in full, so the forwarding rules and the stall rules sit
    in the same function and can be read against each other.

TODO: implement `ForwardingPipeline`, `forward_operands`, `step_forwarding` and
`run_forwarding`.
"""

import isa
from stage_02 import decode, disassemble, registers
from stage_04 import ALU_OPS, alu
from stage_05 import Memory
from stage_06 import Fault, TraceRow
from stage_08 import Pipeline, STAGES

#: The stall causes every pipeline counts, always all present: a dependency a
#: bypass could not cover (`"data"`, zero under forwarding), the one-cycle wait a
#: load forces (`"load_use"`), and the cycles a control costs (`"control"`).
STALL_KEYS = ("data", "load_use", "control")


class ForwardingPipeline(Pipeline):
    """The five-stage pipeline with forwarding, the load-use stall and the
    branch flush — the same architectural state as stage 6's `Machine` and stage
    8's slow `Pipeline`, at fewer cycles."""

    def __init__(self, program, *, data_size=4096, pc=0, initial=None):
        """A pipeline on `program`, with `data_size` bytes of zeroed data memory,
        the counter at `pc`, and the registers seeded by `initial` (a mapping of
        name/index to value, or sixteen values; `r0` stays 0)."""
        raise NotImplementedError("stage 9: implement ForwardingPipeline()")

    def program(self):
        """The program's words — a tuple, immutable by construction."""
        raise NotImplementedError("stage 9: implement ForwardingPipeline.program()")

    def snapshot(self):
        """A copy of the architectural state plus the pipeline counters."""
        raise NotImplementedError("stage 9: implement ForwardingPipeline.snapshot()")


def forward_operands(pipeline):
    """The `(a, b)` the EX stage uses, after the forwarding bypass.

    The operands are read from the register file and then overwritten by the
    instruction one stage ahead in EX/MEM — its EX result, or a load's MEM
    result. The MEM/WB latch (WB) is never a source; see the template.
    """
    raise NotImplementedError("stage 9: implement forward_operands()")


def step_forwarding(pipeline):
    """Run one cycle of the forwarding machine, in stage order WB -> IF."""
    raise NotImplementedError("stage 9: implement step_forwarding()")


def run_forwarding(pipeline, *, max_cycles=None):
    """Cycle until the machine halts or faults, or `max_cycles` is reached (the
    machine is then left in status `"budget"`)."""
    raise NotImplementedError("stage 9: implement run_forwarding()")
