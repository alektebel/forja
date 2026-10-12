# Roadmap

The order to build this repository in, and the review it is based on.
`python3 codecraft/cli.py path` renders this with your live progress.

The order is the one you set: **AWS → LLM internals → RAG → evals + agents → MCP
→ harness → benchmark → eval → the machine stack (GPU, CPU, OS) → the rest.**

---

## The review: every project, by what it needs to be usable

### Ready now — checker-driven, pure Python, `codecraft` runs them as-is

Fifteen courses, 181 graded checks between them, no dependencies.

| Course | Checks | What it teaches |
|---|---|---|
| `aws-from-scratch` | 18 | IAM, S3, SQS, DynamoDB, Lambda, SNS, KMS, VPC + capstone |
| `dynamo-paper` | 17 | Consistent hashing, vector clocks, quorums, hinted handoff, Merkle, gossip |
| `context-caching` | 16 | KV cache, prefix/radix caching, paged KV + copy-on-write, routing |
| `contextcite` | 14 | Context attribution by ablation + LASSO; the eval-flavoured one |
| `llm-from-scratch` | 13 | BPE, attention, sampling, KV cache, RoPE |
| `compiler-and-vgpu` | 12 | ISA, assembler, front end, register allocation, SIMT divergence |
| `deploy-and-debug` | 12 | Capacity math, percentiles, SLOs, fault diagnosis, rollout |
| `evals-from-scratch` | 10 | Group-wise splits, EM/F1, nDCG, judge bias, kappa, paired significance, Holm, the gate |
| `agents-from-scratch` | 10 | The tool loop and its transcript, tool schemas, errors as observations, parsing a reply, retries + idempotent effects, turn-aware memory, a path sandbox, an approval gate, budgets, a state-based audit |
| `mcp-from-scratch` | 10 | The JSON-RPC envelope and its codes, stdio/SSE/HTTP framing, the handshake and derived capabilities, tools with the protocol/execution error split, resources and prompts, subscriptions/progress/cancellation, read-only first, idempotency keys, a diff-bound confirmation, the trajectory policy and the audit line (spec 2025-06-18) |
| `agent-harness-from-scratch` | 10 | The runtime under an agent with the model as a callable: collect an event stream into one turn, a prompt budget recomputed from the bytes, the loop where a spent budget is an outcome, dispatch where an unknown tool is a message, streaming with TTFT and inter-token timings, retries that stop before anything is forwarded, compaction that summarizes the middle, a trace of six keys and no payloads, a process reward grounded in the previous result, and a verifier plus a self-generated data loop measured on held-out tasks |
| `vector-index-from-scratch` | 10 | Exact scan, the metric, k-means, IVF, the frontier, HNSW, deletions, int8 |
| `eval-framework-from-scratch` | 10 | The runner under an eval, with the task set, the actors and the clock provided: a suite config that refuses a typo and materialises its defaults into the hashed form, metric plugins resolved before the first call, one record per case with the error taxonomy of a budgeted call, budgets checked before the call, an aggregation whose unit is the case and whose weights travel in the record, a judge session that caches by prompt/answer/reference and asks both orders, canonical records whose bytes two runs share, a gate ordered invalid-run-before-failed-gate with four exit codes, a baseline diff that needs the difference to beat the noise, and a resume that repairs a half-written tail and leaves the log of an uninterrupted run |
| `benchmark-from-scratch` | 10 | The measurement machinery around a provided mus engine: a turn gate where a refusal is data and not a turn, a match loop with as-dealt snapshots and two rails, one ground-truth record per decision taken before the action, the link from an aggression to the answer it got, the strength reference drawn from the hands that could bet, a risk scorecard where a bluff is a weak hand and not a lost bet, an outcome that survives the 40-point vaca reset, Brier/log-loss/AUC/calibration probes with their degenerate cases, the publishability gate and its leaderboard, and the mirrored pair that cancels the seat advantage |
| `rag-from-scratch` | 9 | Chunking, TF-IDF, exact index, BM25, rank fusion, reranking, citations, tenants |

### Legacy — templates and solutions, but no checker (needs a `course.py`)

These are real and mostly substantial; they cannot join `codecraft` until they
have graded checks. An authored `course.py` can wrap a C/CUDA/Haskell project
just as well as a Python one — its check functions may shell out to `make`.

