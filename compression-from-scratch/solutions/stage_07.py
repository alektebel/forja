"""Compression From Scratch — stage 7: DEFLATE: stored, static, dynamic.

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

import corpus
import inflate
import stage_01 as s1
import stage_03 as s3
import stage_04 as s4
import stage_05 as s5

#: the stream's one final flag: DEFLATE is a sequence of blocks and the
#: last one carries this bit
FINAL = 1

#: the block kinds, as the stream's two bits spell them
STORED = 0
FIXED = 1
DYNAMIC = 2

#: the block kinds' names, as the caller spells them
MODES = ("stored", "fixed", "dynamic")

#: the literal alphabet's size: 0..255 are bytes, 256 ends the block,
#: 257..285 are the match lengths
LITERALS = 286

#: the distance alphabet's size: 0..29 name the distances
DISTANCES = 30

#: DEFLATE's own cap on a code width: the trees never say fifteen-plus
MAX_WIDTH = 15

#: the end-of-block symbol: the block's boundary in the bitstream
END_OF_BLOCK = 256

#: the window DEFLATE's distance alphabet holds: 32 KiB, so the pairs
#: never name a distance the format cannot spell
WINDOW = 32768

#: the smallest and largest match a pair can carry: the length
#: alphabet's own floor and ceiling
MIN_MATCH = 3
MAX_MATCH = 258

#: a stored block's LEN field is two bytes wide
STORED_MAX = 0xFFFF

#: the code-length alphabet: 0..15 are widths, 16 repeats the previous
#: width 3..6 times, 17 a run of zeros 3..10, 18 a run of zeros 11..138
_CL_REPEAT = 16
_CL_ZERO_SHORT = 17
_CL_ZERO_LONG = 18

#: the code-length code's own transmission order, the RFC's permutation
_CL_ORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14,
             1, 15)

#: how many code-length codes the header transmits at least
_CL_MIN = 4

#: the code-length code's own width cap
_CL_MAX_WIDTH = 7


class EncodeError(ValueError):
    """A caller's or a stream's mistake, named."""


#: the length symbols' tables, the RFC's own: 257..285 over 3..258
_LENGTH_BASE = (3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31,
                35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258)
_LENGTH_EXTRA = (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2,
                 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0)

#: the distance symbols' tables, the RFC's own: 0..29 over 1..32768
_DIST_BASE = (1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193,
              257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145,
              8193, 12289, 16385, 24577)
_DIST_EXTRA = (0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6,
               7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13)

#: the fixed code's lengths, the RFC's own: widths 8, 9, 7, 8 by range,
#: and every distance five bits
_FIXED_LITERAL_LENGTHS = [8] * 144 + [9] * 112 + [7] * 24 + [8] * 8
_FIXED_DISTANCE_LENGTHS = [5] * 32


def _reverse_bits(value, width):
    """A code's bits, high bit first: the stream reads codes
    MSB-of-code first while the writer packs LSB-first, so each code
    goes in reversed."""
    out = 0
    for bit in range(width):
        if (value >> bit) & 1:
            out |= 1 << (width - 1 - bit)
    return out


def _write_code(writer, code, width):
    """One Huffman code into the stream, its bits high-bit first."""
    writer.append(_reverse_bits(code, width), width)


def _canonical(lengths):
    """The canonical codes for any alphabet: by width, then by symbol,
    each one past — the same law `inflate._build` reads back."""
    counts = [0] * (MAX_WIDTH + 1)
    for width in lengths:
        if width:
            counts[width] += 1
    first = [0] * (MAX_WIDTH + 1)
    code = 0
    for width in range(1, MAX_WIDTH + 1):
        code = (code + counts[width - 1]) << 1
        first[width] = code
    codes = [(0, 0)] * len(lengths)
    for width in range(1, MAX_WIDTH + 1):
        for symbol in range(len(lengths)):
            if lengths[symbol] == width:
                codes[symbol] = (first[width], width)
                first[width] += 1
    return tuple(codes)


def _length_symbol(length):
    """The length symbol 257..285, its extra bits, and the extras'
    width, for a match of `length` bytes (3..258)."""
    if length < MIN_MATCH or length > MAX_MATCH:
        raise EncodeError(
            "deflate: a match of %d bytes is not one the length alphabet "
            "spells (3..258)" % (length,))
    index = len(_LENGTH_BASE) - 1
    while _LENGTH_BASE[index] > length:
        index -= 1
    return 257 + index, length - _LENGTH_BASE[index], _LENGTH_EXTRA[index]


def _distance_symbol(distance):
    """The distance symbol 0..29, its extra bits, and the extras'
    width, for a distance of `distance` bytes (1..32768)."""
    if distance < 1 or distance > WINDOW:
        raise EncodeError(
            "deflate: a distance of %d is not one the distance alphabet "
            "spells (1..%d)" % (distance, WINDOW))
    index = len(_DIST_BASE) - 1
    while _DIST_BASE[index] > distance:
        index -= 1
    return index, distance - _DIST_BASE[index], _DIST_EXTRA[index]


def _pairs(data):
    """The LZ77 stream the block will spell, the window the format
    holds."""
    return s5.lz77_encode(data, WINDOW, MIN_MATCH, MAX_MATCH) if data else ()


def _stored_block(data, final):
    """The block as raw bytes: a byte-aligned header carrying LEN and
    its complement, then the bytes themselves."""
    if len(data) > STORED_MAX:
        raise EncodeError(
            "deflate: a stored block holds %d bytes; the LEN field is "
            "two bytes wide (%d at most)" % (len(data), STORED_MAX))
    writer = s1.BitWriter()
    writer.append(FINAL if final else 0, 1)
    writer.append(STORED, 2)
    length = len(data)
    nlen = length ^ 0xFFFF
    out = bytearray(writer.bytes())
    # the kind's three bits are the only bits the writer holds: the
    # reference aligns to the next byte, so LEN starts at byte 1
    out.append(length & 0xFF)
    out.append((length >> 8) & 0xFF)
    out.append(nlen & 0xFF)
    out.append((nlen >> 8) & 0xFF)
    out += data
    return bytes(out)


def _spell_stream(writer, stream, literal_codes, distance_codes):
    """The stream's symbols and extra bits, then the end-of-block."""
    for item in stream:
        if isinstance(item, int):
            code, width = literal_codes[item]
            _write_code(writer, code, width)
            continue
        length, distance = item
        lsym, lextra, lwidth = _length_symbol(length)
        code, width = literal_codes[lsym]
        _write_code(writer, code, width)
        if lwidth:
            writer.append(lextra, lwidth)
        dsym, dextra, dwidth = _distance_symbol(distance)
        code, width = distance_codes[dsym]
        _write_code(writer, code, width)
        if dwidth:
            writer.append(dextra, dwidth)
    code, width = literal_codes[END_OF_BLOCK]
    _write_code(writer, code, width)


