"""CPU From Scratch — stage 2: the decoder.

A word is thirty-two bits and nothing else. Before the machine can do anything
it has to decide *what* a word is: which opcode, which registers, which
immediate — and it has to decide it the same way the assembler wrote it, or the
program that assembled cleanly will run as some other program.

DESIGN DECISION — why does `Instruction` carry the `isa.Op` instead of the
opcode number?
    The rejected alternative is the bare number: `decode` hands back 18 and
    every consumer looks `18` up in `isa.BY_CODE` to find the format, the
    mnemonic and the semantics. The cost is a second table lookup at every use
    site and, far worse, a use site that gets it wrong: stage 6's control unit
    consults the format to pick an operand, and a consumer that has to remember
    that `sw`'s "rd" field is not a destination will eventually forget. The
    decode step already did the lookup; carrying the `Op` hands each consumer
    the mnemonic, the format and the one-line semantics for free.

DESIGN DECISION — why do the fields the format does not use read as zero?
    The rejected alternative is to unpack all four fields and let the consumer
    consult the format before trusting them. The cost shows up silently: a `sw`
    word has arbitrary bits in the rd field, so the unpacked instruction
    "writes" a register it never meant to, and stage 8's dependence logic then
    stalls on a write that does not exist. An unused field is not an operand;
    the decoder is the one place that knows which fields the format uses.

DESIGN DECISION — why does `decode` refuse an unknown opcode instead of
returning a placeholder?
    The rejected alternative is an `Instruction` with `op=None` (or a fabricated
    `@29` operation) that the caller is expected to check. The cost is that the
    illegal instruction has to be detected a second time, farther from the word
    that carried it, and a run loop that forgets to check executes the
    placeholder as if it were an instruction. The word's opcode is the one
    thing a decoder exists to validate.

DESIGN DECISION — why is the immediate sign-extended in `decode` and not where
it is used?
    The rejected alternative is to keep the raw fourteen-bit field and let each
    user sign-extend it. The cost is three users — the ALU's immediate, a load
    or store address, a branch target — each of which has to remember, and the
    one that forgets turns `-1` into `16383`: an offset that lands inside memory,
    or a jump that lands near the start of the program, and looks entirely
    plausible while being wrong. `imm` has exactly one meaning; decode is where
    it is decided.

DESIGN DECISION — why does `registers()` drop `r0` from both tuples?
    The rejected alternative is to report every field the format mentions,
    zero included. The cost is that `r0` becomes a dependency: `sw` has no
    destination but its rd field reads as 0, and an instruction that writes r0
    appears to write it, so a dependence check waits for a write to a register
    that is hardwired and never changes. Worse, the same bug counts the write
    to r0 as a *read* of r0 — the two tuples then disagree about what the
    instruction does.

DESIGN DECISION — why is `disassemble`'s spelling not the assembler's?
    The rejected alternative is to reuse the assembler's positional operand
    list, so a load prints as `lw t0, s1, 4`. The cost is that the text of a
    trace row can no longer be read as an instruction: the reader cannot tell
    which of the two registers is the base and which the destination, and must
    remember the format string to find out. `lw t0, 4(s1)` says the address
    next to the register that holds it — the spelling every RISC manual uses.

TODO: implement `decode`, `encode`, `disassemble`, `registers` and `opcode`.
"""

from collections import namedtuple

import isa
from stage_01 import sign_extend

#: One decoded instruction. `pc` and `word` are where it came from (the trace
#: and the error messages need both); the four fields are the decoded operands,
#: and a field the format does not use is 0. `op` is the `isa.Op` *record* for
#: the word's opcode — `op.code`, `op.name`, `op.fmt`, `op.semantics` — never an
#: int and never a mnemonic string; `disassemble`, `registers` and stage 6's
#: machine all read it that way, which is why a consumer never looks the opcode
#: up a second time.
Instruction = namedtuple("Instruction", "pc word op rd rs1 rs2 imm")


class BadInstruction(ValueError):
    """An encoding whose opcode is not in the ISA. Carries `.word` and `.pc`.

    Constructed as `BadInstruction(word, *, pc=0)`, and its message names both
    the word in hex and the opcode.
    """


def decode(word, *, pc=0):
    """The `Instruction` a word encodes, or `BadInstruction` if it cannot.

    `op` is the `isa.Op` record of the word's opcode (never the int code, never
    the mnemonic string). The fields the format does not use read as 0, and a
    used immediate is sign-extended.
    """
    raise NotImplementedError("stage 2: implement decode()")


def encode(ins):
    """The word an `Instruction` encodes to: the inverse of `decode`.

    Only the fields the instruction's format uses are written; the rest are
    zero, so that `encode(decode(w))` reproduces exactly the fields of `w`.
    """
    raise NotImplementedError("stage 2: implement encode()")


def disassemble(ins):
    """The source spelling of a decoded instruction.

    `"add t0, t1, t2"`, `"li t0, -1"`, `"jmp 12"`. A load prints its address
    as `imm(rs1)` — `"lw t0, 4(s1)"`, `"lb t0, -8(s0)"` — and a store prints its
    value first and the address second — `"sw t3, 0(t2)"`, `"sb t1, 2(sp)"`.
    Every other format (including `addi`) is a plain comma-separated list.
    """
    raise NotImplementedError("stage 2: implement disassemble()")


def registers(ins):
    """`(reads, writes)`: the register indexes the instruction touches.

    Each side is a tuple of distinct indexes in ascending order; `r0` is never
    a dependency and appears in neither. Which fields are sources is `ins.op`'s
    format, not the fields' values.
    """
    raise NotImplementedError("stage 2: implement registers()")


def opcode(word):
    """The six-bit opcode field of a word, with no validation at all."""
    raise NotImplementedError("stage 2: implement opcode()")
