"""Consensus From Scratch — stage 8: The snapshot: commit without losing a
committed entry.

A replicated log cannot grow forever: a node that joins late, or a
follower that fell so far behind its prev_index is below what the leader
still holds, needs the state itself, not the history of how it was built.
`build_snapshot` compacts the leader's committed prefix into a
`wire.snapshot` message and drops those entries from the tail;
`install_snapshot` is the receiver's side — replace the log, adopt the
boundary, resume replication from there.

DESIGN DECISION — why may a snapshot drop only COMMITTED entries, and
never move the boundary past `commit_index`?
Because the snapshot's promise is "these commands are in every surviving
future state machine" — the only way to keep that promise is to compact
below the commit line. A snapshot of an uncommitted prefix would install
a state the cluster might still roll back (the entry could be overwritten
by a newer term), and `conflicts` would record two commands for slots the
leader deleted. `build_snapshot` refuses an `upto_index` above
`commit_index` with a `wire.ProtocolError` naming both numbers; the
boundary moves to `(upto, entry's term)`, and `commit_index` rides with
it.

DESIGN DECISION — why is the snapshot message's payload the committed
commands, not the state machine's values?
Because the state machine is the application's business (the fabric's
`history.linearizable` judge replays commands, not values). A snapshot in
this course is `wire.snapshot(term, sender, last_included_term,
last_included_index, entries)` where `entries` are the very
`(index, term, command)` triples being compacted — so a receiver can
verify the boundary pair matches its replay and can re-apply with its own
rules. The receiver's `snapshot_at = (last_included_index,
last_included_term)` makes `wire.last_entry` answer the boundary when the
tail is empty, which is exactly what stage 1's up-to-date law needs to
keep snapshotted nodes electable.

DESIGN DECISION — why does install refuse a snapshot that does not beat
the follower's own boundary?
Because installing an older snapshot over a longer log is data loss with
extra steps. The rule mirrors stage 1: compare `(index, term)` against
`wire.last_entry` — install when it is strictly ahead of what the
follower has and when nothing in the follower's tail contradicts it. On
install the follower's log becomes the payload, its commit line lands at
the boundary, and the next APPEND's prev check runs against the new
boundary — replication resumes without the leader noticing which peers
compacted.
"""

import wire


def _rebuild(s):
    """Rebuild through the role's builder — the builders are the law."""
    if s["role"] == "leader":
        return wire.leader(s["id"], s["term"], log=s["log"],
                           commit_index=s["commit_index"],
                           config=s["config"], matched=s["matched"],
                           next_index=s["next_index"],
                           elapsed=s["elapsed"],
                           snapshot_at=s["snapshot_at"],
                           old_config=s["old_config"])
    if s["role"] == "candidate":
        return wire.candidate(s["id"], s["term"], voted_for=s["voted_for"],
                              log=s["log"], commit_index=s["commit_index"],
                              config=s["config"], elapsed=s["elapsed"],
                              votes=s["votes"],
                              snapshot_at=s["snapshot_at"])
    return wire.follower(s["id"], term=s["term"], voted_for=s["voted_for"],
                         log=s["log"], commit_index=s["commit_index"],
                         config=s["config"], elapsed=s["elapsed"],
                         snapshot_at=s["snapshot_at"])


