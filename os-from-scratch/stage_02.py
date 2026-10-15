"""OS From Scratch — stage 2: The frame allocator, and the bitmap inside it.

Stage 1 answered *which* frames this kernel may hand out; it did not answer how
the kernel will remember, and how it will know which of them are already gone.
That record is the whole of this stage, and the decision underneath it is where
the record lives: in a bitmap written into one of the frames the pool tracks, not
in a Python list beside it. A list is invisible to the machine, and an invisible
record of what was handed out is the same as no record at all — the next boot
hands the same frame to somebody else.

    FREE, USED, BITMAP   what a pool frame can be, as far as a caller asks
    FramesError          the family every refusal in this stage belongs to
    Frames               a pool of frames, and the bitmap that tracks it

The pool is a *set of frames*, not an address range: the clean boot map leaves
frames `0..127` and `193..239` handable, with the kernel, the boot info and the
firmware in between. The bitmap indexes a frame's *position* in that pool rather
than its number, which is where the byte/bit split lives and where an off-by-one
is invisible until two owners hold one frame. `state` answers for any frame at
all — a frame this allocator does not own is answered, not refused — while
`alloc` and `free` refuse by name and by state, and a refused `alloc` leaves the
pool exactly as it found it.

DESIGN DECISION — why does the bitmap live *inside* the pool it tracks, and not
beside it?
Because the only ledger that survives is the one the machine can see. A Python
list answers every question a caller can ask and none of the questions the next
kernel asks: the frames it forgot are, to the hardware, free. Putting the bits in
one of the frames means the record and the thing recorded share one lifetime, one
address space and one failure mode, and it costs one frame of the pool — a frame
that `state` names `bitmap` and that no allocation will ever hand out.

DESIGN DECISION — why one bit per *position in the pool*, and not one bit per
frame number?
Because the pool is what stage 1 left handable, and that is a set with holes in
it: `0..127` and `193..239`, not `0..239`. A bitmap indexed by frame number would
have to be as large as the machine to describe 175 frames, and the frames the
kernel and the firmware took would need bits that are never read. Indexing by
position makes the bitmap exactly `(len(pool) + 7) // 8` bytes, and it makes the
byte/bit split — `index // 8` for the byte, `index % 8` for the bit — the one
place a frame can be lost for free.

DESIGN DECISION — why must a refused `alloc` change *nothing*?
Because a partial answer is the worst of the three possible answers. An allocator
that hands back four frames when five were asked for has not failed, it has lied:
the caller will use the four, write past the end of them, and the pool's count
will be short by the frames nobody notices are gone. Refusing as a whole means the
caller either gets exactly what it asked for or gets a message naming the request
and the free count, and the pool it leaves behind is the pool it found — which is
what makes a refusal safe to retry.

DESIGN DECISION — why does `state` answer `"outside"` where `free` refuses?
Because they are two different acts. `state` is a question, and the honest answer
to "is frame 300 yours?" is that it is not this allocator's frame at all — a
kernel that wants to know whether an address belongs to it should get an answer,
not an exception. `free` is an act, and an act on a frame this pool does not own
is a bug in the caller; refusing it by name, before anything changes, is the only
way the caller learns. The same rule runs through the whole course: a refusal is
raised for the caller's mistake, a decision is returned as data.

DESIGN DECISION — why does the bitmap track only the frames that were handed out,
while the bitmap's own frame and the reserved ones are excluded by name?
Because the bitmap is a record of an *act*, and only one of the three exclusions
is an act: a frame is `used` because `alloc` handed it out, which is exactly what
one bit can say. The bitmap's own frame and a reserved one are facts about the
pool, not events in its life — they are unavailable before the first allocation
and they stay unavailable — so a bit for them would be a bit written once and read
forever, and `free` would have to tell "reserved" from "in use" by looking
somewhere else anyway. Excluding them by name keeps one meaning per bit: set means
this frame is out, and it is the only thing `used` and `free_count` have to agree
about.

TODO: implement `Frames.__init__`, `Frames.state`, `Frames.alloc`, `Frames.free`,
`Frames.free_count`, `Frames.used`, `Frames.bitmap_bytes`, `Frames.bits` and
`Frames.log`.
"""

import machine

FREE, USED, BITMAP = "free", "used", "bitmap"


class FramesError(ValueError):
    """A frame pool that cannot be built, or a pool asked for something it cannot do."""


class Frames:
    """A pool of frames, and the bitmap that tracks it inside the pool itself."""

    def __init__(self, ram, pool, bitmap_frame=None, reserved=()):
        """The pool's frames, in ascending order, and the frame that holds the bitmap.

        The bitmap's default frame is the pool's first, the pool is refused when
        it is empty or when the bitmap frame is not one of its frames, and the
        bitmap is zeroed: every pool frame starts free.
        """
        raise NotImplementedError("stage 2: implement Frames.__init__()")

    def state(self, frame):
        """What a frame is: `free`, `used`, `bitmap`, `reserved`, or `outside`.

        A frame the pool does not hold is `"outside"`: answered, not refused.
        """
        raise NotImplementedError("stage 2: implement Frames.state()")

    def alloc(self, count=1):
        """`count` distinct frames, ascending — or a refusal that changes nothing.

        A request larger than the free count is refused as a whole, naming the
        request and the free count; `alloc(0)` is `()`, and a count that is not a
        whole number of frames is refused.
        """
        raise NotImplementedError("stage 2: implement Frames.alloc()")

    def free(self, frame):
        """Give a frame back, or refuse naming the frame and the state it is in.

        A frame outside the pool, the bitmap's own frame, a reserved frame and a
        frame that is not in use are all refused, and nothing is changed by it.
        """
        raise NotImplementedError("stage 2: implement Frames.free()")

    def free_count(self):
        """The pool, minus the frames in use, minus the bitmap, minus the reserved."""
        raise NotImplementedError("stage 2: implement Frames.free_count()")

    def used(self):
        """The frames currently handed out, ascending."""
        raise NotImplementedError("stage 2: implement Frames.used()")

    def bitmap_bytes(self):
        """How many bytes one bit per pool frame takes."""
        raise NotImplementedError("stage 2: implement Frames.bitmap_bytes()")

    def bits(self):
        """The bitmap as the frame holds it: one bit per pool frame, in pool order.

        The bits are read back out of RAM, so an allocator that keeps its bitmap
        somewhere else answers with what RAM holds, which is nothing.
        """
        raise NotImplementedError("stage 2: implement Frames.bits()")

    def log(self):
        """The frames handed out, given back, refusals, and the frames out now."""
        raise NotImplementedError("stage 2: implement Frames.log()")
