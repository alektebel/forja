"""CPU From Scratch — course manifest.

Ten graded stages that build a working 32-bit machine: the word algebra and the
flags, a decoder for a real encoding, the register file, the ALU, byte-addressed
memory, the control unit, the record of what a machine did, and then a
five-stage pipeline that runs the same programs and retires the same trace —
first correctly and slowly, then correctly and quickly, with forwarding, the
one stall no wiring can remove, and a branch flush. The last stage measures both
machines and reports the CPI.

The thesis of the whole course is one sentence, and every stage's check asserts
it: ONE PROGRAM, TWO MACHINES, ONE RESULT. A pipeline that is faster because it
computes something else is the bug this course exists to make impossible to
ship, and the way it is made impossible is that every machine has to produce
the same architectural trace and the same fingerprint, instruction for
instruction, while the cycle counts differ in exactly the way the model says.

The instruction set, the assembler and the five programs are provided
(`isa.py`, complete and proven); the exercise is the machine: fetch, decode,
execute, fault, retire and pipeline it. No network, no wall clock, no
unseeded randomness and no module-level mutable state: cycles are counted, not
timed, and two runs of a program produce the same words, the same trace and the
same report.

    python3 codecraft/cli.py run cpu-from-scratch
"""

from codecraft.api import stage

TITLE = "CPU From Scratch"
DESCRIPTION = ("A real datapath from scratch on a provided ISA: mask a 32-bit "
               "word and derive the flags, decode an encoding whose unused "
               "fields must not become operands, keep a register file whose "
               "zero register cannot be written and whose snapshots are "
               "copies, divide and take remainders the way hardware does and "
               "not the way Python does, address bytes with alignment and "
               "bounds checked before anything is stored, fetch and execute and "
               "record a trace where a fault is data rather than an exception, "
               "and then run the same programs on a five-stage pipeline that "
               "must retire the identical trace — with a stall for every "
               "dependency at first, and then with forwarding, a one-cycle "
               "load-use stall and a branch flush — before measuring both "
               "machines and reporting the CPI.")
LEVEL = "intermediate"
ORDER = 16

# --- the checks. Each one is self-contained: its fixtures are nested
# inside it because `course.py` is one namespace for ten stages.

import os
import shutil
import sys
import tempfile
import hashlib


def check_1():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _is_refused(fn, *args, **kwargs):
        """True when the call raises `ValueError` (a refusal, not a crash)."""
        try:
            fn(*args, **kwargs)
        except ValueError:
            return True
        except Exception as exc:                                    # noqa: BLE001
            raise AssertionError("refused with the wrong type: %s: %s"
                                 % (type(exc).__name__, exc))
        return False

    import isa
    import stage_01 as s

    # --- the constants are the provided module's, not re-derived copies -----
    assert (s.WORD_BITS, s.WORD_MASK) == (isa.WORD_BITS, isa.WORD_MASK), \
        "WORD_BITS/WORD_MASK must be re-exported from isa, got %r" \
        % ((s.WORD_BITS, s.WORD_MASK),)
    assert (s.IMM_MIN, s.IMM_MAX) == (isa.IMM_MIN, isa.IMM_MAX) == (-8192, 8191), \
        "the immediate range is the ISA's -8192..8191, got %r" % ((s.IMM_MIN, s.IMM_MAX),)

    # --- word: a mask, at both ends of the range ---------------------------
    assert s.word(0) == 0, "word(0) is 0, got %r" % (s.word(0),)
    assert s.word(-1) == 0xFFFFFFFF, \
        "word(-1) must be the all-ones word 0xFFFFFFFF, not %r (a mask is not a " \
        "truncation toward zero)" % (s.word(-1),)
    assert s.word(2**32) == 0, \
        "word(2**32) must wrap to 0, not stay %r" % (s.word(2**32),)
    assert s.word(2**32 + 5) == 5, \
        "word(2**32 + 5) must be 5, got %r" % (s.word(2**32 + 5),)
    assert s.word(0xFFFFFFFF) == 0xFFFFFFFF, \
        "word(0xFFFFFFFF) must be unchanged, got %r" % (s.word(0xFFFFFFFF),)
    for value in (0, 1, 0x12345678, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF):
        assert s.word(value) == value, \
            "a word value must survive the mask: word(%r) == %r" % (value, s.word(value))

    # --- signed: a reinterpretation, not an arithmetic shift ---------------
    assert s.signed(0) == 0, "signed(0) is 0, got %r" % (s.signed(0),)
    assert s.signed(0x7FFFFFFF) == 2**31 - 1, \
        "signed(0x7FFFFFFF) is the largest positive word, got %r" % (s.signed(0x7FFFFFFF),)
    assert s.signed(0x80000000) == -2**31, \
        "signed(0x80000000) must be -2**31 (subtract 2**32, do not add a sign), got %r" \
        % (s.signed(0x80000000),)
    assert s.signed(0xFFFFFFFF) == -1, \
        "signed(0xFFFFFFFF) must be -1, got %r" % (s.signed(0xFFFFFFFF),)
    for value in range(-300, 300):
        assert s.signed(s.word(value)) == value, \
            "signed(word(%r)) must round-trip, got %r" % (value, s.signed(s.word(value)))

    # --- sign_extend: the top bit is replicated upward ---------------------
    assert s.sign_extend(0x3FFF, 14) == -1, \
        "sign_extend(0x3FFF, 14) must be -1 (the top bit is set), got %r" \
        % (s.sign_extend(0x3FFF, 14),)
    assert s.sign_extend(0x2000, 14) == -8192, \
        "sign_extend(0x2000, 14) must be -8192, got %r" % (s.sign_extend(0x2000, 14),)
    assert s.sign_extend(0x1FFF, 14) == 8191, \
        "sign_extend(0x1FFF, 14) must be 8191 (top bit clear), got %r" \
        % (s.sign_extend(0x1FFF, 14),)
    assert s.sign_extend(0, 14) == 0, "sign_extend(0, 14) is 0, got %r" % (s.sign_extend(0, 14),)
    assert s.sign_extend(1, 1) == -1, \
        "sign_extend(1, 1) must be -1 (a one-bit sign), got %r" % (s.sign_extend(1, 1),)
    assert s.sign_extend(0xFFFFFFFF, 14) == -1, \
        "sign_extend must take the low `bits` bits first: sign_extend(0xFFFFFFFF, 14) " \
        "must be -1, got %r" % (s.sign_extend(0xFFFFFFFF, 14),)
    for value in range(isa.IMM_MIN, isa.IMM_MAX + 1):
        assert s.sign_extend(value, isa.IMM_BITS) == value, \
            "a 14-bit signed value must be its own extension: sign_extend(%r, 14) == %r" \
            % (value, s.sign_extend(value, isa.IMM_BITS))

    # --- fits_imm: the inclusive bounds, and a bool is not an immediate -----
    assert s.fits_imm(-8192) is True, \
        "fits_imm(-8192) must be True (inclusive lower bound), got %r" % (s.fits_imm(-8192),)
    assert s.fits_imm(8191) is True, \
        "fits_imm(8191) must be True (inclusive upper bound), got %r" % (s.fits_imm(8191),)
    assert s.fits_imm(-8193) is False, \
        "fits_imm(-8193) must be False (one below the range), got %r" % (s.fits_imm(-8193),)
    assert s.fits_imm(8192) is False, \
        "fits_imm(8192) must be False (one above the range), got %r" % (s.fits_imm(8192),)
    assert s.fits_imm(1) is True, \
        "the int 1 *is* an immediate; only the bool is refused, got %r" % (s.fits_imm(1),)
    assert s.fits_imm(True) is False, \
        "fits_imm(True) must be False: True == 1 fits, but a bool is not an immediate " \
        "(got %r)" % (s.fits_imm(True),)
    assert s.fits_imm(False) is False, \
        "fits_imm(False) must be False: a bool is not an immediate, got %r" % (s.fits_imm(False),)
    for value in range(isa.IMM_MIN, isa.IMM_MAX + 1):
        assert s.fits_imm(value) is True, \
            "every 14-bit signed value fits: fits_imm(%r) was %r" % (value, s.fits_imm(value))
    assert s.fits_imm(isa.IMM_MIN - 1) is False and s.fits_imm(isa.IMM_MAX + 1) is False, \
        "the values just outside the range must not fit"

    # --- shift_amount: the bottom five bits ---------------------------------
    assert s.shift_amount(0) == 0, "shift_amount(0) is 0, got %r" % (s.shift_amount(0),)
    assert s.shift_amount(31) == 31, "shift_amount(31) is 31, got %r" % (s.shift_amount(31),)
    assert s.shift_amount(32) == 0, \
        "shift_amount(32) must be 0 (the hardware shifts by 32 & 31), got %r" \
        % (s.shift_amount(32),)
    assert s.shift_amount(33) == 1, \
        "shift_amount(33) must be 1, got %r" % (s.shift_amount(33),)
    assert s.shift_amount(63) == 31, \
        "shift_amount(63) must be 31 (no shift past a word), got %r" % (s.shift_amount(63),)

    # --- Flags is a value type, four fields wide ---------------------------
    F = s.Flags
    assert F._fields == ("zero", "negative", "carry", "overflow"), \
        "Flags must be the four named fields zero/negative/carry/overflow, got %r" \
        % (F._fields,)
    one = F(True, False, False, False)
    assert isinstance(one, tuple) and len(one) == 4, \
        "a Flags must be a 4-tuple, got %r" % (one,)
    assert one == F(True, False, False, False), \
        "two Flags compare by value, got %r" % (one,)
    assert one != F(False, True, False, False), \
        "two different Flags must not compare equal, got %r" % (one,)
    assert (one.zero, one.negative, one.carry, one.overflow, one[0]) == \
        (True, False, False, False, True), \
        "the Flags fields are in contract order, got %r" % (one,)

    def flags(zero=False, negative=False, carry=False, overflow=False):
        return s.Flags(zero, negative, carry, overflow)

    def result_of(pair):
        assert isinstance(pair, tuple) and len(pair) == 2, \
            "add_flags/sub_flags must return (result, Flags), got %r" % (pair,)
        return pair

    # --- add_flags: zero, negative, carry, overflow ------------------------
    assert result_of(s.add_flags(0, 0)) == (0, flags(zero=True)), \
        "0 + 0 is zero; every add_flags flag, got %r" % (s.add_flags(0, 0),)
    assert result_of(s.add_flags(5, 3)) == (8, flags()), \
        "5 + 3 sets no flag, got %r" % (s.add_flags(5, 3),)
    assert result_of(s.add_flags(0xFFFFFFFF, 1)) == (0, flags(zero=True, carry=True)), \
        "0xFFFFFFFF + 1 wraps to zero and *carries out* of bit 31, with no signed " \
        "overflow (signs differ): got %r" % (s.add_flags(0xFFFFFFFF, 1),)
    assert result_of(s.add_flags(0x7FFFFFFF, 1)) == (0x80000000, flags(negative=True, overflow=True)), \
        "the largest positive + 1 wraps negative: signed overflow, and no carry: got %r" \
        % (s.add_flags(0x7FFFFFFF, 1),)
    assert result_of(s.add_flags(0x80000000, 0x80000000)) == \
        (0, flags(zero=True, carry=True, overflow=True)), \
        "two negatives summing to zero both carry and overflow: got %r" \
        % (s.add_flags(0x80000000, 0x80000000),)
    assert result_of(s.add_flags(0xFFFFFFFF, 0xFFFFFFFF)) == (0xFFFFFFFE, flags(negative=True, carry=True)), \
        "two negatives stay negative: a carry, but no signed overflow: got %r" \
        % (s.add_flags(0xFFFFFFFF, 0xFFFFFFFF),)
    assert result_of(s.add_flags(2**32, 1)) == (1, flags()), \
        "add_flags must mask its operands before adding: got %r" % (s.add_flags(2**32, 1),)

    # --- sub_flags: zero, negative, carry (no borrow), overflow -------------
    assert result_of(s.sub_flags(5, 3)) == (2, flags(carry=True)), \
        "5 - 3 needs no borrow, so it carries: got %r" % (s.sub_flags(5, 3),)
    assert result_of(s.sub_flags(3, 5)) == (0xFFFFFFFE, flags(negative=True)), \
        "3 - 5 borrows to a negative word, with no carry: got %r" % (s.sub_flags(3, 5),)
    assert result_of(s.sub_flags(0, 1)) == (0xFFFFFFFF, flags(negative=True)), \
        "0 - 1 borrows to the all-ones word: got %r" % (s.sub_flags(0, 1),)
    assert result_of(s.sub_flags(0xFFFFFFFF, 0xFFFFFFFF)) == (0, flags(zero=True, carry=True)), \
        "a word minus itself is zero and carries (a >= b): got %r" \
        % (s.sub_flags(0xFFFFFFFF, 0xFFFFFFFF),)
    assert result_of(s.sub_flags(1, 0xFFFFFFFF)) == (2, flags()), \
        "1 - (-1) is 2 with no flag: the operands differ in sign, so there is no " \
        "overflow, got %r" % (s.sub_flags(1, 0xFFFFFFFF),)
    assert result_of(s.sub_flags(0x80000000, 1)) == (0x7FFFFFFF, flags(carry=True, overflow=True)), \
        "negative - positive turns positive: signed overflow (and no borrow): got %r" \
        % (s.sub_flags(0x80000000, 1),)
    assert result_of(s.sub_flags(0x7FFFFFFF, 0xFFFFFFFF)) == \
        (0x80000000, flags(negative=True, overflow=True)), \
        "positive - negative turns negative: signed overflow, and 0x7FFFFFFF < " \
        "0xFFFFFFFF so no carry: got %r" % (s.sub_flags(0x7FFFFFFF, 0xFFFFFFFF),)
    assert result_of(s.sub_flags(2**32, 1)) == (0xFFFFFFFF, flags(negative=True)), \
        "sub_flags must mask its operands before subtracting: got %r" % (s.sub_flags(2**32, 1),)

    # --- pack_word / unpack_word: four little-endian bytes -----------------
    packed = s.pack_word(0x01020304)
    assert isinstance(packed, bytes) and len(packed) == 4, \
        "pack_word returns four bytes, got %r" % (packed,)
    assert packed == b"\x04\x03\x02\x01", \
        "the bytes are little-endian (least significant first), so pack_word(0x01020304) " \
        "is 04 03 02 01, got %r" % (packed,)
    assert s.pack_word(0) == b"\x00\x00\x00\x00", \
        "pack_word(0) is four zero bytes, got %r" % (s.pack_word(0),)
    assert s.pack_word(-1) == b"\xff\xff\xff\xff", \
        "pack_word(-1) masks first, so it is four 0xff bytes, got %r" % (s.pack_word(-1),)
    assert s.unpack_word(b"\x01\x00\x00\x00") == 1, \
        "unpack_word reads little-endian, so 01 00 00 00 is 1, got %r" \
        % (s.unpack_word(b"\x01\x00\x00\x00"),)
    assert s.unpack_word(b"\x00\x00\x00\x80") == 0x80000000, \
        "the most significant byte is last: got %r" % (s.unpack_word(b"\x00\x00\x00\x80"),)
    assert s.unpack_word(b"\xff\xff\xff\xff") == 0xFFFFFFFF, \
        "four 0xff bytes are the all-ones word, got %r" % (s.unpack_word(b"\xff\xff\xff\xff"),)
    for value in (0, 1, 0x01020304, 0x12345678, 0x80000000, 0xFFFFFFFF):
        assert s.unpack_word(s.pack_word(value)) == value, \
            "pack/unpack must round-trip: %r came back wrong" % (value,)
    assert _is_refused(s.unpack_word, b"\x00\x00\x00"), \
        "unpack_word must refuse a three-byte buffer, not read three bytes of it"
    assert _is_refused(s.unpack_word, b"\x00" * 5), \
        "unpack_word must refuse a five-byte buffer"

    print("check_01: PASS")

