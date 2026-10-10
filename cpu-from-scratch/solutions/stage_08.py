"""CPU From Scratch — stage 8 (solution): the five-stage pipeline, correct and slow.

The reasoning — why stalls and no forwarding, why the control hazard is resolved
in EX and counted, why the identity `cycles == retired + 4 + stalls` has to hold
— lives in `stage_08.py`'s template. This file is the implementation.

The pipeline registers are the four between-stage registers a five-stage
pipeline really has (`_if_id`, `_id_ex`, `_ex_mem`, `_mem_wb`); a cycle processes
the five stages in the order WB, MEM, EX, ID, IF, which is what lets a write at
WB be visible to the decode in the same cycle without forwarding.
"""

import isa
from stage_02 import BadInstruction, decode, disassemble
from stage_03 import RegisterFile
from stage_04 import ALU_OPS, ArithmeticFault, alu
from stage_05 import AddressFault, Memory
from stage_06 import Fault, TraceRow

#: the five stages, entry first: an instruction enters IF and retires at WB
STAGES = ("IF", "ID", "EX", "MEM", "WB")
#: every stall cause the pipeline reports. "load_use" exists for stage 9; here
#: every dependency is a "data" stall, so it stays zero.
STALL_CAUSES = ("data", "load_use", "control")

_WORD_MASK = 0xFFFFFFFF
#: opcodes this machine resolves in EX
JMP, JZ, JNZ, BEQ, BNE, JAL, JR = 22, 23, 24, 25, 26, 27, 28
_CONTROLS = (JMP, JZ, JNZ, BEQ, BNE, JAL, JR)
#: code -> bytes moved, for the two loads and the two stores
LOADS = {18: 4, 20: 1}
STORES = {19: 4, 21: 1}
_HALT = 1
_LI = 2
_MOV = 3
_ADDI = 9


def _seed(initial):
    """A 16-tuple of registers from a name/index mapping or a 16-sequence."""
    values = [0] * isa.NUM_REGS
    if initial is None:
        return tuple(values)
    if hasattr(initial, "items"):
        for key, value in initial.items():
            if isinstance(key, str):
                if key not in isa.REG_INDEX:
                    raise ValueError("stage 8: not a register name: %r" % (key,))
                index = isa.REG_INDEX[key]
            elif isinstance(key, int) and not isinstance(key, bool):
                index = key
            else:
                raise ValueError("stage 8: not a register name or index: %r" % (key,))
            if not 0 <= index < isa.NUM_REGS:
                raise ValueError("stage 8: register index out of range: %r" % (key,))
            values[index] = int(value) & _WORD_MASK
    else:
        sequence = list(initial)
        if len(sequence) != isa.NUM_REGS:
            raise ValueError("stage 8: initial needs %d values, got %d"
                             % (isa.NUM_REGS, len(sequence)))
        values = [int(value) & _WORD_MASK for value in sequence]
    values[isa.ZERO] = 0
    return tuple(values)


def _slot(pc, word):
    """One instruction as it travels down the pipe (a mutable run-time record)."""
    return {"pc": pc, "word": word, "ins": None, "reads": (), "dest": None,
            "kind": None, "value": None, "writes": (), "addr": None,
            "size": None, "store": None, "taken": False, "target": None,
            "halt": False}


def _dest_of(slot):
    return None if slot is None else slot["dest"]


def _stalls_on(reads, ex_slot, mem_slot):
    """True when a value read here is still being computed downstream."""
    if not reads:
        return False
    for other in (ex_slot, mem_slot):
        if other is not None and other["dest"] is not None and other["dest"] in reads:
            return True
    return False


def _empty(pipeline):
    return (pipeline._if_id is None and pipeline._id_ex is None
            and pipeline._ex_mem is None and pipeline._mem_wb is None)


