"""Failover From Scratch — stage 10: The drill: RTO/RPO measured, the foil run, the audit refused

Every stage so far was a rule; this is the machine. The node protocol
(`init/recv/tick/client`) is what `fabric.Fabric` drives; the seven
schedules run through it; the report — RTO and RPO as NUMBERS THIS RUN
PRODUCED, every lost rid named — comes out the other end. The audit is
the hardest half: a pass is worth nothing unless the foil is shown
failing for the stated reasons, and the foil's failure is evidence only
when it comes back from a REAL `Fabric(naive)` run — never from `PINS`
quoted as a constant, never from the stage's opinion (H6's law). The
`notices` field is the watch channel's folded shape (§0.2): plain fleet
ids this node currently believes dead, `dead` claims folded in,
`alive` retracted, arrival-order law as always.

DESIGN DECISION — the arrival epoch is the node's own epoch, and the
replay gate is stage 8's `apply_once` wholesale?
Because a request reaching a live node through the fabric HAS been
admitted by the world's routing (the fabric itself refuses unpromoted
homes before the node ever speaks); the node's fence then guards only
what stage 8 pinned: a committed `(client, rid)` owed its recorded
answer — `REGION_DIE`'s `r=3` at ticks 9 and 11 answers `("applied",)`
twice and applies once — while a NEW write below the node's epoch is
refused forever after. The ledger shape stays stage 8's exactly, so
`seen` still reads it.

DESIGN DECISION — reads are free: a `get` never enters the ledger,
even though the wire could cache it?
Because DUAL's answer column CHANGES across ticks: caching a read is
caching a lie about the moment of service. `s3.served` re-reads the
store — every surviving sibling, never narrowed — and `applied`,
`applied_count` and the ledger move ONLY on a first-arrival `set`.

DESIGN DECISION — a `propose` adopted above the node's own epoch
absorbs the proposer's whole store BEFORE answering `("adopt",
proposer, epoch)`?
So an adopter answers from real data, not a stub, and its later
client calls resolve the DUAL siblings the proposal carried; the
reply carries the PROPOSAL's epoch (the ask is for that epoch), and a
stale propose or adopt at or below the node's own epoch is the
monotonicity law on the wire — never counted, never adopted.

DESIGN DECISION — a fresh write leaves on the wire as `sync` to every
LIVE peer and ONE `relay` to the other region's entry node?
Because the roster is where quorum lives and the link is where
siblings heal: `FLAP`'s revived `e2` still believes a majority of east
is dead, so it redirects beta's session WEST — and the west answers
from the value its peers synced at 13. Cross `sync` the fabric drops
anyway (a stage-2 law); naming the entry keeps replication one hop,
not three.

DESIGN DECISION — `drill` MEASURES rto/rpo from its own run's columns
and `audit` RE-DRIVES the foil?
Because `PINS` is the world's answer for a correct node; a report that
pastes the pin instead of computing from `result()` proves nothing
about the node that produced it — and `audit` that trusts the stage's
word about the foil trusts the accused. `naive` enters this file ONLY
as the node handed to `Fabric`: the audit is the run that proves it.
"""

import sys
import fabric
import kv
import naive
import scenarios
import topology

import stage_01 as s1
import stage_02 as s2
import stage_07 as s7
import stage_08 as s8
import stage_09 as s9

FailError = s1.FailError

DRILLS = ("ONE_NODE", "REGION_DIE", "DUAL", "FLAP", "LAG", "FAKE_DEATH",
          "ALL_DIE")
SERVED = ("ok", "applied")


def init(node_id, peers):
    """The node's opening state: `INITIAL_EPOCH`, unpromoted, empty
    store/ledger/votes/notices. `peers` is the fabric's own list — the
    region's other two ids — and this node counts itself into its
    region at `majority(len(peers) + 1)`, exactly stage 7's roster.
    An id outside the fleet is a caller's mistake, `FailError`
    naming it."""
    if node_id not in kv.VALID_NODES:
        raise FailError("init: node id %r is not in the fleet %s"
                        % (node_id, ", ".join(kv.VALID_NODES)))
    for peer in tuple(peers):
        if peer not in kv.VALID_NODES:
            raise FailError("init: peer %r is not in the fleet" % (peer,))
    return {"id": node_id, "peers": tuple(peers),
            "epoch": topology.INITIAL_EPOCH, "promoted": False,
            "applied": (), "store": {}, "hints": (), "applied_count": 0,
            "notices": (), "ledger": {}, "votes": {}}


