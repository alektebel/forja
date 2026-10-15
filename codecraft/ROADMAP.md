# Roadmap

The order to build this repository in, and the review it is based on.
`python3 codecraft/cli.py path` renders this with your live progress.

The order is the one you set: **AWS → LLM internals → RAG → evals + agents → MCP
→ harness → benchmark → eval → the machine stack (GPU, CPU, OS) → agent infra →
the rest.**

---

## The review: every project, by what it needs to be usable

### Ready now — checker-driven, pure Python, `codecraft` runs them as-is

Twenty-five courses, 281 graded checks between them, no dependencies.

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
| `cpu-from-scratch` | 10 | A real datapath on a provided ISA and assembler (`isa.py`): word algebra and the four flags, a decoder that ignores the fields a format does not use, a register file whose zero register cannot be written and whose snapshots are copies, an ALU whose division truncates and whose remainder takes the dividend's sign, byte-addressed memory with alignment and bounds checked before anything is stored, a control unit where a fault is data and a trace records every effect, and then the same programs on a five-stage pipeline that must retire the identical trace — stalls first, then forwarding with the one-cycle load-use stall and a branch flush — measured by CPI. One program, two machines, one result |
| `os-from-scratch` | 10 | An operating system as what you write after the hardware breaks its last promise, on a provided machine (`machine.py`, `devices.py`, `userland.py`): the boot map and the frames a kernel may actually hand out, a bitmap allocator that protects the frame its own bits live in and answers all or nothing, page tables whose entries cannot be confused with frame numbers and whose permission bits are checked on every walk, the fault word a trap carries so a handler decides from data rather than from an exception, a syscall boundary that checks a pointer before it uses it and writes a line with a promise before it acts, the process as a dict with a space, a ledger and a zombie at the end, a scheduler whose pick is priority and age behind a quantum that rotates, two CPUs on an interleaving where the critical section is a lock and its order is checked, a real on-disk filesystem with a superblock written last and a mount that reads only what a barrier made durable, and a capstone userland whose kernel report is recomputed from its own log and cross-checked against the machine's records |
| `eval-framework-from-scratch` | 10 | The runner under an eval, with the task set, the actors and the clock provided: a suite config that refuses a typo and materialises its defaults into the hashed form, metric plugins resolved before the first call, one record per case with the error taxonomy of a budgeted call, budgets checked before the call, an aggregation whose unit is the case and whose weights travel in the record, a judge session that caches by prompt/answer/reference and asks both orders, canonical records whose bytes two runs share, a gate ordered invalid-run-before-failed-gate with four exit codes, a baseline diff that needs the difference to beat the noise, and a resume that repairs a half-written tail and leaves the log of an uninterrupted run |
| `benchmark-from-scratch` | 10 | The measurement machinery around a provided mus engine: a turn gate where a refusal is data and not a turn, a match loop with as-dealt snapshots and two rails, one ground-truth record per decision taken before the action, the link from an aggression to the answer it got, the strength reference drawn from the hands that could bet, a risk scorecard where a bluff is a weak hand and not a lost bet, an outcome that survives the 40-point vaca reset, Brier/log-loss/AUC/calibration probes with their degenerate cases, the publishability gate and its leaderboard, and the mirrored pair that cancels the seat advantage |
| `queue-and-workers-from-scratch` | 10 | A scheduler as a data structure, not a thread pool, on a provided clock and worker fleet: typed specs that refuse a typo instead of defaulting it, admission that counts running work and refuses with `QueueFull` instead of growing, priority as a total order with the tie that makes two runs differ, the concurrency limit checked before a worker runs, leases that expire and hand the task and the slot back, retries with a growing backoff on the injected clock and dead letters at the attempt budget, the water mark with refuse/shed/block and nothing lost, ageing capped so the interactive tenant survives, a record whose every number is rebuilt from the run's own log, and two runs that print identical bytes |
| `interconnects-from-scratch` | 10 | NCCL's model on a provided fabric (links, four topologies, an executor): a cost model you write yourself — per hop `latency + ceil(bytes / bandwidth)`, a step priced by its slowest transfer, a plan by the sum of its steps — ring and tree broadcast and reduce with the accumulator that travels, the ring all-reduce's `2(N-1)` steps and its chunks, recursive doubling with the one-hop XOR partners it actually needs, all-gather and reduce-scatter composed back into stage 4 transfer for transfer, the all-to-all whose per-destination offsets make the receiver's buffer a transpose, send/recv and group semantics on full-duplex links, choosing an algorithm by ticking every candidate against a per-direction lower bound (SHARP as a plan the executor can run), and one training step's four parallelism axes with the communication hidden behind the compute |
| `distributed-training-from-scratch` | 10 | The plans on top of I9's collectives, with a model handed over: DDP's bucketed all-reduce hidden behind the compute, ZeRO's ladder (`4 + 12/N`, then `2 + 2/N + 12/N`), FSDP's per-unit gather and scatter and its `4P(N−1)/N` peak, tensor parallel's two all-reduces per block, GPipe vs 1F1B and the bubble replayed from the slots, interleaving's `(p−1)/(m·v+p−1)`, the expert all-to-all with its capacity cap, ring attention's exact running pivot, and the configuration whose report is recomputed from the plan it chose |
| `autograd-from-scratch` | 10 | Reverse-mode automatic differentiation over exact rationals, on a provided forward algebra (`exact.py`): the graph and the topological order that visits a diamond once, the local derivatives and the accumulation that makes a node used twice add up, broadcasting and the reduction that hands each operand back its own shape, `matmul`'s two transposed VJPs with the small MLP composed from them, `shared`/`trainable` as a freeze that stops the walk, the seed of a non-scalar output and its explicit collapse, `detach` and the `no_grad` region, the kink at a tie and the left-operand rule, an exact central-difference oracle off by exactly `h²` on a cubic, and the capstone step that learns XOR in eight exact steps and reproduces the reference gradient — no float anywhere |
| `rag-from-scratch` | 9 | Chunking, TF-IDF, exact index, BM25, rank fusion, reranking, citations, tenants |
| `orchestration-from-scratch` | 10 | A big task as a graph of small ones, on a provided clock, a scripted fleet and the raw plans: a subtask and a graph that refuse a typo instead of defaulting it, the edge set and the waves a dependency forces — with a cycle refused by naming its path — a schedule decided by the states rather than by the wave, so a fast node never waits for a slow sibling, the handoff that carries exactly a child's own dependencies' accepted results, each cut to the budget that dependency declared, a reviewer who can reject and a rework that carries the reason and stops at `MAX_REWORK`, one failure that skips its transitive dependents without running them, an effect held behind its approval instead of landing before it, the call a budget cannot pay for refused before it happens, a record of seven kinds and no payload text with a report recomputed from it, and the capstone that runs the whole plan to identical bytes twice |
| `durable-execution-from-scratch` | 10 | A run as a log rather than a process, on a provided disk that loses everything it was not told to sync: the line and the journal that holds it — eight fields, nine kinds, a typo refused by name — the write that was not synced and the sync that makes it a fact, a replay with the half-written tail refused by index and text instead of guessed at, a lease whose deadline is derived from its own line (`claimed_at + ticks`) and whose steal is refused naming both owners, the beat that renames a deadline and the grace that separates *expired* from *dead*, a crash that replays only what the disk would keep and writes the `expire` lines the dead owners' jobs owe, an effect that happens exactly once because its intent is synced before it runs and the world's own `count` decides what a replay owes, a checkpoint beside the append-only journal with a resume that refuses another run's or another plan's log by name, a report whose counters are all recounted from the lines and a caller's total refused when the log contradicts it, and a capstone that kills one worker holding a lease in the middle of the run and still ends on the same states, and the same effects, as the run nobody killed — two death paths, and the log says which one happened |