def build_snapshot(leader, upto_index):
    """The committed prefix as a message plus the leader past it:
    (snapshot_msg, leader2). Refuses `upto_index` above `commit_index`."""
    if leader["role"] != "leader":
        raise wire.ProtocolError("stage_08: build_snapshot expects a "
                                 "leader, got role %r" % (leader["role"],))
    if isinstance(upto_index, bool) or not isinstance(upto_index, int):
        raise wire.ProtocolError("stage_08: build_snapshot wants an int "
                                 "index, got %r" % (upto_index,))
    start = wire.log_start(leader["log"])
    last = wire.last_entry(leader)[0]
    if upto_index > leader["commit_index"]:
        raise wire.ProtocolError("stage_08: build_snapshot will not compact "
                                 "past the commit line: upto_index %d is "
                                 "above commit_index %d"
                                 % (upto_index, leader["commit_index"]))
    if upto_index < start or upto_index > last:
        raise wire.ProtocolError("stage_08: build_snapshot compacts entries "
                                 "this leader holds: upto_index %d is "
                                 "outside the tail %d..%d"
                                 % (upto_index, start, last))
    if (leader["snapshot_at"] is not None
            and upto_index <= leader["snapshot_at"][0]):
        raise wire.ProtocolError("stage_08: build_snapshot moves the "
                                 "boundary forward only: upto_index %d does "
                                 "not beat %d"
                                 % (upto_index, leader["snapshot_at"][0]))
    payload = leader["log"][:upto_index - start + 1]
    boundary = payload[-1]  # the (index, term, command) at upto_index
    msg = wire.snapshot(leader["term"], leader["id"], boundary[1],
                        boundary[0], payload)
    tail = leader["log"][upto_index + 1 - start:]
    leader2 = wire.leader(leader["id"], leader["term"], log=tail,
                          commit_index=leader["commit_index"],
                          config=leader["config"], matched=leader["matched"],
                          next_index=leader["next_index"],
                          elapsed=leader["elapsed"],
                          snapshot_at=(boundary[0], boundary[1]),
                          old_config=leader["old_config"])
    return msg, leader2


def install_snapshot(follower, msg):
    """The receiver's side: adopt a snapshot only when it beats what the
    follower holds: (reply, follower2)."""
    if not isinstance(msg, tuple) or not msg or msg[0] != wire.SNAPSHOT:
        raise wire.ProtocolError("stage_08: install_snapshot expects a "
                                 "SNAPSHOT message, got %r" % (msg,))
    if len(msg) != 6:
        raise wire.ProtocolError("stage_08: the snapshot is not the "
                                 "grammar: arity %d" % (len(msg),))
    _kind, term, sender, last_term, last_index, payload = msg
    try:
        wire.snapshot(term, sender, last_term, last_index, payload)
    except wire.ProtocolError as problem:
        raise wire.ProtocolError("stage_08: the snapshot is not the "
                                 "grammar: %s" % (problem,))
    if (not payload or payload[-1][0] != last_index
            or payload[-1][1] != last_term):
        raise wire.ProtocolError("stage_08: the snapshot's boundary pair "
                                 "must name its own last entry, got %r "
                                 "over %r" % ((last_index, last_term),
                                               payload[-1] if payload
                                               else payload))
    for slot, (index, _term, _command) in enumerate(payload):
        if index != payload[0][0] + slot:
            raise wire.ProtocolError("stage_08: the snapshot payload is "
                                     "not a contiguous log: slot %d holds "
                                     "index %d" % (slot, index))
    s = dict(follower)
    if term > s["term"]:
        # The term law ends every claim the old term had — role included.
        s["term"] = term
        s["role"] = "follower"
        s["voted_for"] = None
    if term < follower["term"] or (s["role"] == "leader"
                                   and sender != s["id"]):
        # Stale sender or a rival in our own term: refuse, keep our state.
        ours = wire.last_entry(s)
        return (wire.snapshot_reply(s["term"], s["id"], ours[0],
                                    leader=sender), _rebuild(s))
    if s["role"] != "follower":
        s["role"] = "follower"  # a candidate stands down to a real leader
    ours = wire.last_entry(s)
    boundary = (last_index, last_term)
    refuse = (boundary == ours
              or last_index < s["commit_index"]
              or not wire.at_least_as_up_to_date(boundary, ours))
    if not refuse:
        first = payload[0][0]
        for index, entry_term, command in s["log"]:
            if index > last_index:
                break
            if index < first:
                continue  # below the payload: folded into its state
            if payload[index - first] != (index, entry_term, command):
                refuse = True  # the payload rewrites remembered history
                break
    if refuse:
        # Not strictly ahead, or contradicting what we hold: refuse and
        # answer at our own end; the leader reconciles over APPEND.
        return (wire.snapshot_reply(s["term"], s["id"], ours[0],
                                    leader=sender), _rebuild(s))
    # Strictly ahead and contradicting nothing: the payload IS the state.
    s["log"] = payload
    s["commit_index"] = last_index
    s["snapshot_at"] = boundary
    s["elapsed"] = 0  # proof of life from a majority-backed node
    if s["voted_for"] is None:
        s["voted_for"] = sender
    reply = wire.snapshot_reply(s["term"], s["id"], last_index,
                                leader=sender)
    return reply, _rebuild(s)
