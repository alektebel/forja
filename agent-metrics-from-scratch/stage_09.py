"""Agent Metrics From Scratch — stage 9: The report, and the fleet's own count.

Eight stages have built the folds. This one is where they become a *report*: one
row of eighteen cells over one window and — this is the stage's real subject —
the one thing that makes the row worth believing, the fleet's **own count** of
what it did. `record()` writes two things down: the events, and a summary the
simulation counted as it went, never derived from the lines. A fold over the
events that disagrees with that summary has lost an event, counted one twice, or
misread a kind, and it is wrong. So a report is not a printout; it is a claim,
and the claim is checked against the world that made it before it is returned.

The eighteen cells are the course in one row: how many events fell in the window,
what the counters did (`tasks`, `attempts`, `failures`, `retries`, `dropped`),
what the queue's state was at the window's two ends and how deep it got inside,
the three quantiles of the attempts that finished in it, what it spent in tokens
and in micros, and the two rates. `metrics` recomputes every cell from the events
and nothing else — never from a summary — because a counter taken from the
fleet's own record is a number that can never disagree with it, and a check that
cannot fail is not a check. `report` folds the window and then walks the fleet's
count, refusing the first key whose numbers differ, naming the key *and both
numbers*. `audit` walks the same comparison and reports instead of raising: the
keys the fleet counted that the row cannot explain, the cells the row holds that
the fleet never counted, and how many keys were compared at all.

Two of the cells are read from the whole run and not from the window's own
events: the depth at the window's two ends and the peak inside it, because a
window is a state somebody was already in. So are the attempt latencies, and an
attempt is attributed to the window its finish fell in — which is what lets a
tumbling set partition a run's attempts exactly as it partitions its events.

DESIGN DECISION — why is the fleet's own count the tie-breaker, when the events
are right there to fold?
    Because the events are what the fold was given and the summary is what
    *happened*, and the two are written by different code paths. The lines can be
    read back with a field dropped, an event lost on a boundary, a kind
    misread — and every one of those mistakes is invisible in the events
    themselves, because the events were the thing that was damaged. The summary
    is a second witness: the simulation incremented a counter as it went, so a
    fold that reproduces all twelve of its keys has proved it lost nothing, and
    that proof is the reason to believe the other six cells too. It is also why
    the report is built *from the events* rather than from the summary: a
    counter taken from the fleet's record can never disagree with it, and a
    report whose every number came from the witness is not a second witness at
    all.

DESIGN DECISION — why does the default window run from the first event's tick to
the last event's tick *plus one*, and what does a run with no events answer?
    Because the interval is half-open everywhere in this course, so the run's own
    last tick is *inside* the run's window and the default window is the whole
    run — `[first, last + 1)`, not `[first, last]`. Getting that off by one drops
    exactly the last event of every run: the final finish, the last drop, the one
    event whose tokens and micros nobody would ever see in the numbers again. A
    run with no events at all has no first tick to start from, so its window is
    the single tick `[0, 1)` — the empty run's own empty window — and the row is
    the zero row, which is the honest answer to a dashboard over a fleet that did
    nothing.

DESIGN DECISION — why does a window that nothing happened in answer a row of
zeros, when the folds below this stage refuse an unmeasured field?
    Because a `total` over a field nobody measured and a window in which nothing
    finished are different questions, and only the first has no answer. Stages 2,
    4 and 7 refuse on purpose: "no event here carries tokens_out" and "a quantile
    of an empty sequence is a question with no answer" are verdicts on a *fold of
    nothing*. A report is a row of cells, and a cell of a window is asked about
    whatever the window contains — nothing, sometimes — so the report answers
    zero for the percentile of no attempts and for the rate with no denominator,
    and the refusals below it stay exactly as sharp for the caller who asks them
    directly. The cells that are the window's *state* are not part of the zero
    row: a window that nothing happened in can still have a queue in it, and its
    peak is the first tick of the window when nothing inside it ever went deeper.

DESIGN DECISION — why is an attempt's latency counted in the window it *finished*
in, and the gauge read from the whole run?
    Because a latency is a measurement, and a measurement belongs to the moment
    it was taken: an attempt is over when it finishes, and the window that holds
    the finish holds what the attempt cost. That is also what makes the cells add
    up: each `finished` event is in exactly one window of a tumbling set, so each
    attempt is in exactly one of their percentile cells, and the three quantiles
    of the whole run are the quantiles of the union. The depth is the other half
    of the same rule — a gauge is a *state*, not a measurement, so the window's
    ends and its peak are read from the run: the queue at the window's first tick
    is what the ticks before it left behind, and a window that began at 20 is
    still looking at a task admitted at 6.

DESIGN DECISION — why does `audit` report what it cannot compare instead of
raising the first disagreement?
    Because `report` is the verdict and `audit` is the coverage, and a caller who
    is diagnosing a disagreement needs to know how much of the board the proof
    covers. `missing` is every key the fleet counted that the row cannot explain:
    the ones the row has no cell for at all (`died`, `first_tick`), the one that
    is a state rather than a fold (`in_flight`), and any comparable key whose
    number came out different. `extra` is the other side of the same ledger: the
    cells the row holds that this fleet never counted, so nobody reads a
    percentile on this board as verified. `count` is how many keys were actually
    put side by side. An audit that raised would answer none of that: it would
    stop at the first key, and the second one would still be a mystery.

DESIGN DECISION — why is `in_flight` the window's own end state rather than a
cell the fleet's count can check?
    Because the fleet counts *folds* — admissions, finishes, retries, tokens,
    micros — and the depth is a different kind of number, derived from those
    counters rather than recorded. A whole run ends with everything resolved, so
    a summary that carried an `in_flight` would be carrying the state at whatever
    instant it stopped counting, which is not the window's last tick and not a
    number the fleet ever promised. So the walk refuses to put that cell beside
    anything: a caller who hands over a summary carrying `in_flight` is not
    refused, because the fleet may say whatever it likes — but the cell is never
    compared, and the audit reports it as a key the row cannot explain.

TODO: implement `metrics`, `report` and `audit`.
"""

