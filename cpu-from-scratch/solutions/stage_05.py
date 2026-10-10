"""CPU From Scratch — stage 5: memory (solution).

The template explains why each decision is the one it is; this file is only the
body. `Memory` is a byte-addressed, little-endian buffer that refuses an access
before it moves a byte.
"""

from stage_01 import pack_word, unpack_word, word

#: the number of data bytes a Memory holds when its constructor is not told otherwise
DEFAULT_SIZE = 4096

#: the only sizes memory serves: a byte, a halfword, a word
ACCESS_SIZES = (1, 2, 4)

#: the labels a fault carries in `.detail`
DETAIL_OUT_OF_BOUNDS = "out of bounds"
DETAIL_UNALIGNED = "unaligned"
DETAIL_BAD_SIZE = "unsupported access size"
DETAIL_BAD_ADDRESS = "address is not an integer"


class AddressFault(ValueError):
    """A refused memory access. Carries `.address`, `.size` and `.detail`."""

    def __init__(self, message, *, address=None, size=None, detail=None):
        super().__init__(message)
        self.address = address
        self.size = size
        self.detail = detail


class Memory:
    """A zero-filled block of byte-addressed, little-endian data memory."""

    def __init__(self, size=DEFAULT_SIZE):
        self._data = bytearray(size)

    def __len__(self):
        return len(self._data)

    def _refuse(self, address, size):
        """Raise `AddressFault` unless `address` is a legal `size`-byte access."""
        if isinstance(size, bool) or not isinstance(size, int) or size not in ACCESS_SIZES:
            raise AddressFault(
                "refusing a %r-byte access: memory serves only the sizes %r"
                % (size, ACCESS_SIZES),
                address=address, size=size, detail=DETAIL_BAD_SIZE)
        if isinstance(address, bool) or not isinstance(address, int):
            raise AddressFault(
                "refusing an address of %r: an address is an integer byte index"
                % (address,),
                address=address, size=size, detail=DETAIL_BAD_ADDRESS)
        if address < 0 or address + size > len(self._data):
            raise AddressFault(
                "refusing address %r (size %r): the bytes %r..%r are outside 0..%r"
                % (address, size, address, address + size - 1, len(self._data) - 1),
                address=address, size=size, detail=DETAIL_OUT_OF_BOUNDS)
        if size > 1 and address % size != 0:
            raise AddressFault(
                "refusing address %r for a %r-byte access: it is not aligned to %r"
                % (address, size, size),
                address=address, size=size, detail=DETAIL_UNALIGNED)

    def load(self, address, size):
        """`size` bytes at `address`, little-endian and zero-extended."""
        self._refuse(address, size)
        raw = bytes(self._data[address:address + size])
        return unpack_word(raw + b"\x00" * (4 - size))

    def store(self, address, size, value):
        """Store the low `size` bytes of `value` at `address`, little-endian."""
        self._refuse(address, size)
        image = pack_word(word(value))
        for offset in range(size):
            self._data[address + offset] = image[offset]

    def snapshot(self):
        """The whole memory as an immutable `bytes` copy."""
        return bytes(self._data)
