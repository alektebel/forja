"""Compression From Scratch — stage 6: LZ4's block format: nibbles and extensions.

LZ4's block format is LZ77 with a byte budget: a token whose high
nibble is the literal length and low nibble the match length, 255-bytes
for the extensions, the literals inline, a little-endian two-byte offset —
and the last sequence literals-only. `lz4_block_encode` writes it; the
reference `lz4ref.lz4_block_decode` is the judge, and the ratio bars are
the world's.

DESIGN DECISION — why is the reference decoder the judge rather than the
stage's own decoder?
Because LZ4 is a format that exists outside this course, and the one
fact that matters is that the bytes a stage writes are the bytes real
LZ4 means: the reference decoder is that fact, strict where the spec is
strict. A stage's own decoder proves nothing about interop.

DESIGN DECISION — why does the token put both nibbles in one byte?
Because most sequences are small: one byte covers the common case, the
255-extension only when a length exceeds fifteen. The format's economy
is the token's — and the check holds the ratio bar that proves it.

DESIGN DECISION — why must the last sequence end literals-only?
Because a match that names no bytes after it is a match the decoder
cannot bound: the trailing literals are where the format says "this is
the end". The reference refuses anything else, and the encoder that
tries one is refused too.

DESIGN DECISION — why does the encoder lean on stage 5's stream rather
than match again?
Because LZ4's block IS LZ77 with a byte budget: the window is 64 KiB
(the offset's two bytes), a match pays for four, and the greedy
longest-match stream is already pinned. The stage's work is the
budget's arithmetic — nibbles, extensions, the offset's endianness —
not a second matcher.
"""

import stage_05 as s5

#: the offset is two bytes little-endian, so no distance past 65535
#: can be named — the window is the format's own law, not a choice
WINDOW = 65535

#: the smallest match that can pay: the token's low nibble is the
#: match length minus 4, so a pair is never worth fewer than four
MIN_MATCH = 4

#: the stream's pairs are capped only by the data's own length — the
#: 255-extension chain climbs as high as the match reaches
MAX_MATCH = 1 << 30


class EncodeError(ValueError):
    """A caller's mistake: the refusal names the offender."""


def _append_extension(out, extra):
    """A length's 255-bytes: every full 255 is one byte, the tail ends
    the chain. The caller has already subtracted the nibble's fifteen."""
    while extra >= 255:
        out.append(255)
        extra -= 255
    out.append(extra)


def _emit_sequence(out, literals, length, distance):
    """One full sequence: token, extensions, literals, the offset."""
    literal_length = len(literals)
    match_nibble = length - 4
    token = ((literal_length if literal_length < 15 else 15) << 4) | \
        (match_nibble if match_nibble < 15 else 15)
    out.append(token)
    if literal_length >= 15:
        _append_extension(out, literal_length - 15)
    out += literals
    out.append(distance & 0xFF)
    out.append((distance >> 8) & 0xFF)
    if match_nibble >= 15:
        _append_extension(out, match_nibble - 15)


def _emit_last_sequence(out, literals):
    """The last sequence: token and literals only — the low nibble is
    zero and nothing follows, the format's own ending."""
    literal_length = len(literals)
    out.append((literal_length if literal_length < 15 else 15) << 4)
    if literal_length >= 15:
        _append_extension(out, literal_length - 15)
    out += literals


def lz4_block_encode(data):
    """The block format's tokens, literals, offsets — the last sequence
    literals-only."""
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise EncodeError(
            "lz4_block_encode: data is %s, not bytes"
            % (type(data).__name__,))
    data = bytes(data)
    out = bytearray()
    if not data:
        return bytes(out)
    stream = s5.lz77_encode(data, WINDOW, MIN_MATCH, MAX_MATCH)
    literals = bytearray()
    count = len(stream)
    for index, item in enumerate(stream):
        last = index == count - 1
        if isinstance(item, int):
            literals.append(item)
            continue
        length, distance = item
        if last:
            # the last sequence is literals-only, so the final match
            # gives its last byte back as a literal and the stream ends
            # literals-only — or, too short to spare a byte, folds whole
            if length >= 5:
                _emit_sequence(out, literals, length - 1, distance)
                literals = bytearray(data[-1:])
            else:
                literals += data[-length:]
        else:
            _emit_sequence(out, literals, length, distance)
            literals = bytearray()
    if literals:
        _emit_last_sequence(out, literals)
    return bytes(out)
