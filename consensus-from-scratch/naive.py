"""naive.py — the foil: a plausible, simple, WRONG node (provided world).

Every node in the cluster runs this module; every rule it enforces is a
rule a beginner would write. It replicates with a real quorum commit, it
paces heartbeats, it steps down on higher terms. Its one shortcut is the
one that breaks Raft: **a request for a vote is a compliment — everyone
grants it.** `voted_for` is never latched and the candidate's log is
never compared, so in a partition that intersects only through a bridge
node, the bridge grants BOTH candidates the same term's vote and the
world gets two leaders that each command a majority. Each leader commits
its own entry into the same slot; committed data is lost.

The correct protocol refuses one of those two grants — either the latch
(I already stand with a4 this term) or the log restriction (this
candidate cannot carry what I have committed). This file is the reason
those two lines exist; stage 1's check drives it in the ASYMMETRIC
scenario and shows slot 0 committed twice with different commands.

Shapes match the stage ladder exactly: init/recv/tick/client plus
persist/recover, same state keys, same wire grammar — the flaws are in
the RULES, so a student diffing naive against a correct node finds
exactly the election restriction.
"""

import wire
from sim import timeout


def _values(state):
    values = {}
    members = None
    start = wire.log_start(state["log"])
    for entry in state["log"][:state["commit_index"] - start + 1]:
        command = entry[2]
        if command.startswith("members:"):
            members = tuple(command[len("members:"):].split(","))
        elif "=" in command:
            key, value = command.split("=", 1)
            values[key] = value
    return values, members


def _note_commit(s):
    values, members = _values(s)
    if members is not None and members != s["config"]:
        s["config"] = members
    return s


def init(node_id, peers):
    return wire.follower(node_id, config=tuple(peers))


def _become_candidate(s):
    last_index, last_term = wire.last_entry(s)
    message = wire.request_vote(s["term"] + 1, s["id"], last_term,
                                last_index)
    return wire.candidate(s["id"], s["term"] + 1, log=s["log"],
                          commit_index=s["commit_index"], config=s["config"],
                          elapsed=0, votes=(s["id"],),
                          snapshot_at=s["snapshot_at"]), (message,)


def _become_leader(s):
    matched = {}
    next_index = {}
    for peer in s["config"]:
        if peer == s["id"]:
            continue
        matched[peer] = -1
        next_index[peer] = len(s["log"])
    return wire.leader(s["id"], s["term"], log=s["log"],
                       commit_index=s["commit_index"], config=s["config"],
                       matched=matched, next_index=next_index, elapsed=0,
                       snapshot_at=s["snapshot_at"])


def _send_appends(s):
    out = []
    start = wire.log_start(s["log"])
    for peer in s["config"]:
        if peer == s["id"]:
            continue
        nxt = s["next_index"].get(peer, start + len(s["log"]))
        prev_index = nxt - 1
        if prev_index >= start:
            prev_term = s["log"][prev_index - start][1]
        elif s["snapshot_at"] is not None:
            prev_term = s["snapshot_at"][1]
        else:
            prev_term = 0
        entries = tuple(s["log"][nxt:])
        out.append(wire.append(s["term"], s["id"], prev_term, prev_index,
                               entries, s["commit_index"]))
    return tuple(out)


def _update_match(s, reply):
    s = dict(s)
    s["matched"] = dict(s["matched"])
    s["next_index"] = dict(s["next_index"])
    node = reply[2]
    if node in s["matched"]:
        s["matched"][node] = reply[3]
        s["next_index"][node] = reply[4]
    return s


def _advance_commit(s):
    s = dict(s)
    needed = wire.majority(len(s["config"]))
    new_ci = s["commit_index"]
    start = wire.log_start(s["log"])
    for index in range(max(new_ci + 1, start), len(s["log"])):
        entry = s["log"][index]
        if entry[1] != s["term"]:
            continue
        votes = 1 + sum(1 for peer in s["config"]
                        if peer != s["id"]
                        and s["matched"].get(peer, -1) >= index)
        if votes >= needed:
            new_ci = index
        else:
            break
    if new_ci != s["commit_index"]:
        s["commit_index"] = new_ci
        _note_commit(s)
    return s


def _step_down(s, term):
    s = dict(s)
    s["role"] = "follower"
    s["term"] = term
    s["elapsed"] = 0
    return s


