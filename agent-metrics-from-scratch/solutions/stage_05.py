"""Agent Metrics From Scratch — stage 5: Latency, and where the time went.

A wait is how long a task sat in the queue before an attempt started; a service
is how long that attempt then ran; a latency is the fold of the two, and a
task's *span* is admission to its last finish. The three are different numbers
and only one of them is a fold of the others, which is the whole of this stage: a
retry spends time between two attempts that belongs to no attempt at all. Every
finished event is matched with the `started` event of the *same* attempt, added
up, and the task's span is measured from admission to its last finish so the gap
a retry leaves is a number somebody can see.
"""

import stage_01


class LatencyError(stage_01.TelemetryError):
    """A latency this stage cannot compute, refused by name."""


def waits(events):
    """The wait of every start, in tick order."""
    return tuple(event["wait"] for event in _started(events))


def services(events):
    """The service of every finish, in tick order."""
    return tuple(event["service"] for event in _finished(events))


def attempt_latency(events):
    """wait + service, one per finished attempt."""
    return tuple(wait + service for wait, service in _attempts(events))


def task_latency(events):
    """(task id, ticks) per task, sorted by id."""
    admitted = _admitted(events)
    done = _last_finished(events)
    spans = []
    for task in sorted(admitted):
        if task not in done:
            raise LatencyError("task %s never finished: what it has cost so far "
                               "is a different metric" % (task,))
        spans.append((task, done[task] - admitted[task]))
    return tuple(spans)


def split(events):
    """The waits, the services and the gaps, summing to the total exactly."""
    wait = 0
    service = 0
    for one, other in _attempts(events):
        wait += one
        service += other
    total = 0
    for _, ticks in task_latency(events):
        total += ticks
    return {"wait": wait, "service": service, "gap": total - wait - service,
            "total": total}


def _started(events):
    """Every `started` event, in the order it was recorded."""
    return tuple(event for event in events if event["kind"] == "started")


def _finished(events):
    """Every `finished` event, in the order it was recorded."""
    return tuple(event for event in events if event["kind"] == "finished")


def _attempts(events):
    """(wait, service) for every finished attempt, matched by (task, attempt)."""
    starts = {}
    for event in _started(events):
        starts[(event["task"], event["attempt"])] = event["wait"]
    pairs = []
    for event in _finished(events):
        key = (event["task"], event["attempt"])
        if key not in starts:
            raise LatencyError("attempt %d of task %s has no started event"
                               % (event["attempt"], event["task"]))
        pairs.append((starts[key], event["service"]))
    return tuple(pairs)


def _admitted(events):
    """task id -> the tick it was first admitted at."""
    out = {}
    for event in events:
        if event["kind"] == "admitted" and event["task"] not in out:
            out[event["task"]] = event["tick"]
    return out


def _last_finished(events):
    """task id -> the tick of the last finished event it has."""
    out = {}
    for event in events:
        if event["kind"] == "finished":
            if event["task"] not in out or event["tick"] > out[event["task"]]:
                out[event["task"]] = event["tick"]
    return out
