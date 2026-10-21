# Roadmap

The order to build this repository in, and the review it is based on.
`python3 codecraft/cli.py path` renders this with your live progress.

The order is the one you set: **AWS → LLM internals → RAG → evals + agents → MCP
→ harness → benchmark → eval → the machine stack (GPU, CPU, OS) → agent infra →
the rest.**

---

## The review: every project, by what it needs to be usable

### Ready now — checker-driven, pure Python, `codecraft` runs them as-is

Thirty courses, 341 graded checks between them, no dependencies.

| Course | Checks | What it teaches |
|---|---|---|
| `aws-from-scratch` | 18 | IAM, S3, SQS, DynamoDB, Lambda, SNS, KMS, VPC + capstone |
| `dynamo-paper` | 17 | Consistent hashing, vector clocks, quorums, hinted handoff, Merkle, gossip |
| `context-caching` | 16 | KV cache, prefix/radix caching, paged KV + copy-on-write, routing |
| `contextcite` | 14 | Context attribution by ablation + LASSO; the eval-flavoured one |
| `llm-from-scratch` | 13 | BPE, attention, sampling, KV cache, RoPE |
| `compiler-and-vgpu` | 12 | ISA, assembler, front end, register allocation, SIMT divergence |
| `deploy-and-debug` | 12 | Capacity math, percentiles, SLOs, fault diagnosis, rollout |
| `fde-from-scratch` | 12 | Enterprise AI delivery end to end: identity and the row, air-gapped deployment, dirty invoices reconciled into a hybrid store, retrieval that filters before the limit, the ERP as tools with the credential staying in the vault, PII masked out and restored back, a gate a person answers, the model that fits the customer's GPU, the work counted in hours and cents, shadow evals and one verdict, a vague ask scoped to four weeks, a runbook drilled against armed faults |
| `evals-from-scratch` | 10 | Group-wise splits, EM/F1, nDCG, judge bias, kappa, paired significance, Holm, the gate |
| `agents-from-scratch` | 10 | The tool loop and its transcript, tool schemas, errors as observations, parsing a reply, retries + idempotent effects, turn-aware memory, a path sandbox, an approval gate, budgets, a state-based audit |
| `mcp-from-scratch` | 10 | The JSON-RPC envelope and its codes, stdio/SSE/HTTP framing, the handshake and derived capabilities, tools with the protocol/execution error split, resources and prompts, subscriptions/progress/cancellation, read-only first, idempotency keys, a diff-bound confirmation, the trajectory policy and the audit line (spec 2025-06-18) |
| `agent-harness-from-scratch` | 10 | The runtime under an agent with the model as a callable: collect an event stream into one turn, a prompt budget recomputed from the bytes, the loop where a spent budget is an outcome, dispatch where an unknown tool is a message, streaming with TTFT and inter-token timings, retries that stop before anything is forwarded, compaction that summarizes the middle, a trace of six keys and no payloads, a process reward grounded in the previous result, and a verifier plus a self-generated data loop measured on held-out tasks |
| `vector-index-from-scratch` | 10 | Exact scan, the metric, k-means, IVF, the frontier, HNSW, deletions, int8 |
| `mqtt-broker-from-scratch` | 10 | A broker whose every frame its own reader takes back, on a provided byte-pipe transport (`streams.py`) and a provided policy table (`grants.py`): the fixed header and the variable-length integer that says how long the rest is, CONNECT and the session flags, a topic trie where `+` and `#` are matched by components and never by prefix string, SUBSCRIBE and the QoS actually granted, PUBLISH routed to real subscribers and retained for the next one, QoS 1 as state (the packet id, the PUBACK, the deadline that re-sends with DUP), QoS 2 as a four-way handshake whose id may not be reused before PUBCOMP, a session that outlives the socket with its queue and its keep-alive, the last will a cut connection owes, grants and denials written down before the act, and a capstone that runs one scenario twice, re-reads its own trace with the course's own reader, and holds its report against the transport's log key by key |
| `concurrent-servers-from-scratch` | 10 | Four models for one server on a provided in-memory `link.py` whose own log is the tie-breaker: a connection as a state machine over an outbox that has to be counted rather than assumed, a blocking server and the one slow client that starves everybody behind it, threads whose interleaving the *check* chooses (the scheduler is a data structure, and `time`, `threading` and `asyncio` are banned because they are the subject), a reactor whose readiness is a set and whose poll loop never busy-waits, the event loop with a monotonic timer queue, callbacks as a handle table where the cancelled one must not run, futures and `async`/`await` as a desugaring onto the same loop, backpressure as a reply deferred in the connection's own state (`pending`/`offset`, because the outbox's bound is the world's) with head-of-line blocking reported as `stalled`, the Redis case study as a command loop with per-connection state and expiry deadlines on the injected clock, and a capstone that runs one workload through all four models — 148 bytes delivered by each for 42, 54, 19 and 23 steps — and settles a disagreement with the link's own counts rather than with a model's beliefs |
| `cpu-from-scratch` | 10 | A real datapath on a provided ISA and assembler (`isa.py`): word algebra and the four flags, a decoder that ignores the fields a format does not use, a register file whose zero register cannot be written and whose snapshots are copies, an ALU whose division truncates and whose remainder takes the dividend's sign, byte-addressed memory with alignment and bounds checked before anything is stored, a control unit where a fault is data and a trace records every effect, and then the same programs on a five-stage pipeline that must retire the identical trace — stalls first, then forwarding with the one-cycle load-use stall and a branch flush — measured by CPI. One program, two machines, one result |
| `os-from-scratch` | 10 | An operating system as what you write after the hardware breaks its last promise, on a provided machine (`machine.py`, `devices.py`, `userland.py`): the boot map and the frames a kernel may actually hand out, a bitmap allocator that protects the frame its own bits live in and answers all or nothing, page tables whose entries cannot be confused with frame numbers and whose permission bits are checked on every walk, the fault word a trap carries so a handler decides from data rather than from an exception, a syscall boundary that checks a pointer before it uses it and writes a line with a promise before it acts, the process as a dict with a space, a ledger and a zombie at the end, a scheduler whose pick is priority and age behind a quantum that rotates, two CPUs on an interleaving where the critical section is a lock and its order is checked, a real on-disk filesystem with a superblock written last and a mount that reads only what a barrier made durable, and a capstone userland whose kernel report is recomputed from its own log and cross-checked against the machine's records |
| `tcp-ip-from-scratch` | 10 | The stack as data against a provided lossy `wire.py` and five named hosts: the frame and the type field that says what is inside (and the padding a NIC adds, which nobody owns), ARP with a cache that ages and a broadcast that comes back to its sender, IPv4 with a routing table, a TTL decremented on every hop and a checksum recomputed over the header, ICMP echo whose reply carries the request's identifier, the handshake as a state machine you can be wrong about in six places, a sliding window that must not be overrun and a zero-window probe, the socket API as a table of descriptors that owns nothing a descriptor cannot reach, retransmission on the injected clock with a timer that stops only when the acknowledgement is *ahead*, the close as four segments and a state you wait in rather than a sleep, and a capstone that runs one whole session and then argues about it with the wire's own segment log — key by key, and the wire wins |
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
| `infrastructure-from-scratch` | 18 | The building blocks, one module each: URL shortener, consistent hashing, caching (LRU/TTL/aside/stampede), CDN, the four rate limiters, throttling, batching, pooling, stickiness, circuit breaking, queues with DLQ, leaderboards, hot partitions, locality, eventual consistency, idempotency keys, edge computing, capacity math — slot A5, superseding the `system-design/` pile (the 6,000 lines stay as prose material) |