| Project | Notes |
|---|---|
| `system-design` | 6,000 lines, pure Python, 528 TODO markers. The big one. |
| `quantitative-trading` | 5,400 lines; numpy / pandas / scipy / sklearn |
| `world-models` | 10,500 lines of PyTorch across five papers |
| `lean-proofs` | 6,400 lines, 658 `sorry`s — the deepest single project here |
| `haskell-projects` | 3,600 lines |
| `c-compiler` | C; lexer, parser, semantic, codegen, optimizer + tests |
| `bash-from-scratch`, `http-server`, `dns-server`, `firewall-from-scratch`, `toralizer` | C systems projects |
| `communication-protocols`, `cryptographic-library`, `quantum-computing-lang` | C |
| `cuda-from-scratch` | 14 `.cu` files; needs a GPU |
| `diffusion-models`, `deepfake-creation`, `deepfake-detection` | PyTorch |
| `distributed-training`, `ml-in-production`, `ml-inference` | Thin (~210–280 lines) |
| `mlops` | 268 lines, and no `solutions/` at all |
| `spectral-graphs` | 473 lines; numpy |
| `sas-lineage-tool` | Python + SAS fixtures |
| `web-scraping` | **Complete** — zero TODO markers; use it as a reference, not a course |

### Docs-only — a README and nothing to build

`vllm-engine`, `tensorrt-inference`, `sgl-lang`. These need a course authored
from scratch, not just a checker.

### Missing entirely — the half of your list the repo does not have yet

No `CPU` or `OS`; the benchmark and the eval runner are now
`benchmark-from-scratch` (phase F1) and `eval-framework-from-scratch` (phase F2).
`rag-from-scratch/` (phase B1), `vector-index-from-scratch/` (phase B2),
`evals-from-scratch/` (phase C1), `agents-from-scratch/` (phase C2),
`mcp-from-scratch/` (phase D1) and `agent-harness-from-scratch` (phase E1) now
exist and are graded. Phase I adds thirteen
more "to author" lines: the inference spine below names the artifact each stage
builds on, and the SIROM/MUS benchmark work in phase F is its last stage.

---

## Do you need anything before AWS?

**No.** `aws-from-scratch` is self-contained: pure Python, no dependencies, and
its first section (`iam.py`) is the intended entry point — everything else gates
on it. Start there.

Three adjacent courses deepen it later, and none block it:

- `system-design` — queues, idempotency, caching. Makes `sqs.py` and
  `dynamodb.py` click.
- `dynamo-paper` — the paper behind DynamoDB: quorums and partitioning in depth.
- `deploy-and-debug` — capacity and failure, the operational half.

---

## Saving what other branches already did

Substantial material exists outside `main`. Before authoring the missing
courses, cherry-pick these — do not re-invent them:

| Branch | What to port |
|---|---|
| `claude/enterprise-ai-project-guides` | `enterprise-ai-projects/` — **12 implementation guides**, including `02-multitenant-rag.md`, `10-mcp-legacy-erp.md`, `11-shadow-evaluator.md`. Guides, not code: exactly the source material for phases B, C, D. |
| `claude/curriculum-and-repo-index` | `curriculum/` — six course blocks plus `REPO-MAP.md`, which maps all 34 directories and says which no course covers. |
| `claude/weekly-repo-layout` | `ROADMAP.md` (an 18-week plan with three tracks), `progress.py`, `REMAINING.md`, and the week-01.. folders. |
| `claude/rl-posttraining-llm-exercises-wzfe8w` | `rl-posttraining-llm/` — GRPO, rewards, an agent loop (phase 5), and `test_harness.py`. Source material for agents and the harness. |
| `claude/linux-from-scratch-curriculum-2qokjd` | `linux-from-scratch/` — the OS course for phase G. |

---

## How to begin

```bash
python3 codecraft/cli.py path                 # the plan, with progress
python3 codecraft/cli.py run aws-from-scratch # stage 1: iam.py
```

Work one stage at a time; the coach and the mentor handle the rest. Phases B1,
B2, C1, C2, D1, E1, F1 and F2 are built (`rag-from-scratch`,
`vector-index-from-scratch`, `evals-from-scratch`, `agents-from-scratch`,
`mcp-from-scratch`, `agent-harness-from-scratch`, `benchmark-from-scratch`,
`eval-framework-from-scratch`); the
next course to author is phase G3, the CPU: a real datapath — decoder, register
file, ALU, control unit, memory and pipelining — simulated and tested, which the
repo does not have at all.

