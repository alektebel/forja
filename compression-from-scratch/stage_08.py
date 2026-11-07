"""Compression From Scratch — stage 8: FSE: the table the format builds.

FSE (finite-state entropy) is ANS's table form: a distribution becomes
a table of states, the encoder walks states forward, the decoder walks
them back — and the table IS the format, transmitted as the counts it
normalizes. `fse_build_table` normalizes counts to the state count and
lays the table; `fse_encode` and `fse_decode` walk it — the stage's own
decoder, because FSE's decode is the format.

DESIGN DECISION — why is the decoder stage code rather than a reference?
Because FSE's decode is not a side of the format but the format itself:
the table the encoder walks is the table the decoder walks backwards,
and a reference decoder would be the same code twice. The check holds
the round-trip and the table's normalization — both halves.

DESIGN DECISION — why must the normalized counts sum exactly to the
state count?
Because the table's arithmetic — where each symbol's states sit — is
defined by that sum: a distribution that normalizes to more states than
the table holds is a table the decoder cannot walk. The check holds the
sum on every corpus.

DESIGN DECISION — why spread the states by the formula rather than sort?
Because the spread is what makes the decoder's single table walk
possible: symbol states interleaved so the next state's low bits are
the next symbol's. Sorting would give a simpler table and a decoder
that cannot run backwards — the one property FSE exists for.
"""


import stage_01 as _s1


EncodeError = _s1.EncodeError

def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def _normalize(counts, max_state):
    """The counts scaled to exactly `max_state` states: each counted
    symbol a floor of one, the rest by largest remainder, ties by symbol
    ascending. All-zero counts pre-answer symbol 0."""
    total = sum(counts)
    if total == 0:
        return [1] + [0] * (len(counts) - 1)
    scaled = [c * max_state / total for c in counts]
    norm = [int(x) for x in scaled]
    for i, count in enumerate(counts):
        if count and norm[i] < 1:
            norm[i] = 1
    rest = max_state - sum(norm)
    remainders = sorted(range(len(counts)),
                        key=lambda i: (-(scaled[i] - norm[i]), i))
    i = 0
    while rest > 0:
        norm[remainders[i % len(remainders)]] += 1
        rest -= 1
        i += 1
    return norm


def fse_build_table(counts, max_state):
    """The distribution normalized to the state count, the states spread.

    Answers `(norm, spread, ranks, slots)`: the normalized counts, the
    state's symbol per slot, the slot's rank among its symbol's states,
    and each symbol's owned slots. The spread walks the table by the
    odd step `(L>>1) + (L>>3) + 3`, symbols in descending normalized
    order; the ranks are dense per symbol, ascending by slot."""
    if not isinstance(max_state, int) or isinstance(max_state, bool) \
            or max_state < 1:
        _refuse("bad_state_count", max_state)
    if (max_state & (max_state - 1)) != 0:
        _refuse("not_a_power_of_two", max_state)
    if not isinstance(counts, (tuple, list)) or not counts:
        _refuse("bad_counts", counts)
    if any(isinstance(c, float) or not isinstance(c, int)
           or isinstance(c, bool) or c < 0 for c in counts):
        bad = [c for c in counts
               if isinstance(c, float) or not isinstance(c, int)
               or isinstance(c, bool) or c < 0]
        _refuse("bad_count", bad[0])
    live = sum(1 for c in counts if c)
    if live > max_state:
        _refuse("too_many_symbols", live, max_state)
    norm = _normalize(list(counts), max_state)
    L = max_state
    if live <= 1:
        # the degenerate table: every state answers symbol 0
        spread = tuple([0] * L)
        ranks = tuple([0] * L)
        slots = [()] * len(norm)
        # the degenerate table's own pin: symbol 0's slots named as the
        # symbol it answers, one per state
        slots[0] = tuple([0] * L)
        return tuple(norm), spread, ranks, tuple(slots)
    order = sorted(range(len(norm)), key=lambda s: (-norm[s], s))
    step = (L >> 1) + (L >> 3) + 3
    if step % 2 == 0:
        step += 1
    spread = [None] * L
    slots = [()] * len(norm)
    pos = 0
    for symbol in order:
        owned = []
        for _ in range(norm[symbol]):
            spread[pos] = symbol
            owned.append(pos)
            pos = (pos + step) % L
        slots[symbol] = tuple(sorted(owned))
    ranks = [None] * L
    for symbol, owned in enumerate(slots):
        for rank, slot in enumerate(owned):
            ranks[slot] = rank
    return tuple(norm), tuple(spread), tuple(ranks), tuple(slots)


