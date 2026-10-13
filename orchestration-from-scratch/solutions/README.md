# Solutions

One file per stage, in the order the course builds them. Each one is the
reference answer to its template: read it after your own attempt, not before.

| File | Stage | What it decides |
|---|---|---|
| `stage_01.py` | 1 | `SUBTASK_KEYS`, `Subtask`, `parse_subtask`, `parse_graph`: every key a shape spells, every default materialised, and a typo refused by name — with the key it was probably meant, at edit distance two |
| `stage_02.py` | 2 | `dependencies`, `waves`, `would_cycle`, `validate_order`: the edge set, the levels a dependency forces, and the cycle named by its path |
| `stage_03.py` | 3 | `runnable`, `dispatchable`: the nodes that may start now — every own dependency `ok` — and the cap against what is already running |
| `stage_04.py` | 4 | `HandoffError`, `budgeted`, `handoff`, `render_prompt`: a token is a character, the cut is exact, and a child receives its own dependencies' accepted results and nothing else |
| `stage_05.py` | 5 | `MAX_REWORK`, `review_prompt`, `accepts`, `rework_prompt`, `next_attempt`: the acceptance predicate, the reason that travels to the next attempt, and where a rejection becomes a failure |
| `stage_06.py` | 6 | `skip_set`, `propagate`: the transitive dependents of a failure, skipped without running, over a fresh id-sorted table that never overwrites what already finished |
| `stage_07.py` | 7 | `approval_prompt`, `needs_approval`, `answers`, `gate_status`: the effect that waits for an answer, and the dispatch held — never placed — while the answer is missing |
| `stage_08.py` | 8 | `BudgetExhausted`, `spend`, `affordable`, `budget_line`: `spent + node.tokens <= budget` asked before the call, and a line of two exact ints |
| `stage_09.py` | 9 | `RecordError`, `EVENT_KEYS`, `RUN_KEYS`, `record`, `report`: six fields, seven kinds, no payload text, and every report number recomputed and checked against the claim |
| `stage_10.py` | 10 | `DEFAULT_LIMIT`, `run`: the loop over the injected clock that composes the nine, ends with stage 9's report, and returns identical values on two runs of one fixture |

## The ladder

The stages compose, and each solution imports only what it stands on — a stage
may import **only stage 1** plus the provided modules, which the course audit
enforces:

- on `graphs` (and stdlib) alone: **1**, the container and the parser every other
  stage stands on.
- on stage **1**: **2**, **3**, **4**, **6** and **9**.
- on stage **1** and `agents`: **5** (`Reply`, `VERDICTS`), **7**
  (`APPROVALS`) and **8** (`Reply.tokens` as the cost a call reports).
- on stages **1**–**9**, `agents` and `fleet`: **10**, the capstone, which drives
  the whole plan over J1's `Clock` and returns the states, the events, stage 9's
  report, the tick reached and every prompt it handed out.

Each earlier stage keeps its own refusal family — `OrchestrationError` and a
derived `HandoffError`, `RecordError` or `BudgetExhausted` — so one `except` still
catches a broken graph anywhere in the course.

## Copying them over

The course runner solves a stage by overwriting its template with the solution:

```bash
cd orchestration-from-scratch
cp solutions/stage_01.py stage_01.py     # one stage at a time
python3 ../codecraft/cli.py run orchestration-from-scratch
```

The dev harness does the same thing into a temporary tree — the templates in this
directory are never modified in place — and re-runs each stage's check and its
mutation proof after the copy. The smoke composes all ten in one process, and
backing the ten templates up before an overlay (and `cmp`-ing them after) is the
habit that keeps the exercise honest.
