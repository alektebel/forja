# Solutions

One file per stage, in the order the course builds them. Each one is the
reference answer to its template: read it after your own attempt, not before.

| File | Stage | What it decides |
|---|---|---|
| `stage_01.py` | 1 | The graph and the order: `Node`, `add`, `mul`, a diamond-once `backward`, and `zero_grad` |
| `stage_02.py` | 2 | The other derivatives: `sub`, `div`, `pow`, `neg`, all in exact pairs |
| `stage_03.py` | 3 | Broadcasting and the reduction: which operand is reduced, `sum`'s axis, and `mean`'s extent |
| `stage_04.py` | 4 | The chain rule through a matrix: `matmul`'s two VJPs and the fixture `mlp` around them |
| `stage_05.py` | 5 | Reuse and freezing: `shared` as identity, `trainable` as a stop that drops the stale gradient |
| `stage_06.py` | 6 | The seed of a non-scalar output, and `sum_to_scalar` as the caller's collapse |
| `stage_07.py` | 7 | `detach`: the cut edge, and the `no_grad` region that restores what it found |
| `stage_08.py` | 8 | The kink: `max`, `relu`, `abs`, and the tie that goes to the left operand |
| `stage_09.py` | 9 | The oracle: the exact central difference, and the check that compares pairs |
| `stage_10.py` | 10 | The capstone: `sgd`, `train`, and `reproduce_reference` over the fixture's own run |

## The ladder

The stages compose, and each solution imports only what it stands on — a stage
may import **only earlier stages**, which the course audit enforces:

- on `exact` alone: **1** (the container, the engine and the two local
  derivatives every other stage reuses).
- on stage **1**: **2**, **3**, **5**, **6**, **7**, **8** and **9**.
- on stages **1** and **3**: **4**, which reuses the broadcasting `add` for its
  bias and carries its own private activation — stage 8 comes *later*, so
  importing it would be a forward import.
- on stages **1**, **3** and **4**, plus `fixtures`: **10**, the capstone, which
  composes `mlp` with `mean(mul(sub(out, y), sub(out, y)))` and drives it.

## Copying them over

The course runner solves a stage by overwriting its template with the solution:

```bash
cd autograd-from-scratch
cp solutions/stage_01.py stage_01.py     # one stage at a time
python3 ../codecraft/cli.py run autograd-from-scratch
```

The dev harness does the same thing into a temporary tree — the templates in this
directory are never modified in place — and re-runs each stage's check and its
mutation proof after the copy. The smoke composes all ten in one process, and
backing the ten templates up before an overlay (and `cmp`-ing them after) is the
habit that keeps the exercise honest.
