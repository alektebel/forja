# Concurrent Servers From Scratch

Build the four servers that run on a link you did not write. `link.py` is
provided complete: a `Link(clients, *, outbox=8, clock=None, seed=0)` that
carries `bytes` in both directions on named connections and moves them only when
its clock moves — `step()` is the only mover — with `MAX_CHUNK = 64` bytes a
move, `BACKLOG = 4` clients the listener holds, and an outbox of 8 bytes per
connection taking what fits and handing back how much it took. Every move it
makes is in its own log (`accept`, `listen`, `read`, `write`, `drop`, `drain`,
`close`) and in its own counters, including the ones nobody wants to read:
`drops`, `bytes_dropped`, and a `close` whose `cause` is `"patience"` because the
client gave up. `fleet.py` is provided complete as well, and it is J1's file
copied byte for byte — the clock this link is handed when you would rather not
use the one inside it, and the subject the threads half of this course is the
other half of.

What is *not* here is the server. A server is a policy about who gets the
processor, and this course is the four policies side by side on one workload: a
blocking server that waits for one client and starves the rest; a scheduler whose
interleaving the check chooses rather than the operating system; a reactor whose
readiness is a set and whose poll loop never busy-waits; and an event loop with a
timer queue. Between them are the mechanics every real one has: a connection as a
state machine, an outbox that has to be counted rather than assumed, a reply
bigger than the outbox that has to be deferred in a connection's own state,
callbacks as a handle table with cancellation, futures and `async`/`await` as a
desugaring onto the same loop, head-of-line blocking made a number, and a command
loop with per-connection state on one shared store. This is the repository's
second principle — *MVP first, then complicate, driven by limit cases* — applied
to a server, and the ladder is the one J1's queue and J3's durable executor are
already on; this course is the half that asks who runs next, and it answers
with a step count.

The world is refused the two things that would make the answer unfalsifiable.
There is no wall clock: `time`, `threading` and `asyncio` are banned *because they
are the subject*, and a step of a scheduler here is an entry in a log rather than
an interval. There is no randomness: a `Link` is a function of its clients, its
seed and the number of times it was stepped, so two runs of one workload are one
run.

Every one of the failures below is a check here, and every one of them leaves the
stage's own output unchanged and is only visible through the link:

- a reply staged as soon as any byte of the request arrived, so the link carries
  an answer to half a request and `bytes_written` proves it;
- a connection between two requests reported as finished, so the second request
  reaches a server that has already closed the socket;
- a connection handed to a step function that belongs to another link, stepped
  happily until two worlds disagree about one connection;
- one slow client served last instead of starving everybody else, so the
  blocking model's `steps` look like the reactor's and the lesson disappears;
- a thread that yields to nobody, so the chosen interleaving is a lie and the
  answer depends on the order the caller built a list in;
- a poll loop that services a connection that is not ready, so a read returns
  nothing and the reactor's `steps` count a turn it did not need;
- a timer queue that fires a timer early because `next_at` was handed the wrong
  tick, so a client that was still writing is timed out and its connection is
  drained with bytes still owed;
- a handle table that runs a callback it was told to cancel, and a callback
  whose return value is asked for rather than awaited, so a chain that should
  have been cancelled ran;
- a future that settles twice, so one loop's answer depends on which writer got
  there first;
- the deferred remainder of a reply dropped instead of kept in the connection's
  state, so the reply is short and `bytes_drained` is where the missing bytes are;
- an offset reset on every `send`, so the reply's opening bytes reach the client
  twice and the answer is longer than the request ever asked for;
- `stalled` computed as "everyone slow" instead of "everyone whose pending bytes
  did not move", so head-of-line blocking is attributed to the client rather than
  to the write path;
- an expired key still counted by `KEYS`, because the deadline was checked on
  `GET` and nowhere else;
- an input buffer cleared on a partial read, so a command split across two reads
  is lost and its client waits forever for an answer nobody owes;
- two commands in one read executed as one, so a pipeline answers once;
- per-connection state kept in the loop variable, so two clients share one
  buffer and one client's `QUIT` closes the other's connection;
- the four models run on one link, so the second model starts with the first
  one's leftovers and its answers agree with the first model's for the wrong
  reason;
- a model's own report believed instead of the link's log, so a server that
  believes it answered while the client received less is graded as correct;
