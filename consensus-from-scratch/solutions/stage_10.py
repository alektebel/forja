"""Consensus From Scratch — stage 10: The proof: one history, two verdicts.

Everything before this stage was a law stated; this stage is the law
tested. The full node protocol — `init`, `recv`, `tick`, `client`,
`persist`, `recover` — composed from stages 1–9, driven by `sim.Cluster`
through every scenario in `scenarios.py`, judged by `history.linearizable`
against the history the fabric itself recorded, and pinned against the
`PINS` table: the leaders, the first commits, the conflicts, the
verdicts — for a correct node, and for the foil.

DESIGN DECISION — why is the composed node a thin dispatcher?
Because every law it obeys already lives in an earlier stage and the
check for it already passed there: `grant_vote` (1), the election and its
tally (2), the won-election maps and the reply ledger (3), the append
reconciliation (4), the commit rule (5), the term door (6), the image and
the heal (7), the snapshot install (8), the membership reading (9). This
stage adds exactly three things no earlier stage could own: the FABRIC'S
routing shape (one election REQUEST_VOTE per beat — the driver fans a
REQUEST_VOTE, APPEND or SNAPSHOT out to every live peer itself, so
emitting one request per peer would deliver the grid twice over; the
per-peer APPEND is NOT fanned: replies route to `leader=`, so the leader
writes one message per peer), the state machine applied at the commit
line (`_values`, and the members command taking effect there), and the
verdict functions `prove`/`audit`. Composition, not reimagination.

DESIGN DECISION — why does `client` answer reads from the COMMITTED state
and never append a `get` to the log?
Because a read has no order to agree on: its value is whatever the state
machine holds at the instant the leader answers, and the fabric records
that value in the history. A `get` that became an entry would let a
majority commit a command that changes nothing and consume a slot — and a
leader that reads uncommitted entries would answer a value a newer term
can still overwrite: the stale read the foil answers under LAGGARD.
`("read", value)` / ("not_leader", hint) / (None,) for an accepted
write — those three answers are the whole client contract, and `sim`
refuses anything else.

DESIGN DECISION — why is a non-leader's `client` a refusal with a hint
rather than a forward?
Because the fabric has no directory and the protocol has no obligation to
invent one: `("not_leader", hint)` records an invocation that took no
effect anywhere, and `history` drops refused calls on exactly that law.
Forwarding through the cluster would add a routing protocol the course
never asked for; the hint is where the client (in this stage's scenarios,
the submit list itself) retries — and a retry closes the older open call
as a timeout, which the fabric also records honestly.

DESIGN DECISION — why does a leader send a SNAPSHOT instead of an APPEND
when a peer's next_index has fallen at or below the boundary?
Because past the boundary the leader no longer holds the entries the peer
must match against: the prev check can never pass, and the peer would
refuse forever. `stage_08.build_snapshot` at the commit line is the only
message that can land a follower behind the compaction. The leader sends
it WITHOUT compacting itself: trimming is optional, delivering the
boundary is not.

DESIGN DECISION — why does `prove(name)` return the run plus the pins
side by side instead of a bool?
Because a verdict without evidence is this course's foil: the check wants
to see WHICH leader was elected at WHICH tick and WHICH command landed at
slot 0, the same way `verify_provided` shows them. `("scenario", "result",
"pins", "linear")` — the stage compares its own run against the probe
column and asks the linearizer; the bool is `linear` AND equality, but
the tuple is the proof.

DESIGN DECISION — why must `audit` RUN the foil through the fabric rather
than read `PINS` and trust it?
Because `PINS` is the world's claim and the audit is the stage's proof:
a stage that reports the foil behaving correctly has either edited the
world (digest check catches that) or is not driving it at all. The audit
instantiates `sim.Cluster(naive, scenario=...)` on ASYMMETRIC and demands
a non-empty `conflicts` — the double-committed slot — and refuses its own
verdict if the foil comes back clean. The stage imports the foil ONLY
inside `audit`, as the node module of a run; `naive` never enters the
stage's protocol logic (the banned-import shape of this docstring's
promise is enforced by the check).
"""

import sys
import wire

import history
import scenarios
import sim

import stage_01
import stage_02
import stage_03
import stage_04
import stage_05
import stage_06
import stage_07
import stage_08
import stage_09