def check_2():
    HERE = os.path.dirname(os.path.abspath(__file__))

    COURSE = "cpu-from-scratch"

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _refused(fn, *args, **kwargs):
        """`(exception, message)` when a call is refused, or `(None, None)`."""
        try:
            fn(*args, **kwargs)
        except Exception as exc:                                    # noqa: BLE001
            return exc, str(exc)
        return None, None

    import isa
    import stage_02 as s

    opcode_mask = (1 << isa.OPCODE_BITS) - 1
    reg_mask = (1 << isa.REG_BITS) - 1
    imm_mask = (1 << isa.IMM_BITS) - 1

    def pack(code, rd=0, rs1=0, rs2=0, imm=0):
        return (((code & opcode_mask) << isa.OPCODE_SHIFT)
                | ((rd & reg_mask) << isa.RD_SHIFT)
                | ((rs1 & reg_mask) << isa.RS1_SHIFT)
                | ((rs2 & reg_mask) << isa.RS2_SHIFT)
                | (imm & imm_mask))

    def signed14(raw):
        """The definition the decoder must implement, spelled out here."""
        return raw - (1 << isa.IMM_BITS) if raw >= (1 << (isa.IMM_BITS - 1)) else raw

    def ins(op, rd=0, rs1=0, rs2=0, imm=0, pc=0):
        """An instruction built by hand, field by field.

        The fixtures supply the fields directly, so a check can put junk in a
        field the format does not use — often the point of the fixture — rather
        than letting `decode` clear it first.
        """
        assert isinstance(op, isa.Op), "the fixtures are isa.Op records, %r" % (op,)
        return s.Instruction(pc, 0, op, rd, rs1, rs2, imm)

    # --- the exhaustive round trip, over every opcode and every field --------
    patterns = [
        ("all fields zero", (0, 0, 0, 0)),
        ("all fields at their maximum", (reg_mask, reg_mask, reg_mask, imm_mask)),
        ("a mixed pattern (negative immediate)", (1, 2, 3, 0x2AAA)),
        ("a mixed pattern (positive immediate)", (4, 5, 6, 0x1234)),
    ]
    for op in isa.OPS:
        fmt = op.fmt
        uses_rd = "d" in fmt
        uses_rs1 = "a" in fmt
        uses_rs2 = "b" in fmt
        uses_imm = "i" in fmt
        for why, (rd, rs1, rs2, imm) in patterns:
            word = pack(op.code, rd, rs1, rs2, imm)
            decoded = s.decode(word, pc=11)
            assert decoded.pc == 11 and decoded.word == word, \
                "the instruction remembers its pc and its word, got %r" % (decoded,)
            assert decoded.op is op, \
                "op is the isa.Op of the word's opcode, got %r" % (decoded.op,)
            for field, used_here, got, raw in (
                    ("rd", uses_rd, decoded.rd, rd),
                    ("rs1", uses_rs1, decoded.rs1, rs1),
                    ("rs2", uses_rs2, decoded.rs2, rs2)):
                expected = raw if used_here else 0
                assert got == expected, \
                    ("%s %s: %s reads as %r, expected %r — a used field must "
                     "come from its own shift, and a field the format does not "
                     "use must read as 0" % (op.name, why, field, got, expected,))
            expected_imm = signed14(imm) if uses_imm else 0
            assert decoded.imm == expected_imm, \
                ("%s %s: imm reads as %r, expected %r — the immediate is signed "
                 "%d-bit and only a format with 'i' has one"
                 % (op.name, why, decoded.imm, expected_imm, isa.IMM_BITS))
            clean = pack(op.code,
                         rd if uses_rd else 0, rs1 if uses_rs1 else 0,
                         rs2 if uses_rs2 else 0, imm if uses_imm else 0)
            assert s.encode(decoded) == clean, \
                ("%s %s: encode(decode(w)) is %#010x, expected %#010x — the "
                 "round trip is exact for the fields the format uses and only "
                 "for those" % (op.name, why, s.encode(decoded), clean))
            if word != clean:
                assert s.encode(decoded) != word, \
                    ("%s %s: encode(decode(w)) reproduced %#010x's junk in an "
                     "unused field" % (op.name, why, word))

    # --- every immediate, twice over ----------------------------------------
    li = isa.BY_CODE[2]
    for value in range(isa.IMM_MIN, isa.IMM_MAX + 1):
        word = s.encode(s.Instruction(0, 0, li, 1, 0, 0, value))
        back = s.decode(word)
        assert back.imm == value, \
            ("li r1, %d decodes back to imm %r — the immediate must sign-extend "
             "across the whole %d..%d range"
             % (value, back.imm, isa.IMM_MIN, isa.IMM_MAX))
        assert (word & imm_mask) == (value & imm_mask), \
            "the immediate bits of li r1, %d are %#x" % (value, word & imm_mask)

    # --- the opcode field, over all four patterns ---------------------------
    for code in range(1 << isa.OPCODE_BITS):
        for why, (rd, rs1, rs2, imm) in patterns:
            word = pack(code, rd, rs1, rs2, imm)
            assert s.opcode(word) == code, \
                ("opcode() is the top %d bits (%s), got %r for %#010x — it must "
                 "not validate and must not mask with the register width"
                 % (isa.OPCODE_BITS, why, s.opcode(word), word))

    # --- an unknown opcode is refused, and the refusal carries the word -----
    for code in range(29, 1 << isa.OPCODE_BITS):
        word = pack(code, reg_mask, reg_mask, reg_mask, imm_mask)
        exc, message = _refused(s.decode, word, pc=99)
        assert isinstance(exc, s.BadInstruction), \
            ("opcode %d decoded to %r instead of raising BadInstruction"
             % (code, exc))
        assert isinstance(exc, ValueError), \
            "BadInstruction is a ValueError (%r is not)" % (type(exc).__name__,)
        assert exc.word == word and exc.pc == 99, \
            ("BadInstruction carries .word=%r and .pc=%r, expected %#010x and 99"
             % (exc.word, exc.pc, word))
        assert "0x%08x" % word in message, \
            "the refusal names the word in hex, got %r" % (message,)
        assert str(code) in message, \
            "the refusal names the opcode %d, got %r" % (code, message)
    assert s.opcode(pack(63, 15, 15, 15, imm_mask)) == 63, \
        "opcode() reports the field even when nothing has that number"

    # --- registers(): reads, writes, and r0 ---------------------------------
    t0, t1, t2, t3, sp, ra = 8, 9, 10, 11, 14, 15
    for op_name, operands, reads, writes, why in (
        ("nop", dict(), (), (), "a nop touches nothing"),
        ("halt", dict(), (), (), "a halt touches nothing"),
        ("li", dict(rd=t0, imm=5), (), (t0,), "li reads no register"),
        ("li", dict(rd=0, imm=5), (), (), "a write to r0 is dropped"),
        ("mov", dict(rd=t0, rs1=t1), (t1,), (t0,), "mov reads rs1 and writes rd"),
        ("add", dict(rd=t0, rs1=t1, rs2=t2), (t1, t2), (t0,),
         "add reads both sources"),
        ("add", dict(rd=0, rs1=0, rs2=t2), (t2,), (),
         "a write to r0 is not a read of r0"),
        ("add", dict(rd=t1, rs1=t1, rs2=t1), (t1,), (t1,),
         "the same register on both sides is one index, sorted and distinct"),
        ("add", dict(rd=t3, rs1=t1, rs2=t0), (t0, t1), (t3,),
         "the two tuples are sorted by index, not by operand order"),
        ("sw", dict(rd=reg_mask, rs1=t2, rs2=t3, imm=4), (t2, t3), (),
         "sw has no destination: its rd field is not a register it writes"),
        ("lw", dict(rd=t0, rs1=sp, imm=-8), (sp,), (t0,),
         "lw reads its base register"),
        ("jz", dict(rs1=t1, imm=7), (t1,), (), "jz reads rs1"),
        ("beq", dict(rs1=t1, rs2=t2, imm=3), (t1, t2), (), "beq reads both"),
        ("jal", dict(rd=ra, imm=9), (), (ra,), "jal writes rd and reads nothing"),
        ("jal", dict(rd=0, imm=9), (), (), "jal to r0 writes nothing"),
        ("jr", dict(rs1=ra), (ra,), (), "jr reads rs1"),
        ("jmp", dict(rd=reg_mask, rs1=reg_mask, imm=9), (), (),
         "jmp has no operands but its target"),
    ):
        op = isa.BY_NAME[op_name]
        decoded = ins(op, **operands)
        got = s.registers(decoded)
        assert isinstance(got, tuple) and len(got) == 2 \
            and all(isinstance(side, tuple) for side in got), \
            "registers() returns two tuples, got %r" % (got,)
        assert got == (reads, writes), \
            ("registers(%s) is %r, expected %r — %s"
             % (op_name, got, (reads, writes), why))

    # --- disassemble(): the spelling ----------------------------------------
    for op_name, operands, text, why in (
        ("nop", dict(), "nop", "an opcode with no operands is just its name"),
        ("halt", dict(), "halt", "an opcode with no operands is just its name"),
        ("add", dict(rd=t0, rs1=t1, rs2=t2), "add t0, t1, t2", "rd, rs1, rs2"),
        ("sub", dict(rd=1, rs1=2, rs2=3), "sub at, v0, v1", "register names"),
        ("addi", dict(rd=t0, rs1=t1, imm=-1), "addi t0, t1, -1",
         "addi is not a memory op: a plain comma list, with the signed immediate"),
        ("addi", dict(rd=t0, rs1=t1, imm=8191), "addi t0, t1, 8191", "the top"),
        ("mov", dict(rd=t0, rs1=t1), "mov t0, t1", "rd, rs1"),
        ("li", dict(rd=t0, imm=5), "li t0, 5", "li prints its destination"),
        ("li", dict(rd=t0, imm=-8192), "li t0, -8192", "the bottom"),
        ("lw", dict(rd=t0, rs1=13, imm=4), "lw t0, 4(s1)",
         "a load prints imm(rs1), not three comma-separated operands"),
        ("lb", dict(rd=t0, rs1=12, imm=-8), "lb t0, -8(s0)",
         "a byte load, with a negative offset"),
        ("sw", dict(rs1=t2, rs2=t3, imm=0), "sw t3, 0(t2)",
         "a store prints its value, then imm(rs1)"),
        ("sb", dict(rs1=sp, rs2=t1, imm=2), "sb t1, 2(sp)", "a byte store"),
        ("jmp", dict(imm=12), "jmp 12",
         "an immediate-only opcode prints no register at all"),
        ("jz", dict(rs1=t1, imm=7), "jz t1, 7", "rs1, imm"),
        ("jnz", dict(rs1=t1, imm=-2), "jnz t1, -2", "a negative target"),
        ("beq", dict(rs1=t1, rs2=t2, imm=3), "beq t1, t2, 3", "rs1, rs2, imm"),
        ("bne", dict(rs1=t1, rs2=t2, imm=-3), "bne t1, t2, -3", "a negative target"),
        ("jal", dict(rd=ra, imm=9), "jal ra, 9", "jal prints its link register"),
        ("jr", dict(rs1=ra), "jr ra", "jr prints its register"),
        ("jmp", dict(rd=reg_mask, rs1=reg_mask, imm=0), "jmp 0",
         "jmp ignores the fields it does not have"),
    ):
        op = isa.BY_NAME[op_name]
        got = s.disassemble(ins(op, **operands))
        assert got == text, \
            ("disassemble(%s) is %r, expected %r — %s"
             % (op_name, got, text, why))
    for op_name in ("nop", "li", "addi", "jmp", "jz", "jal"):
        text = s.disassemble(ins(isa.BY_NAME[op_name],
                                 rd=reg_mask, rs1=reg_mask, rs2=reg_mask, imm=1))
        assert "(" not in text, \
            "only a load or a store prints an address, got %r for %s" % (text, op_name)

    # --- decode's defaults and refusals -------------------------------------
    assert s.decode(pack(0)).pc == 0, "pc defaults to 0"
    assert isinstance(s.decode(pack(0)), s.Instruction), \
        "decode returns an Instruction"
    exc, message = _refused(s.decode, 0, pc=5)
    assert exc is None, "nop is a legal encoding, got %r" % (message,)
    assert s.encode(ins(isa.BY_NAME["li"], rd=t0, imm=-1)) == pack(2, rd=t0, imm=-1), \
        "encode of li t0, -1 is its 14-bit two's-complement pattern"
    # the classic missing mask: a negative immediate reaching the opcode's bits
    assert s.opcode(s.encode(ins(isa.BY_NAME["li"], rd=t0, imm=-1))) == 2, \
        "a negative immediate must be masked before it is packed"
    assert s.opcode(s.encode(ins(isa.BY_NAME["sw"], rs1=t2, rs2=t3, imm=-4))) == 19, \
        "a negative store offset must be masked before it is packed"
    # encode writes only the fields the format has
    assert s.encode(ins(isa.BY_NAME["mov"], rd=t0, rs1=t1, rs2=reg_mask, imm=imm_mask)) \
        == pack(3, rd=t0, rs1=t1), \
        "encode(mov) must not write the rs2 and imm fields it has no operands for"
    assert s.encode(ins(isa.BY_NAME["sw"], rd=reg_mask, rs1=t2, rs2=t3, imm=4)) \
        == pack(19, rs1=t2, rs2=t3, imm=4), \
        "encode(sw) must not write an rd field that is not a destination"

