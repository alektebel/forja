# Transformer Inference Physics

Build the cost model that predicts TTFT and ITL — prefill and decode as two
different machines wearing one model, in pure standard-library Python, with
no floats anywhere: nanoseconds, bytes, flops and per-mille are ints the
whole way, and a prediction one nanosecond off is one formula wrong.

Inference is the one place where a model of the hardware pays for itself:
the same weights are compute-bound in prefill and memory-bound in decode,
the cache is a third budget that quantization cannot shrink, and the batch
where the two budgets trade places is arithmetic a check can demand. The
world is provided (`configs.py` — five transformer configs from TINY_MHA's
384-wide six layers to BIG_GQA's 8192-wide eighty, the dtype table
`{"fp16": 2, "fp8": 1, "int8": 1}` and the four dtype names; `devices.py` —
three accelerators as rows `(peak_fp16, bw_bytes_per_ns, eff_compute,
eff_bandwidth, launch_ns, vram_bytes)` — H_CLASS 989000/3350/700/800/250 and
80 GB, A_CLASS 312000/2039/650/750/300 and 40 GB, D_CLASS 165000/1008/600/900/
350 and 24 GB — plus `FLOP_MULT` giving each dtype its tensor-core
multiplier; `trace.py` — six workloads, the measured trace as a reference
implementation, `PROBE_NS = 1500` and the sixteen-row `TRACKS` grid). The
cost model on top of that world is what you write, and the trace — written
by the world, never by a stage — is the judge.

Count the parameters and the weight bytes with int4's per-matrix packing;
count the flops a token and a prompt cost, the matmuls only, the head once
per sequence; count the bytes — the weights' read, the cache's rent, the
intensity per kilobyte; put the two budgets on one roofline where the wall
time is a max and a tie serves memory; price prefill (TTFT's model,
compute-bound, no probe tax in the arithmetic); price decode (ITL's model,
memory-bound by a hundred-fold); tabulate the KV cache's life against a
device's VRAM; find the crossover batch where the mlp flips — 259 for every
fp16 config on H, 110 on D — and walk the batch curve through it; trade the
weights against quantization while the cache refuses to shrink; and audit
every prediction against the world's own measurement, wall included: the
rows the device cannot serve refuse before the model gets to guess.

No clock, no `random`, no `float`, no `math` behind a stage: a `PhysError`
that refuses by naming the offending pin is the only honest answer to a
config that cannot be a transformer, and the hand-derived literals the
checks demand come from the contract's formulas — never from `trace`.

## The ten stages

| N | File | Title |
|---|---|---|
| 1 | `stage_01.py` | The parameters: what a config is |
| 2 | `stage_02.py` | The flops: the compute budget |
| 3 | `stage_03.py` | The bytes: the memory budget |
| 4 | `stage_04.py` | The roofline: the race's rules |
| 5 | `stage_05.py` | Prefill: TTFT's model |
| 6 | `stage_06.py` | Decode: ITL's model |
| 7 | `stage_07.py` | The KV cache: the third budget |
| 8 | `stage_08.py` | The crossover: where decode stops being memory-bound |
| 9 | `stage_09.py` | Quantization: the weights' half of the trade |
| 10 | `stage_10.py` | The audit: the model meets the measurement |

Stage 10 is the capstone: `predict` walks a `TRACKS` row from names to
nanoseconds — TTFT the prefill plus one probe tax, ITL the generation's mean
decode step over the schedule `prompt + i` plus one probe tax, tps floored,
the VRAM law refusing a wall before any arithmetic — and `audit` grades
every row against `trace.measure`/`trace.bound` exactly, naming a liar as
`(row, key, expected, got)`. The audit measures through `trace`, never
through the stages it is auditing: a stage grading its own homework along
its own code path is the one corruption a from-scratch course cannot
tolerate.

## Measured verification

