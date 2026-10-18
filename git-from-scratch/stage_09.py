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

PACK_KEYS = ("count", "objects")


def apply_delta(base, delta):
    """The delta script applied: copy and insert, sizes verified."""
    raise NotImplementedError("stage 9: implement apply_delta()")


def read_pack(repo, data):
    """Every object the pack holds, deltas applied, checksum verified."""
    raise NotImplementedError("stage 9: implement read_pack()")
