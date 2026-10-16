# Next session — where everything is

Written at the end of the session that shipped **L3
(`mqtt-broker-from-scratch`)** — a broker whose every frame its own reader takes
back, on a provided byte-pipe transport (`streams.py`) and a provided policy table
(`grants.py`): ten stages from the fixed header and its variable-length integer to
a capstone that runs one scenario twice, re-reads its own trace and holds its
report against the transport's log — **600 planted mutations**. Phase L is closed:
L1, L2 and L3 are all in the ready table. Everything in *Done* is committed and
pushed; the section after it is the commit that carries this file.

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

## The unit this file carries — L3 `mqtt-broker-from-scratch`

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

- **`./cz dag`** prints the whole registry as waves: `60 projects · 87 hard edges ·
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
  caught mutations** at the time (nineteen and 10,452/4,633 after L1).
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

## In flight — nothing

The next unit is **L4, `git-from-scratch`** — the other artifact in this repository
that another program validates: a `.git` directory real `git` reads, with blobs
addressed by their own digest, trees whose entries are sorted and whose modes are
exact, commits that carry an author and a parent, refs and a detachable HEAD, an
index that stages, a diff that names a hunk, a merge that finds the base and marks
the conflict instead of guessing, and a packfile whose delta-compressed objects are
reachable through its index — where `git` is on PATH and `git fsck` and `git log`
are the judge. It needs G4, and L3 was the last of the three L slots. Twelve
*projects* — not slots — are queued in `ENTERPRISE.md`: the enterprise-AI list kept
on `claude/enterprise-ai-project-guides`, each row naming what this repository
already has for it and the gap that remains.
The rows registered in the units before this one queue behind it, one per slot —
G7, G8, H5, H6, H7, L4, then I13, I14, H8 — each carrying its own thesis in
`path.py`, each with its place in `cz dag`. After those: G5/G6 (phase G's
remaining two, which need checkers, not writing) and phase K's five. The backlog
is **23 `author`, 6 `legacy`, 2 `salvage`, 29 `ready` — 60 rows** — `./cz path`,
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
