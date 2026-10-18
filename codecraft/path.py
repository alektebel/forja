"""The path: what to build, in what order, and what is missing.

`codecraft path` renders this merged with your live progress. The order follows
the plan you set — AWS first, then LLM internals, then the AI-engineering half
(RAG, evals, agents, MCP, harness, benchmark, eval), then the systems half
(compiler/GPU/CPU and the rest).

Each item is one of:

  ready     an existing course with a check.py — run it now
  legacy    an existing project with templates and solutions but no checker;
            to use it in codecraft it needs a course.py (see scaffold.py)
  author    a course that does not exist yet; author it with `codecraft new`
  salvage   material exists on another git branch; port it first

`prereq` is the honest dependency, not a suggestion. A course can be started
without its prereqs, but the stages assume them.
"""

import re

PHASES = [
    ("A", "Cloud and LLM internals", [
        {"id": "A1", "title": "AWS From Scratch", "course": "aws-from-scratch",
         "kind": "ready", "prereq": [],
         "why": "Eight mechanism families in pure Python, 18 checks. The best "
                "first course: no dependencies, every stage is a real failure mode."},
        {"id": "A2", "title": "LLM From Scratch", "course": "llm-from-scratch",
         "kind": "ready", "prereq": [],
         "why": "BPE, attention, sampling, KV cache, RoPE. 13 checks, pure Python."},
        {"id": "A3", "title": "Context Caching From Scratch", "course": "context-caching",
         "kind": "ready", "prereq": ["A2"],
         "why": "The direct continuation of A2: page, prefix-share, evict the KV "
                "cache without changing the output. 16 checks."},
        {"id": "A4", "title": "ContextCite From Scratch", "course": "contextcite",
         "kind": "ready", "prereq": ["A2"],
         "why": "Which context caused the answer — ablation and a LASSO surrogate. "
                "The eval-flavoured course, and the bridge into RAG. 14 checks."},
        {"id": "A5", "title": "System Design", "course": "system-design",
         "kind": "legacy", "prereq": [],
         "why": "Optional but cheap: caching, queues, idempotency, rate limiting. "
                "Makes sqs/dynamodb in A1 click and underpins the agent half."},
        {"id": "A6", "title": "Dynamo From Scratch", "course": "dynamo-paper",
         "kind": "ready", "prereq": ["A1"],
         "why": "The paper behind DynamoDB, in depth: quorums, hinted handoff, "
                "Merkle anti-entropy. 17 checks."},
        {"id": "A7", "title": "Deploy & Debug", "course": "deploy-and-debug",
         "kind": "ready", "prereq": ["A1"],
         "why": "Capacity math, SLOs, root-causing faults from metrics. The "
                "operations thread that every later course leans on. 12 checks."},
        {"id": "A8", "title": "Autograd From Scratch",
         "course": "autograd-from-scratch", "kind": "ready", "prereq": ["A2"],
         "why": "Built: the engine every training course in this repository "
                "assumes — reverse-mode automatic differentiation over exact "
                "rationals, on a provided forward algebra (`exact.py`) so the "
                "gradients are yours: the graph and its topological order, the "
                "local derivatives, broadcasting and the reduction of a broadcast "
                "gradient, accumulation, the seed of a non-scalar output, detach, "
                "the kink at a tie, the exact finite-difference oracle, and one "
                "training step. Ten checks and 504 planted mutations, no float "
                "anywhere — every gradient is an equal pair and the last stage "
                "reproduces a reference gradient exactly."},
    ]),
    ("B", "RAG", [
        {"id": "B1", "title": "RAG From Scratch", "course": "rag-from-scratch",
         "kind": "ready", "prereq": ["A2", "A4"],
         "why": "Built and ready: chunking, TF-IDF, a vector index, BM25, rank "
                "fusion, reranking, citations, tenant isolation, recall@k. 9 checks."},
        {"id": "B2", "title": "Vector Index From Scratch", "course": "vector-index-from-scratch",
         "kind": "ready", "prereq": ["B1"],
         "why": "Brute force -> IVF -> HNSW, with recall and work measured "
                "against the exact index you built in B1. 10 checks, pure "
                "Python, and the stage that makes 'approximate' mean "
                "something."},
    ]),
    ("C", "Evals and agents", [
        {"id": "C1", "title": "Evals From Scratch",
         "course": "evals-from-scratch", "kind": "ready", "prereq": ["A4"],
         "why": "Datasets, exact/F1 metrics, LLM-as-judge and its calibration, "
                "statistical significance, regression gating. Do this before agents."},
        {"id": "C2", "title": "Agents From Scratch",
         "course": "agents-from-scratch", "kind": "ready", "prereq": ["C1", "B1"],
         "why": "The loop and the transcript that is its state, tool schemas and "
                "validation, errors as observations, parsing what a model actually "
                "writes, retries with idempotent effects, memory bounded by turns, a "
                "filesystem sandbox, an approval gate against injected content, "
                "budgets that stop before the cap, and a state-based audit."},
    ]),
    ("D", "MCP", [
        {"id": "D1", "title": "MCP From Scratch",
         "course": "mcp-from-scratch", "kind": "ready", "prereq": ["C2"],
         "why": "Ten stages, all graded: the JSON-RPC envelope and the spec's error "
                "codes, stdio/SSE/HTTP framing with stdout purity, the lifecycle "
                "handshake and derived capabilities, tools with the protocol-"
                "versus-execution error split, resources and prompts with the "
                "pinned -32002, subscriptions/progress/cancellation, read-only "
                "first with an allowlisted report tool, idempotency keys, a "
                "confirmation that shows the diff, and the trajectory policy with "
                "an audit line that has no clock and no payload. Pinned to spec "
                "revision 2025-06-18."},
    ]),
    ("E", "Harness", [
        {"id": "E1", "title": "Agent Harness From Scratch",
         "course": "agent-harness-from-scratch", "kind": "ready",
         "prereq": ["C2", "D1"],
         "why": "Ten stages, all graded: collect a model's event stream into one "
                "turn, a prompt budget recomputed from the bytes, the loop whose "
                "exhaustion is an outcome, dispatch where an unknown tool is a "
                "message the model can read, streaming with TTFT and inter-token "
                "timings, retries that stop the moment anything was forwarded, "
                "compaction that summarizes the middle and pins the system "
                "message, a trace of six keys and no payloads, a process reward "
                "grounded in the previous result, and a verifier plus a "
                "self-generated data loop measured on held-out tasks. The model "
                "is a callable, the clock is injected, and `time.time` is under a "
                "landmine in the smoke run."},
    ]),
    ("F", "Benchmark and eval", [
        {"id": "F1", "title": "Benchmark From Scratch (Mus)",
         "course": "benchmark-from-scratch", "kind": "ready",
         "prereq": ["C1", "E1"],
         "why": "Ten stages, all graded: the turn gate where a refusal is data and "
                "not a turn, the match loop with as-dealt snapshots and the rails "
                "that stop a run that became about the harness, one ground-truth "
                "record per decision taken BEFORE the action, the link from an "
                "aggression to the answer it got, the strength reference drawn "
                "from the hands that could bet, a risk scorecard where a bluff is "
                "a weak hand and not a lost bet, the outcome that survives the "
                "40-point vaca reset, the calibration and discrimination probes "
                "with their degenerate cases, the gate that decides what may be "
                "published, and the mirrored pair that cancels the seat "
                "advantage. The game is provided (`mus.py`: a Fournier mus table "
                "with the four lances, three bet scales and two reference seats); "
                "the measurement is the exercise. Reference repo: "
                "~/Desarrollo/mus-benchmark."},
        {"id": "F2", "title": "Eval Framework From Scratch",
         "course": "eval-framework-from-scratch", "kind": "ready",
         "prereq": ["F1"],
         "why": "Ten stages, all graded, and the runner rather than the metrics "
                "(phase C1 owns what to measure): a suite config that refuses a "
                "typo instead of running differently from what its author "
                "believed, metric plugins resolved before the first call, one "
                "record per case with an error taxonomy that blames the right "
                "side, budgets checked BEFORE the call, an aggregation whose unit "
                "is the case, a judge asked through a cached and budgeted session "
                "in both orders, records whose bytes two runs share, a gate that "
                "refuses to pass what it cannot evaluate, a baseline diff that "
                "only cries regression when the difference beats the noise, and a "
                "resume that leaves behind the log of an uninterrupted run. The "
                "task set, the actors and the clock are provided (`lab.py`)."},
    ]),
    ("G", "GPU, CPU and the machine stack", [
        {"id": "G1", "title": "Compiler + Virtual GPU", "course": "compiler-and-vgpu",
         "kind": "ready", "prereq": [],
         "why": "One ISA, two machines: assembler, front end, register allocation "
                "with spilling, SIMT divergence. 12 checks. The right first systems "
                "course before real CUDA."},
        {"id": "G2", "title": "CUDA From Scratch", "course": "cuda-from-scratch",
         "kind": "legacy", "prereq": ["G1"],
         "why": "Kernels from vector add to a network. Needs a GPU and a checker "
                "wrapper to join codecraft."},
        {"id": "G3", "title": "CPU From Scratch", "course": "cpu-from-scratch",
         "kind": "ready", "prereq": ["G1"],
         "why": "Ten stages, all graded, on a provided ISA and assembler "
                "(`isa.py`: 29 opcodes in the same family as G1's \u2014 32-bit words, "
                "16 registers, [opcode:6][rd:4][rs1:4][rs2:4][imm:14], plus the "
                "memory sizes, the compares and the flags a datapath needs). Mask a "
                "word and derive the flags; decode an encoding whose unused fields "
                "must not become operands; keep a register file whose zero register "
                "cannot be written and whose snapshots are copies; divide and take "
                "remainders the way hardware does rather than the way Python does; "
                "address bytes with alignment and bounds checked before anything is "
                "stored; fetch and execute with a fault as data and a trace of "
                "effects; then run the same programs on a five-stage pipeline that "
                "must retire the identical trace \u2014 stalling at first, then "
                "forwarding with the one-cycle load-use stall and a branch flush "
                "\u2014 before measuring both machines and reporting the CPI. One "
                "program, two machines, one result."},
        {"id": "G4", "title": "OS From Scratch", "course": "os-from-scratch",
         "kind": "ready", "prereq": ["G3"],
         "why": "Built, and the salvage is part of it: `linux-from-scratch/` (the "
                "curriculum kept from the branch) is the prose, and ten graded "
                "stages are the course, on a provided machine (`machine.py`, "
                "`devices.py`, `userland.py`) whose promises break as soon as a "
                "program does something it should not. The thesis: an operating "
                "system is what you write after the hardware breaks your last "
                "promise. Join a boot map's regions and derive the frames a kernel "
                "may hand out; allocate frames from a bitmap that protects the frame "
                "its own bits live in and answers all or nothing; build page tables "
                "whose entries can never be read as frame numbers and check a "
                "permission bit on every walk, not just on the first; take a fault "
                "as a word a handler decides from rather than an exception; check a "
                "pointer before it is used and write the line that promises the act "
                "before the act; make a process a dict with a space, a ledger and a "
                "zombie at the end, and `fork` copy frames rather than table "
                "entries; pick by priority and age behind a quantum that rotates; "
                "put two CPUs on an interleaving where the critical section is a "
                "lock whose order is checked; format a real on-disk filesystem whose "
                "superblock is written last and mount only what a barrier made "
                "durable; and end on a userland whose kernel report is recomputed "
                "from its own log and cross-checked, key by key, against the "
                "machine's records."},
        {"id": "G5", "title": "C Compiler", "course": "c-compiler",
         "kind": "legacy", "prereq": ["G1"],
         "why": "Lexer, parser, semantic analysis, codegen, optimizer. Templates and "
                "solutions exist; it needs a checker to join codecraft."},
        {"id": "G6", "title": "The C systems set", "course": None,
         "kind": "legacy", "prereq": [],
         "why": "bash-from-scratch, http-server, dns-server, firewall-from-scratch, "
                "toralizer, communication-protocols, cryptographic-library, "
                "quantum-computing-lang. One at a time; each needs a checker."},
        {"id": "G7", "title": "Shell From Scratch", "course": "shell-from-scratch",
         "kind": "ready", "prereq": ["G4"],
         "why": "A shell is what a kernel looks like from the outside: a line of "
                "text becomes a process tree, and every promise G4's kernel makes "
                "is on show — what a child inherits, what a pipe costs, who waits "
                "for whom, and what a signal does to a job. Parse a line into words "
                "and operators; expand variables, tilde, globs and here-documents "
                "in the order a shell must; fork, exec and wait for real exit "
                "codes; build pipes and redirections as a descriptor table before "
                "anything runs; keep a job table that knows a background job from a "
                "stopped one; send signals and reap a child without losing it; and "
                "end on a session the harness replays byte for byte, where `set -e`, "
                "`&&` and a pipeline's exit status are decided by the rules and not "
                "by luck. Author shell-from-scratch against the kernel of G4."},
        {"id": "G8", "title": "Runtime From Scratch", "course": None,
         "kind": "author", "prereq": ["G3", "G4"],
         "why": "A language runtime makes two promises — the program runs, and "
                "memory stops being your problem — and a provided bytecode, "
                "assembler and heap are where you keep both. Execute a stack "
                "machine with calls, frames and exact step accounting; lay out a "
                "heap of objects with headers and references; then collect, in the "
                "order the field settled it: mark and sweep, reference counting "
                "that cannot free a cycle, a tri-colour incremental collector that "
                "must not lose an object the mutator can still reach, write "
                "barriers and a remembered set, a nursery, and a copying collector "
                "that moves objects without breaking a reference. The acceptance is "
                "a program's own output plus its collection counts, and the one "
                "invariant a collector may never break: nothing reachable is ever "
                "collected, and no uncollected frame is ever read. Author "
                "runtime-from-scratch."},
        {"id": "G9", "title": "Coreutils From Scratch",
         "course": None, "kind": "author", "prereq": [],
         "why": "The tools the terminal is made of, each one a byte-oriented "
                "contract: grep is a matcher whose anchors, classes and -v "
                "inversion are decisions, not flags; tail is circulation "
                "over a fixed buffer for -n and a backward scan for -c, and "
                "its -f is a polling loop the harness drives tick by tick; "
                "sort's merge and key spec; wc's count that must be wrong "
                "the same way GNU is wrong when the last line lacks its "
                "newline; and an editor that is a gap buffer, a screen model "
                "of rows and columns over those bytes, and the redraw that "
                "shows exactly the cursor's truth. Each command is judged "
                "byte-for-byte against the real one on provided corpora, the "
                "editor against scripted keystrokes and the frame it must "
                "have drawn. Author coreutils-from-scratch; nothing must "
                "come first \u2014 bytes and integers the whole way."},
        {"id": "G10", "title": "Custom OS in C, End to End",
         "course": None, "kind": "author", "prereq": ["G4", "G5"],
         "why": "The big one, and the only project in this repository where "
                "the acceptance is real hardware obeying you: a bootable x86-64 "
                "kernel in C and a userland on top, built end to end — GRUB or "
                "your own bootloader handing control at the magic number, the "
                "GDT and IDT you write by hand, the PIT and the APIC and the "
                "timer that makes time exist, physical and virtual memory with "
                "the page tables QEMU's `info page-tables` can show you, "
                "interrupts where a keypress becomes a scan code becomes a "
                "character on your own screen, the scheduler you proved as data "
                "in G4 now context-switching for real, the syscall entry with "
                "its privilege ring crossing and the user pointer you must "
                "validate twice, drivers written against the device rather "
                "than a model: the PS/2 controller's ports and its second-byte "
                "wait, the ATA identify and the read sector that polls its "
                "status register, PCI enumeration walking the config space "
                "bus by bus, and the e1000 or virtio NIC whose ring you fill "
                "and whose interrupt you share; a ramdisk and then a real "
                "filesystem on a disk image, an ELF loader so a program you "
                "compiled with G5 runs as a process with its own address "
                "space, fork and exec and wait as real code, and the shell "
                "from G7 speaking to your kernel instead of another's. QEMU "
                "is the judge where the checker can reach (`info registers`, "
                "the serial log, the framebuffer the test draws to); the "
                "real machine is the honest one. The graded path is the "
                "x86-64 stages; the arm64 port is the second half. Author "
                "custom-os-from-scratch in C; G4's simulator is the model, "
                "G5 the toolchain, linux-from-scratch/ the prose."},
        {"id": "G11", "title": "Advanced Algorithms & Data Structures",
         "course": None, "kind": "author", "prereq": [],
         "why": "La Rocca's book mechanised, one stage per chapter, every "
                "structure judged against a work counter and a reference the "
                "way B2 judges HNSW against brute force: priority queues and "
                "d-way heaps measured on Dijkstra (ch. 2), treaps where the "
                "rotation is right because the expected height the profiler "
                "prints agrees with the theory (ch. 3), Bloom filters whose "
                "false-positive rate is measured, not assumed, against the "
                "exact set (ch. 4), disjoint sets by path compression and "
                "union by rank counted in finds (ch. 5), tries and T9 and "
                "autocomplete with the compressed variant (ch. 6), LRU and "
                "LFU caches with the hit rate the workload produces (ch. 7), "
                "k-d trees whose nearest neighbour is checked against the "
                "linear scan it must beat (ch. 8\u20139), SS-trees and "
                "approximate search with the recall the book's own image "
                "retrieval asks for (ch. 10\u201311), DBSCAN and OPTICS "
                "clustering on the points the reference clusters identically "
                "(ch. 12\u201313), graphs from BFS and connected components "
                "to Dijkstra and minimum spanning trees (ch. 14), graph "
                "embeddings, planarity and the force-directed drawing whose "
                "crossings the checker counts (ch. 15), then gradient "
                "descent (ch. 16) and simulated annealing (ch. 17) as "
                "optimisation on those graphs, and the genetic algorithm "
                "that closes the book on TSP, its tours compared against "
                "the branch-and-bound answer on the small instances (ch. "
                "18). Author advanced-dsa-from-scratch in pure Python with "
                "no float where a counter suffices \u2014 nothing must come "
                "first; the book is the reading, the checker the grade."},
        {"id": "G12", "title": "SQLite From Scratch",
         "course": None, "kind": "author", "prereq": ["G9"],
         "why": "The database embebida, from the recovered codecrafters corpus "
                "(codecrafters-reference/sqlite/, nine stages with the tester's "
                "own commands): a real single-file database that `sqlite3` "
                "itself opens. Parse the database header and walk the schema "
                "table whose rows are the other tables; decode a table B-tree "
                "page by page — cell pointer array, varints, overflow pages — "
                "until `SELECT` over your file returns the rows sqlite3 "
                "returns; build the record format serial types and the "
                "freelist; then the write half: the WAL, the commit that is "
                "not acknowledged before the WAL says so, and the crash that "
                "loses nothing. The judge is sqlite3 itself reading what you "
                "wrote and the row counts matching on the files both wrote. "
                "H5 is the query engine; this is the storage layer it runs "
                "on, done for real. Author sqlite-from-scratch."},
        {"id": "G13", "title": "Regex From Scratch",
         "course": None, "kind": "author", "prereq": [],
         "why": "The one language every tool in phase G already assumes, taught "
                "by building the engine twice: Thompson's construction first — "
                "parse with the shunting yard, compile to an NFA whose states "
                "are epsilon-closures, simulate in linear time — then the "
                "backtracking engine, whose catastrophic cases (`(a+)+$`) the "
                "work counter exposes by the seconds it burns where the NFA "
                "spent microseconds. Character classes, anchors, quantifiers "
                "greedy and lazy, groups and backreferences the NFA refuses "
                "(and why PCRE pays for them), then the integration that "
                "gives the course its teeth: grep (G9) re-derives its -E from "
                "this engine, tail -f's scrollback filter and G7's shell "
                "globs borrow the same compile step, and the judge is the "
                "match sets agreeing with Python's `re` on a corpus built to "
                "distinguish the two engines. Author regex-from-scratch; "
                "nothing must come first."},
        {"id": "G14", "title": "Reverse Engineering",
         "course": None, "kind": "author", "prereq": ["G3", "G5"],
         "why": "The discipline of reading a program you do not have the "
                "source for, taught on binaries you can verify: the ELF and "
                "PE formats as data \u2014 headers, sections, symbols, "
                "relocations \u2014 parsed until `readelf` and yours agree; "
                "x86-64 disassembly with the length-decoding problem that "
                "makes it not just a table (prefixes, ModRM, the cases "
                "where data is code and back); the calling conventions and "
                "the stack frame reconstructed from prologues; control-flow "
                "recovery \u2014 the CFG from a linear sweep and the "
                "recursive descent and where they disagree; the "
                "decompilation lift to a C-like IR and what it always gets "
                "wrong; then the dynamic half: the ptrace attach, "
                "breakpoints, the memory dump, the syscall trace that tells "
                "you what the binary does when the static reading lies; "
                "strings, imports and the entropy profile that finds the "
                "packed sections; and the capstone, a crackme and a stripped "
                "binary from the provided estate, where the licence check "
                "must be found, understood and described \u2014 the judge "
                "being the write-up whose every claim (function boundaries, "
                "the key derivation, the anti-debug trick) is checked "
                "against ground truth the estate carries. Built with the "
                "tools, not around them: objdump, gdb, radare2 are the "
                "reference outputs your own parser and lifter are checked "
                "against. Author reverse-engineering-from-scratch; G3 built "
                "the CPU, G5 built the compiler \u2014 this reads what they "
                "emit, without the source."},
    ]),
    ("H", "The rest", [
        {"id": "H1", "title": "Distributed Training",
         "course": "distributed-training-from-scratch",
         "kind": "ready", "prereq": ["A2", "I9"],
         "why": "Built: the plans on top of I9's collectives, on a fabric copied "
                "verbatim and a model handed to you. A step as a plan with its bytes "
                "per rank and its memory ledger, DDP's bucketed all-reduce hidden "
                "behind the compute, ZeRO's ladder (4 + 12/N, then 2 + 2/N + 12/N), "
                "FSDP's per-unit gather and scatter and its 4P(N-1)/N peak, tensor "
                "parallel's two all-reduces per block, GPipe vs 1F1B and the bubble "
                "replayed from the slots, interleaving's (p-1)/(m*v+p-1), the expert "
                "all-to-all with its routing table and capacity cap, ring attention's "
                "exact running pivot, and the configuration whose report is "
                "recomputed from the plan it chose. 10 checks, 554 mutations caught, "
                "no float anywhere."},
        {"id": "H2", "title": "Inference and serving", "course": None,
         "kind": "salvage", "prereq": ["A3"],
         "why": "Superseded by phase I, which is this list as a twelve-stage spine: "
                "vllm-engine, sgl-lang and tensorrt-inference are I3, I6 and I5 there. "
                "ml-inference lives here; three of the four are README-only on main, "
                "and an inference-from-scratch set exists on a branch."},
        {"id": "H3", "title": "Generative models", "course": None,
         "kind": "legacy", "prereq": ["C1"],
         "why": "diffusion-models, world-models (10k lines of PyTorch), deepfake "
                "creation and detection."},
        {"id": "H4", "title": "Long tail", "course": None, "kind": "legacy", "prereq": [],
         "why": "quantitative-trading, spectral-graphs, lean-proofs, haskell-projects, "
                "mlops, ml-in-production, sas-lineage-tool, web-scraping."},
        {"id": "H5", "title": "Query Engine From Scratch", "course": None,
         "kind": "author", "prereq": ["G4"],
         "why": "A database is a file format plus a promise about what a query "
                "returns. A heap file of pages on a disk that can lose what was not "
                "synced, a catalog, and tables to query are provided. Parse a SQL "
                "subset into a tree; resolve names against a catalog that may be "
                "wrong; plan it — predicate pushdown, join order, an index chosen or "
                "refused; execute with iterators over a page buffer and a B+tree you "
                "split yourself; make a transaction a log and a commit a rule; and "
                "prove it: the same rows as the reference for a hundred queries, a "
                "plan that uses the index only when the predicate earns it, and a "
                "crash schedule where the log decides which tuples exist. Author "
                "query-engine-from-scratch; G4 is the format and the barrier, and A6 "
                "is the distributed half this repo already has."},
        {"id": "H6", "title": "Consensus From Scratch", "course": None,
         "kind": "author", "prereq": ["J3", "I9"],
         "why": "Consensus is the one thing a replicated system cannot fake: a "
                "leader is a number a majority agreed on, and a log entry is "
                "committed when a majority holds it. Five nodes, a deterministic "
                "network with partitions and delays, a clock, and durable storage "
                "that can lose its last write are provided. Elect a leader with "
                "terms and votes; replicate a log whose entries match term by term; "
                "commit only what a majority holds and refuse a stale leader; keep a "
                "membership change safe; snapshot a log without losing a committed "
                "entry; and recover a node whose disk lied. The acceptance is a "
                "linearizability check over the history the world itself recorded, "
                "plus a partition schedule on which the wrong implementation splits "
                "the brain. Author consensus-from-scratch; J3 is durability and I9 "
                "is the fabric."},
        {"id": "H7", "title": "Compression From Scratch", "course": None,
         "kind": "author", "prereq": [],
         "why": "A compressor is a byte format you can be exactly wrong about, and "
                "it is judged on a ratio: Huffman with canonical codes and a length "
                "limit; LZ77's window and why its size is the whole trade; LZ4's "
                "block format with its nibble lengths; DEFLATE bit by bit — dynamic "
                "trees, the matched pairs, the end-of-block symbol, and the "
                "stored/static/dynamic choice per block; then FSE/ANS with a table "
                "you build, and a frame with a real header and a checksum. The "
                "reference decoders (inflate, LZ4, a zstd-compatible frame reader) "
                "and the corpora are provided. A stage passes when the decoder "
                "accepts your bytes and the ratio clears the bar, and the tester "
                "flips one bit to see whether the checksum you wrote notices. Author "
                "compression-from-scratch; nothing to read first — it is bytes and "
                "integers the whole way."},
        {"id": "H8", "title": "Multi-Region Failover", "course": None,
         "kind": "author", "prereq": ["A6", "H6"],
         "why": "A replica is not a strategy until you have failed it over: the "
                "region that answers has to be a decision with a rule, the write "
                "that arrived late has to be reconciled rather than guessed at, "
                "and the RTO you claim has to be a number your own drill "
                "produced. Two simulated regions with independent clocks, a link "
                "that drops for a chosen window, and clients with pinned sessions "
                "are provided. Write the health signal that is not a heartbeat, "
                "the promotion rule with both of its halves — H6's quorum and "
                "A6's hinted handoff and Merkle anti-entropy — the redirect that "
                "does not apply a write twice, and the report that states RTO and "
                "RPO as measured, with the writes it lost named. Author "
                "failover-from-scratch; A6 and H6 are the two halves it joins."},
    ]),
    ("I", "Inference engineering: from silicon to serving", [
        {"id": "I1", "title": "Systems & GPU Foundations", "course": "compiler-and-vgpu",
         "kind": "ready", "prereq": ["G1"],
         "why": "The silicon half: thread blocks, warps and SIMT divergence are G1's "
                "12 checks; then author gpu-architecture-from-scratch for the memory "
                "hierarchy (banks, coalescing, TLB, PCIe vs NVLink) and the matmul "
                "kernel, as a simulator plus a roofline, with the CUDA/cuBLAS profile "
                "as the runbook. C++ and Rust belong here too: one kernel each, "
                "compiled, so the toolchain is not a mystery."},
        {"id": "I2", "title": "Transformer Inference Physics", "course": None,
         "kind": "author", "prereq": ["A2", "I1"],
         "why": "Prefill vs decode as two different machines, arithmetic intensity, "
                "the KV-cache equation, and where tokens/second actually comes from. "
                "Author inference-physics-from-scratch: a cost model that predicts "
                "TTFT and ITL from config alone, checked against measured traces — "
                "the offline stand-in for Nsight Systems."},
        {"id": "I3", "title": "Modern Serving Engines & Batching", "course": None,
         "kind": "author", "prereq": ["I2", "A3"],
         "why": "vLLM, SGLang, PagedAttention, continuous batching, chunked prefill. "
                "vllm-engine/ and sgl-lang/ are README-only on main; A3 already builds "
                "paged KV with copy-on-write, so this course authors the scheduler: "
                "admission, prefill/decode mixing, chunk sizing, and the starvation "
                "curve a throughput number hides."},
        {"id": "I4", "title": "KV-Cache & Memory Optimization", "course": "context-caching",
         "kind": "ready", "prereq": ["A3"],
         "why": "Prefix and radix reuse, semantic routing and eviction are A3's 16 "
                "checks. The missing half (KV quantization, CPU offload, multi-turn "
                "reuse across sessions, a KV-affinity routing proxy) is what "
                "kv-cache-ops would add on top."},
        {"id": "I5", "title": "Quantization & Compression", "course": None,
         "kind": "salvage", "prereq": ["I2"],
         "why": "FP8, INT4, AWQ, GPTQ, sparsity and calibration. tensorrt-inference/ is "
                "README-only; author quantization-from-scratch: scales and zero points, "
                "per-channel vs per-tensor, KL calibration, and the quality/latency/VRAM "
                "trade-off measured on a tiny model instead of promised."},
        {"id": "I6", "title": "Kernel-Level Engineering", "course": None,
         "kind": "author", "prereq": ["G1", "I2"],
         "why": "Triton, FlashAttention, CUDA graphs, fusion. sgl-lang/ is README-only; "
                "author kernels-from-scratch: tiling and online softmax by hand in "
                "Python, then a small Triton-shaped IR with a fusion pass and a "
                "launch-overhead model. The fused RMSNorm/softmax benchmark becomes a "
                "check that the fused path is bit-identical and cheaper."},
        {"id": "I7", "title": "Distributed Inference & Parallelism", "course": None,
         "kind": "author", "prereq": ["I3", "I9"],
         "why": "Tensor, pipeline and expert parallelism: how a 405B model is cut, "
                "what each cut costs, and why the comms hide behind the compute or do "
                "not. Author distributed-inference-from-scratch: shard one model "
                "across N simulated ranks, schedule the pipeline, dispatch the experts, "
                "and measure the volume on a modelled interconnect."},
        {"id": "I8", "title": "Speculative Decoding", "course": None,
         "kind": "author", "prereq": ["I2"],
         "why": "Draft-target, Medusa heads, n-gram drafting, acceptance rates, and the "
                "KV bookkeeping that makes rejection cheap. Author "
                "speculative-decoding-from-scratch: pure Python, offline, with the "
                "acceptance-rate math and the '2x at zero quality cost' claim made "
                "checkable rather than repeated."},
        {"id": "I9", "title": "Multi-Node & Hardware Interconnects",
         "course": "interconnects-from-scratch",
         "kind": "ready", "prereq": ["G3", "J1"],
         "why": "Built and ready: NCCL's model in code — what a byte costs on a "
                "link, the ring and the tree all-reduce and the size where each "
                "wins, recursive doubling with the one-hop partners it actually "
                "needs, all-gather and reduce-scatter as first-class collectives, "
                "the all-to-all whose offsets depend on the data, group semantics "
                "and full-duplex links, the lower bound that decides an algorithm, "
                "and one training step's collectives laid over four parallelism "
                "axes and overlapped with compute as a max. Deterministic and "
                "in-process over a provided fabric (links with bandwidth and "
                "latency, four topologies, an executor): a collective is a plan "
                "whose correctness and whose price are checked separately, with "
                "438 planted mutations behind the ten checks. The "
                "prerequisite for H1, the distributed-training course."},
        {"id": "I10", "title": "Cluster Orchestration & GPU Scheduling", "course": None,
         "kind": "author", "prereq": ["A7", "I3"],
         "why": "Kubernetes GPU operators, Ray, Slurm, MIG partitioning, KEDA. "
                "deploy-and-debug/ already grades rollout and capacity math; author "
                "gpu-scheduling-from-scratch: a scheduler simulator with MIG slices, "
                "queue-based autoscaling, spot preemption, and the cost model that "
                "makes an idle H100 a bug."},
        {"id": "I11", "title": "AI Gateways, Routing & Observability", "course": None,
         "kind": "author", "prereq": ["A7", "I5"],
         "why": "TTFT/ITL SLOs, complexity routing, DCGM metrics, OpenTelemetry for "
                "LLMs. Author ai-gateway-from-scratch: a router that sends the cheap "
                "query to the quantized local model and the hard one upstream, with the "
                "SLO, the percentile pipeline and a throttling detector as graded "
                "checks. A3's routing and A7's percentiles are the two halves it "
                "joins."},
        {"id": "I12", "title": "Public Benchmarks & Teardowns", "course": None,
         "kind": "author", "prereq": ["F1", "I3"],
         "why": "Reproducible methodology, latency/throughput Pareto curves, "
                "cost-per-token. F1/F2 own the measurement machinery; "
                "inference-benchmark-from-scratch is the teardown: capture the full "
                "config, sweep the knobs, plot the frontier, pin cost per token to a "
                "price, and fail the run when a config is missing."},
        {"id": "I13", "title": "Serving Cluster From Scratch", "course": None,
         "kind": "author", "prereq": ["I3", "I7", "I10"],
         "why": "The last mile of serving is not a model, it is a cluster that "
                "stays ready: a supervisor that brings a rank back without "
                "losing the mesh, readiness that means the weights are in VRAM "
                "rather than the process is alive, and a drain that finishes the "
                "requests it already accepted instead of dropping them at the "
                "load balancer. A node simulator with health probes, a sharded "
                "weight store and a client fleet that measures what it saw are "
                "provided. Write the bring-up order, the liveness/readiness "
                "split, the rolling upgrade that never drops a request, the "
                "retry budget at the edge rather than per call, and the latency "
                "report the cluster publishes about itself — TTFT and ITL "
                "percentiles per node, with the node that failed the drill named. "
                "Author serving-cluster-from-scratch; I3, I7 and I10 are its "
                "parts."},
        {"id": "I14", "title": "Model Weight Delivery", "course": None,
         "kind": "author", "prereq": ["I3", "I7"],
         "why": "Cold starts are usually a storage problem wearing compute "
                "clothes: getting the right shard onto the node is the bring-up "
                "cost, and every byte fetched eagerly is paid again on every "
                "replica. A content-addressed store of safetensors-shaped "
                "shards, a node with a fixed disk and a clock, and a client that "
                "reports only bytes and time are provided. Write the manifest and "
                "its digests, the shard-to-rank map, the lazy load with a "
                "prefetch order derived from the first tokens, the CDN layer "
                "whose cache key is the digest and whose invalidation is a new "
                "digest, and the measurement that says which of those actually "
                "cut cold start — bytes fetched, time to first token, cache hit "
                "rate per node. Author weight-delivery-from-scratch; I3 says what "
                "the node needs and I7 says how it was cut."},
    ]),
    ("J", "Agent infrastructure", [
        {"id": "J1", "title": "Queue & Workers",
         "course": "queue-and-workers-from-scratch",
         "kind": "ready", "prereq": ["C2", "A7"],
         "why": "Built and ready: a task queue and a worker pool as data "
                "structures, deterministic and in-process, with the clock "
                "injected — typed specs that refuse a typo instead of defaulting "
                "it, admission that counts running work and refuses instead of "
                "growing, priority as a total order, the concurrency limit "
                "checked before a worker runs, leases that reclaim the task a "
                "dead worker was holding, backoff and dead letters on that same "
                "clock, refuse/shed/block backpressure, ageing, and a record "
                "rebuilt from the run's own log rather than declared. 10 checks, "
                "no threads and no floats."},
        {"id": "J2", "title": "Multi-Agent Orchestration",
         "course": "orchestration-from-scratch",
         "kind": "ready", "prereq": ["J1", "C2"],
         "why": "Built and ready: a big task as a graph of small ones, and the "
                "graph as data. Subtasks that refuse a typo instead of "
                "defaulting it, the edge set and the waves a cycle would break, "
                "a schedule decided by the states rather than by the wave, the "
                "handoff that carries exactly a child's own dependencies' "
                "accepted results (each cut to the budget that dependency "
                "declared), a reviewer who can reject and a rework that carries "
                "the reason and stops at MAX_REWORK, one failure that skips its "
                "transitive dependents without running them, an effect held "
                "until its approval is answered rather than after it lands, the "
                "call a budget cannot pay for refused before it happens, and a "
                "record of seven kinds and no payload text with a report "
                "recomputed from it — two runs of one fixture, identical bytes. "
                "10 checks and 526 mutations caught, on J1's clock and a scripted "
                "fleet: no threads, no model, no floats."},
        {"id": "J3", "title": "Durable Execution",
         "course": "durable-execution-from-scratch",
         "kind": "ready", "prereq": ["J1"],
         "why": "Built and ready: a run as a log rather than a process. The line "
                "and the journal that holds it, the write that was not synced "
                "and the sync that makes it a fact, replay with the half-written "
                "tail refused rather than guessed at, a lease whose deadline is "
                "derived from the line and whose owner is named, the heartbeat "
                "and the grace that separate *expired* from *dead*, a crash that "
                "replays only what the disk would keep and writes the lines the "
                "dead owners' jobs owe, an effect that happens exactly once "
                "because its intent is synced before it runs, a checkpoint and a "
                "resume that refuses another run's log by name, a report whose "
                "every counter is recounted from the lines, and a capstone that "
                "kills one worker holding a lease in the middle of the run and "
                "still lands on the same states as the run nobody killed. "
                "10 checks and 558 mutations caught, on a disk that loses "
                "everything it was not told to sync: no threads, no filesystem, "
                "no floats."},
        {"id": "J4", "title": "Sandbox & Capabilities",
         "course": "sandbox-capabilities-from-scratch", "kind": "ready",
         "prereq": ["C2", "D1"],
         "why": "Control what an agent can touch, on a world made of data: a "
                "capability per tool that is declared, granted and then "
                "intersected rather than inferred, a principal's grant whose "
                "answer is the missing difference and never a boolean, a path "
                "jail that resolves before it decides and refuses the sibling "
                "root a prefix test hands over, a network policy of exact "
                "host:port specs with no wildcard a reader cannot evaluate, "
                "cpu/memory/ticks limits charged all or nothing before the work, "
                "secrets that reach the model as a fingerprint and leak in none "
                "of four encodings, an audit line per call with a closed reason "
                "vocabulary written before the act, the six questions decided in "
                "one order with a denial that touches nothing and spends "
                "nothing, a report recomputed from the lines and cross-checked "
                "against the filesystem's, the wire's and the vault's own "
                "records, and a capstone whose answer to 'what did it touch' is "
                "its audit and not its plan. 10 checks and 494 mutations caught, "
                "with no filesystem, no socket and no float: C2's real path jail "
                "and D1's read-only-first policy are its two parts."},
        {"id": "J5", "title": "Observability & Metrics",
         "course": "agent-metrics-from-scratch", "kind": "ready",
         "prereq": ["J1", "A7"],
         "why": "A trace is not a metric, over a fleet that records its own "
                "events: a twelve-field event whose kind decides which of them "
                "mean anything, a half-open window that makes a tumbling set a "
                "partition and refuses an inclusive end, queue depth as a gauge "
                "derived from a state machine over the five kinds and never "
                "summed, a percentile as a nearest-rank index over exact integers "
                "with no float and no interpolation, latency split into the wait, "
                "the service and the retry gap with the identity asserted, tokens "
                "and micros summed before they are divided and priced by the pool "
                "that ran the task, failure and retry rates that name their own "
                "denominators and answer floored basis points, windows whose step "
                "may not leave a hole, a report recomputed from the events and "
                "cross-checked key by key against the fleet's own count of the "
                "same run, and a capstone whose budget is spent by the size of an "
                "overshoot and whose alert names the window that spent the last "
                "of it. 10 checks and 510 mutations caught, with no float, no "
                "library statistics and no clock but the injected tick: E1's "
                "six-key trace is the input and A7's percentile pipeline is the "
                "other half."},
    ]),
    ("K", "Applied AI engineering", [
        {"id": "K1", "title": "Agentic Retrieval",
         "course": "agentic-retrieval-from-scratch", "kind": "ready",
         "prereq": ["B1", "B2", "C2"],
         "why": "Retrieval that checks itself, as ten stages against a corpus "
                "whose ground truth is data (clauses, cross-references, a "
                "duplicated clause number and a superseded document): chunk a "
                "document and name what is odd, size the index of a "
                "ten-million-document estate against a budget, score lexically "
                "and semantically and fuse the two rankings, make a reranker "
                "earn its place against the noise, rewrite a question whose "
                "referent lives only in the conversation, critique what came "
                "back, decide grounded-or-abstain with a citation per claim, run "
                "the loop under a budget that stops for a reason it names, price "
                "the checking against the naive retrieve-and-answer, and "
                "diagnose the customer's own twelve failures without reading the "
                "label they carried. 10 checks and 589 mutations caught, with no "
                "float, no library statistics and no clock but the injected "
                "tick: B1's fusion and reranking and B2's recall accounting are "
                "its parts, and the judgement about them is what it adds."},
        {"id": "K2", "title": "Prompt & Routing Ops", "course": None,
         "kind": "author", "prereq": ["E1", "F2", "J1"],
         "why": "A prompt and a model choice as versioned artifacts: a typed "
                "triage router with a measured escalation rate, shadow mode "
                "mirroring a fraction of traffic and diffing trajectories and "
                "costs, a rollout/rollback gate, the cost kill-switch and the "
                "degradation chain frontier → mid → local → cache. Author "
                "prompt-ops-from-scratch; F2's gate and baseline diff and E1's "
                "six-key trace are its halves."},
        {"id": "K3", "title": "Memory Engine", "course": None,
         "kind": "author", "prereq": ["E1", "B2"],
         "why": "The three tiers as data structures: a working scratchpad with a "
                "hard budget, episodic summaries with a consolidation rule, a "
                "semantic store with importance scoring and eviction, and recall "
                "measured over a long conversation. Author "
                "memory-engine-from-scratch; E1's compaction is the one-tier "
                "version of exactly this."},
        {"id": "K4", "title": "Fine-Tuning", "course": None,
         "kind": "author", "prereq": ["A8", "C1"],
         "why": "LoRA and preference tuning over A8's exact engine: the "
                "low-rank update and why it trains, a 5K-example budget that "
                "refuses a plan it cannot pay for, DPO preference pairs built "
                "from recorded failures, and the decision itself — fine-tune, "
                "RAG or prompting — defended against a number. Author "
                "fine-tuning-from-scratch; C1 is how the result is judged."},
        {"id": "K5", "title": "Privacy & Injection", "course": None,
         "kind": "author", "prereq": ["C2", "D1", "J2"],
         "why": "What leaves the process and what may come back: a gateway that "
                "tokenizes sensitive values before the context window and "
                "restores them after, an audit line that answers 'what did it "
                "touch', per-agent least privilege and scoped tool sets, and the "
                "sanitization of one agent's output before it becomes another's "
                "input. Author agent-privacy-from-scratch; J4 is the sandbox "
                "half and this is the data-in-transit half."},
        {"id": "K6", "title": "Forward Deployed Engineer",
         "course": "fde-from-scratch", "kind": "ready",
         "prereq": ["B1", "C1", "D1", "J4"],
         "why": "The twelve skills an FDE is hired for, as twelve stages against a "
                "customer that is data: the assertion, the session and the row; a "
                "deployment that cannot reach out; an invoice feed reconciled into a "
                "hybrid store; a retriever that filters before the limit; the legacy "
                "system as tools with the credential staying in the vault; PII masked "
                "on the way out and restored on the way back; a workflow that stops "
                "at a person and journals the decision; the model that fits the GPU "
                "somebody else owns; the AI's work counted in hours and cents; the "
                "customer's own tickets run in shadow and answered with one verdict; a "
                "vague ask turned into a scoped four weeks; and a runbook drilled "
                "against armed faults, handed to an admin who is not you. Built as "
                "`fde-from-scratch`: twelve stages over a provided `estate.py`, "
                "`network.py` and `meter.py` — the customer's directory, its basement "
                "and its meter — where every claim is held against the world's own "
                "log and no stage may write it. B1 is the retriever this course makes "
                "refuse a row, C1 the harness it points at the customer's tickets, D1 "
                "the protocol behind its tools, and J4 the discipline its credentials "
                "follow."},
    ]),
    ("L", "Programs that talk", [
        {"id": "L1", "title": "TCP/IP From Scratch",
         "course": "tcp-ip-from-scratch", "kind": "ready", "prereq": ["G3", "J4"],
         "why": "The stack as data, from the first of the three series kept in "
                "`NETWORKING.md`: a frame and its type field, ARP and a cache "
                "that ages, IPv4 with a routing table and a TTL that has to be "
                "decremented, ICMP echo and a checksum recomputed over the "
                "header, the handshake as a state machine, the sliding window "
                "that must not be overrun, the socket API as a table, "
                "retransmission on the injected clock, the close with TIME_WAIT "
                "as a state rather than a sleep, and a session whose tie-breaker "
                "is the wire's own segment log. Ten stages against a provided "
                "lossy `wire.py`; G3 is the house's example of a simulator a "
                "course is written against, and J4 is the method: the world "
                "keeps the record."},
        {"id": "L2", "title": "Concurrent Servers",
         "course": "concurrent-servers-from-scratch", "kind": "ready",
         "prereq": ["J1", "J3"],
         "why": "Four models for one server, from the second series: a blocking "
                "server and the one slow client that stops everyone, "
                "thread-per-connection over J1's scheduler with the interleaving "
                "the check chooses, a reactor whose readiness is a set and whose "
                "poll loop never busy-waits, the event loop with a monotonic "
                "timer queue, callbacks as a handle table with cancellation, "
                "futures and async/await as a desugaring, backpressure and "
                "head-of-line blocking, the Redis case study as a command loop, "
                "and one workload through all four models with identical answers "
                "and a counted number of scheduler steps. Ten stages against a "
                "provided `link.py` — the world whose own log every claim of "
                "every model is held against, and which no model writes — over "
                "J1's `fleet.py` copied byte for byte; J1 is the queueing half "
                "and J3 is the durability half of the same problem."},
        {"id": "L3", "title": "MQTT Broker", "course": "mqtt-broker-from-scratch",
         "kind": "ready", "prereq": ["L1", "J4"],
         "why": "The wire format itself, from the third series: the fixed header "
                "and its variable-length integer, CONNECT and the session flags, "
                "a topic trie where `+` and `#` are matched by components and "
                "never by prefix string, QoS 1 as state (the packet id, the "
                "PUBACK, the redelivery deadline), QoS 2 as a four-way handshake "
                "and why an id may not be reused before PUBCOMP, retained "
                "messages and the last will, a session that survives a "
                "reconnect, and a trace replayed twice byte-identically with "
                "every frame the broker wrote accepted by the course's own "
                "reader. Built as `mqtt-broker-from-scratch`: ten stages against "
                "a provided `streams.py` — the byte-pipe transport whose `send` "
                "returns what it took, whose `step()` is the only thing that "
                "moves a byte or a tick, and whose own log and `stats()` every "
                "number of the broker's report is held against — and a provided "
                "`grants.py`, the policy table with six reasons whose decision "
                "line is written before the act it allows. L1 is the framing half "
                "of a wire, and J4 is the policy that decides who may publish "
                "where."},
        {"id": "L5", "title": "Redis From Scratch", "course": None,
         "kind": "author", "prereq": ["L2", "J3"],
         "why": "The in-memory store whose protocol is the lesson: RESP byte by "
                "byte, the command table a dict of (arity, handler) that refuses "
                "an arity it does not name, the store as a dict with per-key "
                "expiry where a lazy pass on read and an active cycle on the "
                "clock both evict, and an RDB the course parses byte by byte "
                "before it writes one. Then the hard half: AOF as a journal "
                "whose every line is a prediction until fsync makes it a fact "
                "(J3's discipline, at the file's mercy), and leader-follower "
                "replication where the follower's acknowledgement is state the "
                "leader keeps and the offset is the number both sides agree on. "
                "Accepted on a session the harness replays byte for byte, with "
                "the world's own RESP reader as the referee. Source: the "
                "124-stage CodeCrafters corpus in `codecrafters-reference/redis/`."},
        {"id": "L6", "title": "Kafka From Scratch", "course": None,
         "kind": "author", "prereq": ["L2", "J1"],
         "why": "The log as the product: the fetch/produce request envelopes of "
                "the real protocol, a partition as an append-only log with an "
                "offset cursor per consumer group, and the delivery contract "
                "decided, not assumed — at-least-once through redelivery "
                "deadline and dedup by id, at-most-once by committing the "
                "cursor before the work, exactly-once by idempotent producer "
                "sequence numbers. L2 is the framing half of a wire and J1 is "
                "the queue whose delivery semantics this course makes the "
                "broker's own decision. Source: the 25-stage CodeCrafters "
                "corpus in `codecrafters-reference/kafka/`."},
        {"id": "L7", "title": "Docker From Scratch", "course": None,
         "kind": "author", "prereq": ["G4", "J4"],
         "why": "A container is isolation you can name: a chroot whose root "
                "is an overlay of layers, a PID and network and mount namespace "
                "the process is born into, cgroups that charge CPU and memory "
                "all or nothing, and capabilities that decide what the process "
                "may still do — the image as a stack of layers addressed by "
                "digest, `pull` resolving a manifest, `run` building the mount "
                "table before the exec, and a health check the container "
                "answers about itself. The namespaces are G4's process table "
                "made real and the capability gate is J4's, applied to a "
                "process that actually runs. Source: the 6-stage CodeCrafters "
                "corpus in `codecrafters-reference/docker/`, mocker and bocker "
                "in `tutorials-reference/`."},
        {"id": "L8", "title": "Emulator From Scratch", "course": None,
         "kind": "author", "prereq": ["G3"],
         "why": "A machine implemented by being another machine: the CHIP-8's "
                "35 opcodes decoded from bytes, a memory map where the font "
                "lives where the spec says it lives, a display the emulator "
                "owns as a bitmap, and two timers the program cannot read a "
                "tick of but which everyone can see count down — then the "
                "second machine on the same discipline, where a cycle is not "
                "a step but a number of them and the ROM's behaviour is the "
                "judge. G3 is the datapath habit; here the *programs* are "
                "provided (the ROMs) and their accepted behaviour is the "
                "answer key. Source: the CHIP-8 tutorials in "
                "`tutorials-reference/chip8-python/` and the LC-3 VM."},
        {"id": "L9", "title": "RL Control From Scratch", "course": None,
         "kind": "author", "prereq": ["A8"],
         "why": "Control as arithmetic over a value function: a world that is "
                "a Markov chain you can step (a gridworld, a gambler, a "
                "random walk — deterministic, seeded, its optimal policy "
                "computable by hand), then the estimation of that policy from "
                "experience alone — dynamic programming first, because the "
                "answer key is checkable, then Monte-Carlo returns and their "
                "first-visit variance, TD(0) and the bootstrapping that makes "
                "it biased, SARSA against Q-learning and what off-policy "
                "costs, a function approximator over A8's exact autograd "
                "engine for the state the table cannot hold, and a report "
                "whose every number (returns, regret, the policy's own "
                "actions) the world can recompute. Source: RL-from-zero and "
                "dennybritz's notebooks, in `tutorials-reference/`."},
        {"id": "L4", "title": "Git From Scratch", "course": None,
         "kind": "author", "prereq": ["G4"],
         "why": "The one artefact in this repository that another program "
                "validates: a `.git` directory that real `git` reads. Blobs "
                "addressed by their own digest, trees whose entries are sorted and "
                "whose modes are exact, a commit with an author, a message and a "
                "parent, refs and a HEAD that can be detached; then the half that "
                "makes it a tool — an index that stages, a diff that names a hunk, a "
                "merge that finds the base and marks a conflict instead of guessing, "
                "and a packfile whose objects are delta-compressed and whose index "
                "lets a random read land without walking the file. A byte-oriented "
                "filesystem and a git-compatible reader are provided, and where "
                "`git` is on PATH the tester runs it: `git fsck` and `git log` have "
                "to accept your objects. Author git-from-scratch; G4 is the "
                "format-and-barrier course."},
    ]),
    ("M", "Banking and credit risk", [
        {"id": "M1", "title": "Credit Lifecycle",
         "course": "credit-lifecycle-from-scratch", "kind": "ready",
         "prereq": [],
         "why": "The arithmetic a bank runs over a loan's whole life: the "
                "contractual schedule and the effective interest rate that "
                "discounts it, the delinquency buckets and the new definition of "
                "default (the 90-days-past-due backstop, the unlikeliness-to-pay "
                "indicators, the materiality threshold and the cure period), PD "
                "from an observed rating migration matrix and the lifetime PD "
                "built from it, LGD from the recovery cash flows discounted to the "
                "default date, EAD and the credit conversion factor on what is "
                "undrawn, the ECL as PD times LGD times EAD discounted at the "
                "effective rate and weighted over the given scenarios, IFRS 9's "
                "three stages with the significant-increase-in-credit-risk test, "
                "the provision roll-forward with its P&L and OCI split, the "
                "reporting pack the bank files (exposures by stage, rating and "
                "past-due bucket, coverage ratios, forbearance, vintage and "
                "migration matrices) and the backtesting of PD and LGD against "
                "what actually happened. Built over a provided `book.py`, "
                "`dates.py` and `rules.py` — a twelve-loan book, thirty-six "
                "reporting dates, three model artifacts and the policy as data, "
                "with integer basis points everywhere, which is accounting's own "
                "fixed point and needs no float and no library. 10 checks and 643 "
                "mutations caught, against a world pinned by 9417 of its own "
                "facts: the bank's records are the answer key every stage is "
                "graded against."},
        {"id": "M0", "title": "Credit Origination",
         "course": None, "kind": "author", "prereq": [],
         "why": "Before a loan exists it is an application, and the bank's "
                "first arithmetic is a decision: the applicant as facts "
                "(income, obligations, collateral, history) on a provided "
                "estate that is the ground truth, the affordability ratio "
                "and the debt-service math that says whether the payment "
                "fits, the application scorecard — weight, points, cutoff — "
                "as a table a reviewer can audit rather than a model they "
                "must trust, the rating the bank assigns and the price it "
                "sets from it (the rate that covers expected loss plus "
                "funding plus capital charge, in basis points), the limit "
                "structure and what is committed versus uncommitted, the "
                "collateral and its haircuts and lien, the covenant as a "
                "promise written before the drawdown, the approval as a "
                "record with who decided and why, and the offer letter the "
                "contract then becomes. Ends where M1 begins: a booked "
                "facility with its schedule. Author "
                "credit-origination-from-scratch; nothing must come first "
                "\u2014 the decision is integer arithmetic and a policy, not "
                "a model."},
        {"id": "M3", "title": "Collections, Workout and Recovery",
         "course": None, "kind": "author", "prereq": ["M1"],
         "why": "The loan after it goes wrong, as actions and their "
                "consequences over M1's own book and ledger: the delinquency "
                "strategy as a state machine (dunning at day X, call at day "
                "Y, referral at day Z, each step a record the customer's own "
                "history answers), forbearance as the bank's decision \u2014 "
                "the restructure, the term extension, the capitalisation of "
                "arrears \u2014 and the probation and cure it triggers, the "
                "cure rate and the re-default the strategy is measured on, "
                "the collections waterfall over the cash that arrives (what "
                "pays fees, what pays interest, what pays principal, and "
                "what the ledger says actually happened), the workout on "
                "default: the sale of the collateral and its costs, the "
                "settlement, the deficiency that survives, the write-off as "
                "an accounting act distinct from the cash recovery that "
                "follows it, the recovery cash flows M1's stage 4 discounted "
                "\u2014 now produced by the strategy you wrote and measured "
                "against the bank's actuals, and the per-loan story: one "
                "loan followed from first missed payment to final recovery, "
                "every bank action and cash movement on its own line. Author "
                "collections-workout-from-scratch; M1 is the book and the "
                "default definition it works on."},
        {"id": "M4", "title": "Bank P&L and the Loan's Full Cost",
         "course": None, "kind": "author", "prereq": ["M1", "M3"],
         "why": "Where the contract lands on the bank's own statements, over "
                "M1's book with the strategy M3 wrote: the interest income "
                "the schedule earns and the day-count that computes it, the "
                "funding cost of every euro lent (the transfer price, in "
                "basis points, and why a 300bp margin is not 300bp of "
                "profit), the expected loss booked as the provision (M1's "
                "stage 6) and the release or charge as stages move, the "
                "impairment P&L line the roll-forward explains, the "
                "unexpected loss the capital absorbs and the return on it "
                "\u2014 RAROC as a ratio of exact integers, the operating "
                "cost of the origination (M0) and collections (M3) "
                "machinery, fee income and its recognition, the economic "
                "profit per loan, grade and vintage, and the statement the "
                "course files: for the same book, the net interest, the "
                "provision charge, the cost and the capital \u2014 the "
                "numbers a chief credit officer reads and the per-grade "
                "report that shows where the bank made money and where the "
                "contract's risk ate it. Author bank-pl-from-scratch; M1 "
                "is the book, M3 the cash that actually arrives."},
        {"id": "M2", "title": "IRB and Regulatory Capital",
         "course": None, "kind": "author", "prereq": ["M1"],
         "why": "The bank's own estimates, and the ones the regulator does "
                "not let it trust alone: the PIT/TTC split and where each is "
                "legal, the IRB risk-weight formula as integer arithmetic "
                "\u2014 the correlation R per asset class, the maturity "
                "adjustment, the capital requirement K as the exact series "
                "it is, the normal quantile tabulated as data because the "
                "house rule is no float and a table is also what a reviewer "
                "can recompute \u2014 downturn LGD (the downturn multiplier "
                "and the collateral it is allowed to haircut), best-estimate "
                "LGD for the accounting stage against the downturn floor for "
                "the capital stage, BE-EAD with its CCFs, the output floor "
                "phased in over the schedule, and the reconcile-the-two-books "
                "check: IFRS 9's provision and IRB's capital computed from "
                "the same world, per grade and in total, each shown where "
                "the other cannot agree with it. Author "
                "irb-capital-from-scratch over M1's book, dates and rules, "
                "with the policy extended rather than replaced and every "
                "number still basis points."},
        {"id": "M5", "title": "Distressed Debt Investing",
         "course": None, "kind": "author", "prereq": ["M1", "M3"],
         "why": "The same default seen from the buy side, where it is an "
                "opportunity with a price: the capital structure as a "
                "waterfall of claims over M1's borrower \u2014 who is owed "
                "what, secured ahead of whom \u2014 the distressed bond and "
                "loan bought below par, and the question every price asks: "
                "recovery, reorganisation, or the debtor's death; the "
                "distressed exchange and the maturity extension as the "
                "negotiated outcomes, the restructuring waterfall applied "
                "to the absolute-priority rule and the violations that "
                "settle it in practice, the claim the fund bought valued "
                "three ways \u2014 the expected recovery from M3's actual "
                "cash flows, the Merton distance-to-default on the "
                "borrower's own assets, and the comparables \u2014 and "
                "where the three disagree is the trade; the entry price "
                "implied return and the IRR in basis points that survives "
                "the timing of the recovery, the hold decision against the "
                "carry, and the report the fund writes: why this claim, at "
                "this price, with what recovery and by when \u2014 checked "
                "against what actually happened to the borrower. Author "
                "distressed-debt-from-scratch over M1's book and M3's "
                "collections log; the bank's provisioning and the fund's "
                "thesis are two readings of one default."},
        {"id": "M6", "title": "LBO Model From Scratch",
         "course": None, "kind": "author", "prereq": ["M1", "M3"],
         "why": "The leveraged buyout as arithmetic that either holds or does "
                "not, built over M1's amortisation machinery and M3's "
                "workout realism: the target as facts \u2014 EBITDA, "
                "capex, working capital, the cap table \u2014 on a provided "
                "estate whose five-year path is the ground truth; the sources "
                "and uses that balance to the cent, entry multiple and "
                "financing structure as the two decisions that set "
                "everything; the debt schedule as a waterfall of tranches "
                "with covenants the model cannot quietly violate \u2014 "
                "revolver drawn when cash falls short, mandatory prepayment "
                "from excess cash, the incurrence test checked every period; "
                "the operating build from revenue to EBITDA to free cash "
                "flow with integer arithmetic and the day-count from M1; "
                "exit on the multiple the estate actually realises, and the "
                "returns decomposition the sponsor's own memo contains: how "
                "much of the IRR is leverage, how much is EBITDA growth, "
                "how much is multiple expansion \u2014 each named, each "
                "checked against the estate. Sensitivity as the model's "
                "honesty: the grid over entry price, exit multiple and "
                "leverage where the downside case breaches the covenant and "
                "the checker demands the breach be visible, not amortised "
                "away. Author lbo-model-from-scratch; M5 values the claim "
                "on the way down, M6 buys the whole company on the way in \u2014 "
                "two prices, one discipline: the cash flows decide."},
    ]),
    ("N", "Web3 and simulation", [
        {"id": "N1", "title": "Blockchain From Scratch",
         "course": None, "kind": "author", "prereq": [],
         "why": "A ledger is a hash chain plus a rule for who appends: the "
                "block header and the digest that seals it, Merkle trees and "
                "the inclusion proof that is the point of them, addresses and "
                "signatures over a provided keypair scheme, the UTXO set and "
                "the spend that must name what it consumes, the mempool and "
                "the double-spend the ordering kills, proof-of-work's target "
                "and difficulty adjustment as the two constants that make a "
                "chain honest about time, then proof-of-stake's slots and "
                "attestations on the same world, fork choice as a rule "
                "recomputable from any node's own view, and a network of "
                "simulated peers whose clocks and drops the harness drives "
                "\u2014 accepted when every node converges on the same chain "
                "and a planted fork with less honest weight loses. Author "
                "blockchain-from-scratch; H6 is the agreement half taken "
                "seriously, N1 the ledger half."},
        {"id": "N2", "title": "Smart Contracts & dApp",
         "course": None, "kind": "author", "prereq": ["N1"],
         "why": "A contract is a program the ledger agrees to run exactly "
                "once, priced by the work it does: the account model over "
                "N1's UTXO world, the bytecode VM \u2014 stack, memory, "
                "storage whose every cold slot is charged \u2014 and the gas "
                "schedule that makes the meter real; a compiler from a toy "
                "contract language to that bytecode with the ABI that lets a "
                "caller encode a call; the escrow, the token and the voting "
                "contracts written in it, each with the reentrancy or "
                "overflow bug the tester plants and the checker asks your "
                "guard about; then the dApp on top: a local node your client "
                "talks to, transactions signed, sent and receipted, events "
                "indexed by your own scanner, and the front-end state "
                "machine that reads the chain and never trusts it. Author "
                "dapp-from-scratch; N1 is the machine it runs on."},
        {"id": "N3", "title": "MuJoCo-Style Physics Engine",
         "course": None, "kind": "author", "prereq": ["A8"],
         "why": "A physics engine is a constraint solver wearing a scene "
                "graph: rigid bodies with mass and inertia tensors, contact "
                "detection as narrowphase over provided shapes, the contact "
                "Jacobian and the LCP that a projected solver iterates to "
                "rest, the warm start that makes it stable, the integrator's "
                "order and its energy drift, actuators and PD control, then "
                "a MuJoCo-shaped MJCF subset parsed into that world \u2014 "
                "and the proof of the whole thing: the gradients. MuJoCo "
                "exists because differentiable simulation trains "
                "controllers; A8's exact reverse mode over the solver's "
                "unrolled steps is the capstone, checked against the "
                "finite-difference oracle at every parameter. Author "
                "physics-engine-from-scratch; A8 is the engine that makes "
                "the last stage possible."},
    ]),
]

