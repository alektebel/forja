"""Queue & Workers From Scratch — stage 7: backpressure — refuse, shed or
block, and never lose a task.

SOLUTION. Stage 2 refuses at `capacity`, and stage 2's `submit` is the only door
into the queue, so a producer that keeps offering work fills every slot before
anything says no: by then the pool is holding work it cannot start for a long
time, and the burst that arrives at that point is either lost or left waiting
behind the whole backlog. This stage owns the early warning: a water mark that
is already in the pool spec (`high_water`) and three ways to hold the line when
`depth()` reaches it — refuse the arrival, shed the least valuable waiting task
to make room, or block the producer.

Every path is still data. `admit` reads `queue.depth()` and the injected clock,
writes stage 2's tables through stage 2 and stage 6, and returns the decision it
took; nothing sleeps and nothing moves the clock. `queue.decisions` and
`queue.events` grow at the moment the decision is taken, never in advance. The
invariant the whole stage rests on: **every input ends admitted, dead-lettered
with a reason, or refused naming why** — nothing is dropped in silence, and
nothing is queued past capacity.
"""

from collections.abc import Mapping

import fleet
import stage_02
import stage_03
import stage_06

#: The three ways to answer a queue that has reached its water mark. Refusing is
#: the default because it is the only one that costs nothing the queue had
#: already accepted: shedding gives up a task the queue took in, and blocking
#: makes the producer carry the wait.
POLICIES = ("refuse", "shed", "block")


class ShedError(fleet.QueueError):
    """The queue was asked to shed a task to make room and had none to give up.

    A separate type from `QueueFull` because the caller's next move is
    different: the queue is at its mark and every task it counts is *running*,
    so the producer has to wait for a completion rather than for a free slot in
    the backlog. Filing it as "full" hides the case where `shed` did nothing at
    all.
    """


class BlockedError(fleet.QueueError):
    """The queue is at its water mark and the producer is told to hold the task.

    Nothing is admitted: `block` is the policy that back-pressures by refusal,
    so the caller keeps the task and comes back later. It is not `QueueFull`,
    because the queue is not out of room — it is out of room it is willing to
    hand to *this* wave, and a caller that cannot tell the two apart cannot tell
    "come back in a moment" from "the queue is broken".
    """


def _label(source):
    """The name of the task a refusal is about, as well as it can be read.

    The refusal is written before any ticket exists, so this may not build one:
    it reads the `id` off whichever shape the caller handed in — a `Ticket`, a
    task spec, or a raw mapping — and answers `"?"` for a shape that carries no
    name. The *decided* path never needs it: an admitted task is named by the
    ticket stage 2's `submit` builds.
    """
    if isinstance(source, stage_02.Ticket):
        return source.task.id
    ident = getattr(source, "id", None)
    if isinstance(ident, str):
        return ident
    if isinstance(source, Mapping) and isinstance(source.get("id"), str):
        return source["id"]
    return "?"


def admit(queue, task, *, policy="refuse"):
    """One task offered to the queue: admitted, shed for, or refused.

    Below `queue.pool.high_water` every policy admits: the task goes in through
    stage 2's `submit`, which validates it and gives it its arrival number, and
    the decision recorded is `"admitted"`. At or above the mark the policy
    decides:

      * `refuse` raises `QueueFull` — the arrival keeps the task and retries,
        and nothing the queue already holds is touched;
      * `shed` gives up the *lowest-order* pending ticket (stage 3's order, so
        fewest priorities first and the later arrival of a tie) through stage
        6's `dead_letter` with the reason `"shed"`, then admits the new task,
        and returns `"shed"`;
      * `block` raises `BlockedError` and admits nothing, so the caller keeps
        the task.

    The mark is compared against `depth()` — the waiting *and* the running — on
    purpose: the queue's room is what the pool is holding, not what it has not
    started yet. An unknown policy is refused before anything is read or
    written, naming the three the queue knows, because a typo in a policy is a
    configuration mistake and must not read as "refused" or as "admitted".

    The counter is bumped where the decision is taken, so the run's record never
    shows an admission that did not happen. The order of the record is fixed:
    `submit` writes `submitted`, then the decision is written — `admitted`, or
    `dead_lettered` followed by `submitted` followed by `shed` (the room is
    made before the task goes in), or `refused`/`blocked` on its own, since a
    task that never entered has no `submitted` line.

    Returns the decision it performed: `"admitted"` or `"shed"`. The refusing
    policies raise rather than return, because there is no ticket to hand back.
    """
    if policy not in POLICIES:
        raise fleet.QueueError(
            "admit() does not know the policy %r: the policies are %s"
            % (policy, ", ".join(repr(name) for name in POLICIES)))
    now = queue.clock.now()
    name = _label(task)
    if queue.depth() < queue.pool.high_water:
        ticket = queue.submit(task)
        queue.decisions["admitted"] += 1
        queue.events.append({"at": now, "kind": "admitted",
                             "task": ticket.task.id, "policy": policy})
        return "admitted"
    if policy == "refuse":
        queue.decisions["refused"] += 1
        queue.events.append({"at": now, "kind": "refused", "task": name,
                             "reason": "high_water", "policy": policy})
        raise stage_02.QueueFull(
            "pool %r is at or above its high water %d: depth %d, refusing %r"
            % (queue.pool.id, queue.pool.high_water, queue.depth(), name))
    if policy == "shed":
        waiting = stage_03.reorder(queue)
        if not waiting:
            queue.decisions["refused"] += 1
            queue.events.append({"at": now, "kind": "refused", "task": name,
                                 "reason": "nothing_to_shed", "policy": policy})
            raise ShedError(
                "pool %r is at or above its high water %d with nothing pending "
                "to give up (depth %d is all in flight): %r cannot be admitted "
                "by shedding"
                % (queue.pool.id, queue.pool.high_water, queue.depth(), name))
        victim = waiting[-1]
        stage_06.dead_letter(queue, victim, "shed")
        ticket = queue.submit(task)
        queue.decisions["shed"] += 1
        queue.events.append({"at": now, "kind": "shed", "task": victim.task.id,
                             "admitted": ticket.task.id, "policy": policy})
        return "shed"
    queue.decisions["blocked"] += 1
    queue.events.append({"at": now, "kind": "blocked", "task": name,
                         "reason": "high_water", "policy": policy})
    raise BlockedError(
        "pool %r is at or above its high water %d: depth %d, blocking %r "
        "rather than letting it grow past the mark"
        % (queue.pool.id, queue.pool.high_water, queue.depth(), name))
