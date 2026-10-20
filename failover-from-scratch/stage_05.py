"""Failover From Scratch — stage 5: Health: a signal that is not a heartbeat.

TODO: implement each function; the docstring is the contract.

A heartbeat says "I heard nothing, so you are dead" — and the nothing
is the lie: a cut link silences everyone and promotes nothing. The
fabric's watch notices are different animals: `("dead", n)` arrives when
n KILLED, `("alive", n)` RETRACTS the claim when n revives, and silence
carries no vote at all. This stage folds those notices into three
verdicts — `"up"`, `"suspect"`, `"down"` — with the laws the drill will
test: only a MAJORITY of explicit deaths is down, a lagging region is
suspect while its majority still answers, and a region nobody can hear
is suspect, never down. `FAKE_DEATH` is the whole scenario behind that
last line: the link cut, the peers go silent, and nothing may declare
a death the fleet never witnessed.

DESIGN DECISION — silence is absence, not a dead vote?
Because `("dead", n)` is a signal the fabric PRODUCES only when n
dies, and a cut link produces nothing. A row missing from the
observations cannot vote, so `health((), ())` answers `"suspect"`:
wrong about nothing, and honest about what it does not know. Treating
absence as death makes every link failure a mass outage — the exact
false-positive `FAKE_DEATH` pins against.

DESIGN DECISION — retraction is arrival order, no clock arithmetic?
Because the fabric sends `("alive", n)` exactly when n's catch-up
notice lands, and the notice list already IS the history: dead-then-
alive clears the claim, alive-then-dead re-makes it. Timestamps would
ask a flapping node to arbitrate its own burial order; the list is
what the node received, in the order it received it.

DESIGN DECISION — why is an observed `alive=False` row the same vote as
a `("dead", n)` notice?
Because the row IS the watch: `healthy_count`'s shape came from the
fabric's own observations, and a claim of death — said by a notice or
said by an observation — is evidence. The third of the fleet that
never answered is neither: it is absent, and absence cannot vote. The
count that kills is therefore the count of WITNESSED deaths, silent
rows excluded, and `down` means the region died on the record."""


import fabric

import kv

import topology

import stage_01 as s1

import stage_02 as s2

FailError = s1.FailError

VERDICTS = ("up", "suspect", "down")

def _members(region):
    """The region's nodes, or the stage's own refusal naming the region.
    `topology` answers a plain ValueError; the protocol's refusals are
    `FailError`, so the gate re-raises with the region named."""
    raise NotImplementedError("stage 5: implement _members()")

def _region_of(node, where):
    """The node's region, or the stage's own refusal naming the node."""
    raise NotImplementedError("stage 5: implement _region_of()")

def _check_notice(notice):
    """One watch entry: a received `("dead", node)` / `("alive", node)`
    pair, or a PLAIN fleet id — the shape the fabric's own state folds
    the outstanding claims into (§0.2: `notices` is a tuple of fleet
    ids). Anything else is a caller's mistake, and the refusal names
    it."""
    raise NotImplementedError("stage 5: implement _check_notice()")

def _dead_set(notices):
    """The fleet ids with an OUTSTANDING death claim: `("dead", n)`
    adds, `("alive", n)` retracts, arrival order decides. No clocks."""
    raise NotImplementedError("stage 5: implement _dead_set()")

def _region_of_votes(rows, dead):
    """The one region these votes are about, refusing a mixed pile.
    Rows vote first; without rows, the dead claims do; without either,
    no verdict needs a roster, and the caller answers suspect."""
    raise NotImplementedError("stage 5: implement _region_of_votes()")

def health(observations, notices):
    """`"up"`, `"suspect"` or `"down"` for ONE region. `"up"`: a
    majority of the roster voted ALIVE and stage 2's `healthy_count`
    of those rows reaches the majority — alive AND within `LAG_BOUND`.
    `"down"`: a majority of WITNESSED deaths — `("dead", n)` notices or
    observed `alive=False` rows, retracted by `("alive", n)` in arrival
    order. `"suspect"`: everything else — the lag broken, or silence
    blocking a verdict. Silence never votes, so no count of missing
    pings is ever `"down"`. A malformed row or notice, or votes spanning
    two regions, raises `FailError` naming the offender."""
    raise NotImplementedError("stage 5: implement health()")

def primary_gone(notices, old_region):
    """True iff the death notices a node RECEIVED prove a majority of
    `old_region` dead — retraction by arrival order, and silence never
    counts. The promotion gate of stage 7 reads exactly this: a region
    promotes when the watch SAW the old primary die, not when a ping
    went unanswered. A malformed notice or region raises `FailError`
    naming it."""
    raise NotImplementedError("stage 5: implement primary_gone()")
