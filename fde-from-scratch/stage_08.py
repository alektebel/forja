"""FDE From Scratch — stage 8: The model that fits the customer's GPU.

Half of this customer's data may never leave their building, so the model has to
come to the data — and the machine it lands on is theirs, not a cloud that scales
on demand. That turns a question nobody usually asks into the question this stage
is about: which of the customer's model variants fits which of the customer's
cards, and what happens to a request when nothing does.

A card is not a disk. A variant and its quantisation have a footprint, the card has
memory the customer paid for and will not let the AI fill to the brim, and a
machine without a card runs nothing at all. `HEADROOM` is the share of a card a
model may take, and it is settled as an exact integer inequality — `memory_mb * 100
<= gpu_memory_mb * HEADROOM` — because a ratio carrying a decimal point is one
rounding away from admitting a model the card cannot hold. Every one of those is a
*reason* rather than an exception: deciding what to run is the job this stage
describes, so the answer is data.

Then the queue. Once a variant is on a card, what is left is throughput: the model
serves a fixed number of tokens per tick, callers submit work with a tick of their
own, and the deployment has a small queue and a caller's patience (`BUDGET_TICKS`).
A submission that would wait longer than that is refused — returned, per
submission, naming why — and the refused submission never occupies a slot a
servable one needed, which is why the checks run in the order they do. A zone whose
egress policy reaches `"public"` may not serve at all: nothing is dequeued.

    FIT_REASONS                the six reasons a model does not fit a node, in order
    HEADROOM                   the percent of a card's memory a model may take (90)
    QUEUE_MAX                  the submissions the queue holds at once (4)
    BUDGET_TICKS               the ticks a submission may wait for, inclusive (3)
    SUBMISSION_KEYS            the five fields of a submission, in order
    SERVE_REASONS              the four reasons a scheduler refuses a submission
    EdgeError                  the edge's refusal: a shape it cannot accept
    fits(model, node)          -> (True, None) | (False, reason)
    place(models, nodes, zone) -> (model, node, None) | (None, None, reason)
    Scheduler(model, node, network, zone)      one variant on one machine, in one zone
    Scheduler.submit(name, tokens, tick)       -> SUBMISSION_KEYS, queued or refused
    Scheduler.drain(tick)                      -> the SUBMISSION_KEYS one tick served
    Scheduler.queue()                          -> the queued submissions, in order
    Scheduler.served()                         -> the names served, in service order
    Scheduler.refused()                        -> (name, reason) pairs, in refusal order

DESIGN DECISION — why is the headroom rule an integer inequality with the boundary
inclusive?
Because "90% of the card" has to mean one thing for every card. `7200` megabytes on
an `8000` megabyte card is exactly 90% and must fit; `7201` must not, and no
floating-point division may decide that. Multiplying both sides by a hundred keeps
the comparison exact while the numbers stay whole, and it is the *card's* memory
that is compared, never the machine's RAM — a node with 128 GB of RAM and an 8 GB
card can still only hold an 8 GB model, and the mistake of reaching for
`memory_mb` (the node's) instead of `gpu_memory_mb` is precisely the mistake that
makes a deployment that runs beautifully on the FDE's laptop fail on the customer's.

DESIGN DECISION — why does `fits` answer `unknown-model` for a name instead of
looking one up?
Because `fits` holds no catalogue, and a function that invented one would be
inventing a customer. `fits(model, node)` is answered from two records and nothing
else: hand it a record and it judges the record, hand it a *name* and the honest
answer is that this function cannot see any model by that name — the caller has
handed it a label where the thing itself belongs. The `Scheduler` is where a name
meets the catalogue, because the `Scheduler` is the one thing holding the network;
the split is what keeps "does this fit" answerable on the back of an envelope while
"may this serve" stays a question about the customer's basement.

DESIGN DECISION — why is the zone decided by `place` and the `Scheduler` rather
than inside `fits`?
Because a zone is only wrong *relative to a request*. A node knows its own zone and
nothing about which zone was asked for, so a two-argument `fits` that answered
`zone` would be pretending to a fact it does not have. `place(models, nodes, zone)`
has the request, so the zone filter and the `zone` reason live there: a node in
another zone is not a candidate at all, and when no node in the requested zone
exists at all, that is the reason the answer carries.

DESIGN DECISION — why is a submission checked against the queue's capacity before
its own wait, and both before it is counted into the queue?
Because a full queue cannot accept the submission at all — that is a fact about the
queue — while the wait is a fact about this submission, and a refusal that had
already taken a slot would be a submission nobody ever serves, blocking a servable
one behind it. So the ladder is ordered (egress, then an unknown model, then
capacity, then budget), the budget is judged from the work already ahead of the
submission plus its own tokens, and the refusal is returned as data: `state`
`"refused"`, no queue entry, and a line in `refused()`.

DESIGN DECISION — why does `drain` spend exactly one tick of the model's throughput?
Because `tokens_per_tick` is what the model does in a tick, and a tick is the only
time there is. A `drain` that emptied the queue would make the reported `waiting`
meaningless and the budget unreachable: every submission would be served the moment
it arrived and a wait could never exceed a tick. Serving up to `tokens_per_tick`
tokens per call, in submission order, with a submission completed only when its own
last token is spent, is what makes "the ticks it has waited" a measurement rather
than a decoration — and it is why a submission larger than one tick's worth is
servable at all.

TODO: implement `EdgeError`, `fits`, `place` and `Scheduler` in this file: the
integer headroom ladder, the placement ordered by quality and its name tie-break,
and the scheduler with its submit, its one-tick drain, its queue, its served names
and its refusals.
"""

