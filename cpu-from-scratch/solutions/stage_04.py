"""CPU From Scratch — stage 4: the arithmetic and logic unit.

The reasoning lives in `stage_04.py`; this is the implementation.
"""

import isa

from stage_01 import Flags, add_flags, shift_amount, signed, sub_flags, word

#: the opcodes `alu` computes: the arithmetic and logic subset of the ISA.
ALU_OPS = frozenset({4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17})

#: what every op other than add/sub returns: the ISA has no flag register.
_NO_FLAGS = Flags(False, False, False, False)


class ArithmeticFault(ValueError):
    """A division or remainder by zero, carrying the pc that caused it."""

    def __init__(self, message, *, detail=""):
        super().__init__(message)
        self.detail = detail


def _trunc_div(x, y):
    """Signed integer division truncated toward zero."""
    quotient = abs(x) // abs(y)
    return -quotient if (x < 0) != (y < 0) else quotient


def _trunc_mod(x, y):
    """Signed remainder; the result takes the dividend's sign."""
    remainder = abs(x) % abs(y)
    return -remainder if x < 0 else remainder


def _divisor(code, b, *, pc):
    """`signed(b)` for a div/mod, or an `ArithmeticFault` when b is zero."""
    divisor = signed(b)
    if divisor == 0:
        raise ArithmeticFault(
            "%s: division by zero at pc %d" % (isa.mnemonic(code), pc),
            detail="%s by zero at pc %d" % (isa.mnemonic(code), pc))
    return divisor


def alu(code, a, b, *, pc=0):
    """One arithmetic or logic operation, returning `(value, Flags)`.

    `code` must be one of `ALU_OPS`; any other opcode is refused with a plain
    `ValueError` naming it. Only `add` and `sub` carry flags; `div`/`mod` by zero
    raise `ArithmeticFault`, whose message names `pc`.
    """
    for name, value in (("a", a), ("b", b)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                "alu: operand %s must be an int word, got %r" % (name, value))
    if code not in ALU_OPS:
        raise ValueError("alu: opcode %r (%s) is not an ALU operation"
                         % (code, isa.mnemonic(code)))
    a = word(a)
    b = word(b)
    if code == 4:
        return add_flags(a, b)
    if code == 5:
        return sub_flags(a, b)
    if code == 6:
        return word(a * b), _NO_FLAGS
    if code == 7:
        return word(_trunc_div(signed(a), _divisor(code, b, pc=pc))), _NO_FLAGS
    if code == 8:
        return word(_trunc_mod(signed(a), _divisor(code, b, pc=pc))), _NO_FLAGS
    if code == 10:
        return a & b, _NO_FLAGS
    if code == 11:
        return a | b, _NO_FLAGS
    if code == 12:
        return a ^ b, _NO_FLAGS
    if code == 13:
        return word(a << shift_amount(b)), _NO_FLAGS
    if code == 14:
        return a >> shift_amount(b), _NO_FLAGS
    if code == 15:
        return word(signed(a) >> shift_amount(b)), _NO_FLAGS
    if code == 16:
        return (1 if signed(a) < signed(b) else 0), _NO_FLAGS
    if code == 17:
        return (1 if a < b else 0), _NO_FLAGS
    raise ValueError("alu: opcode %r (%s) is not implemented"
                     % (code, isa.mnemonic(code)))
