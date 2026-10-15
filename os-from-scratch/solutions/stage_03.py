"""OS From Scratch — stage 3: The address space, and the translation you forgot to invalidate.

The tables in RAM are what the machine believes and the mirror is what the kernel
believes: `_space` is the single door the mirror goes through, so a structure this
kernel did not build is refused by name instead of crashing a walk later.
`map_page` is the only writer of the tables, `unmap_page` and `protect` are the
only two functions that change a translation the machine may already be holding,
and both of them call `MMU.invalidate` for the page they changed — a translation
the machine still remembers is a translation the kernel has not finished
removing. `lookup` and `mapped` read the mirror and never walk, so the check can
hold belief and hardware side by side, and `space_frames` is the frame ledger a
caller frees against.
"""

import machine

ADDRESS_WIDTH = machine.PAGE_SIZE * machine.ENTRIES * machine.ENTRIES

_KEYS = ("root", "tables", "maps")
_PERMISSIONS = machine.WRITE | machine.USER | machine.EXEC


class SpaceError(ValueError):
    """An address space this kernel cannot build, or cannot read back."""


def _vpage(vaddr):
    """The virtual page an address falls in; anything that is not one is refused."""
    if isinstance(vaddr, bool) or not isinstance(vaddr, int):
        raise SpaceError("an address is an int, not %r" % (vaddr,))
    if vaddr < 0:
        raise SpaceError("address %d is negative" % (vaddr,))
    return vaddr // machine.PAGE_SIZE


def _frame(frame):
    """A frame index this machine has."""
    if isinstance(frame, bool) or not isinstance(frame, int):
        raise SpaceError("a frame is an int, not %r" % (frame,))
    if not 0 <= frame < machine.FRAME_COUNT:
        raise SpaceError("frame %d is outside RAM (0..%d)"
                         % (frame, machine.FRAME_COUNT - 1))
    return frame


def _flags(flags):
    """The permission bits of a mapping. Presence is the kernel's own bit."""
    if isinstance(flags, (tuple, list)):
        bits = 0
        for bit in flags:
            if isinstance(bit, bool) or not isinstance(bit, int):
                raise SpaceError("a permission bit is an int, not %r" % (bit,))
            bits |= bit
    elif isinstance(flags, bool) or not isinstance(flags, int):
        raise SpaceError("flags are permission bits, not %r" % (flags,))
    else:
        bits = flags
    if bits & machine.PRESENT:
        raise SpaceError("flags %#x carry PRESENT, and presence is the kernel's"
                         % (bits,))
    if bits & ~_PERMISSIONS:
        raise SpaceError("flags %#x are not permission bits (WRITE, USER, EXEC)"
                         % (bits,))
    if bits & machine.WRITE and bits & machine.EXEC:
        raise SpaceError("flags %#x are both WRITE and EXEC, and nothing in this "
                         "machine is writable and executable at once" % (bits,))
    return bits


def _space(space):
    """The mirror's shape, refused by name: the keys, every frame, every page."""
    if not isinstance(space, dict):
        raise SpaceError("a space is a dict, not %r" % (space,))
    missing = [key for key in _KEYS if key not in space]
    if missing:
        raise SpaceError("the space is missing %s" % (", ".join(missing),))
    extra = sorted(set(space) - set(_KEYS))
    if extra:
        raise SpaceError("the space has an extra key %s" % (", ".join(extra),))
    _frame(space["root"])
    if not isinstance(space["tables"], tuple):
        raise SpaceError("tables is a tuple of frames, not %r"
                         % (type(space["tables"]).__name__,))
    for table in space["tables"]:
        _frame(table)
    if not isinstance(space["maps"], dict):
        raise SpaceError("maps is a dict keyed by page, not %r"
                         % (type(space["maps"]).__name__,))
    for vpage, pair in space["maps"].items():
        if isinstance(vpage, bool) or not isinstance(vpage, int) or vpage < 0:
            raise SpaceError("a page number is a non-negative int, not %r"
                             % (vpage,))
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise SpaceError("page %d maps to %r, not (frame, flags)"
                             % (vpage, pair))
        _frame(pair[0])
        _flags(pair[1])
    return space


def _first_entry(mmu, root, high):
    """One first-level entry, read straight out of the root frame in RAM."""
    raw = mmu.ram.read(machine.addr_of(root) + high * 8, 8)
    return int.from_bytes(raw, "little")