| `agent-metrics-from-scratch` | 10 | A trace is not a metric: the fleet's twelve-field event and the fields its kind carries, a half-open window that makes a tumbling set a partition and refuses an inclusive end, queue depth as a gauge derived from a state machine over the five kinds and never summed, a percentile as a nearest-rank index over exact integers (no float, no interpolation), latency split into the wait, the service and the retry gap with the identity asserted, tokens and micros summed before they are divided and priced by the pool that ran the task, failure and retry rates that name their own denominators and answer floored basis points, windows whose step may not leave a hole, a report recomputed from the events and cross-checked key by key against the fleet's own count of its own run, and a capstone whose budget is spent by the size of an overshoot and whose alert names the window that spent the last of it |
| `sandbox-capabilities-from-scratch` | 10 | An agent's power as the intersection of declared, granted and affordable, on a world made of data: a capability vocabulary and a per-tool demand that must be a set, a principal's grant whose answer is the missing difference and never a boolean, a path jail that resolves `..` before anything is judged and refuses the sibling root a prefix test would hand over, a network policy of exact `host:port` specs where the port is part of the host's identity, cpu/memory/ticks limits charged all or nothing before the work, secrets that reach the model as a handle, a length and a digest while the leak test knows base64 (padded and stripped), hex (both cases) and the reversed value, an audit line of seven fields always written with a closed reason vocabulary, the six questions — catalogue, grant, jail, host, limit, secret — decided in one order with the line written *before* the act and a denial that reaches the filesystem, the wire, the vault and the meter not at all, a report recomputed from the lines and cross-checked against `VFS.log()`, `Wire.dialled()` and `Vault.reads()` with no denied call allowed in any of them, and a capstone whose answer to "what did it touch" is its audit and not its plan |

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
| `distributed-training`, `ml-in-production`, `ml-inference` | Thin (~210–280 lines). `distributed-training` was the H1 slot and is now **superseded by the built `distributed-training-from-scratch`**; the two-course plan is `DISTRIBUTED.md`, with I9's collectives course as its prerequisite |
| `mlops` | 268 lines, and no `solutions/` at all |
| `spectral-graphs` | 473 lines; numpy |
| `sas-lineage-tool` | Python + SAS fixtures |
| `web-scraping` | **Complete** — zero TODO markers; use it as a reference, not a course |