### Legacy — templates and solutions, but no checker (needs a `course.py`)

These are real and mostly substantial; they cannot join `codecraft` until they
have graded checks. An authored `course.py` can wrap a C/CUDA/Haskell project
just as well as a Python one — its check functions may shell out to `make`.

| Project | Notes |
|---|---|
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
interview and build lists kept in `AI-ENGINEER.md`; its sixth slot is a list of its
own, the twelve-stage FDE skill list, built whole as `fde-from-scratch`.
No broker — that gap is closed too: `mqtt-broker-from-scratch` (L3) is the wire
format itself, built byte by byte against the three C/C++ networking series kept
in `NETWORKING.md`. The stack is `tcp-ip-from-scratch`, the reactor is
`concurrent-servers-from-scratch` and the broker is `mqtt-broker-from-scratch` —
thirty stages between them, from the frame up to a session whose tie-breaker is the
wire's own segment log, from one slow client to one workload served four ways with
identical answers, and from a fixed header and a topic trie to a trace replayed
twice byte-identically with every frame accepted by the course's own reader.
The repo has an application protocol
(legacy `http-server`, `dns-server`) and a modelled
collective (`interconnects-from-scratch`), and it parses a wire format byte by
byte in exactly two places: `tcp-ip-from-scratch`'s frames and
`mqtt-broker-from-scratch`'s packets, each of them a reader the course wrote and
each of them held to a writer the same course wrote.
`rag-from-scratch/` (phase B1), `vector-index-from-scratch/` (phase B2),
`evals-from-scratch/` (phase C1), `agents-from-scratch/` (phase C2),
`mcp-from-scratch/` (phase D1) and `agent-harness-from-scratch` (phase E1) now
exist and are graded. Phase I adds the "to author" lines below — the inference
spine names the artifact each stage builds on, and the SIROM/MUS benchmark work
in phase F is its last stage. Nothing here has ever served two regions against each
other either: multi-region failover is registered as H8, and it is A6's data half
joined to H6's agreement half.

**Twelve projects — not slots — are queued in `ENTERPRISE.md`**: the enterprise-AI
list from `claude/enterprise-ai-project-guides` (legacy sync, zero-trust
multi-tenant RAG, a PII redaction proxy, an air-gapped deployer, ROI telemetry, an
idempotent webhook reconciler, an SSO/SCIM bridge, a fallback and degradation
gateway, a compliance auditor, an MCP server for legacy ERPs, a shadow traffic
evaluator and a 3 AM runbook repo). Each row there names the modules this repo
already has for it — 6 already has the reliability core in `system-design/` and
`aws-from-scratch/`, 8 the breaker, 12 the rollout and the faults — and the gap
that remains. They are projects rather than courses: no provided world, no
template, no check, so `path.py` does not carry them, and building one starts by
turning its guide into a contract.

The neighbouring list that was built is not theirs: the twelve-stage FDE skill list
became `fde-from-scratch` (**K6**, phase K) — a provided customer, twelve graded
stages, 884 mutations — and it covers, simulated, the decision space of nine of the
twelve projects above, eight of them whole. `ENTERPRISE.md`'s last section names them
one by one and says which three have a course nowhere.

---

## What this repo has never built — eleven registered rows (G7, G8, G10, G11, G12, G13, G14, H5, H6, H7, L4)

Eleven rows came out of reviewing the corpus by subject rather than by project: each is the
artefact its own field is normally taught from, each is gradeable on the house rule (a
provided world, a ladder of decisions, planted mutations the checks must catch), and
none of them exists here in any form — the repo has never built a shell over a provided
machine (G7 is built now), a bytecode runtime, a query engine, a consensus protocol, a
compressor, a git object store, a bootable OS, a mechanised algorithms book, a database
file format or a regex engine. They are registered in `codecraft/path.py`, which is
what `codecraft path` renders.

