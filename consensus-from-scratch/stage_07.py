"""Consensus From Scratch — stage 7: The disk that lied: persist and
recover.

`persist` turns a node's whole durable truth — term, voted_for, commit
window, config, snapshot boundary, log — into bytes; `recover` reads them
back. The fabric write-throughs every state transition to the node's disk
and, when a `("crash", tick, node)` event fires, TEARS the last record:
whatever was in the middle of landing is gone. A restarted node comes up
from `recover` of the surviving bytes — or blank, if the protocol never
learned to persist — and `heal_from_leader` is what makes a torn node
rejoin without losing a committed entry.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why persist `term` and `voted_for` at all, when the log
survives?
Because losing the term loses the one-vote-per-term law across a restart:
a node that comes back at term 0 will happily grant two votes in the term
it already voted in, and the election that depends on the overlap of two
majorities stops being safe. The two fields plus the log are the minimum
durable set; the commit window and config ride along because `wire`'s
builders refuse a state without them, and a recover that cannot rebuild
a legal state is a recover that restarts a corpse.

DESIGN DECISION — why is the encoding a versioned, newline-delimited text
image rather than pickle or a struct?
Because the check must read the bytes to prove what survived the tear,
and pickle is opaque and struct needs a width table. `v1` in the first
line means a future stage can refuse an old image with a naming error
instead of misreading it; every field is one line, the log's entries are
`index;term;command` lines, and `-` marks an absent optional (no vote, no
snapshot boundary). `recover` of anything malformed raises
`wire.ProtocolError` naming the line — a torn head is a blank node, not a
half-understood one.

DESIGN DECISION — why does `heal_from_leader` reuse stage 4's prev check
instead of "just re-sync from 0"?
Because the leader's `next_index` walk IS the resync, and a node that
throws its log away on restart would answer `matched = -1` and force the
leader to resend a replicated history it already holds. The torn record
means the last entry may be missing — but everything before it is real,
so the healed follower keeps its prefix, accepts the leader's tail from
the first agreeing (index, term), and the committed entries the leader
holds at or below its `leader_commit` are, by the safety theorem, in that
prefix: the tear can lose an UNCOMMITTED entry (correct) and never a
committed one (the check pins both directions).
"""

def persist(state):
    """The node's durable truth as bytes: a `v1` image the check can read
    line by line. Deterministic: the same state, the same bytes."""
    raise NotImplementedError("stage 7: implement persist()")


def recover(saved):
    """Bytes back to a state, via `wire`'s builders; malformed input
    raises ProtocolError naming the offender."""
    raise NotImplementedError("stage 7: implement recover()")


def heal_from_leader(state, msg):
    """A restarted node answering the leader's APPEND: keep the surviving
    prefix, accept the tail, answer at the boundary: (reply, state2)."""
    raise NotImplementedError("stage 7: implement heal_from_leader()")