import stage_01

#: The eighteen cells of a report, in the order `metrics()` writes them: how many
#: events fell in the window, the five counters, the queue's state at the
#: window's two ends and its peak inside, the three quantiles of the attempts
#: that finished in it, what it spent, and the two rates.
METRIC_KEYS = ("events", "tasks", "attempts", "failures", "retries", "dropped",
               "in_flight", "depth", "peak_tick", "peak_depth", "p50", "p95",
               "p99", "tokens_in", "tokens_out", "micros", "failure_bp",
               "retry_bp")


class ReportError(stage_01.TelemetryError):
    """A report, a fleet's own count or a window this stage refuses.

    The refusal names the offender — the key the fleet's count and the events
    disagree about, the bound that is not a tick, the index of the event that is
    not a record — and, when the offender is a disagreement, it carries *both*
    numbers, because a report that says only "the numbers differ" is a report
    nobody can act on.
    """


def metrics(events, *, start=None, end=None):
    """One window's eighteen cells, over exactly `METRIC_KEYS` and in that order.

    `events` is the run and `[start, end)` the window; both bounds default to the
    whole run (`[the first event's tick, the last event's tick + 1)`), so a
    report over a whole run is a window like any other. Every cell is recomputed
    from the events and nothing else: the counters from stages 2 and 7, the depth
    from stage 3, the quantiles from stage 4 over stage 5's attempt latencies, the
    tokens and micros from stage 6.

    A window holds events, but it also *is* a state: `depth`, `in_flight`,
    `peak_tick` and `peak_depth` are read from the whole run, because the queue
    at the window's first tick is what the ticks before it left behind. An
    attempt's latency is attributed to the tick its finish fell in, so a window
    that begins in the middle of an attempt still holds that attempt's cost.

    Refuses a window with no width (a point has no fold), a bound that is not a
    non-negative int, an `events` that is not a sequence of records, and an event
    that carries no tick — each naming the offender. Every cell that folds the
    window's own events answers zero when the window measured nothing; the folds
    below this stage keep refusing an unmeasured field for a caller who asks them
    directly.
    """
    raise NotImplementedError("stage 9: implement metrics()")


def report(events, fleet_summary, *, start=None, end=None):
    """The window's row, once the fleet's own count agrees with it.

    Folds the window exactly as `metrics` does, then walks `fleet_summary` in its
    own order and compares every key it carries that `METRIC_KEYS` also has —
    except `in_flight`, which is the window's own end state and not a fold the
    fleet counts. The first disagreement is refused, naming the key and both
    numbers ("failures: the fleet counted 4, the events say 3"). A whole-interval
    report is therefore a *proof* that the fold lost nothing, which is the reason
    to believe every other number on the row; the row is returned unchanged, and
    a mapping the fleet counted nothing in is a row of zeros like any other.

    Refuses a `fleet_summary` that is not a mapping of metric names to counts,
    and everything `metrics` refuses.
    """
    raise NotImplementedError("stage 9: implement report()")


def audit(events, fleet_summary, *, start=None, end=None):
    """The same walk as `report`, reporting instead of raising.

    A mapping over exactly `("missing", "extra", "count")`:

    * `missing` — the keys the fleet counted that the row does not explain: the
      ones with no cell on the row (`died`, `first_tick`), the state the walk
      never compares (`in_flight`), and any comparable key whose numbers differ;
    * `extra` — the cells the row holds that the fleet's count does not carry, in
      `METRIC_KEYS` order, so nobody reads them as verified against the world;
    * `count` — how many keys were actually put side by side.

    Both tuples are in a fixed order — `missing` follows the fleet's own count,
    `extra` follows `METRIC_KEYS` — so two audits of the same pair are equal.
    Refuses only what `report` refuses about its arguments; a disagreement is
    reported here, never raised.
    """
    raise NotImplementedError("stage 9: implement audit()")