- `same_answers` true because every model delivered nothing, which is the
  comparison worth nothing dressed as the comparison worth everything.

Nothing here runs on a thread, a wall clock or a `random`. Where a decision was a
judgement call it is written down in the template's own docstring as a DESIGN
DECISION, and the check asserts the consequence.

## The provided world

| Module | What it is |
|---|---|
| `link.py` | The link and its clients: `Link(clients, *, outbox=8, clock=None, seed=0)` with `step`, `accept`, `listen`, `read`, `write`, `close`, `drain`, `idle`, `done`, `conns`, `waiting`, `readable`, `writable`, `owed`, `drainable`, `connection`, `now`, `events`, `log`, `stats`; `Client(name, requests, *, read_every=1, chunk=64, patience=0)`; `Connection` with `id`, `client`, `arrival`, `link`, `inbox`, `outbox`, `pending`, `sent`, `request`, `owed`, `used`, `requests_done`, `closed`, `cause`, `waited`, `listened`, `current()`; `MAX_CHUNK`, `BACKLOG`, `DEFAULT_OUTBOX`, `EVENTS`, `CLOSE_CAUSES`, `LinkError` |
| `fleet.py` | J1's world, byte for byte: `Clock` (`.now()`, `.tick(n=1)`, `.ticks`), `TaskSpec`, `PoolSpec`, `make_task`, `make_pool`, `Worker`, `outcome`, the scripted workers (`reliable`, `instant`, `sluggish`, `flaky`, …), `TASKS`, `POOLS`, `OUTCOMES`, `QueueError` |

The link carries bytes and never looks inside them, so **the protocol is the
course's own**: a request is a line ending in `"\n"`, a reply is that line with
`REPLY_PREFIX` in front of it, and stage 9 is the one stage that replaces it with
a real one (`+OK\r\n`, `$<n>\r\n<bytes>\r\n`, `:<n>\r\n`, `-ERR <why>\r\n`,
`+BYE\r\n`). The link is the record every claim is checked against and it is never
written by the model it grades: `stats()` reports fourteen counters, `log()`
every event with the tick it happened at, and a stage's own ledger is compared
against both — a ledger counted from the server's beliefs agrees with itself by
construction, which is exactly the comparison worth nothing. A client's
`patience` is a count of ticks it will wait with nothing arriving before it walks
away, a connection that is closed with bytes still owed records them as
`bytes_dropped`, and `Link.done()` is a fact about the world rather than an
opinion about the server: every client finished, or gone.

## The stages

| # | File | The stage | The mechanism |
|---|---|---|---|
| 1 | `stage_01.py` | The connection as a state machine | `STATES`, `REPLY_PREFIX`, `open_conn`, `step_conn`, `finish`, `stats` |
| 2 | `stage_02.py` | The blocking server, and the slow client | `serve_blocking` |
| 3 | `stage_03.py` | Threads, and the interleaving the check chooses | `STEP_STATES`, `THREAD_STATES`, `Scheduler` (`spawn`, `ready`, `step`, `run`), `serve_threads` |
| 4 | `stage_04.py` | The reactor: readiness as a set, and no busy-waiting | `ready_set`, `serve_reactor` |
| 5 | `stage_05.py` | The event loop and its timers | `DEFAULT_IDLE`, `DEFAULT_BUDGET`, `Timers` (`arm`, `cancel`, `due`, `next_at`), `serve_with_timeouts` |
| 6 | `stage_06.py` | Callbacks as data, and the one that must not run | `Handles` (`register`, `cancel`, `ready`, `take`), `serve_callbacks` |
| 7 | `stage_07.py` | Futures and `async`/`await` as a desugaring | `MAX_CHAIN`, `CHAIN_STATES`, `Future`, `await_`, `chain`, `Loop` (`spawn`, `run`), `serve_async` |
| 8 | `stage_08.py` | Backpressure, and the write that has to be deferred | `DEFAULT_BUDGET`, `send`, `serve_backpressure` |
| 9 | `stage_09.py` | The Redis case study: a command loop with per-connection state | `COMMANDS`, `parse`, `execute`, `serve_commands` |
| 10 | `stage_10.py` | One workload, four models, and the steps it took | `MODELS`, `workload`, `run_all`, `compare`, `cross_check` |