def _fixed_block(data, final):
    """The block under the RFC's own code: no tree on the wire, just
    the stream."""
    stream = _pairs(data)
    literal_codes = _canonical(_FIXED_LITERAL_LENGTHS)
    distance_codes = _canonical(_FIXED_DISTANCE_LENGTHS)
    writer = s1.BitWriter()
    writer.append(FINAL if final else 0, 1)
    writer.append(FIXED, 2)
    _spell_stream(writer, stream, literal_codes, distance_codes)
    return writer.bytes()


def _run_lengths(transmitted):
    """The widths as (symbol, extra) runs through the code-length
    alphabet: a width run uses 16, a zero run uses 17 (3..10) or 18
    (11..138), never a run the alphabet does not spell."""
    runs = []
    i = 0
    n = len(transmitted)
    while i < n:
        width = transmitted[i]
        run = 1
        while i + run < n and transmitted[i + run] == width:
            run += 1
        i += run
        if width == 0:
            while run >= 11:
                take = min(run, 138)
                runs.append((_CL_ZERO_LONG, take - 11))
                run -= take
            if run >= 3:
                runs.append((_CL_ZERO_SHORT, run - 3))
                run = 0
            while run:
                runs.append((0, 0))
                run -= 1
        else:
            runs.append((width, 0))
            run -= 1
            if run >= 3:
                take = min(run, 6)
                runs.append((_CL_REPEAT, take - 3))
                run -= take
            while run:
                runs.append((width, 0))
                run -= 1
    return runs