#: The fabric write-throughs and restarts through the image law (stage 7):
#: durability is not a new law at stage 10, it is stage 7's, reused.
persist = stage_07.persist
recover = stage_07.recover


def _values(state):
    """The applied state machine over the committed prefix — never past
    the commit line, or a read would answer a value a newer term can
    still roll back."""
    values = {}
    members = None
    start = wire.log_start(state["log"])
    for entry in state["log"][:state["commit_index"] - start + 1]:
        command = entry[2]
        if command.startswith("members:"):
            members = stage_09._peers_of(command)
        elif "=" in command:
            key, value = command.split("=", 1)
            values[key] = value
    return values, members


def _apply_committed(state):
    """Membership takes effect at the commit line: when the committed
    prefix ends in a members command and the config disagrees, swap the
    config and rebuild through the role's builder (stage 9's law)."""
    _read, members = _values(state)
    if members is None or members == state["config"]:
        return state
    s = dict(state)
    s["config"] = members
    return stage_09._rebuild(s)


def _advance(state):
    """Leader-side progress: the commit rule (5), then the membership
    law (9) at the new line."""
    if state["role"] != "leader":
        return state
    return _apply_committed(stage_05.advance_commit(state))


def _prev_term(state, prev_index):
    start = wire.log_start(state["log"])
    if prev_index >= start:
        return state["log"][prev_index - start][1]
    if state["snapshot_at"] is not None:
        return state["snapshot_at"][1]
    return 0


def _broadcast(state):
    """One APPEND per live peer of the config — a SNAPSHOT instead for a
    peer whose next_index has fallen at or below the leader's boundary:
    the heartbeat, the retry, the catch-up, all one shape."""
    start = wire.log_start(state["log"])
    tail = start + len(state["log"])
    boundary = state["snapshot_at"]
    out = []
    for peer in state["config"]:
        if peer == state["id"]:
            continue
        nxt = state["next_index"].get(peer, tail)
        if boundary is not None and nxt <= boundary[0]:
            upto = state["commit_index"]
            if upto < start:
                continue  # nothing committed inside the window
            message, _leader2 = stage_08.build_snapshot(state, upto)
            out.append(message)
            continue
        out.append(wire.append(state["term"], state["id"],
                               _prev_term(state, nxt - 1), nxt - 1,
                               tuple(state["log"][max(nxt - start, 0):]),
                               state["commit_index"]))
    return tuple(out)


def _step_down(state):
    s = dict(state)
    return wire.follower(s["id"], s["term"], voted_for=s["voted_for"],
                         log=s["log"], commit_index=s["commit_index"],
                         config=s["config"], elapsed=0,
                         snapshot_at=s["snapshot_at"])


def init(node_id, peers):
    """A fresh follower: term 0, empty log, no vote cast."""
    return wire.follower(node_id, config=tuple(peers))


def recv(state, message):
    """One message in, replies out: the composed term law (stage 6), the
    vote (1), the append and its reply (3, 4, 5), the snapshot (8), the
    membership command applying at commit (9): (state2, replies)."""
    kind = wire.kind(message)

    if kind == wire.REQUEST_VOTE:
        term, cand = message[1], message[2]
        if state["role"] in ("leader", "candidate") \
                and term <= state["term"]:
            # At our term or below the request cannot take a vote we
            # have already spent on this leadership or this election:
            # deny it and keep the role. Handing a same-term request to
            # stage_01's follower law would forfeit an election already
            # in flight — the three peers voted for US a heartbeat ago.
            return state, (wire.vote_reply(state["term"], state["id"],
                                           cand, False),)
        reply, state2 = stage_01.grant_vote(state, message)
        return state2, (reply,)

    if kind == wire.VOTE_REPLY:
        if state["role"] != "candidate":
            return state, ()
        outcome, after = stage_02.tally(state, (message,))
        if outcome == "leader":
            leader = stage_03.become_leader(state)
            return leader, _broadcast(leader)
        return after, ()

    if kind == wire.APPEND:
        reply, follower2 = stage_04.handle_append(state, message)
        return _apply_committed(follower2), (reply,)

    if kind == wire.APPEND_REPLY:
        if state["role"] != "leader":
            return state, ()
        if message[1] > state["term"]:
            # The contest ended elsewhere: the ledger records the step
            # down, and the maps go with the leadership.
            return stage_03.observe_reply(state, message), ()
        if stage_06.same_term_stale(state, message):
            # Our term was superseded by a rival who truncated a peer
            # below our commit line: stand down, do not re-argue.
            return _step_down(state), ()
        leader2 = stage_03.observe_reply(state, message)
        return _advance(leader2), ()

    if kind == wire.SNAPSHOT:
        reply, follower2 = stage_08.install_snapshot(state, message)
        return follower2, (reply,)

    if kind == wire.SNAPSHOT_REPLY:
        if state["role"] != "leader" or message[1] != state["term"]:
            return state, ()
        node, matched_at = message[2], message[3]
        if node not in state["matched"]:
            return state, ()
        leader2 = stage_03.observe_reply(
            state, wire.append_reply(state["term"], node, matched_at,
                                     matched_at + 1, leader=state["id"]))
        return _advance(leader2), ()

    raise wire.ProtocolError("stage_10: cannot receive %r" % (message,))


