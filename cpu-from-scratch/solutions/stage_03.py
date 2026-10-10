"""CPU From Scratch — stage 3: the register file (implementation).

The reasoning behind the copy, the refusals and the hardwired zero lives in the
template's docstring (`stage_03.py`); this file is only the body.
"""

import isa
from stage_01 import word


#: the three register indexes with a meaning — the hardwired zero, the stack
#: pointer and the return address — re-exported from `isa`.
ZERO, RA, SP = isa.ZERO, isa.RA, isa.SP


def _index_of(index):
    """Resolve a register name or index to an int in `0..15`.

    Raises `ValueError`, naming the value, for an unknown name, a `bool`, a
    non-integer, or an index outside the file.
    """
    if isinstance(index, str):
        try:
            return isa.REG_INDEX[index]
        except KeyError:
            raise ValueError("stage 3: %r is not a register name" % (index,))
    if isinstance(index, bool) or not isinstance(index, int):
        raise ValueError("stage 3: %r is not a register index" % (index,))
    if not 0 <= index < isa.NUM_REGS:
        raise ValueError("stage 3: register index %r is outside 0..15" % (index,))
    return index


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
        registers = [0] * isa.NUM_REGS
        if initial is not None:
            if isinstance(initial, str):
                raise ValueError("stage 3: initial is a mapping or 16 values, not a string: %r"
                                 % (initial,))
            if hasattr(initial, "items"):
                for name, value in initial.items():
                    registers[_index_of(name)] = word(value)
            else:
                values = tuple(initial)
                if len(values) != isa.NUM_REGS:
                    raise ValueError("stage 3: a register file needs 16 initial values, got %d"
                                     % (len(values),))
                for index, value in enumerate(values):
                    registers[index] = word(value)
        registers[ZERO] = 0
        self._registers = registers

    def read(self, index):
        """Return the value of the register named or indexed by `index`."""
        return self._registers[_index_of(index)]

    def write(self, index, value):
        """Store `value` (masked to a word) in the register; a write to `r0` is
        dropped, not an error."""
        position = _index_of(index)
        if position != ZERO:
            self._registers[position] = word(value)

    def snapshot(self):
        """Return the sixteen registers as a tuple — a copy, never the file's own
        state."""
        return tuple(self._registers)

    def restore(self, state):
        """Set the registers from exactly sixteen values, masking each and forcing
        `r0` to 0."""
        values = tuple(state)
        if len(values) != isa.NUM_REGS:
            raise ValueError("stage 3: restore() takes 16 values, got %d" % (len(values),))
        for index, value in enumerate(values):
            self._registers[index] = word(value)
        self._registers[ZERO] = 0
