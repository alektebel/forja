"""Failover From Scratch — stage 9: Late writes: reconcile, name the lost, price the RPO.

TODO: implement each function; the docstring is the contract.

Two regions that wrote through a `DUAL` window come back with two
answers for the same keys, and the merge that ends the outage is the
union stage 4 already knows: `merged` puts every key's siblings
together, choosing nothing — the answer set of a conflicted key is
EVERY surviving sibling, and a subsequent write (stage 8's bump) ends
the conflict, never a silent narrowing. Then the honest part: an acked
write whose key no LIVE store carries at the horizon is a promise the
fleet broke, and a report that counts it without NAMING its rid is how
outages get understated. `lost` walks the acked rows and names every
one the surviving stores cannot answer; `rpo` is its length — a count,
not a percentage; `rto` is the tick difference between the first
refusal and the first service after it, `None` when nothing was ever
refused. `LAG` prices this stage exactly: two acked writes, both named,
`rpo = 2`, and the fabric's `lost` column agrees because the column and
this function read the same acks.

DESIGN DECISION — `merged` unions through `s4.repair` and never takes
the higher side?
Because the sibling set is stage 1's fact and A6's law restated: after
a cut, `('3','5')` are both true. Dropping one is the lost update the
vector clock exists to prevent — the foil's narrowing is what stage 1
names and `DUAL`'s answer column pins. Repair is a union; only stage
8's write, whose bumped clock dominates every sibling, ends a
conflict, and it ends it by construction, not by choice.

DESIGN DECISION — `lost` prices a write by its KEY being absent from
every live store, not by the exact version?
Because the client's ack is a promise about the KEY, not about one
incarnation of it: `DUAL`'s r=1 was legitimately overwritten by the
same client's r=3, and the fabric's `lost` column keeps r=1 — the
fleet still answers for that key. A key no live store carries AT ALL
is a different fact: `LAG`'s `p` was acked east, the relays died with
the hints, and no surviving node can speak for the write. Absence of
the key names the broken promise exactly; absence of one version does
not.

DESIGN DECISION — duplicate acked rows are named ONCE?
Because `rpo` is a count of writes, not a count of arrivals, and a
client that retried `set a=1 r=3` three times while east was dead was
owed ONE promise. Naming it three times would inflate the RPO into a
retry counter, and the report's whole purpose is the honest number.

DESIGN DECISION — `rto` refuses a served tick BELOW the refused tick?
Because `first_served - first_refused` is the outage's duration, and a
negative difference means the caller passed the arguments in the wrong
order — `FLAP`'s `rto = 6` is `13 - 7`, and the function that silently
returns `-6` is the one that makes a 6-tick outage look like a rounding
error. The refusal names both ticks."""


import kv

import stage_01 as s1

import stage_03 as s3

import stage_04 as s4

FailError = s1.FailError

def _check_store(store, where, what):
    """A store is a dict of key -> tuple of owned versions — the
    world's grammar refuses anything else with `kv.KvError`; a store
    that is not a dict at all is the caller's mistake, `FailError`."""
    raise NotImplementedError("stage 9: implement _check_store()")

def merged(store_a, store_b):
    """The union of two stores, per key through §3.4's `repair` —
    every surviving sibling of a conflicted key, no choice, no
    narrowing. A key only one side carries travels whole; a key both
    carry coalesces (`s1.coalesce` inside `repair` absorbs the exact
    duplicates, so syncing the same version twice is idempotent). The
    result is a plain dict keyed in sorted order — determinism, not
    aesthetics: two nodes merging the same pair byte-for-byte agree.
    A malformed store raises `FailError` naming it; a malformed
    version inside one raises `kv.KvError`."""
    raise NotImplementedError("stage 9: implement merged()")

def _check_acked(acked, where):
    """The acked rows are `(client, rid, key)` triples — the ledger's
    shape (stage 8, §0.2's `applied` rows): client and key non-empty
    strings, rid an int >= 0. Anything else is the caller's mistake,
    named."""
    raise NotImplementedError("stage 9: implement _check_acked()")

def lost(acked, final_stores):
    """Every acked `(client, rid, key)` whose key NO live store carries
    at the horizon — each NAMED, never counted-and-forgotten (the
    committed ack is owed the truth, §1). `final_stores` is a tuple of
    the live nodes' stores (empty tuple: nothing survived, every ack is
    named). Rows repeat at most once in the answer: the count is a
    count of WRITES, not of arrivals. Order follows `acked` — the
    ledger's truth in arrival order. A malformed row or a malformed
    store raises `FailError` naming it; a malformed version inside a
    store raises `kv.KvError`."""
    raise NotImplementedError("stage 9: implement lost()")

def rpo(lost_rows):
    """The recovery point objective — the LENGTH of `lost`, an int.
    A count, never a percentage: §1 forbids a float, and a writer that
    divided by a total would be pricing writes that were never acked.
    Not a tuple is the caller's mistake: `FailError`."""
    raise NotImplementedError("stage 9: implement rpo()")

def rto(first_refused, first_served):
    """The recovery time objective — `first_served - first_refused`,
    int ticks, or `None` when EITHER side is `None`: a run that never
    refused (`REGION_DIE`, promoted before the fallback spoke) has no
    outage to price, and a run that refused and never served back
    (`ALL_DIE`) has no recovery to measure — inventing a number for
    either would be the report lying. A served tick BELOW the refused
    tick is the caller's mistake, naming both ticks."""
    raise NotImplementedError("stage 9: implement rto()")
