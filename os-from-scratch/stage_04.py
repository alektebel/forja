"""OS From Scratch — stage 4: The trap table, and the fault as data.

A machine that faults does not ask the kernel *if* it wants the fault: it stops
where it is and hands over a vector, an error code, an address and a CPU. The
kernel's answer is one of exactly three things — resolve the fault and continue,
refuse it and tell the faulting task so, or panic — and this stage is the table
that decides which, plus the small vocabulary that makes the decision readable.
Nothing here executes; a trap is raised by whoever is driving the kernel, and
what comes back is a decision, not a jump.

The interesting half is the error code. A real CPU hands the handler three bits
and nothing else: bit 0 set means the page was present and the access was denied,
bit 1 set means the access was a write, bit 2 set means the access came from
user mode. The walk that raised the fault knows more than that — it knows
whether the page was the kernel's, whether it was not executable, whether it was
not there at all — and it says so in `PageFault.reason`. A handler does not get
that word, and this stage is where the two vocabularies are reconciled: five
machine words in, three handler words out. A kernel that reads `reason` instead
of the bits is a kernel that will not survive being ported to a real CPU.

    FAULT_WORDS     the three words a handler may read out of the error bits
    ACTIONS         resolve, refuse, panic — every decision is one of them
    CAUSES          why a panic happened, from a closed vocabulary
    decode          the error bits as one of the three words
    classify        the vector, its name, its kind, the address, the CPU
    TrapTable       which vectors have handlers, and which may never
    handle          the decision table: the whole stage
    panic_record    the readable line a dead kernel leaves behind

`TrapError` is the family every refusal in this stage belongs to: a handler
installed for a vector this machine does not have, for the double fault itself,
or twice over. Nothing a *fault* can bring is refused — a fault is data, and
data is returned.

DESIGN DECISION — why does the handler get three words when the machine knows
five?
Because that is all a real CPU gives it. `PageFault.reason` is the walk's own
exact word — `supervisor`, `no_execute`, `not_user` and the two this stage also
has — and it is deliberately finer than the three bits: a handler that could read
`supervisor` would be a handler that works in this simulation and not on the
hardware, which is the one kind of code a kernel course must not produce. So
`decode` reads the three bits, the user bit never changes the word (it is
*context*, and the same denied page reads the same from either mode), and the
machine's finer word is available to whoever raised the fault, not to whoever
handles it.

DESIGN DECISION — why is the double fault installed nowhere, instead of given a
handler?
A handler for vector 8 is a promise that the kernel can fail twice and carry on,
and no kernel in this course can: the fault arrived while the machine was already
in the middle of something the kernel could not finish. Refusing to install it
turns "we will cope" into a `TrapError` at boot, which is one message instead of
a triple fault nobody can read. The same rule, one level down, is what
`in_handler` does at run time: a fault that arrives inside a handler panics with
cause `in_handler` rather than being resolved a second time.

DESIGN DECISION — who may be demand-paged, and who may not?
Only a user fault on an address whose page is *not present*, and only when the
kernel was handed the machine and the pool to fix it with. A page fault with the
user bit clear is the kernel touching its own address space, and the kernel does
not demand-page for itself: it pages for processes, and a kernel bug that
silently allocates a page is a kernel bug that is never found. That is why the
user bit is checked before the word is: `not_present` for a user task is a
missing page, and the same word for the kernel is a null pointer.

DESIGN DECISION — what does a refusal look like when there is no handler?
It depends on who was running. An IRQ with no handler is refused with
`unhandled_irq` whatever the mode, because a device nobody listens to is a
device, not a crash. An exception with no handler in user mode is refused with
`unhandled_exception` and the task goes on to be killed by its own supervisor. The
same exception in kernel mode is a panic with cause `unhandled_exception`: the
kernel has no supervisor, and pretending it has one is how a machine that no
longer knows what it is doing keeps running.

DESIGN DECISION — why is the pool's refusal turned into a panic instead of being
allowed to travel?
`out_of_memory` is a decision, and everything that is a decision in this course
is *returned* so that somebody can report it. Letting stage 2's refusal escape
would make the same event an exception from `handle` and a dict from everywhere
else, and the frames the pool had already handed over for the mapping in progress
would be neither mapped nor counted. So the handler catches the allocator's
refusal, gives back what it took, and returns the panic — the ledger is where it
was when the fault arrived.

TODO: implement `decode`, `classify`, `TrapTable`, `handle` and `panic_record`.
"""

