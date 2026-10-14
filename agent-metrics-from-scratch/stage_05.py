"""Agent Metrics From Scratch — stage 5: Latency, and where the time went.

A wait is how long a task sat in the queue before an attempt started; a service
is how long that attempt then ran; a latency is the fold of the two, and a
task's *span* is admission to its last finish. The three are different numbers
and only one of them is the fold of the others, which is the whole of this
stage: a retry spends time between two attempts that belongs to no attempt at
all. This stage matches a finish with the start of the *same* attempt, adds them,
spans each task from admission to its last finish, and writes down the identity
a dashboard leaves implicit — the waits, the services and the retry gaps sum to
the total, exactly.

    LatencyError     a latency this stage cannot compute, refused by name
    waits            the wait of every start, in tick order
    services         the service of every finish, in tick order
    attempt_latency  wait + service, one per finished attempt
    task_latency     (task id, ticks) per task, sorted by id
    split            the waits, the services and the gaps, summing to the total

DESIGN DECISION — why is a finished attempt matched by `(task, attempt)` instead
of by the task alone, or by the order the events happened to arrive in?
    Because `attempt` is the one field that says *which* run of the task a finish
    belongs to, and a task may run more than once. Matching by task alone would
    pair a retry's finish with its first start and report a latency that begins
    before the attempt did; matching by position would pair whatever happened to
    be third. The pair `(task, attempt)` is written on both events by the fleet
    itself, so the match is a lookup and never a guess — and a finish whose start
    is missing refuses by name rather than inventing one.

DESIGN DECISION — why is a task's span admission to its last finish, and not the
sum of its attempts?
    Because those are two different questions and only one of them is "how long
    the task took". The sum of the attempts counts the work; the span counts the
    *waiting* as well, including the gap between a finish that failed and the
    retry that comes after it. On a well-behaved fleet the two can be equal — an
    immediate retry re-queues at the same tick, so the next attempt's wait covers
    the gap — and on any fleet with a backoff they are not, which is exactly why
    the two are reported separately instead of one being derived from the other.

DESIGN DECISION — why does `split` assert that `wait + service + gap == total`
instead of just reporting three sums?
    Because the identity is the point: a decomposition that does not add up is a
    decomposition that lost an event, and the dashboard that shows it is the one
    nobody can audit. `gap` is not a fourth independent measurement — it is
    `total - wait - service`, the residual the task spans have and the attempts
    do not — so the identity holds by construction and *says so*, which is worth
    more than three numbers a reader has to check by hand.

DESIGN DECISION — why does a task that never finished refuse instead of
answering zero, or its last attempt's ticks?
    Because both of those are a number where no measurement exists. A task still
    in flight when the run ends has no last finish, so its span is not zero and
    not the span of the part that did run: it is simply not a latency yet. The
    refusal names the task, because a fold that quietly answers something for a
    task that never finished is how an average latency goes down while the tail
    goes up.

TODO: implement `waits`, `services`, `attempt_latency`, `task_latency` and
`split`.
"""

import stage_01


class LatencyError(stage_01.TelemetryError):
    """A latency this stage cannot compute, refused by name.

    Raised when a `finished` event has no `started` event of the same
    `(task, attempt)` — a latency that would otherwise be guessed at — and when a
    task that was admitted has no `finished` event at all, because a span that
    never ended is not zero.
    """


def waits(events):
    """The wait of every start, in tick order.

    One number per `started` event, in the order the events were recorded: a
    fold never sorts, so a start early in the run stays early in the answer.
    """
    raise NotImplementedError("stage 5: implement waits()")


def services(events):
    """The service of every finish, in tick order.

    One number per `finished` event, in the order the events were recorded.
    """
    raise NotImplementedError("stage 5: implement services()")


def attempt_latency(events):
    """wait + service, one per finished attempt.

    Each `finished` event is matched with the `started` event that carries the
    same `(task, attempt)`, and the two are added. A finished attempt whose start
    is missing refuses by name instead of being paired with whatever start came
    closest.
    """
    raise NotImplementedError("stage 5: implement attempt_latency()")


def task_latency(events):
    """(task id, ticks) per task, sorted by id.

    A task's span is its `admitted` tick to its **last** `finished` tick, so a
    retry's gap is inside it. A task that was admitted and never finished refuses
    by name.
    """
    raise NotImplementedError("stage 5: implement task_latency()")


def split(events):
    """The waits, the services and the gaps, summing to the total exactly.

    Answers `{"wait", "service", "gap", "total"}`: the waits and the services of
    the finished attempts, the residual every task's span has and its attempts do
    not, and their sum — so `wait + service + gap == total` by construction.
    """
    raise NotImplementedError("stage 5: implement split()")