| What | Command | Result |
|---|---|---|
| the stages | `python3 .i2-dev/check_NN.py` (1..10) | ten `PASS` (19+12+16+17+14+12+8+8+11+12 = 129 facts), and ten exits 2 against the templates |
| the mutations | `python3 .i2-dev/mutate_all.py` | `TOTAL 135/135`, `MISSED OR BROKEN: 0` |
| the ladder and the laws | `python3 .i2-dev/audit_course.py` | `AUDITED: 10, PROBLEMS: 0` |
| the provided world | `python3 .i2-dev/verify_provided.py` | `53 facts, all hold` |
| the whole course as one module | `python3 .i2-dev/smoke.py`, `run_assembled.py` | `SMOKE: PASS`, `ASSEMBLED: 10/10` |
| the tests the course ships | `python3 .i2-dev/count_tests.py transformer-inference-physics` | 140, per stage `[17, 13, 17, 18, 12, 12, 12, 12, 14, 13]` |
| the pins | stage 10's `predict` against `trace.TRACKS` | sixteen rows — TTFT, ITL, both bounds, tps, kv_bytes — all equal to the measurement |

The walls are the acceptance evidence beside the passes: `("BIG_GQA",
"H_CLASS", "W_A", "fp16")` needs 139,418,664,960 bytes against a 85,899,345,920-byte
device and refuses, while the int8 row at the same coordinates predicts
103,705,889 ns exactly; `("SEVEN_MHA", "D_CLASS", "W_E", "fp16")` needs
34,688,991,232 against 25,769,803,776 and refuses. The crossover is
config-invariant — 259 for every world config on H at fp16, heads included,
130 under int4, 110 on D, 133 on A — because the `d` and `d_ff` fold out of
the mlp's two budgets, and the battery kills every mutant that forgets it.

The provided world is pinned by digest:

| File | sha256 |
|---|---|
| `configs.py` | `312b785426197a7123bb28b4378f8a3909a4650ef08a013416f21f7c08b4c0b7` |
| `devices.py` | `8e340f4bbdd019d0b01d1fa828c981f8b406a14ac86507fc5372c9d08ca77c33` |
| `trace.py` | `6b3c13523bf5ab93ab4f9b036bc153d3defb8dad174b39aa9728e478d541a552` |

## The laws a stage is held to

- Standard library only; no `float`, no `math`, no `random`, no clock, no
  thread, no socket. Every division is `//` with the contract's (§2)
  rounding order pinned formula by formula.
- `PhysError` (stage 1's, a `ValueError` subclass) refuses by naming the
  pin: a config that does not tile, a dtype off the table, a device off the
  world, a `ctx=0` — the refusal states the offending number or name.
- The tie law: `classify` and `phase_bound` answer `"memory"` on equality —
  the bytes are read into SRAM regardless.
- int4 packs `(params + 1) // 2` per matrix, never one-shot over the total;
  the KV cache is fp16 under every weight dtype and immune to the pack.
- The attention flops ride `n_heads`, never `n_kv_heads` — GQA shrinks the
  read, not the compute; the head runs once per sequence, not per token.
- `prefill` and `decode` totals carry NO probe tax; `predict` adds the
  world's `PROBE_NS` to both events when it meets the measurement.
- The world is never edited to make a stage pass; the three digests are
  pinned, and `trace` is data a stage reads and never re-implements.

## Where the formulas meet silicon

The course never measures anything: `trace.py` is the offline stand-in for
Nsight Systems, with the profiler's own probe tax pinned at `PROBE_NS =
1500` ns — the one number between a cost model's arithmetic and a profile's
answer. Where each formula meets real silicon is the runbook, hardware's
half of the bargain: the achieved fractions behind `eff_compute` and
`eff_bandwidth` (per-mille of the fp16 peak and of the bytes/ns pipe) come
from a GEMM in `nsys profile` and a memcpy in `nvidia-smi dmon`;
`launch_ns` is the per-kernel gap in the same timeline — this course's
decode table is `4 x layers + 1` kernels (qkv, attn, o, mlp per layer, the
head once), and a fused kernel retires that number; `FLOP_MULT`'s 2x for
fp8, int8 and int4 against fp16 is the tensor-core claim the dtype rows are
measured to, and int4 computing at the int8 peak is the one the world pins.

## Running it

    python3 codecraft/cli.py run transformer-inference-physics

The ten stages are graded in order; the later ones compose the earlier ones
(that is what the ladder law is for): stage 1's packing rule is what stage
4's `matrix_bytes` carries into every op table, stage 2's flops and stage
3's bytes are the two budgets stage 4 races, stage 4's per-op max is what
stages 5 and 6 sum into the two phases, stage 7's rent is what stage 8's
crossover outgrows and stage 10's `kv_bytes` bills, stage 6's step is what
stage 9's gain divides against — and stage 10 is the model meeting the
measurement, one nanosecond at a time.
