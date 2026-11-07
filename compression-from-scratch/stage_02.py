"""Compression From Scratch — stage 2: Run-length: the format that cannot fail.

Run-length is the course's first codec and the control arm for every
one after it: a marker byte, a count, the run's byte — a format simple
enough to be obviously correct and weak enough to show why the others
exist. `rle_encode` pays a one-byte tax per non-run segment; the ratio
bars pin what that tax costs on the world's runs (`BINARY`) and on its
noise (`RANDOM`), and `rle_decode` is the strict reader that refuses a
marker with no count or a count with no byte.

DESIGN DECISION — why is RLE stage 2 and not stage 8?
Because the ratio's whole idea — pay bytes only where the data repeats —
is visible in its simplest form here: on `BINARY` the runs pay the format
handsomely, on `RANDOM` every third byte is a marker tax and the bar
proves the tax is bounded. Every later codec is this trade with a
bigger idea of "repeat".

DESIGN DECISION — why a marker byte rather than (count, byte) pairs?
Because a count-first format pays two bytes on every run and a marker
format pays one on runs and three on the rare non-run — and the corpora
are mostly runs. The world's `BINARY` bar is set so the marker's economy
is measurable: a count-first RLE fails it.

DESIGN DECISION — why is the escape of the marker itself part of the
format?
Because the marker byte is in the alphabet: a corpus that contains it
would corrupt silently if the encoder did not escape it and the decoder
did not refuse an unescaped one. A format that handles every input or
refuses — never silently corrupts — is the course's one law, stated
here first.
"""

MARKER = 0x00
#: the shortest run worth its three-byte record: a run of 3 costs 3 either
#: way, so the marked threshold is where marking stops losing
MIN_RUN_MARKED = 3
#: the count byte's ceiling: one record carries at most 255 repetitions
MAX_RUN = 255


class EncodeError(ValueError):
    """Raised for anything the *encoder* got wrong — the caller's mistake."""


def _refuse(reason, *names):
    raise EncodeError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def _runs(data):
    """The input as (byte, count) runs, in order."""
    runs = []
    i = 0
    n = len(data)
    while i < n:
        j = i
        while j < n and data[j] == data[i]:
            j += 1
        runs.append((data[i], j - i))
        i = j
    return runs


def rle_encode(data):
    """The runs marked, the rest literal: the format that cannot fail.

    A run of `MIN_RUN_MARKED` or more becomes `MARKER, count, byte` — split
    at `MAX_RUN` when longer. Shorter runs and every byte that is not in a
    run stay literal, except the marker itself, which is escaped as
    `MARKER, 1, MARKER` — an unescaped marker would corrupt on decode."""
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", type(data).__name__)
    out = bytearray()
    for (byte, count) in _runs(bytes(data)):
        if byte == MARKER:
            # the marker is never literal: each marker byte is its own
            # one-byte run, escaped
            for _ in range(count):
                out += bytes([MARKER, 1, MARKER])
            continue
        while count >= MIN_RUN_MARKED:
            take = min(count, MAX_RUN)
            if count - take and count - take < MIN_RUN_MARKED:
                take = count - MIN_RUN_MARKED if count - MIN_RUN_MARKED \
                    >= MIN_RUN_MARKED else count
            out += bytes([MARKER, take, byte])
            count -= take
        out += bytes([byte]) * count
    return bytes(out)


def rle_decode(data):
    """The runs rebuilt; a marker with no count is refused.

    `MARKER, count, byte` rebuilds `count` copies; any other byte passes
    through. A marker at the end without its count, a zero count, or a
    marker record whose byte is missing is a corrupt stream — refused,
    never guessed."""
    if not isinstance(data, (bytes, bytearray)):
        _refuse("not_bytes", type(data).__name__)
    data = bytes(data)
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == MARKER:
            if i + 2 >= n:
                _refuse("truncated_record", data[i:])
            count = data[i + 1]
            if count == 0:
                _refuse("zero_count", count)
            out += bytes([data[i + 2]]) * count
            i += 3
        else:
            out.append(b)
            i += 1
    return bytes(out)
