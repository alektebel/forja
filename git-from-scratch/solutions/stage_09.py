"""Git From Scratch — stage 9: The packfile: many objects, one file,
deltas to apply.

A pack is the store compressed to a single file: `PACK`, a version, a
count, then the objects — each with a varint header that hides the type
in its first byte and the size in the low four bits plus seven more per
continuation byte. Four types unpack directly; two are deltas — `ofs` and
`ref` — that name a base object and a delta script of `copy` and `insert`
instructions whose own sizes use the same sneaky varint. Reading a pack
without the header is reading a bundle of bytes nobody can name.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why is `apply_delta` a public seam?
Because it is the one operation where a reader can be wrong and still
answer: a copy range that runs past the base, a result size that lies,
an insert shorter than it claims — each is a pack that decodes to
something. The seam gives the check a door: plant each script, prove the
refusal, and the reader above inherits the proof.

DESIGN DECISION — why resolve ref-deltas against objects already in the
store and ofs-deltas against the pack's own objects?
Because the two encodings make different promises: an ofs-delta names its
base by *distance backwards*, which only means anything inside one file,
while a ref-delta names its base by sha, which means anything the store
holds. A reader that answered one with the other's rule would decode the
fixture's chain into a commit that never was.

DESIGN DECISION — why answer every object as `(type, body)` pairs and
verify the pack's checksum?
Because the checksum is the pack's one self-claim, and the type is each
object's: a pack whose tail sha disagrees is a truncated transfer, and a
type read wrong turns a tree into a blob nobody notices. Both cost one
comparison; the failure they prevent is silent corruption.
"""

import repo as rp
import objects as ob

PACK_KEYS = ("count", "objects")

_TYPES = ("commit", "tree", "blob", "tag")


def _varint(data, at):
    """The sneaky varint: 4 size bits first, then 7 per continuation."""
    byte = data[at]
    value = byte & 0x0F
    shift = 4
    while byte & 0x80:
        at += 1
        byte = data[at]
        value |= (byte & 0x7F) << shift
        shift += 7
    return value, at + 1


def _plain_varint(data, at):
    """The delta header's varint: plain 7 bits per continuation byte."""
    value = 0
    shift = 0
    while True:
        byte = data[at]
        at += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, at


def apply_delta(base, delta):
    """The delta script applied: copy and insert, sizes verified."""
    at = 0
    base_size, at = _plain_varint(delta, at)
    if base_size != len(base):
        raise rp.GitError("apply_delta: the script says the base is %d "
                          "bytes, it is %d" % (base_size, len(base)))
    result_size, at = _plain_varint(delta, at)
    out = bytearray()
    while at < len(delta):
        op = delta[at]
        at += 1
        if op & 0x80:                      # copy from the base
            offset = 0
            size = 0
            for i in range(4):
                if op & (1 << i):
                    offset |= delta[at] << (8 * i)
                    at += 1
            for i in range(3):
                if op & (0x10 << i):
                    size |= delta[at] << (8 * i)
                    at += 1
            if size == 0:
                size = 0x10000
            if offset + size > len(base):
                raise rp.GitError("apply_delta: a copy reads [%d, %d) from "
                                  "a %d-byte base"
                                  % (offset, offset + size, len(base)))
            out += base[offset:offset + size]
        elif op:                           # insert the next op bytes
            chunk = delta[at:at + op]
            if len(chunk) < op:
                raise rp.GitError("apply_delta: an insert claims %d bytes, "
                                  "the script has %d" % (op, len(chunk)))
            out += chunk
            at += op
        else:
            raise rp.GitError("apply_delta: opcode 0x00")
    if len(out) != result_size:
        raise rp.GitError("apply_delta: the script says the result is %d "
                          "bytes, it built %d" % (result_size, len(out)))
    return bytes(out)


def _inflate(data, at):
    """The zlib body starting at `at`, and the offset past it."""
    import zlib
    engine = zlib.decompressobj()
    body = engine.decompress(data[at:])
    return body, at + (len(data[at:]) - len(engine.unused_data))


def read_pack(repo, data):
    """Every object the pack holds, deltas applied, checksum verified."""
    if data[:4] != b"PACK":
        raise rp.GitError("read_pack: the magic is %r, not PACK"
                          % (data[:4],))
    version = int.from_bytes(data[4:8], "big")
    if version not in (2, 3):
        raise rp.GitError("read_pack: version %d" % (version,))
    count = int.from_bytes(data[8:12], "big")
    objects = []                          # (type_num, body) in pack order
    by_sha = {}                           # the pack's own, named
    at = 12
    for _i in range(count):
        start = at
        type_bits = (data[at] >> 4) & 0x07
        _size, at = _varint(data, at)
        if type_bits <= 4:
            body, at = _inflate(data, at)
            objects.append((type_bits, body))
            sha = ob.sha1(ob.header(_TYPES[type_bits - 1], len(body)) + body)
            by_sha[sha] = (type_bits, body)
        elif type_bits == 6:               # ofs-delta: distance backwards
            base_distance = 0
            byte = data[at]
            at += 1
            while byte & 0x80:
                base_distance = ((base_distance + 1) << 7) | (byte & 0x7F)
                byte = data[at]
                at += 1
            base_distance |= byte & 0x7F
            base_index = (start - 12 - base_distance)
            if base_index < 0 or base_index >= len(objects):
                raise rp.GitError("read_pack: an ofs-delta names base at "
                                  "%d of %d objects"
                                  % (base_index, len(objects)))
            base_num, base_body = objects[base_index]
            script, at = _inflate(data, at)
            result = apply_delta(base_body, script)
            objects.append((base_num, result))
            sha = ob.sha1(ob.header(_TYPES[base_num - 1], len(result))
                          + result)
            by_sha[sha] = (base_num, result)
        elif type_bits == 7:               # ref-delta: base by sha
            base_sha = data[at:at + 20].hex()
            at += 20
            if base_sha in by_sha:
                base = by_sha[base_sha]
            else:
                base = _lookup(repo, base_sha)
            script, at = _inflate(data, at)
            result = apply_delta(base[1], script)
            objects.append((base[0], result))
            sha = ob.sha1(ob.header(_TYPES[base[0] - 1], len(result))
                          + result)
            by_sha[sha] = (base[0], result)
        else:
            raise rp.GitError("read_pack: type %d" % (type_bits,))
    checksum = data[len(data) - 20:].hex()
    if ob.sha1(data[:len(data) - 20]) != checksum:
        raise rp.GitError("read_pack: the tail sha disagrees")
    return {"count": count,
            "objects": tuple((_TYPES[num - 1], body)
                             for (num, body) in objects)}


def _lookup(repo, sha):
    """A ref-delta's base: the store's object, as (type_num, body)."""
    kinds = {"commit": 1, "tree": 2, "blob": 3, "tag": 4}
    kind, body = repo.object_read(sha)
    return (kinds[kind], body)