def check_3():
    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _refusal(fn, *args, **kwargs):
        """The message when a call is refused with `ValueError`, or None otherwise."""
        try:
            fn(*args, **kwargs)
        except ValueError as exc:
            return str(exc)
        except Exception:                                            # noqa: BLE001
            return None
        return None

    def _expect_refusal(fn, value, why):
        """Assert `fn` refuses with a `ValueError` whose message names `value`."""
        message = _refusal(fn)
        assert message is not None, "%s must be refused with ValueError (value %r)" % (why, value)
        assert repr(value) in message, \
            "the refusal of %s names the offending value %r, got %r" % (why, value, message)

    import isa
    import stage_03 as s

    # --- the re-exports are the ISA's --------------------------------------
    assert (s.ZERO, s.RA, s.SP) == (isa.ZERO, isa.RA, isa.SP) == (0, 15, 14), \
        "ZERO/RA/SP must be isa's indexes (0/15/14), got %r" % ((s.ZERO, s.RA, s.SP),)

    # --- a fresh file is sixteen zeros -------------------------------------
    fresh = s.RegisterFile()
    snap = fresh.snapshot()
    assert isinstance(snap, tuple) and len(snap) == isa.NUM_REGS, \
        "a fresh register file is a tuple of 16 values, got %r" % (snap,)
    assert snap == (0,) * isa.NUM_REGS, "a fresh register file is all zeros, got %r" % (snap,)

    # --- read and write every one of the sixteen registers -----------------
    rf = s.RegisterFile()
    for index in range(isa.NUM_REGS):
        rf.write(index, 0x10000 + index)
    want = tuple(0 if index == 0 else 0x10000 + index for index in range(isa.NUM_REGS))
    assert rf.snapshot() == want, \
        "all sixteen registers hold what was written, with r0 hardwired to 0: %r" % (rf.snapshot(),)
    for index in range(isa.NUM_REGS):
        assert rf.read(index) == want[index], \
            "read(%d) must return what write(%d) stored, got %r" % (index, index, rf.read(index))

    # --- every name the ISA knows resolves to its index --------------------
    for name in isa.REG_NAMES:
        index = isa.REG_INDEX[name]
        assert rf.read(name) == want[index], \
            "read(%r) must be register %d, got %r" % (name, index, rf.read(name))
    for index in range(isa.NUM_REGS):
        for spelling in ("r%d" % index, "$%d" % index):
            assert rf.read(spelling) == want[index], \
                "read(%r) must be register %d, got %r" % (spelling, index, rf.read(spelling))
    rf2 = s.RegisterFile()
    rf2.write("$8", 0xCAFEBABE)
    assert rf2.read(8) == 0xCAFEBABE, \
        "a write through the spelling %r lands in register 8, got %r" % ("$8", rf2.read(8))

    # --- the aliasing proof: a snapshot is a copy, and later writes cannot
    #     reach it (and a restore is a copy of the state it was handed) ------
    rf = s.RegisterFile()
    rf.write(8, 0xDEADBEEF)
    saved = rf.snapshot()
    rf.write(8, 0x11111111)
    rf.write(9, 0x22222222)
    rf.write("t1", 3)
    assert saved[8] == 0xDEADBEEF, \
        ("a snapshot is a copy: writing t0 afterwards changed the saved snapshot to %r"
         % (saved[8],))
    assert saved == (0,) * 8 + (0xDEADBEEF,) + (0,) * 7, \
        "a snapshot is a value; the file's later writes must not move it: %r" % (saved,)

    given = [0xAA, 0xBB, 0xCC, 0xDD] + [0] * 12
    rf.restore(given)
    restored = rf.snapshot()
    rf.write(1, 0x99999999)
    given[3] = 0x12345678
    assert restored[1] == 0xBB, \
        "after restore(), writing a register must not change a snapshot taken before it: %r" % (restored[1],)
    assert restored == (0, 0xBB, 0xCC, 0xDD) + (0,) * 12, \
        "restore() must copy the values it is given, not keep them: %r" % (restored,)
    assert rf.read(3) == 0xDD, \
        "restore() copies: mutating the caller's list afterwards must not reach the file, got %r" % (rf.read(3),)

    # --- writes are masked to a word ---------------------------------------
    rf = s.RegisterFile()
    rf.write(1, 0x1_0000_0001)
    assert rf.read(1) == 1, "a 64-bit write is masked to a word, got %r" % (rf.read(1),)
    rf.write(2, -1)
    assert rf.read(2) == 0xFFFFFFFF, "a negative write is masked, got %r" % (rf.read(2),)
    rf.write(3, 2 ** 64 - 1)
    assert rf.read(3) == 0xFFFFFFFF, "a huge value is masked, got %r" % (rf.read(3),)
    assert rf.snapshot()[1] == 1 and rf.snapshot()[2] == 0xFFFFFFFF, \
        "the snapshot shows the masked values, got %r" % (rf.snapshot(),)

    # --- a write to r0 is dropped, not an error, for every spelling ---------
    for value in (1, 0xFFFFFFFF, -1, 2 ** 64 - 1, 0):
        for spelling in (0, "zero", "r0", "$0"):
            rf = s.RegisterFile()
            assert _refusal(rf.write, spelling, value) is None, \
                "a write to %r is dropped, not refused (value %r)" % (spelling, value)
            assert rf.snapshot()[0] == 0, \
                "a write of %r to %r leaves r0 at 0, got %r" % (value, spelling, rf.snapshot()[0])
    rf = s.RegisterFile()
    for value in (1, 0xFFFFFFFF, -1, 2 ** 64 - 1):
        rf.restore((value,) + (0,) * (isa.NUM_REGS - 1))
        assert rf.snapshot()[0] == 0, \
            "restore() forces r0 to 0 whatever value it is handed (%r), got %r" % (value, rf.snapshot()[0])

    # --- restore is exactly sixteen values, masked -------------------------
    rf = s.RegisterFile()
    rf.restore(tuple(range(isa.NUM_REGS)))
    assert rf.snapshot() == (0,) + tuple(range(1, isa.NUM_REGS)), \
        "restore() sets every register and forces r0 to 0, got %r" % (rf.snapshot(),)
    rf.restore((0, 0x1_0000_0001, 2 ** 64 - 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15))
    assert (rf.read(1), rf.read(2), rf.read(15)) == (1, 0xFFFFFFFF, 15), \
        "restore() masks each value to a word, got %r" % (rf.snapshot(),)
    for short in ((), (0,) * (isa.NUM_REGS - 1), (0,) * (isa.NUM_REGS + 1), tuple(range(20))):
        message = _refusal(rf.restore, short)
        assert message is not None, \
            "restore() with %d values must be refused: a state that is not 16 values is not a state" % (len(short),)
        assert repr(len(short)) in message, \
            "the refusal names the number of values given (%d), got %r" % (len(short), message)

    # --- initial: a mapping by name, a 16-sequence, both masked and r0=0 ---
    named = s.RegisterFile(initial={"t0": 5, "v0": 0x1_0000_0001, "zero": 7, 1: -1})
    assert named.read("t0") == 5, "an initial mapping sets the named register, got %r" % (named.read("t0"),)
    assert named.read("v0") == 1, "an initial value is masked to a word, got %r" % (named.read("v0"),)
    assert named.read(1) == 0xFFFFFFFF, "an initial mapping may use an index as a key, got %r" % (named.read(1),)
    assert named.snapshot()[0] == 0, \
        "an initial mapping cannot make r0 non-zero, got %r" % (named.snapshot()[0],)

    sequence = s.RegisterFile(initial=[0, 0x1_0000_0002, 2 ** 64 - 1, 4, 5, 6, 7, 8,
                                       9, 10, 11, 12, 13, 14, 15, 16])
    assert sequence.snapshot() == (0, 2, 0xFFFFFFFF, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16), \
        "a 16-sequence initial populates the file in order, each masked, r0 forced to 0: %r" \
        % (sequence.snapshot(),)
    assert s.RegisterFile(initial=(0,) * isa.NUM_REGS).snapshot() == (0,) * isa.NUM_REGS, \
        "a 16-tuple initial is accepted, not only a list"

    # --- refused initial values --------------------------------------------
    for bad_initial, why in (
        (list(range(isa.NUM_REGS - 1)), "an initial sequence of 15 values"),
        (list(range(isa.NUM_REGS + 1)), "an initial sequence of 17 values"),
        ({"t0": 1, "nope": 2}, "an initial mapping with an unknown name"),
        ({"t0": 1, 16: 2}, "an initial mapping with an out-of-range index"),
        ("a" * isa.NUM_REGS, "an initial that is a string of the right length"),
    ):
        message = _refusal(s.RegisterFile, bad_initial)
        assert message is not None, "%s must be refused" % (why,)

    # --- two files from one initial are equal and independent --------------
    seed = {"t0": 5, "s0": 9, "sp": 0x1000}
    left = s.RegisterFile(seed)
    right = s.RegisterFile(seed)
    assert left.snapshot() == right.snapshot(), \
        "two files built from the same initial are equal: %r vs %r" % (left.snapshot(), right.snapshot())
    left.write("t0", 0xAB)
    left.write(s.RA, 0xCD)
    assert right.read("t0") == 5 and right.read(s.RA) == 0, \
        "one file's writes must never appear in another: t0=%r ra=%r" % (right.read("t0"), right.read(s.RA))
    assert left.snapshot() != right.snapshot(), "the two files must now differ"
    seeded = s.RegisterFile(seed)
    assert seeded.snapshot() == right.snapshot(), \
        "the initial mapping is not consumed by building a file: %r vs %r" % (seeded.snapshot(), right.snapshot())

    # --- a bad index is refused, with the value named ----------------------
    rf = s.RegisterFile()
    rf.write(4, 0x42)
    before = rf.snapshot()
    for bad in (-1, isa.NUM_REGS, True, False, "nope", "$99", "r16", 1.0, None, 2 ** 31):
        _expect_refusal(lambda: rf.read(bad), bad, "read(%r)" % (bad,))
        _expect_refusal(lambda: rf.write(bad, 1), bad, "write(%r, 1)" % (bad,))
    assert rf.snapshot() == before, \
        "a refused write must leave the file untouched, got %r" % (rf.snapshot(),)
    assert rf.read(4) == 0x42, "a refused call must not have written register 4: %r" % (rf.read(4),)

    print("check_03: PASS")

