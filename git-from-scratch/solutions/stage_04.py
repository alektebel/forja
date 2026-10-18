"""Git From Scratch — stage 4: The tree, read: sorted entries with modes.

A tree is the object a directory becomes: entries of
`"<mode> <name>\\0<20 raw sha bytes>"` back to back, no newlines, the sha
raw rather than hex. `ls-tree --name-only` answers the names — byte-sorted,
directories suffixed `/` — and the discipline is in the modes: a mode not
in `MODES` is a corrupted tree, and reading one as if it were fine would
let a `40000` entry point at a blob.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why does `ls_tree` answer the file's order and
`ls_tree_names` the sorted order?
Because they answer different questions: `ls_tree` is the *format* door —
later stages read trees entry by entry and the file's order is the fact —
while `ls_tree_names` is the *user* door, and real git's `ls-tree
--name-only` prints byte-sorted names whatever order the file holds. One
answers "what is written", the other "what the user sees".

DESIGN DECISION — why is a bad mode a refusal rather than a passthrough?
Because the mode is the entry's type claim: `40000` promises a tree, a
`100644` a blob, and stage 5's writer and stage 9's unpacker both rely on
the claim. A reader that passed unknown modes through would answer a tree
whose entries it cannot vouch for — the one thing an object store may
never do.
"""

import repo as rp
import objects as ob


def ls_tree(repo, sha):
    """The entries as `(mode, name, sha_hex)` in the file's order."""
    kind, body = repo.object_read(sha)
    if kind != "tree":
        raise rp.GitError("ls_tree: %r is a %s, not a tree" % (sha, kind))
    entries = []
    at = 0
    while at < len(body):
        space = body.index(b" ", at)
        mode = body[at:space].decode()
        nul = body.index(b"\x00", space)
        name = body[space + 1:nul].decode()
        raw = body[nul + 1:nul + 21]
        if len(raw) < 20:
            raise rp.GitError("ls_tree: entry %r has no full sha" % (name,))
        if mode not in ob.MODES:
            raise rp.GitError("ls_tree: entry %r names mode %r" % (name, mode))
        entries.append((mode, name, raw.hex()))
        at = nul + 21
    return tuple(entries)


def ls_tree_names(repo, sha):
    """The names byte-sorted, directories sorted as `name/` but printed
    plain — the order real git's `ls-tree --name-only` prints."""
    entries = ls_tree(repo, sha)
    keyed = sorted(
        ((ob.entry_sort_key(name, mode == "40000"), name)
         for (mode, name, _sha) in entries))
    return tuple(name for (_key, name) in keyed)