import estate
import network

FIT_REASONS = ("unknown-model", "unknown-node", "no-gpu", "gpu-memory",
               "unknown-quant", "zone")
HEADROOM = 90
QUEUE_MAX = 4
BUDGET_TICKS = 3
SUBMISSION_KEYS = ("name", "tokens", "tick", "state", "waiting")
SERVE_REASONS = ("no-capacity", "budget", "egress", "unknown-model")


class EdgeError(estate.EstateError):
    """The edge's refusal: a shape it cannot accept, and nothing about the weather."""


def fits(model, node):
    """Whether a model variant fits a machine, as `(True, None)` or `(False, reason)`.

    `model` and `node` are `MODEL_KEYS` and `NODE_KEYS` records; a name handed where
    a record belongs is `unknown-model` or `unknown-node`, because this function
    holds no catalogue to look one up in. The ladder is the node's card, the
    quantisation, then the integer headroom rule, and the reason names the rung that
    said no.
    """
    raise NotImplementedError("stage 8: implement fits()")


def place(models, nodes, zone):
    """The best model a zone can run: `(model, node, None)` or `(None, None, reason)`.

    The model is the highest `quality`, ties broken by the higher `tokens_per_tick`
    and then by name, and its node is the first machine in `zone` it fits; when
    nothing fits, the reason is the one that kept the best model off the zone.
    """
    raise NotImplementedError("stage 8: implement place()")


class Scheduler:
    """One model on one machine in one zone: what it serves, and what it refuses.

    `model` and `node` are records or names the customer's own network holds, and
    `zone` is the zone this deployment serves. Construction is the wiring — a model
    that does not fit its node, a node of another zone or a zone that is not a zone
    are refused here, naming the offender, because no submission could make them
    right — while a *model* the network's catalogue does not hold is remembered and
    returned as the `unknown-model` serve reason on every submission.
    """

    def __init__(self, model, node, network, zone):
        """Resolve the variant and the machine, and refuse a wiring that cannot serve.

        `network` is the customer's own `network.Network`. A submission asks about
        this deployment, so everything that cannot be a deployment — the network,
        the zone, the node, the fit — is refused here, by name; only a model the
        catalogue does not hold is deferred, because it has a serve reason of its own.
        """
        raise NotImplementedError("stage 8: implement Scheduler.__init__()")

    def submit(self, name, tokens, tick):
        """Offer one submission and answer its `SUBMISSION_KEYS`.

        Accepted work is `"queued"`; a submission that would wait more than
        `BUDGET_TICKS`, a full queue, a zone that reaches `"public"` and a model the
        catalogue does not hold are answered `"refused"` with the reason, and none of
        them takes a queue slot.
        """
        raise NotImplementedError("stage 8: implement Scheduler.submit()")

    def drain(self, tick):
        """Serve up to `tokens_per_tick` tokens and answer the submissions that finished."""
        raise NotImplementedError("stage 8: implement Scheduler.drain()")

    def queue(self):
        """The queued submissions, in submission order, each with the ticks it has waited."""
        raise NotImplementedError("stage 8: implement Scheduler.queue()")

    def served(self):
        """The names served so far, in service order."""
        raise NotImplementedError("stage 8: implement Scheduler.served()")

    def refused(self):
        """The `(name, reason)` pairs refused so far, in refusal order."""
        raise NotImplementedError("stage 8: implement Scheduler.refused()")
