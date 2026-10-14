"""Agent Metrics From Scratch — stage 7: Failures and retries are rates.

A failure is an **attempt** that did not succeed, and a rate is two counts
divided in exactly one place. So `failures` counts outcomes and never tasks — a
task that failed once and then succeeded is one failure and one success, and
deduplicating the count by task is how a flaky fleet hides behind a green board.
`rate` is the only door a ratio comes through: it reduces the pair by their gcd,
floors the scalar to basis points, and refuses to divide by nothing in the
caller's own words.
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
    """A rate, a denominator or a count this stage refuses."""


def failures(events):
    """The attempts whose outcome is not `ok` — never the tasks that failed."""
    return sum(1 for event in events
               if event["kind"] == _FINISHED and event["outcome"] != _OK)


def attempts(events):
    """Every `finished` event: one attempt, whatever it ended as."""
    return _count(events, _FINISHED)


def retries(events):
    """Every `retried` event: one task told to try again."""
    return _count(events, _RETRIED)


def admissions(events):
    """Every `admitted` event: one task the pool accepted."""
    return _count(events, _ADMITTED)


def rate(numerator, denominator, *, what):
    """A ratio as `{"num", "den", "reduced", "bp"}`, or a refusal.

    `what` is the sentence the refusal quotes when the denominator is zero: only
    the caller knows what its denominator counts, so only the caller can name it.
    `reduced` is the exact pair divided by their gcd and `bp` is the reduced
    numerator in floored basis points of the reduced denominator.
    """
    if denominator == 0:
        raise RateError(what)
    divisor = _gcd(numerator, denominator)
    reduced = (numerator // divisor, denominator // divisor)
    return {"num": numerator, "den": denominator, "reduced": reduced,
            "bp": reduced[0] * 10000 // reduced[1]}


def failure_rate(events):
    """`failures / attempts`: how often an attempt did not succeed."""
    return rate(failures(events), attempts(events),
                what="a failure rate needs attempts")


def retry_rate(events):
    """`retries / admissions`: how often a task had to be tried again."""
    return rate(retries(events), admissions(events),
                what="a retry rate needs admissions")


def _count(events, kind):
    """How many events are of one kind."""
    return sum(1 for event in events if event["kind"] == kind)


def _gcd(one, other):
    """The greatest common divisor of two counts, the plain two-step way."""
    while other:
        one, other = other, one % other
    return one
