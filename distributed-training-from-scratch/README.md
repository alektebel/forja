# Distributed Training From Scratch

Build the plans a training run is made of — DDP's bucketed gradient all-reduce,
ZeRO-1/2/3 and FSDP, tensor parallel's two all-reduces per block, the pipeline
schedules and their bubbles, the expert all-to-all, ring attention, and the
configuration that chooses between them — on the collectives I9 wrote, with the
model handed to you. Ten graded stages, pure standard-library Python, offline,
deterministic, and **every number an int**.

The thesis is one sentence: **one model, many devices, the same math.** Every
stage ends at the same reference single-device result — a gradient, an
activation, an attention output, a loss — reached through a different plan. A
plan is frozen data with three independent checks: its **bytes** (per rank and
over the network), its **memory ledger** (what each rank holds while the plan
runs), and its **semantics** (recomputed against the reference). Two plans can
match on bytes and differ in the ledger; two can match on both and differ in what
they compute. The failures worth preventing are the ones that pass two of the
three: a ZeRO stage that shards the optimizer but forgets the gradients, an FSDP
wrap that gathers a unit and never scatters it, a 1F1B schedule that cools down
before it warms up, an all-to-all whose offsets are per-destination instead of
cumulative, an attention ring that loses a block's contribution to the running
pivot.

## The stages

Ten graded stages. Each one targets a mistake that is easy to make and hard to
notice.

