"""Git From Scratch — stage 5: The tree, written: the whole working tree,
bottom-up.

`write-tree` is the stage where git's object model earns its name: every
file becomes a blob, every directory becomes a tree of its entries sorted
as git sorts them — files by name, directories by `name/` — and the root
tree's sha is the whole working tree's name. The sort is the law (§1.9):
a tree written in any other order has a hash real git does not share, and
a hash real git does not share is a tree real git will not read.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why write the subtree before the parent rather than
collect and write after?
Because the parent's entry needs the subtree's *hash*, and the hash needs
the subtree's bytes: a bottom-up walk answers each sha at the moment it
exists, and the root's answer is the last line of a chain where every link
is already in the store. A collect-first walk needs a second pass and
carries the whole tree in memory to do what the recursion already knows.

DESIGN DECISION — why is `entry_sort_key` a public seam instead of an
inline sort?
Because it is the one line where git's byte-sort rule lives, and two
stages need it: stage 4's `ls_tree_names` sorts for the user, stage 5
sorts for the store. A rule with one definition and two callers cannot
drift — a rule pasted twice always does.

DESIGN DECISION — why does the stage write blobs itself rather than call
stage 3's `hash_object`?
It does not: `write_tree` goes through `hash_object`, because the store
is content-addressed and there is exactly one door. Writing a blob inline
would fork the hashing rule, and the first blob whose bytes disagree with
its name would be a tree nobody can prove.
"""

import repo as rp
import objects as ob
import stage_03 as s3
import stage_04 as s4


def entry_sort_key(name, is_dir):
    """The sort key: `name` for a file, `name + '/'` for a directory."""
    if is_dir and not name.endswith("/"):
        return name + "/"
    return name


def write_tree(repo, path="."):
    """The working tree from `path` written bottom-up; the root's sha."""
    fs = repo.fs
    path = "" if path in (".", "") else path.rstrip("/")
    names = fs.list(path)
    entries = []
    for name in names:
        if name == ".git/":
            continue
        full = path + "/" + name if path else name
        if name.endswith("/"):
            sub_sha = write_tree(repo, full.rstrip("/"))
            entries.append(("40000", name.rstrip("/"), sub_sha))
        else:
            data = fs.read(full)
            sha = s3.hash_object(repo, data)
            mode = "100755" if fs.is_exec(full) else "100644"
            entries.append((mode, name, sha))
    ordered = sorted(
        entries,
        key=lambda e: entry_sort_key(e[1], e[0] == "40000"))
    body = b""
    for (mode, name, sha_hex) in ordered:
        body += (mode.encode() + b" " + name.encode() + b"\x00"
                 + bytes.fromhex(sha_hex))
    sha = ob.sha1(ob.header("tree", len(body)) + body)
    path_in_store = repo.git_dir + "/" + ob.obj_path(sha)
    if not repo.fs.exists(path_in_store):
        repo.fs.write(path_in_store, ob.zlib_wrap("tree", body))
        repo._written += 1
    repo._hashed += 1
    return sha
