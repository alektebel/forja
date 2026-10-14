# Durable Execution From Scratch

A run is not the process that started it; it is the log on disk. Ten graded
stages between a task that runs once, on a machine that stays up, and a run that
survives being killed in the middle of itself — on a provided disk that can lose
everything it was not told to sync, and a scripted fleet whose fixtures fail,
die, and come back.

```
python3 codecraft/cli.py run durable-execution-from-scratch
```

Stage 1 is `stage_01.py`. Every stage is a template with `DESIGN DECISION`
docstrings and `NotImplementedError` stubs; the reference implementations are in
`solutions/`, stage for stage. The checks live in the harness that produced the
course (`/home/diego/Desarrollo/.j3-dev/`): `check_NN.py` is the stage's own
caller, `run_all.py NN` runs it against the templates, `mutate_NN.py` plants
mutations in the solution and proves the check catches every one, and
`python3 smoke.py` walks the ten stages composed in one process.

## Provided complete — you do not write these

| File | What it is |
|---|---|
| `fleet.py` | J1's clock and task/pool specs, copied verbatim: an injected `Clock`, immutable `TaskSpec`/`PoolSpec` records, and the scripted workers (`instant`, `reliable`, `sluggish`, `flaky`, `crasher`, `dying`, `always`) that are honest about what they cost. Nothing here is timed and nothing is threaded. |
| `disk.py` | The whole world, and the reason this course exists: `Disk` with an append-only `write`, a whole-file `replace`, the **`sync`** that is the only thing that makes a byte survive, the **`crash()`** that discards every unsynced byte and hands back what it cost, and the two readings that never lie — `read` (what this process can see) and `synced` (what the disk would keep). `DEFAULT_JOURNAL` is `/var/log/durable/journal`. |
| `work.py` | The job as data — frozen `Job(id, label, ticks, key, value)` — the six fixtures (`fast`, `slow`, `flaky`, `fragile`, `bulk`, `hopeless`), and `Effects`, the world an effect lands in: `apply(key, value, tick)`, `count(key)`, `applied()`, `value(key)`, `log()`. `Effects` deliberately does **not** deduplicate, so `count(key) == 2` is observable and exactly-once is a fact you can check instead of a promise you can make. |

## The ten stages

| # | Template | What it decides |
|---|---|---|
| 1 | `stage_01.py` | The line, and the journal that holds it: the eight fields, the nine kinds, every field a kind carries and needs, and a typo, a missing field or a negative count refused by name (with the name it was probably meant). `write_line` appends and **never** syncs — a line is a prediction until a sync makes it a fact |
| 2 | `stage_02.py` | The write that was not synced did not happen: `append` versus `commit`, `survives` for whole terminated lines only, and `lost()` — what a crash would discard — asserted equal to what `crash()` actually discs |
| 3 | `stage_03.py` | Replay, and the tail that was never finished: the journal as records, the state table the lines imply (`pending`, `running`, `done`, `failed`, `expired`), and `torn(text)` — the half-written tail a crash leaves, refused by index and text rather than guessed at |
| 4 | `stage_04.py` | The lease, and the owner that stops answering: a claim as a line carrying a *length*, the deadline derived (`claimed_at + ticks`), expiry inclusive at the deadline, a live lease that cannot be stolen, and `renew` naming both the caller and the holder |
| 5 | `stage_05.py` | The heartbeat, and the worker that dies holding the slot: a beat as a *line* that renames the deadline, a beat after the deadline refused (it is a claim, not a beat), `MAX_MISSES` as the policy that separates *expired* from *dead*, and `recover` — a reading that writes nothing |
| 6 | `stage_06.py` | Crash, and the process that comes after it: `crash` replays only what the disk would keep, writes the `expire` lines a dead owner's job owes, and returns the lost bytes; `recovered` rebuilds the same states from the disk alone, never from the caller's belief |
| 7 | `stage_07.py` | The effect that happens exactly once: the `intent` written **and synced before** the effect runs, the effect applied under the job's own key (never a per-attempt one), and `settle` — the replay's decision, answered by the world's own `count`, that either records what landed or re-applies what did not |
| 8 | `stage_08.py` | The resume, and the log that is not this run's: a checkpoint as a whole-file rewrite beside the append-only journal, `resume` replaying only the lines *after* it and refusing another run's or another plan's log by name, and `repair` — the one function that edits a log, which drops the torn fragment and never a whole line |
| 9 | `stage_09.py` | The report, and the number that has to come from the log: eleven counters recomputed from the lines, a caller's total, table or world that contradicts the log refused by name, and `audit` reporting the disagreement — against the log the *disk* would keep — instead of raising |
| 10 | `stage_10.py` | Two workers, one killed holding the lease: the cap, the heartbeats, the intent-then-effect pair, a kill in the middle of the run, and a resume over the same disk that ends with the untouched run's states and every effect applied exactly once |

