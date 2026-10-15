"""The machine, as data: RAM, a two-level page walk, traps and a clock.

A kernel is a program that runs on hardware it does not control, and the only
honest way to teach one offline is to hand the hardware over as *data* the
student's kernel has to satisfy. This module is that hardware, and it is
deliberately small enough to hold in your head:

  * **RAM** is a flat byte array of `FRAME_COUNT` frames of `PAGE_SIZE` bytes,
    addressed physically. It refuses a read or a write outside itself, naming
    the address — the machine does not "wrap around" and neither does your code.
  * **The page walk** is real: two levels of `ENTRIES` entries, each table
    exactly one frame, each entry the frame it points at packed together with
    four permission bits. `MMU.translate` walks it and raises a `PageFault`
    whose `reason` is a word from a closed set, because a fault you cannot
    diagnose teaches nothing.
  * **The TLB** is the machine's cache of the walk, and it is the whole reason
    stage 3 exists: change a table through anything but `MMU.invalidate` and the
    machine will keep serving the translation you thought you had removed. The
    counters `walks` and `hits` are how a check proves which path was taken.
  * **Traps** are what the machine raises. Every one carries a vector from
    `VECTORS` and an x86-shaped error code whose three bits (`FAULT_PROTECTION`,
    `FAULT_WRITE`, `FAULT_USER`) say what happened — decoding them is the
    kernel's job, not the machine's.
  * **The clock** is a counter. Nothing here is timed, sampled or measured from a
    wall: `Timer.advance` is the only way time passes.
  * **The boot handoff** is `BOOT_MAPS`: the memory map a firmware would hand a
    kernel, including the fixtures where the firmware lies (an overlap, an
    unknown kind, an unaligned end, an unordered list, a map larger than RAM).
    You cannot trust memory until you have read the map, so a course about a
    kernel starts by reading it.

Nothing in this module knows anything about the course: it has no idea what a
frame allocator, a page table entry or a process is. It keeps its own records —
`RAM` refuses out of bounds, `MMU` counts its walks and hits, `Timer` counts ticks
— and those records are the tie-breaker a stage's report has to agree with.
"""

PAGE_SIZE = 4096
FRAME_COUNT = 256
RAM_BYTES = PAGE_SIZE * FRAME_COUNT

#: entries per table, and the bits of a virtual address each level consumes
ENTRIES = 512
LEVEL_BITS = 9

#: the four permission bits, and the entry packing: (frame << 4) | flags
PRESENT = 1
WRITE = 2
USER = 4
EXEC = 8
FLAGS_ALL = PRESENT | WRITE | USER | EXEC

#: the vectors this machine can raise. A closed vocabulary: a kernel that installs
#: a handler for a vector that does not exist has a bug, not a policy.
VECTORS = {
    0: "divide_error",
    6: "invalid_opcode",
    8: "double_fault",
    13: "general_protection",
    14: "page_fault",
    32: "timer_tick",
}
EXCEPTIONS = (0, 6, 8, 13, 14)
IRQS = (32,)

#: the error code's three bits, as x86 spells them
FAULT_PROTECTION = 1
FAULT_WRITE = 2
FAULT_USER = 4

#: the reasons a `PageFault` can carry, in the order the walk decides them
FAULT_REASONS = ("not_present", "supervisor", "read_only", "no_execute",
                 "not_user")


class MachineError(ValueError):
    """Raised for anything the *caller* of this module got wrong."""


class Trap(Exception):
    """What the machine raises: a vector, an error code, an address, a CPU."""

    def __init__(self, vector, error=0, addr=0, cpu=0):
        self.vector = vector
        self.error = error
        self.addr = addr
        self.cpu = cpu
        super().__init__(f"{trap_name(vector)} at {addr:#x} "
                         f"(error {error:#x}, cpu {cpu})")


