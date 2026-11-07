"""Compression From Scratch — stage 7: DEFLATE: stored, fixed, dynamic.

DEFLATE is Huffman and LZ77 in one stream, with the choice the format
gives every block: stored (no compression, a length and its complement),
fixed (the RFC's own code), or dynamic (a code built for this block).
`deflate_block` writes one block in a named mode; `deflate` chooses per
block. The reference `inflate.inflate` is the judge, and the bars pin
what each mode must achieve.

DESIGN DECISION — why choose per block rather than once per stream?
Because the data changes: `RANDOM` has no code to build and the stored
block beats everything, `TEXT`'s dynamic tree pays for itself in the
first kilobyte. The per-block choice is the format's real economy, and
the check holds both sides of it.

DESIGN DECISION — why must the stored block's header carry LEN and its
complement?
Because a stored block is the one place the format has no other
integrity: the complement is the check that a truncated transfer did not
lose bytes. The reference refuses a LEN that is not NLEN's complement,
and the encoder writes the complement because the format says so.

DESIGN DECISION — why is the end-of-block symbol part of the stage's
law?
Because the symbol is the block's boundary inside a bitstream that has
no byte boundaries: without it the decoder would read into the next
block's tree. The reference refuses a dynamic tree with no
end-of-block code, and the encoder that omits one is refused too.
"""

import stage_01 as _s1

MODES = ("stored", "fixed", "dynamic")
STORED = 0
FIXED = 1
DYNAMIC = 2
FINAL = 1
LITERALS = 286
DISTANCES = 30
MAX_WIDTH = 15
END_OF_BLOCK = 256
WINDOW = 32768
MIN_MATCH = 3
MAX_MATCH = 258
STORED_MAX = 0xFFFF

#: RFC 1951's length symbols: base and extra bits, symbol 257 upward
_LENGTH_BASE = (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
                35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258)
_LENGTH_EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0)
_DIST_BASE = (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
              257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
              8193, 12289, 16385, 24577)
_DIST_EXTRA = (0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
               7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13)
#: the fixed code's own widths, the RFC's table
_FIXED_LIT = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8
_FIXED_DIST = [5] * 30
#: the code-length alphabet's transmission order
_CL_ORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1,
             15)


class EncodeError(ValueError):
    """Raised for anything the *encoder* got wrong — the caller's mistake."""


def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def _reverse_bits(value, width):
    """The code's bits, root-first, for the LSB-first writer."""
    out = 0
    for bit in range(width):
        if (value >> (width - 1 - bit)) & 1:
            out |= 1 << bit
    return out


def _canonical(lengths):
    """The canonical (code, width) per symbol from the widths — Huffman's
    own assignment: by width, then by symbol, each one past."""
    codes = [(0, 0)] * len(lengths)
    ordered = sorted((w, s) for s, w in enumerate(lengths) if w)
    code = 0
    prev = 0
    first = True
    for width, symbol in ordered:
        if first:
            code, prev, first = 0, width, False
        elif width != prev:
            code = (code + 1) << (width - prev)
            prev = width
        else:
            code += 1
        codes[symbol] = (code, width)
    return codes


def _length_symbol(length):
    """The length's symbol index and its extra bits' value."""
    for index in range(len(_LENGTH_BASE) - 1, -1, -1):
        if length >= _LENGTH_BASE[index]:
            # the largest base the length reaches; but 258 is symbol 284's
            # base with 0 extra AND symbol 285 exactly — the RFC uses 285
            if length == 258:
                return 28, 0
            return index, length - _LENGTH_BASE[index]
    _refuse("bad_length", length)


def _dist_symbol(distance):
    """The distance's symbol index and its extra bits' value."""
    for index in range(len(_DIST_BASE) - 1, -1, -1):
        if distance >= _DIST_BASE[index]:
            return index, distance - _DIST_BASE[index]
    _refuse("bad_distance", distance)


def _matches(data):
    """The LZ77 parse: literals and (length, distance) pairs, greedy,
    the window the format's 32 KiB, matches 3..258, the copy free to
    overlap, never running past the data's end (the last byte stays
    literal — the block's tail is the end-of-block symbol's own)."""
    n = len(data)
    out = []
    i = 0
    head = {}
    while i < n:
        best_len = 0
        best_dist = 0
        low = max(0, i - WINDOW)
        limit = min(MAX_MATCH, n - i)
        for start in range(i - 1, low - 1, -1):
            length = 0
            while length < limit and data[start + length] == data[i + length]:
                length += 1
            if length > best_len:
                best_len = length
                best_dist = i - start
                if best_len >= limit:
                    break
        if best_len >= MIN_MATCH:
            out.append((best_len, best_dist))
            i += best_len
        else:
            out.append(data[i])
            i += 1
    return tuple(out)


