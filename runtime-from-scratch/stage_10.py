"""Runtime From Scratch — stage 10: The copying collector, forwarding, and
the audit.

The last mechanism, and then the reckoning. The copying collector never frees
anything in place: it copies every reachable object into the other
semispace, leaves a forwarding pointer in the old body, and reclaims the
whole old space in one stroke. `heap.move` is the primitive and this stage's
`copy_collect` is its loop: copy the roots, then chase every copied object's
slots through the forwarding pointers, until the reachable set lives entirely
in the new space. The old bodies stay until *this* collector reclaims them —
which is what stage 5's sweep was skipping.

`audit` is the diagnostic the whole course earns: it takes a stage's own
records and re-reads them against the heap's ledger, answering one of the
four verdicts — `pass` when the numbers agree and nothing reachable died,
`leak` when bytes were allocated and never freed and the program is over,
`premature` when the freed set touches the reachable set, `miscount` when a
stage's claimed numbers disagree with the world's. Each verdict carries its
reasons, and the check holds each against the reason that produced it — the
audit is graded the way the whole unit was: against the ledger, not against
anyone's prose.

DESIGN DECISION — Why does `copy_collect` walk via the forwarding pointers
instead of a separate worklist of new ids?
Because the forwarding pointer IS the worklist's memory: an old id answers
its twin, so the loop can chase slots by following, exactly the way the
world's own `validate_reachability` walks. A separate worklist would be a
second bookkeeping that could disagree with the forwarding — and the
check's central assertion is that nothing disagrees.

DESIGN DECISION — Why does `audit` answer reasons as a list of strings and
not a single message?
Because a corrupt record can fail more than one way — a miscount can also be
a leak — and the diagnostic that names only its first finding hides the
second. The verdict is the worst thing the audit found; the reasons are
everything it found.


TODO: implement the functions this stage names; the docstrings above are the contract.

DESIGN DECISION — Why does the audit walk defensively instead of trusting
`heap.validate_reachability` on a corrupt heap?
Because the audit's whole job is to look at corrupt records: the walk that
raises on a dangling slot is the walk that cannot report on the premature free
that caused it. The verdicts are earned from the evidence — including evidence
of damage.
"""

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


def copy_collect(heap):
    """The reachable, copied to the other semispace: the roots move, then the
    loop chases every copied object's slots through the forwarding pointers.

    Answers COPY_KEYS — how many objects moved, how many old addresses now
    resolve through forwarding, the live bytes after, and the audit's record
    of the collection itself."""

    raise NotImplementedError("stage 10: implement copy_collect()")


def audit(heap, records):
    """A stage's records, re-read against the heap's ledger.

    Answers AUDIT_KEYS: the verdict (the worst thing found, in VERDICTS'
    order of severity), the reasons that earned it, whether the ledger
    agrees with the records' own numbers, and whether anything reachable
    was freed."""

    raise NotImplementedError("stage 10: implement audit()")
