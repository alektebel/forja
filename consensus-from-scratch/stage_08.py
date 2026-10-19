"""Consensus From Scratch — stage 8: The snapshot: commit without losing a
committed entry.

A replicated log cannot grow forever: a node that joins late, or a
follower that fell so far behind its prev_index is below what the leader
still holds, needs the state itself, not the history of how it was built.
`build_snapshot` compacts the leader's committed prefix into a
`wire.snapshot` message and drops those entries from the tail;
`install_snapshot` is the receiver's side — replace the log, adopt the
boundary, resume replication from there.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why may a snapshot drop only COMMITTED entries, and
never move the boundary past `commit_index`?
Because the snapshot's promise is "these commands are in every surviving
future state machine" — the only way to keep that promise is to compact
below the commit line. A snapshot of an uncommitted prefix would install
a state the cluster might still roll back (the entry could be overwritten
by a newer term), and `conflicts` would record two commands for slots the
leader deleted. `build_snapshot` refuses an `upto_index` above
`commit_index` with a `wire.ProtocolError` naming both numbers; the
boundary moves to `(upto, entry's term)`, and `commit_index` rides with
it.

DESIGN DECISION — why is the snapshot message's payload the committed
commands, not the state machine's values?
Because the state machine is the application's business (the fabric's
`history.linearizable` judge replays commands, not values). A snapshot in
this course is `wire.snapshot(term, sender, last_included_term,
last_included_index, entries)` where `entries` are the very
`(index, term, command)` triples being compacted — so a receiver can
verify the boundary pair matches its replay and can re-apply with its own
rules. The receiver's `snapshot_at = (last_included_index,
last_included_term)` makes `wire.last_entry` answer the boundary when the
tail is empty, which is exactly what stage 1's up-to-date law needs to
keep snapshotted nodes electable.

DESIGN DECISION — why does install refuse a snapshot that does not beat
the follower's own boundary?
Because installing an older snapshot over a longer log is data loss with
extra steps. The rule mirrors stage 1: compare `(index, term)` against
`wire.last_entry` — install when it is strictly ahead of what the
follower has and when nothing in the follower's tail contradicts it. On
install the follower's log becomes the payload, its commit line lands at
the boundary, and the next APPEND's prev check runs against the new
boundary — replication resumes without the leader noticing which peers
compacted.
"""

def build_snapshot(leader, upto_index):
    """The committed prefix as a message plus the leader past it:
    (snapshot_msg, leader2). Refuses `upto_index` above `commit_index`."""
    raise NotImplementedError("stage 8: implement build_snapshot()")


def install_snapshot(follower, msg):
    """The receiver's side: adopt a snapshot only when it beats what the
    follower holds: (reply, follower2)."""
    raise NotImplementedError("stage 8: implement install_snapshot()")