def _table(mmu, space, vpage):
    """The second-level table a mapped page's first level points at."""
    first = _first_entry(mmu, space["root"], vpage // machine.ENTRIES)
    if first == 0 or not machine.flags_of_entry(first) & machine.PRESENT:
        raise SpaceError("page %d is in the mirror but its table is not present"
                         % (vpage,))
    return machine.frame_of_entry(first)


def _slot(table, vpage):
    """Where one second-level entry lives: an entry is 8 bytes."""
    return machine.addr_of(table) + (vpage % machine.ENTRIES) * 8


def new_space(mmu, pool):
    """A fresh address space: a root frame from the pool, zeroed, and no maps."""
    root = _frame(pool.alloc(1)[0])
    mmu.ram.write_frame(root, bytes(machine.PAGE_SIZE))
    return {"root": root, "tables": (), "maps": {}}


def map_page(mmu, pool, space, vaddr, frame, flags):
    """Install one translation in the tables *and* in the mirror."""
    _space(space)
    bits = _flags(flags)
    vpage = _vpage(vaddr)
    if vaddr >= ADDRESS_WIDTH:
        raise SpaceError("address %#x is at or past the space (%#x)"
                         % (vaddr, ADDRESS_WIDTH))
    frame = _frame(frame)
    if vpage in space["maps"]:
        raise SpaceError("page %d (address %#x) is already mapped to frame %d"
                         % (vpage, vaddr, space["maps"][vpage][0]))
    high = vpage // machine.ENTRIES
    first = _first_entry(mmu, space["root"], high)
    consumed = ()
    if first == 0 or not machine.flags_of_entry(first) & machine.PRESENT:
        table = _frame(pool.alloc(1)[0])
        mmu.ram.write_frame(table, bytes(machine.PAGE_SIZE))
        mmu.ram.write(machine.addr_of(space["root"]) + high * 8,
                      machine.entry_of(table, machine.PRESENT
                                       | machine.WRITE).to_bytes(8, "little"))
        space["tables"] = space["tables"] + (table,)
        consumed = (table,)
    else:
        table = machine.frame_of_entry(first)
    entry = machine.entry_of(frame, bits | machine.PRESENT)
    mmu.ram.write(_slot(table, vpage), entry.to_bytes(8, "little"))
    space["maps"][vpage] = (frame, bits)
    return {"tables": consumed, "entry": entry}


def unmap_page(mmu, space, vaddr):
    """Remove one translation: the mirror, the table entry, and the TLB's copy."""
    _space(space)
    vpage = _vpage(vaddr)
    if vpage not in space["maps"]:
        raise SpaceError("page %d (address %#x) is not mapped" % (vpage, vaddr))
    table = _table(mmu, space, vpage)
    frame, bits = space["maps"].pop(vpage)
    mmu.ram.write(_slot(table, vpage), bytes(8))
    mmu.invalidate(vpage)
    return {"frame": frame, "flags": bits}


def protect(mmu, space, vaddr, flags):
    """Change a mapped page's permissions: table entry, mirror, and the TLB."""
    _space(space)
    bits = _flags(flags)
    vpage = _vpage(vaddr)
    if vpage not in space["maps"]:
        raise SpaceError("page %d (address %#x) is not mapped" % (vpage, vaddr))
    frame = space["maps"][vpage][0]
    table = _table(mmu, space, vpage)
    entry = machine.entry_of(frame, bits | machine.PRESENT)
    mmu.ram.write(_slot(table, vpage), entry.to_bytes(8, "little"))
    space["maps"][vpage] = (frame, bits)
    mmu.invalidate(vpage)
    return {"frame": frame, "flags": bits}


def lookup(space, vaddr):
    """What the kernel believes about an address: `(frame, flags)` or `None`."""
    _space(space)
    vpage = _vpage(vaddr)
    return space["maps"].get(vpage)


def mapped(space):
    """The mirror as `(vpage, frame, flags)`, sorted by page."""
    _space(space)
    return tuple((vpage, frame, flags)
                 for vpage, (frame, flags) in sorted(space["maps"].items()))


def space_frames(space):
    """Every frame the space owns, ascending: its root, its tables, its pages."""
    _space(space)
    frames = {space["root"]}
    frames.update(space["tables"])
    frames.update(frame for frame, _ in space["maps"].values())
    return tuple(sorted(frames))


def free_space(mmu, pool, space):
    """Release every frame the space owns and forget every translation it had."""
    frames = space_frames(space)
    for frame in frames:
        pool.free(frame)
    mmu.invalidate()
    return frames