class Pipeline:
    """A five-stage in-order pipeline with stalls instead of forwarding.

    The architectural surface is stage 6's `Machine`: `registers`, `memory`,
    `pc`, `status`, `fault`, `cycles`, `retired` and a `trace` of the same
    `TraceRow`s, so the two machines can be compared as one.
    """

    def __init__(self, program, *, data_size=4096, pc=0, initial=None):
        self.program = tuple(program)
        self._seed = _seed(initial)
        self._initial_pc = pc
        self.registers = RegisterFile(self._seed)
        self.memory = Memory(data_size)
        self.pc = pc
        self.status = "running"
        self.fault = None
        self.cycles = 0
        self.retired = 0
        self.stalls = {cause: 0 for cause in STALL_CAUSES}
        self._trace = []
        self._if_id = None
        self._id_ex = None
        self._ex_mem = None
        self._mem_wb = None
        self._halt_seen = False
        self.stages = (None, None, None, None, None)

    # -- the architectural state -------------------------------------------

    @property
    def trace(self):
        """The retired instructions, in order, as the machine's own rows."""
        return tuple(self._trace)

    def snapshot(self):
        """The whole architectural state, as copies (never the live objects)."""
        return {"pc": self.pc, "status": self.status, "fault": self.fault,
                "registers": list(self.registers.snapshot()),
                "memory": self.memory.snapshot(), "cycles": self.cycles,
                "retired": self.retired, "trace": self.trace}

    def reset(self):
        """Back to the architectural state the pipeline was built with."""
        self.registers = RegisterFile(self._seed)
        self.memory = Memory(len(self.memory))
        self.pc = self._initial_pc
        self.status = "running"
        self.fault = None
        self.cycles = 0
        self.retired = 0
        self.stalls = {cause: 0 for cause in STALL_CAUSES}
        self._trace = []
        self._if_id = self._id_ex = self._ex_mem = self._mem_wb = None
        self._halt_seen = False
        self.stages = (None, None, None, None, None)
        return self


def _advances(pipeline):
    if pipeline.status == "running":
        return True
    return pipeline.status == "faulted" and not _empty(pipeline)


def _abort(pipeline, fault):
    """A faulting instruction never retires: record it and stop at its pc."""
    pipeline.fault = fault
    pipeline.pc = fault.pc
    pipeline.status = "faulted"


def _fetch(pipeline):
    """`(slot, None)` for the word at the pc, or `(None, Fault)` for a fetch fault."""
    pc = pipeline.pc
    if pc < 0 or pc >= len(pipeline.program):
        return None, Fault("fetch", pc,
                           "pc %d outside a program of %d words"
                           % (pc, len(pipeline.program)))
    pipeline.pc = pc + 1
    return _slot(pc, pipeline.program[pc]), None


def retire(pipeline):
    """Write back and trace the instruction at WB, and count it as retired."""
    slot = pipeline._mem_wb
    if slot is None:
        return
    for effect in slot["writes"]:
        if effect[0] == "r":
            pipeline.registers.write(effect[1], effect[2])
    pipeline._trace.append(TraceRow(slot["pc"], slot["word"],
                                    disassemble(slot["ins"]), slot["writes"]))
    pipeline.retired += 1
    if slot["ins"].op.code == _HALT:
        pipeline.status = "halted"
    pipeline._mem_wb = None


def _id_beat(pipeline, slot):
    """Decode the instruction in ID (an `illegal` fault is data, not an error)."""
    try:
        ins = decode(slot["word"], pc=slot["pc"])
    except BadInstruction as exc:
        return Fault("illegal", slot["pc"], str(exc))
    slot["ins"] = ins
    fmt = ins.op.fmt
    reads = []
    if "a" in fmt and ins.rs1 != isa.ZERO:
        reads.append(ins.rs1)
    if "b" in fmt and ins.rs2 != isa.ZERO:
        reads.append(ins.rs2)
    slot["reads"] = tuple(reads)
    slot["dest"] = ins.rd if ("d" in fmt and ins.rd != isa.ZERO) else None
    slot["halt"] = ins.op.code == _HALT
    return None


def _write(slot, value):
    slot["kind"] = "alu"
    value &= _WORD_MASK
    slot["value"] = value
    rd = slot["ins"].rd
    slot["writes"] = (("r", rd, value),) if rd != isa.ZERO else ()


def _resolve(slot, code, ins, a, b):
    if code in (JMP, JAL):
        taken, target = True, ins.imm
    elif code == JZ:
        taken, target = a == 0, ins.imm
    elif code == JNZ:
        taken, target = a != 0, ins.imm
    elif code == BEQ:
        taken, target = a == b, ins.imm
    elif code == BNE:
        taken, target = a != b, ins.imm
    else:                                            # JR
        taken, target = True, a
    slot["kind"] = "control"
    slot["taken"] = taken
    slot["target"] = target
    if code == JAL:
        rd = ins.rd
        slot["writes"] = (("r", rd, ins.pc + 1),) if rd != isa.ZERO else ()


