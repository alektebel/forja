"""Consensus From Scratch — stage 4: Replication: the entries match term by
term.

`client_submit` is where a command becomes a log entry — the leader
appends `(index, term, command)` and the entry exists for the cluster the
moment it exists on the leader. `broadcast_append` sends each peer its
tail from that peer's `next_index`. `handle_append` is where a follower's
log and the leader's are reconciled: the prev check passes and the tail
is installed — overwriting anything the old leader left behind.

TODO: implement each function; the docstring is the contract.

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

def client_submit(leader, command):
    """A command becomes an entry: (leader2, messages). Never a `get` —
    reads answer from the committed state, they do not replicate."""
    raise NotImplementedError("stage 4: implement client_submit()")


def broadcast_append(leader):
    """Each peer's tail from its next_index: the appends, one per peer."""
    raise NotImplementedError("stage 4: implement broadcast_append()")


def handle_append(follower, msg):
    """Reconcile a follower's log with the leader's: prev check, install
    the tail, truncate by term on mismatch, clamp the commit line: (reply,
    follower2)."""
    raise NotImplementedError("stage 4: implement handle_append()")