The stages are cumulative in the only direction that matters: a stage imports the
world and the earlier stages it needs, and nothing from a later one. Stage 1
takes `MAX_CHUNK` from the link and nothing else; stages 2, 3, 4, 5, 6 and 7
import stage 1 (stage 3 also takes the link and `heapq`, stage 5 the link); stage
8 imports stages 1 and 4; stage 9 imports stages 1 and 4; and stage 10 composes
stages 2, 3, 4 and 5, because those four are the four models it runs against each
other. That is what lets stages 2 to 7 be built at once — and why 8, 9 and 10
need the reactor to exist before their checks can run.

One workload is the whole point of the last stage, and its four clients are the
four pressures this course is about: one client answered at once, one with two
requests (so no model may close a connection between them), one that reads two
bytes every third tick, and one whose request and reply are longer than a
`MAX_CHUNK` move (so every model has to defer a write and nobody can finish a
reply in a turn). On that workload the four models deliver the same 148 bytes and
cost 42, 54, 19 and 23 steps; the reactor is the cheapest *here*, and the check
asserts the blocking model is not the cheapest, because one slow reader is enough
to say so.

## How to use this directory

```bash
python3 codecraft/cli.py run concurrent-servers-from-scratch      # what to build next, and why
python3 codecraft/cli.py stage concurrent-servers-from-scratch 4  # one stage: the file, what you write, what the tester costs
```

Or without codecraft: the templates are ordinary modules, and an unimplemented
one raises `NotImplementedError`. Implement them at the top level; finished
versions are in `solutions/`, and nothing beyond `solutions/` ships a solution or
a hint in this directory. The templates fail and the solutions pass, and that is
the whole grading loop — this course is checker-driven and there is no test
framework anywhere. The ten checks are assembled into `course.py`, and every one
of them is a module-level `def check():` of bare
`assert <condition>, "<message>"` statements, where the message names the mistake
rather than the symptom; an untouched template reports as not implemented yet
rather than failing for the wrong reason, because the check lets
`NotImplementedError` escape before any broad `except` catches it. Every check
builds its own link and never mutates a module-level object, and the last section
of every check runs its own work twice and compares the two runs byte for byte,
because determinism here is asserted rather than assumed.

Every check is mutation-tested: 757 plausible wrong implementations across the
ten stages, between 50 and 118 per stage, each a minimal edit to that stage's
solution, and the stage's check must fail. A mutant that hangs its check counts
as caught, because a wrong implementation that never terminates anything is not a
passing implementation. The audit reads each template and its solution and
refuses them unless the first docstring paragraph is exactly
`Concurrent Servers From Scratch — stage NN: <title>.`, the template carries 3–6
`DESIGN DECISION — ` blocks and a `TODO: implement` line, the solution declares
every public name the template declares, the template imports nothing from a
later stage, and neither contains a float literal or imports a banned module (a
clock, a thread, an `asyncio`, a `random`, an `os`, a socket, a `subprocess`).

## Prerequisites

Standard library only — `heapq` in stage 5 is the only import that is not the
course itself. No numpy, no network, no threads, no sockets. `time`, `threading`
and `asyncio` are banned because a scheduler step counted by the model is this
course's unit and a wall clock would make the number a machine's opinion;
`random` because every fixture is deterministic and a `Link` is a function of its
seed; and `os`, `socket`, `subprocess`, `secrets`, `shutil`, `tempfile`,
`pathlib`, `uuid`, `math`, `statistics`, `decimal` and `fractions` are imports no
stage may make either. There are no floats anywhere — not in a template, not in a
solution, not in a check — so every tick, byte count, step, timeout, deadline,
offset and connection id is an `int`, and the arithmetic is written out by hand
on purpose.

You should be comfortable with dicts as records, with tuples as answers, with
`try`/`except` and with a state machine whose transitions are data. Some of the
later stages are easier if you have met a callback table and a future before, but
nothing here assumes it: stage 6 and stage 7 build both from scratch, which is
the point.

## Design decisions

- **A scheduler step, not a wall clock, is the comparison.** Every model counts
  the turns it took and the check asserts the count, so "the reactor is cheaper
  here" is 19 against 42 rather than a benchmark on a machine somebody else is
  using. The link counts ticks of the same clock, so a model that moves a byte
  outside `Link.step()` shows up as a disagreement between its own `steps` and
  the link's `ticks`.
