# Interconnects From Scratch

Build the collectives a training step is made of — broadcast, reduce, all-reduce,
all-gather, reduce-scatter, all-to-all, a group exchange, an algorithm chooser
and one whole training step — on a fabric you are given and a cost model you
write yourself. Ten graded stages, pure standard-library Python, offline,
deterministic, and every number an int.

The thesis is one sentence: **a collective has a plan and a price, and the two
are independent.** Correctness is decided by running the plan — the provided
executor applies every transfer to the buffers and the answer either appears on
every rank or it does not. Cost is decided by counting — `latency + ceil(bytes /
bandwidth)` per hop, the slowest transfer for a step, the sum of the steps for a
plan. The failures worth preventing pass one check and fail the other: a
butterfly that shrugs off a hop it cannot afford, a ring that prices a 4096-element
message like a 400-element one, a "best" algorithm chosen by a table of sizes
instead of by arithmetic.

## The stages

Ten graded stages. Each one targets a mistake that is easy to make and hard to
notice.

| # | File | The mechanism | The thing people get wrong |
|---|---|---|---|
| 1 | `stage_01.py` | The link and the fabric: hops, bytes, a step's max, a plan's sum, `validate` | A message priced per message instead of per byte plus per hop; a step charged the sum of its transfers instead of its slowest |
| 2 | `stage_02.py` | Broadcast: the ring one turn per step, the tree one level per step | The root sending to every rank at once (its own link carries N−1 copies in one step); a tree that walks levels the topology does not have |
| 3 | `stage_03.py` | Reduce, and where the accumulator lives: it travels the ring, the root lands last | A star gather to the root (more ticks than the chain); a rank forwarding in the step it receives, when a step is simultaneous |
| 4 | `stage_04.py` | The ring all-reduce: reduce-scatter then all-gather | A step count that changes with the chunk count — chunking changes the transfer size, not `2(N−1)` steps |
| 5 | `stage_05.py` | The tree all-reduce, recursive doubling, and `all_reduce_best` | A butterfly whose XOR partners are not one hop away; a `best` that hard-codes a size instead of counting ticks |
| 6 | `stage_06.py` | All-gather and reduce-scatter as first-class collectives | Treating them as each other's inverse, or as one collective with two names; a half that ships the whole buffer |
| 7 | `stage_07.py` | All-to-all: one step, one transfer per pair, offsets cumulative by destination | Per-pair offsets instead of cumulative ones; a diagonal treated as a transfer; a rank that neither sends nor receives counted as an error |
| 8 | `stage_08.py` | Send, recv and groups: one launch, priced by its slowest transfer | Two transfers over one *directed* link in a step allowed (and opposite directions forbidden, which a full-duplex link allows); a group charged the sum of its exchanges |
| 9 | `stage_09.py` | Choosing an algorithm, and the lower bound: every candidate priced, SHARP as a plan | A size table instead of counting ticks; a bound with the wrong denominator; SHARP assumed to be an integer rather than a plan the executor can run |
| 10 | `stage_10.py` | One step, end to end: four axes on one topology, comms behind compute | Comms added to compute instead of overlapped; an axis of one still emitting its collective; one expert exchange where the dispatch and the combine are two |

Stages 2–10 compose the earlier ones (stage 4 is stage 6's two halves, stage 5
compares itself against stage 4, stage 9 prices every candidate with stage 1,
stage 10 lays the four axes over stage 9's chooser and stage 6/7/8's
collectives), so they are meant to be done in order — each check imports the
solutions of the stages it builds on.

## The provided fabric

`fabric.py` is given and is not part of the exercise: it is the world the
collectives run in, and the thing the cost model prices.

- `ELEMENT_BYTES = 4`, `OPS = ("sum", "min", "max")`, `TRANSFER_OPS = ("send",
  "reduce")`, `FabricError`, `ceil_div`.
- `Link` (bandwidth per tick, latency, the two ranks it joins), `Topology`
  (`name`, `ranks`, links, `distance`, `path`), `Transfer` (source,
  destination, length, offset, op, step), `Plan` (transfers in canonical order,
  `at(step)`).
- Fixtures: `ring(n)`, `full(n)`, `tree(n)`, `switch(n, width=4)`, and
  `rank_ids(n)`.
- `send(src, dst, length, offset, *, op="send")`, `legality_problems(topology,
  plan)`, `buffers(n, length, *, fill=None)`, `reference(buffers_map, *,
  op="sum")`, `run(topology, plan, buffers_map, *, op="sum", check=True)`.

Five rules make the rest of the course checkable:

- **A hop costs `latency + ceil(bytes / bandwidth)`, and hops add.** Store and
  forward: a transfer over three links is not the price of one link.
- **A step is its slowest transfer; a plan is the sum of its steps.** A step is
  simultaneous: every transfer reads the buffers as they stood at the start of
  that step and writes its own destination.
- **Links are full duplex.** Two transfers over one link in one step are legal
  in opposite directions and illegal in the same direction; `legality_problems`
  keys on the *directed* link.
- **Every route is legal or it is refused.** A plan that is not link-legal does
  not run with `check=False` and is not rewritten into several steps to look
  legal; it is a `FabricError` naming the pair and the hops.
- **No number in this course is a float.** Every tick is an int, every plan is
  a function of its inputs, and no fixture reads a clock.

## How to use this directory

```bash
python3 codecraft/cli.py run interconnects-from-scratch   # what to build next, and why
python3 codecraft/cli.py hint interconnects-from-scratch  # when a nudge is not enough
```

Or without codecraft:

```bash
python3 -c "import course; [print(i, s.title) for i, s in enumerate(course.STAGES, 1)]"
```

