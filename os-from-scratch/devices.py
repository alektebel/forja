"""The devices, as data: a console that keeps every byte, and a disk that lies.

Two devices, and both of them are *records* before they are devices. That is not
a simplification for the course's sake — it is the only way an offline kernel can
be held to its promises: something other than the kernel has to remember what
actually happened, and here that something is the hardware.

The console is the easy one. Every byte a kernel sends it is kept, in order, and
`Console.text()` is what it printed. A check compares the userland's output
against it, which is what makes "the shell ran the program" a fact rather than a
claim.

The disk is the hard one, and it is the whole reason stage 9 exists:

  * A sector is `SECTOR` bytes and a write is a *whole sector*. The device does
    not do partial writes.
  * `Disk.write` puts bytes in a **buffer**. `Disk.read` reads the **durable**
    image. Your own write is therefore invisible to your own read until a
    barrier — the disk is not hiding anything, it is telling you the truth about
    when a write becomes a fact.
  * `Disk.barrier` flushes the buffer, in the order the writes were made, and
    says how many sectors that made durable.
  * `Disk.power_fail` is the fixture a filesystem has to survive: the buffer is
    lost, and with `tear=True` the *last* buffered write lands half-way — the
    first half of the sector from the new bytes, the rest from the old ones. The
    next mount sees a mixture of two orders of writes, which is exactly what a
    power failure leaves behind, and refusing to mount it is a correct outcome.

`Disk.log()` is the device's own record — every operation, in order, with the
torn and lost writes marked. A kernel's report of what it wrote is checked
against it.
"""

SECTOR = 512


class DeviceError(ValueError):
    """Raised for anything the *caller* of a device got wrong."""


class Console:
    """A byte sink that keeps every byte, in order."""

    def __init__(self):
        self._bytes = bytearray()
        self.writes = 0

    def write(self, data):
        """Send bytes to the console. Anything that is not bytes is refused."""
        if not isinstance(data, (bytes, bytearray)):
            raise DeviceError(f"the console takes bytes, not {type(data).__name__}")
        self._bytes += data
        self.writes += 1
        return len(data)

    def text(self):
        """What the console has been asked to print, as a str."""
        return bytes(self._bytes).decode("utf-8", "replace")

    def bytes(self):
        return bytes(self._bytes)

    def log(self):
        return {"writes": self.writes, "bytes": len(self._bytes)}


class Disk:
    """Sectors, a buffer, a barrier, and two ways to lose what you wrote."""

    def __init__(self, sectors=64, sector=SECTOR):
        if not isinstance(sectors, int) or isinstance(sectors, bool) or sectors < 1:
            raise DeviceError(f"a disk has at least one sector, not {sectors!r}")
        self.sectors = sectors
        self.sector_size = sector
        self._durable = [bytes(sector) for _ in range(sectors)]
        self._buffer = []
        self._log = []
        self.lost = 0
        self.torn = 0

    def _check_sector(self, index):
        if not isinstance(index, int) or isinstance(index, bool):
            raise DeviceError(f"a sector index is an int, not {index!r}")
        if not 0 <= index < self.sectors:
            raise DeviceError(f"sector {index} is outside this disk "
                              f"(0..{self.sectors - 1})")

    def read(self, index):
        """One whole sector, as it is *durable* right now."""
        self._check_sector(index)
        self._log.append(("read", index))
        return self._durable[index]

    def write(self, index, data):
        """Buffer one whole sector. Nothing is durable until a barrier."""
        self._check_sector(index)
        data = bytes(data)
        if len(data) != self.sector_size:
            raise DeviceError(f"a sector write is {self.sector_size} bytes, "
                              f"not {len(data)}")
        self._buffer.append((index, data))
        self._log.append(("write", index))
        return len(self._buffer)

    def barrier(self):
        """Make every buffered write durable, in the order they were made."""
        made = len(self._buffer)
        for index, data in self._buffer:
            self._durable[index] = data
        self._buffer = []
        self._log.append(("barrier", made))
        return made

    def pending(self):
        """How many writes are in the buffer, and therefore not a fact yet."""
        return len(self._buffer)

    def power_fail(self, tear=False):
        """Lose the buffer. With `tear`, half of the last write lands anyway.

        Returns what the failure did — `{"lost": n, "torn": sector or None}` —
        so a check can say which fixture it used.
        """
        lost = len(self._buffer)
        torn = None
        if tear and lost:
            index, data = self._buffer[-1]
            half = self.sector_size // 2
            self._durable[index] = (data[:half] + self._durable[index][half:])
            torn = index
        self._buffer = []
        self.lost += lost
        if torn is not None:
            self.torn += 1
        self._log.append(("power_fail", lost, torn))
        return {"lost": lost, "torn": torn}

    def durable(self):
        """The whole durable image: what a mount would read after a crash."""
        return tuple(self._durable)

    def durable_sha(self):
        """A digest of the durable image: one number for "did anything change"."""
        digest = 0
        for index, sector in enumerate(self._durable):
            for byte in sector:
                digest = (digest * 31 + byte + index) & 0xFFFFFFFF
        return digest

    def log(self):
        """Every operation this device was asked to perform, in order."""
        return tuple(self._log)

    def counters(self):
        return {"reads": sum(1 for e in self._log if e[0] == "read"),
                "writes": sum(1 for e in self._log if e[0] == "write"),
                "barriers": sum(1 for e in self._log if e[0] == "barrier"),
                "lost": self.lost, "torn": self.torn}
