# CPU From Scratch

Build the machine that runs a program — decoder, register file, ALU, control
unit, memory, and then a five-stage pipeline — in pure standard-library Python,
with the instruction set, the assembler and five real programs provided.

The lab is here (`isa.py`): 29 opcodes in one encoding
(`[opcode:6][rd:4][rs1:4][rs2:4][imm:14]`, a signed 14-bit immediate), a
two-pass assembler with labels that names the line it refuses, and five programs
— `sum_to_n`, `factorial`, `fib`, `memcpy`, `count_bits` — which all assemble,
all halt, and all halt on a zero input. What is *not* here is the datapath.
Every one of the failures below is a check here, and every one of them is easy to
make and hard to notice:

- a mask that does not mask (`word(-1)` returning `-1`), a sign extension that
  forgets the top bit (`0x3FFF` as 16383 instead of -1), an immediate range that
  admits 8192 or a `bool`, a shift amount Python is happy to honour (32) where
  hardware uses the low five bits;
- carry confused with signed overflow: `0xFFFFFFFF + 1` wraps to zero and
  *carries*, with no overflow, while `sub`'s carry is the absence of a borrow;
- `pack_word` written big-endian, `unpack_word` reading three bytes of a
  four-byte buffer, or `-0.0`-style sloppiness — a packed word that is not
  masked before it becomes bytes;
- a decoder that reads a field through another field's shift, or lets the fields
  a format does not use survive as operands (`nop` with an `rd`), so `decode`
  then `encode` no longer round-trips;
- an unknown opcode that decodes as a `nop` instead of raising, and a refusal
  that names the mnemonic but not the word, the pc or the opcode;
- a load that disassembles as a positional operand list (`lw t0, t1, 4`) or a
  store that prints its base instead of its value, and register names off by one;
- a destination counted as a read (`add` "reads" `rd`), a store's base counted as
  a destination, a write to `r0` counted as a write, reads that come back in the
  wrong order or as lists;
- `r0` writable; `snapshot()` handing out the live list, so a value read before a
  write changes after it; `restore()` keeping the caller's list instead of
  copying it, or accepting fifteen values;
- `div` written as Python's `//`, which floors toward negative infinity where
  hardware truncates toward zero, and `mod` with Python's remainder, which takes
  the *divisor's* sign; `sra` shifting the unsigned word and `srl` the signed one;
- `slt` comparing the unsigned words and `sltu` the signed ones, or a comparison
  returning a `bool` where the ISA wants a masked word;
- a missing flag: `add` and `sub` are the only ops that set flags, and a machine
  with a flag register invents one for `and`;
- an ALU fault raised as a `ZeroDivisionError`, without the pc, or an
  `ArithmeticFault` used for a bad opcode (which is a plain `ValueError`);
- a bounds check that looks only at the first byte, so a four-byte load ending
  one past the end succeeds; alignment demanded against 2 for every size; a
  negative address or a `bool` size treated as legal;
- a store that writes before it refuses, so a refused store still moved a byte;
  a store that writes the raw value (`ValueError: byte must be in range`) or only
  its first byte, repeatedly; a byte load sign-extending `0xFF` to -1 instead of
  255;
- a snapshot that aliases the live buffer, or a `Memory(16)` that is 4096 bytes
  long;
- a machine whose fetch never faults, or whose fault *raises* instead of being
  recorded: a fault is data here, and the faulting instruction does not retire;
- `halt` that does not retire, or leaves the pc on itself; `cycles` that count
  fetches instead of retirements; a halted machine that keeps running; a step
  cap reported as a fault instead of a budget stop;
- `jal` linking the pc or the jump target instead of `pc + 1`; `jz` branching on
  non-zero; `mov` reading `rs2`; a load *always* reading four bytes, so `memcpy`
  faults instead of copying;
- `reset` that keeps the registers, the memory or the fault — a reset machine
  that is not the machine you started with;
- a loader that assembles every source text as a program name, that runs the
  program before handing back the machine, or whose `limit=0` means "no limit"
  instead of zero rows;
- a trace that keeps the `TraceRow`s instead of the `(pc, word)` pairs, or is a
  live list rather than a tuple;
