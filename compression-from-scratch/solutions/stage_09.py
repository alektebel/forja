"""Compression From Scratch — stage 9: The frame: a header, blocks, and a checksum.

The frame is the course's container: a magic, a header that names the
content's size, blocks of the codec the stage's mode names, and a
checksum over the content — the one integrity the frame owns.
`frame_encode` writes it; `frame_decode` reads it back; the reference
`zstdref.frame_decode` is the judge. One flipped bit anywhere must be
noticed — that is the checksum's law and the check's own bit flip.

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

DESIGN DECISION — what does an rle-mode block's content MEAN?
Two readings were possible: the content is stage 2's marked encoding
(the caller's own `rle_encode` bytes) or the content is the ORIGINAL
chunk and the RLE kind is a promise about it. The reference settles
it: it expands an RLE block's one byte verbatim — handed the marked
bytes it would answer the wrong cargo — so the content is the original
chunk. The kind is spent only on a chunk that is exactly a whole
BLOCK_SIZE run of one byte (the pin, and the only way the frame's
arithmetic holds: a shorter run expanded by the kind's own law would
disagree with the header); every other chunk rides a raw block, its
bytes on the wire as they are. RLE mode on noise pays the same tax
raw pays: the kind is the run's discount, not a second codec.
"""

import inflate
import zstdref
import stage_01 as s1
import stage_07 as s7

#: the frame's magic, its block kinds, and its block size: the reference
#: frame's own constants, borrowed rather than spelled a second time
MAGIC = zstdref.MAGIC
BLOCK_RAW = zstdref.BLOCK_RAW
BLOCK_RLE = zstdref.BLOCK_RLE
BLOCK_COMPRESSED = zstdref.BLOCK_COMPRESSED
BLOCK_SIZE = zstdref.BLOCK_SIZE

#: the codecs a frame's blocks may speak, as the caller names them
MODES = ("raw", "rle", "compressed")

#: the block-size byte spells the block size as a power of two: 4096 is
#: two to the twelfth
_BLOCK_SIZE_CODE = BLOCK_SIZE.bit_length() - 1

#: the header's one flags byte: only zero is defined
_FLAGS = 0

#: the content-size field is three bytes wide: the most a frame holds
_CONTENT_MAX = (1 << 24) - 1


class EncodeError(ValueError):
    """A caller's or a frame's mistake, named."""


def _blocks(data):
    """The content's BLOCK_SIZE-sized chunks: the frame's own unit."""
    for start in range(0, len(data), BLOCK_SIZE):
        yield data[start:start + BLOCK_SIZE]


def _rle_block(chunk):
    """The rle mode's block for one chunk: the RLE kind only on the
    run the pin names (a whole BLOCK_SIZE of one byte), everything
    else raw — see the pinned choice in the module's docstring."""
    if len(chunk) == BLOCK_SIZE and chunk == chunk[:1] * BLOCK_SIZE:
        return BLOCK_RLE, chunk[:1]
    return BLOCK_RAW, chunk


def _compressed_block(chunk):
    """The compressed mode's block for one chunk: the payload is
    exactly what `s7.deflate_block` answers, in the smallest of its
    three modes. When no mode fits the frame's block size (a full
    block of noise: even stored is five bytes over), the chunk rides
    a raw block, the same escape the rle mode's pin gives a non-run."""
    blocks = []
    for mode in s7.MODES:
        payload = s7.deflate_block(chunk, mode)
        blocks.append((len(payload), mode, payload))
    blocks.sort(key=lambda item: (item[0], item[1]))
    payload = blocks[0][2]
    if len(payload) < len(chunk):
        return BLOCK_COMPRESSED, payload
    return BLOCK_RAW, chunk


_WRITERS = {"raw": lambda chunk: (BLOCK_RAW, chunk),
            "rle": _rle_block,
            "compressed": _compressed_block}


