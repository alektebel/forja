"""CPU From Scratch — stage 4: the arithmetic and logic unit

DESIGN DECISION — why truncate toward zero instead of using Python's `//`?
    `//` is right there, it is one token, and for two of the four sign
    combinations it is already correct. It is floor division: it rounds toward
    minus infinity, so `-7 // 2` is -4, not -3. Adopting it costs the ISA its
    meaning at exactly the boundary a compiler is most likely to emit (a negative
    dividend), and the bug stays invisible unless the test picks a negative
    numerator — which is why this stage's check enumerates all four sign
    combinations instead of trusting the usual `7 / 2`.

DESIGN DECISION — why does the remainder take the dividend's sign?
    Python's `%` returns a remainder with the *divisor's* sign, so `-7 % 2` is 1
    rather than -1. A non-negative remainder looks tidy and satisfies the
    identity `a == (a // b) * b + a % b` under floor division; under the
    truncating division this ISA actually uses it costs that very identity, and
    it silently flips the sign of every `mod` whose dividend is negative — an
    index or a hash that wraps to the far end of a table instead of slightly
    before zero.

DESIGN DECISION — why do only `add` and `sub` set flags?
    Deriving `zero`/`negative` from every result is uniform and costs nothing to
    write. It also invents a flag register the ISA deliberately does not have:
    the shifts' `negative` bit would come from bit 31 of a value nothing consumes,
    and a later machine (stage 6) would have to decide whether to store it.
    Returning all-false flags from every other op makes "there is no flag
    register" a decision the check can assert, rather than an assumption.

DESIGN DECISION — why is a division by zero an exception, not a result of zero?
    Several real ISAs (ARM among them) define `x / 0` as 0 and move on: one branch
    fewer to write, and the program keeps running. That leniency costs the machine
    the ability to notice — `x / 0` becomes a plausible number that propagates
    through every later instruction, and the divisor that was supposed to be
    checked is never named. An exception carrying the `pc` is the only shape that
    lets the control unit (stage 6) turn the event into an architectural fault at
    the address that caused it.

DESIGN DECISION — why must an opcode outside the set be refused, and by name?
    Letting the ALU compute whatever it is handed is lenient and never raises in
    the middle of a run. It costs the decoder's mistakes their visibility: a word
    whose opcode field says `lw` would come back as a plausible arithmetic result,
    the illegal-instruction fault of stage 6 would never fire, and the bug would
    be found by staring at a wrong number instead of at the encoding. Naming the
    opcode — with its mnemonic — puts the failing instruction in the message.

DESIGN DECISION — why mask the operands rather than trust the caller?
    The register file already holds 32-bit words, so masking looks redundant. But
    Python's ints are arbitrary precision and the operands are not always a
    register: a negative immediate, or a product wider than a word, would flow
    through unmasked — `sra` would then shift a value that is not a word, and
    `mul` would hand back a number wider than the machine. Masking at the boundary
    keeps every path a function of words alone.

TODO: implement `alu`. `Flags`, `word`, `signed`, `add_flags`, `sub_flags` and
`shift_amount` are the stage 1 surface; `isa.mnemonic` names an opcode in a
refusal.
"""

#: the opcodes `alu` computes: the arithmetic and logic subset of the ISA.
ALU_OPS = frozenset({4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17})


class ArithmeticFault(ValueError):
    """A division or remainder by zero, carrying the pc that caused it.

    `.detail` is a one-line description of the failing operation.
    """

    def __init__(self, message, *, detail=""):
        super().__init__(message)
        self.detail = detail


def alu(code, a, b, *, pc=0):
    """One arithmetic or logic operation, returning `(value, Flags)`.

    `code` must be one of `ALU_OPS`; any other opcode is refused with a plain
    `ValueError` naming it. `a` and `b` are words — any int is accepted, a value
    of another type is refused. Only `add` and `sub` carry flags; every other op
    returns all-false flags. `div` and `mod` truncate toward zero and take the
    dividend's sign for the remainder; a zero divisor is an `ArithmeticFault`
    whose message names `pc`.
    """
    raise NotImplementedError("stage 4: implement alu()")
