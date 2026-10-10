"""CPU From Scratch — stage 10: the measurement, the CPI and the two machines.

The reasoning behind every choice here lives in the template's docstring
(`stage_10.py`); this file is the finished version of that lesson.
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


def _source(program):
    """`(label, source text)` for a catalogue name or an inline program."""
    if not isinstance(program, str):
        raise ValueError("measure: program must be a name or source text, got %s"
                         % (type(program).__name__,))
    if program in isa.PROGRAMS:
        return program, isa.PROGRAMS[program]
    return "<source>", program


def _measured(source, data_size, max_cycles):
    """The single-cycle machine's (stage 6) run of a program."""
    machine = load(source, data_size=data_size)
    run(machine, max_steps=max_cycles)
    return machine


def _pipelined(source, data_size, forwarding, max_cycles):
    """The pipeline's run of a program: forwarding or stalls-only."""
    program = isa.assemble(source)
    if forwarding:
        machine = ForwardingPipeline(program, data_size=data_size)
        run_forwarding(machine, max_cycles=max_cycles)
    else:
        machine = Pipeline(program, data_size=data_size)
        run_pipeline(machine, max_cycles=max_cycles)
    return machine


def _halted_or_raise(label, single, pipeline):
    """Refuse a run there is nothing to measure in, whatever the reason."""
    if single.retired == 0:
        raise ValueError("measure: %s retires nothing; a CPI over zero "
                         "instructions is not a number" % (label,))
    if single.status != "halted" or pipeline.status != "halted":
        raise ValueError("measure: %s did not halt (single=%s, pipeline=%s); a "
                         "program that never halts has no CPI, not a partial "
                         "report" % (label, single.status, pipeline.status))


def _report(label, single, pipeline, equivalent):
    """The report dict: exactly `REPORT_KEYS`, every float rounded to `DP`."""
    retired = single.retired
    cycles = pipeline.cycles
    return {
        "program": label,
        "retired": retired,
        "single_cycles": retired,
        "pipeline_cycles": cycles,
        "cpi": round(cycles / retired, DP),
        "stalls": dict(pipeline.stalls),
        "speedup": round(retired / cycles, DP),
        "equivalent": equivalent,
    }


def measure(program, *, data_size=4096, forwarding=True, max_cycles=None):
    """Run one program on the pipeline and report its CPI and stalls."""
    label, source = _source(program)
    single = _measured(source, data_size, max_cycles)
    pipeline = _pipelined(source, data_size, forwarding, max_cycles)
    _halted_or_raise(label, single, pipeline)
    equivalent = fingerprint(single) == fingerprint(pipeline)
    return _report(label, single, pipeline, equivalent)


def compare(program, *, data_size=4096):
    """Run a program on both machines and report the one result they share."""
    label, source = _source(program)
    single = _measured(source, data_size, None)
    pipeline = _pipelined(source, data_size, True, None)
    _halted_or_raise(label, single, pipeline)
    single_fingerprint = fingerprint(single)
    pipeline_fingerprint = fingerprint(pipeline)
    if single_fingerprint != pipeline_fingerprint:
        raise ValueError("compare: %s is not equivalent; the pipeline computed a "
                         "different result from the single-cycle machine"
                         % (label,))
    report = _report(label, single, pipeline, True)
    report["single"] = single_fingerprint
    report["pipeline"] = pipeline_fingerprint
    return report
