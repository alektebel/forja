"""Compression From Scratch — stage 3: Canonical Huffman: codes from lengths.

Huffman's tree gives each byte symbol a code whose width is that
symbol's frequency's due; the canonical rebuild takes only the widths and
deterministically assigns the codes — smallest width first, then by
symbol, each code one past its predecessor. `huffman_lengths` builds the
tree from counts, `canonical_codes` assigns from widths alone, and
`huffman_decode` reads the codes back: the format's both halves in one
stage, because a code you cannot decode is a cipher, not a compression.

TODO: implement each function; the docstring is the contract.

DESIGN DECISION — why ship the lengths rather than the tree?
Because the canonical form's whole point is that the lengths ARE the
code: the decoder rebuilds exactly what the encoder built from a table
that fits in 256 bytes. A format that shipped the tree would ship a
pointer graph; a format that ships lengths ships arithmetic.

DESIGN DECISION — why is `canonical_codes` deterministic given lengths
alone?
Because two encoders given the same lengths must produce byte-identical
streams — the determinism the course is judged on — and the canonical
order (by width, then by symbol) is the one assignment that makes that
true without any extra state.

DESIGN DECISION — why decode in stage 3 rather than a provided reader?
Because Huffman's decode is the same table walk the encoder does in
reverse, and seeing both at once is what makes the format legible:
`huffman_decode` refusing a code that runs past a leaf is the same law
as `canonical_codes` refusing Kraft's sum above one.
"""

import stage_01 as s1


class EncodeError(ValueError):
    """A caller's mistake: the refusal names the offender."""


def huffman_lengths(data):
    """Per-symbol code lengths from the byte's own frequencies."""
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    lengths = [0] * 256
    live = [symbol for symbol in range(256) if counts[symbol]]
    if not live:
        return tuple(lengths)
    if len(live) == 1:
        # One symbol alone gets width 1: a width-0 code encodes nothing
        # and a decoder could never read the byte back.
        lengths[live[0]] = 1
        return tuple(lengths)
    # The tree, built by hand: leaves 0..255 keep their symbol as their
    # tie-break, internals are numbered on from 256, so the two smallest
    # (weight, id) are always picked deterministically.
    weight = list(counts)
    children = {}
    active = list(live)
    nxt = 256
    while len(active) > 1:
        left = min(active, key=lambda node: (weight[node], node))
        active.remove(left)
        right = min(active, key=lambda node: (weight[node], node))
        active.remove(right)
        weight.append(weight[left] + weight[right])
        children[nxt] = (left, right)
        active.append(nxt)
        nxt += 1
    stack = [(active[0], 0)]
    while stack:
        node, depth = stack.pop()
        if node < 256:
            lengths[node] = depth
        else:
            low, high = children[node]
            stack.append((low, depth + 1))
            stack.append((high, depth + 1))
    return tuple(lengths)


def canonical_codes(lengths):
    """The canonical codes: by width, then by symbol, each one past."""
    if len(lengths) != 256:
        raise EncodeError("canonical_codes: expected 256 lengths, got %d"
                          % (len(lengths),))
    counts = [0] * 64
    max_width = 0
    for width in lengths:
        if width < 0:
            raise EncodeError("canonical_codes: negative width %d"
                              % (width,))
        if width >= 64:
            raise EncodeError("canonical_codes: width %d outruns the table"
                              % (width,))
        if width:
            counts[width] += 1
            max_width = max(max_width, width)
    if max_width:
        # Kraft's sum as integers: sum(2**(max_width - w)) against 2**max_width.
        used = 0
        for width in range(1, max_width + 1):
            used += counts[width] << (max_width - width)
        if used > (1 << max_width):
            raise EncodeError("canonical_codes: Kraft's sum above one "
                              "(%d over %d)" % (used, 1 << max_width))
    first = [0] * 64
    code = 0
    for width in range(1, max_width + 1):
        code = (code + counts[width - 1]) << 1
        first[width] = code
    codes = [(0, 0)] * 256
    for width in range(1, max_width + 1):
        for symbol in range(256):
            if lengths[symbol] == width:
                codes[symbol] = (first[width], width)
                first[width] += 1
    return tuple(codes)


def huffman_encode(data):
    """The stream and the lengths that rebuild it: (bytes, lengths)."""
    lengths = huffman_lengths(data)
    if not data:
        return (b"", lengths)
    codes = canonical_codes(lengths)
    # The writer packs LSB-first, but a canonical code's prefix law
    # holds on its bits read MSB-of-code first — so the encoder writes
    # each code's bits reversed (the code's high bit lands first in the
    # stream), and the decoder's accumulation rebuilds the code itself.
    writer = s1.BitWriter()
    for byte in data:
        code, width = codes[byte]
        reversed_code = 0
        for bit in range(width):
            if (code >> bit) & 1:
                reversed_code |= 1 << (width - 1 - bit)
        writer.append(reversed_code, width)
    return (writer.bytes(), lengths)


def huffman_decode(data, lengths, size):
    """The lengths' codes read back; a code that runs past a leaf refuses."""
    if size < 0:
        raise EncodeError("huffman_decode: negative size %d" % (size,))
    codes = canonical_codes(lengths)
    # The stream holds each code's bits MSB-of-code first; reading one
    # bit at a time and accumulating MSB-first rebuilds the canonical
    # code. The leaves are keyed by (width, code) — exactly what the
    # accumulation holds at the moment a leaf is reached.
    leaves = {}
    max_width = 0
    for symbol in range(256):
        code, width = codes[symbol]
        if not width:
            continue
        leaves[(width, code)] = symbol
        max_width = max(max_width, width)
    out = bytearray()
    current = 0
    width = 0
    total = len(data) * 8
    pos = 0
    while len(out) < size:
        if pos >= total:
            raise EncodeError(
                "huffman_decode: the stream ends after %d of %d symbols"
                % (len(out), size))
        bit = (data[pos >> 3] >> (pos & 7)) & 1
        pos += 1
        current = (current << 1) | bit
        width += 1
        symbol = leaves.get((width, current))
        if symbol is not None:
            out.append(symbol)
            current = 0
            width = 0
        elif width > max_width:
            raise EncodeError(
                "huffman_decode: a code runs past a leaf at bit %d"
                % (pos - 1))
    return bytes(out)
