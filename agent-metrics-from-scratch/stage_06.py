"""Agent Metrics From Scratch — stage 6: Tokens, and the cost that was summed first.

A token count is a fact about a call, but a price is a property of the pool that
ran it — so the money this stage reports is built from two things no single event
owns: the tokens the call spent and the rate the pool charges for them. The rate
lives in exactly one place, `telemetry.PRICES`, keyed by the *event's* pool, and
a pool the table does not name is refused rather than defaulted: a default rate
is a rate somebody made up, and every number downstream would carry the invention
without ever saying so. The one piece of arithmetic the whole stage turns on is
the order of two operations. A cost per task is the sum of every event's micros,
divided once by the number of events that finished; it is *never* the mean of a
column of per-event figures, because a figure already divided has already lost
the remainder it was going to lend to its neighbours.

    TOKEN_KEYS     the two halves of a token count, in the order they are reported
    COST_KEYS      the five keys of a cost per task, in the order they are reported
    CostError      what a pool with no price, or a cost with no denominator, raises
    tokens         every token the run spent, in and out
    by_pool        what each pool spent, in micros, its pools in sorted order
    micros         the run's exact total, in micros
    cost_per_task  one sum over one count: the exact pair and the floored basis points

DESIGN DECISION — why is a price a property of the *pool* and not of the task or
of the call?
    Because a task is what has to be done and a pool is where it was done: the
    same `render` costs one thing on a pool that runs a small model and another
    on a pool that runs a wide one, so the only field that can decide the rate is
    the one that names where the work ran. `telemetry.PRICES` is keyed by pool for
    that reason, and the fold reads the *event's* own pool field rather than
    trusting any caller to hand the price in. A pool the table does not have is
    refused by name — never defaulted to `{"in": 1, "out": 1}` — because a
    defaulted rate is a number nobody can trace back to a decision, and it would
    sail through every check downstream as if it had been real.

DESIGN DECISION — why is a cost per task a sum divided once, and not the mean of
the per-event figures?
    Because integer division does not commute with addition. Pricing one event
    and then rounding it down loses the remainder that event's neighbours were
    going to carry; sum a column of floored figures and the answer is smaller
    than the exact one by up to one micro per event, silently, forever. The sum
    is the only intermediate that is exact — it is a total of whole micros — so
    the divide happens exactly once, at the end, on the whole total. This is why
    `micros` answers an int and `cost_per_task` answers an *exact reduced pair*
    alongside its floored basis points: the pair is the truth and the basis
    points are the one lossy spelling the course allows, and it is floored so two
    readers of the same events cannot disagree about which way to go.

DESIGN DECISION — what is the denominator of a cost per task, and why does a task
that never finished appear in neither the numerator nor the denominator?
    Because the numerator and the denominator have to be about the same events,
    or the quotient is about nothing. The numerator is the micros of every event
    that finished — a failed attempt finished too, and its tokens were really
    spent — and the denominator is how many events finished. A task that was
    dropped, or that ran out of ticks still waiting, spent its tokens nowhere and
    finished nowhere, so it belongs in neither: counting admissions would price
    work that never happened, and counting every event would divide real money by
    admissions and retries that cost nothing. A zero denominator is refused, not
    answered with zero, because "nobody finished" is a question with no answer
    and zero is a number.

DESIGN DECISION — why does `tokens` fold *every* event instead of selecting the
finished ones?
    Because `ABSENT` is a field nobody measured and it must count nothing rather
    than refuse, and a fold that reached for `event["tokens_in"]` on an admitted
    event would either crash on the string `-` or, worse, be "fixed" with a
    default. `tokens` therefore reads both token fields of every event and lets
    `ABSENT` contribute zero, which means an event that never spent a token is
    invisible and an event that did is counted — a fact of the fold, not a filter
    anyone has to maintain. It is also the reason `tokens` needs no price at all:
    a token is a property of the task, and only `by_pool`, `micros` and
    `cost_per_task` ever look a pool up.

DESIGN DECISION — why does `by_pool` report a pool that never finished anything,
and why is its key order the sorted one rather than the caller's?
    Because "this pool spent zero" and "this pool is not in the run" are different
    answers to an operator's question, and a mapping that dropped a zero-spend
    pool would make the two indistinguishable. `by_pool` walks every event, so it
    prices each pool the run names, including one that only ever admitted and
    dropped; a pool with nothing to price answers zero. The keys are sorted so the
    mapping does not depend on the order the events happened to arrive in — a
    metric is a function of the *events*, not of the sequence they were handed
    over in — and the returned mapping is fresh, so a caller bending it cannot
    bend the events.

TODO: implement `tokens`, `by_pool`, `micros` and `cost_per_task`.
"""

import telemetry

import stage_01
from stage_01 import TelemetryError

#: The two halves of a token count, in the order `tokens` reports them.
TOKEN_KEYS = ("in", "out")

#: The five keys of a cost per task, in the order `cost_per_task` reports them.
#: A ratio is a pair here — `numerator` over `denominator` — and the floored
#: basis points are the one scalar spelling this course allows.
COST_KEYS = ("micros", "tasks", "numerator", "denominator", "bp")


class CostError(TelemetryError):
    """A pool with no price, or a cost that has no denominator.

    The refusal names the offender — the pool — and, when the offender is within
    edit distance two of a pool the price table has, the pool it probably meant.
    """


def tokens(events):
    """Every token the run spent, in and out.

    A fold over each event's two token fields: `ABSENT` is a field nobody
    measured and counts nothing, so an event that never finished contributes
    zero rather than a refusal. The mapping is fresh, with `in` before `out`.
    """
    raise NotImplementedError("stage 6: implement tokens()")


def by_pool(events):
    """What each pool spent, in micros, its pools in sorted order.

    The price is looked up by the event's own `pool` field, and a pool the price
    table does not name is refused by name rather than defaulted. A pool the run
    names but never finishes anything on answers zero; the keys are sorted so the
    mapping does not depend on the order the events arrived in.
    """
    raise NotImplementedError("stage 6: implement by_pool()")


def micros(events):
    """The run's exact total, in micros.

    The sum of `by_pool`: a total that were a mean of per-event figures would be
    a total nobody could add a second run to.
    """
    raise NotImplementedError("stage 6: implement micros()")


def cost_per_task(events):
    """One sum over one count: the exact pair and the floored basis points.

    Sum first, divide once — the numerator is the whole run's micros and the
    denominator is how many events finished, so a task that never finished
    appears in neither. A zero denominator is refused.
    """
    raise NotImplementedError("stage 6: implement cost_per_task()")