```bash
python3 codecraft/cli.py new cpu-from-scratch \
    --title "CPU From Scratch" --stages 10
```

F1 was a salvage, and it landed: `~/Desarrollo/mus-benchmark` had the turn-gated
engine, the per-decision JSONL record, the scorecards and the calibration probes,
and `benchmark-from-scratch` is the graded machinery around them — a turn gate
where a refusal is data, a loop with as-dealt snapshots and two rails, one
ground-truth record per decision taken before the action, the aggression link,
the strength reference drawn from the hands that could bet, the bluff that is a
weak hand and not a lost bet, the outcome that survives the vaca reset, the four
read probes, the publishability gate, and the mirrored pair — one mistake per
stage, each one an error the reference repo made and fixed. E1's
`agent-harness-from-scratch` is where
`agents-from-scratch`'s loop, `mcp-from-scratch`'s transports and the harness
material on the `claude/rl-posttraining-llm-exercises-wzfe8w` branch met:
context assembly and compaction, streaming, dispatch, tracing.

A course is its tests — write the check that catches the mistake that is easy to
make and hard to notice. The enterprise RAG guide tells you which mistakes those
are (the `FORCE ROW LEVEL SECURITY` line everyone forgets, embeddings not being
de-identified, recall vs. latency) — and `vector-index-from-scratch` (sixteen
planted mistakes) and `evals-from-scratch` (thirty-four) are the worked examples
of the standard: every check catches the stage's own characteristic error.

---

## The inference spine (phase I) — fourteen stages, silicon to serving

The serving track, in order. Each stage is a real piece of infrastructure
knowledge; each one is graded the way the rest of this repo grades — by the
mistake it catches, offline and deterministic — and each one carries a **runbook**
for the hardware run, the way `deploy-and-debug` carries the real
`vllm`/`nvidia-smi`/`kubectl` commands. The rule throughout: the *check* grades the
mechanism, the *runbook* tells you how to see it on a real GPU. A stage that needs
a cluster to be graded is a stage that will never be graded.

