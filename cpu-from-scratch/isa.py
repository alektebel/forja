"""CPU From Scratch — the PROVIDED ISA. Do not edit; it has no TODOs.

This is G3's `mus.py`/`lab.py`: the specification as data, plus a complete
assembler, provided so that the course is about the *machine* and not about
tokenizing assembly. It is the file the ten stages agree through: the one place
that says where the opcode lives in a word, which registers exist, what an
instruction may contain, and which opcodes are legal at all. Every stage imports
it, no stage may change it, and the checks for it live outside the course.

There is no time, no random, no os, no network and no module-level mutable
state here: the only mapping this file exposes is read-only, and every function
returns tuples. Two calls with the same text produce the same words.

What this file does NOT know about: machines, decoders, the register file as a
thing with state, memory, cycles, pipelines. It knows what an instruction *is*
and how to write one down; executing it is the course. In particular the
`semantics` line of every `Op` is documentation for the student, not code: the
machine that implements it is `stage_06.py`.

Five things this file exists to get exactly right, because a stage that gets
them wrong fails in a way that is very hard to see:

1. **One layout, stated once.** `[opcode:6][rd:4][rs1:4][rs2:4][imm:14]`. The
   shifts and masks are constants here, so a decoder that reads the immediate
   from the wrong place disagrees with the assembler that wrote it — and the
   check that catches that is `encode(decode(word)) == word` over the fields the
   format actually uses.
2. **The immediate is signed.** 14 bits, `-8192 .. 8191`, sign-extended when
   decoded. `0x3FFF` is `-1`, not `16383`. Everything about loads, stores and
   branches depends on this and nothing else in the course will tell you again.
3. **A label is a position, not an instruction** (the two-pass assembler). A
   one-pass assembler cannot resolve a jump to a label defined later, and the
   program that shows it is in `PROGRAMS`.
4. **The format decides the operand count.** `add` takes three, `li` two, `nop`
   none, and an instruction with the wrong count is refused with its line.
   A label and an instruction may share a line; a label may not share a line
   with another label.
5. **Refusal carries the line number.** `AssemblyError` messages are read by a
   student staring at a program that will not assemble: they name the line, the
   token and what was expected.

The ISA is deliberately the same family as the one in `compiler-and-vgpu`
(phase G1): 32-bit words, 16 registers, the same field layout, and the same
`li`/`mov`/`jal` shapes — so a program written in that course's assembler
assembles here. This course adds the memory sizes (`lb`/`sb`), the compares
(`slt`/`sltu`), and the flags the ALU reports, because a datapath has to have
them.

Frozen surface the stages import:

    WORD_BITS WORD_MASK BYTES_PER_WORD                     # the word
    OPCODE_BITS OPCODE_SHIFT RD_SHIFT RS1_SHIFT RS2_SHIFT REG_BITS
    IMM_BITS IMM_SHIFT IMM_MIN IMM_MAX                     # the encoding
    NUM_REGS REG_NAMES ZERO SP RA REG_INDEX                # the register file
    AssemblyError UndefinedLabel                           # refusals
    Op OPS BY_CODE BY_NAME mnemonic(code)                  # the instruction set
    assemble(text) assemble_lines(text) PROGRAMS           # the assembler
"""

import types
from collections import namedtuple

# ---------------------------------------------------------------------------
# the word
# ---------------------------------------------------------------------------

#: a word is 32 bits, and every value a machine holds is masked to it
WORD_BITS = 32
WORD_MASK = 0xFFFFFFFF
#: memory is byte-addressed; a word is four bytes
BYTES_PER_WORD = 4

# ---------------------------------------------------------------------------
# the encoding: [ opcode:6 ][ rd:4 ][ rs1:4 ][ rs2:4 ][ imm:14 ]
# ---------------------------------------------------------------------------

#: bits of the opcode field, and its distance from the bottom of the word
OPCODE_BITS = 6
OPCODE_SHIFT = 26
#: a register field is four bits wide
REG_BITS = 4
RD_SHIFT = 22
RS1_SHIFT = 18
RS2_SHIFT = 14
#: the immediate is fourteen bits, signed, and sits at the bottom
IMM_BITS = 14
IMM_SHIFT = 0
IMM_MIN = -(1 << (IMM_BITS - 1))
IMM_MAX = (1 << (IMM_BITS - 1)) - 1

# ---------------------------------------------------------------------------
# the register file
# ---------------------------------------------------------------------------

