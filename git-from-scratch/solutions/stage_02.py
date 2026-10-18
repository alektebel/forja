"""Git From Scratch — stage 2: The blob, read: a header, then its body.

An object file is zlib bytes; unwrapped, it is `"<type> <size>\0"` and then
the body. `cat-file -p` is the command that answers the body — and the
discipline is in what it refuses: a sha that names no file in the store is
named as missing, a header that says `tree` is named as the wrong type, and
a header that lies about its size is refused before any body is answered.
A reader that trusted the header would hand a truncated blob to a writer.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why does `read_header` refuse a size that disagrees with
the body?
Because the header is the object's self-description and the store is the
one place a lie costs everything: `git fsck` reads the same bytes real git
wrote, but a stage-written store holds stage-written objects, and a writer
that hashed one length and wrote another has corrupted the name's meaning.
The check plants such an object and the refusal must name the two counts.

DESIGN DECISION — why is the type checked in `cat_file` and not in
`read_header`?
Because the header's job is to *report* the type — stage 4 and stage 8 read
trees and commits through the same door and would find their objects
refused at the wrong altitude. `cat_file` owns the blob contract; the
header door owns only the grammar.

DESIGN DECISION — why answer bytes and never a str?
Because a blob is file content, and file content is bytes: encodings are
the caller's business, and a decode here would turn a binary fixture into
a UnicodeDecodeError instead of the bytes the user stored.
"""

import repo as rp
import objects as ob


def read_header(repo, sha):
    """`(type, size)` as the header reports them, grammar verified."""
    path = repo.git_dir + "/" + ob.obj_path(sha)
    if not repo.fs.exists(path):
        raise rp.GitError("read_header: no object %r" % (sha,))
    import zlib
    plain = zlib.decompress(repo.fs.read(path))
    kind, size, _body = ob.parse_header(plain)
    return kind, size


def cat_file(repo, sha):
    """The blob's body: unwrapped, type-verified, bytes."""
    kind, _size = read_header(repo, sha)
    if kind != "blob":
        raise rp.GitError("cat_file: %r is a %s, not a blob" % (sha, kind))
    return repo.object_read(sha)[1]
