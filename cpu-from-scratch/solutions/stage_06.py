"""CPU From Scratch stage 06, implemented.

The reasoning — why faults are data, why the program is a tuple apart from the
data memory, why r0's write still retires, why a budget stop is not a fault and
why a snapshot is a copy — lives in the template's docstring.
"""

from collections import namedtuple

import isa
from stage_01 import word
from stage_02 import BadInstruction, decode, disassemble
from stage_03 import RegisterFile
from stage_04 import ALU_OPS, ArithmeticFault, alu
from stage_05 import AddressFault, Memory

FAULT_KINDS = ("illegal", "arith", "address", "fetch")
STATUSES = ("running", "halted", "faulted", "budget")

Fault = namedtuple("Fault", "kind pc detail")
TraceRow = namedtuple("TraceRow", "pc word text writes")

_NOP = isa.BY_NAME["nop"].code
_HALT = isa.BY_NAME["halt"].code
_LI = isa.BY_NAME["li"].code
_MOV = isa.BY_NAME["mov"].code
_ADDI = isa.BY_NAME["addi"].code
_LW = isa.BY_NAME["lw"].code
_LB = isa.BY_NAME["lb"].code
_SW = isa.BY_NAME["sw"].code
_SB = isa.BY_NAME["sb"].code
_JMP = isa.BY_NAME["jmp"].code
_JZ = isa.BY_NAME["jz"].code
_JNZ = isa.BY_NAME["jnz"].code
_BEQ = isa.BY_NAME["beq"].code
_BNE = isa.BY_NAME["bne"].code
_JAL = isa.BY_NAME["jal"].code
_JR = isa.BY_NAME["jr"].code


class Machine:
    """A single-cycle machine: one instruction per cycle, in program order."""

    def __init__(self, program, *, data_size=4096, pc=0, initial=None):
        self._program = tuple(program)
        self._data_size = data_size
        self._initial_pc = pc
        self.registers = RegisterFile()
        self.memory = Memory(data_size)
        self.pc = pc
        self.status = "running"
        self.fault = None
        self.cycles = 0
        self.retired = 0
        self.trace = ()
        #: the register mapping a reset restores: a copy, never the live file
        self.initial = self._seed(initial)

    def _seed(self, initial):
        """Apply the constructor's register seed, and return it as a tuple."""
        if initial is None:
            return self.registers.snapshot()
        if hasattr(initial, "items"):
            for register, value in initial.items():
                self.registers.write(register, word(value))
        else:
            self.registers.restore(tuple(initial))
        return self.registers.snapshot()

    @property
    def program(self):
        """The program's words — a tuple, immutable by construction."""
        return self._program

    def snapshot(self):
        """A copy of the whole architectural state, safe to keep and compare."""
        return {
            "pc": self.pc,
            "status": self.status,
            "fault": self.fault,
            "registers": list(self.registers.snapshot()),
            "memory": self.memory.snapshot(),
            "cycles": self.cycles,
            "retired": self.retired,
            "trace": self.trace,
        }


def _fault(machine, kind, pc, detail):
    """Record a fault as state: the machine stops, and says why."""
    machine.status = "faulted"
    machine.fault = Fault(kind, pc, detail)


def _write(registers, writes, index, value):
    """Write a register, masking it, and record the effect (r0 has none)."""
    registers.write(index, value)
    if index != isa.ZERO:
        writes.append(("r", index, word(value)))


def _execute(machine, ins, next_pc, writes):
    """Run one decoded instruction; returns the pc the machine should have."""
    code = ins.op.code
    registers = machine.registers
    if code in (_NOP, _HALT):
        return next_pc
    if code == _LI:
        _write(registers, writes, ins.rd, ins.imm)
    elif code == _MOV:
        _write(registers, writes, ins.rd, registers.read(ins.rs1))
    elif code in ALU_OPS:
        value, _flags = alu(code, registers.read(ins.rs1), registers.read(ins.rs2),
                            pc=ins.pc)
        _write(registers, writes, ins.rd, value)
    elif code == _ADDI:
        _write(registers, writes, ins.rd, word(registers.read(ins.rs1) + ins.imm))
    elif code in (_LW, _LB):
        size = 4 if code == _LW else 1
        address = word(registers.read(ins.rs1) + ins.imm)
        _write(registers, writes, ins.rd, machine.memory.load(address, size))
    elif code in (_SW, _SB):
        size = 4 if code == _SW else 1
        address = word(registers.read(ins.rs1) + ins.imm)
        value = registers.read(ins.rs2)
        machine.memory.store(address, size, value)
        writes.append(("m", address, size, value))
    elif code == _JMP:
        return ins.imm
    elif code == _JZ:
        return ins.imm if registers.read(ins.rs1) == 0 else next_pc
    elif code == _JNZ:
        return ins.imm if registers.read(ins.rs1) != 0 else next_pc
    elif code == _BEQ:
        return ins.imm if registers.read(ins.rs1) == registers.read(ins.rs2) else next_pc
    elif code == _BNE:
        return ins.imm if registers.read(ins.rs1) != registers.read(ins.rs2) else next_pc
    elif code == _JAL:
        _write(registers, writes, ins.rd, word(ins.pc + 1))
        return ins.imm
    elif code == _JR:
        return registers.read(ins.rs1)
    return next_pc


def step(machine):
    """Fetch, decode and execute one instruction at ``machine.pc``."""
    if machine.status != "running":
        return
    pc = machine.pc
    if not 0 <= pc < len(machine._program):
        _fault(machine, "fetch", pc,
               "pc %d outside a program of %d words" % (pc, len(machine._program)))
        return
    word_ = machine._program[pc]
    try:
        ins = decode(word_, pc=pc)
    except BadInstruction as exc:
        _fault(machine, "illegal", pc, str(exc))
        return
    writes = []
    next_pc = pc + 1
    try:
        next_pc = _execute(machine, ins, next_pc, writes)
    except ArithmeticFault as exc:
        _fault(machine, "arith", pc, str(exc))
        return
    except AddressFault as exc:
        _fault(machine, "address", pc, str(exc))
        return
    machine.pc = next_pc
    machine.trace = machine.trace + (TraceRow(pc, word_, disassemble(ins),
                                              tuple(writes)),)
    machine.retired += 1
    machine.cycles += 1
    if ins.op.code == _HALT:
        machine.status = "halted"


def run(machine, *, max_steps=None):
    """Step until the machine halts, faults, or ``max_steps`` is reached."""
    if max_steps is None:
        while machine.status == "running":
            step(machine)
        return machine
    performed = 0
    while machine.status == "running" and performed < max_steps:
        step(machine)
        performed += 1
    if machine.status == "running":
        machine.status = "budget"
    return machine


def reset(machine):
    """Return ``machine`` to its initial architectural state, counters zeroed."""
    machine.registers.restore(machine.initial)
    machine.memory = Memory(machine._data_size)
    machine.pc = machine._initial_pc
    machine.status = "running"
    machine.fault = None
    machine.cycles = 0
    machine.retired = 0
    machine.trace = ()
    return machine