Implement the templates at the top level; finished versions are in `solutions/`.
Copy a solution over its template to compare (`cp solutions/stage_05.py
stage_05.py`), and put the template back to try again. `solutions/README.md`
has the ladder of what imports what.

## Prerequisites

`I9` sits after `G3` and `J1`. Basic Python (classes, dataclasses, closures,
comprehensions) is enough; what the course leans on from elsewhere is the habit
of a bounded, deterministic algorithm and a cost you can predict before you run
it. No dependencies outside the standard library, no network, no GPU.

## Design decisions

- **The cost model is the student's stage 1, and the fabric provides only the
  world.** If the course shipped the price of a hop, the stage-1 mistake — per
  message instead of per byte plus per hop — would not be a mistake anyone could
  make. `fabric.py` gives links, routes, the executor and the fixtures; every
  tick in this course is computed by grader-visible arithmetic.
- **A collective is checked by running it, not by reading its plan.** The two
  independent checkers — the student's `validate` and the provided
  `legality_problems` — must agree, and `run(check=True)` uses the provided one,
  so a buggy `validate` cannot make the executor accept a bad plan.
- **Time is step-indexed and integer.** A plan is transfers with a `step`;
  there is no clock object in this course (unlike `queue-and-workers`'s
  `fleet.Clock`) because a collective has no duration until the fabric prices
  it, and every tick is an int.
- **Doubling needs one-hop XOR partners, and that is the honest mechanism.** On
  a ring or across a two-level switch's spine the partner is several hops away
  and the butterfly's step is link-illegal; the course refuses rather than
  staging it or running it unchecked. This is also why real frameworks run the
  butterfly inside an NVLink domain and a ring across nodes.
- **SHARP is modelled as a rank-level plan.** A gather to each group's spine
  port, one reduction across the spine, a broadcast back — something the
  executor can actually run and the cost model can price. An "algorithm" that
  returns an integer would be untestable, and the interesting part is exactly
  the rank-level part.
- **A ring closes.** On `ring(4)` rank `r0` and rank `r3` are neighbours, so
  "distance 3" is a property of the *pair on this ring*, not of "two ranks on a
  ring" — the fixtures pin both the one-hop and the three-hop case.
- **One step is priced by its slowest axis, not its sum.** At stage 10 the four
  parallelism axes are disjoint rank sets, so their collectives overlap; adding
  them would be the same class of mistake as adding comms to compute.

## Verification

The solutions pass all ten checks, and every check is mutation-tested: 438
plausible wrong implementations — a transfer priced as one hop, a step charged
the sum of its transfers, a star instead of the travelling accumulator, a rank
forwarding in the step it receives, a step count that follows the chunk count, a
butterfly with a two-hop partner, an all-gather that ships the whole buffer,
per-pair instead of cumulative offsets, a group charged its sum, a size table
instead of ticking arithmetic, comms added to compute — are each planted into a
solution and the stage's check must fail. Per stage: 46, 40, 37, 42, 47, 43, 43,
38, 47, 55. `git log` and the checks are the record; the mutations were applied
privately, by anchor, to a rebuilt tree, and the assertions that catch them name
the mistake in their message.

The assembled course is then run as a student would (`python3 codecraft/cli.py
run interconnects-from-scratch` reports `0/10 passing` on the templates), and a
single end-to-end smoke runs all ten stages in one process against the
solutions:

```
1: one 400-element hop 21 ticks, three hops 63, a two-transfer step 21
2: ring broadcast 63 ticks in three steps, tree broadcast 42 in two
3: reduce ring 63 ticks, three steps, the accumulator one hop per step
4: ring all-reduce in six steps, 13 ticks each at chunks=2 and 9 at chunks=4, and chunks=1 refused
5: crossover ring(8) tree 48 -> ring 364; two-level tree 1520 vs ring 1610
6: reduce-scatter + all-gather compose to 36 + 36 ticks of the ring all-reduce
7: the ragged all-to-all is the transpose, kept slices untouched, one step
8: two pairs in one launch, full duplex on one link, a directed collision refused
9: choose ring 364 / tree 48 / sharp 844, the bound the ring meets exactly
10: one step = max over the axes; comms overlap compute at 94 against 1000

SMOKE PASS — 10 stages, one deterministic step: a collective has a plan and a price, and the two are independent
```

That smoke earned its keep three times, and each time it was the smoke's
expectation that was wrong, not the course: `r0` and `r3` are neighbours on
`ring(4)` (the ring closes), a chunked all-reduce gets *cheaper* per step
because each step carries less, and `exchange_with` answers with the blocks that
fill each buffer rather than the buffers themselves. Each is now an assertion in
the smoke with the arithmetic attached — which is the point of the course: the
price is not a table of remembered numbers.

## Where this stops

Deliberately left out, so you know the boundary:

- **No hardware and no driver.** A `Link` is a bandwidth, a latency and two
  ranks. There is no routing protocol, no congestion control, no adaptive
  routing, and no NIC: the fabric's routes are fixed by its fixture, which is
  what makes a plan's price a number you can predict.
- **The in-network reduction is modelled, not built.** SHARP appears as the
  rank-level plan a switch-based reduction implies. What the switch does inside
  is the one thing in the course that is priced but not executed.
- **Compute is a parameter.** Stage 10 overlaps a compute cost you hand it with
  the communication it priced; there is no model of what the compute is, and no
  arithmetic on FLOPs. That is the subject of `distributed-training-from-scratch`
  (`H1`), which prices the same collectives against a training step's compute.
- **The collectives stop at the training step's set.** Ring attention, tensor
  parallel's sequence-parallel variants, hierarchical all-reduce and the
  pipeline schedules that make bubbles small are named and priced in
  `DISTRIBUTED.md`; here the mechanism stops at the plan and its price.
