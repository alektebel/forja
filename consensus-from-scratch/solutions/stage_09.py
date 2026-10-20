"""Consensus From Scratch — stage 9: The membership change: one at a time.

A replicated log's safety rests on two majorities always overlapping —
but that holds only while every voter shares ONE config. Swap the
membership in one step and the cluster splits into an old-majority and a
new-majority that can each commit a different log. Joint consensus fixes
this: for one entry's lifetime the cluster is BOTH configs, and the vote
count that commits is measured so no side can be missed.

DESIGN DECISION — why is the change itself a log command
(`members:a,b,c`) rather than a message kind?
Because a membership takes effect at a point in the log, and only a
replicated, committed entry has a point in the log. `wire` has no
membership kind on purpose: a message would take effect when it ARRIVES,
differently on each node, and two nodes could hold different majorities
about the same commit. `begin_change` appends through the same numbering
`client_submit` uses — index `log_start + len(log)`, the leader's term —
so it replicates like any write and everyone agrees on WHEN before
anyone acts on WHAT. The log entry is therefore the stage's only record
of the new set: `config` carries the union (what the replication and
commit loops must iterate during the window) and `old_config` marks the
window open, so the new set is read back from the last `members:` entry.

DESIGN DECISION — why `wire.majority(len(old)) +
wire.majority(len(new))` and not "a majority of each, checked as sets"?
Because the stage must answer with one int. The two sets are disjoint by
construction, so a count that reaches the SUM cannot have missed a side:
`majority(3) + majority(2) = 4` votes means at least 2 of the old 3 and
at least 2 of the new 2 answered. Anything looser (say the union's own
majority) lets one config commit alone; anything set-shaped at the call
sites would put quorum arithmetic outside `wire.majority`, the course's
only quorum function. When `old_config` is None the answer is simply
`wire.majority(len(config))` — the window is closed and there is one
config again.

DESIGN DECISION — why may `finish_change` drop the old config only once
the joint entry is committed AND a new-only majority holds it?
Because the moment a new-only majority has the joint entry, every future
commit needs that majority, and an old node that disagrees is simply
outside the cluster from that index onward. Dropping `old_config` earlier
would hand the old side a club to overwrite committed entries. When the
new set no longer contains the leader's own id, the cluster reformed
without it: `finish_change` stops the leadership and rebuilds through
`wire.follower` — a departed node cannot lead a config it is not in. A
leader that is still in the config swaps `config` to the new set, clears
`old_config`, and prunes `matched`/`next_index` to the surviving voters;
rows for departed peers would mislead the next leader's arithmetic.

DESIGN DECISION — why refuse an empty new config, an unknown id, a
duplicate, a nested window, and a `finish_change` outside a window?
Each is the split-brain in a different coat: an empty config has no
majority; an unknown id has no row in `wire.TIMEOUTS` so no node can ever
hold its state; a duplicate inflates one voter's weight; a second window
inside the first means two changes whose order nobody can agree on; and
finishing without beginning is a direct swap. All raise
`wire.ProtocolError` naming the offender before anything is appended.
"""

import wire

_MEMBERS = "members:"


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


def _joint_entry(state):
    """The latest `members:` entry the log still carries: (index,
    command), or None — the log is the change's record."""
    for index, _term, command in reversed(state["log"]):
        if command.startswith(_MEMBERS):
            return (index, command)
    return None


def _peers_of(command):
    return tuple(command[len(_MEMBERS):].split(","))


def _check_new(new_peers):
    if not isinstance(new_peers, tuple) or not new_peers:
        raise wire.ProtocolError("stage_09: a new config is a non-empty "
                                 "tuple of node ids, got %r" % (new_peers,))
    known = frozenset(node for node, _timeout in wire.TIMEOUTS)
    for member in new_peers:
        if not isinstance(member, str) or not member:
            raise wire.ProtocolError("stage_09: a member id must be a "
                                     "non-empty string, got %r" % (member,))
        if member not in known:
            raise wire.ProtocolError("stage_09: unknown member %r has no "
                                     "row in the world's TIMEOUTS table"
                                     % (member,))
    if len(set(new_peers)) != len(new_peers):
        raise wire.ProtocolError("stage_09: the new config repeats a "
                                 "member: %r" % (new_peers,))


