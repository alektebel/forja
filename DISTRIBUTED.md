# Distributed infrastructure — NCCL, collectives, and how LLMs train across devices

This document is the detailed map for two slots the roadmap already carries:
**I9 `interconnects-from-scratch`** (the collectives, the fabric, NCCL's
algorithms) and **H1 `distributed-training-from-scratch`** (what a training
framework does with them). It exists because both are easy to *use* and hard to
*see*: the failure modes they hide — a ring all-reduce that sends the whole
buffer every step, a ZeRO-3 that all-gathers the world instead of the layer, a
pipeline schedule whose bubble formula ignores the micro-batches, comms added to
compute instead of hidden behind it — are all silent. They produce a number that
looks plausible and a run that is three times slower than it should be.

The repo's shape decides how these get taught: **a provided simulator, a
deterministic model, numbers that are counted and never timed.** No GPU, no
network, no `time`. Every byte and every tick in these courses is an int.

---

## Part 1 — What NCCL is

NCCL (NVIDIA Collective Communications Library) is a **library of collective
operations over GPUs**, and nothing else. It does not shard models, schedule
pipeline stages, or decide what to all-reduce. A framework decides *what* to
communicate; NCCL decides *how the bytes get there*, and it is the layer where
"how" is worth 2× to 5× of a training step's wall clock.

**The model.** One *communicator* per group of ranks (`ncclCommInitRank`), one
rank per device in the usual one-process-per-GPU layout, and every collective is
launched on the group's set of streams. Collectives are *symmetric*: every rank
calls the same function with the same arguments (only the send/recv buffers and
the root differ), and `ncclGroupStart`/`ncclGroupEnd` makes a set of calls
launch as one operation — all of them or none. That is the contract: a
collective call is not a message send, it is a joint commitment.

**The surface** (`ncclAllReduce`, `ncclReduce`, `ncclBroadcast`, `ncclAllGather`,
`ncclReduceScatter`, `ncclAllToAll`, `ncclSend`/`ncclRecv`, plus the `Group`
pair), the in-place variants, `ncclCommSplit` for sub-groups, and the data types
— bf16/fp16/fp32/int8 — matter because **the dtype is the cost**: an all-reduce
of fp32 gradients moves twice the bytes of the bf16 reduction of the same model.

**The transports.** NCCL discovers the topology and then uses the fastest path it
can: P2P over **NVLink/NVSwitch** inside a node (hundreds of GB/s), CUDA P2P over
PCIe, host shared memory between processes on one box, and **InfiniBand verbs
(RDMA) over the network** between nodes. A transferred buffer is chopped into
*chunks*, a chunk travels a *ring* or a *tree* built from the discovered
topology, and the per-link bandwidth and latency decide which of them is used —
that decision is the whole reason `NCCL_ALGO` and `NCCL_PROTO` exist as knobs.

**The protocols.** `Simple` (each chunk copied to the wire once, the most
bandwidth-efficient, the most latency-sensitive), `LL` (a small flag per step so
the receiver can poll with 8-byte transactions — latency-optimal, poor for large
messages) and `LL128` (128-byte lines, a compromise). The lesson the courses
teach: *no single protocol wins*, because the trade is always bytes-per-flop of
progress versus bytes-on-the-wire per payload byte.

**The algorithms, with their costs.** Let `S` be the message size in bytes, `N`
the number of ranks, `α` the per-hop latency and `β` the per-link bandwidth:

| Collective | Algorithm | Per-rank bytes | Steps |
|---|---|---|---|
| All-reduce | **ring**: reduce-scatter then all-gather | `2·S·(N−1)/N` | `2(N−1)` |
| All-reduce | **tree**: reduce to root, broadcast | `≈ 2S` per rank, but `≈ 2S(N−1)` on the network | `2·log N` |
| All-reduce | **recursive doubling / halving** | `S·log N` | `log N` |
| Reduce-scatter / All-gather | ring | `S·(N−1)/N` | `N−1` |
| Broadcast | ring / binomial tree | `S·(N−1)/N` / `≈ S` | `N−1` / `log N` |
| All-to-all | pairwise exchange, uneven splits | `S·(N−1)/N` | `1` (bandwidth-bound) |

The ring is **bandwidth-optimal** (`(N−1)/N → 1`) and tree-style algorithms are
**latency-optimal** (`log N` steps instead of `N−1`). Note the tree's second
column: it is cheap *per rank* — one send up, one receive down — and expensive on
the *network*, because every level moves the whole payload again. That is exactly
the trade: small messages want fewer hops (tree), large messages want fewer bytes
on the wire (ring), and `NCCL_ALGO` exists because the crossover depends on `S`.
Add SHARP/CollNet — in-network reduction, where the switch adds the partials so
they cross the fabric once instead of `2(N−1)/N` times — and the lesson becomes:
*the algorithm is part of the model.*