class PageFault(Trap):
    """A `Trap` on vector 14, with the walk's own word for what went wrong.

    The walk knows *exactly* what went wrong; the error code is the three bits
    x86 would have raised, and those bits are all a handler in the kernel gets.
    Turning them back into a word is stage 4's job, and its words are coarser
    than this one's on purpose — a real CPU cannot tell `supervisor` from
    `no_execute` either.
    """

    def __init__(self, reason, addr, access="read", user=False, cpu=0):
        if reason not in FAULT_REASONS:
            raise MachineError(f"unknown fault reason {reason!r}")
        error = FAULT_PROTECTION if reason in ("read_only", "no_execute",
                                               "supervisor") else 0
        if access == "write":
            error |= FAULT_WRITE
        if user:
            error |= FAULT_USER
        self.reason = reason
        self.access = access
        self.user = bool(user)
        Trap.__init__(self, 14, error, addr, cpu)
        self.args = (f"{self.reason} at {addr:#x} ({access}"
                     f"{', user' if user else ''}, error {error:#x}, "
                     f"cpu {cpu})",)


def trap_name(vector):
    """The word for a vector, or `"unknown"` — never a guess."""
    return VECTORS.get(vector, "unknown")


def entry_of(frame, flags):
    """Pack a frame index and four flags the way the walk expects."""
    if not isinstance(frame, int) or isinstance(frame, bool) or frame < 0:
        raise MachineError(f"a frame index is a non-negative int, not {frame!r}")
    if flags & ~FLAGS_ALL:
        raise MachineError(f"unknown flag bits {flags & ~FLAGS_ALL:#x}")
    return (frame << 4) | flags


def frame_of_entry(entry):
    return entry >> 4


def flags_of_entry(entry):
    return entry & FLAGS_ALL


def frame_of(addr):
    """The frame an address falls in. An address outside RAM is refused."""
    if not 0 <= addr < RAM_BYTES:
        raise MachineError(f"address {addr:#x} is outside RAM "
                           f"(0..{RAM_BYTES - 1:#x})")
    return addr // PAGE_SIZE


def addr_of(frame):
    """The first address of a frame. A frame outside RAM is refused."""
    if not 0 <= frame < FRAME_COUNT:
        raise MachineError(f"frame {frame} is outside RAM (0..{FRAME_COUNT - 1})")
    return frame * PAGE_SIZE


class RAM:
    """The physical memory, and the record of what was done to it."""

    def __init__(self, bytes_=RAM_BYTES):
        self.bytes = bytes_
        self.frames = bytes_ // PAGE_SIZE
        self._data = bytearray(bytes_)
        self.reads = 0
        self.writes = 0

    def _check(self, addr, n):
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise MachineError(f"a length is a non-negative int, not {n!r}")
        if n == 0:
            return
        if addr < 0 or addr + n > self.bytes:
            raise MachineError(f"the range {addr:#x}..{addr + n:#x} is outside "
                               f"RAM (0..{self.bytes - 1:#x})")

    def read(self, addr, n):
        """`n` bytes at a physical address, or a refusal naming both."""
        self._check(addr, n)
        self.reads += 1
        return bytes(self._data[addr:addr + n])

    def write(self, addr, data):
        """Write bytes at a physical address; the whole write or none of it."""
        data = bytes(data)
        self._check(addr, len(data))
        self.writes += 1
        self._data[addr:addr + len(data)] = data

    def frame(self, index):
        """One whole frame, by index."""
        return self.read(addr_of(index), PAGE_SIZE)

    def write_frame(self, index, data):
        """One whole frame, by index: exactly `PAGE_SIZE` bytes, no more."""
        data = bytes(data)
        if len(data) != PAGE_SIZE:
            raise MachineError(f"a frame is {PAGE_SIZE} bytes, not {len(data)}")
        self.write(addr_of(index), data)

    def log(self):
        """What the memory was asked to do: the reads and the writes so far."""
        return {"reads": self.reads, "writes": self.writes}


