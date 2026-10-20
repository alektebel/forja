"""Failover From Scratch — stage 8: The redirect that does not apply a write twice.

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
and the next `get` would answer two values for an acked write.
"""

import kv

import stage_01 as s1
import stage_03 as s3

FailError = s1.FailError

OPS = ("set", "get")


def _owned_hint(hint):
    """A parked hint must be a legal hint tuple — a shape the caller
    broke raises `FailError` naming it, not the world's `KvError`."""
    if not isinstance(hint, tuple) or len(hint) != 4 or hint[0] != "hint":
        raise FailError("state: hint %r is malformed" % (hint,))
    try:
        kv.hint(hint[1], hint[2], hint[3])
    except kv.KvError as problem:
        raise FailError("state: hint %r is malformed (%s)" % (hint, problem))


def _check_state(state, where):
    """The node's state: `id` in the fleet, `epoch` an int >= 0, `store`
    a dict of `s3.owned` version tuples, `applied` a tuple of
    `(client, rid, key)` rows, `applied_count` an int >= 0, `ledger` a
    dict of `(client, rid)` -> recorded entry, `hints` a tuple of legal
    hints (read only, for `get`'s answer shape). Every malformed field
    raises `FailError` naming the offender."""
    if not isinstance(state, dict):
        raise FailError("%s: state must be a dict, got %r" % (where, state))
    node = state.get("id")
    if node not in kv.VALID_NODES:
        raise FailError("%s: state id %r is not in the fleet %s"
                        % (where, node, ", ".join(kv.VALID_NODES)))
    epoch = state.get("epoch")
    if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
        raise FailError("%s: epoch must be an int >= 0, got %r"
                        % (where, epoch))
    store = state.get("store")
    if not isinstance(store, dict):
        raise FailError("%s: store must be a dict, got %r" % (where, store))
    for versions in store.values():
        s3.owned(versions)
    applied = state.get("applied", ())
    if not isinstance(applied, tuple):
        raise FailError("%s: applied must be a tuple, got %r"
                        % (where, applied))
    for row in applied:
        if (not isinstance(row, tuple) or len(row) != 3
                or not isinstance(row[0], str) or not isinstance(row[1], int)
                or isinstance(row[1], bool) or row[1] < 0
                or not isinstance(row[2], str)):
            raise FailError("%s: applied row %r must be (client, rid, key)"
                            % (where, row))
    applied_count = state.get("applied_count")
    if (not isinstance(applied_count, int)
            or isinstance(applied_count, bool) or applied_count < 0):
        raise FailError("%s: applied_count must be an int >= 0, got %r"
                        % (where, applied_count))
    ledger = state.get("ledger", {})
    if not isinstance(ledger, dict):
        raise FailError("%s: ledger must be a dict, got %r" % (where, ledger))
    for rid_key, entry in ledger.items():
        if (not isinstance(rid_key, tuple) or len(rid_key) != 2
                or not isinstance(rid_key[0], str)
                or not isinstance(rid_key[1], int)
                or isinstance(rid_key[1], bool) or rid_key[1] < 0):
            raise FailError("%s: ledger key %r must be (client, rid)"
                            % (where, rid_key))
        if (not isinstance(entry, tuple) or len(entry) != 2
                or not isinstance(entry[0], tuple)
                or entry[0][0] not in ("applied", "ok", "refused")
                or not isinstance(entry[1], str)):
            raise FailError("%s: ledger entry %r must be (answer, value)"
                            % (where, entry))
    hints = state.get("hints", ())
    if not isinstance(hints, tuple):
        raise FailError("%s: hints must be a tuple, got %r" % (where, hints))
    for hint in hints:
        _owned_hint(hint)
    return node, epoch, store, applied, applied_count, ledger, hints


def _check_op(op):
    """The arriving op is `(kind, key, value, epoch)`: kind in `OPS`,
    key a non-empty string, value a string for a `set` and `None` for a
    `get`, epoch the arrival epoch — an int >= 0. Anything else is the
    caller's mistake, named."""
    if (not isinstance(op, tuple) or len(op) != 4
            or op[0] not in OPS):
        raise FailError("apply_once: an op must be (kind, key, value, "
                        "epoch) with kind in %s, got %r"
                        % (", ".join(OPS), op))
    kind, key, value, epoch = op
    if not isinstance(key, str) or not key:
        raise FailError("apply_once: a key must be a non-empty string, "
                        "got %r" % (key,))
    if kind == "set" and not isinstance(value, str):
        raise FailError("apply_once: a set's value must be a string, "
                        "got %r" % (value,))
    if kind == "get" and value is not None:
        raise FailError("apply_once: a get carries no value, got %r"
                        % (value,))
    if not isinstance(epoch, int) or isinstance(epoch, bool) or epoch < 0:
        raise FailError("apply_once: an op epoch must be an int >= 0, "
                        "got %r" % (epoch,))
    return kind, key, value, epoch


def _merged_clock(versions, node):
    """The bump clock of a write: `kv.bump` of the elementwise max over
    the SURVIVING siblings' clocks — dominating every sibling by
    construction, so a replica holding one of them cannot resurrect it
    against this write."""
    clock = []
    for sibling in s1.coalesce(versions):
        for peer, counter in kv.clock_of(sibling):
            clock = [(p, max(c, counter)) if p == peer else (p, c)
                     for p, c in clock]
            if not any(p == peer for p, _c in clock):
                clock.append((peer, counter))
    return kv.bump(tuple(sorted(clock)), node)


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
    node, epoch, store, applied, applied_count, ledger, hints = \
        _check_state(state, "apply_once")
    if not isinstance(client, str) or not client:
        raise FailError("apply_once: client must be a non-empty string, "
                        "got %r" % (client,))
    if not isinstance(rid, int) or isinstance(rid, bool) or rid < 0:
        raise FailError("apply_once: rid must be an int >= 0, got %r"
                        % (rid,))
    kind, key, value, op_epoch = _check_op(op)
    if kind == "set":
        entry = ledger.get((client, rid))
        if entry is not None:
            return entry[0], state
    if op_epoch < epoch:
        return ("refused", "fenced"), state
    versions = tuple(store.get(key, ()))
    if kind == "get":
        return s3.served(versions, hints), state
    winner = kv.version(value, _merged_clock(versions, node))
    store2 = dict(store)
    store2[key] = (winner,)
    ledger2 = dict(ledger)
    ledger2[(client, rid)] = (("applied",), value)
    state2 = dict(state, store=store2,
                  applied=applied + ((client, rid, key),),
                  applied_count=applied_count + 1,
                  ledger=ledger2)
    return ("applied",), state2


def seen(state, client, rid):
    """The ledger's entry for `(client, rid)` — `(("applied",), value)`
    — or `None` when this node has never seen that request. A `get`
    never lands here: reads are free, writes are once."""
    _check_state(state, "seen")
    if not isinstance(rid, int) or isinstance(rid, bool) or rid < 0:
        raise FailError("seen: rid must be an int >= 0, got %r" % (rid,))
    return state.get("ledger", {}).get((client, rid))