def _region(state):
    """The node's own region — `topology` answers, never a guess."""
    return topology.region_of(state["id"])


def _other_region(state):
    """The home across the link: the relay's destination region."""
    return "west" if _region(state) == topology.PRIMARY else "east"


def _roster(state):
    """This node's region roster: itself plus its peers — the SAME
    three ids `majority` was taken over in stage 7."""
    return (state["id"],) + tuple(state["peers"])


def _alive(state):
    """The roster members under NO outstanding death claim."""
    return tuple(n for n in _roster(state) if n not in state["notices"])


def _quorum_ok(state):
    """Stage 2's gate read off this node's folded notices: the region
    can answer while a majority of its roster is not under a death
    claim. Silence is not death — notices only (§1)."""
    return s2.writable(_region(state), _alive(state)) is True


def _absorb(store, key, version):
    """Union law (stage 1): the arriving version meets the local
    siblings and NOTHING silently narrows — the maximal set under
    dominance survives, an already-held version changes no state (no
    phantom key, no re-count)."""
    old = tuple(store.get(key, ()))
    merged = s1.coalesce(old + (version,))
    if merged == old:
        return store
    store2 = dict(store)
    store2[key] = merged
    return store2


def _record(state, client_id, rid, key):
    """A write this node holds (its own or one it absorbed): the
    `(client, rid, key)` row moves with the store, stage 8's law — a
    row already present changes nothing, so a re-delivery never
    inflates `applied_count` and the fabric's `dups` column stays
    empty here."""
    entry = (client_id, rid, key)
    if entry in state["applied"]:
        return state
    return dict(state, applied=state["applied"] + (entry,),
                applied_count=state["applied_count"] + 1)


def _fold(state, subject, claimed):
    """Watch notices fold into `notices` (the §0.2 plain-id shape):
    `dead` claims, `alive` retracts, arrival order kept, a duplicate
    claim absorbed — stage 5's law carrying folded pairs."""
    notices = state["notices"]
    if claimed:
        if subject in notices:
            return state
        return dict(state, notices=notices + (subject,))
    if subject not in notices:
        return state
    return dict(state, notices=tuple(n for n in notices if n != subject))


def _wire(state, key, version, client_id, rid):
    """The replication fan: `sync` to every LIVE peer of the region,
    one `relay` to the other region's entry node — dead peers are
    skipped at the source, not dropped as traffic."""
    msgs = [fabric.message("sync", peer, state["id"], key, version,
                           client_id, rid)
            for peer in state["peers"] if peer not in state["notices"]]
    entry = topology.nodes_of(_other_region(state))[0]
    msgs.append(fabric.message("relay", entry, state["id"], key, version,
                               client_id, rid))
    return tuple(msgs)


def recv(state, message):
    """One arrival, state in / state out, replies out. `("dead"|
    "alive", subject)` folds into the notices; `sync`/`relay` — the
    7-tuples — absorb the version and record the sender's
    `(client, rid, key)` row; a `propose` (the 5-tuple) at an epoch
    above ours absorbs the proposer's whole store and answers
    `("adopt", proposer, epoch)` via the field-2 sender law, while a
    stale one moves nothing; an `adopt` tallies through stage 7 —
    counted only above our own epoch, monotonicity on the wire.
    Anything else is the caller's mistake, `FailError` naming the
    kind."""
    kind = message[0]
    if kind == "dead":
        return _fold(state, message[1], True), ()
    if kind == "alive":
        return _fold(state, message[1], False), ()
    if kind in ("sync", "relay"):
        (_kind, _target, _sender, key, version, client_id, rid) = message
        store = _absorb(state["store"], key, version)
        return _record(dict(state, store=store), client_id, rid, key), ()
    if kind == "propose":
        (_kind, _target, proposer, epoch, store) = message
        if epoch <= state["epoch"]:
            return state, ()  # monotonicity: a stale ask changes nothing
        merged = state["store"]
        for key, versions in store.items():
            for version in versions:
                merged = _absorb(merged, key, version)
        state = dict(state, store=merged)
        return state, (fabric.message("adopt", proposer, state["id"],
                                      epoch),)
    if kind == "adopt":
        (_kind, _target, adopter, epoch) = message
        if epoch <= state["epoch"]:
            return state, ()  # the recorded refusal, on the wire
        _promoted, state2 = s7.tally(state, (("adopt", state["id"],
                                              adopter, epoch),))
        return state2, ()
    raise FailError("recv: %r is not a kind this node speaks" % (kind,))


