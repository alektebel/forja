"""The heap: objects with headers, references, and the ledger of what happened.

A collector's promises are about *objects* — where they live, who points at
them, whether the collector moved them, whether it freed one it should not
have. This module is where those objects live, and it is the referee: every
allocation, read, write, move and free goes through it, and it keeps the
ledger a stage's counts have to agree with.

  * **An object** is a header plus its payload. The header is what a real
    collector's header is: a shape (`SHAPES`), a mark bit, a reference count,
    a forwarding address (where a copying collector moved it), and the
    generation it was born in. The payload is the shape's slots: a `pair`
    holds two, an `array` holds `n`, a `box` holds one immutable value.
  * **A reference** is an object id — an int, `NULL_ID` meaning none. A slot
    that holds an id points at an object; the heap answers `deref` and refuses
    a dangling id, because a runtime that reads through a dead reference must
    fail loudly, not quietly.
  * **The ledger** is the point: `Heap.stats()` answers the counts every
    collector stage is graded on — allocations per shape, bytes live, bytes
    freed, moves, and the mark count of the last collection. A stage that
    claims "12 objects collected" against a heap that freed 11 is wrong, and
    the disagreement is in the ledger, not in anyone's prose.
  * **The roots** are the mutator's handles: the runtime's stack, frames and
    globals hold references, and `Heap.roots` is where they are registered. A
    collector that misses a root collects a live object; the heap cannot
    prevent that, but `validate_reachability` can catch it after the fact —
    the one invariant no collector may break: nothing reachable is ever freed.

Nothing in this module collects. Allocation, deref, set-slot, free and the
ledger are here; deciding *which* objects to free is every stage's job.
"""

POLICY_VERSION = "heap-policy-1"

#: object shapes (mirrored from the bytecode's demand table)
SHAPE_PAIR = "pair"
SHAPE_ARRAY = "array"
SHAPE_BOX = "box"
SHAPES = (SHAPE_PAIR, SHAPE_ARRAY, SHAPE_BOX)

#: the reference that points at nothing
NULL_ID = 0

#: header words, for `describe`'s line shape
MARK_CLEAR = 0
MARK_SET = 1

#: generation numbering: everything is born in the nursery (0)
NURSERY = 0


class HeapError(ValueError):
    """A caller's mistake: a slot out of range, a dangling id, a free of an
    already-freed object. Raised naming the offender."""


class Object:
    """One heap object: the header fields plus its slots.

    `slots` is a list (it *is* mutable — that is the mutator's whole job);
    everything else is the header the collector reads and the heap maintains.
    `forwarded` is `None` until a copying collector moves the object, then it
    is the object's new id, and reading the old id must answer the new one —
    that is what "moving without breaking a reference" means, and the heap
    enforces it.
    """
    __slots__ = ("id", "shape", "slots", "value", "marked", "refcount",
                 "forwarded", "generation")

    def __init__(self, oid, shape, nslots=0, value=None, generation=NURSERY):
        nslots = 0 if nslots is None else nslots
        self.id = oid
        self.shape = shape
        self.slots = [NULL_ID] * nslots
        self.value = value          # SHAPE_BOX only; immutable by contract
        self.marked = MARK_CLEAR
        self.refcount = 0
        self.forwarded = None
        self.generation = generation


