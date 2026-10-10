"""CPU From Scratch — stage 09: forward, stall for a load, flush a branch

The finished implementation of `ForwardingPipeline`, `forward_operands`,
`step_forwarding` and `run_forwarding`. The reasoning — why there is no WB
bypass, why a load still costs one cycle, why a control is resolved in EX and
its two younger fetches are lost, and why the trace must be unchanged — is
argued in `stage_09.py`'s docstring. This file is only the body.

`ForwardingPipeline` is a sibling of stage 08's `Pipeline`, not a wrapper: it
runs its own cycle and shares stage 08 only the name of the machine it is a
faster version of. That keeps the forwarding rules visible in one place.
"""

import isa
from stage_01 import word
from stage_02 import BadInstruction, decode, disassemble, registers
from stage_03 import RegisterFile
from stage_04 import ALU_OPS, ArithmeticFault, alu
from stage_05 import AddressFault, Memory
from stage_06 import Fault, TraceRow
from stage_08 import Pipeline, STAGES

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

_LOADS = frozenset((_LW, _LB))
_STORES = frozenset((_SW, _SB))

#: The stall causes every pipeline counts, always all present.
STALL_KEYS = ("data", "load_use", "control")


class _Uop:
    """One instruction in flight: its decode plus whatever its stages latched."""

    __slots__ = ("pc", "word", "ins", "text", "op", "reads", "rd", "rs1", "rs2",
                 "writes_rd", "a", "b", "value", "address", "mem_size",
                 "store_value", "mem_effect", "faulted")

    def __init__(self, ins):
        self.pc = ins.pc
        self.word = ins.word
        self.ins = ins
        self.text = disassemble(ins)
        self.op = ins.op.code
        reads, writes = registers(ins)
        self.reads = reads
        self.rd = ins.rd
        self.rs1 = ins.rs1
        self.rs2 = ins.rs2
        self.writes_rd = bool(writes)
        self.a = 0
        self.b = 0
        self.value = None
        self.address = None
        self.mem_size = 4 if self.op in (_LW, _SW) else 1
        self.store_value = None
        self.mem_effect = None
        self.faulted = False

    def is_load(self):
        return self.op in _LOADS

    def is_store(self):
        return self.op in _STORES


class ForwardingPipeline(Pipeline):
    """The five-stage pipeline with forwarding, the load-use stall and the
    branch flush. Same architectural state as stage 06's `Machine`."""

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
        self._trace = []
        self.stalls = {key: 0 for key in STALL_KEYS}
        self._seed = self._apply_seed(initial)
        self.initial = self._seed
        self._if_id = None
        self._id_ex = None
        self._ex_mem = None
        self._mem_wb = None
        self._pending_fault = None
        self.stages = (None,) * len(STAGES)

    def _apply_seed(self, initial):
        """Apply the constructor's register seed, and return it as a tuple.

        Stored as `self._seed` so the inherited `Pipeline.reset` can rebuild the
        register file from it exactly as stage 8 does.
        """
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
        """A copy of the architectural state plus the pipeline counters."""
        return {
            "pc": self.pc,
            "status": self.status,
            "fault": self.fault,
            "registers": list(self.registers.snapshot()),
            "memory": self.memory.snapshot(),
            "cycles": self.cycles,
            "retired": self.retired,
            "trace": self.trace,
            "stalls": dict(self.stalls),
        }

    def reset(self):
        """Back to the state the pipeline was built with.

        Stage 8's `reset` rebuilds the register file from `self._seed`, zeroes
        the counters and the stalls, empties the trace and the latches; this
        machine additionally drops a fault that was still draining.
        """
        super().reset()
        self._pending_fault = None
        return self


def forward_operands(pipeline):
    """The `(a, b)` the EX stage uses, after the forwarding bypass.

    The operands start in the register file and are then overwritten by the
    instruction one stage ahead, in EX/MEM: its EX result (an ALU op) or its MEM
    result (a load). The MEM/WB latch is deliberately not a source: WB writes
    the register file before EX reads it in the same cycle, so a two-cycle-old
    value can never shadow a fresh one.
    """
    uop = pipeline._id_ex
    if uop is None:
        return 0, 0
    a = pipeline.registers.read(uop.rs1)
    b = pipeline.registers.read(uop.rs2)
    producer = pipeline._ex_mem
    if (producer is not None and producer.writes_rd
            and producer.value is not None and producer.rd != isa.ZERO):
        if producer.rd == uop.rs1 and uop.rs1 != isa.ZERO:
            a = producer.value
        if producer.rd == uop.rs2 and uop.rs2 != isa.ZERO:
            b = producer.value
    return a, b


def _fetch(pipeline):
    """Fetch and decode at the pc, or record a fault and return None."""
    pc = pipeline.pc
    if not 0 <= pc < len(pipeline._program):
        pipeline._pending_fault = ("fetch", pc,
                                   "pc %d outside a program of %d words"
                                   % (pc, len(pipeline._program)))
        return None
    word_ = pipeline._program[pc]
    try:
        ins = decode(word_, pc=pc)
    except BadInstruction as exc:
        pipeline._pending_fault = ("illegal", pc, str(exc))
        return None
    pipeline.pc = pc + 1
    return _Uop(ins)


def _halt_in_flight(pipeline):
    for latch in (pipeline._if_id, pipeline._id_ex, pipeline._ex_mem,
                  pipeline._mem_wb):
        if latch is not None and latch.op == _HALT:
            return True
    return False


