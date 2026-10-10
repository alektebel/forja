"""CPU From Scratch — stage 07: the program, and the record of what it did

The finished implementation of `load`, `trace` and `fingerprint`. Every choice
below (why the loader does not run, why the trace is `(pc, word)` of retired
instructions only, why a limit is a count, why the fingerprint hashes the data
memory, and why the fault is part of it) is argued in `stage_07.py`'s docstring.
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
    if not isinstance(source, str):
        raise ValueError("stage 07: a program is a name or source text, got %r"
                         % (type(source).__name__,))
    text = isa.PROGRAMS.get(source, source)
    return Machine(isa.assemble(text), data_size=data_size, pc=pc)


def trace(machine, *, limit=None):
    """The `(pc, word)` pairs of the instructions that retired, oldest first.

    `limit` caps the number of rows: `0` is no rows, a limit past the end is the
    whole trace, and a negative or non-integer limit is refused.
    """
    rows = machine.trace
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("stage 07: the limit is a count of rows, got %r" % (limit,))
        if limit < 0:
            raise ValueError("stage 07: a negative limit %r is not a count" % (limit,))
        rows = rows[:limit]
    return tuple((row.pc, row.word) for row in rows)


def fingerprint(machine):
    """A comparable, immutable summary of a machine's architectural state.

    `(status, fault, pc, registers, memory-digest)`: the register file as a
    snapshot tuple, and a short hex digest of the data memory's bytes.
    """
    digest = hashlib.sha256(machine.memory.snapshot()).hexdigest()[:DIGEST_CHARS]
    return (machine.status, machine.fault, machine.pc,
            machine.registers.snapshot(), digest)
