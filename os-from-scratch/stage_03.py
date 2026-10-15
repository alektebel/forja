"""OS From Scratch — stage 3: The address space, and the translation you forgot to invalidate.

Between a virtual address and the frame that holds its byte stands the two-level
walk `machine.MMU` performs: a root frame the kernel allocates, one second-level
table of 512 entries per 512 pages, and an entry that packs a frame index with
four permission bits. Writing those tables is the kernel's first act of
ownership — and the moment a table exists, the machine starts remembering what it
walked, so *changing* a table is only half of changing a translation.

This stage keeps two things in step: the tables in RAM, which the walk reads and
which the rest of the machine believes, and the kernel's own mirror, a dict of
virtual page to `(frame, flags)`. The mirror is not a cache and must never be
used as one — it is what the kernel *believes*, and the check's job is to prove
belief and hardware agree, entry by entry, through `MMU.entry`.

The mistake the stage exists for is the third leg of the stool: `MMU.translate`
remembers the translation it walked, and only `MMU.invalidate` makes it forget. A
kernel that removes a page from the tables and does not invalidate it has removed
nothing — the next access is answered out of the TLB, with no walk, no fault and
no sign that anything changed. `MMU.log()`'s `hits` and `cached` are the world's
own record of that, and this stage is graded against them.

    ADDRESS_WIDTH   the whole space: every entry of both levels
    new_space       a root frame from the pool, zeroed, and an empty mirror
    map_page        the one door that writes both the tables and the mirror
    unmap_page      remove a translation, clear its entry, invalidate its page
    protect         change a page's permissions, and invalidate it
    lookup          the mirror's answer for an address, never a walk
    mapped          the mirror as `(vpage, frame, flags)`, ascending
    space_frames    every frame the space owns: root, tables, mapped pages
    free_space      release them all, and forget every translation

`SpaceError` is the refusal: any space, address, frame or flag set this kernel
cannot build a translation on — from an address past the end of the space to a
caller who passes the `PRESENT` bit, which is the kernel's to set.

DESIGN DECISION — why does the kernel keep a *mirror* of its own page tables?
Walking the tables answers the same question, one frame-sized read at a time, and
it is what the machine does anyway. The mirror exists because "what does this
space hold" is asked by the frame ledger, by `fork` and by the check itself, over
and over, and because a walk that disagrees with the kernel's belief is a bug
worth catching rather than hiding. The mirror is only honest while it is written
by the same act that writes the tables, which is why `map_page` is the only
function allowed to write either.

DESIGN DECISION — why are a mapping's flags *permissions*, and `PRESENT` the
kernel's own bit?
A caller that could set `PRESENT` could also clear it, and a page table is not
where that decision is made: presence is what "this page is mapped" means, and
only `map_page`, `unmap_page` and `protect` may say it. Since an entry of `0` is
how this machine spells "not present", a mapping of frame 0 is still a nonzero
entry — which is exactly why presence must be added by the kernel and never
borrowed from the caller's flags.

DESIGN DECISION — why does `map_page` write both the tables and the mirror?
Because a mirror written by a second call is a mirror that can be forgotten, and
a table written without the mirror is a translation the kernel cannot see. One
call that does both means every later question — `lookup`, `mapped`,
`space_frames` — is answered from a structure that was true the moment the
translation became true, and the check can prove it by walking the tables.

DESIGN DECISION — why must `unmap_page` and `protect` invalidate, while `map_page`
does not have to?
`map_page` installs a translation that did not exist, so the machine has nothing
remembered to serve: a stale TLB entry for that page can only come from a root
frame that was freed and reused, and `free_space` invalidates everything it drops
for exactly that reason. `unmap_page` and `protect` change a page the machine may
already be remembering, and a cache that is older than the tables is a cache that
serves the translation the kernel just removed.

DESIGN DECISION — why does `unmap_page` not free the frame it removes?
Because the mapping and the frame are two different owners' business: the kernel
owns the translation, the caller owns the frame, and an unmap that released the
frame would take a page away from whoever is still using it — the classic
unmap-then-fault that hands the same frame to two owners. The table stays too,
even when the unmap empties it: freeing it would make the next mapping of the
same page allocate a table the machine may still be walking.

TODO: implement `new_space`, `map_page`, `unmap_page`, `protect`, `lookup`,
`mapped`, `space_frames` and `free_space`.
"""

import machine

ADDRESS_WIDTH = machine.PAGE_SIZE * machine.ENTRIES * machine.ENTRIES


class SpaceError(ValueError):
    """An address space this kernel cannot build, or cannot read back."""


def new_space(mmu, pool):
    """A fresh address space: a root frame from the pool, zeroed, and no maps.

    The root is zeroed in RAM before anything is installed in it, because a frame
    the pool handed back has held somebody else's tables: an entry nobody wrote
    is an entry that still points at whatever was there.
    """
    raise NotImplementedError("stage 3: implement new_space()")


def map_page(mmu, pool, space, vaddr, frame, flags):
    """Install one translation in the tables *and* in the mirror.

    Allocates and zeroes the page's second-level table when its first level is
    empty, counts it in `space["tables"]`, and returns `{"tables": (the frames it
    consumed,), "entry": the entry it installed}` — the entry carrying `PRESENT`
    plus the caller's permissions.
    """
    raise NotImplementedError("stage 3: implement map_page()")


def unmap_page(mmu, space, vaddr):
    """Remove one translation: the mirror, the table entry, and the TLB's copy.

    Returns `{"frame", "flags"}` of the page it removed and does **not** free the
    frame: the caller owns it, and the table stays even when it is now empty.
    """
    raise NotImplementedError("stage 3: implement unmap_page()")


def protect(mmu, space, vaddr, flags):
    """Change a mapped page's permissions: the table entry, the mirror, the TLB."""
    raise NotImplementedError("stage 3: implement protect()")


def lookup(space, vaddr):
    """What the kernel believes about an address: `(frame, flags)` or `None`.

    The mirror only — never a walk, and never a read of RAM. An address past the
    end of the space is not mapped, and an address that is not an int, or is
    negative, is refused.
    """
    raise NotImplementedError("stage 3: implement lookup()")


def mapped(space):
    """The mirror as `(vpage, frame, flags)`, sorted by page."""
    raise NotImplementedError("stage 3: implement mapped()")


def space_frames(space):
    """Every frame the space owns, ascending: its root, its tables, its pages."""
    raise NotImplementedError("stage 3: implement space_frames()")


def free_space(mmu, pool, space):
    """Release every frame the space owns and forget every translation it had.

    Returns the frames it released, ascending. The space is spent afterwards.
    """
    raise NotImplementedError("stage 3: implement free_space()")
