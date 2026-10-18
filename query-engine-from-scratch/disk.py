"""The disk, as data: sectors, a buffer, a barrier, and two ways to lose what
you wrote.

A query engine runs on a disk it does not control, and the only honest way to
teach one offline is to hand the disk over as *data* the engine has to satisfy.
This module is that disk, and it is deliberately small enough to hold in your
head:

  * A sector is `SECTOR` bytes and a write is a *whole sector*. The device does
    not do partial writes, and it refuses a write that is not exactly one
    sector — a pager's job is to speak in pages, and pages are a whole number
    of sectors.
  * `Disk.write` puts bytes in a **buffer**. `Disk.read` reads the **durable**
    image. Your own write is therefore invisible to your own read until a
    barrier — the disk is not hiding anything, it is telling you the truth
    about when a write becomes a fact. Every durability rule in this course is
    this one sentence: *nothing is a fact until a barrier says so*.
  * `Disk.barrier` flushes the buffer, in the order the writes were made, and
    says how many sectors that made durable. The order is the record: a log
    whose entries were appended in one order cannot become durable in another.
  * `Disk.power_fail` is the fixture a recovery exists to survive: the buffer
    is lost, and with `tear=True` the *last* buffered write lands half-way —
    the first half of the sector from the new bytes, the rest from the old
    ones. A torn log entry is exactly what a power failure leaves behind, and
    recovery discarding it is a correct outcome, not a bug.
  * `Disk.log()` is the device's own record — every operation, in order, with
    the torn and lost writes marked. A stage's report of what it wrote is
    checked against it.

Nothing in this module knows anything about the course: it has no idea what a
page, a B+tree or a WAL is. It keeps its own records — `counters()` answers
reads, writes, barriers, lost and torn — and those records are the tie-breaker
a stage's report has to agree with. The world is read-only in the course's
sense: the *tables*, the *catalog* and the *queries* are data a stage reads;
this disk is the one mutable thing, because durability is the course's subject.
"""

SECTOR = 128          # a page is two sectors; a WAL entry is one


class DeviceError(ValueError):
    """Raised for anything the *caller* of this device got wrong."""


class Disk:
    """Sectors, a buffer, a barrier, and two ways to lose what you wrote."""

    def __init__(self, sectors=256):
        if not isinstance(sectors, int) or isinstance(sectors, bool) \
                or sectors < 1:
            raise DeviceError("a disk has at least one sector, not %r"
                              % (sectors,))
        self.sectors = sectors
        self._durable = [bytes(SECTOR) for _ in range(sectors)]
        self._buffer = []
        self._log = []
        self.lost = 0
        self.torn = 0

    def _check_sector(self, index):
        if not isinstance(index, int) or isinstance(index, bool):
            raise DeviceError("a sector index is an int, not %r" % (index,))
        if not 0 <= index < self.sectors:
            raise DeviceError("sector %r is outside this disk (0..%d)"
                              % (index, self.sectors - 1))

    def read(self, index):
        """One whole sector, as it is *durable* right now."""
        self._check_sector(index)
        self._log.append(("read", index))
        return self._durable[index]

    def write(self, index, data):
        """Buffer one whole sector. Nothing is durable until a barrier."""
        self._check_sector(index)
        data = bytes(data)
        if len(data) != SECTOR:
            raise DeviceError("a sector write is %d bytes, not %d"
                              % (SECTOR, len(data)))
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
        """How many writes are buffered, and therefore not a fact yet."""
        return len(self._buffer)

    def power_fail(self, tear=False):
        """Lose the buffer. With `tear`, half of the last write lands anyway."""
        lost = len(self._buffer)
        torn = None
        if tear and lost:
            index, data = self._buffer[-1]
            half = SECTOR // 2
            self._durable[index] = (data[:half] + self._durable[index][half:])
            torn = index
        self._buffer = []
        self.lost += lost
        if torn is not None:
            self.torn += 1
        self._log.append(("power_fail", lost, torn))
        return {"lost": lost, "torn": torn}

    def durable(self):
        """The whole durable image: what a mount reads after a crash."""
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
        """The device's own record: reads, writes, barriers, losses, tears."""
        return {"reads": sum(1 for e in self._log if e[0] == "read"),
                "writes": sum(1 for e in self._log if e[0] == "write"),
                "barriers": sum(1 for e in self._log if e[0] == "barrier"),
                "lost": self.lost, "torn": self.torn}
