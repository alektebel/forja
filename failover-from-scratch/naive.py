"""naive.py — the foil node: a Dynamo-shaped wishful thinker (provided world).

Three flaws, each the negative image of a law:

1. SILENCE IS DEATH. The foil expects heartbeats its peers never send —
   the watch channel carries edge notices only — so after HB of its own
   ticks without hearing anything it declares the primary gone and
   promotes itself. Every quiet cluster "fails over" on its own;
   FAKE_DEATH splits the brain without a single death. (Law: health is
   built from notices, stages 5 and 7.)

2. NEVER RECONCILE ACROSS THE LINK. It syncs writes to same-region
   peers and calls that replicated. A concurrent sibling set is answered
   by "my local best" — the lost-update law, stages 1 and 9 — and a
   sibling's divergent history never reaches the other region.

3. NO LEDGER. Every arrival of a retried (client, rid) is applied afresh
   and re-acked. Exactly-once is a property of the ledger (stage 8);
   the foil has none, so FLAP's duplicate deliveries double-apply.

PINS in scenarios.py records what this node does on every scenario so
each stage's check can name, per scenario, the columns the honest node
gets right and this one gets wrong. It speaks the fabric's wire shapes
exactly like any stage node — it is legal code, not broken glue.
"""

import fabric
import kv
import topology

HB = 4  # the foil's made-up suspicion timeout, in its own ticks


def init(node_id, peers):
    return {"id": node_id, "peers": peers, "epoch": topology.INITIAL_EPOCH,
            "promoted": False, "applied": (), "store": {}, "hints": (),
            "applied_count": 0, "notices": (), "beats": 0}


def _absorb(state, key, version):
    store = dict(state["store"])
    versions = list(store.get(key, ()))
    if version not in versions:
        versions.append(version)
    store[key] = tuple(versions)
    return dict(state, store=store)


def _local_best(versions):
    if not versions:
        return None
    return max(versions, key=lambda v: (v[2], v[1]))


def recv(state, message):
    kind = message[0]
    if kind in ("dead", "alive"):
        # the foil does not build health from notices — it counts silence.
        return state, ()
    if kind == "sync":
        # ("sync", target, sender, key, version, client, rid)
        return _absorb(state, message[3], message[4]), ()
    # relay/hint/propose/adopt: the foil speaks none of them.
    return state, ()


def tick(state):
    beats = state["beats"] + 1
    promoted, epoch = state["promoted"], state["epoch"]
    if not promoted and beats >= HB:
        promoted, epoch = True, epoch + 1
    return dict(state, beats=beats, promoted=promoted, epoch=epoch), ()


def client(state, command):
    op, key, value, client_id, rid = fabric.parse_command(command)
    if op == "set":
        versions = state["store"].get(key, ())
        clock = {}
        for v in versions:
            for node, counter in v[2]:
                clock[node] = max(clock.get(node, 0), counter)
        version = kv.version(value, kv.bump(tuple(sorted(clock.items())),
                                            state["id"]))
        state = _absorb(state, key, version)
        # NO LEDGER: applied unconditionally, even for a seen (client, rid).
        state = dict(state,
                     applied=state["applied"] + ((client_id, rid, key),),
                     applied_count=state["applied_count"] + 1)
        msgs = tuple(fabric.message("sync", p, state["id"], key, version,
                                    client_id, rid)
                     for p in state["peers"])
        return state, msgs, ("applied",)
    best = _local_best(state["store"].get(key, ()))
    answers = (best[1],) if best is not None else ()
    return state, (), ("ok", answers)
