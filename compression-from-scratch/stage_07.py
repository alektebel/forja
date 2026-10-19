"""Compression From Scratch — stage 7: DEFLATE: stored, static, dynamic.

DEFLATE is Huffman and LZ77 in one stream, with the choice the format
gives every block: stored (no compression, a length and its complement),
fixed (the RFC's own code), or dynamic (a code built for this block).
`deflate_block` writes one block in a named mode; `deflate` chooses per
block. The reference `inflate.inflate` is the judge, and the bars pin
what each mode must achieve.

TODO: implement each function; the docstring is the contract.

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

def deflate_block(data, mode):
    """One block in the named mode: stored, fixed, or dynamic."""
    raise NotImplementedError("stage 7: implement deflate_block()")


def deflate(data):
    """The stream, the mode chosen per block."""
    raise NotImplementedError("stage 7: implement deflate()")