| Slot | Course to author | The mechanism | After |
|---|---|---|---|
| G8 | `runtime-from-scratch` | A bytecode, an assembler and a heap are given; the runtime is yours: a stack machine with calls, frames and exact step accounting, then mark-sweep, reference counting that cannot free a cycle, a tri-colour incremental collector with write barriers and a remembered set, a nursery, and a copying collector — accepted on a program's output and its collection counts, never on a reachable object being freed | G3, G4 |
| H5 | `query-engine-from-scratch` | A SQL subset parsed, resolved against a catalog that may be wrong, planned (pushdown, join order, an index chosen or refused) and executed with iterators over a page buffer and a B+tree you split yourself — judged by the same rows as the reference for a hundred queries, a plan that earns its index, and a crash schedule where the log decides which tuples exist | G4 |
| H6 | `consensus-from-scratch` | Raft on five nodes, with a deterministic partitioned network, a clock and storage that can lose its last write: terms and votes, a log that matches term by term, commit by majority, a stale leader refused, membership changes, snapshots, and recovery from a lying disk — accepted by a linearizability check over the history the world itself recorded | J3, I9 |
| H7 | `compression-from-scratch` | Huffman with canonical codes, LZ77's window, LZ4's nibble lengths, DEFLATE bit by bit with dynamic trees and the stored/static/dynamic choice, then FSE/ANS and a frame with a real header and checksum — accepted when the provided decoder accepts your bytes, the ratio clears the bar, and the checksum you wrote notices the one bit the tester flips | — |
| G10 | `custom-os-from-scratch` | The big one: a bootable x86-64 kernel in C and a userland on top, end to end — bootloader handoff, GDT/IDT by hand, PIT and APIC, paging you can inspect in QEMU, interrupts where a keypress becomes a character on your own screen, G4's scheduler context-switching for real, the syscall ring crossing with the pointer validated twice, drivers against the device itself (PS/2's second-byte wait, ATA's polled status register, PCI enumeration, an e1000/virtio ring with a shared interrupt), a real filesystem on a disk image, an ELF loader running a program G5 compiled, fork/exec/wait as code, and G7's shell speaking to your kernel — QEMU the judge where the checker reaches, the real machine the honest one; the graded path is x86-64, the arm64 port the second half | G4, G5 |
| G11 | `advanced-dsa-from-scratch` | La Rocca's *Advanced Algorithms and Data Structures*, one stage per chapter, every structure judged against a work counter and a reference: d-way heaps measured on Dijkstra, treaps with the height profiler, Bloom filters with the measured false-positive rate, disjoint sets counted in finds, tries and autocomplete, LRU/LFU caches, k-d trees and SS-trees checked against the linear scan, DBSCAN/OPTICS, graphs to Dijkstra and MST, embeddings and force-directed drawing with counted crossings, gradient descent, simulated annealing, genetic algorithms on TSP against branch-and-bound | — |
| G12 | `sqlite-from-scratch` | A real single-file database that `sqlite3` itself opens, from the recovered codecrafters corpus (9 stages): header and schema table, table B-trees page by page — cell pointer array, varints, overflow pages, freelist — the record format's serial types, then the WAL and the commit that is not acknowledged before the WAL says so; the judge is sqlite3 reading what you wrote and the row counts matching | G9 |
| G13 | `regex-from-scratch` | The engine built twice: Thompson's construction — shunting yard, NFA, epsilon-closures, linear-time simulation — then the backtracking engine whose catastrophic cases the work counter exposes; classes, anchors, quantifiers, groups, backreferences the NFA refuses; grep (G9) re-derives its -E from this engine, tail's scrollback filter and G7's globs borrow the same compile step; the judge is the match sets agreeing with Python's `re` on a corpus built to distinguish the two engines | — |
| G14 | `reverse-engineering-from-scratch` | Reading a program you have no source for, on binaries you can verify: ELF and PE parsed until `readelf` and yours agree, x86-64 disassembly with the length-decoding problem (prefixes, ModRM, where data is code and back), calling conventions and stack frames from prologues, CFG recovery by linear sweep and recursive descent and where they disagree, the decompiler lift to a C-like IR and what it always gets wrong; then the dynamic half — ptrace attach, breakpoints, memory dumps, the syscall trace that catches the static reading lying; strings, imports, the entropy profile that finds packed sections; capstone: a crackme and a stripped binary from the estate, the licence check found, understood and written up, every claim checked against ground truth the estate carries — objdump, gdb and radare2 the reference outputs your own parser and lifter are checked against | G3, G5 |
| L4 | `git-from-scratch` | A `.git` directory real `git` reads: blobs addressed by their own digest, sorted trees with exact modes, commits, refs and a detachable HEAD, an index, a diff that names a hunk, a merge that finds the base and marks conflicts instead of guessing, and a packfile whose delta-compressed objects are reachable through its index — where `git` is on PATH, `git fsck` and `git log` are the judge | G4 |

One more was considered and left out rather than registered: a hand-rolled crypto
handshake — it duplicates the `cryptographic-library` project the G6 legacy slot
already carries. The regex engine considered here was registered anyway as G13,
with G9's grep as its customer.

---

## G7, `shell-from-scratch` — a shell over a provided machine, in ten stages

**G7, `shell-from-scratch`**, is built: a shell is what a kernel looks like from
the outside, and every promise G4's kernel makes is on show. The world never
changes and the course never writes it: `machine.py` is a deterministic scheduler
with its own filesystem, pipes, process tree and signal delivery
(`machine.machine(7)`); `programs.py` is the ten programs a shell can become, each
with its own step budget; `rules.py` is the policy in data (`POLICY_VERSION =
"shell-policy-1"`); `scripts.py` is eight fixture sessions whose expected records
are the answer key a stage has to reproduce, not read. The ten stages are the
whole pipeline — the lexer that keeps quoting as written and matches operators
longest first; expansion in the order a shell must (parameter, tilde, split, glob,
quote-removal); the descriptor table a pipeline builds before anything runs and
the byte cost the machine prices it at; the process tree of fork-exec-wait with
every child reaped and the status always the last command's; the job table that
keeps background and stopped jobs without waiting; signals and traps, where
`128 + n` is a signal and never a plain status; the builtins that must run in the
shell's own process; lists and short-circuits under the rules of `set -e`; the
session replayed byte for byte against the world's own record; and the audit that
answers *why* a status was the number it was, one reason per step, from the
evidence and never from the answer key — one check per stage, 910 testers and 506
planted mutations caught. Every counter a session reports is the machine's own
delta from a mark, so a session answers for what it did and not for what the
machine already held when it was handed over. The contract is frozen in
`.g7-dev/CONTRACT.md` with ten amendments recorded, each one a reading that a
stage found in the middle of the work and the plan had got wrong.