- a fingerprint that drops the fault, hashes the memory object or its `repr`
  instead of its bytes, or uses the full `sha256` where the contract wants
  sixteen hex characters;
- a pipeline that does not see a dependency on the instruction in MEM (a
  *wrong value* rather than a stall, surfacing far from the hazard), charges no
  stall, files a control cycle as a data stall, or lets a squashed fetch behind a
  taken branch retire — so the pipeline computes something the single-cycle
  machine did not;
- a forwarding path that reads the producer from ID instead of MEM, that forwards
  a value two instructions back over the fresh one, that never forwards the
  second operand, or that forgets the one stall no wiring can remove — the
  load-use stall of a load feeding the very next instruction;
- a flush counted as a data stall; a cycle cap not reported as `budget`; a
  `stalls` dict losing or reordering its three causes;
- a CPI computed as the reciprocal (`0.454545` for 2.2), unrounded, truncated to
  two decimals, or carried as a string; a speedup hard-coded; a report whose key
  set is not exactly the contract's; `equivalent` hard-coded `True` where it must
  be computed by comparing two fingerprints;
- a measurement that accepts a run which retired nothing, or one that never
  halted, and publishes the truncated cycles as a partial result.

No network, no wall clock, no global state: a cycle is *counted*, and `time.time`,
`time.sleep`, `time.monotonic` and `time.perf_counter` are under landmines in the
smoke run. Where a decision was a judgement call, it is written down in the
template's docstring as a DESIGN DECISION, and the check asserts the consequence.

## The provided ISA

`isa.py` is complete and has no TODOs. The surface the course builds on:

```python
WORD_BITS, WORD_MASK, IMM_BITS, IMM_MIN, IMM_MAX   # 32, 0xFFFFFFFF, 14, -8192, 8191
REG_COUNT, REG_NAMES, ZERO, RA, SP                  # 16, the names, 0, 15, 14
Op, OPS, BY_CODE, BY_NAME, mnemonic(code)           # 29 opcodes, 0..28
AssemblyError, UndefinedLabel                       # .line, .token
assemble(text), assemble_lines(text)                # words from source text
PROGRAMS                                            # a read-only mapping of the five
```

Five programs come with it: `sum_to_n` (a0 → v0 = 1..n), `factorial` (a0 → v0 =
n!, through `jal`/`jr`), `fib` (a0 → v0 = fib(n), with a load immediately used
every iteration and a counter kept in memory), `memcpy` (a0/a1/a2 → a byte copy)
and `count_bits` (a0 → v0 = popcount). They fit in 8 to 16 words, they all end in
`halt`, and every one of them halts on a zero input — which is what makes them
usable as a fixture for a check that is allowed to be slow.

Three properties of `isa.py` are load-bearing: the immediate is **signed 14-bit**
(so a program can hold -1 but not 8192), the opcode field is **6 bits** (29 of 64
codes are used, and the rest must decode to a refusal rather than to a `nop`), and
the assembler is **two-pass** (a forward `jmp` to a label defined later must
assemble, and a program written as a name must be looked up in `PROGRAMS` rather
than assembled as text).

## The stages

