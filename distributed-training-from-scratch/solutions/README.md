# Solutions

One file per stage, in the order the course builds them. Each one is the
reference answer to its template: read it after your own attempt, not before.

| File | Stage | What it decides |
|---|---|---|
| `stage_01.py` | 1 | The step as a plan: bytes per rank and over the network, the ledger, and the tick model every later stage prices itself with |
| `stage_02.py` | 2 | Data parallel: the gradient bucketed, all-reduced, and overlapped with the compute |
| `stage_03.py` | 3 | ZeRO's ladder: which of the four state lines are sharded, and at what cost |
| `stage_04.py` | 4 | FSDP: the wrap policy, the per-unit gather and scatter, and the peak memory |
| `stage_05.py` | 5 | Tensor parallel: the column block, the row block, and the two all-reduces per block |
| `stage_06.py` | 6 | The pipeline schedules: GPipe and 1F1B, and the bubble replayed from the slots |
| `stage_07.py` | 7 | Interleaving: `m·v` units over `p` stages, and the activation lifetimes |
| `stage_08.py` | 8 | Expert parallel: the routing table, the capacity cap, the balance loss, dispatch and combine |
| `stage_09.py` | 9 | Ring attention: the exact running pivot, its accumulator, and the KV ring |
| `stage_10.py` | 10 | The configuration: every split priced, the argmin chosen, and the report derived from the plan |

## The ladder

The stages compose, and each solution imports only what it stands on:

- on `fabric`, `model` and `plans` only: **1** (with `model` and `fabric`), **6**
  and **7** (with `model` alone — the two schedules are self-contained, and stage 7
  builds on stage 6's slot model rather than importing it), **8** and **9**.
- on stage **1**: **2**, **3**, **4**, **5**, **8**, **9** — every one of them
  prices itself with stage 1's `plan_ticks`/`step_ticks` and states its ledger as
  stage 1's `MemoryLine`s.
- on stages **1, 3, 4, 5, 8, 9**: **10**, the capstone, which composes the axes
  and adds the data-parallel axis from `plans.py` directly.

## Copying them over

The course runner solves a stage by overwriting its template with the solution:

```bash
cd distributed-training-from-scratch
cp solutions/stage_01.py stage_01.py     # one stage at a time
python3 ../codecraft/cli.py run distributed-training-from-scratch
```

The dev harness does the same thing into a temporary tree — the templates in this
directory are never modified in place — and re-runs each stage's check and its
mutation proof after the copy.