class MMU:
    """The walk, the TLB, and the counters that prove which one answered."""

    def __init__(self, ram, entries=ENTRIES):
        self.ram = ram
        self.entries = entries
        self._tlb = {}
        self.walks = 0
        self.hits = 0

    def _table_slot(self, table, index):
        """The address of one entry of one table: an entry is 8 bytes."""
        return addr_of(table) + index * 8

    def _read_entry(self, table, index):
        raw = self.ram.read(self._table_slot(table, index), 8)
        return int.from_bytes(raw, "little")

    def _decide(self, entry, access, user):
        """The walk's word for why this entry cannot serve the access, or None.

        The order matters and it is the machine's: a page that is not present is
        not present whatever else its bits say, and a page the kernel may write
        may still not be one a user may write.
        """
        if entry == 0 or not flags_of_entry(entry) & PRESENT:
            return "not_present"
        flags = flags_of_entry(entry)
        if user and not flags & USER:
            return "supervisor"
        if access == "write" and not flags & WRITE:
            return "read_only"
        if access == "exec" and not flags & EXEC:
            return "no_execute"
        return None

    def entry(self, root, vaddr):
        """The second-level entry for an address, walking every table.

        No TLB: this is the walk itself, and the counters say so.
        """
        self.walks += 1
        high = (vaddr // PAGE_SIZE) // self.entries
        low = (vaddr // PAGE_SIZE) % self.entries
        first = self._read_entry(root, high)
        if first == 0 or not flags_of_entry(first) & PRESENT:
            return 0
        return self._read_entry(frame_of_entry(first), low)

    def translate(self, root, vaddr, access="read", user=False):
        """Walk (or remember) the translation of one address.

        Returns `(frame, offset)`. Raises `PageFault` with the walk's own word
        for what went wrong, and remembers only translations that succeeded.
        """
        if access not in ("read", "write", "exec"):
            raise MachineError(f"unknown access {access!r}")
        if not isinstance(vaddr, int) or isinstance(vaddr, bool):
            raise MachineError(f"an address is an int, not {vaddr!r}")
        vpage = vaddr // PAGE_SIZE
        key = (root, vpage)
        entry = self._tlb.get(key)
        if entry is not None:
            self.hits += 1
        else:
            entry = self.entry(root, vaddr)
        reason = self._decide(entry, access, user)
        if reason is not None:
            raise PageFault(reason, vaddr, access, user)
        self._tlb[key] = entry
        return (frame_of_entry(entry), vaddr % PAGE_SIZE)

    def load(self, root, vaddr, n, user=False):
        """Bytes from a virtual address, one frame at a time."""
        out = bytearray()
        while len(out) < n:
            addr = vaddr + len(out)
            frame, offset = self.translate(root, addr, "read", user)
            take = min(n - len(out), PAGE_SIZE - offset)
            out += self.ram.read(addr_of(frame) + offset, take)
        return bytes(out)

    def store(self, root, vaddr, data, user=False):
        """Bytes to a virtual address, one frame at a time."""
        data = bytes(data)
        done = 0
        while done < len(data):
            addr = vaddr + done
            frame, offset = self.translate(root, addr, "write", user)
            take = min(len(data) - done, PAGE_SIZE - offset)
            self.ram.write(addr_of(frame) + offset, data[done:done + take])
            done += take

    def invalidate(self, vpage=None):
        """Forget translations: one page, or every page. Returns how many went.

        **This is the one call a kernel must not forget.** `translate` caches
        without asking, and the cache is only correct while the tables it came
        from do not change behind its back.
        """
        if vpage is None:
            went = len(self._tlb)
            self._tlb = {}
            return went
        went = 0
        for key in [key for key in self._tlb if key[1] == vpage]:
            del self._tlb[key]
            went += 1
        return went

    def cached(self):
        """How many translations the machine is currently remembering."""
        return len(self._tlb)

    def log(self):
        return {"walks": self.walks, "hits": self.hits, "cached": len(self._tlb)}


class Timer:
    """The clock: a counter, and the only way time passes."""

    def __init__(self):
        self.ticks = 0

    def advance(self, n=1):
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise MachineError(f"a tick count is a non-negative int, not {n!r}")
        self.ticks += n
        return self.ticks

    def log(self):
        return {"ticks": self.ticks}


def raise_trap(vector, error=0, addr=0, cpu=0):
    """Raise one trap, from a vector this machine has.

    A trap no vector in `VECTORS` names is a caller's bug: the machine does not
    invent vectors, and a kernel that handles one is handling nothing.
    """
    if vector not in VECTORS:
        raise MachineError(f"{vector} is not a vector this machine has "
                           f"(0, 6, 8, 13, 14, 32)")
    raise Trap(vector, error, addr, cpu)


# --------------------------------------------------------------------------
# The boot handoff.
#
# A firmware hands a kernel a memory map and little else. The map below is the
# fixture set this course starts from, and three of its four defects are the
# ones a kernel that trusts its firmware will not survive.
# --------------------------------------------------------------------------

#: what a region can be. A kernel may only hand out frames from `usable`.
REGION_KINDS = ("usable", "reserved", "kernel", "boot_info", "firmware")

BOOT_MAPS = {
    # what a well-behaved firmware hands over: the kernel image and the boot
    # info are inside the first usable region's address range, and neither may
    # be handed to a process.
    "clean": (
        {"start": 0x00000000, "end": 0x00080000, "kind": "usable"},
        {"start": 0x00080000, "end": 0x000C0000, "kind": "kernel"},
        {"start": 0x000C0000, "end": 0x000C1000, "kind": "boot_info"},
        {"start": 0x000C1000, "end": 0x000F0000, "kind": "usable"},
        {"start": 0x000F0000, "end": 0x00100000, "kind": "firmware"},
    ),
    # two regions claim the same frame, and the second one is `usable`
    "overlap": (
        {"start": 0x00000000, "end": 0x00090000, "kind": "usable"},
        {"start": 0x00080000, "end": 0x000C0000, "kind": "usable"},
        {"start": 0x000C0000, "end": 0x00100000, "kind": "firmware"},
    ),
    # a kind no kernel has ever heard of
    "unknown_kind": (
        {"start": 0x00000000, "end": 0x00080000, "kind": "usable"},
        {"start": 0x00080000, "end": 0x00090000, "kind": "reclaimable"},
        {"start": 0x00090000, "end": 0x00100000, "kind": "firmware"},
    ),
    # an end that is not frame-aligned: a frame that is half usable
    "unaligned": (
        {"start": 0x00000000, "end": 0x00000801, "kind": "usable"},
        {"start": 0x00001000, "end": 0x00100000, "kind": "firmware"},
    ),
    # the list is not sorted, and the kernel is not where a kernel should be
    "unordered": (
        {"start": 0x00090000, "end": 0x00100000, "kind": "firmware"},
        {"start": 0x00000000, "end": 0x00080000, "kind": "usable"},
        {"start": 0x00080000, "end": 0x00090000, "kind": "kernel"},
    ),
    # a map that claims more memory than the machine has
    "too_big": (
        {"start": 0x00000000, "end": 0x00080000, "kind": "usable"},
        {"start": 0x00080000, "end": 0x00200000, "kind": "usable"},
    ),
}

def _near(name, names):
    """The one suggestion rule in this course: within Levenshtein distance 2."""
    best, best_d = None, 3
    for candidate in names:
        d = _levenshtein(str(name), str(candidate))
        if d < best_d:
            best, best_d = candidate, d
    return best


def _levenshtein(a, b):
    if a == b:
        return 0
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def boot_map(name="clean"):
    """A memory map a firmware could hand over, refused by name when it is not one.

    Every call hands back a fresh list of fresh dicts: a stage that edits the map
    it was given must not edit the fixture the next check reads.
    """
    if name not in BOOT_MAPS:
        near = _near(name, tuple(BOOT_MAPS))
        hint = f" (did you mean {near!r}?)" if near else ""
        raise MachineError(f"no boot map named {name!r}{hint}")
    return [dict(region) for region in BOOT_MAPS[name]]


def map_names():
    """The names of the fixtures, sorted: the vocabulary a caller may pass."""
    return tuple(sorted(BOOT_MAPS))