---

## The AI-infrastructure list — three more registered rows, and where the other twelve live (I13, I14, H8)

A fifteen-item list arrived from outside — *systems that prove you can serve, scale
& keep GPUs honest* — and the useful answer was not yes or no but the row each item
already has, or the row it should have. Twelve of the fifteen were already the
subject of a registered course. Two were covered nowhere. One — the cluster itself
— was scattered across three rows with no row of its own, which is how a serving
stack ends up being nobody's course. Those three are now registered in
`codecraft/path.py`, the file `cz path` and `cz dag` render.

| # | The item | Where it lives |
|---|---|---|
| 1 | Self-hosted inference cluster | **I13 `serving-cluster-from-scratch`** — new: I3 schedules, I7 shards, I10 places, and nothing kept the cluster up, drained it, or published what it saw |
| 2 | Cost-per-token dashboard | I11 (`ai-gateway-from-scratch`: SLO, percentile pipeline, cost accounting) + I12 (cost per token pinned to a price and a utilisation) + A7 (the ops thread) + J5 (a trace is not a metric) |
| 3 | Queue-based GPU autoscaler | I10 — "Kubernetes GPU operators, Ray, Slurm, MIG partitioning, KEDA" and "queue-based autoscaling, spot preemption" are its own thesis |
| 4 | Continuous-batching load test | I3 (continuous batching, chunked prefill, the starvation curve a throughput number hides) + I12 (the methodology) + F1 (the harness) |
| 5 | Model weight delivery | **I14 `weight-delivery-from-scratch`** — new: nothing here treated cold start as a storage problem pretending to be a compute problem |
| 6 | Multi-model AI gateway | I11 (routing, retries, fallbacks) + K2 (versioned prompts and models, shadow mode, the degradation chain, the cost kill-switch) + J1 (admission that refuses rather than grows) |
| 7 | Quantized-serving bakeoff | I5 (`quantization-from-scratch`: scales and zero points, KL calibration, and the quality/latency/VRAM trade-off measured on a tiny model instead of promised) |
| 8 | Secure multi-tenant inference | J4 (capabilities declared, granted and intersected — built) + K5 (what leaves the process and what may come back) + G6's `cryptographic-library` for the keys |
| 9 | Checkpointed distributed training | H1 (DDP, the ZeRO ladder, FSDP — built) + J3 (a run as a log: replay, leases, recovery — built) + I10 for the Ray/Slurm half |
| 10 | Speculative decoding prototype | I8 (the acceptance-rate math, the 2x claim made checkable) + A3/I4 (prefix reuse, paged KV) + I3 (chunked prefill) |
| 11 | GPU partitioning lab | I10 (MIG slices, fair scheduling, spot preemption, the cost model that makes an idle H100 a bug) |
| 12 | Triton / custom kernel path | I6 (tiling and online softmax by hand, a small Triton-shaped IR with a fusion pass, and a check that the fused path is bit-identical) |
| 13 | Observability spine for non-determinism | J5 (kinds, half-open windows, a gauge derived from a state machine — built) + A7 + I11 (DCGM and OTel) + F2 (the error taxonomy) |
| 14 | Multi-region failover drill | **H8 `failover-from-scratch`** — new: A6 owns the data half, H6 the agreement half, and nobody ran the drill |
| 15 | Public benchmark teardown | I12 — "capture the full config, sweep the knobs, plot the frontier, pin cost per token to a price, and fail the run when a config is missing" is verbatim its thesis |

The three new rows, in the same shape as the six above:

| Slot | Course to author | The mechanism | After |
|---|---|---|---|
| I13 | `serving-cluster-from-scratch` | A cluster that stays ready: bring-up order, the liveness/readiness split where readiness means the weights are in VRAM rather than the process is alive, a drain that finishes what it accepted, a rolling upgrade that never drops a request, a retry budget at the edge rather than per call, and the TTFT/ITL report the cluster publishes about itself with the node that failed the drill named | I3, I7, I10 |
| I14 | `weight-delivery-from-scratch` | Cold start as a storage problem: a manifest of digests, the shard-to-rank map, lazy loading with a prefetch order derived from the first tokens, a CDN whose cache key *is* the digest and whose invalidation is a new digest, and the measurement — bytes fetched, time to first token, hit rate — that says which of them actually cut it | I3, I7 |
| H8 | `failover-from-scratch` | Two regions with independent clocks and a link that drops for a chosen window: the health signal that is not a heartbeat, promotion with both halves (H6's quorum, A6's hinted handoff and Merkle anti-entropy), a redirect that does not apply a write twice, and RTO/RPO stated as measured with the writes it lost named | A6, H6 |

The list's framing — *most people watch tutorials, builders ship systems* — is the
house rule already: each of these is graded on the mechanism it gets wrong, offline
and deterministic, and each carries the real-hardware runbook the way
`deploy-and-debug` does.

---

## Do you need anything before AWS?

**No.** `aws-from-scratch` is self-contained: pure Python, no dependencies, and
its first section (`iam.py`) is the intended entry point — everything else gates
on it. Start there.

Three adjacent courses deepen it later, and none block it:

