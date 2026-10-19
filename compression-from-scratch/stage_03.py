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

def huffman_lengths(data):
    """Per-symbol code lengths from the byte's own frequencies."""
    raise NotImplementedError("stage 3: implement huffman_lengths()")


def canonical_codes(lengths):
    """The canonical codes: by width, then by symbol, each one past."""
    raise NotImplementedError("stage 3: implement canonical_codes()")


def huffman_encode(data):
    """The stream and the lengths that rebuild it: (bytes, lengths)."""
    raise NotImplementedError("stage 3: implement huffman_encode()")


def huffman_decode(data, lengths, size):
    """The lengths' codes read back; a code that runs past a leaf refuses."""
    raise NotImplementedError("stage 3: implement huffman_decode()")
