"""Consensus From Scratch — stage 6: The stale leader: refuse, downgrade,
never ignore.

Every node in the cluster carries one obligation: answer at a term nobody
believes in and someone must tell you. `check_request` is that telling,
applied to every kind a node receives: a higher term adopts and steps down
FIRST; a lower term is refused with the node's own term in the reply so
the sender learns it is obsolete. `same_term_stale` closes the loop on the
leader's side: evidence that its own term has been superseded elsewhere —
a denial whose term is higher, a reply from a node that has clearly moved
on — and the leader gives up before its heartbeats lie.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why does the node answer a lower-term request rather
than drop it?
Because silence is indistinguishable from a dead link, and a stale leader
that believes it is alive keeps appending to its own log forever. The
reply is the message: "your term is old, here is mine" — the sender's
step-down rule (stage 3's observe_reply) does the rest. Dropping refuses
to inform and leaves a partitioned leader writing entries that will be
truncated in a later term.

DESIGN DECISION — why does `check_request` return (accept, state2) with
the state ALREADY upgraded when the term is higher, before the message's
own kind is handled?
Because the term law is universal — it applies to REQUEST_VOTE, APPEND
and SNAPSHOT alike — and running it once at the door keeps each kind's
handler from re-implementing it (and from re-implementing it wrongly in a
different corner of the stage). The stage's later handlers receive states
whose term is never below the message they process.

DESIGN DECISION — why does a leader step down on a same-term reply that
proves it stale?
Because a leader's authority is a fact about the PAST — it won an
election — and every heartbeat is an implicit claim that fact still
holds. A reply from a peer at the same term whose log state can only
exist if a higher term won elsewhere (matched regressed below what this
leader committed, denial of entries that must be present after the peer
adopted a newer leader) falsifies the claim: step down now, as follower,
elapsed reset, rather than wait to be deposed by the next election.
Correctness here is not visible in the scenario pins — the fabric makes
it so that any protocol whose stale leaders keep claiming survives by
being truncated; the check pins it with hand-built states: a leader's
`observe_reply`/`check_request` chain on evidence of supersession ends
in role follower.
"""

def check_request(state, msg):
    """The term law for every kind: (accept, state2) — on a higher term,
    the state adopts (and downgrades from leader) and accepts; on a lower
    term the state is unchanged and the reply field (if any) carries the
    node's own term so the sender learns."""
    raise NotImplementedError("stage 6: implement check_request()")


def same_term_stale(leader, reply):
    """Does this APPEND_REPLY prove the leader's term was superseded?
    bool."""
    raise NotImplementedError("stage 6: implement same_term_stale()")