### Docs-only — a README and nothing to build

`vllm-engine`, `tensorrt-inference`, `sgl-lang`. These need a course authored
from scratch, not just a checker.

### Missing entirely — the half of your list the repo does not have yet

The benchmark, the eval runner, the CPU and the OS are now
`benchmark-from-scratch` (phase F1), `eval-framework-from-scratch` (phase F2),
`cpu-from-scratch` (phase G3) and `os-from-scratch` (phase G4) — the machine
stack's second half, graded on the same rule as its first: the hardware is
provided, and its promises are the thing the course makes you keep.
Phase J's five — the task queue, multi-agent orchestration, durable execution
across a killed worker, the capability sandbox and the fleet's own metrics — are
all built now, from the Agent Infra list kept in `AGENT-INFRA.md`.
No retrieval that checks itself, no prompt/routing ops, no memory engine, no
fine-tuning and no privacy gateway — phase K, below, is those five, from the
interview and build lists kept in `AI-ENGINEER.md`.
No TCP/IP stack, no reactor and no broker — phase L, below, is those three, from
the three C/C++ networking series kept in `NETWORKING.md`. The repo has an
application protocol (legacy `http-server`, `dns-server`) and a modelled
collective (`interconnects-from-scratch`), and has never parsed a wire format
byte by byte.
`rag-from-scratch/` (phase B1), `vector-index-from-scratch/` (phase B2),
`evals-from-scratch/` (phase C1), `agents-from-scratch/` (phase C2),
`mcp-from-scratch/` (phase D1) and `agent-harness-from-scratch` (phase E1) now
exist and are graded. Phase I adds eleven
more "to author" lines: the inference spine below names the artifact each stage
builds on, and the SIROM/MUS benchmark work in phase F is its last stage.

---

## What this repo has never built — six registered rows (G7, G8, H5, H6, H7, L4)

Six rows came out of reviewing the corpus by subject rather than by project: each
is the artefact its own field is normally taught from, each is gradeable on the
house rule (a provided world, a ladder of decisions, planted mutations the checks
must catch), and none of them exists here in any form — the repo has never built
a shell, a bytecode runtime, a query engine, a consensus protocol, a compressor
or a git object store. They are registered in `codecraft/path.py`, which is what
`codecraft path` renders.