def frame_encode(data, mode):
    """Magic, header, blocks in the named codec, the content's checksum."""
    if not isinstance(data, (bytes, bytearray)):
        raise EncodeError(
            "frame_encode: the data %r is not bytes" % (data,))
    data = bytes(data)
    if mode not in _WRITERS:
        raise EncodeError("frame_encode: mode %r is not one of %s"
                          % (mode, ", ".join(MODES)))
    if len(data) > _CONTENT_MAX:
        raise EncodeError(
            "frame_encode: the content's %d bytes do not fit the "
            "header's three-byte size (%d at most)"
            % (len(data), _CONTENT_MAX))
    write = _WRITERS[mode]
    out = bytearray()
    out += MAGIC
    out += len(data).to_bytes(3, "little")
    out.append(_BLOCK_SIZE_CODE)
    out.append(_FLAGS)
    for chunk in _blocks(data):
        kind, content = write(chunk)
        if len(content) > BLOCK_SIZE:
            raise EncodeError(
                "frame_encode: a %s block's content is %d bytes, past "
                "the frame's block size %d"
                % (mode, len(content), BLOCK_SIZE))
        out.append(kind)
        out += len(content).to_bytes(3, "little")
        out += content
    out += zstdref.checksum(data).to_bytes(4, "little")
    return bytes(out)


def frame_decode(data):
    """The frame read back; the checksum's refusal is its signature."""
    data = bytes(data)
    if len(data) < 12:
        raise EncodeError("frame: a frame is at least 12 bytes, "
                             "this is %d" % (len(data),))
    if data[:4] != MAGIC:
        raise EncodeError("frame: the magic is %r, not the frame's"
                             % (data[:4],))
    content_size = int.from_bytes(data[4:7], "little")
    if data[7] != _BLOCK_SIZE_CODE:
        raise EncodeError(
            "frame: the block-size byte is %d, only %d (a %d-byte "
            "block) is defined"
            % (data[7], _BLOCK_SIZE_CODE, BLOCK_SIZE))
    if data[8] != _FLAGS:
        raise EncodeError("frame: the flags byte is %d, only %d is "
                             "defined" % (data[8], _FLAGS))
    at = 9
    out = bytearray()
    while at < len(data) - 4:
        kind = data[at]
        at += 1
        if at + 3 > len(data) - 4:
            raise EncodeError("frame: a block header is cut off")
        size = int.from_bytes(data[at:at + 3], "little")
        at += 3
        if size > BLOCK_SIZE:
            raise EncodeError("frame: a block of %d bytes exceeds "
                                 "the frame's block size %d"
                                 % (size, BLOCK_SIZE))
        if at + size > len(data) - 4:
            raise EncodeError(
                "frame: a block's content overruns the frame")
        content = data[at:at + size]
        at += size
        if kind == BLOCK_RAW:
            out += content
        elif kind == BLOCK_RLE:
            if size != 1:
                raise EncodeError("frame: an RLE block's content is "
                                     "%d bytes, exactly 1" % (size,))
            out += content * BLOCK_SIZE
        elif kind == BLOCK_COMPRESSED:
            decoded, bits = inflate.inflate(content)
            # the stream must reach into the content's last byte: the
            # bits after it are the writer's padding, bytes after it
            # are cargo nobody wrote
            if bits <= (len(content) - 1) * 8:
                raise EncodeError(
                    "frame: the deflate stream ends %d bits before the "
                    "block's content does"
                    % ((len(content) - 1) * 8 - bits,))
            out += decoded
        else:
            raise EncodeError("frame: block kind %d" % (kind,))
    if len(out) != content_size:
        raise EncodeError("frame: the header says %d bytes, the "
                             "blocks wrote %d" % (content_size, len(out)))
    stored = int.from_bytes(data[len(data) - 4:], "little")
    if zstdref.checksum(bytes(out)) != stored:
        raise EncodeError("frame: the checksum disagrees")
    return bytes(out)