# one glyph per row kind — the same four `render_dag` draws
SYMBOL = {"ready": "\u25cb", "legacy": "\u00b7", "author": "\u270e", "salvage": "\u21bb"}


def _find(courses, name):
    for c in courses:
        if c["name"] == name:
            return c
    return None


def find(name):
    """The registry row for a slug, an id or a title, as (letter, phase, item).

    `codecraft stage L2` has to work before the directory exists — it did for
    tcp-ip-from-scratch — so it looks the row up here rather than in the
    discovered courses. Returns (None, None, None) when nothing matches.
    """
    want = re.sub(r"[^a-z0-9]+", "-", str(name or "").lower()).strip("-")
    if not want:
        return None, None, None
    for letter, phase, items in PHASES:
        for item in items:
            names = [item["id"].lower(), (item.get("course") or "").lower(),
                     re.sub(r"[^a-z0-9]+", "-", item["title"].lower()).strip("-")]
            if want in names:
                return letter, phase, item
    return None, None, None


def render_path(profile, courses, ink):
    green, yellow, grey, cyan = ("\033[32m", "\033[33m", "\033[90m", "\033[36m")
    lines = ["", ink("  codecraft \u00b7 the path", "\033[1m"),
             ink("  your order: AWS, LLM internals, RAG, evals + agents, MCP, "
                 "harness, benchmark, eval, the machine stack, the inference "
                 "spine, and agent infra", grey), ""]
    done = active = 0
    for code, title, items in PHASES:
        lines.append(ink(f"  PHASE {code} \u2014 {title}", cyan))
        for item in items:
            course = _find(courses, item["course"]) if item["course"] else None
            cstate = profile["courses"].get(item["course"], {}) if item["course"] else {}
            total = (cstate.get("total")
                     or (len(course["stages"]) if course else 0))
            passed = cstate.get("last_passed", 0)
            if item["kind"] == "ready" and course and total and passed == total:
                state, mark, note = "complete", ink("\u2713", green), ""
                done += 1
            elif item["kind"] == "ready" and course and cstate:
                state, mark = "doing", ink("\u25cf", yellow)
                note = (f"{passed}/{total}  next stage {cstate.get('next_step')} "
                        f"({course['stages'].get(cstate.get('next_step'), {}).get('file', '')})")
                active += 1
            elif item["kind"] == "ready":
                state, mark, note = "ready", ink("\u25cb", grey), "not started"
            elif item["kind"] == "author":
                mark, note = ink("\u270e", yellow), ink("to author", yellow)
            elif item["kind"] == "salvage":
                mark, note = ink("\u21bb", yellow), ink("port from a branch", yellow)
            else:
                mark, note = ink("\u00b7", grey), ink("no checker yet", grey)
            prereq = ""
            if item["prereq"]:
                prereq = ink("  after " + ", ".join(item["prereq"]), grey)
            label = f"{item['id']}  {item['title']}"
            lines.append(f"  {mark} {label:<34} {note}{prereq}")
            lines.append(ink(f"       {item['why']}", grey))
        lines.append("")
    lines.append(ink(f"  {done} complete \u00b7 {active} in progress \u00b7 "
                     f"start: python3 codecraft/cli.py run {_first_ready(courses)}", grey))
    lines.append("")
    return "\n".join(lines)


def _first_ready(courses):
    for code, title, items in PHASES:
        for item in items:
            if item["kind"] == "ready" and _find(courses, item["course"]):
                return item["course"]
    return "<course>"
