"""Consensus From Scratch — stage 9: The membership change: one at a time.

A replicated log's safety rests on two majorities always overlapping —
but that holds only while every voter shares one config. Swap the
membership in one step and the cluster can split into an old-majority and
a new-majority that commit two different logs. Joint consensus fixes
this: for one entry's lifetime the cluster is BOTH configs, and a commit
in the joint phase needs a majority of each.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why is the change itself a log command
(`members:a,b,c`) rather than a message kind?
Because a membership takes effect at a point in the log, and only a
replicated, committed log entry has a point in the log. A wire kind would
take effect when it arrives — differently on different nodes — and two
nodes could hold different majorities about the same commit. `wire` has
no membership kind on purpose; the command rides the same replication
path as any write, so everyone agrees on WHEN the change happened before
anyone acts on it.

DESIGN DECISION — why does `begin_change` append the entry and set
`config = union(old, new)` with `old_config` kept, but leave the voters'
behavior to `quorum`?
Because the joint window has exactly one law: commit needs a majority of
EACH config. `quorum(state)` answers the vote count a joint leader needs
when `old_config` is set: `wire.majority(len(old)) +
wire.majority(len(new))` — the two sets are disjoint by construction, so
reaching that count means both majorities answered, and no count means
one side was missed. When `old_config` is None the answer is simply
`wire.majority(len(config))`. The sum form keeps the stage int-only: no
"and" over sets at the call sites, one number, measured.

DESIGN DECISION — why may `finish_change` drop the old config only once
the JOINT entry is committed on the new majority?
Because the moment a new-only majority holds the joint entry, every
future commit needs that new majority, and any old node that disagrees is
simply outside the cluster from the entry's index onward. Committing the
joint entry needs both majorities (the window), so after commit the
overlap is preserved by construction: the new config elected its own
leader only via nodes that had already accepted the joint entry. A leader
whose `config` no longer includes its own id (the cluster reformed without
it) stops leading — it serves the joint entry as a follower would.

DESIGN DECISION — why refuse an empty new config or a change that skips
the joint step?
Because both are the split-brain in a different coat: an empty config has
no majority; a direct swap creates two majorities at once. `begin_change`
raises `wire.ProtocolError` naming the offender, so a caller cannot
"almost" do the right thing.
"""

def begin_change(leader, new_peers):
    """Enter the joint config: append the members command, config becomes
    the union, old_config kept: (leader2, entry). Refuses empty/illegal
    sets."""
    raise NotImplementedError("stage 9: implement begin_change()")


def quorum(state):
    """Votes a proposal needs: majority of each config while joint,
    majority of the single config otherwise. An int."""
    raise NotImplementedError("stage 9: implement quorum()")


def finish_change(leader):
    """Leave the joint config once the joint entry is committed under it:
    config becomes the new set, old_config None: leader2."""
    raise NotImplementedError("stage 9: implement finish_change()")
