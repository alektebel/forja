"""CPU From Scratch — stage 3: the register file, and the snapshot that must not
be the machine.

DESIGN DECISION — why is a write to r0 dropped instead of refused?
    `zero` is a name a program can write, and a real machine retires `addi zero,
    zero, 0` or `mov zero, t0` without complaint: the instruction is legal, it
    just has no effect. Refusing the write would make a fault depend on which
    operand a program happened to name rather than on what it computed, and the
    pipeline would owe a special case at write-back for an instruction the
    decoder already accepts. Dropping the write keeps "r0 reads 0" true for every
    sequence of instructions, which is what lets every later stage reason about
    `zero` without asking how the register was reached.

DESIGN DECISION — why does snapshot() return a copy rather than the registers?
    The whole course is accepted by running one program on two machines and
    comparing their state. If `snapshot()` hands out the machine's own list, that
    comparison is a machine against itself: it is equal by construction, so every
    equivalence test becomes vacuous while still reporting success. A copy makes
    the snapshot a value: writing a register afterwards cannot move it, and a
    saved state and a later state are two witnesses instead of two names for one
    object.

DESIGN DECISION — why is an out-of-range index refused instead of Python-indexed?
    `registers[-1]` is a Python convenience a machine does not have. A decoder
    bug that yields -1, or a hand-typed 16, would quietly address another
    register — -1 lands on `ra` — and the program would compute a plausible wrong
    answer instead of stopping. Range-checking every index turns a lost register
    into a message that names the value.

DESIGN DECISION — why does restore() force r0 to 0 and mask the values?
    A snapshot is a value that a test may build itself, so `restore` cannot trust
    its sixteen inputs. If it did, a restored machine could hold a non-zero
    `zero`, and then "r0 reads 0" would depend on where the state came from
    rather than on the machine. `restore` is the boundary that turns any sixteen
    integers into a legal architectural state: masked to a word, with the
    hardwired register put back where it belongs.

DESIGN DECISION — why must restore() take exactly sixteen values?
    The alternative — accept fewer and zero the rest, or ignore the extras —
    silently invents a state. A restore of fifteen values leaves one register at
    whatever the machine held before, so a machine that round-trips through
    `snapshot()`/`restore()` is no longer the machine the snapshot described. A
    length that is not sixteen is a bug in the caller, and the message says so.

TODO: implement `RegisterFile` (`__init__`, `read`, `write`, `snapshot`,
`restore`) and re-export `ZERO`, `RA`, `SP`.
"""

import isa
from stage_01 import word


#: the three register indexes with a meaning — the hardwired zero, the stack
#: pointer and the return address — re-exported from `isa` so a caller can say
#: `rf.read(RA)` without importing the register table itself.
ZERO, RA, SP = isa.ZERO, isa.RA, isa.SP


class RegisterFile:
    """The architectural register file: sixteen 32-bit words, `r0` hardwired to 0.

    A register is named by an integer index in `0..15`, or by any spelling
    `isa.REG_INDEX` knows (`"t0"`, `"r8"`, `"$8"`). An index outside the file, a
    `bool`, or an unknown name is refused with the value named in the message.
    """

    def __init__(self, initial=None):
        """Build a file of sixteen zeros, or of `initial`.

        `initial` is either a mapping from a register (name or index) to its
        value, or a sequence of exactly sixteen values. Every value is masked to
        a word and `r0` is forced to 0.
        """
        raise NotImplementedError("stage 3: implement RegisterFile.__init__()")

    def read(self, index):
        """Return the value of the register named or indexed by `index`."""
        raise NotImplementedError("stage 3: implement RegisterFile.read()")

    def write(self, index, value):
        """Store `value` (masked to a word) in the register; a write to `r0` is
        dropped, not an error."""
        raise NotImplementedError("stage 3: implement RegisterFile.write()")

    def snapshot(self):
        """Return the sixteen registers as a tuple — a copy, never the file's own
        state."""
        raise NotImplementedError("stage 3: implement RegisterFile.snapshot()")

    def restore(self, state):
        """Set the registers from exactly sixteen values, masking each and forcing
        `r0` to 0."""
        raise NotImplementedError("stage 3: implement RegisterFile.restore()")