def check_4():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _word(value):
        return value & 0xFFFFFFFF

    def _signed(value):
        value &= 0xFFFFFFFF
        return value - (1 << 32) if value >> 31 else value

    def _tdiv(x, y):
        """The ISA's division, by hand: truncated toward zero."""
        quotient = abs(x) // abs(y)
        return -quotient if (x < 0) != (y < 0) else quotient

    def _tmod(x, y):
        """The ISA's remainder, by hand: the dividend's sign."""
        return x - _tdiv(x, y) * y

    import isa
    import stage_04 as s
    from stage_01 import Flags, add_flags, sub_flags

    # --- the set of ops, exactly -------------------------------------------
    expected = frozenset({4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17})
    assert isinstance(s.ALU_OPS, frozenset), \
        "ALU_OPS must be a frozenset, got %r" % (type(s.ALU_OPS).__name__,)
    assert s.ALU_OPS == expected, \
        "ALU_OPS is exactly the arithmetic and logic subset; got %r" \
        % (sorted(s.ALU_OPS),)

    no_flags = Flags(False, False, False, False)

    # --- every accepted op returns a masked int and a Flags -----------------
    for code in sorted(s.ALU_OPS):
        for a, b in ((0, 0), (0xFFFFFFFF, 0xFFFFFFFF), (1, 0)):
            if code in (7, 8) and b == 0:
                continue
            value, flags = s.alu(code, a, b)
            assert type(value) is int and 0 <= value <= 0xFFFFFFFF, \
                "op %d on %r/%r must produce a masked int word, got %r" \
                % (code, a, b, value)
            assert type(flags).__name__ == "Flags", \
                "op %d must return (value, Flags), got flags %r" % (code, flags)

    # --- a refusal is a plain ValueError naming the opcode ------------------
    for code in (0, 1, 2, 3, 9) + tuple(range(18, 30)) + (99, -1):
        try:
            outcome = s.alu(code, 1, 1)
        except ValueError as exc:
            assert type(exc) is ValueError, \
                ("an opcode outside ALU_OPS is a plain ValueError, not %r "
                 "(ArithmeticFault is only for div/mod by zero)"
                 % (type(exc).__name__,))
            spoken = isa.mnemonic(code)
            assert spoken in str(exc) or ("%d" % code) in str(exc), \
                "the refusal names the opcode %r (%s), got %r" \
                % (code, spoken, str(exc))
        else:
            raise AssertionError(
                "alu accepted opcode %r, which is not an ALU operation: %r"
                % (code, outcome))

    # --- operands that are not words are refused, not masked ----------------
    for bad in ("7", True, False, 2.5, None):
        for slot in ("a", "b"):
            args = (4, bad, 1) if slot == "a" else (4, 1, bad)
            try:
                outcome = s.alu(*args)
            except ValueError:
                continue
            raise AssertionError(
                "alu must refuse a %s %s operand rather than mask it: got %r"
                % (type(bad).__name__, slot, outcome))

    # --- add/sub carry stage 1's flags; every other op carries none ---------
    pairs = ((0, 0), (1, 1), (5, 3), (3, 5), (0xFFFFFFFF, 1), (0x7FFFFFFF, 1),
             (0x80000000, 0x80000000), (0xFFFFFFFF, 0xFFFFFFFF), (0x80000000, 1))
    for a, b in pairs:
        assert s.alu(4, a, b) == add_flags(a, b), \
            "add's flags must be stage 1's add_flags for %r/%r: got %r, want %r" \
            % (a, b, s.alu(4, a, b), add_flags(a, b))
        assert s.alu(5, a, b) == sub_flags(a, b), \
            "sub's flags must be stage 1's sub_flags for %r/%r: got %r, want %r" \
            % (a, b, s.alu(5, a, b), sub_flags(a, b))

    for code in (6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17):
        for a, b in pairs:
            if code in (7, 8) and b == 0:
                continue
            value, flags = s.alu(code, a, b)
            assert flags == no_flags, \
                ("op %d invents a flag: only add and sub set flags, and there is "
                 "no flag register; got %r for %r/%r" % (code, flags, a, b))

    # --- division truncates toward zero: all four sign combinations ---------
    for x in range(-9, 10):
        for y in range(-9, 10):
            if y == 0:
                continue
            value, _ = s.alu(7, _word(x), _word(y))
            want = _word(_tdiv(x, y))
            assert value == want, \
                ("div(%r, %r) must truncate toward zero (got %r); Python's // "
                 "floors and would give %r" % (x, y, value, _word(x // y)))
            value, _ = s.alu(8, _word(x), _word(y))
            want = _word(_tmod(x, y))
            assert value == want, \
                ("mod(%r, %r) must keep the dividend's sign (got %r); Python's "
                 "%% gives %r" % (x, y, value, _word(x % y)))

    # --- multiplication is the low 32 bits, negative operands included ------
    for x in range(-9, 10):
        for y in range(-9, 10):
            value, _ = s.alu(6, _word(x), _word(y))
            assert value == _word(x * y), \
                "mul(%r, %r) must be the low 32 bits of the product, got %r" \
                % (x, y, value)
    value, _ = s.alu(6, 0xFFFFFFFF, 0xFFFFFFFF)
    assert value == 1, \
        "mul(0xFFFFFFFF, 0xFFFFFFFF) is the low 32 bits, 1, got %r" % (value,)

    # --- shifts mask their amount; sra reads its operand as signed ----------
    shift_values = (0, 1, 0x7FFFFFFF, 0x80000000, 0xFFFFFFFF)
    for amount in (0, 1, 31, 32, 33):
        k = amount & 31
        for a in shift_values:
            value, _ = s.alu(13, a, amount)
            assert value == _word(a << k), \
                ("sll(%#x, %d) must mask the amount to %d, got %#x; an unmasked "
                 "shift by 32 would empty the word" % (a, amount, k, value))
            value, _ = s.alu(14, a, amount)
            assert value == _word(a >> k), \
                "srl(%#x, %d) must mask the amount to %d, got %#x" \
                % (a, amount, k, value)
            value, _ = s.alu(15, a, amount)
            assert value == _word(_signed(a) >> k), \
                ("sra(%#x, %d) must shift the signed value by %d and mask the "
                 "amount, got %#x" % (a, amount, k, value))

    # --- slt is signed, sltu is unsigned ------------------------------------
    for a, b, less_signed, less_unsigned in (
        (0xFFFFFFFF, 1, 1, 0),
        (1, 0xFFFFFFFF, 0, 1),
        (_word(-1), 1, 1, 0),
        (0x80000000, 0, 1, 0),
        (0, 0x80000000, 0, 1),
    ):
        value, _ = s.alu(16, a, b)
        assert type(value) is int and value == less_signed, \
            ("slt(%#x, %#x) compares signed: signed %r < signed %r is %r, got %r"
             % (a, b, _signed(a), _signed(b), less_signed, value))
        value, _ = s.alu(17, a, b)
        assert type(value) is int and value == less_unsigned, \
            ("sltu(%#x, %#x) compares unsigned: %r < %r is %r, got %r"
             % (a, b, a, b, less_unsigned, value))

    # --- (0, 0) is a boundary every op survives, and operands are masked ----
    for code in sorted(s.ALU_OPS):
        if code in (7, 8):
            continue
        value, _ = s.alu(code, 0, 0)
        assert value == 0, "op %d on (0, 0) is 0, got %r" % (code, value)
    assert s.alu(4, -1, 0)[0] == 0xFFFFFFFF, \
        "an unmasked negative operand is still a word: add(-1, 0) is 0xFFFFFFFF"
    assert s.alu(13, -1, 1)[0] == 0xFFFFFFFE, \
        "sll must mask its operand: -1 << 1 is 0xFFFFFFFE, got %r" \
        % (s.alu(13, -1, 1)[0],)

    # --- div and mod by zero are an ArithmeticFault that names the pc -------
    for code, op in ((7, "div"), (8, "mod")):
        for pc in (0, 42, 8191):
            for a, b in ((7, 0), (0, 0), (0xFFFFFFFF, 0)):
                try:
                    outcome = s.alu(code, a, b, pc=pc)
                except s.ArithmeticFault as exc:
                    assert isinstance(exc, ValueError), \
                        "ArithmeticFault is a ValueError, got %r" % (type(exc).__mro__,)
                    assert isinstance(exc.detail, str) and exc.detail, \
                        "ArithmeticFault carries a non-empty .detail, got %r" \
                        % (exc.detail,)
                    assert ("%d" % pc) in str(exc), \
                        "the ArithmeticFault names the pc %d, got %r" % (pc, str(exc))
                    assert op in str(exc), \
                        "the ArithmeticFault names the operation %r, got %r" \
                        % (op, str(exc))
                else:
                    raise AssertionError(
                        "%s by zero at pc %d must raise ArithmeticFault, not "
                        "return %r" % (op, pc, outcome))

    assert issubclass(s.ArithmeticFault, ValueError), \
        "ArithmeticFault must subclass ValueError, the contract's inheritance"

    print("check_04: ALU_OPS is %d ops, div/mod exhaustive over %d signed pairs, "
          "shifts by 0/1/31/32/33, slt/sltu on the sign boundary and the "
          "ArithmeticFault — all asserted"
          % (len(s.ALU_OPS), 19 * 18))

def check_5():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("F3_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "cpu-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set F3_REPO=/path/to/forja")

    def _fault(fn, *args, **kwargs):
        """The exception a refused call raised, or None when it was not refused."""
        import stage_05 as s
        try:
            fn(*args, **kwargs)
        except s.AddressFault as exc:
            return exc
        except Exception as exc:                                        # noqa: BLE001
            return RuntimeError("WRONG TYPE: %s: %s" % (type(exc).__name__, exc))
        return None

    def _expect_fault(s, desc, fn, *args, **kwargs):
        exc = _fault(fn, *args, **kwargs)
        assert isinstance(exc, s.AddressFault), \
            "%s must be refused with an AddressFault, got %r" % (desc, exc)
        return exc

    import stage_05 as s

    assert issubclass(s.AddressFault, ValueError), \
        "AddressFault must stay a ValueError, got %r" % (s.AddressFault.__mro__,)
    assert s.DEFAULT_SIZE == 4096, \
        "a Memory with no size argument is 4096 bytes, got %r" % (s.DEFAULT_SIZE,)
    assert s.ACCESS_SIZES == (1, 2, 4), \
        "memory serves exactly the sizes 1, 2 and 4, got %r" % (s.ACCESS_SIZES,)

    big = s.Memory()
    assert len(big) == 4096, "a default Memory is 4096 bytes long, got %r" % (len(big),)
    m = s.Memory(16)
    assert len(m) == 16, "Memory(16) is 16 bytes long, got %r" % (len(m),)
    assert bytes(m.snapshot()) == b"\x00" * 16, \
        "memory starts zero-filled, got %r" % (bytes(m.snapshot()),)

    # --- a legal access is legal at the edges ------------------------------
    assert m.load(15, 1) == 0, \
        "a one-byte access is legal at the last byte, got %r" % (m.load(15, 1),)
    assert m.load(14, 2) == 0, \
        "a two-byte access ending at the last byte is legal, got %r" % (m.load(14, 2),)
    assert m.load(12, 4) == 0, \
        "a four-byte access ending at the last byte is legal, got %r" % (m.load(12, 4),)
    m.store(15, 1, 0x7F)
    assert m.load(15, 1) == 0x7F, \
        "a one-byte store/load at the last byte round-trips, got %r" % (m.load(15, 1),)

    refusals = 0

    # --- out of bounds, first byte or last ---------------------------------
    for address, size in ((16, 1), (17, 1), (-1, 1), (-4, 4), (15, 2), (14, 4), (13, 4)):
        exc = _expect_fault(
            s, "a %r-byte load at %r on a 16-byte memory" % (size, address),
            m.load, address, size)
        assert exc.address == address and exc.size == size, \
            "the fault names the access it refused, got address=%r size=%r" \
            % (exc.address, exc.size)
        refusals += 1
    exc = _expect_fault(s, "a two-byte load at len-1 (its second byte is past the end)",
                        m.load, 15, 2)
    assert "15" in str(exc), \
        "the fault message names the address with %%r, got %r" % (str(exc),)
    assert isinstance(exc.detail, str) and exc.detail, \
        "the fault carries a `.detail` label, got %r" % (exc.detail,)

    # --- an ALIGNED access whose last byte is past the end -----------------
    # (the check is the last byte's; alignment must not be the only thing that
    # saves the bounds rule, so these are aligned and still out of bounds)
    odd = s.Memory(15)
    exc = _expect_fault(s, "an aligned four-byte load ending past a 15-byte memory",
                        odd.load, 12, 4)
    assert exc.detail == s.DETAIL_OUT_OF_BOUNDS, \
        "an aligned access past the end is refused as out of bounds, got %r" \
        % (exc.detail,)
    _expect_fault(s, "an aligned two-byte load ending past a 15-byte memory",
                  odd.load, 14, 2)
    assert odd.load(8, 4) == 0 and odd.load(12, 2) == 0, \
        "the aligned accesses that just fit a 15-byte memory are still legal"
    refusals += 2

    # --- an unsupported size, including a bool -----------------------------
    for size in (0, 3, 5, -1, True, False, 8):
        exc = _expect_fault(s, "a load of size %r" % (size,), m.load, 0, size)
        assert exc.size == size, \
            "the size fault names the size it refused, got %r" % (exc.size,)
        refusals += 1

    # --- a non-integer address ---------------------------------------------
    for address in ("0", 1.0, None, True, False):
        exc = _expect_fault(s, "a load at address %r" % (address,), m.load, address, 1)
        assert exc.address == address, \
            "the address fault names the address it refused, got %r" % (exc.address,)
        refusals += 1

    # --- an unaligned multi-byte access ------------------------------------
    for address, size in ((1, 2), (3, 2), (1, 4), (2, 4), (3, 4), (10, 4)):
        exc = _expect_fault(
            s, "an unaligned %r-byte load at %r" % (size, address), m.load, address, size)
        assert exc.size == size, \
            "the alignment fault names the size, got %r" % (exc.size,)
        refusals += 1

    # --- a refusal writes nothing ------------------------------------------
    m = s.Memory(16)
    m.store(0, 4, 0xDEADBEEF)
    before = bytes(m.snapshot())
    for desc, args in (
        ("an out-of-bounds store", (15, 2, 0xFFFF)),
        ("an unaligned store", (1, 2, 0xFFFF)),
        ("a store of an unsupported size", (0, 3, 0xFFFFFF)),
        ("a store at a negative address", (-1, 1, 0xFF)),
        ("a store whose last byte is past the end", (14, 4, 0xFFFFFFFF)),
        ("a store at a bool size", (0, True, 0xFF)),
    ):
        _expect_fault(s, desc, m.store, *args)
        assert bytes(m.snapshot()) == before, \
            "%s must leave memory byte-identical, got %r" % (desc, bytes(m.snapshot()))
    assert m.load(0, 4) == 0xDEADBEEF, \
        "the refused stores did not disturb the word that was there, got %r" \
        % (m.load(0, 4),)

    # --- little-endian, and the round trip ---------------------------------
    m = s.Memory(16)
    m.store(0, 4, 0x01020304)
    assert m.load(0, 4) == 0x01020304, \
        "a four-byte store/load round-trips, got %r" % (m.load(0, 4),)
    assert bytes(m.snapshot()[:4]) == b"\x04\x03\x02\x01", \
        "a word is stored little-endian (low byte first), got %r" \
        % (bytes(m.snapshot()[:4]),)

    # --- a two-byte store touches exactly two bytes ------------------------
    m = s.Memory(8)
    m.store(0, 4, 0xAABBCCDD)
    m.store(2, 2, 0x1122)
    assert bytes(m.snapshot()) == b"\xdd\xcc\x22\x11\x00\x00\x00\x00", \
        ("a two-byte store replaces exactly two bytes, the low two, little-endian; "
         "got %r" % (bytes(m.snapshot()),))
    assert m.load(0, 4) == 0x1122CCDD, \
        "only the low half of the word changed, got %r" % (m.load(0, 4),)

    # --- a one-byte load zero-extends, never sign-extends -------------------
    m = s.Memory(4)
    m.store(0, 1, 0xFF)
    assert m.load(0, 1) == 0xFF, \
        "a one-byte load zero-extends 0xFF to 255, got %r" % (m.load(0, 1),)
    m.store(1, 1, 0x80)
    assert m.load(1, 1) == 0x80, \
        "a one-byte load zero-extends 0x80 (it is not -128), got %r" % (m.load(1, 1),)
    m.store(2, 2, 0xFFFF)
    assert m.load(2, 2) == 0xFFFF, \
        "a two-byte load zero-extends 0xFFFF, got %r" % (m.load(2, 2),)

    # --- a store is masked to its size -------------------------------------
    m = s.Memory(8)
    m.store(0, 4, (1 << 40) + 7)
    assert m.load(0, 4) == 7, \
        "a four-byte store keeps only the low 32 bits, got %r" % (m.load(0, 4),)
    m.store(4, 1, 0x1FF)
    assert m.load(4, 1) == 0xFF, \
        "a one-byte store keeps only the low byte, got %r" % (m.load(4, 1),)
    m.store(0, 2, (1 << 32) + 9)
    assert m.load(0, 2) == 9, \
        "a two-byte store keeps only the low two bytes, got %r" % (m.load(0, 2),)

    # --- a snapshot is an immutable copy -----------------------------------
    m = s.Memory(4)
    m.store(0, 4, 0x01020304)
    before = m.snapshot()
    m.store(0, 1, 0xFE)
    assert before == b"\x04\x03\x02\x01", \
        "a snapshot is a snapshot: storing into memory afterwards does not change it, got %r" \
        % (before,)
    assert m.load(0, 4) == 0x010203FE, \
        "the live memory did change when it was stored into, got %r" % (m.load(0, 4),)
    first = m.snapshot()
    second = m.snapshot()
    assert isinstance(first, bytes), \
        "snapshot returns an immutable `bytes`, got %r" % (type(first).__name__,)
    assert first == second, \
        "two snapshots of the same memory are equal, got %r vs %r" % (first, second)
    if hasattr(m, "_data"):
        assert m.snapshot() is not m._data, \
            "snapshot hands out a copy, not the internal buffer"

    # --- two memories share nothing ----------------------------------------
    p = s.Memory(16)
    q = s.Memory(16)
    p.store(0, 1, 0xFF)
    assert p.load(0, 1) == 0xFF, "the store went where it was asked, got %r" % (p.load(0, 1),)
    assert q.load(0, 1) == 0, \
        "two Memory(16) instances are independent, got %r" % (q.load(0, 1),)

    print("check_05: %d refusals and %d legal accesses asserted over memory"
          % (refusals, 10))

def check_6():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _started(program, regs=None, **kwargs):
        """A machine on ``program`` (source text or words), seeded with ``regs``."""
        import stage_06 as s
        import isa
        source = isa.assemble(program) if isinstance(program, str) else program
        return s.Machine(source, initial=regs, **kwargs)

    import isa
    import stage_02 as s2
    import stage_06 as s

    A0, A1, A2 = (isa.REG_INDEX[n] for n in ("a0", "a1", "a2"))
    T0, T1 = isa.REG_INDEX["t0"], isa.REG_INDEX["t1"]
    V0, RA = isa.REG_INDEX["v0"], isa.REG_INDEX["ra"]

    assert s.FAULT_KINDS == ("illegal", "arith", "address", "fetch"), \
        "FAULT_KINDS is %r" % (s.FAULT_KINDS,)
    assert s.STATUSES == ("running", "halted", "faulted", "budget"), \
        "STATUSES is %r" % (s.STATUSES,)

    # --- the catalogue: each program's result, computed by the machine -----
    for name, regs, expected in (
            ("sum_to_n", {"a0": 10}, 55), ("sum_to_n", {"a0": 0}, 0),
            ("factorial", {"a0": 6}, 720), ("factorial", {"a0": 0}, 1),
            ("factorial", {"a0": 1}, 1),
            ("fib", {"a0": 10}, 55), ("fib", {"a0": 0}, 0),
            ("count_bits", {"a0": 0xF0F0}, 8), ("count_bits", {"a0": 0}, 0)):
        machine = _started(isa.PROGRAMS[name], regs)
        assert s.run(machine, max_steps=2000) is machine, "run did not return the machine"
        assert machine.status == "halted", \
            "%r with %r did not reach its halt: status %r" % (name, regs, machine.status)
        assert machine.registers.read(V0) == expected, \
            "%r with %r gives v0 %r, not %r" % (name, regs, machine.registers.read(V0), expected)
        assert machine.cycles == machine.retired == len(machine.trace), \
            "%r: cycles/retired/trace are %r/%r/%r, not one per instruction" \
            % (name, machine.cycles, machine.retired, len(machine.trace))

    # --- memcpy: byte addressing, source untouched, exactly a2 bytes ---------
    machine = _started(isa.PROGRAMS["memcpy"], {"a0": 32, "a1": 96, "a2": 5})
    source = (0x11, 0x22, 0x33, 0x44, 0x55)
    for offset, byte in enumerate(source):
        machine.memory.store(32 + offset, 1, byte)
    s.run(machine, max_steps=2000)
    assert machine.status == "halted", "memcpy did not halt: %r" % (machine.status,)
    left = tuple(machine.memory.load(32 + i, 1) for i in range(5))
    copied = tuple(machine.memory.load(96 + i, 1) for i in range(5))
    assert left == source, "memcpy changed its source: %r" % (left,)
    assert copied == source, "memcpy copied %r, not %r" % (copied, source)
    assert machine.memory.load(101, 1) == 0, \
        "memcpy copied a byte past a2: %r" % (machine.memory.load(101, 1),)
    stores = tuple(effect for row in machine.trace for effect in row.writes
                   if effect[0] == "m")
    assert stores and stores[0] == ("m", 96, 1, 0x11), \
        "a store's traced effect is wrong: %r" % (stores[0] if stores else None,)

    # --- beq and bne branch on equality, and only on equality ----------------
    machine = _started("li t0, 3\nli t1, 3\nbeq t0, t1, hit\nli v0, 1\nhalt\n"
                       "hit: li v0, 2\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.registers.read(V0) == 2, \
        "beq did not branch when the operands are equal: v0 is %r" \
        % (machine.registers.read(V0),)
    machine = _started("li t0, 3\nli t1, 4\nbeq t0, t1, hit\nli v0, 1\nhalt\n"
                       "hit: li v0, 2\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.registers.read(V0) == 1, \
        "beq branched when the operands differ: v0 is %r" % (machine.registers.read(V0),)
    machine = _started("li t0, 3\nli t1, 4\nbne t0, t1, hit\nli v0, 1\nhalt\n"
                       "hit: li v0, 2\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.registers.read(V0) == 2, \
        "bne did not branch when the operands differ: v0 is %r" % (machine.registers.read(V0),)
    machine = _started("li t0, 3\nli t1, 3\nbne t0, t1, hit\nli v0, 1\nhalt\n"
                       "hit: li v0, 2\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.registers.read(V0) == 1, \
        "bne branched when the operands are equal: v0 is %r" % (machine.registers.read(V0),)
    machine = _started("li t0, 1\njnz t0, hit\nli v0, 1\nhalt\n"
                       "hit: li v0, 2\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.registers.read(V0) == 2, \
        "jnz did not branch on a non-zero register: v0 is %r" % (machine.registers.read(V0),)
    machine = _started("li t0, 0\njnz t0, hit\nli v0, 1\nhalt\n"
                       "hit: li v0, 2\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.registers.read(V0) == 1, \
        "jnz branched on a zero register: v0 is %r" % (machine.registers.read(V0),)

    # --- jal links pc + 1, and jr ra returns to the next instruction ---------
    machine = _started("jal ra, sub\nli v0, 1\nhalt\nsub: li v0, 2\njr ra\n")
    s.run(machine, max_steps=1)
    assert machine.pc == 3, "jal did not jump to the callee: pc %r" % (machine.pc,)
    assert machine.registers.read(RA) == 1, \
        "jal did not link pc + 1: ra is %r" % (machine.registers.read(RA),)
    assert machine.trace[0].writes == (("r", RA, 1),), \
        "jal's link is not the call's only effect: %r" % (machine.trace[0].writes,)
    machine = _started("jal ra, sub\nli v0, 1\nhalt\nsub: li v0, 2\njr ra\n")
    s.run(machine, max_steps=2000)
    assert machine.status == "halted", "the call/return pair did not halt: %r" % (machine.status,)
    assert [row.pc for row in machine.trace] == [0, 3, 4, 1, 2], \
        "jr ra did not return to the instruction after the call: %r" \
        % ([row.pc for row in machine.trace],)
    assert machine.registers.read(V0) == 1, \
        "the callee's jr ra landed on the wrong instruction: v0 is %r" % (machine.registers.read(V0),)

    # --- every fault kind is recorded; the faulting word does not retire -----
    machine = _started((63 << isa.OPCODE_SHIFT,))
    s.run(machine, max_steps=2000)
    assert machine.status == "faulted" and machine.fault.kind == "illegal", \
        "an unknown opcode is not an illegal fault: %r/%r" % (machine.status, machine.fault)
    assert machine.fault.pc == 0 and machine.trace == (), \
        "the faulting instruction was retired: pc %r, trace %r" % (machine.fault.pc, machine.trace)
    assert machine.fault.detail, "the illegal fault names no detail: %r" % (machine.fault.detail,)
    assert machine.pc == 0, "a fault advanced the pc to %r" % (machine.pc,)

    machine = _started("li t1, 0\ndiv t0, t1, t1\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.status == "faulted" and machine.fault.kind == "arith", \
        "dividing by zero is not an arith fault: %r/%r" % (machine.status, machine.fault)
    assert machine.fault.pc == 1 and len(machine.trace) == 1, \
        "the faulting div was retired: pc %r, trace %r" % (machine.fault.pc, machine.trace)
    assert machine.fault.detail and machine.retired == 1 and machine.cycles == 1, \
        "an arith fault counted wrong: detail %r, retired %r, cycles %r" \
        % (machine.fault.detail, machine.retired, machine.cycles)
    assert machine.pc == 1, "an arith fault advanced the pc to %r" % (machine.pc,)

    for program in ("li t1, 4096\nlw t0, t1, 0\nhalt\n",
                    "li t1, 4096\nsw t1, t1, 0\nhalt\n"):
        machine = _started(program)
        s.run(machine, max_steps=2000)
        assert machine.status == "faulted" and machine.fault.kind == "address", \
            "an out-of-bounds access is not an address fault in %r: %r/%r" \
            % (program, machine.status, machine.fault)
        assert machine.fault.pc == 1 and len(machine.trace) == 1, \
            "the faulting access was retired in %r: pc %r, trace %r" \
            % (program, machine.fault.pc, machine.trace)
        assert machine.fault.detail, "the address fault names no detail: %r" % (machine.fault.detail,)

    machine = _started("nop\n")
    s.run(machine, max_steps=2000)
    assert machine.status == "faulted" and machine.fault.kind == "fetch", \
        "a pc past the program is not a fetch fault: %r/%r" % (machine.status, machine.fault)
    assert machine.fault.pc == 1 and len(machine.trace) == 1 and machine.pc == 1, \
        "the fetch fault retired an instruction: pc %r, trace %r" % (machine.fault.pc, machine.trace)

    machine = _started("nop\n", pc=-1)
    s.run(machine, max_steps=2000)
    assert machine.status == "faulted" and machine.fault.kind == "fetch" \
        and machine.fault.pc == -1, \
        "a negative pc is not a fetch fault: %r/%r" % (machine.status, machine.fault)

    # --- a faulted machine's further steps are no-ops ------------------------
    machine = _started((63 << isa.OPCODE_SHIFT,))
    s.run(machine, max_steps=2000)
    frozen = (machine.status, machine.fault, machine.cycles, machine.retired, machine.trace)
    s.step(machine)
    s.step(machine)
    s.run(machine, max_steps=3)
    assert (machine.status, machine.fault, machine.cycles, machine.retired, machine.trace) == frozen, \
        "a faulted machine kept running: %r" % ((machine.status, machine.retired, machine.trace),)

    # --- halt retires, advances the pc, and stops the machine ----------------
    machine = _started("nop\nli t0, 3\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.status == "halted" and machine.retired == 3, \
        "halt did not stop the machine: %r/%r" % (machine.status, machine.retired)
    assert machine.pc == 3, "a retired halt left the pc at %r, not one past" % (machine.pc,)
    assert machine.trace[0].writes == () and machine.trace[2].writes == (), \
        "a nop or a halt wrote something: %r/%r" \
        % (machine.trace[0].writes, machine.trace[2].writes)
    stopped = (machine.cycles, machine.retired, machine.trace)
    s.step(machine)
    assert (machine.cycles, machine.retired, machine.trace) == stopped, \
        "a halted machine retired another instruction: %r" % (machine.retired,)

    # --- a write to r0 retires, and traces nothing ---------------------------
    machine = _started("li t0, 5\nadd zero, t0, t0\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.retired == 3, "a write to r0 was not retired: %r" % (machine.retired,)
    assert machine.trace[1].pc == 1 and machine.trace[1].writes == (), \
        "a write to r0 left an effect in the trace: %r" % (machine.trace[1].writes,)
    assert machine.registers.read(0) == 0, "r0 changed: %r" % (machine.registers.read(0),)

    # --- li sign-extends the immediate ---------------------------------------
    machine = _started("li t0, -1\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.registers.read(T0) == 0xFFFFFFFF, \
        "li forgot the sign: t0 is %r" % (machine.registers.read(T0),)
    assert machine.trace[0].writes == (("r", T0, 0xFFFFFFFF),), \
        "li's traced value is not its register value: %r" % (machine.trace[0].writes,)
    machine = _started("li t1, -8192\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.registers.read(T1) == 0xFFFFE000, \
        "li -8192 gave %r" % (machine.registers.read(T1),)

    # --- a step cap is a budget, never a fault -------------------------------
    machine = _started("loop: jmp loop\n")
    s.run(machine, max_steps=7)
    assert machine.status == "budget" and machine.fault is None, \
        "a step cap is not a budget stop: %r/%r" % (machine.status, machine.fault)
    assert machine.retired == 7 and machine.cycles == 7 and len(machine.trace) == 7, \
        "the budget stop retired %r on %r cycles" % (machine.retired, machine.cycles)
    machine = _started("nop\nhalt\n")
    s.run(machine, max_steps=100)
    assert machine.status == "halted", \
        "a run that finished early was called a budget: %r" % (machine.status,)
    machine = _started("nop\nhalt\n")
    s.run(machine, max_steps=0)
    assert machine.status == "budget" and machine.retired == 0, \
        "max_steps=0 ran %r instructions and left %r" % (machine.retired, machine.status)

    # --- initial seeds the registers, in all three forms ---------------------
    machine = _started("halt\n", {"a0": 10})
    assert machine.registers.read(A0) == 10, \
        "a name mapping did not seed a0: %r" % (machine.registers.read(A0),)
    machine = _started("halt\n", {A0: 10})
    assert machine.registers.read(A0) == 10, \
        "an index mapping did not seed a0: %r" % (machine.registers.read(A0),)
    machine = _started("halt\n", {0: 10})
    assert machine.registers.read(0) == 0, \
        "the initial mapping made r0 writable: %r" % (machine.registers.read(0),)
    machine = _started("halt\n", tuple([7] * 16))
    assert machine.registers.snapshot() == (0,) + (7,) * 15, \
        "a 16-sequence seed was not applied through word() with r0 at 0: %r" \
        % (machine.registers.snapshot(),)

    # --- reset: the whole architectural state, back to the initial seed ------
    machine = _started(isa.PROGRAMS["count_bits"], {"a0": 0xF0F0})
    s.run(machine, max_steps=2000)
    rows_before = machine.trace
    assert rows_before, "count_bits retired nothing to reset past"
    machine.memory.store(0, 4, 0xDEADBEEF)
    assert s.reset(machine) is machine, "reset did not return the machine"
    assert machine.registers.snapshot() == tuple(
        0xF0F0 if index == A0 else 0 for index in range(16)), \
        "reset did not restore the initial registers: %r" % (machine.registers.snapshot(),)
    assert machine.memory.snapshot() == bytes(4096), \
        "reset kept a memory byte: %r" % (machine.memory.snapshot()[:8],)
    assert machine.pc == 0 and machine.status == "running" and machine.fault is None, \
        "reset kept the pc/status/fault: %r/%r/%r" % (machine.pc, machine.status, machine.fault)
    assert machine.cycles == 0 and machine.retired == 0 and machine.trace == (), \
        "reset kept a counter: %r/%r/%r" % (machine.cycles, machine.retired, machine.trace)
    assert len(rows_before) > 0, \
        "reset mutated the trace it replaced, instead of binding a new one: %r" % (rows_before,)
    s.run(machine, max_steps=2000)
    assert machine.registers.read(V0) == 8, \
        "the machine could not be reset and rerun: v0 is %r" % (machine.registers.read(V0),)
    machine = _started("li t1, 0\ndiv t0, t1, t1\nhalt\n")
    s.run(machine, max_steps=2000)
    assert machine.status == "faulted", "the div-by-zero probe did not fault: %r" % (machine.status,)
    s.reset(machine)
    assert machine.status == "running" and machine.fault is None, \
        "reset kept the fault: %r/%r" % (machine.status, machine.fault)

    # --- the program is a tuple a sw cannot reach ----------------------------
    words = isa.assemble("li t0, 0\nli t1, 7\nsw t0, t1, 0\nhalt\n")
    machine = s.Machine(words)
    s.run(machine, max_steps=2000)
    assert isinstance(machine.program, tuple), \
        "the program is not a tuple: %r" % (type(machine.program),)
    assert machine.program == words, \
        "a store rewrote the program (address 0 is instruction 0): %r" % (machine.program,)
    assert machine.memory.load(0, 4) == 7, \
        "the store did not land in the data memory: %r" % (machine.memory.load(0, 4),)

    words = isa.assemble("li t0, 1000\nli t1, 7\nsw t0, t1, 0\nhalt\n")
    machine = s.Machine(words)
    s.run(machine, max_steps=2000)
    assert machine.program == words, \
        "a store to an address no instruction occupies changed the program: %r" % (machine.program,)

    # --- the trace row is the spec's row -------------------------------------
    machine = _started("li v0, 5\nhalt\n")
    s.run(machine, max_steps=2000)
    assert isinstance(machine.trace, tuple), \
        "the trace is not a tuple: %r" % (type(machine.trace),)
    row = machine.trace[0]
    assert row.pc == 0 and row.word == isa.assemble("li v0, 5")[0], \
        "a trace row names the wrong instruction: %r" % (row,)
    assert row.writes == (("r", V0, 5),), \
        "a trace row's register effect is wrong: %r" % (row.writes,)
    assert row.text == s2.disassemble(s2.decode(row.word, pc=0)), \
        "a trace row's text is not its word disassembled: %r" % (row.text,)

    # --- snapshot() is a value, not the live state ---------------------------
    machine = _started("li v0, 5\nhalt\n", {"a0": 7})
    snap = machine.snapshot()
    assert set(snap) == {"pc", "status", "fault", "registers", "memory", "cycles",
                         "retired", "trace"}, \
        "the snapshot's keys are %r" % (sorted(snap),)
    assert isinstance(snap["registers"], list), \
        "the snapshot's registers are not a value: %r" % (type(snap["registers"]),)
    assert snap["registers"][A0] == 7, \
        "the snapshot's registers do not match the machine: %r" % (snap["registers"][A0],)
    snap["registers"][A0] = 999
    assert machine.registers.read(A0) == 7, \
        "mutating the snapshot's registers changed the machine: a0 is %r" \
        % (machine.registers.read(A0),)
    assert isinstance(snap["memory"], bytes), \
        "the snapshot's memory is not a value: %r" % (type(snap["memory"]),)
    machine.memory.store(8, 4, 0xABCD)
    s.run(machine, max_steps=2000)
    assert snap["registers"][A0] == 999 and machine.registers.read(A0) == 7, \
        "the snapshot and the machine's registers are not independent: %r/%r" \
        % (snap["registers"][A0], machine.registers.read(A0))
    assert snap["memory"] == bytes(4096), \
        "the snapshot follows the machine's memory: %r" % (snap["memory"][:12],)
    assert snap["retired"] == 0 and snap["pc"] == 0 and snap["status"] == "running" \
        and snap["fault"] is None, \
        "the snapshot is the live state: %r" % ((snap["retired"], snap["pc"], snap["status"]),)
    assert machine.retired > 0, "the machine did not run after the snapshot"

    # --- the default data memory is 4 KiB ------------------------------------
    machine = s.Machine(isa.assemble("halt\n"))
    assert len(machine.memory) == 4096, \
        "the default data memory is %r bytes" % (len(machine.memory),)
    machine = _started("li t1, 64\nlw t0, t1, 0\nhalt\n", data_size=64)
    s.run(machine, max_steps=2000)
    assert machine.status == "faulted" and machine.fault.kind == "address", \
        "a machine's own data_size is ignored: %r/%r" % (machine.status, machine.fault)

    print("check_06: PASS")

def check_7():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    SUM = """\
    # t0 = 0 .. a0, summed
            li   t0, 0
            li   a0, 10
    loop:   slt  t1, t0, a0
            jz   t1, done
            addi t0, t0, 1
            jmp  loop
    done:   halt
    """

    def _refused(fn, *args, **kwargs):
        """The error message when a call is refused, or None when it is not."""
        try:
            fn(*args, **kwargs)
        except ValueError as exc:
            return str(exc)
        except Exception as exc:                                    # noqa: BLE001
            return "WRONG TYPE: %s: %s" % (type(exc).__name__, exc)
        return None

    def _run(stage6, machine, **kwargs):
        """`run` returns the machine (contract §2.6); mutating in place is the same
        machine, but accept a `None` for that spelling too."""
        result = stage6.run(machine, **kwargs)
        return machine if result is None else result

    import isa
    import stage_06 as s6
    import stage_07 as s

    catalogue = dict(isa.PROGRAMS)

    # --- a catalogue name is a program, and so is raw source text ----------
    machine = s.load("fib")
    assert isinstance(machine, s6.Machine), \
        "load returns the machine stage 6 defines, got %r" % (type(machine).__name__,)
    expected_words = isa.assemble(isa.PROGRAMS["fib"])
    assert isinstance(machine.program, tuple) and machine.program == expected_words, \
        ("load's machine runs the assembled catalogue text, not a rewrite of it: %r"
         % (machine.program,))
    assert (machine.pc, machine.status) == (0, "running"), \
        ("load returns a machine ready to start, not one that already ran: pc=%r status=%r"
         % (machine.pc, machine.status))
    assert len(machine.memory) == 4096, \
        "load's default data memory is 4096 bytes, got %r" % (len(machine.memory),)
    assert machine.trace == () and machine.retired == 0, \
        ("load assembles and builds; the history is the caller's to spend: trace=%r retired=%r"
         % (machine.trace, machine.retired))
    machine = _run(s6, machine)
    assert machine.status == "halted", \
        "the loaded fib program runs to a halt, got %r" % (machine.status,)

    n = s.load(SUM)
    assert isinstance(n.program, tuple) and n.program == isa.assemble(SUM), \
        "load accepts any source text, not only a catalogue name: %r" % (n.program,)
    n = _run(s6, n)
    assert n.status == "halted" and n.registers.read("t0") == 10, \
        ("a machine loaded from raw text computes the same thing: status=%r t0=%r"
         % (n.status, n.registers.read("t0")))

    # --- the catalogue is read, never written ------------------------------
    a = s.load("fib")
    b = s.load("fib")
    assert a.program == b.program, \
        "two loads of one name assemble to the same words, not to a rewrite: %r" % (a.program,)
    assert isa.PROGRAMS["fib"] == catalogue["fib"], \
        "load must not rewrite the shared catalogue text: %r" % (isa.PROGRAMS["fib"],)
    assert dict(isa.PROGRAMS) == catalogue, \
        "load must not add to or remove from isa.PROGRAMS: %r" % (sorted(isa.PROGRAMS),)

    # --- the pc and the data size belong to the caller ---------------------
    placed = s.load("fib", pc=3, data_size=64)
    assert placed.pc == 3, "load passes its pc through to the machine, got %r" % (placed.pc,)
    assert len(placed.memory) == 64, \
        "load passes its data_size through to the machine, got %r" % (len(placed.memory),)
    assert placed.program == expected_words, \
        "the program does not depend on pc or data_size: %r" % (placed.program,)

    # --- something that is neither a name nor text -------------------------
    message = _refused(s.load, 123)
    assert message is not None, \
        "load refuses something that is neither a catalogue name nor source text"
    assert not message.startswith("WRONG TYPE") and "stage 07" in message, \
        "load refuses a non-str itself, before the assembler sees it: %r" % (message,)

    # --- the trace is the retired instructions, in order -------------------
    halted = _run(s6, s.load(SUM))
    rows = halted.trace
    t = s.trace(halted)
    assert isinstance(t, tuple), "trace returns a tuple, got %r" % (type(t).__name__,)
    assert t == tuple((row.pc, row.word) for row in rows), \
        "the trace is exactly the retired rows, reduced to (pc, word): %r" % (t,)
    assert len(t) == halted.retired == len(rows), \
        ("one trace row per retired instruction: %d rows, %d retirements"
         % (len(t), halted.retired))
    assert len(t) > 10, "the fixture must retire enough to make its limits meaningful: %r" % (len(t),)
    for row in t:
        assert isinstance(row, tuple) and len(row) == 2 and all(isinstance(x, int) for x in row), \
            "a trace row is a (pc, word) pair of two ints, got %r" % (row,)

    # --- a limit is a count, and zero is a count ---------------------------
    assert s.trace(halted, limit=0) == (), \
        "limit=0 is a count of zero rows, not 'no limit': %r" % (s.trace(halted, limit=0),)
    assert s.trace(halted, limit=1) == t[:1], \
        "limit=1 is the first row, got %r" % (s.trace(halted, limit=1),)
    assert s.trace(halted, limit=len(t)) == t, \
        "a limit at the end is the whole trace: %r" % (s.trace(halted, limit=len(t)),)
    assert s.trace(halted, limit=len(t) + 5) == t, \
        ("a limit past the end is the whole trace, not an error: %r"
         % (s.trace(halted, limit=len(t) + 5),))
    assert s.trace(halted, limit=len(t) - 1) == t[:-1], \
        "a limit trims the tail, not the head: %r" % (s.trace(halted, limit=len(t) - 1),)
    assert s.trace(halted, limit=None) == t, "no limit is the whole trace"
    assert s.trace(s.load(SUM)) == (), \
        "a machine that has not run has retired nothing: %r" % (s.trace(s.load(SUM)),)
    halting = _run(s6, s.load("halt\n"))
    assert s.trace(halting) == ((0, isa.assemble("halt\n")[0]),), \
        ("halt retires and is traced like any other instruction: %r" % (s.trace(halting),))
    for bad, why in ((-1, "a negative limit"), (1.5, "a fractional limit"),
                     ("2", "a string limit"), (True, "a boolean limit")):
        message = _refused(s.trace, halted, limit=bad)
        assert message is not None, "%s is refused" % (why,)
        assert not message.startswith("WRONG TYPE"), \
            "%s is refused with this stage's ValueError, got %r" % (why, message)

    # --- the trace stops where the machine stopped -------------------------
    faulting = _run(s6, s.load("li t0, 0\ndiv t0, t0, t0\nhalt\n"))
    assert faulting.status == "faulted" and faulting.fault.kind == "arith", \
        ("the fixture faults on its second instruction: %r/%r"
         % (faulting.status, faulting.fault))
    assert (faulting.pc, faulting.retired) == (1, 1), \
        ("the instruction at a faulting pc never retires: pc=%r retired=%r"
         % (faulting.pc, faulting.retired))
    ft = s.trace(faulting)
    first_word = isa.assemble("li t0, 0\ndiv t0, t0, t0\nhalt\n")[0]
    assert ft == ((0, first_word),), \
        ("the trace excludes the instruction at the faulting pc and everything after it: %r"
         % (ft,))

    ffp = s.fingerprint(faulting)
    assert ffp == (faulting.status, faulting.fault, faulting.pc,
                   faulting.registers.snapshot(),
                   hashlib.sha256(faulting.memory.snapshot()).hexdigest()[:16]), \
        ("a faulted machine's fingerprint names the fault in its second slot: %r" % (ffp,))
    assert ffp[0] == "faulted" and ffp[1] is not None and ffp[1].kind == "arith", \
        "the status and the fault are part of the fingerprint, not dropped: %r" % (ffp,)

    off = _run(s6, s.load("li t0, 5\nli t1, 6\n"))
    assert off.status == "faulted" and off.fault.kind == "fetch", \
        ("a program that walks off its end faults on the fetch: %r/%r"
         % (off.status, off.fault))
    words = isa.assemble("li t0, 5\nli t1, 6\n")
    assert s.trace(off) == ((0, words[0]), (1, words[1])), \
        ("the fetch past the end retires nothing and is not in the trace: %r"
         % (s.trace(off),))
    assert off.retired == 2 and len(s.trace(off)) == 2, \
        "both instructions retired before the fetch fault: %r" % (s.trace(off),)

    # --- two machines that ran the same program are one machine ------------
    first = _run(s6, s.load(SUM))
    second = _run(s6, s.load(SUM))
    assert s.trace(first) == s.trace(second), \
        "same program, same trace: %r vs %r" % (s.trace(first), s.trace(second))
    assert s.fingerprint(first) == s.fingerprint(second), \
        "same program, same fingerprint: %r vs %r" % (s.fingerprint(first), s.fingerprint(second))

    # --- the fingerprint's five parts, in the frozen order -----------------
    fp = s.fingerprint(first)
    assert isinstance(fp, tuple) and len(fp) == 5, \
        ("the fingerprint is the 5-part tuple (status, fault, pc, registers, digest): %r"
         % (fp,))
    expected = (first.status, first.fault, first.pc, first.registers.snapshot(),
                hashlib.sha256(first.memory.snapshot()).hexdigest()[:16])
    assert fp == expected, \
        ("the fingerprint is exactly (status, fault, pc, registers.snapshot(), "
         "sha256(memory)[:16]): %r != %r" % (fp, expected))
    assert isinstance(fp[4], str) and len(fp[4]) == 16, \
        "the memory digest is 16 hex characters, got %r" % (fp[4],)
    assert fp[4] == fp[4].lower() and all(c in "0123456789abcdef" for c in fp[4]), \
        "the digest is lowercase hex, got %r" % (fp[4],)
    assert fp[2] == first.pc and fp[0] == first.status and fp[1] == first.fault, \
        "the fingerprint's first three parts are the machine's status, fault and pc: %r" % (fp,)

    registers = fp[3]
    assert isinstance(registers, tuple) and len(registers) == 16 \
        and all(isinstance(r, int) for r in registers), \
        ("the registers part is a snapshot tuple of 16 ints, not a live object: %r"
         % (registers,))
    assert registers == first.registers.snapshot(), \
        "the registers part is the register file's snapshot: %r" % (registers,)
    assert registers is not first.registers and registers is not fp, \
        "the registers part is a copy, not the file itself"
    assert hash(fp) == hash(s.fingerprint(first)), \
        "no part of a fingerprint is mutable, so a fingerprint hashes: %r" % (fp,)

    first.registers.write(8, 999)
    assert s.fingerprint(first)[3] != fp[3], \
        ("a fingerprint took a snapshot: a later register write must not change it: %r"
         % (fp[3],))
    assert fp[3][8] != 999 and len(fp[3]) == 16, \
        "the old fingerprint's registers must not follow the file: %r" % (fp[3],)

    # --- a fault is part of what a machine did -----------------------------
    halted_same = _run(s6, s.load("li t0, 0\nhalt\n"))
    faulted_same = _run(s6, s.load("li t0, 0\ndiv t0, t0, t0\n"))
    assert halted_same.registers.snapshot() == faulted_same.registers.snapshot(), \
        ("the fixture pair holds identical registers, so only the status separates them: %r"
         % (halted_same.registers.snapshot(),))
    assert s.fingerprint(halted_same)[0] == "halted" \
        and s.fingerprint(faulted_same)[0] == "faulted", \
        "the fixture pair's statuses are halted and faulted"
    assert s.fingerprint(halted_same) != s.fingerprint(faulted_same), \
        ("a machine that faulted must not fingerprint like one that halted on the same "
         "registers: %r" % (s.fingerprint(faulted_same),))

    # --- the digest follows the data memory, not the program ---------------
    one = _run(s6, s.load("li t0, 1\nhalt\n"))
    two = _run(s6, s.load("li t0, 2\nhalt\n"))
    assert one.program != two.program and one.memory.snapshot() == two.memory.snapshot(), \
        "the fixture pair differs only in its program, and both memories are zeroed"
    assert s.fingerprint(one)[4] == s.fingerprint(two)[4], \
        ("two machines that left the same memory share the digest, whatever program ran: %r vs %r"
         % (s.fingerprint(one)[4], s.fingerprint(two)[4]))
    before = s.fingerprint(one)[4]
    one.memory.store(4, 1, 0x41)
    assert s.fingerprint(one)[4] != before, \
        "a byte stored in memory must move the digest, got %r" % (s.fingerprint(one)[4],)

    hand = _run(s6, s.load("li t0, 1\nhalt\n"))
    hand.memory.store(4, 1, 0x41)
    stored = _run(s6, s.load("li t0, 0x41\nli t1, 4\nsb t1, t0, 0\nhalt\n"))
    assert stored.program != hand.program, "the sb fixture runs a different program"
    assert s.fingerprint(stored)[4] == s.fingerprint(hand)[4], \
        ("a program's sb and a hand store of the same byte are the same memory: %r vs %r"
         % (s.fingerprint(stored)[4], s.fingerprint(hand)[4]))

    print("check_07: a name, a source, a trace that stops at the fault, a limit of zero, "
          "and a hashable fingerprint whose digest follows the memory — all asserted "
          "(%d trace rows, %d digest chars)" % (len(t), len(fp[4])))

def check_8():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    CYCLE_CAP = 5000

    PINNED = {
        "sum_to_n":   (5, 15, {"data": 4, "load_use": 0, "control": 2}),
        "factorial":  (7, 19, {"data": 0, "load_use": 0, "control": 8}),
        "fib":        (10, 22, {"data": 6, "load_use": 0, "control": 2}),
        "memcpy":     (4, 14, {"data": 4, "load_use": 0, "control": 2}),
        "count_bits": (5, 13, {"data": 2, "load_use": 0, "control": 2}),
    }

    SQUASH = """\
            li   t0, 1
            beq  t0, t0, taken
            li   t1, 99
    taken:  halt
    """

    UNTAKEN = """\
            li   t0, 5
            jz   t0, skip
            li   t1, 7
    skip:   halt
    """

    WRAP = "li t0, -1\naddi t1, t0, 1\nhalt\n"

    STORE = """\
            li   t0, 0x2a
            li   t1, 8
            sw   t1, t0, 0
            lw   t2, t1, 0
            halt
    """

    import isa
    import stage_06 as s6
    import stage_07 as s7
    import stage_08 as s

    # --- the stage and stall vocabularies are this stage's -----------------
    assert s.STAGES == ("IF", "ID", "EX", "MEM", "WB"), \
        ("the five stages, entry first, are IF ID EX MEM WB, got %r" % (s.STAGES,))
    assert s.STALL_CAUSES == ("data", "load_use", "control"), \
        ("the stall vocabulary is ('data', 'load_use', 'control'), got %r"
         % (s.STALL_CAUSES,))
    fresh = s.Pipeline(())
    assert isinstance(fresh.stages, tuple) and len(fresh.stages) == 5, \
        "stages is the tuple of the five stage slots, got %r" % (fresh.stages,)
    assert dict(fresh.stalls) == {"data": 0, "load_use": 0, "control": 0}, \
        "the stalls dict starts zero-filled with the three causes, got %r" % (fresh.stalls,)

    def run_both(words, **kwargs):
        machine = s6.Machine(words, **kwargs)
        s6.run(machine, max_steps=CYCLE_CAP)
        pipe = s.Pipeline(words, **kwargs)
        s.run_pipeline(pipe, max_cycles=CYCLE_CAP)
        return machine, pipe

    def equivalent(machine, pipe, where):
        assert pipe.trace == machine.trace, \
            ("%s: the pipeline's trace is not the machine's, row for row — a faster "
             "machine that computes something else: pipeline %r, machine %r"
             % (where, pipe.trace, machine.trace))
        fp_pipe, fp_machine = s7.fingerprint(pipe), s7.fingerprint(machine)
        assert fp_pipe == fp_machine, \
            ("%s: same program, different architectural state — fingerprint %r != %r"
             % (where, fp_pipe, fp_machine))

    def stalls_shape(pipe, where):
        assert set(pipe.stalls) == {"data", "load_use", "control"}, \
            ("%s: stalls has exactly the keys ('data', 'load_use', 'control'), got %r"
             % (where, sorted(pipe.stalls)))
        assert all(isinstance(v, int) and v >= 0 for v in pipe.stalls.values()), \
            "%s: a stall count is a non-negative int, got %r" % (where, dict(pipe.stalls))
        assert pipe.stalls["load_use"] == 0, \
            ("%s: this stage has no forwarding, so every dependency is a *data* "
             "stall; load_use must stay 0, got %r" % (where, pipe.stalls["load_use"]))

    def identity(pipe, where):
        total = sum(pipe.stalls.values())
        assert pipe.cycles == pipe.retired + 4 + total, \
            ("%s: the cycle identity cycles == retired + 4 + stalls_total must hold "
             "(cycles=%r, retired=%r, stalls=%r)"
             % (where, pipe.cycles, pipe.retired, dict(pipe.stalls)))

    # --- each catalogue program: one machine, two results ------------------
    for name in sorted(isa.PROGRAMS):
        words = isa.assemble(isa.PROGRAMS[name])
        machine, pipe = run_both(words)
        assert pipe.status == "halted", \
            "%s: the program halts, so the pipeline must too, got %r" % (name, pipe.status)
        stalls_shape(pipe, name)
        equivalent(machine, pipe, name)
        assert pipe.trace == machine.trace and isinstance(pipe.trace, tuple), \
            "%s: the pipeline's trace is the machine's tuple of rows, got %r" \
            % (name, type(pipe.trace).__name__)
        assert pipe.cycles > pipe.retired, \
            ("%s: a five-stage pipeline takes more cycles than it retires "
             "instructions (cycles=%r, retired=%r)" % (name, pipe.cycles, pipe.retired))
        identity(pipe, name)
        retired, cycles, stalls = PINNED[name]
        assert pipe.retired == retired, \
            ("%s: the hazard logic must retire exactly %d instructions, got %r"
             % (name, retired, pipe.retired))
        assert pipe.cycles == cycles, \
            ("%s: a regression in the stall or squash logic changed the cycle count "
             "(expected %d, got %r; stalls %r)" % (name, cycles, pipe.cycles, dict(pipe.stalls)))
        assert dict(pipe.stalls) == stalls, \
            ("%s: the stall counts belong to the hazard logic (expected %r, got %r)"
             % (name, stalls, dict(pipe.stalls)))

    # --- a store reaches the memory and the digest follows it --------------
    words = isa.assemble(STORE)
    machine, pipe = run_both(words)
    assert pipe.registers.read("t2") == 0x2A, \
        ("a load reads back what a store wrote: t2=%r" % (pipe.registers.read("t2"),))
    assert any(pipe.memory.snapshot()), \
        "the store fixture must leave a nonzero byte in memory, got %r" % (pipe.memory.snapshot(),)
    assert pipe.memory.snapshot() == machine.memory.snapshot(), \
        ("a store must reach the same memory as the machine's: %r != %r"
         % (pipe.memory.snapshot()[:16], machine.memory.snapshot()[:16]))
    equivalent(machine, pipe, "store")

    # --- the seed is the machine's seed, r0 included -----------------------
    words = isa.assemble("add v0, a0, a1\nhalt\n")
    seed = {"a0": 5, "a1": 9, "r1": 3, "zero": 7, "sp": -1}
    machine = s6.Machine(words, initial=dict(seed))
    pipe = s.Pipeline(words, initial=dict(seed))
    assert pipe.registers.snapshot() == machine.registers.snapshot(), \
        ("the pipeline must seed its registers exactly as the machine does: %r != %r"
         % (pipe.registers.snapshot(), machine.registers.snapshot()))
    assert pipe.registers.read(0) == 0, \
        ("r0 is hardwired zero even when the seed tries to write it: got %r"
         % (pipe.registers.read(0),))
    s6.run(machine)
    s.run_pipeline(pipe, max_cycles=CYCLE_CAP)
    stalls_shape(pipe, "initial-seeded")
    equivalent(machine, pipe, "initial-seeded")
    assert pipe.registers.read("v0") == 14, \
        "the seeded a0 and a1 reach the program: v0=%r" % (pipe.registers.read("v0"),)
    identity(pipe, "initial-seeded")

    # --- a pc the caller chose is where the pipeline starts ----------------
    words = isa.assemble("li t0, 1\nli t1, 2\nli t2, 3\nhalt\n")
    machine = s6.Machine(words, pc=1)
    s6.run(machine)
    pipe = s.Pipeline(words, pc=1)
    s.run_pipeline(pipe, max_cycles=CYCLE_CAP)
    equivalent(machine, pipe, "pc=1")

    # --- a taken branch squashes the fetch behind it -----------------------
    words = isa.assemble(SQUASH)
    machine, pipe = run_both(words)
    retired_pcs = [row.pc for row in pipe.trace]
    assert 2 not in retired_pcs, \
        ("a taken branch must squash the instruction fetched behind it: pc 2 "
         "(li t1, 99) retired anyway, trace %r" % (retired_pcs,))
    assert pipe.registers.read("t1") == 0, \
        ("the squashed li t1, 99 must not write t1: t1=%r" % (pipe.registers.read("t1"),))
    equivalent(machine, pipe, "taken branch")

    # --- an untaken branch falls through -----------------------------------
    words = isa.assemble(UNTAKEN)
    machine, pipe = run_both(words)
    assert [row.pc for row in pipe.trace] == [0, 1, 2, 3], \
        ("an untaken branch falls through: the instruction after it retires, "
         "trace pcs %r" % ([row.pc for row in pipe.trace],))
    assert pipe.registers.read("t1") == 7, \
        ("the fall-through li t1, 7 must write t1: t1=%r" % (pipe.registers.read("t1"),))
    equivalent(machine, pipe, "untaken branch")

    # --- a result wider than a word is masked ------------------------------
    words = isa.assemble(WRAP)
    machine, pipe = run_both(words)
    assert pipe.registers.read("t1") == 0, \
        ("a computed value is masked to a word: 0xFFFFFFFF + 1 wraps to 0, got %r"
         % (pipe.registers.read("t1"),))
    equivalent(machine, pipe, "wrap")

    # --- the four faults are reported, not raised, and never retire --------
    faults = (
        ("illegal", (63 << isa.OPCODE_SHIFT,), 0),
        ("arith", isa.assemble("li t0, 0\ndiv t0, t0, t0\nhalt\n"), 1),
        ("address", isa.assemble("li t1, 4096\nlw t0, t1, 0\nhalt\n"), 1),
        ("fetch", isa.assemble("li t0, 5\nli t1, 6\n"), 2),
    )
    for kind, words, fault_pc in faults:
        machine, pipe = run_both(words)
        assert machine.status == "faulted" and machine.fault.kind == kind, \
            "the %s fixture must fault in the machine too: %r/%r" \
            % (kind, machine.status, machine.fault)
        assert pipe.status == "faulted", \
            ("%s: a fault is data, not an exception: status=%r" % (kind, pipe.status))
        assert pipe.fault is not None and pipe.fault.kind == kind, \
            ("%s fault is recorded with its kind, got %r" % (kind, pipe.fault))
        assert pipe.fault.pc == fault_pc == machine.fault.pc, \
            ("the %s fault is reported at the faulting pc: %r != %r"
             % (kind, pipe.fault.pc, machine.fault.pc))
        equivalent(machine, pipe, "%s fault" % kind)
        fault_pcs = [row.pc for row in pipe.trace]
        assert fault_pc not in fault_pcs, \
            ("the faulting instruction never retires: %r is in the trace %r"
             % (fault_pc, fault_pcs))
        assert len(pipe.trace) == pipe.retired, \
            "one trace row per retirement: %d rows, %d retirements" \
            % (len(pipe.trace), pipe.retired)

    # --- a write to r0 retires, and does nothing ---------------------------
    words = isa.assemble("li r0, 5\nli t0, 3\nhalt\n")
    machine, pipe = run_both(words)
    assert pipe.trace[0].writes == (), \
        ("a write to r0 is dropped, but the instruction still retires with no "
         "effect: writes=%r" % (pipe.trace[0].writes,))
    assert pipe.registers.read(0) == 0 and pipe.retired == 3, \
        ("r0 stays 0 and the instruction still retires: r0=%r retired=%r"
         % (pipe.registers.read(0), pipe.retired))
    equivalent(machine, pipe, "r0 write")

    # --- halt retires, and the pc has already moved ------------------------
    words = isa.assemble("li t0, 1\nhalt\n")
    machine, pipe = run_both(words)
    halt_pc = len(words) - 1
    assert pipe.status == "halted", "halt halts, got %r" % (pipe.status,)
    assert pipe.trace[-1].pc == halt_pc and pipe.trace[-1].writes == (), \
        ("halt retires like any instruction with no effect: last row %r"
         % (pipe.trace[-1],))
    assert pipe.pc == halt_pc + 1, \
        ("the pc advances past halt before the status becomes halted: pc=%r, "
         "halt at %r" % (pipe.pc, halt_pc))
    equivalent(machine, pipe, "halt")

    # --- a run that must stop, stops ---------------------------------------
    spin = isa.assemble("jmp 0\n")
    pipe = s.Pipeline(spin)
    s.run_pipeline(pipe, max_cycles=7)
    assert pipe.status == "budget", \
        ("run_pipeline must stop at max_cycles and report it (a branch to itself "
         "never halts): status=%r" % (pipe.status,))
    assert pipe.cycles == 7, \
        "the capped run spends exactly max_cycles cycles, got %r" % (pipe.cycles,)
    capped = s.Pipeline(isa.assemble("li t0, 1\nhalt\n"))
    s.run_pipeline(capped, max_cycles=1)
    assert capped.status == "budget" and capped.cycles == 1, \
        ("a cap short of the halt stops the run: status=%r cycles=%r"
         % (capped.status, capped.cycles))

    # --- an empty program retires nothing ----------------------------------
    machine = s6.Machine(())
    s6.run(machine)
    pipe = s.Pipeline(())
    s.run_pipeline(pipe, max_cycles=CYCLE_CAP)
    assert pipe.retired == 0 and pipe.trace == (), \
        ("an empty program retires nothing: retired=%r trace=%r"
         % (pipe.retired, pipe.trace))
    equivalent(machine, pipe, "empty program")

    # --- a nop retires with no effect --------------------------------------
    words = isa.assemble("nop\nnop\nnop\nhalt\n")
    machine, pipe = run_both(words)
    assert [row.writes for row in pipe.trace[:3]] == [(), (), ()], \
        ("a nop retires with no effect: %r" % ([row.writes for row in pipe.trace],))
    assert pipe.retired == 4, "three nops and the halt retire: %r" % (pipe.retired,)
    equivalent(machine, pipe, "nops")
    identity(pipe, "nops")

    # --- two runs of one program are the same run --------------------------
    for name in sorted(isa.PROGRAMS):
        words = isa.assemble(isa.PROGRAMS[name])
        first = s.Pipeline(words)
        s.run_pipeline(first, max_cycles=CYCLE_CAP)
        second = s.Pipeline(words)
        s.run_pipeline(second, max_cycles=CYCLE_CAP)
        assert first.trace == second.trace, \
            "%s: two runs of one program give one trace: %r != %r" \
            % (name, first.trace, second.trace)
        assert s7.fingerprint(first) == s7.fingerprint(second), \
            "%s: two runs of one program give one fingerprint" % (name,)
        assert (first.cycles, first.retired, first.stalls) \
            == (second.cycles, second.retired, second.stalls), \
            ("%s: two runs of one program give one set of counters: %r != %r"
             % (name, (first.cycles, first.retired, first.stalls),
                (second.cycles, second.retired, second.stalls)))

    print("check_08: %d catalogue programs agree with the machine (trace, fingerprint, "
          "and the cycle identity), the four faults are reported and never retire, a "
          "taken branch squashes (and an untaken one does not), r0 and halt retire "
          "with no effect, a capped run stops, and the pinned stall counts hold — "
          "all asserted" % (len(isa.PROGRAMS),))

def check_9():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    LOAD_USE = """\
            li   t0, 42
            li   t1, 8
            sw   t1, t0, 0
            lw   t2, t1, 0
            add  v0, t2, t0
            halt
    """

    LOAD_USE_RS2 = """\
            li   t0, 7
            li   t1, 4
            sw   t1, t0, 0
            lw   t2, t1, 0
            add  v0, t0, t2
            halt
    """

    CHAIN = """\
            li   t0, 3
            addi t1, t0, 1
            addi t2, t1, 1
            addi v0, t2, 1
            halt
    """

    TWO_BACK = """\
            li   t0, 1
            li   t0, 2
            add  v0, t0, r0
            halt
    """

    STORE_FWD = """\
            li   t2, 77
            li   t0, 4
            addi t2, t2, 1
            sw   t0, t2, 0
            lw   v0, t0, 0
            halt
    """

    LOAD_FWD = """\
            li   t2, 99
            li   t3, 20
            li   s0, 16
            sw   s0, t2, 0
            addi t3, t3, -4
            lw   v0, t3, 0
            halt
    """

    BYTE_FWD = """\
            li   t0, 0x102
            li   t1, 0
            sw   t1, t0, 0
            lb   v0, t1, 1
            halt
    """

    NEGATIVES = """\
            li   t0, -5
            li   t1, -8192
            addi t2, t0, -3
            mov  v0, t2
            halt
    """

    BRANCH = """\
            li   t0, 0
    loop:   addi t0, t0, 1
            li   t1, 3
            slt  t2, t0, t1
            jnz  t2, loop
            mov  v0, t0
            halt
    """

    CAP = 50000

    def _refused(fn, *args, **kwargs):
        """The error message when a call is refused, or None when it is not."""
        try:
            fn(*args, **kwargs)
        except ValueError as exc:
            return str(exc)
        except Exception as exc:                                    # noqa: BLE001
            return "WRONG TYPE: %s: %s" % (type(exc).__name__, exc)
        return None

    import isa
    import stage_06 as s6
    import stage_07 as s7
    import stage_08 as s8
    import stage_09 as s9

    def words(text):
        return isa.assemble(text)

    def single(program, **kwargs):
        machine = s6.Machine(program, **kwargs)
        s6.run(machine, max_steps=CAP)
        return machine

    def slow(program, **kwargs):
        pipeline = s8.Pipeline(program, **kwargs)
        s8.run_pipeline(pipeline, max_cycles=CAP)
        return pipeline

    def fast(program, **kwargs):
        pipeline = s9.ForwardingPipeline(program, **kwargs)
        s9.run_forwarding(pipeline, max_cycles=CAP)
        return pipeline

    def first_diff(left, right):
        """The index of the first row two traces disagree on, or None."""
        for index, (a, b) in enumerate(zip(left, right)):
            if a != b:
                return index
        return None if len(left) == len(right) else min(len(left), len(right))

    # --- the stall vocabulary, before anything else ------------------------
    probe = fast(words("halt\n"))
    assert tuple(probe.stalls) == ("data", "load_use", "control"), \
        ("the stalls dict must carry exactly the three causes "
         '("data", "load_use", "control") in that order, got %r'
         % (probe.stalls,))

    def agree(program, label, **kwargs):
        """Run all three machines and assert the equivalence spine."""
        machine = single(program, **kwargs)
        stalling = slow(program, **kwargs)
        forward = fast(program, **kwargs)
        assert machine.status == "halted" and forward.status == "halted", \
            ("%s: every machine must halt on this fixture, got single=%r "
             "forwarding=%r" % (label, machine.status, forward.status))
        mrows, srows, frows = (s7.trace(machine), s7.trace(stalling),
                               s7.trace(forward))
        assert frows == mrows == srows, \
            ("%s: forwarding changed the retired trace (a faster machine that "
             "computes something else): the first differing row is %r"
             % (label, first_diff(frows, mrows)))
        assert (s7.fingerprint(forward) == s7.fingerprint(machine) ==
                s7.fingerprint(stalling)), \
            ("%s: forwarding changed the architectural state: forward=%r "
             "single=%r" % (label, s7.fingerprint(forward),
                            s7.fingerprint(machine)))
        assert forward.retired == machine.retired == stalling.retired, \
            ("%s: the three machines must retire the same instruction count, "
             "got forward=%r single=%r" % (label, forward.retired,
                                           machine.retired))
        assert forward.stalls["data"] == 0, \
            ("%s: a forwarding machine has no data stalls, got %r"
             % (label, forward.stalls["data"]))
        stalled = sum(forward.stalls.values())
        assert forward.cycles == forward.retired + 4 + stalled, \
            ("%s: cycles must be retired + 4 + stalls_total, got %r cycles, "
             "%r retired and %r stalls"
             % (label, forward.cycles, forward.retired, stalled))
        assert forward.cycles <= stalling.cycles, \
            ("%s: forwarding must never cost cycles: forwarding=%r, stalling=%r"
             % (label, forward.cycles, stalling.cycles))
        return machine, stalling, forward

    # --- the catalogue: both machines, both input sets ---------------------
    for name in ("sum_to_n", "factorial", "fib", "memcpy", "count_bits"):
        agree(words(isa.PROGRAMS[name]), "catalogue/%s" % (name,))
    for name, initial in (("sum_to_n", {"a0": 10}), ("factorial", {"a0": 6}),
                          ("fib", {"a0": 10}), ("count_bits", {"a0": 45}),
                          ("memcpy", {"a0": 0, "a1": 64, "a2": 5})):
        agree(words(isa.PROGRAMS[name]), "catalogue/%s[a0=%r]"
              % (name, initial.get("a0")), initial=initial)

    # --- the speedup is exact and real ------------------------------------
    fib_fast, fib_slow = fast(words(isa.PROGRAMS["fib"])), slow(words(isa.PROGRAMS["fib"]))
    sum_fast, sum_slow = fast(words(isa.PROGRAMS["sum_to_n"])), slow(words(isa.PROGRAMS["sum_to_n"]))
    assert (fib_fast.cycles, fib_slow.cycles) == (17, 22), \
        ("fib's forwarding pipeline must run in 17 cycles against the stalling "
         "22, got %r against %r" % (fib_fast.cycles, fib_slow.cycles))
    assert (sum_fast.cycles, sum_slow.cycles) == (11, 15), \
        ("sum_to_n's forwarding pipeline must run in 11 cycles against the "
         "stalling 15, got %r against %r" % (sum_fast.cycles, sum_slow.cycles))
    assert fib_fast.cycles < fib_slow.cycles, \
        ("fib must be strictly faster under forwarding: %r !< %r"
         % (fib_fast.cycles, fib_slow.cycles))
    assert sum_fast.cycles < sum_slow.cycles, \
        ("sum_to_n must be strictly faster under forwarding: %r !< %r"
         % (sum_fast.cycles, sum_slow.cycles))
    fib_fast, fib_slow = (fast(words(isa.PROGRAMS["fib"]), initial={"a0": 10}),
                          slow(words(isa.PROGRAMS["fib"]), initial={"a0": 10}))
    sum_fast, sum_slow = (fast(words(isa.PROGRAMS["sum_to_n"]), initial={"a0": 10}),
                          slow(words(isa.PROGRAMS["sum_to_n"]), initial={"a0": 10}))
    assert (fib_fast.cycles, fib_slow.cycles) == (137, 202), \
        ("fib(a0=10) runs in 137 cycles against the stalling 202, got %r vs %r"
         % (fib_fast.cycles, fib_slow.cycles))
    assert (sum_fast.cycles, sum_slow.cycles) == (81, 125), \
        ("sum_to_n(a0=10) runs in 81 cycles against the stalling 125, got %r "
         "vs %r" % (sum_fast.cycles, sum_slow.cycles))

    # --- the load-use case: exactly one cycle, and the loaded value --------
    _, _, loadstall = agree(words(LOAD_USE), "load-use")
    assert loadstall.stalls["load_use"] == 1, \
        ("a load used by the very next instruction stalls exactly one cycle, "
         "got load_use=%r" % (loadstall.stalls["load_use"],))
    assert loadstall.registers.read("v0") == 84, \
        ("the consumer must use the LOADED word (84), not the stale register: "
         "v0 is %r" % (loadstall.registers.read("v0"),))

    _, _, loadrs2 = agree(words(LOAD_USE_RS2), "load-use-rs2")
    assert loadrs2.stalls["load_use"] == 1, \
        ("a load feeding the very next instruction's rs2 stalls one cycle "
         "too, got load_use=%r" % (loadrs2.stalls["load_use"],))
    assert loadrs2.registers.read("v0") == 14, \
        ("the rs2 consumer must use the LOADED word (14), got %r"
         % (loadrs2.registers.read("v0"),))

    # --- a chain without a load has no load-use stall ---------------------
    _, _, chain = agree(words(CHAIN), "chain")
    assert chain.stalls["load_use"] == 0, \
        ("an ALU-only dependency chain forwards every value, so load_use must "
         "stay 0, got %r" % (chain.stalls["load_use"],))
    assert chain.registers.read("v0") == 6, \
        ("the forwarded chain must produce 6, got %r"
         % (chain.registers.read("v0"),))

    # --- a two-instruction-old value must not overwrite the fresh one -----
    _, _, twoback = agree(words(TWO_BACK), "two-back")
    assert twoback.registers.read("v0") == 2, \
        ("a value two instructions back (1) must not be forwarded over the "
         "fresh one (2): v0 is %r" % (twoback.registers.read("v0"),))

    # --- a store forwards its value, and a load its base ------------------
    _, _, stored = agree(words(STORE_FWD), "store-value")
    assert stored.registers.read("v0") == 78, \
        ("a store writes the forwarded value 78, not the stale 77: memory read "
         "back %r" % (stored.registers.read("v0"),))
    _, _, loadfwd = agree(words(LOAD_FWD), "load-address")
    assert loadfwd.registers.read("v0") == 99, \
        ("a load's effective address must use the forwarded base 16, not the "
         "stale 20: v0 is %r" % (loadfwd.registers.read("v0"),))

    # --- the sizes are 4 and 1, in that order -----------------------------
    _, _, byte = agree(words(BYTE_FWD), "byte-load")
    assert byte.registers.read("v0") == 1, \
        ("a word store then a byte load of its second byte yields 1, got %r"
         % (byte.registers.read("v0"),))

    # --- sign extension of negative immediates ----------------------------
    _, _, negatives = agree(words(NEGATIVES), "negatives")
    assert negatives.registers.read("v0") == 0xFFFFFFF8, \
        ("negative immediates must sign-extend and mask once: v0 is %r, not "
         "0xFFFFFFF8" % (negatives.registers.read("v0"),))

    # --- a taken branch: the flush costs cycles, the trace is unchanged ---
    _, _, branch = agree(words(BRANCH), "taken-branch")
    assert branch.stalls["control"] > 0, \
        ("a taken branch loses cycles to the flush, got control=%r"
         % (branch.stalls["control"],))
    assert branch.registers.read("v0") == 3, \
        ("the branch loop counts to 3, got %r" % (branch.registers.read("v0"),))

    # --- every fault kind is the single-cycle machine's -------------------
    faults = (
        ("illegal", (63 << 26,), {}),
        ("arith", words("li t0, 1\nli t1, 0\ndiv v0, t0, t1\nhalt\n"), {}),
        ("address", words("li t0, 4096\nlw v0, t0, 0\nhalt\n"), {}),
        ("fetch", words("halt\n"), {"pc": 5}),
    )
    kinds = set()
    for kind, program, kwargs in faults:
        machine = single(program, **kwargs)
        forward = fast(program, **kwargs)
        assert machine.status == "faulted" and forward.status == "faulted", \
            ("%s fault: both machines must record it as state, got single=%r "
             "forwarding=%r" % (kind, machine.status, forward.status))
        assert (forward.fault.kind, forward.fault.pc) == (machine.fault.kind,
                                                          machine.fault.pc), \
            ("%s fault: the forwarding pipeline must report the same kind and "
             "pc, got %r" % (kind, (forward.fault.kind, forward.fault.pc)))
        assert s7.trace(forward) == s7.trace(machine), \
            ("%s fault: the retired trace up to the fault must match, got %r"
             % (kind, first_diff(s7.trace(forward), s7.trace(machine))))
        kinds.add(forward.fault.kind)
    assert kinds == {"illegal", "arith", "address", "fetch"}, \
        ("the four fault kinds must all be reachable, got %r" % (sorted(kinds),))

    # --- initial, data_size and pc come from stage 8 ---------------------
    tiny = words("mov v0, a0\nhalt\n")
    for initial in ({"r0": 999, "a0": 7}, {0: 999, "a0": 7},
                    tuple([999] + list(range(1, isa.NUM_REGS)))):
        machine = single(tiny, initial=initial)
        stalling = slow(tiny, initial=initial)
        forward = fast(tiny, initial=initial)
        assert s7.fingerprint(forward) == s7.fingerprint(stalling) == \
            s7.fingerprint(machine), \
            ("initial %r: the register seed must mean the same thing to both "
             "pipelines, got %r" % (initial, forward.registers.snapshot()))
        assert forward.registers.read(0) == 0, \
            ("r0 is hardwired: a seed of r0 must not stick, got %r"
             % (forward.registers.read(0),))
    small = fast(tiny, data_size=64)
    assert len(small.memory) == 64, \
        ("data_size sizes the forwarding pipeline's data memory, got %r bytes"
         % (len(small.memory),))
    assert len(slow(tiny, data_size=64).memory) == 64, \
        "data_size sizes stage 8's memory too (the baseline)"
    over = words("li t0, 64\nlw v0, t0, 0\nhalt\n")
    assert fast(over, data_size=64).fault.kind == "address", \
        ("a load past a 64-byte memory is an address fault, the same as single "
         "cycle")
    stalling_pc = slow(tiny, pc=1)
    forward_pc = fast(tiny, pc=1)
    assert s7.trace(forward_pc) == s7.trace(stalling_pc) == \
        s7.trace(single(tiny, pc=1)), \
        ("pc=1 must start both pipelines at word 1, got %r"
         % (s7.trace(forward_pc),))
    assert forward_pc.retired == 1, \
        ("pc=1 starts at the halt and retires one instruction, got %r"
         % (forward_pc.retired,))

    # --- the constructor refuses what stage 8 refuses ---------------------
    for bad in ({"nope": 1}, (1, 2, 3)):
        message = _refused(s9.ForwardingPipeline, tiny, initial=bad)
        assert message is not None, \
            ("an initial of %r must be refused with ValueError, it was accepted"
             % (bad,))

    # --- the machine is deterministic, and idle once halted ---------------
    run_a, _, run_b = (fast(words(LOAD_USE)), None, fast(words(LOAD_USE)))
    assert (s7.fingerprint(run_a) == s7.fingerprint(run_b) and
            run_a.stalls == run_b.stalls and run_a.cycles == run_b.cycles), \
        ("two runs of the same program must be identical, got %r/%r cycles"
         % (run_a.cycles, run_b.cycles))
    idle = fast(words("halt\n"))
    before = (idle.cycles, idle.retired)
    s9.step_forwarding(idle)
    assert (idle.cycles, idle.retired) == before, \
        ("a halted machine is idle: stepping it changed %r to %r"
         % (before, (idle.cycles, idle.retired)))

    # --- reset: back to the start, and the run reproduces ----------------
    program = words(isa.PROGRAMS["sum_to_n"])
    pipe = s9.ForwardingPipeline(program, initial={"a0": 10})
    seed = s6.Machine(program, initial={"a0": 10}).registers.snapshot()
    start = (pipe.pc, pipe.status, pipe.cycles, pipe.retired,
             dict(pipe.stalls), pipe.trace)
    s9.run_forwarding(pipe, max_cycles=20)
    assert pipe.cycles == 20 and pipe.retired > 0, \
        ("the partial run must have work to lose, got %r cycles and %r retired"
         % (pipe.cycles, pipe.retired))
    assert pipe.reset() is pipe, \
        "reset returns the pipeline (stage 8's surface), got %r" % (pipe.reset,)
    assert (pipe.pc, pipe.status, pipe.cycles, pipe.retired,
            dict(pipe.stalls), pipe.trace) == start, \
        ("reset must put pc/status/cycles/retired/stalls/trace back to the "
         "start, got %r"
         % ((pipe.pc, pipe.status, pipe.cycles, pipe.retired,
             dict(pipe.stalls), pipe.trace),))
    assert pipe.registers.snapshot() == seed, \
        ("reset must restore the register seed (a0=10, everything else 0), "
         "got %r" % (pipe.registers.snapshot(),))
    assert pipe.registers.read(0) == 0, \
        "reset keeps r0 hardwired at 0, got %r" % (pipe.registers.read(0),)
    assert pipe.fault is None and pipe.memory.snapshot() == bytes(len(pipe.memory)), \
        ("reset clears the fault and the data memory, got fault=%r"
         % (pipe.fault,))
    first = s9.ForwardingPipeline(program, initial={"a0": 10})
    s9.run_forwarding(first)
    s9.run_forwarding(pipe)
    assert (s7.trace(pipe) == s7.trace(first) and
            s7.fingerprint(pipe) == s7.fingerprint(first) and
            pipe.cycles == first.cycles and pipe.stalls == first.stalls), \
        ("a full run after a reset reproduces the first run exactly, got %r "
         "cycles against %r" % (pipe.cycles, first.cycles))

    # --- a cycle cap stops as "budget", not as a fault --------------------
    capped = s9.ForwardingPipeline(words(isa.PROGRAMS["sum_to_n"]))
    result = s9.run_forwarding(capped, max_cycles=6)
    assert (result if result is not None else capped).status == "budget", \
        ("a cycle cap leaves the run as 'budget', got %r"
         % ((result if result is not None else capped).status,))

    print("check_09: %d catalogue programs, %d catalogue input runs, 9 fixtures, "
          "4 fault kinds — forwarding agrees with both slower machines"
          % (5, 5))

def check_10():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    FORWARDING_KEYS = ("data", "load_use", "control")

    def _refused(fn, *args, **kwargs):
        """The `ValueError` message when a call is refused, or None, or a wrong-type
        marker when it raises something that is not a `ValueError`."""
        try:
            fn(*args, **kwargs)
        except ValueError as exc:
            return str(exc)
        except Exception as exc:                                           # noqa: BLE001
            return "WRONG TYPE: %s: %s" % (type(exc).__name__, exc)
        return None

    import isa
    import stage_06
    import stage_07
    import stage_08
    import stage_09
    import stage_10 as s

    # --- the constants are the contract's ---------------------------------
    assert s.DP == 6, "DP must be 6, the precision of every report float: %r" % (s.DP,)
    assert tuple(s.REPORT_KEYS) == ("program", "retired", "single_cycles",
                                    "pipeline_cycles", "cpi", "stalls", "speedup",
                                    "equivalent"), \
        "REPORT_KEYS is the contract's tuple, in order: %r" % (s.REPORT_KEYS,)

    # --- every program, on both control units -----------------------------
    for name in sorted(isa.PROGRAMS):
        for forwarding in (True, False):
            report = s.measure(name, forwarding=forwarding)
            assert set(report) == set(s.REPORT_KEYS), \
                ("a report has exactly REPORT_KEYS, got %r" % (sorted(report),))
            assert report["program"] == name, \
                "a catalogue program reports its name: %r" % (report["program"],)
            retired = report["retired"]
            assert isinstance(retired, int) and not isinstance(retired, bool) and retired > 0, \
                "retired is the number of instructions that retired: %r" % (retired,)
            assert report["single_cycles"] == retired, \
                ("the single-cycle machine spends one cycle per retired "
                 "instruction: %r vs %r" % (report["single_cycles"], retired))
            cycles = report["pipeline_cycles"]
            assert isinstance(cycles, int) and not isinstance(cycles, bool) and cycles > 0, \
                "pipeline_cycles is the pipeline's cycle count: %r" % (cycles,)
            assert report["cpi"] == round(cycles / retired, 6), \
                ("cpi must be round(pipeline_cycles / retired, 6): %r vs %r"
                 % (report["cpi"], round(cycles / retired, 6)))
            assert report["speedup"] == round(report["single_cycles"] / cycles, 6), \
                ("speedup must be round(single_cycles / pipeline_cycles, 6): %r vs %r"
                 % (report["speedup"], round(report["single_cycles"] / cycles, 6)))
            assert set(report["stalls"]) == set(FORWARDING_KEYS), \
                ("stalls carries exactly the three causes, zero-filled: %r"
                 % (report["stalls"],))
            for value in report["stalls"].values():
                assert isinstance(value, int) and not isinstance(value, bool) and value >= 0, \
                    "a stall count is a non-negative int: %r" % (value,)
            for key in ("cpi", "speedup"):
                value = report[key]
                assert isinstance(value, float), \
                    "a report fraction is a float, got %r" % (type(value).__name__,)
                assert str(value) == str(round(value, 6)), \
                    ("a report float carries binary noise: %r (str %r vs %r)"
                     % (value, str(value), str(round(value, 6))))
            assert report["equivalent"] is True, \
                ("the pipelines must retire the same trace and end in the same "
                 "architectural state as the single-cycle machine, for %r "
                 "forwarding=%r" % (name, forwarding))

    # --- an inline program names itself "<source>" ------------------------
    inline = s.measure(isa.PROGRAMS["sum_to_n"])
    assert inline["program"] == "<source>", \
        "a program passed as text is labelled %r, got %r" % ("<source>", inline["program"])
    assert inline["equivalent"] is True

    # --- forwarding strictly beats stalls-only on the load-use program ----
    fast = s.measure("fib", forwarding=True)
    slow = s.measure("fib", forwarding=False)
    assert fast["pipeline_cycles"] < slow["pipeline_cycles"], \
        ("forwarding must strictly beat stalls-only on fib: %r vs %r"
         % (fast["pipeline_cycles"], slow["pipeline_cycles"]))
    assert fast["stalls"]["data"] == 0, \
        ("under forwarding there are no data stalls, only the load-use wait "
         "and the branch flush: %r" % (fast["stalls"],))
    assert fast["equivalent"] is True and slow["equivalent"] is True
    assert sum(slow["stalls"].values()) > sum(fast["stalls"].values()), \
        ("the stalls-only machine must pay strictly more stall cycles than the "
         "forwarding one on fib: %r vs %r" % (slow["stalls"], fast["stalls"]))

    # --- compare: both machines, one result -------------------------------
    compared = s.compare("fib")
    assert set(compared) == set(s.REPORT_KEYS) | {"single", "pipeline"}, \
        ("compare's report is measure's plus the two fingerprints, got %r"
         % (sorted(compared),))
    assert compared["equivalent"] is True
    single = stage_07.load(isa.PROGRAMS["fib"])
    stage_06.run(single)
    pipeline = stage_09.ForwardingPipeline(isa.assemble(isa.PROGRAMS["fib"]))
    stage_09.run_forwarding(pipeline)
    assert compared["single"] == stage_07.fingerprint(single), \
        ("compare reports the single-cycle machine's own fingerprint: %r vs %r"
         % (compared["single"], stage_07.fingerprint(single)))
    assert compared["pipeline"] == stage_07.fingerprint(pipeline), \
        ("compare reports the pipeline's own fingerprint: %r vs %r"
         % (compared["pipeline"], stage_07.fingerprint(pipeline)))
    assert compared["pipeline_cycles"] == s.measure("fib")["pipeline_cycles"], \
        "compare's pipeline is the measured (forwarding) pipeline"
    assert compared["retired"] == s.measure("fib")["retired"]

    # --- equivalent is computed from the fingerprints, never asserted -----
    # Break the pipeline's result behind measure's back: the two fingerprints
    # now disagree, so a computed equivalence reports False. A hard-coded True
    # reports success for a machine that computed something else.
    real_fingerprint = stage_07.fingerprint

    def divergent(machine):
        result = real_fingerprint(machine)
        if isinstance(machine, (stage_08.Pipeline, stage_09.ForwardingPipeline)):
            return result + ("divergent",)
        return result

    s.fingerprint = divergent
    stage_07.fingerprint = divergent
    try:
        diverged = s.measure("fib")
        assert diverged["equivalent"] is False, \
            ("equivalent must be computed by comparing the two fingerprints; a "
             "hard-coded True calls a machine that computed something else "
             "equivalent: %r" % (diverged["equivalent"],))
        refused = _refused(s.compare, "fib")
        assert refused is not None, \
            ("compare must refuse a pair of machines that are not equivalent: a "
             "faster machine that computes something else is not a faster machine")
        assert "WRONG TYPE" not in refused, \
            "compare refuses an inequivalent run with ValueError, got %r" % (refused,)
    finally:
        s.fingerprint = real_fingerprint
        stage_07.fingerprint = real_fingerprint

    # --- stalls leaves the machine as a copy ------------------------------
    seen = []
    real_forwarding = s.ForwardingPipeline

    class Watching(real_forwarding):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            seen.append(self)

    s.ForwardingPipeline = Watching
    try:
        watched = s.measure("fib")
    finally:
        s.ForwardingPipeline = real_forwarding
    assert seen, "measure must run the forwarding pipeline"
    assert isinstance(watched["stalls"], dict), \
        "the report's stalls is a dict, got %r" % (type(watched["stalls"]).__name__,)
    assert watched["stalls"] is not seen[-1].stalls, \
        ("the report's stalls must be a copy, not the pipeline's live dict: "
         "editing the report would rewrite the machine")
    first = s.measure("fib")
    expected = dict(first["stalls"])
    first["stalls"]["data"] = 987654
    first["stalls"]["load_use"] = -1
    first["stalls"]["control"] = 42
    second = s.measure("fib")
    assert second["stalls"] == expected, \
        ("the report's stalls is a copy: editing one report must not change a "
         "later run's counts: %r vs %r" % (second["stalls"], expected))

    # --- a program with nothing to retire is refused ----------------------
    message = _refused(s.measure, "")
    assert message is not None, \
        "measure of a program with nothing to retire must be refused, not reported"
    assert "WRONG TYPE" not in message, \
        "a zero-retirement program is refused with ValueError, got %r" % (message,)
    assert "retire" in message, \
        ("the refusal names the missing retirement, not a generic halt status: %r"
         % (message,))

    # --- a program that never halts is stopped and refused ----------------
    forever = "loop: jmp loop\n"
    message = _refused(s.measure, forever, max_cycles=64)
    assert message is not None, \
        ("measure of a program that never halts must not return the truncated "
         "cycles as a partial report")
    assert "WRONG TYPE" not in message, \
        "a budget run is refused with ValueError, got %r" % (message,)
    assert "budget" in message, \
        ("the refusal names the budget status rather than a silent partial "
         "success: %r" % (message,))

    # --- two runs are equal -----------------------------------------------
    assert s.measure("count_bits") == s.measure("count_bits"), \
        "two runs of the same program report the same dict"
    assert s.measure("fib", forwarding=False) == s.measure("fib", forwarding=False), \
        "two stalls-only runs of the same program report the same dict"
    assert s.compare("memcpy") == s.compare("memcpy"), \
        "two compares of the same program report the same dict"

    print("check_10: CPI and speedup recomputed from the cycles, floats rounded to "
          "DP=%d with no binary noise, equivalence computed from the fingerprints "
          "(a hard-coded True is caught), stalls a copy, zero-retirement and "
          "never-halting runs refused, and two runs equal — all asserted"
          % (s.DP,))

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The word, and the flags nobody keeps",
        tags=["word", "flags"],
        action="Write `Flags`, `word`, `signed`, `sign_extend`, `fits_imm`, "
               "`shift_amount`, `add_flags`, `sub_flags`, `pack_word` and "
               "`unpack_word` in stage_01.py.",
        predict="What `word(-1)` is, whether `signed(0x80000000)` adds or "
                "subtracts, what a shift by 33 does to a Python int rather than "
                "to a register, and when `carry` and `overflow` disagree.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The decoder, and the field the format does not use",
        tags=["decode", "encoding"],
        action="Write `Instruction`, `BadInstruction`, `decode`, `encode`, "
               "`disassemble`, `registers` and `opcode` in stage_02.py.",
        predict="What the immediate is for `addi t0, t1, -1`, what `rs2` reads "
                "as for an instruction whose format has no `b`, and whether "
                "`encode(decode(w))` is `w` for a word with junk in an unused "
                "field.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The register file, and the snapshot that is not a window",
        tags=["registers", "aliasing"],
        action="Write `RegisterFile` in stage_03.py.",
        predict="What happens to a write to `zero`, what a snapshot taken before "
                "a write contains afterwards, and what a `restore` of fifteen "
                "values does.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The ALU, and the remainder Python gets right and hardware wrong",
        tags=["alu", "arithmetic"],
        action="Write `ArithmeticFault`, `ALU_OPS` and `alu` in stage_04.py.",
        predict="What `-7 mod 2` is in hardware versus in Python, which of "
                "`slt` and `sltu` calls `0xFFFFFFFF` smaller than 1, and which "
                "operations set flags.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Memory, and the store that must not happen",
        tags=["memory", "faults"],
        action="Write `AddressFault` and `Memory` in stage_05.py.",
        predict="What a four-byte load at the last byte of memory does, what a "
                "two-byte store into a word replaces, and whether a faulting "
                "store leaves a trace behind.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The machine: a fault is data, not an exception",
        tags=["machine", "control-unit"],
        action="Write `Fault`, `FAULT_KINDS`, `STATUSES`, `TraceRow`, `Machine`, "
               "`step`, `run` and `reset` in stage_06.py.",
        predict="What `retired` and `cycles` are for a program that faulted on "
                "its third instruction, what a `jal` links, and what a budget "
                "stop is not.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The record of what a machine did",
        tags=["trace", "fingerprint"],
        action="Write `load`, `trace` and `fingerprint` in stage_07.py.",
        predict="What `limit=0` returns, which rows a trace contains when the "
                "run faulted, and what two machines that halted say about each "
                "other in one tuple.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The five-stage pipeline that is allowed to be slow",
        tags=["pipeline", "stalls"],
        action="Write `STAGES`, `Pipeline`, `step_pipeline`, `run_pipeline` and "
               "`retire` in stage_08.py.",
        predict="What `cycles` is for eleven instructions with no dependencies, "
                "how many cycles a load-use pair costs when nothing is "
                "forwarded, and why `cycles == retired + 4 + stalls` must hold "
                "for every run.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="Forwarding, and the one stall no wiring can remove",
        tags=["forwarding", "hazards"],
        action="Write `ForwardingPipeline`, `forward_operands`, `step_forwarding` "
               "and `run_forwarding` in stage_09.py.",
        predict="Which of the three forwarding paths must not exist, what a "
                "`lw` followed immediately by a use costs even with forwarding, "
                "and what a squashed fetch does to the cycle count.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="One program, two machines, one result",
        tags=["cpi", "equivalence"],
        action="Write `DP`, `REPORT_KEYS`, `measure` and `compare` in "
               "stage_10.py.",
        predict="What CPI is for a program with one load-use pair and ten "
                "instructions, what `speedup` is measured against, and what a "
                "report says about a program that never halts.",
        check=check_10,
    ),
]
