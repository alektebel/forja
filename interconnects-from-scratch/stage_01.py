"""Interconnects From Scratch — stage 1: The link and the fabric

Below this stage is the provided `fabric.py`: ranks joined by links, each link
with a bandwidth in bytes per tick and a latency in ticks; transfers placed in
steps; a router that answers the shortest route between any two ranks; and an
executor that applies a plan to buffers. None of that computes a price. This
stage is the price: given a plan and a topology, what does it cost in ticks,
and is it a plan the fabric could run at all?

This is the rest of the course in miniature. A collective is a plan and a
price, and the two are independent: the executor tells you whether the buffers
come out right, and these seven functions tell you what the plan costs.
Nothing here is timed, so "cost" is a count; and every count is an `int`,
because a fraction of a tick is not a thing this course can represent.

DESIGN DECISION — why is a step's cost the maximum of its transfers, and not
their sum?
    A step is what the fabric lets run *at once*: its transfers have been placed
    so that no link carries two of them in the same direction, so they overlap
    in time and the step ends when the last of them ends. Summing them instead
    charges every transfer to the clock one after another, which is the cost of
    a plan that had serialised that step — a different and worse plan. The sum
    is the mistake that makes a pipelined ring look as expensive as a sequential
    one; the maximum is what "one step" is.

DESIGN DECISION — why does a transfer cost per hop as well as per byte, instead
of a flat cost per message?
    A message is not the unit a fabric charges for. Every byte of the message
    crosses every link on its route, so the price has two terms: the bytes over
    the bandwidth of each link (`ceil(bytes / bandwidth)`), and the latency each
    link charges once per hop. A flat per-message price would make a three-hop
    transfer cost the same as a one-hop one, and a 400-element transfer the same
    as a 4-element one — erasing exactly the size and distance dependence the
    rest of the course is built to compare. Charging per byte makes size matter;
    charging per hop makes distance matter.

DESIGN DECISION — why does `bytes_by_link` charge a multi-hop transfer to every
link on its route, and not only to its first and last link?
    The bytes cross every link in between. A transfer from `r1` to `r5` on the
    switch fabric goes `r1 — r0 — r4 — r5`: the two cheap in-group hops and the
    expensive spine hop all carry the message, and the spine carries it at 25
    bytes per tick. Crediting only the endpoints would make the spine look idle
    while it is the bottleneck, and it would make the cost this course reads off
    `bytes_by_link` disagree with the ticks it counts hop by hop. Every link on
    the route carries the bytes; every link on the route is charged.

DESIGN DECISION — why is latency paid once per hop per transfer, rather than
once per plan?
    Latency is the tick a link spends setting a transfer up before its bytes
    flow; a message crossing three links is set up three times, once per link,
    once per transfer. A single latency for the whole plan describes a fabric
    whose links need configuring exactly once, which is not this one; a single
    latency per transfer describes a fabric where only the first hop has a setup
    cost, which is not this one either. Per hop, per transfer is what
    `fabric.Link.latency` means.

DESIGN DECISION — why is the byte time an integer ceiling rather than `//` or
`round`?
    Ticks are integers, so a partial tick is unrepresentable and the model must
    choose a convention. `round` needs an inexact division (a float in disguise)
    and can *under*-charge: 120 bytes at 100 bytes per tick take one and a fifth
    ticks, and rounding down would let the transfer finish inside one tick. `//`
    floors and errs the same way. A link still busy at the end of a tick has not
    finished; the ceiling is the first tick at which it has. `fabric.ceil_div` is
    that ceiling, and it is the function the provided module uses too.

DESIGN DECISION — why is `validate` the student's own checker rather than a
call to `fabric.legality_problems`?
    `legality_problems` is the executor's opinion: it is what `run(check=True)`
    consults, and it deliberately checks only the rules that need no buffer
    length, because it is never handed one. `validate` is the plan builder's
    opinion: it is asked before there is a buffer, and it answers the same rules
    plus the ones the plan itself carries. Delegating would make the exercise
    vacuous — the check compares the two for *agreement*, which it cannot do if
    one is an alias of the other — and it would hide the rule the student is
    meant to own.

The cost model has no free parameters: every number it charges comes from a
`fabric.Link` (its `bandwidth`, in bytes per tick, and its `latency`, in ticks)
and from the width of an element, `fabric.ELEMENT_BYTES`.

TODO: implement `hop_count`, `transfer_ticks`, `step_ticks`, `plan_ticks`, `bytes_by_link`, `bytes_per_rank` and `validate`.
"""

#: How many bytes one element of a buffer is worth. It is `fabric.ELEMENT_BYTES`;
#: the cost model charges bytes, and this is the only place a length in elements
#: becomes a size in bytes.
BYTES_PER_ELEMENT = 4


def hop_count(topology, a, b):
    """The number of hops on the shortest route from `a` to `b`.

    `0` when the two ranks are the same, and `None` when no route joins them (a
    topology need not be connected). An unknown rank is a `fabric.FabricError`,
    raised by the topology itself.
    """
    raise NotImplementedError("stage 1: implement hop_count()")


def transfer_ticks(topology, transfer):
    """What one transfer costs, in ticks: every hop of its route, once.

    A transfer carries `BYTES_PER_ELEMENT * length` bytes, and each hop of its
    route charges that hop's `latency` plus `ceil(bytes / bandwidth)`. The hops
    add. A transfer that cannot be routed is a `fabric.FabricError`.
    """
    raise NotImplementedError("stage 1: implement transfer_ticks()")


def step_ticks(topology, plan, step):
    """What one step of `plan` costs: the slowest transfer in it.

    The transfers in a step overlap, so the step ends when the last of them
    does — the maximum, not the sum. A step with no transfers costs nothing.
    """
    raise NotImplementedError("stage 1: implement step_ticks()")


def plan_ticks(topology, plan):
    """What the whole plan costs: the sum of its steps' costs.

    The steps run one after another, so their costs add. `plan.steps()` names
    only the steps that carry a transfer, so an empty step is not a step.
    """
    raise NotImplementedError("stage 1: implement plan_ticks()")


def bytes_by_link(topology, plan):
    """Bytes carried by each undirected link, over the whole plan.

    A transfer's bytes are charged to *every* link on its route, not only to its
    ends. Links that carry nothing are absent from the mapping, and the keys are
    `fabric.Link` objects.
    """
    raise NotImplementedError("stage 1: implement bytes_by_link()")


def bytes_per_rank(topology, plan):
    """Bytes each rank of the topology handled: what it sent plus what it got.

    Every rank of the topology appears, with `0` for one the plan never touches.
    A transfer is charged to both ends, `send` or `reduce` alike: the sender
    handled those bytes and so did the receiver.
    """
    raise NotImplementedError("stage 1: implement bytes_per_rank()")


def validate(topology, plan):
    """Refuse a plan the fabric could not run, naming the offender.

    Raises `fabric.FabricError` for a rank the topology does not have, a
    transfer that cannot be routed, a transfer to itself, a non-positive length,
    a negative offset, a slice past the buffer when the plan carries a `length`,
    and two transfers that share a directed link inside one step. Returns `None`
    for a legal plan.
    """
    raise NotImplementedError("stage 1: implement validate()")
