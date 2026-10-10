"""CPU From Scratch — stage 2 (the decoder): the finished implementation.

The reasoning is in `stage_02.py`, next to the stubs; this file is what the
course's checks run.
"""

from collections import namedtuple

import isa
from stage_01 import sign_extend

#: One decoded instruction: where it came from (`pc`, `word`), the `isa.Op` of
#: its opcode, and the four decoded fields. A field the format does not use is 0.
Instruction = namedtuple("Instruction", "pc word op rd rs1 rs2 imm")

#: the width of each field, as a mask, and the field letter -> field name
_OPCODE_MASK = (1 << isa.OPCODE_BITS) - 1
_REG_MASK = (1 << isa.REG_BITS) - 1
_IMM_MASK = (1 << isa.IMM_BITS) - 1
_FIELD_OF = {"d": "rd", "a": "rs1", "b": "rs2", "i": "imm"}

#: the reads and stores: they print their address as `imm(rs1)`, and a store's
#: first operand in the encoding is the base register, not a destination
_LOADS = frozenset((18, 20))
_STORES = frozenset((19, 21))


class BadInstruction(ValueError):
    """An encoding whose opcode is not in the ISA. Carries `.word` and `.pc`."""

    def __init__(self, word, *, pc=0):
        super().__init__(
            "illegal instruction 0x%08x at pc %d: opcode %d is not in the ISA"
            % (word & isa.WORD_MASK, pc,
               (word >> isa.OPCODE_SHIFT) & _OPCODE_MASK))
        self.word = word
        self.pc = pc


def opcode(word):
    """The six-bit opcode field of a word, with no validation at all."""
    return (word >> isa.OPCODE_SHIFT) & _OPCODE_MASK


def _field(word, shift):
    """One register field, masked to its four bits."""
    return (word >> shift) & _REG_MASK


def decode(word, *, pc=0):
    """The `Instruction` a word encodes, or `BadInstruction` if it cannot.

    The fields the format does not use read as 0, and a used immediate is
    sign-extended.
    """
    op = isa.BY_CODE.get(opcode(word))
    if op is None:
        raise BadInstruction(word, pc=pc)
    fields = {"rd": 0, "rs1": 0, "rs2": 0, "imm": 0}
    for letter in op.fmt:
        name = _FIELD_OF[letter]
        if name == "imm":
            fields["imm"] = sign_extend(word & _IMM_MASK, isa.IMM_BITS)
        elif name == "rd":
            fields["rd"] = _field(word, isa.RD_SHIFT)
        elif name == "rs1":
            fields["rs1"] = _field(word, isa.RS1_SHIFT)
        else:
            fields["rs2"] = _field(word, isa.RS2_SHIFT)
    return Instruction(pc, word, op, fields["rd"], fields["rs1"],
                       fields["rs2"], fields["imm"])


def encode(ins):
    """The word an `Instruction` encodes to: the inverse of `decode`.

    Only the fields the instruction's format uses are written; the rest are
    zero, so that `encode(decode(w))` reproduces exactly the fields of `w`.
    """
    word = (ins.op.code & _OPCODE_MASK) << isa.OPCODE_SHIFT
    if "d" in ins.op.fmt:
        word |= (ins.rd & _REG_MASK) << isa.RD_SHIFT
    if "a" in ins.op.fmt:
        word |= (ins.rs1 & _REG_MASK) << isa.RS1_SHIFT
    if "b" in ins.op.fmt:
        word |= (ins.rs2 & _REG_MASK) << isa.RS2_SHIFT
    if "i" in ins.op.fmt:
        word |= ins.imm & _IMM_MASK
    return word


def disassemble(ins):
    """The source spelling of a decoded instruction.

    `"add t0, t1, t2"`, `"li t0, -1"`, `"jmp 12"`; a load or a store prints its
    address as `imm(rs1)`: `"lw t0, 4(s1)"`.
    """
    if ins.op.code in _LOADS:
        parts = [isa.REG_NAMES[ins.rd], _address(ins)]
    elif ins.op.code in _STORES:
        parts = [isa.REG_NAMES[ins.rs2], _address(ins)]
    else:
        parts = []
        for letter in ins.op.fmt:
            if letter == "i":
                parts.append("%d" % (ins.imm,))
            else:
                parts.append(isa.REG_NAMES[getattr(ins, _FIELD_OF[letter])])
    if not parts:
        return ins.op.name
    return ins.op.name + " " + ", ".join(parts)


def _address(ins):
    """The `imm(rs1)` operand of a load or a store."""
    return "%d(%s)" % (ins.imm, isa.REG_NAMES[ins.rs1])


def registers(ins):
    """`(reads, writes)`: the register indexes the instruction touches.

    Each side is a tuple of distinct indexes in ascending order; `r0` is never
    a dependency and appears in neither.
    """
    reads = set()
    if "a" in ins.op.fmt:
        reads.add(ins.rs1)
    if "b" in ins.op.fmt:
        reads.add(ins.rs2)
    reads.discard(isa.ZERO)
    writes = set()
    if "d" in ins.op.fmt:
        writes.add(ins.rd)
    writes.discard(isa.ZERO)
    return tuple(sorted(reads)), tuple(sorted(writes))
