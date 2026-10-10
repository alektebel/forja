"""CPU From Scratch — stage 1: the word, and the flags.

Everything a 32-bit machine does is arithmetic on a *word*, and the first
lesson is to make the word the only kind of value that exists. This stage
supplies the algebra the rest of the course is written in: the mask, the
two's-complement reinterpretation, the immediate test, the shift amount, the
two flag-producing operations, and the byte order of memory.

DESIGN DECISION — why is a word a Python int masked to 32 bits, and not just a
Python int?
    Python's integers are unbounded, so `a + b` is never wrong until it is: a
    register that holds `2**32` loads, compares as larger than `0xFFFFFFFF`,
    and prints as a number no 32-bit machine can hold — and the bug surfaces
    three stages later as a fingerprint that differs between two machines that
    agree on every bit. Masking at every producer (`word`) makes the word the
    only representation the machine ever sees. The rejected alternative — mask
    only where a value is *stored* — lets a stale high bit ride through a
    comparison and change a branch.

DESIGN DECISION — why does `signed` subtract `2**32`, rather than adding a
sign bit's worth?
    Two's complement is a reinterpretation, not a sign flip: the same 32 bits
    stand for `v` when bit 31 is clear and for `v - 2**32` when it is set. The
    tempting `v + 2**31` (or `v - 2**31`) is off by half a word: it maps
    `0x80000000` to `0` or to `2**32`, and the only `slt` that uses it is
    exactly the one comparing the most negative number — a case a test written
    with small positives never reaches. Rejected: sign-magnitude
    (`-(v & 0x7FFFFFFF)`), which makes the minimum value equal to zero.

DESIGN DECISION — why are `carry` and `overflow` two flags, and not one?
    They answer different questions. Carry is the unsigned one: did the sum
    leave bit 31 (`a + b > WORD_MASK`), or, for a subtract, was there no borrow
    (`a >= b` unsigned). Overflow is the signed one: the result's sign is
    impossible for the operands' signs. A student who computes carry as signed
    overflow gets it right on `0xFFFFFFFF + 1` (both set) and wrong on
    `0x7FFFFFFF + 1` (overflow alone) and on `0xFFFFFFFF + 0xFFFFFFFF` (carry
    alone) — precisely the cases that separate them. Rejected: a single "error"
    flag, which cannot express the machine's contract that adding two unsigned
    addresses is not an error when bit 31 overflows.

DESIGN DECISION — why little-endian, when "network order" is big-endian?
    `pack_word`/`unpack_word` fix the byte order of machine memory, and the ISA
    has no endianness-independent primitive to fall back on: a `lb` at an
    address must see the byte a `sw` put there, or the `memcpy` program copies a
    byte-reversed buffer. Little-endian is the choice the rest of the course is
    written against — `unpack_word(b'\\x01\\x00\\x00\\x00')` is 1 — so the
    checks read the same bytes the machine does. Rejected: big-endian "because
    networks use it", which silently swaps every multi-byte value while leaving
    the arithmetic checks green.

DESIGN DECISION — why is the shift amount masked to five bits?
    The ISA says `sll` shifts by `rs2 & 31`; Python shifts by the whole
    integer, happily and silently, so `x << 32` is `0` and `x << 33` is
    `x << 1` — plausible-looking answers from a value the hardware would have
    reduced. `shift_amount` puts that reduction in one place, shared by the
    decoder and the ALU, instead of duplicated at each use. Rejected: trusting
    the caller to pass a small amount, a promise the register file cannot keep,
    since a register holds any 32-bit value.

DESIGN DECISION — why is `True` not a legal immediate?
    `True == 1`, so `fits_imm(True)` would answer "yes, 1 fits" and an
    immediate of `True` would assemble as `1` — a condition from a caller's code
    arriving as an instruction's constant, which no assembly source can even
    spell. The range test is a predicate over integers, so a `bool` is refused
    by answering `False`; the alternative, coercing it to 1, hides exactly the
    type confusion this stage exists to catch. Everywhere else here coercion is
    the rule (masking *is* coercion); this is the one boundary where a `bool`
    must become visible.

TODO: implement `word`, `signed`, `sign_extend`, `fits_imm`, `shift_amount`,
`add_flags`, `sub_flags`, `pack_word` and `unpack_word`.
"""

from collections import namedtuple

#: the provided module's geometry, re-exported so a stage has one source of
#: truth: a word is 32 bits and four bytes, and the immediate is a signed
#: 14-bit value.
from isa import WORD_BITS, WORD_MASK, BYTES_PER_WORD, IMM_MIN, IMM_MAX

#: the four flags an `add`/`sub` produces, in a fixed order; a value type, so
#: two results compare by value rather than by identity.
Flags = namedtuple("Flags", "zero negative carry overflow")


def word(value):
    """Mask `value` to one 32-bit word: an int in `0 .. 0xFFFFFFFF`."""
    raise NotImplementedError("stage 1: implement word()")


def signed(value):
    """Reinterpret a word as a signed two's-complement integer."""
    raise NotImplementedError("stage 1: implement signed()")


def sign_extend(value, bits):
    """Replicate bit `bits - 1` of the low `bits` bits of `value` upward."""
    raise NotImplementedError("stage 1: implement sign_extend()")


def fits_imm(value):
    """True when `value` is an integer in the 14-bit immediate range.

    A `bool` is refused: `True == 1` fits the range, but a flag is not an
    immediate, and accepting it would let one reach an instruction as 1.
    """
    raise NotImplementedError("stage 1: implement fits_imm()")


def shift_amount(value):
    """The amount a runtime shift uses: the bottom five bits of `value`."""
    raise NotImplementedError("stage 1: implement shift_amount()")


def add_flags(a, b):
    """`(result, Flags)` for an unsigned add of two words (both masked)."""
    raise NotImplementedError("stage 1: implement add_flags()")


def sub_flags(a, b):
    """`(result, Flags)` for an unsigned subtract of two words (both masked)."""
    raise NotImplementedError("stage 1: implement sub_flags()")


def pack_word(value):
    """The four little-endian bytes of `value` masked to a word."""
    raise NotImplementedError("stage 1: implement pack_word()")


def unpack_word(data):
    """The word held in four little-endian bytes.

    A buffer whose length is not `BYTES_PER_WORD` is refused with a `ValueError`
    naming the length it saw, rather than reading a prefix of it: a three-byte
    read is the mistake this function exists to make impossible.
    """
    raise NotImplementedError("stage 1: implement unpack_word()")