def tick(state):
    """The node's only self-initiated act, and it is stage 7's `propose`
    wholesale: the gate (not promoted, still at `INITIAL_EPOCH`, not
    the primary's own region, a MAJORITY of the old primary dead on the
    record, this region able to answer), the proposal carrying the
    store to every live peer, the self-vote recorded. When the gate
    declines, the pair is `(state, ())` — a node asks once, its region
    decides once."""
    msgs, state2 = s7.propose(state)
    return state2, msgs


def client(state, command):
    """A pinned session speaks here. Quorum first: below a majority of
    its own region on the notices, the node answers `("redirect",
    other)` — the session goes HOME, never absorbed from the wrong
    side. Otherwise stage 8's `apply_once` is the gate: a committed
    `(client, rid)` re-answers the recorded verdict and moves nothing
    (the FLAP law: three arrivals of `r=3`, one apply), a `get` reads
    through `s3.served` — free, uncached, never narrowed — and a first
    `set` applies with a clock that dominates every surviving sibling.
    The applied write then leaves on the wire: syncs plus the one
    relay. The arrival epoch is this node's own — the fabric has
    already admitted the call by routing it."""
    op, key, value, client_id, rid = fabric.parse_command(command)
    if not _quorum_ok(state):
        return state, (), ("redirect", _other_region(state))
    answer, state2 = s8.apply_once(state, client_id, rid,
                                   (op, key, value, state["epoch"]))
    if op == "get" or answer != ("applied",):
        return state, (), answer
    entry = (client_id, rid, key)
    if entry in state["applied"]:
        # the fabric re-routed a row this node already holds (the
        # REGION_DIE replay at tick 7): the ledger answers `applied`
        # again, and `applied`/`applied_count` move ONCE (stage 8's
        # law), never twice.
        state2 = dict(state2, applied=state["applied"],
                      applied_count=state["applied_count"])
    version = state2["store"][key][-1]
    return state2, _wire(state2, key, version, client_id, rid), answer


def _measure(result):
    """`(rto, rpo)` from the run's OWN columns: the first refused tick,
    the first served tick AT OR AFTER it, stage 9's `rto` (None when
    either side is missing — `REGION_DIE` never refused, `ALL_DIE`
    never served after), and `rpo` over the fabric's `lost` column.
    The pins are never the source; this run is."""
    refused = [t for t, _c, _r, verdict in result["answers"]
               if verdict[0] == "refused"]
    first_refused = min(refused) if refused else None
    served = [t for t, _c, _r, verdict in result["answers"]
              if verdict[0] in SERVED
              and first_refused is not None and t >= first_refused]
    first_served = min(served) if served else None
    return s9.rto(first_refused, first_served), s9.rpo(result["lost"])


def _name_of(pins):
    """The schedule a pins row belongs to: identity against
    `scenarios.PINS` — a drill hands back the row it read, and the
    audit grades against the world's table, not the stage's memory."""
    for name, row in scenarios.PINS.items():
        if row is pins:
            return name
    raise FailError("audit: a drill's pins is not a row of the world's "
                    "PINS table")


def _foil(name):
    """The naive foil DRIVEN through the real fabric for `name`'s
    schedule — the audit's ONLY source of foil evidence (never a
    quoted PINS column, never this module's opinion)."""
    _kind, spec, ticks, _pins = scenarios.scenario(name)
    foil = fabric.Fabric(naive, scenario=spec)
    foil.run(ticks)
    return foil.result()