#: sixteen registers. `zero` is hardwired to 0, `sp` and `ra` are conventions:
#: nothing in the hardware treats them specially, but the programs in this file
#: use `ra` for the return address and never touch `zero`.
NUM_REGS = 16
REG_NAMES = ("zero", "at", "v0", "v1", "a0", "a1", "a2", "a3",
             "t0", "t1", "t2", "t3", "s0", "s1", "sp", "ra")
ZERO = 0
SP = 14
RA = 15
#: name -> index, and the three spellings of each register the assembler accepts
REG_INDEX = {name: index for index, name in enumerate(REG_NAMES)}
for _index, _name in enumerate(REG_NAMES):
    REG_INDEX["r%d" % _index] = _index
    REG_INDEX["$%d" % _index] = _index
del _index, _name

# ---------------------------------------------------------------------------
# refusals
# ---------------------------------------------------------------------------


class AssemblyError(ValueError):
    """A program that cannot be assembled. Carries `.line` and `.token`."""

    def __init__(self, message, *, line=None, token=None):
        super().__init__("line %s: %s" % (line if line is not None else "?",
                                          message))
        self.line = line
        self.token = token


class UndefinedLabel(AssemblyError):
    """A label that is used but never defined. Carries `.label`."""

    def __init__(self, label, *, line=None):
        super().__init__("undefined label %r" % (label,), line=line,
                         token=label)
        self.label = label


# ---------------------------------------------------------------------------
# the instruction set
# ---------------------------------------------------------------------------

#: one opcode: its number, its mnemonic, its operand format and its meaning.
#: `fmt` is a string over {"d", "a", "b", "i"} — rd, rs1, rs2, the immediate —
#: in that order, so "dab" is `op rd, rs1, rs2` and "di" is `op rd, imm`.
Op = namedtuple("Op", "code name fmt semantics")

#: every opcode the machine knows. A word whose opcode is not in here is an
#: illegal instruction, and the machine that decodes it must say so.
OPS = (
    Op(0, "nop", "", "does nothing but advance the pc"),
    Op(1, "halt", "", "halts the machine"),
    Op(2, "li", "di", "rd = sign_extend(imm)"),
    Op(3, "mov", "da", "rd = rs1"),
    Op(4, "add", "dab", "rd = rs1 + rs2, with flags"),
    Op(5, "sub", "dab", "rd = rs1 - rs2, with flags"),
    Op(6, "mul", "dab", "rd = rs1 * rs2 (low 32 bits)"),
    Op(7, "div", "dab", "signed division, truncating toward zero; 0 divides is an arith fault"),
    Op(8, "mod", "dab", "signed remainder taking the dividend's sign; 0 divides is an arith fault"),
    Op(9, "addi", "dai", "rd = rs1 + imm"),
    Op(10, "and", "dab", "rd = rs1 & rs2"),
    Op(11, "or", "dab", "rd = rs1 | rs2"),
    Op(12, "xor", "dab", "rd = rs1 ^ rs2"),
    Op(13, "sll", "dab", "rd = rs1 << (rs2 & 31)"),
    Op(14, "srl", "dab", "rd = rs1 >> (rs2 & 31), logical"),
    Op(15, "sra", "dab", "rd = signed(rs1) >> (rs2 & 31), arithmetic"),
    Op(16, "slt", "dab", "rd = 1 if signed(rs1) < signed(rs2) else 0"),
    Op(17, "sltu", "dab", "rd = 1 if rs1 < rs2 else 0"),
    Op(18, "lw", "dai", "rd = load(rs1 + imm, 4), little-endian"),
    Op(19, "sw", "abi", "store(rs1 + imm, 4, rs2)"),
    Op(20, "lb", "dai", "rd = load(rs1 + imm, 1), zero-extended"),
    Op(21, "sb", "abi", "store(rs1 + imm, 1, rs2)"),
    Op(22, "jmp", "i", "pc = imm (an absolute word index)"),
    Op(23, "jz", "ai", "if rs1 == 0: pc = imm"),
    Op(24, "jnz", "ai", "if rs1 != 0: pc = imm"),
    Op(25, "beq", "abi", "if rs1 == rs2: pc = imm"),
    Op(26, "bne", "abi", "if rs1 != rs2: pc = imm"),
    Op(27, "jal", "di", "rd = pc + 1, then pc = imm"),
    Op(28, "jr", "a", "pc = rs1 (a call returns with `jr ra`)"),
)

BY_CODE = {op.code: op for op in OPS}
BY_NAME = {op.name: op for op in OPS}

#: the order of the field letters in a format string
_FIELDS = "dabi"
_FORMAT_LETTERS = frozenset(_FIELDS)


