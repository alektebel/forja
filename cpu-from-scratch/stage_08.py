"""CPU From Scratch — stage 8: the five-stage pipeline, correct and slow.

DESIGN DECISION — why stalls instead of forwarding, in this stage?
    Forwarding is the next stage, and a pipeline that forwards needs the pipeline
    to be right first. So here any instruction whose source register is written
    by an instruction still in the pipeline stalls in ID until the write is in
    the register file. The rejected alternative — reach for forwarding now — costs
    the lesson: with forwarding in place a load-use hazard produces a *wrong
    value* instead of a stall, because a load's data does not exist until MEM and
    no forwarding path can invent it, and that wrong value surfaces far from the
    hazard that caused it. Correct and slow is a baseline stage 9 can measure
    against; correct and fast must earn its cycles.

DESIGN DECISION — why is a control instruction resolved in EX, and its younger
fetches squashed AND counted?
    A branch or jump does not know its target until its operands are read, which
    happens in EX. The instructions fetched behind it are on a path that may not
    be the one taken, so when the control resolves taken they are squashed: they
    must not retire, or the pipeline has computed something the single-cycle
    machine did not. The rejected alternative — assume not-taken, or resolve in ID
    — costs correctness (a taken branch's two younger fetches retire on the wrong
    path) and costs the accounting (the cycles spent fetching them vanish, so
    `cycles == retired + 4 + stalls` stops holding and stage 10's CPI becomes a
    number nobody can check).

DESIGN DECISION — why must every architectural effect equal the single-cycle
machine's, not just its final registers?
    The thesis of the course is one program, two machines, one result. The
    rejected alternative — compare only the final register file and memory — costs
    every bug that leaves the answer right by accident: a pipeline that squashes
    the older instruction instead of the younger one, or writes a register at EX
    so a later instruction reads a value one cycle early, still lands on the same
    final state in an easy program. The `trace` (the order of retirements and the
    effects each one had) and the `fingerprint` are what catch it, so the check
    compares them, and stage 9 has to keep them identical too.

DESIGN DECISION — why is a fault data here, exactly as in stage 6?
    A faulting instruction does not retire: its pc stays on it, its row never
    enters the trace, and `status` becomes `"faulted"`. The rejected alternative —
    raise the fault through `step_pipeline` — costs the same thing it costs the
    single-cycle machine: the run dies at the first bad address instead of
    reporting a fault, no two fingerprints compare, and the fault's kind is lost
    at the one moment it was the answer. Instead the pipeline drains the older
    instructions that had already retired in the single-cycle machine, then stops.

DESIGN DECISION — why is the load's value read at MEM, and a register written at
WB?
    The stages exist to be observable. A load that read its data at EX would
    collapse the load-use hazard into a silent wrong answer; a register written at
    EX would let the very next instruction read it a cycle early, which is the
    difference between a pipeline and a pile of stages. The rejected alternative
    in both cases — do the work at the earliest stage that can — costs exactly the
    hazard this course is about, so memory is touched at MEM and the register file
    is written at WB, and nothing else.

DESIGN DECISION — why does the cycle identity hold for a faulted run too?
    `cycles == retired + 4 + stalls` counts fill, drain, and lost cycles. A
    faulting instruction aborts at its stage, but the older instructions still in
    flight drain and retire, and the pipeline stops the moment the last of them
    does — so the same four cycles of fill that a completed run pays are paid, and
    the identity survives. The rejected alternative — stop the instant the fault is
    detected — costs the identity and, worse, drops retirements the single-cycle
    machine made, so the two traces no longer compare.

TODO: implement `Pipeline`, `retire`, `step_pipeline` and `run_pipeline`.
"""

from stage_06 import Fault, TraceRow

#: The five stages, entry first: an instruction enters IF and retires at WB.
STAGES = ("IF", "ID", "EX", "MEM", "WB")

#: Every stall cause the pipeline reports, zero-filled and always present.
#: "data" is a dependency stall, "control" the cycles a jump or branch loses;
#: "load_use" belongs to stage 9's forwarding machine and stays zero here.
STALL_CAUSES = ("data", "load_use", "control")


class Pipeline:
    """A five-stage in-order pipeline with stalls instead of forwarding.

    The architectural surface is stage 6's `Machine` — `registers`, `memory`,
    `pc`, `status`, `fault`, `cycles`, `retired` and a `trace` of the same
    `TraceRow`s — plus `stalls`, the counts of the cycles lost by cause. A
    pipeline is built from a program (a tuple of words), a data-memory size, a
    starting pc and an optional register seed, exactly as the machine is.
    """

    def __init__(self, program, *, data_size=4096, pc=0, initial=None):
        raise NotImplementedError("stage 8: implement Pipeline()")

    def snapshot(self):
        """The whole architectural state, as copies (never the live objects)."""
        raise NotImplementedError("stage 8: implement Pipeline.snapshot()")

    def reset(self):
        """Back to the architectural state the pipeline was built with."""
        raise NotImplementedError("stage 8: implement Pipeline.reset()")


def retire(pipeline):
    """Write back and trace the instruction at WB, and count it as retired.

    Internal, but named, because the checks read a retired row and the counters
    from here: the effects are applied in the order the row records them, the
    trace row is `TraceRow(pc, word, text, writes)`, and `halt` moves the machine
    to `"halted"` after retiring and advancing past itself.
    """
    raise NotImplementedError("stage 8: implement retire()")


def step_pipeline(pipeline):
    """One cycle, processed in stage order WB to IF, and then latched.

    A write at WB lands in the register file before this cycle's decode reads it,
    so a producer one stage ahead of a consumer needs no stall; a producer still
    in EX or MEM does, and the consumer waits in ID while the older instructions
    retire. A taken control in EX squashes the instructions in ID and IF and
    redirects the pc.
    """
    raise NotImplementedError("stage 8: implement step_pipeline()")


def run_pipeline(pipeline, *, max_cycles=None):
    """Step until halted or faulted and drained, or until the cycle cap is hit.

    A run that reaches `max_cycles` while still running stops with status
    `"budget"`; a run that drains after a fault stops with status `"faulted"`.
    """
    raise NotImplementedError("stage 8: implement run_pipeline()")