def tick(state):
    """One clock tick: heartbeat when leading, election when the silence
    outlasts `sim.timeout(s["id"])`, otherwise age the timer: (state2,
    replies)."""
    s = dict(state)
    s["elapsed"] = s["elapsed"] + 1
    if s["role"] == "leader":
        if s["elapsed"] >= wire.HEARTBEAT:
            s["elapsed"] = 0
            leader = stage_09._rebuild(s)
            return leader, _broadcast(leader)
        return stage_09._rebuild(s), ()
    if s["elapsed"] >= sim.timeout(s["id"]):
        requests, candidate = stage_02.start_election(s)
        if not requests:
            return candidate, ()
        # The fabric fans ONE request to every live peer; emitting one
        # per peer would deliver the grid in duplicate.
        return candidate, (requests[0],)
    return stage_09._rebuild(s), ()


def client(state, command):
    """The application's call: (state2, messages, answer) — a leader
    appends writes and answers reads from committed state; everyone else
    refuses."""
    if state["role"] != "leader":
        return state, (), ("not_leader", "")
    if command.startswith("get "):
        values, _members = _values(state)
        return state, (), ("read", values.get(command[len("get "):], ""))
    leader2, _messages = stage_04.client_submit(state, command)
    advanced = _advance(leader2)
    return advanced, _broadcast(advanced), (None,)


def prove(name):
    """Run scenario `name` through `sim.Cluster` with THIS stage as the
    node module: ("scenario", "result", "pins", "linear")."""
    _kind, events, ticks, pins = scenarios.scenario(name)
    cluster = sim.Cluster(sys.modules[__name__], scenario=events)
    result = cluster.run(ticks)
    linear = history.linearizable(result["history"])
    return (name, result, pins["probe"], linear)


def audit(proofs):
    """The verdict over every scenario PLUS the foil's ASYMMETRIC run
    through the fabric: ("verdict", "reasons")."""
    import naive

    reasons = []
    for proof in proofs:
        name, result, _pins, linear = proof
        if name not in scenarios.PINS:
            reasons.append("%s: not a scenario the pins table knows"
                           % (name,))
            continue
        want = scenarios.PINS[name]["probe"]
        if result["leaders"] != want["leaders"]:
            reasons.append("%s: leaders %r are not the pinned %r"
                           % (name, result["leaders"], want["leaders"]))
        if result["committed"] != want["committed"]:
            reasons.append("%s: commits %r are not the pinned %r"
                           % (name, result["committed"], want["committed"]))
        if result["conflicts"] != want["conflicts"]:
            reasons.append("%s: conflicts %r are not the pinned %r"
                           % (name, result["conflicts"], want["conflicts"]))
        if not linear[0]:
            reasons.append("%s: the history is not linearizable: %s"
                           % (name, "; ".join(linear[1])))
    _kind, events, ticks, _pins = scenarios.scenario("ASYMMETRIC")
    foil = sim.Cluster(naive, scenario=events).run(ticks)
    if not foil["conflicts"]:
        reasons.append("foil ASYMMETRIC: conflicts empty — the audit is "
                       "not driving the real world, it proves nothing")
    if reasons:
        return ("fail", tuple(reasons))
    return ("pass", ())
