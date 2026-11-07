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
"""

#: the format's own window: the offset is two bytes, little-endian
WINDOW = 65535
#: the shortest match the format pays for (the token adds four)
MIN_MATCH = 4
#: the longest match one sequence can name
MAX_MATCH = WINDOW


class EncodeError(ValueError):
    """Raised for anything the *encoder* got wrong — the caller's mistake."""


def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def _write_length(out, nibble_in_token, length):
    """A length in the LZ4 idiom: the token's nibble, then 255-bytes.

    Answers the nibble to put in the token and appends the extension
    bytes. A nibble of 15 says "keep reading 255s"; anything under 15 is
    the whole length."""
    if length < 15:
        out.append(length)
        return length
    out.append(15)
    rest = length - 15
    while rest >= 255:
        out.append(255)
        rest -= 255
    out.append(rest)
    return 15




def lz4_block_encode(data):
    """The block format's tokens, literals, offsets — the last sequence
    literals-only.

    LZ77 matching through stage 5's engine at the format's window, then
    the LZ4 byte budget: literal runs of any size, matches of four to
    MAX_MATCH, the little-endian two-byte offset, 255-extensions for the
    lengths past fifteen. A caller mistake about the input type is
    refused; the bytes are always what the reference decoder means."""
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", type(data).__name__)
    data = bytes(data)
    if not data:
        return b""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        # the literals this sequence carries: everything until the next
        # usable match
        lit_start = i
        match = None
        while i < n:
            best_len = 0
            best_dist = 0
            low = max(0, i - WINDOW)
            for start in range(i - 1, low - 1, -1):
                length = 0
                limit = min(MAX_MATCH, n - i - 1)
                while (length < limit
                       and data[start + length] == data[i + length]):
                    length += 1
                if length > best_len:
                    best_len = length
                    best_dist = i - start
                    if best_len >= limit:
                        break
            if best_len >= MIN_MATCH:
                match = (best_len, best_dist)
                break
            i += 1
        literals = data[lit_start:i]
        if match is None:
            # the last sequence: literals only
            token_byte = bytearray()
            nibble = _write_length(token_byte, 0, len(literals))
            out.append(nibble << 4)
            out += token_byte[1:]
            out += literals
            break
        # the token's own byte plus the extensions
        token = bytearray()
        lit_nibble = _write_length(token, 0, len(literals))
        length = match[0]
        match_nibble = length - 4 if length - 4 < 15 else 15
        out.append((lit_nibble << 4) | match_nibble)
        out += token[1:]
        out += literals
        (length, distance) = match
        out.append(distance & 0xFF)
        out.append((distance >> 8) & 0xFF)
        extra = length - 4
        if extra >= 15:
            rest = extra - 15
            while rest >= 255:
                out.append(255)
                rest -= 255
            out.append(rest)
        i += length
    return bytes(out)
