"""Failover From Scratch — stage 3: Hints: held for a peer, never served as yours.

TODO: implement each function; the docstring is the contract.

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
could not promise it."""


import fabric

import kv

import topology

import stage_01 as s1

FailError = s1.FailError

def _region_of(node, where):
    """The actor/owner's region as a `FailError`-raising lookup:
    `topology` answers a plain ValueError naming the id and the roster;
    the protocol's refusals are `FailError`, so the text is carried."""
    raise NotImplementedError("stage 3: implement _region_of()")

def _check_hint(h):
    """A hint must be exactly `kv.hint(...)`'s shape; anything else is
    `kv.KvError` naming the offender."""
    raise NotImplementedError("stage 3: implement _check_hint()")

def park(parker, hints, h):
    """The pile with `h` added. An exact duplicate stays one hint; a
    hint whose owner lives in the PARKER's own region is refused with
    `FailError` naming both ids and the region — intra-region traffic
    lands same-tick, so a neighbor is never unreachable. A malformed
    hint raises `kv.KvError`; a malformed actor raises `FailError`."""
    raise NotImplementedError("stage 3: implement park()")

def deliver(parker, hints, live_ids):
    """Every hint whose owner is in `live_ids` leaves the pile as
    `fabric.message("relay", owner, parker, key, version)`; the rest
    stays, in pile order. Re-running with the same live set relays the
    same payloads and keeps the whole pile — the owner's ledger (stage
    8) is what makes the re-delivery cost nothing. A malformed actor or
    live id raises `FailError`; a malformed hint raises `kv.KvError`."""
    raise NotImplementedError("stage 3: implement deliver()")

def owned(store_versions):
    """The versions a node OWNS for a key: already a tuple, validated
    through `kv` so a hint-shaped thing parked in a store is refused
    here, never served."""
    raise NotImplementedError("stage 3: implement owned()")

def served(versions, held_hints):
    """The read answer `("ok", values)`: the node's OWN versions,
    coalesced (stage 1), values sorted. `held_hints` is the pile the
    node might be tempted by — it NEVER widens the answer; the check
    pins `served(v, ()) == served(v, hints)`."""
    raise NotImplementedError("stage 3: implement served()")
