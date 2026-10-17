# learn-stuff-from-scratch

A collection of from-scratch implementations of various systems and projects for learning purposes.

**New here? Read [PHILOSOPHY.md](PHILOSOPHY.md)** — what this repo is for, and the three
principles every directory follows: design choices named as problem-solving decisions,
MVP-then-complicate driven by limit cases, and verification you can run.

**Learning Agent Infra? Read [AGENT-INFRA.md](AGENT-INFRA.md)** — the twelve-area skill list this repo's phase J is being built from.

## codecraft — the adaptive course runner

**[codecraft/](codecraft/)** turns this repo into your own CodeCrafters. It runs any
course's `check.py`, remembers every attempt, classifies how you got stuck (the same
failure three times vs. three different failures get different advice), and tunes the
nudge, hint depth and pacing to you. It also scaffolds **new** from-scratch courses you
author yourself:

```bash
cz run llm-from-scratch       # run a course, get coached (cz = the CLI shim)
cz path                       # the ordered plan, with progress
cz dag                        # the dependency DAG: what must come first
cz stage llm-from-scratch 5   # one stage: what to write, what the tester costs
python3 codecraft/cli.py new my-course --title "Build X" --stages 3
```

`cz` is a one-line forwarder to `python3 codecraft/cli.py`; both work. See
[codecraft/README.md](codecraft/README.md).

## Directory Structure

### Low-Level Systems (C/C++)
- **[c-compiler/](c-compiler/)** - C compiler implementation in C
- **[quantum-computing-lang/](quantum-computing-lang/)** - Quantum computing language and simulator (like Qiskit) in C
- **[cryptographic-library/](cryptographic-library/)** - Cryptographic primitives (SHA-256, ECDSA, etc.) in C
- **[bash-from-scratch/](bash-from-scratch/)** - Unix shell/terminal implementation
- **[http-server/](http-server/)** - HTTP server implementation
- **[dns-server/](dns-server/)** - DNS server implementation with UDP networking and protocol parsing
- **[firewall-from-scratch/](firewall-from-scratch/)** - Packet filtering firewall with raw sockets, protocol parsing, and rule-based filtering
- **[communication-protocols/](communication-protocols/)** - Serial & parallel communication protocol implementations: UART/USART, SPI, I2C, CAN bus, RS-232/RS-485 (with Linux spidev/i2c-dev/SocketCAN hardware support)

### GPU Programming & Parallel Computing
- **[cuda-from-scratch/](cuda-from-scratch/)** - CUDA parallel programming from basics to neural networks on GPU
- **[compiler-and-vgpu/](compiler-and-vgpu/)** - A compiler and a virtual GPU sharing one instruction set: 32-bit ISA, two-pass assembler, scalar CPU, recursive-descent front end, code generation with linear-scan register allocation and spilling, and a SIMT warp with divergence, mask stacks and barrier deadlock detection (12 graded checks via `python3 check.py`)

### Functional Programming & Formal Verification
- **[haskell-projects/](haskell-projects/)** - Various projects to learn Haskell
- **[lean-proofs/](lean-proofs/)** - Mathematical proofs in Lean, progressing toward Galois theorem
- **[skill-tree/](skill-tree/)** - Dependency graph of 38 math and pattern-recognition skills (Mathematics for ML, Axler, Trefethen & Bau, Blitzstein & Hwang, Boyd, Bishop PRML), each with prerequisites, acceptance criteria and limit cases, validated by `tree.py`; modules are built into [math/](math/) following `.claude/skills/skill-tree-worker`
- **[math/](math/)** - Graded modules for the skill-tree nodes in the repo's template + `check.py` + `solutions/` format, mutation-tested by planted bugs

### Machine Learning & MLOps
- **[distributed-training/](distributed-training/)** - Distributed training systems (data parallelism, model parallelism, multi-node training)
- **[ml-in-production/](ml-in-production/)** - Production ML systems (model serving, monitoring, A/B testing)
- **[mlops/](mlops/)** - MLOps pipelines (experiment tracking, CI/CD, feature stores)
- **[ml-inference/](ml-inference/)** - High-performance inference (optimization, quantization, edge deployment)

### Generative AI & Deep Learning
- **[diffusion-models/](diffusion-models/)** - Diffusion models from scratch (DDPM, DDIM, U-Net, image generation like Stable Diffusion)
- **[deepfake-creation/](deepfake-creation/)** - Deepfake generation techniques (face swapping, reenactment, First Order Motion Model, Wav2Lip)
- **[deepfake-detection/](deepfake-detection/)** - Deepfake detection methods (CNN-based, temporal analysis, frequency domain, biological signals)

