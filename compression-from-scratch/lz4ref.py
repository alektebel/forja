"""Compression From Scratch — the reference LZ4 block decoder: strict.

The judge for the LZ4 stage: a decoder that accepts exactly what the LZ4
block format allows and refuses everything else. Sequences of (token:
high nibble literal length, low nibble match length), extended lengths as
255-bytes, the literals, the little-endian offset, and the last sequence's
literals-only ending. The last match must start at least twelve bytes
before the end; the match cannot read before the output's start.

This module is provided; its digest is pinned and it is never edited to
make a stage pass.
"""


class Lz4Error(ValueError):
    """The decoder's one refusal: what the format forbids."""


def lz4_block_decode(data):
    """An LZ4 block decoded: the bytes it writes.

    Strict per the LZ4 block format: the last sequence carries only
    literals, every match's offset reaches into bytes the output already
    holds, and nothing runs past the block's end.
    """
    out = bytearray()
    at = 0
    if not data:
        return b""
    while at < len(data):
        token = data[at]
        at += 1
        literal_length = token >> 4
        if literal_length == 15:
            while True:
                if at >= len(data):
                    raise Lz4Error("lz4: the literal length runs past the "
                                   "block")
                extra = data[at]
                at += 1
                literal_length += extra
                if extra != 255:
                    break
        if at + literal_length > len(data):
            raise Lz4Error("lz4: the literals run past the block")
        out += data[at:at + literal_length]
        at += literal_length
        if at == len(data):
            break                      # the last sequence: literals only
        if at + 2 > len(data):
            raise Lz4Error("lz4: an offset is cut off")
        offset = data[at] | (data[at + 1] << 8)
        at += 2
        if offset == 0:
            raise Lz4Error("lz4: an offset of zero")
        if offset > len(out):
            raise Lz4Error("lz4: an offset of %d reaches before the "
                           "output's start (%d bytes)"
                           % (offset, len(out)))
        match_length = token & 0x0F
        if match_length == 15:
            while True:
                if at >= len(data):
                    raise Lz4Error("lz4: the match length runs past the "
                                   "block")
                extra = data[at]
                at += 1
                match_length += extra
                if extra != 255:
                    break
        match_length += 4
        if match_length > offset:
            # overlapping copy: byte by byte, the format's own semantics
            for _ in range(match_length):
                out.append(out[-offset])
        else:
            out += out[len(out) - offset:len(out) - offset + match_length]
    return bytes(out)