| Slot | Course to author | The mechanism | After |
|---|---|---|---|
| G7 | `shell-from-scratch` | A line of text becomes a process tree over G4's kernel: word splitting and expansion order, `fork`/`exec`/`wait` with real exit codes, pipes and redirections as a descriptor table built before anything runs, a job table that knows a background job from a stopped one, signals and reaping, and a session the harness replays byte for byte | G4 |
| G8 | `runtime-from-scratch` | A bytecode, an assembler and a heap are given; the runtime is yours: a stack machine with calls, frames and exact step accounting, then mark-sweep, reference counting that cannot free a cycle, a tri-colour incremental collector with write barriers and a remembered set, a nursery, and a copying collector — accepted on a program's output and its collection counts, never on a reachable object being freed | G3, G4 |
| H5 | `query-engine-from-scratch` | A SQL subset parsed, resolved against a catalog that may be wrong, planned (pushdown, join order, an index chosen or refused) and executed with iterators over a page buffer and a B+tree you split yourself — judged by the same rows as the reference for a hundred queries, a plan that earns its index, and a crash schedule where the log decides which tuples exist | G4 |
| H6 | `consensus-from-scratch` | Raft on five nodes, with a deterministic partitioned network, a clock and storage that can lose its last write: terms and votes, a log that matches term by term, commit by majority, a stale leader refused, membership changes, snapshots, and recovery from a lying disk — accepted by a linearizability check over the history the world itself recorded | J3, I9 |
| H7 | `compression-from-scratch` | Huffman with canonical codes, LZ77's window, LZ4's nibble lengths, DEFLATE bit by bit with dynamic trees and the stored/static/dynamic choice, then FSE/ANS and a frame with a real header and checksum — accepted when the provided decoder accepts your bytes, the ratio clears the bar, and the checksum you wrote notices the one bit the tester flips | — |
| L4 | `git-from-scratch` | A `.git` directory real `git` reads: blobs addressed by their own digest, sorted trees with exact modes, commits, refs and a detachable HEAD, an index, a diff that names a hunk, a merge that finds the base and marks conflicts instead of guessing, and a packfile whose delta-compressed objects are reachable through its index — where `git` is on PATH, `git fsck` and `git log` are the judge | G4 |

Two more were considered and left out rather than registered: a regex engine and
a hand-rolled crypto handshake. The first is small enough to be a stage of G5
rather than a course, and the second duplicates the `cryptographic-library`
project the G6 legacy slot already carries.

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
B2, C1, C2, D1, E1, F1, F2, J1, J2, I9 and H1 are built (`rag-from-scratch`,
`vector-index-from-scratch`, `evals-from-scratch`, `agents-from-scratch`,
`mcp-from-scratch`, `agent-harness-from-scratch`, `benchmark-from-scratch`,
`eval-framework-from-scratch`, `cpu-from-scratch`,
`queue-and-workers-from-scratch`, `orchestration-from-scratch`,
`interconnects-from-scratch`,
`distributed-training-from-scratch`), and so is **A8, `autograd-from-scratch`**
— reverse-mode automatic differentiation over exact rationals, the engine every
training course here assumes: ten checks and 504 mutations caught, on a provided
forward algebra (`exact.py`) so every gradient is yours, and nothing in it is a
float, so a gradient is an equal pair and the last stage reproduces a reference
gradient exactly (its frozen plan — the ten stages, the two provided modules,
the mistake catalogue — is in `.h2-dev/CONTRACT.md`). **J2,
`orchestration-from-scratch`**, is built on J1's clock and a scripted fleet: a
big task as a graph of small ones, ten checks and 526 mutations caught, with the
schedule decided by the states rather than by the wave, the handoff cut to the
budget each dependency declared, the reviewer who can reject, the failure that
skips its transitive dependents, the effect held behind its approval, the budget
asked before the call, and a report recomputed from a record that carries no
text (`.j2-dev/CONTRACT.md`). **J3, `durable-execution-from-scratch`**, is built
on a disk that loses everything it was not told to sync: a run as a log, ten
checks and 558 mutations caught, with the lease's deadline derived from its own
line, the grace that separates *expired* from *dead*, a crash that replays only
what the disk would keep and writes the lines the dead owners' jobs owe, an
intent synced before the effect so the effect happens exactly once however often
the run is resumed, a checkpoint whose resume refuses another run's log by name,
a report recounted from the lines, and a capstone that kills one worker holding a
lease mid-run and still ends on the states the run nobody killed reached
(`.j3-dev/CONTRACT.md`). **J4, `sandbox-capabilities-from-scratch`**, is the
same idea one layer out — the sandbox around the call rather than the log under
the run: 10 checks and 494 mutations caught, with the capability a tool demands
intersected against the capability its principal holds so the answer is the
missing difference rather than a boolean, a jail that resolves `..` before
anything is judged and refuses `/home/agent-other` for the sibling root it is, a
host policy where the port is part of the identity, limits charged all or nothing
before the work, a secret that reaches the model as a fingerprint and leaks in
none of four encodings, an audit line with a closed reason vocabulary written
before the act, and a report recomputed from the lines and cross-checked against
the filesystem's, the wire's and the vault's own records
(`.j4-dev/CONTRACT.md`). **J5, `agent-metrics-from-scratch`**, closes the phase:
a trace is not a metric, and the whole course is the distance between them — a
fleet that records twelve fields per event and five kinds, a fold over a window
whose ends decide what is in it, depth as a gauge that is derived and never
summed, a percentile that is an index into sorted samples rather than an
interpolation between two that never happened, latency split into the wait, the
service and the retry gap, tokens and micros summed before they are divided and
priced by the pool, rates that name their own denominators, and a report whose
every number is recomputed from the events and cross-checked against the fleet's
own count of the same run — the one comparison a fold that quietly lost an event
cannot survive (`10 checks and 510 mutations caught`, `.j5-dev/CONTRACT.md`).
**G4, `os-from-scratch`**, is built: an operating system as what you write after
the hardware breaks its last promise, on a provided machine (`machine.py`,
`devices.py`, `userland.py`) — ten checks and 641 mutations caught, from the boot
map's first frame to a capstone that runs the world's own userland on the kernel
you wrote and then asks the only question left, whether the kernel's account of
the run agrees with the machine's key by key, with an audit line whose promise is
written before the act it predicts (`.g4-dev/CONTRACT.md`). The salvage the unit
began as stays beside it as prose: `linux-from-scratch/`, nineteen files and the
fifteen phase directories of
`origin/claude/linux-from-scratch-curriculum-2qokjd`, whose 176 exercises are the
reading and whose ten stages here are the writing. The next unit is **L1,
`tcp-ip-from-scratch`** — the stack as data against a provided lossy `wire.py` —
and then L2 and L3.

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

