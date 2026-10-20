"""Failover From Scratch — stage 10: The drill: RTO/RPO measured, the foil run, the audit refused.

TODO: implement each function; the docstring is the contract.

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
as the node handed to `Fabric`: the audit is the run that proves it."""


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
    raise NotImplementedError("stage 10: implement init()")

def _region(state):
    """The node's own region — `topology` answers, never a guess."""
    raise NotImplementedError("stage 10: implement _region()")

def _other_region(state):
    """The home across the link: the relay's destination region."""
    raise NotImplementedError("stage 10: implement _other_region()")

def _roster(state):
    """This node's region roster: itself plus its peers — the SAME
    three ids `majority` was taken over in stage 7."""
    raise NotImplementedError("stage 10: implement _roster()")

def _alive(state):
    """The roster members under NO outstanding death claim."""
    raise NotImplementedError("stage 10: implement _alive()")

def _quorum_ok(state):
    """Stage 2's gate read off this node's folded notices: the region
    can answer while a majority of its roster is not under a death
    claim. Silence is not death — notices only (§1)."""
    raise NotImplementedError("stage 10: implement _quorum_ok()")

def _absorb(store, key, version):
    """Union law (stage 1): the arriving version meets the local
    siblings and NOTHING silently narrows — the maximal set under
    dominance survives, an already-held version changes no state (no
    phantom key, no re-count)."""
    raise NotImplementedError("stage 10: implement _absorb()")

def _record(state, client_id, rid, key):
    """A write this node holds (its own or one it absorbed): the
    `(client, rid, key)` row moves with the store, stage 8's law — a
    row already present changes nothing, so a re-delivery never
    inflates `applied_count` and the fabric's `dups` column stays
    empty here."""
    raise NotImplementedError("stage 10: implement _record()")

def _fold(state, subject, claimed):
    """Watch notices fold into `notices` (the §0.2 plain-id shape):
    `dead` claims, `alive` retracts, arrival order kept, a duplicate
    claim absorbed — stage 5's law carrying folded pairs."""
    raise NotImplementedError("stage 10: implement _fold()")

def _wire(state, key, version, client_id, rid):
    """The replication fan: `sync` to every LIVE peer of the region,
    one `relay` to the other region's entry node — dead peers are
    skipped at the source, not dropped as traffic."""
    raise NotImplementedError("stage 10: implement _wire()")

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
    raise NotImplementedError("stage 10: implement recv()")

def tick(state):
    """The node's only self-initiated act, and it is stage 7's `propose`
    wholesale: the gate (not promoted, still at `INITIAL_EPOCH`, not
    the primary's own region, a MAJORITY of the old primary dead on the
    record, this region able to answer), the proposal carrying the
    store to every live peer, the self-vote recorded. When the gate
    declines, the pair is `(state, ())` — a node asks once, its region
    decides once."""
    raise NotImplementedError("stage 10: implement tick()")

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
    raise NotImplementedError("stage 10: implement client()")

def _measure(result):
    """`(rto, rpo)` from the run's OWN columns: the first refused tick,
    the first served tick AT OR AFTER it, stage 9's `rto` (None when
    either side is missing — `REGION_DIE` never refused, `ALL_DIE`
    never served after), and `rpo` over the fabric's `lost` column.
    The pins are never the source; this run is."""
    raise NotImplementedError("stage 10: implement _measure()")

def _name_of(pins):
    """The schedule a pins row belongs to: identity against
    `scenarios.PINS` — a drill hands back the row it read, and the
    audit grades against the world's table, not the stage's memory."""
    raise NotImplementedError("stage 10: implement _name_of()")

def _foil(name):
    """The naive foil DRIVEN through the real fabric for `name`'s
    schedule — the audit's ONLY source of foil evidence (never a
    quoted PINS column, never this module's opinion)."""
    raise NotImplementedError("stage 10: implement _foil()")

def _divergence(name, foil_result):
    """The three signature failures, read off the foil's run:
    FAKE_DEATH promotes (it votes silence), FLAP re-applies a retried
    rid, DUAL answers a sibling pair NARROWED — one value where the
    probe column holds both. `None` when the foil behaved: a proof
    that reports the foil correct must itself fail."""
    raise NotImplementedError("stage 10: implement _divergence()")

def drill(name):
    """`("scenario", result, pins, rto, rpo)` — the schedule `name`
    run through `Fabric` at its pinned horizon with THIS module as the
    node. `result` is the run's own dict (promotes, answers, dups,
    lost, final states, traffic); `pins` is the world's row for the
    name; `rto`/`rpo` are MEASURED from the run (§1: the report's
    numbers are the ones this node produced). An unknown name is the
    caller's mistake — `scenarios.scenario` refuses it, naming the
    table."""
    raise NotImplementedError("stage 10: implement drill()")

def _grade(name, result, pins, rto, rpo):
    """The run graded against the probe column, fact by fact — every
    mismatch names its column, never a bare False."""
    raise NotImplementedError("stage 10: implement _grade()")

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
    raise NotImplementedError("stage 10: implement audit()")
