"""OS From Scratch — course manifest.

Ten graded stages between a machine that keeps records and a kernel whose every
decision can be held against them. The world is provided and complete:
`machine.py` is RAM, a real two-level page walk with a TLB that only
`MMU.invalidate` empties, traps and page faults that carry the walk's own word
for what went wrong, a tick counter, and six boot maps including the ones where
the firmware lies (`overlap`, `unknown_kind`, `unaligned`, `unordered`,
`too_big`); `devices.py` is a console that keeps every byte and a disk whose
writes are buffered until a barrier, with `power_fail(tear=True)` for the sector
that lands half new and half old; `userland.py` is the programs, as scripts of
syscalls, and the filesystem the course's own formatter is asked to build.

The thesis of the whole course is one sentence, and every stage's check asserts
it: AN OPERATING SYSTEM IS WHAT YOU WRITE AFTER THE HARDWARE BREAKS YOUR LAST
PROMISE. Each stage exists because the one before it left a hole: you cannot
trust memory until you have read the map the firmware handed you; a map with no
allocator is a map you cannot use twice, and the allocator's own bitmap has to
live inside the pool it tracks; an address space whose translation cache was
never invalidated serves the page you removed; a fault with nowhere to go is a
dead machine, and a fault with a reason is a decision; a kernel that trusts a
user pointer dereferences anything, so the pointer is checked before a byte of it
is touched; a process that forgets one frame leaks it forever, and the frame pool
is where that is proved; a task that checks a condition and then sleeps loses the
wakeup that happened in between; two CPUs in one critical section lose an update,
and a lock held across a yield is held for as long as somebody else takes; a
write that was not put behind a barrier is a write that never happened, so the
filesystem's format is written in an order that a power failure cannot make
wrong; and only a userland can prove any of it, which is why the last stage runs
programs and checks the console against them.

The failures worth preventing are the ones that look like success: a region's
last frame claimed by two owners, a bitmap handed out as a frame, a page table
left full of garbage, a TLB serving a translation that is gone, a kernel fault
read as a user fault, a length checked but not the access, a fork that shares its
parent's frames, a wakeup lost between two calls, a deferred CPU whose steps ran
early, a superblock written before the data it points at, and a report counted
from the kernel's beliefs instead of its log.

Standard library only, offline, deterministic, **ints only** (every address,
frame, sector, size, tick and uid — there is no float literal anywhere in this
course): no `time`, no `threading`, no `asyncio`, no `random`, no `os`, no
sockets, no subprocesses, no wall clock, no module-level mutable state, and no
`statistics`, `math`, `decimal` or `fractions` either — the three of them would
decide by themselves which page a byte belongs to, and that is the thing this
course exists to decide by hand. The clock is `machine.Timer`, time passes only
when a caller says so, and every ratio the course needs is an exact integer.

The salvaged curriculum in `linux-from-scratch/` is the other half of this unit:
176 exercises on real hardware across fifteen phases, and its own README says it
cannot ship a checker. This is that checker, on a machine small enough to grade.

    python3 codecraft/cli.py run os-from-scratch
"""

from codecraft.api import stage

TITLE = "OS From Scratch"
DESCRIPTION = ("A fault as the input and a promise as the output: the memory map "
               "the firmware hands over and the frames it leaves usable, a frame "
               "allocator whose bitmap lives inside the pool it tracks, an address "
               "space whose translations are invalidated or they are lies, a trap "
               "table where a fault is decided rather than fatal, a syscall "
               "boundary that checks a user pointer before it touches it, "
               "processes whose frames are all released, a scheduler that cannot "
               "lose a wakeup, two CPUs that cannot lose an update, an on-disk "
               "format whose writes are ordered so a power failure cannot make it "
               "wrong, and a userland whose console output and frame pool are the "
               "proof that the kernel kept every promise it made.")