## The inference spine (phase I) — twelve stages, silicon to serving

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

The honest sequence: I1–I2 before I3 (the cost model is what makes a scheduler
decision checkable), I9 before I7 (you cannot shard without knowing what a link
costs), and I4/I5 before I11 (a gateway routes to what exists). Everything else is
parallel.

---

## Agent infrastructure (phase J) — a twelve-item list, as five courses

`AGENT-INFRA.md` keeps a skill list for Agent Infra — the infrastructure an agent
runs *on*, as opposed to the model or the prompt. Twelve items. Four of them this
repo already teaches end to end: the runtime loop (`agents-from-scratch`), retries
with idempotent effects (that course plus `agent-harness-from-scratch`), the tool
and MCP layer (`mcp-from-scratch`), and evaluation with replay
(`evals-from-scratch` + `eval-framework-from-scratch`). Six more it reaches in
part: context and state, checkpointing, distributed state, the filesystem sandbox,
permissions, and traces. The five below were the parts nothing here touched at
at all; J1, J2 and J3 are now built and graded, and the two that follow are in
the order they build on each other:

| Slot | Course | The mechanism | After |
|---|---|---|---|
| J1 | **built** — `queue-and-workers-from-scratch` (10 checks) | Concurrency limits, priority, backpressure and a worker pool — deterministic and in-process, with the clock injected, so the scheduler is a data structure and not a thread pool | C2, A7 |
| J2 | **built** — `orchestration-from-scratch` (10 checks, 526 mutations caught) | A DAG of subtasks, a reviewer that can reject, a handoff that must carry its own context, and a human-in-the-loop that stops before the effect instead of after it — scheduled by the states rather than by the wave, with the record of seven kinds and no payload text that the capstone's report is recomputed from | J1, C2 |
| J3 | **built** — `durable-execution-from-scratch` (10 checks, 558 mutations caught) | A run as a log rather than a process: the line and the journal, the sync that makes a write a fact, replay with the half-written tail refused, a lease derived from its own line, the heartbeat and the grace, a crash that replays only what the disk would keep, an effect that happens exactly once because its intent is synced first, a checkpoint and a resume that refuses another run's log, a report recounted from the lines, and a capstone that kills one worker holding a lease mid-run and still ends on the same states | J1 |
| J4 | **built** — `sandbox-capabilities-from-scratch` (10 checks, 494 mutations caught) | Capability sets per tool that refuse a demand the vocabulary does not have, a grant whose answer is the missing difference, a jail that resolves before it decides and refuses the sibling root a prefix test hands over, a network policy of exact `host:port` specs, limits charged all or nothing before the work, secrets that travel as a fingerprint and leak in none of four encodings, an audit line written before the act with a closed reason vocabulary, and a report cross-checked against the filesystem's, the wire's and the vault's own records | C2, D1 |
| J5 | **built** — `agent-metrics-from-scratch` (10 checks, 510 mutations caught) | A trace as the input and a metric as the fold: the event and the fields its kind carries, a half-open window that partitions a tumbling set, depth as a derived gauge, nearest-rank percentiles over exact integers, latency split into the wait, the service and the retry gap, tokens and micros summed before the division, rates with named denominators, and a report recomputed from the events and cross-checked against the fleet's own count | J1, A7 |