def _ex_beat(pipeline, slot):
    """Read the operands and compute the result (or the control decision) in EX."""
    ins = slot["ins"]
    code = ins.op.code
    a = pipeline.registers.read(ins.rs1)
    b = pipeline.registers.read(ins.rs2)
    if code in ALU_OPS:
        try:
            value, _flags = alu(code, a, b, pc=ins.pc)
        except ArithmeticFault as exc:
            return Fault("arith", ins.pc, str(exc))
        _write(slot, value)
    elif code == _LI:
        _write(slot, ins.imm)
    elif code == _ADDI:
        _write(slot, a + ins.imm)
    elif code == _MOV:
        _write(slot, a)
    elif code in LOADS:
        slot["kind"] = "load"
        slot["addr"] = (a + ins.imm) & _WORD_MASK
        slot["size"] = LOADS[code]
    elif code in STORES:
        slot["kind"] = "store"
        slot["addr"] = (a + ins.imm) & _WORD_MASK
        slot["size"] = STORES[code]
        slot["store"] = b
    elif code in _CONTROLS:
        _resolve(slot, code, ins, a, b)
    return None


def _mem_beat(pipeline, slot):
    """Touch the data memory in MEM: a store now, a load's value now."""
    if slot["kind"] == "load":
        try:
            value = pipeline.memory.load(slot["addr"], slot["size"])
        except AddressFault as exc:
            return Fault("address", slot["pc"], str(exc))
        slot["value"] = value
        rd = slot["ins"].rd
        slot["writes"] = (("r", rd, value),) if rd != isa.ZERO else ()
    elif slot["kind"] == "store":
        try:
            pipeline.memory.store(slot["addr"], slot["size"], slot["store"])
        except AddressFault as exc:
            return Fault("address", slot["pc"], str(exc))
        slot["writes"] = (("m", slot["addr"], slot["size"], slot["store"]),)
    return None


def _publish(pipeline):
    pipeline.stages = (pipeline._if_id, pipeline._id_ex, pipeline._ex_mem,
                       pipeline._mem_wb, None)


def step_pipeline(pipeline):
    """One cycle, WB first: retire, then MEM, EX, ID, and only then IF."""
    if not _advances(pipeline):
        return
    pipeline.cycles += 1
    # WB
    retire(pipeline)
    # MEM
    if pipeline._ex_mem is not None:
        fault = _mem_beat(pipeline, pipeline._ex_mem)
        if fault is not None:
            _abort(pipeline, fault)
            pipeline._ex_mem = pipeline._id_ex = pipeline._if_id = None
            _publish(pipeline)
            return
    # EX
    squash = False
    if pipeline._id_ex is not None:
        fault = _ex_beat(pipeline, pipeline._id_ex)
        if fault is not None:
            _abort(pipeline, fault)
            pipeline._mem_wb = pipeline._ex_mem
            pipeline._ex_mem = pipeline._id_ex = pipeline._if_id = None
            _publish(pipeline)
            return
        if pipeline._id_ex["kind"] == "control" and pipeline._id_ex["taken"]:
            squash = True
    # ID
    stall = False
    if not squash and pipeline._if_id is not None:
        fault = _id_beat(pipeline, pipeline._if_id)
        if fault is not None:
            _abort(pipeline, fault)
            pipeline._mem_wb = pipeline._ex_mem
            pipeline._ex_mem = pipeline._id_ex
            pipeline._id_ex = pipeline._if_id = None
            _publish(pipeline)
            return
        if pipeline._if_id["halt"]:
            pipeline._halt_seen = True
        elif _stalls_on(pipeline._if_id["reads"], pipeline._id_ex, pipeline._ex_mem):
            stall = True
    # IF
    fetched = None
    if squash:
        pipeline.pc = pipeline._id_ex["target"]
        pipeline.stalls["control"] += 2
    elif stall:
        pipeline.stalls["data"] += 1
    elif not pipeline._halt_seen:
        fetched, fault = _fetch(pipeline)
        if fault is not None:
            _abort(pipeline, fault)
            pipeline._mem_wb = pipeline._ex_mem
            pipeline._ex_mem = pipeline._id_ex
            pipeline._id_ex = pipeline._if_id
            pipeline._if_id = None
            _publish(pipeline)
            return
    # latch
    pipeline._mem_wb = pipeline._ex_mem
    pipeline._ex_mem = pipeline._id_ex
    if squash:
        pipeline._id_ex = pipeline._if_id = None
    elif stall:
        pipeline._id_ex = None                   # p._if_id stays frozen
    else:
        pipeline._id_ex = pipeline._if_id
        pipeline._if_id = fetched
    _publish(pipeline)


def run_pipeline(pipeline, *, max_cycles=None):
    """Step until halted, faulted and drained, or the cycle cap is reached."""
    while _advances(pipeline):
        if max_cycles is not None and pipeline.cycles >= max_cycles:
            pipeline.status = "budget"
            break
        step_pipeline(pipeline)
    return pipeline
