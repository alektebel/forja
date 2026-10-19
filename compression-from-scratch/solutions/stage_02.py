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

THE FORMAT, PINNED — the marker is 0x00. A literal byte other than the
marker is copied through as itself. A run is the record
`0x00, count, byte` with 1 <= count <= 255, and a byte that IS the
marker is escaped the same way: a literal 0x00 is the record
`0x00, 1, 0x00` — every 0x00 in the stream begins a record, so nothing
is ever misread. Runs of three or more use the record (three bytes for
three or more literals, and each further byte of run is free); runs of
two stay literal. THE WORST CASE: an isolated 0x00 between alternating
single literals costs three bytes for one — a stream like
`0x00, x, 0x00, y, ...` encodes at 2000 per-mille, the format's ceiling.
On the world's `RANDOM` no byte dominates and 0x00 is rare, so the
measured tax stays near the original: the bar's spirit — the tax is
bounded, not the format free.
"""

MARKER = 0x00
MIN_RUN_MARKED = 3
MAX_RUN = 255


class EncodeError(ValueError):
    """A caller's or a stream's mistake, named."""


def rle_encode(data):
    """The runs marked, the rest literal: the format that cannot fail."""
    data = bytes(data)
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        j = i
        while j < n and data[j] == b and j - i < MAX_RUN:
            j += 1
        run = j - i
        if run >= MIN_RUN_MARKED or b == MARKER:
            out.append(MARKER)
            out.append(run)
            out.append(b)
        else:
            out += data[i:j]
        i = j
    return bytes(out)


def rle_decode(data):
    """The runs rebuilt; a marker with no count is refused."""
    data = bytes(data)
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b != MARKER:
            out.append(b)
            i += 1
            continue
        if i + 1 >= n:
            raise EncodeError(
                "rle_decode: marker with no count byte at offset %d" % i)
        count = data[i + 1]
        if count == 0:
            raise EncodeError(
                "rle_decode: a count of zero is not a run (offset %d)" % i)
        if i + 2 >= n:
            raise EncodeError(
                "rle_decode: run count with no run byte at offset %d" % i)
        out += bytes([data[i + 2]]) * count
        i += 3
    return bytes(out)
