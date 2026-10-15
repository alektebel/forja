"""OS From Scratch — stage 08: Two CPUs, and the critical section nobody guarded.

One CPU makes every kernel mistake look like a kernel mistake: a step either
happened or it did not, and the order of a program's own steps is the order it
wrote them in. Two CPUs break that assumption without breaking anything else.
`load`, `add (one)`, `store` over a shared counter is correct code — each of the
three steps is — and two CPUs that interleave it lose an update every time: both
load the old value, both add one, both store it, and one of the two increments is
gone. Nothing raised, nothing faulted, no table is short a frame. The counter is
just wrong, and it is wrong *deterministically* here, because in this course the
interleaving is not a race: it is a schedule the caller hands over.

That is the whole design of this stage. A real SMP kernel cannot grade a spin,
because a spin is timing, and timing is not something a check can pin. So the
schedule is data — the frozen `(cpu, op, name)` steps of §2.4 — and the interesting
operation is `serialize`: walk the steps, and when a CPU reaches a lock somebody
else holds, *defer* that CPU's every step, rather than letting it spin, until the
holder releases. A spinning CPU and a deferred one reach the same state; only one
of the two can be written into a check.

DESIGN DECISION — why does a blocked CPU get *deferred* instead of spinning?
Because a spin is the one thing this course cannot check: the moment a spinning
CPU finally takes the lock is a property of time, and this machine has no time.
Deferring replaces the spin with a rule — this CPU's remaining steps happen at the
moment the lock is released — and a rule is the same on every machine.

DESIGN DECISION — why does the *whole* tail of a blocked CPU defer, not just its
`lock` step?
Because a CPU that is spinning has not advanced at all. Deferring only the `lock`
would let the following `load`, `add`, `store` run early, and the counter would
come out right for the wrong reason, hiding the very bug this stage exists to show.

DESIGN DECISION — why is a recursive acquire refused rather than allowed?
An `acquire` by the CPU that already holds the lock is either a nested critical
section, which needs a count and a release policy, or a CPU about to deadlock
against itself. The kernel cannot read which one the caller meant, so it refuses
instead of picking a reentrancy policy silently.

DESIGN DECISION — why does the cycle come back closed, starting at the lowest CPU?
A cycle written as a path differs by where the walk began, so a check that pinned
it would be pinning the walk and not the deadlock. The front door is the lowest
CPU id and the last element repeats the first, which makes a cycle of one — a CPU
waiting for the lock it already holds — read as `(5, 5)`.

DESIGN DECISION — why is a lock held across a `yield` a finding, and one held
across a `load` not?
The danger is not that the lock is held, it is that the holder has stopped running.
A `load` is the holder making progress; a `yield` hands the CPU over with the lock
still in hand, which is the big-kernel-lock bug the audit exists to name — the same
problem, at the end of the trace, for the locks nobody ever released.
"""

import machine

OPS = ("load", "add", "store", "lock", "unlock", "yield")

_LOCK_OPS = ("lock", "unlock")


class LockError(ValueError):
    """A lock or a schedule used in a way no kernel in this course allows."""


def _lock_name(name):
    """A lock name: a non-empty `str`, or a refusal saying what arrived."""
    if not isinstance(name, str) or not name:
        raise LockError("a lock name must be a non-empty str, not %r" % (name,))
    return name


def _step(raw):
    """One frozen `(cpu, op, name)` step, or a refusal naming the offender."""
    if not isinstance(raw, tuple) or len(raw) != 3:
        raise LockError(
            "a schedule step is a 3-tuple (cpu, op, name), not %r" % (raw,))
    cpu, op, name = raw
    if op not in OPS:
        near = machine._near(op, OPS)
        hint = " (did you mean %r?)" % (near,) if near else ""
        raise LockError("no op named %r%s" % (op, hint))
    if op in _LOCK_OPS:
        _lock_name(name)
    return (cpu, op, name)


class Lock:
    """One owner, a queue of waiters, and an acquire that never spins."""

    def __init__(self, name):
        self._name = _lock_name(name)
        self._owner = None
        self._waiting = []

    def acquire(self, cpu):
        """Take the lock for `cpu`, or say that it is held and who holds it."""
        if self._owner is not None and self._owner == cpu:
            raise LockError("lock %r is already held by cpu %d: no recursive "
                            "acquire" % (self._name, cpu))
        if self._owner is None:
            self._owner = cpu
            return {"cpu": cpu, "acquired": True, "owner": self._owner,
                    "waiting": self.waiting()}
        if cpu not in self._waiting:
            self._waiting.append(cpu)
        return {"cpu": cpu, "acquired": False, "owner": self._owner,
                "waiting": self.waiting()}

    def release(self, cpu):
        """Give the lock up, handing it to the first waiter, if there is one."""
        if self._owner is None:
            raise LockError("lock %r is free: cpu %d cannot release it"
                            % (self._name, cpu))
        if self._owner != cpu:
            raise LockError("lock %r is held by cpu %d, not cpu %d"
                            % (self._name, self._owner, cpu))
        self._owner = self._waiting.pop(0) if self._waiting else None
        return {"cpu": cpu, "owner": self._owner, "waiting": self.waiting()}

    def owner(self):
        """The CPU that holds the lock, or `None` when it is free."""
        return self._owner

    def waiting(self):
        """The CPUs queued on the lock, in the order they were refused it."""
        return tuple(self._waiting)


