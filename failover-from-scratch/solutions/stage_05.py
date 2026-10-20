"""Failover From Scratch — stage 5: Health: a signal that is not a heartbeat.

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
rows excluded, and `down` means the region died on the record.
"""

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
    try:
        return topology.nodes_of(region)
    except ValueError as problem:
        raise FailError(str(problem)) from None


def _region_of(node, where):
    """The node's region, or the stage's own refusal naming the node."""
    if node not in kv.VALID_NODES:
        raise FailError("%s: %r is not in the fleet %s"
                        % (where, node, ", ".join(kv.VALID_NODES)))
    return topology.region_of(node)


def _check_notice(notice):
    """One watch entry: a received `("dead", node)` / `("alive", node)`
    pair, or a PLAIN fleet id — the shape the fabric's own state folds
    the outstanding claims into (§0.2: `notices` is a tuple of fleet
    ids). Anything else is a caller's mistake, and the refusal names
    it."""
    if isinstance(notice, str):
        if notice in kv.VALID_NODES:
            return ("dead", notice)
        raise FailError("health: %r is not a fleet id" % (notice,))
    if (not isinstance(notice, tuple) or len(notice) != 2
            or notice[0] not in fabric.WATCH_KINDS
            or not isinstance(notice[1], str)
            or notice[1] not in kv.VALID_NODES):
        raise FailError("health: a notice must be ('dead'|'alive', node) "
                        "with node in the fleet, got %r" % (notice,))
    return notice


def _dead_set(notices):
    """The fleet ids with an OUTSTANDING death claim: `("dead", n)`
    adds, `("alive", n)` retracts, arrival order decides. No clocks."""
    dead = set()
    for notice in tuple(notices):
        kind, node = _check_notice(notice)
        if kind == "dead":
            dead.add(node)
        else:
            dead.discard(node)
    return dead


def _region_of_votes(rows, dead):
    """The one region these votes are about, refusing a mixed pile.
    Rows vote first; without rows, the dead claims do; without either,
    no verdict needs a roster, and the caller answers suspect."""
    region = None
    for row in rows:
        node_region = _region_of(row[0], "health")
        if region is None:
            region = node_region
        elif node_region != region:
            raise FailError("health: %s is in %s, but %s is in %s — "
                            "one call, one region"
                            % (rows[0][0], region, row[0], node_region))
    if region is None:
        for node in sorted(dead):
            node_region = _region_of(node, "health")
            if region is None:
                region = node_region
            elif node_region != region:
                raise FailError("health: the death claims span %s and %s "
                                "— one call, one region"
                                % (region, node_region))
    return region


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
    rows = tuple(observations)
    s2.healthy_count(rows)  # the shape gate: (node, int>=0, bool), or refuse
    dead = _dead_set(notices)
    region = _region_of_votes(rows, dead)
    if region is None:
        return "suspect"
    roster = _members(region)
    need = topology.majority(len(roster))
    alive_votes = []
    alive_ids = set()
    dead_votes = set()
    for node, applied, alive in rows:
        if node in dead:
            dead_votes.add(node)
        elif alive:
            alive_ids.add(node)
            alive_votes.append((node, applied, True))
        else:
            dead_votes.add(node)
    dead_votes |= {node for node in dead if node in roster}
    if len(dead_votes) >= need:
        return "down"
    if len(alive_ids) >= need and s2.healthy_count(alive_votes) >= need:
        return "up"
    return "suspect"


def primary_gone(notices, old_region):
    """True iff the death notices a node RECEIVED prove a majority of
    `old_region` dead — retraction by arrival order, and silence never
    counts. The promotion gate of stage 7 reads exactly this: a region
    promotes when the watch SAW the old primary die, not when a ping
    went unanswered. A malformed notice or region raises `FailError`
    naming it."""
    roster = _members(old_region)
    dead = _dead_set(notices)
    return len({node for node in dead
                if node in roster}) >= topology.majority(len(roster))
