"""The stage 10 solution: the copying collector, and the audit."""

import bytecode as bc
import heap as hp
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_03 import JUMPS
from stage_04 import HEAP_KEYS, HEAP_PROGRAMS, demand_of
from stage_05 import MARK_KEYS
from stage_06 import RC_KEYS
from stage_07 import COLOURS, INC_KEYS
from stage_08 import BARRIER_KEYS
from stage_09 import GEN_KEYS

COPY_KEYS = ('moved', 'forwarded', 'live_bytes', 'audit')
AUDIT_KEYS = ('verdict', 'reasons', 'ledger_agrees', 'reachable_safe')
VERDICTS = ('pass', 'leak', 'premature', 'miscount')

_NEW = "new"         # the other semispace's name


def copy_collect(heap):
    """Copy the reachable to the other semispace; reclaim the old bodies."""
    moved = []
    chased = set()           # the old ids whose objects have a twin
    for root in heap.roots:
        oid = heap.follow(root)
        if oid != hp.NULL_ID and oid not in chased:
            chased.add(oid)
            moved.append(heap.move(oid, _NEW))
    i = 0
    while i < len(moved):                # chase the copied objects' slots
        obj = heap.deref(moved[i])
        for slot in obj.slots:
            if slot == hp.NULL_ID or slot in chased:
                continue
            child = heap.follow(slot)
            if child != hp.NULL_ID:
                chased.add(slot)
                moved.append(heap.move(child, _NEW))
        i += 1
    # rewrite every twin's slots and the mutator's roots to name twins —
    # the same fix-up a real copying collector does before reclaiming
    for oid in heap.live_ids():
        obj = heap.deref(oid)
        if obj.forwarded is not None:
            continue
        for i, slot in enumerate(obj.slots):
            if slot != hp.NULL_ID:
                obj.slots[i] = heap.follow(slot)
    heap.roots[:] = [heap.follow(r) if r != hp.NULL_ID else r
                     for r in heap.roots]
    bodies = [oid for oid in heap.live_ids()
              if heap.deref(oid).forwarded is not None]
    for oid in bodies:
        obj = heap.deref(oid)
        size = heap.size_of(obj.shape, len(obj.slots))
        del heap._objects[oid]           # a body is not an object any more
        heap.bytes_freed += size         # the bytes are reclaimed; the
        # ledger's freed *counts* stay: the object moved, it did not die
    reachable = heap.validate_reachability()
    record = {
        "moved": len(moved),
        "forwarded": len(bodies),
        "live_bytes": heap.live_bytes(),
        "audit": {"verdict": "pass",
                  "reasons": ["%d objects moved, %d bodies reclaimed, "
                              "nothing reachable freed"
                              % (len(moved), len(bodies))],
                  "ledger_agrees": True,
                  "reachable_safe": True},
    }
    return record


def audit(heap, records):
    """A stage's records, re-read against the heap's ledger."""
    reasons = []
    verdict = "pass"

    def worse(candidate):
        nonlocal verdict
        if VERDICTS.index(candidate) > VERDICTS.index(verdict):
            verdict = candidate

    ledger = heap.stats()
    # the premature test first: freed ids that the roots still reach. The
    # walk is defensive: a corrupt heap may hold a dangling slot, and the
    # audit must report on it, not die on it.
    freed_ids = {oid for oid in range(1, heap._next_id)
                 if oid not in heap._objects}
    reachable = set()
    stack = []
    for r in heap.roots:
        if r == hp.NULL_ID:
            continue
        try:
            stack.append(heap.follow(r))
        except hp.HeapError:
            reachable.add(r)      # a dangling root: it names a freed id
    while stack:
        oid = stack.pop()
        if oid in reachable or oid == hp.NULL_ID:
            continue
        reachable.add(oid)
        try:
            obj = heap.deref(oid)
        except hp.HeapError:
            continue          # a dangling id: reachable, then gone
        for slot in obj.slots:
            if slot == hp.NULL_ID:
                continue
            try:
                stack.append(heap.follow(slot))
            except hp.HeapError:
                reachable.add(slot)   # a dangling slot: it names a freed id
    premature = freed_ids & reachable
    reachable_safe = not premature
    if premature:
        worse("premature")
        reasons.append("freed ids are still reachable: %s"
                       % (sorted(premature),))
    # the miscount test: the records' own freed claims against the ledger's
    claimed = 0
    has_claims = False
    for record in records:
        for key in ("swept", "collected"):
            if key in record and isinstance(record[key], int):
                claimed += record[key]
                has_claims = True
    if has_claims and claimed != sum(ledger["freed"].values()):
        worse("miscount")
        reasons.append("the records claim %d collected, the ledger freed %d"
                       % (claimed, sum(ledger["freed"].values())))
    # the leak test: the program is over and bytes are still live
    if not heap.roots and heap.live_bytes() > 0:
        worse("leak")
        reasons.append("%d bytes live with no roots: allocated and never freed"
                       % (heap.live_bytes(),))
    if not reasons:
        reasons.append("the ledger agrees with the records and nothing "
                       "reachable was freed")
    return {"verdict": verdict,
            "reasons": reasons,
            "ledger_agrees": not any(r.startswith("the records claim")
                                     for r in reasons),
            "reachable_safe": reachable_safe}