def _write_items(writer, stream, lit_codes, dist_codes):
    """The LZ77 stream in a Huffman bitstream: literals and pairs, then
    the end-of-block symbol."""
    for item in stream:
        if isinstance(item, int):
            (code, width) = lit_codes[item]
            writer.append(_reverse_bits(code, width), width)
        else:
            (length, distance) = item
            (sym, extra) = _length_symbol(length)
            (code, width) = lit_codes[257 + sym]
            writer.append(_reverse_bits(code, width), width)
            if _LENGTH_EXTRA[sym]:
                writer.append(extra, _LENGTH_EXTRA[sym])
            (dsym, dextra) = _dist_symbol(distance)
            (code, width) = dist_codes[dsym]
            writer.append(_reverse_bits(code, width), width)
            if _DIST_EXTRA[dsym]:
                writer.append(dextra, _DIST_EXTRA[dsym])
    (code, width) = lit_codes[END_OF_BLOCK]
    writer.append(_reverse_bits(code, width), width)


def _fixed_block(writer, stream):
    """The fixed code's block: header bits, items, end-of-block."""
    writer.append(FINAL, 1)
    writer.append(FIXED, 2)
    _write_items(writer, stream, _canonical(_FIXED_LIT),
                 _canonical(_FIXED_DIST))


def _dynamic_block(writer, stream):
    """The dynamic block: a tree built for this block, on the wire.

    The tree's widths are the Huffman code of the items' symbols (the
    same lengths stage 3 builds, capped by the format's fifteen), the
    code-length code below them, and the items themselves."""
    # the block's symbols: literals as themselves, pairs as the length
    # symbol, the distance symbol, and the extras' raw bits — the tree
    # prices only the alphabets' symbols
    lit_syms = [END_OF_BLOCK]
    dist_syms = []
    for item in stream:
        if isinstance(item, int):
            lit_syms.append(item)
        else:
            (sym, _e) = _length_symbol(item[0])
            lit_syms.append(257 + sym)
            (dsym, _e) = _dist_symbol(item[1])
            dist_syms.append(dsym)
    lit_widths = _tree_widths(lit_syms, LITERALS)
    dist_widths = _tree_widths(dist_syms, DISTANCES)
    hlit = LITERALS
    while hlit > 257 and lit_widths[hlit - 1] == 0:
        hlit -= 1
    hdist = DISTANCES
    while hdist > 1 and dist_widths[hdist - 1] == 0:
        hdist -= 1
    # the code-length code over the combined widths, RLE-compressed
    runs = _rle_widths(list(lit_widths[:hlit]) + list(dist_widths[:hdist]))
    cl_syms = []
    for item in runs:
        cl_syms.append(item[0])
    cl_widths = _tree_widths(cl_syms, 19, limit=7)
    hclen = 19
    while hclen > 4 and cl_widths[_CL_ORDER[hclen - 1]] == 0:
        hclen -= 1
    writer.append(FINAL, 1)
    writer.append(DYNAMIC, 2)
    writer.append(hlit - 257, 5)
    writer.append(hdist - 1, 5)
    writer.append(hclen - 4, 4)
    for i in range(hclen):
        writer.append(cl_widths[_CL_ORDER[i]], 3)
    cl_codes = _canonical(cl_widths)
    for item in runs:
        (symbol, count) = item
        (code, width) = cl_codes[symbol]
        writer.append(_reverse_bits(code, width), width)
        if symbol == 16:
            writer.append(count - 3, 2)
        elif symbol == 17:
            writer.append(count - 3, 3)
        elif symbol == 18:
            writer.append(count - 11, 7)
    # the block's own bits
    _write_items(writer, stream, _canonical(lit_widths),
                 _canonical(dist_widths))


