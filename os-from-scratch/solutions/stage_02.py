"""OS From Scratch — stage 2: The frame allocator, and the bitmap inside it.

Stage 1 read the map; this stage is the thing that hands the frames out, and
hands each of them out exactly once. The record of that is a bitmap, and the
decision this stage exists for is where the bitmap lives: in one of the frames
the pool tracks, written into RAM and read back out of RAM. A Python list would
answer every question a reader can ask the allocator and none of the questions
the machine asks — the machine cannot see a list, so the frame the allocator just
handed out is a frame the next kernel hands out again.

The pool is a set of frames, not a range: the clean boot map leaves `0..127` and
`193..239` handable, with the kernel, the boot info and the firmware in between.
The bitmap therefore indexes a frame's *position* in the pool rather than its
number, which is where the byte/bit split (`index // 8`, `index % 8`) and the
off-by-one both live. `state` answers for any frame at all; `alloc` and `free`
refuse by name and by state; and a refusal changes nothing but the refusal count.
"""

import machine

FREE, USED, BITMAP = "free", "used", "bitmap"


class FramesError(ValueError):
    """A frame pool that cannot be built, or a pool asked for something it cannot do."""


class Frames:
    """A pool of frames, and the bitmap that tracks it inside the pool itself."""

    def __init__(self, ram, pool, bitmap_frame=None, reserved=()):
        """The pool's frames, in ascending order, and the frame that holds the bitmap."""
        self._ram = ram
        self._pool = tuple(sorted(set(pool)))
        if not self._pool:
            raise FramesError("an empty pool: no frame to keep the bitmap in")
        if bitmap_frame is None:
            bitmap_frame = self._pool[0]
        if self._index(bitmap_frame) is None:
            raise FramesError("the bitmap frame %r is not a frame of the pool"
                              % (bitmap_frame,))
        self._bitmap_frame = bitmap_frame
        self._reserved = frozenset(reserved)
        self._allocated = 0
        self._freed = 0
        self._refused = 0
        self._ram.write_frame(self._bitmap_frame, bytes(machine.PAGE_SIZE))

    def _index(self, frame):
        """Where a frame sits in the bitmap: its position in the pool, or `None`."""
        for index, inside in enumerate(self._pool):
            if inside == frame:
                return index
        return None

    def _bit(self, index):
        """One bit of the bitmap, read out of the frame that holds it."""
        raw = self._ram.read(machine.addr_of(self._bitmap_frame) + index // 8, 1)
        return (raw[0] >> (index % 8)) & 1

    def _put(self, index, value):
        """Set or clear one bit, in RAM — there is no second copy of the bitmap."""
        addr = machine.addr_of(self._bitmap_frame) + index // 8
        byte = self._ram.read(addr, 1)[0]
        if value:
            byte |= 1 << (index % 8)
        else:
            byte &= ~(1 << (index % 8)) & 0xFF
        self._ram.write(addr, bytes((byte,)))

    def state(self, frame):
        """What a frame is: `free`, `used`, `bitmap`, `reserved`, or `outside`."""
        index = self._index(frame)
        if index is None:
            return "outside"
        if frame == self._bitmap_frame:
            return BITMAP
        if frame in self._reserved:
            return "reserved"
        if self._bit(index):
            return USED
        return FREE

    def alloc(self, count=1):
        """`count` distinct frames, ascending — or a refusal that changes nothing."""
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            self._refused += 1
            raise FramesError("alloc wants how many frames, not %r" % (count,))
        if count == 0:
            return ()
        free = self.free_count()
        if count > free:
            self._refused += 1
            raise FramesError("alloc(%d) but the pool has only %d frames free"
                              % (count, free))
        taken = []
        for frame in self._pool:
            if self.state(frame) == FREE:
                taken.append(frame)
                if len(taken) == count:
                    break
        for frame in taken:
            self._put(self._index(frame), 1)
        self._allocated += len(taken)
        return tuple(taken)

    def free(self, frame):
        """Give a frame back, or refuse naming the frame and the state it is in."""
        state = self.state(frame)
        if state != USED:
            self._refused += 1
            raise FramesError("frame %r is %s, so it cannot be freed" % (frame, state))
        self._put(self._index(frame), 0)
        self._freed += 1

    def free_count(self):
        """The pool, minus the frames in use, minus the bitmap, minus the reserved."""
        return sum(1 for frame in self._pool if self.state(frame) == FREE)

    def used(self):
        """The frames currently handed out, ascending."""
        return tuple(frame for frame in self._pool if self.state(frame) == USED)

    def bitmap_bytes(self):
        """How many bytes one bit per pool frame takes."""
        return (len(self._pool) + 7) // 8

    def bits(self):
        """The bitmap as the frame holds it: one bit per pool frame, in pool order."""
        raw = self._ram.read(machine.addr_of(self._bitmap_frame), self.bitmap_bytes())
        return tuple((raw[index // 8] >> (index % 8)) & 1
                     for index in range(len(self._pool)))

    def log(self):
        """The frames handed out, the frames given back, the refusals, the frames out."""
        return {"alloc": self._allocated, "free": self._freed,
                "refused": self._refused, "frames_out": self.used()}
