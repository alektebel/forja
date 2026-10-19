"""Consensus From Scratch — stage 2: The election: a leader is a number a
majority agreed on.

`start_election` advances the term and casts the node's own vote; `tally`
decides what the granted replies mean. A leader is not a node that
announces itself — it is a count: grants from distinct voters plus the
self-vote, at least `wire.majority` of the config. A majority of an
election's voters is the only authority a term can have, and if two nodes
counted different majorities the same term could elect two leaders; five
nodes, two quorums, one overlap — the overlap is the safety.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why does the candidate vote for itself?
Because the node IS in its own config and its vote is one of the votes a
quorum counts. Without the self-vote a one-node cluster could never elect,
and every quorum arithmetic downstream would have to subtract one. The
latch from stage 1 is what makes this legal: the vote is cast through the
same `voted_for` law, at the new term, before any reply arrives.

DESIGN DECISION — why are grants counted as DISTINCT voter ids?
Because `wire.vote_reply` carries the voter (field 2) precisely so a reply
cannot be counted twice and a reply from outside the config cannot sneak
into the tally. `tally` keeps `votes` as a sorted tuple of ids on the
candidate state — the same voter granting twice is one grant — and reaches
leader only when `wire.majority(len(config)) <= len(votes)`.

DESIGN DECISION — why does a higher term in a reply demote, but an
equal-term denial keep the candidacy alive?
Because the term is the clock of the protocol: a reply bearing a higher
term proves a newer reality exists and every claim this candidacy made is
already void — become follower, adopt, clear. A denial at the candidate's
own term proves nothing newer: the voters are simply committed elsewhere,
and starting a second election in the same term would spend votes the term
has already given out. The candidacy waits for its timeout, then raises
the term.

DESIGN DECISION — why does `start_election` return requests for ALL peers
but a `request_vote` whose last (index, term) comes from
`wire.last_entry`?
Because the voter's up-to-date law (stage 1) compares the candidate's
whole claim — its boundary snapshot included. `wire.last_entry` returns
the snapshot pair when the tail is empty; hand-picking `last_of(s["log"])`
would let a snapshotted candidate look empty and lose elections it should
win.
"""

import wire


def start_election(state):
    """Advance the term, self-vote, and ask: (requests, candidate2). One
    `wire.request_vote` per peer, none to self."""
    if state["role"] not in ("follower", "candidate"):
        raise wire.ProtocolError(
            "stage_02: start_election expects a follower or a candidate, "
            "got role %r" % (state["role"],))
    term = state["term"] + 1
    last_index, last_term = wire.last_entry(state)
    requests = tuple(
        wire.request_vote(term, state["id"], last_term, last_index)
        for peer in sorted(state["config"]) if peer != state["id"])
    candidate2 = wire.candidate(
        state["id"], term, voted_for=state["id"], log=state["log"],
        commit_index=state["commit_index"], config=state["config"],
        elapsed=0, votes=(), snapshot_at=state["snapshot_at"])
    return requests, candidate2


def tally(candidate, replies):
    """What the replies mean: (role, state2) with role in
    ("leader", "follower", "candidate") — leader only on a majority of
    DISTINCT granting voters plus the self-vote."""
    if candidate["role"] != "candidate":
        raise wire.ProtocolError(
            "stage_02: tally expects a candidate state, got role %r"
            % (candidate["role"],))
    fields = []
    for reply in replies:
        if wire.kind(reply) != wire.VOTE_REPLY or len(reply) != 5:
            raise wire.ProtocolError(
                "stage_02: tally expects vote_reply messages, got %r"
                % (reply,))
        term, voter, addressed, granted = reply[1], reply[2], reply[3], \
            reply[4]
        # Re-validate through the grammar: a hand-built reply is refused
        # the same as a malformed state.
        wire.vote_reply(term, voter, addressed, granted)
        fields.append((term, voter, addressed, granted))
    # The term law first: any higher term voids this candidacy BEFORE a
    # majority can be counted, even if the grants arrived in the same batch.
    for term, _voter, _addressed, _granted in fields:
        if term > candidate["term"]:
            return "follower", wire.follower(
                candidate["id"], term, voted_for=None,
                log=candidate["log"],
                commit_index=candidate["commit_index"],
                config=candidate["config"], elapsed=candidate["elapsed"],
                snapshot_at=candidate["snapshot_at"])
    voters = set(candidate["votes"])
    for term, voter, addressed, granted in fields:
        if (granted and addressed == candidate["id"]
                and term == candidate["term"]
                and voter in candidate["config"]):
            voters.add(voter)
    votes = tuple(sorted(voters | {candidate["id"]}))
    if len(votes) >= wire.majority(len(candidate["config"])):
        return "leader", wire.leader(
            candidate["id"], candidate["term"], log=candidate["log"],
            commit_index=candidate["commit_index"],
            config=candidate["config"],
            snapshot_at=candidate["snapshot_at"])
    return "candidate", wire.candidate(
        candidate["id"], candidate["term"],
        voted_for=candidate["voted_for"], log=candidate["log"],
        commit_index=candidate["commit_index"], config=candidate["config"],
        elapsed=candidate["elapsed"], votes=votes,
        snapshot_at=candidate["snapshot_at"])