### ML Infrastructure & Serving
- **[sgl-lang/](sgl-lang/)** - Structured Generation Language (SGL) for LLMs - constrained generation, grammar enforcement, compilation
- **[tensorrt-inference/](tensorrt-inference/)** - TensorRT-style inference engine - graph optimization, quantization, kernel auto-tuning
- **[vllm-engine/](vllm-engine/)** - vLLM serving engine - PagedAttention, continuous batching, high-throughput LLM serving
- **[context-caching/](context-caching/)** - LLM context caching from scratch on a tiny pure-Python transformer: KV cache, block-hash and radix-tree prefix caching, paged KV blocks with copy-on-write, semantic response caching, and cache-aware request routing (16 graded checks via `python3 check.py`)
- **[contextcite/](contextcite/)** - ContextCite (NeurIPS 2024) replicated from scratch: context attribution by ablating sources and fitting a sparse LASSO surrogate - source partitioning, logit-probability scoring, coordinate-descent LASSO, held-out LDS evaluation, and the paper's three applications (14 graded checks via `python3 check.py`)

### LLM Engineering & Retrieval
- **[llm-from-scratch/](llm-from-scratch/)** - The forward-pass mechanisms of a language model in plain Python: BPE tokenizer, attention, sampling, the KV cache and rotary positions (13 graded checks via `python3 check.py`)
- **[rag-from-scratch/](rag-from-scratch/)** - Retrieval-augmented generation from the parts up: chunking with exact offsets, TF-IDF, an exact vector index, BM25, reciprocal rank fusion, reranking with MRR, grounded citations and tenant isolation (9 graded checks via `python3 codecraft/cli.py run rag-from-scratch`)
- **[agentic-retrieval-from-scratch/](agentic-retrieval-from-scratch/)** - Retrieval that checks itself, over a provided contract corpus that *is* the ground truth (`corpus.py`, `meter.py`; standard library only, no float, no clock, no randomness, no library statistics): chunk a document into its numbered clauses with their cross-references and name the duplicate and the skip, size the index of a ten-million-document estate against a memory budget, score lexically and semantically and fuse the two rankings, make a reranker earn its place against the noise, rewrite a question whose referent lives only in the conversation, critique what came back before believing it, decide grounded-or-abstain with a citation for every claim, run the loop under a budget that stops for a reason it names, price the checking against the naive retrieve-and-answer, and diagnose twelve real failures without reading the label the customer gave them (10 graded checks via `python3 codecraft/cli.py run agentic-retrieval-from-scratch`)
- **[credit-lifecycle-from-scratch/](credit-lifecycle-from-scratch/)** - A loan's whole life as numbers, over a provided bank whose own records are the answer key (`book.py`, `dates.py`, `rules.py`; integer basis points and cents only, no float, no library, no clock): the contractual schedule and the effective interest rate that discounts it, the days past due and the new definition of default with its materiality threshold and its cure period, PD from the book's own rating migration matrix and the lifetime PD built from it, LGD from the recovery cash flows discounted to the default date, the drawn and undrawn balance and the credit conversion factor estimated on the book's own defaults, the expected credit loss with its horizon and its scenarios, IFRS 9's three stages with the significant-increase-in-credit-risk test, the provision roll-forward decomposed line by line, the reporting pack with its coverage ratios and its reconciliation, and the backtest, validation and attribution of a model the course did not fit (10 graded checks via `python3 codecraft/cli.py run credit-lifecycle-from-scratch`)
- **[vector-index-from-scratch/](vector-index-from-scratch/)** - Approximate nearest-neighbour search, measured against the exact answer: brute force with a work counter, the metric and its norm cache, k-means, IVF with `nprobe`, HNSW built and walked, deletions by tombstone, int8 quantization, and the recall/latency frontier with the tuning held out (10 graded checks via `python3 codecraft/cli.py run vector-index-from-scratch`)
- **[evals-from-scratch/](evals-from-scratch/)** - The harness that decides whether a text system got better: group-wise splits, operational rates and percentiles, deterministic assertions with three states, EM and token F1, recall@k/MRR/nDCG, an LLM judge judged in both orders, Cohen's kappa and the F1-optimal threshold, McNemar and the paired bootstrap, Holm's correction, and a regression gate with per-slice floors (10 graded checks via `python3 codecraft/cli.py run evals-from-scratch`)
- **[agents-from-scratch/](agents-from-scratch/)** - The runtime under an agent, with the model injected as a callable so every run is deterministic and offline: the tool loop and the transcript that is its state, tool schemas and argument validation, a toolbox that turns a failure into an observation, parsing what a model actually writes, retries with an injected clock and effects that cannot land twice, memory bounded by turns, a filesystem sandbox that resolves before it compares, an approval gate against content that is not a command, budgets that stop before the call that would exceed them, and a trace plus a state-based audit (10 graded checks via `python3 codecraft/cli.py run agents-from-scratch`)
- **[mcp-from-scratch/](mcp-from-scratch/)** - A Model Context Protocol server from the bytes up (spec revision 2025-06-18, standard library only, no sockets): the JSON-RPC envelope and its error codes, stdio/SSE/HTTP framing with stdout purity, the lifecycle handshake with derived capabilities, tools and the protocol-versus-execution error split, resources and prompt templates including the one "not found" the spec pins at -32002, subscriptions/progress/cancellation where a cancelled request gets no response at all, read-only first with an allowlisted report tool, idempotency keys for a caller that retries, a confirmation dialog that shows the diff it is about to apply, and the trajectory policy plus an audit line with no clock and no payload (10 graded checks via `python3 codecraft/cli.py run mcp-from-scratch`)
- **[agent-harness-from-scratch/](agent-harness-from-scratch/)** - The runtime under an agent, with the model as a callable returning an event stream (standard library only, no network, no wall clock): collect a turn from text/tool_call/usage/end events, a prompt budget recomputed from the bytes, the loop where a spent budget is an outcome instead of an exception, dispatch where an unknown tool or a bad argument is an observation the model can repair, streaming with TTFT and inter-token timings, retries that stop the moment anything was forwarded, compaction by turn that summarizes the middle and pins the system message, a trace of exactly six keys and no payloads, a process reward that grounds every step in the result before it, and a verifier plus a self-generated data loop whose accuracy is measured on held-out tasks (10 graded checks via `python3 codecraft/cli.py run agent-harness-from-scratch`)
- **[benchmark-from-scratch/](benchmark-from-scratch/)** - The measurement machinery of a benchmark on top of a provided Fournier mus engine (standard library only, no network, no wall clock): gate an action so a refusal is data and not a turn, run a match with as-dealt snapshots, an engine-supplied fallback and the rails that stop a run that became about the harness, record one ground-truth decision per turn from the position the seat actually faced, link an aggression to the answer it got, tercile the strength of the hands that could bet, score aggression, bluffs and fold equity, reduce a match to piedras that survive the vaca reset, probe a declared probability with Brier, log-loss, AUC and a calibration table, gate what may be published, and play every matchup twice under one seed so the seat advantage cancels.
- **[eval-framework-from-scratch/](eval-framework-from-scratch/)** - The runner under an eval, with the task set, the actors and the clock provided (standard library only, no network, no wall clock): validate a suite config and hash its effective form, resolve metric plugins before the first call, run one case per record with an error taxonomy that blames the right side, check call and clock budgets before the call instead of reporting them after, aggregate by case with the weights the suite declared, ask a judge through a cached and budgeted session that survives a position bias, write records whose bytes two runs share, gate a run with exit codes that order an invalid run before a failed gate, diff a candidate against a baseline through the noise of both, and resume a killed run into the exact bytes of an uninterrupted one.
- **[cpu-from-scratch/](cpu-from-scratch/)** - A CPU from scratch on a provided ISA and assembler (standard library only, no wall clock - cycles are counted): mask a word and derive the four flags, decode an encoding whose unused fields must not become operands, keep a register file whose zero register cannot be written, truncate division and take the remainder the way hardware does rather than the way Python does, address bytes with bounds and alignment checked before anything is stored, fetch, execute and record a trace where a fault is data rather than an exception, and then run the same programs on a five-stage pipeline that must retire the identical trace - stalling first, then forwarding with the one-cycle load-use stall and a branch flush - before measuring both machines and reporting the CPI.
- **[os-from-scratch/](os-from-scratch/)** - An operating system as what you write after the hardware breaks its last promise, on a provided machine (standard library only, no clock, no randomness, no float anywhere): join a boot map's regions and derive the frames a kernel may hand out, allocate them from a bitmap that protects the frame its own bits live in and answers all or nothing, build page tables whose entries can never be read as frame numbers and whose permission bits are checked on every walk, take a fault as a word a handler decides from, refuse a pointer before anything is done with it and write the line that promises the act before the act, make a process a dict with a space, a ledger and a zombie at the end where `fork` copies frames rather than table entries, pick by priority and age behind a quantum that rotates, put two CPUs on a checked interleaving where the critical section is a lock, format a real on-disk filesystem with its superblock written last and mount only what a barrier made durable, and finish on a capstone userland whose kernel report is recomputed from its own log and cross-checked against the machine's records (10 graded checks via `python3 codecraft/cli.py run os-from-scratch`)

