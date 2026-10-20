"""Failover From Scratch — stage 8: The redirect that does not apply a write twice.

TODO: implement each function; the docstring is the contract.

A client with a pinned session does not know its home died. It retries —
same client, same request id — and a node that cannot tell a retry from
a new order applies the write twice. `applied` after `applied` is the
`dups` column, `REGION_DIE` and `FLAP` naming every re-apply of the
naive foil. The fix is a ledger keyed `(client, rid)`: the FIRST arrival
of a set applies — store, `applied` and `applied_count` all move
together — and every later arrival returns the RECORDED answer and moves
nothing. Reads are free: a `get` never touches the ledger, because a
read answers from the store as it stands, not from history. And an op
that arrives from BELOW the node's epoch is refused `"fenced"`: a write
carried by a stale partition cannot re-open a closed epoch.

DESIGN DECISION — the ledger lookup runs BEFORE the fence test?
Because a client that was acked `("applied",)` at tick 3 is owed that
answer at tick 7 even though the node promoted in between. `REGION_DIE`
is exactly that call: `set a=2 r=2` acked east pre-death, retried west
at tick 7 at epoch 2 — fence-first would answer `("refused", "fenced")`
and break the probe's pinned column. The fence protects the store from
a NEW write of an old epoch; it never un-acks a committed one.

DESIGN DECISION — the recorded entry is `(("applied",), value)`, and a
replay returns the ANSWER half only?
Because the fabric's answer column is `("applied",)`, exactly: what the
ledger REMEMBERS (the value the first application produced) is more
than what a retry NEEDS to be told (`seen` exposes the full entry). A
richer answer on replay would make the retry's verdict differ from the
first — clients noticing a difference is clients noticing a bug.

DESIGN DECISION — the new version's clock is the elementwise max over
the surviving siblings, bumped for this node?
Because `DUAL`'s lesson is that a sibling set is never silently
narrowed — but a WRITE after the conflict must END it: only a clock
that dominates every sibling (`kv.dominates`, world law) makes the new
value unresurrectable by a replica that still holds one of them.
Bumping one sibling's clock alone would leave the other concurrent,
and the next `get` would answer two values for an acked write."""


import kv

import stage_01 as s1

import stage_03 as s3

FailError = s1.FailError

OPS = ("set", "get")

def _owned_hint(hint):
    """A parked hint must be a legal hint tuple — a shape the caller
    broke raises `FailError` naming it, not the world's `KvError`."""
    raise NotImplementedError("stage 8: implement _owned_hint()")

def _check_state(state, where):
    """The node's state: `id` in the fleet, `epoch` an int >= 0, `store`
    a dict of `s3.owned` version tuples, `applied` a tuple of
    `(client, rid, key)` rows, `applied_count` an int >= 0, `ledger` a
    dict of `(client, rid)` -> recorded entry, `hints` a tuple of legal
    hints (read only, for `get`'s answer shape). Every malformed field
    raises `FailError` naming the offender."""
    raise NotImplementedError("stage 8: implement _check_state()")

def _check_op(op):
    """The arriving op is `(kind, key, value, epoch)`: kind in `OPS`,
    key a non-empty string, value a string for a `set` and `None` for a
    `get`, epoch the arrival epoch — an int >= 0. Anything else is the
    caller's mistake, named."""
    raise NotImplementedError("stage 8: implement _check_op()")

def _merged_clock(versions, node):
    """The bump clock of a write: `kv.bump` of the elementwise max over
    the SURVIVING siblings' clocks — dominating every sibling by
    construction, so a replica holding one of them cannot resurrect it
    against this write."""
    raise NotImplementedError("stage 8: implement _merged_clock()")

def apply_once(state, client, rid, op):
    """`(answer, state2)` — the exactly-once gate. A `set` whose
    `(client, rid)` is already in the ledger returns the RECORDED
    answer and moves NOTHING (the FLAP law); the fence test runs only
    for arrivals the ledger has never seen, and refuses an op arriving
    from below the node's epoch with `("refused", "fenced")`, state
    untouched. A first arrival of a `set` applies: one new version per
    key whose clock dominates every surviving sibling (`_merged_clock`
    + `kv.bump`), `applied`, `applied_count` and the ledger entry all
    moving together, and the answer is `("applied",)`. A `get` answers
    from the store — `s3.served` over the key's versions — and touches
    nothing: reads are free, writes are once. A malformed client, rid
    or op raises `FailError` naming it; a malformed state or a hint
    parked in the store raises `FailError` / `kv.KvError`."""
    raise NotImplementedError("stage 8: implement apply_once()")

def seen(state, client, rid):
    """The ledger's entry for `(client, rid)` — `(("applied",), value)`
    — or `None` when this node has never seen that request. A `get`
    never lands here: reads are free, writes are once."""
    raise NotImplementedError("stage 8: implement seen()")