LEVEL = "advanced"
ORDER = 25


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _region(start, end, kind):
        return {"start": start, "end": end, "kind": kind}

    import machine
    import stage_01 as s

    page = machine.PAGE_SIZE

    # ---- the constants and the refusal family -----------------------------

    assert s.REGION_KINDS == machine.REGION_KINDS, (
        "this stage's kinds are %r, not the machine's" % (s.REGION_KINDS,))
    assert tuple(s.REGION_KINDS) == ("usable", "reserved", "kernel", "boot_info",
                                     "firmware"), (
        "the kinds are %r in the wrong order or with the wrong members"
        % (s.REGION_KINDS,))
    assert issubclass(s.BootError, ValueError), (
        "BootError is not a ValueError: %r" % (s.BootError,))
    assert issubclass(s.MapError, s.BootError), (
        "MapError is not a BootError: %r" % (s.MapError,))

    clean = machine.boot_map("clean")

    # ---- region_frames: inclusive, and one frame is a region too -----------

    got = s.region_frames(_region(0, 128 * page, "usable"))
    assert got == (0, 127), "a region 0..0x80000 owns frames 0..127, not %r" % (got,)
    got = s.region_frames(_region(0x80000, 0xC0000, "kernel"))
    assert got == (128, 191), "the kernel region is frames 128..191, not %r" % (got,)
    got = s.region_frames(_region(3 * page, 4 * page, "usable"))
    assert got == (3, 3), "a region of one frame is (3, 3), not %r" % (got,)
    got = s.region_frames(_region(machine.RAM_BYTES - page, machine.RAM_BYTES,
                                  "firmware"))
    assert got == (255, 255), "the machine's last frame is 255, not %r" % (got,)

    message = _refuses(s.MapError, "region_frames of a missing key",
                       lambda: s.region_frames({"start": 0, "kind": "usable"}))
    assert "end" in message, (
        "a region without an end must be refused naming `end`, got %r" % (message,))
    message = _refuses(s.MapError, "region_frames of an extra key",
                       lambda: s.region_frames({"start": 0, "end": page,
                                                "kind": "usable", "owner": 1}))
    assert "owner" in message, (
        "an extra key must be named in the refusal, got %r" % (message,))
    _refuses(s.MapError, "region_frames of a bool address",
             lambda: s.region_frames(_region(False, page, "usable")))
    _refuses(s.MapError, "region_frames of a float address",
             lambda: s.region_frames(_region(0, float(page), "usable")))
    _refuses(s.MapError, "region_frames of a negative address",
             lambda: s.region_frames(_region(-page, page, "usable")))
    message = _refuses(s.MapError, "region_frames of an unaligned end",
                       lambda: s.region_frames(_region(0, 0x801, "usable")))
    assert "0x801" in message, (
        "an unaligned end must name the address, got %r" % (message,))
    _refuses(s.MapError, "region_frames of an end before its start",
             lambda: s.region_frames(_region(4 * page, 2 * page, "usable")))
    _refuses(s.MapError, "region_frames of a region with no frames at all",
             lambda: s.region_frames(_region(4 * page, 4 * page, "usable")))
    _refuses(s.MapError, "region_frames of a kind that is not a word",
             lambda: s.region_frames(_region(0, page, 7)))
    message = _refuses(s.MapError, "region_frames of a near-miss kind",
                       lambda: s.region_frames(_region(0, page, "usablee")))
    assert "usable" in message.replace("usablee", ""), (
        "a kind one edit from a real one must be told what it probably meant, "
        "got %r" % (message,))
    message = _refuses(s.MapError, "region_frames of a far kind",
                       lambda: s.region_frames(_region(0, page, "squatter")))
    assert "did you mean" not in message, (
        "a kind that is not close to any real one must not suggest one: %r"
        % (message,))
    _refuses(s.MapError, "region_frames of something that is not a dict",
             lambda: s.region_frames((0, page, "usable")))

    # ---- validate: sorted, disjoint, in the machine, and fresh ------------

    unordered = machine.boot_map("unordered")
    ordered = s.validate(unordered)
    assert [r["kind"] for r in ordered] == ["usable", "kernel", "firmware"], (
        "validate must sort the map rather than refuse it: got %r"
        % ([r["kind"] for r in ordered],))
    assert all(ordered[i]["end"] == ordered[i + 1]["start"]
               for i in range(len(ordered) - 1)), (
        "the sorted map is not disjoint: %r" % (ordered,))
    assert ordered[-1]["end"] == machine.RAM_BYTES, (
        "the sorted map does not reach the end of the machine: %r" % (ordered,))
    assert all(a is not b for a, b in zip(ordered, unordered)), (
        "validate handed back the caller's own dicts")
    ordered[0]["start"] = 123456
    again = s.validate(unordered)
    assert again[0]["start"] == 0, (
        "editing the answer must not edit the fixture: %r" % (again[0],))

    message = _refuses(s.MapError, "validate of an overlapping map",
                       lambda: s.validate(machine.boot_map("overlap")))
    assert "0x0..0x90000" in message and "0x80000..0xc0000" in message, (
        "an overlap must name both regions, got %r" % (message,))
    assert "128..143" in message, (
        "an overlap must name the frames they share, in order, got %r" % (message,))
    message = _refuses(s.MapError, "validate of an unknown kind",
                       lambda: s.validate(machine.boot_map("unknown_kind")))
    assert "reclaimable" in message, (
        "an unknown kind must be named, got %r" % (message,))
    message = _refuses(s.MapError, "validate of an unaligned region",
                       lambda: s.validate(machine.boot_map("unaligned")))
    assert "0x801" in message, (
        "an unaligned region must name the address, got %r" % (message,))
    message = _refuses(s.MapError, "validate of a map past the machine",
                       lambda: s.validate(machine.boot_map("too_big")))
    assert "0x200000" in message and "0x100000" in message, (
        "a map past the machine must name the address and the machine, got %r"
        % (message,))
    message = _refuses(s.MapError, "validate of an empty map", lambda: s.validate([]))
    assert "empty" in message, (
        "an empty map must be refused as empty, got %r" % (message,))
    message = _refuses(s.MapError, "validate of something that is not a list",
                       lambda: s.validate("clean"))
    assert "list" in message, (
        "the refusal must say what a map is, got %r" % (message,))

    exact = s.validate([_region(0, machine.RAM_BYTES, "usable")])
    assert exact[0]["end"] == machine.RAM_BYTES, (
        "a region ending exactly at the machine is legal: %r" % (exact,))
    _refuses(s.MapError, "validate of one frame past the machine",
             lambda: s.validate([_region(0, machine.RAM_BYTES + page, "usable")]))
    holed = s.validate([_region(0, 4 * page, "usable"),
                        _region(8 * page, 16 * page, "usable")])
    assert len(holed) == 2, (
        "a map with a hole is a map: %r" % (holed,))

    # ---- usable_frames ----------------------------------------------------

    usable = s.usable_frames(clean)
    assert len(usable) == 175, (
        "the clean map hands out 175 of 256 frames, not %d" % (len(usable),))
    assert usable[:2] == (0, 1) and usable[-1] == 239, (
        "the handable frames run from 0 to 239: %r" % (usable,))
    assert all(frame not in usable for frame in (128, 191, 192, 240, 255)), (
        "a kernel, boot_info or firmware frame is handable: %r" % (usable,))
    assert list(usable) == sorted(set(usable)), (
        "the handable frames are not ascending and distinct: %r" % (usable,))
    split = s.usable_frames([_region(0, 2 * page, "usable"),
                             _region(2 * page, 3 * page, "reserved"),
                             _region(3 * page, 8 * page, "usable")])
    assert split == (0, 1, 3, 4, 5, 6, 7), (
        "a reserved region between two usable ones is not handable: %r" % (split,))
    assert s.usable_frames([_region(0, 4 * page, "reserved")]) == (), (
        "a map with nothing usable hands out nothing")
    _refuses(s.MapError, "usable_frames validates before it answers",
             lambda: s.usable_frames(machine.boot_map("overlap")))

    # ---- region_at --------------------------------------------------------

    assert s.region_at(clean, 0x80000)["kind"] == "kernel", (
        "the first address of the kernel region is in it")
    assert s.region_at(clean, 0xBFFFF)["kind"] == "kernel", (
        "the last address of the kernel region is in it")
    assert s.region_at(clean, 0xC0000)["kind"] == "boot_info", (
        "the boundary belongs to the region that starts there")
    assert s.region_at([_region(0, 4 * page, "usable")], 8 * page) is None, (
        "an address the map does not cover answers None")
    assert s.region_at(clean, machine.RAM_BYTES) is None, (
        "an address past the machine answers None")
    _refuses(s.MapError, "region_at of a negative address",
             lambda: s.region_at(clean, -1))
    _refuses(s.MapError, "region_at of a float address",
             lambda: s.region_at(clean, 1.5))
    _refuses(s.MapError, "region_at validates the map",
             lambda: s.region_at(machine.boot_map("unaligned"), 0))

    # ---- summary and holes ------------------------------------------------

    counts = s.summary(clean)
    assert tuple(counts) == ("usable", "reserved", "kernel", "boot_info",
                             "firmware", "frames", "holes"), (
        "summary's keys are %r, not the five kinds plus frames and holes"
        % (tuple(counts),))
    assert counts["usable"] == 175 and counts["kernel"] == 64, (
        "summary's counts are wrong: %r" % (counts,))
    assert counts["boot_info"] == 1 and counts["firmware"] == 16, (
        "summary's counts are wrong: %r" % (counts,))
    assert counts["reserved"] == 0 and counts["frames"] == 256, (
        "summary must report every kind and the machine's own total: %r"
        % (counts,))
    assert counts["holes"] == 0, (
        "the clean map leaves no holes: %r" % (counts,))
    holed = [_region(0, 4 * page, "usable"), _region(8 * page, 16 * page, "usable")]
    assert s.summary(holed)["holes"] == len(s.holes(holed)), (
        "summary's holes count and holes() must agree: %r vs %r"
        % (s.summary(holed), s.holes(holed)))
    assert s.summary(holed)["frames"] == 256, (
        "summary's frames are the machine's, not the map's: %r" % (s.summary(holed),))
    got = s.holes(holed)
    want = tuple(range(4, 8)) + tuple(range(16, 256))
    assert got == want, (
        "the frames no region claims are 4..7 and 16..255, not %r" % (got[:6],))
    assert s.holes(clean) == (), "the clean map has no holes"
    got = s.holes([_region(0, 4 * page, "usable")])
    assert got == tuple(range(4, 256)), (
        "a map that stops early leaves the rest as holes: %r" % (got[:4],))
    _refuses(s.MapError, "summary validates the map",
             lambda: s.summary(machine.boot_map("too_big")))
    _refuses(s.MapError, "holes validates the map",
             lambda: s.holes(machine.boot_map("unaligned")))

    # ---- and the world is where it was ------------------------------------

    assert machine.boot_map("clean") == clean, (
        "the clean fixture changed while the stage ran: %r" % (machine.boot_map("clean"),))
    got = s.holes([_region(0, page, "usable"), _region(8 * page, 16 * page, "usable")])
    assert list(got) == sorted(set(got)), "holes are not ascending: %r" % (got,)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _packed(bits):
        """The bytes a bitmap of these bits holds: bit `k` is `k % 8` of byte `k // 8`."""
        out = bytearray((len(bits) + 7) // 8)
        for index, bit in enumerate(bits):
            if bit:
                out[index // 8] |= 1 << (index % 8)
        return bytes(out)

    import machine
    import stage_01 as s1
    import stage_02 as s

    # ---- the constants and the refusal family -----------------------------

    assert (s.FREE, s.USED, s.BITMAP) == ("free", "used", "bitmap"), (
        "the three states are %r, %r and %r, not 'free', 'used' and 'bitmap'"
        % (s.FREE, s.USED, s.BITMAP))
    assert issubclass(s.FramesError, ValueError), (
        "FramesError is not a ValueError: %r" % (s.FramesError,))

    # ---- a small pool: nine frames, so two bitmap bytes -------------------

    pool = (4, 5, 6, 7, 8, 9, 10, 11, 12)
    ram = machine.RAM()
    f = s.Frames(ram, pool)

    assert isinstance(f, s.Frames), "Frames(ram, pool) is not a Frames: %r" % (f,)
    assert f.bitmap_bytes() == 2, (
        "nine pool frames need two bitmap bytes, not %d" % (f.bitmap_bytes(),))
    assert f.bits() == (0,) * 9, (
        "a fresh pool's bitmap is all free, not %r" % (f.bits(),))
    assert f.used() == (), (
        "a fresh pool has handed nothing out, but used() is %r" % (f.used(),))
    assert f.free_count() == 8, (
        "nine frames minus the bitmap leave eight free, not %d" % (f.free_count(),))
    assert tuple(f.log()) == ("alloc", "free", "refused", "frames_out"), (
        "log's keys are %r, not alloc/free/refused/frames_out" % (tuple(f.log()),))
    assert f.log() == {"alloc": 0, "free": 0, "refused": 0,
                       "frames_out": ()}, (
        "a fresh pool's log is zero everywhere, not %r" % (f.log(),))

    # ---- state: the five answers, and outside is answered ----------------

    assert f.state(4) == s.BITMAP, (
        "the pool's first frame holds the bitmap, but state(4) is %r"
        % (f.state(4),))
    assert f.state(5) == s.FREE, (
        "a frame nobody holds is free, but state(5) is %r" % (f.state(5),))
    assert f.state(12) == s.FREE, (
        "the pool's last frame is free too, but state(12) is %r" % (f.state(12),))
    assert f.state(3) == "outside", (
        "a frame the pool does not hold is outside, not %r" % (f.state(3),))
    assert f.state(13) == "outside", (
        "the frame after the pool is outside, not %r" % (f.state(13),))
    assert f.state(-1) == "outside", (
        "a negative frame is outside, not %r" % (f.state(-1),))
    assert f.state(machine.FRAME_COUNT) == "outside", (
        "a frame past the machine is outside, not %r"
        % (f.state(machine.FRAME_COUNT),))

    # ---- alloc: ascending, distinct, and written into the bitmap in RAM ----

    before = ram.log()["writes"]
    taken = f.alloc(3)
    after = ram.log()["writes"]
    assert taken == (5, 6, 7), (
        "alloc(3) on a fresh pool is frames 5, 6 and 7 — frame 4 is the bitmap — "
        "not %r" % (taken,))
    assert isinstance(taken, tuple), (
        "alloc hands back a tuple, not %r" % (type(taken).__name__,))
    assert list(taken) == sorted(set(taken)), (
        "the frames alloc hands out are ascending and distinct: %r" % (taken,))
    assert after > before, (
        "handing a frame out must write the bitmap into RAM: writes stayed at %d"
        % (before,))
    assert f.used() == (5, 6, 7), (
        "the frames handed out are 5, 6 and 7, not %r" % (f.used(),))
    assert f.state(5) == s.USED, (
        "a frame that was handed out is used, not %r" % (f.state(5),))
    assert f.free_count() == 5, (
        "three frames handed out leave five free, not %d" % (f.free_count(),))
    assert f.bits() == (0, 1, 1, 1, 0, 0, 0, 0, 0), (
        "one bit per pool frame, in pool order, is (0, 1, 1, 1, 0, ...), not %r"
        % (f.bits(),))
    assert ram.read(machine.addr_of(4), 2) == bytes((14, 0)), (
        "the bitmap in RAM holds bit 1, 2 and 3 of its first byte (0x0e), not %r"
        % (ram.read(machine.addr_of(4), 2),))
    assert f.log() == {"alloc": 3, "free": 0, "refused": 0,
                       "frames_out": (5, 6, 7)}, (
        "three frames allocated are three frames in the log, not %r" % (f.log(),))

    # ---- alloc: all or nothing, and the count must be a count -------------

    message = _refuses(s.FramesError, "alloc of more frames than are free",
                       lambda: f.alloc(f.free_count() + 1))
    assert "alloc(6)" in message, (
        "the refusal must name the request, got %r" % (message,))
    assert "5" in message, (
        "the refusal must name the free count, got %r" % (message,))
    assert f.free_count() == 5 and f.used() == (5, 6, 7), (
        "a refused alloc must change nothing: free_count %d, used %r"
        % (f.free_count(), f.used()))
    assert f.bits() == (0, 1, 1, 1, 0, 0, 0, 0, 0), (
        "a refused alloc must not touch the bitmap: %r" % (f.bits(),))

    message = _refuses(s.FramesError, "alloc(-1)",
                       lambda: f.alloc(-1))
    assert "-1" in message, (
        "a negative count must be named in the refusal, got %r" % (message,))
    _refuses(s.FramesError, "alloc(True)", lambda: f.alloc(True))
    _refuses(s.FramesError, "alloc of a fractional count", lambda: f.alloc(1.5))
    assert f.log()["refused"] == 4, (
        "four refusals so far are four in the log, not %r" % (f.log()["refused"],))

    assert f.alloc(0) == (), (
        "alloc(0) hands out nothing, not %r" % (f.alloc(0),))
    assert f.log() == {"alloc": 3, "free": 0, "refused": 4,
                       "frames_out": (5, 6, 7)}, (
        "alloc(0) is not an allocation and not a refusal: %r" % (f.log(),))

    # ---- free: by name and by state --------------------------------------

    f.free(6)
    assert f.used() == (5, 7), (
        "freeing frame 6 leaves 5 and 7 handed out, not %r" % (f.used(),))
    assert f.state(6) == s.FREE, (
        "a frame given back is free again, not %r" % (f.state(6),))
    assert f.free_count() == 6, (
        "giving a frame back makes six free, not %d" % (f.free_count(),))
    assert f.bits() == (0, 1, 0, 1, 0, 0, 0, 0, 0), (
        "freeing frame 6 clears its bit and no other, not %r" % (f.bits(),))
    assert ram.read(machine.addr_of(4), 2) == bytes((10, 0)), (
        "the bitmap in RAM holds bit 1 and bit 3 of its first byte (0x0a), not %r"
        % (ram.read(machine.addr_of(4), 2),))
    assert f.log()["free"] == 1, (
        "a frame given back is counted as one frame, not %r" % (f.log()["free"],))

    message = _refuses(s.FramesError, "a double free", lambda: f.free(6))
    assert "6" in message and " is free" in message, (
        "a double free must name the frame and the state it is in, got %r"
        % (message,))
    message = _refuses(s.FramesError, "free of a frame nobody handed out",
                       lambda: f.free(8))
    assert "8" in message and " is free" in message, (
        "a frame that was never handed out must be refused by name and state, "
        "got %r" % (message,))
    message = _refuses(s.FramesError, "free of a frame outside the pool",
                       lambda: f.free(3))
    assert "3" in message and "outside" in message, (
        "free must name a frame the pool does not hold as outside, got %r"
        % (message,))
    message = _refuses(s.FramesError, "free of the bitmap's own frame",
                       lambda: f.free(4))
    assert "4" in message and "bitmap" in message, (
        "free must refuse the bitmap's own frame by name and state, got %r"
        % (message,))
    assert f.log()["refused"] == 8, (
        "four free refusals after four alloc refusals are eight, not %r"
        % (f.log()["refused"],))
    assert f.used() == (5, 7) and f.bits() == (0, 1, 0, 1, 0, 0, 0, 0, 0), (
        "a refused free must change nothing: used %r, bits %r"
        % (f.used(), f.bits()))
    assert f.alloc(1) == (6,), (
        "the frame just given back is the frame handed out again, not %r"
        % (f.alloc(1),))
    assert f.used() == (5, 6, 7) and f.bits() == (0, 1, 1, 1, 0, 0, 0, 0, 0), (
        "the pool is back where it was, not used %r, bits %r"
        % (f.used(), f.bits()))

    # ---- a reserved frame is never handed out and never freed -------------

    ram2 = machine.RAM()
    g = s.Frames(ram2, pool, reserved=(6, 7))
    assert g.state(6) == "reserved" and g.state(7) == "reserved", (
        "a reserved frame's state is reserved, not %r" % (g.state(6),))
    assert g.free_count() == 6, (
        "nine frames, minus the bitmap, minus two reserved, leave six, not %d"
        % (g.free_count(),))
    assert g.alloc(3) == (5, 8, 9), (
        "alloc skips the bitmap and the reserved frames: %r" % (g.alloc(3),))
    assert g.used() == (5, 8, 9), (
        "the frames handed out are 5, 8 and 9, not %r" % (g.used(),))
    assert g.alloc(3) == (10, 11, 12), (
        "the last three handable frames are 10, 11 and 12, not %r"
        % (g.alloc(3),))
    assert g.free_count() == 0, (
        "a pool with everything handed out has nothing free, not %d"
        % (g.free_count(),))
    message = _refuses(s.FramesError, "alloc from a pool with nothing free",
                       lambda: g.alloc(1))
    assert "alloc(1)" in message and "0" in message, (
        "the refusal must name the request and the empty free count, got %r"
        % (message,))
    message = _refuses(s.FramesError, "free of a reserved frame",
                       lambda: g.free(6))
    assert "6" in message and "reserved" in message, (
        "a reserved frame must be refused by name and state, got %r" % (message,))
    assert g.state(6) == "reserved" and g.state(7) == "reserved", (
        "a refused free must not turn a reserved frame into anything else: %r"
        % (g.state(6),))
    assert g.bits() == (0, 1, 0, 0, 1, 1, 1, 1, 1), (
        "the reserved frames' bits are not set by anybody: %r" % (g.bits(),))

    # ---- the bitmap frame is not always the pool's first ------------------

    ram3 = machine.RAM()
    k = s.Frames(ram3, pool, bitmap_frame=8)
    assert k.state(8) == s.BITMAP and k.state(4) == s.FREE, (
        "the bitmap lives in the frame it names: state(8) %r, state(4) %r"
        % (k.state(8), k.state(4)))
    assert k.free_count() == 8, (
        "nine frames minus one bitmap leave eight free, not %d" % (k.free_count(),))
    assert k.alloc(1) == (4,), (
        "the pool's first frame is handable here, not %r" % (k.alloc(1),))
    assert k.bits() == (1, 0, 0, 0, 0, 0, 0, 0, 0), (
        "the bit is set for the frame handed out, not for the bitmap: %r"
        % (k.bits(),))
    assert ram3.read(machine.addr_of(8), 1) == bytes((1,)), (
        "the bitmap is written into frame 8, not into the pool's first frame: %r"
        % (ram3.read(machine.addr_of(8), 1),))
    assert ram3.read(machine.addr_of(4), 1) == bytes((0,)), (
        "the pool's first frame holds no part of the bitmap here: %r"
        % (ram3.read(machine.addr_of(4), 1),))

    # ---- the pool is distinct frames, and boundaries of a bitmap byte -----

    ram4 = machine.RAM()
    m = s.Frames(ram4, (5, 4, 4), bitmap_frame=4)
    assert m.bitmap_bytes() == 1 and m.free_count() == 1, (
        "an unsorted pool with a duplicate is two frames, not %d/%d"
        % (m.bitmap_bytes(), m.free_count()))
    assert m.bits() == (0, 0), (
        "two pool frames are two bits, not %r" % (m.bits(),))
    assert m.alloc(1) == (5,), (
        "the frame of an unsorted pool still comes back once, not %r"
        % (m.alloc(1),))
    assert s.Frames(machine.RAM(), (0,)).bitmap_bytes() == 1, (
        "one frame needs one bitmap byte, not %d"
        % (s.Frames(machine.RAM(), (0,)).bitmap_bytes(),))
    eight = s.Frames(machine.RAM(), (0, 1, 2, 3, 4, 5, 6, 7))
    assert eight.bitmap_bytes() == 1, (
        "eight frames still need one byte, not %d" % (eight.bitmap_bytes(),))
    assert eight.free_count() == 7 and eight.used() == (), (
        "eight frames minus the bitmap leave seven free, not %d"
        % (eight.free_count(),))

    message = _refuses(s.FramesError, "a bitmap frame the pool does not hold",
                       lambda: s.Frames(machine.RAM(), (5, 6, 7), bitmap_frame=9))
    assert "9" in message, (
        "a bitmap frame outside the pool must be named, got %r" % (message,))
    message = _refuses(s.FramesError, "a pool with no frames at all",
                       lambda: s.Frames(machine.RAM(), ()))
    assert "empty" in message, (
        "a pool with no frames has nowhere to keep a bitmap, got %r" % (message,))

    # ---- the bitmap frame is zeroed before it is used ---------------------

    dirty = machine.RAM()
    dirty.write_frame(4, b"\xff" * machine.PAGE_SIZE)
    n = s.Frames(dirty, pool)
    assert n.bits() == (0,) * 9, (
        "a fresh allocator's bitmap is all free whatever the frame held, not %r"
        % (n.bits(),))
    assert dirty.frame(4) == bytes(machine.PAGE_SIZE), (
        "the frame that holds the bitmap must be zeroed, not left as it was found")
    assert n.free_count() == 8, (
        "the frames the frame held as set bits are free, not %d" % (n.free_count(),))

    # ---- the pool stage 1 hands out: 175 frames, 22 bitmap bytes ----------

    handable = s1.usable_frames(machine.boot_map("clean"))
    assert len(handable) == 175 and handable[0] == 0, (
        "the clean map's pool is 175 frames from 0, not %r" % (handable[:3],))
    big_ram = machine.RAM()
    big = s.Frames(big_ram, handable)
    assert big.bitmap_bytes() == 22, (
        "175 pool frames need 22 bitmap bytes, not %d" % (big.bitmap_bytes(),))
    assert len(big.bits()) == 175, (
        "the bitmap is one bit per pool frame: %d bits for 175 frames"
        % (len(big.bits()),))
    assert set(big.bits()) == {0}, (
        "a fresh pool's bitmap is all free, not %r" % (big.bits(),))
    assert big.state(0) == s.BITMAP, (
        "the pool's first frame holds the bitmap, not %r" % (big.state(0),))
    assert big.free_count() == 174, (
        "175 frames minus the bitmap leave 174 free, not %d" % (big.free_count(),))
    assert big.alloc(1) == (1,), (
        "the first frame a caller can get is 1, never the bitmap's 0: %r"
        % (big.alloc(1),))
    assert big.state(128) == "outside", (
        "the kernel's frames are not in the pool at all, not %r"
        % (big.state(128),))
    assert big.state(192) == "outside" and big.state(255) == "outside", (
        "the boot_info and firmware frames are not in the pool either")
    taken = big.alloc(173)
    assert taken[:3] == (2, 3, 4) and taken[-1] == 239, (
        "the 173 frames left run from 2 to 239, not %r" % (taken[:3],))
    assert 0 not in taken and 128 not in taken and 240 not in taken, (
        "no bitmap, kernel or firmware frame is ever handed out: %r"
        % (taken[:3],))
    assert big.used() == tuple(range(1, 128)) + tuple(range(193, 240)), (
        "the frames handed out are the pool's frames but the bitmap's, not %r"
        % (big.used()[:4],))
    assert big.free_count() == 0, (
        "a pool with every frame out has none free, not %d" % (big.free_count(),))
    assert big_ram.read(machine.addr_of(0), 22) == _packed(big.bits()), (
        "the bitmap in RAM must be the bits the allocator reports: %r vs %r"
        % (big_ram.read(machine.addr_of(0), 22)[:4], _packed(big.bits())[:4]))
    message = _refuses(s.FramesError, "alloc from a pool that is full",
                       lambda: big.alloc(1))
    assert "alloc(1)" in message, (
        "the refusal must name the request, got %r" % (message,))
    big.free(239)
    assert big.free_count() == 1 and big.used()[-1] == 238, (
        "giving frame 239 back makes exactly one free and 238 the highest frame "
        "still out, not %d/%r" % (big.free_count(), big.used()[-1]))
    assert 239 not in big.used(), (
        "the frame given back is not handed out any more: %r" % (big.used()[-4:],))
    assert big.alloc(1) == (239,), (
        "the frame given back is the frame handed out, not %r" % (big.alloc(1),))

    # ---- and the fixture the pool came from is where it was ---------------

    assert len(s1.usable_frames(machine.boot_map("clean"))) == 175, (
        "the pool's source changed while the stage ran: %r"
        % (len(s1.usable_frames(machine.boot_map("clean"))),))

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _Pool:
        """A frame pool with the two calls this stage makes and no page tables.

        Only `alloc` and `free` are needed for a translation to be built; the rest is
        bookkeeping the check reads to prove that a frame moved or did not. Frames go
        out lowest first, so a check can lay two of them out by hand.
        """

        def __init__(self, frames):
            self._free = sorted(frames)
            self._used = []

        def alloc(self, count=1):
            if count < 0 or count > len(self._free):
                raise ValueError("this pool has %d frames free, and was asked for %d"
                                 % (len(self._free), count))
            got = tuple(self._free[:count])
            del self._free[:count]
            self._used.extend(got)
            return got

        def free(self, frame):
            if frame not in self._used:
                raise ValueError("frame %d was not handed out by this pool" % (frame,))
            self._used.remove(frame)
            self._free.append(frame)
            self._free.sort()

        def state(self, frame):
            if frame in self._used:
                return "used"
            if frame in self._free:
                return "free"
            return "outside"

        def used(self):
            return tuple(sorted(self._used))

        def free_count(self):
            return len(self._free)

    import machine
    import stage_03 as s

    page = machine.PAGE_SIZE
    entries = machine.ENTRIES

    # ---- the width of the space, and the refusal family --------------------

    assert s.ADDRESS_WIDTH == page * entries * entries, (
        "ADDRESS_WIDTH is %r, and it is every entry of both levels"
        % (s.ADDRESS_WIDTH,))
    assert s.ADDRESS_WIDTH == 1073741824, (
        "the space is 2**30 bytes wide, not %d" % (s.ADDRESS_WIDTH,))
    assert issubclass(s.SpaceError, ValueError), (
        "SpaceError is not a ValueError: %r" % (s.SpaceError,))

    # ---- a fresh space -----------------------------------------------------

    ram = machine.RAM()
    mmu = machine.MMU(ram)
    pool = _Pool((4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15))
    room = pool.free_count()
    space = s.new_space(mmu, pool)

    assert isinstance(space, dict), (
        "a space is a dict, and new_space returned %r" % (space,))
    assert sorted(space) == ["maps", "root", "tables"], (
        "a space has exactly root, tables and maps: %r" % (sorted(space),))
    assert isinstance(space["root"], int) and not isinstance(space["root"], bool), (
        "the root is a frame index, and it is %r" % (space["root"],))
    assert pool.state(space["root"]) == "used", (
        "the root frame did not come from the pool: the pool holds %r"
        % (pool.used(),))
    assert pool.used() == (space["root"],), (
        "a fresh space consumes one frame, and it consumed %r" % (pool.used(),))
    assert pool.free_count() == room - 1, (
        "the pool went from %d free frames to %d" % (room, pool.free_count()))
    assert space["tables"] == (), (
        "a fresh space has no second-level tables: %r" % (space["tables"],))
    assert space["maps"] == {}, (
        "a fresh space maps nothing: %r" % (space["maps"],))
    assert ram.frame(space["root"]) == bytes(page), (
        "the root table was handed over full of the previous tenant's entries")
    assert s.mapped(space) == (), (
        "mapped of a fresh space is empty, and it is %r" % (s.mapped(space),))
    assert s.space_frames(space) == (space["root"],), (
        "a fresh space owns its root and nothing else: %r"
        % (s.space_frames(space),))
    assert s.lookup(space, 0) is None, (
        "nothing is mapped in a fresh space, and lookup answered %r"
        % (s.lookup(space, 0),))
    for vpage in (0, 1, 2, 3, 511, 512):
        assert mmu.entry(space["root"], vpage * page) == 0, (
            "the walk sees a nonzero entry at page %d of a fresh space"
            % (vpage,))

    # a root frame the pool hands back dirty is zeroed before it is used

    reused_pool = _Pool((20, 21, 22))
    ram.write_frame(20, b"\x5a" * page)
    reused = s.new_space(mmu, reused_pool)
    assert reused["root"] == 20, (
        "new_space takes the pool's lowest free frame, and it took %r"
        % (reused["root"],))
    assert ram.frame(20) == bytes(page), (
        "the root was handed out with somebody else's entries still in it")

    # ---- the first mapping: the table, the entry, the mirror ---------------

    one = pool.alloc(1)[0]
    first = s.map_page(mmu, pool, space, 0x1000, one,
                       (machine.WRITE, machine.USER))

    assert sorted(first) == ["entry", "tables"], (
        "map_page answers with the tables it consumed and the entry it installed, "
        "and it answered %r" % (sorted(first),))
    assert first["entry"] == (one << 4) | machine.PRESENT | machine.WRITE | machine.USER, (
        "the installed entry is %#x, not frame %d with PRESENT, WRITE and USER"
        % (first["entry"], one))
    assert first["tables"] == space["tables"] and len(first["tables"]) == 1, (
        "the first mapping of a page allocates one table, and it consumed %r"
        % (first["tables"],))
    assert pool.state(first["tables"][0]) == "used", (
        "the second-level table did not come from the pool: %r"
        % (pool.used(),))
    assert space["maps"] == {1: (one, machine.WRITE | machine.USER)}, (
        "the mirror is keyed by page number and holds the permissions, and it is "
        "%r" % (space["maps"],))
    assert mmu.entry(space["root"], 0x1000) == first["entry"], (
        "the walk answered %#x for a page the mirror says is %#x"
        % (mmu.entry(space["root"], 0x1000), first["entry"]))

    # a second page of the same 512-page block reuses the table

    two = pool.alloc(1)[0]
    second = s.map_page(mmu, pool, space, 0x2000, two, machine.WRITE)
    assert second["tables"] == (), (
        "a second page in the same table allocates nothing, and it consumed %r"
        % (second["tables"],))
    assert second["entry"] == machine.entry_of(two, machine.PRESENT | machine.WRITE), (
        "the second entry is %#x, not frame %d with PRESENT and WRITE"
        % (second["entry"], two))
    assert space["maps"][2] == (two, machine.WRITE), (
        "page 2 is %r in the mirror" % (space["maps"][2],))
    assert len(space["tables"]) == 1, (
        "one table serves both pages, and the space counts %r" % (space["tables"],))

    # a page in the *next* first-level block gets its own table

    three = pool.alloc(1)[0]
    far = entries * page
    third = s.map_page(mmu, pool, space, far, three, machine.EXEC)
    assert len(third["tables"]) == 1, (
        "a page in another block allocates a table, and it consumed %r"
        % (third["tables"],))
    assert third["tables"][0] != first["tables"][0], (
        "the second block reuses the first block's table: %r" % (space["tables"],))
    assert space["maps"][entries] == (three, machine.EXEC), (
        "page %d is %r in the mirror" % (entries, space["maps"].get(entries)))
    assert mmu.entry(space["root"], far) == third["entry"], (
        "the walk answered %#x for the block-%d page" % (mmu.entry(space["root"], far), 1))

    six = pool.alloc(1)[0]
    sibling = s.map_page(mmu, pool, space, far + page, six, machine.WRITE)
    assert sibling["tables"] == (), (
        "a second page in the second block's table allocates nothing, and it "
        "consumed %r" % (sibling["tables"],))
    assert len(space["tables"]) == 2, (
        "two blocks own two tables, and the space counts %r" % (space["tables"],))

    four = pool.alloc(1)[0]
    s.map_page(mmu, pool, space, 0x4000, four, machine.WRITE)

    # a second-level table the pool hands back dirty is zeroed before it is used

    reused_table_pool = _Pool((24, 25, 26))
    ram.write_frame(25, b"\xff" * page)
    reused_space = s.new_space(mmu, reused_table_pool)
    assert reused_space["root"] == 24, (
        "the second fixture's root is its pool's lowest frame, and it is %r"
        % (reused_space["root"],))
    dirty = s.map_page(mmu, reused_table_pool, reused_space, 0x1000, 200,
                       machine.WRITE)
    assert dirty["tables"] == (25,), (
        "map_page takes the table from the pool, and it consumed %r"
        % (dirty["tables"],))
    leftovers = [slot for slot in range(0, page, 8)
                 if ram.frame(25)[slot:slot + 8] != bytes(8)]
    assert len(leftovers) == 1, (
        "the new second-level table was not zeroed: %d entries nobody installed "
        "are still in it" % (len(leftovers),))
    assert mmu.entry(reused_space["root"], 0x1000) == dirty["entry"], (
        "the walk disagrees with the entry map_page reported")

    # ---- belief and hardware, entry by entry ------------------------------

    for vpage, (frame, flags) in space["maps"].items():
        assert mmu.entry(space["root"], vpage * page) == machine.entry_of(
            frame, flags | machine.PRESENT), (
            "the kernel believes page %d is frame %d with flags %#x, and the "
            "tables say otherwise" % (vpage, frame, flags))
    for vpage in (0, 1, 2, 3, 4, 5, 511, 512, 513, entries * 2):
        held = mmu.entry(space["root"], vpage * page) != 0
        assert held == (vpage in space["maps"]), (
            "the tables hold a mapping for page %d that the mirror does not (or "
            "the reverse)" % (vpage,))

    # ---- the mirror read back ---------------------------------------------

    assert s.mapped(space) == ((1, one, machine.WRITE | machine.USER),
                               (2, two, machine.WRITE),
                               (4, four, machine.WRITE),
                               (entries, three, machine.EXEC),
                               (entries + 1, six, machine.WRITE)), (
        "mapped is (vpage, frame, flags) ascending, and it is %r"
        % (s.mapped(space),))
    assert s.lookup(space, 0x1000) == (one, machine.WRITE | machine.USER), (
        "lookup of the first mapped page is %r" % (s.lookup(space, 0x1000),))
    assert s.lookup(space, 0x1FFF) == (one, machine.WRITE | machine.USER), (
        "a byte inside a page is that page: lookup answered %r"
        % (s.lookup(space, 0x1FFF),))
    assert s.lookup(space, far) == (three, machine.EXEC), (
        "lookup of the block-%d page is %r" % (1, s.lookup(space, far)))
    assert s.lookup(space, 0x3000) is None, (
        "page 3 was never mapped, and lookup answered %r"
        % (s.lookup(space, 0x3000),))
    assert s.lookup(space, s.ADDRESS_WIDTH) is None, (
        "an address past the size of the space is not mapped, and lookup "
        "answered %r" % (s.lookup(space, s.ADDRESS_WIDTH),))
    assert s.lookup(space, s.ADDRESS_WIDTH + page) is None, (
        "an address past the size of the space is not mapped, and lookup "
        "answered %r" % (s.lookup(space, s.ADDRESS_WIDTH + page),))

    frames = sorted((space["root"], one, two, three, four, six) + space["tables"])
    assert s.space_frames(space) == tuple(frames), (
        "space_frames is the root, the tables and the mapped frames ascending, "
        "and it is %r" % (s.space_frames(space),))
    assert space["root"] in s.space_frames(space), (
        "space_frames forgot the root: %r" % (s.space_frames(space),))
    for table in space["tables"]:
        assert table in s.space_frames(space), (
            "space_frames forgot the table %d: %r" % (table, s.space_frames(space)))

    # ---- unmap: the mirror, the table, the TLB ----------------------------

    assert mmu.translate(space["root"], 0x1000, "read", True) == (one, 0), (
        "the first mapped page does not translate where the mirror says it does")
    assert mmu.log()["cached"] >= 1, (
        "the machine remembered nothing after a translation: %r" % (mmu.log(),))
    removed = s.unmap_page(mmu, space, 0x1000)
    assert sorted(removed) == ["flags", "frame"], (
        "unmap_page returns the frame and the flags of the page it removed, and it "
        "returned %r" % (sorted(removed),))
    assert removed == {"frame": one, "flags": machine.WRITE | machine.USER}, (
        "unmap_page returned %r, not the frame and permissions it removed"
        % (removed,))
    assert 1 not in space["maps"], (
        "the mirror still holds page 1: %r" % (space["maps"],))
    assert mmu.entry(space["root"], 0x1000) == 0, (
        "the table entry for an unmapped page is %#x, not 0"
        % (mmu.entry(space["root"], 0x1000),))
    assert pool.state(one) == "used", (
        "unmap_page freed a frame the caller owns: the pool holds %r"
        % (pool.used(),))
    assert one not in s.space_frames(space), (
        "space_frames still claims an unmapped frame: %r" % (s.space_frames(space),))
    message = _refuses(machine.PageFault,
                       "translate of a page that was just unmapped",
                       lambda: mmu.translate(space["root"], 0x1000))
    assert "not_present" in message, (
        "the walk's word for an unmapped page is not_present, and it said %r"
        % (message,))
    message = _refuses(s.SpaceError, "unmap of a page that is not mapped",
                       lambda: s.unmap_page(mmu, space, 0x1000))
    assert "0x1000" in message, (
        "the refusal for an unmapped page must name the address, and it said %r"
        % (message,))

    # an unmap that empties a table keeps the table

    mmu.translate(space["root"], 0x2000, "read")
    s.unmap_page(mmu, space, 0x2000)
    s.unmap_page(mmu, space, 0x4000)
    assert space["tables"] == first["tables"] + third["tables"], (
        "an unmap must not drop the table it emptied, and the space now holds %r"
        % (space["tables"],))
    assert first["tables"][0] in s.space_frames(space), (
        "space_frames dropped a table that is still in the tables: %r"
        % (s.space_frames(space),))
    for vpage in (1, 2, 4):
        assert mmu.entry(space["root"], vpage * page) == 0, (
            "an unmapped page still has a table entry: page %d" % (vpage,))
        assert vpage not in space["maps"], (
            "the mirror still holds page %d: %r" % (vpage, space["maps"]))
    five = pool.alloc(1)[0]
    back = s.map_page(mmu, pool, space, 0x5000, five, machine.USER)
    assert back["tables"] == (), (
        "mapping into an emptied table allocates nothing, and it consumed %r"
        % (back["tables"],))
    assert space["maps"][5] == (five, machine.USER), (
        "page 5 is %r in the mirror" % (space["maps"].get(5),))
    assert mmu.entry(space["root"], 0x5000) == back["entry"], (
        "the walk does not see the page remapped into the emptied table")

    # ---- protect: the entry, the mirror, and the TLB -----------------------

    assert mmu.translate(space["root"], 0x5000, "read", True) == (five, 0), (
        "a page mapped USER does not translate for a user")
    changed = s.protect(mmu, space, 0x5000, machine.WRITE)
    assert sorted(changed) == ["flags", "frame"], (
        "protect returns the frame and its new flags, and it returned %r"
        % (sorted(changed),))
    assert changed == {"frame": five, "flags": machine.WRITE}, (
        "protect returned %r, not the frame and the permissions it installed"
        % (changed,))
    assert space["maps"][5] == (five, machine.WRITE), (
        "the mirror still says page 5 is %r" % (space["maps"].get(5),))
    assert mmu.entry(space["root"], 0x5000) == machine.entry_of(
        five, machine.PRESENT | machine.WRITE), (
        "protect did not rewrite the table entry: the walk sees %#x"
        % (mmu.entry(space["root"], 0x5000),))
    message = _refuses(machine.PageFault,
                       "a user read of a page just protected to supervisor",
                       lambda: mmu.translate(space["root"], 0x5000, "read", True))
    assert "supervisor" in message, (
        "the walk's word for a user read of a supervisor page is supervisor, and "
        "it said %r" % (message,))
    assert mmu.translate(space["root"], 0x5000, "write") == (five, 0), (
        "the kernel cannot write the page it just made writable")
    changed = s.protect(mmu, space, 0x5000, ())
    assert mmu.entry(space["root"], 0x5000) == machine.entry_of(
        five, machine.PRESENT), (
        "a page protected to no permissions is a present read-only page, and the "
        "walk sees %#x" % (mmu.entry(space["root"], 0x5000),))
    message = _refuses(machine.PageFault,
                       "a write to a page just protected read-only",
                       lambda: mmu.translate(space["root"], 0x5000, "write"))
    assert "read_only" in message, (
        "the walk's word for a write to a read-only page is read_only, and it "
        "said %r" % (message,))
    s.protect(mmu, space, 0x5000, machine.USER)
    assert mmu.translate(space["root"], 0x5000, "read", True) == (five, 0), (
        "a page protected back to USER does not translate for a user")

    # ---- the refusals ------------------------------------------------------

    before = dict(space["maps"])
    tables_before = space["tables"]
    frames_before = pool.used()
    refusals = pool.free_count()

    message = _refuses(s.SpaceError, "map_page of an address already mapped",
                       lambda: s.map_page(mmu, pool, space, 0x5000, 30, machine.WRITE))
    assert "0x5000" in message, (
        "the refusal for a double map must name the address, and it said %r"
        % (message,))
    message = _refuses(s.SpaceError, "map_page at the address width",
                       lambda: s.map_page(mmu, pool, space, s.ADDRESS_WIDTH, 30,
                                          machine.WRITE))
    assert "0x40000000" in message, (
        "the refusal for an address past the space must name it, and it said %r"
        % (message,))
    message = _refuses(s.SpaceError, "map_page of a frame outside RAM",
                       lambda: s.map_page(mmu, pool, space, 0x6000,
                                          machine.FRAME_COUNT, machine.WRITE))
    assert "256" in message, (
        "the refusal for a frame outside RAM must name it, and it said %r"
        % (message,))
    _refuses(s.SpaceError, "map_page of a negative frame",
             lambda: s.map_page(mmu, pool, space, 0x6000, -1, machine.WRITE))
    _refuses(s.SpaceError, "map_page of a bool frame",
             lambda: s.map_page(mmu, pool, space, 0x6000, True, machine.WRITE))
    _refuses(s.SpaceError, "map_page of a negative address",
             lambda: s.map_page(mmu, pool, space, -page, 30, machine.WRITE))
    _refuses(s.SpaceError, "map_page of a float address",
             lambda: s.map_page(mmu, pool, space, float(page), 30, machine.WRITE))
    message = _refuses(s.SpaceError, "map_page with the PRESENT bit in its flags",
                       lambda: s.map_page(mmu, pool, space, 0x6000, 30,
                                          machine.PRESENT | machine.WRITE))
    assert "PRESENT" in message, (
        "the refusal for a caller-set PRESENT bit must say so, and it said %r"
        % (message,))
    message = _refuses(s.SpaceError, "map_page with a bit that is not a permission",
                       lambda: s.map_page(mmu, pool, space, 0x6000, 30, 16))
    assert "0x10" in message, (
        "the refusal for an unknown flag bit must name it, and it said %r"
        % (message,))
    message = _refuses(s.SpaceError, "map_page of a page both writable and executable",
                       lambda: s.map_page(mmu, pool, space, 0x6000, 30,
                                          machine.WRITE | machine.EXEC))
    assert "WRITE" in message and "EXEC" in message, (
        "the refusal for W^X must name both bits, and it said %r" % (message,))
    _refuses(s.SpaceError, "map_page of a space whose tables are not a tuple",
             lambda: s.map_page(mmu, pool, {"root": space["root"], "tables": [],
                                            "maps": {}}, 0x6000, 30,
                                machine.WRITE))
    _refuses(s.SpaceError, "map_page of a space whose maps are not a dict",
             lambda: s.map_page(mmu, pool, {"root": space["root"], "tables": (),
                                            "maps": []}, 0x6000, 30,
                                machine.WRITE))
    message = _refuses(s.SpaceError, "map_page of a space with no root",
                       lambda: s.map_page(mmu, pool, {"tables": (), "maps": {}},
                                          0x6000, 30, machine.WRITE))
    assert "root" in message, (
        "the refusal for a space with no root must name it, and it said %r"
        % (message,))
    _refuses(s.SpaceError, "map_page of a space with an extra key",
             lambda: s.map_page(mmu, pool, {"root": space["root"], "tables": (),
                                            "maps": {}, "next": 0}, 0x6000, 30,
                                machine.WRITE))
    _refuses(s.SpaceError, "map_page of a space whose root is not a frame",
             lambda: s.map_page(mmu, pool, {"root": machine.FRAME_COUNT,
                                            "tables": (), "maps": {}}, 0x6000, 30,
                                machine.WRITE))

    _refuses(s.SpaceError, "unmap of a page that is not mapped",
             lambda: s.unmap_page(mmu, space, 0x6000))
    _refuses(s.SpaceError, "unmap of a negative address",
             lambda: s.unmap_page(mmu, space, -page))
    _refuses(s.SpaceError, "protect of a page that is not mapped",
             lambda: s.protect(mmu, space, 0x6000, machine.WRITE))
    _refuses(s.SpaceError, "protect with the PRESENT bit in its flags",
             lambda: s.protect(mmu, space, 0x5000, machine.PRESENT))
    _refuses(s.SpaceError, "protect of a page to both writable and executable",
             lambda: s.protect(mmu, space, 0x5000,
                               machine.WRITE | machine.EXEC))
    _refuses(s.SpaceError, "lookup of a bool address",
             lambda: s.lookup(space, True))
    _refuses(s.SpaceError, "lookup of an address that is not an int",
             lambda: s.lookup(space, "0x5000"))
    _refuses(s.SpaceError, "lookup of a negative address",
             lambda: s.lookup(space, -page))

    assert space["maps"] == before, (
        "a refused mapping changed the mirror: %r" % (space["maps"],))
    assert space["tables"] == tables_before, (
        "a refused mapping changed the tables: %r" % (space["tables"],))
    assert pool.used() == frames_before and pool.free_count() == refusals, (
        "a refused mapping consumed a frame: %r" % (pool.used(),))
    assert mmu.entry(space["root"], 0x5000) == machine.entry_of(
        five, machine.PRESENT | machine.USER), (
        "a refused protect changed the page: the walk sees %#x"
        % (mmu.entry(space["root"], 0x5000),))

    # a space whose mirror claims a page whose table is not there

    torn_pool = _Pool((40, 41, 42))
    torn = s.new_space(mmu, torn_pool)
    torn_page = torn_pool.alloc(1)[0]
    s.map_page(mmu, torn_pool, torn, 0x1000, torn_page, machine.WRITE)
    ram.write(machine.addr_of(torn["root"]), bytes(8))
    _refuses(s.SpaceError, "unmap of a page whose table is not present",
             lambda: s.unmap_page(mmu, torn, 0x1000))
    _refuses(s.SpaceError, "protect of a page whose table is not present",
             lambda: s.protect(mmu, torn, 0x1000, machine.USER))

    # ---- free_space: everything, and the translations with it --------------

    mmu.translate(space["root"], 0x5000, "read", True)
    assert mmu.cached() >= 1, (
        "the machine remembered nothing: %r" % (mmu.log(),))
    for frame in (one, two, four):
        pool.free(frame)
    assert pool.used() == s.space_frames(space), (
        "the pool holds %r and the space owns %r"
        % (pool.used(), s.space_frames(space)))
    held = s.space_frames(space)
    loose = pool.free_count()
    given = s.free_space(mmu, pool, space)
    assert given == held, (
        "free_space returns the frames it released, and it returned %r for the "
        "frames %r" % (given, held))
    assert pool.used() == (), (
        "free_space left frames in the pool's hands: %r" % (pool.used(),))
    assert pool.free_count() == loose + len(held), (
        "free_space released %d frames and the pool gained %d"
        % (len(held), pool.free_count() - loose))
    for frame in held:
        assert pool.state(frame) == "free", (
            "free_space did not release frame %d: it is %s"
            % (frame, pool.state(frame)))
    assert mmu.cached() == 0, (
        "free_space left %d translations in the machine" % (mmu.cached(),))

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _Pool:
        """A frame pool the check owns: the frames given out, and the ones left.

        It has the three calls this stage's demand paging makes — `alloc`, `free`,
        `free_count` — and it refuses an empty pool the way stage 2's allocator does
        (`ValueError`), so the fault handler can be driven without a sibling stage.
        """

        def __init__(self, frames):
            self._free = list(frames)
            self._out = []

        def alloc(self, count=1):
            if count < 1 or count > len(self._free):
                raise ValueError("a pool of %d frames was asked for %d"
                                 % (len(self._free), count))
            taken = tuple(self._free[:count])
            del self._free[:count]
            self._out.extend(taken)
            return taken

        def free(self, frame):
            if frame not in self._out:
                raise ValueError("frame %d was never handed out" % (frame,))
            self._out.remove(frame)
            self._free.append(frame)
            self._free.sort()

        def free_count(self):
            return len(self._free)

    def _space(root, tables=(), maps=None):
        """One address space, in the mirror §2.4 froze."""
        return {"root": root, "tables": tuple(tables), "maps": dict(maps or {})}

    import machine
    import stage_04 as s

    page = machine.PAGE_SIZE
    keys = ["action", "vector", "name", "word", "frame", "reason", "cause"]
    allowed = machine.PRESENT | machine.WRITE | machine.USER

    # ---- the three vocabularies, and the one refusal family ---------------

    assert s.FAULT_WORDS == ("not_present", "read_only", "protected"), (
        "the handler's three words are %r" % (s.FAULT_WORDS,))
    assert s.ACTIONS == ("resolved", "refused", "panic"), (
        "the three actions are %r, not ('resolved', 'refused', 'panic')"
        % (s.ACTIONS,))
    assert s.CAUSES == ("in_handler", "double_fault", "unhandled_exception",
                        "unhandled_irq", "kernel_fault", "out_of_memory"), (
        "the six causes are %r" % (s.CAUSES,))
    assert issubclass(s.TrapError, ValueError), (
        "TrapError is not a ValueError: %r" % (s.TrapError,))

    # ---- decode: the three bits, and bit 2 is not one of them -------------

    assert s.decode(0) == "not_present", (
        "a read of an absent page is `not_present`, not %r" % (s.decode(0),))
    assert s.decode(machine.FAULT_WRITE) == "not_present", (
        "a write to an absent page is still `not_present`, not %r"
        % (s.decode(machine.FAULT_WRITE),))
    assert s.decode(machine.FAULT_USER) == "not_present", (
        "the user bit is context, not a reason: a user read of an absent page is "
        "`not_present`, not %r" % (s.decode(machine.FAULT_USER),))
    assert s.decode(machine.FAULT_WRITE | machine.FAULT_USER) == "not_present", (
        "a user write to an absent page is `not_present`, not %r"
        % (s.decode(machine.FAULT_WRITE | machine.FAULT_USER),))
    assert s.decode(machine.FAULT_PROTECTION) == "protected", (
        "a denied read of a present page is `protected`, not %r"
        % (s.decode(machine.FAULT_PROTECTION),))
    assert (s.decode(machine.FAULT_PROTECTION | machine.FAULT_USER)
            == "protected"), (
        "the user bit must not turn `protected` into anything else: %r"
        % (s.decode(machine.FAULT_PROTECTION | machine.FAULT_USER),))
    assert (s.decode(machine.FAULT_PROTECTION | machine.FAULT_WRITE)
            == "read_only"), (
        "a write the page forbids is `read_only`, not %r"
        % (s.decode(machine.FAULT_PROTECTION | machine.FAULT_WRITE),))
    assert (s.decode(machine.FAULT_PROTECTION | machine.FAULT_WRITE
                     | machine.FAULT_USER) == "read_only"), (
        "a user write the page forbids is `read_only`, not %r"
        % (s.decode(machine.FAULT_PROTECTION | machine.FAULT_WRITE
                    | machine.FAULT_USER),))
    message = _refuses(s.TrapError, "decode of a bool",
                       lambda: s.decode(True))
    assert "True" in message, (
        "a bool is not an error code and must be named in the refusal, got %r"
        % (message,))

    reasons = (("not_present", "read", False), ("supervisor", "read", True),
               ("read_only", "write", False), ("no_execute", "exec", False),
               ("not_user", "read", False))
    words = tuple(s.decode(machine.PageFault(reason, page, access, user).error)
                  for reason, access, user in reasons)
    assert words == ("not_present", "protected", "read_only", "protected",
                     "not_present"), (
        "the machine's five reasons must collapse onto the handler's three, got "
        "%r" % (words,))
    assert machine.PageFault("supervisor", page, "read", user=True).reason == (
        "supervisor"), (
        "the walk's own word for a denied user read is `supervisor`, whatever the "
        "handler is allowed to read out of the bits")

    # ---- classify ---------------------------------------------------------

    got = s.classify(machine.Trap(13, 0, 0x1000, 2))
    assert list(got) == ["vector", "name", "kind", "cpu", "addr"], (
        "classify's keys are %r, not ['vector', 'name', 'kind', 'cpu', 'addr']"
        % (list(got),))
    assert got == {"vector": 13, "name": "general_protection",
                   "kind": "exception", "cpu": 2, "addr": 0x1000}, (
        "a general protection fault is %r" % (got,))
    assert s.classify(machine.Trap(0, 0, 0, 0))["kind"] == "exception", (
        "vector 0 is one of the five exceptions: %r"
        % (s.classify(machine.Trap(0, 0, 0, 0)),))
    assert s.classify(machine.Trap(8, 0, 0, 0))["name"] == "double_fault", (
        "vector 8 is the double fault: %r"
        % (s.classify(machine.Trap(8, 0, 0, 0)),))
    got = s.classify(machine.Trap(32, 0, 0, 5))
    assert got["kind"] == "irq" and got["name"] == "timer_tick", (
        "the timer is the one irq this machine has: %r" % (got,))
    got = s.classify(machine.Trap(7, 0, 8, 1))
    assert got == {"vector": 7, "name": "unknown", "kind": "unknown",
                   "cpu": 1, "addr": 8}, (
        "a vector this machine does not have is `unknown` in both name and "
        "kind: %r" % (got,))
    fault = machine.PageFault("not_present", 3 * page, "read", user=True, cpu=4)
    got = s.classify(fault)
    assert got["name"] == "page_fault" and got["kind"] == "exception", (
        "a page fault is exception 14 by name: %r" % (got,))
    assert got["addr"] == 3 * page and got["cpu"] == 4, (
        "classify must carry the fault's own address and cpu: %r" % (got,))
    message = _refuses(s.TrapError, "classify of a bare vector",
                       lambda: s.classify(13))
    assert "13" in message, (
        "classify of something that is not a trap must name it, got %r"
        % (message,))

    # ---- TrapTable: what may be installed, and what may not ---------------

    handlers = s.TrapTable()
    assert handlers.vectors() == (), (
        "a fresh table serves nothing: %r" % (handlers.vectors(),))
    assert handlers.handler(14) is None, (
        "a vector nobody serves answers None, not %r" % (handlers.handler(14),))
    assert handlers.handler(7) is None, (
        "a vector this machine does not have answers None too, not %r"
        % (handlers.handler(7),))
    answer = handlers.install(14, "page_fault")
    assert answer is None, (
        "install answers None, not %r" % (answer,))
    assert handlers.handler(14) == "page_fault", (
        "the installed handler is %r" % (handlers.handler(14),))
    assert handlers.vectors() == (14,), (
        "the vectors served are %r, not (14,)" % (handlers.vectors(),))
    other = s.TrapTable()
    assert other.vectors() == () and other.handler(14) is None, (
        "two tables must not share their handlers: %r" % (other.vectors(),))
    message = _refuses(s.TrapError, "install of a vector this machine does not "
                                    "have",
                       lambda: handlers.install(7, "general_protection"))
    assert "7" in message, (
        "a vector this machine does not have must be named, got %r" % (message,))
    message = _refuses(s.TrapError, "install of the double fault",
                       lambda: handlers.install(8, "double_fault"))
    assert "8" in message, (
        "the double fault is refused by its own number, got %r" % (message,))
    _refuses(s.TrapError, "install of an empty handler name",
             lambda: handlers.install(13, ""))
    _refuses(s.TrapError, "install of a handler name that is not a str",
             lambda: handlers.install(13, 13))
    message = _refuses(s.TrapError, "install of a vector already served",
                       lambda: handlers.install(14, "again"))
    assert "page_fault" in message, (
        "a double install must name the handler already there, got %r"
        % (message,))
    assert handlers.vectors() == (14,), (
        "a refused install must change nothing: %r" % (handlers.vectors(),))
    assert handlers.handler(14) == "page_fault", (
        "a refused install must not replace the handler: %r"
        % (handlers.handler(14),))
    served = s.TrapTable({13: "general_protection", 0: "divide_error",
                          32: "timer_tick", 6: "invalid_opcode"})
    assert served.vectors() == (0, 6, 13, 32), (
        "the vectors come back ascending as a tuple: %r" % (served.vectors(),))
    assert served.handler(32) == "timer_tick", (
        "the table's own entry for the timer is %r" % (served.handler(32),))
    _refuses(s.TrapError, "a table built from entries with a double fault",
             lambda: s.TrapTable({13: "general_protection", 8: "double_fault"}))
    _refuses(s.TrapError, "a table built from entries that are not a dict",
             lambda: s.TrapTable("general_protection"))

    # ---- handle: a user fault whose page is absent, and really resolved ---

    ram = machine.RAM()
    root, second = 0, 1
    ram.write_frame(root, bytes(page))
    ram.write_frame(second, bytes(page))
    ram.write(machine.addr_of(root),
              machine.entry_of(second, allowed).to_bytes(8, "little"))
    pool = _Pool((2, 3, 4, 5, 6, 7))
    space = _space(root, (second,))
    mmu = machine.MMU(ram)
    handlers = s.TrapTable({14: "page_fault"})

    got = s.handle(machine.Trap(14, machine.FAULT_WRITE | machine.FAULT_USER,
                                3 * page, 0), handlers,
                   mmu=mmu, pool=pool, space=space)
    assert list(got) == keys, (
        "handle's keys are %r, not %r" % (list(got), keys))
    assert got["action"] == "resolved", (
        "a user write to an absent page, with the pool and the machine in hand, "
        "is resolved, not %r" % (got,))
    assert got["vector"] == 14 and got["name"] == "page_fault", (
        "the decision must carry the vector and its name: %r" % (got,))
    assert got["word"] == "not_present", (
        "the resolution must report the word it acted on: %r" % (got,))
    assert got["frame"] == 2, (
        "the frame is the pool's first free frame, not %r" % (got["frame"],))
    assert got["reason"] is None and got["cause"] is None, (
        "a resolved fault has no reason and no cause: %r" % (got,))
    assert mmu.entry(root, 3 * page) == machine.entry_of(2, allowed), (
        "the entry the machine walks is %#x, not %#x"
        % (mmu.entry(root, 3 * page), machine.entry_of(2, allowed)))
    assert ram.read(machine.addr_of(second) + 3 * 8, 8) == (
        machine.entry_of(2, allowed).to_bytes(8, "little")), (
        "the entry must be written into the table in RAM, where the world can "
        "read it back")
    assert space["maps"] == {3: (2, allowed)}, (
        "the space's mirror is %r, not {3: (2, %#x)}" % (space["maps"], allowed))
    assert space["tables"] == (second,), (
        "the table the space already had must stay counted: %r"
        % (space["tables"],))
    assert pool.free_count() == 5, (
        "resolving one fault takes one frame: %r still free" % (pool.free_count(),))
    assert pool.alloc(1) == (3,), (
        "the frame that was taken must be out of the pool")
    pool.free(3)
    assert mmu.translate(root, 3 * page, "write", user=True) == (2, 0), (
        "the resolved page must be one the process can really write")
    mmu.store(root, 3 * page, b"hi", user=True)
    assert ram.frame(2)[:2] == b"hi", (
        "the bytes a user wrote through the resolved page are %r"
        % (ram.frame(2)[:2],))
    got = s.handle(machine.Trap(14, machine.FAULT_USER, 4 * page, 1), handlers,
                   mmu=mmu, pool=pool, space=space)
    assert got["action"] == "resolved" and got["frame"] == 3, (
        "a user read of an absent page is a missing page too: %r" % (got,))
    assert space["maps"] == {3: (2, allowed), 4: (3, allowed)}, (
        "the second resolution must be in the mirror too: %r" % (space["maps"],))
    assert handlers.handler(14) == "page_fault", (
        "the page fault is the kernel's, not the table's: the handler for 14 must "
        "not have been consulted")
    got = s.handle(machine.Trap(14, machine.FAULT_WRITE | machine.FAULT_USER,
                                3 * page, 0), handlers, mmu=mmu, pool=pool,
                   space=space, in_handler=True)
    assert got["action"] == "panic" and got["cause"] == "in_handler", (
        "a fault inside a handler is not resolved a second time: %r" % (got,))
    assert pool.free_count() == 4, (
        "a panicking fault must not take a frame: %r still free"
        % (pool.free_count(),))

    # ---- handle: what a fault must not do ---------------------------------

    got = s.handle(machine.Trap(14, machine.FAULT_WRITE | machine.FAULT_USER,
                                6 * page, 0), handlers)
    assert got["action"] == "refused", (
        "with no machine and no pool to fix it with, a demand fault is refused, "
        "not %r" % (got,))
    assert got["reason"] == "not_present" and got["frame"] is None, (
        "the refusal carries the word the fault arrived with: %r" % (got,))
    got = s.handle(machine.Trap(14, machine.FAULT_WRITE | machine.FAULT_USER,
                                6 * page, 0), handlers, mmu=mmu)
    assert got["action"] == "refused" and got["reason"] == "not_present", (
        "the machine without a pool is not enough to resolve: %r" % (got,))
    got = s.handle(machine.Trap(14, machine.FAULT_PROTECTION | machine.FAULT_WRITE
                                | machine.FAULT_USER, 5 * page, 0), handlers,
                   mmu=mmu, pool=pool, space=space)
    assert got["action"] == "refused" and got["reason"] == "read_only", (
        "a write the page forbids is refused as `read_only`, not %r" % (got,))
    assert got["cause"] is None and got["frame"] is None, (
        "a refusal has a reason and nothing else: %r" % (got,))
    assert mmu.entry(root, 5 * page) == 0 and pool.free_count() == 4, (
        "a refused fault must not map anything or take a frame")
    got = s.handle(machine.Trap(14, machine.FAULT_PROTECTION | machine.FAULT_USER,
                                5 * page, 0), handlers,
                   mmu=mmu, pool=pool, space=space)
    assert got["action"] == "refused" and got["reason"] == "protected", (
        "a denied read is refused as `protected`, not %r" % (got,))
    got = s.handle(machine.Trap(14, machine.FAULT_WRITE, 7 * page, 0), handlers,
                   mmu=mmu, pool=pool, space=space)
    assert got["action"] == "panic" and got["cause"] == "kernel_fault", (
        "a page fault with the user bit clear is the kernel's own bug: %r"
        % (got,))
    assert got["word"] == "not_present" and got["frame"] is None, (
        "the kernel-fault panic still reports the word: %r" % (got,))
    assert mmu.entry(root, 7 * page) == 0 and pool.free_count() == 4, (
        "a kernel fault must not demand-page for the kernel")

    dry = _Pool(())
    dry_space = _space(root, (second,))
    got = s.handle(machine.Trap(14, machine.FAULT_WRITE | machine.FAULT_USER,
                                6 * page, 0), handlers,
                   mmu=mmu, pool=dry, space=dry_space)
    assert got["action"] == "panic" and got["cause"] == "out_of_memory", (
        "a pool with no frame left is a panic, not an exception out of handle: %r"
        % (got,))
    assert got["reason"] is None and got["frame"] is None, (
        "an out-of-memory panic has a cause and nothing else: %r" % (got,))
    assert dry.free_count() == 0 and dry_space["maps"] == {}, (
        "a fault that could not be resolved must leave no mapping and no frame")
    assert dry_space["tables"] == (second,) and mmu.entry(root, 6 * page) == 0, (
        "a panic must not have installed an entry in the tables")

    # ---- handle: a space whose table is not there yet ---------------------

    fresh_ram = machine.RAM()
    fresh_root = 30
    fresh_ram.write_frame(fresh_root, bytes(page))
    for preowned in (31, 32):
        fresh_ram.write_frame(preowned, b"\xff" * page)
    fresh_pool = _Pool((31, 32))
    fresh_space = _space(fresh_root, ())
    fresh_mmu = machine.MMU(fresh_ram)
    far_page = 600
    far = far_page * page
    high = far_page // machine.ENTRIES
    low = far_page % machine.ENTRIES
    got = s.handle(machine.Trap(14, machine.FAULT_USER, far, 1), handlers,
                   mmu=fresh_mmu, pool=fresh_pool, space=fresh_space)
    assert got["action"] == "resolved" and got["frame"] == 31, (
        "a fault in a space with no table yet is still a fault to resolve: %r"
        % (got,))
    assert fresh_space["tables"] == (32,), (
        "the table the mapping built must be counted in the space: %r"
        % (fresh_space["tables"],))
    assert fresh_space["maps"] == {far_page: (31, allowed)}, (
        "the mirror of the new space is %r" % (fresh_space["maps"],))
    assert fresh_ram.read(machine.addr_of(fresh_root) + high * 8, 8) == (
        machine.entry_of(32, allowed).to_bytes(8, "little")), (
        "the first-level entry for the new table must be in RAM where the walk "
        "looks for it")
    assert fresh_ram.read(machine.addr_of(fresh_root) + low * 8, 8) == bytes(8), (
        "the new table must be entered under its own first-level index, and no "
        "other")
    assert fresh_ram.frame(32)[low * 8:low * 8 + 8] == (
        machine.entry_of(31, allowed).to_bytes(8, "little")), (
        "the page's entry must be the one the page's own index names")
    assert fresh_ram.frame(32)[:low * 8] == bytes(low * 8), (
        "a table the kernel builds must be zeroed: its first bytes are %r"
        % (fresh_ram.frame(32)[:low * 8],))
    assert fresh_ram.frame(32)[low * 8 + 8:] == bytes(page - low * 8 - 8), (
        "a table the kernel builds must be zeroed: the rest of it is %r"
        % (fresh_ram.frame(32)[low * 8 + 8:low * 8 + 40],))
    assert fresh_mmu.entry(fresh_root, far) == machine.entry_of(31, allowed), (
        "the machine's own walk must find the new page")
    assert fresh_pool.free_count() == 0, (
        "the page and its table are two frames: %r free" % (fresh_pool.free_count(),))

    roll_ram = machine.RAM()
    roll_root = 20
    roll_ram.write_frame(roll_root, bytes(page))
    roll_ram.write_frame(21, b"\xff" * page)
    roll_pool = _Pool((21,))
    roll_space = _space(roll_root, ())
    got = s.handle(machine.Trap(14, machine.FAULT_USER, 0, 0), handlers,
                   mmu=machine.MMU(roll_ram), pool=roll_pool, space=roll_space)
    assert got["action"] == "panic" and got["cause"] == "out_of_memory", (
        "a pool that cannot finish the mapping is a panic: %r" % (got,))
    assert roll_pool.free_count() == 1 and roll_pool.alloc(1) == (21,), (
        "the frame the failed mapping took must be back in the pool")
    roll_pool.free(21)
    assert roll_space["maps"] == {} and roll_space["tables"] == (), (
        "a failed mapping must leave the space as it found it: %r" % (roll_space,))
    assert roll_ram.frame(roll_root) == bytes(page), (
        "a failed mapping must not install a first-level entry")
    assert roll_ram.frame(21) == b"\xff" * page, (
        "a failed mapping must not touch the frame it took")

    # ---- handle: the timer, the exceptions, and the nowhere-to-go ---------

    got = s.handle(machine.Trap(32, 0, 0, 0), handlers)
    assert got["action"] == "refused" and got["reason"] == "unhandled_irq", (
        "a timer nobody serves is refused, not a panic: %r" % (got,))
    assert got["word"] is None and got["cause"] is None, (
        "the timer has no fault word: %r" % (got,))
    got = s.handle(machine.Trap(32, 0, 0, 0), s.TrapTable({32: "timer_tick"}))
    assert got["action"] == "resolved" and got["frame"] is None, (
        "a timer with a handler is resolved through it: %r" % (got,))
    assert got["name"] == "timer_tick" and got["reason"] is None, (
        "the resolved irq carries its own name: %r" % (got,))
    sr = s.TrapTable({13: "general_protection"})
    got = s.handle(machine.Trap(13, machine.FAULT_USER, 0x40, 1), handlers)
    assert got["action"] == "refused" and got["reason"] == "unhandled_exception", (
        "a user exception with no handler is refused, not a panic: %r" % (got,))
    got = s.handle(machine.Trap(13, machine.FAULT_USER, 0x40, 1), sr)
    assert got["action"] == "resolved" and got["frame"] is None, (
        "a user exception with a handler is resolved through it: %r" % (got,))
    got = s.handle(machine.Trap(13, 0, 0x40, 1), sr)
    assert got["action"] == "panic" and got["cause"] == "unhandled_exception", (
        "an exception in kernel mode is a panic even with a handler: %r" % (got,))
    got = s.handle(machine.Trap(0, 0, 0, 0), sr)
    assert got["action"] == "panic" and got["cause"] == "unhandled_exception", (
        "a divide error in kernel mode is a panic: %r" % (got,))
    got = s.handle(machine.Trap(6, machine.FAULT_USER, 0, 0),
                   s.TrapTable({6: "invalid_opcode"}))
    assert got["action"] == "resolved", (
        "a user opcode fault with a handler is resolved: %r" % (got,))
    got = s.handle(machine.Trap(7, machine.FAULT_USER, 0, 0), handlers)
    assert got["action"] == "refused" and got["reason"] == "unhandled_exception", (
        "a vector this machine does not have has nowhere to go: %r" % (got,))
    assert got["name"] == "unknown", (
        "the unknown vector must be named as unknown: %r" % (got,))
    got = s.handle(machine.Trap(7, 0, 0, 0), handlers)
    assert got["action"] == "panic" and got["cause"] == "unhandled_exception", (
        "an unknown vector in kernel mode is a panic: %r" % (got,))

    got = s.handle(machine.Trap(8, 0, 0x60, 2), handlers)
    assert got["action"] == "panic" and got["cause"] == "double_fault", (
        "vector 8 is a panic with its own cause: %r" % (got,))
    assert got["name"] == "double_fault" and got["word"] is None, (
        "the double fault has no fault word: %r" % (got,))
    got = s.handle(machine.Trap(13, machine.FAULT_USER, 0x40, 3), handlers,
                   in_handler=True)
    assert got["action"] == "panic" and got["cause"] == "in_handler", (
        "a trap inside a handler panics whatever it is: %r" % (got,))
    assert got["name"] == "general_protection" and got["word"] is None, (
        "the in-handler panic still names the trap it arrived on: %r" % (got,))

    # ---- the walk's own word must not be the handler's --------------------

    sup_ram = machine.RAM()
    sup_root, sup_second, sup_page = 40, 41, 42
    sup_ram.write_frame(sup_root, bytes(page))
    sup_ram.write_frame(sup_second, bytes(page))
    sup_ram.write(machine.addr_of(sup_root),
                  machine.entry_of(sup_second, allowed).to_bytes(8, "little"))
    sup_ram.write(machine.addr_of(sup_second) + 5 * 8,
                  machine.entry_of(sup_page, machine.PRESENT).to_bytes(8, "little"))
    sup_pool = _Pool((43,))
    sup_space = _space(sup_root, (sup_second,), {5: (sup_page, machine.PRESENT)})
    sup_mmu = machine.MMU(sup_ram)
    denied = None
    try:
        sup_mmu.translate(sup_root, 5 * page, "read", user=True)
    except machine.PageFault as fault:
        denied = fault
    assert denied is not None and denied.reason == "supervisor", (
        "the walk's own word for a denied user read of a supervisor page is "
        "`supervisor`, got %r" % (getattr(denied, "reason", None),))
    assert denied.access == "read", (
        "the walk's own record of the access is %r" % (denied.access,))
    assert denied.error & machine.FAULT_USER, (
        "the fault the walk raised for a user read carries the user bit: %r"
        % (denied,))
    assert s.decode(denied.error) == "protected", (
        "the handler's word for the same fault is `protected`, not %r"
        % (s.decode(denied.error),))
    got = s.handle(denied, handlers, mmu=sup_mmu, pool=sup_pool, space=sup_space)
    assert got["action"] == "refused" and got["reason"] == "protected", (
        "the handler must read the bits, not the walk's own word: %r" % (got,))
    assert sup_pool.free_count() == 1, (
        "a refused fault must not take a frame: %r free" % (sup_pool.free_count(),))
    absent = None
    try:
        sup_mmu.translate(sup_root, 6 * page, "read", user=True)
    except machine.PageFault as fault:
        absent = fault
    assert absent is not None and absent.reason == "not_present", (
        "an address with no entry at all is `not_present`, got %r"
        % (getattr(absent, "reason", None),))
    got = s.handle(absent, handlers, mmu=sup_mmu, pool=sup_pool, space=sup_space)
    assert got["action"] == "resolved" and got["frame"] == 43, (
        "a real absent-page fault from the walk must resolve: %r" % (got,))
    assert sup_space["maps"] == {5: (sup_page, machine.PRESENT),
                                 6: (43, allowed)}, (
        "the mirror after the walk's own fault is %r" % (sup_space["maps"],))

    # ---- panic_record -----------------------------------------------------

    got = s.panic_record(machine.Trap(14, machine.FAULT_WRITE | machine.FAULT_USER,
                                      0x7000, 3), "page_fault", "kernel_fault")
    assert list(got) == ["vector", "name", "word", "addr", "cpu", "handler",
                         "cause"], (
        "panic_record's keys are %r" % (list(got),))
    assert got == {"vector": 14, "name": "page_fault", "word": "not_present",
                   "addr": 0x7000, "cpu": 3, "handler": "page_fault",
                   "cause": "kernel_fault"}, (
        "the panic record is %r" % (got,))
    got = s.panic_record(machine.Trap(8, 0, 0x10, 1), None, "double_fault")
    assert got["word"] is None and got["handler"] is None, (
        "a panic with no handler records no handler: %r" % (got,))
    assert got["cause"] == "double_fault" and got["name"] == "double_fault", (
        "the panic record must carry the cause it was handed: %r" % (got,))
    got = s.panic_record(machine.Trap(13, 0, 0x10, 1), "general_protection",
                         "unhandled_exception")
    assert got["word"] is None, (
        "an error code on a general protection fault is not a fault word: %r"
        % (got,))
    assert got["handler"] == "general_protection" and got["addr"] == 0x10, (
        "the panic record must carry the handler and the address: %r" % (got,))

    # ---- the mirror and the tables agree, and the world is where it was ---

    agreed = {(vpage, mmu.entry(root, vpage * page)) for vpage in space["maps"]}
    assert agreed == {(vpage, machine.entry_of(*space["maps"][vpage]))
                      for vpage in space["maps"]}, (
        "the kernel's mirror and the machine's tables disagree: %r" % (agreed,))
    fresh = {(vpage, fresh_mmu.entry(fresh_root, vpage * page))
             for vpage in fresh_space["maps"]}
    assert fresh == {(vpage, machine.entry_of(*fresh_space["maps"][vpage]))
                     for vpage in fresh_space["maps"]}, (
        "the new space's mirror and tables disagree: %r" % (fresh,))
    walked = {(vpage, sup_mmu.entry(sup_root, vpage * page))
              for vpage in sup_space["maps"]}
    assert walked == {(vpage, machine.entry_of(*sup_space["maps"][vpage]))
                      for vpage in sup_space["maps"]}, (
        "the walked space's mirror and tables disagree: %r" % (walked,))
    assert machine.FAULT_REASONS == ("not_present", "supervisor", "read_only",
                                     "no_execute", "not_user"), (
        "the machine's own fault vocabulary moved: %r"
        % (machine.FAULT_REASONS,))
    assert machine.VECTORS[14] == "page_fault" and machine.VECTORS[8] == (
        "double_fault"), (
        "the machine's vectors moved under the stage: %r" % (machine.VECTORS,))

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _fixture(machine, mmu):
        """A walk over a RAM with five user pages, one supervisor page, no page one,
        and the lie this machine will serve for an address outside the space.

        The space is the mirror of §2.4 for the pages it really has: the root frame,
        the two second-level tables, and the six mappings. The lie is not in the
        mirror — it cannot be, because there is no such vpage — and that is exactly
        the point: the walk here does arithmetic on the address, so a vpage of
        `2 ** 18` reads the entry *past* the root table (the next frame's first
        entry) and a vpage of `-1` reads the entry *before* it (the previous frame's
        last one). Both entries name a present user page in this fixture, so a kernel
        that does not refuse an out-of-range address is handed a translation nobody
        installed — which is the mistake `user_range`'s bounds exist to catch, and
        the only way the check can reach it.
        """
        page = machine.PAGE_SIZE
        ram = mmu.ram
        present, write, user = machine.PRESENT, machine.WRITE, machine.USER
        root, lower, top = 12, 4, 9
        writable, readonly, supervisor = 6, 7, 8
        later_write, later_read, top_frame = 10, 20, 5
        root_words = ((root, 0, machine.entry_of(lower, present)),
                      (root, 511, machine.entry_of(top, present)),
                      (root, 512, machine.entry_of(14, present)),
                      (root, -1, machine.entry_of(15, present)))
        lower_words = ((lower, 0, machine.entry_of(writable, present | write | user)),
                       (lower, 2, machine.entry_of(readonly, present | user)),
                       (lower, 3, machine.entry_of(supervisor, present | write)),
                       (lower, 4, machine.entry_of(later_write,
                                                   present | write | user)),
                       (lower, 5, machine.entry_of(later_read, present | user)),
                       (top, 511, machine.entry_of(top_frame, present | write | user)),
                       (14, 0, machine.entry_of(16, present | write | user)),
                       (15, 511, machine.entry_of(17, present | write | user)))
        for frame, index, entry in root_words + lower_words:
            ram.write(machine.addr_of(frame) + index * 8, entry.to_bytes(8, "little"))
        ram.write(machine.addr_of(writable), b"hello" + bytes(page - 5))
        ram.write(machine.addr_of(writable) + 100, b"middle")
        ram.write(machine.addr_of(writable) + page - 2, b"ab")
        ram.write(machine.addr_of(readonly), b"nobody may write here")
        ram.write(machine.addr_of(supervisor), b"the kernel's own page")
        ram.write(machine.addr_of(later_write) + page - 2, b"yz")
        ram.write(machine.addr_of(later_read), b"cd")
        space = {"root": root,
                 "tables": (lower, top),
                 "maps": {0: (writable, present | write | user),
                          2: (readonly, present | user),
                          3: (supervisor, present | write),
                          4: (later_write, present | write | user),
                          5: (later_read, present | user),
                          262143: (top_frame, present | write | user)}}
        return {"ram": ram, "space": space}

    class _Pool:
        """The one thing `frames()` needs from a frame allocator: its free count."""

        def __init__(self, free):
            self._free = free

        def free_count(self):
            return self._free

    class _Watched:
        """A console that remembers, at every write, how many audit lines existed.

        `dispatch` promises to write its line *before* the act, and a line written
        afterwards is a description rather than a promise. A console that can look at
        the audit while it is being written is the only witness to that order; it
        keeps one count per write, so the check can assert the order itself rather
        than the number of lines.
        """

        def __init__(self, console, audit):
            self.console = console
            self.audit = audit
            self.at_write = []

        def write(self, data):
            self.at_write.append(len(self.audit))
            return self.console.write(data)

        def bytes(self):
            return self.console.bytes()

        def text(self):
            return self.console.text()

        def log(self):
            return self.console.log()

    import machine
    import devices
    import stage_05 as s

    page = machine.PAGE_SIZE
    width = machine.PAGE_SIZE * machine.ENTRIES * machine.ENTRIES

    # ---- the constants and the refusal family ------------------------------

    assert s.SYSCALLS == ("write", "getpid", "yield", "frames"), (
        "this stage answers four calls in this order, not %r" % (s.SYSCALLS,))
    assert s.ERRNOS == ("EFAULT", "EBADF", "EINVAL", "ENOSYS", "EPERM", "ENOENT",
                        "ENOSPC", "EMFILE", "EAGAIN"), (
        "the errno vocabulary is closed and is %r, not this stage's own"
        % (s.ERRNOS,))
    assert issubclass(s.SyscallError, ValueError), (
        "SyscallError is not a ValueError: %r" % (s.SyscallError,))

    # ---- number: from 1, in the table's order, and a suggestion -------------

    for index, name in enumerate(s.SYSCALLS, 1):
        assert s.number(name) == index, (
            "%r must be call number %d, not %r" % (name, index, s.number(name)))
    message = _refuses(s.SyscallError, "number of a name one edit from a real one",
                       lambda: s.number("writee"))
    assert "did you mean 'write'" in message, (
        "a name one edit from a real call must be told what it probably meant, "
        "got %r" % (message,))
    message = _refuses(s.SyscallError, "number of a name nowhere near one",
                       lambda: s.number("reboot"))
    assert "did you mean" not in message, (
        "a name that is not close to any call must not suggest one: %r" % (message,))
    message = _refuses(s.SyscallError, "number of something that is not a word",
                       lambda: s.number(4))
    assert "4" in message, (
        "a refusal must name the offender whatever it was, got %r" % (message,))

    # ---- user_range: the access, the user bit, every page, and the bounds ---

    mmu = machine.MMU(machine.RAM())
    fixture = _fixture(machine, mmu)
    ram = fixture["ram"]
    space = fixture["space"]
    root = space["root"]
    v1, v2, v3, v4, v5 = page, 2 * page, 3 * page, 4 * page, 5 * page
    top = 262143 * page
    writable = space["maps"][0][0]
    readonly = space["maps"][2][0]
    later = space["maps"][4][0]

    assert mmu.entry(root, width) != 0, (
        "the fixture is wrong: this machine must be willing to serve a "
        "translation for the vpage one past the address space, or the bound "
        "below is not what refused the range")
    assert mmu.entry(root, -page) != 0, (
        "the fixture is wrong: this machine must be willing to serve a "
        "translation for the vpage of a negative address")

    assert s.user_range(mmu, space, 0, page) is True, (
        "a mapped user page is a range to read")
    assert s.user_range(mmu, space, 0, page, "write") is True, (
        "a writable user page is a range to write")
    assert s.user_range(mmu, space, v2, page) is True, (
        "a read-only user page is still a range to read")
    assert s.user_range(mmu, space, v2, page, "write") is False, (
        "a read-only user page is not a range to write: the access is checked")
    assert s.user_range(mmu, space, v3, page) is False, (
        "a supervisor page is not a user range: the user bit is checked")
    assert s.user_range(mmu, space, v1, page) is False, (
        "an unmapped page is not a range")
    assert s.user_range(mmu, space, 0, page - 1) is True, (
        "a range inside one mapped page is a range")
    assert s.user_range(mmu, space, 1, page - 1) is True, (
        "a range that starts unaligned is a range")
    assert s.user_range(mmu, space, v4, 2 * page) is True, (
        "two adjacent mapped user pages are a range")
    assert s.user_range(mmu, space, 0, 2 * page) is False, (
        "a range whose last page is unmapped is not a range: every page is checked")
    assert s.user_range(mmu, space, 0, 3 * page) is False, (
        "a range whose middle page is unmapped is not a range: the page after "
        "the first is checked too")
    assert s.user_range(mmu, space, v5 - 2, page + 4) is False, (
        "a range that starts unaligned and runs into an unmapped page is not a "
        "range: the page of its last byte is checked")
    assert s.user_range(mmu, space, 0, 0) is True, (
        "a range of no bytes is a range")
    assert s.user_range(mmu, space, v1 + 5, 0) is True, (
        "a range of no bytes is a range at an unmapped address too")
    assert s.user_range(mmu, space, width, 0) is True, (
        "the address one past the last page is still inside the address space")
    assert s.user_range(mmu, space, width + 1, 0) is False, (
        "one byte past the top of the address space is not a range")
    assert s.user_range(mmu, space, top, page) is True, (
        "a range ending exactly at ADDRESS_WIDTH is a range")
    assert s.user_range(mmu, space, width, page) is False, (
        "a range at ADDRESS_WIDTH is not a range, whatever the walk would answer")
    assert s.user_range(mmu, space, -page, page) is False, (
        "a negative address is not a range, whatever the walk would answer")
    assert s.user_range(mmu, space, 0, -1) is False, (
        "a negative length is not a range")
    assert s.user_range(mmu, space, 0, page, "poke") is False, (
        "an access this machine does not have is not a range")
    assert s.user_range(mmu, space, False, page) is False, (
        "a boolean is not an address")
    assert s.user_range(mmu, space, 0, True) is False, (
        "a boolean is not a length")
    assert s.user_range(mmu, None, 0, page) is False, (
        "a call without a space has no user range")
    assert s.user_range(mmu, {"root": "the kernel's own space"}, 0, page) is False, (
        "a root that is not a frame is not a space")
    assert s.user_range(mmu, {"root": -1}, 0, page) is False, (
        "a negative root is not a frame: the machine refuses it and this answers "
        "False rather than raising")
    writes = ram.log()["writes"]
    s.user_range(mmu, space, 0, 2 * page)
    assert ram.log()["writes"] == writes, (
        "user_range must not write a byte of the range it checks")

    # ---- copy_in: the bytes, the offset, the page boundary, the refusals ----

    got = s.copy_in(mmu, space, 0, 5)
    assert got == b"hello", (
        "the first five bytes of the writable page are 'hello', not %r" % (got,))
    got = s.copy_in(mmu, space, 0, 0)
    assert got == b"", "a copy of no bytes is no bytes, not %r" % (got,)
    got = s.copy_in(mmu, space, 100, 6)
    assert got == b"middle", (
        "six bytes at offset 100 of the page are 'middle', not %r" % (got,))
    got = s.copy_in(mmu, space, v5 - 2, 4)
    assert got == b"yzcd", (
        "a range across two frames is two frames of bytes ('yzcd'), not %r"
        % (got,))
    got = s.copy_in(mmu, space, v2, 12)
    assert got == b"nobody may w", (
        "a read-only user page is readable: %r" % (got,))
    message = _refuses(s.SyscallError, "copy_in of an unmapped page",
                       lambda: s.copy_in(mmu, space, v1, 4))
    assert "%#x" % v1 in message and "%#x" % (v1 + 4) in message, (
        "a refused copy must name the range it refused, got %r" % (message,))
    _refuses(s.SyscallError, "copy_in of a supervisor page",
             lambda: s.copy_in(mmu, space, v3, 4))
    _refuses(s.SyscallError, "copy_in past the address space",
             lambda: s.copy_in(mmu, space, width, 4))
    _refuses(s.SyscallError, "copy_in of a negative address",
             lambda: s.copy_in(mmu, space, -page, 4))
    _refuses(s.SyscallError, "copy_in of a boolean address",
             lambda: s.copy_in(mmu, space, False, 4))
    _refuses(s.SyscallError, "copy_in to an address that is not an int",
             lambda: s.copy_in(mmu, space, "hello", 4))
    _refuses(s.SyscallError, "copy_in with a length that is not an int",
             lambda: s.copy_in(mmu, space, 0, "4"))
    writes = ram.log()["writes"]
    s.copy_in(mmu, space, 0, 5)
    assert ram.log()["writes"] == writes, (
        "copy_in reads the user's bytes and must not write one")

    # ---- copy_out: the count, the bytes, and a refusal that moves nothing ---

    held = ram.read(machine.addr_of(writable) + 200, 8)
    got = s.copy_out(mmu, space, 200, b"written")
    assert got == 7, "copy_out answers the bytes it wrote, not %r" % (got,)
    assert ram.read(machine.addr_of(writable) + 200, 8) == b"written" + held[7:], (
        "copy_out writes exactly its bytes where the address says: %r"
        % (ram.read(machine.addr_of(writable) + 200, 8),))
    got = s.copy_out(mmu, space, 0, b"")
    assert got == 0, "an empty copy_out writes nothing and answers 0, not %r" % (got,)
    held = ram.read(machine.addr_of(readonly), 19)
    message = _refuses(s.SyscallError, "copy_out into a read-only user page",
                       lambda: s.copy_out(mmu, space, v2, b"x"))
    assert "%#x" % v2 in message, (
        "a refused copy must name the range, got %r" % (message,))
    assert ram.read(machine.addr_of(readonly), 19) == held, (
        "a refused copy into a read-only page moved a byte: %r"
        % (ram.read(machine.addr_of(readonly), 19),))
    held = ram.read(machine.addr_of(later) + page - 2, 2)
    _refuses(s.SyscallError, "copy_out astride a read-only page",
             lambda: s.copy_out(mmu, space, v5 - 2, b"ABCD"))
    assert ram.read(machine.addr_of(later) + page - 2, 2) == held, (
        "a copy refused because of its second page moved a byte of the first: %r"
        % (ram.read(machine.addr_of(later) + page - 2, 2),))
    _refuses(s.SyscallError, "copy_out into a supervisor page",
             lambda: s.copy_out(mmu, space, v3, b"x"))
    _refuses(s.SyscallError, "copy_out into an unmapped page",
             lambda: s.copy_out(mmu, space, v1, b"x"))
    _refuses(s.SyscallError, "copy_out past the address space",
             lambda: s.copy_out(mmu, space, width, b"x"))
    _refuses(s.SyscallError, "copy_out of something that is not bytes",
             lambda: s.copy_out(mmu, space, 0, "x"))
    _refuses(s.SyscallError, "copy_out to a boolean address",
             lambda: s.copy_out(mmu, space, True, b"x"))

    # ---- dispatch: the shape, the value of each call, and each refusal ------

    console = devices.Console()
    got = s.dispatch(2, (), mmu=mmu, space=space, pid=7)
    assert tuple(got) == ("nr", "name", "value", "errno"), (
        "a call answers with exactly these keys: %r" % (tuple(got),))
    assert got == {"nr": 2, "name": "getpid", "value": 7, "errno": None}, (
        "getpid answers the caller's own pid: %r" % (got,))
    got = s.dispatch(3, (), mmu=mmu, space=space, pid=7, tick=5)
    assert got == {"nr": 3, "name": "yield", "value": 0, "errno": None}, (
        "yield answers zero whatever the tick: %r" % (got,))
    got = s.dispatch(4, (), mmu=mmu, space=space, pid=7, pool=_Pool(42))
    assert got == {"nr": 4, "name": "frames", "value": 42, "errno": None}, (
        "frames answers the pool's own free count: %r" % (got,))
    got = s.dispatch(4, (), mmu=mmu, space=space, pid=7)
    assert got == {"nr": 4, "name": "frames", "value": None, "errno": "EINVAL"}, (
        "frames without a pool has nothing to count: %r" % (got,))
    got = s.dispatch(1, (1, 0, 5), mmu=mmu, space=space, pid=7)
    assert got == {"nr": 1, "name": "write", "value": None, "errno": "EINVAL"}, (
        "write without a console has nowhere to write and must not answer that "
        "it wrote %r" % (got,))

    got = s.dispatch(1, (1, 0, 5), mmu=mmu, space=space, pid=7, console=console)
    assert got == {"nr": 1, "name": "write", "value": 5, "errno": None}, (
        "write(1, addr, 5) answers five bytes written: %r" % (got,))
    assert console.bytes() == b"hello", (
        "the console holds the user's own bytes, not %r" % (console.bytes(),))
    got = s.dispatch(1, (1, 100, 3), mmu=mmu, space=space, pid=7, console=console)
    assert console.bytes() == b"hellomid", (
        "a write sends the first n bytes of the range and no more: %r"
        % (console.bytes(),))
    got = s.dispatch(1, (1, v5 - 2, 4), mmu=mmu, space=space, pid=7, console=console)
    assert got["value"] == 4 and console.bytes() == b"hellomid" + b"yzcd", (
        "a write across a page boundary sends both frames: %r / %r"
        % (got, console.bytes()))
    got = s.dispatch(1, (1, 0, 0), mmu=mmu, space=space, pid=7, console=console)
    assert (
        got == {"nr": 1, "name": "write", "value": 0, "errno": None}
        and console.bytes() == b"hellomid" + b"yzcd"
    ), "a write of no bytes is not a refusal: %r" % (got,)

    fresh = devices.Console()
    got = s.dispatch(1, (1, v2, 12), mmu=mmu, space=space, pid=7, console=fresh)
    assert got["value"] == 12 and fresh.bytes() == b"nobody may w", (
        "a user may write to the console out of a page it may only read: %r / %r"
        % (got, fresh.bytes()))

    empty = devices.Console()
    for fd in (0, 2, 99):
        got = s.dispatch(1, (fd, 0, 5), mmu=mmu, space=space, pid=7, console=empty)
        assert got == {"nr": 1, "name": "write", "value": None, "errno": "EBADF"}, (
            "a descriptor that is not 1 is EBADF, and fd %r gave %r" % (fd, got))
    got = s.dispatch(1, (1, 0, -1), mmu=mmu, space=space, pid=7, console=empty)
    assert got == {"nr": 1, "name": "write", "value": None, "errno": "EINVAL"}, (
        "a negative length is EINVAL, not EFAULT: %r" % (got,))
    got = s.dispatch(1, (1, v1, 4), mmu=mmu, space=space, pid=7, console=empty)
    assert got == {"nr": 1, "name": "write", "value": None, "errno": "EFAULT"}, (
        "a pointer that is not a mapped user range is EFAULT: %r" % (got,))
    got = s.dispatch(1, (1, v3, 4), mmu=mmu, space=space, pid=7, console=empty)
    assert got["errno"] == "EFAULT", (
        "a supervisor page is not a user range: %r" % (got,))
    assert empty.bytes() == b"", (
        "a refused write must never reach the console: %r" % (empty.bytes(),))
    got = s.dispatch(1, (2, v1, -1), mmu=mmu, space=space, pid=7, console=empty)
    assert got["errno"] == "EBADF", (
        "the descriptor is refused before the length and the pointer: %r" % (got,))
    got = s.dispatch(1, (1, v1, -1), mmu=mmu, space=space, pid=7, console=empty)
    assert got["errno"] == "EINVAL", (
        "a bad length is refused before the pointer: %r" % (got,))
    got = s.dispatch(1, (1, "x", 4), mmu=mmu, space=space, pid=7, console=empty)
    assert got["errno"] == "EINVAL", (
        "an argument that is not an int is EINVAL, never a pointer fault: %r"
        % (got,))
    got = s.dispatch(1, ("1", 0, 4), mmu=mmu, space=space, pid=7, console=empty)
    assert got["errno"] == "EINVAL", (
        "a descriptor that is not an int is EINVAL, not EBADF: %r" % (got,))
    got = s.dispatch(1, (1, 0, "4"), mmu=mmu, space=space, pid=7, console=empty)
    assert got["errno"] == "EINVAL", (
        "a length that is not an int is EINVAL, not a length: %r" % (got,))

    for args in ((), (1,), (1, 0), (1, 0, 4, 5)):
        got = s.dispatch(1, args, mmu=mmu, space=space, pid=7, console=empty)
        assert got == {"nr": 1, "name": "write", "value": None, "errno": "EINVAL"}, (
            "write takes three arguments and was given %d: %r" % (len(args), got))
    got = s.dispatch(2, (3,), mmu=mmu, space=space, pid=7)
    assert got["errno"] == "EINVAL", (
        "getpid takes no arguments, and a call that exists is never ENOSYS: %r"
        % (got,))
    got = s.dispatch(4, (1,), mmu=mmu, space=space, pid=7, pool=_Pool(3))
    assert got["errno"] == "EINVAL", (
        "frames takes no arguments: %r" % (got,))
    for nr in (0, 5, 99):
        got = s.dispatch(nr, (), mmu=mmu, space=space, pid=7)
        assert got == {"nr": nr, "name": "unknown", "value": None,
                       "errno": "ENOSYS"}, (
            "a number nothing in the table names is ENOSYS: %r" % (got,))

    _refuses(s.SyscallError, "dispatch of a negative number",
             lambda: s.dispatch(-1, (), mmu=mmu, space=space, pid=7))
    _refuses(s.SyscallError, "dispatch of a number that is not an int",
             lambda: s.dispatch("1", (), mmu=mmu, space=space, pid=7))
    _refuses(s.SyscallError, "dispatch of a boolean number",
             lambda: s.dispatch(True, (), mmu=mmu, space=space, pid=7))
    _refuses(s.SyscallError, "dispatch of arguments that are not a tuple",
             lambda: s.dispatch(1, [1, 0, 4], mmu=mmu, space=space, pid=7))
    _refuses(s.SyscallError, "dispatch with an audit that is not a list",
             lambda: s.dispatch(2, (), mmu=mmu, space=space, pid=7, audit=()))

    # ---- the audit: the promise, the order, and both kinds of line ----------

    audit = []
    watched = _Watched(devices.Console(), audit)
    got = s.dispatch(1, (1, 0, 5), mmu=mmu, space=space, pid=7, console=watched,
                     tick=3, audit=audit)
    assert watched.at_write == [1], (
        "the audit line must be written before the act writes a byte; the console "
        "saw %r lines" % (watched.at_write,))
    assert len(audit) == 1, (
        "one call writes one line, and this wrote %d" % (len(audit),))
    line = audit[0]
    assert tuple(line) == ("pid", "tick", "nr", "name", "args", "decision",
                           "predict"), (
        "the audit line carries these seven keys in this order: %r" % (tuple(line),))
    assert line == {"pid": 7, "tick": 3, "nr": 1, "name": "write",
                    "args": (1, 0, 5), "decision": "act", "predict": 5}, (
        "an act promises the value the call returned: %r" % (line,))
    assert line["predict"] == got["value"], (
        "the promise %r is not the answer %r" % (line["predict"], got["value"]))

    audit = []
    got = s.dispatch(1, (2, 0, 5), mmu=mmu, space=space, pid=9,
                     console=devices.Console(), tick=4, audit=audit)
    assert got["errno"] == "EBADF", (
        "the call this records a promise about was refused: %r" % (got,))
    assert len(audit) == 1, (
        "a refused call is recorded too: %d lines" % (len(audit),))
    line = audit[0]
    assert line == {"pid": 9, "tick": 4, "nr": 1, "name": "write",
                    "args": (2, 0, 5), "decision": "refuse", "predict": "EBADF"}, (
        "a refusal promises the errno word it is about to return: %r" % (line,))
    assert line["predict"] == got["errno"], (
        "the promise %r is not the errno %r" % (line["predict"], got["errno"]))

    line = s.audit_line(7, 3, 3, "yield", (), "act", 0)
    assert line == {"pid": 7, "tick": 3, "nr": 3, "name": "yield", "args": (),
                    "decision": "act", "predict": 0}, (
        "audit_line writes the line it was given: %r" % (line,))
    assert line["args"] == (), (
        "the arguments of a call stay a tuple: %r" % (line["args"],))
    line = s.audit_line(7, 3, 9, "unknown", (7,), "refuse", "ENOSYS")
    assert line["decision"] == "refuse" and line["predict"] == "ENOSYS", (
        "a refusal's line carries its errno word: %r" % (line,))
    _refuses(s.SyscallError, "audit_line with a decision that is not one",
             lambda: s.audit_line(7, 3, 1, "write", (), "maybe", 5))
    _refuses(s.SyscallError, "audit_line with a value promised by a refusal",
             lambda: s.audit_line(7, 3, 1, "write", (), "refuse", 5))
    _refuses(s.SyscallError, "audit_line with a word promised by an act",
             lambda: s.audit_line(7, 3, 1, "write", (), "act", "EFAULT"))
    _refuses(s.SyscallError, "audit_line with arguments that are not a tuple",
             lambda: s.audit_line(7, 3, 1, "write", [1], "act", 5))

    # ---- and the world is where it was -------------------------------------

    for vpage, (frame, flags) in sorted(space["maps"].items()):
        entry = mmu.entry(root, vpage * page)
        assert machine.frame_of_entry(entry) == frame, (
            "vpage %d has moved in the tables: it names frame %d, not %d"
            % (vpage, machine.frame_of_entry(entry), frame))
        assert machine.flags_of_entry(entry) == flags, (
            "vpage %d has the wrong flags: %#x, not %#x"
            % (vpage, machine.flags_of_entry(entry), flags))

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named."""
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import machine
    import stage_02
    import stage_03
    import stage_06 as s
    import stage_01

    page = machine.PAGE_SIZE

    def boot(limits=None):
        """A machine, a pool over the clean map, and an empty table."""
        ram = machine.RAM()
        pool = stage_02.Frames(ram, stage_01.usable_frames(machine.boot_map("clean")))
        mmu = machine.MMU(ram)
        return ram, mmu, pool, s.Processes(mmu, pool)

    # ---- the constants ----------------------------------------------------

    assert s.USER_BASE == page, (
        "a task's memory starts at the first page above zero, not %r"
        % (s.USER_BASE,))
    assert s.STATES == ("ready", "running", "blocked", "zombie", "dead"), (
        "the task states are %r, not the five the contract froze" % (s.STATES,))
    assert s.TASK_KEYS == ("pid", "ppid", "state", "space", "frames", "uid",
                           "slots", "priority", "limits", "ticks",
                           "exit_status"), (
        "the task's keys are %r, not the eleven §2.4 froze" % (s.TASK_KEYS,))
    assert dict(s.DEFAULT_LIMITS) == {"frames": 64, "children": 8, "ticks": 256}, (
        "the default limits are %r" % (s.DEFAULT_LIMITS,))
    assert issubclass(s.ProcessError, ValueError), (
        "ProcessError is not a ValueError: %r" % (s.ProcessError,))

    # ---- new_task ---------------------------------------------------------

    task = s.new_task(7)
    assert tuple(task) == s.TASK_KEYS, (
        "a new task's keys, in order, are %r" % (tuple(task),))
    assert (task["pid"], task["ppid"], task["uid"]) == (7, 0, 0), (
        "a new task is pid 7 with no parent and uid 0: %r" % (task,))
    assert task["state"] == "ready", "a new task is ready, not %r" % (task["state"],)
    assert task["space"] is None and task["frames"] == (), (
        "a new task has no space and no frames: %r" % (task,))
    assert task["slots"] == {} and task["priority"] == 0 and task["ticks"] == 0, (
        "a new task has empty slots, priority 0 and no ticks: %r" % (task,))
    assert task["exit_status"] is None, (
        "a new task has no exit status yet: %r" % (task["exit_status"],))
    assert task["limits"] == s.DEFAULT_LIMITS, (
        "a new task's limits are the defaults: %r" % (task["limits"],))
    assert task["limits"] is not s.DEFAULT_LIMITS, (
        "a task's limits are a copy of the defaults, not the defaults")
    other = s.new_task(8)
    assert other["limits"] is not task["limits"], (
        "two tasks must not share one limits dict")
    task["limits"]["frames"] = 1
    assert other["limits"]["frames"] == 64 and s.DEFAULT_LIMITS["frames"] == 64, (
        "bending one task's limits bent another's: %r, %r"
        % (other["limits"], s.DEFAULT_LIMITS))
    shared = {"frames": 5, "children": 1, "ticks": 2}
    twin = s.new_task(10, limits=shared)
    shared["frames"] = 6
    assert twin["limits"]["frames"] == 5, (
        "a task's limits must be a copy of what it was handed: %r"
        % (twin["limits"],))
    mine = s.new_task(9, ppid=7, uid=1001, limits={"frames": 5, "children": 1,
                                                   "ticks": 2})
    assert (mine["ppid"], mine["uid"]) == (7, 1001), (
        "new_task kept the wrong parent or uid: %r" % (mine,))
    assert mine["limits"] == {"frames": 5, "children": 1, "ticks": 2}, (
        "new_task kept the wrong limits: %r" % (mine["limits"],))

    _refuses(s.ProcessError, "new_task with pid 0",
             lambda: s.new_task(0, ppid=1))
    _refuses(s.ProcessError, "new_task with a negative pid", lambda: s.new_task(-1))
    _refuses(s.ProcessError, "new_task with a boolean pid", lambda: s.new_task(True))
    _refuses(s.ProcessError, "new_task with a float uid",
             lambda: s.new_task(1, uid=1.5))
    _refuses(s.ProcessError, "new_task with a negative ppid",
             lambda: s.new_task(1, ppid=-1))
    _refuses(s.ProcessError, "new_task as its own parent",
             lambda: s.new_task(4, ppid=4))
    _refuses(s.ProcessError, "new_task with no limits at all",
             lambda: s.new_task(1, limits=()))
    _refuses(s.ProcessError, "new_task with a limit missing a resource",
             lambda: s.new_task(1, limits={"frames": 4, "children": 2}))
    _refuses(s.ProcessError, "new_task with a resource nobody has",
             lambda: s.new_task(1, limits={"frames": 4, "children": 2, "ticks": 2,
                                           "pids": 1}))
    _refuses(s.ProcessError, "new_task with a negative limit",
             lambda: s.new_task(1, limits={"frames": -1, "children": 2,
                                           "ticks": 2}))

    # ---- spawn ------------------------------------------------------------

    ram, mmu, pool, procs = boot()
    before = pool.free_count()
    first = procs.spawn()
    assert (first["pid"], first["ppid"], first["uid"]) == (1, 0, 0), (
        "spawn's first task is pid 1 with no parent and uid 0: %r" % (first,))
    frames = stage_03.space_frames(first["space"])
    assert tuple(frames) == tuple(first["frames"]), (
        "a task's frames are its space's: %r vs %r" % (first["frames"], frames))
    assert len(frames) == 3, (
        "a fresh task holds a root, one table and one page, not %d frames: %r"
        % (len(frames), frames))
    assert pool.free_count() == before - 3, (
        "a task costs three frames: the pool went from %d to %d"
        % (before, pool.free_count()))
    pages = s.images(first)
    assert [vpage for vpage, _frame in pages] == [1], (
        "a fresh task maps exactly vpage 1: %r" % (pages,))
    entry = mmu.entry(first["space"]["root"], s.USER_BASE)
    assert machine.frame_of_entry(entry) == pages[0][1], (
        "the machine's own walk must find the page `images` reports: %r vs %r"
        % (machine.frame_of_entry(entry), pages[0][1]))
    assert machine.frame_of_entry(entry) in tuple(first["frames"]), (
        "the page a task maps is one of the frames it holds: %r" % (first["frames"],))
    assert pool.state(pages[0][1]) == "used", (
        "the page's frame must be one the pool handed out: %r"
        % (pool.state(pages[0][1]),))
    flags = machine.flags_of_entry(entry)
    assert flags & machine.PRESENT and flags & machine.USER and flags & machine.WRITE, (
        "a task's first page is present, user and writable: %r" % (flags,))
    assert not flags & machine.EXEC, (
        "a task's first page is not executable: nothing in this machine is both "
        "writable and executable, and this page is writable")
    mmu.store(first["space"]["root"], s.USER_BASE, b"hello", user=True)
    got = mmu.load(first["space"]["root"], s.USER_BASE, 5, user=True)
    assert got == b"hello", "the task's own bytes are not there: %r" % (got,)
    assert procs.ledger() == {"frames_held": {1: 3}, "free": pool.free_count(),
                              "tasks": 1}, (
        "the ledger after one task is %r" % (procs.ledger(),))
    assert procs.get(1) is first, "the table must hand back the task itself"
    assert procs.get(2) is None, "there is no task 2 yet: %r" % (procs.get(2),)
    assert len(procs.log()) == 1 and procs.log()[0]["op"] == "spawn", (
        "spawn must leave one line in the log: %r" % (procs.log(),))

    second = procs.spawn(ppid=1)
    assert second["pid"] == 2, "pids are handed out in order: %r" % (second["pid"],)
    assert second["ppid"] == 1, "spawn kept the wrong parent: %r" % (second,)
    assert procs.children(first) == (2,), (
        "the first task's children are %r" % (procs.children(first),))
    user = procs.spawn(uid=1001)
    assert user["uid"] == 1001, (
        "spawn must keep the uid it was handed: %r" % (user["uid"],))
    procs.exit(user)

    held = pool.free_count()
    message = _refuses(s.ProcessError, "spawn under a pid that is not a task",
                       lambda: procs.spawn(ppid=99))
    assert "99" in message, (
        "the refusal must name the pid it could not find, got %r" % (message,))
    assert pool.free_count() == held, "a refused spawn moved a frame"
    exact = procs.spawn(limits={"frames": 3, "children": 4, "ticks": 8})
    assert len(exact["frames"]) == 3, (
        "a task whose frame limit is exactly its cost must be allowed to exist: "
        "%r for a limit of 3" % (exact["frames"],))
    held = pool.free_count()
    first["limits"] = {"frames": 64, "children": 1, "ticks": 256}
    _refuses(s.ProcessError, "spawn under a parent with no children left",
             lambda: procs.spawn(ppid=first["pid"]))
    assert pool.free_count() == held, "a refused spawn moved a frame"

    held = pool.free_count()
    message = _refuses(s.ProcessError, "spawn that cannot hold its own space",
                       lambda: procs.spawn(limits={"frames": 2, "children": 4,
                                                   "ticks": 8}))
    assert "2" in message and pool.free_count() == held, (
        "a frame limit that cannot hold a task must be refused before a frame "
        "moves, got %r for %d free" % (message, pool.free_count()))
    ram2, mmu2, pool2, procs2 = boot()
    pool2.alloc(pool2.free_count() - 2)
    assert pool2.free_count() == 2, "the fixture needs a pool with two frames left"
    _refuses(s.ProcessError, "spawn with a pool that has too few frames",
             lambda: procs2.spawn())
    assert pool2.free_count() == 2, "a refused spawn moved a frame"
    zombie_parent = procs.spawn()
    procs.exit(zombie_parent)
    held = pool.free_count()
    message = _refuses(s.ProcessError, "spawn under a zombie",
                       lambda: procs.spawn(ppid=zombie_parent["pid"]))
    assert pool.free_count() == held, "a refused spawn moved a frame"

    # ---- fork -------------------------------------------------------------

    ram, mmu, pool, procs = boot()
    parent = procs.spawn()
    stage_03.map_page(mmu, pool, parent["space"], s.USER_BASE + page,
                      pool.alloc(1)[0], machine.WRITE | machine.USER)
    parent["frames"] = stage_03.space_frames(parent["space"])
    mmu.store(parent["space"]["root"], s.USER_BASE, b"parent", user=True)
    mmu.store(parent["space"]["root"], s.USER_BASE + page, b"second", user=True)
    parent["limits"] = {"frames": 40, "children": 3, "ticks": 99}
    parent["priority"] = 3
    before = pool.free_count()
    child = procs.fork(parent)
    assert (child["pid"], child["ppid"]) == (2, 1), (
        "a fork's child is the next pid and its parent's child: %r" % (child,))
    assert child["state"] == "ready", "a fork's child is ready: %r" % (child,)
    assert child["limits"] == parent["limits"], (
        "a fork's limits are its parent's: %r" % (child["limits"],))
    assert child["limits"] is not parent["limits"], (
        "a fork copies its parent's limits instead of sharing them")
    assert child["slots"] is not parent["slots"] and child["slots"] == {}, (
        "a fork copies its parent's slots: %r" % (child["slots"],))
    assert child["priority"] == parent["priority"], (
        "a fork keeps its parent's priority: %r" % (child["priority"],))
    assert len(child["frames"]) == len(parent["frames"]), (
        "a fork holds as many frames as its parent: %r vs %r"
        % (child["frames"], parent["frames"]))
    assert not set(child["frames"]) & set(parent["frames"]), (
        "a fork must not share one frame with its parent: %r"
        % (sorted(set(child["frames"]) & set(parent["frames"])),))
    assert pool.free_count() == before - len(parent["frames"]), (
        "a fork costs one frame per frame its parent holds: %d free, was %d"
        % (pool.free_count(), before))
    for vpage, frame in s.images(parent):
        got = mmu.load(child["space"]["root"], vpage * page, 8, user=True)
        want = mmu.load(parent["space"]["root"], vpage * page, 8, user=True)
        assert got == want, (
            "vpage %d holds %r in the child and %r in the parent"
            % (vpage, got, want))
        child_entry = mmu.entry(child["space"]["root"], vpage * page)
        assert machine.frame_of_entry(child_entry) in tuple(child["frames"]), (
            "the child's own table must map vpage %d to a frame the child holds, "
            "not %r" % (vpage, machine.frame_of_entry(child_entry)))
        assert machine.frame_of_entry(child_entry) != frame, (
            "the child's vpage %d is the parent's own frame: a fork that shares "
            "a page is a fork that did not copy it" % (vpage,))
    mirror = {vpage: frame for vpage, frame, _flags in stage_03.mapped(child["space"])}
    assert mirror == {vpage: frame for vpage, frame in s.images(child)}, (
        "the child's mirror and its pages disagree: %r vs %r"
        % (mirror, s.images(child)))
    for vpage, frame in s.images(child):
        entry = mmu.entry(child["space"]["root"], vpage * page)
        assert machine.frame_of_entry(entry) == frame, (
            "the child's mirror says frame %d for vpage %d and its tables say "
            "%d" % (frame, vpage, machine.frame_of_entry(entry)))
    mmu.store(child["space"]["root"], s.USER_BASE, b"child!", user=True)
    assert mmu.load(parent["space"]["root"], s.USER_BASE, 6, user=True) == b"parent", (
        "a write in the child reached the parent's frame")
    mmu.store(parent["space"]["root"], s.USER_BASE + page, b"parent", user=True)
    assert mmu.load(child["space"]["root"], s.USER_BASE + page, 6, user=True) == b"second", (
        "a write in the parent reached the child's frame")
    assert procs.children(parent) == (2,), (
        "the parent's children are %r" % (procs.children(parent),))
    _refuses(s.ProcessError, "fork of a copy of a task",
             lambda: procs.fork(dict(parent)))
    _refuses(s.ProcessError, "fork of a pid nobody has",
             lambda: procs.fork({"pid": 99, "state": "ready"}))
    zombie = procs.spawn()
    procs.exit(zombie)
    _refuses(s.ProcessError, "fork of a zombie", lambda: procs.fork(zombie))
    tight = procs.spawn(limits={"frames": 5, "children": 4, "ticks": 64})
    for extra in (1, 2):
        stage_03.map_page(mmu, pool, tight["space"], s.USER_BASE + extra * page,
                          pool.alloc(1)[0], machine.WRITE | machine.USER)
    tight["frames"] = stage_03.space_frames(tight["space"])
    assert len(tight["frames"]) == 5, (
        "the fixture needs a parent that holds more than a fresh task: %r"
        % (tight["frames"],))
    tight["limits"]["frames"] = 4
    held_frames = pool.free_count()
    _refuses(s.ProcessError, "fork that cannot hold every frame of its parent",
             lambda: procs.fork(tight))
    assert pool.free_count() == held_frames, "a refused fork moved a frame"
    lonely_parent = procs.spawn(limits={"frames": 64, "children": 0, "ticks": 64})
    _refuses(s.ProcessError, "fork by a parent with no children left",
             lambda: procs.fork(lonely_parent))
    _refuses(s.ProcessError, "spawn by a parent with no children left",
             lambda: procs.spawn(ppid=lonely_parent["pid"]))

    # ---- exec -------------------------------------------------------------

    ram, mmu, pool, procs = boot()
    task = procs.spawn()
    for index in range(2):
        stage_03.map_page(mmu, pool, task["space"], s.USER_BASE + (2 + index) * page,
                          pool.alloc(1)[0], machine.WRITE | machine.USER)
    task["frames"] = stage_03.space_frames(task["space"])
    old_frames = tuple(task["frames"])
    old_pages = s.images(task)
    old_tables = tuple(task["space"]["tables"])
    before = pool.free_count()
    procs.exec(task, 2)
    pages_now = s.images(task)
    assert [vpage for vpage, _frame in pages_now] == [1, 2], (
        "an exec of two pages maps vpage 1 and 2: %r" % (pages_now,))
    assert len({frame for _vpage, frame in pages_now}) == 2, (
        "an exec must give each page a frame of its own: %r" % (pages_now,))
    assert len(task["frames"]) == 4, (
        "an exec of two pages leaves a root, a table and two pages: %r"
        % (task["frames"],))
    assert task["frames"] == tuple(stage_03.space_frames(task["space"])), (
        "an exec must leave the task's frames equal to its space's: %r"
        % (task["frames"],))
    assert tuple(task["space"]["tables"]) == old_tables, (
        "an exec keeps the tables: %r -> %r"
        % (old_tables, tuple(task["space"]["tables"])))
    for frame in stage_03.space_frames(task["space"]):
        assert pool.state(frame) == "used", (
            "a frame the space still holds is %r in the pool"
            % (pool.state(frame),))
    assert pool.free_count() == before + len(old_pages) - 2, (
        "an exec of two pages releases its three and takes two: %d free, was %d"
        % (pool.free_count(), before))
    for vpage, frame in s.images(task):
        assert pool.state(frame) == "used", (
            "vpage %d's frame is not the pool's to hand out: %r" % (vpage, frame))
        assert mmu.entry(task["space"]["root"], vpage * page), (
            "the machine must walk vpage %d after an exec" % (vpage,))
    mmu.store(task["space"]["root"], s.USER_BASE, b"data", user=True)
    assert mmu.load(task["space"]["root"], s.USER_BASE, 4, user=True) == b"data", (
        "an exec's fresh pages must be user-writable")
    far = s.USER_BASE + machine.ENTRIES * page
    stage_03.map_page(mmu, pool, task["space"], far, pool.alloc(1)[0],
                      machine.WRITE | machine.USER)
    task["frames"] = stage_03.space_frames(task["space"])
    task["limits"]["frames"] = 3
    _refuses(s.ProcessError, "exec whose tables push it over its limit",
             lambda: procs.exec(task, 1))
    task["limits"]["frames"] = 4
    procs.exec(task, 1)
    assert len(task["frames"]) == 4, (
        "an exec must count the tables it already has: %r" % (task["frames"],))
    assert len(task["frames"]) <= task["limits"]["frames"], (
        "an exec left the task over its own frame limit: %r" % (task["frames"],))
    task["limits"]["frames"] = 64
    _refuses(s.ProcessError, "exec of a task with no pages at all",
             lambda: procs.exec(task, 0))
    message = _refuses(s.ProcessError, "exec past the end of the address space",
                       lambda: procs.exec(task, 300000))
    assert "space" in message and "300000" in message, (
        "the refusal must name the address space and the count, got %r"
        % (message,))
    held = pool.free_count()
    before_pages = s.images(task)
    message = _refuses(s.ProcessError, "exec past the task's frame limit",
                       lambda: procs.exec(task, 400))
    ram3, mmu3, pool3, procs3 = boot()
    small = procs3.spawn()
    pool3.alloc(pool3.free_count() - 1)
    assert pool3.free_count() == 1, "the fixture needs a pool with one frame left"
    _refuses(s.ProcessError, "exec with a pool that has too few frames",
             lambda: procs3.exec(small, 3))
    assert pool3.free_count() == 1, "a refused exec moved a frame"
    assert "400" in message and pool.free_count() == held, (
        "an exec over the frame limit must be refused before a frame moves, "
        "got %r for %d free" % (message, pool.free_count()))
    assert s.images(task) == before_pages, (
        "a refused exec changed the task's pages: %r vs %r"
        % (s.images(task), before_pages))

    # ---- exit -------------------------------------------------------------

    ram, mmu, pool, procs = boot()
    parent = procs.spawn()
    child = procs.spawn(ppid=1)
    grandchild = procs.spawn(ppid=child["pid"])
    child_frames = tuple(child["frames"])
    before = pool.free_count()
    procs.exit(child, 7)
    assert child["state"] == "zombie", (
        "an exited task is a zombie, not %r" % (child["state"],))
    assert child["exit_status"] == 7, (
        "an exited task keeps its status: %r" % (child["exit_status"],))
    assert child["space"] is None and child["frames"] == (), (
        "an exited task holds nothing: %r" % (child,))
    assert pool.free_count() == before + len(child_frames), (
        "an exit gives back every frame the task held: %d free, was %d"
        % (pool.free_count(), before))
    for frame in child_frames:
        assert pool.state(frame) == "free", (
            "frame %d is %r after the task that held it exited"
            % (frame, pool.state(frame)))
    assert procs.get(grandchild["pid"])["ppid"] == 0, (
        "a dying task's children belong to pid 0, not %r"
        % (procs.get(grandchild["pid"])["ppid"],))
    assert procs.children(child) == (), (
        "a zombie has no children to hand out: %r" % (procs.children(child),))
    _refuses(s.ProcessError, "exit twice",
             lambda: procs.exit(child))
    _refuses(s.ProcessError, "exit of a stranger",
             lambda: procs.exit({"pid": 99, "state": "ready"}))

    # ---- wait -------------------------------------------------------------

    reaped = procs.wait(parent, child["pid"])
    assert reaped == {"reaped": child["pid"], "status": 7}, (
        "a wait for a zombie child reaps it: %r" % (reaped,))
    assert procs.get(child["pid"]) is None, (
        "a reaped task is gone from the table: %r" % (procs.get(child["pid"]),))
    _refuses(s.ProcessError, "a wait for a child that was already reaped",
             lambda: procs.wait(parent, child["pid"]))
    alive = procs.spawn(ppid=parent["pid"])
    blocked = procs.wait(parent)
    assert blocked == {"blocked": True}, (
        "a wait with a live child and no zombie is blocked: %r" % (blocked,))
    assert procs.get(alive["pid"]) is alive, (
        "a blocked wait must not reap the child that is still alive")
    named = procs.wait(parent, alive["pid"])
    assert named == {"blocked": True}, (
        "a wait for a named child that is alive is blocked: %r" % (named,))
    assert procs.get(alive["pid"]) is alive, (
        "a blocked wait for a named child must not reap it")
    assert procs.get(1) is parent, "a blocked wait must not reap anything"
    _refuses(s.ProcessError, "a wait for a pid that is not this parent's child",
             lambda: procs.wait(parent, 999))
    _refuses(s.ProcessError, "a wait for a pid that is not a child",
             lambda: procs.wait(parent, grandchild["pid"]))
    lonely = procs.spawn()
    _refuses(s.ProcessError, "a wait by a task with no children at all",
             lambda: procs.wait(lonely))
    first_dead = procs.spawn(ppid=parent["pid"])
    second_dead = procs.spawn(ppid=parent["pid"])
    want = tuple(sorted((alive["pid"], first_dead["pid"], second_dead["pid"])))
    assert procs.children(parent) == want, (
        "children are pids ascending: %r, not %r" % (procs.children(parent), want))
    procs.exit(first_dead, 3)
    procs.exit(second_dead, 4)
    assert procs.wait(parent) == {"reaped": first_dead["pid"], "status": 3}, (
        "a wait for any child reaps the lowest-numbered zombie")
    assert procs.wait(parent, second_dead["pid"]) == {"reaped": second_dead["pid"],
                                                      "status": 4}, (
        "a wait must reap the zombie it was asked for")
    _refuses(s.ProcessError, "a wait for a child that never was a child",
             lambda: procs.wait(parent, parent["pid"]))

    # ---- the ledger and the log -------------------------------------------

    ram, mmu, pool, procs = boot()
    one = procs.spawn()
    two = procs.spawn(ppid=one["pid"])
    procs.fork(two)
    procs.exit(two)
    ledger = procs.ledger()
    assert ledger["tasks"] == 3, (
        "the zombie is still in the table: %r" % (ledger,))
    assert ledger["frames_held"] == {one["pid"]: len(one["frames"]),
                                     two["pid"]: 0,
                                     3: len(procs.get(3)["frames"])}, (
        "the ledger's frames per task are %r" % (ledger["frames_held"],))
    assert ledger["frames_held"][two["pid"]] == 0, (
        "a zombie holds no frames and is still counted: %r"
        % (ledger["frames_held"],))
    procs.wait(one, two["pid"])
    assert procs.log()[-1]["free"] == pool.free_count(), (
        "the last log line's free count must be the pool's: %r vs %r"
        % (procs.log()[-1], pool.free_count()))
    assert procs.log()[-1]["op"] == "reap" and procs.log()[-1]["frames"] == 0, (
        "a reap holds no frames and says so: %r" % (procs.log()[-1],))
    stolen = pool.alloc(1)[0]
    ledger = procs.ledger()
    assert ledger["free"] == pool.free_count(), (
        "the ledger's free count must be the pool's, not the kernel's: %r vs %r"
        % (ledger, pool.free_count()))
    assert ledger["tasks"] == 2, (
        "the reaped task is gone and two are left: %r" % (ledger,))
    assert ledger["frames_held"] == {one["pid"]: len(one["frames"]),
                                     3: len(procs.get(3)["frames"])}, (
        "the ledger's frames per task are %r" % (ledger["frames_held"],))
    assert all(count > 0 for count in ledger["frames_held"].values()), (
        "a task in the table holds at least its root: %r" % (ledger["frames_held"],))
    ops = [line["op"] for line in procs.log()]
    assert ops == ["spawn", "spawn", "fork", "exit", "wait", "reap"], (
        "the log's ops in order are %r" % (ops,))
    assert procs.log()[0]["frames"] == len(one["frames"]), (
        "a log line's frames are the task's: %r" % (procs.log()[0],))
    assert procs.log()[0]["pid"] == one["pid"], (
        "a log line's pid is the task's: %r" % (procs.log()[0],))
    assert isinstance(procs.log(), tuple), (
        "the log is a tuple, not %r" % (type(procs.log()).__name__,))
    assert s.images(s.new_task(1)) == (), (
        "a task with no space has no pages: %r" % (s.images(s.new_task(1)),))
    assert pool.state(stolen) == "used", (
        "the frame taken behind the table's back is the pool's business")
    _refuses(s.ProcessError, "get() with a pid that is not a pid",
             lambda: procs.get(None))
    _refuses(s.ProcessError, "children() of a stranger",
             lambda: procs.children({"pid": 99}))

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _task(pid, priority=5, state="ready"):
        """A task of the shape §2.4 froze: eleven keys, and the scheduler's view."""
        return {"pid": pid, "ppid": 0, "state": state, "space": None, "frames": (),
                "uid": 0, "slots": {}, "priority": priority,
                "limits": {"frames": 1, "children": 1, "ticks": 1},
                "ticks": 0, "exit_status": None}

    def _table(*tasks):
        return {task["pid"]: task for task in tasks}

    import stage_07 as s

    # ---- the constant and the refusal family ------------------------------

    assert s.AGEING == 8, (
        "ageing buys a point of priority every 8 ticks of waiting, not %r"
        % (s.AGEING,))
    assert isinstance(s.AGEING, int) and not isinstance(s.AGEING, bool), (
        "ageing is a tick count, not %r" % (s.AGEING,))
    assert issubclass(s.SchedError, ValueError), (
        "SchedError is not a ValueError: %r" % (s.SchedError,))

    # ---- the quantum ------------------------------------------------------

    sched = s.Scheduler()
    assert sched.quantum == 3, (
        "the default quantum is 3 ticks, not %r" % (sched.quantum,))
    assert s.Scheduler(7).quantum == 7, "a quantum is what it was built with"
    assert s.Scheduler(quantum=1).quantum == 1, "a quantum may be one tick"
    message = _refuses(s.SchedError, "a quantum of no ticks",
                       lambda: s.Scheduler(0))
    assert "0" in message, (
        "a quantum of no ticks must name it, got %r" % (message,))
    _refuses(s.SchedError, "a negative quantum", lambda: s.Scheduler(-3))
    _refuses(s.SchedError, "a quantum that is not a number",
             lambda: s.Scheduler("3"))
    _refuses(s.SchedError, "a quantum that is not a whole number",
             lambda: s.Scheduler(2.5))
    _refuses(s.SchedError, "a boolean quantum", lambda: s.Scheduler(True))

    # ---- add, and the run queue in arrival order --------------------------

    first, second = _task(1), _task(2)
    sched = s.Scheduler(quantum=1)
    sched.add(first)
    sched.add(second)
    assert sched.queues() == {"ready": (1, 2)}, (
        "the run queue is the pids in arrival order, not %r" % (sched.queues(),))
    assert sched.log() == (("add", 1), ("add", 2)), (
        "the ledger records one add per task: %r" % (sched.log(),))
    message = _refuses(s.SchedError, "adding the same pid twice",
                       lambda: sched.add(_task(1)))
    assert "1" in message, (
        "a pid queued twice must be named, got %r" % (message,))
    message = _refuses(s.SchedError, "adding something that is not a task",
                       lambda: sched.add("1"))
    assert "dict" in message, (
        "the refusal must say what a task is, got %r" % (message,))
    message = _refuses(s.SchedError, "adding a task without a pid",
                       lambda: sched.add({"state": "ready"}))
    assert "pid" in message, (
        "a task without a pid must be refused naming it, got %r" % (message,))
    _refuses(s.SchedError, "adding a task whose pid is not an int",
             lambda: sched.add(_task("1")))
    _refuses(s.SchedError, "adding a task whose pid is a bool",
             lambda: s.Scheduler(quantum=1).add(_task(True)))
    message = _refuses(s.SchedError, "adding a task with a negative pid",
                       lambda: sched.add(_task(-2)))
    assert "-2" in message, (
        "a negative pid must be named, got %r" % (message,))

    # ---- the pick: FIFO among equals, priority before arrival -------------

    later, sooner = _task(5), _task(4)
    sched = s.Scheduler(quantum=2)
    sched.add(later)
    sched.add(sooner)
    step = sched.step(0, _table(later, sooner))
    assert tuple(step) == ("ran", "switches", "tick"), (
        "a step answers with ran, switches and tick, not %r" % (tuple(step),))
    assert step == {"ran": 5, "switches": 1, "tick": 0}, (
        "the first arrival runs first among equals: %r" % (step,))
    assert sched.queues() == {"ready": (5, 4)}, (
        "a task that has not used its quantum keeps its place: %r"
        % (sched.queues(),))

    slow, quick = _task(6, priority=9), _task(7, priority=0)
    sched = s.Scheduler(quantum=1)
    sched.add(slow)
    sched.add(quick)
    assert sched.step(0, _table(slow, quick)) == {"ran": 7, "switches": 1, "tick": 0}, (
        "the lower priority number runs first, whatever the arrival order")

    # ---- the quantum, the rotation, and the trace -------------------------

    a, b = _task(1), _task(2)
    sched = s.Scheduler(quantum=2)
    sched.add(a)
    sched.add(b)
    result = sched.run(6, _table(a, b))
    assert tuple(result) == ("trace", "switches", "per_pid", "starved"), (
        "a run answers with trace, switches, per_pid and starved, not %r"
        % (tuple(result),))
    assert result["trace"] == ((0, 1), (1, 1), (2, 2), (3, 2), (4, 1), (5, 1)), (
        "two equal tasks take two ticks each and then the queue rotates: %r"
        % (result["trace"],))
    assert result["switches"] == 3, (
        "the task that ran changed three times: %r" % (result["switches"],))
    assert result["per_pid"] == {1: 4, 2: 2}, (
        "the ticks each pid got are wrong: %r" % (result["per_pid"],))
    assert sum(result["per_pid"].values()) == 6, (
        "the ticks per pid must sum to the ticks that ran: %r"
        % (result["per_pid"],))
    assert result["starved"] == (), (
        "both tasks ran, so nobody starved: %r" % (result["starved"],))
    assert sched.queues() == {"ready": (2, 1)}, (
        "the task that ran out of quantum is at the back: %r" % (sched.queues(),))

    # ---- ageing: a low-priority task cannot starve for ever ---------------

    low, hog = _task(1, priority=8), _task(2, priority=0)
    sched = s.Scheduler(quantum=1)
    sched.add(low)
    sched.add(hog)
    short = sched.run(8, _table(low, hog))
    assert short["per_pid"] == {2: 8}, (
        "in eight ticks the priority-0 task runs them all: %r" % (short["per_pid"],))
    assert short["starved"] == (1,), (
        "a task ready for the whole run and never picked is starved: %r"
        % (short["starved"],))

    sched = s.Scheduler(quantum=1)
    sched.add(low)
    sched.add(hog)
    long_run = sched.run(72, _table(low, hog))
    assert long_run["per_pid"] == {2: 71, 1: 1}, (
        "in 72 ticks ageing must let the priority-8 task run exactly once: %r"
        % (long_run["per_pid"],))
    assert long_run["starved"] == (), (
        "ageing is what stops the starvation: %r" % (long_run["starved"],))

    # ---- a blocked, zombie or dead task is never scheduled ----------------

    sleeper, zombie, dead, runner = (_task(1, state="blocked"),
                                     _task(2, state="zombie"),
                                     _task(3, state="dead"), _task(4))
    sched = s.Scheduler(quantum=1)
    for task in (sleeper, zombie, dead, runner):
        sched.add(task)
    got = sched.run(3, _table(sleeper, zombie, dead, runner))
    assert got["per_pid"] == {4: 3}, (
        "only the ready task may run: %r" % (got["per_pid"],))
    assert got["starved"] == (), (
        "a blocked, zombie or dead task was never ready: %r" % (got["starved"],))

    # the one currently running, blocked under it, stops being scheduled
    running, other = _task(1), _task(2)
    sched = s.Scheduler(quantum=3)
    sched.add(running)
    sched.add(other)
    assert sched.step(0, _table(running, other))["ran"] == 1, (
        "the first task runs first")
    assert running["state"] == "running", (
        "the task that is running says so: %r" % (running["state"],))
    sched.block(running, "io")
    assert running["state"] == "blocked", (
        "a blocked task is marked blocked: %r" % (running["state"],))
    assert sched.step(1, _table(running, other)) == {"ran": 2, "switches": 2,
                                                     "tick": 1}, (
        "a task that blocks mid-quantum hands the cpu over: %r"
        % (sched.queues(),))

    # ---- block, and the queue name it refuses ----------------------------

    x, y = _task(5), _task(3)
    sched = s.Scheduler(quantum=1)
    sched.add(x)
    sched.add(y)
    assert sched.block(x, "io") == {"pid": 5, "queue": "io", "state": "blocked"}, (
        "block answers with the pid, the queue and the state")
    sched.block(y, "io")
    assert sched.queues() == {"ready": (), "io": (5, 3)}, (
        "a wait queue is in arrival order, and a blocked task is not ready: %r"
        % (sched.queues(),))
    message = _refuses(s.SchedError, "blocking a task twice",
                       lambda: sched.block(x, "io"))
    assert "5" in message and "io" in message, (
        "a second enqueue must name the pid and the queue, got %r" % (message,))
    guard = _task(4)
    gate = s.Scheduler(quantum=1)
    gate.add(guard)
    message = _refuses(s.SchedError, "blocking on a queue with no name",
                       lambda: gate.block(guard, ""))
    assert "''" in message or '""' in message, (
        "an empty queue name must be named, got %r" % (message,))
    message = _refuses(s.SchedError, "blocking on a queue that is not a word",
                       lambda: gate.block(guard, 7))
    assert "7" in message, (
        "a queue name that is not a word must be named, got %r" % (message,))
    message = _refuses(s.SchedError, "blocking on the run queue's own name",
                       lambda: gate.block(guard, "ready"))
    assert "ready" in message, (
        "the run queue's name is not a work queue, got %r" % (message,))
    message = _refuses(s.SchedError, "blocking a task that is not queued",
                       lambda: gate.block(_task(9), "io"))
    assert "9" in message, (
        "a task this scheduler does not hold must be named, got %r" % (message,))

    # ---- wake: pid order, once, and back into the run queue ---------------

    woken = sched.wake("io", "sector 7")
    assert woken == (3, 5), (
        "a wake names its tasks in pid order, not arrival order: %r" % (woken,))
    assert isinstance(woken, tuple), "a wake answers with a tuple: %r" % (type(woken),)
    assert sched.queues() == {"ready": (3, 5)}, (
        "a woken task is ready again, at the back in pid order: %r"
        % (sched.queues(),))
    assert x["state"] == "ready" and y["state"] == "ready", (
        "a woken task is ready again: %r, %r" % (x["state"], y["state"]))
    assert sched.wake("io", "sector 7") == (), (
        "a task woken once is not woken by the second wake of the queue")
    assert sched.queues() == {"ready": (3, 5)}, "the second wake changed nothing"
    again = sched.run(2, _table(x, y))
    assert again["trace"] == ((0, 3), (1, 5)), (
        "the woken tasks run, in the order the wake put them: %r"
        % (again["trace"],))
    assert sched.log()[-1] == ("run", 1, 5), (
        "the ledger ends with the last tick: %r" % (sched.log()[-1],))

    # ---- the ledger keeps the value a wake carried ------------------------

    log = sched.log()
    assert ("wake", "io", "sector 7", (3, 5)) in log, (
        "the ledger records the queue, the value and the pids: %r" % (log,))
    assert ("wake", "io", "sector 7", ()) in log, (
        "a wake that woke nobody is in the ledger too: %r" % (log,))
    assert ("block", 5, "io") in log and ("block", 3, "io") in log, (
        "every block is in the ledger: %r" % (log,))
    assert isinstance(log, tuple), "the ledger is a tuple: %r" % (type(log),)

    # ---- remove: out of both queues, and free to be added again -----------

    one, two = _task(1), _task(2)
    sched = s.Scheduler(quantum=1)
    sched.add(one)
    sched.add(two)
    sched.block(two, "io")
    sched.remove(two)
    assert sched.queues() == {"ready": (1,)}, (
        "a removed task is out of the run queue and off its wait queue: %r"
        % (sched.queues(),))
    assert sched.wake("io", "x") == (), (
        "no later wake can wake a task that was removed")
    message = _refuses(s.SchedError, "removing a task twice",
                       lambda: sched.remove(two))
    assert "2" in message, (
        "a removed pid must be named, got %r" % (message,))
    _refuses(s.SchedError, "removing something that is not a task",
             lambda: sched.remove((1,)))
    sched.add(two)
    assert sched.queues() == {"ready": (1, 2)}, (
        "a removed pid is free to be added again: %r" % (sched.queues(),))

    # a pid that was removed and added again is a new arrival, so it switches
    lonely = _task(1)
    sched = s.Scheduler(quantum=1)
    sched.add(lonely)
    assert sched.step(0, _table(lonely)) == {"ran": 1, "switches": 1, "tick": 0}, (
        "the first task to run is a switch")
    sched.remove(lonely)
    sched.add(lonely)
    assert sched.step(1, _table(lonely)) == {"ran": 1, "switches": 2, "tick": 1}, (
        "a pid that was removed and added again is a new arrival: a switch")

    # removing the task that is running hands the cpu over at the next tick
    one, two = _task(1), _task(2)
    sched = s.Scheduler(quantum=3)
    sched.add(one)
    sched.add(two)
    assert sched.step(0, _table(one, two)) == {"ran": 1, "switches": 1, "tick": 0}
    sched.remove(one)
    assert sched.step(1, _table(one, two)) == {"ran": 2, "switches": 2, "tick": 1}, (
        "the tick after the running task is removed runs the other one")

    # ---- the tasks table a step refreshes its view from -------------------

    steady, rival = _task(1), _task(2)
    sched = s.Scheduler(quantum=1)
    sched.add(steady)
    sched.add(rival)
    assert sched.step(0, _table(steady, rival))["ran"] == 1, (
        "the first arrival runs first")
    assert sched.step(1, _table(steady, _task(2, priority=9)))["ran"] == 1, (
        "a step sees the task dict it was handed, not the one it stored")
    message = _refuses(s.SchedError, "a task filed under another pid",
                       lambda: sched.step(2, {9: _task(1)}))
    assert "1" in message and "9" in message, (
        "the task and the pid it is filed under must both be named, got %r"
        % (message,))

    # ---- the tick refusals ------------------------------------------------

    message = _refuses(s.SchedError, "a negative tick",
                       lambda: sched.step(-1, _table(steady)))
    assert "-1" in message, "a negative tick must be named, got %r" % (message,)
    message = _refuses(s.SchedError, "a tick that is not a number",
                       lambda: sched.step("0", _table(steady)))
    assert "0" in message, "a tick that is not a number must be named"
    _refuses(s.SchedError, "a boolean tick", lambda: sched.step(True, _table(steady)))
    message = _refuses(s.SchedError, "ticks that are not a mapping",
                       lambda: sched.step(0, [_task(1)]))
    assert "mapping" in message, (
        "the refusal must say what the tasks are, got %r" % (message,))
    _refuses(s.SchedError, "a run of a negative number of ticks",
             lambda: sched.run(-1, _table(steady)))
    _refuses(s.SchedError, "a run of ticks that are not a number",
             lambda: sched.run(True, _table(steady)))

    # ---- a tick where nothing was ready is in the trace -------------------

    lonely = _task(1)
    sched = s.Scheduler(quantum=1)
    sched.add(lonely)
    assert sched.run(1, _table(lonely)) == {"trace": ((0, 1),), "switches": 1,
                                            "per_pid": {1: 1}, "starved": ()}, (
        "a one-tick run of one ready task runs it")
    sched.block(lonely, "io")
    nothing = sched.run(2, _table(lonely))
    assert nothing["trace"] == ((0, None), (1, None)), (
        "a tick with nothing ready is in the trace as None: %r"
        % (nothing["trace"],))
    assert nothing["per_pid"] == {} and nothing["starved"] == (), (
        "nobody ran and nobody was ready: %r" % (nothing,))
    assert sched.log()[-2:] == (("run", 0, None), ("run", 1, None)), (
        "a tick on which nobody ran is in the ledger too: %r" % (sched.log()[-2:],))
    assert sched.run(0, _table(lonely)) == {"trace": (), "switches": 1,
                                            "per_pid": {}, "starved": ()}, (
        "a run of no ticks runs nothing")

    # ---- the wakeup that never came --------------------------------------

    late = _task(1)
    naive = s.Scheduler(quantum=1)
    naive.add(late)
    assert naive.wake("disk", 7) == (), (
        "a wake on a queue nobody waits on wakes nobody")
    naive.block(late, "disk")
    assert naive.queues() == {"ready": (), "disk": (1,)}, (
        "the naive sleep left the task on the queue: %r" % (naive.queues(),))
    assert late["state"] == "blocked", (
        "the naive sleep left the task blocked: %r" % (late["state"],))
    lost = naive.run(3, _table(late))
    assert lost["trace"] == ((0, None), (1, None), (2, None)), (
        "a task that slept after the wakeup runs on no tick: %r"
        % (lost["trace"],))
    assert lost["per_pid"] == {} and lost["starved"] == (), (
        "the lost wakeup leaves the task unrun and unready: %r" % (lost,))
    assert naive.wake("disk", 7) == (1,), (
        "only a wake that comes after the sleep wakes the sleeper")
    assert naive.run(2, _table(late))["per_pid"] == {1: 2}, (
        "the same task runs once a wake really reaches it")

    # ---- and the same race, slept with wait_on ---------------------------

    calls = []

    def arrives_between_the_checks(task):
        calls.append(task["pid"])
        return len(calls) >= 2

    sleeper = _task(3)
    fixed = s.Scheduler(quantum=1)
    fixed.add(sleeper)
    answer = s.wait_on(fixed, sleeper, "disk", arrives_between_the_checks)
    assert tuple(answer) == ("pid", "queue", "state", "checks"), (
        "a wait answers with pid, queue, state and checks, not %r"
        % (tuple(answer),))
    assert answer == {"pid": 3, "queue": "disk", "state": "ready", "checks": 2}, (
        "the condition is evaluated after the enqueue too: %r" % (answer,))
    assert fixed.queues() == {"ready": (3,)}, (
        "a task taken back off the queue is not waiting: %r" % (fixed.queues(),))
    assert sleeper["state"] == "ready", (
        "the task that saw the late wakeup stays ready: %r" % (sleeper["state"],))
    assert ("block", 3, "disk") in fixed.log(), (
        "the enqueue really happened, and the ledger says so: %r" % (fixed.log(),))
    saved = fixed.run(3, _table(sleeper))
    assert saved["per_pid"] == {3: 3}, (
        "the task that re-checked its condition runs: %r" % (saved["per_pid"],))
    assert fixed.log()[-1] == ("run", 2, 3), (
        "the ledger ends with the last tick: %r" % (fixed.log()[-1],))

    # ---- the other two branches of wait_on --------------------------------

    already = _task(7)
    sched = s.Scheduler(quantum=1)
    sched.add(already)
    assert s.wait_on(sched, already, "disk", lambda task: True) == {
        "pid": 7, "queue": "disk", "state": "ready", "checks": 1}, (
        "a condition that already holds sleeps nobody")
    assert sched.queues() == {"ready": (7,)} and sched.log() == (("add", 7),), (
        "a task that never slept is never enqueued: %r" % (sched.log(),))

    waiting = _task(8)
    sched = s.Scheduler(quantum=1)
    sched.add(waiting)
    assert s.wait_on(sched, waiting, "disk", lambda task: False) == {
        "pid": 8, "queue": "disk", "state": "blocked", "checks": 2}, (
        "a condition that never holds leaves the task asleep")
    assert sched.queues() == {"ready": (), "disk": (8,)}, (
        "the sleeping task is on its queue: %r" % (sched.queues(),))
    assert sched.log() == (("add", 8), ("block", 8, "disk")), (
        "one add and one block: %r" % (sched.log(),))

    # ---- wait_on's refusals ----------------------------------------------

    message = _refuses(s.SchedError, "a wait on something that is not a scheduler",
                       lambda: s.wait_on({}, waiting, "disk", lambda task: False))
    assert "scheduler" in message, (
        "a wait needs a scheduler, got %r" % (message,))
    message = _refuses(s.SchedError, "a wait with no queue name",
                       lambda: s.wait_on(sched, waiting, "", lambda task: False))
    assert "''" in message or '""' in message, (
        "an empty queue name must be named, got %r" % (message,))
    message = _refuses(s.SchedError, "a condition that is not a callable",
                       lambda: s.wait_on(sched, waiting, "disk", 7))
    assert "7" in message, (
        "a condition that is not a callable must be named, got %r" % (message,))
    message = _refuses(s.SchedError, "a wait on a task that is not queued",
                       lambda: s.wait_on(sched, _task(9), "disk",
                                         lambda task: False))
    assert "9" in message, (
        "a task this scheduler does not hold must be named, got %r" % (message,))

    # ---- and the scheduler wrote nothing it was not asked to -------------

    keeper = _task(4, priority=2)
    limits = dict(keeper["limits"])
    sched = s.Scheduler(quantum=1)
    sched.add(keeper)
    sched.run(2, _table(keeper))
    assert keeper["priority"] == 2 and keeper["uid"] == 0, (
        "the scheduler never invents a priority or a uid: %r" % (keeper,))
    assert keeper["limits"] == limits and keeper["ticks"] == 0, (
        "the scheduler does not touch a task's limits or its own ticks: %r"
        % (keeper,))
    assert keeper["exit_status"] is None, (
        "running a task does not end it: %r" % (keeper["exit_status"],))
    assert s.Scheduler().queues() == {"ready": ()}, (
        "a fresh scheduler runs nobody: %r" % (s.Scheduler().queues(),))
    assert s.Scheduler().log() == (), "a fresh scheduler has written no ledger"

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _racing(locked=True, cpus=2, name="cnt"):
        """The classic lost update: every CPU does `load`, `add` (one), `store`.

        The CPUs are interleaved one step at a time, which is exactly what two CPUs
        do to each other; `locked` wraps each CPU's three steps in a `lock`/`unlock`
        pair, and the pairs themselves interleave.
        """
        steps = []
        for op in ("load", "add", "store"):
            for cpu in range(cpus):
                steps.append((cpu, op, ""))
        if not locked:
            return tuple(steps)
        return (
            tuple((cpu, "lock", name) for cpu in range(cpus))
            + tuple(steps)
            + tuple((cpu, "unlock", name) for cpu in range(cpus))
        )

    def _nested(name_a="a", name_b="b"):
        """One CPU that blocks twice: it defers on `a`, and re-defers on `b`."""
        return ((0, "lock", name_a), (1, "lock", name_a), (1, "lock", name_b),
                (0, "lock", name_b), (0, "unlock", name_a), (0, "unlock", name_b))

    import machine
    import stage_08 as s

    # ---- the vocabulary ---------------------------------------------------

    assert s.OPS == ("load", "add", "store", "lock", "unlock", "yield"), (
        "OPS is the frozen six in the contract's order, not %r" % (s.OPS,))
    assert issubclass(s.LockError, ValueError), (
        "LockError must be a ValueError: %r is not" % (s.LockError,))
    assert not issubclass(s.LockError, NotImplementedError), (
        "LockError must not be the not-implemented error")

    # ---- the lock, on its own ---------------------------------------------

    lock = s.Lock("a")
    assert lock.owner() is None, (
        "a fresh lock has no owner, not %r" % (lock.owner(),))
    assert lock.waiting() == (), (
        "a fresh lock has no waiters, not %r" % (lock.waiting(),))
    assert isinstance(lock.waiting(), tuple), (
        "waiting() answers a tuple, not a %s" % (type(lock.waiting()).__name__,))

    got = lock.acquire(0)
    assert list(got) == ["cpu", "acquired", "owner", "waiting"], (
        "acquire answers the four keys in order, not %r" % (list(got),))
    assert got == {"cpu": 0, "acquired": True, "owner": 0, "waiting": ()}, (
        "the first acquire takes the lock and queues nobody: %r" % (got,))
    assert lock.owner() == 0, (
        "after cpu 0 acquired, the owner is 0, not %r" % (lock.owner(),))

    got = lock.acquire(1)
    assert list(got) == ["cpu", "acquired", "owner", "waiting"], (
        "acquire answers the four keys in order, not %r" % (list(got),))
    assert got == {"cpu": 1, "acquired": False, "owner": 0, "waiting": (1,)}, (
        "a refused acquire reports the holder and the queue: %r" % (got,))
    got = lock.acquire(2)
    assert got["waiting"] == (1, 2), (
        "waiters queue in arrival order, not %r" % (got["waiting"],))
    got = lock.acquire(2)
    assert got["waiting"] == (1, 2), (
        "a CPU already in the queue is not queued twice: %r" % (got["waiting"],))
    assert got["acquired"] is False and got["owner"] == 0, (
        "cpu 2 neither owns the lock nor may take it: %r" % (got,))

    message = _refuses(s.LockError, "a recursive acquire", lambda: lock.acquire(0))
    assert "a" in message and "'a'" in message, (
        "the recursive-acquire refusal names the lock: %r" % (message,))
    assert "0" in message, (
        "the recursive-acquire refusal names the CPU: %r" % (message,))
    message = _refuses(s.LockError, "a release by a CPU that does not own the lock",
                       lambda: lock.release(1))
    assert "'a'" in message and "1" in message and "0" in message, (
        "the wrong-owner refusal names the lock and both CPUs: %r" % (message,))

    got = lock.release(0)
    assert list(got) == ["cpu", "owner", "waiting"], (
        "release answers its three keys in order, not %r" % (list(got),))
    assert got == {"cpu": 0, "owner": 1, "waiting": (2,)}, (
        "release hands the lock to the first waiter: %r" % (got,))
    assert lock.owner() == 1, (
        "the waiter owns the lock after the hand-off, not %r" % (lock.owner(),))
    assert lock.waiting() == (2,), (
        "the handed-off waiter leaves the queue: %r" % (lock.waiting(),))
    message = _refuses(s.LockError, "a release by the CPU that just lost the lock",
                       lambda: lock.release(0))
    assert "'a'" in message and "0" in message and "1" in message, (
        "the refusal names the lock and both CPUs: %r" % (message,))

    got = lock.release(1)
    assert got == {"cpu": 1, "owner": 2, "waiting": ()}, (
        "the second hand-off goes to the remaining waiter: %r" % (got,))
    got = lock.release(2)
    assert got == {"cpu": 2, "owner": None, "waiting": ()}, (
        "the last release leaves the lock free: %r" % (got,))
    assert lock.owner() is None and lock.waiting() == (), (
        "a fully released lock is free with no waiters: %r %r"
        % (lock.owner(), lock.waiting()))
    message = _refuses(s.LockError, "a release of a free lock", lambda: lock.release(2))
    assert "'a'" in message, (
        "the free-lock refusal names the lock: %r" % (message,))
    assert "free" in message, (
        "the free-lock refusal says the lock is free: %r" % (message,))

    other = s.Lock("b")
    assert other.owner() is None, "locks do not share an owner"
    assert other.acquire(0)["acquired"] is True, "a second lock is free on its own"
    assert lock.owner() is None, "taking one lock does not take another"

    message = _refuses(s.LockError, "an empty lock name", lambda: s.Lock(""))
    assert "lock name" in message, (
        "the empty-name refusal says what is wrong: %r" % (message,))
    message = _refuses(s.LockError, "a lock name that is not a str", lambda: s.Lock(7))
    assert "lock name" in message and "7" in message, (
        "the non-str-name refusal names the offender: %r" % (message,))

    # ---- serialize: the effective order of two CPUs -----------------------

    assert s.serialize(()) == {"order": (), "deferred": {}, "acquired": {}}, (
        "an empty schedule has no order, no deferrals and no takes: %r"
        % (s.serialize(()),))

    uncontended = ((0, "lock", "a"), (0, "load", ""), (0, "unlock", "a"),
                   (1, "lock", "a"), (1, "load", ""), (1, "unlock", "a"))
    got = s.serialize(uncontended)
    assert list(got) == ["order", "deferred", "acquired"], (
        "serialize answers its three keys in order, not %r" % (list(got),))
    assert got["order"] == uncontended, (
        "with nothing contended the order is the schedule, not %r"
        % (got["order"],))
    assert got["deferred"] == {0: 0, 1: 0}, (
        "nobody deferred in an uncontended schedule: %r" % (got["deferred"],))
    assert got["acquired"] == {"a": (0, 1)}, (
        "an uncontended lock records both takes in order: %r" % (got["acquired"],))

    got = s.serialize(_racing())
    assert got["order"] == (
        (0, "lock", "cnt"), (0, "load", ""), (0, "add", ""), (0, "store", ""),
        (0, "unlock", "cnt"), (1, "lock", "cnt"), (1, "load", ""),
        (1, "add", ""), (1, "store", ""), (1, "unlock", "cnt"),
    ), "cpu 1's whole tail waits for cpu 0 to release: %r" % (got["order"],)
    assert got["deferred"] == {0: 0, 1: 4}, (
        "cpu 1 deferred its lock and its three steps, cpu 0 none: %r"
        % (got["deferred"],))
    assert got["acquired"] == {"cnt": (0, 1)}, (
        "the contended lock was taken by 0 and then by 1: %r" % (got["acquired"],))

    got = s.serialize(_racing(locked=False))
    assert got["order"] == _racing(locked=False), (
        "with no lock steps nothing defers: %r" % (got["order"],))
    assert got["deferred"] == {0: 0, 1: 0}, (
        "with no lock steps nobody defers: %r" % (got["deferred"],))
    assert got["acquired"] == {}, (
        "with no lock steps nothing is taken: %r" % (got["acquired"],))

    got = s.serialize(_racing(cpus=3))
    assert got["order"] == (
        (0, "lock", "cnt"), (0, "load", ""), (0, "add", ""), (0, "store", ""),
        (0, "unlock", "cnt"), (1, "lock", "cnt"), (1, "load", ""),
        (1, "add", ""), (1, "store", ""), (1, "unlock", "cnt"),
        (2, "lock", "cnt"), (2, "load", ""), (2, "add", ""), (2, "store", ""),
        (2, "unlock", "cnt"),
    ), "the blocked CPUs replay in the order they blocked: %r" % (got["order"],)
    assert got["deferred"] == {0: 0, 1: 4, 2: 4}, (
        "cpu 1 and cpu 2 each deferred four steps: %r" % (got["deferred"],))
    assert got["acquired"] == {"cnt": (0, 1, 2)}, (
        "the three takes are recorded in order: %r" % (got["acquired"],))

    got = s.serialize(_nested())
    assert got["order"] == (
        (0, "lock", "a"), (0, "lock", "b"), (0, "unlock", "a"),
        (1, "lock", "a"), (0, "unlock", "b"), (1, "lock", "b"),
    ), "a CPU that blocks a second time keeps its remaining steps deferred: %r" % (
        got["order"],)
    assert got["deferred"] == {0: 0, 1: 2}, (
        "cpu 1 deferred exactly its two lock steps: %r" % (got["deferred"],))
    assert got["acquired"] == {"a": (0, 1), "b": (0, 1)}, (
        "both locks were taken in the same order: %r" % (got["acquired"],))

    deferred_unlock = ((0, "lock", "a"), (1, "lock", "a"), (1, "load", ""),
                       (1, "unlock", "a"), (0, "unlock", "a"))
    got = s.serialize(deferred_unlock)
    assert got["order"] == (
        (0, "lock", "a"), (0, "unlock", "a"), (1, "lock", "a"), (1, "load", ""),
        (1, "unlock", "a"),
    ), "an unlock that was itself deferred runs at the release, in its place: %r" % (
        got["order"],)
    assert got["deferred"] == {0: 0, 1: 3}, (
        "cpu 1 deferred three steps including its unlock: %r" % (got["deferred"],))
    assert got["acquired"] == {"a": (0, 1)}, (
        "the lock is taken once per CPU, in order: %r" % (got["acquired"],))

    got = s.serialize(((0, "lock", "a"), (0, "unlock", "a"), (1, "lock", "a")))
    assert got["acquired"] == {"a": (0, 1)}, (
        "a lock taken again after a release records the second take: %r"
        % (got["acquired"],))

    got = s.serialize(((0, "lock", "a"), (1, "lock", "b"), (0, "yield", "")))
    assert got["order"] == ((0, "lock", "a"), (1, "lock", "b"), (0, "yield", "")), (
        "two CPUs on two locks never defer: %r" % (got["order"],))
    assert got["acquired"] == {"a": (0,), "b": (1,)}, (
        "each lock records the CPU that took it: %r" % (got["acquired"],))

    # ---- run_schedule: the lost update ------------------------------------

    got = s.run_schedule(_racing(locked=False))
    assert list(got) == ["counter", "order", "deferred"], (
        "run_schedule answers its three keys in order, not %r" % (list(got),))
    assert got["counter"] == 1, (
        "without the lock two CPUs score one, not %r" % (got["counter"],))
    assert got["order"] == _racing(locked=False), (
        "the counter's order is the schedule when nothing defers: %r"
        % (got["order"],))
    got = s.run_schedule(_racing())
    assert got["counter"] == 2, (
        "with the lock two CPUs score two, not %r" % (got["counter"],))
    assert got["order"] == s.serialize(_racing())["order"], (
        "run_schedule orders its steps the way serialize does: %r"
        % (got["order"],))
    assert got["deferred"] == s.serialize(_racing())["deferred"], (
        "run_schedule counts the deferrals the way serialize does: %r"
        % (got["deferred"],))
    got = s.run_schedule(((0, "store", ""),))
    assert got["counter"] == 0, (
        "a store with nothing loaded writes its register's own start, zero: %r"
        % (got["counter"],))
    got = s.run_schedule(((0, "add", ""), (0, "store", "")))
    assert got["counter"] == 1, (
        "an add with nothing loaded counts up from zero: %r" % (got["counter"],))
    got = s.run_schedule(_racing(locked=False, cpus=3))
    assert got["counter"] == 1, (
        "three CPUs without the lock still score one, not %r" % (got["counter"],))
    got = s.run_schedule(_racing(cpus=3))
    assert got["counter"] == 3, (
        "three CPUs with the lock score three, not %r" % (got["counter"],))

    # ---- detect_deadlock --------------------------------------------------

    assert s.detect_deadlock(()) is None, "no waits, no deadlock"
    assert s.detect_deadlock(((0, "a", "a"),)) == (0, 0), (
        "a CPU waiting for the lock it already holds is a cycle of one: %r"
        % (s.detect_deadlock(((0, "a", "a"),)),))
    assert s.detect_deadlock(((5, "x", "x"),)) == (5, 5), (
        "the cycle of one is that CPU, twice: %r"
        % (s.detect_deadlock(((5, "x", "x"),)),))
    assert s.detect_deadlock(((0, "a", "b"), (1, "b", "a"))) == (0, 1, 0), (
        "two CPUs holding each other's lock deadlock: %r"
        % (s.detect_deadlock(((0, "a", "b"), (1, "b", "a"))),))
    assert s.detect_deadlock(((1, "b", "a"), (0, "a", "b"))) == (0, 1, 0), (
        "the cycle starts at its lowest CPU however the waits are listed: %r"
        % (s.detect_deadlock(((1, "b", "a"), (0, "a", "b"))),))
    assert s.detect_deadlock(((2, "a", "b"), (0, "b", "c"), (1, "c", "a"))) \
        == (0, 1, 2, 0), (
        "a three-CPU cycle comes back closed at the lowest: %r"
        % (s.detect_deadlock(((2, "a", "b"), (0, "b", "c"), (1, "c", "a"))),))
    assert s.detect_deadlock(((0, "a", "b"),)) is None, (
        "a wait on a lock nobody holds is not a deadlock: %r"
        % (s.detect_deadlock(((0, "a", "b"),)),))
    assert s.detect_deadlock(((0, "a", "b"), (1, "b", None))) is None, (
        "a chain that ends at a CPU doing nothing is not a deadlock: %r"
        % (s.detect_deadlock(((0, "a", "b"), (1, "b", None))),))
    assert s.detect_deadlock(((0, None, "b"), (1, "b", None))) is None, (
        "a CPU waiting on a lock it does not hold and nobody needs is not a cycle")
    assert s.detect_deadlock(((0, "a", "p"), (6, "p", "q"), (5, "q", "p"))) \
        == (5, 6, 5), (
        "a cycle reached from outside still starts at its lowest CPU: %r"
        % (s.detect_deadlock(((0, "a", "p"), (6, "p", "q"), (5, "q", "p"))),))
    assert s.detect_deadlock(((0, "a", "b"), (1, "b", "a"), (2, "c", "d"),
                              (3, "d", "c"))) == (0, 1, 0), (
        "with two cycles the first is the one from the lowest CPU: %r"
        % (s.detect_deadlock(((0, "a", "b"), (1, "b", "a"), (2, "c", "d"),
                              (3, "d", "c"))),))
    message = _refuses(s.LockError, "a wait that is not a 3-tuple",
                       lambda: s.detect_deadlock(((0, "a"),)))
    assert "(0, 'a')" in message, (
        "the malformed-wait refusal names the wait: %r" % (message,))
    _refuses(s.LockError, "a wait given as a list rather than a tuple",
             lambda: s.detect_deadlock(([0, "a", "b"],)))

    # ---- audit_holds ------------------------------------------------------

    assert s.audit_holds(()) == (), "an empty trace holds nothing"
    assert s.audit_holds(((0, "lock", "a"), (0, "load", ""), (0, "add", ""),
                          (0, "store", ""), (0, "unlock", "a"))) == (), (
        "a lock held across a load, an add and a store is doing its job")
    assert s.audit_holds(((0, "lock", "a"), (0, "load", ""), (0, "yield", ""),
                          (0, "unlock", "a"))) == ((0, "a"),), (
        "a lock held across a yield is the finding: %r"
        % (s.audit_holds(((0, "lock", "a"), (0, "load", ""), (0, "yield", ""),
                          (0, "unlock", "a"))),))
    assert s.audit_holds(((0, "lock", "a"), (0, "lock", "b"), (0, "yield", ""))) \
        == ((0, "a"), (0, "b")), (
        "every lock a yielding CPU holds is a finding, in acquisition order: %r"
        % (s.audit_holds(((0, "lock", "a"), (0, "lock", "b"), (0, "yield", ""))),))
    assert s.audit_holds(((0, "lock", "a"), (1, "lock", "b"))) == ((0, "a"), (1, "b")), (
        "a lock still held at the end of the trace is a finding: %r"
        % (s.audit_holds(((0, "lock", "a"), (1, "lock", "b"))),))
    assert s.audit_holds(((0, "lock", "a"), (0, "yield", ""), (0, "yield", ""))) \
        == ((0, "a"),), (
        "the same lock held across two yields is one finding, not two: %r"
        % (s.audit_holds(((0, "lock", "a"), (0, "yield", ""), (0, "yield", ""))),))
    assert s.audit_holds(((0, "lock", "a"), (0, "yield", ""))) == ((0, "a"),), (
        "a lock held across a yield and never released is one finding: %r"
        % (s.audit_holds(((0, "lock", "a"), (0, "yield", ""))),))
    assert s.audit_holds(((0, "lock", "a"), (0, "yield", ""), (0, "unlock", "a"),
                          (1, "lock", "b"), (1, "yield", ""))) == ((0, "a"), (1, "b")), (
        "findings come in trace order: %r"
        % (s.audit_holds(((0, "lock", "a"), (0, "yield", ""), (0, "unlock", "a"),
                          (1, "lock", "b"), (1, "yield", ""))),))
    assert s.audit_holds(((0, "lock", "a"), (0, "unlock", "a"), (1, "lock", "b"))) \
        == ((1, "b"),), (
        "a lock given back is not a finding at the end of the trace: %r"
        % (s.audit_holds(((0, "lock", "a"), (0, "unlock", "a"), (1, "lock", "b"))),))
    assert s.audit_holds(((0, "yield", ""), (1, "load", ""))) == (), (
        "a yield by a CPU that holds nothing is not a finding")
    message = _refuses(s.LockError, "an unlock by a CPU that holds nothing",
                       lambda: s.audit_holds(((0, "lock", "a"), (1, "unlock", "a"))))
    assert "1" in message and "'a'" in message, (
        "the unlock refusal names the CPU and the lock: %r" % (message,))
    _refuses(s.LockError, "a recursive lock in a trace",
             lambda: s.audit_holds(((0, "lock", "a"), (0, "lock", "a"))))
    message = _refuses(s.LockError, "an empty lock name in a trace",
                       lambda: s.audit_holds(((0, "lock", ""),)))
    assert "''" in message, (
        "the trace's empty lock name is named: %r" % (message,))
    _refuses(s.LockError, "a lock name that is not a str in a trace",
             lambda: s.audit_holds(((0, "unlock", 7),)))

    # ---- the step gate, shared by every schedule function -----------------

    for bad in ((0, "load"), (0, "load", "", 1), [0, "load", ""], "load"):
        message = _refuses(s.LockError, "a step that is not a 3-tuple: %r" % (bad,),
                           lambda bad=bad: s.serialize((bad,)))
        assert repr(bad) in message, (
            "the malformed-step refusal names the step %r: %r" % (bad, message))
        _refuses(s.LockError, "run_schedule on a step that is not a 3-tuple",
                 lambda bad=bad: s.run_schedule((bad,)))

    message = _refuses(s.LockError, "an op outside OPS",
                       lambda: s.serialize(((0, "lck", ""),)))
    assert "'lck'" in message, (
        "the unknown-op refusal names the op: %r" % (message,))
    assert repr(machine._near("lck", s.OPS)) in message, (
        "the suggestion for 'lck' is the world's own: %r wants %r"
        % (message, machine._near("lck", s.OPS)))
    message = _refuses(s.LockError, "an op nowhere near one of the six",
                       lambda: s.serialize(((0, "spin", ""),)))
    assert machine._near("spin", s.OPS) is None, (
        "'spin' is not within distance 2 of an op; the fixture is wrong")
    assert "did you mean" not in message, (
        "a far op earns no suggestion: %r" % (message,))
    _refuses(s.LockError, "run_schedule on an op outside OPS",
             lambda: s.run_schedule(((0, "lck", ""),)))
    _refuses(s.LockError, "audit_holds on an op outside OPS",
             lambda: s.audit_holds(((0, "lck", ""),)))

    message = _refuses(s.LockError, "a lock step with an empty name",
                       lambda: s.serialize(((0, "lock", ""),)))
    assert "''" in message, (
        "the empty-lock-name refusal names the empty name: %r" % (message,))
    message = _refuses(s.LockError, "a lock step with a name that is not a str",
                       lambda: s.serialize(((0, "lock", 7),)))
    assert "7" in message, (
        "the non-str lock name is named: %r" % (message,))
    _refuses(s.LockError, "an unlock step with an empty name",
             lambda: s.serialize(((0, "unlock", ""),)))
    for ok in ((0, "load", 7), (0, "add", None), (0, "store", ""),
               (0, "yield", ""), (0, "lock", "a")):
        got = s.serialize((ok,))
        assert got["order"] == (ok,), (
            "a legal step runs as written: %r gave %r" % (ok, got["order"]))
    assert s.serialize(((0, "load", None),))["acquired"] == {}, (
        "a load takes nothing, whatever its name field holds")

    # ---- and the world is where it was ------------------------------------

    assert machine._near("lck", s.OPS) == "lock", (
        "the world's suggestion rule changed while the stage ran")
    assert machine.PAGE_SIZE == 4096 and machine.IRQS == (32,), (
        "the machine's own vocabulary changed while the stage ran")

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    SECTOR = 512

    USABLE = 508

    CHECKSUM_BYTES = 4

    NAME_BYTES = 24

    ENTRY_BYTES = 2 + NAME_BYTES

    MAX_ENTRIES = USABLE // ENTRY_BYTES

    MAGIC = 0x4F534653

    FORMAT_VERSION = 1

    ROOT_SECTOR = 2

    def _sum(data, index):
        total = index & 0xFFFFFFFF
        for byte in bytes(data):
            total = (total * 31 + byte) & 0xFFFFFFFF
        return total

    def _seal(payload, index):
        return bytes(payload) + _sum(payload, index).to_bytes(CHECKSUM_BYTES, "big")

    def _be(payload, offset, width, value):
        payload[offset:offset + width] = value.to_bytes(width, "big")

    def _inode_image(geom, ino, kind, mode, uid, size, blocks):
        """A whole inode sector, written by the check's own encoder."""
        payload = bytearray(USABLE)
        payload[0] = {"free": 0, "file": 1, "dir": 2}[kind]
        _be(payload, 1, 2, mode)
        _be(payload, 3, 2, uid)
        _be(payload, 5, 4, size)
        payload[9] = len(blocks)
        for slot, block in enumerate(blocks):
            _be(payload, 10 + 2 * slot, 2, block)
        return _seal(payload, geom["inodes_start"] + ino)

    def _dir_image(geom, ino, pairs):
        payload = bytearray(USABLE)
        for slot, (name, child) in enumerate(pairs):
            offset = slot * ENTRY_BYTES
            _be(payload, offset, 2, child)
            raw = name.encode("utf-8")
            payload[offset + 2:offset + 2 + len(raw)] = raw
        return _seal(payload, geom["dir_start"] + ino)

    def _map_image(geom, bitmap):
        payload = bytearray(USABLE)
        payload[:len(bitmap)] = bitmap
        return _seal(payload, geom["free_map_sector"])

    def _super_image(geom, fallback):
        payload = bytearray(USABLE)
        fields = (("magic", 0, 4), ("version", 4, 4), ("inodes_start", 8, 2),
                  ("n_inodes", 10, 2), ("data_start", 12, 2), ("n_data", 14, 2),
                  ("root_ino", 16, 2), ("free_map_sector", 18, 2))
        for key, offset, width in fields:
            _be(payload, offset, width, fallback.get(key, geom[key]))
        return _seal(payload, 0)

    def _copy_image(source, target, skip=()):
        """Every durable sector of `source` into `target`, except the skipped ones."""
        for index in range(source.sectors):
            if index not in skip:
                target.write(index, source.read(index))
        target.barrier()

    def _writes(disk):
        return tuple(entry[1] for entry in disk.log() if entry[0] == "write")

    def _bitmap(disk, geom):
        return bytearray(disk.read(geom["free_map_sector"])[:geom["n_data"]])

    def _full(stage, devices, userland):
        """A card holding a filesystem whose /etc has no room left."""
        disk = devices.Disk(sectors=200)
        stage.format_disk(disk, userland.files(), 40)
        fs = stage.mount(disk)["fs"]
        for index in range(MAX_ENTRIES - 1):
            stage.create(fs, "/etc/f%02d" % (index,), "file", 0o644, 0)
        return fs

    import devices
    import stage_09 as s
    import userland

    files = userland.files()
    geom = s.layout(files, 8, 64)

    # ---- the constants and the refusal family -----------------------------

    assert s.MAGIC == 0x4F534653, "MAGIC is %r, not OSFS" % (s.MAGIC,)
    assert s.FORMAT_VERSION == 1, "the format is version 1, not %r" % (s.FORMAT_VERSION,)
    assert s.NAMES_MAX == 24, "a name may be 24 bytes, not %r" % (s.NAMES_MAX,)
    assert s.SECTOR == devices.SECTOR == 512, (
        "a sector is %r bytes and the device's is %r" % (s.SECTOR, devices.SECTOR))
    assert issubclass(s.FsError, ValueError), (
        "FsError is not a ValueError: %r" % (s.FsError,))
    assert "bad_checksum" in s.PROBLEMS, "the vocabulary names a failed checksum"
    assert "block_shared" in s.PROBLEMS and "size_mismatch" in s.PROBLEMS, (
        "the problem vocabulary is missing a word fsck must be able to say: %r"
        % (s.PROBLEMS,))
    assert list(s.PROBLEMS) == sorted(set(s.PROBLEMS)), (
        "the problem vocabulary has a duplicate or is out of order: %r" % (s.PROBLEMS,))

    # ---- the checksum, and the index really mixed in ----------------------

    assert s.checksum(b"", 0) == 0, "the sum of nothing at sector 0 is 0"
    assert s.checksum(b"\x01", 0) == 1, (
        "one byte 1 sums to 1 at sector 0, not %r" % (s.checksum(b"\x01", 0),))
    assert s.checksum(b"\x02", 0) == 2, (
        "the sum is not a sum: %r" % (s.checksum(b"\x02", 0),))
    assert s.checksum(b"\x01", 1) == 32, (
        "the sector index is not mixed in first: %r" % (s.checksum(b"\x01", 1),))
    assert s.checksum(bytes(USABLE), 0) != s.checksum(bytes(USABLE), 5), (
        "two sectors with the same bytes and different indices share a checksum")
    _refuses(s.FsError, "checksum of a negative sector",
             lambda: s.checksum(b"", -1))
    _refuses(s.FsError, "checksum of a boolean sector",
             lambda: s.checksum(b"", True))

    # ---- layout: the geometry, exactly ------------------------------------

    assert tuple(geom) == ("magic", "version", "sector", "sectors", "inodes_start",
                           "n_inodes", "dir_start", "n_dirs", "data_start",
                           "n_data", "root_ino", "free_map_sector"), (
        "layout's keys are %r, not the twelve the format names" % (tuple(geom),))
    assert geom == s.layout(), (
        "the frozen defaults are not the course's own tree: %r" % (s.layout(),))
    assert geom["magic"] == s.MAGIC and geom["version"] == 1, (
        "layout's magic and version are %r" % (geom,))
    assert geom["sector"] == 512 and geom["sectors"] == 64, (
        "layout's sector size is wrong: %r" % (geom,))
    assert geom["inodes_start"] == 2 and geom["free_map_sector"] == 1, (
        "the inode table starts at sector 2 and the map is sector 1: %r" % (geom,))
    assert geom["n_inodes"] == 9, (
        "nine entries need nine inodes even when eight were asked for, not %d"
        % (geom["n_inodes"],))
    assert geom["dir_start"] == 11 and geom["n_dirs"] == 9, (
        "one directory sector per inode slot after the table: %r" % (geom,))
    assert geom["data_start"] == 20 and geom["n_data"] == 44, (
        "the data region runs from 20 to 63: %r" % (geom,))
    assert geom["root_ino"] == 0, "the root is inode 0, not %r" % (geom["root_ino"],)
    assert geom["dir_start"] == geom["inodes_start"] + geom["n_inodes"], (
        "the directories do not follow the inode table: %r" % (geom,))
    assert geom["data_start"] == geom["dir_start"] + geom["n_dirs"], (
        "the data region does not follow the directories: %r" % (geom,))
    assert geom["data_start"] + geom["n_data"] == geom["sectors"], (
        "the regions do not reach the end of the disk: %r" % (geom,))

    bigger = s.layout(files, 16, 64)
    assert bigger["n_inodes"] == 16, (
        "a caller asking for sixteen inodes gets %d" % (bigger["n_inodes"],))
    assert bigger["dir_start"] == 18 and bigger["data_start"] == 34, (
        "the regions do not follow a table of sixteen: %r" % (bigger,))
    assert bigger["n_data"] == 30, (
        "a table of sixteen leaves thirty data sectors: %r" % (bigger,))

    small = s.layout([("/", "dir", 0o755, 0, b""),
                      ("/one", "file", 0o644, 0, b"x")], 4, 20)
    assert small["n_inodes"] == 4 and small["data_start"] == 10, (
        "a hand-built tree lays out its own table: %r" % (small,))
    assert small["n_data"] == 10, "the data region is what is left: %r" % (small,)

    caller = [("/", "dir", 0o755, 0, b""), ("/a", "file", 0o644, 0, b"hi")]
    snapshot = [(path, kind, mode, uid, bytes(content))
                for path, kind, mode, uid, content in caller]
    s.layout(caller, 4, 20)
    assert caller == snapshot, (
        "layout edited the caller's own file list: %r" % (caller,))

    _refuses(s.FsError, "layout of a table of no inodes",
             lambda: s.layout(files, 0, 64))
    _refuses(s.FsError, "layout of a boolean table",
             lambda: s.layout(files, True, 64))
    _refuses(s.FsError, "layout on a disk of no sectors",
             lambda: s.layout(files, 8, 0))
    _refuses(s.FsError, "layout on a boolean disk",
             lambda: s.layout(files, 8, False))
    message = _refuses(s.FsError, "layout of a table with no room on the disk",
                       lambda: s.layout(files, 400, 64))
    assert "400" in message, (
        "a table that does not fit must name the table, got %r" % (message,))
    message = _refuses(s.FsError, "layout of a tree that is not a list",
                       lambda: s.layout("tree", 8, 64))
    assert "list" in message, (
        "a tree that is not a list must be refused for what it is, got %r"
        % (message,))
    message = _refuses(s.FsError, "layout of an empty tree",
                       lambda: s.layout((), 8, 64))
    assert "root" in message, (
        "an empty tree has no root, got %r" % (message,))
    message = _refuses(s.FsError, "layout of a relative path",
                       lambda: s.layout([("/", "dir", 0o755, 0, b""),
                                         ("etc", "dir", 0o755, 0, b"")], 8, 64))
    assert "etc" in message, (
        "a relative path must be named, got %r" % (message,))
    message = _refuses(s.FsError, "layout of a duplicate path",
                       lambda: s.layout([("/", "dir", 0o755, 0, b""),
                                         ("/a", "file", 0o644, 0, b"x"),
                                         ("/a", "file", 0o644, 0, b"y")], 8, 64))
    assert "/a" in message, "a duplicate path must be named, got %r" % (message,)
    message = _refuses(s.FsError, "layout of a child before its parent",
                       lambda: s.layout([("/", "dir", 0o755, 0, b""),
                                         ("/etc/motd", "file", 0o644, 0, b"x"),
                                         ("/etc", "dir", 0o755, 0, b"")], 8, 64))
    assert "/etc" in message, (
        "a child before its parent must be refused naming the parent, got %r"
        % (message,))
    message = _refuses(s.FsError, "layout of an unknown kind",
                       lambda: s.layout([("/", "dir", 0o755, 0, b""),
                                         ("/a", "link", 0o777, 0, b"x")], 8, 64))
    assert "link" in message, "an unknown kind must be named, got %r" % (message,)
    message = _refuses(s.FsError, "layout of a directory with content",
                       lambda: s.layout([("/", "dir", 0o755, 0, b""),
                                         ("/d", "dir", 0o755, 0, b"x")], 8, 64))
    assert "/d" in message, "a directory with content must be named, got %r" % (message,)
    long_name = "x" * 30
    message = _refuses(s.FsError, "layout of an over-long name",
                       lambda: s.layout([("/", "dir", 0o755, 0, b""),
                                         ("/" + long_name, "file", 0o644, 0, b"")],
                                        8, 64))
    assert long_name in message and "24" in message, (
        "an over-long name must be named, with the limit, got %r" % (message,))
    message = _refuses(s.FsError, "layout of a tree whose root is not a directory",
                       lambda: s.layout([("/", "file", 0o644, 0, b"x")], 8, 64))
    assert "/" in message, (
        "a file for a root must be named, got %r" % (message,))
    _refuses(s.FsError, "layout of a file too big for an inode",
             lambda: s.layout([("/", "dir", 0o755, 0, b""),
                               ("/big", "file", 0o644, 0, bytes(24 * 508 + 1))],
                              8, 64))
    _refuses(s.FsError, "layout of an entry that is not an entry",
             lambda: s.layout([("/", "dir", 0o755, 0, b""), "/etc"], 8, 64))
    message = _refuses(s.FsError, "layout of a tree the data region cannot hold",
                       lambda: s.layout([("/", "dir", 0o755, 0, b""),
                                         ("/a", "file", 0o644, 0, b"x" * 508),
                                         ("/b", "file", 0o644, 0, b"x" * 508)],
                                        2, 9))
    assert "2" in message, (
        "a tree too big for the data region must name how many sectors it needs, "
        "got %r" % (message,))

    # ---- format_disk: what layout promised, in the order that matters ------

    disk = devices.Disk(sectors=64)
    before = disk.durable_sha()
    wrote = s.format_disk(disk, files, 8)
    assert wrote == geom, (
        "format_disk returned %r and layout said %r" % (wrote, geom))
    assert disk.durable_sha() != before, "format_disk wrote nothing"
    assert disk.pending() == 0, (
        "format_disk left %d writes unbarriered" % (disk.pending(),))

    kind_of = {index: ("data" if geom["data_start"] <= index < geom["sectors"]
                       else "inode" if geom["inodes_start"] <= index < geom["dir_start"]
                       else "dir" if geom["dir_start"] <= index < geom["data_start"]
                       else "map" if index == geom["free_map_sector"]
                       else "super" if index == 0 else "?")
               for index in _writes(disk)}
    log = disk.log()
    assert log[0][0] == "write", "format starts with a write: %r" % (log[0],)
    assert log[-1] == ("barrier", 1) and log[-2] == ("write", 0), (
        "the superblock is written last and barriered: the tail is %r"
        % (log[-2:],))
    assert _writes(disk).count(0) == 1, (
        "the superblock is written exactly once: %r" % (log,))
    assert sum(1 for entry in log if entry[0] == "barrier") == 5, (
        "the format has five barriers, and has %d"
        % (sum(1 for entry in log if entry[0] == "barrier"),))
    phases = []
    for entry in log:
        if entry[0] == "barrier":
            phases.append("barrier")
        elif not phases or phases[-1] != kind_of[entry[1]]:
            phases.append(kind_of[entry[1]])
    assert phases == ["data", "barrier", "dir", "barrier", "inode", "barrier",
                      "map", "barrier", "super", "barrier"], (
        "the write order is not data, dirs, inodes, map, superblock, each "
        "barriered: %r" % (phases,))
    writes = _writes(disk)
    assert len(writes) == len(set(writes)), (
        "a sector is written twice during a format: %r" % (writes,))
    owned = (set(range(0, geom["dir_start"]))
             | {geom["dir_start"] + ino for ino in (0, 1, 3, 5, 6, 8)}
             | {20, 21, 22})
    assert set(writes) == owned, (
        "the format wrote %r and owns %r" % (sorted(set(writes)), sorted(owned)))
    assert s.fsck(disk) == {"ok": True, "problems": ()}, (
        "a freshly formatted disk is not consistent: %r" % (s.fsck(disk),))

    torn = devices.Disk(sectors=64)
    _copy_image(disk, torn, skip=(0,))
    message = _refuses(s.FsError, "mount of an image with no superblock",
                       lambda: s.mount(torn))
    assert "0" in message, (
        "a mount with no superblock must name the sector it read, got %r" % (message,))

    _refuses(s.FsError, "format of a disk with the wrong sector size",
             lambda: s.format_disk(devices.Disk(sectors=64, sector=256), files, 8))
    message = _refuses(s.FsError, "mount of a disk with the wrong sector size",
                       lambda: s.mount(devices.Disk(sectors=64, sector=256)))
    assert "256" in message, (
        "a sector that is not the format's must be refused naming its size, got "
        "%r" % (message,))

    # ---- mount ------------------------------------------------------------

    mounted = s.mount(disk)
    assert tuple(mounted) == ("super", "fs"), (
        "mount answers with super and fs, and answered %r" % (tuple(mounted),))
    assert mounted["super"] == geom, (
        "mount's superblock is %r and layout said %r" % (mounted["super"], geom))
    fs = mounted["fs"]
    assert tuple(fs) == ("disk", "super", "root_ino"), (
        "the mounted fs is %r and is not disk, super, root_ino" % (tuple(fs),))
    assert fs["disk"] is disk and fs["root_ino"] == 0, (
        "the mounted fs does not carry the disk and the root: %r" % (fs,))

    blank = devices.Disk(sectors=64)
    message = _refuses(s.FsError, "mount of a disk with no superblock",
                       lambda: s.mount(blank))
    assert "magic" in message, (
        "a disk with no OSFS must be refused naming the magic, got %r" % (message,))
    bad_magic = devices.Disk(sectors=64)
    _copy_image(disk, bad_magic)
    bad_magic.write(0, bytes(512))
    bad_magic.barrier()
    message = _refuses(s.FsError, "mount of a filesystem with foreign magic",
                       lambda: s.mount(bad_magic))
    assert "magic" in message and "0x4f534653" in message.lower(), (
        "a foreign magic must name both what arrived and OSFS, got %r" % (message,))
    bad_version = devices.Disk(sectors=64)
    _copy_image(disk, bad_version)
    bad_version.write(0, _super_image(geom, {"version": 2}))
    bad_version.barrier()
    message = _refuses(s.FsError, "mount of a version this kernel does not know",
                       lambda: s.mount(bad_version))
    assert "2" in message and "1" in message, (
        "an unknown version must name both versions, got %r" % (message,))
    torn_super = devices.Disk(sectors=64)
    _copy_image(disk, torn_super)
    torn_super.write(0, bytes(512))
    torn_super.power_fail(tear=True)
    message = _refuses(s.FsError, "mount of a torn superblock",
                       lambda: s.mount(torn_super))
    assert "checksum" in message and "0" in message, (
        "a torn superblock must be refused naming the checksum and the sector, "
        "got %r" % (message,))
    bad_geometry = devices.Disk(sectors=64)
    _copy_image(disk, bad_geometry)
    bad_geometry.write(0, _super_image(geom, {"n_data": 60}))
    bad_geometry.barrier()
    _refuses(s.FsError, "mount of a geometry that does not fit the disk",
             lambda: s.mount(bad_geometry))
    zero_table = devices.Disk(sectors=64)
    _copy_image(disk, zero_table)
    zero_table.write(0, _super_image(geom, {"inodes_start": 0, "root_ino": 2}))
    zero_table.barrier()
    message = _refuses(s.FsError, "mount of a table that starts at sector 0",
                       lambda: s.mount(zero_table))
    assert "geometry" in message, (
        "a table where the superblock lives must be refused as a geometry that "
        "does not fit, got %r" % (message,))
    root_file = devices.Disk(sectors=64)
    _copy_image(disk, root_file)
    root_file.write(ROOT_SECTOR, _inode_image(geom, 0, "file", 0o755, 0, 8, ()))
    root_file.barrier()
    message = _refuses(s.FsError, "mount of a root that is not a directory",
                       lambda: s.mount(root_file))
    assert "0" in message and "file" in message, (
        "a root that is a file must be refused naming the inode and what it is, "
        "got %r" % (message,))
    spare = devices.Disk(sectors=64)
    default_geoms = s.format_disk(spare)
    assert default_geoms == geom, (
        "format_disk's frozen defaults are not the course's own tree: %r"
        % (default_geoms,))

    hand = devices.Disk(sectors=64)
    hand_files = [("/", "dir", 0o755, 0, b""),
                  ("/big", "file", 0o644, 0, b"0123456789" * 100)]
    s.format_disk(hand, hand_files, 8)
    hand_fs = s.mount(hand)["fs"]
    hand_big = s.lookup(hand_fs, "/big")
    assert hand_big["ino"] == 1 and hand_big["size"] == 1000, (
        "a hand-built tree's file is inode 1, of 1000 bytes: %r" % (hand_big,))
    hand_geom = s.layout(hand_files, 8, 64)
    assert hand_big["blocks"] == (hand_geom["data_start"],
                                  hand_geom["data_start"] + 1), (
        "1000 bytes are the first two data sectors: %r" % (hand_big,))
    assert s.read_file(hand_fs, 1) == b"0123456789" * 100, (
        "a file across two sectors did not survive the format")
    assert s.fsck(hand)["ok"], "a hand-built tree is not consistent"

    # ---- a disk with room, for everything that writes ---------------------

    room = devices.Disk(sectors=64)
    room_geom = s.format_disk(room, [("/", "dir", 0o755, 0, b""),
                                     ("/f", "file", 0o644, 0, b"")], 16)
    room_fs = s.mount(room)["fs"]
    assert room_geom["data_start"] == 34 and room_geom["data_start"] == bigger["data_start"], (
        "a two-entry tree on a table of sixteen has the same regions: %r"
        % (room_geom,))

    # ---- lookup -----------------------------------------------------------

    assert tuple(s.lookup(fs, "/")) == ("ino", "kind", "mode", "uid", "size",
                                        "blocks"), (
        "an inode's keys are %r" % (tuple(s.lookup(fs, "/")),))
    root = s.lookup(fs, "/")
    assert root["ino"] == 0 and root["kind"] == "dir" and root["mode"] == 0o755, (
        "the root is inode 0, a 0o755 directory: %r" % (root,))
    motd = s.lookup(fs, "/etc/motd")
    assert motd["ino"] == 2 and motd["kind"] == "file", (
        "/etc/motd is inode 2, a file: %r" % (motd,))
    assert motd["size"] == 8, (
        "/etc/motd is eight bytes, and lookup says %r" % (motd["size"],))
    assert s.lookup(fs, "/root/secret")["ino"] == 4, (
        "/root/secret is inode 4: %r" % (s.lookup(fs, "/root/secret"),))
    assert s.lookup(fs, "/etc")["uid"] == 0 and s.lookup(fs, "/home/user")["uid"] == 1001, (
        "lookup does not carry the inode's uid: %r" % (s.lookup(fs, "/home/user"),))
    assert s.lookup(fs, "/home/user/notes")["ino"] == 7, (
        "/home/user/notes is inode 7: %r" % (s.lookup(fs, "/home/user/notes"),))
    assert s.lookup(fs, "/tmp")["kind"] == "dir", "/tmp is a directory"
    assert s.lookup(fs, "/tmp")["blocks"] == (geom["dir_start"] + 8,), (
        "a directory's block is its own directory sector: %r"
        % (s.lookup(fs, "/tmp"),))
    assert s.lookup(fs, "/")["size"] == 0, "a directory has no size"
    assert s.lookup(fs, "/etc/./motd")["ino"] == 2, (
        "`.` is skipped, and /etc/./motd is still /etc/motd")
    assert s.lookup(fs, "/etc/../etc/motd")["ino"] == 2, (
        "`..` pops the walk, and /etc/../etc/motd is still /etc/motd")
    assert s.lookup(fs, "/home/user/../../etc/motd")["ino"] == 2, (
        "two pops reach the root, and /home/user/../../etc/motd is /etc/motd")
    assert s.lookup(fs, "/../../etc/motd")["ino"] == 2, (
        "`..` at the root stays at the root")
    assert s.lookup(fs, "/etc/motd/../motd")["ino"] == 2, (
        "`..` pops the walk even after a file")
    assert s.lookup(fs, "//etc//motd")["ino"] == 2, (
        "an empty component is skipped, and //etc//motd is /etc/motd")
    first = s.lookup(fs, "/etc")
    first["ino"] = 99
    assert s.lookup(fs, "/etc")["ino"] == 1, (
        "lookup hands back the caller's own dict, not a fresh one")

    message = _refuses(s.FsError, "lookup of a relative path",
                       lambda: s.lookup(fs, "etc/motd"))
    assert "etc/motd" in message, (
        "a relative path must be named, got %r" % (message,))
    message = _refuses(s.FsError, "lookup of an empty path",
                       lambda: s.lookup(fs, ""))
    assert "non-empty" in message and "''" in message, (
        "an empty path must be refused as empty, naming it, got %r" % (message,))
    message = _refuses(s.FsError, "lookup of a path through nothing",
                       lambda: s.lookup(fs, "/nope/../etc"))
    assert "nope" in message, (
        "a path that walks through a name that is not there must be refused for "
        "that name, got %r" % (message,))
    message = _refuses(s.FsError, "lookup of a missing name",
                       lambda: s.lookup(fs, "/etc/motdd"))
    assert "motdd" in message and "/etc" in message, (
        "a missing name must name the component and the directory, got %r"
        % (message,))
    assert "motd" in message.replace("motdd", ""), (
        "a name one edit from a real one must be told what it probably meant, "
        "got %r" % (message,))
    message = _refuses(s.FsError, "lookup of a name nowhere near a real one",
                       lambda: s.lookup(fs, "/zzzzzz"))
    assert "did you mean" not in message, (
        "a name that is not close to any real one must not suggest one: %r"
        % (message,))
    message = _refuses(s.FsError, "lookup of a file in the middle of a path",
                       lambda: s.lookup(fs, "/etc/motd/x"))
    assert "motd" in message and "file" in message, (
        "a file in the middle of a path must be named, with what it is, got %r"
        % (message,))
    message = _refuses(s.FsError, "lookup of an over-long name",
                       lambda: s.lookup(fs, "/" + long_name))
    assert long_name in message and "24" in message, (
        "an over-long name must be named, with the limit, got %r" % (message,))

    # ---- read_file --------------------------------------------------------

    assert s.read_file(fs, 2) == b"welcome\n", (
        "/etc/motd says %r" % (s.read_file(fs, 2),))
    assert s.read_file(fs, 4) == b"not for you\n", (
        "/root/secret says %r" % (s.read_file(fs, 4),))
    assert s.read_file(fs, 7) == b"mine\n", (
        "/home/user/notes says %r" % (s.read_file(fs, 7),))
    message = _refuses(s.FsError, "read_file of a directory",
                       lambda: s.read_file(fs, 0))
    assert "0" in message and "dir" in message, (
        "reading a directory must name the inode and what it is, got %r"
        % (message,))
    message = _refuses(s.FsError, "read_file of a free inode",
                       lambda: s.read_file(room_fs, 15))
    assert "15" in message and "free" in message, (
        "reading a free inode must name it and say it is free, got %r" % (message,))
    _refuses(s.FsError, "read_file of an inode outside the table",
             lambda: s.read_file(fs, 99))

    # ---- write_file: data, a barrier, the inode ---------------------------

    mark = len(room.log())
    wrote = s.write_file(room_fs, 1, b"hello" * 300)
    log = room.log()[mark:]
    assert tuple(wrote) == ("ino", "size", "blocks", "durable"), (
        "write_file's keys are %r" % (tuple(wrote),))
    assert wrote["ino"] == 1 and wrote["size"] == 1500, (
        "write_file reported %r for 1500 bytes in inode 1" % (wrote,))
    assert wrote["blocks"] == (34, 35, 36), (
        "1500 bytes are three sectors from the data start: %r" % (wrote,))
    assert wrote["durable"] == 5, (
        "three data sectors, a map and an inode are five durable sectors, not %r"
        % (wrote["durable"],))
    assert s.read_file(room_fs, 1) == b"hello" * 300, (
        "a file written across three sectors does not read back")
    assert s.fsck(room) == {"ok": True, "problems": ()}, (
        "a disk this stage wrote is not consistent: %r" % (s.fsck(room),))
    inode_write = log.index(("write", room_geom["inodes_start"] + 1))
    map_write = log.index(("write", room_geom["free_map_sector"]))
    data_write = log.index(("write", 36))
    assert data_write < inode_write and map_write < inode_write, (
        "the data and the free map are written before the inode: %r" % (log,))
    assert any(entry[0] == "barrier"
               for entry in log[data_write:inode_write]), (
        "a barrier separates the data from the inode: %r" % (log,))
    assert log[-1] == ("barrier", 1), (
        "write_file barriers the inode it wrote: %r" % (log[-1:],))
    shape = [entry[0] for entry in log if entry[0] in ("write", "barrier")]
    assert shape == ["write", "write", "write", "write", "barrier", "write",
                     "barrier"], (
        "write_file writes three data sectors and the map, barriers, writes the "
        "inode, barriers: %r" % (log,))
    bitmap = _bitmap(room, room_geom)
    assert bitmap[0] == 0 and bitmap[1] == 0 and bitmap[2] == 0, (
        "the blocks a file claims are not marked used: %r" % (bitmap[:4],))
    assert bitmap[3] == 1, (
        "the block after the file is not left free: %r" % (bitmap[:4],))
    assert room.pending() == 0, "write_file left something buffered"

    s.create(room_fs, "/g", "file", 0o644, 0)
    other = s.write_file(room_fs, 2, b"x" * 900)
    assert other["blocks"] == (37, 38), (
        "a second file takes the next free blocks: %r" % (other,))
    assert not set(wrote["blocks"]) & set(other["blocks"]), (
        "two files were given the same block: %r and %r"
        % (wrote["blocks"], other["blocks"]))
    assert s.read_file(room_fs, 2) == b"x" * 900, "the second file does not read back"
    assert s.fsck(room)["ok"], "two files leave an inconsistent disk"
    freed = s.write_file(room_fs, 2, b"")
    assert freed["blocks"] == (), (
        "an empty file claims no sector: %r" % (freed,))
    assert freed["size"] == 0 and freed["durable"] == 2, (
        "an empty file writes the map and the inode, and no data: %r" % (freed,))
    assert s.read_file(room_fs, 2) == b"", "an empty file reads back as nothing"
    bitmap = _bitmap(room, room_geom)
    assert bitmap[3] == 1 and bitmap[4] == 1, (
        "the blocks a rewritten file gave up are not free again: %r"
        % (bitmap[:6],))
    assert s.fsck(room)["ok"], "a rewritten file leaves an inconsistent disk"

    message = _refuses(s.FsError, "write_file of a directory",
                       lambda: s.write_file(room_fs, 0, b"x"))
    assert "0" in message and "dir" in message, (
        "writing a directory must name it and what it is, got %r" % (message,))
    message = _refuses(s.FsError, "write_file of a free inode",
                       lambda: s.write_file(room_fs, 15, b"x"))
    assert "15" in message and "free" in message, (
        "writing a free inode must name it and say it is free, got %r" % (message,))
    _refuses(s.FsError, "write_file of something that is not bytes",
             lambda: s.write_file(room_fs, 1, "text"))
    message = _refuses(s.FsError, "write_file of a file too big for an inode",
                       lambda: s.write_file(room_fs, 1, bytes(24 * 508 + 1)))
    assert "24" in message, (
        "a file past an inode's block count must name the limit, got %r" % (message,))

    tiny = devices.Disk(sectors=30)
    s.format_disk(tiny, files, 8)
    tiny_fs = s.mount(tiny)["fs"]
    assert tiny_fs["super"]["n_data"] == 10, (
        "a thirty-sector disk has ten data sectors: %r" % (tiny_fs["super"],))
    message = _refuses(s.FsError, "write_file of a file too big for the disk",
                       lambda: s.write_file(tiny_fs, 2, bytes(12 * 508)))
    assert "12" in message, (
        "a file past the data region must name how many sectors it needs, got %r"
        % (message,))

    # ---- create: the inode before the entry ------------------------------

    fresh = devices.Disk(sectors=64)
    s.format_disk(fresh, files, 16)
    fresh_fs = s.mount(fresh)["fs"]
    mark = len(fresh.log())
    made = s.create(fresh_fs, "/etc/hosts", "file", 0o644, 0)
    log = fresh.log()[mark:]
    assert tuple(made) == ("ino", "kind", "mode", "uid", "size", "blocks"), (
        "create's answer is %r" % (tuple(made),))
    assert made["ino"] == 9 and made["kind"] == "file" and made["size"] == 0, (
        "a new file takes the first free inode, empty: %r" % (made,))
    assert made["mode"] == 0o644 and made["uid"] == 0 and made["blocks"] == (), (
        "a new file carries the mode and uid it was made with, and no block: %r"
        % (made,))
    assert s.lookup(fresh_fs, "/etc/hosts")["ino"] == 9, (
        "the new entry does not resolve: %r" % (s.lookup(fresh_fs, "/etc/hosts"),))
    assert s.read_file(fresh_fs, 9) == b"", "a new file is empty"
    assert s.write_file(fresh_fs, 9, b"127.0.0.1\n")["size"] == 10, (
        "a new file cannot be written")
    assert s.read_file(fresh_fs, 9) == b"127.0.0.1\n", "a new file does not read back"
    order = [(entry[0], entry[1]) for entry in log
             if entry[0] in ("write", "barrier")]
    assert order == [("write", 11), ("barrier", 1), ("write", 19), ("barrier", 1)], (
        "create writes the inode, barriers, writes the directory entry, barriers: "
        "%r" % (order,))
    assert s.fsck(fresh)["ok"], "a created file leaves an inconsistent disk"

    made_dir = s.create(fresh_fs, "/home/user/logs", "dir", 0o755, 1001)
    assert made_dir["kind"] == "dir" and made_dir["ino"] == 10, (
        "a new directory takes the first free inode: %r" % (made_dir,))
    assert made_dir["blocks"] == (fresh_fs["super"]["dir_start"] + 10,) == (28,), (
        "a new directory owns its own directory sector: %r" % (made_dir,))
    assert s.lookup(fresh_fs, "/home/user/logs")["kind"] == "dir", (
        "a directory made at runtime does not resolve")
    assert s.create(fresh_fs, "/home/user/logs/deep", "file", 0o644, 0)["ino"] == 11, (
        "a file cannot be made inside a directory made at runtime")
    assert s.fsck(fresh)["ok"], "a created directory leaves an inconsistent disk"

    message = _refuses(s.FsError, "create of a name that is already there",
                       lambda: s.create(fresh_fs, "/etc/motd", "file", 0o644, 0))
    assert "motd" in message and "/etc" in message, (
        "a duplicate name must name the name and the directory, got %r" % (message,))
    message = _refuses(s.FsError, "create of a relative path",
                       lambda: s.create(fresh_fs, "etc/x", "file", 0o644, 0))
    assert "etc/x" in message, (
        "a relative new path must be named, got %r" % (message,))
    message = _refuses(s.FsError, "create below the root itself",
                       lambda: s.create(fresh_fs, "/", "file", 0o644, 0))
    assert "/" in message, "a new entry at the root itself must be refused, got %r" % (message,)
    message = _refuses(s.FsError, "create of an unknown kind",
                       lambda: s.create(fresh_fs, "/etc/x", "link", 0o777, 0))
    assert "link" in message, "an unknown kind must be named, got %r" % (message,)
    message = _refuses(s.FsError, "create of an over-long name",
                       lambda: s.create(fresh_fs, "/etc/" + long_name, "file", 0o644, 0))
    assert long_name in message and "24" in message, (
        "an over-long new name must be named, with the limit, got %r" % (message,))
    _refuses(s.FsError, "create in a parent that is not there",
             lambda: s.create(fresh_fs, "/nope/x", "file", 0o644, 0))
    message = _refuses(s.FsError, "create below a file",
                       lambda: s.create(fresh_fs, "/etc/motd/x", "file", 0o644, 0))
    assert "/etc/motd" in message and "file" in message, (
        "a new entry below a file must name the file and what it is, got %r"
        % (message,))
    message = _refuses(s.FsError, "create in a full directory",
                       lambda: s.create(_full(s, devices, userland), "/etc/extra",
                                        "file", 0o644, 0))
    assert "full" in message and "/etc" in message, (
        "a full directory must be named as full, got %r" % (message,))

    full_disk = devices.Disk(sectors=30)
    s.format_disk(full_disk, [("/", "dir", 0o755, 0, b"")], 2)
    full_fs = s.mount(full_disk)["fs"]
    s.create(full_fs, "/a", "file", 0o644, 0)
    message = _refuses(s.FsError, "create with no free inode",
                       lambda: s.create(full_fs, "/b", "file", 0o644, 0))
    assert "table" in message and "2" in message, (
        "a full inode table must be named, got %r" % (message,))

    # ---- sync -------------------------------------------------------------

    assert s.sync(fresh_fs) == 0, (
        "a barrier with nothing buffered makes nothing durable: %r"
        % (s.sync(fresh_fs),))
    fresh.write(31, bytes(512))
    assert fresh.pending() == 1, "the device buffered a write"
    assert s.sync(fresh_fs) == 1, (
        "sync must answer how many sectors it made durable: %r" % (s.sync(fresh_fs),))
    assert fresh.pending() == 0, "sync left something buffered"

    # ---- fsck -------------------------------------------------------------

    check_disk = devices.Disk(sectors=64)
    s.format_disk(check_disk, files, 16)
    image = s.layout(files, 16, 64)
    assert image == bigger, (
        "the same tree at the same table size has one geometry: %r" % (image,))
    assert tuple(s.fsck(check_disk)) == ("ok", "problems"), (
        "fsck's keys are %r" % (tuple(s.fsck(check_disk)),))
    clean = s.fsck(check_disk)
    assert clean == {"ok": True, "problems": ()}, (
        "a freshly formatted disk has no problems: %r" % (clean,))
    kept = _bitmap(check_disk, image)
    assert kept[:3] == bytearray((0, 0, 0)) and kept[3] == 1, (
        "the first three blocks are the three fixture files: %r" % (kept[:4],))

    torn = devices.Disk(sectors=64)
    _copy_image(check_disk, torn)
    torn.write(image["inodes_start"] + 3, bytes(512))
    torn.write(image["inodes_start"] + 10, bytes(512))
    torn.barrier()
    got = s.fsck(torn)
    assert got["ok"] is False, "a torn inode sector must not read as consistent"
    assert got["problems"] == ("bad_checksum", "entry_not_allocated"), (
        "two torn inode sectors are one bad_checksum word, and the entry that "
        "named the first one is not allocated: %r" % (got,))
    torn_data = devices.Disk(sectors=64)
    _copy_image(check_disk, torn_data)
    torn_data.write(image["data_start"], bytes(512))
    torn_data.power_fail(tear=True)
    got = s.fsck(torn_data)
    assert got["ok"] is False and "bad_checksum" in got["problems"], (
        "a torn data sector must be reported as bad_checksum: %r" % (got,))

    bad_magic = devices.Disk(sectors=64)
    _copy_image(check_disk, bad_magic)
    bad_magic.write(0, bytes(512))
    bad_magic.barrier()
    assert s.fsck(bad_magic) == {"ok": False, "problems": ("bad_magic",)}, (
        "a foreign magic is fsck's first problem: %r" % (s.fsck(bad_magic),))

    bad_version = devices.Disk(sectors=64)
    _copy_image(check_disk, bad_version)
    bad_version.write(0, _super_image(image, {"version": 7}))
    bad_version.barrier()
    got = s.fsck(bad_version)
    assert "bad_version" in got["problems"] and not got["ok"], (
        "an unknown version is a problem fsck names: %r" % (got,))

    bad_geometry = devices.Disk(sectors=64)
    _copy_image(check_disk, bad_geometry)
    bad_geometry.write(0, _super_image(image, {"n_inodes": 5000}))
    bad_geometry.barrier()
    got = s.fsck(bad_geometry)
    assert "bad_geometry" in got["problems"] and not got["ok"], (
        "a geometry that does not fit is a problem fsck names: %r" % (got,))

    outside = devices.Disk(sectors=64)
    _copy_image(check_disk, outside)
    outside.write(image["inodes_start"] + 2,
                  _inode_image(image, 2, "file", 0o644, 0, 8, (1,)))
    outside.barrier()
    got = s.fsck(outside)
    assert "block_out_of_range" in got["problems"] and not got["ok"], (
        "an inode whose block leaves its region is a problem fsck names: %r" % (got,))
    high = devices.Disk(sectors=64)
    _copy_image(check_disk, high)
    high.write(image["inodes_start"] + 2,
               _inode_image(image, 2, "file", 0o644, 0, 8, (image["data_start"] + 60,)))
    high.barrier()
    got = s.fsck(high)
    assert "block_out_of_range" in got["problems"], (
        "a block past the data region is a problem fsck names: %r" % (got,))

    shared = devices.Disk(sectors=64)
    _copy_image(check_disk, shared)
    shared.write(image["inodes_start"] + 2,
                 _inode_image(image, 2, "file", 0o644, 0, 8, (34,)))
    shared.write(image["inodes_start"] + 4,
                 _inode_image(image, 4, "file", 0o600, 0, 12, (34,)))
    shared.barrier()
    got = s.fsck(shared)
    assert "block_shared" in got["problems"] and not got["ok"], (
        "a block two inodes claim is a problem fsck names: %r" % (got,))

    marked_free = devices.Disk(sectors=64)
    _copy_image(check_disk, marked_free)
    marked_free.write(image["inodes_start"] + 2,
                      _inode_image(image, 2, "file", 0o644, 0, 8, (34,)))
    free_map = bytearray(kept)
    free_map[0] = 1
    marked_free.write(image["free_map_sector"], _map_image(image, free_map))
    marked_free.barrier()
    got = s.fsck(marked_free)
    assert "block_marked_free" in got["problems"] and not got["ok"], (
        "a block an inode claims that the map calls free is a problem fsck "
        "names: %r" % (got,))

    dangle = devices.Disk(sectors=64)
    _copy_image(check_disk, dangle)
    dangle.write(image["dir_start"] + 0,
                 _dir_image(image, 0, (("etc", 1), ("root", 3), ("home", 5),
                                       ("tmp", 8), ("ghost", 99))))
    dangle.barrier()
    got = s.fsck(dangle)
    assert "entry_out_of_range" in got["problems"] and not got["ok"], (
        "an entry naming an inode outside the table is a problem fsck names: %r"
        % (got,))

    dangling = devices.Disk(sectors=64)
    _copy_image(check_disk, dangling)
    dangling.write(image["dir_start"] + 0,
                   _dir_image(image, 0, (("etc", 1), ("root", 3), ("home", 5),
                                         ("tmp", 8), ("ghost", 12))))
    dangling.barrier()
    got = s.fsck(dangling)
    assert "entry_not_allocated" in got["problems"] and not got["ok"], (
        "an entry naming a free inode is a problem fsck names: %r" % (got,))

    wrong_size = devices.Disk(sectors=64)
    _copy_image(check_disk, wrong_size)
    wrong_size.write(image["inodes_start"] + 2,
                     _inode_image(image, 2, "file", 0o644, 0, 600, (34,)))
    wrong_size.barrier()
    got = s.fsck(wrong_size)
    assert "size_mismatch" in got["problems"] and not got["ok"], (
        "a size that does not match the block count is a problem fsck names: %r"
        % (got,))

    bad_root = devices.Disk(sectors=64)
    _copy_image(check_disk, bad_root)
    bad_root.write(image["inodes_start"],
                   _inode_image(image, 0, "file", 0o755, 0, 0, ()))
    bad_root.barrier()
    got = s.fsck(bad_root)
    assert "root_not_directory" in got["problems"] and not got["ok"], (
        "a root that is not a directory is a problem fsck names: %r" % (got,))

    assert all(word in s.PROBLEMS for word in
               ("bad_checksum", "bad_magic", "bad_version", "bad_geometry",
                "block_out_of_range", "block_shared", "block_marked_free",
                "entry_out_of_range", "entry_not_allocated", "size_mismatch",
                "root_not_directory")), (
        "every word fsck can say is in the vocabulary: %r" % (s.PROBLEMS,))

    # ---- and the world is where it was ------------------------------------

    assert userland.files() == files, "the file fixture changed while the stage ran"

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "os-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G4_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G4_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names — and a
        `NotImplementedError` is re-raised first, so an untouched template escapes
        this check and the runner can say the stage is not implemented yet.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import devices
    import stage_05
    import stage_10
    import userland

    # --- the table this stage is ------------------------------------------------
    table = stage_10.syscall_table()
    expected = ((1, "write", 3), (2, "getpid", 0), (3, "yield", 0), (4, "frames", 0),
                (10, "read", 3), (11, "open", 2), (12, "close", 1),
                (13, "fork", 0), (14, "wait", 1), (15, "exit", 1),
                (16, "anon", 1), (17, "loop", 1), (18, "limit", 2),
                (19, "uid", 1), (20, "pipe", 0), (21, "dup2", 2))
    assert issubclass(stage_10.KernelError, ValueError), (
        "KernelError is not a ValueError: %r" % (stage_10.KernelError.__mro__,))
    assert stage_10.KernelError is not ValueError, (
        "KernelError is ValueError itself, so a caller cannot tell them apart")
    assert stage_10.TABLE_KEYS == ("nr", "name", "arity", "handler"), (
        "TABLE_KEYS is not the four keys every entry carries: %r"
        % (stage_10.TABLE_KEYS,))
    assert tuple(sorted(table)) == tuple(nr for nr, _name, _arity in expected), (
        "the table's numbers are not stage 5's four and this stage's twelve: %r"
        % (tuple(sorted(table)),))
    for nr, name, arity in expected:
        entry = table[nr]
        assert tuple(sorted(entry)) == tuple(sorted(stage_10.TABLE_KEYS)), (
            "syscall %d carries %r, not the four keys" % (nr, tuple(sorted(entry))))
        assert entry["nr"] == nr, (
            "syscall %d is numbered %r in its own entry" % (nr, entry["nr"]))
        assert entry["name"] == name, (
            "syscall %d is %r to this kernel, not %r" % (nr, entry["name"], name))
        assert entry["arity"] == arity, (
            "syscall %s takes %r arguments, not %d" % (name, entry["arity"], arity))
        assert callable(entry["handler"]), (
            "syscall %s has no handler to answer it: %r" % (name, entry["handler"]))
    handlers = tuple(table[nr]["handler"] for nr, _name, _arity in expected)
    assert len(set(handlers)) == len(expected), (
        "two of the sixteen calls share one handler: %r" % (handlers,))
    assert stage_10.syscall_table()[4]["name"] == "frames", (
        "the table does not come back unchanged for a table that is right: %r"
        % (stage_10.syscall_table(),))

    # --- stage 5 as the source of the first four --------------------------------
    original = stage_05.SYSCALLS
    try:
        stage_05.SYSCALLS = ("write", "getpid", "yield")
        message = _refuses(stage_10.KernelError, "a source table missing frames",
                           stage_10.syscall_table)
        assert "frames" in message, (
            "the refusal does not name the call that is missing: %r" % (message,))
        stage_05.SYSCALLS = ("write", "getpid", "getpid", "frames")
        message = _refuses(stage_10.KernelError, "a source table numbering getpid twice",
                           stage_10.syscall_table)
        assert "getpid" in message, (
            "the refusal does not name the call numbered twice: %r" % (message,))
        stage_05.SYSCALLS = ("write", "getpid", "yield", "frames", "teleport")
        message = _refuses(stage_10.KernelError, "a call stage 5 does not have",
                           stage_10.syscall_table)
        assert "teleport" in message, (
            "the refusal does not name the call stage 5 has not: %r" % (message,))
        stage_05.SYSCALLS = ()
        _refuses(stage_10.KernelError, "a source table with no calls at all",
                 stage_10.syscall_table)
    finally:
        stage_05.SYSCALLS = original
    assert tuple(table[nr]["name"] for nr, _name, _arity in expected[:4]) == original, (
        "the four stage 5 calls are not stage 5's own, in its own order: %r"
        % (tuple(table[nr]["name"] for nr, _name, _arity in expected[:4]),))

    # --- three resources, three numbers -----------------------------------------
    task = {"pid": 1, "ppid": 0, "state": "ready", "frames": (4096, 8192),
            "ticks": 3, "slots": {},
            "limits": {"frames": 8, "children": 2, "ticks": 10}}
    assert stage_10.limits_of(task) == {"frames": 8, "children": 2, "ticks": 10}, (
        "limits_of is not the task's limits as the three resources: %r"
        % (stage_10.limits_of(task),))
    limits = stage_10.limits_of(task)
    limits["frames"] = 99
    assert task["limits"]["frames"] == 8, (
        "limits_of handed out the task's own dict: %r" % (task["limits"],))
    _refuses(stage_10.KernelError, "a task that is not a task",
             lambda: stage_10.limits_of(None))
    _refuses(stage_10.KernelError, "a task with no limits at all",
             lambda: stage_10.limits_of({"pid": 1}))
    message = _refuses(stage_10.KernelError, "limits missing a resource",
                       lambda: stage_10.limits_of({"limits": {"frames": 1, "children": 1}}))
    assert "ticks" in message, (
        "a limit that is missing is refused without naming it: %r" % (message,))
    _refuses(stage_10.KernelError, "a limit that is a float",
             lambda: stage_10.limits_of(
                 {"limits": {"frames": 1.5, "children": 1, "ticks": 1}}))
    _refuses(stage_10.KernelError, "a limit that is negative",
             lambda: stage_10.limits_of(
                 {"limits": {"frames": -1, "children": 1, "ticks": 1}}))
    message = _refuses(stage_10.KernelError, "a limit for a resource this kernel has not",
                       lambda: stage_10.apply_limit(task, "money", 1))
    assert "money" in message, (
        "the refusal does not name the resource the kernel has not: %r" % (message,))
    _refuses(stage_10.KernelError, "a limit that is a bool",
             lambda: stage_10.apply_limit(task, "frames", True))
    _refuses(stage_10.KernelError, "a limit that is a float",
             lambda: stage_10.apply_limit(task, "frames", 2.5))
    message = _refuses(stage_10.KernelError, "a limit that is negative",
                       lambda: stage_10.apply_limit(task, "frames", -2))
    assert "-2" in message, (
        "the refusal does not name the limit it was given: %r" % (message,))
    got = stage_10.apply_limit(task, "frames", 4)
    assert got == {"resource": "frames", "value": 4,
                   "limits": {"frames": 4, "children": 2, "ticks": 10}}, (
        "apply_limit answered %r for frames = 4" % (got,))
    assert task["limits"]["frames"] == 4, (
        "apply_limit did not change the task's own limits: %r" % (task["limits"],))
    assert stage_10.admit(task, "frames", 2) == {"allowed": True, "reason": ""}, (
        "a task holding 2 frames and 2 more inside a limit of 4 was refused: %r"
        % (stage_10.admit(task, "frames", 2),))
    assert stage_10.admit(task, "frames", 3) == {"allowed": False, "reason": "frames"}, (
        "a task one frame past its limit was allowed: %r"
        % (stage_10.admit(task, "frames", 3),))
    assert stage_10.admit(task, "ticks", 7) == {"allowed": True, "reason": ""}, (
        "a task 7 ticks from its budget of 10 was refused: %r"
        % (stage_10.admit(task, "ticks", 7),))
    assert stage_10.admit(task, "ticks", 8) == {"allowed": False, "reason": "ticks"}, (
        "a task one tick past its budget was allowed: %r"
        % (stage_10.admit(task, "ticks", 8),))
    stage_10.apply_limit(task, "children", 0)
    assert stage_10.admit(task, "children", 0)["allowed"] is True, (
        "a task with no children left and none asked for was refused: %r"
        % (stage_10.admit(task, "children", 0),))
    assert stage_10.admit(task, "children", 1)["allowed"] is False, (
        "a task with no children left was allowed another: %r"
        % (stage_10.admit(task, "children", 1),))
    assert stage_10.admit(task, "children", 1)["reason"] == "children", (
        "a refusal does not name the resource that ran out: %r"
        % (stage_10.admit(task, "children", 1),))
    _refuses(stage_10.KernelError, "a resource this kernel has not",
             lambda: stage_10.admit(task, "money", 1))
    _refuses(stage_10.KernelError, "a want that is negative",
             lambda: stage_10.admit(task, "frames", -1))
    _refuses(stage_10.KernelError, "a want that is a bool",
             lambda: stage_10.admit(task, "frames", True))
    assert task["frames"] == (4096, 8192), (
        "admitting a frame moved one: %r" % (task["frames"],))

    # --- the numbers a task holds ------------------------------------------------
    holder = {"pid": 2, "slots": {"first": {"fd": 5, "kind": "pipe", "end": "write"},
                                 "again": {"fd": 5, "kind": "pipe", "end": "write"},
                                 "read": {"fd": 3, "kind": "pipe", "end": "read"},
                                 "pid": 9, "buf": (4096, 8)}}
    assert stage_10.fds(holder) == (3, 5), (
        "fds is not the distinct numbers a task holds, ascending: %r"
        % (stage_10.fds(holder),))
    assert stage_10.fds({"pid": 3}) == (), (
        "a task with no slots has open fds: %r" % (stage_10.fds({"pid": 3}),))
    assert stage_10.fds({"slots": "not a mapping"}) == (), (
        "a task whose slots are not a mapping has open fds: %r"
        % (stage_10.fds({"slots": "not a mapping"}),))
    assert stage_10.fds(None) == (), (
        "not a task, and fds answered %r" % (stage_10.fds(None),))

    # --- one cat, act by act -----------------------------------------------------
    kernel = stage_10.run((("cat", 0),))
    assert kernel["console"].bytes() == b"welcome\n", (
        "one cat did not put the file on the console: %r" % (kernel["console"].bytes(),))
    acts = tuple((line["op"], line["outcome"], line["value"], line["errno"])
                 for line in kernel["log"])
    assert acts == (("boot", "boot", 174, None), ("spawn", "spawn", 1, None),
                    ("open", "act", 2, None), ("read", "act", 8, None),
                    ("write", "act", 8, None), ("close", "act", 0, None),
                    ("exit", "act", 0, None), ("reap", "reap", 1, None)), (
        "one cat is not the eight acts it takes, in order: %r" % (acts,))
    assert stage_10.cross_check(kernel) == {}, (
        "the kernel and the world disagree about one cat: %r"
        % (stage_10.cross_check(kernel),))
    assert kernel["pool"].free_count() == 174, (
        "one cat leaked %d frame(s)" % (174 - kernel["pool"].free_count(),))
    assert kernel["tasks"].ledger() == {"frames_held": {}, "free": 174, "tasks": 0}, (
        "the process table is not empty after one cat: %r" % (kernel["tasks"].ledger(),))
    said = stage_10.report(kernel)
    assert said["tasks"] == 1, (
        "the report counts %r tasks after one program" % (said["tasks"],))
    assert said["syscalls"] == 5, (
        "one cat made %r syscalls, not open, read, write, close and exit"
        % (said["syscalls"],))
    assert said["frames_in_use"] == 0 and said["frames_free"] == 174, (
        "the report's frames after one cat are %r" % (said,))
    assert said["console_bytes"] == 8, (
        "the report counted %r console bytes for `welcome\\n`" % (said["console_bytes"],))
    assert said["ticks"] == kernel["ticks"].ticks == 5, (
        "the report's ticks %r are not the timer's %r"
        % (said["ticks"], kernel["ticks"].ticks))
    assert said["durable_sha"] == kernel["disk"].durable_sha(), (
        "the kernel's belief about the disk is not the disk's own record: %r vs %r"
        % (said["durable_sha"], kernel["disk"].durable_sha()))
    assert said["limits_hit"] == {}, (
        "one cat hit a limit: %r" % (said["limits_hit"],))
    records = kernel["counters"]["records"]
    assert records.sha() == kernel["disk"].durable_sha(), (
        "the ledger and the device disagree on a run that committed everything")
    assert records.barriers > 0, "the format never asked the disk to commit"
    assert records.written, "the ledger recorded nothing the format wrote"
    for index in records.order[:4]:
        assert records.written[index] == kernel["disk"].read(index), (
            "sector %d is not on the disk as the kernel believes it: %r vs %r"
            % (index, records.written[index][:8], kernel["disk"].read(index)[:8]))

    # --- one spawn: the fork, the two writes, and the wait ----------------------
    kernel = stage_10.run((("spawn", 0),))
    assert kernel["console"].bytes() == b"child\nchild\n", (
        "the fork's child and its parent both write `child`: %r"
        % (kernel["console"].bytes(),))
    waits = tuple((line["pid"], line["outcome"]) for line in kernel["log"]
                  if line["op"] == "wait")
    assert waits == ((1, "block"), (2, "refuse"), (1, "act")), (
        "the parent's wait did not block, wake and reap: %r" % (waits,))
    assert tuple(line["value"] for line in kernel["log"]
                 if line["op"] == "wait" and line["outcome"] == "act") == (0,), (
        "the reaped child's status is not the one it exited with: %r"
        % (kernel["log"],))
    assert stage_10.report(kernel)["tasks"] == 2, (
        "a fork is a task this run started, and the report counts %r"
        % (stage_10.report(kernel)["tasks"],))
    assert stage_10.cross_check(kernel) == {}, (
        "the kernel and the world disagree about one spawn: %r"
        % (stage_10.cross_check(kernel),))
    assert kernel["pool"].free_count() == 174, (
        "one spawn leaked %d frame(s)" % (174 - kernel["pool"].free_count(),))

    # --- the pipe, and what came back through it --------------------------------
    kernel = stage_10.run((("piped", 0),))
    assert kernel["console"].bytes() == b"through\n", (
        "the bytes did not come back through the pipe: %r" % (kernel["console"].bytes(),))
    assert tuple(line["value"] for line in kernel["log"]
                 if line["op"] in ("read", "write")) == (8, 8, 8), (
        "the pipe did not carry eight bytes there and back: %r" % (kernel["log"],))
    assert tuple(line["value"] for line in kernel["log"]
                 if line["op"] == "pipe") == (2,), (
        "a pipe's first free fd above the console is not 2: %r" % (kernel["log"],))
    assert stage_10.cross_check(kernel) == {}, (
        "the kernel and the world disagree about one pipe: %r"
        % (stage_10.cross_check(kernel),))
    assert kernel["pool"].free_count() == 174 and kernel["tasks"].ledger()["tasks"] == 0, (
        "one pipe leaked: %r" % (kernel["pool"].free_count(),))

    # --- a uid and a mode --------------------------------------------------------
    kernel = stage_10.run((("nosy", 0),))
    refused = tuple(line for line in kernel["log"] if line["outcome"] == "refuse")
    assert len(refused) == 1 and refused[0]["op"] == "open", (
        "nosy is refused once, on its open: %r" % (refused,))
    assert refused[0]["errno"] == "EPERM" and refused[0]["pid"] == 1, (
        "nosy's open is refused %r, not EPERM" % (refused[0],))
    assert kernel["console"].bytes() == b"", (
        "a refused open still put bytes on the console: %r" % (kernel["console"].bytes(),))
    assert tuple((line["name"], line["predict"]) for line in kernel["audit"]) == (
        ("uid", 1001), ("open", "EPERM"), ("exit", 0)), (
        "the audit of nosy is not the three calls it makes: %r" % (kernel["audit"],))
    assert stage_10.report(kernel)["limits_hit"] == {}, (
        "a refusal by mode and uid is not a limit hit: %r"
        % (stage_10.report(kernel)["limits_hit"],))
    mine = (("/", "dir", 0o755, 0, b""), ("/etc", "dir", 0o755, 0, b""),
            ("/etc/motd", "file", 0o400, 1001, b"welcome\n"))
    assert stage_10.run((("cat", 0),), files=mine)["console"].bytes() == b"welcome\n", (
        "root is not allowed to read a 0400 file it does not own: %r"
        % (stage_10.run((("cat", 0),), files=mine)["console"].bytes(),))
    assert stage_10.run((("cat", 1001),), files=mine)["console"].bytes() == b"welcome\n", (
        "the owner is not allowed to read its own 0400 file: %r"
        % (stage_10.run((("cat", 1001),), files=mine)["console"].bytes(),))
    denied = stage_10.run((("cat", 1002),), files=mine)
    assert denied["console"].bytes() == b"", (
        "a uid that is neither root nor the owner read the file: %r"
        % (denied["console"].bytes(),))
    assert tuple((line["op"], line["errno"]) for line in denied["log"]
                 if line["outcome"] == "refuse") == (("open", "EPERM"),
                                                     ("read", "EBADF"),
                                                     ("write", "EINVAL"),
                                                     ("close", "EBADF")), (
        "a uid that is neither root nor the owner is refused %r"
        % (tuple((line["op"], line["errno"]) for line in denied["log"]
                 if line["outcome"] == "refuse"),))

    # --- the budgets a program can spend ----------------------------------------
    kernel = stage_10.run((("hog", 0),))
    acts = tuple((line["op"], line["outcome"], line["value"]) for line in kernel["log"])
    assert acts == (("boot", "boot", 174), ("spawn", "spawn", 1),
                    ("limit", "act", 12), ("loop", "act", 9),
                    ("stop", "stop", "ticks"), ("reap", "reap", 1)), (
        "hog's log is not the limit, the loop it cuts short and the stop it earns: %r"
        % (acts,))
    assert stage_10.report(kernel)["limits_hit"] == {"ticks": 1}, (
        "hog's stop is not exactly one hit on the tick budget: %r"
        % (stage_10.report(kernel)["limits_hit"],))
    assert tuple(line["ticks"] for line in kernel["log"]
                 if line["op"] == "loop") == (10,), (
        "a loop of nine ticks is not charged ten, one for the op and nine for "
        "the work: %r" % (kernel["log"],))
    assert stage_10.report(kernel)["ticks"] == kernel["ticks"].ticks == 11, (
        "hog's eleven ticks are not the eleven the machine counted: %r vs %r"
        % (stage_10.report(kernel)["ticks"], kernel["ticks"].ticks))
    assert stage_10.cross_check(kernel) == {} and kernel["pool"].free_count() == 174, (
        "hog's run disagrees with the world or leaked: %r" % (stage_10.cross_check(kernel),))
    kernel = stage_10.run((("spawn", 0),),
                          limits={"frames": 64, "children": 8, "ticks": 2})
    assert tuple((line["op"], line["outcome"]) for line in kernel["log"]) == (
        ("boot", "boot"), ("spawn", "spawn"), ("fork", "act"), ("write", "act"),
        ("stop", "stop"), ("write", "act"), ("wait", "refuse"),
        ("stop", "stop"), ("reap", "reap"), ("reap", "reap")), (
        "a task with two ticks of budget is not stopped between its ops: %r"
        % (tuple((line["op"], line["outcome"]) for line in kernel["log"]),))
    assert stage_10.report(kernel)["limits_hit"] == {"ticks": 2}, (
        "two tasks stopped at their own tick budget are not two hits: %r"
        % (stage_10.report(kernel)["limits_hit"],))
    assert kernel["console"].bytes() == b"child\nchild\n", (
        "two tasks stopped at their tick budget write %r" % (kernel["console"].bytes(),))
    assert stage_10.cross_check(kernel) == {} and kernel["pool"].free_count() == 174, (
        "a task stopped at its own budget disagrees with the world or leaked: %r"
        % (stage_10.cross_check(kernel),))
    kernel = stage_10.run((("greedy", 0),))
    refused = tuple(line for line in kernel["log"] if line["outcome"] == "refuse")
    assert len(refused) == 1 and refused[0]["op"] == "anon", (
        "greedy's anon is refused once: %r" % (refused,))
    assert refused[0]["errno"] == "ENOSPC" and refused[0]["limit"] == "frames", (
        "greedy's anon is not refused ENOSPC against its frame budget: %r"
        % (refused[0],))
    assert stage_10.report(kernel)["limits_hit"] == {"frames": 1}, (
        "greedy's refusal is not exactly one hit on the frame budget: %r"
        % (stage_10.report(kernel)["limits_hit"],))
    assert stage_10.cross_check(kernel) == {} and kernel["pool"].free_count() == 174, (
        "greedy's run disagrees with the world or leaked: %r"
        % (stage_10.cross_check(kernel),))

    # --- a budget that stops a fork ----------------------------------------------
    kernel = stage_10.run((("spawn", 0),),
                          limits={"frames": 64, "children": 0, "ticks": 256})
    refused = tuple(line for line in kernel["log"] if line["outcome"] == "refuse")
    assert tuple((line["op"], line["errno"]) for line in refused) == (
        ("fork", "ENOSPC"), ("wait", "EINVAL")), (
        "a task with no children left is refused %r, not a fork and then a wait"
        % (tuple((line["op"], line["errno"]) for line in refused),))
    assert refused[0]["limit"] == "children", (
        "a refused fork is not a hit on the children budget: %r" % (refused[0],))
    assert kernel["console"].bytes() == b"child\n", (
        "the fork that was refused still put two programs' worth on the console: %r"
        % (kernel["console"].bytes(),))
    assert stage_10.report(kernel)["limits_hit"] == {"children": 1}, (
        "a refused fork is not exactly one hit on the children budget: %r"
        % (stage_10.report(kernel)["limits_hit"],))
    assert stage_10.cross_check(kernel) == {} and kernel["pool"].free_count() == 174, (
        "a run with a refused fork disagrees with the world or leaked: %r"
        % (stage_10.cross_check(kernel),))
    kernel = stage_10.run((("spawn", 0),),
                          limits={"frames": 64, "children": 1, "ticks": 256})
    assert kernel["console"].bytes() == b"child\nchild\n", (
        "a task with exactly one child left was refused a fork: %r"
        % (kernel["console"].bytes(),))
    assert stage_10.report(kernel)["limits_hit"] == {}, (
        "a fork inside the budget is counted as a hit: %r"
        % (stage_10.report(kernel)["limits_hit"],))

    # --- an op no syscall answers ------------------------------------------------
    kernel = stage_10.run((("unknown", 0),))
    refused = tuple(line for line in kernel["log"] if line["outcome"] == "refuse")
    assert len(refused) == 1 and refused[0]["op"] == "teleport", (
        "an op this userland has not is refused once, by name: %r" % (refused,))
    assert refused[0]["errno"] == "ENOSYS", (
        "an op no syscall answers is refused %r, not ENOSYS" % (refused[0]["errno"],))
    assert tuple((line["name"], line["predict"]) for line in kernel["audit"]) == (
        ("exit", 0),), (
        "an op no syscall answers wrote an audit line of its own: %r" % (kernel["audit"],))

    # --- the shell, and the three parties' account of it ------------------------
    text = b"hi\nwelcome\nchild\nchild\nthrough\n"
    kernel = stage_10.run(userland.SHELL)
    assert kernel["console"].bytes() == text, (
        "the shell's five programs do not write what they promise: %r"
        % (kernel["console"].bytes(),))
    assert stage_10.cross_check(kernel) == {}, (
        "the kernel and the world disagree about the shell: %r"
        % (stage_10.cross_check(kernel),))
    said = stage_10.report(kernel)
    assert said["tasks"] == 6, (
        "the shell ran %r tasks, not five spawns and the fork" % (said["tasks"],))
    assert said["syscalls"] == 22, (
        "the shell made %r syscalls, not the twenty-two its programs ask for"
        % (said["syscalls"],))
    assert said["console_bytes"] == len(text), (
        "the report counted %r console bytes for %r" % (said["console_bytes"], len(text)))
    assert said["frames_in_use"] == 0 and said["frames_free"] == 174, (
        "the shell's frames did not all come back: %r" % (said,))
    assert said["ticks"] == kernel["ticks"].ticks, (
        "the shell's report and the timer disagree on ticks: %r vs %r"
        % (said["ticks"], kernel["ticks"].ticks))
    assert said["durable_sha"] == kernel["disk"].durable_sha(), (
        "the shell's ledger and the device disagree: %r vs %r"
        % (said["durable_sha"], kernel["disk"].durable_sha()))
    assert said["limits_hit"] == {}, "the shell hit a limit: %r" % (said["limits_hit"],)
    assert kernel["pool"].free_count() == 174, (
        "the shell leaked %d frame(s)" % (174 - kernel["pool"].free_count(),))
    assert tuple(line["frames"] for line in kernel["log"]
                 if line["outcome"] == "spawn") == (3, 3, 3, 3, 3), (
        "a task of this kernel does not hold its three frames all the time it runs: %r"
        % (tuple(line["frames"] for line in kernel["log"]
                 if line["outcome"] == "spawn"),))
    assert kernel["tasks"].ledger() == {"frames_held": {}, "free": 174, "tasks": 0}, (
        "the process table is not empty after the shell: %r" % (kernel["tasks"].ledger(),))
    per_pid = {}
    for line in kernel["audit"]:
        per_pid[line["pid"]] = per_pid.get(line["pid"], 0) + 1
    assert per_pid == {1: 2, 2: 5, 3: 4, 4: 5, 5: 3, 6: 3}, (
        "the shell's syscalls per task are not what its programs ask for: %r" % (per_pid,))
    for line in kernel["audit"]:
        assert tuple(sorted(line)) == ("args", "decision", "name", "nr", "pid",
                                       "predict", "tick"), (
            "an audit line is not the seven fields stage 5 froze: %r" % (line,))
        answered = tuple(entry for entry in kernel["log"]
                         if entry["pid"] == line["pid"]
                         and entry["tick"] == line["tick"]
                         and entry["op"] == line["name"])
        assert len(answered) == 1, (
            "the promise for %s on pid %d at tick %d has %d lines to answer it"
            % (line["name"], line["pid"], line["tick"], len(answered)))
        entry = answered[0]
        assert entry["outcome"] == line["decision"], (
            "%s was promised %r and the log recorded %r"
            % (line["name"], line["decision"], entry["outcome"]))
        if line["decision"] == "act":
            assert entry["value"] == line["predict"], (
                "%s promised %r and the log recorded %r"
                % (line["name"], line["predict"], entry["value"]))
        else:
            assert entry["errno"] == line["predict"], (
                "%s promised %r and the log recorded %r"
                % (line["name"], line["predict"], entry["errno"]))
    refused = tuple((line["pid"], line["op"], line["errno"]) for line in kernel["log"]
                    if line["outcome"] == "refuse")
    assert refused == ((5, "open", "EPERM"), (6, "wait", "EINVAL")), (
        "the shell's refusals are not nosy's open and the fork's child's wait: %r"
        % (refused,))
    assert tuple(line["value"] for line in kernel["log"]
                 if line["op"] == "exit") == (0, 0, 0, 0, 0, 0), (
        "the shell's six exits are not all 0: %r" % (kernel["log"],))
    assert tuple(line["value"] for line in kernel["log"]
                 if line["outcome"] == "spawn") == (1, 2, 3, 4, 5), (
        "the shell's tasks are not the five pids it started in order: %r"
        % (kernel["log"],))

    # --- four programs, one world -------------------------------------------------
    kernel = stage_10.run((("spawn", 0), ("piped", 0), ("nosy", 1001), ("unknown", 0)))
    assert kernel["console"].bytes() == b"child\nchild\nthrough\n", (
        "four programs in one run wrote %r" % (kernel["console"].bytes(),))
    said = stage_10.report(kernel)
    assert said["tasks"] == 5, (
        "four programs and one fork are %r tasks" % (said["tasks"],))
    assert said["console_bytes"] == 20, (
        "four programs wrote %r console bytes, not twelve and eight"
        % (said["console_bytes"],))
    assert stage_10.cross_check(kernel) == {}, (
        "four programs in one run disagree with the world: %r"
        % (stage_10.cross_check(kernel),))
    assert kernel["pool"].free_count() == 174, (
        "four programs in one run leaked %d frame(s)"
        % (174 - kernel["pool"].free_count(),))
    assert kernel["tasks"].ledger() == {"frames_held": {}, "free": 174, "tasks": 0}, (
        "the process table is not empty after four programs: %r"
        % (kernel["tasks"].ledger(),))

    # --- a run cut off by its own budget -----------------------------------------
    kernel = stage_10.run((("spawn", 0),), ticks=4)
    assert kernel["ticks"].ticks == 4, (
        "a run with a budget of 4 advanced %r ticks" % (kernel["ticks"].ticks,))
    stopped = tuple(line for line in kernel["log"] if line["outcome"] == "stop")
    assert len(stopped) == 2 and tuple(line["limit"] for line in stopped) == ("ticks", "ticks"), (
        "a run that ran out of ticks stopped %r" % (stopped,))
    assert stage_10.report(kernel)["limits_hit"] == {"ticks": 2}, (
        "a run cut off by its budget counted %r hits"
        % (stage_10.report(kernel)["limits_hit"],))
    assert stage_10.cross_check(kernel) == {}, (
        "a run cut off by its own budget disagrees with the world: %r"
        % (stage_10.cross_check(kernel),))
    assert kernel["pool"].free_count() == 174, (
        "a run cut off by its own budget leaked %d frame(s)"
        % (174 - kernel["pool"].free_count(),))

    # --- an empty run is a run ---------------------------------------------------
    kernel = stage_10.run(())
    assert tuple(line["op"] for line in kernel["log"]) == ("boot",), (
        "an empty run is not a boot and nothing else: %r" % (kernel["log"],))
    assert kernel["log"][0]["free"] == 174 and kernel["log"][0]["value"] == 174, (
        "the boot line does not say how many frames the kernel was handed: %r"
        % (kernel["log"][0],))
    assert kernel["audit"] == (), (
        "an empty run made %r syscalls" % (kernel["audit"],))
    assert stage_10.cross_check(kernel) == {}, (
        "an empty run disagrees with the world: %r" % (stage_10.cross_check(kernel),))
    assert stage_10.report(kernel) == {
        "tasks": 0, "syscalls": 0, "frames_in_use": 0, "frames_free": 174,
        "console_bytes": 0, "durable_sha": kernel["disk"].durable_sha(),
        "ticks": 0, "limits_hit": {}}, (
        "an empty run's report is not zeros and the frames it was handed: %r"
        % (stage_10.report(kernel),))

    # --- a ledger is a belief, and a tampered world shows it ---------------------
    kernel = stage_10.run((("echo", 0),))
    assert stage_10.cross_check(kernel) == {}, (
        "the clean run the tampers are measured against already disagrees: %r"
        % (stage_10.cross_check(kernel),))
    kernel["log"] = tuple(line for line in kernel["log"] if line["op"] != "write")
    assert stage_10.cross_check(kernel) != {}, (
        "a log that lost the write it was charged for still agreed with the world")
    kernel = stage_10.run((("echo", 0),))
    kernel["console"].write(b"x")
    assert stage_10.cross_check(kernel) != {}, (
        "a byte written to the console behind the kernel's back still agreed")
    kernel = stage_10.run((("echo", 0),))
    kernel["pool"].alloc(1)
    assert stage_10.cross_check(kernel) != {}, (
        "a frame taken from the pool behind the kernel's back still agreed")
    kernel = stage_10.run((("echo", 0),))
    kernel["disk"].write(0, bytes(devices.SECTOR))
    kernel["disk"].barrier()
    assert stage_10.cross_check(kernel) != {}, (
        "a sector written straight to the device still agreed with the ledger")
    assert kernel["counters"]["records"].sha() != kernel["disk"].durable_sha(), (
        "the ledger's belief and the disk's record agree after a write to the device")

    # --- what the kernel refuses -------------------------------------------------
    _refuses(stage_10.KernelError, "a script that is a string",
             lambda: stage_10.run("echo"))
    _refuses(stage_10.KernelError, "a script of things that are not pairs",
             lambda: stage_10.run(("echo",)))
    _refuses(stage_10.KernelError, "a pair with a program and two owners",
             lambda: stage_10.run((("echo", 0, 1),)))
    message = _refuses(stage_10.KernelError, "a program this userland has not",
                       lambda: stage_10.run((("sudo", 0),)))
    assert "sudo" in message and "echo" in message, (
        "the refusal does not name the program and the ones there are: %r" % (message,))
    _refuses(stage_10.KernelError, "a uid that is negative",
             lambda: stage_10.run((("echo", -1),)))
    _refuses(stage_10.KernelError, "a uid that is a bool",
             lambda: stage_10.run((), uid=True))
    _refuses(stage_10.KernelError, "a tick budget of zero",
             lambda: stage_10.run((), ticks=0))
    _refuses(stage_10.KernelError, "a quantum of zero",
             lambda: stage_10.run((), quantum=0))
    _refuses(stage_10.KernelError, "a fixtures list that is not a fixtures list",
             lambda: stage_10.run((), files=(("nope",),)))
    _refuses(stage_10.KernelError, "a report of something that is not a kernel",
             lambda: stage_10.report(None))
    _refuses(stage_10.KernelError, "a report of a kernel with no counters",
             lambda: stage_10.report({"log": (), "audit": ()}))
    _refuses(stage_10.KernelError, "a log line that is missing its fields",
             lambda: stage_10.report({"log": ({},), "audit": ()}))
    kernel = stage_10.run(())
    _refuses(stage_10.KernelError, "a cross-check against a kernel with no pool",
             lambda: stage_10.cross_check({"tasks": kernel["tasks"], "log": (),
                                           "audit": (), "console": kernel["console"],
                                           "disk": kernel["disk"],
                                           "ticks": kernel["ticks"],
                                           "counters": kernel["counters"]}))
    assert stage_10.cross_check(kernel) == {}, (
        "a kernel that is all there was refused: %r"
        % (stage_10.cross_check(kernel),))

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The map you were handed",
        tags=["boot", "memory map"],
        action="Write `BootError`, `MapError`, `REGION_KINDS`, `region_frames`, "
               "`validate`, `usable_frames`, `region_at`, `summary` and `holes` "
               "in stage_01.py.",
        predict="Why a kernel has to read the memory map before it can trust a "
                "single byte of memory, and what a firmware that hands over two "
                "regions with the same frame in them forces a kernel to do.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The frame allocator, and the bitmap inside it",
        tags=["frames", "bitmap"],
        action="Write `FramesError`, `FREE`, `USED`, `BITMAP`, `Frames` "
               "(`state`, `alloc`, `free`, `free_count`, `used`, `bitmap_bytes`, "
               "`bits`, `log`) in stage_02.py.",
        predict="Where the bitmap that tracks the frames lives, and what a "
                "request for more frames than are free must leave behind.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The address space, and the translation you forgot to invalidate",
        tags=["paging", "tlb"],
        action="Write `SpaceError`, `ADDRESS_WIDTH`, `new_space`, `map_page`, "
               "`unmap_page`, `protect`, `lookup`, `mapped`, `space_frames` and "
               "`free_space` in stage_03.py.",
        predict="What a kernel's mirror of its page tables is for, and what the "
                "machine will keep serving if a page is unmapped without the "
                "right call.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The trap table, and the fault as data",
        tags=["traps", "faults"],
        action="Write `TrapError`, `FAULT_WORDS`, `ACTIONS`, `CAUSES`, `decode`, "
               "`classify`, `TrapTable` (`install`, `handler`, `vectors`), "
               "`handle` and `panic_record` in stage_04.py.",
        predict="What a fault's error code can tell a handler and what it cannot, "
                "and which faults a kernel may resolve, which it refuses and "
                "which are a panic.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The syscall boundary, and the pointer you did not check",
        tags=["syscalls", "user pointers"],
        action="Write `SyscallError`, `SYSCALLS`, `ERRNOS`, `number`, "
               "`user_range`, `copy_in`, `copy_out`, `dispatch` and `audit_line` "
               "in stage_05.py.",
        predict="What a kernel has to know about a pointer before it may read "
                "through it, and why the line about a call is written before the "
                "call rather than after it.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The process, and the frame nobody gave back",
        tags=["processes", "frames"],
        action="Write `ProcessError`, `STATES`, `TASK_KEYS`, `DEFAULT_LIMITS`, "
               "`USER_BASE`, `new_task`, `images`, `Processes` (`spawn`, `fork`, "
               "`exec`, `exit`, `wait`, `children`, `get`, `ledger`, `log`) in "
               "stage_06.py.",
        predict="Which frames a fork has to copy and which it must not share, and "
                "what a process that exits owes the allocator.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The scheduler, and the wakeup that never came",
        tags=["scheduling", "wakeups"],
        action="Write `SchedError`, `AGEING`, `Scheduler` (`add`, `remove`, "
               "`block`, `wake`, `step`, `run`, `queues`, `log`) and `wait_on` in "
               "stage_07.py.",
        predict="What a task must check after it enqueues itself to sleep, and "
                "what a low-priority task needs in order not to starve.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="Two CPUs, and the critical section nobody guarded",
        tags=["smp", "locks"],
        action="Write `LockError`, `OPS`, `Lock` (`acquire`, `release`, `owner`, "
               "`waiting`), `serialize`, `run_schedule`, `detect_deadlock` and "
               "`audit_holds` in stage_08.py.",
        predict="What a spinning CPU and a deferred one have in common, and what "
                "the same schedule scores with a lock and without one.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The format, and the write that was not ordered",
        tags=["filesystem", "durability"],
        action="Write `FsError`, `MAGIC`, `FORMAT_VERSION`, `NAMES_MAX`, "
               "`layout`, `format_disk`, `mount`, `lookup`, `read_file`, "
               "`write_file`, `create`, `sync` and `fsck` in stage_09.py.",
        predict="Which sector has to be written last for an interrupted format to "
                "leave nothing to mount, and what a checksum per sector buys a "
                "filesystem that a power failure can tear.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The capstone: the userland, and the kernel's own ledger",
        tags=["capstone", "userland"],
        action="Write `KernelError`, `TABLE_KEYS`, `syscall_table`, `limits_of`, "
               "`apply_limit`, `admit`, `fds`, `run`, `report` and `cross_check` "
               "in stage_10.py.",
        predict="What two records have to agree about before a kernel may be "
                "believed, and what the frame pool proves that a ledger cannot.",
        check=check_10,
    ),
]
