"""Failover From Scratch — stage 7: Promotion: a majority adopted, or no epoch at all.

TODO: implement each function; the docstring is the contract.

The naive foil promotes east at tick 3 of `ONE_NODE` on ONE timeout —
a region promoting itself because a ping went quiet is how split-brain
ships. A promotion is a DECISION with two halves: a candidate only asks
when the watch PROVED the old primary dead (stage 5's `primary_gone`)
and its own region can still answer (a quorum alive), and it only
becomes the primary when a MAJORITY of its own region adopted the new
epoch — each adopter replying to the proposal with an `adopt`, and the
candidate counting DISTINCT ids. The proposal is region-internal, never
cross-link: a vote from the other side would let two halves of a split
fleet each certify the other. And epochs only ever move up: an `adopt`
at or below the node's own epoch is a recorded refusal, because a node
that adopted epoch 2 and then "re-adopts" epoch 1 has found a liar.

DESIGN DECISION — the candidate self-votes at `propose`, and majority
counts `votes | {self}`?
Because the candidate HAS adopted — it is running on the new epoch the
moment it asks. A lonely node (link cut, all peers dead) then answers
one adopter < majority(3) = 2: `False`, always — that single fact is
`FAKE_DEATH`'s boundary, and the check pins it. Forgetting the self-vote
would raise the bar to a unanimous region and stall real failovers;
counting it twice would let one node's two copies of a reply promote a
region alone.

DESIGN DECISION — `tally` processes replies in arrival order, and an
`adopt` at or below the CURRENT epoch is ignored?
Because the fabric drains a tick's same-region messages FIFO, and the
probe's law is monotonicity per receipt: the first adopt for epoch 2
moves the node to epoch 2, so the SECOND adopt for epoch 2 arrives at a
node already on 2 — ignored, harmlessly, since majority(3) = 2 was
already reached with the first. A replayed or stale adopt for a LOWER
epoch is the recorded refusal: counting it would let a late message
from an old epoch hold the region's promotion hostage.

DESIGN DECISION — why does `propose` skip peers with outstanding death
claims?
Because a proposal to a dead node is a vote that can never come back,
and the region's roster still counts it: majority(3) = 2 of THREE, not
2 of the two living. The skip is not an optimization — sending anyway
would let `tally` wait for an adopt that a corpse cannot write, and a
survivor region that cannot promote is exactly the outage `FLAP` tests
against."""


import fabric

import kv

import topology

import stage_01 as s1

import stage_03 as s3

import stage_05 as s5

FailError = s1.FailError

def _check_state(state, where):
    """The candidate's state: `id` in the fleet, `peers` its region's
    others, `epoch` an int >= 0, `promoted` a bool, `notices` fleet ids,
    `store` a dict of `s3.owned` version tuples, `votes` (if present) a
    dict of epoch -> adopter ids. A malformed field raises `FailError`
    naming it — the promotion surface validates its own inputs."""
    raise NotImplementedError("stage 7: implement _check_state()")

def _live_roster(state, node):
    """The region's roster, the alive members and the majority number."""
    raise NotImplementedError("stage 7: implement _live_roster()")

def propose(state):
    """`(msgs, state2)` — the candidate's broadcast, or nothing. A node
    asks only when: not promoted, still on `INITIAL_EPOCH` (a region
    that already moved its epoch without promoting HAS voted and failed;
    asking again would double-count), its region is not the current
    `PRIMARY`, stage 5's `primary_gone` proves a majority of the old
    primary's region died on the record, and its own region keeps a
    quorum alive. Each gate the fabric's naive foil skips — silence,
    self-region, the watch proof — is a `FAKE_DEATH`-style false
    promotion. The proposal is `fabric.message("propose", peer, id,
    epoch + 1, store)` to every LIVE same-region peer — never
    cross-link, never a corpse — and `state2` records the self-vote:
    the candidate adopted the epoch the moment it asked. A malformed
    state raises `FailError` naming the offender."""
    raise NotImplementedError("stage 7: implement propose()")

def tally(state, replies):
    """`(promoted, state2)` — the votes counted in arrival order. Each
    reply is `("adopt", target, sender, epoch)`: `target` must be this
    node, `sender` must live in this node's region (a cross-region vote
    is a split-brain seed and raises `FailError` naming it), and an
    adopt at or below the node's CURRENT epoch is a recorded refusal —
    never counted, never adopted (monotonicity). A higher adopt bumps
    the epoch and joins the sender to that epoch's voters; the region
    is promoted when `votes | {self}` reaches `majority(roster)` —
    DISTINCT ids, so one node answering twice changes nothing. Once
    promoted, promoted STAYS: an epoch is a ratchet, not a vote of
    confidence."""
    raise NotImplementedError("stage 7: implement tally()")
