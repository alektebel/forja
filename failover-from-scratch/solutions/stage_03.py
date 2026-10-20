"""Failover From Scratch — stage 3: Hints: held for a peer, never served as yours.

When a write reaches a quorum but a peer is unreachable, A6's answer is
the hinted handoff: park the write ON the peer, for the peer. Two laws
keep this honest, and both live in this stage. First, a hint is only
for a node you cannot reach — and the fabric delivers intra-region
traffic the same tick, so "cannot reach" is never true of a neighbor:
parking an own-region hint is a misuse the stage refuses by name.
Second, a held hint is not an owned version: serving it as yours would
answer a `get` with traffic you merely hold in transit (that is the
foil's third flaw, and DUAL/FLAP pin it). The pile therefore has an
owner, a relay path home, and a read gate that only ever widens with
versions the node applied itself.

DESIGN DECISION — the actor is a parameter, not a field of the state?
Because "whose region" and "who sent this relay" are statements about
the CALLER, and the fabric's sender law already pins the sender at
field 2 of every message. A `park` that guessed the parker from the
hint would let one node park on another's behalf — the exact forgery
the sender law exists to stop. The actor is explicit so the refusal
and the relay name the right ids.

DESIGN DECISION — `deliver` returns `(relayed, kept)`, never a new
pile in place?
Because the caller must be able to see what left: a pile that merely
shrank hides whether a hint was relayed or dropped. The relayed
messages are the evidence; `kept` is exactly the rest, in pile order.
Idempotence is then mechanical: run the same live set twice and the
second call relays the same payloads and keeps nothing, because
`kept` is `hints` minus what left.

DESIGN DECISION — why does `served` take the hint pile at all?
Because the honest answer to "what would this node reply" must be
testable against the temptation: `served(versions, ())` and
`served(versions, hints)` return the identical answer, and the check
holds that equality as a fact. A function that never saw the pile
could not promise it.
"""

import fabric
import kv
import topology

import stage_01 as s1

FailError = s1.FailError


def _region_of(node, where):
    """The actor/owner's region as a `FailError`-raising lookup:
    `topology` answers a plain ValueError naming the id and the roster;
    the protocol's refusals are `FailError`, so the text is carried."""
    try:
        return topology.region_of(node)
    except ValueError as problem:
        raise FailError("%s: %s" % (where, problem)) from None


def _check_hint(h):
    """A hint must be exactly `kv.hint(...)`'s shape; anything else is
    `kv.KvError` naming the offender."""
    if (not isinstance(h, tuple) or len(h) != 4 or h[0] != kv.KIND_HINT):
        raise kv.KvError("stage_03: a hint must be ('hint', key, version, "
                         "intended_for), got %r" % (h,))
    kv.clock_of(h[2])
    if not isinstance(h[3], str) or h[3] not in kv.VALID_NODES:
        raise kv.KvError("stage_03: a hint's intended_for %r is not in the "
                         "fleet %s" % (h[3], ", ".join(kv.VALID_NODES)))
    return h


def park(parker, hints, h):
    """The pile with `h` added. An exact duplicate stays one hint; a
    hint whose owner lives in the PARKER's own region is refused with
    `FailError` naming both ids and the region — intra-region traffic
    lands same-tick, so a neighbor is never unreachable. A malformed
    hint raises `kv.KvError`; a malformed actor raises `FailError`."""
    mine = _region_of(parker, "park")
    _check_hint(h)
    owner_region = _region_of(h[3], "park")
    if owner_region == mine:
        raise FailError(
            "park: %s holds a hint for %s, both in %s — a hint is only "
            "for a node you cannot reach, and a neighbor always can"
            % (parker, h[3], mine))
    pile = tuple(hints)
    if h in pile:
        return pile
    return pile + (h,)


def deliver(parker, hints, live_ids):
    """Every hint whose owner is in `live_ids` leaves the pile as
    `fabric.message("relay", owner, parker, key, version)`; the rest
    stays, in pile order. Re-running with the same live set relays the
    same payloads and keeps the whole pile — the owner's ledger (stage
    8) is what makes the re-delivery cost nothing. A malformed actor or
    live id raises `FailError`; a malformed hint raises `kv.KvError`."""
    _region_of(parker, "deliver")
    pile = tuple(hints)
    for h in pile:
        _check_hint(h)
    live = set()
    for node in tuple(live_ids):
        if node not in kv.VALID_NODES:
            raise FailError("deliver: live id %r is not in the fleet %s"
                            % (node, ", ".join(kv.VALID_NODES)))
        live.add(node)
    relayed = []
    kept = []
    for h in pile:
        if h[3] in live:
            relayed.append(
                fabric.message("relay", h[3], parker, h[1], h[2]))
        else:
            kept.append(h)
    return tuple(relayed), tuple(kept)


def owned(store_versions):
    """The versions a node OWNS for a key: already a tuple, validated
    through `kv` so a hint-shaped thing parked in a store is refused
    here, never served."""
    versions = tuple(store_versions)
    for v in versions:
        kv.clock_of(v)
    return versions


def served(versions, held_hints):
    """The read answer `("ok", values)`: the node's OWN versions,
    coalesced (stage 1), values sorted. `held_hints` is the pile the
    node might be tempted by — it NEVER widens the answer; the check
    pins `served(v, ()) == served(v, hints)`."""
    tuple(held_hints)  # looked at, never used: the law is the equality
    answers = s1.coalesce(owned(versions))
    return ("ok", tuple(sorted(v[1] for v in answers)))