All five follow the shape of every authored course here: a provided simulator,
ten graded stages, DESIGN DECISION docstrings, and a check per stage with planted
mutations behind it. None of them needs a network, a real server or a thread: the
whole point is that a queue, a lease and a percentile are data structures whose
failures are reproducible, which is what makes them checkable at all.

---

## Applied AI engineering (phase K) — two lists, as five courses

Two more lists arrived from the user and are kept verbatim in `AI-ENGINEER.md`:
**25 interview problems** (design a RAG system for 10M documents; your RAG gives
wrong answers — debug it; cut LLM cost 70%; block prompt injection in a
tool-using agent; …) and **15 things to build** (dynamic context assembler,
durable state machine workflow, raw MCP server, triage router, self-correcting
RAG, 3-tier memory, trajectory CI gate, PII gateway, …). That file maps every one
of the 40 items to what already exists here — most of them are covered or partly
covered by phases B, C, D, E and J — and collects what is not.

Five gaps survived the mapping, and they are the five K slots. All of them are
authorable in the house style (a provided simulator, ten graded stages, a check
per stage, mutations behind every check), and none of them needs a server, a
network or a thread:

| Slot | Course to author | The mechanism | After |
|---|---|---|---|
| K1 | `agentic-retrieval-from-scratch` | Retrieval that checks itself: critique the results, rewrite an ambiguous query, decide grounded-or-abstain, and price each decision against the naive retrieve-and-answer — with contract-shaped chunking (clauses, cross-references) as a fixture | B1, B2, C2 |
| K2 | `prompt-ops-from-scratch` | A prompt and a model choice as versioned artifacts: a typed triage router with a measured escalation rate, shadow mode mirroring a fraction of traffic and diffing trajectories and costs, a rollout/rollback gate, the cost kill-switch, and the degradation chain frontier → mid → local → cache | E1, F2, J1 |
| K3 | `memory-engine-from-scratch` | The three tiers as data structures: a working scratchpad with a hard budget, episodic summaries with a consolidation rule, a semantic store with importance scoring and eviction, and recall measured over a long conversation | E1, B2 |
| K4 | `fine-tuning-from-scratch` | LoRA and preference tuning over A8's exact engine: the low-rank update and why it trains, a 5K-example budget that refuses a plan it cannot pay for, DPO pairs built from recorded failures, and fine-tune-vs-RAG-vs-prompting defended against a number | A8, C1 |
| K5 | `agent-privacy-from-scratch` | What leaves the process and what may come back: tokenize sensitive values before the context window and restore them after, an audit line that answers "what did it touch", per-agent least privilege, and one agent's output sanitized before it becomes another's input | C2, D1, J2 |

Three of the 40 items deliberately have **no slot**, and `AI-ENGINEER.md` says
why for each: serving at scale and 1M-user chat are systems exercises the repo
already decomposes (phase I, `system-design`, the docs-only serving trio), and
voice interruption and computer-use fallback are interface courses that would
need a timeline and a DOM model — real gaps, not yet promises.

