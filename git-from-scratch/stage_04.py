"""Git From Scratch — stage 4: The tree, read: sorted entries with modes.

A tree is the object a directory becomes: entries of
`"<mode> <name>\\0<20 raw sha bytes>"` back to back, no newlines, the sha
raw rather than hex. `ls-tree --name-only` answers the names — byte-sorted,
directories suffixed `/` — and the discipline is in the modes: a mode not
in `MODES` is a corrupted tree, and reading one as if it were fine would
let a `40000` entry point at a blob.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why do both doors answer the file's order?
Because `ls-tree --name-only` is a *reader*, not a sorter: real git prints
what the tree holds, and a tree git wrote was sorted at write time. The
sort lives in the writer (stage 5's `entry_sort_key`); a reader that
sorted would hide a tree written out of order — the corruption the format
door exists to surface.

DESIGN DECISION — why is a bad mode a refusal rather than a passthrough?
Because the mode is the entry's type claim: `40000` promises a tree, a
`100644` a blob, and stage 5's writer and stage 9's unpacker both rely on
the claim. A reader that passed unknown modes through would answer a tree
whose entries it cannot vouch for — the one thing an object store may
never do.

DESIGN DECISION — why do both doors read one object and answer twice?
Because the two questions a tree answers — what does it hold, and in what
order does it hold it — are asked by different callers: `ls_tree` serves
the reader who wants the entries as the file stores them, and
`ls_tree_names` serves the comparer who wants git's own display order. A
door that reordered for both would make one caller parse what the other
already paid for; reading once and answering twice is the whole
economy.
"""

import repo as rp


def ls_tree(repo, sha):
    """The entries as `(mode, name, sha_hex)` in the file's order."""
    raise NotImplementedError("stage 4: implement ls_tree()")


def ls_tree_names(repo, sha):
    """The names byte-sorted, directories suffixed '/'."""
    raise NotImplementedError("stage 4: implement ls_tree_names()")
