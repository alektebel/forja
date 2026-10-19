"""Compression From Scratch — stage 9: The frame: a header, blocks, and a checksum.

The frame is the course's container: a magic, a header that names the
content's size, blocks of the codec the stage's mode names, and a
checksum over the content — the one integrity the frame owns.
`frame_encode` writes it; `frame_decode` reads it back; the reference
`zstdref.frame_decode` is the judge. One flipped bit anywhere must be
noticed — that is the checksum's law and the check's own bit flip.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why a checksum over the content rather than the frame?
Because the frame is the container and the content is the cargo: a
checksum over the frame would change when the block layout changed
without the content changing, and the reader's guarantee is about the
cargo. The reference checks the content, and the encoder must too.

DESIGN DECISION — why does the compressed block carry its own size?
Because the reader must know where the block ends before it decodes: a
decoder that searched for the end would be a parser, not a reader. The
size is the frame's one gift to the decoder and the stage writes it.

DESIGN DECISION — why is the flipped bit the check's own case?
Because a checksum that is never tested is a comment: the check flips
one bit in a real frame and holds the reader's refusal — the only proof
that the checksum notices anything at all.
"""

def frame_encode(data, mode):
    """Magic, header, blocks in the named codec, the content's checksum."""
    raise NotImplementedError("stage 9: implement frame_encode()")


def frame_decode(data):
    """The frame read back; the checksum's refusal is its signature."""
    raise NotImplementedError("stage 9: implement frame_decode()")