| # | File | The mechanism | The thing people get wrong |
|---|---|---|---|
| 1 | `stage_01.py` | `Flags`, `word`, `signed`, `sign_extend`, `fits_imm`, `shift_amount`, `add_flags`, `sub_flags`, `pack_word`, `unpack_word` | A mask that does not mask; carry invented as signed overflow; `sub`'s carry inverted or strict; a shift amount Python honours; big-endian packing; `unpack_word` accepting a three-byte buffer |
| 2 | `stage_02.py` | `Instruction`, `BadInstruction`, `decode`, `encode`, `disassemble`, `registers`, `opcode` | Fields read through the wrong shift, or the unused fields surviving; an unknown opcode decoding as a `nop`; a refusal that names neither the word nor the pc; a load printed as a positional list; a write to `r0` reported as a write |
| 3 | `stage_03.py` | `RegisterFile` (`.read`, `.write`, `.snapshot`, `.restore`), `ZERO`, `RA`, `SP` | `r0` writable; `snapshot()` handing out the live list; `restore()` keeping the caller's list; a 64-bit write unmasked; an initial mapping with an unknown name or an out-of-range index accepted |
| 4 | `stage_04.py` | `ALU_OPS`, `ArithmeticFault`, `alu` | `div` floors where hardware truncates; `mod` takes the divisor's sign; `sra` on the unsigned word; a shift not masked; a flag invented for a logic op; `slt`/`sltu` swapped; a fault raised without its pc |
| 5 | `stage_05.py` | `Memory` (`.load`, `.store`, `.snapshot`, `__len__`), `AddressFault`, `DEFAULT_SIZE`, `ACCESS_SIZES` | Bounds checked on the first byte only; alignment demanded against 2; a store that writes before it refuses; a byte load sign-extending; a snapshot that aliases the live buffer |
| 6 | `stage_06.py` | `Fault`, `FAULT_KINDS`, `STATUSES`, `TraceRow`, `Machine`, `step`, `run`, `reset` | A fault raised instead of recorded; `halt` not retiring; `cycles` counting fetches; `jal` linking the wrong pc; `jz`/`jnz` inverted; a step cap reported as a fault; a store's traced effect missing or zero |
| 7 | `stage_07.py` | `load`, `trace`, `fingerprint` | Assembling a name as text; running the program before handing back the machine; `limit=0` read as "no limit"; the trace as `TraceRow`s or a list; the memory object hashed instead of its bytes |
| 8 | `stage_08.py` | `STAGES`, `STALL_CAUSES`, `Pipeline`, `retire`, `step_pipeline`, `run_pipeline` | A dependency on the MEM slot unseen; a squashed fetch retiring; a stall not charged, so `cycles == retired + 4 + stalls` breaks; a control cycle filed as data; the faulting pc not restored |
| 9 | `stage_09.py` | `ForwardingPipeline`, `forward_operands`, `step_forwarding`, `run_forwarding` | Forwarding a value two instructions back over the fresh one; reading the producer from ID; the second operand never forwarded; the load-use stall missing, filed as data, or watching the wrong latch; a flush counted as a stall |
| 10 | `stage_10.py` | `DP`, `REPORT_KEYS`, `measure`, `compare` | CPI as the reciprocal; an unrounded or string float; a report with an invented key; `equivalent` hard-coded; a zero-retirement or never-halting run published as a partial report |

## How to use this directory

```bash
python3 codecraft/cli.py run cpu-from-scratch    # what to build next, and why
python3 codecraft/cli.py hint cpu-from-scratch   # when a nudge is not enough
```

Or without codecraft:

```bash
python3 -c "import course; [print(i, s.title) for i, s in enumerate(course.STAGES, 1)]"
```

Implement the templates at the top level; finished versions are in `solutions/`.
The stages are cumulative, and the ladder is shallow on purpose: stage 2 imports
stage 1's `sign_extend`, stage 3 its `word`, stage 4 its flags and shifts, stage
5 its two byte helpers, stage 6 imports stages 2, 3, 4 and 5 (the machine *is*
those parts), stage 7 imports stage 6's `Machine`, stage 8 imports stages 2, 3, 4,
5 and 6's `Fault`/`TraceRow`, stage 9 imports stage 8's `Pipeline` and extends it,
and stage 10 imports stage 6's `run` and stage 7's `load`/`fingerprint` and
measures stages 8 and 9 against each other. A check for a late stage therefore
needs the earlier ones implemented, and `solutions/` overlaid on the templates is
the state those checks are written against. `isa.py` is not a stage: it is the
instruction set, the assembler and the programs, provided complete.

## Prerequisites

Standard library only: `hashlib`, `struct`-free byte handling, `sys`. No numpy,
no binary dependencies, no simulator, no HDL, no verilog — the whole machine is
tuples, ints and one `bytearray`. You should be comfortable with integer masking,
two's complement, `try/except` and dataclasses; the arithmetic is written out by
hand, on purpose, because "what does this instruction do to a 32-bit word?" is the
question this course is about.

## Design decisions

- **One program, two machines, one result.** The thesis of the course. The
  single-cycle `Machine` of stage 6, the stalling `Pipeline` of stage 8 and the
  `ForwardingPipeline` of stage 9 must retire the *same* trace — the same rows in
  the same order, with the same effects — and end in the same architectural state,
  which stage 7's `fingerprint` makes comparable as one value. A faster machine
  that computes something else is the bug this course exists to make impossible,
  and it is the failure mode of every real pipeline: a wrong value, three
  instructions later, in a program that still halts.
