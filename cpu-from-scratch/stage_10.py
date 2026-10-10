"""CPU From Scratch — stage 10: the measurement, the CPI and the two machines.

One program, two machines, one result. This stage does not build a machine: it
weighs the two that stages 6 and 9 built and refuses to call a faster machine
faster unless it computed the same thing.

DESIGN DECISION — why is the report's key set frozen and closed?
    Rejected: a free-form dict an implementation may extend (`status`, `notes`,
    a convenience field). The cost is that two reports stop being comparable: a
    downstream tool cannot index a key it has never seen, and a typo (`cpi` for
    `CPI`) becomes a measurement that is silently absent rather than a mistake
    that is loudly refused. A frozen tuple is the interface; the dict is data.

DESIGN DECISION — why does `measure` run both machines, not just the pipeline?
    Rejected: derive `single_cycles` from `retired` and set `equivalent = True`
    by construction. The cost is that the equivalence claim becomes vacuous: the
    exact bug this whole course is about — a faster machine that computes
    something else — can no longer be detected, because nothing ever compares
    the two results. `equivalent` is only worth reporting if it is computed.

DESIGN DECISION — why are the fingerprints, not the traces, the compared thing?
    Rejected: compare the architectural traces (they are already tuples).
    The cost is a false pass: two machines can retire the same instruction
    history and still end in different registers or in different memory — a
    store that landed at the wrong address, a load that read a stale value. The
    fingerprint folds status, fault, pc, registers and a hash of the data memory
    into one comparable tuple, which is what "the same result" has to mean.

DESIGN DECISION — why round every float at DP, and why refuse a zero-retirement run?
    Rejected: return the raw quotient. The cost of raw floats is binary noise:
    a CPI of `0.30000000000000004` prints a precision no measurement has, and
    two reports that describe the same machine compare unequal. And a CPI over
    zero instructions is a division by zero dressed up as a number — a program
    that retires nothing has no cycles to divide.

DESIGN DECISION — why is `stalls` returned as a fresh dict?
    Rejected: hand back the pipeline's own live `stalls` dict. The cost is that
    the report and the machine become one object: a caller who annotates a stall
    in the report silently rewrites the machine's counter, and any later user of
    that machine reports the edited counts. Counters leave the machine as data,
    the same way the register snapshot does.

DESIGN DECISION — why does a run that never halts raise instead of reporting?
    Rejected: return whatever the pipeline retired when the cycle cap was hit.
    The cost is the worst kind of wrong number: a program that never halts has
    no CPI, and reporting the cycles of a truncated run as if they were the
    program's cost is the measurement equivalent of the faster-machine bug. With
    a `max_cycles` cap the run stops with `status == "budget"`; `measure` refuses
    it and names that status instead of returning a partial success.

TODO: implement `measure` and `compare`.
"""

import isa
from stage_06 import run
from stage_07 import fingerprint, load
from stage_08 import Pipeline, run_pipeline
from stage_09 import ForwardingPipeline, run_forwarding


#: every float in a report is rounded to this many decimal places
DP = 6

#: the exact keys of a measurement report, in order
REPORT_KEYS = ("program", "retired", "single_cycles", "pipeline_cycles", "cpi",
               "stalls", "speedup", "equivalent")


def measure(program, *, data_size=4096, forwarding=True, max_cycles=None):
    """Run one program on the pipeline and report its CPI and stalls.

    `program` is a name from `isa.PROGRAMS` or inline source text. The pipeline
    is the forwarding machine (`stage_09`) when `forwarding` is true, otherwise
    the stalls-only machine (`stage_08`). Returns a dict with exactly
    `REPORT_KEYS`. Refuses a run that retires nothing, or that does not halt
    (a budget or fault `status`), with `ValueError`.
    """
    raise NotImplementedError("stage 10: implement measure()")


def compare(program, *, data_size=4096):
    """Run a program on both machines and report the one result they share.

    Returns `measure`'s dict for the forwarding machine plus the two machines'
    fingerprints under `"single"` and `"pipeline"`. Raises `ValueError` if the
    two machines are not equivalent: a faster machine that computes something
    else is not a faster machine.
    """
    raise NotImplementedError("stage 10: implement compare()")