## What the course refuses to hide

- **A line is a prediction; only a sync is a fact.** `write_line` never syncs,
  `claim` never syncs, and the effect line never syncs — because the world is the
  proof of an effect — while the `start` line, the `intent` and a checkpoint
  always do. Which writes may be lost is a *decision*, and the course makes you
  make it explicitly.
- **A claim is a length, not a deadline.** The line carries `ticks`; the deadline
  is `claimed_at + ticks` for a claim and `now + ticks` for a heartbeat. A
  stored deadline would be an answer that goes stale in the one place a log is
  read — after a crash.
- **`expired` is not `dead`.** `expired` is arithmetic (`deadline <= now`); `dead`
  is policy (`misses >= MAX_MISSES and now >= deadline`), the misses are the
  caller's observation and the decision is the function's, and both boundaries
  are inclusive. A lease inside its deadline is alive however many beats a caller
  counted.
- **Recovery is a reading.** `recover` takes lines and returns a table; it has no
  disk argument at all. Only `crash` writes, and it writes the `expire` line that
  a dead owner's job owes, synced.
- **Exactly-once is data, not a promise.** The `intent` is on disk before the
  effect runs, `settle` asks the world's `count(key)`, and `Effects` never
  deduplicates — so an exactly-once claim is checkable, and the classic bug
  (apply again under a fresh per-attempt key) shows up as `count(key) == 2`.
- **A resume is not a replay of everything.** The checkpoint folds what has
  already been decided, the journal is the tail after it, and a log that belongs
  to another run or another plan is refused by name.
- **The report is the log, or it is wrong.** Every counter is recounted from the
  lines, `ticks` is the highest tick the log names, and a caller's total, state
  table or world that contradicts the lines is refused naming the key and both
  numbers.
- **Two death paths, and the log says which one happened.** A worker killed
  before any sync leaves nothing behind — its claim was a prediction — so the
  job is `pending` and the next process claims it at once. A worker killed after
  a sync leaves a durable lease that the next process has to honour until it
  lapses. Neither is ever silently believed, and a job is never `done` while its
  lease is held by a process that no longer exists.

## Constraints

Standard library only, offline, deterministic: no `time`, `threading`, `asyncio`,
`random`, `os`, `uuid`, `socket` or `subprocess`, no module-level mutable state,
and **no float literal anywhere** — ticks and counts are ints. Time is the
injected `fleet.Clock` and the disk is `disk.Disk`, so two runs of the same
fixture produce identical values and a crash is reproducible instead of hoped
for. Every check is a plain `python3` script; nothing here reads a network, a
file or a clock.

## Verified

Ten checks (`check_01.py` … `check_10.py` → `PASS`), 558 planted mutations
(`mutate_all.py 01 … 10` → `TOTAL 558/558`, `MISSED OR BROKEN: 0`), ten stages
audited (`audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0`), `assemble.py`
→ `assembled 10 checks, 5098 lines, compiles`, `probe_manifest.py` →
`MANIFEST: 10/10 clean`, `smoke.py` → `SMOKE PASS — 39 probes, the durable course
composed`, and the course itself: `0/10` on the templates, `10/10` with the
solutions overlaid.
