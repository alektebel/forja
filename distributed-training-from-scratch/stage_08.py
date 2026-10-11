"""Distributed Training From Scratch — stage 8: Expert parallel

An expert layer replaces one feed-forward network with a bank of them, and a
router sends every token to `top_k` of them. The tokens do not live where their
experts do, so the layer pays for **two** all-to-alls: the *dispatch*, which
carries each token to the expert that will process it, and the *combine*, which
carries the expert's output back to the rank that owns the token. This stage
writes the routing as data (`routing`), the two statistics the routing needs
(`dropped` and `balance_loss`), and the layer's `StepPlan`
(`expert_parallel`) — the two ragged exchanges, their lengths taken from the
routing, and the ledger of one expert per rank.

The routing is a **square table of placements**: `routing[source][expert]` is
the number of tokens the block on source rank `source` sends to expert
`expert`, so the table is exactly the `splits` table `plans.alltoall_from_splits`
takes, the row sums are what each rank dispatches and the column sums are the
experts' loads. Rows are the group's ranks in rank order and there is one
expert per rank, so the group is the world and its size is the expert count.
Every token of the block takes the `top_k` experts `(q + k) % experts`, which
are distinct because `top_k <= experts`; `hot=e` moves every token's last
choice to expert `e`, which leaves the row sums — the token count — untouched
and makes one column enormous. A capacity cap then limits how many placements
one (source, expert) cell keeps, and the combine carries back only what was
kept, so the combine is exactly `dropped` placements smaller than the dispatch.

Nothing here is measured: every number is an `int` (a fraction of a token is
not a thing this course can represent), the routing is a function of the shape,
the batch and the sequence alone, and two calls return equal values.

DESIGN DECISION — why two exchanges, and not one?
    A token is processed by an expert that lives on another rank, and its
    result must come home: the dispatch carries the token out, the combine
    carries the answer back, and they move the same kind of data in opposite
    directions. One all-to-all can only do the first half, so a plan with one
    exchange has silently dropped the experts' outputs — the token is processed
    and never returned. The two are separate collectives with separate lengths,
    because they do not move the same number of elements: the combine carries
    only the placements the capacity cap kept.

DESIGN DECISION — why is the exchange priced by the busiest rank, and not by
the mean?
    The whole layer waits for the rank that has the most to hand over. With
    `hot` the balanced row sums are unchanged — every rank still dispatches
    `tokens * top_k` placements in total — but one *expert*'s column is
    enormous, and on a rank whose own expert is hot the tokens it keeps cancel
    the ones it must send: one rank dispatches nothing at all while another
    dispatches its whole block. The mean of the sending ranks is then exactly
    the balanced figure, so a plan that charges the mean cannot tell a hot
    routing from a balanced one, and prices a stall the fabric never runs. The
    per-rank figure is therefore the maximum over the ranks of what one rank
    sends or takes in — the diagonal excluded, because the piece a token's own
    expert keeps on the token's own rank never crosses the fabric.

DESIGN DECISION — why does the combine carry fewer elements than the dispatch?
    The capacity cap exists because an expert's buffer is finite: a cell may
    keep `capacity_factor` times the routing's mean cell, and the placements
    beyond it are dropped. The dispatch still carries every placement — the
    token crossed the fabric whether or not the expert accepted it — but the
    combine carries only what the experts kept, so the difference between the
    two exchanges is exactly `dropped`, in placements. A cap that drops tokens
    and does not count them leaves the two exchanges equal, and the plan then
    claims a fabric that returned tokens no expert ever processed.

DESIGN DECISION — why is `balance_loss` an integer, and which integer?
    A softmax load-balancing loss is a float, and this course has no floats: a
    statistic that cannot be written as a whole count cannot be compared. The
    statistic used here is `experts * sum(load ** 2) - sum(load) ** 2` — the sum
    of the squared deviations of the expert loads from their mean, scaled by the
    expert count so that no fraction ever appears. It is exactly zero when every
    expert carries the same load and grows as one expert takes more, which is
    all a router needs to know; a mean-minus-max difference or a sum of absolute
    deviations would be a different (and coarser) number, and `dropped` alone
    would hide an imbalance that has not yet overflowed the cap.

DESIGN DECISION — why is `hot` a keyword of the plan too?
    The plan is what must expose the cost of a routing, and the fixture that
    shows the cost is an unbalanced one: the same token count, a different
    distribution. If `expert_parallel` could only build the balanced routing,
    the two prices would be indistinguishable to a reader and a mean-charging
    plan would pass every check. So the plan takes the same `hot` keyword the
    routing does, and the check plants both tables with one token count.

DESIGN DECISION — why does the exchange step own no compute?
    This stage prices the exchange: what crosses the fabric between the ranks,
    and what the busiest rank must buffer. The experts' arithmetic is the FFN's
    and would be priced by a device this stage's surface never receives — no
    flops-per-tick enters `expert_parallel`, and inventing one would put a
    number into the plan the caller never chose. So `compute` is 0 and the
    step's cost is the exchange's, which is what the routing decides.

TODO: implement `routing`, `dropped`, `balance_loss` and `expert_parallel`.
"""

import fabric
import model
import plans

import stage_01 as stage1


def routing(shape, *, batch, seq, hot=None):
    """The routing table, as data: `routing[source][expert]` placements.

    Rows are the group's ranks in rank order — rank `i` owns the `i`-th block of
    `batch * seq` tokens — and columns are the experts, one per rank, so the
    table is the square `splits` table an all-to-all takes. Token `q` of a block
    takes the `top_k` experts `(q + k) % experts`, and with `hot=e` its last
    choice becomes `e` when the balanced choices do not already name it, so no
    token is listed twice and every row sums to `batch * seq * top_k`. A dense
    shape, a non-positive batch or sequence, and a `hot` that is not an expert
    index are refused, each naming the offender.
    """
    raise NotImplementedError("stage 8: implement routing()")


def dropped(routing, capacity_factor):
    """The placements the capacity cap refuses, summed over every cell.

    One (source, expert) cell may keep `capacity_factor` times the table's mean
    cell — `ceil_div(capacity_factor * placed, experts * experts)`, a whole
    count — and every placement beyond that is dropped and counted. A balanced
    table never exceeds its own mean times one; a hot one does.
    """
    raise NotImplementedError("stage 8: implement dropped()")


def balance_loss(routing):
    """The imbalance of the expert loads, as an exact integer.

    `experts * sum(load ** 2) - sum(load) ** 2` over the table's column sums:
    the sum of the squared deviations from the mean load, scaled by the expert
    count so that no fraction of a token is ever needed. Zero exactly when
    every expert carries the same load.
    """
    raise NotImplementedError("stage 8: implement balance_loss()")


def expert_parallel(shape, world, *, batch, seq, capacity_factor=2, hot=None):
    """The MoE layer's `StepPlan`: the dispatch and the combine all-to-alls.

    The group is the world's ranks, one expert per rank, so a world whose size
    is not `shape.experts` is refused naming both. The dispatch moves every
    placement the routing names and the combine moves back only what the cap
    kept, each built by `plans.alltoall_from_splits` from the table the routing
    produces; each collective's length is the busiest rank's share, in elements,
    so the exchange is priced by the rank that has the most to hand over — the
    diagonal piece, which never crosses the fabric, taken out. The combine's
    table is the capped dispatch table transposed, so it is exactly `dropped`
    placements smaller than the dispatch's. The ledger reports the expert bank
    one rank holds and the buffer the busiest expert rank's intake needs; the
    step owns no compute.
    """
    raise NotImplementedError("stage 8: implement expert_parallel()")