import machine

FAULT_WORDS = ("not_present", "read_only", "protected")
ACTIONS = ("resolved", "refused", "panic")
CAUSES = ("in_handler", "double_fault", "unhandled_exception", "unhandled_irq",
          "kernel_fault", "out_of_memory")


class TrapError(ValueError):
    """A trap table a kernel cannot be built on: a vector it does not have."""


def decode(error):
    """The error bits as the one word a handler is allowed to read.

    Bit 0 clear is `not_present`; bit 0 set with bit 1 set is `read_only` (the
    access was a write to a page the kernel may not write); bit 0 set with bit 1
    clear is `protected`. Bit 2 is context, not a reason, and never changes the
    word. An error code that is not an int is refused.
    """
    raise NotImplementedError("stage 4: implement decode()")



def classify(trap):
    """One trap as `{"vector", "name", "kind", "cpu", "addr"}`.

    `name` is the machine's word for the vector (`trap_name`, so a vector this
    machine does not have reads as `"unknown"`), and `kind` is `"exception"` for
    the five in `EXCEPTIONS`, `"irq"` for the one in `IRQS`, and `"unknown"`
    otherwise.
    """
    raise NotImplementedError("stage 4: implement classify()")



class TrapTable:
    """Which vectors have handlers: a vector and the name of what serves it."""

    def __init__(self, entries=None):
        """A table, empty unless `entries` maps vectors to handler names.

        Every entry is installed through the same door as `install`, so a table
        handed in already broken is refused at construction.
        """
        raise NotImplementedError("stage 4: implement TrapTable.__init__()")

    def install(self, vector, handler):
        """Give a vector a handler name, or refuse naming what is wrong.

        Refuses a vector this machine does not have, the double fault (vector 8),
        a handler name that is not a non-empty str, and a vector that already has
        one.
        """
        raise NotImplementedError("stage 4: implement TrapTable.install()")

    def handler(self, vector):
        """The name installed for a vector, or `None` when nobody serves it.

        A vector with no handler and a vector this machine does not have are both
        `None`: this is the question `handle` asks, and it is answered, not
        raised.
        """
        raise NotImplementedError("stage 4: implement TrapTable.handler()")

    def vectors(self):
        """The vectors this table serves, ascending, as a tuple."""
        raise NotImplementedError("stage 4: implement TrapTable.vectors()")



def handle(trap, table, *, mmu=None, pool=None, space=None, in_handler=False):
    """What this kernel does about one trap, as a decision rather than a jump.

    Returns `{"action", "vector", "name", "word", "frame", "reason", "cause"}`:
    one of `ACTIONS` in `action`, and exactly one of `frame` (a resolved page
    fault), `reason` (a refusal) and `cause` (a panic) filled in — the rest
    `None`. `in_handler` is the caller's statement that this trap arrived inside
    a handler, and it turns anything into a panic with cause `in_handler`.
    """
    raise NotImplementedError("stage 4: implement handle()")



def panic_record(trap, handler, cause):
    """The readable line a dead kernel leaves: vector, name, word, addr, cpu,
    handler and cause, in that order.

    `word` is what `decode` makes of the error bits for a page fault, and `None`
    for every other vector — an error code on a divide error is not a fault word
    and must not be read as one.
    """
    raise NotImplementedError("stage 4: implement panic_record()")