def _cl_lengths_for(runs):
    """The code-length code's own widths: each run symbol's count,
    limited to the alphabet's seven-bit cap."""
    counts = [0] * 19
    for symbol, _extra in runs:
        counts[symbol] += 1
    return tuple(_limited_lengths(counts, _CL_MAX_WIDTH))


def _write_tree(writer, literal_lengths, distance_lengths):
    """The dynamic block's two trees: HLIT, HDIST, HCLEN, the code-
    length code, then the widths run-lengthed through it. The widths
    are trimmed to the last live symbol — but never below the symbols
    the format transmits (257 literals, 1 distance)."""
    lit = list(literal_lengths)
    dis = list(distance_lengths)
    hlit = LITERALS
    while hlit > 257 and lit[hlit - 1] == 0:
        hlit -= 1
    hdist = DISTANCES
    while hdist > 1 and dis[hdist - 1] == 0:
        hdist -= 1
    transmitted = lit[:hlit] + dis[:hdist]
    runs = _run_lengths(transmitted)
    cl_lengths = _cl_lengths_for(runs)
    cl_codes = _canonical(cl_lengths)
    hclen = len(_CL_ORDER)
    while hclen > _CL_MIN and cl_lengths[_CL_ORDER[hclen - 1]] == 0:
        hclen -= 1
    writer.append(hlit - 257, 5)
    writer.append(hdist - 1, 5)
    writer.append(hclen - 4, 4)
    for i in range(hclen):
        writer.append(cl_lengths[_CL_ORDER[i]], 3)
    for symbol, extra in runs:
        code, width = cl_codes[symbol]
        _write_code(writer, code, width)
        if symbol == _CL_REPEAT:
            writer.append(extra, 2)
        elif symbol == _CL_ZERO_SHORT:
            writer.append(extra, 3)
        elif symbol == _CL_ZERO_LONG:
            writer.append(extra, 7)


def _limited_lengths(counts, max_width):
    """Widths from frequencies, capped at `max_width`: the Huffman
    tree by hand — leaves keep their symbol, internals numbered on,
    the two smallest (weight, id) picked deterministically — then
    stage 4's limit, whose Kraft sum returns to exactly one."""
    size = len(counts)
    live = [symbol for symbol, count in enumerate(counts) if count]
    if not live:
        return [0] * size
    if len(live) == 1:
        widths = [0] * size
        widths[live[0]] = 1
        return widths
    weight = list(counts) + [0] * (size - 1)
    children = {}
    active = list(live)
    nxt = size
    while len(active) > 1:
        left = min(active, key=lambda node: (weight[node], node))
        active.remove(left)
        right = min(active, key=lambda node: (weight[node], node))
        active.remove(right)
        weight[nxt] = weight[left] + weight[right]
        children[nxt] = (left, right)
        active.append(nxt)
        nxt += 1
    depths = [0] * size
    stack = [(active[0], 0)]
    while stack:
        node, depth = stack.pop()
        if node in children:
            left, right = children[node]
            stack.append((left, depth + 1))
            stack.append((right, depth + 1))
        else:
            depths[node] = depth
    return list(s4.limit_lengths(tuple(depths), max_width))


def _tree_lengths(data, stream):
    """The dynamic block's two trees from the block's own symbols:
    frequencies over the literals and lengths, limited to the format's
    fifteen-bit cap."""
    counts = [0] * LITERALS
    for byte in data:
        counts[byte] += 1
    counts[END_OF_BLOCK] = 1  # the end-of-block symbol is the law
    for item in stream:
        if not isinstance(item, int):
            lsym, _extra, _width = _length_symbol(item[0])
            counts[lsym] += 1
    literal_lengths = _limited_lengths(counts, MAX_WIDTH)
    distance_counts = [0] * DISTANCES
    for item in stream:
        if not isinstance(item, int):
            dsym, _extra, _width = _distance_symbol(item[1])
            distance_counts[dsym] += 1
    distance_lengths = _limited_lengths(distance_counts, MAX_WIDTH)
    return literal_lengths, distance_lengths


