"""Consensus From Scratch — stage 3: The heartbeats: leadership is exercised,
not claimed.

A leader holds power by talking: `become_leader` converts the candidate
that won a majority into a state that carries each peer's `matched` and
`next_index`; `heartbeat` asks every peer to confirm the leader's term
with nothing to replicate; `observe_append` is the receiver's side — the
term law, then the prev check; `observe_reply` is the leader reading what
came back. Leadership that stops exercising is leadership that ends: the
followers' timeouts are the proof.

DESIGN DECISION — why does `become_leader` start every peer's
`next_index` one past the leader's own last entry instead of `0`?
Because the leader is the authority on the log: the safest first guess is
"you already have what I have, prove it at the boundary". A rejection
(stage 4's conflict reply) walks it back deterministically; starting at 0
would rescan a whole replicated log of matched entries on every election —
correct but quadratic. With a snapshot boundary the one-past-last entry is
`wire.log_start(log) + len(log)`; the prev term at `next_index - 1` comes
from the tail, from `snapshot_at` at the boundary, or is 0 when the node
has no history at all.

DESIGN DECISION — why is an empty entry list a heartbeat rather than a
separate message kind?
Because `wire` has exactly six kinds and no HEARTBEAT message: a zero-entry
APPEND is a heartbeat — it carries the term and prev check and nothing
else, which is precisely what "I am still your leader, confirm" means.
Adding a kind would double the receiver's term law for no new semantics.

DESIGN DECISION — why does `observe_append` reset the receiver's election
timer while `observe_reply` may step the leader down?
Because the direction is the relationship: an accepted APPEND at the
leader's term is proof of life from a majority-backed node, so the timer
that would start a contest restarts. A reply bearing a HIGHER term than
the leader's is proof the contest already ended elsewhere — the leader
downgrades (role follower, term adopted), never argues. An equal-term
denial is neither; it only says "your entries don't match my log", which
is stage 4's business.

DESIGN DECISION — why does the APPEND_REPLY carry the voter/leader fields
in positions the fabric routes on?
Because the drop-only network routes replies by content: a VOTE_REPLY
answers the candidate at field 3, an APPEND_REPLY answers the leader named
in field 5 or the peer whose APPEND the sender last accepted. The stage
builds replies with `wire.append_reply(term, node, matched, conflict,
leader=...)` and never hand-assembles tuples — the grammar is the world's
and the routing depends on it.
"""

import wire


def _boundary_term(s):
    """The term claimed for the slot just below the tail: the snapshot
    boundary's term, or 0 for a node with no history at all."""
    if s["snapshot_at"] is not None:
        return s["snapshot_at"][1]
    return 0


def _rebuild(s):
    """Rebuild `s` through the builder matching its role — states are
    values, and the builders are the only legitimate way to make one."""
    if s["role"] == "leader":
        return wire.leader(s["id"], s["term"], log=s["log"],
                           commit_index=s["commit_index"],
                           config=s["config"], matched=s["matched"],
                           next_index=s["next_index"], elapsed=s["elapsed"],
                           snapshot_at=s["snapshot_at"],
                           old_config=s["old_config"])
    if s["role"] == "candidate":
        return wire.candidate(s["id"], s["term"], voted_for=s["voted_for"],
                              log=s["log"], commit_index=s["commit_index"],
                              config=s["config"], elapsed=s["elapsed"],
                              votes=s["votes"],
                              snapshot_at=s["snapshot_at"])
    return wire.follower(s["id"], s["term"], voted_for=s["voted_for"],
                         log=s["log"], commit_index=s["commit_index"],
                         config=s["config"], elapsed=s["elapsed"],
                         snapshot_at=s["snapshot_at"])


def _refusal(s, sender):
    """The deny reply: 'my log ends here; walk back to or before it.'"""
    mine = wire.last_entry(s)[0]
    return wire.append_reply(s["term"], s["id"], mine, mine + 1,
                             leader=sender)


def become_leader(candidate):
    """The won election becomes the state: empty matched map, every peer's
    next_index one past the last entry (or the snapshot boundary), commit
    unchanged."""
    if candidate["role"] != "candidate":
        raise wire.ProtocolError("stage_03: become_leader expects a "
                                 "candidate, got role %r"
                                 % (candidate["role"],))
    tail = wire.log_start(candidate["log"]) + len(candidate["log"])
    matched = {}
    next_index = {}
    for peer in candidate["config"]:
        if peer == candidate["id"]:
            continue
        matched[peer] = -1
        next_index[peer] = tail
    return wire.leader(candidate["id"], candidate["term"],
                       log=candidate["log"],
                       commit_index=candidate["commit_index"],
                       config=candidate["config"], matched=matched,
                       next_index=next_index, elapsed=0,
                       snapshot_at=candidate["snapshot_at"])


