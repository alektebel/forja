"""Collections Workout From Scratch — stage 2: The pyramid and its triggers.

The bank's collections operation is a pyramid and this stage is the pyramid's
own walk. Three steps climb it — a dunning letter at day 10 past due, a phone
call at day 30, a referral to the workout desk at day 60 — and each step's
condition is a fact the loan's own history answers, not a rule the
call-site's mood answers: a loan that has already been referred is not
re-referred (it sits at the desk), a loan under a forbearance probation is
exempt from every step while the probation stands, a loan whose arrears have
cured exits the window it was in, and a loan the bank has written off takes no
steps ever again. The step fires on the FIRST day the loan's materiality-tested
days past due reach the trigger while the condition still holds, and all three
can fire on one day when the arrears jump from nothing past sixty — the bank's
ledger produces exactly such a jump on L-07 and L-09.

What the stage answers is a DATE question, not a history question: which of the
pyramid's steps fire on this day for this loan. The answer is empty on the
thousands of days nothing fires, and on the trigger days it is one, two or
three records — each naming the trigger day, the day's own `dpd` as the
outcome token, and the condition the loan's history satisfied for THIS step.

    TraversalError               the refusal this stage raises
    ACTION_KEYS                  the six fields of one pyramid step record
    PYRAMID (from the world)     the steps and their trigger days and conditions
    due_actions(book, loan, at)  -> the steps that fire on `at` for this loan

DESIGN DECISION — why does the stage walk the loan's delinquency day by day
instead of answering `at` alone?
Because the conditions are about a WINDOW, not about a day: the letter fires
once per delinquency window, the call once per window after a letter, and "the
window" is the run of days with a positive `dpd`. Whether a call is due at `at`
depends on whether a letter is already on record INSIDE that window, which is
unanswerable without knowing where the window opened. The stage therefore walks
the loan's days past due from the walk's own first day, carrying the letter and
the call and the referral through the window, and answers the steps that fire
the day `at` arrives.

DESIGN DECISION — why is the walk's record the world's own action log?
Because the conditions ask about the actions ON RECORD, and the bank's record
is the only one: whether a letter has already gone out in this window is a fact
about what the desk actually did. Reading the loan's OWN history for the days
past due and the log for the actions taken is the whole split — the pyramid's
triggers run off the borrower's money, and its conditions off the bank's acts.

DESIGN DECISION — why does the stage refuse days outside the walk's window?
Because the walkable world has an edge: the operation's log begins at
`WINDOW_START` and ends at `WINDOW_END`, and a trigger day asked for a week
before the log starts would need a window state nobody recorded. A date the
pyramid never walked is refused by name rather than answered from nothing —
an empty answer would look like "no steps fire" when it means "no record
exists".

DESIGN DECISION — why do all three steps carry the DAY'S `dpd` as the outcome?
Because the desk's log does: the outcome token is `"dpd-<n>"`, the days past
due the action was taken at, which is what a reader of the log needs to make
sense what the step found. A record named the same way the log names its rows
lets stage 3 replay the log against this walk — the pyramid generates the log,
and the log never generates the pyramid.

DESIGN DECISION — why is the referral's stickiness part of the walk rather than
a post-check?
Because "takes no further steps at all" is a property of the loan's history
from the day the referral landed, and the walk reaches it cleanly: once the
desk has been reached inside the walk, the loan's later days are never re-walked
as candidates. A post-filter would have to re-derive the same fact and could
disagree about the first reach day.

TODO: implement `TraversalError` and `due_actions` in this file: the day-by-day
pyramid walk to `at`, the conditions the loan's history answers, and the
records for the steps that fire on the day itself.

    A loan is refused by name when the book does not hold it, and a day is
    refused by name when it is not ISO text or lies outside the walk's window.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import workout as col
import dates
import rules

ACTION_KEYS = ("loan", "at", "action", "trigger_day", "condition", "outcome")

WINDOW_START = col.WINDOW_START

WINDOW_END = col.WINDOW_END


class TraversalError(ValueError):
    """The refusal this stage raises: something the pyramid cannot walk.

    It names the offender — the loan the book does not hold, the day outside
    the walk's window, the day that is not ISO text — because a trigger day the
    pyramid cannot walk must say what it was asked for rather than answer a
    record nobody can defend.
    """


def due_actions(book, loan, at):
    """The pyramid steps that fire on `at` for this loan, each a record.

    The walk carries the loan's window state — the letter and the call on
    record inside the current window, whether the desk has been reached — from
    the walk's own first day to `at`, the days past due re-derived from the
    loan's payment ledger exactly as stage 1 does, and the forbearance and
    write-off facts the bank recorded. On `at` the ladder is evaluated in its
    own order and every step whose condition holds fires once, so a day whose
    `dpd` jumps past sixty answers three records.

    A loan the book does not hold, a day that is not ISO text, or one outside
    `WINDOW_START`..`WINDOW_END` is refused by name.
    """
    record = _resolve(book, loan)
    day = _day(at)
    if day < WINDOW_START or day > WINDOW_END:
        raise TraversalError("the walk runs from %s to %s, not to %s"
                             % (WINDOW_START, WINDOW_END, day))
    loan_id = _loan_id(record)
    state = _walk_to(book, record, day)
    if state["forborne"] or state["written_off"]:
        return ()
    steps = []
    dpd_answer = state["dpd"]
    if dpd_answer == 0:
        return ()
    for step in col.PYRAMID:
        action, trigger, condition = step["action"], step["trigger_day"], step["condition"]
        if dpd_answer < trigger:
            continue
        if action == "dunning-letter" and state["letter"] is not None:
            continue
        if action == "call" and (state["letter"] is None or state["call"] is not None):
            continue
        if action == "workout-referral" \
                and (state["call"] is None or state["referred"]):
            continue
        steps.append({"loan": loan_id, "at": day, "action": action,
                      "trigger_day": trigger, "condition": condition,
                      "outcome": "dpd-%d" % (dpd_answer,)})
        if action == "dunning-letter":
            state["letter"] = day
        elif action == "call":
            state["call"] = day
        else:
            state["referred"] = True
    return tuple(steps)


# --- the machinery, private to this stage -------------------------------------


def _walk_to(book, record, until):
    """The loan's window state carried to `until`, as the pyramid reads it.

    The walk's record is the bank's own log: the letter, the call and the
    referral on record so far. The walk starts at `WINDOW_START`, resets that
    record every day the `dpd` returns to zero or a valid cure lands, and
    carries the loan's forbearance and write-off facts with it. The rows dated
    `until` itself are the day's own acts, not the state the day reads: the
    arrival day's state is read strictly before them.
    """
    loan_id = _loan_id(record)
    flows, payments = _loan_history(book, record)
    dpd_by_day = _dpd_grid(flows, payments)
    cures = tuple(row["cured_on"] for row in book.defaults()
                  if row["loan"] == loan_id and row["cured_on"] is not None)
    logged = {}
    for row in col.log_of(loan_id):
        logged.setdefault(row["date"], []).append(row)
    write_off = None
    for event in book.events(record):
        if event["kind"] == "write-off":
            write_off = event["date"]
    state = {"dpd": 0, "letter": None, "call": None, "referred": False,
             "forborne": False, "written_off": False}
    day = WINDOW_START
    while day < until:
        if write_off is not None and day >= write_off:
            state["written_off"] = True
        if day in cures:
            state["letter"] = None
            state["call"] = None
        if dpd_by_day.get(day, 0) == 0:
            state["letter"] = None
            state["call"] = None
        for row in logged.get(day, ()):
            if row["action"] == "dunning-letter":
                state["letter"] = day
            elif row["action"] == "call":
                state["call"] = day
            else:
                state["referred"] = True
        day = _next_day(day)
    state["written_off"] = state["written_off"] or \
        (write_off is not None and write_off <= until)
    if until in cures:
        state["letter"] = None
        state["call"] = None
    state["dpd"] = dpd_by_day.get(until, 0)
    if state["dpd"] == 0:
        state["letter"] = None
        state["call"] = None
    state["forborne"] = _forborne_at(book, record, until)
    return state


def _dpd_grid(flows, payments):
    """The materiality-tested days past due, per day of the walk's window.

    The same arithmetic stage 1 names: the covered-arrears view must clear both
    halves of the materiality test before the oldest short instalment's
    distance accrues a single day.
    """
    grid = {}
    owed = 0
    covered = 0
    instalments = 0
    prepaid = 0
    owe_at = {}
    for due, amount in flows:
        owe_at[due] = amount
    cov = {}
    first = WINDOW_START
    seeds = [flow for flow in flows if flow[0] < first]
    owed = sum(flow[1] for flow in seeds)
    for row in payments:
        if row["paid_on"] < first:
            if row["kind"] == "instalment":
                instalments += row["amount_cents"]
                cov[row["due"]] = cov.get(row["due"], 0) + row["amount_cents"]
                if row["due"] < first:
                    covered += row["amount_cents"]
            elif row["kind"] == "prepayment":
                prepaid += row["amount_cents"]
    day = WINDOW_START
    ref = 0
    while day <= WINDOW_END:
        owed = owed + owe_at.get(day, 0)
        for row in payments:
            if row["paid_on"] == day:
                if row["kind"] == "instalment":
                    instalments += row["amount_cents"]
                    cov[row["due"]] = cov.get(row["due"], 0) + row["amount_cents"]
                    covered += row["amount_cents"]
                elif row["kind"] == "prepayment":
                    prepaid += row["amount_cents"]
        arrears = owed - covered
        if arrears < 0:
            arrears = 0
        drawn = instalments - prepaid
        if drawn < 0:
            drawn = 0
        while ref < len(flows) and flows[ref][0] <= day \
                and cov.get(flows[ref][0], 0) >= flows[ref][1]:
            ref = ref + 1
        answer = 0
        if ref < len(flows) and flows[ref][0] <= day \
                and arrears >= rules.MATERIALITY_ABSOLUTE_CENTS \
                and arrears * rules.DISCOUNT_SCALE \
                >= rules.MATERIALITY_RELATIVE_BP * drawn:
            answer = dates.days_between(flows[ref][0], day)
        grid[day] = answer
        day = _next_day(day)
    return grid


def _resolve(book, loan):
    """One loan's record, from an id or a record, or the refusal naming it."""
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    found = None
    for record in book.loans():
        if _loan_id(record) == name:
            found = record
    if found is None:
        raise TraversalError("the book holds no loan %r" % (name,))
    return found


