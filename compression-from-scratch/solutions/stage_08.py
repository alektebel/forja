"""Compression From Scratch — stage 8: FSE: the table the format builds.

FSE (finite-state entropy) is ANS's table form: a distribution becomes
a table of states, the encoder walks states forward, the decoder walks
them back — and the table IS the format, transmitted as the counts it
normalizes. `fse_build_table` normalizes counts to the state count and
lays the table; `fse_encode` and `fse_decode` walk it — the stage's own
decoder, because FSE's decode is the format.

TODO: implement each function; the docstring is the contract.

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

DESIGN DECISION — why spread the states by the formula rather than
sort?
Because the spread is what makes the decoder's single table walk
possible: symbol states interleaved so the next state's low bits are
the next symbol's. Sorting would give a simpler table and a decoder
that cannot run backwards — the one property FSE exists for.
"""

import stage_01 as s1


def _normalize(counts, max_state):
    """The counts scaled to sum exactly `max_state`, or the refusal."""
    if not max_state >= 1:
        raise s1.EncodeError(
            "fse_build_table: a table of %d states holds no state"
            % (max_state,))
    if max_state & (max_state - 1):
        raise s1.EncodeError(
            "fse_build_table: max_state %d is not a power of two"
            % (max_state,))
    total = 0
    positive = 0
    for count in counts:
        if not isinstance(count, int):
            raise s1.EncodeError(
                "fse_build_table: the count %r is not a number"
                % (count,))
        if count < 0:
            raise s1.EncodeError(
                "fse_build_table: a count of %d is not a distribution"
                % (count,))
        total += count
        if count:
            positive += 1
    if total == 0:
        # The degenerate table: every state pre-answers symbol 0, so
        # an EMPTY stream encodes to just the 4-byte final state and
        # the decode of size 0 reads none of them.
        return (1,) + (0,) * (len(counts) - 1) if counts else ()
    if positive > max_state:
        raise s1.EncodeError(
            "fse_build_table: %d counted symbols do not fit %d states"
            % (positive, max_state))
    # Floors first: every positive symbol keeps at least one state,
    # and the floor's remainders always cover the ones that fell to 0.
    norm = [count * max_state // total for count in counts]
    fracs = [count * max_state - norm[i] * total
             for i, count in enumerate(counts)]
    remaining = max_state - sum(norm)
    for i, count in enumerate(counts):
        if count and norm[i] == 0:
            norm[i] = 1
            remaining -= 1
    # What is left goes to the largest remainders, ties to the
    # lower symbol: one pass, because the remainder is smaller than
    # the number of counted symbols.
    order = sorted(range(len(counts)), key=lambda i: (-fracs[i], i))
    for i in order[:remaining]:
        norm[i] += 1
    return tuple(norm)


def _build(norm, max_state):
    """The spread, the ranks and the per-symbol slots the walks use."""
    spread = [-1] * max_state
    # The interleaving step: odd, so against a power-of-two table
    # size `pos = (pos + step) & (max_state - 1)` visits every slot —
    # the walk can never wedge, because gcd(step, max_state) is 1.
    step = ((max_state >> 1) + (max_state >> 3) + 3) | 1
    mask = max_state - 1
    pos = 0
    for symbol in range(len(norm)):
        for _ in range(norm[symbol]):
            spread[pos] = symbol
            pos = (pos + step) & mask
    ranks = []
    if sum(norm) == 1:
        # The degenerate table: one counted symbol, so every state
        # pre-answers it — the walk's single slot is that symbol's,
        # and the rest are the same symbol seen from states the
        # encode of an EMPTY stream never steps through.
        the_symbol = norm.index(1)
        spread = [the_symbol] * max_state
        ranks = [0] * max_state
        slots = tuple((0,) * max_state if symbol == the_symbol else ()
                      for symbol in range(len(norm)))
        return (tuple(spread), tuple(ranks), slots)
    seen = [0] * len(norm)
    for slot in range(max_state):
        symbol = spread[slot]
        ranks.append(seen[symbol])
        seen[symbol] += 1
    slots = []
    for symbol in range(len(norm)):
        slots.append(tuple(slot for slot in range(max_state)
                           if spread[slot] == symbol))
    return (tuple(spread), tuple(ranks), tuple(slots))


def fse_build_table(counts, max_state):
    """The distribution normalized to the state count, the states spread."""
    norm = _normalize(counts, max_state)
    spread, ranks, slots = _build(norm, max_state)
    return (norm, spread, tuple(ranks), slots)


def _table_size(counts):
    """The one table size both walks agree on: the sum's next power
    of two, so `state & (max_state - 1)` is the slot's index."""
    total = sum(counts)
    if total == 0:
        # The degenerate table `_normalize` returns: one state, the
        # whole table pre-answering symbol 0.
        return 1
    return 1 << (total - 1).bit_length()


def fse_encode(data, counts):
    """The states walked forward: (bytes, counts)."""
    if not isinstance(data, (bytes, bytearray)):
        raise s1.EncodeError(
            "fse_encode: the data %r is not bytes" % (data,))
    max_state = _table_size(counts)
    norm, spread, ranks, slots = fse_build_table(counts, max_state)
    k = max_state.bit_length() - 1
    writer = s1.BitWriter()
    state = max_state
    for symbol in data:
        freq = norm[symbol]
        if freq == 0:
            raise s1.EncodeError(
                "fse_encode: symbol %d has a count of 0" % (symbol,))
        # Renorm before the step: emit the low bytes while the state
        # reaches this symbol's own ceiling `freq << 8`, so the stepped
        # state lands back in [max_state, max_state << 8) — the window
        # the decoder's reads restore exactly.
        while state >= freq << 8:
            writer.append(state & 0xFF, 8)
            state >>= 8
        quotient, rest = divmod(state, freq)
        state = (quotient << k) + slots[symbol][rest]
    for _ in range(4):
        writer.append(state & 0xFF, 8)
        state >>= 8
    return writer.bytes(), norm


def fse_decode(data, counts, size):
    """The states walked back: the format's own decode."""
    if not isinstance(data, (bytes, bytearray)):
        raise s1.EncodeError(
            "fse_decode: the data %r is not bytes" % (data,))
    if not isinstance(size, int) or size < 0:
        raise s1.EncodeError(
            "fse_decode: a size of %d decodes no stream" % (size,))
    max_state = _table_size(counts)
    if len(data) < 4:
        raise s1.EncodeError(
            "fse_decode: a stream of %d bytes cannot even hold the "
            "final state" % (len(data),))
    norm, spread, ranks, slots = fse_build_table(counts, max_state)
    k = max_state.bit_length() - 1
    pos = len(data) - 1
    state = 0
    for _ in range(4):
        state = (state << 8) | data[pos]
        pos -= 1
    out = bytearray()
    for _ in range(size):
        while state < max_state:
            if pos < 0:
                raise s1.EncodeError(
                    "fse_decode: the stream ends before the states do")
            state = (state << 8) | data[pos]
            pos -= 1
        slot = state & (max_state - 1)
        symbol = spread[slot]
        rest = ranks[slot]
        state = norm[symbol] * (state >> k) + rest
        out.append(symbol)
    out.reverse()
    return bytes(out)
