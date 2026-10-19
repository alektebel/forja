"""Compression From Scratch — the reference frame reader: the course's
own frame, judged.

The frame is the course's container: a 4-byte magic, a 3-byte header
(frame content size, little-endian; a block-size byte; a flags byte), then
blocks — each a 1-byte kind (0 raw, 1 RLE, 2 compressed), a 3-byte
little-endian content size, and the content — then a 4-byte checksum of
the *content* (a fixed-word checksum, xxhash-style: the same arithmetic
`zstdref.checksum` spells out). `frame_decode` accepts only frames whose
checksum matches what the content hashes to; one flipped bit anywhere is
noticed.

This module is provided; its digest is pinned and it is never edited to
make a stage pass.
"""

MAGIC = b"\x28\xb5\x2f\xfd"
BLOCK_RAW = 0
BLOCK_RLE = 1
BLOCK_COMPRESSED = 2
BLOCK_SIZE = 4096

_PRIME = 2654435761


def checksum(data):
    """The frame's checksum: a fixed-word FNV-style fold of the content.

    Four 32-bit lanes, each folded over the prime, XOR-folded into one
    word — cheap, deterministic, and enough that one flipped bit anywhere
    in the content changes the word.
    """
    lanes = [0, 0, 0, 0]
    for i, byte in enumerate(data):
        lane = i & 3
        lanes[lane] = ((lanes[lane] + byte) * _PRIME) & 0xFFFFFFFF
        lanes[lane] ^= lanes[lane] >> 15
    word = (lanes[0] ^ lanes[1] ^ lanes[2] ^ lanes[3]) & 0xFFFFFFFF
    return word


class FrameError(ValueError):
    """The reader's one refusal: what the frame forbids."""


def frame_decode(data):
    """A frame decoded: the bytes it holds.

    Strict: the magic must be the course's, the flags byte must be 0 (no
    dictionary, no reserved bits), every block's content must fit the
    frame content size, the checksum must match, and nothing may run past
    the frame.
    """
    if len(data) < 12:
        raise FrameError("frame: a frame is at least 12 bytes, this is %d"
                         % (len(data),))
    if data[:4] != MAGIC:
        raise FrameError("frame: the magic is %r, not the frame's"
                         % (data[:4],))
    content_size = int.from_bytes(data[4:7], "little")
    block_size_code = data[7]
    flags = data[8]
    if flags != 0:
        raise FrameError("frame: the flags byte is %d, only 0 is defined"
                         % (flags,))
    at = 9
    out = bytearray()
    while at < len(data) - 4:
        kind = data[at]
        at += 1
        if at + 3 > len(data):
            raise FrameError("frame: a block header is cut off")
        size = int.from_bytes(data[at:at + 3], "little")
        at += 3
        if size > BLOCK_SIZE:
            raise FrameError("frame: a block of %d bytes exceeds the "
                             "frame's block size %d" % (size, BLOCK_SIZE))
        if at + size > len(data) - 4:
            raise FrameError("frame: a block's content is cut off")
        content = data[at:at + size]
        at += size
        if kind == BLOCK_RAW:
            out += content
        elif kind == BLOCK_RLE:
            if size != 1:
                raise FrameError("frame: an RLE block's content is %d "
                                 "bytes, exactly 1" % (size,))
            out += content * BLOCK_SIZE
        elif kind == BLOCK_COMPRESSED:
            raise FrameError("frame: the reference reader does not carry "
                             "the course's compressed blocks — the stage's "
                             "own reader decodes those")
        else:
            raise FrameError("frame: block kind %d" % (kind,))
    if len(out) != content_size:
        raise FrameError("frame: the header says %d bytes, the blocks "
                         "wrote %d" % (content_size, len(out)))
    stored = int.from_bytes(data[len(data) - 4:], "little")
    if checksum(bytes(out)) != stored:
        raise FrameError("frame: the checksum disagrees")
    return bytes(out)
