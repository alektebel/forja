"""Agent Metrics From Scratch — stage 7: Failures and retries are rates.

A count is not a rate. `failures` is a number, `attempts` is another, and the
sentence an operator actually wants — *this fleet fails about one attempt in
five* — is the two of them divided, in one place, as an exact reduced pair and a
scalar in floored basis points. This stage fixes which events each of the four
counts counts, and the one door a ratio comes through. The subtlety is the
numerator: a failure is an **attempt** that did not succeed, not a task that
failed, because a task that failed once and then succeeded is a fact about the
fleet that a per-task count would throw away.

    RateError       a rate, a denominator or a count this stage refuses
    failures        the attempts whose outcome is not `ok`
    attempts        every `finished` event
    retries         every `retried` event
    admissions      every `admitted` event
    rate            the one place a ratio is built, or a refusal
    failure_rate    failures / attempts
    retry_rate      retries / admissions

DESIGN DECISION — why does a failure count an *attempt* rather than a task?
    Because a task that failed once and then succeeded is exactly the fleet the
    operator needs to see, and counting it by task erases the failure. If
    `failures` answered "how many tasks ever failed", then a fleet whose every
    task fails twice before it succeeds and a fleet whose tasks each fail once
    would report the same number, and the retry storm that the second fleet is
    drowning in would be invisible. An attempt is the thing the worker was
    handed, so an attempt is the thing that has an outcome, so `failures` counts
    outcomes. The consequence is deliberate: the same task may be counted twice
    in one window, because it really did fail twice in that window.

DESIGN DECISION — why does `rate` take the refusal sentence instead of the
denominator's name?
    Because the function that divides does not know what its denominator counts,
    and a refusal that guesses is worse than a refusal that is told. `rate` is
    handed two ints and the sentence to say when there is nothing to divide by —
    `"a failure rate needs attempts"`, `"a retry rate needs admissions"` — so the
    one generic door can still name the specific denominator at the call site
    that knows it. A message factory with a vocabulary of denominator names would
    be a second place where "what a denominator is" is written down, and those
    two places would eventually disagree.

DESIGN DECISION — why an exact reduced pair *and* a floored scalar, instead of
one of them?
    Because they answer different questions and the course refuses to let either
    be a float. The reduced pair `(1, 3)` is the ratio itself — exact, addable,
    comparable, and the only form in which two rates can be reasoned about. The
    scalar is what a dashboard, an SLO target and a budget speak in, and it is
    basis points because an integer percentage loses the difference between one
    in three and one in four. It is **floored**, never rounded, so the number a
    reader sees can never claim more of a target than is actually there: `1 / 3`
    is `3333` bp, and the missing third of a basis point is the honest way to be
    wrong.

DESIGN DECISION — why is `retry_rate` divided by admissions and not by attempts?
    Because a retry is a question about *tasks*, not about attempts: it asks how
    often a task that got in had to be tried again. A task admitted once and
    retried twice is two retries over one admission, which is the number an
    operator sizes a queue's churn by; divided by attempts it would instead
    measure how many of the attempts that ran were followed by yet another, which
    is a different question wearing the same name. `admissions` is also the
    count that survives a run that was cut short, so the rate keeps its meaning
    when the last tasks never finish.

DESIGN DECISION — why is a `dropped` event counted as neither a failure nor an
attempt?
    Because it never ran. A dropped event is a task the pool refused or the run
    gave up on, and it has no outcome to be `ok` or not, no service, and no
    tokens — counting it as a failure would attribute a refusal to the worker,
    and counting it as an attempt would put a denominator under a numerator that
    never happened. It is a real and important number, and it is the fleet's own
    `dropped` counter, which is why this stage leaves it alone and a later report
    compares it on its own terms.

TODO: implement `failures`, `attempts`, `retries`, `admissions`, `rate`,
`failure_rate` and `retry_rate`.
"""

from stage_01 import TelemetryError

#: The outcome a finished attempt reports when it succeeded. Everything else —
#: `failed`, `died`, and any word the fleet does not know — is a failure here.
_OK = "ok"

#: The three kinds this stage counts. A `started` event is an attempt still in
#: flight and a `dropped` event never ran at all, so neither is an attempt.
_FINISHED = "finished"
_RETRIED = "retried"
_ADMITTED = "admitted"


class RateError(TelemetryError):
    """A rate, a denominator or a count this stage refuses.

    The refusal names the denominator it was missing, in the caller's own
    words — the one thing the generic `rate` cannot know by itself.
    """


def failures(events):
    """The attempts whose outcome is not `ok`.

    A `finished` event is one attempt, whatever it ended as, and an attempt that
    did not end `ok` is a failure. A task that failed once and then succeeded is
    therefore one failure and one success — never "one failed task", which is
    the count that hides a flaky fleet. A `dropped` event never ran, so it is
    neither an attempt nor a failure.
    """
    raise NotImplementedError("stage 7: implement failures()")


def attempts(events):
    """Every `finished` event: one attempt, whatever it ended as.

    A `started` event is an attempt still in flight and is not counted here, and
    a `dropped` event never started, so neither is an attempt.
    """
    raise NotImplementedError("stage 7: implement attempts()")


def retries(events):
    """Every `retried` event: one task told to try again."""
    raise NotImplementedError("stage 7: implement retries()")


def admissions(events):
    """Every `admitted` event: one task the pool accepted.

    The denominator of the retry rate, and the count that survives a run that
    was cut short — a task that was admitted but never finished is still a task
    the fleet took in.
    """
    raise NotImplementedError("stage 7: implement admissions()")


def rate(numerator, denominator, *, what):
    """A ratio as `{"num", "den", "reduced", "bp"}`, or a refusal.

    The one place a ratio is built. `reduced` is the exact pair divided by the
    gcd of the two counts, and `bp` is the reduced numerator in **floored**
    basis points of the reduced denominator (`num * 10000 // den`), never
    rounded. A denominator of zero is refused with the caller's own `what` —
    the sentence that names what the denominator counts — because a rate of
    nothing is not a rate of zero.
    """
    raise NotImplementedError("stage 7: implement rate()")


def failure_rate(events):
    """`failures / attempts`: how often an attempt did not succeed.

    A zero denominator — a window in which nothing was attempted — is refused,
    naming the attempts it needs rather than answering zero.
    """
    raise NotImplementedError("stage 7: implement failure_rate()")


def retry_rate(events):
    """`retries / admissions`: how often a task had to be tried again.

    A zero denominator — nothing was admitted — is refused, naming the
    admissions it needs rather than answering zero.
    """
    raise NotImplementedError("stage 7: implement retry_rate()")