def _tree_widths(symbols, alphabet, limit=MAX_WIDTH):
    """Per-symbol code widths for the symbols' frequencies, capped at
    fifteen — stage 3's tree over an arbitrary alphabet's counts, with
    every symbol the block uses holding a code."""
    counts = [0] * alphabet
    for symbol in symbols:
        counts[symbol] += 1
    live = [(c, s) for s, c in enumerate(counts) if c]
    if not live:
        return [0] * alphabet
    if len(live) == 1:
        widths = [0] * alphabet
        widths[live[0][1]] = 1
        return widths
    import heapq
    heap = [(c, i, [s]) for i, (c, s) in enumerate(live)]
    heapq.heapify(heap)
    seq = len(heap)
    depths = [0] * alphabet
    while len(heap) > 1:
        (w1, _a, syms1) = heapq.heappop(heap)
        (w2, _b, syms2) = heapq.heappop(heap)
        for symbol in syms1 + syms2:
            depths[symbol] += 1
        heapq.heappush(heap, (w1 + w2, seq, syms1 + syms2))
        seq += 1
    if max(depths) > limit:
        # the format's cap: the package-merge optimum over the counts
        return _package_merge(counts, live, limit)
    return depths


def _package_merge(counts, live, limit):
    """The optimal length-limited code over the live symbols' counts —
    the stage 4 algorithm over a general alphabet, `limit` rounds."""
    n = len(live)
    # package-merge over unit weights per occurrence is the Huffman tree
    # itself; the limit's optimum needs each symbol weighted by its count
    items = sorted(((c, s) for (c, s) in live), key=lambda p: (p[0], p[1]))
    lst = [(w, [s]) for (w, s) in items]
    for _ in range(limit - 1):
        pairs = [(lst[i][0] + lst[i + 1][0], lst[i][1] + lst[i + 1][1])
                 for i in range(0, len(lst) - 1, 2)]
        merged = sorted(pairs + [(w, [s]) for (w, s) in items],
                        key=lambda p: (p[0], p[1]))
        lst = merged[:2 * n]
    take = lst[:2 * n - 2]
    widths = [0] * len(counts)
    for _w, syms in take:
        for s in syms:
            widths[s] += 1
    return widths


def _rle_widths(widths):
    """The widths as RFC 1951's runs: plain symbols, 16 (repeat the last
    3-6), 17 (zeros 3-10), 18 (zeros 11-138). Answers (symbol, count)
    pairs; plain symbols answer themselves."""
    runs = []
    i = 0
    n = len(widths)
    while i < n:
        w = widths[i]
        j = i
        while j < n and widths[j] == w:
            j += 1
        count = j - i
        if w == 0:
            while count >= 11:
                take = min(count, 138)
                runs.append((18, take))
                count -= take
            while count >= 3:
                take = min(count, 10)
                runs.append((17, take))
                count -= take
            while count:
                runs.append((0, 1))
                count -= 1
        else:
            runs.append((w, 1))
            count -= 1
            while count >= 3:
                take = min(count, 6)
                runs.append((16, take))
                count -= take
            while count:
                runs.append((w, 1))
                count -= 1
        i = j
    return runs


def deflate_block(data, mode):
    """One block in the named mode: stored, fixed, or dynamic.

    Stored: the three header bits, then byte-aligned LEN, NLEN, the raw
    bytes. Fixed: the RFC's own code over the LZ77 parse. Dynamic: a tree
    built for this block, its code-length code, then the parse. A caller
    mistake — an unknown mode, an input too long for a stored block — is
    refused, naming the offender."""
    if mode not in MODES:
        _refuse("bad_mode", mode)
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", type(data).__name__)
    data = bytes(data)
    if mode == "stored":
        if len(data) > STORED_MAX:
            _refuse("too_long", STORED_MAX, len(data))
        writer = _s1.BitWriter()
        writer.append(FINAL, 1)
        writer.append(STORED, 2)
        writer.append(0, (8 - writer._bit_count % 8) % 8)  # byte-align
        blob = writer.bytes()
        out = bytearray(blob)
        out += len(data).to_bytes(2, "little")
        out += (len(data) ^ 0xFFFF).to_bytes(2, "little")
        out += data
        return bytes(out)
    stream = _matches(data)
    writer = _s1.BitWriter()
    if mode == "fixed":
        _fixed_block(writer, stream)
    else:
        _dynamic_block(writer, stream)
    return writer.bytes()


def deflate(data):
    """The stream, the mode chosen per block.

    One block for the whole input in the cheapest mode that holds it:
    stored when the data has no structure the trees can price, dynamic
    when it has."""
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", type(data).__name__)
    if len(data) > STORED_MAX:
        _refuse("too_long", STORED_MAX, len(data))
    data = bytes(data)
    stored = deflate_block(data, "stored")
    if len(data) > 64:
        dynamic = deflate_block(data, "dynamic")
        if len(dynamic) < len(stored):
            return dynamic
    fixed = deflate_block(data, "fixed")
    if len(fixed) < len(stored):
        return fixed
    return stored
