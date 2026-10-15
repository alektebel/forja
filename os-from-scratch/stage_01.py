"""OS From Scratch — stage 1: The map you were handed.

Before a kernel can manage memory it has to be told what memory *is*, and it is
told by a firmware that is usually right and occasionally not. The map is a list
of regions — `start` (inclusive), `end` (exclusive), and a kind — and the whole
job of this stage is to make it something the rest of the kernel may stand on:
sorted, disjoint, frame-aligned, inside the machine, and with every kind a word
this machine actually has. A kernel that skips that step does not fail loudly; it
hands a frame to two owners, or reserves the frame its own code lives in, and
finds out a thousand instructions later.

The other half of the stage is the question the map exists to answer: *which
frames may I hand out?* Not "all of RAM", and not "every frame a usable range
spans": the frames every `usable` region names, and nothing else. A firmware that
means to keep a hole inside a usable range marks it `reserved` and *ends the
usable region there*, which is why the frames in between belong to nobody and a
kernel that hands them out overwrites whatever the firmware meant to keep.

    REGION_KINDS    the five kinds, re-exported from the machine
    region_frames   the frames a region owns, inclusive of the last
    validate        a fresh sorted disjoint map, or a refusal naming the offender
    usable_frames   the frames this kernel may hand out, ascending
    region_at       which region claims an address (or `None`)
    summary         the frames per kind, the machine's total, and the holes
    holes           the frames no region claims

`BootError` is the family; `MapError` is what a malformed map raises. Every
refusal names the offender: the region, the frame, the kind, or the pair of
regions that disagree.

DESIGN DECISION — why is the map *validated* instead of used as it arrives?
Trusting the firmware is one line shorter and wrong exactly once per machine. The
alternative is a kernel that carries the doubt everywhere: every later function
would have to ask whether it may trust the region it is reading. Validating once,
at the door, turns that doubt into a map the rest of the kernel can be written
against — and the fixtures where the firmware lies are provided precisely so the
door is testable.

DESIGN DECISION — why is the *last* frame of a region inclusive?
`[start, end)` is the machine's convention everywhere else in this course — a
window, a range, a sector — and `end` is exclusive, so the last frame a region
owns is `(end - 1) // PAGE_SIZE`. Writing it the other way (`end // PAGE_SIZE`)
adds a frame to every region, which is invisible on a map whose regions are
adjacent and catastrophic on a map whose regions are not: the extra frame is
usually the next region's first.

DESIGN DECISION — why is a frame *between* two usable regions not handable?
Because the map was validated before it was asked, so the two usable regions
cannot be one region with a hole punched in it: the only way a firmware can keep
the frames in between is by ending one region and starting another. A kernel that
fills that gap hands out memory the firmware said nothing about, and the fixture
is a two-line map that makes the rule impossible to miss.

DESIGN DECISION — why does `validate` return a fresh sorted list rather than
sorting what it was given?
The map came from a firmware, and in this course from a fixture the next check
will read again. Sorting in place would make one check's result depend on the
order another check ran in, which is the exact class of bug this repository
refuses to have — the world's own fixtures are handed over as fresh copies for
the same reason.

DESIGN DECISION — why is a bad region refused as a whole, instead of skipped?
A kernel that skips a region it does not understand is a kernel that has decided
the region does not matter, and it has no way to know that: an unknown kind is a
*newer* machine's kind, a `reserved` frame is somebody's data, and an unaligned
end is a firmware bug that will be a memory corruption later. Refusing the map
turns all three into one honest message.

TODO: implement `region_frames`, `validate`, `usable_frames`, `region_at`,
`summary` and `holes`.
"""

import machine

REGION_KINDS = machine.REGION_KINDS


class BootError(ValueError):
    """A memory map this kernel cannot be built on."""


class MapError(BootError):
    """A map whose *shape* is wrong: a kind, a boundary, an overlap, a key."""


def region_frames(region):
    """The frames one region owns, as `(first, last)`, both inclusive.

    Refuses a region whose shape is wrong — a missing or extra key, an address
    that is not an int, an end that is not frame-aligned, an end before its
    start — naming the offender.
    """
    raise NotImplementedError("stage 1: implement region_frames()")



def validate(regions, ram_bytes=machine.RAM_BYTES):
    """A fresh, sorted, disjoint map, or a refusal naming what is wrong.

    Every kind must be one of `REGION_KINDS` (a name close to one earns a
    suggestion), every region must lie inside `ram_bytes`, no two regions may
    share a frame, and an empty map is refused: a kernel with no memory has
    nothing to hand out and no business starting.
    """
    raise NotImplementedError("stage 1: implement validate()")



def usable_frames(regions, ram_bytes=machine.RAM_BYTES):
    """The frames this kernel may hand out, ascending.

    The frames every `usable` region owns, and nothing else: a frame between two
    usable regions belongs to nobody, and the map is validated first, so a map
    that cannot be trusted is refused rather than partly used.
    """
    raise NotImplementedError("stage 1: implement usable_frames()")



def region_at(regions, addr):
    """The region that claims an address, or `None` when none does.

    The map is validated first. An address outside the machine is not claimed by
    anything and answers `None`; an address that is not an int is refused.
    """
    raise NotImplementedError("stage 1: implement region_at()")



def summary(regions, ram_bytes=machine.RAM_BYTES):
    """The map as counts: one key per kind, the machine, and the holes.

    Every kind in `REGION_KINDS` is present, zeros included, so a caller can
    index the answer without asking whether the key exists. `"frames"` is the
    machine's total and `"holes"` is the number of frames no region claims.
    """
    raise NotImplementedError("stage 1: implement summary()")



def holes(regions, ram_bytes=machine.RAM_BYTES):
    """The frames no region claims, ascending.

    A hole is not an error: a firmware may hand over a map that does not cover
    the machine, and the frames it says nothing about are frames this kernel may
    not use.
    """
    raise NotImplementedError("stage 1: implement holes()")

