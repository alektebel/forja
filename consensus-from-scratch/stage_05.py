"""Consensus From Scratch — stage 5: The commit rule: a majority, and the
current term.

`advance_commit` is the smallest law with the largest blast radius. A
leader counts, for each index it holds, how many peers' `matched` reach
it — self included — and raises `commit_index` to the highest index a
majority holds, THROUGH ENTRIES OF ITS OWN TERM. The majority half makes
progress possible; the term half makes it safe: an entry of an older term
is committed as a consequence of a current-term entry above it, never by
counting the old entry itself.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why may a leader NOT commit an old-term entry by
counting it, even when a majority holds it?
Because a majority of an OLD term's cluster may no longer be a majority
now: the entries below the line could exist on nodes that voted a NEWER
leader in, and that newer leader may have already overwritten that slot
with its own term. Commit by counting an old entry and you can commit two
different commands to one slot — the foil's exact double-commit. The
current-term rule is the only thing standing between "majority" and
"majority of the right epoch". The check pins the classic figure: new
leader a2 at term 3 holding `(index 2, term 2)` on a majority — it must
NOT commit index 2; a later entry of term 3 at index 3 carries index 2 in
with it, retroactively and safely.

DESIGN DECISION — why is commit monotone (only ever raised) and capped by
what this leader actually holds?
Because committed means durable-in-order: a node that rolled a commit
index back would tell the state machine to undo a transition it already
applied. A stale leader's `leader_commit` beyond the local tail is clamped
to the last entry — the same clamping law stage 4 installs — and never
trusted blindly. `wire.majority` on `len(config)` is the only quorum
arithmetic; comparisons are int against int.

DESIGN DECISION — why does the vote tally count `matched >= index` over
the CONFIG (excluding peers not in it)?
Because membership defines the voters: a peer outside the config can hold
the entry and still not count, and a node in the config that has not
answered counts nothing. The leader's own copy is one vote — that is what
makes a single-node cluster able to commit (and what `advance_commit`
pins on a one-node config). Index arithmetic is measured from
`wire.log_start`, so a snapshotted leader commits over its boundary
without off-by-one.
"""

def advance_commit(leader):
    """The commit line after the current `matched` map: leader2 with
    `commit_index` raised — only through own-term entries, only to a
    majority-reached index, only forward."""
    raise NotImplementedError("stage 5: implement advance_commit()")