---

## Programs that talk (phase L) — three series, as three courses

A third list arrived from the user: three C/C++ networking series — a TCP/IP
stack built part by part, four ways to write a concurrent server, and an MQTT
broker — kept verbatim in `NETWORKING.md`. That file maps each series to what is
already here and collects what is not. The short version: the repo has
application protocols in C (legacy `http-server`, `dns-server`), a protocol-design
slot (`communication-protocols`), a modelled collective (`interconnects-from-
scratch`) and a house method for making a world out of data (`queue-and-workers`,
`durable-execution`, `sandbox-capabilities`); it has never built the layer under
all of them.

Three gaps survived the mapping, and they are the three L slots. All three are
authorable in the house style, and none of them needs a socket or a thread — the
link, the clock and the failure are data, which is what makes the interesting
question answerable (which segment was retransmitted, how many scheduler steps a
model took) instead of a matter of timing:

| Slot | Course to author | The mechanism | After |
|---|---|---|---|
| L1 | `tcp-ip-from-scratch` | The stack as data against a provided lossy `wire.py`: the frame and its type field, ARP and an ageing cache, IPv4 with a routing table and a TTL that has to be decremented, ICMP and a recomputed checksum, the handshake as a state machine, the sliding window, the socket API as a table, retransmission on the injected clock, the close with `TIME_WAIT` as a state, and a session whose tie-breaker is the wire's own segment log | G3, J4 |
| L2 | `concurrent-servers-from-scratch` | Four models for one server over a provided in-memory `link.py`: blocking, thread-per-connection on J1's scheduler with the interleaving the check chooses, a reactor whose readiness is a set, the event loop and its timer queue, callbacks as a handle table, futures and `async`/`await` as a desugaring, backpressure and head-of-line blocking, the Redis case study as a command loop, and one workload through all four with identical answers and a counted number of scheduler steps | J1, J3 |
| L3 | `mqtt-broker-from-scratch` | The wire format itself: the fixed header and its variable-length integer, CONNECT and the session flags, a topic trie where `+` and `#` are matched by components and never by prefix string, QoS 1 as state, QoS 2 as a four-way handshake, retained messages and the last will, a session that survives a reconnect, and a trace replayed twice byte-identically with every frame accepted by the course's own reader | L1, J4 |

`L4 git-from-scratch` joined the phase later, from the review of what this repo
has never built; its row is in *What this repo has never built*, above.

What has no slot: the blog posts (the links are the source, not the course), the C
implementations (the house authors Python; the C versions are what the legacy
slots are for) and the MQTT *client*, which is the broker's protocol seen from the
other side and so is a stage of L3 rather than a course of its own.

---

## Interconnects and distributed training (I9, H1) — the plan in two courses

NCCL is where a training step's wall clock is decided and where it is hardest to
see: ring and tree all-reduce, the protocols, the topology, and the arithmetic
that picks between them. `DISTRIBUTED.md` is the worked-out plan for the two
slots the roadmap already carries.

| Slot | Course to author | The mechanism | After |
|---|---|---|---|
| I9 | **built** — `interconnects-from-scratch` (10 checks) | A provided fabric (links with bandwidth and latency, a topology) and the collectives authored over it: ring reduce-scatter + all-gather with the `2S(N−1)/N` accounting, recursive doubling and trees (and the one-hop partners doubling really needs), all-to-all, send/recv with group semantics, the lower bound that picks an algorithm — and one training step's collectives over four parallelism axes, with comms hidden behind compute as a max | G3, J1 |
| H1 | **built** — `distributed-training-from-scratch` (10 checks, 554 mutations caught) | The plans on top: DDP's bucketed gradient all-reduce, ZeRO-1/2/3 and FSDP, tensor parallel's two all-reduces per block, pipeline bubbles (GPipe vs 1F1B), expert all-to-all, ring attention, and the memory ledger per rank — every axis chosen by bytes per step against the interconnect | I9 |

I9 is built, and it is the floor H1 stands on: every H1 stage is a byte count,
and I9 decides what a byte costs. Both are deterministic and offline in the
house style — no GPU, no network, no `time` — and I7
(`distributed-inference-from-scratch`) is the same
axes with latency instead of throughput, so it should reference I9's fabric
rather than re-deriving it.

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
