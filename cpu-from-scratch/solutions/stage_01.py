"""CPU From Scratch — stage 1: the word, and the flags.

The finished implementation; the reasoning — why values are masked, why
`signed` subtracts `2**32`, why carry and overflow are two flags, why the bytes
are little-endian, and why a `bool` is not an immediate — lives in the
DESIGN DECISION blocks of `stage_01.py`.
"""

from collections import namedtuple

from isa import WORD_BITS, WORD_MASK, BYTES_PER_WORD, IMM_MIN, IMM_MAX

#: the four flags an `add`/`sub` produces, in a fixed order; a value type, so
#: two results compare by value rather than by identity.
Flags = namedtuple("Flags", "zero negative carry overflow")


def word(value):
    """Mask `value` to one 32-bit word: an int in `0 .. 0xFFFFFFFF`."""
    return value & WORD_MASK


def signed(value):
    """Reinterpret a word as a signed two's-complement integer."""
    value &= WORD_MASK
    return value - (1 << WORD_BITS) if value & (1 << (WORD_BITS - 1)) else value


def sign_extend(value, bits):
    """Replicate bit `bits - 1` of the low `bits` bits of `value` upward."""
    value &= (1 << bits) - 1
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def fits_imm(value):
    """True when `value` is an integer in the 14-bit immediate range.

    A `bool` is refused: `True == 1` fits the range, but a flag is not an
    immediate, and accepting it would let one reach an instruction as the
    constant 1.
    """
    if isinstance(value, bool):
        return False
    return IMM_MIN <= value <= IMM_MAX


def shift_amount(value):
    """The amount a runtime shift uses: the bottom five bits of `value`."""
    return value & 31


def add_flags(a, b):
    """`(result, Flags)` for an unsigned add of two words (both masked)."""
    a &= WORD_MASK
    b &= WORD_MASK
    result = (a + b) & WORD_MASK
    sign_a = a >> (WORD_BITS - 1)
    sign_b = b >> (WORD_BITS - 1)
    sign_r = result >> (WORD_BITS - 1)
    flags = Flags(zero=result == 0,
                  negative=bool(sign_r),
                  carry=(a + b) > WORD_MASK,
                  overflow=sign_a == sign_b and sign_r != sign_a)
    return result, flags


def sub_flags(a, b):
    """`(result, Flags)` for an unsigned subtract of two words (both masked)."""
    a &= WORD_MASK
    b &= WORD_MASK
    result = (a - b) & WORD_MASK
    sign_a = a >> (WORD_BITS - 1)
    sign_b = b >> (WORD_BITS - 1)
    sign_r = result >> (WORD_BITS - 1)
    flags = Flags(zero=result == 0,
                  negative=bool(sign_r),
                  carry=a >= b,
                  overflow=sign_a != sign_b and sign_r != sign_a)
    return result, flags


def pack_word(value):
    """The four little-endian bytes of `value` masked to a word."""
    return word(value).to_bytes(BYTES_PER_WORD, "little")


def unpack_word(data):
    """The word held in four little-endian bytes.

    A buffer that is not exactly four bytes is refused: a three-byte read is
    the mistake this function exists to make impossible.
    """
    data = bytes(data)
    if len(data) != BYTES_PER_WORD:
        raise ValueError("unpack_word needs exactly four bytes, got %d" % (len(data),))
    return int.from_bytes(data, "little")