def recv(state, message):
    kind = message[0]
    s = dict(state)

    if kind == wire.REQUEST_VOTE:
        _term, cand, last_term, last_index = message[1], message[2], \
            message[3], message[4]
        # THE FLAW, in one shape: any request at our term or above wins
        # our vote. No `voted_for` latch, no comparison of logs. A term
        # above ours also steps us down, as it should.
        if _term > s["term"]:
            s = _step_down(s, _term)
        granted = _term >= s["term"]
        return s, (wire.vote_reply(s["term"], s["id"], cand, granted),)

    if kind == wire.VOTE_REPLY:
        if s["role"] != "candidate":
            return s, ()
        _term, node, cand, granted = message[1], message[2], message[3], \
            message[4]
        if _term != s["term"] or cand != s["id"] or not granted:
            if _term > s["term"]:
                s = _step_down(s, _term)
            return s, ()
        votes = tuple(sorted(set(s.get("votes", ()) + (node,))))
        s = wire.candidate(s["id"], s["term"], voted_for=s["voted_for"],
                           log=s["log"], commit_index=s["commit_index"],
                           config=s["config"], elapsed=s["elapsed"],
                           votes=votes, snapshot_at=s["snapshot_at"])
        if wire.majority(len(s["config"])) <= len(votes):
            s = _become_leader(s)
            return s, _send_appends(s)
        return s, ()

    if kind == wire.APPEND:
        _term, sender, prev_term, prev_index, entries, leader_commit = \
            message[1], message[2], message[3], message[4], message[5], \
            message[6]
        if _term > s["term"]:
            s = _step_down(s, _term)
        if _term < s["term"] or (s["role"] == "leader" and
                                 sender != s["id"]):
            # Same term, another leader: answer false; never serve two
            # masters. Stepping down on an EQUAL term would erase the
            # split vote that makes the foil diverge.
            mine = wire.last_entry(s)[0]
            return s, (wire.append_reply(s["term"], s["id"], mine,
                                         mine + 1, leader=sender),)
        if s["role"] != "follower":
            s = _step_down(s, _term)
        s["elapsed"] = 0
        start = wire.log_start(s["log"])
        if prev_index < start - 1 or prev_index >= start + len(s["log"]):
            mine = wire.last_entry(s)[0]
            return s, (wire.append_reply(s["term"], s["id"], mine,
                                         mine + 1, leader=sender),)
        if prev_index >= start and s["log"][prev_index - start][1] != \
                prev_term:
            cut = prev_index
            while cut > start and s["log"][cut - 1][1] == prev_term:
                cut -= 1
            s["log"] = s["log"][:cut - start]
            if s["commit_index"] >= cut:
                s["commit_index"] = cut - 1
            mine = wire.last_entry(s)[0]
            return s, (wire.append_reply(s["term"], s["id"], mine,
                                         mine + 1, leader=sender),)
        keep = prev_index + 1 - start
        s["log"] = s["log"][:keep] + tuple(entries)
        last_index = wire.last_entry(s)[0]
        if s["commit_index"] > last_index:
            # a stale leader rewrote the tail past our commit line: the
            # entry is gone whether or not the protocol noticed. (The
            # correct one never sees this; the foil's election flaw does.)
            s["commit_index"] = last_index
        if leader_commit > s["commit_index"]:
            s["commit_index"] = min(leader_commit, last_index)
            _note_commit(s)
        return s, (wire.append_reply(s["term"], s["id"], last_index,
                                     last_index + 1, leader=sender),)

    if kind == wire.APPEND_REPLY:
        if s["role"] != "leader":
            return s, ()
        if message[1] != s["term"]:
            if message[1] > s["term"]:
                s = _step_down(s, message[1])
            return s, ()
        s = _update_match(s, message)
        s = _advance_commit(s)
        return s, ()

    raise wire.ProtocolError("naive: cannot receive %r" % (message,))


def tick(state):
    s = dict(state)
    s["elapsed"] = s["elapsed"] + 1
    if s["role"] == "leader":
        if s["elapsed"] >= wire.HEARTBEAT:
            s = dict(s)
            s["elapsed"] = 0
            return s, _send_appends(s)
        return s, ()
    if s["elapsed"] >= timeout(s["id"]):
        return _become_candidate(s)
    return s, ()


def client(state, command):
    s = state
    if s["role"] != "leader":
        return s, (), ("not_leader", "")
    if command.startswith("get "):
        values, _ = _values(s)
        return s, (), ("read", values.get(command[4:], ""))
    entry = (len(s["log"]), s["term"], command)
    s = dict(s)
    s["log"] = s["log"] + (entry,)
    s = _advance_commit(s)
    return s, _send_appends(s), (None,)


def persist(state):
    parts = ["v1", state["id"], str(state["term"]),
             state["voted_for"] if state["voted_for"] else "-",
             str(state["commit_index"]),
             ",".join(state["config"])]
    snap = state["snapshot_at"]
    parts.append("-" if snap is None else "%d:%d" % (snap[0], snap[1]))
    for index, term, command in state["log"]:
        parts.append("%d;%d;%s" % (index, term, command))
    return "\n".join(parts).encode("utf-8")


def _entry(part):
    index_s, term_s, command = part.split(";", 2)
    return (int(index_s), int(term_s), command)


def recover(saved):
    lines = saved.decode("utf-8").split("\n")
    if not lines or lines[0] != "v1":
        raise wire.ProtocolError("naive.recover: not a naive image")
    node_id = lines[1]
    term = int(lines[2])
    voted_for = None if lines[3] == "-" else lines[3]
    commit_index = int(lines[4])
    config = tuple(lines[5].split(","))
    snapshot_at = None if lines[6] == "-" else tuple(
        int(x) for x in lines[6].split(":"))
    log = tuple(_entry(p) for p in lines[7:])
    return wire.follower(node_id, term=term, voted_for=voted_for, log=log,
                         commit_index=commit_index, config=config,
                         snapshot_at=snapshot_at)
