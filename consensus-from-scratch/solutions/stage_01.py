"""Consensus From Scratch — stage 1: The vote: terms, and one vote per term.

`grant_vote` is where a replicated log either grows a leader or splits in
half. A request carries the candidate's term and the last (index, term)
pair of its log; the voter holds its own term and, once it has voted, the
id it voted for. The laws here are the whole of election safety: a request
from a lower term is refused; a node votes at most once per term; and a
candidate whose log is NOT at least as up-to-date — last term first, then
last index — is refused even in its own term, because a log that is missing
committed entries cannot be allowed to become the authority over them.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why is a higher term adopted BEFORE the vote is
considered, not after?
Because the term is the voter's own bookkeeping: a node that answers at the
old term has already lost — its reply carries an obsolete term and the
candidate demotes nobody. Adopting first (term set, `voted_for` cleared)
means the single vote this term is spent on this candidate, and the reply
answers at the term the whole cluster is moving to. The order is the
protocol; a vote granted then re-latched is two votes in one term.

DESIGN DECISION — why does the up-to-date comparison look at last TERM
before last INDEX?
Because term order is log order: the candidate with the higher last term
holds an entry no lower-term log can contain, and it is that entry — not
the count of entries — that must not be lost. Compare the term first and
fall back to the index only on a tie, exactly as
`wire.at_least_as_up_to_date` does; the stage calls that helper rather
than re-deriving it, because the helper is the world's and it takes
(index, term) PAIRS from `wire.last_entry`.

DESIGN DECISION — why does the reply carry the VOTER's id, not just the
candidate's?
Because a candidate tallies grants by node: two followers granting the same
term are only two votes if they are two different nodes, and a candidate
that cannot name its voters cannot count quorum. `wire.vote_reply(term,
node, cand, granted)` puts the voter in field 2; the stage MUST pass its
own `s["id"]` there. This is the fix that separates a working election from
a term that runs to six with everyone answering and nobody counting.

DESIGN DECISION — why is a refused vote `granted=False` rather than a
raised error?
Because refusal is the protocol's normal traffic. A leader's request from a
superseded term is a message that should be answered so the sender learns;
raising would stop the exchange and strand a node that has not heard about
the newer term yet. Errors here are for malformed input only — a `state`
with a missing key or a `request` that is not a REQUEST_VOTE raises
`wire.ProtocolError` naming the offender.
"""

import wire


def grant_vote(state, request):
    """Decide one vote: (reply, state2). The reply is a `wire.vote_reply`
    carrying this voter's id; the state has adopted a higher term, latched
    `voted_for`, and nothing else."""
    for key in wire.FOLLOWER_KEYS:
        if key not in state:
            raise wire.ProtocolError("stage_01: the state is missing the "
                                     "key %r" % (key,))
    if wire.kind(request) != wire.REQUEST_VOTE or len(request) != 5:
        raise wire.ProtocolError("stage_01: grant_vote needs a "
                                 "request_vote, got %r" % (request,))
    term, cand, last_term, last_index = (request[1], request[2], request[3],
                                         request[4])
    # Re-validate through the grammar; a hand-built tuple is refused.
    wire.request_vote(term, cand, last_term, last_index)
    granted = False
    s = dict(state)
    if term > s["term"]:
        # The term law first: adopt, clear the latch, THEN consider.
        s["term"] = term
        s["voted_for"] = None
        s["elapsed"] = 0
    if term >= state["term"]:
        if s["voted_for"] in (None, cand):
            voter_last = wire.last_entry(s)
            candidate_last = (last_index, last_term)
            if wire.at_least_as_up_to_date(candidate_last, voter_last):
                granted = True
                s["voted_for"] = cand
    reply = wire.vote_reply(s["term"], s["id"], cand, granted)
    state2 = wire.follower(s["id"], s["term"], voted_for=s["voted_for"],
                           log=s["log"], commit_index=s["commit_index"],
                           config=s["config"], elapsed=s["elapsed"],
                           snapshot_at=s["snapshot_at"])
    return reply, state2
