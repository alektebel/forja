"""Interconnects From Scratch — stage 8: Send, recv and groups

Every collective before this one had a shape the plan could be derived from: a
root and a tree, a ring and a chunk index. This stage is the smallest primitive
underneath all of them — a peer sends a slice to a peer and receives one back —
and the smallest unit of *launch*: a group of exchanges that the caller asks the
fabric to perform **at once**.

That single constraint is what makes the stage interesting. "At once" is not
"in turn with the answers thrown away": every exchange of a group must sit in
the *same step*, and the fabric's legality rule decides whether that is possible
— one transfer per directed link per step, with links full duplex. So a group is
both a plan (does the executor produce the right buffers?) and a price (what does
that one step cost?), and the two disagree in the ways this stage names.

A group is one launch, and a launch has a price. The plan is the group; the price
is the slowest transfer of its single step; a sequence of messages is a different
plan with a larger price. Nothing here is timed: the price is a tick count read
off the plan, and every number is an `int`.

DESIGN DECISION — is a group one launch, or a sequence of messages?
    A sequence is the tempting alternative: walk the exchanges and give each one
    its own step, so the plan reads like the calls the caller wrote. Its cost is
    a step per exchange, and a plan's price is the sum of its steps, so a group of
    `N` one-hop exchanges is priced `N` times over — on `ring(4)`, four 400-element
    pairwise exchanges cost 4 * 21 = 84 ticks, where the one-launch group costs
    21. On `switch(8, width=4)` a group holding one cheap in-group exchange and
    one three-hop cross-group exchange costs 104 ticks as one launch and 114 as a
    sequence. The tick count is the giveaway: a group's price is *one* step's
    maximum, not a sum.

DESIGN DECISION — when may two exchanges share one step, given full-duplex links?
    The fabric's rule is per **directed** link: a step may carry `r0 -> r1` and
    `r1 -> r0` at once (that is exactly what a pairwise exchange is — the same
    link, both directions, one step), but two transfers that both cross `r0 -> r1`
    may not, because the link carries one direction at a time. Serialising every
    exchange that touches a shared link is the over-strict alternative: it is
    legal words, but it turns a pairwise exchange into two steps and pays a
    latency twice. Accepting any collision is the under-strict alternative: the
    plan is built, and `fabric.run(check=True)` refuses it, so the group fails at
    the buffer, not at the price. The directed link is the unit both callers and
    the executor agree on.

DESIGN DECISION — is a send and its matching recv between one pair charged once,
or once per endpoint?
    An exchange reads as two operations, and it is tempting to charge the sender
    for its send and the receiver for its recv — two messages for one transfer.
    But the fabric charges the *transfer*: `r0 -> r1` is one slice crossing one
    link in one direction, and its cost model has no term that depends on whose
    buffer the slice came from or went to. Charging both ends would double every
    price, and specifically would price a pairwise exchange (one transfer each
    way on one link) as if four transfers crossed it. A group's price is the
    maximum over its transfers, counted once each.

DESIGN DECISION — is the group's price the maximum of its transfers, or their sum?
    A group is one step, and a step's cost is the slowest transfer in it, because
    those transfers overlap in time and the step ends with the last of them.
    Summing them prices the group as though the exchanges ran one after another —
    the sequence-of-messages price under a one-launch plan. On the switch fixture
    that is 114 ticks against the correct 104, and on `ring(4)` 84 against 21, so
    the sum does not merely look expensive: it is the price of a different plan.
    The maximum is what one launch costs.

DESIGN DECISION — what does an empty group cost, and why is it not one launch?
    A group of no exchanges has no transfer to launch; the empty plan has no
    steps, so its price is 0 and `fabric.run` returns the buffers untouched. The
    alternative — charge one launch's latency for a group that does nothing — is
    the reason a completion is counted per *group* and not per *message*: a group
    pays for the transfers it actually performs, and for nothing else. Billing an
    empty group would make "launch a group" cost something even when there is
    nothing in it, which is exactly the bookkeeping error the tick count exposes.

TODO: implement `sendrecv` and `group_ticks`.
"""


def sendrecv(topology, exchanges):
    """A group as one plan: every exchange lands in step 0.

    `exchanges` is a tuple of `(src, dst, offset, length)` — the slice `offset
    .. offset + length` of `src`'s buffer goes to `dst` in the same step, and
    nothing arrives before the step starts. Refused with a `fabric.FabricError`
    are a self-exchange, an unknown rank, a length that is not positive, a
    negative offset, an exchange with no route, and — because a directed link
    carries one transfer per step — a group whose exchanges collide on one
    directed link. Two transfers may share a link in *opposite* directions: the
    links are full duplex, and that is what a pairwise exchange is.
    """
    raise NotImplementedError("stage 8: implement sendrecv()")


def group_ticks(topology, exchanges):
    """The price of that one launch: the slowest transfer of the group's step.

    A group is one step, so its price is that step's maximum — not the sum of
    the transfers, which is the price of the same exchanges serialised into a
    message chain, and not the cheapest transfer. It equals
    `stage_01.step_ticks(sendrecv(topology, exchanges), 0)`, because `sendrecv`
    places every exchange in step 0; a group with no exchanges costs 0.
    """
    raise NotImplementedError("stage 8: implement group_ticks()")