- **Stalls first, forwarding second.** With forwarding from the start, a load-use
  hazard produces a *wrong value* rather than a stall, and it surfaces far from
  the hazard that caused it — a load's data does not exist until MEM, and no
  forwarding path can invent it. Correct and slow is a baseline stage 9 can be
  measured against; correct and fast has to earn its cycles.
- **The cycle identity is checked, not assumed.**
  `cycles == retired + 4 + stalls_total` on every completed run: four cycles of
  fill, one per retirement, and everything else has to be accounted for as a
  stall. When it fails, the bug is named — a stall not charged, a squashed fetch
  made free, a control cycle filed as data.
- **A fault is data, not an exception.** `status == "faulted"`, `machine.fault`
  carrying the kind, the pc and a detail, further steps no-ops, and the faulting
  instruction *not* retired: its pc stays on it and its row never enters the
  trace. The single-cycle machine and both pipelines agree on all four kinds
  (illegal, arith, address, fetch) — same kind, same pc, same trace — because a
  fault is part of the architectural state, not an implementation's choice. A
  budget stop is `status == "budget"` and is *not* a fault.
- **`jr` exists because a return needs a register.** `jmp`'s format is an
  immediate only, so a call/return pair (`jal ra, f` … `jr ra`) is impossible
  without it. Bending `jmp` to accept a register would have made one opcode mean
  two things and, worse, would have made "is this a control instruction?" a
  question about *operands* rather than about the opcode.
- **A halt retires and is traced.** It writes nothing (`writes == ()`), it counts
  as retired, the pc advances past it, and only then does the status become
  `halted`. Anything else makes the two machines disagree about the last row of
  the trace — and the trace is the contract.
- **The register file is written at WB, memory is touched at MEM.** The stages
  exist to be observable. Writing a register at EX would let the very next
  instruction read it a cycle early; reading a load's data at EX would collapse
  the load-use hazard into a silent wrong answer.
- **Snapshots are values, never windows.** `RegisterFile.snapshot()` is a tuple
  copy, `Memory.snapshot()` is `bytes`, and `Machine.snapshot()` returns those:
  a "snapshot" that is a live view is the classic way for a comparison to pass
  for the wrong reason.
- **In this stage the memory is one flat bytearray with no caches**, so the cycle
  count is a property of the pipeline and not of the access pattern. Cache
  behaviour, branch prediction and out-of-order execution are deliberately someone
  else's course, and every cycle number in this course is exactly reproducible.

## Verification

The solutions pass all ten checks, and every check is mutation-tested: **360
plausible wrong implementations** — a mask that does not mask, carry invented as
overflow, `sub`'s carry inverted, a shift amount Python honours, big-endian
packing, a field read through the wrong shift, an unknown opcode decoding as a
`nop`, a load printed as a positional list, a destination counted as a read, `r0`
writable, a snapshot aliasing the live list, `div` floored by `//`, `mod` taking
the divisor's sign, `slt`/`sltu` swapped, a flag invented for `and`, a bounds
check on the first byte only, a store writing before it refuses, a byte load
sign-extending, a machine whose fault raises, `halt` not retiring, `cycles`
counting fetches, `jal` linking the jump target, `jz` branched backwards, a load
always reading four bytes, a `reset` keeping its memory, a loader assembling a
name as text, `limit=0` as "no limit", a fingerprint hashing the memory `repr`, a
pipeline blind to the MEM slot, a squashed fetch retiring, a stall not charged, a
control cycle filed as data, forwarding a value two instructions back, the second
operand never forwarded, the load-use stall missing, a flush counted as a stall,
a CPI that is the reciprocal, `equivalent` hard-coded `True` — are each planted
into a solution, and the stage's check must fail. Every assertion message names
the mistake, not the symptom; the count per stage is 36, 38, 32, 35, 33, 38, 37,
37, 40, 34.

