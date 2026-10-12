# Autograd From Scratch

Build a reverse-mode automatic-differentiation engine — the graph and the
topological order that visits a diamond once, the local derivatives and their
accumulation, broadcasting and the reduction it forces, the seed of a non-scalar
output, `detach`, the kink at a tie, an exact finite-difference oracle, and one
training step — on a **provided forward algebra**, with **every number an exact
rational**. Ten graded stages, pure standard-library Python, offline,
deterministic, and **no float anywhere**.

The thesis is one sentence: **the forward is given; the gradient is yours.**
`exact.py` already knows how to add, multiply, contract, reduce, reshape and
broadcast a `Tensor` of `Rational`s. What it cannot tell you is how a graph is
walked, what a node used twice is owed, what a broadcast operand's gradient must
be reduced back to, and what the derivative of the operation actually is. Every
stage asks for exactly that, and the answer is a number you assert, not a shape
you eyeball.

## The stages

Ten graded stages. Each one targets a mistake that is easy to make and hard to
notice — and every one of them is caught by a planted mutation in the dev
harness.

| # | File | The mechanism | The thing people get wrong |
|---|---|---|---|
| 1 | `stage_01.py` | The graph and the order: `Node`, `add`, `mul`, a `backward(root, seed=None)` that visits a diamond once, and `zero_grad` | A walk that visits a node once per path, so a reused node's gradient is multiplied by the path count instead of accumulated; a backward that resets where it should add |
| 2 | `stage_02.py` | The other derivatives: `sub`, `div`, `pow`, `neg` | The quotient's sign; an integer division that truncates where an exact pair was required; `pow`'s factor written as `n·xⁿ⁻¹` for a non-constant exponent |
| 3 | `stage_03.py` | Broadcasting and the reduction: `add`/`sub`/`mul` over broadcastable operands, plus `sum` and `mean` | Handing the *equal-shape* operand a reduction too (it is invisible in the values and caught by a spy on `reduce_gradient`); a `sum` that forgets to re-insert the axis it removed; a mean scaled by the wrong extent |
| 4 | `stage_04.py` | The chain rule through a matrix: `matmul`'s two VJPs (`dA = G·Bᵀ`, `dB = Aᵀ·G`) and the small `mlp` the fixtures define | Transposing the wrong operand — right on a square symmetric fixture and wrong everywhere else; a bias whose gradient is not reduced back to the bias's shape |
| 5 | `stage_05.py` | Reuse and freezing: `shared` (the very node) and `trainable` (a stop node that drops the stale gradient) | A freeze that keeps the stale gradient; a "copy" where identity was the point; a stop that still records parents |
| 6 | `stage_06.py` | The seed of a non-scalar output: `backward(root, seed)` and `sum_to_scalar` | A seed broadcast or reshaped instead of compared; a second walk owned by the stage instead of stage 1's; a collapse that loses the operand's shape on the way back |
| 7 | `stage_07.py` | `detach` and the `no_grad` region: a cut edge and a temporarily frozen leaf | A detached node that keeps parents; a `no_grad` that never restores, or that restores `False` where it found `True` |
| 8 | `stage_08.py` | The kink: `max`, `relu`, `abs` — the local factor read from the operands' values | A tie that splits the gradient instead of sending it left, so `relu'(0)` becomes `1`; a factor read from the incoming gradient |
| 9 | `stage_09.py` | The oracle: `finite_difference` (central, exact) and `gradient_check` | A one-sided difference, a `/h` instead of `/2h`, a tolerance where an exact pair would do — the cubic that must be off by exactly `h²` proves the difference |
| 10 | `stage_10.py` | The capstone: `sgd`, `train`, and `reproduce_reference` — the loss at the fixture's weights is exactly `1`, XOR is learned in eight exact steps, and the reference gradient is reproduced `Rational` for `Rational` | A step that reads the gradient it just wrote (the loss read after the update); a learning rate divided instead of multiplied; a parameter updated twice in one step |

Stages 2–10 compose the earlier ones — stage 4's `mlp` is stages 1/3/4, stage 10's
training loop is stages 1/3/4 — so they are meant to be done in order, and a stage
may import **only earlier stages** (the course audit enforces it, which is why
stage 4 carries its own private activation instead of importing stage 8's).

## The provided world

Two modules are given and are not part of the exercise.

`exact.py` is the forward algebra and the number type:

- `Rational` — an exact reduced pair, sign on the numerator, `math.gcd` at
  construction. Every `+ − × ÷` stays exact, and `//` does not exist.
- `Tensor` — cells in row-major order with a shape tuple: `shape_of`,
  `broadcast_shape`, `broadcast_to`, `reshape`, `transpose`, `sum`, `mean`,
  `max`, `abs`, `relu`, `matmul`, `zeros`, `ones`, `full`, and the elementwise
  `add`/`sub`/`mul`/`div`/`pow`/`neg` every stage calls for its forward.
- `reduce_gradient(contribution, shape, output_shape)` — the mechanical half of
  broadcasting: sum a contribution back down to the shape its operand actually
  has. It is *provided* because it is arithmetic; the graded part of stage 3 is
  knowing **when** to call it, and it is a spy on that call that catches the
  mutation no value comparison can see.
- `ExactError` for a broken number or shape, `AutogradError` for a broken graph.