- **The link is the tie-breaker.** `cross_check` holds a model's own account of a
  run against the link's log — the bytes its answers add up to against
  `bytes_drained`, the connections it answered against `closes`, its tick count
  against the link's — and returns the disagreements key by key rather than
  hiding them. The capstone's own check proves the tie-breaker is real by
  doctoring the log and asserting the disagreement is named.
- **A mismatch of shape raises; a verdict about content is returned.** Anything
  that cannot be the thing at all — a state that is not a mapping, a connection
  of another link, a request that is not bytes, a budget that is not a whole
  number of turns, a command that is not one of the seven — raises, naming the
  offender. Anything that is the server's own decision about a client — an outbox
  with no room, a client that walked away, a reply still waiting behind another,
  a key that expired — is returned as data, because a server's whole job is to
  decide, and a decision that arrives as an exception cannot be reported to
  anybody.
- **`done()` means "nothing is in flight and the current request is fully handed
  over".** A client between two requests is not a finished connection, because
  its next request is readable the moment the server listens again.
- **A connection knows its link.** `Connection.link` is a reference, not a copy,
  so a move with a stranger's connection is refused by name instead of quietly
  landing in the wrong world.
- **The outbox's bound is the world's, and a short write is data.** `write`
  returns what it took and the caller owns the rest; growing the outbox is the
  server widening a bound that is not its to widen, and dropping the remainder is
  the bug the stage's `bytes_drained` exists to catch.
- **One reply at a time on the write path, because that is what a server is.**
  Stage 8's loop serves the reply at the head of the queue until its client has
  taken it whole, so the client behind the slow one waits for a turn the server
  has not got — head-of-line blocking, as a count of connections that never
  moved, rather than as an apology.

## Where this stops

Deliberately left out, so you know the boundary:

- **No real sockets, no real threads, no real time.** A `Link` is a queue with
  readiness and a tick, every "thread" is a step function the check drives by
  hand, and nothing here blocks on I/O. `accept` returns a connection, not a file
  descriptor, and there is no `epoll`, no `kqueue`, no `poll(2)` and no signal
  anywhere in the course.
- **No kernel, no filesystem, no privilege.** This is a server's policy, not the
  machine under it: no syscalls, no buffer sizes to tune, no `SO_REUSEPORT`, no
  connection limit imposed by anything other than the link's own `BACKLOG`.
- **No true parallelism.** Two "threads" never run at once; the interleaving is
  chosen by the check, so every question about races is answered by a fixture
  rather than by a machine that is fast enough to lose.
- **No networking protocol beyond the courses' own line protocol and stage 9's
  RESP-lite.** Seven commands (`SET`, `GET`, `DEL`, `INCR`, `EXPIRE`, `KEYS`,
  `QUIT`) and no transactions, no pub/sub, no keyspace notifications, no Lua, no
  ACLs, no RESP3, no replication and no clustering — each of those is a subject
  with its own state machine, and one of them (durability: the log, the rewrite,
  the crash) is J3's.
- **Nothing that needs a database to be interesting.** Stage 9's store is a dict
  that lives as long as the run and the expiry deadlines are ticks of the injected
  clock; persistence, compaction and what happens after a restart are exactly the
  half of that problem this course hands to J3.
- **No TLS, no proxying, no load balancing.** A connection is plain bytes to a
  client that is a fixture; who may connect, who may publish and what a policy
  costs at the edge are J4's and L3's subjects, not this one's.
- **No performance tuning of any kind.** Latency, throughput and the shape of
  the curve under load are not measured, because a machine's speed is not a
  course's unit; the only number this course compares is steps.

## Where this sits

This is the second slot in the repository's L phase, *Programs that talk*, and it
comes after J1 `queue-and-workers-from-scratch` and J3
`durable-execution-from-scratch` — whose disciplines it inherits: J1 supplies the
clock this link is handed and the queueing half of the same question (who runs
next), and J3's executor is the other half of the same answer (what survives a
crash). Before it a server is a thing the repository has only ever driven as a
queue; after it, four servers are four policies over one workload with the same
answers and a counted number of steps each. L1 `tcp-ip-from-scratch` sits beside
it: that course builds the wire this course refuses to look inside, and L3
`mqtt-broker-from-scratch` is where a real wire format's bytes are built by hand.
