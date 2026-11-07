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
"""

import zstdref as _zr
import stage_07 as _s7
import inflate as _inflate

MAGIC = _zr.MAGIC
BLOCK_RAW = _zr.BLOCK_RAW
BLOCK_RLE = _zr.BLOCK_RLE
BLOCK_COMPRESSED = _zr.BLOCK_COMPRESSED
BLOCK_SIZE = _zr.BLOCK_SIZE
MODES = ("raw", "rle", "compressed")


class EncodeError(ValueError):
    """Raised for anything the *encoder* got wrong — the caller's mistake."""


def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def _chunks(data):
    """The content's BLOCK_SIZE chunks, the last short as it falls."""
    return [data[start:start + BLOCK_SIZE]
            for start in range(0, len(data), BLOCK_SIZE)]


def _block_for(chunk, mode):
    """One chunk's block: (kind, payload) under the named mode.

    raw: the bytes verbatim. rle: the RLE kind only for a whole
    BLOCK_SIZE run of one byte — one byte on the wire — anything else
    raw. compressed: the cheapest deflate block, spent only when it
    beats the raw ride; a full block of noise has no mode under
    BLOCK_SIZE (stored alone is five over) and rides raw."""
    if mode == "rle":
        if len(chunk) == BLOCK_SIZE and chunk == chunk[:1] * BLOCK_SIZE:
            return (BLOCK_RLE, chunk[:1])
        return (BLOCK_RAW, chunk)
    if mode == "compressed":
        best = None
        for deflate_mode in _s7.MODES:
            payload = _s7.deflate_block(chunk, deflate_mode)
            if best is None or len(payload) < len(best):
                best = payload
        if best is not None and len(best) < len(chunk):
            return (BLOCK_COMPRESSED, best)
        return (BLOCK_RAW, chunk)
    return (BLOCK_RAW, chunk)


def frame_encode(data, mode):
    """Magic, header, blocks in the named codec, the content's checksum.

    The header: the 3-byte little-endian content size, the block-size
    byte (12 names 4096), the flags byte 0. Each block: a kind byte, a
    3-byte little-endian payload size, the payload. The checksum rides
    the content's hash — the frame's one integrity."""
    if mode not in MODES:
        _refuse("bad_mode", mode)
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", data)
    data = bytes(data)
    if len(data) > 0xFFFFFF:
        _refuse("too_big", 0xFFFFFF, len(data))
    out = bytearray(MAGIC)
    out += len(data).to_bytes(3, "little")
    out.append(12)                 # the block-size byte: 2^12 = 4096
    out.append(0)                  # the flags: only 0 is defined
    for chunk in _chunks(data):
        (kind, payload) = _block_for(chunk, mode)
        out.append(kind)
        out += len(payload).to_bytes(3, "little")
        out += payload
    out += _zr.checksum(data).to_bytes(4, "little")
    return bytes(out)


def frame_decode(data):
    """The frame read back; the checksum's refusal is its signature.

    The header's magic, flags and block-size byte are the frame's; a
    block's payload may not overrun the frame; the blocks must write
    exactly the header's content size; a compressed block's deflate
    stream must reach its content's last byte; and the checksum must
    match the content's hash. Every refusal names its law."""
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", data)
    data = bytes(data)
    if len(data) < 12:
        _refuse("frame_too_short", 12, len(data))
    if data[:4] != MAGIC:
        _refuse("bad_magic", data[:4])
    content_size = int.from_bytes(data[4:7], "little")
    if data[7] != 12:
        _refuse("bad_block_size", data[7])
    if data[8] != 0:
        _refuse("bad_flags", data[8])
    at = 9
    out = bytearray()
    while at < len(data) - 4:
        kind = data[at]
        if kind not in (BLOCK_RAW, BLOCK_RLE, BLOCK_COMPRESSED):
            _refuse("bad_kind", kind)
        if at + 4 > len(data) - 4:
            _refuse("header_overruns", at)
        size = int.from_bytes(data[at + 1:at + 4], "little")
        if size > BLOCK_SIZE:
            _refuse("block_too_big", size, BLOCK_SIZE)
        if at + 4 + size > len(data) - 4:
            _refuse("content_overruns", size, len(data) - 4 - at - 4)
        payload = data[at + 4:at + 4 + size]
        at += 4 + size
        if kind == BLOCK_RAW:
            out += payload
        elif kind == BLOCK_RLE:
            if size != 1:
                _refuse("bad_rle_size", size)
            out += payload * BLOCK_SIZE
        else:
            try:
                (chunk, bits) = _inflate.inflate(payload)
            except _inflate.InflateError as problem:
                _refuse("bad_deflate", problem)
            if bits <= (len(payload) - 1) * 8:
                _refuse("stream_short_of_content", bits, len(payload))
            out += chunk
    if len(out) != content_size:
        _refuse("header_lies", content_size, len(out))
    stored = int.from_bytes(data[len(data) - 4:], "little")
    if _zr.checksum(bytes(out)) != stored:
        _refuse("checksum", stored, _zr.checksum(bytes(out)))
    return bytes(out)
