"""Consensus From Scratch — stage 4: Replication: the entries match term by
term.

`client_submit` is where a command becomes a log entry — the leader
appends `(index, term, command)` and the entry exists for the cluster the
moment it exists on the leader. `broadcast_append` sends each peer its
tail from that peer's `next_index`. `handle_append` is where a follower's
log and the leader's are reconciled: the prev check passes and the tail
is installed — overwriting anything the old leader left behind.

DESIGN DECISION — why does the leader append locally BEFORE broadcasting?
Because the replicated state machine needs an order, and the order is the
index: append at `last_index + 1` with the leader's term, then let the
log spread. A leader that waited for replication to decide the index
would have two candidates for the next slot and no way to pick — the same
double-commit the foil shows when its election law rots. The local append
is also why `client_submit` answers `(None,)` to the fabric: the write is
OPEN, not done — completion belongs to the commit (stage 5), and the
fabric records both ends honestly.

DESIGN DECISION — why does the prev check compare BOTH prev_index and
prev_term, and why does a mismatch truncate by term?
Because matching an index without matching its term would let two
different histories share a slot number — the exact safety violation the
`conflicts` recorder watches for. When the pair disagrees, the follower
drops its own suffix from the first entry with the leader's prev_term,
keeps everything before it, and answers `matched` at the last kept index,
`conflict` one past it: the leader then walks that peer's `next_index`
back and the two logs converge in at most one retry per conflicting term,
deterministically, with no log scanning beyond the boundary.

DESIGN DECISION — why is an entry at the same index with a DIFFERENT term
simply overwritten, no refusal?
Because the leader of the current term is the single authority on the
log: whatever a stale leader wrote at that slot lost its election the
moment a majority backed this term, and a follower still holding it is
behind, not in conflict. The prev check makes this safe: the leader can
only ever overwrite entries AFTER a point both logs agree on. Duplicates
at the boundary are ignored (the slot already matches), which keeps
retransmits free.

DESIGN DECISION — why does the follower clamp `commit_index` to its new
last index after installing?
Because a committed entry is, by the safety theorem, never missing from a
current-term leader's log — but the fabric lets a STALE leader's APPEND
arrive at a follower whose commit line runs past that leader's log. A
correct node never produces the situation (its term laws refuse the stale
leader); a node that does clamp is the foil, and the clamp is what makes
its divergence observable as a stale read instead of a ProtocolError. The
stage's `handle_append` takes the clamp — defensive, deterministic,
never wrong when the protocol is right.
"""

import wire


def _refusal(s, sender):
    """The deny reply: 'my log ends here; walk back to or before it.'"""
    mine = wire.last_entry(s)[0]
    return wire.append_reply(s["term"], s["id"], mine, mine + 1,
                             leader=sender)


def _rebuild(s):
    """Rebuild through the role's builder — the builders are the law."""
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


def _known_members(members):
    known = frozenset(node for node, _timeout in wire.TIMEOUTS)
    for member in members:
        if member not in known:
            raise wire.ProtocolError("stage_04: unknown member %r"
                                     % (member,))


def client_submit(leader, command):
    """A command becomes an entry: (leader2, messages). Never a `get` —
    reads answer from the committed state, they do not replicate."""
    if leader["role"] != "leader":
        raise wire.ProtocolError("stage_04: client_submit expects a "
                                 "leader, got role %r" % (leader["role"],))
    if not isinstance(command, str) or not command:
        raise wire.ProtocolError("stage_04: a command is a non-empty "
                                 "string, got %r" % (command,))
    if command.startswith("get "):
        raise wire.ProtocolError("stage_04: 'get' is a read, not a "
                                 "command to replicate: %r" % (command,))
    if command.startswith("members:"):
        _known_members(tuple(command[len("members:"):].split(",")))
    # The order is the index: append at last+1 with the leader's term,
    # snapshot-relative so a trimmed log still numbers itself correctly.
    index = wire.log_start(leader["log"]) + len(leader["log"])
    s = dict(leader)
    s["log"] = s["log"] + ((index, s["term"], command),)
    leader2 = _rebuild(s)
    return leader2, broadcast_append(leader2)


def broadcast_append(leader):
    """Each peer's tail from its next_index: the appends, one per peer."""
    if leader["role"] != "leader":
        raise wire.ProtocolError("stage_04: broadcast_append expects a "
                                 "leader, got role %r" % (leader["role"],))
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
        elif leader["snapshot_at"] is not None:
            prev_term = leader["snapshot_at"][1]
        else:
            prev_term = 0
        entries = tuple(leader["log"][nxt - start:])
        out.append(wire.append(leader["term"], leader["id"], prev_term,
                               prev_index, entries,
                               leader["commit_index"]))
    return tuple(out)


def handle_append(follower, msg):
    """Reconcile a follower's log with the leader's: prev check, install
    the tail, truncate by term on mismatch, clamp the commit line: (reply,
    follower2)."""
    if wire.kind(msg) != wire.APPEND or len(msg) != 7:
        raise wire.ProtocolError("stage_04: handle_append needs an "
                                 "append, got %r" % (msg,))
    term, sender, prev_term, prev_index, entries, leader_commit = (
        msg[1], msg[2], msg[3], msg[4], msg[5], msg[6])
    # Revalidate through the grammar; a hand-built tuple is refused.
    wire.append(term, sender, prev_term, prev_index, entries, leader_commit)
    s = dict(follower)
    if term > s["term"]:
        # The term law ends every claim the old term had — role included.
        s["term"] = term
        s["role"] = "follower"
        s["voted_for"] = None
    if term < follower["term"] or (s["role"] == "leader"
                                   and sender != s["id"]):
        # Stale sender or a rival in our own term: refuse, keep our state.
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
        # The pair disagrees: drop the suffix from the first entry that
        # carries the leader's claimed prev_term — one retry per
        # conflicting term, deterministically.
        cut = prev_index
        while cut > start and s["log"][cut - 1][1] == prev_term:
            cut -= 1
        s["log"] = s["log"][:cut - start]
        if s["commit_index"] >= cut:
            s["commit_index"] = cut - 1
        return _refusal(s, sender), _rebuild(s)
    # consistent: install the tail (overwriting anything after the anchor)
    keep = prev_index + 1 - start
    s["log"] = s["log"][:keep] + tuple(entries)
    last_index = wire.last_entry(s)[0]
    if leader_commit > s["commit_index"]:
        # Never trust a commit line past what we actually hold.
        s["commit_index"] = min(leader_commit, last_index)
    reply = wire.append_reply(s["term"], s["id"], last_index,
                              last_index + 1, leader=sender)
    return reply, _rebuild(s)