def _dynamic_block(data, final):
    """The block under a tree built for it: the tree on the wire first,
    then the stream, the end-of-block closing it."""
    stream = _pairs(data)
    literal_lengths, distance_lengths = _tree_lengths(data, stream)
    literal_codes = _canonical(literal_lengths)
    distance_codes = _canonical(distance_lengths)
    writer = s1.BitWriter()
    writer.append(FINAL if final else 0, 1)
    writer.append(DYNAMIC, 2)
    _write_tree(writer, literal_lengths, distance_lengths)
    _spell_stream(writer, stream, literal_codes, distance_codes)
    return writer.bytes()


def _block_bits(data, mode):
    """The block's size in bits under a mode: the choice needs a
    common currency, and bits are it. The tree's own cost is measured
    the only honest way — written to a probe and counted."""
    if mode == "stored":
        # the kind's 3 bits pad to a byte, LEN and NLEN, the bytes
        return 8 + 32 + len(data) * 8
    if mode == "fixed":
        stream = _pairs(data)
        literal_codes = _canonical(_FIXED_LITERAL_LENGTHS)
        distance_codes = _canonical(_FIXED_DISTANCE_LENGTHS)
        bits = 3
        for item in stream:
            if isinstance(item, int):
                bits += literal_codes[item][1]
                continue
            lsym, _e, lwidth = _length_symbol(item[0])
            bits += literal_codes[lsym][1] + lwidth
            dsym, _e2, dwidth = _distance_symbol(item[1])
            bits += distance_codes[dsym][1] + dwidth
        return bits + literal_codes[END_OF_BLOCK][1]
    if mode == "dynamic":
        stream = _pairs(data)
        literal_lengths, distance_lengths = _tree_lengths(data, stream)
        probe = s1.BitWriter()
        _write_tree(probe, literal_lengths, distance_lengths)
        bits = 3 + len(probe.bytes()) * 8
        for item in stream:
            if isinstance(item, int):
                bits += literal_lengths[item]
                continue
            lsym, _e, lwidth = _length_symbol(item[0])
            bits += literal_lengths[lsym] + lwidth
            dsym, _e2, dwidth = _distance_symbol(item[1])
            bits += distance_lengths[dsym] + dwidth
        return bits + literal_lengths[END_OF_BLOCK]
    raise EncodeError("deflate: mode %r is not one of %s"
                      % (mode, ", ".join(MODES)))


_WRITERS = {"stored": _stored_block, "fixed": _fixed_block,
            "dynamic": _dynamic_block}


def deflate_block(data, mode):
    """One block in the named mode: stored, fixed, or dynamic."""
    if mode not in _WRITERS:
        raise EncodeError("deflate_block: mode %r is not one of %s"
                          % (mode, ", ".join(MODES)))
    data = bytes(data)
    if mode == "stored" and len(data) > STORED_MAX:
        raise EncodeError(
            "deflate_block: stored mode holds %d bytes at most, got %d"
            % (STORED_MAX, len(data)))
    return _WRITERS[mode](data, True)


def deflate(data):
    """The stream, the mode chosen per block."""
    data = bytes(data)
    if len(data) <= STORED_MAX:
        best = min(MODES, key=lambda mode: (_block_bits(data, mode), mode))
        return _WRITERS[best](data, True)
    # beyond one stored block's reach: chunks, each its own block, the
    # last one final; a chunk too small for the tree to pay for itself
    # is stored
    out = bytearray()
    for start in range(0, len(data), STORED_MAX):
        chunk = data[start:start + STORED_MAX]
        last = start + STORED_MAX >= len(data)
        if len(chunk) >= 64:
            best = min(MODES, key=lambda m: (_block_bits(chunk, m), m))
        else:
            best = "stored"
        out += _WRITERS[best](chunk, last)
    return bytes(out)
