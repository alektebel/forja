# Solutions

One file per stage, in the order the course builds them. Each one is the
reference answer to its template: read it after your own attempt, not before.

| File | Stage | What it decides |
|---|---|---|
| `stage_01.py` | 1 | `LINE_KEYS`, `DurableError`, `JournalError`, `line`, `parse_line`, `write_line`: the eight fields, the nine kinds, the fields each carries and needs, and a refusal that always names the offender |
| `stage_02.py` | 2 | `append`, `commit`, `lost`, `survives`: the same line as a prediction and as a fact, and the exact tuple of bytes a crash would take back |
| `stage_03.py` | 3 | `ReplayError`, `replay`, `state_of`, `torn`: the journal as records, the state table they imply, and the unfinished tail that is a *question*, never a guess |
| `stage_04.py` | 4 | `LeaseError`, `claim`, `lease_of`, `expired`, `renew`: a claim line carrying a length, the deadline derived, expiry inclusive, and a steal refused by naming both owners |
| `stage_05.py` | 5 | `MAX_MISSES`, `heartbeat`, `dead`, `recover`, `reclaimable`: the beat that renames a deadline, the grace that separates *expired* from *dead*, and a recovery that is a pure reading |
| `stage_06.py` | 6 | `RecoveryError`, `crash`, `recovered`: the kill, the survivors (`synced` and nothing else), the `expire` lines the dead owners' jobs owe, and the states a process may believe afterwards |
| `stage_07.py` | 7 | `INTENT_TICK`, `EffectError`, `intent`, `apply_effect`, `settle`: the intent synced before the effect, the effect under the job's own key, and the replay's three-way answer (`applied`, `already`, `recorded`) |
| `stage_08.py` | 8 | `DEFAULT_CHECKPOINT`, `ResumeError`, `checkpoint`, `read_checkpoint`, `repair`, `resume`: the checkpoint that folds what is decided, the tail that is replayed, the run refused by name, and the one function allowed to edit a log |
| `stage_09.py` | 9 | `REPORT_KEYS`, `report`, `audit`: eleven counters recounted from the lines, a caller's total, table or world refused when it contradicts them, and the same walk reporting instead of raising |
| `stage_10.py` | 10 | `DEFAULT_LIMIT`, `LEASE_TICKS`, `run`: two workers, a kill in the middle, and a resume over the same disk that ends with the untouched run's states and every effect applied exactly once |

## The ladder

The stages compose, and each solution imports only what it stands on — the course
audit refuses an import of a *later* stage, and the nine stages below the
capstone keep to stage 1 on purpose, so that a stage is solvable on its own:

- on `fleet` and `disk` alone: **1**, the vocabulary every other stage stands on.
- on stage **1** and `disk`: **2**, **3**, **5**, **6**, **8** and **9**.
- on stage **1**, `disk` and `work`: **4** and **7** (the plan's jobs and the world
  an effect lands in).
- on stages **1**–**9**, `fleet`, `disk` and `work`: **10**, the capstone, which
  composes all of them — `commit`, `replay`/`state_of`, `claim`, `heartbeat`/
  `reclaimable`, `MAX_MISSES`, `crash`, `intent`/`settle`, `checkpoint`/
  `read_checkpoint`/`resume`, `report` — over the injected clock and returns the
  states, the events, stage 9's report, the tick it stopped at and what its crash
  discarded.

Note the consequence of that rule for stage 6: it cannot import stage 5, so it
restates `MAX_MISSES` and the grace rule it needs. Two checks pin the same rule,
independently.

Each stage keeps the course's one refusal family — `DurableError`, with a derived
`JournalError`, `ReplayError`, `LeaseError`, `RecoveryError`, `EffectError` or
`ResumeError` where the stage has something of its own to say — so a single
`except DurableError` still catches a broken stage anywhere in the course.

## Copying them over

The course runner solves a stage by overwriting its template with the solution:

```bash
cd durable-execution-from-scratch
cp solutions/stage_01.py stage_01.py     # one stage at a time
python3 ../codecraft/cli.py run durable-execution-from-scratch
```

The dev harness does the same thing into a temporary tree — the templates in this
directory are never modified in place — and re-runs each stage's check and its
mutation proof after the copy. The smoke composes all ten in one process, and
backing the ten templates up before an overlay (and `cmp`-ing them after) is the
habit that keeps the exercise honest.
