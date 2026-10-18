"""git-from-scratch — the object grammar's provided half.

One law owns this module: an object's name is
`sha1("<type> <size>\\0" + body)`, lowercased hex, 40 characters. Every
other shape here is that law's consequences — the fanout path, the zlib
wrap, the header's parse — and the modes a tree entry may carry.
"""

MODES = ("100644", "100755", "120000", "40000")
OBJ_TYPES = ("blob", "tree", "commit", "tag")


def sha1(data):
    """The content's name: SHA-1 over exactly these bytes, lowercase hex."""
    import hashlib
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("sha1: the data is bytes, not %r"
                        % (type(data).__name__,))
    return hashlib.sha1(bytes(data)).hexdigest()


def header(kind, size):
    """The pre-body bytes the hash is taken over: `<type> <size>\\0`."""
    if kind not in OBJ_TYPES:
        raise ValueError("header: %r is not an object type" % (kind,))
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ValueError("header: the size is a non-negative int, not %r"
                         % (size,))
    return ("%s %d\x00" % (kind, size)).encode()


def parse_header(raw):
    """`(type, size, body)` from unwrapped bytes, or a refusal."""
    nul = raw.find(b"\x00")
    if nul < 0:
        raise ValueError("parse_header: no NUL in the first bytes")
    head = raw[:nul]
    space = head.find(b" ")
    if space < 0:
        raise ValueError("parse_header: no type-size space in %r" % (head,))
    kind = head[:space].decode("ascii", "replace")
    size_text = head[space + 1:]
    if not size_text.isdigit():
        raise ValueError("parse_header: the size %r is not a number"
                         % (size_text,))
    body = raw[nul + 1:]
    if len(body) != int(size_text):
        raise ValueError("parse_header: the header says %s bytes, the body "
                         "has %d" % (size_text.decode(), len(body)))
    if kind not in OBJ_TYPES:
        raise ValueError("parse_header: %r is not an object type" % (kind,))
    return kind, int(size_text), body


def obj_path(sha):
    """The fanout path under .git/: `objects/<2 hex>/<38 hex>`."""
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise ValueError("obj_path: %r is not a 40-hex sha" % (sha,))
    return "objects/%s/%s" % (sha[:2], sha[2:])


def zlib_wrap(kind, body):
    """The object's on-disk bytes: the header and body, compressed."""
    import zlib
    return zlib.compress(header(kind, len(body)) + body)


def zlib_unwrap(raw):
    """`(type, body)` from on-disk bytes, or a refusal."""
    import zlib
    try:
        plain = zlib.decompress(raw)
    except zlib.error as err:
        raise ValueError("zlib_unwrap: not zlib data (%s)" % (err,))
    kind, _size, body = parse_header(plain)
    return kind, body


def entry_sort_key(name, is_dir):
    """Tree entries sort by name as raw bytes, directories as `name/`."""
    if is_dir and not name.endswith("/"):
        return name + "/"
    return name
