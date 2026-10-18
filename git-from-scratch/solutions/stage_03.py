"""Git From Scratch — stage 3: The blob, written: the hash is the
content's name.

`hash-object -w` is the store's door from the other side: build the header,
hash `header + body` with SHA-1, write the zlib bytes at the fanout path —
`objects/<2 hex>/<38 hex>` — and answer the 40-hex name. The law (contract
§1.8) is that the name is *computed*, never invented: the same body is the
same hash in this store, in real git's, and in every store either ever
touches, which is exactly why a sha can cross between them as a promise.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why does the check hold the stage's write against the
world's `repo.object_write` byte for byte?
Because the object store is the course's first concurrency with real git:
every later stage's objects land in the same directory, and a writer whose
hash disagreed with its own bytes would poison the store silently — the
name would answer, the content would not match. Same hash, same file, or
the stage does not ship.

DESIGN DECISION — why is `KNOWN_BLOBS` pinned to real git's hashes?
Because the law's proof is not that the stage agrees with itself: the
empty blob's `e69de29b…` and `hello world\\n`'s `3b18e512…` are hashes real
git computed over the same rule, and matching them is the strongest
statement a stage this small can make — the rule is git's rule, not ours.

DESIGN DECISION — why does an existing object not rewrite its file?
Because the store is content-addressed: a hash names one content, so a
second write of the same body is the same file by definition. Writing it
again is harmless but meaningless; skipping it is what the store's own
`written` counter records, and the check holds that counter against the
law — two writes of one body, one file.
"""

import repo as rp
import objects as ob


def hash_object(repo, data):
    """The blob written at its fanout path; the sha is the answer."""
    head = ob.header("blob", len(data))
    sha = ob.sha1(head + data)
    path = repo.git_dir + "/" + ob.obj_path(sha)
    if not repo.fs.exists(path):
        repo.fs.write(path, ob.zlib_wrap("blob", data))
        repo._written += 1
    repo._hashed += 1
    return sha