| # | File | The mechanism | The thing people get wrong |
|---|---|---|---|
| 1 | `stage_01.py` | The step is a plan: bytes per rank and over the network, the ledger of what each rank holds, and the tick model (`plan_ticks`, `step_ticks`) every later stage prices itself with | A plan priced by its transfers instead of its steps; the ledger reporting the network's bytes or the full state on every rank |
| 2 | `stage_02.py` | Data parallel: the gradient bucketed, all-reduced over the world, and hidden behind the compute | Gradients summed without averaging, or averaged without the bucket; comms added to compute instead of overlapped into a `max` |
| 3 | `stage_03.py` | ZeRO's ladder: the parameters replicated, the gradients and then the optimizer state sharded — `4 + 12/N` for ZeRO-1, `2 + 2/N + 12/N` for ZeRO-2 | Sharding the optimizer and forgetting the gradients; a ledger that shrinks the parameters instead; a reassembly that loses the remainder byte |
| 4 | `stage_04.py` | FSDP: one unit at a time, all-gathered before its forward and reduce-scattered after its backward, with the wrap policy that decides what a unit is | A wrap that never scatters; a peak memory counted from the unit's size instead of the union of the live units; the per-rank figure remembered as `3P` instead of the `4P(N−1)/N` that equals DDP's |
| 5 | `stage_05.py` | Tensor parallel: the column block and the row block, and the two all-reduces per block that put them back together | Summing a column-parallel result that should be concatenated; a row-parallel half that contracts the wrong axis; an axis of one still issuing its collectives |
| 6 | `stage_06.py` | The pipeline schedules: GPipe's forwards-then-backwards and 1F1B's steady state, with the bubble replayed from the schedule | A bubble taken from a formula instead of replayed; a backward in the same step as its own micro-batch's forward; a schedule with no warm-up or cool-down |
| 7 | `stage_07.py` | Interleaving: `m·v` units over `p` stages, so the bubble becomes `(p−1)/(m·v+p−1)` — `3/19` where GPipe's is `3/11` | A virtual chunk order that does not reproduce GPipe at `v=1`; a lifetime that runs forward-to-backward at the wrong stage; a peak taken from one activation instead of the union of the live intervals |
| 8 | `stage_08.py` | Expert parallel: the routing table, the capacity factor that drops the overflow, the balance loss, and the dispatch/combine pair | A routing that is balanced because every token goes to every expert; a capacity that silently rounds up; a dispatch with no combine |
| 9 | `stage_09.py` | Ring attention: the exact running pivot, the accumulator as a pair of integers, and the KV blocks that travel the ring | A pivot that rises (a float's problem, not an exact one); the contribution dropped when the pivot drops; a `q` padded to make the shapes match |
| 10 | `stage_10.py` | The configuration: every axis split priced by ticking it, the argmin chosen, and the report derived from the plan | A split chosen by fashion; an unfittable split returned instead of refused; a report that declares its numbers instead of recomputing them from the plan |

Stages 2–10 compose the earlier ones (stage 10 composes all of them), so they are
meant to be done in order — each check imports the solutions of the stages it
builds on.

## The provided world

Three modules are given and are not part of the exercise.

`fabric.py` is I9's, copied verbatim: links with bandwidth and latency, four
topologies (`ring`, `full`, `tree`, `switch`), the flat `Plan`/`Transfer` records,
`legality_problems`, and the executor that applies a plan to buffers. Every plan
this course builds is one of those — and every one of them is checked for
legality before it is priced.

`plans.py` is I9's collective library lifted into one file: `ring_broadcast`,
`tree_broadcast`, `ring_reduce`, `tree_reduce`, `ring_allreduce`,
`tree_allreduce`, `doubling_allreduce`, `allgather`, `reduce_scatter`,
`alltoall` (scheduled, so its step count is a property of the topology: 7 on
`full(8)`, 14 on `ring(8)`, 16 on `switch(8, width=4)`, 19 on `tree(8)`),
`alltoall_from_splits`, `sendrecv`, and the helpers (`group_ranks`,
`group_fabric`, `chunking`, `equal_split`, `steps`). It refuses what the fabric
cannot serve: a ring all-gather on a tree, a doubling all-reduce across a
two-level switch spine, an in-place ragged table that would overwrite a slice a
later step reads.

`model.py` is the world's arithmetic and the reference every stage is measured
against:

- `ELEMENT_BYTES = 4`, `PARAM_BYTES = 2`, `MASTER_BYTES = 4`,
  `OPTIMIZER_BYTES = 8` — 16 bytes per parameter for the full training state.
- `Tensor`, `ModelShape(layers, hidden, heads, ffn_hidden, vocab, experts=0,
  top_k=0)`, with `params()`, `flops_per_token()`, `activation_bytes(batch, seq)`,
  `tensors()`, `params_per_world(ranks)`.
- `reference_layer(x, w, b)` — `y[i][j] = b[j] + Σ_k x[i][k]·w[j][k]`, one row of
  `w` per output neuron, the only definition of a layer this course uses.
- `reference_gradients(shape, *, batch, seq)` — the exact integer chain rule.
- `reference_attention(q, k, v)` — the exact reduced pair `(numerator,
  denominator)`, never a float.
- `SHAPES`: `tiny` (2/4/2/8/12, 388 parameters), `1b` (20/2048/16/5632/32000,
  1 093 224 448) and `7b` (34/4096/32/11008/32000, 7 012 110 336).

Four rules make the rest of the course checkable:

- **The forward is provided; the plan is yours.** A disaggregated plan must
  reproduce the single-device reference exactly — same layer output, same
  gradient, same attention pair — before its bytes are examined.
- **A plan is priced by its steps.** A step is its slowest transfer; a plan is
  the sum of its steps; an overlap is a `max`, never a `+`.
- **The ledger is per rank and per moment.** What a rank holds *while the plan
  runs* is the number that matters, and sharding that is not in the plan does not
  shrink it.
- **No number in this course is a float.** Every byte count is `ceil_div`, every
  ratio is a reduced `(numerator, denominator)` pair, and no fixture reads a
  clock.

## How to use it

```bash
python3 codecraft/cli.py run distributed-training-from-scratch
```

work one stage at a time; each template states the decision it is asking you to
make and ends with `TODO: implement …`. The solutions are in `solutions/`, meant
to be read after your own attempt — `solutions/README.md` lists them in the order
the stages build on each other.

## Prerequisites

`interconnects-from-scratch` (I9) — the collectives, the cost model and the
fabric this course builds its plans on. Nothing else: no framework, no GPU, no
cluster, no dependency outside the standard library.

## Design decisions

- **Three provided modules, not one.** The fabric is a model of the network, the
  plans are the collectives written once against it, and the model is the
  arithmetic every stage is measured against. Without `plans.py` every stage
  would re-derive I9's algorithms instead of composing them.
- **The tick model lives in stage 1.** `plan_ticks` and `step_ticks` are stage 1's
  surface, and every later stage prices itself with them — so a wrong overlap
  arithmetic is caught once, where it is written, instead of in all eight places
  that use it.
- **Exact rationals, never floats.** Attention's pivot and its accumulator are
  integer pairs with exact shifts, and every bubble is a reduced fraction. A
  float would hide a dropped block behind a rounding error; an exact pair cannot.
- **A plan is not its numbers.** Stage 10's report is recomputed from the plan and
  never declared, which is the one defect class the whole course exists to
  prevent: a configuration that runs, prints plausible numbers, and prices a plan
  it did not build.
- **The schedules are replayed, not formula-derived.** A bubble is counted by
  replaying the slots and asking which `(stage, step)` pairs carry no task, so the
  check cannot agree with a buggy formula by sharing it.

## Verification

Each stage ships with a check and a mutation proof in the course's dev harness:
`check_NN.py` probes the stage's mechanism, its refusals and its boundary cases,
and `mutate_NN.py` plants one defect per mutation in a copy of the solution and
confirms the check catches it. The acceptance bar is every planted mutation
caught, at least 34 per stage.

| Stage | Mutations caught | Stage | Mutations caught |
|---|---|---|---|
| 1 bytes, ledger, ticks | 49 | 6 pipeline schedules | 46 |
| 2 data parallel | 57 | 7 interleaved schedules | 46 |
| 3 ZeRO's ladder | 60 | 8 expert parallel | 59 |
| 4 FSDP | 54 | 9 ring attention | 45 |
| 5 tensor parallel | 54 | 10 the configuration | 84 |

554 mutations across the ten stages, `MISSED OR BROKEN: 0`; the course audit —
every stage's template shape, docstring contract, refusal classes and imports —
reports `PROBLEMS: 0`; and the whole course runs as one process, ten stages
composed into a single deterministic step, ending

    SMOKE PASS — 30 probes, ten stages, one deterministic step

## Where this stops

No autograd (the gradients this course shards are the ones `model.py` computes,
and the engine that computes them is the next course), no NCCL internals, no
CUDA, no launcher, no real hardware. The fabric is a model of a network and the
model is a model of a transformer: what is graded is the plan and its price, and
both are exact.