def begin_change(leader, new_peers):
    """Enter the joint window: append the members command, the live config
    becomes the union, old_config keeps the old one: (leader2, entry)."""
    if leader["role"] != "leader":
        raise wire.ProtocolError("stage_09: begin_change expects a leader, "
                                 "got role %r" % (leader["role"],))
    if leader["old_config"] is not None:
        raise wire.ProtocolError("stage_09: a change is already joint under "
                                 "old_config %r — one window at a time"
                                 % (leader["old_config"],))
    _check_new(new_peers)
    old = leader["config"]
    union = tuple(sorted(set(old) | set(new_peers)))
    index = wire.log_start(leader["log"]) + len(leader["log"])
    entry = (index, leader["term"], _MEMBERS + ",".join(sorted(new_peers)))
    matched = dict(leader["matched"])
    next_index = dict(leader["next_index"])
    for peer in union:
        if peer != leader["id"] and peer not in next_index:
            # A voter the leader never tracked: probe it from the tail, as
            # a fresh leader probes every peer at the start of its term.
            matched[peer] = -1
            next_index[peer] = index + 1
    s = dict(leader)
    s["log"] = s["log"] + (entry,)
    s["config"] = union
    s["old_config"] = old
    s["matched"] = matched
    s["next_index"] = next_index
    return _rebuild(s), entry


def quorum(state):
    """Votes a proposal needs: the sum of both majorities while the window
    is joint, the single config's majority otherwise. An int."""
    if not isinstance(state, dict) or "config" not in state:
        raise wire.ProtocolError("stage_09: quorum expects a built state, "
                                 "got %r" % (state,))
    old = state.get("old_config")
    if old is None:
        return wire.majority(len(state["config"]))
    joint = _joint_entry(state)
    if joint is None:
        raise wire.ProtocolError("stage_09: quorum cannot count the new "
                                 "config — no members entry in the log to "
                                 "read it from")
    return wire.majority(len(old)) + wire.majority(len(_peers_of(joint[1])))


def finish_change(leader):
    """Leave the joint window once its entry is committed and a majority
    of the new config holds it: config becomes the new set, old_config
    None. A leader the new set excludes stops leading: follower2."""
    if leader["role"] != "leader":
        raise wire.ProtocolError("stage_09: finish_change expects a leader, "
                                 "got role %r" % (leader["role"],))
    if leader["old_config"] is None:
        raise wire.ProtocolError("stage_09: finish_change outside a joint "
                                 "window (old_config None) — the change "
                                 "skipped begin_change")
    joint = _joint_entry(leader)
    index = -1 if joint is None else joint[0]
    if joint is None or index > leader["commit_index"]:
        # The window stays open until the entry itself is committed:
        # returning the leader unchanged is the honest "not yet".
        return _rebuild(dict(leader))
    new = _peers_of(joint[1])
    votes = (1 if leader["id"] in new else 0) + sum(
        1 for peer in new
        if peer != leader["id"]
        and leader["matched"].get(peer, -1) >= index)
    if votes < wire.majority(len(new)):
        # Committed, but not yet held by a majority of the new config.
        return _rebuild(dict(leader))
    if leader["id"] not in new:
        # The cluster reformed without this node: it cannot lead it.
        return wire.follower(leader["id"], term=leader["term"],
                             log=leader["log"],
                             commit_index=leader["commit_index"],
                             config=new, elapsed=leader["elapsed"],
                             snapshot_at=leader["snapshot_at"])
    s = dict(leader)
    s["config"] = new
    s["old_config"] = None
    s["matched"] = dict((peer, at) for peer, at in s["matched"].items()
                        if peer in new)
    s["next_index"] = dict((peer, at) for peer, at
                           in s["next_index"].items() if peer in new)
    return _rebuild(s)