def _retire(pipeline, uop):
    """Commit one instruction at WB: its register write, its trace row."""
    effects = []
    if uop.writes_rd and uop.rd != isa.ZERO and uop.value is not None:
        pipeline.registers.write(uop.rd, uop.value)
        effects.append(("r", uop.rd, word(uop.value)))
    if uop.mem_effect is not None:
        effects.append(uop.mem_effect)
    pipeline._trace.append(TraceRow(uop.pc, uop.word, uop.text,
                                    tuple(effects)))
    pipeline.retired += 1
    if uop.op == _HALT:
        pipeline.status = "halted"


def _do_ex(pipeline, uop):
    """Compute one instruction in EX, forwarding its operands.

    `None` continues, an int redirects, the string `"fault"` faults.
    """
    code = uop.op
    a, b = forward_operands(pipeline)
    uop.a, uop.b = a, b
    if code == _LI:
        uop.value = word(uop.ins.imm)
    elif code == _MOV:
        uop.value = a
    elif code in ALU_OPS:
        try:
            uop.value = alu(code, a, b, pc=uop.pc)[0]
        except ArithmeticFault as exc:
            uop.faulted = True
            pipeline._pending_fault = ("arith", uop.pc, str(exc))
            pipeline.pc = uop.pc
            return "fault"
    elif code == _ADDI:
        uop.value = word(a + uop.ins.imm)
    elif code in _LOADS:
        uop.address = word(a + uop.ins.imm)
    elif code in _STORES:
        uop.address = word(a + uop.ins.imm)
        uop.store_value = b
    elif code == _JMP:
        return uop.ins.imm
    elif code == _JZ:
        return uop.ins.imm if a == 0 else None
    elif code == _JNZ:
        return uop.ins.imm if a != 0 else None
    elif code == _BEQ:
        return uop.ins.imm if a == b else None
    elif code == _BNE:
        return uop.ins.imm if a != b else None
    elif code == _JAL:
        uop.value = word(uop.pc + 1)
        return uop.ins.imm
    elif code == _JR:
        return a
    return None


def _do_mem(pipeline, uop):
    """Do the memory access. True when it faulted (the store is not written)."""
    if uop.op in _LOADS:
        try:
            uop.value = pipeline.memory.load(uop.address, uop.mem_size)
        except AddressFault as exc:
            uop.faulted = True
            pipeline._pending_fault = ("address", uop.pc, str(exc))
            pipeline.pc = uop.pc
            return True
    elif uop.op in _STORES:
        try:
            pipeline.memory.store(uop.address, uop.mem_size, uop.store_value)
        except AddressFault as exc:
            uop.faulted = True
            pipeline._pending_fault = ("address", uop.pc, str(exc))
            pipeline.pc = uop.pc
            return True
        uop.mem_effect = ("m", uop.address, uop.mem_size, uop.store_value)
    return False


def _hazard(pipeline, uop):
    """The only forwarding stall: a load in EX whose result the next
    instruction needs at EX, one cycle before MEM has produced it."""
    producer = pipeline._id_ex
    if (producer is not None and producer.is_load() and producer.writes_rd
            and producer.rd in uop.reads):
        return "load_use"
    return None


def step_forwarding(pipeline):
    """Run one cycle of the forwarding machine, in stage order WB -> IF."""
    if pipeline.status != "running":
        return
    pipeline.cycles += 1

    # --- WB ---
    if pipeline._mem_wb is not None:
        _retire(pipeline, pipeline._mem_wb)

    # --- MEM ---
    next_mem_wb = pipeline._ex_mem
    next_ex_mem = pipeline._id_ex
    next_id_ex = None
    next_if_id = None
    redirect = None
    if next_mem_wb is not None and _do_mem(pipeline, next_mem_wb):
        next_mem_wb = None
        next_ex_mem = None
        redirect = "fault"
    elif next_ex_mem is not None:
        outcome = _do_ex(pipeline, next_ex_mem)
        if outcome == "fault":
            next_ex_mem = None
            redirect = "fault"
        elif outcome is not None:
            redirect = outcome

    # --- ID and IF ---
    if redirect == "fault":
        pipeline._if_id = None
    elif redirect is not None:
        if pipeline._if_id is not None:
            pipeline.stalls["control"] += 1
        pipeline.stalls["control"] += 1
        pipeline._if_id = None
        pipeline.pc = redirect
    elif pipeline._if_id is not None:
        cause = _hazard(pipeline, pipeline._if_id)
        if cause is not None:
            pipeline.stalls[cause] += 1
            next_if_id = pipeline._if_id
        else:
            next_id_ex = pipeline._if_id
            if not _halt_in_flight(pipeline):
                next_if_id = _fetch(pipeline)
    elif not _halt_in_flight(pipeline):
        next_if_id = _fetch(pipeline)

    pipeline._if_id = next_if_id
    pipeline._id_ex = next_id_ex
    pipeline._ex_mem = next_ex_mem
    pipeline._mem_wb = next_mem_wb
    pipeline.stages = (pipeline._if_id, pipeline._id_ex, pipeline._ex_mem,
                       pipeline._mem_wb, None)

    if (pipeline._pending_fault is not None and pipeline._if_id is None
            and pipeline._id_ex is None and pipeline._ex_mem is None
            and pipeline._mem_wb is None):
        kind, fpc, detail = pipeline._pending_fault
        pipeline.status = "faulted"
        pipeline.fault = Fault(kind, fpc, detail)
        pipeline._pending_fault = None


def run_forwarding(pipeline, *, max_cycles=None):
    """Cycle until the machine halts or faults, or `max_cycles` is reached."""
    if max_cycles is None:
        while pipeline.status == "running":
            step_forwarding(pipeline)
        return pipeline
    performed = 0
    while pipeline.status == "running" and performed < max_cycles:
        step_forwarding(pipeline)
        performed += 1
    if pipeline.status == "running":
        pipeline.status = "budget"
    return pipeline