def _state_count(counts):
    """The table's size for the counts: the next power of two at or past
    the data's total, per the world's own choice."""
    total = sum(counts)
    if total == 0:
        return 1
    return 1 << (total - 1).bit_length()


def fse_encode(data, counts):
    """The states walked forward: (bytes, counts).

    Answers the packed stream and the table's normalized counts. The
    walk: for each symbol in reverse, emit the state's low bits (the
    count is the symbol's state-log), then step to the symbol's next
    state; the final state flushes whole. A non-bytes input, a symbol
    the counts never counted, and an empty table for non-empty data are
    refused, naming the offender."""
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", data)
    data = bytes(data)
    if not isinstance(counts, (tuple, list)) or not counts:
        _refuse("bad_counts", counts)
    L = _state_count(counts)
    (norm, spread, ranks, slots) = fse_build_table(counts, L)
    if sum(counts) == 0:
        if data:
            _refuse("no_states", len(data))
        return b"", tuple(norm)
    Lbits = L.bit_length() - 1
    nb_bits = [Lbits - (norm[s].bit_length() - 1) if norm[s] else 0
               for s in range(len(norm))]
    bits = []
    state = 0
    for byte in reversed(data):
        symbol = byte
        if not norm[symbol]:
            _refuse("uncoded_symbol", symbol)
        nb = nb_bits[symbol]
        for j in reversed(range(nb)):
            bits.append((state >> j) & 1)
        state = slots[symbol][state >> nb]
    for j in reversed(range(Lbits)):
        bits.append((state >> j) & 1)
    # the stream reads forward: the flush is its head, the symbols' bits
    # follow in data order — the walk's groups, appended MSB-first, so
    # the reversal lands each group LSB-first
    bits.reverse()
    # the stream's own count: a four-byte little-endian header, because
    # the decoder must know where the bits stop
    out = bytearray(len(bits).to_bytes(4, "little"))
    out += bytearray((len(bits) + 7) // 8)
    for i, bit in enumerate(bits):
        if bit:
            out[4 + i // 8] |= 1 << (i % 8)
    return bytes(out), tuple(norm)


def fse_decode(data, counts, size):
    """The states walked back: the format's own decode.

    The flushed state comes off the stream's head, then each symbol's
    low bits walk it on. A non-bytes stream, a negative size, a stream
    too short for the state, and a stream that ends before the size is
    fed are refused, naming the offender."""
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", data)
    data = bytes(data)
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        _refuse("bad_size", size)
    if not isinstance(counts, (tuple, list)) or not counts:
        _refuse("bad_counts", counts)
    if size == 0:
        return b""
    L = _state_count(counts)
    (norm, spread, ranks, slots) = fse_build_table(counts, L)
    Lbits = L.bit_length() - 1
    nb_bits = [Lbits - (norm[s].bit_length() - 1) if norm[s] else 0
               for s in range(len(norm))]
    if len(data) < 4:
        _refuse("stream_too_short", len(data))
    bit_count = int.from_bytes(data[:4], "little")
    if (bit_count + 7) // 8 > len(data) - 4:
        _refuse("stream_too_short", len(data))
    pos = 32                   # the bits start after the header

    def read(width):
        nonlocal pos
        if pos + width > 32 + bit_count:
            _refuse("stream_ends_early", size)
        value = 0
        for j in range(width):
            bit = (data[pos // 8] >> (pos % 8)) & 1
            value |= bit << j
            pos += 1
        return value

    state = read(Lbits)
    out = bytearray()
    for _ in range(size):
        symbol = spread[state]
        out.append(symbol)
        nb = nb_bits[symbol]
        low = read(nb)
        state = (ranks[state] << nb) | low
    return bytes(out)
