"""CPU From Scratch — stage 5: memory, and the refusal that writes nothing.

DESIGN DECISION — why does a fault refuse the access before the first byte moves?
    The obvious spelling checks the bytes as it copies them: read the first byte,
    read the second, discover the second is past the end, raise. The cost is a
    *partially written* access: a store that fails has already destroyed one byte
    of data that the machine still believes in. A fault is an architectural event
    with a cause and a pc, not data corruption, so the bytes it touches must be
    exactly the bytes of a successful access. Refusing up front makes a faulted
    store a no-op, and the check proves it by comparing the memory before and
    after byte for byte.

DESIGN DECISION — why is the bounds check the LAST byte's, not the first's?
    `address < len` looks like the whole check, and for a one-byte access it is.
    For a two-byte access at `len - 1` it is wrong: the first byte is inside and
    the second is past the end, and a machine that checks only the first reads
    whatever follows the buffer. Memory knows how many bytes it is about to move,
    so it refuses an access whose *highest* touched byte is outside — which also
    catches `address == len` and every negative address in the same comparison.

DESIGN DECISION — why must a 2- or 4-byte access be aligned, while a 1-byte one need not?
    Alignment is the deal the hardware makes so that a halfword or word lives in
    one place rather than being assembled from two: a misaligned word is a thing
    the memory would have to stitch together, and stitching it correctly is a
    decision the *machine* should make (or reject), not something memory should
    guess at. A byte has no alignment requirement, so demanding one would refuse
    `lb`/`sb` at an odd address — which is exactly what `memcpy` does and why the
    ISA bothers to have those two instructions at all.

DESIGN DECISION — why does `snapshot` return a copy instead of the live buffer?
    A snapshot is a value: the state at a moment. Handing out the internal buffer
    means the next store silently rewrites the past, and a check that fingerprints
    a machine before and after a step ends up comparing a machine with itself. In
    this course the mistake is worse than usually: every later equivalence test
    (the single-cycle machine versus the pipeline) rests on snapshots that really
    are independent, so an aliasing `snapshot` would make the whole spine vacuous.

DESIGN DECISION — why does `load` zero-extend instead of sign-extend?
    The ISA's `lb` is defined as zero-extending (see `isa.py`), and a pipeline that
    sign-extends a byte instead turns `0xFF` into `-1`, which is not a bug the
    student can see until a program's checksum is off by 256 somewhere. Zero is
    the neutral behaviour for a *size* being smaller than a word: the bytes that
    were not read contribute nothing, rather than contributing their sign.

TODO: implement `Memory.load`, `Memory.store`, `Memory.snapshot` and `Memory.__len__`.
"""

# the word helpers stage 1 provides: `word` masks a value to 32 bits, and
# `pack_word`/`unpack_word` are the little-endian half of the round trip.
from stage_01 import pack_word, unpack_word, word

#: the number of data bytes a Memory holds when its constructor is not told otherwise
DEFAULT_SIZE = 4096

#: the only sizes memory serves: a byte, a halfword, a word. Anything else is a bug.
ACCESS_SIZES = (1, 2, 4)

#: the labels a fault carries in `.detail`, so a caller can branch on the kind
DETAIL_OUT_OF_BOUNDS = "out of bounds"
DETAIL_UNALIGNED = "unaligned"
DETAIL_BAD_SIZE = "unsupported access size"
DETAIL_BAD_ADDRESS = "address is not an integer"


class AddressFault(ValueError):
    """A refused memory access: out of bounds, unaligned, an unsupported size, or
    an address that is not an integer. Carries `.address`, `.size` and `.detail`."""

    def __init__(self, message, *, address=None, size=None, detail=None):
        super().__init__(message)
        self.address = address
        self.size = size
        self.detail = detail


class Memory:
    """A zero-filled block of byte-addressed, little-endian data memory."""

    def __init__(self, size=DEFAULT_SIZE):
        raise NotImplementedError("stage 5: implement Memory()")

    def load(self, address, size):
        """`size` bytes at `address`, little-endian and zero-extended.

        Refuses, with an `AddressFault`, a size other than 1, 2 or 4 (a `bool`
        included), an address that is not an integer (a `bool` included), an
        access whose last byte is outside the memory, and a 2- or 4-byte access
        that is not aligned to its size."""
        raise NotImplementedError("stage 5: implement Memory.load()")

    def store(self, address, size, value):
        """Store the low `size` bytes of `value` at `address`, little-endian.

        Refuses exactly what `load` refuses — a bad size (a `bool` included), a
        non-integer address (a `bool` included), an out-of-bounds access, an
        unaligned 2/4-byte access — and refuses it before writing a byte."""
        raise NotImplementedError("stage 5: implement Memory.store()")

    def snapshot(self):
        """The whole memory as an immutable `bytes` copy.

        It is a copy, not the live buffer, and it is `bytes` (never a
        `bytearray`), so nothing that holds it can alias — or rewrite — the
        memory it came from."""
        raise NotImplementedError("stage 5: implement Memory.snapshot()")

    def __len__(self):
        raise NotImplementedError("stage 5: implement Memory.__len__()")