def mnemonic(code):
    """The name of an opcode, or ``'@<code>'`` when nothing has that number."""
    op = BY_CODE.get(code)
    return op.name if op is not None else "@%d" % (code,)


# ---------------------------------------------------------------------------
# the assembler (two passes: labels first, because a jump may look forward)
# ---------------------------------------------------------------------------

PROGRAM_HEADER = ("# a program is one instruction per line; '#' starts a comment,\n"
                  "# 'name:' is a label on a line of its own (or before an\n"
                  "# instruction), operands are comma separated, and a label or a\n"
                  "# number is an absolute word index for jumps and branches.\n")


def _strip(raw):
    """The comment-free part of a line, with the whitespace trimmed."""
    cut = raw.find("#")
    if cut >= 0:
        raw = raw[:cut]
    return raw.strip()


def _split_operands(text):
    """Split an operand list on commas, refusing an empty operand."""
    operands = []
    for chunk in text.split(","):
        operand = chunk.strip()
        if not operand:
            raise ValueError("empty operand")
        operands.append(operand)
    return operands


def _parse_line(number, raw):
    """`(label, op, operands, line_number)` for one source line, or None."""
    text = _strip(raw)
    if not text:
        return None
    label = None
    while ":" in text:
        head, _, tail = text.partition(":")
        head = head.strip()
        if not head or any(character.isspace() for character in head):
            break
        if label is not None:
            raise AssemblyError("one label per line", line=number, token=head)
        label = head
        text = tail.strip()
        if not text:
            return label, None, [], number
    if not text:
        if label is None:
            return None
        return label, None, [], number
    head, _, tail = text.partition(" ")
    head = head.strip()
    if tail.strip():
        try:
            operands = _split_operands(tail.strip())
        except ValueError as exc:
            raise AssemblyError(str(exc), line=number) from None
    else:
        operands = []
    return label, head, operands, number


def _number(token, *, line):
    """A source number: decimal, or `0x`/`0b`/`0o`, or negative."""
    try:
        return int(token, 0)
    except ValueError:
        pass
    try:
        return int(token, 10)
    except ValueError:
        raise AssemblyError("%r is not a number" % (token,), line=line,
                            token=token) from None


def _register(token, *, line):
    index = REG_INDEX.get(token)
    if index is None:
        raise AssemblyError("%r is not a register (try r0..r15, or %s)"
                            % (token, ", ".join(REG_NAMES[:4]) + ", ..."),
                            line=line, token=token)
    return index


def _operand_fields(op, operands, *, line, labels, position):
    """`(rd, rs1, rs2, imm)` for one instruction's operands."""
    letters = op.fmt
    # the immediate of a format that has other operands may be left out: it is 0
    if (letters and letters[-1] == "i" and len(letters) > 1
            and len(operands) == len(letters) - 1):
        operands = operands + ["0"]
    if len(operands) != len(letters):
        raise AssemblyError(
            "%s takes %d operand%s, got %d" % (op.name, len(letters),
                                               "" if len(letters) == 1 else "s",
                                               len(operands)),
            line=line, token=op.name)
    fields = {"rd": 0, "rs1": 0, "rs2": 0, "imm": 0}
    names = {"d": "rd", "a": "rs1", "b": "rs2", "i": "imm"}
    for letter, operand in zip(letters, operands):
        if letter == "i":
            if operand in labels:
                value = labels[operand]
            elif operand.lstrip("+-").isdigit() or operand.lstrip("+-")[:2].lower() in ("0x", "0b", "0o"):
                value = _number(operand, line=line)
            else:
                raise UndefinedLabel(operand, line=line)
            if not IMM_MIN <= value <= IMM_MAX:
                raise AssemblyError(
                    "immediate %d does not fit in %d signed bits (%d..%d)"
                    % (value, IMM_BITS, IMM_MIN, IMM_MAX), line=line,
                    token=operand)
            fields["imm"] = value & ((1 << IMM_BITS) - 1)
        else:
            fields[names[letter]] = _register(operand, line=line)
    return fields["rd"], fields["rs1"], fields["rs2"], fields["imm"]


def _encode(op, fields):
    """One instruction word, from an opcode and its four fields."""
    rd, rs1, rs2, imm = fields
    return (((op.code & ((1 << OPCODE_BITS) - 1)) << OPCODE_SHIFT)
            | ((rd & ((1 << REG_BITS) - 1)) << RD_SHIFT)
            | ((rs1 & ((1 << REG_BITS) - 1)) << RS1_SHIFT)
            | ((rs2 & ((1 << REG_BITS) - 1)) << RS2_SHIFT)
            | (imm & ((1 << IMM_BITS) - 1)))