def heartbeat(leader):
    """One empty-payload `wire.append` per peer: term, prev at each
    peer's next_index, leader_commit, nothing to replicate."""
    if leader["role"] != "leader":
        raise wire.ProtocolError("stage_03: heartbeat expects a leader, "
                                 "got role %r" % (leader["role"],))
    start = wire.log_start(leader["log"])
    tail = start + len(leader["log"])
    out = []
    for peer in leader["config"]:
        if peer == leader["id"]:
            continue
        nxt = leader["next_index"].get(peer, tail)
        prev_index = nxt - 1
        if prev_index >= start:
            prev_term = leader["log"][prev_index - start][1]
        else:
            prev_term = _boundary_term(leader)
        out.append(wire.append(leader["term"], leader["id"], prev_term,
                               prev_index, (), leader["commit_index"]))
    return tuple(out)


def observe_append(follower, msg):
    """The receiver's side of an APPEND: term law, prev check, and the
    reply: (reply, follower2). Only heartbeats (empty payloads) are
    received here; stage 4 owns entry installation."""
    if wire.kind(msg) != wire.APPEND or len(msg) != 7:
        raise wire.ProtocolError("stage_03: observe_append needs an "
                                 "append, got %r" % (msg,))
    term, sender, prev_term, prev_index, entries, leader_commit = (
        msg[1], msg[2], msg[3], msg[4], msg[5], msg[6])
    # Revalidate through the grammar; a hand-built tuple is refused.
    wire.append(term, sender, prev_term, prev_index, entries, leader_commit)
    if entries:
        raise wire.ProtocolError("stage_03: observe_append receives "
                                 "heartbeats; stage 4 installs entries")
    s = dict(follower)
    if term > s["term"]:
        # The term law ends every claim the old term had — role included.
        s["term"] = term
        s["role"] = "follower"
        s["voted_for"] = None
    if term < follower["term"] or (s["role"] == "leader"
                                   and sender != s["id"]):
        # A stale sender, or a rival in our own term: refuse at our term.
        return _refusal(s, sender), _rebuild(s)
    if s["role"] != "follower":
        s["role"] = "follower"  # a candidate stands down to a real leader
    s["elapsed"] = 0  # proof of life from a majority-backed node
    if s["voted_for"] is None:
        s["voted_for"] = sender
    start = wire.log_start(s["log"])
    if prev_index < start - 1 or prev_index >= start + len(s["log"]):
        # The claimed anchor is not inside this node's window.
        return _refusal(s, sender), _rebuild(s)
    if prev_index >= start and s["log"][prev_index - start][1] != prev_term:
        # The pair disagrees with our history; stage 4 truncates, we deny.
        return _refusal(s, sender), _rebuild(s)
    # accepted heartbeat: the commit line may settle, clamped to the tail
    last_index = wire.last_entry(s)[0]
    if leader_commit > s["commit_index"]:
        s["commit_index"] = min(leader_commit, last_index)
    reply = wire.append_reply(s["term"], s["id"], last_index,
                              last_index + 1, leader=sender)
    return reply, _rebuild(s)


def observe_reply(leader, reply):
    """The leader reading one APPEND_REPLY: records matched/conflict and
    steps down on a higher term: leader2."""
    if leader["role"] != "leader":
        raise wire.ProtocolError("stage_03: observe_reply expects a "
                                 "leader, got role %r" % (leader["role"],))
    if wire.kind(reply) != wire.APPEND_REPLY or len(reply) not in (5, 6):
        raise wire.ProtocolError("stage_03: observe_reply needs an "
                                 "append_reply, got %r" % (reply,))
    sender_leader = reply[5] if len(reply) == 6 else None
    wire.append_reply(reply[1], reply[2], reply[3], reply[4],
                      leader=sender_leader)
    term, node, matched, conflict = reply[1], reply[2], reply[3], reply[4]
    if term > leader["term"]:
        # The contest already ended elsewhere: downgrade, never argue.
        s = dict(leader)
        return wire.follower(s["id"], term, voted_for=s["voted_for"],
                             log=s["log"], commit_index=s["commit_index"],
                             config=s["config"], elapsed=0,
                             snapshot_at=s["snapshot_at"])
    if term < leader["term"] or node not in leader["matched"]:
        return _rebuild(dict(leader))  # stale, or not a peer of this config
    s = wire.leader(leader["id"], leader["term"], log=leader["log"],
                    commit_index=leader["commit_index"],
                    config=leader["config"],
                    matched=dict(leader["matched"]),
                    next_index=dict(leader["next_index"]),
                    elapsed=leader["elapsed"],
                    snapshot_at=leader["snapshot_at"],
                    old_config=leader["old_config"])
    s["matched"][node] = matched
    s["next_index"][node] = conflict
    return s