The lower bound to check every implementation against: an all-reduce must make
every rank hold the sum, so at least `S·(N−1)/N` bytes have to *leave* each rank
once. A ring all-reduce hits `2×` that (scatter then gather) and no algorithm can
beat it by much; an implementation that moves `S` per rank per step is moving the
whole buffer — the planted mistake in stage 4 of I9.

---

## Part 2 — What the training algorithms do with it

**Data parallel (DDP).** Replicate the model, split the batch, all-reduce the
gradients. With `P` parameters, the steady-state cost per step is
`2·P·(N−1)/N` bytes per rank — for `N` large, **2P** (bf16/fp32) — and the whole
game is *overlap*: gradients become available layer by layer during the backward
pass, so a framework buckets them (the classic 25 MB bucket) and starts a
reduce-scatter per bucket as soon as it is full. Compute and comms then overlap,
and the step time becomes `max(compute, comms)` instead of their sum. The reason
DDP keeps working is arithmetic: ~`6·P` FLOPs per token forward+backward against
`2·P` bytes of gradient per rank — the ratio that has to be large compared to the
accelerator's FLOPs-per-byte of interconnect, which is why **gradient
accumulation** (more compute per communication) is the first lever, and why
faster interconnect is worth real money.

**ZeRO (1/2/3) and FSDP.** The memory per parameter, mixed precision + Adam:
fp16 params (2 B) + fp16 grads (2 B) + fp32 optimizer state (4 + 4 B for the two
moments) + fp32 master weights (4 B) = **16 B/param** at the optimizer step.
ZeRO-1 shards the 12 B of optimizer state across `N` ranks, ZeRO-2 adds the 2 B of
gradients, ZeRO-3 (FSDP) adds the 2 B of parameters — so a 7B model's ~112 GB
becomes 112/`N` GB. The price is comms: DDP all-reduces grads once (2P bytes), the
fully sharded plan must **all-gather parameters per layer before its compute and
reduce-scatter its gradients after** (≈ 3P bytes per step in total), which only
pays because both happen layer by layer and overlap the compute of the previous
and next layers. The lesson: *sharding is a memory-for-bandwidth trade, and the
trade is only good if the traffic hides.*

**Tensor parallel (Megatron).** Split a weight matrix itself — column-parallel
then row-parallel, so each rank computes a partial sum that has to be combined
with an **all-reduce per block** (one in the forward pass, one in the backward),
plus the matching pair for the MLP and the attention projections. Per transformer
layer that is a handful of all-reduces of an activation-shaped tensor
(`batch·seq·hidden·dtype` bytes each), which is a *latency* problem, not a
bandwidth one — hence tensor parallelism lives inside a node, on NVLink, and
usually with `N ≤ 8`. Sequence parallelism moves the LayerNorm/dropout work out
of that path; context (ring-attention) parallel splits the *sequence* and passes
KV blocks around a ring with an online softmax, so the attention's own comms stay
`O(seq · heads)` per hop.

**Pipeline parallel.** Split the *layers*, move activations between stages with
point-to-point sends. The naive schedule (GPipe: all micro-batches forward, then
all backward) has a bubble of `(p−1)/(m + p − 1)` of the step — `p` stages, `m`
micro-batches — and the fix is the schedule itself: 1F1B interleaves forward and
backward so the bubble shrinks to `(p−1)/(m·v + p − 1)` with `v` virtual stages
per rank. Pipeline parallelism is bandwidth-cheap (`batch·seq·hidden` bytes per
stage boundary, latency-bound) and costs the most in **bubble** and activation
memory, which is why it is the outermost axis, spanning nodes.

**Expert parallel (MoE).** Route tokens to experts on other ranks: two
**all-to-all** exchanges per MoE layer (dispatch, then combine), a capacity
factor that caps how many tokens one expert will take, and a load-balancing loss
to keep the exchange even. The all-to-all is the only collective whose cost
depends on the *data* — a hot expert makes it unbalanced, and a token dropped at
the capacity cap silently changes the model.

**The composition.** Real training is a product of all of these: DP across nodes
× ZeRO within a group × TP within a node × PP across stages × EP inside the MoE
blocks. The arithmetic that decides each axis is the same in every case: **bytes
per step, divided by the interconnect's bandwidth, against the compute it should
hide behind.** A course can teach that exactly, because it is counting.

---

## Part 3 — The two courses

### I9 `interconnects-from-scratch` — the collectives themselves

