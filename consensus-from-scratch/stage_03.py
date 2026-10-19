"""Consensus From Scratch — stage 3: The heartbeats: leadership is exercised,
not claimed.

A leader holds power by talking: `become_leader` converts the candidate
that won a majority into a state that carries each peer's `matched` and
`next_index`; `heartbeat` asks every peer to confirm the leader's term
with nothing to replicate; `observe_append` is the receiver's side — the
term law, then the prev check; `observe_reply` is the leader reading what
came back. Leadership that stops exercising is leadership that ends: the
followers' timeouts are the proof.

TODO: implement each function; the docstring is the contract.

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

def become_leader(candidate):
    """The won election becomes the state: empty matched map, every peer's
    next_index one past the last entry (or the snapshot boundary), commit
    unchanged."""
    raise NotImplementedError("stage 3: implement become_leader()")


def heartbeat(leader):
    """One empty-payload `wire.append` per peer: term, prev at each
    peer's next_index, leader_commit, nothing to replicate."""
    raise NotImplementedError("stage 3: implement heartbeat()")


def observe_append(follower, msg):
    """The receiver's side of an APPEND: term law, prev check, and the
    reply: (reply, follower2)."""
    raise NotImplementedError("stage 3: implement observe_append()")


def observe_reply(leader, reply):
    """The leader reading one APPEND_REPLY: records matched/conflict and
    steps down on a higher term: leader2."""
    raise NotImplementedError("stage 3: implement observe_reply()")