`fixtures.py` is the data and the frozen references: the `AND`, `OR`, `XOR` and
`PARITY` datasets as exact rank-2 tensors, the `linear`/`mlp`/`deep` models with
their `w`/`b` tensors and the parameter names `REFERENCE_GRADIENTS` is keyed by,
`LEARNING_RATE = 1/4`, `STEPS = 200` for the cheap linear fixture,
`EXPECTED_STEPS = 8` with the exact `EXPECTED_LOSS` of those eight steps on
XOR, and the reference gradient at the initial weights.

Four rules make the rest of the course checkable:

- **The value is `exact`'s.** Every node's forward value must equal what the
  provided algebra computes for the same operation, element for element — the
  engine adds no arithmetic of its own.
- **A gradient's shape is its operand's shape.** Not the output's, not the
  broadcast shape: the shape the operand was born with.
- **Gradients accumulate; they are never assigned.** A node used twice adds up,
  and a second `backward(root)` without `zero_grad` doubles.
- **No number in this course is a float.** Every gradient is an exact reduced
  `(numerator, denominator)` pair and every comparison is `==` — there is no
  tolerance to tune, because there is nothing to round.

## Why eight steps and not two hundred

Exactness is a fact, not a budget. An exact rational's denominators grow by
roughly three bits per step, so the `2→4→1` model on XOR carries denominators of
about 11661 bits by step 8 — and each further step multiplies that by `4·D³`.
`EXPECTED_STEPS = 8` is therefore the length at which the capstone can freeze the
**whole** loss trajectory and have you reproduce it `Rational` for `Rational`:
the loss starts at exactly `1`, falls strictly, and XOR is learned by the eighth
step. The linear fixture is the cheap one: `STEPS = 200` of it stay under 1200
bits, it learns AND and OR, and it cannot learn XOR — which is the point of the
`2→4→1` model the capstone trains instead.

## How to use it

```bash
python3 codecraft/cli.py run autograd-from-scratch
```

work one stage at a time; each template states the decision it is asking you to
make and ends with `TODO: implement …`. The solutions are in `solutions/`, meant
to be read after your own attempt — `solutions/README.md` lists them in the order
the stages build on each other. When a check fails it names the shape, the index
and both exact pairs, never a tolerance.

## Prerequisites

`llm-from-scratch` (A2) is the course that assumes an engine like this one.
Nothing else: no framework, no GPU, no network, no dependency outside the
standard library.

## Design decisions

- **The forward algebra is provided whole; the backward is entirely yours.**
  Splitting the forward out is what makes the course gradable in the house style:
  every stage's value can be compared against a provided implementation instead of
  against a table of expected numbers, and a wrong gradient is a wrong *number*
  rather than a wrong shape.
- **`reduce_gradient` is provided, calling it is not.** The summation itself is
  arithmetic; deciding that an operand was broadcast — and calling the reduction
  for that operand only — is the reasoning stage 3 is about.
- **`Node` is provided as a mutable container.** Gradients accumulate *into* it,
  so the container is given and every function on top is the exercise: the
  fields, `__init__`, `__repr__` and identity `__eq__` are not what you are being
  taught.
- **The manifest is the surface of record.** The assembled `course.py` fixes each
  stage's title line and its function names, and the audit compares the templates
  against it — so a renamed function is a course problem, not a style choice.
- **An exact oracle beats an eyeballed one.** Stage 9's central difference is the
  same arithmetic the engine uses, and its one asymmetry — a cubic off by exactly
  `h²` — is asserted with `==`, at `x = 2^60` where no float comparison could see
  anything at all.

## Verification

Each stage ships with a check and a mutation proof in the course's dev harness
(`/home/diego/Desarrollo/.h2-dev/`): `check_NN.py` probes the stage's mechanism,
its refusals and its boundary cases, and `mutate_NN.py` plants one defect per
mutation in a copy of the solution and confirms the check catches it. The
acceptance bar is every planted mutation caught, at least 34 per stage.

| Stage | Mutations caught | Stage | Mutations caught |
|---|---|---|---|
| 1 the graph and the order | 46 | 6 the seed of a non-scalar output | 41 |
| 2 the other derivatives | 58 | 7 detach and the `no_grad` region | 36 |
| 3 broadcasting and the reduction | 64 | 8 the kink | 52 |
| 4 the chain rule through a matrix | 63 | 9 the oracle | 41 |
| 5 reuse and freezing | 45 | 10 the capstone | 58 |

504 mutations across the ten stages, `MISSED OR BROKEN: 0`; the course audit —
every stage's template shape, docstring contract, refusal classes and imports —
reports `PROBLEMS: 0`; `assemble.py` builds the manifest into
`autograd-from-scratch/course.py` (10 checks, 5412 lines); the assembled
manifest's ten checks run clean in fresh subprocesses over a solutions-overlaid
tree (`MANIFEST: 10/10 clean`); and the whole course composes into one process,
ending

    SMOKE PASS — 23 probes, ten stages composed, one exact graph

With the solutions overlaid, `python3 codecraft/cli.py run autograd-from-scratch`
reports `10/10 passing` and `COURSE COMPLETE`; with the templates in place it
reports `0/10` and, for every stage, `not implemented yet` — the honest failure a
stub should have.

## Where this stops

No float, anywhere — so no `exp`, `log` or `tanh` (a stage that needed one would
need an exact series and a truncation rule, and neither is in this course). No
higher-order derivatives, no `jacobian`/`vmap`-style transforms, no sparse
tensors, no GPU. The engine is single-threaded, deterministic and offline: what is
graded is the derivative and the walk that computes it, and both are exact.
