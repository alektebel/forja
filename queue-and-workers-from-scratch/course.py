"""Queue & Workers From Scratch — course manifest.

Ten graded stages that build the thing an agent platform runs on: a task queue
and a worker pool that admit work, order it, bound how much of it runs at once,
take work back from a worker that dies holding it, retry what failed, give up on
what will never succeed, hold the line when the queue is full, and report what
happened in a record that two identical runs agree on to the byte.

The thesis of the whole course is one sentence, and every stage's check asserts
it: THE SCHEDULER IS A DATA STRUCTURE, NOT A THREAD POOL. There is no thread and
no wall clock anywhere in it. The clock is injected, the workers are pure
functions of `(task, attempt)`, and the scheduler is the only thing that moves
time forward — which is why a run is deterministic, why a failure is a value
rather than a race, and why two runs of the same inputs produce the same bytes.

The clock, the two read-only catalogues (`TASKS`, `POOLS`), the fixture bags and
the nine scripted workers are provided (`fleet.py`, complete and proven); the
exercise is the queue itself. No network, no `time`, no `threading`, no
`asyncio`, no unseeded randomness and no module-level mutable state: ticks are
counted, not timed.

    python3 codecraft/cli.py run queue-and-workers-from-scratch
"""

from codecraft.api import stage

TITLE = "Queue & Workers From Scratch"
DESCRIPTION = ("A deterministic task queue and worker pool from scratch on a "
               "provided clock and provided scripted workers: parse a task and "
               "a pool without letting a typo run as a default, admit work and "
               "refuse instead of growing, order by priority with arrival as "
               "the tie-break, check the concurrency limit before the worker "
               "starts, take a task back from a worker that dies holding its "
               "lease, retry on the injected clock and dead-letter what will "
               "never succeed, choose between refusing, shedding and blocking "
               "without ever losing a task, age a tenant that would starve, "
               "count a record that agrees with the log it summarises, and "
               "finish with two runs of the same inputs producing identical "
               "bytes.")
LEVEL = "intermediate"
ORDER = 17

# --- the checks. Each one is self-contained: its fixtures are nested
# inside it because `course.py` is one namespace for ten stages.

