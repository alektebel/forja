"""Interconnects From Scratch — stage 9: Choosing an algorithm, and the lower bound

Stage 5 built the tree and the butterfly, stage 4 the ring, and every one of
them is the right answer on some fabric at some size. This stage writes the
choice down: `choose` builds each candidate, prices it with
`stage_01.plan_ticks`, and returns the cheapest. It also writes down the one
thing a cost comparison cannot: what an all-reduce must move at all, whatever
shape it takes.

`sharp_ticks` prices SHARP — the in-network reduction — by building it as a
rank-level plan on the two-level `switch` fabric and pricing it in the same
ticks. `lower_bound` states the elements one rank must move in one direction,
and `within_bound` checks a plan against that floor.

DESIGN DECISION — why is the choice a recomputation of ticks, and not a size
table? A rule like "messages under 4096 elements take the tree, larger ones the
ring" is a table of one fabric's bandwidth and one fabric's latency: it is right
on the fabric it was measured on and wrong everywhere else. The rejected
alternative hard-codes a size; on `switch(8, width=4)` the spine's twenty ticks
per hop move the crossover to a different size again, and on a full mesh the
tree wins at every size the ring is legal at. Building every candidate and
comparing `stage_01.plan_ticks` makes the pick a function of the two plans'
prices, so a fabric nobody has seen yet is answered correctly, and a tie is a
tie — broken by the candidate order, never by the fabric's name.

DESIGN DECISION — why is the bound per direction, and not per plan? An
all-reduce moves information twice: once *toward* the accumulator (the
reduce-scatter's direction) and once *away* from it (the all-gather's
direction). Each direction carries every rank's contribution past the ranks
that do not own it, so each direction moves `S(N - 1)/N` elements per rank —
and the rejected alternative, the *total* `2S(N - 1)/N`, is a bound on the
whole collective, not on one direction of it. Comparing a plan against the
larger number would let a plan pass while moving half of what a direction
requires; comparing it against `S/N` (the wrong denominator, as if one rank's
data had to reach everyone without travelling) would fail every honest plan.
The bound is a floor, not a ceiling: a plan may move more, never less.

DESIGN DECISION — what does SHARP buy, and where is it legal? SHARP moves the
reduction *into the switch*: the group's ranks hand their buffers to the
group's spine port, the ports combine on the spine, and the ports copy the
answer back — two cheap intra-group phases and one crossing, instead of the
ring's fourteen steps that cross the spine in every one of them. The rejected
alternative — running the same shape on a fabric with no group/spine split —
buys nothing and lies: on a uniform ring there is no spine to reduce in, so
`sharp_ticks` raises `FabricError` naming the topology, and `choose` simply
drops the candidate. On the fabric that *has* a spine the candidate is built
and must be picked when it wins: refusing it there would ignore the one
algorithm the hardware offers.

DESIGN DECISION — why is SHARP built as a rank-level plan, and not as a cost
formula? A formula like "two group hops plus one spine hop" cannot be run: no
executor checks that the ports actually hold the reduced buffer, or that the
copy back reached the group. The rejected alternative is a price with no plan
inside it, and it is exactly the kind of number that is right on paper and
wrong on a fabric. The plan this stage builds is ordinary transfers of the same
`fabric.Plan` the ring and the tree build, so `fabric.legality_problems` checks
its steps and `fabric.run` proves its buffers; `sharp_ticks` is then nothing but
`stage_01.plan_ticks` of that plan, which is what makes it comparable with every
other candidate.

DESIGN DECISION — why is a candidate whose preconditions fail dropped, and not
raised? `choose` is asked on fabrics where a shape cannot exist: a ring fabric
whose rank count is not a power of two, a switch whose butterfly partners are
three hops apart, a message size the ring's chunking does not divide. The
rejected alternative — letting the candidate's own `FabricError` out of
`choose` — would answer "no plan at all" on a fabric where three of the four
shapes fit perfectly, and patching the fourth up (staging a multi-hop butterfly
over several steps, say) would return a plan whose price is no longer the
algorithm's. A candidate that cannot be built is not a candidate; only a fabric
where *nothing* fits is an error, and that refusal names the fabric and the
size.

TODO: implement `choose`, `sharp_ticks`, `lower_bound` and `within_bound`.
"""


def choose(topology, length, op="reduce"):
    """The cheapest candidate for this fabric and size, and its plan.

    Every candidate is priced with `stage_01.plan_ticks`; ties break by the
    candidate order, and a candidate whose preconditions fail is dropped.
    """
    raise NotImplementedError("stage 9: implement choose()")


def sharp_ticks(topology, length):
    """What the in-network reduction costs, in the cost model's own ticks."""
    raise NotImplementedError("stage 9: implement sharp_ticks()")


def lower_bound(length, n):
    """The elements one rank must move, in one direction, for an all-reduce."""
    raise NotImplementedError("stage 9: implement lower_bound()")


def within_bound(plan, length, n):
    """Whether the plan's largest per-rank send reaches the bound."""
    raise NotImplementedError("stage 9: implement within_bound()")
