"""CPU From Scratch — stage 7: the program, and the record of what it did

DESIGN DECISION — why is `load` a loader and not a runner?
    A load that also runs hands back a machine whose history is already spent:
    the caller cannot single-step the first instruction, cannot stop it at the
    fault, and cannot ask what the program *was* before it changed the machine.
    The rejected alternative — `load` assembles, runs and returns the finished
    machine — buys one saved call and costs every check that wants to observe a
    machine mid-flight (the trace's boundary, the fault's pc, the budget stop).
    `load` ends where the interesting part begins: assembled words in a machine
    at its starting pc, with `run` (stage 6) left to spend the history.

DESIGN DECISION — why does `trace` reduce a retired row to `(pc, word)`?
    Stage 6 already records a `TraceRow` per retired instruction — pc, word,
    text, writes — because the pipeline stages need the effects. But the trace
    that two machines must agree on is the *architectural* one: which
    instructions ran, and at what pc. Keeping the disassembly text and the
    effect tuples in the comparison would make the check compare the record's
    formatting instead of the computation, and the `writes` of a store carry a
    value the load-use hazard can legitimately produce at a different cycle.
    Rejected alternatives both fail the same way: returning the `TraceRow`s
    themselves (a comparison that grows with the program), and rebuilding the
    trace from `machine.program` (which includes the instruction that faulted
    and everything after it — instructions that never retired).

DESIGN DECISION — why is `limit` a count where `0` means zero rows?
    The tempting spelling is `if limit and ...`, treating a falsy limit as "no
    limit". That makes `limit=0` mean "every row" — exactly the value a caller
    uses to ask for none — and the mistake is invisible until a check asserts
    the empty trace and gets the whole program back. A limit is a count, not a
    flag, and a count is never negative: `-1` sliced into the trace would return
    everything *but* the last row, a plausible-looking answer to an impossible
    question, so a negative limit is refused loudly.

DESIGN DECISION — why is the fingerprint a hash of memory and not the memory?
    Two machines are compared as one tuple, and a machine's data memory is 4096
    bytes: returning it whole puts 8 KiB into the message of every failed
    equivalence assertion, and compares two byte strings that stage 6 can mutate
    after the fact. The digest is a fixed-width, comparable summary of the same
    bytes. The program is deliberately absent from the fingerprint: it is a
    tuple, no instruction can change it, and two machines running different
    programs must still fingerprint equal when they leave the same state behind.

DESIGN DECISION — why do `status` and `fault` belong in the fingerprint?
    A machine that faulted at pc 3 and a machine that halted at pc 3 can hold
    *identical* registers and memory: the arithmetic fault is data, not an
    exception (§2.6), so nothing else in the architectural state records it.
    A fingerprint without them would call two machines equivalent when one
    computed an answer and the other stopped at a division by zero — the exact
    failure this course exists to catch.

TODO: implement `load`, `trace` and `fingerprint`.
"""

import hashlib

import isa
from stage_06 import Machine

#: the number of hex characters the fingerprint keeps of the memory digest
DIGEST_CHARS = 16


def load(source, *, data_size=4096, pc=0):
    """Assemble a catalogue name or any source text into a ready `Machine`.

    `source` is a key of `isa.PROGRAMS` or a program's own text; either way the
    catalogue is only ever read. The returned machine holds the assembled words
    as its program, `data_size` bytes of zeroed data memory, and the counter at
    `pc`, and has executed nothing yet.
    """
    raise NotImplementedError("stage 07: implement load()")


def trace(machine, *, limit=None):
    """The `(pc, word)` pairs of the instructions that retired, oldest first.

    `limit` caps the number of rows: `0` is no rows, a limit past the end is the
    whole trace, and a negative or non-integer limit is refused.
    """
    raise NotImplementedError("stage 07: implement trace()")


def fingerprint(machine):
    """A comparable, immutable summary of a machine's architectural state.

    `(status, fault, pc, registers, memory-digest)`: the register file as a
    snapshot tuple, and a short hex digest of the data memory's bytes.
    """
    raise NotImplementedError("stage 07: implement fingerprint()")