- `infrastructure-from-scratch` — queues, idempotency, caching
  (`system-design`'s built successor). Makes `sqs.py` and `dynamodb.py` click.
- `dynamo-paper` — the paper behind DynamoDB: quorums and partitioning in depth.
- `deploy-and-debug` — capacity and failure, the operational half.

---

## Saving what other branches already did

Substantial material exists outside `main`. Before authoring the missing
courses, cherry-pick these — do not re-invent them:

| Branch | What to port |
|---|---|
| `claude/enterprise-ai-project-guides` | `enterprise-ai-projects/` — **12 implementation guides**, including `02-multitenant-rag.md`, `10-mcp-legacy-erp.md`, `11-shadow-evaluator.md`. Guides, not code: exactly the source material for phases B, C, D. Each one is listed in `ENTERPRISE.md`, which says what this repo already has for it and what the gap is. |
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
reading and whose ten stages here are the writing. **L1, `tcp-ip-from-scratch`**,
is built too: the stack as data against a provided lossy `wire.py` — ten checks
and 554 mutations caught, from a frame's type field and the padding nobody owns,
through ARP's ageing cache and a broadcast that comes back to its sender, a
routing table with a TTL and a checksum over the pseudo-header, ICMP echo, the
handshake as a state machine, the window that must not be overrun, the socket
table, retransmission on the injected clock, the close as four segments and a
state you wait in — to a capstone that runs one whole session and then argues
about it with the wire's own segment log, key by key, and loses
(`.l1-dev/CONTRACT.md`). **L2, `concurrent-servers-from-scratch`**, is built too:
four models for one server on a provided in-memory `link.py` whose own log is
what every model is held against — ten checks and 757 mutations caught, from the
connection as a state machine, through a blocking server and the one slow client
that starves the rest, threads whose interleaving the check chooses, a reactor
whose readiness is a set, the event loop and its timer queue, callbacks as a
handle table, futures and `async`/`await` as a desugaring, the deferred write that
is backpressure, and the Redis case study as a command loop with per-connection
state — to a capstone that runs one workload through all four models, delivers
the same 148 bytes for 42, 54, 19 and 23 steps, and calls the link's own log as
the tie-breaker (`.l2-dev/CONTRACT.md`).
**L3, `mqtt-broker-from-scratch`**, is built too — the wire format itself, byte by
byte: a broker on a provided byte-pipe transport (`streams.py`, whose `step()` is
the only thing that moves a byte or a tick and whose `stats()` recomputes every
number from its own log) and a provided policy table (`grants.py`, six reasons and
a decision line written before the act) — ten checks and 600 mutations caught,
from the fixed header and its variable-length integer, through the two-byte string
and CONNECT, the topic trie that matches by components, the SUBSCRIBE that answers
the QoS it will actually grant, PUBLISH routed and retained, QoS 1 as a state with
a deadline on the injected clock, QoS 2 as a four-way handshake whose id survives
until PUBCOMP, a session that outlives the socket and the will a cut connection
owes, and refusals that arrive as a grant's own line — to a capstone that runs one
scenario twice, reads its own trace back with the course's own reader, and holds
its report against the transport's log key by key (`.l3-dev/CONTRACT.md`).
The next unit is **L4, `git-from-scratch`**.

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
| I13 Serving cluster | `serving-cluster-from-scratch` (+ I7, I10) | to author |
| I14 Model weight delivery | `weight-delivery-from-scratch` (+ I3, I7) | to author |

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

Two rows sit past this twelve-stage framing, added from the AI-infrastructure list
at the end of this file: **I13 `serving-cluster-from-scratch`** (the cluster that
stays ready — nothing above keeps a rank up, drains it or publishes what it saw) and
**I14 `weight-delivery-from-scratch`** (cold start as a storage problem — the
manifest, the shard map and the prefetch order that decide it).

The honest sequence: I1–I2 before I3 (the cost model is what makes a scheduler
decision checkable), I9 before I7 (you cannot shard without knowing what a link
costs), and I4/I5 before I11 (a gateway routes to what exists). I13 sits at the end
of the serving track because it needs a scheduler, a sharding plan and a placer to
be worth keeping up; I14 needs the same two halves for a smaller question. The rest
is parallel.

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

## Applied AI engineering (phase K) — two lists and one skill list, as six courses

Two more lists arrived from the user and are kept verbatim in `AI-ENGINEER.md`:
**25 interview problems** (design a RAG system for 10M documents; your RAG gives
wrong answers — debug it; cut LLM cost 70%; block prompt injection in a
tool-using agent; …) and **15 things to build** (dynamic context assembler,
durable state machine workflow, raw MCP server, triage router, self-correcting
RAG, 3-tier memory, trajectory CI gate, PII gateway, …). That file maps every one
of the 40 items to what already exists here — most of them are covered or partly
covered by phases B, C, D, E and J — and collects what is not.

Five gaps survived that mapping, and they are the first five K slots. The sixth is
not from those two lists at all: the **twelve-stage FDE skill list** — what a
forward deployed engineer is hired to do, learned, practised and defended, stage by
stage — and it is built whole as `fde-from-scratch` rather than left as prose, over
a customer that is data (`estate.py`, `network.py`, `meter.py`). **Two of the six are
built** — K1, `agentic-retrieval-from-scratch`, and K6, `fde-from-scratch` (both
below) — and the remaining four are authorable in the house style (a provided
simulator, ten or twelve graded stages, a check per stage, mutations behind every
check), and none of them needs a server, a network or a thread:

| Slot | Course to author | The mechanism | After |
|---|---|---|---|
| K1 | `agentic-retrieval-from-scratch` | Retrieval that checks itself: critique the results, rewrite an ambiguous query, decide grounded-or-abstain, and price each decision against the naive retrieve-and-answer — with contract-shaped chunking (clauses, cross-references) as a fixture | B1, B2, C2 |
| K2 | `prompt-ops-from-scratch` | A prompt and a model choice as versioned artifacts: a typed triage router with a measured escalation rate, shadow mode mirroring a fraction of traffic and diffing trajectories and costs, a rollout/rollback gate, the cost kill-switch, and the degradation chain frontier → mid → local → cache | E1, F2, J1 |
| K3 | `memory-engine-from-scratch` | The three tiers as data structures: a working scratchpad with a hard budget, episodic summaries with a consolidation rule, a semantic store with importance scoring and eviction, and recall measured over a long conversation | E1, B2 |
| K4 | `fine-tuning-from-scratch` | LoRA and preference tuning over A8's exact engine: the low-rank update and why it trains, a 5K-example budget that refuses a plan it cannot pay for, DPO pairs built from recorded failures, and fine-tune-vs-RAG-vs-prompting defended against a number | A8, C1 |
| K5 | `agent-privacy-from-scratch` | What leaves the process and what may come back: tokenize sensitive values before the context window and restore them after, an audit line that answers "what did it touch", per-agent least privilege, and one agent's output sanitized before it becomes another's input | C2, D1, J2 |
| K6 | `fde-from-scratch` | The twelve skills an FDE is hired for, over a customer that is data: identity and the row, an air-gapped deployment, dirty invoices reconciled into a hybrid store, retrieval that filters before the limit, the legacy ERP as tools with the credential staying in the vault, PII masked out and restored back, a workflow that stops at a person, the model that fits the customer's GPU, the work counted in hours and cents, their own tickets run in shadow, a vague ask scoped to four weeks, and a runbook drilled against armed faults handed to an admin who is not you | B1, C1, D1, J4 |

Three of the 40 items deliberately have **no slot**, and `AI-ENGINEER.md` says
why for each: serving at scale and 1M-user chat are systems exercises the repo
already decomposes (phase I, `system-design`, the docs-only serving trio), and
voice interruption and computer-use fallback are interface courses that would
need a timeline and a DOM model — real gaps, not yet promises.

**K1, `agentic-retrieval-from-scratch`**, is built: retrieval that checks itself,
as ten stages over a provided contract corpus whose ground truth is data
(`corpus.py` with 8 documents, 16 questions, 12 labelled failures and the estate's
scale; `meter.py` for what a call costs). The world never changes and the course
never writes it: what a clause *is* comes from `clause_index`, what an answer must
cite comes from `questions`, which stage failed comes from `failures`, and the
10M-document estate comes from `SCALE`. The ten stages are the two source items
mechanised — chunk clauses and their cross-references, size the index against a
memory budget, score lexically and semantically and fuse the rankings, rerank what
earns it, rewrite an ambiguous question and record the rewrite, critique what came
back, decide grounded-or-abstain with a citation per claim, run the loop under a
budget, price the checking against the naive retrieve-and-answer, and diagnose the
labelled failures without reading the label — one check per stage, 893 testers and
589 planted mutations caught, no float anywhere (BM25 and the fusion are integer,
and the world's vectors have an exact integer norm so a similarity is a dot
product). The contract is frozen in `.k1-dev/CONTRACT.md` with eight amendments
recorded, each one a reading that a stage found in the middle of the work and that
the plan had got wrong.

**Candidates, not yet registered** — the three gaps a 20-topic AI-engineering
syllabus audit found against the registry (the other seventeen are covered by
A3, B1, B2, C1, C2, D1, E1, F2, J2, J4, K1, K4, K5 and the inference spine):
`query-transform-from-scratch` (HyDE, step-back, multi-query — the rewrite
measured by the recall it buys, K1's corpus as the estate),
`graphrag-from-scratch` (a knowledge graph over B1's corpus, entity and
relation extraction with the hallucinated edge the checker plants, community
detection, the graph walk beside the vector search and the fused answer citing
which half produced it), and `llm-observability-from-scratch` (tracing as
spans over C2's event stream, the OpenTelemetry-shaped model, cost and latency
attributed per span, the drift the trace catches — I11's percentile pipeline
is the sibling to build second).

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

Three gaps survived the mapping, and they were the three L slots — all of them are
built: `tcp-ip-from-scratch` (L1, ten checks and 554 mutations caught),
`concurrent-servers-from-scratch` (L2, ten checks and 757 mutations caught) and
`mqtt-broker-from-scratch` (L3, ten checks and 600 mutations caught), all three in
the ready table above. The third is the one that needed no socket and no thread
either — the link, the clock and the failure are data, which is what makes the
interesting question answerable (how many bytes the transport carried for each
frame the broker wrote, which decision line a refusal was written on) instead of a
matter of timing.

`L4 git-from-scratch` joined the phase later, from the review of what this repo
has never built; its row is in *What this repo has never built*, above.

What has no slot: the blog posts (the links are the source, not the course), the C
implementations (the house authors Python; the C versions are what the legacy
slots are for) and the MQTT *client*, which is the broker's protocol seen from the
other side and so is a stage of L3 rather than a course of its own.

---

## Banking and credit risk (phase M) — a loan's whole life, as numbers

A fifth list arrived from the user, in Spanish and in one line: *"lgds, nueva
definición de default pd, cálculo de provisiones, y todos los cálculos de reporting
y estimación que hace un banco en su lifecycle"*. It is registered as **M1,
`credit-lifecycle-from-scratch`** — not because a bank's arithmetic is AI, but
because it is the same kind of course this repository is good at: a provided world
that *is* the ground truth (the portfolio, its observed payment histories, the
recoveries actually collected, the policy and the scenarios), ten graded stages that
recompute it, and every number an integer in basis points. That last constraint is
not a stylistic one: accounting is a fixed-point discipline, an ECL is a product of
rates and exposures, and the arithmetic a reviewer has to be able to recompute by
hand is exactly the arithmetic a float would hide.

**The four rows of this table are now all built — so phase M covers the loan from
the first application to its final effect on the bank — the lifecycle end to end:**

| Slot | Course | The mechanism | After |
|---|---|---|---|
| M0 | **ready** — `credit-origination-from-scratch` (10 checks) | The loan before it exists: the applicant as facts, the affordability and debt-service arithmetic, the application scorecard as an auditable table (weight, points, cutoff) rather than a model, the rating assigned and the price set from it — rate covering expected loss, funding and capital charge — the limit structure, collateral with its haircuts and lien, the covenant as a promise written before the drawdown, and the approval record; ends where M1 begins, at a booked facility with its schedule | — |
| M3 | **ready** — `collections-workout-from-scratch` (10 checks, 23/23 mutations) | The loan after it goes wrong: the delinquency strategy as a state machine (dunning, call, referral, each a record the customer's history answers), forbearance as the bank's decision with its probation and cure, cure rate and re-default as the strategy's measurement, the collections waterfall over the cash that arrives, the workout — collateral sale with its costs, settlement, the deficiency that survives — the write-off as an accounting act distinct from the cash that follows, and one loan followed from first missed payment to final recovery, every action and movement on its own line | M1 |
| M5 | **ready** — `distressed-debt-from-scratch` (10 checks, 21/21 mutations) | The same default from the buy side, where it is an opportunity with a price: the capital structure as a waterfall of claims over M1's borrower, the distressed claim bought below par and the question every price asks — recovery, reorganisation, or death; the distressed exchange and maturity extension as negotiated outcomes, the restructuring waterfall against the absolute-priority rule and the violations that settle it in practice, the claim valued three ways — expected recovery from M3's actual cash flows, Merton distance-to-default on the borrower's assets, comparables — where the three disagree is the trade; entry price, implied return and the IRR in basis points that survives the recovery's timing, the hold decision against the carry, and the thesis report checked against what actually happened | M1, M3 |
| M6 | **ready** — `lbo-model-from-scratch` (10 checks, 33/33 mutations) | The buyout as arithmetic that either holds or does not, over M1's amortisation and M3's workout realism: the target as facts on a provided estate whose five-year path is the ground truth, sources and uses balancing to the cent, the debt schedule as a waterfall of tranches with covenants the model cannot quietly violate (revolver drawn when cash falls short, mandatory prepayment, the incurrence test every period), the operating build from revenue to free cash flow in integer arithmetic, exit on the multiple the estate actually realises, and the returns decomposition the sponsor's memo contains — leverage vs EBITDA growth vs multiple expansion, each named, each checked; the sensitivity grid where the downside case breaches the covenant and the checker demands the breach be visible, not amortised away | M1, M3 |

With M1 (built) and M2 (below), phase M is then seven rows:
origination → the lifecycle arithmetic → collections/workout → capital →
the P&L — M5, the same default priced by the fund that buys it, and M6, the
buyout of a whole company, which is the whole of a bank's credit question in
the order a bank does it, plus both other sides of the trade: the fund buying
the claim and the sponsor buying the firm.

| Slot | Course to author | What it is | After |
|---|---|---|---|
| M1 | `credit-lifecycle-from-scratch` | A loan's whole life as numbers: the schedule and the effective interest rate that discounts it; delinquency buckets and the new definition of default (90 days past due, the unlikeliness-to-pay indicators, the materiality threshold, the cure period); PD from an observed rating migration matrix and the lifetime PD built from it; LGD from the recovery cash flows discounted to the default date; EAD and the credit conversion factor on what is undrawn; the ECL as PD × LGD × EAD discounted at the effective rate and weighted over the given scenarios; IFRS 9's three stages and the significant-increase-in-credit-risk test; the provision roll-forward with its P&L and OCI split; the reporting pack the bank files — exposures by stage, rating and past-due bucket, coverage ratios, forbearance, vintage and migration matrices — and the backtesting of PD and LGD against what happened | — |

**M1, `credit-lifecycle-from-scratch`**, is built: a loan's whole life as numbers,
as ten stages over a provided bank whose own records are the answer key
(`book.py` — `Book.build(7)`, twelve loans, thirty-six month-end reporting dates
and three model artifacts; `dates.py` for the calendar; `rules.py` for the policy,
the scenarios and the ratios, all in basis points). The world never changes and the
course never writes it: what a borrower still owes comes from the payment ledger,
what the bank calls a default comes from its own statuses, what a grade is worth
comes from the artifact in force, and what the provision moved by comes from the
roll-forward. The ten stages are the user's one line mechanised — the schedule and
the effective interest rate that discounts it, the bucket and the new definition of
default, the migration matrix and the lifetime PD, the recovery flows behind the
LGD, the drawn and undrawn balance behind the EAD, the ECL with its horizon and its
scenarios, IFRS 9's three stages and the significant-increase-in-credit-risk test,
the roll-forward line by line, the reporting pack with its coverage ratios and its
reconciliation, and the backtest, validation and attribution of a model the course
did **not** fit — one check per stage, 727 testers and 643 planted mutations
caught, no float anywhere: every division carries the contract's pinned rounding,
because accounting is a fixed-point discipline and the arithmetic a reviewer has to
recompute by hand is exactly the arithmetic a float would hide. The contract is
frozen in `.m1-dev/CONTRACT.md` with twenty-two amendments recorded, each one a
reading that a stage found in the middle of the work and the plan had got wrong.

**M2, `irb-capital-from-scratch`**, built (10 checks, 21/21 mutations): the row
the first M list implied and M1 did not cover — the bank's *own* parameter
estimates and the regulator's version of them. PIT vs TTC and where each is
legal; the IRB risk-weight formula in integer arithmetic (correlation R per
asset class, the maturity adjustment, K as the exact series, the normal
quantile as tabulated data — the no-float house rule and the reviewer's
recomputation agree on a table); downturn LGD with the multiplier and the
collateral haircut it is allowed; best-estimate LGD for the accounting stage
against the downturn floor for the capital stage; BE-EAD and its CCFs; the
output floor phased in; and the capstone that reconciles the two books —
IFRS 9's provision and IRB's capital from the same world, per grade and in
total, shown where they cannot agree with each other. Built over M1's
`book.py`/`dates.py`/`rules.py`, policy extended, everything still basis
points.

**Candidates, not yet registered** — the finance rows the registry could grow,
in the order the existing M rows make them land: `transfer-pricing-from-scratch`
(the internal liquidity desk — every deposit and loan pays for its tenor and its
optionality; closes M4's funding loop), `ledger-from-scratch` (double-entry as an
invariant — debits equal credits, always — the general ledger as a data structure,
statements derived, not drawn; the root M1 and M4 assume), `fixed-income-from-scratch`
(bootstrapping the curve, duration and convexity, the swap priced as legs),
`xva-from-scratch` (CVA/DVA/FVA over M1+M2 — future exposure as a distribution),
`options-from-scratch` (Black-Scholes by formula, by Monte Carlo and by tree, all
three agreeing; the one row where float is the domain), and
`portfolio-from-scratch` (constrained Markowitz, backtested VaR/ES).

---

## Coreutils (phase G, row G9) — grep, tail and an editor, byte for byte

Registered (to author, no prereqs): the tools the terminal is made of, judged
byte-for-byte against the real ones. `grep` — a matcher whose anchors,
character classes and `-v` inversion are decisions, not flags; `tail` —
circulation over a fixed buffer for `-n`, a backward scan for `-c`, and `-f`
as a polling loop the harness drives tick by tick; `sort`'s merge and key
spec; `wc` with GNU's last-line-without-newline behaviour reproduced exactly;
and an editor — gap buffer, a row/column screen model over the bytes, and the
redraw that must show exactly the cursor's truth, graded against scripted
keystrokes and the frame it had to have drawn. Same shape as H7: provided
corpora, provided reference behaviour, and the checker that plants the byte
you got wrong.

---

## Web3 and simulation (phase N) — the ledger, the contract, the engine

The first row built, two still to author:

| Slot | Course | The mechanism | After |
|---|---|---|---|
| N1 | **ready** — `blockchain-from-scratch` (10 checks, 37/37 mutations) | A ledger as a hash chain plus a rule for who appends: block headers and the digest that seals them, Merkle trees and inclusion proofs, addresses and signatures, the UTXO set and the spend that names what it consumes, the mempool and the double-spend the ordering kills, proof-of-work's target and difficulty adjustment, then proof-of-stake's slots and attestations, fork choice recomputable from any node's view — accepted when every simulated peer converges and a planted fork with less honest weight loses | — |
| N2 | `dapp-from-scratch` | A contract as a program the ledger runs exactly once, priced: the account model over N1's UTXO world, a bytecode VM (stack, memory, storage with cold-slot charges) and the gas schedule that makes the meter real, a toy contract language compiled to it with its ABI, escrow/token/voting contracts each carrying the reentrancy or overflow bug the tester plants, then the dApp: signed transactions, receipts, an event scanner you wrote, and a front-end state machine that reads the chain and never trusts it | N1 |
| N3 | `physics-engine-from-scratch` | A constraint solver wearing a scene graph: rigid bodies and inertia tensors, narrowphase contacts, the contact Jacobian and the LCP a projected solver iterates, warm starts, integrator order and energy drift, actuators and PD control, an MJCF subset parsed into that world — and the capstone that justifies the exercise: MuJoCo exists for differentiable simulation, so A8's exact reverse mode runs over the solver's unrolled steps, checked against the finite-difference oracle at every parameter | A8 |

Nothing else in the registry duplicates them: N1's agreement half is H6's
subject but its ledger half is new; N2's VM shares G8's heap questions but
the gas meter and the ABI are its own; N3 is the repo's first continuous
dynamics, and A8 is the only engine here that can grade its gradients.
---

## Linux device drivers (phase P) — the kernel's other half, in C

Twelve rows, one course, all built — `linux-device-driver-from-scratch`, twelve
staged modules (`l_01.py` … `l_12.py`) over a provided `kernel.py` that stands in
for the kernel's own promises: 12 checks (91 asserts); no mutation battery was
run, so the stats row says `None` rather than a zero. The chain is strictly
linear — each stage is the boundary the next one crosses:

| Slot | Course | The mechanism | After |
|---|---|---|---|
| P1 | **ready** — `l_01` Kernel Module Lifecycle | `module_init`/`module_exit`, `module_param`, `init_module`/`delete_module` — the boundaries of every driver's life | C1 |
| P2 | **ready** — `l_02` Character Device Driver | `cdev`, `file_operations`, open/read/write/release — the simplest device interface | P1 |
| P3 | **ready** — `l_03` Kernel Memory Management | `kmalloc`/`kfree`, `mmap`, memory lifecycle — every device needs memory | P2 |
| P4 | **ready** — `l_04` ioctl Commands | `_IO`/`_IOW`/`_IOR`/`_IOWR` encoding — device-specific userspace commands | P3 |
| P5 | **ready** — `l_05` Interrupt Handling | `request_irq`/`free_irq`/ISR — how hardware talks to the driver | P4 |
| P6 | **ready** — `l_06` Platform Driver Model | `platform_driver`/`platform_device`, probe/remove — kernel hardware discovery | P5 |
| P7 | **ready** — `l_07` Device Resources | `platform_get_resource`, memory and IRQ resources — hardware description | P6 |
| P8 | **ready** — `l_08` sysfs and Device Attributes | kobject hierarchy, `/sys/class` — driver state exposed to userspace | P7 |
| P9 | **ready** — `l_09` Wait Queues and Polling | `wait_event`/`wake_up`/`poll` — blocking without busy-waiting | P8 |
| P10 | **ready** — `l_10` Workqueues and Kernel Threading | `queue_work`/`work_struct`/`kthread_create` — deferred work in the kernel | P9 |
| P11 | **ready** — `l_11` Network Device Driver | `alloc_netdev`/`ndo_open`/`ndo_start_xmit` — the most complex device type | P10 |
| P12 | **ready** — `l_12` Synchronization Primitives | spinlock/mutex/semaphore/RCU — concurrency is the hardest part | P11 |

P1 gates on C1 (`evals-from-scratch`) by the user's registration choice — the
only edge in the whole phase that is not inside the chain. Its semantics are a
stretch (a scored harness before a module's `init`); the dependency audit flagged
it and kept it, because it is buildable and it is the user's row.

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
