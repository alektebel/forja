"""Compression From Scratch — stage 3: Canonical Huffman: codes from lengths.

Huffman's tree gives each byte symbol a code whose width is that
symbol's frequency's due; the canonical rebuild takes only the widths and
deterministically assigns the codes — smallest width first, then by
symbol, each code one past its predecessor. `huffman_lengths` builds the
tree from counts, `canonical_codes` assigns from widths alone, and
`huffman_decode` reads the codes back: the format's both halves in one
stage, because a code you cannot decode is a cipher, not a compression.

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

import stage_01 as _s1
import heapq

#: the widest code the tree may produce — the count byte's arithmetic's
#: own ceiling for a 256-symbol alphabet's frequencies
MAX_CODE_WIDTH = 32


class EncodeError(ValueError):
    """Raised for anything the *encoder* got wrong — the caller's mistake."""


def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def huffman_lengths(data):
    """Per-symbol code lengths from the byte's own frequencies.

    The tree is built Huffman's way — two lightest nodes paired, ties
    broken by symbol ascending — and the lengths are the leaves' depths.
    One symbol alone gets width 1; an empty input gets all-zero widths."""
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", type(data).__name__)
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    lengths = [0] * 256
    live = [(counts[s], s) for s in range(256) if counts[s]]
    if not live:
        return tuple(lengths)
    if len(live) == 1:
        lengths[live[0][1]] = 1
        return tuple(lengths)
    # the tree: each node (weight, tiebreak, [symbols]) — the tiebreak is a
    # counter that keeps heapq honest and the pairing deterministic
    heap = []
    for seq, (weight, symbol) in enumerate(live):
        heap.append((weight, seq, [symbol]))
    heapq.heapify(heap)
    seq = len(heap)
    while len(heap) > 1:
        (w1, _s1_, syms1) = heapq.heappop(heap)
        (w2, _s2_, syms2) = heapq.heappop(heap)
        merged = syms1 + syms2
        heapq.heappush(heap, (w1 + w2, seq, merged))
        seq += 1
    # the survivors' depths are their code widths
    for depth, symbol in enumerate(heap[0][2]):
        pass
    # walk differently: re-derive depths by replaying the merge order —
    # each merge adds one to every symbol it swallowed
    depths = [0] * 256
    heap = []
    for i, (weight, symbol) in enumerate(live):
        heap.append((weight, i, [symbol]))
    heapq.heapify(heap)
    seq = len(heap)
    while len(heap) > 1:
        (w1, _a, syms1) = heapq.heappop(heap)
        (w2, _b, syms2) = heapq.heappop(heap)
        for symbol in syms1 + syms2:
            depths[symbol] += 1
        heapq.heappush(heap, (w1 + w2, seq, syms1 + syms2))
        seq += 1
    return tuple(depths)


def canonical_codes(lengths):
    """The canonical codes: by width, then by symbol, each one past.

    Answers a 256-tuple of `(code, width)`. Kraft's sum above one — widths
    that over-subscribe the code space — is refused, naming the law."""
    if not isinstance(lengths, tuple) or len(lengths) != 256:
        _refuse("bad_lengths", len(lengths) if isinstance(lengths, tuple)
                else type(lengths).__name__)
    # Kraft's sum in integers: scale to the widest width present
    used = 0
    scale = 1
    for width in lengths:
        if width > scale:
            scale = width
    for width in lengths:
        if width:
            used += 1 << (scale - width)
    if used > (1 << scale):
        _refuse("Kraft", used, scale)
    codes = [None] * 256
    ordered = sorted((width, symbol) for symbol, width in enumerate(lengths)
                     if width)
    codes = [(0, 0)] * 256
    prev_width = 0
    first = True
    for width, symbol in ordered:
        if first:
            code = 0
            prev_width = width
            first = False
        elif width != prev_width:
            code = (code + 1) << (width - prev_width)
            prev_width = width
        else:
            code += 1
        codes[symbol] = (code, width)
    return tuple(codes)


def huffman_encode(data):
    """The stream and the lengths that rebuild it: (bytes, lengths).

    Every byte's canonical code is appended through the stage 1 writer —
    LSB-first — so the stream the reader decodes is the stream this wrote."""
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", type(data).__name__)
    lengths = huffman_lengths(data)
    codes = canonical_codes(lengths)
    writer = _s1.BitWriter()
    for byte in data:
        (code, width) = codes[byte]
        # the stream is MSB-first within a code (the tree's path from the
        # root), written LSB-first into the byte stream — the reverse the
        # reader undoes
        writer.append(_reverse_bits(code, width), width)
    return writer.bytes(), lengths


def huffman_decode(data, lengths, size):
    """The lengths' codes read back; a code that runs past a leaf refuses.

    `size` symbols are read; a stream too short to feed the size, a size
    below zero, or bits that walk past the widest leaf are refused — never
    guessed."""
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        _refuse("bad_size", size)
    codes = canonical_codes(lengths)
    # the decode table: (width, code) -> symbol, walked bit by bit
    widest = max((width for (_c, width) in codes if width), default=0)
    table = {}
    for symbol, (code, width) in enumerate(codes):
        if width:
            # the stream carries the code MSB-of-code first (the path from
            # the root); the reader delivers bits LSB-first, so the running
            # value accumulates the code's bits high-first
            table[(width, _reverse_bits(code, width))] = symbol
    reader = _s1.BitReader(data) if hasattr(_s1, "BitReader") else None
    if reader is None:
        # a tiny reader over the stage 1 stream, the same LSB-first law
        class _R:
            def __init__(self, blob):
                self._blob = blob
                self._i = 0
                self._n = len(blob) * 8

            def read(self, width):
                if self._i + width > self._n:
                    _refuse("short_stream", self._i + width, self._n)
                value = 0
                for j in range(width):
                    byte = self._blob[(self._i + j) // 8]
                    value |= ((byte >> ((self._i + j) % 8)) & 1) << j
                self._i += width
                return value
        reader = _R(data)
    out = bytearray()
    for _ in range(size):
        run = 0
        width = 0
        symbol = None
        while symbol is None:
            if width > widest:
                _refuse("past_leaf", run)
            try:
                bit = reader.read(1)
            except EncodeError:
                _refuse("short_stream", size, len(out))
            run |= bit << width
            width += 1
            symbol = table.get((width, run))
        out.append(symbol)
    return bytes(out)


def _reverse_bits(value, width):
    """The code's bits, root-first, as the stream's LSB-first run."""
    out = 0
    for bit in range(width):
        if (value >> (width - 1 - bit)) & 1:
            out |= 1 << bit
    return out