Two proofs sit outside the per-stage checks. `mutate_all.py` replays all 360
mutations against the solutions under one runner (`MISSED OR BROKEN: 0`, the tree
rebuilt for every mutation with `PYTHONDONTWRITEBYTECODE=1`, because a stale
`__pycache__` whose size and second match the previous mutant's runs the
*previous* mutant's code and shows a real catch up as a miss; a mutant that hangs
its check for sixty seconds is reported as caught, because a wrong implementation
that never terminates anything is not a passing implementation). A smoke run
composes all ten stages over the five catalogue programs — three machines each,
the cycle identity, the four fault kinds, and stage 10's report — with
`time.time`, `time.sleep`, `time.monotonic` and `time.perf_counter` patched to
raise for the whole run:

```
SMOKE PASS — 5 programs, three machines, one result
  count_bits  85 retired | single 85 | stall 157 (data 34, control 34) | forward 123 (load_use 0, control 34)
  factorial   31 retired | single 31 | stall 56 (data 1, control 20) | forward 55 (load_use 0, control 20)
  fib         100 retired | single 100 | stall 202 (data 76, control 22) | forward 137 (load_use 11, control 22)
  memcpy      44 retired | single 44 | stall 94 (data 34, control 12) | forward 60 (load_use 0, control 12)
  sum_to_n    55 retired | single 55 | stall 125 (data 44, control 22) | forward 81 (load_use 0, control 22)
  faults: arith/illegal/address reported as data, identically, by all three machines
  measure: fib retired 10, single 10, pipeline 17, cpi 1.700, stall 2, forward 1, equivalent True
```

The forwarding pipelines win exactly where a load feeds the next instruction:
`fib` pays eleven load-use stalls and still runs in 137 cycles against 202 for
the stalling pipeline, `sum_to_n` in 81 against 125, and `stalls["data"]` is
zero on every forwarding run — the value came down a wire, it was not waited for.

The provided ISA has its own proof, `/tmp`-side in development and re-run before
this course was committed: 56 checks over `isa.py` — the encoding round-trips,
every opcode's format, the assembler's refusals (an unknown mnemonic, a wrong
operand count, a bad register, an out-of-range immediate, an undefined label, a
duplicate label, two labels on one line, an empty operand, a non-str program),
and the five programs assembling, halting and halting on a zero input.

Re-running the proofs:

```bash
python3 codecraft/cli.py run cpu-from-scratch    # per stage, with the failure line
python3 /tmp/g3-checks/run_all.py                # every stage's check, solutions overlaid
python3 /tmp/g3-checks/mutate_all.py             # every mutation, one runner
python3 /tmp/g3-checks/verify_isa.py             # the provided ISA and its assembler
python3 /tmp/g3-smoke.py                         # all ten stages composed
```

## Where this stops

Deliberately left out, so you know the boundary:

- **No floating point.** The ISA has integers, bytes and compares; `fadd` is
  someone else's rabbit hole. Two's complement, masking and signed division are
  the arithmetic this course is about.
- **No caches, no branch prediction, no speculation.** The memory is one flat
  `bytearray`, and a branch flush is modelled (the squashed fetches are counted)
  but never *predicted*: every cycle count here is a property of the pipeline,
  not of the access pattern. A cache course would make the cycle count depend on
  history, and this course exists so that two machines can be compared exactly.
- **No out-of-order or superscalar execution.** In-order, five stages, one
  instruction per stage per cycle. The interesting mistakes of out-of-order
  execution (renaming, in-order retirement, memory ordering) are a different
  course, and none of them can be checked before this one is right.
- **No interrupts, no traps with a handler, no privilege levels.** A fault stops
  the machine and is recorded; there is no vector table, no `eret`, no supervisor
  mode. That is the CPU half of an OS course, and the OS is phase G4.
- **No linker and no relocations.** The assembler takes one file of text and emits
  words; labels are resolved in the second pass. Object files, sections, symbols
  and relocation entries belong to a toolchain course.
- **No RISC-V compatibility.** The encoding is in the same *family* as phase G1's
  `compiler-and-vgpu` (32-bit words, 16 registers, split opcode/register/immediate
  fields) so the two courses speak one dialect, but it is a teaching ISA with an
  opcode for `li` and a 14-bit immediate, and it is not binary-compatible with
  anything. The instruction set is provided precisely so that the datapath is the
  subject.
