"""Git From Scratch — stage 6: The commit: a tree, a parent, and a frozen
line.

A commit is the object that turns a tree into history:
`tree <sha>\\nparent <sha>\\nauthor <line>\\ncommitter <line>\\n\\n<message>\\n`
— plain text after the header, hex shas rather than raw, the blank line
between the metadata and the message. The discipline is in the refusals: a
tree sha that names no object and a parent sha that names no commit are
refusals named before anything is written, because a commit whose parent
is a claim rather than a record is history nobody can walk.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why verify the tree and the parent before writing?
Because the commit is the store's first cross-reference: its bytes name two
other objects, and a commit written against a missing parent becomes the
dangling reference `git fsck` reports — the corruption is invisible until
someone walks the history. The refusal costs one `object_read`; the
dangling commit costs a history.

DESIGN DECISION — why is the author line frozen in the world?
Because the course is deterministic and a commit's bytes are its hash: a
clock or a username inside the commit would make the hash unknowable in
advance and the check unable to hold anything. `worktree.AUTHOR` and
`worktree.TIMESTAMP` freeze the line; the check pins the commit's own hash
to the one real git computes over the same bytes.

DESIGN DECISION — why does `commit_tree` answer the sha rather than write
a ref?
Because plumbing writes objects; porcelain moves refs. `git commit-tree`
answers a sha and the caller (or a later stage) decides what names it —
mixing the two here would make the stage unable to build the two-headed
histories stage 8's log walks.
"""

import repo as rp
import objects as ob
import worktree as wt


def commit_tree(repo, tree_sha, parent_sha, message):
    """The commit object written; its sha is the answer."""
    tree_kind, _body = repo.object_read(tree_sha)
    if tree_kind != "tree":
        raise rp.GitError("commit_tree: %r is a %s, not a tree"
                          % (tree_sha, tree_kind))
    parent_kind, _body = repo.object_read(parent_sha)
    if parent_kind != "commit":
        raise rp.GitError("commit_tree: parent %r is a %s, not a commit"
                          % (parent_sha, parent_kind))
    line = "%s %s" % (wt.AUTHOR, wt.TIMESTAMP)
    body = ("tree %s\nparent %s\nauthor %s\ncommitter %s\n\n%s\n"
            % (tree_sha, parent_sha, line, line, message)).encode()
    head = ob.header("commit", len(body))
    sha = ob.sha1(head + body)
    path = repo.git_dir + "/" + ob.obj_path(sha)
    if not repo.fs.exists(path):
        repo.fs.write(path, ob.zlib_wrap("commit", body))
        repo._written += 1
    repo._hashed += 1
    return sha
