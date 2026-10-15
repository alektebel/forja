"""OS From Scratch — stage 1: The map you were handed.

The map is the kernel's first input and the one it can never re-read: whatever
the firmware said is true stays true for the life of the machine, which is why
every later stage takes a validated map and never a raw one. `_shape` is the
single door every region goes through, `validate` is the single door every map
does, and the three questions the rest of the course asks — which frames may I
hand out, which region owns this address, how much memory is there — are all
answered from the validated copy and never from the caller's list.
"""

import machine

REGION_KINDS = machine.REGION_KINDS

_KEYS = ("start", "end", "kind")


class BootError(ValueError):
    """A memory map this kernel cannot be built on."""


class MapError(BootError):
    """A map whose *shape* is wrong: a kind, a boundary, an overlap, a key."""


def _where(region):
    return "region %#x..%#x" % (region["start"], region["end"])


def _shape(region, where="region"):
    """The three keys exactly, both ends framed, and a kind this machine has."""
    if not isinstance(region, dict):
        raise MapError("%s is not a region: %r" % (where, region))
    keys = set(region)
    missing = [key for key in _KEYS if key not in keys]
    if missing:
        raise MapError("%s is missing %s" % (where, ", ".join(missing)))
    extra = sorted(keys - set(_KEYS))
    if extra:
        raise MapError("%s has an extra key %s" % (where, ", ".join(extra)))
    for key in ("start", "end"):
        value = region[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise MapError("%s: %s is %r, and an address is an int" % (where, key, value))
        if value < 0:
            raise MapError("%s: %s is %d, and an address is not negative" % (where, key, value))
        if value % machine.PAGE_SIZE:
            raise MapError("%s: %s %#x is not a frame boundary" % (where, key, value))
    if region["end"] <= region["start"]:
        raise MapError("%s ends at %#x, which is not after its start (%#x)"
                       % (where, region["end"], region["start"]))
    kind = region["kind"]
    if not isinstance(kind, str):
        raise MapError("%s: kind is %r, not a word" % (where, kind))
    if kind not in REGION_KINDS:
        near = machine._near(kind, REGION_KINDS)
        hint = " (did you mean %r?)" % (near,) if near else ""
        raise MapError("%s: %r is not a region kind%s" % (where, kind, hint))
    return region


def _frames_of(region):
    """Every frame a region owns, ascending: `end` is exclusive."""
    return range(region["start"] // machine.PAGE_SIZE,
                 region["end"] // machine.PAGE_SIZE)


def region_frames(region):
    """The frames one region owns, as `(first, last)`, both inclusive."""
    _shape(region)
    first = region["start"] // machine.PAGE_SIZE
    last = region["end"] // machine.PAGE_SIZE - 1
    return (first, last)


def validate(regions, ram_bytes=machine.RAM_BYTES):
    """A fresh, sorted, disjoint map, or a refusal naming what is wrong."""
    if isinstance(regions, bool) or not isinstance(regions, (list, tuple)):
        raise MapError("a map is a list of regions, not %s" % (type(regions).__name__,))
    if not regions:
        raise MapError("an empty map: a kernel with no memory cannot start")
    clean = []
    for index, region in enumerate(regions):
        clean.append(dict(_shape(region, "region %d" % (index,))))
    for region in clean:
        if region["end"] > ram_bytes:
            raise MapError("%s ends at %#x, past the machine (%#x)"
                           % (_where(region), region["end"], ram_bytes))
    clean.sort(key=lambda region: (region["start"], region["end"]))
    for before, after in zip(clean, clean[1:]):
        if after["start"] < before["end"]:
            first = after["start"] // machine.PAGE_SIZE
            last = before["end"] // machine.PAGE_SIZE - 1
            raise MapError("%s (%s) and %s (%s) share frame%s %d..%d"
                           % (_where(before), before["kind"], _where(after),
                              after["kind"], "" if first == last else "s", first, last))
    return clean


def usable_frames(regions, ram_bytes=machine.RAM_BYTES):
    """The frames this kernel may hand out, ascending."""
    clean = validate(regions, ram_bytes)
    handable = []
    for region in clean:
        if region["kind"] == "usable":
            handable.extend(_frames_of(region))
    return tuple(handable)


def region_at(regions, addr):
    """The region that claims an address, or `None` when none does."""
    if isinstance(addr, bool) or not isinstance(addr, int):
        raise MapError("an address is an int, not %r" % (addr,))
    if addr < 0:
        raise MapError("address %d is negative" % (addr,))
    for region in validate(regions):
        if region["start"] <= addr < region["end"]:
            return dict(region)
    return None


def summary(regions, ram_bytes=machine.RAM_BYTES):
    """The map as counts: one key per kind, the machine, and the holes."""
    clean = validate(regions, ram_bytes)
    counts = {kind: 0 for kind in REGION_KINDS}
    for region in clean:
        counts[region["kind"]] += len(_frames_of(region))
    machine_frames = ram_bytes // machine.PAGE_SIZE
    counts["frames"] = machine_frames
    counts["holes"] = machine_frames - sum(
        count for kind, count in counts.items() if kind in REGION_KINDS)
    return counts


def holes(regions, ram_bytes=machine.RAM_BYTES):
    """The frames no region claims, ascending."""
    clean = validate(regions, ram_bytes)
    claimed = set()
    for region in clean:
        claimed.update(_frames_of(region))
    return tuple(frame for frame in range(ram_bytes // machine.PAGE_SIZE)
                 if frame not in claimed)