def assemble_lines(text):
    """`tuple[(line_number, word), ...]` for a program's source text.

    The line numbers are the source's (1-based), which is what an error message
    has to name and what a disassembly-of-one-instruction cannot tell you.
    """
    if not isinstance(text, str):
        raise AssemblyError("a program is text, got %r" % (type(text).__name__,),
                            line=None)
    parsed = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = _parse_line(number, raw)
        if line is not None and (line[0] is not None or line[1] is not None
                                 or line[2]):
            parsed.append(line)
    # pass one: every label is the index of the next instruction
    labels = {}
    position = 0
    for label, name, _, number in parsed:
        if label is not None:
            if label in labels:
                raise AssemblyError("label %r is defined twice" % (label,),
                                    line=number, token=label)
            labels[label] = position
        if name is not None:
            position += 1
    # pass two: encode, now that every label is a number
    words = []
    position = 0
    for label, name, operands, number in parsed:
        if name is None:
            continue
        op = BY_NAME.get(name)
        if op is None:
            raise AssemblyError("unknown mnemonic %r (try %s)"
                                % (name, ", ".join(sorted(BY_NAME)[:5]) + ", ..."),
                                line=number, token=name)
        fields = _operand_fields(op, operands, line=number, labels=labels,
                                 position=position)
        words.append((number, _encode(op, fields)))
        position += 1
    return tuple(words)


def assemble(text):
    """`tuple[int, ...]`: the words of a program's source text."""
    return tuple(word for _, word in assemble_lines(text))


# ---------------------------------------------------------------------------
# the programs (a catalogue, not a test suite: their results are checked by the
# course's own checks, which compute what they expect from the machine)
# ---------------------------------------------------------------------------

_PROGRAM_SOURCES = {
    "sum_to_n": """\
# v0 = 1 + 2 + ... + a0 (0 when a0 is 0). A counted loop: a compare, a branch,
# and an accumulator. The branch is not taken until the end, so the pipeline
# sees a taken branch exactly once.
        li   v0, 0
        li   t0, 0
loop:   slt  t1, t0, a0
        jz   t1, done
        addi t0, t0, 1
        add  v0, v0, t0
        jmp  loop
done:   halt
""",
    "factorial": """\
# v0 = a0! (1 when a0 is 0), computed by a called routine: `jal` links the
# return address in `ra`, and the routine returns with `jmp ra`. Exercises the
# link register and a call/return pair the pipeline has to keep in order.
main:   mov  a1, a0
        jal  ra, fact
        jmp  end
fact:   li   v0, 1
loop:   jz   a1, ret
        mul  v0, v0, a1
        addi a1, a1, -1
        jmp  loop
ret:    jr   ra
end:    halt
""",
    "fib": """\
# v0 = fib(a0), with the counter kept in memory: every iteration is a
# `lw` immediately followed by an instruction that needs its value, which is
# the load-use hazard, and a `sw` to the same address the next load reads.
        li   t0, 0
        li   t1, 1
        li   t2, 8
        li   t3, 0
        sw   t2, t3, 0
loop:   lw   t3, t2, 0
        slt  s0, t3, a0
        jz   s0, done
        add  s1, t0, t1
        mov  t0, t1
        mov  t1, s1
        addi t3, t3, 1
        sw   t2, t3, 0
        jmp  loop
done:   mov  v0, t0
        halt
""",
    "memcpy": """\
# copy a2 bytes from a0 to a1, one byte at a time, then fall through to halt.
# Byte addressing, no alignment to rely on, and a loop whose branch is taken
# often: the control hazard on a long run.
        li   t0, 0
loop:   slt  t1, t0, a2
        jz   t1, done
        add  t2, a0, t0
        lb   t3, t2, 0
        add  s0, a1, t0
        sb   s0, t3, 0
        addi t0, t0, 1
        jmp  loop
done:   halt
""",
    "count_bits": """\
# v0 = the number of 1 bits in a0. Shifts and masks: `srl t0, t0, t2` shifts by
# `t2 & 31`, so a shift amount of 33 would be a shift of 1 — this program only
# ever shifts by 1, and the course's check is what tests the masking.
        li   v0, 0
        li   t2, 1
        mov  t0, a0
loop:   jz   t0, done
        and  t1, t0, t2
        add  v0, v0, t1
        srl  t0, t0, t2
        jmp  loop
done:   halt
""",
}

#: the catalogue: name -> source text. Read-only: a stage may assemble these,
#: never edit them.
PROGRAMS = types.MappingProxyType(_PROGRAM_SOURCES)
