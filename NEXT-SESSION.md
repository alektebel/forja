# Next session — where everything is

Written at the end of the session that shipped **G7 (`shell-from-scratch`)**, a shell
over a provided machine as ten graded stages — the line and its operators, expansion in
the order a shell must, the descriptor table a pipeline builds before anything runs,
the process tree of fork-exec-wait, the job table, signals and traps, the builtins that
must not fork, lists under the rules of `set -e`, the session replayed byte for byte,
and the audit that answers why a status was the number it was — **506 planted
mutations**, 910 testers, the world's four digests pinned. Before it, in its own
session: **M1 (`credit-lifecycle-from-scratch`)**,
the arithmetic of a loan's whole life as ten graded stages over a bank provided as data
whose own records are the answer key (`book.py` — `Book.build(7)`: twelve loans,
thirty-six month-end reporting dates, three model artifacts; `dates.py`; `rules.py`) —
and, earlier still, **K1 (`agentic-retrieval-from-scratch`)**, phase K's
first slot. K1 is retrieval that checks itself over a provided contract corpus whose
ground truth is data (`corpus.py`: 8 documents, 16 questions, 12 labelled failures, the
estate's scale; `meter.py`: what a call costs): clauses and their cross-references, an
index sized against a memory budget, two scorers and the fusion that has to beat both, a
reranker that earns its place, an ambiguous question rewritten and recorded, the critique
of what came back, grounded-or-abstain with a citation per claim, the loop under a budget
that stops for a reason it names, the checking priced against the naive
retrieve-and-answer, and a debugger that diagnoses the customer's own failures without
ever reading the label they carried — **589 planted mutations**, 893 testers, no float
anywhere. M1 is a loan's life as numbers: the contractual schedule and the effective
interest rate that discounts it, the bucket and the new definition of default, the
migration matrix and the lifetime PD built from it, the LGD behind the recovery cash
flows, the drawn and undrawn balance behind the EAD, the expected credit loss with its
horizon and its scenarios, IFRS 9's three stages and the significant-increase-in-credit-
risk test, the provision roll-forward line by line, the reporting pack with its
reconciliation, and the backtest, validation and attribution of a model the course did
**not** fit — **643 planted mutations**, 727 testers, and no float anywhere either:
every division carries the contract's pinned rounding, because accounting is a
fixed-point discipline. Everything in *Done* is committed and pushed; the section after
it is the commit that carries this file.

**Asked for next, by the user, and not started**: nothing outstanding. What remains is
the queue this file has been carrying — **G8 `runtime-from-scratch`** first, then H5,
L4, H7, H6, H8, I2 → I3 → {I6, I7, I8, I10, I12, I14} → I13, and phase K's remaining
four (K2, K3, K4, K5), one unit per commit, in the order its own section records.

## Done, pushed, on `origin/main`

| Commit | Unit |
|---|---|
| `9332df2` | **Agent Infra**: `AGENT-INFRA.md` (the twelve-item list kept verbatim) and **phase J** registered |
| `68c98bb` | **G3 `cpu-from-scratch`** — 10 stages, provided `isa.py`, 360 mutations |
| `b944541` | **J1 `queue-and-workers-from-scratch`** — provided `fleet.py`, 386 mutations, smoke green |
| `21206f4` | **`profiling-pytorch/`** — the three Hugging Face *Profiling in PyTorch* posts as study notes (the posts themselves gitignored) |
| `bfff13f` | **`DISTRIBUTED.md`** and I9/H1 registered |
| `5c74fbc` | **I9 `interconnects-from-scratch`** — 10 stages, 438 mutations, smoke green, registered |
| `f446db4` | **H1 `distributed-training-from-scratch`** — 10 stages, 554 mutations, smoke green, registered |
| `2dab44e` | **A8 `autograd-from-scratch`** — 10 stages, provided `exact.py` + `fixtures.py`, 504 mutations, smoke green, registered |
| `2ba19e5` | the A8 manifest prose fix: the copied `course_head.py` still described H1's course |
| `13bd3eb` | **J2 `orchestration-from-scratch`** — 10 stages, provided `agents.py` + `graphs.py`, 526 mutations, smoke green, registered |
| `10b361c` | **`AI-ENGINEER.md`** — the user's two lists kept verbatim (25 AI-engineer interview problems, 15 things to build), a per-item coverage table for all 40, and the five surviving gaps registered as **phase K** (`path.py` + `ROADMAP.md`, all five `kind: "author"`, with three items deliberately left with no slot and their reasons stated) |
| `b926158` | **J3 `durable-execution-from-scratch`** — 10 stages, provided `disk.py` + `work.py`, 558 mutations, thesis *a run is not the process that started it; it is the log on disk*, registered |
| `83e7a55` | **J4 `sandbox-capabilities-from-scratch`** — 10 stages, provided `fleet.py` (J1's, byte-identical), `vfs.py` and `tools.py`, 494 mutations, thesis *an agent's power is the intersection of what its tools declare, what its principal granted and what the world will still afford*, registered |
| `0230b92` | **J5 `agent-metrics-from-scratch`** — 10 stages, provided `fleet.py` (J1's, byte-identical) and `telemetry.py`, 510 mutations, thesis *a trace is not a metric*, smoke green, registered |
| `4755f5c` | **G4 `os-from-scratch`** — 10 stages, 641 mutations, the machine provided (`machine.py`, `devices.py`, `userland.py`), thesis *an operating system is what you write after the hardware breaks your last promise*; `linux-from-scratch/` staged beside it as prose; smoke green, registered |
| `bfbdefb` | **`cz stage`, per-stage counts, six registered rows** — the stage page before the run, `codecraft/stats.py` (9,323 asserts and 4,079 caught mutations across the eighteen built courses), the 128 hardcoded repo roots replaced by `__file__`, and G7/G8/H5/H6/H7/L4 registered |
| `6eb8f8d` | **`cz dag`** — the registry as a dependency DAG (`./cz dag`, `./cz dag <course>`, `cz tree` as an alias), the derived waves and the advisory `ADVICE` layer, and the fifteen-item AI-infrastructure list mapped onto three new rows (I13, I14, H8) |
| `5ab0f55` | **L1 `tcp-ip-from-scratch`** — 10 stages, provided `wire.py` and `hosts.py` (J1's world, `fleet.py`'s cross-check discipline), 554 mutations, smoke green, registered |
| `246003c` | **`cz tracks`** — the registry read as tracks and weakly-connected components: `./cz tracks` (roots, terminals, leverage, merge points, the five components) and `./cz tracks <row>`, answering both "is this row a dependency of most others" and "where does it sit", with the measured reading the command prints — 60 rows · 87 hard edges · 25 tracks · 9 waves, roots `A1, A2, A5, G1, G6, H4, H7`, `A2` in 19 of 25 tracks, `I13` furthest with 17 behind it, 53 of 60 rows carrying at least one prerequisite |
| `d7c9d3e` | **L2 `concurrent-servers-from-scratch`** — 10 stages, provided `link.py` (J1's `fleet.py` byte-identical), 757 mutations, smoke green, registered |
| `4856935` | the L2 doc follow-up: the six files the flip left stale (`NETWORKING.md`, `NEXT-SESSION.md`, root `README.md`, `codecraft/README.md`, `codecraft/ROADMAP.md`, `codecraft/briefs.py`) |
| `1268705` | **L3 `mqtt-broker-from-scratch`** — 10 stages, provided `streams.py` (the byte-pipe transport) and `grants.py` (the policy table), 600 mutations, smoke green, registered; phase L closed |
| `eaf0a64` | **`ENTERPRISE.md`** — the twelve enterprise-AI projects kept verbatim with a per-project "already in this repo / the gap to build" table, and the queue folded into `path.py` |
| `bc0e6bb` | **K6 `fde-from-scratch`** — twelve stages over a provided customer that is data (`estate.py`, `idp.py`, `network.py`, `meter.py`), 884 mutations, smoke green, registered: the twelve-stage FDE skill list built whole |
| `3263177` | the K6 doc follow-up: `ENTERPRISE.md`'s coverage of the twelve enterprise projects, `codecraft/ROADMAP.md`'s K6 row and phase-K paragraph, and the course README's pointer |
| `4e64609` | **K1 `agentic-retrieval-from-scratch`** — 10 stages over a provided contract corpus that *is* the ground truth (`corpus.py`, `meter.py`), 589 mutations, 893 testers, smoke green, registered: retrieval that checks itself, with phase K's census and the dependency tree's measured lines refreshed |

## The unit this file carries — G7 `shell-from-scratch`

**G7 `shell-from-scratch`** — ten stages, **506 mutations**, 910 testers, over a
provided machine that never changes and that the course never writes: a shell is what
a kernel looks like from the outside, and every promise G4's kernel makes is on show —
what a child inherits, what a pipe costs, who waits for whom, and what a signal does
to a job. The contract is frozen in `.g7-dev/CONTRACT.md` (§0 the unit and the
ten-stage mapping, §1 the laws a stage is audited against, §2 the world name by name,
§3 the execution model, §4 every answer's keys and every rule, §5 the check
conventions, §6 the harness, §7 the amendments) and so is the world: the course reads
it and never writes it.

### The world it is given, and never writes

`shell-from-scratch/machine.py` (`sha256 8acb4bbd…`), `programs.py` (`c17e065c…`),
`rules.py` (`b2b33cf0…`) and `scripts.py` (`5462a4af…`), standard library only, pinned
by `.g7-dev/verify_provided.py` → `PROVIDED: 149, PROBLEMS: 0`. `machine.machine(7)` is
a deterministic scheduler with its own filesystem, pipes, process tree and signal
delivery, and its own ledger of what happened: `machine.store(...)` hands out the
mark every later observation is a delta from — the transcript, the spawn ledger, the
deadlocks and the terminal are read back as counters against it, so a session answers
for what it did and not for what the machine already held when it was handed over.
`programs.py` is the ten programs a shell can become (`cat`, `echo`, `env`, `false`,
`grep`, `head`, `pwd`, `sort`, `tick`, `wc`), each with its own step budget;
`rules.py` carries the policy as data (`POLICY_VERSION = "shell-policy-1"` — the exit
codes, the signal numbers, the operators longest-first, the expansion order, the
builtins); `scripts.py` is **eight fixture sessions** with their expected records —
transcripts, statuses, spawn counts, deadlocks — the answer key a stage reproduces
from the machine's doors, not reads.

The landmines the world plants are real and the checks reach them: a pipeline the
shell still holds the write end of, whose blocked `cat` deadlocks until someone reaps
it (`signal(reader, "TERM")`, then `advance`, then `close` on the write end);
`kill -STOP 1` against a fresh machine's own pid; a status that is `128 + n` from a
signal and never a plain number; `$p` expanded from a stored tool that cannot execute
(126) versus one that does not exist (127); `cat < /missing | echo hi`, where the
refusal must be recorded as `redirection-failed` and the right-hand side still runs;
and `exit 143`, where the plain status of the last pipeline wins over the signal the
number resembles.

### The ten stages

| # | File | What it builds | Mutations |
|---|---|---|---|
| 1 | `stage_01.py` | The line, the word and the operator: quoting as part of a word's bytes, the longest operator recognised before the shortest, the parse errors named | 75 |
| 2 | `stage_02.py` | Expansion, in the order a shell must: parameter, tilde, split, glob, quote-removal, here-documents, and why the count of words depends on the order | 45 |
| 3 | `stage_03.py` | The pipeline, the descriptor table built before anything runs, and what a pipe costs the machine in bytes | 75 |
| 4 | `stage_04.py` | The process tree: fork, exec, wait, every child reaped, and the status that is always the last command's | 55 |
| 5 | `stage_05.py` | The job table: background, stopped, and who waits for whom, with `wait` that reaps in job order | 68 |
| 6 | `stage_06.py` | Signals, traps, and what a signal does to a job: `128 + n` is a signal and never a plain status, traps replace by name and fire in order | 22 |
| 7 | `stage_07.py` | The builtins that must not fork, and the ones (`trap`, `kill`, `wait`) stage 7 refuses to route | 32 |
| 8 | `stage_08.py` | Lists, conditions and the rules of `set -e`, with the refused builtins routed to the stage that owns them | 45 |
| 9 | `stage_09.py` | The session, replayed byte for byte against the world's own record | 52 |
| 10 | `stage_10.py` | Exit codes, and the audit of a session's statuses: one reason per step, from the evidence, never from the answer key | 37 |

### How it is verified, and the rule that keeps it verified

`.g7-dev/` is the harness, outside the repository on purpose: `verify_provided.py` (the
world), `assemble.py` (writes `course.py` from the ten checks, `course_head.py` and
`course_tail.py`), `check_NN.py` (each stage, runnable alone, exits 2 naming the stub
in the template), `mutate_NN.py` (`mutate_all.py` for the sweep), `smoke.py`,
`run_assembled.py`, `run_all.py`, `audit_course.py` (the laws) and `probe_stages.py` —
an independent second reading that drives each stage's functions directly. The last
measured full pass: `verify_provided.py` → `PROVIDED: 149, PROBLEMS: 0`; `check_NN.py`
× 10 → ten `PASS`, and ten exits 2 against the template; `mutate_all.py` → every
mutation caught, `MISSED OR BROKEN: 0`; `audit_course.py` → `AUDITED: 10, PROBLEMS:
0`; `probe_stages.py` → `PROBED: 362, PROBLEMS: 0`; `smoke.py` → `PASS` (the manifest,
all ten checks green on the solutions and red on the templates); `run_assembled.py` →
`ASSEMBLED: 10/10`; `count_tests.py shell-from-scratch` → 910 testers, per stage
`[102, 73, 116, 83, 87, 117, 152, 72, 59, 49]`.

**The rule is the same one K1 carries**: a `mutate_NN.py` entry is anchored to exact
solution text, so any later rewrite of `solutions/stage_NN.py` must be followed by
`mutate_all.py NN` and `audit_course.py NN` — and **the world is never edited to make
a stage pass**. If a stage disagrees with `machine.py`, the stage is wrong; if the
contract disagrees with both, the contract gets an amendment row (§7 has **ten**, each
one a reading a stage found in the middle of the work and that the plan had got wrong,
and a rule no run can reach is deleted from the contract rather than tested).

### What the next session should know

- `codecraft/path.py`'s G7 row is `"kind": "ready"` with `"course":
  "shell-from-scratch"`; `codecraft/stats.py` carries the measured row
  `(102, 75), (73, 45), (116, 75), (83, 55), (87, 68), (72, 22), (152, 32), (72, 45),
  (59, 52), (49, 37)`; `codecraft/briefs.py` maps `"G7"` to `.g7-dev/CONTRACT.md`. The
  dependency tree's measured lines are unchanged — `62 projects · 91 hard edges ·
  26 tracks · 9 waves` — because G7 was already a node before it was a course; the
  only render change is `G7` itself, now `ready`, unlocking nothing yet.
- **Stage 10's checks run on a used machine, not a fresh one.** Every fixture is
  audited after the machine has been warmed (spawn, echo, a reaped deadlock, wait),
  with a twin machine warmed identically to build the expected record — that is what
  makes the counter-delta mutations observable. The `deadlock` fixture alone still
  runs on a fresh machine, because its lines literally say `kill -STOP 1`.
- The four world digests above are pinned in the course README; if any of them ever
  changes, the README and `verify_provided.py` change with it, and every stage is
  re-checked.
- The runtime files `codecraft/{history.jsonl,profile.json,mentor_cache.json}` and any
  `__pycache__` are regenerated by any `./cz` invocation: delete them before a commit.
- `assemble.py` must be re-run after **any** edit to a `check_NN.py` — a stale
  `course.py` once graded nine of ten stages before anyone noticed.

### The unit before it — M1 `credit-lifecycle-from-scratch`

**M1 `credit-lifecycle-from-scratch`** — ten stages, **643 mutations**, 727 testers, the
whole of the user's one-line ask: *"lgds, nueva definición de default pd, cálculo de
provisiones, y todos los cálculos de reporting y estimación que hace un banco en su
lifecycle"*. The arithmetic and the data of a loan's whole life, held to accounting's
own discipline: every number an integer count of cents or basis points, every division
carrying the contract's pinned rounding, no float literal anywhere. Its world is
`book.py` (`Book.build(7)`: twelve loans, thirty-six month-end reporting dates, three
model artifacts, the observed payment ledger), `dates.py` and `rules.py`, pinned by
`.m1-dev/verify_provided.py` → `PROVIDED: 9417, PROBLEMS: 0`; the contract is frozen
in `.m1-dev/CONTRACT.md` with twenty-two amendments.

### The unit before it — K1 `agentic-retrieval-from-scratch` (`4e64609`)

**K1 `agentic-retrieval-from-scratch`** — ten stages, **589 mutations**, 893 testers,
phase K's first built slot: *retrieval that checks itself*, where the pipeline decides
whether it may answer at all and every decision it makes about its own search is either
recorded or priced. Its source is `AI-ENGINEER.md`'s phase-K row: interview problems
**#1** (a RAG for 10M documents), **#2** (your RAG gives wrong answers — debug it), **#3**
(chunking for legal contracts), **#4** (BM25 vs dense vs hybrid), **#5** (add a reranker
and measure whether it helped) and **#14** (detect and reduce hallucinations), plus build
**5** (self-correcting agentic RAG) — nothing cut for being hard to grade offline.

#### The world it is given, and never writes

`agentic-retrieval-from-scratch/corpus.py` (`sha256 04009cad…`) and `meter.py`
(`sha256 ef04c856…`), standard library only (`hashlib` in the one, nothing in the other),
pinned by `.k1-dev/verify_provided.py` → `PROVIDED: 102, PROBLEMS: 0`. `Corpus.build(7)`
is deterministic and carries the ground truth: `clause_index(doc)` (what a clause *is* —
including a deliberately duplicated number, `msa-3:5.2`, and a skipped one in `sup-1`),
`questions` (16, five with conversations, three two-hop, one superseded document `lic-2`,
five carrying a glossary acronym), `failures` (12 rows, each labelled with the stage that
failed, over the seven-name vocabulary), `glossary` (five acronyms, lower-case keys),
`SCALE` (10M documents, 140M clauses, 250k terms, 480 bytes a clause, 10% hot),
`terms`/`idf`/`embed`/`stats` — **the only analyzer in the world**, which is why every
stage that tokenizes is handed the corpus. `Meter` prices five kinds of call in cents and
keeps the injected tick.

There is **no float anywhere in the course**: BM25 is fixed point (120bp, 75bp), fusion is
`10000 // (60 + rank)`, and the world's vectors have an exact integer norm of 1000, so a
similarity is a dot product — no `math`, no square root, no logarithm, no `statistics`.

#### The ten stages

| # | File | What it builds | Mutations |
|---|---|---|---|
| 1 | `stage_01.py` | The clause chunker: numbered clauses, cross-references, definitions, and four parse problems **returned, never raised** | 50 |
| 2 | `stage_02.py` | The index of 10M documents as a **decision**: three layouts × shards, a memory budget, a scan budget, the cheapest plan that pays, and a refusal naming its own numbers | 64 |
| 3 | `stage_03.py` | Two scorers (BM25, dense) and the rank fusion that has to beat both, with per-question and aggregate measurement and the corpus's own ledger as the tie-breaker | 58 |
| 4 | `stage_04.py` | The reranker that has to earn its place: lexical signals over a deep pool, a before/after comparison, and a verdict of earned / within-noise / hurt | 56 |
| 5 | `stage_05.py` | The ambiguous question: the referent recovered from the conversation's last turn, the acronym expanded, the elliptical query filled, every fix recorded, and the two-hop split | 57 |
| 6 | `stage_06.py` | The critique: supported / stale / conflicting / off-topic / unresolvable, decided in that order, and the survivors | 51 |
| 7 | `stage_07.py` | Grounded or abstain: a claim per survivor, a citation per claim, the distinct-term grounding share, and four named abstentions in precedence order | 52 |
| 8 | `stage_08.py` | The loop under a budget: five stops it names (answered, abstained, budget, round-cap, repeat), a round priced before it runs, and a loop that can stop with no answer at all | 56 |
| 9 | `stage_09.py` | What the checking cost: the naive retrieve-and-answer beside it, the per-question "where did it lose", and "was it worth it" at a ±400bp noise band | 57 |
| 10 | `stage_10.py` | The debugger: the failing stage decided from the failure's **own evidence** (never its label), the distribution, the agreement with the customer, and the checker's verdict against the baseline | 88 |

#### How it is verified, and the one rule that keeps it verified

`.k1-dev/` is the harness, and it lives outside the repository on purpose:
`verify_provided.py` (the world), `assemble.py` (writes `course.py` from the ten checks +
`course_head.py` + `course_tail.py`), `run_all.py` (each stage's check against the
template → must fail — and against the solution → must pass), `mutate_all.py` (the planted
mistakes), `smoke.py`, `run_assembled.py`, `audit_course.py` (the eleven laws: the first
docstring paragraph, no float literal, no banned import, the ladder, every public name
declared) and `probe_stages.py` (the parent's own second reading of the contract, which
never imports a stage's check).

**A `mutate_NN.py` entry is anchored to exact solution text** (the substring must occur
once), so any later rewrite of `solutions/stage_NN.py` must be followed by
`mutate_all.py NN` and `audit_course.py NN`. And **the world is never edited to make a
stage pass**: if a stage disagrees with `corpus.py`, the stage is wrong, and if the
contract disagrees with both, the contract gets an amendment row (§7 has eight of them,
each one a reading a stage found in the middle of the work).

#### What the next session should know

- `codecraft/path.py`'s K1 row is `"kind": "ready"` with `"course":
  "agentic-retrieval-from-scratch"`; `codecraft/stats.py` carries the measured row
  `(74, 50), (104, 64), (93, 58), (95, 56), (91, 57), (84, 51), (75, 52), (82, 56),
  (94, 57), (101, 88)`; `codecraft/briefs.py` maps `"K1"` to `.k1-dev/CONTRACT.md`.
- The runtime files `codecraft/{history.jsonl,profile.json,mentor_cache.json}` and any
  `__pycache__` are regenerated by any `./cz` invocation: delete them before a commit.
- The course's own `README.md` carries the ten-stage table, the design decisions and the
  measured "how this course is verified" block; the contract is frozen in
  `.k1-dev/CONTRACT.md` (716+ lines) and is the thing to read first.

### The unit after this one — G8 `runtime-from-scratch`

Nothing the user asked for is outstanding: G7 was the head of the queue, and it is
built. What comes next is the head of the queue below — **G8 `runtime-from-scratch`**,
then H5, L4, H7, H6 → H8, I2 → I3 → {I6, I7, I8, I10, I12, I14} → I13, and phase K's
remaining four (K2, K3, K4, K5). One unit per commit, in that order: each flips its own
`path.py` row to `kind: "ready"`, adds its `stats.py` row and the census arithmetic,
writes its course `README.md`, refreshes the measured tree lines in
`codecraft/README.md` if the graph moved, and lands its section here.

The row-by-row reasoning is the table below, and it is worth reading before choosing:
**H6 blocks H8** and **I2 blocks four rows**, so doing them early costs nothing and
doing them late costs a wave.

### The rest of the queue, in the order the DAG allows

Nineteen rows carry `kind: "author"` and no course (G7 was the twentieth, and it is
built). **Ten of them have every prerequisite already built** — they are the ones a
session can pick up cold, and they are listed here in the order the graph suggests
(cheapest first, and the two rows that unlock other rows before the rows they unlock):

| Row | Course | Why it is here, and what it opens |
|---|---|---|
| G8 | `runtime-from-scratch` | G3 and G4 are built; it is the machine stack's last row |
| H5 | `query-engine-from-scratch` | G4 is built |
| L4 | `git-from-scratch` | G4 is built; the one row with a *provided* `git` as a tie-breaker |
| H7 | `compression-from-scratch` | no prerequisites at all |
| H6 | `consensus-from-scratch` | J3 and I9 are built; **H8 is blocked on it** |
| I2 | `transformer-inference-physics` | A2 and I1 are built; **four rows are blocked on it** |
| K2 | `prompt-ops-from-scratch` | E1, F2 and J1 are built |
| K3 | `memory-engine-from-scratch` | E1 and B2 are built |
| K4 | `fine-tuning-from-scratch` | A8 and C1 are built |
| K5 | `privacy-from-scratch` | C2, D1 and J2 are built |

The other ten author rows are **blocked on unbuilt rows**, and the chain is worth
writing down because it decides the order: I2 → I3 → {I6, I7, I8, I10, I12, I14} →
I13, plus H6 → H8. And **I11 is blocked on I5**, which is a `kind: "salvage"` row
(the quantization and compression reading, salvaged into a course) rather than an
authoring job: a session that wants I11 has to do I5 first, and I5 is a different
kind of work — turning what other branches already did into a course.

Two rows carry no course for a third reason: **G6** (`legacy`, the C systems set)
and **H4** (`legacy`, the long tail) are inventories of directories that exist
(`bash-from-scratch/`, `firewall-from-scratch/`, `linux-from-scratch/` and friends,
each mentioned in a row's prose and none of them registered as a course of its own),
so their "completion" is a decision about those directories rather than a course to
author.

The recipe for each is the one this unit followed, and it is worth repeating
verbatim: **freeze the contract first** (the world's shapes, the ten surfaces, the
laws, and every answer's keys), then provide the world and pin its digests, then
write one check per stage with the stages themselves delegated in parallel, then
verify nothing by report — re-run every command — and register the row, the measured
row in `codecraft/stats.py`, the ROADMAP paragraph, the census and this file, in one
commit.

## The unit the previous session carried — K6 `fde-from-scratch`

**K6 `fde-from-scratch`** — twelve stages, **884 mutations**, and the first built
slot of phase K: *an FDE builds the smallest thing that survives the customer's own
reality — a boundary enforced by the system rather than remembered by the author,
and an artifact checked against the customer's own record rather than against a
belief*. The twelve are the twelve-stage FDE skill list, one stage each and none
invented: the assertion, the session and the row; a deployment that cannot reach
out; the invoice, the reconciliation and the hybrid store; retrieval that cannot
leak a row; the legacy system as tools, and the credentials that stay behind; mask,
forward, restore, and prove nothing leaked; the workflow that waits for a human; the
model that fits the customer's GPU; what the AI did for this team, in hours and
cents; shadow traffic and a verdict; from a vague ask to a scoped four weeks; and a
runbook that is tested, and an admin who is not you.

The world is provided and frozen, three modules no stage may write: `estate.py`,
the customer itself — a directory of roles, groups and clearances (`IdP`), the
twenty-five rows across two tenants in four classifications, the eight documents
that arrive from their invoicing system dirty in exactly the ways thirty-year-old
data is dirty, and the audit log every act is written to whose `stats()` recounts
itself; `network.py`, the basement — five images in a bundle, six nodes, one of them
missing from the bundle, and not one zone that reaches `"public"`; and `meter.py`,
what a token cost and what a resolution saved per team. Both tenants are in the
estate on purpose: `contoso`'s rows are the ones carrying `restricted`, so isolation
has to be *demonstrated* rather than assumed, and a whole-course rule follows from
it — the course never writes the world, it asks it questions, and a refusal that
leaves a trace in the world's own log fails the stage.

What the shipped artifacts prove, every line re-run by the parent on the frozen
tree: `verify_provided.py` → `PROVIDED: 107, PROBLEMS: 0` (all three provided
digests unchanged); `run_all.py` → twelve `stage NN: PASS`, `FAILED: 0`;
`mutate_all.py` → `TOTAL 884/884`, `MISSED OR BROKEN: 0`, between 54 and 87 per
stage; `audit_course.py` → `AUDITED: 12, PROBLEMS: 0`; `assemble.py` → `assembled
12 checks, 6989 lines, compiles`; `smoke.py` → `SMOKE: PASS`, meaning every check
passes on the solutions *and* fails on the untouched templates; and a parent-written
runner that overlays `solutions/` on the templates in a temp copy and calls the
twelve checks inside the assembled `course.py` → `ASSEMBLED: 12/12`. **The parent's
probe is a second reading**: `.fde-dev/probe_stages.py` is one section per stage
written from the contract alone — no delegate's report consulted — and it reads the
plan back against the landed files: **331 expectations, 0 problems**. It earned its
keep differently from L3's: what it found was six bugs *in itself*, and the joins it
forced (an approval runs what the gate released; `fits` answers a reason for a name
it holds no catalogue for; `calibrate` takes the labelled cases; a gap nobody
drilled outranks the one that still needs the engineer) were readings the stages had
already made and documented, so the contract was amended to them rather than the
other way round — which is what §7 is for.

Twelve delegates wrote the twelve stages, one stage each and four files apiece —
the template, its solution, the check and the mutation list — against a contract
frozen in `.fde-dev/CONTRACT.md` before stage 1 (§0 the ladder, §1 the laws, §2 the
provided world and its API, §3 the execution model, §4.0 every answer shape pinned,
§4.1–§4.12 one section per stage with its surface, rules and mistake catalogue, §5
the check conventions, §6 the harness, §7 the amendments). The parent re-ran every
verdict rather than trusting a report — `run_all`, `mutate_all`, `audit_course` and
the probe, per stage — and the harness is `.fde-dev/`, outside the repository as the
house keeps them (`assemble.py`, `run_all.py`, `audit_course.py`, `mutate_all.py`,
`smoke.py`, `run_assembled.py`, `verify_provided.py`, `probe_stages.py`,
`count_tests.py`, and the twelve `check_NN.py` / `mutate_NN.py` pairs). Two of the
parent's own readings are worth recording because they were wrong first: the audit
enforced an unpadded stage number in titles and stub messages — the house
convention, read off thirty assembled courses — after an earlier reading of it
demanded the opposite, and the probe's own fixture assumed a `restricted` row in the
customer's tenant, which the world does not have.

Registered: `path.py` → **K6** `Forward Deployed Engineer`, `course:
"fde-from-scratch"`, `kind: "ready"`, prereq `["B1", "C1", "D1", "J4"]` (the
retriever this course makes refuse a row, the harness it points at the customer's
tickets, the protocol behind its tools, the discipline its credentials follow), with
a `why` that names all three provided modules; `stats.py` gains the row — **1,377
ways the twelve checks can reject your file and 884 caught mutations**, 54 to 87 per
stage, measured from the assembled `course.py` with the recipe re-derived against
L2's, mqtt's, rag's and agents' recorded rows first — and its census moves to
twenty-two courses with a `course.py`; `briefs.py` gains `"K6":
".fde-dev/CONTRACT.md"`, so `cz brief K6` prints `frozen before stage 1` instead of
falling through; the ROADMAP's census moves to twenty-nine courses and 323 graded
checks, its ready table gains the row, and the phase-K narrative now reads six slots
— the fifth gap's two lists plus the FDE skill list, built whole; the root README's
*Operations & Reliability* list gains the course; `NEXT-SESSION.md` is this file; and
the course carries its own `README.md`, whose *Where this stops* says what is
simulated rather than real (no Okta, no SAP, no Kubernetes, no GPU, no model server,
no socket, no clock, no randomness, no float).

Ten amendment rows in `.fde-dev/CONTRACT.md` §7 record where the course beat the
plan: the shape of an approval (`approve` runs what the gate released, and the
journal line is what keeps the decision observable), a 0-based journal `seq`, a
reason rather than a raise for a name where a record belongs, `grade`'s two models
taken from the shadow rows' own fields, `shadow`/`calibrate` speaking the case's
text and `CASE_KEYS`' own `expected`, `problems` as `(problem, requirement id)`
pairs with `scope-out-as-requirement` matched on the statement's exact text, `gaps`
reporting `uncovered` before `fde-only`, `no-expect` as the fifth runbook problem
with the failure path behind it, `forward` restoring into an audit line because
`GUARD_KEYS` has no slot for the answer, and the unpadded stage number. Nothing was
cut for being unreachable: every guard the twelve stages declare is reached by a
fixture in its own check, and every mutation leaves the stage's own output alone and
is caught.

### The unit before it — L3 `mqtt-broker-from-scratch`

**L3 `mqtt-broker-from-scratch`** — ten stages, **600 mutations**, and the last of
the three L slots: *a broker is a reader that never guesses and a writer that never
improvises — every byte it accepts is a frame the format allows, and every byte it
sends is one its own reader takes back*. The world is provided and frozen: a
byte-pipe `Transport` (`streams.py`) whose `step()` is the only thing that moves a
byte or a tick, whose `send` returns how many bytes it took, and whose `stats()`
recomputes every number from its own log; and `grants.py`, the policy table with
six reasons and a decision line written before the act. Ten stages go from the fixed
header and its variable-length integer, through the two-byte string and CONNECT, the
topic trie, SUBSCRIBE and the QoS actually granted, PUBLISH routed and retained,
QoS 1 as state and QoS 2 as a four-way handshake, the session that outlives the
socket, and the vocabulary a refusal arrives in — to a capstone that runs one
scenario twice, re-reads its own trace with the course's own reader, and holds the
broker's report against the transport's log key by key.

What the shipped artifacts prove, every line re-run by the parent on the frozen
tree: `verify_provided.py` → `PROVIDED: 46, PROBLEMS: 0` (both provided digests
unchanged); `run_all.py` → ten `stage NN: PASS`, `FAILED: 0`; `mutate_all.py` →
`TOTAL 600/600`, `MISSED OR BROKEN: 0` (between 40 and 86 per stage);
`audit_course.py` → `AUDITED: 10, PROBLEMS: 0`; `assemble.py` → `assembled 10
checks, 5243 lines, compiles`; `smoke.py` → `SMOKE: PASS`; and a parent-written
runner that overlays `solutions/` on the templates in a temp copy and calls the ten
checks *inside the assembled `course.py`* → `ASSEMBLED: 10/10`. **The parent's probe
is a second reading**: `.l3-dev/probe_stages.py` is one section per stage written
from `.l3-dev/CONTRACT.md` §4 alone — no delegate's report consulted — and it reads
the contract back against the landed files: **348 expectations, 0 problems**. It
earned its keep three times, catching defects the stages' own checks had missed:
stage 1 declared `REQUIRED_FLAGS` and never enforced them (now every nibble the
format forbids is refused, naming the type and both nibbles); stage 4 called a short
body `ProtocolError` where the contract says `Incomplete`; stage 5 marked a live
delivery `retained=True` where the flag belongs to the call rather than to the
message.

Registered: `path.py` L3 → `course: "mqtt-broker-from-scratch"`, `kind: "ready"`,
its `why` naming both provided modules; `stats.py` gains the row (984 assertions,
600 caught mutations, between 40 and 86 per stage) — the `tests` recipe was
re-derived from L2's ten recorded rows before it was applied (*asserts + explicit
`raise`s + refusal calls − 1*, which reproduces all ten of L2's numbers exactly);
the ROADMAP's census moves to twenty-eight courses and 311 graded checks, its ready
table gains the row above L2's, and the phase-L narrative now closes all three
slots instead of promising one; `NETWORKING.md`, the root README's *System Design &
Distributed Systems* list (newest-first) and `codecraft/README.md`'s "ten of the
twenty-one courses" follow; and `briefs.py` gains `"L3":
".l3-dev/CONTRACT.md"`, so `cz brief L3` prints `frozen before stage 1` instead of
falling through to generic guidance.

Ten amendment rows in `.l3-dev/CONTRACT.md` §7 record where the course beat the
plan — the largest being the shape that decided every writer in it: **a packet's
fixed header is read once, by stage 1, and handed down**, so every `write_*`
returns a body (`write_connack(0, 0) == b"\x00\x00"`) and the only frame reader in
the course is stage 10's `read_frames`. Four rules no run could reach were cut
rather than pinned: stage 4's unreserved-nibble rule (stage 1's now), an
unreachable two-byte length guard, stage 6's ring wrap (the id table's bottom-edge
rewind makes it dead), and stage 7's DUP-in-the-body mutations (DUP is a header bit
and every writer returns a body, so both sides of that mutation are the same bytes —
expressed where it is observable instead, in `due`'s flags).

### The unit before it — L2 `concurrent-servers-from-scratch`

**L2 `concurrent-servers-from-scratch`** — ten stages, **757 mutations**, four
models for one server: *a server is a policy about who gets the processor, and
the link whose log every claim is measured against is not written by the model it
grades*. Provided: `link.py`, written by this unit (a `Link` that carries bytes
on named connections and moves them only when its own clock is stepped, 64 bytes
a move, an outbox of 8, a listener backlog of 4, a client whose `patience` is a
count of ticks, seven kinds of event in its own log and fourteen counters in
`stats()`, including the drops nobody wants to read), and `fleet.py`, J1's file
copied byte for byte (`cmp` clean) — the clock this link is handed when you would
rather not use the one inside it. Chain: 1 the connection as a state machine →
2 the blocking server and the one slow client that starves the rest → 3 threads,
with the interleaving the *check* chooses → 4 the reactor: readiness as a set,
no busy-waiting → 5 the event loop and its timer queue → 6 callbacks as data,
and the one that must not run → 7 futures and `async`/`await` as a desugaring →
8 backpressure and the write that has to be deferred → 9 the Redis case study as
a command loop with per-connection state → 10 the capstone: one workload through
all four models, and the link's own log as the tie-breaker.

- `python3 /home/diego/Desarrollo/.l2-dev/verify_provided.py` → **`PROVIDED: 98,
  PROBLEMS: 0`** for `link.py` and `fleet.py`, neither of which any stage may
  edit (`fleet.py` is compared against J1's copy byte for byte, and the link is
  checked with `fleet.Clock()` injected).
- `run_all.py 01 … 10` → **`FAILED: 0`**; `mutate_all.py 01 … 10` → **`TOTAL
  757/757`, `MISSED OR BROKEN: 0`**. Per stage: 64, 60, 89, 61, 70, 84, 90, 71,
  118, 50 — the capstone and the blocking server are the smallest counts and the
  widest reach, because what they grade is a *disagreement*: the capstone's check
  doctors the link's own report three ways (one byte drained, one close missing,
  one tick too many) and the log wins every one.
- `audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0`, and `probe_stages.py`
  → **`PROBED: 10, PROBLEMS: 0`** — the parent's own reading of each stage,
  written from `CONTRACT.md` before the stage's check was read: stage 8's `send`
  probed turn by turn against an outbox of 8 until the 42-byte reply is handed
  over in outbox-fulls (`8, 8, 8, 8, 8, 2`) and its state is reading again; stage
  9's store probed by hand for `+OK`, bulk, `$-1`, `:n`, the error line, byte
  order in `KEYS` and a key forgotten at its deadline; the capstone probed with a
  one-client workload wrapped into a run by hand and then doctored.
- `assemble.py` → `assembled 10 checks, 5477 lines, compiles`; `smoke.py` →
  **`SMOKE: PASS`** (all ten green on the solutions, all ten red on the
  templates), and the both-ways run was repeated on a *copy* of the repo outside
  it: `./cz run concurrent-servers-from-scratch` → `0/10` on the templates, the
  same command with `solutions/` overlaid → **`10/10 passing`**, and the real
  course's twelve files the same checksums afterwards as before.
- Registered: `path.py` L2 → `course: "concurrent-servers-from-scratch"`,
  `kind: "ready"`, a `why` that no longer says "author"; `codecraft/stats.py` →
  the measured row (133, 72, 138, 88, 110, 91, 114, 114, 174, 71 rejections and
  64, 60, 89, 61, 70, 84, 90, 71, 118, 50 mutations), `cz stage
  concurrent-servers-from-scratch 10` printing `71 asserts · 50 planted mutations
  the check must catch`; the ROADMAP's ready-table row, its counts (**27
  courses, 301 graded checks**) and its phase-L table; a bullet in the root
  `README.md`; and the course's own `README.md` (the provided world, the ten-stage
  ladder, the failure catalogue in stage order, and where the course deliberately
  stops).
- **Stage 8's check arrived red, and that was the useful part**: its solution read
  a client's next request while that client's previous reply was still in flight,
  so an answer was lost — found by the mutation harness, not by the check. The
  check grew four scenarios (a request of 71 bytes, more than one `MAX_CHUNK`,
  assembled from exactly two reads; a dead head whose client's patience expired
  with a live reply queued behind it; a `seed=8` staggered arrival; and refusals
  for the phase and for both offset ranges that name the offender), the solution's
  read side now honours the phase, and the six mutations that no scenario can
  reach were cut with their reasons recorded in `mutate_08.py`'s docstring.
- The **capstone was written by hand** (`Stage10-2` had already died in the L1
  session as a length-stop, so the parent wrote `stage_10.py`,
  `solutions/stage_10.py`, `check_10.py` and `mutate_10.py`), and the workload is
  tuned so that all four models agree by bytes: 148 delivered by each for 42, 54,
  19 and 23 steps, with `compare` reporting that the reactor is cheapest *here*
  and asserting nothing.
- Harness: `/home/diego/Desarrollo/.l2-dev/` (`CONTRACT.md` — frozen first, §0–§7
  with ten stage specs and **three** amendment rows — `DELEGATE.md`,
  `course_head.py`, `course_tail.py`, ten `check_NN.py`, ten `mutate_NN.py`,
  `run_all.py`, `mutate_all.py`, `audit_course.py`, `assemble.py`, `smoke.py`,
  `verify_provided.py`, `probe_stages.py`, `STATE.md`). **Never in `/tmp`.**

Shapes worth keeping: **the world's log is the only account that cannot argue
with itself** — every stage returns what it decided, the capstone's `cross_check`
holds it against the link's own counters key by key, and the check proves the
comparison is real by doctoring the log rather than by trusting the model;
**steps, not seconds** — the unit of comparison is a turn the model counts, and
`time`, `threading` and `asyncio` are banned *because they are the subject*;
**a reply in flight lives in a connection's state** — stage 8's `pending` and
`offset` are the difference between a reply that takes turns and a reply a loop
variable lost, and `stalled` names the connections the head-of-line blocking cost
nobody could see; **a check that arrives red is worth more than nine that arrive
green** — stage 8's lost reply was a real bug the mutations found, and the fix
made the check's queue guard exact rather than clever; **the parent's probe is a
second reading** — where it disagreed with a stage, the prose was wrong once (the
template's `send` docstring named three of the state's five keys) and the
solution was wrong zero times; and **the `tests` metric is the check's own
rejections** — `assert` plus `raise` plus `_refuses(` calls, which is why L2's
checks count 1,105 of them. Across the twenty-one courses that carry a `course.py`
the measured totals are now **12,541 assertions and 5,990 caught mutations**,
recomputed from the rows in `codecraft/stats.py`.

Three contract amendments the *stages* forced, all in `.l2-dev/CONTRACT.md` §7
(the course wins over the plan): the state a `send` is handed is stage 1's
connection and phase plus `buffer`, `pending` and `offset`, and a send is a
`"writing"` move that returns the state to `"reading"` when the reply is drained;
the capstone's `tie_breaker` is `cross_check(runs[cheapest])` rather than the
plan's pair of unnamed numbers, so a disagreement says *which* key disagreed; and
`fleet.py` ships byte-identical while a client's patience is an int on the client
instead of a scripted worker from J1 — one clock, still moved only by
`Link.step()`, and a check's fixture is a number a reader can see.


### The unit before it — L1 `tcp-ip-from-scratch` (`5ab0f55`)

**L1 `tcp-ip-from-scratch`** — ten stages, **554 mutations**, the stack as data
against a world that does not care: *the wire keeps the record, and the ledger
that agrees with it is the only account of a session that cannot be argued with*.
Provided: `wire.py` (a link that loses, reorders never, delivers on a tick you
advance by hand, and keeps its own log of every frame with its ordinal) and
`hosts.py` (five named hosts with MACs and addresses, a box each, and the router
ports). Chain: 1 the frame and the type field that says what is inside → 2 ARP,
the cache that ages and the broadcast that comes back → 3 IPv4, the routing
table and the TTL that must be decremented → 4 ICMP echo and the checksum over
the pseudo-header → 5 the handshake as a state machine → 6 the sliding window
that must not be overrun → 7 the socket API as a table of descriptors → 8
retransmission on the injected clock → 9 the close, with TIME_WAIT as a state
rather than a sleep → 10 the capstone: one session, and the wire's own log as the
tie-breaker.

- `python3 /home/diego/Desarrollo/.l1-dev/verify_provided.py` → `PROVIDED: 93,
  PROBLEMS: 0` for `wire.py` and `hosts.py`, which no stage is allowed to edit.
- `run_all.py 01 … 10` → **`FAILED: 0`**; `mutate_all.py 01 … 10` → **`TOTAL
  554/554`, `MISSED OR BROKEN: 0`**. Per stage: 42, 57, 70, 64, 77, 57, 43, 46,
  58, 40 — the capstone carries the smallest count and the widest reach, because
  what it grades is a *disagreement*: its check tampers with the ledger three
  ways and the wire wins every one.
- `audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0`, and `probe_stages.py`
  → **`PROBED: 148, PROBLEMS: 0`** — the parent's own reading of each stage,
  written independently of the stage's check, so that a green check and a green
  probe are two readings of the same promise.
- `assemble.py` → `assembled 10 checks, 4711 lines, compiles`; `smoke.py` →
  **`SMOKE: PASS`** (all ten green on the solutions, all ten red on the
  templates).
- `./cz run tcp-ip-from-scratch` → **`0/10`** on the templates, every stage
  reporting `not implemented yet` at its own line; `./cz run tcp-ip-from-scratch
  --stage 4` → `stage 4: 0/1 passing`, which is the new selector doing its job on
  a course whose stages are stubs.
- Registered: `path.py` L1 → `course: "tcp-ip-from-scratch"`, `kind: "ready"`, a
  `why` that no longer says "author" (the row that was the *plan* page for L1 is
  the course page now); `codecraft/stats.py` → the measured row, `cz stage
  tcp-ip-from-scratch 10` printing `71 asserts · 40 planted mutations the check
  must catch`; a bullet in the root `README.md`; and the course's own
  `README.md` (265 lines: the ten-stage ladder, the frozen world and the mistake
  catalogue in stage order).
- **`cz brief <row>`** — the layer this unit added beside the course: per author
  row the guidelines, what to read and the acceptance checklist, generalising the
  contract that froze L1 (`codecraft/briefs.py`, `codecraft/contract.py`,
  `render.render_brief`, `cli.cmd_brief`). `./cz brief` lists the 24 rows still to
  author, `./cz brief L2` reads one in full, and the footer's example now points
  at the first row in that list rather than a hardcoded L1.
- **`cz run <course> --stage N`** — the selector that turns the ladder into one
  rung: `_stage_flag` in `cli.cmd_run`, verified on `os-from-scratch --stage 3`
  and on L1's own stubs.
- The **capstone was written by hand**: `Stage10-2` returned zero files after
  24m50s (a length-stop), and stage 10 is the one stage where the surface *is* the
  contract — so the parent wrote `solutions/stage_10.py`, `stage_10.py`,
  `check_10.py` and `mutate_10.py`, and the 40 mutations are the proof it is
  graded like the rest.
- Harness: `/home/diego/Desarrollo/.l1-dev/` (`CONTRACT.md` — frozen first, §0–§7
  with ten stage specs and **fifteen** amendment rows — `DELEGATE.md`,
  `course_head.py`, `course_tail.py`, ten `check_NN.py`, ten `mutate_NN.py`,
  `run_all.py`, `mutate_all.py`, `audit_course.py`, `assemble.py`, `smoke.py`,
  `verify_provided.py`, `probe_stages.py`, `STATE.md`). **Never in `/tmp`.**

Shapes worth keeping: **the world is provided and frozen** — `wire.py` and
`hosts.py` are read-only for every stage, and the only way to be wrong about them
is to be wrong about the wire's log; **the wire's log is the tie-breaker** — the
capstone's `cross_check` compares the session's ledger against `Wire.sent()`,
`delivered()`, `dropped()`, the tick and the sends' own ordinals, so a session
that reports what it *intended* is the failure the stage exists to catch, and the
`received` side of the comparison is witnessed by the server's box rather than by
the session's own claim; **a rule no run can reach is cut** — three mutations were
planted on the capstone's reader (the server's own echo, a segment for another
port, the settle before the final counts) and cut when no scenario could reach
them, because an uncatchable mutation is worse than a missing one; **the
capstone's own scenarios are the course's** — `plan()` ships a clean wire, one
that eats a single segment and one that loses more than it has ticks, so
`"expired": True` is a rule a scenario can actually break; and **the checks count
their own rejections** — L1's checks use `_refuses(exc, what, call, names)` for
the refusal sites, which is why `cz stage`'s `tests` metric counts those calls
alongside `assert` and `raise` (the nineteen built courses now total **10,452
assertions** and **4,633 caught mutations**).

Four contract amendments the *stages* forced at the capstone, all in
`.l1-dev/CONTRACT.md` §7 (fifteen rows in total, the course wins over the plan):
the ledger's frozen key list is eleven and not the ten `run`'s bullet spelled out
(`"expired"` is required by the same section's own rules); `open_session` drives
the wire it is handed instead of building one, because the stage is graded against
that object; the session drives both ends' stage 5 connections rather than stage
7's table (which owns the connection behind each descriptor and gives no way back
to it, and stage 9's close needs that object); and `plan()` ships three scenarios
rather than two, so the `expired` rule is observable.


### The unit before it — `cz dag`, the registry as a dependency DAG (`6eb8f8d`)

**The registry as a dependency DAG, and the fifteen-item AI-infrastructure list
mapped onto it.**

- **`./cz dag`** prints the whole registry as waves: `62 projects · 91 hard edges ·
  9 waves`, each row once, in the wave its longest path reaches, with what it
  unlocks. **`./cz dag <course>`** zooms on one row — its wave, its direct prereqs,
  everything that must come first *in wave order*, everything it opens,
  transitively, and the advice. Rows resolve by slug, id (`cz dag J3`) or title.
  New: `codecraft/dag.py` (`graph`, `before`, `unlocks`, `advice`, `focus`),
  `render.render_dag`/`render_dag_row`, `cli.cmd_dag` (`cz tree` is an alias).
- **The graph is derived, not written.** `path.PHASES` owns the rows and their
  `prereq` lists; `dag.py` reads them and nothing else, so the plan and the DAG
  cannot drift. `_level` is the longest path from a root, and the module reports
  the only two defects a registry can have — a prereq that names no row, and a
  cycle — instead of hiding them. All six of those invariants are now `cz
  self-test` failures, including "every prereq sits in an earlier wave" and
  "a row's closure is transitive and excludes itself".
- **A second, advisory layer.** `prereq` is the honest dependency; `ADVICE` is
  advice, is never an edge, and holds the nine places where a row's own thesis asks
  for something that nothing forces — A1 after A5 ("makes sqs/dynamodb in A1
  click"), F2 after C1 ("phase C1 owns what to measure"), H5 after A6, I11 after
  A3, I12 after F2, J5 after E1, K5 after J4, C2 after A5, H1 after A8. Every
  entry names the thesis it came from, and the self-test checks that each target is
  a real row.
- **Three more rows, from the list that arrived mid-unit** (I13
  `serving-cluster-from-scratch`, I14 `weight-delivery-from-scratch`, H8
  `failover-from-scratch`). Twelve of the fifteen items were already the subject of
  a registered course; #5 (weight delivery) and #14 (multi-region failover) were
  covered nowhere, and #1 (the cluster) was scattered across I3, I7 and I10 with no
  row of its own. The new ROADMAP section carries the full fifteen-row mapping plus
  the three mechanisms, and the inference-spine table gained its I13/I14 lines.
  `author` rows are **25** now, and the registry is **60 rows**.
- Docs touched: `codecraft/README.md` (the verb, a worked DAG, the two layers
  explained), the root `README.md`, the `cz` shim header, the web page's footer,
  `ROADMAP.md`, and this file.

### The unit before it — `cz stage`, per-stage counts, six registered rows (`bfbdefb`)

**`cz stage`, per-stage counts in the repo, six registered rows** — the
CodeCrafters-shaped surface the CLI was missing, the two defects found while
looking for it, and the plan rows that came out of the same review.

- **`cz stage <course> [n]`** — the page *before* the run: the file, what you
  write in it, how big the tester is, the live status and the ladder. No argument
  lands on the first stage that is not passing. A slug, an id (`G4`) or a title
  (`"OS From Scratch"`) all resolve, and a registered-but-unwritten course prints
  the row, its prerequisites and its thesis instead of "no course named …": that
  was `cz stage tcp-ip-from-scratch` for L1 until the unit this file carries
  wrote it. New:
  `cli.cmd_stage`, `render.render_stage`/`render.render_plan`, and
  `path.find`, the registry lookup the verb needs.
- **`codecraft/stats.py`** — the measured size of every built course's stages,
  recorded *in* the repo because half of it is unrecoverable: `tests` counts the
  `assert`/`raise` sites in a stage's check (recomputable from `course.py` at any
  time), while `mutants` is what that check was *proven* to catch by the
  development harness — which lives outside this repository and is cleaned up once
  a course ships. Eight courses carry both numbers; the other ten say `None`
  rather than a zero, and the page says "not measured" rather than lying.
  `cz stage os-from-scratch 5` → `93 asserts · 69 planted mutations the check must
  catch`; the eighteen built courses totalled **9,323 assertions** and **4,079
  caught mutations** at the time (nineteen and 10,452/4,633 after L1; twenty-four
  and 15,538/8,106 before G7; twenty-five and 16,403/8,612 after it — the sweep
  re-measured, the earlier readings left as they were taken).
- **The hardcoded repo root is gone.** 128 lines across 14 assembled `course.py`
  files carried `DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"`,
  and five more carried the same path as a `COURSE_REPO` default; all of them now
  derive the root from `__file__`. Verified by running **all fourteen courses from
  `/tmp`** with the templates in place — every stage reported `not implemented
  yet`, which is the proof the check found the repo and reached the stub — and G4
  with the solutions overlaid (`10/10 passing`, templates restored
  byte-for-byte). Two `# --- from /tmp/…` provenance comments were normalised in
  the same pass (they are the only stage separators in `mcp-` and
  `agents-from-scratch`).
- **Six registered rows**, in `path.py` (the authority `./cz path` renders) and in
  a new ROADMAP section that names each one's world, ladder and prerequisite:
  `G7 shell-from-scratch`, `G8 runtime-from-scratch`, `H5
  query-engine-from-scratch`, `H6 consensus-from-scratch`, `H7
  compression-from-scratch`, `L4 git-from-scratch`. `author` rows are **22** now.
  Two candidates were *not* registered, and the ROADMAP says why: a regex engine
  belongs as a stage of G5, and a hand-rolled crypto handshake duplicates the
  `cryptographic-library` project the G6 legacy slot already owns.
- Docs touched: `codecraft/README.md` (quickstart, the `cz` block, a worked stage
  page and what `asserts`/`mutants` mean), the root `README.md`, the `cz` shim's
  header, the web page's footer verb list, `ROADMAP.md`, and this file.

### The unit before it — G4 `os-from-scratch`, shipped in `4755f5c`

**G4 `os-from-scratch`** — ten stages, **641 mutations**, the thesis *an operating
system is what you write after the hardware breaks your last promise*. Provided:
`machine.py` (RAM, the page tables and the `MMU` that walks them, the `PageFault`
a trap carries as data, and the `Timer` the whole course advances by hand),
`devices.py` (a `Console`, and a `Disk` that loses everything it was not told to
sync) and `userland.py` (nine files with owners and modes, and eight programs
written in one op frame). Chain: 1 the map you were handed → 2 the frame allocator
and the bitmap inside it → 3 the address space and the translation you forgot to
invalidate → 4 the trap table and the fault as data → 5 the syscall boundary and
the pointer you did not check → 6 the process and the frame nobody gave back → 7
the scheduler and the wakeup that never came → 8 two CPUs and the critical section
nobody guarded → 9 the format and the write that was not ordered → 10 the
capstone: the userland, and the kernel's own ledger.

- `python3 /home/diego/Desarrollo/.g4-dev/verify_provided.py` → `provided: ALL
  PASS (171 checks)` for the three provided modules.
- `check_NN.py` → PASS for all ten; `run_all.py 01 … 10` → **`FAILED: 0`**;
  `mutate_all.py 01 … 10` → **`TOTAL 641/641`, `MISSED OR BROKEN: 0`**. Per stage:
  35, 49, 59, 62, 69, 81, 62, 60, 113, 51 — the capstone is the densest because
  every number in its report is a comparison with the machine's own records.
- `audit_course.py` → `AUDITED: 10, PROBLEMS: 0`; with no argument the audit
  refuses a `stage_10` that does not exist, which is how the solution's absence
  was caught before it was written.
- `assemble.py` → `assembled 10 checks, 5378 lines, compiles`;
  `probe_manifest.py` → `MANIFEST: 10/10 clean`; `smoke.py` → **`SMOKE: PASS`**
  (the manifest's ten stage entries by title and file name, every check green with
  the solutions overlaid, and every check red on the templates).
- `./cz run os-from-scratch` → `0/10` on the templates (every stage reporting
  `not implemented yet`), `10/10` with the solutions overlaid — *Course complete* —
  and the ten templates restored byte-for-byte (`cmp` clean against
  `.g4-dev/templates/`).
- Registered: `path.py` G4 → `course: "os-from-scratch"`, `kind: "ready"`, a real
  `why`; `ROADMAP.md` → **Twenty-five courses, 281 graded checks**, the
  `os-from-scratch` row right after `cpu-from-scratch`, the "missing entirely"
  paragraph now saying the machine stack's second half is built, and the plan
  paragraph naming G4's thesis with L1 as what comes next; a bullet in the root
  `README.md`; the course's own `README.md` (380 lines, sixty mistake bullets in
  stage order, the provided-world table and the ten-stage ladder).
- The **salvage**: `linux-from-scratch/` — nineteen files, the fifteen phase
  directories of `origin/claude/linux-from-scratch-curriculum-2qokjd`, 176
  exercises, prose left verbatim and staged here. The course is the graded ladder
  of the same idea; the prose is the reading beside it.
- Harness: `/home/diego/Desarrollo/.g4-dev/` (`CONTRACT.md` — frozen first, §0–§7
  with ten stage specs and the amendment rows — `DELEGATE.md`, `course_head.py`,
  `course_tail.py`, ten `check_NN.py`, ten `mutate_NN.py`, `run_all.py`,
  `mutate_all.py`, `audit_course.py`, `assemble.py`, `smoke.py`,
  `probe_manifest.py`, `verify_provided.py`, `templates/`, `STATE.md`). **Never in
  `/tmp`.**

Shapes worth keeping: **a refusal raises, a decision is returned** — a caller's
error (`KernelError`, `SyscallError`, `ProcessError`) is an exception, while the
kernel's own outcomes are data (`ERRNOS`, `ACTIONS`, `CAUSES`, `FAULT_WORDS`, and
the `{"allowed", "reason"}` an admission answers with), so a handler decides from
a value instead of from an exception it has to catch; **a promise is written
before the act it predicts** — one audit line per syscall, written *before* the
work, and the log line after it, so a report that folds both is a comparison of
three parties rather than of a record with itself, and the check can walk every
audit line and find exactly one log line whose value (or errno word) is what the
line promised; **the log line is ten keys with exactly one of `errno` and `value`
set**, and nothing is counted during the run — `report` recomputes every number
from the log and the audit, which is what makes `cross_check` able to disagree;
**the kernel's belief about the disk is computed independently** — `_Ledger` wraps
the device, records every write and mixes the same rolling checksum `Disk` does,
so a sector written straight to the device is caught; **`write` is one call number
with two implementations chosen by fd** — the console through stage 5's boundary,
a pipe through the kernel — which keeps the arity, the pointer check and the
promise identical on both paths; and **a budget is asked for before the work**
(`admit` never moves a frame and never raises for a limit that is spent, while
`apply_limit` raises for a resource this kernel does not have and for a limit that
is not a count).

Four contract amendments the *stages* forced, all recorded in `.g4-dev/CONTRACT.md`
§7 (the course wins over the plan): `machine.PageFault` gained `.user` — the
contract promised it and stage 4's delegate hit the `AttributeError`, with two
checks in `verify_provided.py` pinning it and its error bits; stage 9's `inodes`
argument became a **floor** (`max(inodes, len(files))`) rather than a count,
because a format that cannot hold the directory it is given is not a format; one
directory sector per inode *slot*, so a lookup's arithmetic is the layout's and
not a scan's; and three public names (`SECTOR`, `PROBLEMS`, `checksum`) added to
stage 9 so the format's own vocabulary is readable from outside.

## In flight — G8 `runtime-from-scratch`, shipped through stage 10

**G8 is built and pushed.** The world (`bytecode.py`, `assembler.py`, `heap.py`)
froze at `PROVIDED: 55, PROBLEMS: 0`; the contract lives in `.g8-dev/CONTRACT.md`.
All ten stages ship templates + solutions: 1 dispatch, 2 stack pricing, 3 control
flow (the step pins hold: arith 6, branch 7, countdown 31, fib10 129), 4 heap and
ledger, 5 mark-sweep, 6 reference counting and its honest cycle, 7 tri-colour
incremental, 8 the write barrier, 9 generations, 10 the copying collector and the
audit. The harness in `.g8-dev/` is complete: `run_all.py` 10/10 green, `smoke.py`
PASS on the assembled manifest, `run_assembled.py` 10/10, `audit_course.py`
`PROBLEMS: 0`, `verify_provided.py` 55 facts, `probe_stages.py` `PROBED: 10,
PROBLEMS: 0`, and the mutation sweep `mutate_all.py` **168/168, MISSED OR BROKEN:
0**. The assembled `runtime-from-scratch/course.py` (2,319 lines) is committed and
pushed. The next unit in the queue is **H5** — see the rows below.
Twelve *projects* — not slots — are queued in `ENTERPRISE.md`: the enterprise-AI list kept
on `claude/enterprise-ai-project-guides`, each row naming what this repository
already has for it and the gap that remains.
The rows registered in the units before this one queue behind it, one per slot —
H5, L4, H7, H6, then I13, I14, H8 (G8 is now among the shipped) — each carrying its own thesis in
`path.py`, each with its place in `cz dag`. After those: G5/G6 (phase G's
remaining two, which need checkers, not writing), phase K's five, and the rows
registered from the recovered corpora — **L5 `redis-from-scratch`** (L2 + J3),
**L6 `kafka-from-scratch`** (L2 + J1) from the CodeCrafters stage descriptions,
and **L7 `docker-from-scratch`** (G4 + J4), **L8 `emulator-from-scratch`**
(G3 — CHIP-8, then a second machine) and **L9 `rl-control-from-scratch`**
(A8 — DP, then MC, then TD/SARSA/Q-learning, then an approximator) from the
build-your-own-x tutorials in `tutorials-reference/`. The backlog
is **28 `author`, 6 `legacy`, 2 `salvage`, 34 `ready` — 81 rows** — `./cz path`,
`./cz dag`, `./cz tracks` and the ROADMAP's own tables are authoritative over this
file.

Two questions from earlier sessions are **answered**: the legacy, thin
`distributed-training/` directory stays exactly as it is (the user's call,
2026-10-14) — the roadmap marks it superseded and nothing touches it — and the
two lists in `AI-ENGINEER.md` are handled: 40 items mapped to existing courses,
five gaps registered as phase K.

## The workflow that produced G3, F2, J1, I9, H1, A8, J2, J3, J4, J5, G4, L1, L2 and L3 — keep it

1. **Recon**, then **freeze a contract** in a dev directory beside the repo
   (`/home/diego/Desarrollo/.g4-dev/CONTRACT.md`): thesis, conventions, the
   provided modules, the execution model, and per stage the surface, the frozen
   shapes and the *mistake catalogue*. Freeze it before writing any stage; amend
   it — never silently — the moment a stage's real surface differs, with a table
   recording what the plan said, what the course does and why (J3's §7 has eight
   such rows, J4's nineteen, J5's three, G4's four, L1's fifteen, L2's three,
   L3's ten).
2. **Never `/tmp`.** It was wiped three times and killed four delegates. The
   harness lives beside the repo and is re-synced after every change.
3. **One delegate per stage**, four files each (`stage_NN.py`,
   `solutions/stage_NN.py`, `check_NN.py`, `mutate_NN.py`). **A delegate's verdict
   is not evidence**: the parent re-runs `check_NN.py`, `mutate_NN.py`,
   `run_all.py NN`, `mutate_all.py NN`, `audit_course.py NN` — every time. Forty
   delegates across A8, J2, J3, J4 and J5, forty green; G4 ran the same drill one
   delegate at a time, and the one delegate that died after twenty-six minutes
   with zero files written is why the capstone was written by hand — and L1's
   `Stage10-2` did the same thing (twenty-four minutes, a length-stop, zero
   files), so L1's capstone was written by hand too and proved by its own forty
   mutations like any other stage.
4. **Stages that import only stage 1 can be delegated concurrently** — in J5 all
   seven of 2–8 were spawned in one batch while stage 1 was already verified, then
   9 (composing 2–8) and only then the capstone, which imports all nine. G4's
   ladder is a chain (each stage composes the one below it), so the ten stages were
   written in order and the audit's "imports a *later* stage" rule never fired.
5. **Keep delegate briefs short** and point at the contract (G4's `DELEGATE.md` is
   the mechanical part, one page). Long briefs died with length-stops producing no
   files.
6. **The smoke and the acceptance run are where your own expectations get caught,
   not the course.** In G4 the check failed eleven times before it passed and every
   failure was the parent's arithmetic, never the kernel's: a task holding two
   frames inside a limit of four was asked to admit four more, a refused `cat`
   continues after its refused open (so its read, its write and its close are
   refused too), a fork's child inherits the parent's tick budget, and `hog` is
   stopped by its own loop's stop rather than by its next op. Treat a red
   assertion as a claim about *your* expectation until the stage's own behaviour
   proves otherwise.
7. **The `NotImplementedError` rule.** Every check must let it escape (a broad
   handler re-raises it first), or an untouched template reports as `✗` instead of
   `· not implemented yet` in `./cz run`. Verified both ways: `0/10` on the
   templates, `10/10` with the solutions overlaid.
8. **A copied harness carries the old paths — and the old prose.** A8's
   `assemble.py` still had `HERE = ".../.h1-dev"`; A8's `course_head.py` still
   described H1's course. `.g4-dev/` was copied from `.j5-dev/` and swept
   (`grep -Hn 'j5-dev\|metrics\|trace' .g4-dev/*.py`), and **`course_head.py`,
   `course_tail.py` and `audit_course.py`'s title string were rewritten from
   scratch** because the repointed copies still carried the old thesis and the old
   ten titles. Read the copied head's prose before committing, and make the probe
   run the assembled file rather than trusting it.
9. **Mutation hygiene**: rebuild the tree per mutation,
   `PYTHONDONTWRITEBYTECODE=1`, a stale anchor is `BROKEN` not `CAUGHT`, a mutant
   that hangs counts as `[hung  ]` = caught, and a no-op or unreachable mutation is
   worthless — it surfaces later as `MISSED`. A defect invisible in the *values*
   needs a spy, not a comparison. G4's first mutation run came back `42/52` with
   five `BROKEN` (indentation copied by eye) and five `MISSED`; three of the
   misses were fixed by *adding an assertion that reaches the branch* (the frames
   a task holds mid-run, the loop charged ten ticks rather than nine, a task
   stopped at its own tick budget), and the one defect no world program can reach
   was cut rather than kept as a mutation — every program this userland has ends
   with an explicit `exit`, so the "ran out of ops" path is defensive code and not
   a mutation target. L1's capstone cut three the same way: the server's own
   broadcast echo, a segment addressed to another port, and the settle before the
   final counts — none is reachable from any scenario the course ships, so none is
   a mutation worth keeping.
10. **Register, then commit**: `path.py`, `ROADMAP.md` (the count in the header,
    the ready row, the phase table, the plan paragraph), the measured row in
    `codecraft/stats.py` (`tests` recomputable from the assembled `course.py`,
    `mutants` from the harness), `AGENT-INFRA.md`'s two
    tables when a slot closes a numbered item, the root `README.md` bullet, the
    course's own `README.md`, and this file — after deleting
    `codecraft/{history.jsonl, profile.json, mentor_cache.json}` and every
    `__pycache__`. Then `git pull --rebase --autostash origin main && git push
    origin main`, then `./cz self-test`.

### Five traps worth remembering

- **`solutions/` sorts before `stage_*.py`.** A smoke that walks a directory and
  copies the solutions as it goes gets its overlay overwritten by the templates
  that follow. Copy the templates first, the solutions last — `.g4-dev/smoke.py`
  does exactly that.
- **`ast.get_source_segment` is not a body extractor.** Assemble bodies by line
  range (`statements[0].lineno` … `statements[-1].end_lineno`), verbatim, then
  dedent once; the symptom is an `IndentationError` in a file that looks correctly
  indented.
- **A course directory that is not committed yet has no `git checkout` to fall
  back on.** Overlaying the solutions onto the templates to watch `10/10` is worth
  it — but back the ten templates up to the dev directory first (`cp -a
  stage_*.py .g4-dev/templates/`) and `cmp` them after restoring. `git pull
  --rebase` also refuses with unstaged changes: `--autostash` is the way to push
  around them.
- **A delegate that contradicts the contract is usually right, and a death is not
  a verdict.** Three of J5's four stage-level findings began as a delegate's
  objection, and G4's stage 4 found the provided `PageFault` missing `.user` —
  a contract the world itself did not keep, fixed in the world and pinned by two
  checks. Treat an objection as evidence and re-run the check before overruling
  it; and when a reason, a branch or a mutation cannot be reached, the world or
  the order is wrong — not the check that failed to reach it.
- **A check is worth exactly the mutations it catches.** Fifty-one mutations and a
  check that pins the log act by act, the audit line by line, the report's six
  numbers against the machine's and four tampers that must be *detected* — that
  is the standard. An assertion nobody can break is not a test, and a mutation
  that nothing can catch is a design bug: strengthen the check or cut the rule.

## Ground rules

- **Deterministic, offline, integer-only.** No `time`, `threading`, `asyncio`,
  `random`, `os.environ`, `uuid`, no module-level mutable state, and **no float
  anywhere**: every count is an int, every ratio an exact reduced pair, so a run is
  a function of its inputs and a check can assert a number instead of timing
  something. G4 adds two of its own: a kernel is a *dict of records* rather than an
  object graph, and the only randomness in the whole course is the order the
  scheduler chooses to be fair in.
- **Docs in the repo are English**; the user writes Spanish, so answers are in
  Spanish with paths and identifiers verbatim.
- **The user's twelve-item list in `AGENT-INFRA.md` stays verbatim (Spanish)**,
  and so do the two lists in `AI-ENGINEER.md` and the three in `NETWORKING.md`;
  the analysis around them is English.
- `./cz` is `python3 codecraft/cli.py`. Before committing: no `history.jsonl`, no
  `profile.json`, no `mentor_cache.json`, no `__pycache__`.
- Ask before destructive commands; a course's own templates are the exercise, so
  never "fix" a stub into a solution outside `solutions/`.