def _loan_id(record):
    """The record's loan id, whatever shape arrived."""
    if isinstance(record, dict):
        return record.get("loan", record.get("id"))
    return record


def _day(value):
    """A check that the day is ISO text, or the refusal naming what arrived."""
    if not isinstance(value, str):
        raise TraversalError("the day %r is a %s, not ISO text"
                             % (value, type(value).__name__))
    try:
        dates.parse(value)
    except Exception as error:
        raise TraversalError("the day %r is not readable: %s" % (value, error))
    return value


def _next_day(day):
    """The ISO text of the day after `day`, on the contract's own calendar."""
    year, month, d = dates.parse(day)
    d = d + 1
    if d > dates.days_in_month(year, month):
        d = 1
        month = month + 1
        if month > 12:
            year, month = year + 1, 1
    return dates.iso(year, month, d)


def _forborne_at(book, record, day):
    """Whether a forbearance probation stands at `day`: granted on or before it,
    running for the length the remedies carry."""
    for event in book.events(record):
        if event["kind"] == "forbearance" and event["date"] <= day:
            until = dates.add_months(event["date"], rules.CURE_MONTHS)
            if day < until:
                return True
    return False


def _loan_history(book, record):
    """The loan's dues and its payment rows, in the shapes the walk reads."""
    schedule = book.schedule(record)
    flows = tuple((flow["date"], flow["amount_cents"])
                  for flow in schedule["flows"])
    payments = tuple(book.payments(record))
    return flows, payments


if __name__ == "__main__":
    import book as book_module
    the_book = book_module.Book.build(7)
    print("stage 2 — the steps that fire")
    for loan_name, days in (("L-06", ("2031-04-07", "2031-04-08", "2031-04-27",
                                     "2031-05-27", "2031-06-11")),
                            ("L-07", ("2031-11-30",)),
                            ("L-09", ("2031-07-31",)),
                            ("L-11", ("2031-08-10", "2031-08-30", "2031-09-29")),
                            ("L-01", ("2031-04-07",))):
        for day in days:
            steps = due_actions(the_book, loan_name, day)
            print("  %-5s %s -> %d step(s)" % (loan_name, day, len(steps)))
            for step in steps:
                print("        %-17s trigger=%-3d outcome=%-8s %s"
                      % (step["action"], step["trigger_day"], step["outcome"],
                         step["condition"]))