| Stage | Repo artifact | State |
|---|---|---|
| I1 Systems & GPU foundations | `compiler-and-vgpu` (G1) + `gpu-architecture-from-scratch` | G1 ready; the memory hierarchy is to author |
| I2 Transformer inference physics | `inference-physics-from-scratch` (+ A2's KV math) | to author |
| I3 Serving engines & batching | `vllm-engine` (README-only on main), A3's paged KV | to author |
| I4 KV-cache & memory optimization | `context-caching` (A3) + `kv-cache-ops` | A3 ready; the rest to author |
| I5 Quantization & compression | `quantization-from-scratch`, `tensorrt-inference` (README-only) | to author / salvage |
| I6 Kernel-level engineering | `kernels-from-scratch`, `sgl-lang` (README-only) | to author |
| I7 Distributed inference & parallelism | `distributed-inference-from-scratch` | to author |
| I8 Speculative decoding | `speculative-decoding-from-scratch` | to author |
| I9 Multi-node & interconnects | `interconnects-from-scratch` | to author |
| I10 Cluster orchestration & GPU scheduling | `gpu-scheduling-from-scratch` (+ A7) | to author |
| I11 AI gateways, routing & observability | `ai-gateway-from-scratch` (+ A3's routing, A7's percentiles) | to author |
| I12 Public benchmarks & teardowns | `inference-benchmark-from-scratch` (+ F1/F2) | to author |
| I13 Fault tolerance & recovery | `inference-resilience-from-scratch` (+ A7's faults, A3's KV) | to author |
| I14 Weight loading & cold start | `weight-loading-from-scratch` (+ I1's bandwidths) | to author |

The stages, verbatim as they were set out, with what the offline course does about
each:

**Stage 1 — Systems & GPU Foundations.**
*Learn:* C++, Rust, CUDA memory hierarchy, PCIe vs NVLink, thread blocks and warp
scheduling. *Practice:* write a custom CUDA kernel for matrix multiplication from
scratch and profile it against cuBLAS. *Why:* you cannot optimize what you do not
understand at the silicon level.
→ `compiler-and-vgpu` (G1) already grades the ISA, register allocation and SIMT
divergence in pure Python. The missing course adds the memory hierarchy itself —
banks, coalescing, L2/TLB, host↔device and PCIe vs NVLink bandwidth — as a
simulator with a roofline, so the matmul kernel's *predicted* time can be checked
against its measured time; the CUDA/cuBLAS profile is the runbook, and both C++ and
Rust get one compiled kernel each so the toolchain stops being the excuse.

**Stage 2 — Transformer Inference Physics.**
*Learn:* prefill vs decode phases, arithmetic intensity, memory bandwidth
bottlenecks, KV-cache math. *Practice:* profile a HuggingFace model with Nsight
Systems to find the exact memory bottleneck during generation. *Why:* LLM inference
is almost always memory-bound, not compute-bound.
→ `inference-physics-from-scratch`: a cost model that predicts TTFT and ITL from
the config alone (parameters, batch, context, dtype, bandwidth), and a check that
fails when the model's prediction and a measured trace disagree. The Nsight run is
the runbook; the arithmetic is the graded part.

**Stage 3 — Modern Serving Engines & Batching.**
*Learn:* vLLM, SGLang, PagedAttention, continuous batching, chunked prefill.
*Practice:* deploy a 70B model and tune chunk sizes to maximise throughput without
starving decode requests during long-context prefills. *Why:* naive batching leaves
60% of GPU VRAM wasted; PagedAttention fixes this.
→ A3 already builds paged KV with copy-on-write and eviction. This course authors
the scheduler around it: admission, mixing prefill and decode tokens, chunk sizing,
the starvation curve a throughput number hides, and the VRAM accounting that makes
"60% wasted" a number the check can reproduce. `vllm-engine/` on main is README-only
and becomes this course's documentation half.

**Stage 4 — KV-Cache & Memory Optimization.**
*Learn:* prefix caching, KV quantization, CPU offloading, multi-turn cache reuse.
*Practice:* build a routing proxy that directs requests with identical system
prompts to the same replica to share KV blocks. *Why:* reused cache is free speed —
it can cut TTFT by 80%.
→ A3 grades prefix sharing, radix reuse, eviction, semantic routing and the proxy
idea (16 checks). What is missing is KV *quantization* (per-head scales, the
quality/VRAM curve), CPU offload with a transfer budget, and cache reuse across
sessions; those go into `kv-cache-ops`.

**Stage 5 — Quantization & Compression.**
*Learn:* FP8, INT4, AWQ, GPTQ, sparsity, TensorRT-LLM calibration. *Practice:*
serve a model in FP8 vs FP16 and benchmark the exact perplexity drop against the
latency and VRAM gains. *Why:* quantization is the only way to fit frontier models
on edge GPUs and protect your margins.
→ `quantization-from-scratch`: scales and zero points, per-tensor vs per-channel vs
group-wise, KL-divergence calibration, activation-aware weighting, and the
quality/compression/latency trade-off measured on a tiny model — the "perplexity
drop" becomes a graded number instead of a vendor chart. `tensorrt-inference/`
(README-only) supplies the calibration half.

**Stage 6 — Kernel-Level Engineering.**
*Learn:* Triton, FlashAttention, CUDA graphs, operator fusion. *Practice:* write a
fused Triton kernel for RMSNorm or Softmax and benchmark it against native
PyTorch. *Why:* Python overhead kills inference; fused kernels save milliseconds
that compound at scale.
→ `kernels-from-scratch`: tiling and online softmax by hand in Python (so the
algorithm is not hidden behind a framework), then a small Triton-shaped IR with a
fusion pass and a launch-overhead model. The check: the fused path is bit-identical
to the reference and measurably cheaper in the model's own counters. `sgl-lang/`
(README-only) is the DSL half.

**Stage 7 — Distributed Inference & Parallelism.**
*Learn:* tensor parallelism, pipeline parallelism, expert parallelism for MoE.
*Practice:* shard a 405B model across 8 nodes and measure the communication
overhead. *Why:* single-GPU inference is dead for frontier models; you must master
the shard.
→ `distributed-inference-from-scratch`: cut one model across N simulated ranks
(row/column/tensor, layer/pipeline, expert/MoE), schedule the pipeline stages,
dispatch the experts, and measure the communication volume on a modelled
interconnect from I9. The 8-node run is the runbook; the sharding arithmetic and
the comms/ compute overlap are the checks.

**Stage 8 — Speculative Decoding.**
*Learn:* draft-target models, Medusa heads, acceptance rates, n-gram drafting.
*Practice:* build a pipeline where a local 3B model drafts tokens for a cloud 70B
model to verify in parallel. *Why:* 2x decode speed at zero quality cost is the
closest thing to a free lunch in inference.
→ `speculative-decoding-from-scratch`: the draft/verify loop with a scripted draft
model, the acceptance-rate math, rejection sampling that provably preserves the
target distribution, tree attention for Medusa-style heads, and the KV bookkeeping
that makes rejection cheap. "2x at zero quality cost" becomes a distribution check,
not a claim.

**Stage 9 — Multi-Node & Hardware Interconnects.**
*Learn:* NCCL, RDMA, InfiniBand, NVLink, disaggregated prefill/decode. *Practice:*
set up a multi-node cluster and profile network latency of tensor parallelism
across nodes vs within a node. *Why:* network latency is the new GPU bottleneck;
disaggregating prefill and decode is the 2026 meta.
→ `interconnects-from-scratch`: ring and tree all-reduce with a latency/bandwidth
model (the same algorithm NCCL runs), one-sided RDMA semantics with completion
queues, NVLink vs PCIe vs IB as parameterised links, and the disaggregation
scheduler that decides whether moving the prefill pays. It is `aws-from-scratch`'s
networking chapter with a different wire.

**Stage 10 — Cluster Orchestration & GPU Scheduling.**
*Learn:* Kubernetes GPU operators, Ray, Slurm, MIG partitioning, KEDA. *Practice:*
build a queue-based autoscaler that spins up spot GPUs from pending requests and
drains them when empty. *Why:* idle H100s burn $3+/hr; FinOps and scheduling are
core infra responsibilities.
→ `gpu-scheduling-from-scratch`: a scheduler with MIG slices, queue depth,
autoscaling policy, spot preemption and a cost model, graded on the failures that
matter (a drain that kills an in-flight request, an autoscaler that oscillates, a
queue that starves a tenant). `deploy-and-debug` (A7) already grades rollout,
liveness/readiness and budget-based rollback; the Kubernetes/Ray/Slurm specifics
are the runbook.

**Stage 11 — AI Gateways, Routing & Observability.**
*Learn:* TTFT/ITL SLOs, semantic routing, DCGM metrics, OpenTelemetry for LLMs.
*Practice:* build a gateway that routes simple queries to a quantized local model
and complex reasoning to a frontier API based on prompt complexity. *Why:* routing
protects your margins and DCGM metrics tell you when your GPUs are silently
throttling.
→ `ai-gateway-from-scratch`: an SLO in TTFT/ITL, a complexity classifier that
decides the route, cost accounting per request, a percentile pipeline (A7's
percentiles), and a throttling detector that catches the clock drop before the
users do. DCGM and OTel are the runbook; the routing decision and the SLO
arithmetic are graded.

**Stage 12 — Public Benchmarks & Teardowns.**
*Learn:* reproducible methodology, latency/throughput Pareto curves,
cost-per-token analysis. *Practice:* publish a teardown comparing vLLM vs SGLang vs
TensorRT-LLM on your specific hardware with full configs. *Why:* public proof of
hardware mastery gets you hired instantly by top AI labs.
→ `inference-benchmark-from-scratch`: capture the full config or refuse to run,
sweep the knobs, plot the latency/throughput frontier, pin cost per token to a
price and a utilisation, and fail the comparison when two runs differ in a knob
nobody recorded. F1 (`mus-benchmark`) and F2 own the measurement machinery it
reuses, and the `benchmark-methodology` skill is the checklist behind it.

**Stage 13 — Inference Fault Tolerance & Recovery.**
*Build:* a harness that injects network partitions, simulated GPU ECC errors and
OOMs to test the cluster's ability to migrate KV-caches and recover. *Why:* at
scale, hardware fails daily; the architecture must heal itself.
→ `inference-resilience-from-scratch`: a deterministic fault injector over a
simulated cluster (replicas, a router, paged KV from A3), and the recovery paths
graded on what they must never do: a retry that duplicates tokens already streamed
to the client, a KV migration that resumes from a stale block, a drain that drops an
in-flight request, a recovery that hides its cost from the SLO. The choice between
migrating the KV and recomputing the prefill is a cost decision the check
reproduces from bandwidths and context length. `deploy-and-debug` (A7) diagnoses
faults from metrics; this stage acts on them. Real chaos tooling (fault injection
on Kubernetes, `nvidia-smi` ECC counters) is the runbook.

**Stage 14 — Weight Loading & Cold Start.**
*Build:* a system that streams model weights directly from an S3 bucket to GPU VRAM
on cold-start, bypassing local disk. *Why:* cold-start latency kills autoscaling.
→ `weight-loading-from-scratch`: a tensor file format with a header and offsets
(safetensors-shaped), ranged reads in chunks, a bounded pipeline that overlaps
download, host copy and host-to-device transfer, and a cold-start model that
predicts time-to-ready from model size and the bandwidth of each hop. The checks:
the streamed weights are byte-identical to the source, memory stays under the
buffer budget, a failed chunk is retried without corrupting the tensor, and
streaming beats disk-first by the margin the model predicts — no more. I10's
autoscaler consumes this cold-start number. Real S3 + `safetensors` + pinned memory
is the runbook.

The honest sequence: I1–I2 before I3 (the cost model is what makes a scheduler
decision checkable), I9 before I7 (you cannot shard without knowing what a link
costs), I4/I5 before I11 (a gateway routes to what exists), and I4/I10 before I13 (you
cannot recover a KV cache or a replica you have not modelled). Everything else is
parallel.

---

## AWS for real (phase W) and system design on AWS (phase S)

`aws-from-scratch` (A1) teaches the mechanisms offline. Phases W and S are the other
half: the same mechanisms on a real account with **Terraform**, from first account to
the level of **AWS Solutions Architect – Associate (SAA-C03)** and **Machine Learning
Engineer – Associate (MLA-C01)**, plus twelve system design exercises built from the
same blocks. Every project is specified in
[`aws-architect-track/`](../aws-architect-track/) — one directory and one README per
project: goal, what to build, measured acceptance, and the questions to answer before
the first `terraform apply`.

- **W0–W10 (SAA-C03):** account guardrails, CDN, VPC, three-tier HA with caching,
  serverless, containers, streaming, security, multi-account and hybrid networking,
  DR, cost and a Well-Architected review.
- **W11–W16 (MLA-C01):** data lake, SageMaker training with a feature store,
  deployment and inference cost, MLOps pipeline, monitoring and governance, and a
  RAG capstone evaluated with C1.
- **S1–S12:** URL shortener, rate limiter, notifications, news feed, chat, video,
  payments ledger, job scheduler, autocomplete, geo matching, recommendation
  serving and a multi-tenant LLM platform — each a design doc, ADRs, a failure-mode
  table and a cost estimate, with an optional build slice.

What changes from the rest of this repo: **nothing here is graded by `codecraft`.**
The projects run on a real account and cost money, so they carry acceptance criteria
you measure (a failover time, bytes scanned, a message in a DLQ) instead of checks.
`path.py` lists them under two kinds of their own, `real` and `design`. Projects
marked **$$** have a meaningful hourly charge: apply, measure and destroy in the same
session; W0 exists so a mistake costs an email, not a bill.

What it does not claim: passing it is not passing the exams. The projects cover the
architecture; the breadth of the exams is covered better by practice questions.

---

## The MUS benchmark (phase F) — resolved

MUS is the Spanish card game, and `mus-benchmark` is **your own** project
(`~/Desarrollo/mus-benchmark`, GitHub `alektebel/mus-benchmark`): a benchmark
for cooperation between two-player LLM teams, Team A on seats 0 and 2, Team B on
1 and 3, under partial observability.

Its machinery is exactly what phase F is for, and it is unusually well thought
through — worth reimplementing stage by stage rather than reusing:

- a **strict, turn-gated engine** that validates declarations, discards and turn
  order, with a documented rules variant;
- **señs** — private, partner-directed, TTL-expiring gestures on a virtual-time
  kernel, so a gesture made mid-deliberation reaches the partner's next decision
  or fades;
- the insight that a 10-hand match yields **one noisy bit**, so the unit of
  measurement becomes the **decision**, logged one JSONL record at a time with
  the engine's ground truth;
- **scorecards** — aggression, bluff rate, fold-error, payoff — where a bluff is
  defined against the empirical strength distribution for that lance, not
  "bet and lost";
- **calibration probes** (`READ_PROBE`) scored by Brier, log-loss and AUC, with
  the control arm it needs;
- **mirrored seating**, because seats 0+2 carry a measured positional edge;
- and honest limits: short matches and fixed model names do not rank models.

A course that rebuilds those is a course in *measurement*, which is the same
lesson phase C and F2 are after, applied to an adversarial game.

## Other open questions

- **Legacy projects need checkers.** Which to convert first is a policy choice:
  converting underneath the courses you are actually doing beats converting the
  most impressive-sounding project.