import json
import os
import shutil
import sys
import tempfile


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    def _task_fields(task):
        """The five task fields, in the frozen order."""
        return (task.id, task.ticks, task.priority, task.tenant, task.attempts)

    def _pool_fields(pool):
        """The five pool fields, in the frozen order."""
        return (pool.id, pool.max_concurrency, pool.capacity, pool.high_water,
                pool.low_water)

    def _refusal(what, error, call, *needles):
        """`call()` must raise `error`, and the text must name every needle.

        A mistake that is accepted, or refused without naming what and where, is the
        same failure: the reader cannot see what they spelled wrong.
        """
        try:
            accepted = call()
        except error as exc:
            text = str(exc)
            for needle in needles:
                assert needle in text, (
                    "the refusal of %s did not name %r: %r" % (what, needle, text))
            return text
        raise AssertionError("the mistake of %s was accepted as %r" % (what, accepted))

    import dataclasses
    import fleet
    import stage_01 as s

    reject = fleet.QueueError

    # --- the frozen interface nine later stages import ----------------------
    assert s.TASK_KEYS == ("id", "ticks", "priority", "tenant", "attempts"), (
        "the task key list is not the frozen one: %r" % (s.TASK_KEYS,))
    assert s.POOL_KEYS == ("id", "max_concurrency", "capacity", "high_water",
                           "low_water"), (
        "the pool key list is not the frozen one: %r" % (s.POOL_KEYS,))
    assert s.TASK_DEFAULTS == {"ticks": 3, "priority": 5, "tenant": "batch",
                               "attempts": 3}, (
        "the task defaults are not the frozen ones: %r" % (s.TASK_DEFAULTS,))
    assert s.POOL_DEFAULTS == {"max_concurrency": 1, "capacity": 4,
                               "high_water": 3, "low_water": 1}, (
        "the pool defaults are not the frozen ones: %r" % (s.POOL_DEFAULTS,))
    assert [f.name for f in dataclasses.fields(s.Task)] == [
        "id", "ticks", "priority", "tenant", "attempts"], (
        "the Task field order is not the frozen one: %r"
        % ([f.name for f in dataclasses.fields(s.Task)],))
    assert [f.name for f in dataclasses.fields(s.Pool)] == [
        "id", "max_concurrency", "capacity", "high_water", "low_water"], (
        "the Pool field order is not the frozen one: %r"
        % ([f.name for f in dataclasses.fields(s.Pool)],))

    probe = s.parse_task({"id": "probe"})
    probe_pool = s.parse_pool({"id": "probe"})
    assert dataclasses.is_dataclass(probe) and dataclasses.is_dataclass(probe_pool), (
        "a spec is not a dataclass, so its shape is not the frozen one: "
        "task=%r pool=%r" % (probe, probe_pool))
    try:
        probe.ticks = 4
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError(
            "the task spec is mutable, so a queued ticket's cost can be edited "
            "in place: %r" % (probe,))
    try:
        probe_pool.max_concurrency = 2
    except dataclasses.FrozenInstanceError:
        pass
    else:
        raise AssertionError(
            "the pool spec is mutable, so a queue's capacity can move under it: "
            "%r" % (probe_pool,))

    # --- the provided catalogue round-trips, field for field ---------------
    for task_id in sorted(fleet.TASKS):
        spec = fleet.TASKS[task_id]
        task = s.parse_task(spec)
        expected = (task_id, spec["ticks"], spec["priority"], spec["tenant"], 3)
        assert _task_fields(task) == expected, (
            "the task %r parsed to %r, not %r" % (task_id, _task_fields(task),
                                                  expected))
        for name, value in (("ticks", task.ticks), ("priority", task.priority),
                            ("attempts", task.attempts)):
            assert type(value) is int, (
                "the %s of task %r is not an int count: %r"
                % (name, task_id, value))

    # --- the defaults are materialised, not implied ------------------------
    bare = s.parse_task({"id": "bare"})
    assert _task_fields(bare) == ("bare", 3, 5, "batch", 3), (
        "a task that spelled no field did not get the frozen defaults "
        "materialised: %r" % (_task_fields(bare),))
    bare_pool = s.parse_pool({"id": "bare"})
    assert _pool_fields(bare_pool) == ("bare", 1, 4, 3, 1), (
        "a pool that spelled no field did not get the frozen defaults "
        "materialised: %r" % (_pool_fields(bare_pool),))
    spelled = s.parse_task({"id": "spelled", "ticks": 9, "tenant": "edge"})
    assert _task_fields(spelled) == ("spelled", 9, 5, "edge", 3), (
        "the spelled fields did not survive the defaults being materialised "
        "around them: %r" % (_task_fields(spelled),))

    # --- a typo is refused, never defaulted --------------------------------
    _refusal("a task that is not a mapping", reject, lambda: s.parse_task(5),
             "mapping")
    _refusal("a task spelled as a string", reject, lambda: s.parse_task("render"),
             "mapping")
    _refusal("a typo'd task key", reject,
             lambda: s.parse_task({"id": "render", "tickz": 30}),
             "tickz", "ticks")
    _refusal("a task with no id", reject, lambda: s.parse_task({}), "id")
    _refusal("an empty task id", reject, lambda: s.parse_task({"id": ""}),
             "id", "empty")
    _refusal("a non-string task id", reject, lambda: s.parse_task({"id": 5}),
             "id", "str")

    # --- a count is an int and never a bool, a string, a float or negative --
    for what, bad in (("a string", {"id": "x", "ticks": "3"}),
                      ("a bool", {"id": "x", "ticks": True}),
                      ("a float", {"id": "x", "ticks": 2.5}),
                      ("a negative", {"id": "x", "ticks": -1})):
        _refusal("%s ticks" % (what,), reject, lambda bad=bad: s.parse_task(bad),
                 "ticks")
    for what, bad in (("a bool", {"id": "x", "priority": True}),
                      ("a string", {"id": "x", "priority": "5"}),
                      ("a float", {"id": "x", "priority": 5.5}),
                      ("a negative", {"id": "x", "priority": -5})):
        _refusal("%s priority" % (what,), reject, lambda bad=bad: s.parse_task(bad),
                 "priority")
    for what, bad in (("a bool", {"id": "x", "attempts": False}),
                      ("a string", {"id": "x", "attempts": "3"}),
                      ("a float", {"id": "x", "attempts": 1.5}),
                      ("a negative", {"id": "x", "attempts": -1})):
        _refusal("%s attempts" % (what,), reject, lambda bad=bad: s.parse_task(bad),
                 "attempts")
    for what, bad in (("a number", {"id": "x", "tenant": 5}),
                      ("None", {"id": "x", "tenant": None}),
                      ("a bool", {"id": "x", "tenant": True})):
        _refusal("a tenant that is %s" % (what,), reject,
                 lambda bad=bad: s.parse_task(bad), "tenant")

    # --- the pool's own guards --------------------------------------------
    _refusal("a pool that is not a mapping", reject, lambda: s.parse_pool("small"),
             "mapping")
    _refusal("a typo'd pool key", reject,
             lambda: s.parse_pool({"id": "small", "lease": 8}),
             "lease", "capacity")
    _refusal("a pool with no id", reject, lambda: s.parse_pool({}), "id")
    _refusal("a pool that runs nothing", reject,
             lambda: s.parse_pool({"id": "p", "max_concurrency": 0}),
             "max_concurrency")
    _refusal("a bool max_concurrency", reject,
             lambda: s.parse_pool({"id": "p", "max_concurrency": True}),
             "max_concurrency")
    _refusal("water marks above the capacity", reject,
             lambda: s.parse_pool({"id": "p", "capacity": 2}),
             "low_water", "high_water", "capacity")
    _refusal("a low water mark above the high one", reject,
             lambda: s.parse_pool({"id": "p", "capacity": 4, "high_water": 3,
                                   "low_water": 9}),
             "low_water", "high_water")
    _refusal("a high water mark above the capacity", reject,
             lambda: s.parse_pool({"id": "p", "capacity": 4, "high_water": 9,
                                   "low_water": 1}),
             "low_water", "high_water")
    _refusal("a negative capacity", reject,
             lambda: s.parse_pool({"id": "p", "capacity": -1}),
             "capacity")

    # --- a task list: order kept, a duplicated id named --------------------
    parsed = s.parse_tasks([fleet.TASKS["render"], fleet.TASKS["index"],
                            fleet.TASKS["audit"]])
    assert isinstance(parsed, tuple), (
        "parse_tasks returned a %s, not a tuple: %r"
        % (type(parsed).__name__, parsed))
    assert [_task_fields(task)[0] for task in parsed] == ["render", "index", "audit"], (
        "the task list came back in a different order than it was given: %r"
        % ([task.id for task in parsed],))
    assert [_task_fields(task) for task in parsed] == [
        ("render", 3, 5, "batch", 3), ("index", 7, 1, "batch", 3),
        ("audit", 5, 5, "compliance", 3)], (
        "a parsed task list lost a field: %r" % ([_task_fields(t) for t in parsed],))
    _refusal("a duplicated task id", reject,
             lambda: s.parse_tasks([{"id": "dup"}, {"id": "dup"}]), "dup")

    # --- the canonical text: one spec, one text, whatever the spelling -----
    render_text = ('{"attempts":3,"id":"render","priority":5,"tenant":"batch",'
                   '"ticks":3}')
    for spelling in ({"id": "render"},
                     {"ticks": 3, "priority": 5, "tenant": "batch",
                      "attempts": 3, "id": "render"},
                     {"priority": 5, "id": "render", "attempts": 3,
                      "tenant": "batch", "ticks": 3},
                     s.parse_task({"id": "render"}),
                     fleet.make_task("render"),
                     fleet.TASKS["render"]):
        got = s.canonical_task(spelling)
        assert got == render_text, (
            "two spellings of one task produced two canonical texts, so the text "
            "is not deterministic: %r from %r" % (got, spelling))
    notify_text = ('{"attempts":3,"id":"notify","priority":9,'
                   '"tenant":"interactive","ticks":1}')
    assert s.canonical_task(s.parse_task(fleet.TASKS["notify"])) == notify_text, (
        "the canonical text of task 'notify' is not its own fields sorted and "
        "compacted: %r" % (s.canonical_task(s.parse_task(fleet.TASKS["notify"])),))
    family_text = ('{"attempts":3,"id":"train","priority":3,"tenant":"batch",'
                   '"ticks":12}')
    assert s.canonical_task(fleet.TASKS["train"]) == family_text, (
        "the canonical text of task 'train' is not its own fields sorted and "
        "compacted: %r" % (s.canonical_task(fleet.TASKS["train"]),))
    _refusal("a typo'd key in a canonical task", reject,
             lambda: s.canonical_task({"id": "render", "tickz": 1}), "tickz")

    small_text = ('{"capacity":4,"high_water":3,"id":"small","low_water":1,'
                  '"max_concurrency":1}')
    for spelling in ({"id": "small"}, fleet.POOLS["small"],
                     s.parse_pool({"id": "small"}), fleet.make_pool("small"),
                     {"low_water": 1, "max_concurrency": 1, "high_water": 3,
                      "capacity": 4, "id": "small"}):
        got = s.canonical_pool(spelling)
        assert got == small_text, (
            "two spellings of one pool produced two canonical texts, so the text "
            "is not deterministic: %r from %r" % (got, spelling))
    wide_text = ('{"capacity":16,"high_water":12,"id":"wide","low_water":4,'
                 '"max_concurrency":4}')
    assert s.canonical_pool(fleet.POOLS["wide"]) == wide_text, (
        "the canonical text of pool 'wide' is not its own fields sorted and "
        "compacted: %r" % (s.canonical_pool(fleet.POOLS["wide"]),))
    _refusal("a pool whose marks are out of order in the canonical text", reject,
             lambda: s.canonical_pool({"id": "p", "capacity": 2}),
             "low_water", "high_water")

    print("check_01: the task and the pool spec round-trip, a typo is refused "
          "instead of defaulted, every count is an int, and the canonical text "
          "is one text per spec")

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    import dataclasses

    import fleet
    import stage_02 as s

    def field_names(cls):
        return [f.name for f in dataclasses.fields(cls)]

    def required(cls):
        return [f.name for f in dataclasses.fields(cls)
                if f.default is dataclasses.MISSING
                and f.default_factory is dataclasses.MISSING]

    # ---- §3's frozen state, which eight later stages read -------------------

    assert field_names(s.Ticket) == [
        "seq", "task", "submitted_at", "attempts", "ready_at"], (
        "Ticket's fields are not §3's, so every later stage reads the wrong "
        "names: %r" % (field_names(s.Ticket),))
    assert required(s.Ticket) == [
        "seq", "task", "submitted_at", "attempts"], (
        "Ticket defaulted a field §3 requires: an attempt count and an arrival "
        "are counted, never assumed: %r" % (required(s.Ticket),))
    ready_default = dataclasses.fields(s.Ticket)[-1].default
    assert ready_default is None, (
        "Ticket.ready_at must default to None, i.e. 'due now'; a numeric "
        "default makes a fresh ticket a delayed one: %r" % (ready_default,))

    assert field_names(s.Flight) == [
        "ticket", "attempt", "started_at", "finishes_at", "deadline_at"], (
        "Flight's fields are not §3's: %r" % (field_names(s.Flight),))
    assert required(s.Flight) == field_names(s.Flight), (
        "Flight defaulted a field §3 requires: a flight must always name its "
        "three tick marks, so a lease-less flight is not the same as an "
        "unfinished one: %r" % (required(s.Flight),))

    assert field_names(s.DeadLetter) == ["task", "attempts", "reason", "at"], (
        "DeadLetter's fields are not §3's, so a dead letter without its reason "
        "or its tick would still be constructible: %r" % (field_names(s.DeadLetter),))
    assert required(s.DeadLetter) == field_names(s.DeadLetter), (
        "DeadLetter defaulted a field §3 requires: %r" % (required(s.DeadLetter),))

    assert field_names(s.Queue) == [
        "pool", "clock", "pending", "in_flight", "dead", "events", "sequence",
        "decisions"], (
        "Queue's fields are not §3's, so later stages read the wrong table: %r"
        % (field_names(s.Queue),))
    assert not [name for name in field_names(s.Queue)[1:]
                if name in required(s.Queue)], (
        "Queue(pool) is not a fresh empty queue: §3 gives every field but pool a "
        "default, but these have none: %r" % (required(s.Queue),))

    for name, make, attribute in (
            ("Ticket", lambda: s.Ticket(0, None, 0, 0), "attempts"),
            ("Flight", lambda: s.Flight(s.Ticket(0, None, 0, 0), 1, 0, 3, None), "attempt"),
            ("DeadLetter", lambda: s.DeadLetter(None, 1, "poison", 0), "reason"),
            ("Queue", lambda: s.Queue(fleet.make_pool("small")), "sequence")):
        record = make()
        try:
            setattr(record, attribute, 99)
        except dataclasses.FrozenInstanceError:
            continue
        raise AssertionError(
            "%s is not a frozen record: a caller that edits the ticket it was "
            "handed back rewrites history for every stage that reads it "
            "(set %s = 99 and it stuck)" % (name, attribute))

    assert isinstance(s.EVENT_KINDS, tuple) and s.EVENT_KINDS == (
        "submitted", "refused", "admitted", "shed", "blocked", "started",
        "succeeded", "failed", "died", "retried", "dead_lettered", "stopped"), (
        "EVENT_KINDS is not §3's twelve kinds in order, so this queue's events "
        "and stage 9's record disagree about the log: %r" % (s.EVENT_KINDS,))

    assert issubclass(s.QueueFull, fleet.QueueError), (
        "QueueFull is not a QueueError, so a caller cannot tell the queue's "
        "refusals from a bug: %r" % (s.QueueFull.__mro__,))

    # ---- a fresh queue: empty, zeroed, and nobody else's state --------------

    pool = fleet.make_pool("small")            # capacity 4, high_water 3
    clock = fleet.Clock()
    queue = s.Queue(pool, clock=clock)

    assert queue.pool.id == "small" and queue.pool.capacity == 4, (
        "Queue did not keep the pool it was handed: %r" % (queue.pool,))
    assert queue.clock is clock, (
        "Queue ignored the clock it was handed and kept one of its own, so the "
        "run's time is not the caller's: %r" % (queue.clock,))
    assert (queue.depth(), queue.queued(), queue.is_full()) == (0, 0, False), (
        "a fresh queue is not empty: depth %d, queued %d, is_full %r"
        % (queue.depth(), queue.queued(), queue.is_full()))
    assert queue.pending == [] and queue.in_flight == {} and queue.dead == [], (
        "a fresh queue's tables are not empty: pending=%r in_flight=%r dead=%r"
        % (queue.pending, queue.in_flight, queue.dead))
    assert queue.events == [] and queue.sequence == 0, (
        "a fresh queue has no history: events=%r sequence=%r"
        % (queue.events, queue.sequence))
    assert queue.decisions == {
        "admitted": 0, "refused": 0, "shed": 0, "blocked": 0, "limit_hits": 0}, (
        "queue.decisions is not §3's five counters zero-filled: %r" % (queue.decisions,))
    assert list(queue.decisions) == [
        "admitted", "refused", "shed", "blocked", "limit_hits"], (
        "queue.decisions does not carry §3's keys in order: %r" % (list(queue.decisions),))

    twin = s.Queue(pool)
    second_twin = s.Queue(pool)
    assert queue.clock is not twin.clock and second_twin.clock is not twin.clock, (
        "two queues built without a clock were handed one shared clock, so a "
        "tick on one run's clock moves the other run's time and two runs of the "
        "same input stop being the same run: %r" % (twin.clock,))
    twin.clock.tick(5)
    assert queue.clock.now() == 0 and second_twin.clock.now() == 0, (
        "ticking one default queue's clock moved another queue's reading to %d"
        % (second_twin.clock.now(),))
    for table in ("pending", "in_flight", "dead", "events", "decisions"):
        assert getattr(queue, table) is not getattr(twin, table), (
            "two queues share one %s table, so a task in one is a task in the "
            "other" % (table,))

    # ---- submit: one arrival, one ticket, one line, no clock moved ---------

    clock.tick(3)                       # the caller moves the clock, not submit
    first = queue.submit(fleet.make_task("render"))
    assert isinstance(first, s.Ticket), (
        "submit did not return the ticket it filed, so a caller cannot name the "
        "arrival it just made: %r" % (first,))
    assert queue.pending[-1] is first and queue.queued() == 1, (
        "the admitted ticket is not the last one waiting: pending=%r"
        % (queue.pending,))
    assert queue.in_flight == {}, (
        "submit filed the task as running before any worker saw it: in_flight=%r"
        % (queue.in_flight,))
    assert (first.seq, first.attempts, first.submitted_at) == (0, 0, 3), (
        "the first ticket must be seq 0, 0 attempts and stamped at the clock "
        "(3), got %r" % ((first.seq, first.attempts, first.submitted_at),))
    assert first.ready_at is None, (
        "an admitted ticket is due immediately; ready_at %r makes it a delayed "
        "one" % (first.ready_at,))
    assert first.task.id == "render", (
        "the ticket does not name the task that was submitted: %r"
        % (first.task.id,))
    assert getattr(first.task, "attempts", None) == 3, (
        "the task was filed without going through stage 1: a raw task bag has "
        "no attempt budget, so stage 6 would retry it forever, got %r"
        % (first.task,))
    assert queue.sequence == 1, (
        "the arrival counter did not advance on an admission: %r" % (queue.sequence,))
    assert clock.ticks == 3, (
        "submit moved the clock: only the scheduler ticks it, ticks=%d"
        % (clock.ticks,))
    assert len(queue.events) == 1, (
        "one admission must leave exactly one line: %r" % (queue.events,))
    line = queue.events[0]
    assert {"at", "kind", "task"} <= set(line), (
        "the record line is not {'at', 'kind', 'task', ...}: %r" % (line,))
    assert (line["at"], line["kind"], line["task"]) == (3, "submitted", "render"), (
        "the submitted line must read at=3, kind=submitted, task=render: %r"
        % (line,))

    # ---- depth counts the running tasks; the counter is not a length -------

    running = s.Queue(pool)
    one = running.submit(fleet.make_task("render"))
    two = running.submit({"id": "index", "ticks": 7, "priority": 1, "tenant": "batch"})
    assert (one.seq, two.seq, running.sequence) == (0, 1, 2), (
        "the arrival counter is the queue's own and starts at 0: seqs %r, "
        "sequence %r" % ([one.seq, two.seq], running.sequence))
    running.pending.remove(two)
    running.in_flight["index"] = s.Flight(two, 1, running.clock.now(), 7, None)
    assert (running.depth(), running.queued()) == (2, 1), (
        "depth counts what the queue holds, waiting plus running: depth %d, "
        "queued %d" % (running.depth(), running.queued()))
    three = running.submit(fleet.make_task("notify"))
    assert three.seq == 2, (
        "the arrival counter is not len(pending): one ticket moved to the "
        "in-flight table, and the next arrival is seq %d instead of 2"
        % (three.seq,))
    assert running.sequence == 3, (
        "the arrival counter did not advance once per admission: %r"
        % (running.sequence,))
    before = running.depth()
    running.dead.append(s.DeadLetter(three.task, 3, "poison", 4))
    assert running.depth() == before, (
        "depth counted the dead letters: a task the queue gave up on is not "
        "queued, depth %d was %d" % (running.depth(), before))

    # ---- is_full is depth >= capacity, not the water mark and not > --------

    roomy = s.Queue(fleet.make_pool("small"))          # capacity 4, high_water 3
    for task_id in ("render", "index", "notify"):
        roomy.submit(fleet.make_task(task_id))
    assert (roomy.depth(), roomy.is_full()) == (3, False), (
        "is_full refused at the high water mark (3) instead of the capacity "
        "(4): depth %d, is_full %r" % (roomy.depth(), roomy.is_full()))
    roomy.submit(fleet.make_task("audit"))
    assert (roomy.depth(), roomy.is_full()) == (4, True), (
        "is_full must be depth() >= capacity: at exactly capacity (4) the queue "
        "is full, depth %d, is_full %r" % (roomy.depth(), roomy.is_full()))

    # ---- a full queue refuses: QueueFull, a refused line, nothing moved ----

    tiny = s.Queue(fleet.make_pool("small", capacity=1, high_water=1, low_water=1))
    kept = tiny.submit(fleet.make_task("render"))
    events_before = list(tiny.events)
    failure = None
    try:
        tiny.submit(fleet.make_task("audit"))
    except s.QueueFull as refused:
        failure = refused
    except fleet.QueueError as wrong:
        raise AssertionError(
            "a full queue raised %s instead of QueueFull, so a caller that "
            "wants to retry cannot tell 'full, come back later' from 'that is "
            "not a task, never': %r" % (type(wrong).__name__, str(wrong)))
    assert failure is not None, (
        "a full queue did not refuse: it grew to depth %d (capacity 1), or it "
        "dropped the task in silence" % (tiny.depth(),))
    message = str(failure)
    assert "small" in message and "1" in message and "audit" in message, (
        "the refusal must name the pool, the capacity and the task it turned "
        "away: %r" % (message,))
    assert tiny.pending == [kept] and tiny.queued() == 1 and tiny.depth() == 1, (
        "the refusal changed the queue it refused: pending=%r depth=%d"
        % (tiny.pending, tiny.depth()))
    assert tiny.sequence == 1, (
        "the refusal spent an arrival number: the counter is at %d after one "
        "admission" % (tiny.sequence,))
    assert len(tiny.events) == len(events_before) + 1, (
        "the refusal left no line (or left more than one): the record must say "
        "the task was offered and turned away, events=%r" % (tiny.events,))
    refused_line = tiny.events[-1]
    assert (refused_line["kind"], refused_line["task"]) == ("refused", "audit"), (
        "the refusal line must read kind=refused, task=audit: %r" % (refused_line,))
    assert refused_line["at"] == tiny.clock.now(), (
        "the refusal line is stamped at %r, not at the clock (%r)"
        % (refused_line["at"], tiny.clock.now()))

    tiny.pending.clear()                       # the task finished; room again
    again = tiny.submit(fleet.make_task("audit"))
    assert again.seq == 1, (
        "the arrival counter was reset or moved by a refusal: the next "
        "admission is seq %d, not 1" % (again.seq,))

    # ---- a raw task goes through stage 1, or it does not go in at all ------

    fresh = s.Queue(pool)
    for source in ({"id": "render", "tick": 3}, {"id": 7},
                   {"id": "render", "ticks": "3"}, {"id": "render", "attempts": True},
                   {}, "render"):
        try:
            fresh.submit(source)
        except fleet.QueueError:
            continue
        raise AssertionError(
            "submit filed %r without validating it through stage 1: a typo'd "
            "key, a non-str id, a string cost and a non-task are all refusals"
            % (source,))
    assert fresh.queued() == 0 and fresh.sequence == 0, (
        "a refused source still grew the queue: pending=%r sequence=%r"
        % (fresh.pending, fresh.sequence))

    # ---- a Ticket source is a new arrival, not the same ticket re-filed ----

    source = fresh.submit(fleet.make_task("purge"))
    again = fresh.submit(source)
    assert again is not source, (
        "submitting a Ticket re-filed the very same ticket instead of minting a "
        "new arrival: %r" % (again,))
    assert again.task is source.task and again.seq == source.seq + 1, (
        "a submitted Ticket's task is admitted as a new arrival: got task=%r "
        "seq=%r" % (again.task, again.seq))
    assert again.attempts == 0 and again.ready_at is None, (
        "a re-admitted task starts with no attempts and no delay: %r"
        % (again,))

    # ---- the pool may arrive as a raw mapping -----------------------------

    from_text = s.Queue(fleet.POOLS["small"])
    assert from_text.pool.id == "small" and from_text.pool.capacity == 4, (
        "a raw pool mapping was stored unvalidated, so the queue never learned "
        "its capacity: %r" % (from_text.pool,))

    auto = s.Queue(pool, clock=None)
    assert auto.clock is not None and auto.clock.now() == 0, (
        "Queue(pool, clock=None) must make its own clock: %r" % (auto.clock,))
    assert auto.clock is not queue.clock, (
        "clock=None handed the queue somebody else's clock: %r" % (auto.clock,))

    print("check_02: the full queue refuses with QueueFull, depth counts the "
          "running tasks, and the sequence and clock are the queue's own")

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import dataclasses
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    def _ids(tickets):
        """The task ids of a sequence of tickets, in order."""
        return [ticket.task.id for ticket in tickets]

    def _queue(fleet, stage_02, *, now=0, capacity=16, max_concurrency=4):
        """A wide queue on a fresh clock that has already spent `now` ticks."""
        pool = fleet.make_pool("wide", capacity=capacity, max_concurrency=max_concurrency)
        clock = fleet.Clock()
        if now:
            clock.tick(now)
        return stage_02.Queue(pool, clock=clock)

    def _fill(queue, fleet, *task_ids):
        """Submit `task_ids` in order through the queue, and return its tickets."""
        for task_id in task_ids:
            queue.submit(dataclasses.asdict(fleet.make_task(task_id)))
        return list(queue.pending)

    def _delay(queue, index, ready_at):
        """Make the ticket at `index` due at `ready_at` — the frozen shape, replaced."""
        queue.pending[index] = dataclasses.replace(queue.pending[index], ready_at=ready_at)

    import fleet
    import stage_02 as s2
    import stage_03 as s

    # --- the key: priority first, arrival second -----------------------------
    q = _queue(fleet, s2)
    tickets = _fill(q, fleet, "publish", "notify", "index", "purge")
    keys = [s.order_key(ticket) for ticket in tickets]
    assert keys == [(-9, 0), (-9, 1), (-1, 2), (-7, 3)], (
        "order_key is not (-ticket.task.priority, ticket.seq), so the order is not "
        "priority-then-arrival: %r" % (keys,))

    order = _ids(s.reorder(q))
    assert order == ["publish", "notify", "purge", "index"], (
        "the tie at priority 9 was broken by id or by the pending list's order "
        "instead of by arrival: %r" % (order,))
    assert _ids(q.pending) == ["publish", "notify", "index", "purge"], (
        "reorder mutated queue.pending, so the arrival order is no longer "
        "recoverable from the queue: %r" % (_ids(q.pending),))
    result = s.reorder(q)
    assert isinstance(result, tuple) and result is not q.pending, (
        "reorder returned %r, not a fresh tuple: a caller can reorder the queue "
        "through the value it was handed" % (type(result).__name__,))

    # --- pick_next / take_next follow that order -----------------------------
    picked = s.pick_next(q)
    assert picked is not None and picked.task.id == "publish", (
        "pick_next did not return the highest-order due ticket: %r"
        % (None if picked is None else picked.task.id,))
    assert len(q.pending) == 4, (
        "pick_next removed a ticket; only take_next may do that: %r"
        % (_ids(q.pending),))
    taken = s.take_next(q)
    assert taken is picked, (
        "take_next did not return the ticket pick_next picked: %r vs %r"
        % (None if taken is None else taken.task.id, picked.task.id))
    assert _ids(q.pending) == ["notify", "index", "purge"], (
        "take_next did not remove the ticket it picked from pending: %r"
        % (_ids(q.pending),))

    # --- an equal-priority tie is arrival, not id ----------------------------
    tie = _queue(fleet, s2)
    _fill(tie, fleet, "publish", "notify")          # both priority 9; ids sort the
    order = _ids(s.reorder(tie))                    # other way round
    assert order == ["publish", "notify"], (
        "the tie at priority 9 was broken by task id instead of arrival: %r"
        % (order,))

    tenants = _queue(fleet, s2)
    _fill(tenants, fleet, "audit", "render")        # both priority 5; tenants differ
    order = _ids(s.reorder(tenants))
    assert order == ["audit", "render"], (
        "the tie at priority 5 was broken by tenant instead of arrival: %r"
        % (order,))

    newest = _queue(fleet, s2)
    _fill(newest, fleet, "render", "audit")         # both priority 5, arrival order
    order = _ids(s.reorder(newest))
    assert order == ["render", "audit"], (
        "the tie at priority 5 was broken newest-first instead of by arrival: %r"
        % (order,))

    # --- a requeued ticket keeps its seq, not the list's stale position ------
    q4 = _queue(fleet, s2)
    _fill(q4, fleet, "render", "audit", "notify", "digest")
    q4.pending.append(q4.pending.pop(0))            # what stage 6's retry does:
    order = _ids(s.reorder(q4))                     # render back on the tail
    assert order == ["notify", "digest", "render", "audit"], (
        "the order leaned on the stable sort, so a requeued ticket was placed by "
        "the pending list's stale order instead of by arrival: %r" % (order,))
    assert _ids(q4.pending) == ["audit", "notify", "digest", "render"], (
        "reorder mutated queue.pending, destroying the arrival record a requeue "
        "left behind: %r" % (_ids(q4.pending),))

    head = s.pick_next(q4)
    assert head is not None and head.task.id == "notify", (
        "pick_next skipped the highest-order pending ticket: %r"
        % (None if head is None else head.task.id,))
    assert len(q4.pending) == 4, (
        "pick_next removed a ticket; only take_next may do that: %r"
        % (_ids(q4.pending),))
    taken = s.take_next(q4)
    assert taken is not None and taken.task.id == "notify", (
        "take_next returned %r, not the ticket pick_next picks from a pending "
        "list that is not in service order"
        % (None if taken is None else taken.task.id,))
    assert _ids(q4.pending) == ["audit", "digest", "render"], (
        "take_next removed the head (or the tail) of pending instead of the "
        "ticket it picked: %r" % (_ids(q4.pending),))

    # --- eligibility: a future ready_at is not due ---------------------------
    q5 = _queue(fleet, s2, now=5)
    _fill(q5, fleet, "notify", "purge", "index", "publish")
    _delay(q5, 0, 9)                                # the highest order, not due
    _delay(q5, 3, 5)                                # due exactly now
    order = _ids(s.reorder(q5))
    assert order == ["notify", "publish", "purge", "index"], (
        "reorder dropped a ticket that is not yet due; reorder is the whole "
        "pending list, delayed tickets included: %r" % (order,))
    picked = s.pick_next(q5)
    assert picked is not None and picked.task.id == "publish", (
        "a ticket whose ready_at is in the future was picked, or the ticket due "
        "exactly now (ready_at == clock) was not eligible: %r"
        % (None if picked is None else picked.task.id,))
    taken = s.take_next(q5)
    assert taken is not None and taken.task.id == "publish", (
        "take_next did not pick the ticket that is due exactly now: %r"
        % (None if taken is None else taken.task.id,))
    assert _ids(q5.pending) == ["notify", "purge", "index"], (
        "take_next removed the wrong ticket when the highest order was not due: %r"
        % (_ids(q5.pending),))

    # --- nothing is due: pick_next and take_next give up, and remove nothing --
    q6 = _queue(fleet, s2, now=0)
    _fill(q6, fleet, "render", "notify")
    _delay(q6, 0, 4)
    _delay(q6, 1, 6)
    assert s.pick_next(q6) is None, (
        "pick_next picked a ticket whose ready_at is in the future: %r"
        % (s.pick_next(q6),))
    assert s.take_next(q6) is None, (
        "take_next returned a ticket whose ready_at is in the future: %r"
        % (s.take_next(q6),))
    assert _ids(q6.pending) == ["render", "notify"], (
        "take_next removed a ticket it did not pick (there was nothing to pick): "
        "%r" % (_ids(q6.pending),))

    # --- an empty queue is not an error --------------------------------------
    q7 = _queue(fleet, s2)
    assert s.reorder(q7) == (), (
        "reorder of an empty queue is not the empty tuple: %r" % (s.reorder(q7),))
    assert s.pick_next(q7) is None, (
        "pick_next of an empty queue is not None: %r" % (s.pick_next(q7),))
    assert s.take_next(q7) is None, (
        "take_next of an empty queue is not None: %r" % (s.take_next(q7),))

    print("check_03: 9 fixtures — order_key, reorder, pick_next and take_next "
          "follow one (-priority, seq) order with a <= eligibility boundary")

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import dataclasses
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    def _queue(fleet, stage_02, *, now=0, pool_id="small", **overrides):
        """A queue over one pool, on a fresh clock that has already spent `now`."""
        clock = fleet.Clock(start=now)
        return stage_02.Queue(fleet.make_pool(pool_id, **overrides), clock=clock), clock

    def _recording(fleet, *, status="ok", ticks=2, detail="recorded"):
        """A worker that answers one outcome and remembers each `(id, attempt)`."""
        seen = []

        def fn(task, attempt):
            seen.append((task.id, attempt))
            return fleet.outcome(status, ticks, detail)

        return fleet.Worker(fn, label="recording"), seen

    def _ids(outcomes):
        return [outcome["task"] for outcome in outcomes]

    import fleet
    import stage_02 as s2
    import stage_04 as s

    # ---- validate_outcome: an answer is an outcome, or it is a refusal ------

    assert issubclass(s.OutcomeError, fleet.QueueError), (
        "OutcomeError is not a QueueError, so a worker that answers garbage is "
        "not the queue's refusal: %r" % (s.OutcomeError.__mro__,))

    good = fleet.outcome("ok", 3, "done")
    assert s.validate_outcome(good) == {
        "status": "ok", "ticks": 3, "detail": "done"}, (
        "validate_outcome changed or dropped a well-formed outcome: %r"
        % (s.validate_outcome(good),))
    assert s.validate_outcome(
        {"status": "died", "ticks": 0, "detail": ""})["status"] == "died", (
        "validate_outcome refused a `died` answer, which is one of OUTCOMES: %r"
        % (fleet.OUTCOMES,))

    for answer, needle in (
            ("ok", "mapping"),
            (None, "mapping"),
            (["ok", 1, ""], "mapping"),
            ({"status": "ok", "ticks": 1}, "keys"),
            ({"status": "ok", "ticks": 1, "detail": "", "extra": 1}, "keys"),
            ({"status": "fine", "ticks": 1, "detail": ""}, "fine"),
            ({"status": "ok", "ticks": -1, "detail": ""}, "ticks"),
            ({"status": "ok", "ticks": True, "detail": ""}, "ticks"),
            ({"status": "ok", "ticks": "3", "detail": ""}, "ticks"),
            ({"status": "ok", "ticks": 1.5, "detail": ""}, "ticks")):
        try:
            s.validate_outcome(answer)
        except s.OutcomeError as refused:
            message = str(refused)
            assert needle in message, (
                "the refusal of %r does not name what was wrong (want %r in "
                "the message): %r" % (answer, needle, message))
            continue
        except Exception as wrong:
            raise AssertionError(
                "validate_outcome(%r) raised %s instead of OutcomeError: a "
                "worker that answers garbage is the queue's refusal, not a "
                "crash three frames away" % (answer, type(wrong).__name__))
        raise AssertionError(
            "validate_outcome accepted %r as an outcome, so a worker that "
            "reports nonsense is filed as a success" % (answer,))

    # ---- free_slots counts the running flights, and nothing else -----------

    wide, _ = _queue(fleet, s2, pool_id="wide", max_concurrency=2, capacity=8)
    assert s.free_slots(wide) == 2, (
        "an empty pool of 2 has %d free slots" % (s.free_slots(wide),))
    for task_id in ("notify", "publish", "render", "index"):
        wide.submit(fleet.make_task(task_id))
    assert s.free_slots(wide) == 2, (
        "free_slots spent a slot on a ticket that is only waiting: 4 pending "
        "tasks left %d slots of 2" % (s.free_slots(wide),))
    wide.dead.append(s2.DeadLetter(fleet.make_task("audit"), 3, "poison", 0))
    assert s.free_slots(wide) == 2, (
        "free_slots spent a slot on a dead letter, so the pool shrinks every "
        "time a task is given up on: %d of 2" % (s.free_slots(wide),))

    limited = fleet.reliable()
    first = s.start(wide, limited)
    assert first is not None and s.free_slots(wide) == 1, (
        "one flight in flight left %d free slots of 2" % (s.free_slots(wide),))
    second = s.start(wide, limited)
    assert second is not None and s.free_slots(wide) == 0, (
        "two flights in flight left %d free slots of 2" % (s.free_slots(wide),))

    # ---- the limit is checked before the worker starts ----------------------

    calls = limited.calls
    assert s.start(wide, limited) is None, (
        "start started a third task on a pool of 2, so the limit was checked "
        "after the worker had already run")
    assert limited.calls == calls, (
        "the worker ran %d extra time(s) on a pool with no free slot, so the "
        "limit is data the queue learns too late"
        % (limited.calls - calls,))
    assert wide.decisions["limit_hits"] == 1, (
        "the refused dispatch was not counted: a limit hit is a fact the "
        "record must carry, limit_hits=%r" % (wide.decisions["limit_hits"],))

    # ---- start: the flight's three tick marks are the clock's --------------

    narrow, clock = _queue(fleet, s2, now=4)                # small: 1 slot
    narrow.submit(fleet.make_task("render", ticks=3))
    recorder, seen = _recording(fleet, ticks=3)
    flight = s.start(narrow, recorder)
    assert isinstance(flight, s2.Flight), (
        "start returned %r, not the Flight it recorded" % (flight,))
    assert flight.ticket.task.id == "render" and flight.attempt == 1, (
        "the first flight of `render` must be attempt 1 of its ticket: %r"
        % ((flight.ticket.task.id, flight.attempt),))
    assert seen == [("render", 1)], (
        "the worker was called with %r, not (render, attempt 1)" % (seen,))
    assert (flight.started_at, flight.finishes_at, flight.deadline_at) == (4, 7, None), (
        "a flight started at tick 4 for 3 ticks must read started_at 4, "
        "finishes_at 7 and no deadline (no lease was given), got %r"
        % ((flight.started_at, flight.finishes_at, flight.deadline_at),))
    assert narrow.in_flight == {"render": flight}, (
        "the flight was not filed under the task id the worker ran: %r"
        % (narrow.in_flight,))
    assert narrow.pending == [] and narrow.queued() == 0, (
        "the started ticket is still waiting, so the queue holds it twice: %r"
        % (narrow.pending,))
    assert clock.ticks == 0, (
        "start moved the clock; only the scheduler moves it, ticks=%d"
        % (clock.ticks,))
    line = narrow.events[-1]
    assert (line["at"], line["kind"], line["task"]) == (4, "started", "render"), (
        "the started line must read at=4, kind=started, task=render: %r"
        % (line,))

    # ---- the flight costs the ticks the worker reported, not the estimate --

    quick, quick_clock = _queue(fleet, s2, now=3)
    quick.submit(fleet.make_task("render", ticks=3))        # the estimate is 3
    instant = s.start(quick, fleet.instant())               # the worker says 0
    assert instant.finishes_at == quick_clock.now() == 3, (
        "the flight finished at %r; it must finish when the worker said it "
        "would (0 ticks, tick 3) and not when the task's estimate says (3)"
        % (instant.finishes_at,))
    resolved = s.complete(quick)
    assert isinstance(resolved, tuple) and _ids(resolved) == ["render"], (
        "a flight that finishes exactly at the current tick was not resolved, "
        "so the boundary is < and not <=: %r" % (resolved,))
    assert quick_clock.ticks == 0 and quick_clock.now() == 3, (
        "complete moved the clock to %d; resolving a flight is not work"
        % (quick_clock.now(),))

    # ---- the lease stamps the deadline; the attempt is the ticket's ---------

    leased, lease_clock = _queue(fleet, s2, now=5)
    leased.submit(fleet.make_task("purge", ticks=2))
    held = s.start(leased, fleet.reliable(), lease=8)
    assert (held.started_at, held.finishes_at, held.deadline_at) == (5, 7, 13), (
        "a flight started at 5 with 2 ticks and an 8-tick lease must read "
        "started_at 5, finishes_at 7 and deadline_at 13, got %r"
        % ((held.started_at, held.finishes_at, held.deadline_at),))

    spent, _ = _queue(fleet, s2)
    spent.submit(fleet.make_task("render", ticks=1))
    spent.pending[0] = dataclasses.replace(spent.pending[0], attempts=2)
    retry_recorder, retry_seen = _recording(fleet, ticks=1)
    third = s.start(spent, retry_recorder)
    assert third.attempt == 3, (
        "a ticket that already spent 2 attempts started as attempt %d; the "
        "attempt is the ticket's spent count plus one" % (third.attempt,))
    assert retry_seen == [("render", 3)], (
        "the worker was called with %r instead of (render, attempt 3)" % (retry_seen,))

    # ---- start takes stage 3's next due ticket, never a delayed one --------

    ordered, _ = _queue(fleet, s2, pool_id="wide", max_concurrency=4, capacity=8)
    for task_id in ("index", "notify", "purge"):
        ordered.submit(fleet.make_task(task_id))
    ordered.pending[1] = dataclasses.replace(ordered.pending[1], ready_at=20)
    order_recorder, _ = _recording(fleet, ticks=1)
    picked = s.start(ordered, order_recorder)
    assert picked is not None and picked.ticket.task.id == "purge", (
        "start picked %r; `notify` is the highest order but is not due until "
        "tick 20, so the next eligible ticket (`purge`) is the one to start"
        % (None if picked is None else picked.ticket.task.id,))
    picked = s.start(ordered, order_recorder)
    assert picked is not None and picked.ticket.task.id == "index", (
        "start picked %r instead of the next eligible ticket (`index`)"
        % (None if picked is None else picked.ticket.task.id,))
    assert s.start(ordered, order_recorder) is None, (
        "start started the not-yet-due `notify` (or a ticket with no slot): %r"
        % (ordered.in_flight,))
    assert ordered.decisions["limit_hits"] == 0, (
        "a dispatch that had a slot and nothing due was counted as a limit hit "
        "(%r); only a pool with no free slot is a limit hit"
        % (ordered.decisions["limit_hits"],))
    assert len(ordered.pending) == 1 and ordered.pending[0].task.id == "notify", (
        "the delayed ticket left pending, so it can never be due again: %r"
        % ([ticket.task.id for ticket in ordered.pending],))

    empty, _ = _queue(fleet, s2)
    assert s.start(empty, fleet.reliable()) is None, (
        "start of an empty queue returned %r" % (s.start(empty, fleet.reliable()),))
    assert empty.decisions["limit_hits"] == 0, (
        "an empty queue counted a limit hit: %r" % (empty.decisions,))

    # ---- a worker that answers garbage leaves the queue exactly as it was --

    risky, _ = _queue(fleet, s2)
    risky.submit(fleet.make_task("render"))
    risky.submit(fleet.make_task("audit"))
    before_pending = list(risky.pending)
    before_events = list(risky.events)
    for shape in ("string", "negative", "bad_status", "no_ticks"):
        broken = fleet.bad_shape(shape)
        try:
            s.start(risky, broken)
        except s.OutcomeError:
            pass
        else:
            raise AssertionError(
                "start filed a worker that answered the %r shape, so a bad "
                "answer becomes a started flight" % (shape,))
        assert risky.pending == before_pending, (
            "the worker's bad `%s` answer cost the queue its next ticket: the "
            "ticket was taken out of pending before the answer was validated, "
            "pending=%r" % (shape, [ticket.task.id for ticket in risky.pending]))
        assert risky.in_flight == {}, (
            "a flight was recorded for a worker that answered the %r shape: %r"
            % (shape, risky.in_flight))
        assert risky.events == before_events, (
            "a started line was written before the worker's %r answer was "
            "validated: %r" % (shape, risky.events[-1:]))
        assert broken.calls == 1, (
            "the %r worker was called %d times for one dispatch"
            % (shape, broken.calls))
    assert s.free_slots(risky) == 1 and risky.decisions["limit_hits"] == 0, (
        "four bad answers spent the pool or counted a limit hit: %r"
        % (risky.decisions,))
    recovered = s.start(risky, fleet.reliable())
    assert recovered is not None and recovered.ticket.task.id == "render", (
        "the queue did not recover from a bad answer: %r" % (recovered,))

    # ---- a flight that has not finished is left alone ----------------------

    waiting, waiting_clock = _queue(fleet, s2)
    waiting.submit(fleet.make_task("render", ticks=3))
    pending_flight = s.start(waiting, fleet.reliable())
    waiting_clock.tick(2)
    assert s.complete(waiting) == (), (
        "complete resolved a flight that finishes at tick 3 while the clock "
        "reads 2: %r" % (s.complete(waiting),))
    assert waiting.in_flight == {"render": pending_flight}, (
        "the unfinished flight left the queue: %r" % (waiting.in_flight,))
    assert waiting_clock.ticks == 2 and waiting_clock.now() == 2, (
        "complete advanced the clock to %d" % (waiting_clock.now(),))

    # ---- completions resolve in (finishes_at, seq) order -------------------

    twin, twin_clock = _queue(fleet, s2, pool_id="wide", max_concurrency=4, capacity=8)
    twin.submit(fleet.make_task("index", ticks=3))         # seq 0, priority 1
    twin.submit(fleet.make_task("notify", ticks=3))        # seq 1, priority 9
    assert s.start(twin, fleet.reliable()).ticket.task.id == "notify" and \
        s.start(twin, fleet.reliable()).ticket.task.id == "index", (
        "the two flights did not start in stage 3's order: %r"
        % ([flight.ticket.task.id for flight in twin.in_flight.values()],))
    twin_clock.tick(3)
    same_tick = s.complete(twin)
    assert _ids(same_tick) == ["index", "notify"], (
        "two flights finishing at the same tick were resolved in %r; the tie "
        "is broken by arrival (seq), not by the dictionary's order" % (_ids(same_tick),))
    assert [line["task"] for line in twin.events if line["kind"] == "succeeded"] == \
        ["index", "notify"], (
        "the succeeded lines are not in the resolution order: %r"
        % ([line["task"] for line in twin.events],))

    spread, spread_clock = _queue(fleet, s2, pool_id="wide", max_concurrency=4,
                                  capacity=8)
    for task_id in ("publish", "purge", "notify"):         # 9/3, 7/2, 9/1
        spread.submit(fleet.make_task(task_id))
    for _ in range(3):
        s.start(spread, fleet.reliable())
    spread_clock.tick(3)
    ordered_outcomes = s.complete(spread)
    assert _ids(ordered_outcomes) == ["notify", "purge", "publish"], (
        "the flights were resolved in %r; the earliest finish tick is first "
        "(notify at 1, purge at 2, publish at 3), never the arrival order "
        "and never the dictionary's order" % (_ids(ordered_outcomes),))
    assert spread.in_flight == {} and spread.pending == [], (
        "resolved flights were left in the queue: in_flight=%r pending=%r"
        % (spread.in_flight, [ticket.task.id for ticket in spread.pending]))

    # ---- a failed flight requeues its ticket, due again, one attempt spent --

    retrying, retry_clock = _queue(fleet, s2)
    retrying.submit(fleet.make_task("render", ticks=3))
    flaky = fleet.crasher(on_attempt=1)                    # attempt 1 fails
    tried = s.start(retrying, flaky)
    assert tried.attempt == 1 and tried.finishes_at == 3, (
        "the first attempt of `render` must cost the 3 ticks the worker "
        "reported: %r" % ((tried.attempt, tried.finishes_at),))
    retry_clock.tick(3)
    failed = s.complete(retrying)
    assert len(failed) == 1 and failed[0]["task"] == "render" and \
        failed[0]["status"] == "failed" and failed[0]["attempt"] == 1, (
        "the resolution of a failed flight must carry task, status and the "
        "attempt that failed: %r" % (failed,))
    assert retrying.in_flight == {} and s.free_slots(retrying) == 1, (
        "the resolved flight is still holding its slot: %r" % (retrying.in_flight,))
    assert len(retrying.pending) == 1, (
        "a failed ticket was dropped instead of requeued: pending=%r"
        % (retrying.pending,))
    back = retrying.pending[0]
    assert back.seq == tried.ticket.seq and back.task.id == "render", (
        "the requeued ticket is not the ticket that failed: %r" % (back,))
    assert back.attempts == 1, (
        "the requeued ticket spent %d attempts; a failed attempt is one the "
        "queue must count" % (back.attempts,))
    assert back.ready_at is None, (
        "the requeued ticket is due at %r; stage 4 returns it due immediately "
        "and stage 6 is the stage that adds the backoff" % (back.ready_at,))
    assert retrying.events[-1]["kind"] == "failed" and \
        retrying.events[-1]["at"] == 3 and retrying.events[-1]["task"] == "render", (
        "the failed line must read at=3, kind=failed, task=render: %r"
        % (retrying.events[-1],))

    again = s.start(retrying, flaky)
    assert again.attempt == 2 and again.ticket is back, (
        "the retried ticket started as attempt %d of %r"
        % (again.attempt, (again.ticket.attempts, again.ticket.ready_at)))
    assert again.started_at == 3 and again.finishes_at == 6, (
        "the retry started at %r and finishes at %r, not at the clock (3) "
        "plus the ticks the worker reported (3)"
        % (again.started_at, again.finishes_at))
    retry_clock.tick(3)
    succeeded = s.complete(retrying)
    assert len(succeeded) == 1 and succeeded[0]["status"] == "ok" and \
        succeeded[0]["attempt"] == 2, (
        "the second attempt's resolution is %r, so it does not report the "
        "attempt that actually ran" % (succeeded,))
    assert retrying.in_flight == {} and retrying.pending == [], (
        "the successful retry did not leave the queue: in_flight=%r pending=%r"
        % (retrying.in_flight, [ticket.task.id for ticket in retrying.pending]))
    assert retrying.events[-1]["kind"] == "succeeded" and \
        retrying.events[-1]["at"] == 6 and retrying.events[-1]["task"] == "render", (
        "the succeeded line must read at=6, kind=succeeded, task=render: %r"
        % (retrying.events[-1],))
    assert flaky.calls == 2, (
        "the worker was called %d times for two attempts: the worker is called "
        "once per attempt, and `complete` does not call it again" % (flaky.calls,))

    # ---- a died flight requeues too, and its line says `died` --------------

    dying_queue, dying_clock = _queue(fleet, s2)
    dying_queue.submit(fleet.make_task("audit", ticks=2))
    scripted = fleet.scripted(["died", "ok"], ticks=2)
    gone = s.start(dying_queue, scripted)
    assert gone.attempt == 1, "the first attempt of `audit` is attempt 1: %r" % (gone.attempt,)
    dying_clock.tick(2)
    died = s.complete(dying_queue)
    assert len(died) == 1 and died[0]["status"] == "died", (
        "a flight whose worker reported `died` resolved as %r" % (died,))
    assert dying_queue.in_flight == {}, (
        "the died flight is still holding its slot: %r" % (dying_queue.in_flight,))
    assert len(dying_queue.pending) == 1 and dying_queue.pending[0].attempts == 1, (
        "a died ticket must go back to pending with one attempt spent: %r"
        % (dying_queue.pending,))
    assert dying_queue.events[-1]["kind"] == "died" and \
        dying_queue.events[-1]["task"] == "audit", (
        "a died flight's line must read kind=died, not the failure it looks "
        "like: %r" % (dying_queue.events[-1],))

    # ---- and a queue whose work is done stays quiet -------------------------

    done, done_clock = _queue(fleet, s2)
    done.submit(fleet.make_task("notify", ticks=1))
    s.start(done, fleet.reliable())
    done_clock.tick(1)
    last = s.complete(done)
    assert isinstance(last, tuple) and len(last) == 1 and isinstance(last[0], dict), (
        "the last resolution is not a one-dict tuple: %r" % (last,))
    assert set(last[0]) >= {"task", "status", "attempt"}, (
        "the resolution must carry at least task, status and attempt: %r"
        % (last[0],))
    assert (last[0]["task"], last[0]["status"], last[0]["attempt"]) == (
        "notify", "ok", 1), (
        "the resolution of a successful first attempt must read (notify, ok, "
        "1): %r" % (last[0],))
    assert s.complete(done) == (), (
        "a queue with nothing in flight resolved something: %r" % (s.complete(done),))

    print("check_04: 14 fixtures — the limit is checked before the worker runs, "
          "a bad answer is refused without moving the queue, and every flight "
          "resolves in (finishes_at, seq) order with a status the worker "
          "actually reported")

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import dataclasses
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    NO_DECISIONS = {"admitted": 0, "refused": 0, "shed": 0, "blocked": 0,
                    "limit_hits": 0}

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    def _queue(fleet, stage_02, *, now=0, capacity=16, max_concurrency=4):
        """A wide queue on a fresh clock that has already spent `now` ticks."""
        pool = fleet.make_pool("wide", capacity=capacity, max_concurrency=max_concurrency)
        clock = fleet.Clock()
        if now:
            clock.tick(now)
        return stage_02.Queue(pool, clock=clock)

    def _arm(queue, stage_02, task, *, attempt=1, ticks=None, lease=None, spent=0):
        """One running flight, placed the way stage 4's `start` places it.

        The frozen `Flight` shape, with `deadline_at` stamped from the lease it was
        given (`None` when it was given none) — and the ticket taken out of
        `pending`, which is what stage 3's `take_next` does before stage 4 records
        the flight.
        """
        ticket = queue.submit(dataclasses.asdict(task))
        queue.pending.remove(ticket)
        if spent:
            ticket = dataclasses.replace(ticket, attempts=spent)
        started = queue.clock.now()
        cost = task.ticks if ticks is None else ticks
        flight = stage_02.Flight(ticket=ticket, attempt=attempt, started_at=started,
                                 finishes_at=started + cost,
                                 deadline_at=None if lease is None else started + lease)
        queue.in_flight[task.id] = flight
        return flight

    def _ids(tickets):
        """The task ids of a sequence of tickets, in order."""
        return [ticket.task.id for ticket in tickets]

    def _kinds(queue):
        """The kinds in the queue's record, in order."""
        return [entry["kind"] for entry in queue.events]

    def _refuses(fleet, what, call):
        """The message of the `QueueError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except fleet.QueueError as refused:
            return str(refused)
        except Exception as wrong:
            raise AssertionError(
                "%s raised %s instead of the queue's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import fleet
    import stage_02 as s2
    import stage_05 as s

    # ---- the number this stage owns ----------------------------------------

    assert s.DEFAULT_LEASE == 8 and type(s.DEFAULT_LEASE) is int, (
        "DEFAULT_LEASE is not the int 8: %r" % (s.DEFAULT_LEASE,))

    # ---- a flight at its deadline is dead, and the slot is free again ------

    q = _queue(fleet, s2)
    flight = _arm(q, s2, fleet.make_task("purge"), ticks=5, lease=2)
    q.clock.tick(2)                              # exactly the deadline: <=, not <
    out = s.sweep(q)
    assert isinstance(out, tuple), (
        "sweep returned %r, not a tuple of the outcomes it resolved"
        % (type(out).__name__,))
    assert [entry["task"] for entry in out] == ["purge"], (
        "sweep did not resolve the one flight that reached its lease (deadline "
        "2, now 2): %r" % (out,))
    assert out[0]["status"] == "died", (
        "the flight past its lease was filed as %r: a worker that went away "
        "never finished" % (out[0]["status"],))
    assert out[0]["attempt"] == 1, (
        "the died outcome names attempt %r, not the attempt that never "
        "finished: %r" % (out[0]["attempt"], out[0]))
    assert q.in_flight == {}, (
        "the swept flight is still in flight, so the slot is still held and a "
        "later completion could file it as a success: %r" % (sorted(q.in_flight),))
    assert _ids(q.pending) == ["purge"], (
        "the swept task was dropped instead of requeued: pending is %r"
        % (_ids(q.pending),))
    back = q.pending[0]
    assert back.attempts == 1, (
        "the swept ticket came back with attempts=%r: the attempt that never "
        "finished still cost one, and the next one is attempt 2" % (back.attempts,))
    assert back.seq == flight.ticket.seq, (
        "the requeued ticket took a fresh arrival number (%r, not %r), so it "
        "jumps the queue instead of holding its place in line"
        % (back.seq, flight.ticket.seq))
    assert back.submitted_at == flight.ticket.submitted_at, (
        "the requeued ticket was stamped as submitted at %r, not the %r it "
        "arrived at: ageing would restart from the wrong tick"
        % (back.submitted_at, flight.ticket.submitted_at))
    assert back.ready_at is None, (
        "the reclaimed ticket came back with ready_at=%r, not due now: the "
        "sweep schedules nothing, it hands the task back" % (back.ready_at,))
    died = [entry for entry in q.events if entry["kind"] == "died"]
    assert died == [{"at": 2, "kind": "died", "task": "purge"}], (
        "the sweep did not append exactly one died event at the tick of the "
        "sweep naming the task: %r" % (died,))
    assert q.decisions == NO_DECISIONS, (
        "the sweep moved the queue's decision counters: %r" % (q.decisions,))

    # ---- a flight inside its lease is left strictly alone ------------------

    q = _queue(fleet, s2)
    _arm(q, s2, fleet.make_task("render"), ticks=3, lease=5)      # deadline 5
    q.clock.tick(4)                                               # a tick short
    out = s.sweep(q)
    assert out == (), (
        "sweep resolved a flight that is still inside its lease (deadline 5, "
        "now 4): a lease is not the work estimate, and the work estimate is not "
        "the lease: %r" % (out,))
    assert list(q.in_flight) == ["render"] and q.pending == [], (
        "the sweep changed a queue whose flights are all inside their leases: "
        "in_flight=%r pending=%r" % (sorted(q.in_flight), _ids(q.pending)))
    assert _kinds(q) == ["submitted"], (
        "the sweep appended an event for a flight it did not resolve: %r"
        % (_kinds(q),))

    # ---- a flight with no lease never expires ------------------------------

    q = _queue(fleet, s2)
    _arm(q, s2, fleet.make_task("index"), ticks=7, lease=None)
    _arm(q, s2, fleet.make_task("purge"), ticks=2, lease=3)
    q.clock.tick(50)
    out = s.sweep(q)
    assert [entry["task"] for entry in out] == ["purge"], (
        "sweep resolved %r: a flight with no lease (deadline_at is None) has no "
        "deadline to miss" % ([entry["task"] for entry in out],))
    assert list(q.in_flight) == ["index"], (
        "the flight with no lease did not stay in flight: %r"
        % (sorted(q.in_flight),))

    # ---- the order of the outcomes: earliest deadline, then arrival --------

    q = _queue(fleet, s2)
    _arm(q, s2, fleet.make_task("publish"), ticks=3, lease=5)     # deadline 5, seq 0
    _arm(q, s2, fleet.make_task("purge"), ticks=2, lease=1)       # deadline 1, seq 1
    _arm(q, s2, fleet.make_task("render"), ticks=3, lease=3)      # deadline 3, seq 2
    _arm(q, s2, fleet.make_task("index"), ticks=7, lease=1)       # deadline 1, seq 3
    q.clock.tick(6)
    out = s.sweep(q)
    order = [entry["task"] for entry in out]
    assert order == ["purge", "index", "render", "publish"], (
        "the swept flights came back as %r: the order is (deadline_at, seq), "
        "earliest deadline first with the tie at deadline 1 broken by arrival"
        % (order,))
    assert sorted(_ids(q.pending)) == ["index", "publish", "purge", "render"], (
        "the swept tasks did not all come back to pending: %r" % (_ids(q.pending),))

    # ---- a flight is swept once, so the attempt is spent once --------------

    q = _queue(fleet, s2)
    _arm(q, s2, fleet.make_task("purge"), ticks=5, lease=2)
    q.clock.tick(3)
    first = s.sweep(q)
    assert [entry["task"] for entry in first] == ["purge"], (
        "sweep did not resolve the flight whose lease expired: %r" % (first,))
    out = s.sweep(q)
    assert out == (), (
        "the second sweep resolved a flight the first one already took, so the "
        "task dies twice: %r" % (out,))
    assert q.pending[0].attempts == 1, (
        "the second sweep spent another attempt on the same task: %r"
        % (q.pending[0],))
    assert _kinds(q).count("died") == 1, (
        "the record carries %d died events for one dead flight: %r"
        % (_kinds(q).count("died"), q.events))

    # ---- dying is not finishing: the ticks do not make it a success --------

    q = _queue(fleet, s2)
    _arm(q, s2, fleet.make_task("purge"), ticks=1, lease=1)       # deadline 1 == cost
    q.clock.tick(4)
    out = s.sweep(q)
    assert len(out) == 1 and out[0]["status"] == "died", (
        "a flight nobody resolved by its deadline was filed as %r because its "
        "ticks say the work finished by now: a worker that went away never "
        "reported an outcome at all"
        % ([entry["status"] for entry in out],))

    # ---- nothing in flight, nothing to sweep -------------------------------

    q = _queue(fleet, s2)
    out = s.sweep(q)
    assert out == () and q.events == [], (
        "sweep of a queue with nothing in flight returned %r and wrote %r"
        % (out, q.events))

    # ---- ack: the flight goes, the ticket comes back to the caller ---------

    q = _queue(fleet, s2)
    flight = _arm(q, s2, fleet.make_task("audit"), ticks=5, lease=8)
    ticket = s.ack(q, "audit")
    assert ticket is flight.ticket, (
        "ack returned %r instead of the ticket of the flight it removed"
        % (type(ticket).__name__,))
    assert q.in_flight == {}, (
        "ack left the flight in flight, so the slot and the task id are still "
        "held: %r" % (sorted(q.in_flight),))
    assert q.pending == [], (
        "ack put the acknowledged task back in pending, so it runs (and is "
        "counted) twice: %r" % (_ids(q.pending),))
    assert q.depth() == 0 and q.decisions == NO_DECISIONS, (
        "ack left the queue holding something: depth=%d decisions=%r"
        % (q.depth(), q.decisions))
    assert _kinds(q) == ["submitted"], (
        "ack appended an event: the twelve kinds have no entry for it, so the "
        "record is no longer the run's log: %r" % (_kinds(q),))

    # ---- ack of an id the queue is not running refuses, and names it -------

    q = _queue(fleet, s2)
    _arm(q, s2, fleet.make_task("purge"), ticks=5, lease=2)
    message = _refuses(fleet, "ack of a task the queue is not running",
                       lambda: s.ack(q, "ghost"))
    assert "ghost" in message, (
        "the refusal does not name the id it could not find: %r" % (message,))
    q.clock.tick(3)
    s.sweep(q)                                   # the task is back, the flight is gone
    message = _refuses(fleet, "ack of a flight the sweep already resolved",
                       lambda: s.ack(q, "purge"))
    assert "purge" in message and q.in_flight == {}, (
        "ack of an already-resolved id did not refuse naming it: %r (in_flight "
        "%r)" % (message, sorted(q.in_flight)))

    # ---- release: back in pending, and not one attempt older ---------------

    q = _queue(fleet, s2)
    flight = _arm(q, s2, fleet.make_task("train"), ticks=12, lease=8)
    ticket = s.release(q, "train")
    assert q.in_flight == {}, (
        "release left the flight in flight, so the task is in two places at "
        "once and the slot is still held: %r" % (sorted(q.in_flight),))
    assert len(q.pending) == 1 and q.pending[0] is ticket, (
        "release did not put the ticket it returned back in pending: %r vs %r"
        % (ticket, q.pending))
    assert ticket.task.id == "train" and ticket.seq == flight.ticket.seq, (
        "the released ticket is not the one that was running (task %r, seq %r "
        "vs %r)" % (ticket.task.id, ticket.seq, flight.ticket.seq))
    assert ticket.submitted_at == flight.ticket.submitted_at, (
        "the released ticket was re-stamped as submitted at %r, not %r: it is "
        "the same arrival" % (ticket.submitted_at, flight.ticket.submitted_at))
    assert ticket.attempts == 0, (
        "release spent an attempt (%r): a release is housekeeping, not a failed "
        "attempt, and spending one here lets a rebalance dead-letter a task "
        "that never failed" % (ticket.attempts,))
    assert ticket.ready_at is None, (
        "the released ticket came back with ready_at=%r, not due now"
        % (ticket.ready_at,))
    assert q.depth() == 1 and q.decisions == NO_DECISIONS, (
        "release left the queue in the wrong shape: depth=%d decisions=%r"
        % (q.depth(), q.decisions))
    assert _kinds(q) == ["submitted"], (
        "release appended an event: a release is not a retry, and the twelve "
        "kinds have no entry for it: %r" % (_kinds(q),))

    q = _queue(fleet, s2)
    _arm(q, s2, fleet.make_task("train"), ticks=12, lease=8, attempt=2, spent=1)
    ticket = s.release(q, "train")
    assert ticket.attempts == 1, (
        "release changed the attempt count from the 1 it had to %r: only a "
        "finished attempt spends one" % (ticket.attempts,))

    # ---- release of an unknown id, and of a flight already released --------

    q = _queue(fleet, s2)
    message = _refuses(fleet, "release of a task the queue is not running",
                       lambda: s.release(q, "ghost"))
    assert "ghost" in message, (
        "the refusal does not name the id it could not find: %r" % (message,))
    _arm(q, s2, fleet.make_task("digest"), ticks=4, lease=8)
    s.release(q, "digest")
    message = _refuses(fleet, "release of a flight already released",
                       lambda: s.release(q, "digest"))
    assert "digest" in message and q.in_flight == {}, (
        "a second release of the same id did not refuse naming it: %r (in_flight "
        "%r)" % (message, sorted(q.in_flight)))

    print("check_05: 12 fixtures — the lease expires at its deadline and not "
          "before, the swept task comes back with one attempt and due now in "
          "(deadline_at, seq) order, and ack/release free the slot while naming "
          "an id they cannot find")

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import dataclasses
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    DECISION_KEYS = ("admitted", "refused", "shed", "blocked", "limit_hits")

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    def _zeros():
        """A fresh zeroed counter bag — the check's own copy, never a shared one."""
        return {key: 0 for key in DECISION_KEYS}

    def _queue(fleet, stage_02, *, now=0, capacity=16, max_concurrency=4):
        """A wide queue on a fresh clock that has already spent `now` ticks."""
        pool = fleet.make_pool("wide", capacity=capacity, max_concurrency=max_concurrency)
        clock = fleet.Clock()
        if now:
            clock.tick(now)
        return stage_02.Queue(pool, clock=clock)

    def _ids(tickets):
        """The task ids of a sequence of tickets, in order."""
        return [ticket.task.id for ticket in tickets]

    def _spec(fleet, task_id, **overrides):
        """One catalogue task as the raw mapping `submit` validates."""
        fields = dataclasses.asdict(fleet.make_task(task_id))
        fields.update(overrides)
        return fields

    def _kinds(queue):
        """The event kinds a queue has written, in order."""
        return [event["kind"] for event in queue.events]

    def _refuses(fleet, stage, value):
        """True when `stage.backoff(value)` refused with the queue's own error."""
        try:
            stage.backoff(value)
        except fleet.QueueError:
            return True
        except Exception as exc:                                  # noqa: BLE001
            raise AssertionError(
                "backoff(%r) raised %r instead of QueueError: the 1-based schedule "
                "has no answer for it and must say so" % (value, exc))
        return False

    import fleet
    import stage_02 as s2
    import stage_06 as s

    # --- the schedule is a pure, growing function of the attempt number ------
    assert s.BACKOFF_BASE == 2, (
        "BACKOFF_BASE is %r, not the 2 the retry schedule is built on"
        % (s.BACKOFF_BASE,))
    table = [s.backoff(n) for n in (1, 2, 3, 4, 5)]
    assert table == [1, 2, 4, 8, 16], (
        "backoff is not BACKOFF_BASE ** (attempt - 1) on a 1-based attempt "
        "number: the waits for attempts 1..5 were %r, not [1, 2, 4, 8, 16]"
        % (table,))
    assert all(isinstance(value, int) and not isinstance(value, bool)
               for value in table), (
        "backoff returned a non-int (a float schedule cannot be charged to an "
        "int clock): %r" % ([type(value).__name__ for value in table],))
    assert all(table[i] < table[i + 1] for i in range(len(table) - 1)), (
        "the retry schedule does not grow: a later attempt waits no longer than "
        "an earlier one, so a poison task is retried at full speed: %r"
        % (table,))
    for bad in (0, -1):
        assert _refuses(fleet, s, bad), (
            "backoff(%r) was answered instead of refused: the schedule is "
            "1-based and has no attempt 0 (a 0-based reading answers 2 ** -1, a "
            "float)" % (bad,))
    assert _refuses(fleet, s, True), (
        "backoff(True) was answered: a bool is not an attempt number, and "
        "True == 1 hides a caller that forgot to pass a count")
    assert _refuses(fleet, s, "2"), (
        "backoff('2') was answered: a string is not an attempt number")

    # --- a failed attempt is retried on the injected clock -------------------
    q = _queue(fleet, s2, now=10)
    ticket = q.submit(_spec(fleet, "render"))       # the default budget is 3
    retried = s.requeue(q, ticket, reason="failed")
    assert isinstance(retried, s2.Ticket), (
        "requeue of a task with attempts left returned %r, not a Ticket"
        % (type(retried).__name__,))
    assert retried.seq == ticket.seq, (
        "the retry lost the arrival's sequence number, so its place in the "
        "service order changed: %r vs %r" % (retried.seq, ticket.seq))
    assert retried.attempts == 1, (
        "the retry does not carry the one attempt that was made: attempts is %r"
        % (retried.attempts,))
    assert retried.ready_at == 11, (
        "the retry was not scheduled backoff(1) ticks after the injected clock's "
        "now (10 + 1): ready_at is %r" % (retried.ready_at,))
    assert q.clock.now() == 10, (
        "requeue moved the clock itself (now %r): only the scheduler advances "
        "the injected clock" % (q.clock.now(),))
    assert len(q.pending) == 1 and q.pending[0] is retried, (
        "the failed attempt did not leave exactly one pending ticket (the retry), "
        "so the task is queued twice or not at all: %r" % (_ids(q.pending),))
    assert q.decisions == _zeros(), (
        "requeue changed an admission decision: a retry is not an admission, and "
        "the counters are where the run's record comes from: %r" % (q.decisions,))
    assert _kinds(q) == ["submitted", "retried"], (
        "the retry was not recorded as a retried event after the submitted one: "
        "%r" % (_kinds(q),))
    event = q.events[-1]
    assert (event["at"], event["task"], event["reason"]) == (10, "render", "failed"), (
        "the retried event does not carry the tick, the task and the reason it "
        "was written for: %r" % (event,))
    assert event.get("attempt") == 1, (
        "the retried event does not say which attempt the retry is: %r" % (event,))

    # --- the second retry waits longer than the first ------------------------
    second = s.requeue(q, retried, reason="failed")
    assert isinstance(second, s2.Ticket) and second.attempts == 2, (
        "the second retry does not carry attempts == 2: %r"
        % (getattr(second, "attempts", second),))
    assert second.ready_at == 12, (
        "the second retry was not scheduled backoff(2) == 2 ticks after now: "
        "ready_at is %r" % (second.ready_at,))
    assert second.ready_at > retried.ready_at, (
        "the second retry waits less than the first (%r vs %r): the schedule is "
        "not growing" % (second.ready_at, retried.ready_at))
    assert len(q.pending) == 1 and q.pending[0] is second, (
        "a repeated requeue left more than one copy of the task in pending: %r"
        % (_ids(q.pending),))

    # --- due: a retry is not eligible before its ready_at --------------------
    assert s.due(q) == (), (
        "due returned a retry that is still waiting on its backoff: %r"
        % (_ids(s.due(q)),))
    q.clock.tick(1)                                  # now 11, one tick early
    assert s.due(q) == (), (
        "due returned the retry one tick before its ready_at: %r"
        % (_ids(s.due(q)),))
    q.clock.tick(1)                                  # now 12 == ready_at
    assert s.due(q) == (second,), (
        "due did not return a ticket that becomes ready exactly now (the "
        "boundary is <=, not <): %r" % (_ids(s.due(q)),))

    # --- due is a filter over the service order, not the arrival order -------
    q5 = _queue(fleet, s2)
    q5.submit(_spec(fleet, "index"))                  # priority 1
    q5.submit(_spec(fleet, "notify"))                 # priority 9
    q5.submit(_spec(fleet, "render"))                 # priority 5
    order = _ids(s.due(q5))
    assert order == ["notify", "render", "index"], (
        "due returned the pending list's arrival order instead of stage 3's "
        "service order: %r" % (order,))
    result = s.due(q5)
    assert isinstance(result, tuple) and result is not q5.pending, (
        "due returned %r rather than a fresh tuple: a caller can reorder the "
        "queue through it" % (type(result).__name__,))

    # --- a delayed ticket sits behind the due ones ---------------------------
    q6 = _queue(fleet, s2, now=5)
    q6.submit(_spec(fleet, "purge"))                  # priority 7, no ready_at
    high = q6.submit(_spec(fleet, "notify"))          # priority 9
    s.requeue(q6, high, reason="failed")             # ready at 5 + 1 == 6
    ids = _ids(s.due(q6))
    assert ids == ["purge"], (
        "due returned the not-yet-due retry (or dropped the ticket that is due): "
        "%r" % (ids,))
    q6.clock.tick(1)
    ids = _ids(s.due(q6))
    assert ids == ["notify", "purge"], (
        "the retry did not become due at its ready_at, or it lost its place in "
        "the service order: %r" % (ids,))

    empty = _queue(fleet, s2)
    assert s.due(empty) == (), (
        "due of an empty queue is not the empty tuple: %r" % (s.due(empty),))

    # --- the budget: the third failure is where the queue gives up -----------
    q2 = _queue(fleet, s2)
    t2 = q2.submit(_spec(fleet, "render"))            # budget 3
    r1 = s.requeue(q2, t2, reason="failed")
    assert isinstance(r1, s2.Ticket), (
        "the first failure of a task with 3 attempts was dead-lettered instead "
        "of retried: %r" % (r1,))
    r2 = s.requeue(q2, r1, reason="died")
    assert isinstance(r2, s2.Ticket) and r2.attempts == 2, (
        "the second failure of a task with 3 attempts was not retried with "
        "attempts == 2: %r" % (r2,))
    letter = s.requeue(q2, r2, reason="died")
    assert isinstance(letter, s2.DeadLetter), (
        "a task whose third and last attempt failed was retried again instead of "
        "dead-lettered, so a poison task runs forever: %r" % (letter,))
    assert letter.task.id == "render", (
        "the dead letter names %r, not the task that was given up on"
        % (letter.task.id,))
    assert letter.attempts == 3, (
        "the dead letter recorded %r attempts, not the 3 that were made: the "
        "record of how hard the queue tried is wrong" % (letter.attempts,))
    assert letter.reason == "died", (
        "the dead letter carries the reason %r, not the failure it gave up on"
        % (letter.reason,))
    assert letter.at == q2.clock.now() == 0, (
        "the dead letter is stamped at %r, not the tick it was recorded at (%r)"
        % (letter.at, q2.clock.now()))
    assert q2.dead == [letter], (
        "queue.dead holds %r, not the one dead letter that was returned"
        % (q2.dead,))
    assert _ids(q2.pending) == [], (
        "the dead-lettered task is still pending, so it is given up on and still "
        "queued: %r" % (_ids(q2.pending),))
    assert _kinds(q2) == ["submitted", "retried", "retried", "dead_lettered"], (
        "the run's record does not show two retries and then the dead letter: %r"
        % (_kinds(q2),))
    tried = [event["attempt"] for event in q2.events if event["kind"] == "retried"]
    assert tried == [1, 2], (
        "the retried events do not carry the increasing attempt numbers 1 and 2: "
        "%r" % (tried,))
    final = q2.events[-1]
    assert (final["task"], final["attempts"], final["reason"]) == ("render", 3, "died"), (
        "the dead_lettered event does not carry the task, the attempts made and "
        "the reason: %r" % (final,))
    assert s.due(q2) == (), (
        "a dead-lettered task is still returned by due: %r" % (_ids(s.due(q2)),))

    # --- a task with a budget of one attempt stops at the first failure ------
    q3 = _queue(fleet, s2, now=4)
    t3 = q3.submit(_spec(fleet, "purge", attempts=1))
    letter3 = s.requeue(q3, t3, reason="failed")
    assert isinstance(letter3, s2.DeadLetter), (
        "a task with a budget of one attempt was retried instead of "
        "dead-lettered: %r" % (letter3,))
    assert letter3.attempts == 1 and letter3.at == 4, (
        "the dead letter of a one-attempt task recorded attempts=%r at tick %r, "
        "not attempts=1 at the tick it happened" % (letter3.attempts, letter3.at))
    assert _ids(q3.pending) == [], (
        "the one-attempt task was dead-lettered but left pending: %r"
        % (_ids(q3.pending),))

    # --- dead_letter on its own: it removes a pending task and records it ----
    q4 = _queue(fleet, s2, now=7)
    first = q4.submit(_spec(fleet, "notify"))
    doomed = q4.submit(_spec(fleet, "digest"))
    letter4 = s.dead_letter(q4, doomed, "shed")
    assert isinstance(letter4, s2.DeadLetter), (
        "dead_letter returned %r, not the DeadLetter it recorded"
        % (type(letter4).__name__,))
    assert letter4.attempts == 0, (
        "the dead letter invented an attempt for a task that never ran: "
        "attempts is %r" % (letter4.attempts,))
    assert (letter4.reason, letter4.at) == ("shed", 7), (
        "the dead letter does not carry the reason and the tick it was given up "
        "at: %r" % (letter4,))
    assert q4.pending == [first], (
        "dead_letter left the task it recorded in pending, so it will be "
        "dispatched after being given up on: %r" % (_ids(q4.pending),))
    assert q4.dead == [letter4], (
        "queue.dead holds %r, not the dead letter dead_letter returned"
        % (q4.dead,))
    assert q4.decisions == _zeros(), (
        "dead_letter changed an admission decision: giving up on a task is not "
        "an admission: %r" % (q4.decisions,))
    last = q4.events[-1]
    assert (last["kind"], last["task"], last["attempts"], last["reason"]) == (
        "dead_lettered", "digest", 0, "shed"), (
        "the dead_lettered event does not carry the task, the attempts and the "
        "reason: %r" % (last,))

    # --- the schedule is anchored to now, not to the arrival -----------------
    q9 = _queue(fleet, s2, now=3)
    t9 = q9.submit(_spec(fleet, "render"))
    q9.clock.tick(4)                                 # now 7, four ticks later
    r9 = s.requeue(q9, t9, reason="failed")
    assert r9.submitted_at == 3, (
        "the retry lost the arrival's submission tick: %r" % (r9.submitted_at,))
    assert r9.ready_at == 8, (
        "the retry was scheduled from something other than the injected clock's "
        "now (7 + backoff(1) == 8): ready_at is %r (the ticket arrived at %r)"
        % (r9.ready_at, r9.submitted_at))

    print("check_06: 10 fixtures — backoff is a 1-based, growing function of the "
          "attempt; requeue schedules the retry on the injected clock and "
          "dead-letters at the task's budget; due is the service-ordered "
          "eligibility view")

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import dataclasses
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    DECISION_KEYS = ("admitted", "refused", "shed", "blocked", "limit_hits")

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    def _counts(**overrides):
        """A fresh zeroed counter bag with the named decisions set."""
        bag = {key: 0 for key in DECISION_KEYS}
        for key, value in overrides.items():
            assert key in bag, "the check itself asked for a key §3 does not fix: %r" % (key,)
            bag[key] = value
        return bag

    def _queue(fleet, stage_02, *, now=0, capacity=6, high_water=3, max_concurrency=4):
        """A queue over one pool, on a fresh clock that has already spent `now`."""
        pool = fleet.make_pool("wide", capacity=capacity, high_water=high_water,
                               max_concurrency=max_concurrency)
        clock = fleet.Clock(start=now)
        return stage_02.Queue(pool, clock=clock)

    def _spec(fleet, task_id, **overrides):
        """One catalogue task as the raw mapping `submit` validates."""
        fields = dataclasses.asdict(fleet.make_task(task_id))
        fields.update(overrides)
        return fields

    def _ids(tickets):
        """The task ids of a sequence of tickets, in order."""
        return [ticket.task.id for ticket in tickets]

    def _kinds(queue):
        """The kinds in the queue's record, in order."""
        return [event["kind"] for event in queue.events]

    def _arm(queue, stage_02, task, *, ticks=9, attempt=1):
        """One running flight, placed the way stage 4's `start` places it."""
        ticket = queue.submit(dataclasses.asdict(task))
        queue.pending.remove(ticket)
        started = queue.clock.now()
        flight = stage_02.Flight(ticket=ticket, attempt=attempt, started_at=started,
                                 finishes_at=started + ticks, deadline_at=None)
        queue.in_flight[task.id] = flight
        return flight

    def _raises(what, call, kind):
        """The exception `call` must raise: a return, or another type, is the bug."""
        try:
            got = call()
        except kind as refused:
            return refused
        except Exception as wrong:                                # noqa: BLE001
            raise AssertionError(
                "%s raised %s (%r) instead of %s: a caller cannot tell what "
                "happened" % (what, type(wrong).__name__, str(wrong), kind.__name__))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import fleet
    import stage_02 as s2
    import stage_03 as s3
    import stage_06 as s6
    import stage_07 as s

    # ---- the three policies, and the refusals this stage owns --------------

    assert s.POLICIES == ("refuse", "shed", "block"), (
        "POLICIES is %r, not the refuse/shed/block the stage is defined as"
        % (s.POLICIES,))
    assert all(isinstance(name, str) for name in s.POLICIES), (
        "POLICIES holds something that is not a policy name: %r" % (s.POLICIES,))

    assert issubclass(s.ShedError, fleet.QueueError), (
        "ShedError is not a QueueError, so a shed the queue could not perform "
        "is not the queue's own refusal: %r" % (s.ShedError.__mro__,))
    assert issubclass(s.BlockedError, fleet.QueueError), (
        "BlockedError is not a QueueError, so a blocked producer is not told by "
        "the queue's own refusal: %r" % (s.BlockedError.__mro__,))
    assert s.ShedError is not s.BlockedError, (
        "ShedError and BlockedError are the same type, so the caller cannot "
        "tell 'nothing to give up' from 'we will not take this wave'")
    assert not issubclass(s.BlockedError, s2.QueueFull), (
        "BlockedError is a QueueFull, so a caller cannot tell a queue that is "
        "out of room from a queue that is at its water mark: %r"
        % (s.BlockedError.__mro__,))

    # ---- below the mark every policy admits, through stage 2's submit ------

    for policy in s.POLICIES:
        q = _queue(fleet, s2, capacity=6, high_water=3, max_concurrency=2)
        for task_id in ("index", "notify", "purge"):        # depths 0, 1, 2
            got = s.admit(q, _spec(fleet, task_id), policy=policy)
            assert got == "admitted", (
                "a queue below its water mark (depth %r at the time, mark 3) "
                "answered %r under the %r policy: every policy admits while "
                "there is room under the mark"
                % (q.depth(), got, policy))
        assert q.depth() == 3, (
            "the three tasks admitted below the mark left a depth of %r, not 3"
            % (q.depth(),))
        assert q.decisions == _counts(admitted=3), (
            "admitting three tasks below the mark left the counters at %r: each "
            "admission is counted once, at the decision" % (q.decisions,))
        assert q.dead == [], (
            "a queue below its mark shed a task: %r" % (_ids(q.dead),))
        assert _kinds(q) == ["submitted", "admitted"] * 3, (
            "the record of three admissions is %r, not the submitted line "
            "followed by the admitted line for each" % (_kinds(q),))
        assert q.events[-1]["policy"] == policy, (
            "the admitted line does not name the policy it was decided under: "
            "%r" % (q.events[-1],))
        assert [ticket.seq for ticket in q.pending] == [0, 1, 2], (
            "the admitted tickets did not take the queue's arrival numbers 0, "
            "1, 2: %r — admission must go through stage 2's submit"
            % ([ticket.seq for ticket in q.pending],))
        assert all(ticket.attempts == 0 and ticket.submitted_at == 0
                   for ticket in q.pending), (
            "an admitted ticket arrived with attempts/submitted_at %r, not a "
            "fresh arrival at tick 0"
            % ([(ticket.attempts, ticket.submitted_at) for ticket in q.pending],))
        assert q.clock.ticks == 0, (
            "admit moved the injected clock by %r ticks: the scheduler is the "
            "only thing that advances it" % (q.clock.ticks,))

    # ---- the mark is `>=`, and it counts the work in flight ---------------

    q = _queue(fleet, s2, capacity=6, high_water=3, max_concurrency=2)
    for task_id in ("index", "render", "audit"):
        assert s.admit(q, _spec(fleet, task_id)) == "admitted"
    assert q.depth() == 3
    before = _ids(q.pending)
    refused = _raises(
        "admit() let a task past the water mark (depth 3, mark 3) under refuse",
        lambda: s.admit(q, _spec(fleet, "purge"), policy="refuse"), s2.QueueFull)
    assert type(refused) is s2.QueueFull, (
        "the refusal at the water mark raised %s, not the queue's own QueueFull"
        % (type(refused).__name__,))
    text = str(refused)
    assert "purge" in text and "high water" in text, (
        "the refusal does not name the task and why it was refused: %r" % (text,))
    assert q.depth() == 3 and _ids(q.pending) == before, (
        "the refused task changed the queue: depth %r, pending %r"
        % (q.depth(), _ids(q.pending)))
    assert q.decisions == _counts(admitted=3, refused=1), (
        "the refusal was counted as %r: the counters must show three admissions "
        "and one refusal, bumped where the decision was taken" % (q.decisions,))
    assert _kinds(q) == ["submitted", "admitted"] * 3 + ["refused"], (
        "the refused task wrote a submitted line (or none at all): %r — a task "
        "that never entered has no arrival" % (_kinds(q),))
    last = q.events[-1]
    assert last["task"] == "purge" and last["at"] == 0, (
        "the refusal does not name the task it refused and the tick it "
        "happened: %r" % (last,))
    assert last["reason"] == "high_water", (
        "the refusal does not say why (the water mark): %r" % (last,))

    # ---- a queue whose depth is all in flight is at the mark --------------

    q = _queue(fleet, s2, capacity=4, high_water=2, max_concurrency=4)
    _arm(q, s2, fleet.make_task("index"))                   # priority 1
    _arm(q, s2, fleet.make_task("train"))                   # priority 3
    assert q.depth() == 2 and q.queued() == 0, (
        "the fixture is wrong: depth %r, queued %r" % (q.depth(), q.queued()))
    running = dict(q.in_flight)
    refused = _raises(
        "admit() admitted past the mark because it measured the pending list "
        "instead of depth() (queued 0, but two tasks are running)",
        lambda: s.admit(q, _spec(fleet, "notify"), policy="refuse"), s2.QueueFull)
    assert type(refused) is s2.QueueFull
    assert q.depth() == 2 and q.in_flight == running and q.pending == [], (
        "the refused task disturbed a queue whose work is all in flight: depth "
        "%r, in_flight %r, pending %r"
        % (q.depth(), sorted(q.in_flight), _ids(q.pending)))
    assert q.decisions == _counts(refused=1), (
        "the refusal of a queue full of running work counted %r" % (q.decisions,))

    # ---- shed with nothing waiting to give up is its own refusal ----------

    q = _queue(fleet, s2, capacity=4, high_water=2, max_concurrency=4)
    _arm(q, s2, fleet.make_task("index"))
    _arm(q, s2, fleet.make_task("train"))
    nothing = _raises(
        "shed admitted a task while every task the queue counted was running "
        "(nothing pending to give up)",
        lambda: s.admit(q, _spec(fleet, "notify"), policy="shed"), s.ShedError)
    assert type(nothing) is s.ShedError, (
        "a shed with nothing to shed raised %s, not the stage's ShedError"
        % (type(nothing).__name__,))
    assert q.depth() == 2 and q.dead == [] and q.pending == [], (
        "the failed shed changed the queue: depth %r, dead %r, pending %r"
        % (q.depth(), _ids(q.dead), _ids(q.pending)))
    assert q.decisions == _counts(refused=1), (
        "a shed that could not be performed was counted as %r: the input was "
        "refused, and the counters say so" % (q.decisions,))
    assert _kinds(q)[-1] == "refused", (
        "the failed shed wrote %r, not a refused line" % (_kinds(q)[-1],))

    # ---- block: the producer keeps the task, and nothing is queued --------

    q = _queue(fleet, s2, capacity=6, high_water=3, max_concurrency=4)
    for task_id in ("index", "render", "audit"):
        assert s.admit(q, _spec(fleet, task_id)) == "admitted"
    before = _ids(q.pending)
    blocked = _raises(
        "block queued the task anyway at the water mark (depth 3, mark 3)",
        lambda: s.admit(q, _spec(fleet, "notify"), policy="block"), s.BlockedError)
    assert type(blocked) is s.BlockedError, (
        "the block policy raised %s, not the stage's BlockedError: a caller "
        "cannot tell 'wait' from 'the queue is full'"
        % (type(blocked).__name__,))
    text = str(blocked)
    assert "notify" in text and "high water" in text, (
        "the block refusal does not name the task and the mark: %r" % (text,))
    assert q.depth() == 3 and _ids(q.pending) == before, (
        "block changed the queue: depth %r, pending %r"
        % (q.depth(), _ids(q.pending)))
    assert q.dead == [] and q.in_flight == {}, (
        "the block policy shed a task or started one: dead %r, in_flight %r"
        % (_ids(q.dead), sorted(q.in_flight)))
    assert q.decisions == _counts(admitted=3, blocked=1), (
        "the block counted %r: three admissions and one block, no refused and "
        "no shed" % (q.decisions,))
    assert _kinds(q)[-1] == "blocked", (
        "the block wrote %r, not a blocked line" % (_kinds(q)[-1],))
    last = q.events[-1]
    assert last["task"] == "notify" and last["at"] == 0 and last["reason"], (
        "the blocked line does not name the task, the tick and why: %r" % (last,))

    # ---- shed gives up the lowest-order pending ticket, and nothing else --

    q = _queue(fleet, s2, capacity=6, high_water=3, max_concurrency=4)
    for task_id in ("purge", "train", "digest"):            # 7, 3, 6
        q.submit(_spec(fleet, task_id))
    expected = sorted(q.pending, key=s3.order_key)[-1]
    assert expected.task.id == "train", (
        "the fixture is wrong: stage 3's lowest order is %r" % (expected.task.id,))
    got = s.admit(q, _spec(fleet, "notify"), policy="shed")      # priority 9
    assert got == "shed", (
        "the shed policy returned %r, not the decision it performed" % (got,))
    assert q.dead and q.dead[0].task.id == "train", (
        "shed gave up %r, not the lowest-order pending ticket (train, priority "
        "3): the newest arrival is digest and the highest-order is purge"
        % ([letter.task.id for letter in q.dead],))
    letter = q.dead[0]
    assert (letter.reason, letter.attempts, letter.at) == ("shed", 0, 0), (
        "the shed dead letter is %r, not a never-run task at tick 0 with the "
        "reason 'shed'" % (letter,))
    assert q.depth() == 3, (
        "shed left a depth of %r, not the mark it started at: one task left and "
        "one entered" % (q.depth(),))
    assert sorted(_ids(q.pending)) == ["digest", "notify", "purge"], (
        "after the shed the queue holds %r, not the two survivors and the new "
        "task" % (_ids(q.pending),))
    assert "train" not in _ids(q.pending), (
        "the shed task is still pending, so it is given up on and still queued: "
        "%r" % (_ids(q.pending),))
    assert q.decisions == _counts(admitted=0, shed=1), (
        "the shed decision left the counters at %r: one shed, and no admission "
        "(the decision taken was 'shed')" % (q.decisions,))
    assert _kinds(q) == ["submitted"] * 3 + ["dead_lettered", "submitted", "shed"], (
        "the record of a shed is %r, not the victim's dead_lettered line, then "
        "the submitted line of the task that took its place, then the shed "
        "decision" % (_kinds(q),))
    assert q.events[-1]["task"] == "train", (
        "the shed decision names %r, not the task that was given up"
        % (q.events[-1]["task"],))
    assert q.clock.ticks == 0 and q.clock.now() == 0, (
        "the shed moved the injected clock: %r" % (q.clock,))

    # ---- the tie in the order is broken by arrival, not by list position --

    q = _queue(fleet, s2, capacity=6, high_water=3, max_concurrency=4)
    q.submit(_spec(fleet, "render", priority=3))            # seq 0, the oldest
    q.submit(_spec(fleet, "audit", priority=3))             # seq 1, the tie
    q.submit(_spec(fleet, "notify", priority=9))
    got = s.admit(q, _spec(fleet, "purge", priority=7), policy="shed")
    assert got == "shed"
    assert q.dead[0].task.id == "audit", (
        "the tie at priority 3 was broken by %r instead of by arrival: the "
        "lowest order is the later arrival (audit), and the pick stayed "
        "deterministic instead of leaning on the list's order"
        % (q.dead[0].task.id,))

    # ---- running work is never shed --------------------------------------

    q = _queue(fleet, s2, capacity=6, high_water=3, max_concurrency=4)
    flight = _arm(q, s2, fleet.make_task("index"))          # priority 1: the
    q.submit(_spec(fleet, "purge"))                         # lowest order of
    q.submit(_spec(fleet, "render"))                        # all, and running
    q.submit(_spec(fleet, "digest"))
    assert q.depth() == 4
    kept = dict(q.in_flight)
    got = s.admit(q, _spec(fleet, "notify"), policy="shed")
    assert got == "shed"
    assert q.in_flight == kept, (
        "shed reached into the running tasks (%r): a worker is holding that "
        "task, and dead-lettering it would leave it running and finished at "
        "once" % (sorted(q.in_flight),))
    assert q.dead[0].task.id == "render", (
        "shed gave up %r, not the lowest-order *pending* ticket (render, "
        "priority 5); the in-flight index is lower order and must be left alone"
        % (q.dead[0].task.id,))
    assert q.depth() == 4, (
        "the shed against a queue with running work left a depth of %r, not 4"
        % (q.depth(),))

    # ---- making the room happens before the task goes in ------------------

    q = _queue(fleet, s2, capacity=3, high_water=2, max_concurrency=1)
    for task_id in ("index", "train", "purge"):
        q.submit(_spec(fleet, task_id))
    assert q.is_full() and q.depth() == 3, (
        "the fixture is wrong: depth %r, full %r" % (q.depth(), q.is_full()))
    got = s.admit(q, _spec(fleet, "notify"), policy="shed")
    assert got == "shed", (
        "a shed at capacity returned %r: the victim must be released before the "
        "new task goes in, or stage 2's submit refuses it" % (got,))
    assert q.depth() == 3, (
        "the shed at capacity left a depth of %r, not the capacity it started "
        "at" % (q.depth(),))
    assert q.dead[0].task.id == "index", (
        "shed gave up %r, not the lowest-order pending ticket (index)" 
        % (q.dead[0].task.id,))
    assert sorted(_ids(q.pending)) == ["notify", "purge", "train"], (
        "the queue holds %r after the shed at capacity" % (_ids(q.pending),))

    # ---- the counters are bumped where the decision is taken -------------

    q = _queue(fleet, s2, capacity=6, high_water=3, max_concurrency=4)
    for task_id in ("index", "render", "audit"):
        assert s.admit(q, _spec(fleet, task_id)) == "admitted"
    events, decisions, depth = list(q.events), dict(q.decisions), q.depth()
    unknown = _raises(
        "an unknown policy was answered instead of refused naming the known "
        "policies", lambda: s.admit(q, _spec(fleet, "notify"), policy="shedd"),
        fleet.QueueError)
    text = str(unknown)
    assert not isinstance(unknown, (s2.QueueFull, s.ShedError, s.BlockedError)), (
        "the unknown policy fell through to the %s branch: a typo in a policy "
        "must be refused where the policies are known, not treated as one of "
        "them" % (type(unknown).__name__,))
    assert all(name in text for name in ("refuse", "shed", "block")), (
        "the refusal of the unknown policy does not name the known ones: %r"
        % (text,))
    assert q.events == events and q.decisions == decisions and q.depth() == depth, (
        "the unknown policy changed the queue before the refusal: events %r, "
        "decisions %r, depth %r"
        % (_kinds(q), q.decisions, q.depth()))

    q = _queue(fleet, s2, capacity=6, high_water=3, max_concurrency=4)
    unknown = _raises(
        "an unknown policy was admitted below the water mark (the policy check "
        "must not depend on the depth)",
        lambda: s.admit(q, _spec(fleet, "notify"), policy="refuse!"), fleet.QueueError)
    assert q.depth() == 0 and q.events == [] and q.decisions == _counts(), (
        "the unknown policy admitted a task below the mark: depth %r, events "
        "%r, decisions %r" % (q.depth(), _kinds(q), q.decisions))

    # ---- the invariant: every input ends admitted, shed, or refused -------

    offered = ["index", "train", "purge", "notify", "render", "digest"]

    q = _queue(fleet, s2, capacity=4, high_water=2, max_concurrency=2)
    answers = []
    for task_id in offered:
        try:
            answers.append(s.admit(q, _spec(fleet, task_id), policy="refuse"))
        except s2.QueueFull:
            answers.append("refused")
        assert q.depth() <= q.pool.capacity, (
            "the refuse policy queued past capacity: depth %r of %r"
            % (q.depth(), q.pool.capacity))
    assert answers == ["admitted", "admitted", "refused", "refused", "refused",
                       "refused"], (
        "the refuse policy answered %r for the six arrivals: the mark is 2, so "
        "the first two go in and the rest keep their task" % (answers,))
    assert q.decisions == _counts(admitted=2, refused=4), (
        "the refuse run counted %r" % (q.decisions,))

    q = _queue(fleet, s2, capacity=4, high_water=2, max_concurrency=2)
    answers = []
    for task_id in offered:
        answers.append(s.admit(q, _spec(fleet, task_id), policy="shed"))
        assert q.depth() <= q.pool.capacity, (
            "the shed policy queued past capacity: depth %r of %r"
            % (q.depth(), q.pool.capacity))
    assert answers == ["admitted", "admitted", "shed", "shed", "shed", "shed"], (
        "the shed policy answered %r for the six arrivals" % (answers,))
    assert q.depth() == 2 and len(q.dead) == 4, (
        "the shed run ended with depth %r and %r dead letters, not a steady 2 "
        "and the four it gave up" % (q.depth(), len(q.dead)))
    assert sorted(_ids(q.pending)) == ["digest", "notify"], (
        "the shed run kept %r, not the two highest-order arrivals"
        % (_ids(q.pending),))
    assert [letter.task.id for letter in q.dead] == ["index", "train", "purge",
                                                    "render"], (
        "the shed run gave up %r, not the lowest-order ticket each time"
        % ([letter.task.id for letter in q.dead],))
    assert all(letter.reason == "shed" for letter in q.dead), (
        "a shed dead letter carries no reason: %r"
        % ([letter.reason for letter in q.dead],))
    seen = set(_ids(q.pending)) | set(q.in_flight) | {letter.task.id
                                                      for letter in q.dead}
    assert seen == set(offered), (
        "the shed run lost a task: it holds %r, not everything offered"
        % (sorted(seen),))
    assert q.decisions == _counts(admitted=2, shed=4), (
        "the shed run counted %r" % (q.decisions,))

    q = _queue(fleet, s2, capacity=4, high_water=2, max_concurrency=2)
    answers = []
    for task_id in offered:
        try:
            answers.append(s.admit(q, _spec(fleet, task_id), policy="block"))
        except s.BlockedError:
            answers.append("blocked")
        assert q.depth() <= q.pool.capacity, (
            "the block policy queued past capacity: depth %r of %r"
            % (q.depth(), q.pool.capacity))
    assert answers == ["admitted", "admitted", "blocked", "blocked", "blocked",
                       "blocked"], (
        "the block policy answered %r for the six arrivals" % (answers,))
    assert _ids(q.pending) == ["index", "train"] and q.dead == [], (
        "the block run changed the queue it had: pending %r, dead %r"
        % (_ids(q.pending), _ids(q.dead)))
    assert q.decisions == _counts(admitted=2, blocked=4), (
        "the block run counted %r" % (q.decisions,))

    # ---- a retry that is still waiting is pending, and may be shed --------

    q = _queue(fleet, s2, capacity=4, high_water=2, max_concurrency=2)
    q.submit(_spec(fleet, "notify"))                        # priority 9
    train = q.submit(_spec(fleet, "train"))                 # priority 3
    delayed = s6.requeue(q, train, reason="failed")
    assert delayed.ready_at == 1 and q.clock.now() == 0, (
        "the fixture is wrong: the retry is ready at %r" % (delayed.ready_at,))
    got = s.admit(q, _spec(fleet, "purge"), policy="shed")
    assert got == "shed"
    assert q.dead[0].task.id == "train", (
        "shed gave up %r: a pending retry waiting on its backoff is still "
        "pending, and train is the lowest-order one" % (q.dead[0].task.id,))
    assert q.dead[0].attempts == 1, (
        "the shed dead letter records %r attempts, not the one the retry "
        "carried" % (q.dead[0].attempts,))
    assert _ids(q.pending) == ["notify", "purge"], (
        "the queue holds %r after shedding the delayed retry"
        % (_ids(q.pending),))

    print("check_07: 14 fixtures — the water mark is compared against depth(); "
          "every policy admits below it; refuse raises QueueFull, shed gives up "
          "the lowest-order pending ticket through stage 6 and then admits, "
          "block raises BlockedError; the counters are bumped where the "
          "decision is taken and nothing is lost")

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import dataclasses
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    def _queue(fleet, stage_02, *, now=0, capacity=16, max_concurrency=4):
        """A wide queue on a fresh clock that has already spent `now` ticks."""
        pool = fleet.make_pool("wide", capacity=capacity, max_concurrency=max_concurrency)
        clock = fleet.Clock()
        if now:
            clock.tick(now)
        return stage_02.Queue(pool, clock=clock)

    def _submit(queue, fleet, task_id):
        """Submit one catalogue task through the queue and return its ticket."""
        queue.submit(dataclasses.asdict(fleet.make_task(task_id)))
        return queue.pending[-1]

    def _ids(tickets):
        """The task ids of a sequence of tickets, in order."""
        return [ticket.task.id for ticket in tickets]

    import fleet
    import stage_02 as s2
    import stage_03 as s3
    import stage_08 as s

    # --- the two dials are the numbers the stage fixes ----------------------
    assert s.AGE_STEP == 4, (
        "AGE_STEP is %r, not the 4 ticks that buy one priority step"
        % (s.AGE_STEP,))
    assert s.AGE_LIMIT == 20, (
        "AGE_LIMIT is %r, not the 20 ticks past which a pending task is starved"
        % (s.AGE_LIMIT,))

    # --- waited: a pending ticket ages on the caller's clock ----------------
    q = _queue(fleet, s2)
    index = _submit(q, fleet, "index")            # seq 0, arrived at tick 0, p1
    assert (index.seq, index.submitted_at, index.task.priority) == (0, 0, 1), (
        "the fixture did not land at arrival 0 with priority 1: %r"
        % ((index.seq, index.submitted_at, index.task.priority),))
    assert s.waited(index, now=7) == 7, (
        "a ticket that arrived at tick 0 has waited something other than seven "
        "ticks at tick 7: %r" % (s.waited(index, now=7),))
    assert isinstance(s.waited(index, now=7), int), (
        "waited returned %r, a %s, instead of a whole number of ticks"
        % (s.waited(index, now=7), type(s.waited(index, now=7)).__name__))
    assert s.waited(index, now=0) == 0, (
        "a ticket that has just arrived has already waited: %r"
        % (s.waited(index, now=0),))
    held = dataclasses.replace(index, ready_at=40)
    assert s.waited(held, now=5) == 5, (
        "the wait of a ticket whose ready_at is in the future was measured from "
        "ready_at instead of from its arrival, so a backoff reports a negative "
        "wait: %r" % (s.waited(held, now=5),))

    # --- no clock named, no wait to report ----------------------------------
    q0 = _queue(fleet, s2, now=8)
    later = _submit(q0, fleet, "index")           # arrived at tick 8
    assert later.submitted_at == 8, "the fixture did not arrive at tick 8: %r" % (later,)
    assert s.waited(later) == 0, (
        "waited answered without any clock named — it reported %r for a ticket "
        "that arrived at tick 8; a wait measured against a clock the caller "
        "never named is the second clock this stage exists to refuse"
        % (s.waited(later),))

    # --- effective_priority: a step per AGE_STEP ticks, and a ceiling -------
    assert s.effective_priority(index, now=0) == 1, (
        "a priority-1 ticket that has just arrived is worth %r, not 1: the boost "
        "is already lifting a task that has not waited"
        % (s.effective_priority(index, now=0),))
    assert s.effective_priority(index, now=3) == 1, (
        "a priority-1 ticket that waited 3 of the 4 ticks a step costs was "
        "lifted anyway: %r" % (s.effective_priority(index, now=3),))
    assert s.effective_priority(index, now=4) == 2, (
        "a priority-1 ticket that waited AGE_STEP ticks is worth %r, not 2"
        % (s.effective_priority(index, now=4),))
    assert isinstance(s.effective_priority(index, now=4), int), (
        "effective_priority returned %r, a %s: every number in this course is an "
        "int count" % (s.effective_priority(index, now=4),
                       type(s.effective_priority(index, now=4)).__name__))
    assert s.effective_priority(index, now=24) == 7, (
        "a priority-1 ticket that waited 24 ticks is worth %r, not the six steps "
        "24 // AGE_STEP buy: %r" % (s.effective_priority(index, now=24),
                                    s.effective_priority(index, now=24)))
    assert s.effective_priority(index, now=32) == 9, (
        "a priority-1 ticket that waited 32 ticks is worth %r, not the ceiling 9"
        % (s.effective_priority(index, now=32),))
    assert s.effective_priority(index, now=400) == 9, (
        "a very old priority-1 ticket is worth %r: the boost must be capped at "
        "the top priority, or it outranks the interactive tenant forever"
        % (s.effective_priority(index, now=400),))
    ladder = [s.effective_priority(index, now=now) for now in range(0, 64, 4)]
    assert ladder == sorted(ladder) and all(1 <= value <= 9 for value in ladder), (
        "the aged priority is not monotone in the wait, or has left [priority, "
        "ceiling]: %r" % (ladder,))
    q_mid = _queue(fleet, s2)
    purge = _submit(q_mid, fleet, "purge")        # priority 7
    assert s.effective_priority(purge, now=0) == 7, (
        "a priority-7 ticket that has just arrived is worth %r, not 7: waiting "
        "is not a licence to raise a task that did not wait"
        % (s.effective_priority(purge, now=0),))
    assert s.effective_priority(purge, now=8) == 9, (
        "two steps of waiting did not carry a priority-7 ticket to the ceiling: "
        "%r" % (s.effective_priority(purge, now=8),))
    assert s.effective_priority(purge, now=400) == 9, (
        "a very old priority-7 ticket is worth %r, not the ceiling 9"
        % (s.effective_priority(purge, now=400),))

    # --- fixture A: the interactive flood, and the batch task it starves ----
    q_a = _queue(fleet, s2)                       # clock at 0
    old_index = _submit(q_a, fleet, "index")      # seq 0, arrived 0, p1 (batch)
    q_a.clock.tick(24)
    notify = _submit(q_a, fleet, "notify")        # seq 1, arrived 24, p9
    q_a.clock.tick(8)                             # now = 32
    assert q_a.clock.now() == 32, "the fixture clock is %r, not 32" % (q_a.clock.now(),)
    assert (s.waited(old_index, now=32), s.waited(notify, now=32)) == (32, 8), (
        "the fixture's waits are not (32, 8): %r"
        % ((s.waited(old_index, now=32), s.waited(notify, now=32)),))
    assert s.effective_priority(old_index, now=32) == 9, (
        "the batch task that waited 32 ticks is worth %r, not the capped 9: the "
        "fixture cannot show the aged order serving it otherwise"
        % (s.effective_priority(old_index, now=32),))
    assert s.effective_priority(notify, now=32) == 9, (
        "the fresh interactive task is worth %r, not the capped 9: the tie the "
        "arrival order settles is not there" % (s.effective_priority(notify, now=32),))
    assert _ids(s3.reorder(q_a)) == ["notify", "index"], (
        "stage 3's order no longer puts the fresh interactive task first, so this "
        "fixture starves nobody: %r" % (_ids(s3.reorder(q_a)),))
    assert s3.order_key(old_index) == (-1, 0), (
        "stage 3's order_key was changed by this stage: it is %r, not the raw "
        "(-priority, seq)" % (s3.order_key(old_index),))
    assert s3.pick_next(q_a).task.id == "notify", (
        "the unaged order started the batch task, so ageing is not what served "
        "it: %r" % (s3.pick_next(q_a).task.id,))
    assert _ids(s.reorder_aged(q_a)) == ["index", "notify"], (
        "the aged order did not serve the batch task the unaged order starves: "
        "both are worth 9 once the boost is capped, and arrival must decide: %r"
        % (_ids(s.reorder_aged(q_a)),))
    assert _ids(s.starved(q_a)) == ["index"], (
        "the task that waited 32 ticks was not the one reported starved (or the "
        "one that waited 8 was): %r" % (_ids(s.starved(q_a)),))
    assert _ids(s.reorder_aged(q_a, now=24)) == ["notify", "index"], (
        "reorder_aged ignored the now it was handed and read the queue's clock "
        "instead: at tick 24 the batch task is worth only 7: %r"
        % (_ids(s.reorder_aged(q_a, now=24)),))

    # --- fixture B: the aged tie at the ceiling, with pending out of order --
    q_b = _queue(fleet, s2)
    publish = _submit(q_b, fleet, "publish")      # seq 0, arrived 0, p9
    q_b.clock.tick(8)
    notify = _submit(q_b, fleet, "notify")        # seq 1, arrived 8, p9
    q_b.clock.tick(24)                            # now = 32
    assert (s.waited(publish, now=32), s.effective_priority(publish, now=32)) == (32, 9), (
        "publish is not (waited 32, worth 9): %r"
        % ((s.waited(publish, now=32), s.effective_priority(publish, now=32)),))
    assert (s.waited(notify, now=32), s.effective_priority(notify, now=32)) == (24, 9), (
        "notify is not (waited 24, worth 9): %r"
        % ((s.waited(notify, now=32), s.effective_priority(notify, now=32)),))
    q_b.pending.append(q_b.pending.pop(0))        # what a requeue leaves behind
    assert _ids(q_b.pending) == ["notify", "publish"], (
        "the fixture did not put pending out of arrival order: %r"
        % (_ids(q_b.pending),))
    assert _ids(s.reorder_aged(q_b)) == ["publish", "notify"], (
        "the aged tie at 9 was broken by id, newest-first, or by the pending "
        "list's stale order instead of by arrival: %r" % (_ids(s.reorder_aged(q_b)),))
    aged_b = s.reorder_aged(q_b)
    assert isinstance(aged_b, tuple) and aged_b is not q_b.pending, (
        "reorder_aged returned %r, not a fresh tuple: a caller can reorder the "
        "queue through the value it was handed" % (type(aged_b).__name__,))
    assert _ids(q_b.pending) == ["notify", "publish"], (
        "reorder_aged mutated queue.pending, destroying the arrival record a "
        "requeue left behind: %r" % (_ids(q_b.pending),))

    # --- a fresh interactive task still outranks a barely aged low one ------
    q_e = _queue(fleet, s2)
    old_index = _submit(q_e, fleet, "index")      # seq 0, arrived 0, p1
    q_e.clock.tick(4)
    fresh_notify = _submit(q_e, fleet, "notify")  # seq 1, arrived 4, p9
    q_e.clock.tick(4)                             # now = 8
    assert s.effective_priority(old_index, now=8) == 3, (
        "a priority-1 task that waited 8 ticks is worth %r, not 3"
        % (s.effective_priority(old_index, now=8),))
    assert s.effective_priority(fresh_notify, now=8) == 9, (
        "a priority-9 task that waited 4 ticks is worth %r, not the capped 9"
        % (s.effective_priority(fresh_notify, now=8),))
    assert _ids(s.reorder_aged(q_e)) == ["notify", "index"], (
        "the aged order served the oldest ticket instead of the higher-priority "
        "one: the key is (effective priority, seq), and ageing does not hand the "
        "queue to whoever arrived first: %r" % (_ids(s.reorder_aged(q_e)),))
    assert _ids(q_e.pending) == ["index", "notify"], (
        "reorder_aged mutated queue.pending: %r" % (_ids(q_e.pending),))

    # --- a delayed ticket is still waiting, and still in the aged order -----
    q_d = _queue(fleet, s2)
    held = _submit(q_d, fleet, "index")
    q_d.pending[0] = dataclasses.replace(held, ready_at=100)
    q_d.clock.tick(32)
    assert s.effective_priority(q_d.pending[0], now=32) == 9, (
        "the delayed ticket is not aged: a backoff does not stop the clock it "
        "arrived on: %r" % (s.effective_priority(q_d.pending[0], now=32),))
    assert _ids(s.reorder_aged(q_d)) == ["index"], (
        "reorder_aged dropped the ticket whose ready_at is in the future: it is "
        "the whole pending list, delayed tickets included: %r"
        % (_ids(s.reorder_aged(q_d)),))
    assert _ids(s.starved(q_d)) == ["index"], (
        "a delayed ticket that has waited past the limit is still starved: %r"
        % (_ids(s.starved(q_d)),))

    # --- a running ticket is not waiting, and is not starving ---------------
    q_c = _queue(fleet, s2)
    running = _submit(q_c, fleet, "index")        # arrived at tick 0
    q_c.clock.tick(40)
    taken = s3.take_next(q_c)
    assert taken is running, (
        "the fixture could not take the ticket it submitted: %r"
        % (None if taken is None else taken.task.id,))
    q_c.in_flight[taken.task.id] = s2.Flight(
        ticket=taken, attempt=1, started_at=0, finishes_at=9, deadline_at=None)
    flight = q_c.in_flight["index"]
    assert s.waited(flight, now=40) == 0, (
        "waited measured a running task's submission time: a ticket in flight is "
        "being served and its wait is over, not %r" % (s.waited(flight, now=40),))
    assert s.starved(q_c, now=40) == (), (
        "starved counted an in-flight ticket, or is not a tuple at all: the task "
        "is being served, and the report is about the tasks that are not: %r"
        % (s.starved(q_c, now=40),))
    assert isinstance(s.starved(q_c, now=40), tuple), (
        "starved returned %r, not a tuple"
        % (type(s.starved(q_c, now=40)).__name__,))
    assert s.reorder_aged(q_c, now=40) == (), (
        "reorder_aged dragged an in-flight ticket back into the pending order, "
        "or is not a tuple: %r" % (s.reorder_aged(q_c, now=40),))

    # --- starved: the boundary is >, and the limit belongs to the caller ----
    q_l = _queue(fleet, s2)
    _submit(q_l, fleet, "index")                  # arrived at tick 0
    assert s.starved(q_l, now=5) == (), (
        "starved reported a ticket that has waited 5 of the 20 ticks it is "
        "allowed: %r" % (s.starved(q_l, now=5),))
    assert s.starved(q_l, now=10) == (), (
        "the default limit is not AGE_LIMIT (20): a ticket that waited 10 ticks "
        "was reported starved: %r" % (s.starved(q_l, now=10),))
    assert s.starved(q_l, now=20) == (), (
        "a ticket that waited exactly the limit was reported starved: the "
        "boundary is >, not >=: %r" % (s.starved(q_l, now=20),))
    assert _ids(s.starved(q_l, now=21)) == ["index"], (
        "a ticket that waited one tick past the limit was not reported starved, "
        "or the now it was handed was ignored: %r" % (_ids(s.starved(q_l, now=21)),))
    assert s.starved(q_l, now=21, limit=21) == (), (
        "starved ignored the limit it was handed and used AGE_LIMIT instead: %r"
        % (s.starved(q_l, now=21, limit=21),))
    assert _ids(s.starved(q_l, now=21, limit=5)) == ["index"], (
        "starved ignored the limit it was handed: %r"
        % (_ids(s.starved(q_l, now=21, limit=5)),))
    assert _ids(s.starved(q_l, now=30)) == ["index"], (
        "the task the stage fixes as starved at 30 ticks was not: %r"
        % (_ids(s.starved(q_l, now=30)),))

    # --- an empty queue is not an error -------------------------------------
    q_empty = _queue(fleet, s2)
    assert s.reorder_aged(q_empty) == (), (
        "reorder_aged of an empty queue is not the empty tuple: %r"
        % (s.reorder_aged(q_empty),))
    assert s.starved(q_empty) == (), (
        "starved of an empty queue is not the empty tuple: %r"
        % (s.starved(q_empty),))

    print("check_08: 57 assertions — waited ages a pending ticket on the caller's "
          "clock and nothing else, the boost is one step per AGE_STEP ticks "
          "capped at 9, the aged order keeps stage 3's seq tie-break on a "
          "fixture the unaged order starves, and starved counts pending tickets "
          "past the limit")

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import dataclasses
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    def _queue(fleet, stage_02, *, start=0, pool_id="bulk", capacity=16,
               concurrency=4):
        """A queue over a pool whose id is not a catalogue id, on a fresh clock.

        `start` is the clock's reading, so a run whose clock already spent ticks is
        a run where `clock.now()` and `clock.ticks` disagree.
        """
        pool = fleet.make_pool(pool_id, capacity=capacity, max_concurrency=concurrency)
        return stage_02.Queue(pool, clock=fleet.Clock(start=start))

    def _spec(fleet, task_id, **overrides):
        """One catalogue task as the raw mapping `submit` validates."""
        fields = dataclasses.asdict(fleet.make_task(task_id))
        fields.update(overrides)
        return fields

    def _kinds(queue):
        """The event kinds a queue has written, in order."""
        return [line["kind"] for line in queue.events]

    def _refusal(fleet, stage, queue, kind):
        """The `QueueError` event() raised for an unknown kind, or None."""
        try:
            stage.event(queue, kind)
        except fleet.QueueError as error:
            return error
        except Exception as error:                                # noqa: BLE001
            raise AssertionError(
                "event(%r) raised %r instead of the queue's own QueueError: a run's "
                "log has twelve kinds and this is not one of them" % (kind, error))
        return None

    import fleet
    import stage_02 as s2
    import stage_04 as s4
    import stage_09 as s

    counts = ("submitted", "admitted", "refused", "shed", "blocked", "started",
              "succeeded", "failed", "died", "retried", "dead_lettered")

    # --- the record's shape is fixed --------------------------------------
    assert s.RUN_KEYS == ("pool", "tasks", "submitted", "admitted", "refused",
                          "shed", "blocked", "started", "succeeded", "failed",
                          "died", "retried", "dead_lettered", "max_in_flight",
                          "final_depth", "ticks", "stopped"), (
        "RUN_KEYS is not §4.9's seventeen keys in that order, so a reader that "
        "unpacks the record reads the wrong field: %r" % (s.RUN_KEYS,))

    # --- event: the one writer of the log ---------------------------------
    q = _queue(fleet, s2, start=7, capacity=8, concurrency=2)
    line = s.event(q, "submitted", task="render")
    assert q.events and line == q.events[-1], (
        "event returned %r but appended nothing to the log: %r"
        % (line, q.events))
    assert (line["at"], line["kind"], line["task"]) == (7, "submitted", "render"), (
        "the line does not carry the queue's clock (now %r), the kind and the "
        "task: %r" % (q.clock.now(), line))
    extra = s.event(q, "started", task="index", note="second")
    assert extra.get("note") == "second", (
        "the fields the caller passed were dropped from the line, so a line "
        "cannot say why it was written: %r" % (extra,))
    assert len(q.events) == 2 and _kinds(q) == ["submitted", "started"], (
        "event did not append the lines it returned, in order: %r" % (_kinds(q),))

    before = list(q.events)
    error = _refusal(fleet, s, q, "exploded")
    assert error is not None, (
        "the unknown kind 'exploded' was accepted: the log then carries a line "
        "no RUN_KEYS key will ever count, and the record summarises a log it "
        "cannot see the whole of — the log is now %r" % (_kinds(q),))
    assert "exploded" in str(error), (
        "the refusal does not name the kind it refused, so a typo ('suceeded') "
        "reads as a run with no successes instead of as a bug: %r" % (str(error),))
    assert q.events == before, (
        "a refused kind still left a line in the log: %r" % (_kinds(q),))

    # --- a drained run: every key present, zero-filled ---------------------
    empty = _queue(fleet, s2)
    record = s.run_record(empty)
    assert tuple(record) == s.RUN_KEYS, (
        "the record's key order is not RUN_KEYS, so a reader that unpacks it "
        "reads the wrong field: %r" % (list(record),))
    assert set(record) == set(s.RUN_KEYS), (
        "the record's keys are not exactly RUN_KEYS: %r" % (sorted(record),))
    assert all(record[key] == 0 for key in counts), (
        "a run that never happened reports a count: a key with no lines must be "
        "a zero, never an absent key and never a line: %r" % (record,))
    assert record["pool"] == "bulk" and isinstance(record["pool"], str), (
        "the record's `pool` is not the pool's id (it is %r, a %s): a record "
        "must name the pool it summarises" % (record["pool"],
                                              type(record["pool"]).__name__))
    assert (record["tasks"], record["max_in_flight"], record["final_depth"],
            record["ticks"]) == (0, 0, 0, 0), (
        "an empty run's record invents a number: %r" % (record,))
    assert record["stopped"] is None, (
        "a drained run's record says it was stopped %r: nothing stopped it, and "
        "a run that finished must not read as a truncation" % (record["stopped"],))
    assert empty.events == [], (
        "taking the record of a drained run wrote a line into the log: %r"
        % (_kinds(empty),))

    # --- a real run: every counter is a line the run wrote -----------------
    q = _queue(fleet, s2, capacity=8, concurrency=2)
    worker = fleet.reliable()
    q.submit(_spec(fleet, "render"))                 # priority 5, three ticks
    q.submit(_spec(fleet, "notify"))                 # priority 9, one tick
    q.submit(_spec(fleet, "index"))                  # priority 1, seven ticks
    first = s4.start(q, worker)
    second = s4.start(q, worker)
    assert (first.ticket.task.id, second.ticket.task.id) == ("notify", "render"), (
        "the fixture run did not start the highest-order tickets first: %r"
        % ([first.ticket.task.id, second.ticket.task.id],))
    assert s4.start(q, worker) is None, (
        "a third flight started on a pool of two slots")
    assert q.decisions["limit_hits"] == 1, (
        "the dispatch that found no slot was not counted: %r" % (q.decisions,))
    q.clock.tick(1)                                  # now 1: notify is due
    s4.complete(q)
    assert s4.start(q, worker).ticket.task.id == "index", (
        "the slot freed at tick 1 did not take the next due ticket")
    q.clock.tick(2)                                  # now 3: render is due
    s4.complete(q)
    q.clock.tick(5)                                  # now 8: index is due
    s4.complete(q)
    assert not q.pending and not q.in_flight, (
        "the fixture run is not drained: pending=%r in_flight=%r"
        % ([ticket.task.id for ticket in q.pending], sorted(q.in_flight)))
    assert _kinds(q) == ["submitted", "submitted", "submitted",
                         "started", "started", "succeeded", "started",
                         "succeeded", "succeeded"], (
        "the run's log is not the nine lines the fixture fixes: %r" % (_kinds(q),))
    record = s.run_record(q)
    assert (record["pool"], record["tasks"]) == ("bulk", 3), (
        "the run saw three distinct task ids (and its pool is 'bulk'): pool=%r "
        "tasks=%r" % (record["pool"], record["tasks"]))
    assert record["submitted"] == 3 and record["started"] == 3, (
        "the run admitted three tasks and started three attempts: submitted=%r "
        "started=%r" % (record["submitted"], record["started"]))
    assert record["succeeded"] == 3, (
        "three succeeded lines were written and the record counts %r: a counter "
        "must be read from the log it summarises" % (record["succeeded"],))
    assert record["max_in_flight"] == 2, (
        "the run had two flights in the air at once, and the record's peak is "
        "%r: the table's present length (0), the pool's concurrency (2) or the "
        "number of starts (3) is not the high-water mark"
        % (record["max_in_flight"],))
    assert record["final_depth"] == 0 and record["ticks"] == 8, (
        "the drained run ended at depth 0 after 8 ticks: final_depth=%r ticks=%r"
        % (record["final_depth"], record["ticks"]))
    assert record["stopped"] is None, (
        "the run drained, and the record claims it was stopped %r"
        % (record["stopped"],))
    assert all(record[key] == 0 for key in
               ("admitted", "refused", "shed", "blocked", "failed", "died",
                "retried", "dead_lettered")), (
        "the run wrote no such line, and the record counts one: %r" % (record,))

    # --- the log is the truth even when `decisions` disagrees --------------
    s.event(q, "admitted", task="render")
    s.event(q, "admitted", task="index")
    q.decisions.update({"admitted": 99, "refused": 5, "shed": 4, "blocked": 3})
    record = s.run_record(q)
    assert record["admitted"] == 2, (
        "the admitted count was read from queue.decisions (%r) instead of the "
        "log, which carries two admitted lines: the counter and the log it "
        "summarises disagree, which is the one thing a record may not do"
        % (q.decisions["admitted"],))
    assert (record["refused"], record["shed"], record["blocked"]) == (0, 0, 0), (
        "a count was read from queue.decisions (refused=%r shed=%r blocked=%r) "
        "where the log wrote no such line: the tally beside the log is not the "
        "truth" % (record["refused"], record["shed"], record["blocked"]))
    assert tuple(record) == s.RUN_KEYS, (
        "the record's key order is not RUN_KEYS: %r" % (list(record),))
    assert "limit_hits" not in record, (
        "the record carries the limit_hits decision, which §4.9's RUN_KEYS does "
        "not: the record's shape is fixed and a decision is not a line: %r"
        % (list(record),))

    # --- every kind is counted from its own lines --------------------------
    q = _queue(fleet, s2, capacity=2, concurrency=1)
    q.submit(_spec(fleet, "render"))
    q.submit(_spec(fleet, "audit"))
    try:
        q.submit(_spec(fleet, "train"))
    except s2.QueueFull:
        pass
    else:
        raise AssertionError(
            "the third task into a capacity-2 pool was taken: the fixture needs "
            "the refused line, and a full queue must refuse")
    s.event(q, "admitted", task="render")
    s.event(q, "shed", task="audit")
    s.event(q, "blocked", task="train")
    s.event(q, "failed", task="render")
    s.event(q, "died", task="audit")
    s.event(q, "retried", task="render", attempt=1)
    s.event(q, "dead_lettered", task="train", attempts=3, reason="failed")
    record = s.run_record(q)
    assert (record["submitted"], record["refused"]) == (2, 1), (
        "two submissions and one refusal were written: submitted=%r refused=%r"
        % (record["submitted"], record["refused"]))
    assert (record["admitted"], record["shed"], record["blocked"]) == (1, 1, 1), (
        "one admitted, one shed and one blocked line were written: %r"
        % ({key: record[key] for key in ("admitted", "shed", "blocked")},))
    assert (record["failed"], record["died"]) == (1, 1), (
        "one failed and one died line were written: %r"
        % ({key: record[key] for key in ("failed", "died")},))
    assert (record["retried"], record["dead_lettered"]) == (1, 1), (
        "one retried and one dead_lettered line were written: %r"
        % ({key: record[key] for key in ("retried", "dead_lettered")},))
    assert (record["started"], record["succeeded"]) == (0, 0), (
        "no flight started or succeeded here, and the record counts %r starts "
        "and %r successes" % (record["started"], record["succeeded"]))
    assert record["tasks"] == 3, (
        "the log names three distinct task ids (render, audit and the train "
        "that was refused) and the record counts %r: `tasks` is neither the "
        "number of lines (%r) nor only the ids still in the queue's tables"
        % (record["tasks"], len(q.events)))
    assert (record["max_in_flight"], record["final_depth"]) == (0, 2), (
        "nothing ran and two tickets wait: the peak is %r (the count of lines or "
        "of starts) and the depth is %r (the running flights or the dead, not "
        "the waiting)" % (record["max_in_flight"], record["final_depth"]))

    # --- the peak is the high-water mark, not the run's total --------------
    q = _queue(fleet, s2, capacity=8, concurrency=3)
    worker = fleet.reliable()
    for task_id in ("notify", "purge", "digest", "audit"):
        q.submit(_spec(fleet, task_id))
    for _ in range(3):
        assert s4.start(q, worker) is not None, (
            "fewer than three flights started on a pool of three slots")
    assert len(q.in_flight) == 3, (
        "the fixture needs three flights in the air at once: %r"
        % (sorted(q.in_flight),))
    q.clock.tick(1)                                  # now 1: notify is due
    s4.complete(q)
    assert s4.start(q, worker) is not None, (
        "the slot freed at tick 1 was not refilled")
    q.clock.tick(1)                                  # now 2: purge is due
    s4.complete(q)
    q.clock.tick(2)                                  # now 4: digest is due
    s4.complete(q)
    q.clock.tick(2)                                  # now 6: audit is due
    s4.complete(q)
    assert not q.pending and not q.in_flight, (
        "the peak fixture is not drained: pending=%r in_flight=%r"
        % ([ticket.task.id for ticket in q.pending], sorted(q.in_flight)))
    record = s.run_record(q)
    assert record["started"] == 4 and record["succeeded"] == 4, (
        "four attempts started and four succeeded: started=%r succeeded=%r"
        % (record["started"], record["succeeded"]))
    assert record["max_in_flight"] == 3, (
        "the run started four attempts, three at a time, so its peak is 3: %r is "
        "the number of starts, the pool's capacity or the flights in the air now"
        % (record["max_in_flight"],))
    assert record["max_in_flight"] <= q.pool.max_concurrency, (
        "the peak exceeds the pool's concurrency: the run never had more than %r "
        "flights, and the record reports %r"
        % (q.pool.max_concurrency, record["max_in_flight"]))
    assert record["ticks"] == 6 and record["final_depth"] == 0, (
        "the run spent 6 ticks and drained: ticks=%r final_depth=%r"
        % (record["ticks"], record["final_depth"]))

    # --- a flight still in the air is part of the depth --------------------
    q = _queue(fleet, s2, start=4, capacity=8, concurrency=2)
    q.submit(_spec(fleet, "render"))
    q.submit(_spec(fleet, "index"))
    assert s4.start(q, fleet.reliable()) is not None
    record = s.run_record(q)
    assert record["final_depth"] == 2, (
        "one ticket waits and one runs, so the depth at the end is 2, not the "
        "waiting tickets (%r) and not the running flights (%r): %r"
        % (len(q.pending), len(q.in_flight), record["final_depth"]))
    assert record["max_in_flight"] == 1 and record["started"] == 1, (
        "one flight is in the air: peak=%r started=%r"
        % (record["max_in_flight"], record["started"]))
    assert (record["ticks"], record["succeeded"], record["stopped"]) == (0, 0, None), (
        "nothing has finished and no bound stopped this run: %r" % (record,))

    # --- tasks: distinct ids the log names, even after one has left --------
    q = _queue(fleet, s2, capacity=8, concurrency=1)
    worker = fleet.reliable()
    q.submit(_spec(fleet, "render"))
    q.submit(_spec(fleet, "render"))                 # the same id, a second ticket
    q.submit(_spec(fleet, "notify"))                 # priority 9
    assert s4.start(q, worker).ticket.task.id == "notify", (
        "the run did not start the highest-order ticket")
    q.clock.tick(1)
    s4.complete(q)                                   # notify succeeded and left
    record = s.run_record(q)
    assert record["tasks"] == 2, (
        "the log names two distinct task ids (render twice and notify), and the "
        "record counts %r: the %d lines it wrote and the %d id still in its "
        "tables are both the wrong number"
        % (record["tasks"], len(q.events), 1))
    assert record["submitted"] == 3 and record["succeeded"] == 1, (
        "three submissions and one success were written: %r" % (record,))
    assert record["final_depth"] == 2, (
        "the two render tickets still wait: depth is %r" % (record["final_depth"],))

    # --- ticks: what the run spent, not the reading or the line count ------
    q = _queue(fleet, s2, start=10, capacity=8, concurrency=1)
    worker = fleet.reliable()
    q.submit(_spec(fleet, "render"))
    q.submit(_spec(fleet, "render"))
    assert s4.start(q, worker) is not None
    q.clock.tick(3)                                  # now 13, three ticks spent
    s4.complete(q)
    assert (q.clock.now(), q.clock.ticks) == (13, 3), (
        "the fixture clock reads 13 after spending 3: %r" % (q.clock,))
    record = s.run_record(q)
    assert record["ticks"] == 3, (
        "the record's ticks is %r: the clock's reading (13) is when the run was, "
        "and the number of lines (%r) is not time — `ticks` is what was spent"
        % (record["ticks"], len(q.events)))

    # --- a died or failed flight takes its flight down, so no inflated peak ---
    q = _queue(fleet, s2, capacity=8, concurrency=1)
    q.submit(_spec(fleet, "notify"))
    worker = fleet.scripted(["died", "failed", "ok"])
    assert s4.start(q, worker) is not None
    q.clock.tick(1)
    s4.complete(q)                                   # the worker is gone: `died`
    assert _kinds(q)[-1] == "died", (
        "the worker that dies must leave a died line: %r" % (_kinds(q),))
    assert s4.start(q, worker) is not None, (
        "the slot the dead worker held did not come back to the queue")
    q.clock.tick(1)
    s4.complete(q)                                   # the attempt finished: `failed`
    assert _kinds(q)[-1] == "failed", (
        "an attempt that finished and failed must leave a failed line: %r"
        % (_kinds(q),))
    assert s4.start(q, worker) is not None, (
        "the failed ticket did not come back to the queue")
    q.clock.tick(1)
    s4.complete(q)
    record = s.run_record(q)
    assert (record["died"], record["failed"], record["succeeded"]) == (1, 1, 1), (
        "one died, one failed and one successful attempt were written: %r"
        % ({key: record[key] for key in ("died", "failed", "succeeded")},))
    assert record["started"] == 3, (
        "three attempts started against one slot: %r" % (record["started"],))
    assert record["max_in_flight"] == 1, (
        "one slot was busy at a time, so the peak is 1: %r counts a died or a "
        "failed flight as still in the air, and it is not the 3 starts either"
        % (record["max_in_flight"],))
    assert record["final_depth"] == 0 and record["dead_lettered"] == 0, (
        "the task came back and succeeded on its third of three attempts: %r"
        % (record,))

    # --- stopped: the log's own fact, corroborated and read ---------------
    q = _queue(fleet, s2, start=3, capacity=8, concurrency=2)
    q.submit(_spec(fleet, "render"))
    assert s.run_record(q)["stopped"] is None, (
        "the record of a run nobody stopped claims it was stopped")
    lines_before = len(q.events)
    record = s.run_record(q, stopped="max_ticks")
    assert record["stopped"] == "max_ticks", (
        "the record of a run the bound stopped says stopped=%r: a truncated run "
        "that reads as a drained one is a silent truncation" % (record["stopped"],))
    last = q.events[-1]
    assert last["kind"] == "stopped", (
        "the record claims the run stopped but the log's last line is %r: the "
        "record must never claim a stop the log cannot corroborate" % (last,))
    assert last.get("reason") == "max_ticks", (
        "the stopped line does not say why the run ended: %r" % (last,))
    assert (last["at"], len(q.events)) == (q.clock.now(), lines_before + 1), (
        "the stopped line is stamped at %r, not the tick it happened (%r), and "
        "one stop wrote %d lines" % (last["at"], q.clock.now(),
                                     len(q.events) - lines_before))
    assert record["tasks"] == 1, (
        "the log names one task and one run-level line; the record counts %r, so "
        "it is counting the stopped line as a task the run saw"
        % (record["tasks"],))
    assert tuple(record) == s.RUN_KEYS
    written = s.run_record(q)                        # no reason handed in at all
    assert written["stopped"] == "max_ticks", (
        "the log's last line is a stopped line carrying %r, and a reason-less "
        "run_record reports stopped=%r: every value in the record comes from the "
        "log, and the stop is a log fact like any other"
        % (q.events[-1].get("reason"), written["stopped"]))
    again = s.run_record(q, stopped="max_ticks")
    assert again["stopped"] == "max_ticks" and _kinds(q).count("stopped") == 1, (
        "taking the record of the same stop twice wrote a second stopped line: "
        "the stop is written once, and asking for the record again does not "
        "re-stop the run: %r" % (_kinds(q),))
    other = s.run_record(q, stopped="no_progress")
    assert other["stopped"] == "max_ticks" and _kinds(q).count("stopped") == 1, (
        "a run_record handed a reason the log does not carry declared it over "
        "the log's own stop (%r): the record is derived, never declared, so the "
        "log wins and no replacement line is written: %r"
        % (other["stopped"], _kinds(q)))

    # --- a stop the caller logged is what a reason-less record reports -----
    q = _queue(fleet, s2, start=5, capacity=8, concurrency=2)
    q.submit(_spec(fleet, "render"))
    s.event(q, "stopped", reason="no_progress")      # exactly what `run` writes
    record = s.run_record(q)
    assert record["stopped"] == "no_progress", (
        "the log's last line is a stopped line carrying 'no_progress' and the "
        "record reports stopped=%r: a record that answers None while the log "
        "carries a stop disagrees with the log it summarises" % (record["stopped"],))
    assert record["submitted"] == 1 and record["tasks"] == 1, (
        "the snapshot of one submitted ticket and its stop: %r" % (record,))
    assert tuple(record) == s.RUN_KEYS
    assert _kinds(q).count("stopped") == 1, (
        "reading the log's stop wrote another stopped line: %r" % (_kinds(q),))

    # ... and when a log somehow carries two, the later one ended the run -----
    q = _queue(fleet, s2, capacity=8, concurrency=1)
    s.event(q, "stopped", reason="max_steps")
    s.event(q, "stopped", reason="no_progress")
    record = s.run_record(q)
    assert record["stopped"] == "no_progress", (
        "the log's last stopped line carries 'no_progress' and the record "
        "reports %r: the stop that ended the run is the last one in the log"
        % (record["stopped"],))
    assert _kinds(q).count("stopped") == 2, (
        "reading the record of a stopped log wrote or dropped a line: %r"
        % (_kinds(q),))

    # --- the record is a fresh snapshot, not the live log ------------------
    q = _queue(fleet, s2, capacity=8, concurrency=2)
    q.submit(_spec(fleet, "render"))
    record = s.run_record(q)
    assert "events" not in record and "log" not in record, (
        "the record carries the live event log under %r: a caller can then edit "
        "the run's history through its summary" % (sorted(record),))
    assert type(record) is dict and record is not q.events, (
        "the record is not a plain dict: %r" % (type(record).__name__,))
    assert record["submitted"] == 1 and record["final_depth"] == 1, (
        "the snapshot of one submitted ticket: %r" % (record,))
    q.submit(_spec(fleet, "audit"))
    assert s.run_record(q)["submitted"] == 2, (
        "a second record of the same queue did not see the line written in "
        "between: the record is taken now, from the log, every time")

    print("check_09: 15 fixtures — RUN_KEYS is the fixed shape; event is the only "
          "writer and refuses an unknown kind by name; every counter is a line "
          "the log wrote and never a decisions tally; the peak is rebuilt from "
          "the log, the depth from the tables and the ticks from what was spent; "
          "the record is a fresh zero-filled dict in RUN_KEYS order; and `stopped` "
          "is the log's own stop, read from it, written to it exactly once, and "
          "never declared from the argument")

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import dataclasses
    import json
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _repo(start=None):
        for candidate_start in (os.environ.get("J1_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "queue-and-workers-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set J1_REPO=/path/to/learn-stuff-from-scratch")

    def _kinds(queue):
        return [line["kind"] for line in queue.events]

    def _verdict(queue):
        """The record a caller reads off the finished queue: the reason its own
        `stopped` line carries, if any."""
        import stage_09
        reason = None
        for line in queue.events:
            if line["kind"] == "stopped":
                reason = line.get("reason")
        return stage_09.run_record(queue, stopped=reason)

    def _spec(fleet, task_id, **overrides):
        fields = dataclasses.asdict(fleet.make_task(task_id))
        fields.update(overrides)
        return fields

    import fleet
    import stage_01
    import stage_02
    import stage_09
    import stage_10 as s

    # --- a clean drain: the loop resolves, dispatches and stops as data ------
    pool = fleet.make_pool("wide")
    queue = s.run(pool, [fleet.make_task("render"), fleet.make_task("index")],
                  worker=fleet.reliable(), max_steps=200)
    assert isinstance(queue, stage_02.Queue), (
        "run() returned %r, not the Queue it ran" % (type(queue).__name__,))
    assert queue.in_flight == {} and queue.pending == [], (
        "a drained run left work behind: in_flight=%r pending=%r"
        % (sorted(queue.in_flight), [t.task.id for t in queue.pending]))
    assert _kinds(queue) == ["submitted", "admitted", "submitted", "admitted",
                             "started", "started", "succeeded", "succeeded"], (
        "the clean run's log is not the ordered submission, admission, start and "
        "success it should be: %r" % (_kinds(queue),))
    record = _verdict(queue)
    assert record["stopped"] is None, (
        "a run that finished everything it took was stopped with %r, not left to "
        "drain" % (record["stopped"],))
    assert (record["started"], record["succeeded"], record["max_in_flight"]) == (2, 2, 2), (
        "two flights ran at once and both succeeded: started=%r succeeded=%r "
        "peak=%r" % (record["started"], record["succeeded"],
                     record["max_in_flight"]))
    assert (record["ticks"], record["final_depth"], record["tasks"]) == (7, 0, 2), (
        "the clean run spent 7 ticks (render 3, index 7, at once) and drained: "
        "ticks=%r depth=%r tasks=%r" % (record["ticks"], record["final_depth"],
                                        record["tasks"]))

    # --- completions come before the sweeps ---------------------------------
    queue = s.run(fleet.make_pool("small"), [fleet.make_task("render")],
                  worker=fleet.reliable(), lease=3, max_steps=200)
    record = _verdict(queue)
    assert (record["succeeded"], record["died"], record["dead_lettered"]) == (1, 0, 0), (
        "a flight that finished at exactly its lease deadline (3) answered the "
        "worker, so it is a success, not a death swept out from under it: "
        "succeeded=%r died=%r dead_lettered=%r"
        % (record["succeeded"], record["died"], record["dead_lettered"]))
    assert queue.dead == [], (
        "the boundary success was also dead-lettered: %r" % (queue.dead,))

    # --- advance to the earliest due time, not the latest -------------------
    queue = s.run(fleet.make_pool("small", max_concurrency=2, capacity=8),
                  [fleet.make_task("notify"), fleet.make_task("render"),
                   fleet.make_task("audit")],
                  worker=fleet.reliable(), max_steps=200)
    record = _verdict(queue)
    assert record["ticks"] == 6, (
        "the loop did not advance to the earliest finish each time: the run "
        "spent %r ticks, not 6 (notify at 1 frees the slot for audit at 6)"
        % (record["ticks"],))
    succeeded_at = [line["at"] for line in queue.events
                    if line["kind"] == "succeeded"]
    assert succeeded_at == [1, 3, 6], (
        "the completions were not resolved at the tick each one came due: %r"
        % (succeeded_at,))

    # --- retries on the injected clock, with a growing backoff --------------
    worker = fleet.flaky(failures=2)
    queue = s.run(fleet.make_pool("small"), [_spec(fleet, "render")],
                  worker=worker, max_steps=200)
    record = _verdict(queue)
    assert worker.calls == 3, (
        "flaky(failures=2) on a three-attempt task must be attempted three "
        "times, not %r" % (worker.calls,))
    assert (record["retried"], record["failed"], record["succeeded"]) == (2, 2, 1), (
        "two failures must be retried and the third attempt must succeed: "
        "retried=%r failed=%r succeeded=%r"
        % (record["retried"], record["failed"], record["succeeded"]))
    assert record["stopped"] is None and record["dead_lettered"] == 0, (
        "a task that eventually succeeded was stopped or given up on: %r"
        % (record,))
    waits = [line["ready_at"] - line["at"] for line in queue.events
             if line["kind"] == "retried"]
    assert waits == [1, 2], (
        "the two retries did not wait backoff(1)=1 then backoff(2)=2 ticks on "
        "the injected clock: the waits were %r" % (waits,))
    assert [line["reason"] for line in queue.events
            if line["kind"] == "retried"] == ["failed", "failed"], (
        "each retry must carry the failure it followed, not another reason: %r"
        % ([line["reason"] for line in queue.events
            if line["kind"] == "retried"],))

    # --- a poison task is dead-lettered, and the pool stops, not spins ------
    queue = s.run(fleet.make_pool("small"), [_spec(fleet, "render")],
                  worker=fleet.flaky(failures=5), max_steps=200)
    record = _verdict(queue)
    assert record["dead_lettered"] == 1 and record["succeeded"] == 0, (
        "a task that fails every one of its three attempts must be dead-lettered "
        "and never succeed: dead_lettered=%r succeeded=%r"
        % (record["dead_lettered"], record["succeeded"]))
    assert record["stopped"] == "no_progress", (
        "a run whose every attempt died gave up on work and must stop with "
        "stopped='no_progress', not %r" % (record["stopped"],))
    assert queue.dead and queue.in_flight == {}, (
        "the dead-lettered task must be in the DLQ with nothing left in the air: "
        "dead=%r in_flight=%r" % (queue.dead, sorted(queue.in_flight)))

    # --- a pool that cannot progress stops instead of spinning --------------
    queue = s.run(fleet.make_pool("small"), [fleet.make_task("render")],
                  worker=fleet.always("died"), max_steps=200)
    record = _verdict(queue)
    assert record["stopped"] == "no_progress" and record["died"] == 3, (
        "a died-forever pool must stop with stopped='no_progress' after three "
        "died attempts, not %r with died=%r"
        % (record["stopped"], record["died"]))
    assert (record["dead_lettered"], record["ticks"]) == (1, 12), (
        "the died-forever run dead-letters once and ends at tick 12 (retry waits "
        "1 then 2 after finishes at 3 and 7): dead_lettered=%r ticks=%r"
        % (record["dead_lettered"], record["ticks"]))
    assert [line["reason"] for line in queue.events
            if line["kind"] == "retried"] == ["died", "died"], (
        "each retry of a died attempt must carry the reason 'died', not another "
        "failure: %r" % ([line["reason"] for line in queue.events
                         if line["kind"] == "retried"],))
    letters = [line for line in queue.events if line["kind"] == "dead_lettered"]
    assert letters and letters[0]["reason"] == "died", (
        "the dead letter must carry the reason the queue gave up on: %r"
        % (letters,))

    # --- the lease is stamped, so a worker that died is swept --------------
    queue = s.run(fleet.make_pool("small"), [fleet.make_task("render")],
                  worker=fleet.always("died", ticks=100), lease=5, max_ticks=50)
    record = _verdict(queue)
    assert record["stopped"] == "no_progress" and record["ticks"] == 18, (
        "a flight past its lease must be swept at the deadline (5, 11, 18), not "
        "left to its made-up finish at 100: stopped=%r ticks=%r"
        % (record["stopped"], record["ticks"]))
    assert record["died"] == 3, (
        "all three attempts of the always-died worker must be resolved as died: "
        "%r" % (record["died"],))

    # --- max_ticks: a bound before the dispatch, recorded, never raised ------
    queue = s.run(fleet.make_pool("small"),
                  [fleet.make_task("render"), fleet.make_task("index")],
                  worker=fleet.reliable(), max_ticks=3)
    record = _verdict(queue)
    assert record["stopped"] == "max_ticks", (
        "a run held at max_ticks=3 must stop with stopped='max_ticks', not %r "
        "(and must not raise)" % (record["stopped"],))
    assert (record["ticks"], record["started"], len(queue.pending)) == (3, 1, 1), (
        "at the bound the run resolved the flight it had started and stopped "
        "before dispatching the next: ticks=%r started=%r pending=%r"
        % (record["ticks"], record["started"], len(queue.pending)))
    stops = [line for line in queue.events if line["kind"] == "stopped"]
    assert len(stops) == 1 and stops[0].get("reason") == "max_ticks", (
        "the log must carry exactly one stopped line, with the reason: %r" % (stops,))

    # --- max_steps: the other bound, recorded the same way ------------------
    queue = s.run(fleet.make_pool("small"),
                  [fleet.make_task("render"), fleet.make_task("index")],
                  worker=fleet.reliable(), max_steps=1)
    record = _verdict(queue)
    assert record["stopped"] == "max_steps" and record["started"] == 1, (
        "one loop step must stop the run with stopped='max_steps' after one "
        "dispatch: stopped=%r started=%r" % (record["stopped"], record["started"]))

    # --- the policy is honoured --------------------------------------------
    four = [_spec(fleet, task_id) for task_id in ("render", "index", "notify", "audit")]
    pool = fleet.make_pool("small", capacity=4, high_water=2)
    refused = _verdict(s.run(pool, four, worker=fleet.reliable(), policy="refuse",
                             max_steps=200))
    assert (refused["admitted"], refused["refused"]) == (2, 2), (
        "at high_water=2 with four tasks, refuse admits two and refuses two: "
        "%r" % (refused,))
    blocked = _verdict(s.run(pool, four, worker=fleet.reliable(), policy="block",
                             max_steps=200))
    assert (blocked["admitted"], blocked["blocked"], blocked["refused"]) == (2, 2, 0), (
        "with policy='block' two tasks are admitted and two blocked, none "
        "refused: %r" % (blocked,))
    shed = _verdict(s.run(pool, four, worker=fleet.reliable(), policy="shed",
                          max_steps=200))
    assert (shed["admitted"], shed["shed"], shed["dead_lettered"]) == (2, 2, 2), (
        "with policy='shed' the four tasks shed two and admit two, each shed "
        "task dead-lettered with a reason: %r" % (shed,))

    # --- the caller's clock is the one the run moves ------------------------
    clock = fleet.Clock(start=5)
    queue = s.run(fleet.make_pool("small"), [fleet.make_task("render")],
                  worker=fleet.reliable(), clock=clock, max_steps=200)
    assert queue.clock is clock and queue.events[0]["at"] == 5, (
        "the run ignored the injected clock: it started its log at %r, not 5"
        % (queue.events[0]["at"],))
    assert clock.ticks == 3, (
        "the injected clock must record the 3 ticks the run spent, not %r"
        % (clock.ticks,))

    # --- admissions swallow only the policy's refusals ----------------------
    six = [_spec(fleet, task_id) for task_id in
           ("render", "index", "notify", "audit", "purge", "digest")]
    record = _verdict(s.run(fleet.make_pool("small", capacity=4), six,
                            worker=fleet.reliable(), max_steps=200))
    assert record["refused"] == 3, (
        "six tasks into a capacity-4 pool at high_water=3 refuse three and the "
        "run carries on: refused=%r" % (record["refused"],))
    try:
        s.run(fleet.make_pool("small"), [{"id": "x", "tickz": 1}],
              worker=fleet.reliable())
    except fleet.QueueError:
        pass
    else:
        raise AssertionError(
            "a malformed task spec was swallowed by the admission catch instead "
            "of being refused loudly")

    # --- the canonical text: one text per run, not per rendering ------------
    pool = fleet.make_pool("wide")
    tasks = [fleet.make_task("render"), fleet.make_task("index"),
             fleet.make_task("notify")]
    first = s.run_bytes(pool, tasks, worker=fleet.reliable(), max_steps=200)
    second = s.run_bytes(pool, tasks, worker=fleet.reliable(), max_steps=200)
    assert isinstance(first, bytes), (
        "run_bytes returned %r, not bytes" % (type(first).__name__,))
    assert first == second, (
        "two runs of the same inputs rendered different bytes")
    rebuilt = s.run_bytes(json.loads(stage_01.canonical_pool(pool)),
                          [json.loads(stage_01.canonical_task(task)) for task in tasks],
                          worker=fleet.reliable(), max_steps=200)
    assert first == rebuilt, (
        "a run rebuilt from canonical_pool/canonical_task text rendered "
        "different bytes from the run it rebuilds")

    text = first.decode("utf-8")
    assert text.endswith("\n"), (
        "the canonical text is not newline-terminated: %r" % (text[-20:],))
    lines = text.split("\n")[:-1]
    assert len(lines) == len(tasks) * 4 + 1, (
        "the canonical text must be the events (submitted+admitted+started+"
        "succeeded per task) and then one record line: %d lines for %d tasks"
        % (len(lines), len(tasks)))
    parsed = []
    for line in lines:
        assert line and line == json.dumps(json.loads(line), sort_keys=True,
                                           separators=(",", ":")), (
            "a canonical line is not sort_keys JSON with separators=(\",\", "
            "\":\"): %r" % (line,))
        parsed.append(json.loads(line))
    events, record_line = parsed[:-1], parsed[-1]
    assert all("kind" in line for line in events), (
        "the events must come before the record line, each carrying a kind: %r"
        % (parsed,))
    assert "kind" not in record_line and record_line["pool"] == pool.id, (
        "the last line must be the record (no kind, naming the pool): %r"
        % (record_line,))

    def _no_stray(value, line):
        if isinstance(value, dict):
            for key, item in value.items():
                allowed = (line.get("kind") == "stopped" and key == "task") or \
                    ("kind" not in line and key == "stopped")
                assert not (item is None and not allowed), (
                    "a None where the text wants a value: %r in %r" % (key, line))
                if isinstance(item, (dict, list)):
                    _no_stray(item, line)
        elif isinstance(value, list):
            for entry in value:
                _no_stray(entry, line)
        else:
            assert not isinstance(value, float), (
                "a float leaked into the canonical text: %r in %r"
                % (value, line))

    for line in parsed:
        _no_stray(line, line)
    assert record_line["stopped"] is None, (
        "a drained run's record line carries stopped=%r, not null"
        % (record_line["stopped"],))

    # --- a bound stop is corroborated in the bytes too ----------------------
    bounded = s.run_bytes(fleet.make_pool("small"),
                          [fleet.make_task("render"), fleet.make_task("index")],
                          worker=fleet.reliable(), max_ticks=3)
    bounded_lines = bounded.decode("utf-8").split("\n")[:-1]
    bounded_record = json.loads(bounded_lines[-1])
    assert bounded_record["stopped"] == "max_ticks", (
        "the record line after a bound stop must carry the reason the log's "
        "stopped line does: %r" % (bounded_record["stopped"],))
    stop_lines = [json.loads(line) for line in bounded_lines
                  if json.loads(line).get("kind") == "stopped"]
    assert len(stop_lines) == 1 and stop_lines[0]["reason"] == "max_ticks", (
        "the canonical text must carry exactly one stopped line and its reason: "
        "%r" % (stop_lines,))

    # --- the record line is the log's own stop, read back as data -----------
    pinned = s.run(fleet.make_pool("small"),
                   [fleet.make_task("render"), fleet.make_task("index")],
                   worker=fleet.reliable(), max_ticks=3)
    pinned_lines = s.canonical_run(pinned).split("\n")[:-1]
    pinned_log = [json.loads(line) for line in pinned_lines[:-1]]
    pinned_record = json.loads(pinned_lines[-1])
    log_last = pinned_log[-1]
    assert (log_last["kind"], log_last.get("reason")) == ("stopped", "max_ticks"), (
        "a run stopped by max_ticks=3 must end its log with the bound's own "
        "stopped line: the log's last line was %r" % (log_last,))
    assert (len(pinned.pending) + len(pinned.in_flight)) > 0, (
        "the bound must bite with work still queued or in flight: pending=%r "
        "in_flight=%r" % ([ticket.task.id for ticket in pinned.pending],
                          sorted(pinned.in_flight)))
    assert pinned_record["stopped"] == log_last.get("reason"), (
        "the record line claims a clean drain although the log's last line "
        "stopped the run with %r: the record line carried stopped=%r"
        % (log_last.get("reason"), pinned_record["stopped"]))
    assert stage_09.run_record(pinned)["stopped"] == "max_ticks", (
        "run_record of a run stopped by max_ticks=3 carried stopped=%r, not "
        "the log's reason" % (stage_09.run_record(pinned)["stopped"],))

    # --- a drained run's record line and log agree on no stop ---------------
    drained = s.run(fleet.make_pool("wide"),
                    [fleet.make_task("render"), fleet.make_task("index")],
                    worker=fleet.reliable(), max_steps=200)
    drained_lines = s.canonical_run(drained).split("\n")[:-1]
    drained_log = [json.loads(line) for line in drained_lines[:-1]]
    drained_record = json.loads(drained_lines[-1])
    drained_stops = [line for line in drained_log if line.get("kind") == "stopped"]
    assert not drained_stops, (
        "a run that drained with no bound must write no stopped line: the log "
        "carried %r" % (drained_stops,))
    assert drained_record["stopped"] is None, (
        "a run that drained with no bound must render a record line carrying "
        "stopped=None, not %r" % (drained_record["stopped"],))
    assert stage_09.run_record(drained)["stopped"] is None, (
        "run_record of a drained run carried stopped=%r, not None"
        % (stage_09.run_record(drained)["stopped"],))

    print("check_10: composed the loop (completions before sweeps, retries on "
          "the injected clock, bounds as data, no_progress) and the canonical "
          "bytes (one JSONL text per run)")

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The task and the pool, and the typo that runs as a default",
        tags=["specs", "validation"],
        action="Write `TASK_KEYS`, `POOL_KEYS`, `TASK_DEFAULTS`, `POOL_DEFAULTS`, "
               "`Task`, `Pool`, `parse_task`, `parse_pool`, `parse_tasks`, "
               "`canonical_task` and `canonical_pool` in stage_01.py.",
        predict="What `parse_task({\"id\": \"a\", \"tick\": 1})` does, what "
                "`priority=True` parses to, and why two mappings that mean the "
                "same pool must produce the same text.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="Admission, and the full queue that refuses instead of growing",
        tags=["admission", "capacity"],
        action="Write `QueueFull`, `Ticket`, `Flight`, `DeadLetter` and `Queue` "
               "in stage_02.py.",
        predict="What `depth()` counts and what `queued()` leaves out, what the "
                "seventh task into a capacity-six pool gets, and which values "
                "the sequence counter takes across a refusal.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Priority as a total order, and the tie that makes two runs differ",
        tags=["ordering", "ties"],
        action="Write `order_key`, `reorder`, `pick_next` and `take_next` in "
               "stage_03.py.",
        predict="What breaks two tickets of equal priority when the sort leans "
                "on the list's order instead, and whether a ticket due exactly "
                "now is due.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The concurrency limit, checked before the worker starts",
        tags=["concurrency", "outcomes"],
        action="Write `OutcomeError`, `validate_outcome`, `free_slots`, `start` "
               "and `complete` in stage_04.py.",
        predict="What a worker that answers a string gets, what `None` from "
                "`start` means, and what happens to a `failed` ticket when the "
                "flight is resolved.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The lease, and the worker that dies holding the slot",
        tags=["leases", "timeouts"],
        action="Write `DEFAULT_LEASE`, `sweep`, `ack` and `release` in "
               "stage_05.py.",
        predict="What a flight past its deadline must not be (a success), where "
                "the task goes when it is swept, and whether a task that never "
                "ran should spend an attempt.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Retries, backoff on the injected clock, and the poison task",
        tags=["retries", "dead-letter"],
        action="Write `BACKOFF_BASE`, `backoff`, `due`, `requeue` and "
               "`dead_letter` in stage_06.py.",
        predict="How long the second retry waits, what `ready_at` does to "
                "eligibility, and what a task with no attempts left becomes.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Backpressure: refuse, shed or block, and never lose a task",
        tags=["backpressure", "watermarks"],
        action="Write `POLICIES`, `ShedError`, `BlockedError` and `admit` in "
               "stage_07.py.",
        predict="Which task `shed` gives up on, where the counter for each "
                "decision is incremented, and what the queue holds after a "
                "`block` refuses.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="Ageing, and the tenant that never gets served",
        tags=["fairness", "ageing"],
        action="Write `AGE_STEP`, `AGE_LIMIT`, `waited`, `effective_priority`, "
               "`reorder_aged` and `starved` in stage_08.py.",
        predict="What `waited` is for a task that is already running, how much "
                "priority twenty-four ticks of waiting buys, and what breaks "
                "the tie once the boost is capped.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The record, and the counters that must come from the tickets",
        tags=["records", "events"],
        action="Write `RUN_KEYS`, `event` and `run_record` in stage_09.py.",
        predict="What a drained run's `stopped` is, where `max_in_flight` comes "
                "from, and which key a count of successes must not be read "
                "from.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="Two runs, identical bytes: the scheduler end to end",
        tags=["scheduler", "determinism"],
        action="Write `run`, `canonical_run` and `run_bytes` in stage_10.py.",
        predict="What happens to a pool whose every attempt dies, whether a "
                "bound stop raises or is recorded, and what two runs of the "
                "same inputs have to say about each other in bytes.",
        check=check_10,
    ),
]