*After G3/J1. Provided: `fabric.py` — a topology of ranks joined by links, each
with a bandwidth and a latency, plus the transfer accounting (a link moves bytes
at its bandwidth for a length of time the model fixes, and the model advances
ticks). Nothing is timed and nothing is concurrent: a collective is a plan over
the fabric, and its cost is computed.*

| # | Stage | The mechanism | The mistake it makes visible |
|---|---|---|---|
| 1 | The link and the fabric | `Link`, `Topology`, `LinkCost`, the ring a topology suggests | A cost model that charges per message instead of per byte plus per hop |
| 2 | Broadcast | Ring and binomial tree broadcast | A tree that sends to every child in turn |
| 3 | Reduce | Ring reduce to a root | The root's accumulator aliasing a rank's buffer |
| 4 | All-reduce, ring | Reduce-scatter then all-gather, chunked, pipelined | Sending the whole buffer per rank per step |
| 5 | All-reduce, tree and doubling | Recursive doubling/halving, and the size where it wins | A tree whose per-rank bytes are `S`, not `2S·log N` |
| 6 | All-gather / reduce-scatter | The two halves as first-class collectives | A reduce-scatter that leaves the last chunk unreduced |
| 7 | All-to-all | Even and uneven splits, the transpose | A plan that assumes every pair exchanges the same amount |
| 8 | Send/recv and groups | Point-to-point with completions, and group semantics | A group that is a sequence of messages, not one launch |
| 9 | Choosing an algorithm | Ring vs tree vs SHARP by message size, with the lower bound | A heuristic that never picks the tree for small messages |
| 10 | One step, end to end | A training step's collectives, the overlap model, the step time | Comms added to compute instead of `max(compute, comms)` |

### H1 `distributed-training-from-scratch` — the plans on top

*After I9. Provided: `model.py` — a deterministic transformer shape calculus
(parameters, FLOPs, activation bytes, per-layer tensors) and the fabric from I9.
The student authors the parallelisation plans, their per-step byte counts and
their memory ledgers, against the invariant that **every plan must produce the
reference single-device training semantics** — one model, many devices, the same
math.*

| # | Stage | The mechanism | The mistake it makes visible |
|---|---|---|---|
| 1 | The shapes and the ledger | `ModelShape`, `plan_bytes`, `plan_memory` | Counting params but not optimizer state |
| 2 | Data parallel | Gradient all-reduce, the bucket schedule, the overlap | Comms summed with compute instead of hidden behind it |
| 3 | ZeRO-1 / ZeRO-2 | Sharding the optimizer state, then the gradients | A shard count that divides the world but not the state |
| 4 | ZeRO-3 / FSDP | All-gather per layer, reduce-scatter per layer, the wrap policy | All-gathering the whole model instead of one layer |
| 5 | Tensor parallel | `f`/`g` operators, the two all-reduces per block | One all-reduce per block, so the forward pass is wrong |
| 6 | Pipeline parallel | GPipe vs 1F1B, the micro-batch schedule as data | A bubble formula that ignores the micro-batches |
| 7 | Pipeline schedules | Interleaved/virtual stages, activation memory in flight | A schedule that reuses a buffer still in flight |
| 8 | Expert parallel | The two all-to-alls, capacity factor, balance loss | An unbalanced exchange charged as if even |
| 9 | Sequence/context parallel | Ring attention, the KV exchange, online softmax | A ring that recomputes attention instead of accumulating |
| 10 | The configuration | Choose the plan for `(N GPUs, interconnect, model)` and report step time and memory | An axis chosen by fashion instead of by the bytes |

Both courses follow the house shape: ten graded stages, `fleet`-style provided
simulators, `DESIGN DECISION` docstrings, a check per stage with 30+ planted
mutations, and one composed smoke run that landmines `time`.

---

## Part 4 — Where this sits, and the order to do it in

- **I9 comes first**: H1's every stage is a byte count, and I9 is the thing that
  decides what a byte costs. I9 also stands on its own as the multi-node half of
  phase I (it is listed as I7's prerequisite).
- **I7 `distributed-inference-from-scratch`** stays where it is — inference
  parallelism is the same axes with a different objective (latency, not
  throughput), and it should reference I9's fabric rather than re-derive it.
- **H1's slot already exists** as `kind: "legacy"` over a thin
  `distributed-training/` directory; the plan above is what turns it into a
  course, and `path.py`/`ROADMAP.md` now point at this document.
- **Not here, deliberately**: real CUDA kernels, real RDMA verbs, and real
  topology discovery. Those need hardware and belong to `cuda-from-scratch` (G2)
  and to the reader's own cluster. What this pair teaches is the *decision* —
  which failure mode is the one that costs 5×, and how to see it in a byte count.