def _divergence(name, foil_result):
    """The three signature failures, read off the foil's run:
    FAKE_DEATH promotes (it votes silence), FLAP re-applies a retried
    rid, DUAL answers a sibling pair NARROWED — one value where the
    probe column holds both. `None` when the foil behaved: a proof
    that reports the foil correct must itself fail."""
    answers = foil_result["answers"]
    if name == "FAKE_DEATH":
        return foil_result["promotes"] or None
    if name == "FLAP":
        return foil_result["dups"] or None
    if name == "DUAL":
        probe = {row[:3]: row[3] for row in
                 scenarios.PINS["DUAL"]["probe"]["answers"]}
        for row in answers:
            verdict = row[3]
            want = probe.get(row[:3])
            if (verdict[0] == "ok" and want is not None
                    and want[0] == "ok" and set(verdict[1]) < set(want[1])):
                return row
        return None
    return None


def drill(name):
    """`("scenario", result, pins, rto, rpo)` — the schedule `name`
    run through `Fabric` at its pinned horizon with THIS module as the
    node. `result` is the run's own dict (promotes, answers, dups,
    lost, final states, traffic); `pins` is the world's row for the
    name; `rto`/`rpo` are MEASURED from the run (§1: the report's
    numbers are the ones this node produced). An unknown name is the
    caller's mistake — `scenarios.scenario` refuses it, naming the
    table."""
    _kind, spec, ticks, pins = scenarios.scenario(name)
    node = sys.modules[__name__]
    fabric_run = fabric.Fabric(node, scenario=spec)
    fabric_run.run(ticks)
    result = fabric_run.result()
    rto, rpo = _measure(result)
    return ("scenario", result, pins, rto, rpo)


def _grade(name, result, pins, rto, rpo):
    """The run graded against the probe column, fact by fact — every
    mismatch names its column, never a bare False."""
    why = []
    probe = pins["probe"]
    for column in ("promotes", "answers", "dups", "lost"):
        if result[column] != probe[column]:
            why.append("%s: %s %r, the probe column says %r"
                       % (name, column, result[column], probe[column]))
    if rto != probe["rto"]:
        why.append("%s: measured rto %r, the probe column says %r"
                   % (name, rto, probe["rto"]))
    if rpo != probe["rpo"]:
        why.append("%s: measured rpo %r, the probe column says %r"
                   % (name, rpo, probe["rpo"]))
    return why


def audit(drills):
    """`("verdict", reasons)` — `("pass", ())` only under BOTH proofs.
    THE RUN: every drill row must match its probe column on promotes,
    answers, dups, lost and on the MEASURED rto/rpo — which carries
    FLAP's empty `dups`, LAG's `lost` naming every rid the fabric's
    column names, and the rto/rpo of the report itself. THE FOIL:
    FAKE_DEATH, FLAP and DUAL are re-driven through `Fabric(naive)`
    HERE, and the audit passes only if the foil's own run shows the
    signature failures — promotions on silence, re-applied retries, a
    narrowed sibling answer. A proof that reports the foil behaving
    correctly is itself a wrong answer (H6's law, restated): that
    drill row FAILS, with every reason named."""
    rows = []
    for row in tuple(drills):
        if (not isinstance(row, tuple) or len(row) != 5
                or row[0] != "scenario"):
            raise FailError("audit: a drill row must be ('scenario', "
                            "result, pins, rto, rpo), got %r" % (row,))
        _tag, result, pins, rto, rpo = row
        if not isinstance(result, dict) or not isinstance(pins, dict):
            raise FailError("audit: a drill row must carry the run's "
                            "result dict and its pins dict, got %r"
                            % (row,))
        for column in ("promotes", "answers", "dups", "lost"):
            if column not in result:
                raise FailError("audit: the run's result is missing %r"
                                % (column,))
        for column in ("probe", "naive"):
            if column not in pins:
                raise FailError("audit: the pins row is missing %r"
                                % (column,))
        rows.append((_name_of(pins), result, pins, rto, rpo))
    reasons = []
    for name, result, pins, rto, rpo in rows:
        reasons.extend(_grade(name, result, pins, rto, rpo))
    drilled = {name for name, _r, _p, _x, _y in rows}
    for name in DRILLS:
        if name not in drilled:
            reasons.append("the drill never ran %s" % (name,))
    for name in ("FAKE_DEATH", "FLAP", "DUAL"):
        foil_result = _foil(name)
        if _divergence(name, foil_result) is None:
            reasons.append("the naive foil's %s run behaved correctly "
                           "— the audit refuses a proof that reports "
                           "the foil right" % (name,))
    if reasons:
        return ("fail", tuple(reasons))
    return ("pass", ())