def serialize(schedule):
    """The effective order of a schedule, and how much each CPU deferred."""
    order = []
    acquired = {}
    deferred = {}
    locks = {}
    pending = {}
    blocked = []

    def lock_of(name):
        lock = locks.get(name)
        if lock is None:
            lock = locks[name] = Lock(name)
        return lock

    def take(cpu, name):
        lock_of(name).acquire(cpu)
        holders = acquired.get(name)
        if holders is None:
            holders = acquired[name] = []
        holders.append(cpu)

    def replay(cpu):
        queue = pending[cpu]
        while queue:
            one = queue[0]
            if one[1] == "lock" and lock_of(one[2]).owner() is not None:
                return
            queue.pop(0)
            if one[1] == "lock":
                take(one[0], one[2])
            elif one[1] == "unlock":
                lock_of(one[2]).release(one[0])
            order.append(one)
        del pending[cpu]
        blocked.remove(cpu)

    def drain():
        while True:
            progress = False
            for cpu in tuple(blocked):
                if cpu not in pending:
                    continue
                head = pending[cpu][0]
                if head[1] == "lock" and lock_of(head[2]).owner() is not None:
                    continue
                replay(cpu)
                progress = True
            if not progress:
                return

    for raw in schedule:
        cpu, op, name = step = _step(raw)
        if cpu not in deferred:
            deferred[cpu] = 0
        if cpu in pending:
            pending[cpu].append(step)
            deferred[cpu] += 1
            continue
        if op == "lock" and lock_of(name).owner() is not None:
            pending[cpu] = [step]
            blocked.append(cpu)
            deferred[cpu] += 1
            continue
        if op == "lock":
            take(cpu, name)
        elif op == "unlock":
            lock_of(name).release(cpu)
        order.append(step)
        drain()

    return {"order": tuple(order), "deferred": deferred,
            "acquired": {name: tuple(cpus) for name, cpus in acquired.items()}}


def run_schedule(schedule):
    """The lost update: the counter the schedule scores, and how it got there."""
    effective = serialize(schedule)
    counter = 0
    registers = {}
    for cpu, op, name in effective["order"]:
        if op == "load":
            registers[cpu] = counter
        elif op == "add":
            registers[cpu] = registers.get(cpu, 0) + 1
        elif op == "store":
            counter = registers.get(cpu, 0)
    return {"counter": counter, "order": effective["order"],
            "deferred": effective["deferred"]}


def detect_deadlock(waits):
    """The cycle in a set of `(cpu, holding, waiting_for)` triples, or `None`."""
    triples = []
    for wait in waits:
        if not isinstance(wait, tuple) or len(wait) != 3:
            raise LockError(
                "a wait is a 3-tuple (cpu, holding, waiting_for), not %r"
                % (wait,))
        triples.append(wait)
    holds = {}
    for cpu, holding, waiting_for in triples:
        if holding is not None:
            holds[holding] = cpu
    edges = {}
    for cpu, holding, waiting_for in triples:
        if waiting_for is not None and waiting_for in holds:
            edges.setdefault(cpu, holds[waiting_for])
    for start in sorted(edges):
        seen = {}
        path = []
        node = start
        while node is not None and node in edges and node not in seen:
            seen[node] = len(path)
            path.append(node)
            node = edges[node]
        if node in seen:
            cycle = path[seen[node]:]
            lowest = min(cycle)
            pivot = cycle.index(lowest)
            cycle = cycle[pivot:] + cycle[:pivot]
            return tuple(cycle) + (lowest,)
    return None


def audit_holds(trace):
    """Every `(cpu, lock)` held across a `yield`, and every lock never released."""
    holds = {}
    findings = []
    noted = set()

    def note(cpu, name):
        if (cpu, name) not in noted:
            noted.add((cpu, name))
            findings.append((cpu, name))

    for raw in trace:
        cpu, op, name = _step(raw)
        if op == "lock":
            held = holds.setdefault(cpu, [])
            if name in held:
                raise LockError("cpu %d already holds lock %r: no recursive "
                                "acquire" % (cpu, name))
            held.append(name)
        elif op == "unlock":
            held = holds.get(cpu, ())
            if name not in held:
                raise LockError("cpu %d does not hold lock %r, so it cannot "
                                "release it" % (cpu, name))
            held.remove(name)
        elif op == "yield":
            for lock in tuple(holds.get(cpu, ())):
                note(cpu, lock)
    for cpu, held in holds.items():
        for lock in held:
            note(cpu, lock)
    return tuple(findings)