### System Design & Distributed Systems
- **[mqtt-broker-from-scratch/](mqtt-broker-from-scratch/)** - A broker whose every frame its own reader takes back (standard library only, no sockets, no threads, no wall clock, no floats): the fixed header and the variable-length integer that says how long the rest is, CONNECT and the session flags, a topic trie where `+` and `#` are matched by components and never by prefix string, SUBSCRIBE and the QoS actually granted, PUBLISH routed to real subscribers and the message retained for the next one, QoS 1 as state (the packet id, the PUBACK, the deadline that re-sends with DUP) and QoS 2 as a four-way handshake where the id may not be reused before PUBCOMP, a session that outlives the socket with its queue and its keep-alive, the last will a cut connection owes, grants and denials written down before the act, and a capstone that runs one scenario twice, re-reads its own trace with the course's own reader and holds its report against the transport's log — on a provided `streams.py` and `grants.py` whose `stats()` and decision lines are the tie-breaker (10 graded checks via `python3 codecraft/cli.py run mqtt-broker-from-scratch`)
- **[concurrent-servers-from-scratch/](concurrent-servers-from-scratch/)** - Four models for one server on a provided in-memory `link.py` whose own log is the tie-breaker (standard library only, no threads, no sockets, no wall clock, no floats): a connection as a state machine over an outbox that has to be counted rather than assumed, a blocking server and the one slow client that starves everybody behind it, threads whose interleaving the check chooses, a reactor whose readiness is a set and whose poll loop never busy-waits, the event loop with a monotonic timer queue, callbacks as a handle table where the cancelled one must not run, futures and `async`/`await` as a desugaring onto the same loop, backpressure as a reply deferred in the connection's own state with head-of-line blocking reported as `stalled`, the Redis case study as a command loop with per-connection state and expiry deadlines on the injected clock, and a capstone that runs one workload through all four models — 148 bytes delivered by each for 42, 54, 19 and 23 steps — and settles any disagreement with the link's own counts rather than with a model's beliefs (10 graded checks via `python3 codecraft/cli.py run concurrent-servers-from-scratch`)
- **[tcp-ip-from-scratch/](tcp-ip-from-scratch/)** - A network stack as data, on a provided `wire.py` that loses, duplicates, delays and reorders what it carries (standard library only, no clock but the wire's tick, no randomness but a rule that names the frame): the frame and the type field that says what is inside, ARP with a cache that ages out, IPv4 with a hop count spent before it can circulate and a checksum that covers only its own header, ICMP whose checksum covers the whole message, the handshake as a state machine that answers only what it agreed to, the window with the acknowledgement that covers everything behind it, the socket API as a table of eight calls and one log, the retransmission timer that doubles for the oldest unacknowledged segment, the close with TIME_WAIT as a state with a deadline rather than a sleep, and a capstone whose session ledger is cross-checked against the wire's own record of what it sent, dropped and delivered (10 graded checks via `python3 codecraft/cli.py run tcp-ip-from-scratch`)
- **[system-design/](system-design/)** - Core distributed systems patterns: caching (LRU, cache-aside, stampede), async queues (retries, backoff, DLQ, idempotency), reliability (circuit breaker, bulkhead, backpressure), consistent hashing, leaderboards, URL shortener, rate limiter, and capacity math
- **[queue-and-workers-from-scratch/](queue-and-workers-from-scratch/)** - A scheduler as a data structure, not a thread pool (standard library only, no threads, no wall clock, no floats): typed specs that refuse a typo instead of defaulting it, admission that counts running work and refuses with `QueueFull`, priority as `(-priority, seq)` with the tie that makes two runs differ, the concurrency limit checked before a worker runs, leases that expire and hand the task and the slot back, a growing backoff on the injected clock with dead letters at the attempt budget, the water mark answered with refuse/shed/block, ageing capped so the interactive tenant survives, a record rebuilt from the run's own log, and two runs that print identical bytes (10 graded checks via `python3 codecraft/cli.py run queue-and-workers-from-scratch`)
- **[orchestration-from-scratch/](orchestration-from-scratch/)** - A big task as a graph of small ones, and the graph as data (standard library only, no threads, no model, no floats): subtasks and graphs that refuse a typo instead of defaulting it, the edge set and the waves a dependency forces with a cycle refused by naming its path, the schedule decided by the states rather than by the wave so a fast node never waits for a slow sibling, the handoff that carries exactly a child's own dependencies' accepted results each cut to the budget that dependency declared, a reviewer who can reject with a rework that carries the reason and stops at `MAX_REWORK`, one failure that skips its transitive dependents without running them, an effect held behind its approval rather than landing before it, the call a budget cannot pay for refused before it happens, and a record of seven kinds and no payload text with a report recomputed from it — two runs of one fixture, identical bytes (10 graded checks via `python3 codecraft/cli.py run orchestration-from-scratch`)
- **[durable-execution-from-scratch/](durable-execution-from-scratch/)** - A run as a log rather than a process, on a provided disk that loses everything it was not told to sync (standard library only, no threads, no filesystem, no floats): the line and the journal that holds it with a typo refused by name instead of defaulted, the write that was not synced and the sync that makes it a fact, a replay that refuses the half-written tail a crash leaves rather than guessing what it meant, a lease whose deadline is derived from its own line (`claimed_at + ticks`) with a steal refused by naming both owners, the beat that renames a deadline and the grace that separates *expired* from *dead*, a crash that replays only what the disk would keep and writes the `expire` lines the dead owners' jobs owe, an effect that happens exactly once because its intent is synced before it runs and the world's own count decides what a replay owes, a checkpoint beside the append-only journal with a resume that refuses another run's log by name, a report whose every counter is recounted from the lines and a caller's total refused when the log contradicts it, and a capstone that kills one worker holding a lease mid-run and still ends on the same states, and the same effects, as the run nobody killed (10 graded checks via `python3 codecraft/cli.py run durable-execution-from-scratch`)
- **[sandbox-capabilities-from-scratch/](sandbox-capabilities-from-scratch/)** - An agent's power as the intersection of what its tools declare, what its principal granted and what the world will still afford, on a world made of data (standard library only, no filesystem, no sockets, no floats): a capability per tool that is declared, granted and then intersected rather than inferred, a demand that must be a set and a vocabulary that refuses a name it does not have, a path jail that resolves `..` before anything is judged and refuses the sibling root a `startswith` test would hand over, a network policy where the port is part of the host's identity and no wildcard a reader cannot evaluate is a policy, cpu/memory/ticks limits charged all or nothing before the work, secrets that reach the model as a handle, a length and a digest while the leak test knows base64 (padded and stripped), hex (both cases) and the reversed value, an audit line of seven fields always written with a closed reason vocabulary, the six questions - catalogue, grant, jail, host, limit, secret - decided in one order with the line written *before* the act and a denial that reaches the filesystem, the wire, the vault and the meter not at all, a report recomputed from the lines and cross-checked against `VFS.log()`, `Wire.dialled()` and `Vault.reads()` with no denied call allowed in any of them, and a run whose answer to "what did it touch" is its audit and not its plan (10 graded checks via `./cz run sandbox-capabilities-from-scratch`)
- **[agent-metrics-from-scratch/](agent-metrics-from-scratch/)** - A trace is not a metric, measured over a fleet that writes down what happened (standard library only, no floats, no clock but the injected tick): the twelve-field event whose kind decides which of them mean anything, a half-open window that makes a tumbling set a partition and refuses an inclusive end, queue depth as a gauge derived from a state machine over the five kinds and never summed, a percentile as a nearest-rank index over exact integers, latency split into the wait, the service and the retry gap with the identity asserted, tokens and micros summed before they are divided and priced by the pool that ran the task, failure and retry rates that name their own denominators, windows whose step may not leave a hole, and a report recomputed from the events and cross-checked key by key against the fleet's own count of the same run (10 graded checks via `python3 codecraft/cli.py run agent-metrics-from-scratch`)
- **[interconnects-from-scratch/](interconnects-from-scratch/)** - NCCL's model in code, on a provided fabric (links with bandwidth and latency, four topologies, an executor): the cost model you write yourself (`latency + ceil(bytes / bandwidth)` per hop, a step is its slowest transfer, a plan the sum of its steps), ring and tree broadcast and reduce, the ring all-reduce with its `2(N-1)` steps and its chunks, recursive doubling with the one-hop partners it actually needs, all-gather and reduce-scatter as first-class collectives, the all-to-all whose offsets depend on the data, send/recv with full-duplex group semantics, the lower bound that decides an algorithm (SHARP modelled as a plan the executor can run), and one training step's four parallelism axes overlapped with compute as a max — a collective has a plan and a price, and the two are checked independently (10 graded checks)
- **[autograd-from-scratch/](autograd-from-scratch/)** - Reverse-mode automatic differentiation over exact rationals, on a provided forward algebra (`exact.py`, standard library only, no float anywhere): the graph and the topological order that visits a diamond once, the local derivatives and the accumulation that makes a node used twice add up, broadcasting and the reduction that hands each operand back its own shape, `matmul`'s two transposed VJPs with the small MLP composed from them, `shared`/`trainable` as a freeze that stops the walk, the seed of a non-scalar output and its explicit collapse, `detach` and the `no_grad` region, the kink at a tie and the left-operand rule, an exact central-difference oracle off by exactly `h²` on a cubic, and the capstone step that learns XOR in eight exact steps and reproduces the reference gradient (10 graded checks via `python3 codecraft/cli.py run autograd-from-scratch`)
- **[distributed-training-from-scratch/](distributed-training-from-scratch/)** - The plans on top of I9's collectives, on a fabric copied verbatim and a model handed to you (standard library only, no network, no GPU, no floats): a step as a plan with its bytes per rank and its memory ledger, DDP's bucketed gradient all-reduce hidden behind the compute, ZeRO's ladder (`4 + 12/N` for ZeRO-1, `2 + 2/N + 12/N` for ZeRO-2), FSDP's per-unit gather and scatter with its `4P(N−1)/N` peak, tensor parallel's column and row blocks with the two all-reduces per block, GPipe versus 1F1B and the bubble replayed from the slots, interleaving's `(p−1)/(m·v+p−1)`, the expert all-to-all with its routing table, capacity cap and balance loss, ring attention's exact running pivot and its KV ring, and the configuration that ticks every split, takes the argmin and reports its price from the plan itself (10 graded checks via `python3 codecraft/cli.py run distributed-training-from-scratch`)
- **[dynamo-paper/](dynamo-paper/)** - Amazon's Dynamo paper (SOSP 2007) implemented directly: consistent hashing with preference lists, vector clocks, N/R/W quorums, sloppy quorum with hinted handoff, Merkle-tree anti-entropy, and gossip membership (17 graded checks via `python3 check.py`)
- **[aws-from-scratch/](aws-from-scratch/)** - Learn AWS by implementing toy versions of its core services: IAM policy evaluation, S3 with versioning and delete markers, SQS visibility timeouts, DynamoDB hot partitions, Lambda concurrency and cold starts, SNS filter policies and EventBridge patterns, KMS envelope encryption, VPC stateful-vs-stateless networking, plus a capstone pipeline wiring them together - and a map of which remaining AWS services are variations of which mechanism (18 graded checks via `python3 check.py`)

### Operations & Reliability
- **[deploy-and-debug/](deploy-and-debug/)** - Running the systems in this repo and debugging them when they break: capacity math (KV cache sizing, N/R/W failure tolerance), percentiles/queueing/error budgets, root-cause diagnosis of 11 injected faults from metrics alone, and safe rollout (liveness vs readiness, canary analysis, budget-based auto-rollback) - plus a runbook of the real vllm/nodetool/nvidia-smi/k8s commands (12 graded checks via `python3 check.py`)
- **[fde-from-scratch/](fde-from-scratch/)** - An enterprise AI deployment whose every claim is a record a check can read back, over a provided customer that is data (`estate.py`, `network.py`, `meter.py`; standard library only, no clock, no randomness, no floats): the assertion, the session and the row, a deployment that cannot reach out, dirty invoices reconciled into a hybrid store, retrieval that filters before the limit, the legacy system as tools with the credential staying in the vault, PII masked out and restored back so nothing leaked, a workflow that stops at a person and journals the decision, the model that fits the GPU somebody else owns, the AI's work counted in hours and cents, the customer's own tickets run in shadow and answered with one verdict, a vague ask scoped to four weeks, and a runbook drilled against armed faults handed to an admin who is not you (12 graded checks via `python3 codecraft/cli.py run fde-from-scratch`)

### Data Engineering & Analytics
- **[sas-lineage-tool/](sas-lineage-tool/)** - SAS field lineage parser for tracking data transformations and dependencies
- **[web-scraping/](web-scraping/)** - Industrial web scraping/crawler library (Python/C, CUDA acceleration, CAPTCHA bypass, distributed architecture)

### Quantitative Finance & Trading
- **[quantitative-trading/](quantitative-trading/)** - Algorithmic trading systems (statistical arbitrage, ML strategies, RL agents, market microstructure)

## Philosophy

This repository is dedicated to learning by building things from scratch. Each directory contains:
- **Template files** with TODO comments and implementation guidelines
- **Step-by-step instructions** for gradual implementation
- **Complete solutions** in the `solutions/` folder for reference
- A clear learning path from basics to advanced topics

## Structure

Each project directory contains:

```
project-name/
├── README.md              # Project overview and learning path
├── template-files         # Empty templates with TODOs and guidelines
├── Makefile              # Build configuration (for C projects)
└── solutions/            # Complete working implementations
    ├── README.md         # Solution documentation
    └── solution-files    # Fully implemented code
```

## Getting Started

1. **Choose a project** that interests you
2. **Read the README** in that directory to understand the goals
3. **Start with the template files** - they have TODOs and guidelines
4. **Implement gradually** - follow the TODO comments step by step
5. **Test frequently** - build and test as you implement each section
6. **Check solutions** when stuck or to verify your approach
7. **Learn and iterate** - understand each step before moving forward

## Implementation Approach

The templates are designed to be:
- ✅ **Gradual**: Start simple, add complexity incrementally
- ✅ **Guided**: Clear TODO comments explain what to implement
- ✅ **Balanced**: Not too easy (no hand-holding), not too hard (reasonable steps)
- ✅ **Educational**: Focus on understanding concepts, not just copying code

## Building Projects

Most C projects include a Makefile:

```bash
cd project-name/
make          # Build the project
make run      # Run the program
make test     # Run tests (if available)
make clean    # Clean build artifacts
```

## Video Courses & Learning Resources

To complement the hands-on projects in this repository, we've curated relevant video courses from universities and online platforms. These courses provide theoretical foundations and different perspectives on the topics covered here.

**Note**: This curated list is based on the excellent [cs-video-courses](https://github.com/Developer-Y/cs-video-courses) repository by Developer-Y, which maintains a comprehensive collection of Computer Science courses with video lectures.

### General Computer Science
- [CS 50 - Introduction to Computer Science, Harvard University](https://online-learning.harvard.edu/course/cs50-introduction-computer-science)
- [6.0001 - Introduction to Computer Science and Programming in Python - MIT OCW](https://ocw.mit.edu/courses/6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/video_galleries/lecture-videos/)

### Systems Programming & Operating Systems
*Relevant for: bash-from-scratch, http-server, dns-server, c-compiler*
- [15-213 Introduction to Computer Systems - CMU](https://scs.hosted.panopto.com/Panopto/Pages/Sessions/List.aspx#folderID=%22b96d90ae-9871-4fae-91e2-b1627b43e25e%22&maxResults=150)
- [CS 162 Operating Systems - UC Berkeley](https://archive.org/details/ucberkeley-webcast-PL-XXv-cvA_iBDyz-ba4yDskqMDY6A1w_c?sort=titleSorter)
- [6.824 - Distributed Systems - MIT](https://pdos.csail.mit.edu/6.824/schedule.html)

### Compiler Design & Programming Languages
*Relevant for: c-compiler, quantum-computing-lang*
- [CS143 - Compilers - Stanford](https://web.stanford.edu/class/cs143/)
- [Theoretical CS and Programming Languages courses](https://github.com/Developer-Y/cs-video-courses#theoretical-cs-and-programming-languages)

### Cryptography & Security
*Relevant for: cryptographic-library*
- [Security Courses - Various Universities](https://github.com/Developer-Y/cs-video-courses#security)

### Parallel Computing & GPU Programming
*Relevant for: cuda-from-scratch*
- [Parallel Computing and GPU Programming courses](https://github.com/Developer-Y/cs-video-courses#computer-organization-and-architecture)

### Machine Learning & Deep Learning
*Relevant for: distributed-training, ml-in-production, mlops, ml-inference, diffusion-models, deepfake-creation, deepfake-detection, world-models*
- [CS229 - Machine Learning - Stanford](http://cs229.stanford.edu/)
- [6.S191 - Introduction to Deep Learning - MIT](http://introtodeeplearning.com/)
- [Deep Learning Specialization - Various Universities](https://github.com/Developer-Y/cs-video-courses#deep-learning)
- [Computer Vision Courses](https://github.com/Developer-Y/cs-video-courses#computer-vision)
- [Generative AI and LLMs](https://github.com/Developer-Y/cs-video-courses#generative-ai-and-llms)

### MLOps & Production ML
*Relevant for: sgl-lang, tensorrt-inference, vllm-engine*
- [Full Stack Deep Learning](https://fullstackdeeplearning.com/)
- [Machine Learning Systems Design](https://github.com/Developer-Y/cs-video-courses#machine-learning)

### LLM Agents & Retrieval
*Relevant for: agents-from-scratch, mcp-from-scratch, rag-from-scratch, vector-index-from-scratch, evals-from-scratch*
- [NirDiamant/agents-towards-production](https://github.com/NirDiamant/agents-towards-production) — end-to-end tutorials on evaluations, guardrails, deployment and cost control: what a benchmark never teaches, and the same problems flock's gate, budgets and badges solve
- [NirDiamant/RAG_Techniques](https://github.com/NirDiamant/RAG_Techniques) — every advanced RAG technique in a runnable notebook (hybrid search, reranking, graph RAG…); the catalog of variants once you have built the parts yourself with rag-from-scratch
- [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers) — the master catalog of MCP servers for wiring agents to real systems (databases, APIs, tools); the index of what an mcp-from-scratch server can actually talk to

### Agent Harness Patterns
*Relevant for: agent-harness-from-scratch, agents-from-scratch, mcp-from-scratch, evals-from-scratch*
The model is one part of a coding agent; the harness decides memory, context, tools, permissions and what happens around every call. Twelve named patterns, distilled from Claude Code: persistent instruction file, scoped context assembly, tiered memory, dream consolidation, progressive compaction · explore-plan-act, context-isolated subagents, fork-join parallelism · progressive tool expansion, command risk classification, single-purpose tools · deterministic lifecycle hooks.
- [12 Agentic Harness Patterns](https://dev.to/akki907/12-agentic-harness-patterns-2jkj) — the list itself, with the trade-off of each pattern and notes from a shipped build
- [keli-wen/agentic-harness-patterns-skill](https://github.com/keli-wen/agentic-harness-patterns-skill) — the same twelve as an installable agent skill (EN/ZH), Codex CLI and Gemini CLI on the roadmap
- [huangjia2019/agent-design-patterns](https://github.com/huangjia2019/agent-design-patterns) — 28 patterns on a 7×6 coordinate grid with runnable slices taken from Claude Code, Aider, OpenHands and DeerFlow
- [mahonzhan/awesome-agent-harness](https://github.com/mahonzhan/awesome-agent-harness) — curated catalog of harnesses, agent and workflow frameworks, and emerging protocols
- [Dive into Claude Code](https://arxiv.org/abs/2604.14228) — the design-space study behind the list; and [Harness Engineering](https://arxiv.org/abs/2609.00006), a source-code anatomy of eleven production coding harnesses

### Functional Programming
*Relevant for: haskell-projects*
- [FP 101x - Introduction to Functional Programming - TU Delft](https://ocw.tudelft.nl/courses/introduction-to-functional-programming/)
- [Functional Programming courses](https://github.com/Developer-Y/cs-video-courses#theoretical-cs-and-programming-languages)

### Formal Verification
*Relevant for: lean-proofs*
- [Formal Methods and Verification courses](https://github.com/Developer-Y/cs-video-courses#theoretical-cs-and-programming-languages)

### Quantum Computing
*Relevant for: quantum-computing-lang*
- [Quantum Computing Courses](https://github.com/Developer-Y/cs-video-courses#quantum-computing)

### Computational Finance
*Relevant for: quantitative-trading*
- [Computational Finance Courses](https://github.com/Developer-Y/cs-video-courses#computational-finance)

### System Design & Distributed Systems
*Relevant for: system-design*
- [CS 75 - Building Dynamic Websites - Harvard](https://cs75.tv/2012/summer/)
- [6.824 - Distributed Systems - MIT](https://pdos.csail.mit.edu/6.824/schedule.html)
- [CMU 15-445 Database Systems](https://15445.courses.cs.cmu.edu/fall2022/)
- [Database Systems Courses](https://github.com/Developer-Y/cs-video-courses#database-systems)
- [Distributed Systems Courses](https://github.com/Developer-Y/cs-video-courses#distributed-systems)

### Data Engineering
*Relevant for: sas-lineage-tool, web-scraping*
- [Database Systems Courses](https://github.com/Developer-Y/cs-video-courses#database-systems)

### Computer Networks
*Relevant for: http-server, dns-server, communication-protocols*
- [Computer Networks Courses](https://github.com/Developer-Y/cs-video-courses#computer-networks)

**For a complete list of courses across all CS topics**, visit the [Developer-Y/cs-video-courses](https://github.com/Developer-Y/cs-video-courses) repository.

## Note

These implementations are for educational purposes. They prioritize clarity and understanding over production-ready features or performance. Use the solutions as reference, but try to implement yourself first for maximum learning!