class Heap:
    """The object space and its ledger.

    Created fresh per run (`Heap()`); the runtime registers roots, allocates,
    reads and writes through it, and the collectors run *over* it. The heap
    never decides anything about liveness — it records, refuses and answers.
    """

    def __init__(self):
        self._objects = {}          # id -> Object (freed ids removed)
        self._next_id = 1           # 0 is NULL_ID; ids are never reused
        self.roots = []             # the mutator's root references
        # --- the ledger
        self.allocated = {s: 0 for s in SHAPES}
        self.freed = {s: 0 for s in SHAPES}
        self.bytes_allocated = 0
        self.bytes_freed = 0
        self.moves = 0
        self.marks = 0              # objects marked by the last collection
        self.collections = 0

    # --- allocation and the header ------------------------------------------
    def allocate(self, shape, nslots=None, value=None, generation=NURSERY):
        """Allocate one object and answer its id. The ledger's `allocated` and
        `bytes_allocated` move here and nowhere else. A pair defaults to its
        two slots; a box takes a `value` and no slots; an array takes `nslots`."""
        if shape not in SHAPES:
            raise HeapError("unknown shape: %r" % (shape,))
        if shape == SHAPE_PAIR:
            if nslots is None:
                nslots = 2
            if nslots != 2:
                raise HeapError("a pair has two slots, got %r" % (nslots,))
        if shape == SHAPE_BOX and nslots:
            raise HeapError("a box has no slots, got %r" % (nslots,))
        if shape == SHAPE_ARRAY and nslots < 0:
            raise HeapError("negative array length: %r" % (nslots,))
        oid = self._next_id
        self._next_id += 1
        obj = Object(oid, shape, nslots, value, generation)
        self._objects[oid] = obj
        self.allocated[shape] += 1
        self.bytes_allocated += self.size_of(shape, nslots)
        return oid

    def size_of(self, shape, nslots=0):
        """The bytes this object occupies: header + payload, by shape."""
        header = 16
        if shape == SHAPE_PAIR:
            return header + 2 * 8
        if shape == SHAPE_ARRAY:
            return header + nslots * 8
        if shape == SHAPE_BOX:
            return header + 8
        raise HeapError("unknown shape: %r" % (shape,))

    # --- references ----------------------------------------------------------

    def deref(self, oid):
        """The object `oid` points at. A dangling or forwarded id answers the
        truth: a forwarded id follows the forwarding pointer; a freed or never-
        allocated id raises, because reading through one is the bug."""
        if oid == NULL_ID:
            raise HeapError("deref of NULL_ID")
        if oid in self._objects:
            return self._objects[oid]
        raise HeapError("dangling reference: %r" % (oid,))

    def follow(self, oid):
        """Resolve a reference to its *current* id, following forwarding
        pointers. A freed id raises exactly as `deref` does."""
        if oid == NULL_ID:
            return NULL_ID
        obj = self.deref(oid)
        seen = set()
        while obj.forwarded is not None:
            if obj.id in seen:
                raise HeapError("forwarding cycle at %r" % (obj.id,))
            seen.add(obj.id)
            obj = self.deref(obj.forwarded)
        return obj.id

    def slot(self, oid, index):
        """Read one slot of an object, as a reference id."""
        obj = self.deref(oid)
        if obj.shape == SHAPE_BOX:
            raise HeapError("a box has no slots")
        if not 0 <= index < len(obj.slots):
            raise HeapError("slot %r out of range for %r (%d slots)"
                            % (index, obj.shape, len(obj.slots)))
        return obj.slots[index]

    def set_slot(self, oid, index, value_id):
        """Write one slot. THIS is where a write barrier belongs — the barrier
        itself is the stages' job; the heap only records the write happened."""
        obj = self.deref(oid)
        if obj.shape == SHAPE_BOX:
            raise HeapError("a box has no slots")
        if not 0 <= index < len(obj.slots):
            raise HeapError("slot %r out of range for %r (%d slots)"
                            % (index, obj.shape, len(obj.slots)))
        obj.slots[index] = value_id

    def value_of(self, oid):
        """The immutable value of a box."""
        obj = self.deref(oid)
        if obj.shape != SHAPE_BOX:
            raise HeapError("value_of on a %r" % (obj.shape,))
        return obj.value

    # --- freeing and moving --------------------------------------------------

    def free(self, oid):
        """Remove one object from the heap and move the ledger. Freeing an
        already-freed id raises — double-free is the bug the ledger exists to
        catch. Freeing a forwarded id frees the *target*."""
        real = self.follow(oid)
        obj = self.deref(real)
        del self._objects[real]
        self.freed[obj.shape] += 1
        self.bytes_freed += self.size_of(obj.shape, len(obj.slots))

    def move(self, oid, generation):
        """A copying collector's primitive: allocate a twin of `oid` in
        `generation`, copy its payload, set the old header's forwarding pointer
        and move the ledger's `moves`. Answers the new id."""
        obj = self.deref(oid)
        new_id = self.allocate(obj.shape, len(obj.slots), obj.value, generation)
        twin = self.deref(new_id)
        twin.slots = list(obj.slots)
        twin.refcount = obj.refcount
        obj.forwarded = new_id
        self.moves += 1
        return new_id

    # --- the collector's view ------------------------------------------------

    def live_ids(self):
        """Every id currently in the heap, in allocation order."""
        return sorted(self._objects)

    def live_bytes(self):
        """Bytes currently occupied: allocated minus freed."""
        return self.bytes_allocated - self.bytes_freed

    def snapshot(self, oid):
        """A deep copy of `oid`'s shape: ("pair", (left, right)) with ids
        resolved through forwarding — the shape a reachability check walks."""
        obj = self.deref(oid)
        if obj.shape == SHAPE_BOX:
            return (SHAPE_BOX, obj.value)
        return (obj.shape,
                tuple(self.follow(s) for s in obj.slots))

    def stats(self):
        """The ledger, as a dict with pinned keys — the shape every stage's
        report has to agree with."""
        return {
            "allocated": dict(self.allocated),
            "freed": dict(self.freed),
            "bytes_allocated": self.bytes_allocated,
            "bytes_freed": self.bytes_freed,
            "live_bytes": self.live_bytes(),
            "moves": self.moves,
            "marks": self.marks,
            "collections": self.collections,
        }

    # --- the invariant checker ----------------------------------------------

    def validate_reachability(self, root_ids=None):
        """The one invariant, checked: walk from the roots over live objects
        and answer the set of reachable ids. A collector's correctness test is
        `freed ∩ reachable == ∅` — the check that uses this answers it."""
        roots = self.roots if root_ids is None else root_ids
        seen = set()
        stack = [self.follow(r) for r in roots if r != NULL_ID]
        while stack:
            oid = stack.pop()
            if oid in seen or oid == NULL_ID:
                continue
            seen.add(oid)
            obj = self.deref(oid)
            stack.extend(self.follow(s) for s in obj.slots)
        return seen
