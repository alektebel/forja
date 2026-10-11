# Solutions

Finished, runnable versions of each stage. Read them *after* attempting — a
solution read cold is just more prose.

| File | Stage |
|---|---|
| `stage_01.py` | Typed specs, one canonical text per spec |
| `stage_02.py` | Admission, `QueueFull`, depth, the sequence |
| `stage_03.py` | Priority as a total order: `(-priority, seq)` |
| `stage_04.py` | The concurrency limit checked before the worker runs |
| `stage_05.py` | The lease: `deadline_at`, `sweep`, `ack`, `release` |
| `stage_06.py` | A growing backoff on the injected clock, and dead letters |
| `stage_07.py` | The water mark and the three answers: refuse, shed, block |
| `stage_08.py` | Ageing as a second order, not a second clock |
| `stage_09.py` | `run_record`: every number rebuilt from the log |
| `stage_10.py` | The loop, the bounds, and canonical JSONL bytes |

Stages 4–10 build on the earlier ones (`stage_04` imports `stage_02` and
`stage_03`, `stage_07` adds `stage_06`, `stage_10` runs the whole ladder), so
copying one over its template needs the earlier ones in place too.

To compare a stage, copy it over the template and re-run the checker, then
restore the template if you want to try again:

```bash
cp solutions/stage_07.py stage_07.py
python3 codecraft/cli.py run queue-and-workers-from-scratch
```

All ten pass their checks with the standard library alone: no threads, no
asyncio, no wall clock, and no float anywhere — every count is an int, which is
what lets a check assert the numbers a run produced instead of timing it.
