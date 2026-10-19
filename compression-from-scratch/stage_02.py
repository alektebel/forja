"""Compression From Scratch — stage 2: Run-length: the format that cannot fail.

Run-length is the course's first codec and the control arm for every
one after it: a marker byte, a count, the run's byte — a format simple
enough to be obviously correct and weak enough to show why the others
exist. `rle_encode` pays a one-byte tax per non-run segment; the ratio
bars pin what that tax costs on the world's runs (`BINARY`) and on its
noise (`RANDOM`), and `rle_decode` is the strict reader that refuses a
marker with no count or a count with no byte.

TODO: implement each function; the docstring is the contract.

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

def rle_encode(data):
    """The runs marked, the rest literal: the format that cannot fail."""
    raise NotImplementedError("stage 2: implement rle_encode()")


def rle_decode(data):
    """The runs rebuilt; a marker with no count is refused."""
    raise NotImplementedError("stage 2: implement rle_decode()")
