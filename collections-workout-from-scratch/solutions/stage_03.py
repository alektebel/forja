"""Collections Workout From Scratch — stage 3: Replaying the actual action log.

The pyramid of stage 2 generates actions day by day and writes them to the bank's
own log. This stage reads the log and asks a harder question: does every row of
the log *belong*? A valid row must be inferable from the pyramid rules and the
loan's history — the day must be one the walk reaches, the action must follow
the ladder order, and the conditions that made it fire must have held on the
record the pyramid walked.

The stage answers with the loan's own sequence of log rows, exactly as
workout.py generated them, and it also validates the log's integrity by
walking the pyramid itself and comparing row for row. A row the pyramid
cannot justify is a gap between the bank's records and the rule it was
supposed to follow.

    ReplayError                the refusal this stage raises
    LOG_RECORD_KEYS            the six fields of one replay record, in order
    replay(book, loan)         -> the loan's own action rows, verified
    vault()                    -> the log's integrity: no unexplained rows

DESIGN DECISION — why does the stage validate the log instead of just echoing it?
Because the pyramid generates the log, and a log that cannot be inferred from
the pyramid is a breach of the rule the bank was meant to follow. A stage that
only echoes the log would not test whether the bank's process itself was
correct; the vault catches a dunning fired on a current day, a referral with
no call before it, or a second call inside one window, each of which is a
forgery the pyramid would refuse.

DESIGN DECISION — why does the stage walk the loan's own pyramid to validate?
Because the conditions the pyramid checks are about the loan's history: a
window is the run of days with a positive dpd, a letter fires once per window,
and a referral leaves the pyramid forever. Reading workout.py's log for the
conditions and the pyramid for the triggers would create a circular dependency;
walking the same walk the pyramid walked is the only way to independently verify.

DESIGN DECISION — why are the vault's checks structural (the pyramid rules) rather
than just comparing the replay to the log?
Because the replay is *the* log, so a comparison would be a tautology. The vault
asks: could the pyramid have produced *exactly* these rows? A row that the
pyramid could not produce, even on the same date, is a gap.

TODO: implement `ReplayError`, `replay` and `vault` in this file: the
loan's verified log sequence and the log's integrity check.

    A loan is refused by name when the book does not hold it.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import book as book_module
import workout as col
import dates
import rules
import stage_01 as s1
import stage_02 as s2

LOG_RECORD_KEYS = ("loan", "date", "action", "trigger_day", "condition", "outcome")


class ReplayError(ValueError):
    """The refusal this stage raises: a log row that cannot belong.

    It names the offender — the loan the book does not hold, the action outside
    `col.ACTIONS`, the log row the pyramid could not justify — because a
    replay that cannot be justified must say what it was asked for rather than
    answer a row nobody can defend.
    """


def replay(book, loan):
    """The verified log sequence for one loan.

    Returns the loan's rows from `workout.py`'s log, in date order, each
    wrapped in a record that adds the pyramid's own `trigger_day` and `condition`
    from the world's `PYRAMID` table. The rows are verified: each action must
    be inferable from the pyramid walk and the loan's history.

    A loan the book does not hold is refused by name.
    """
    record = _resolve(book, loan)
    loan_id = _loan_id(record)
    rows = []
    for row in col.log_of(loan_id):
        pyramid_step = _pyramid_step(row["action"])
        rows.append({
            "loan": loan_id,
            "date": row["date"],
            "action": row["action"],
            "trigger_day": pyramid_step["trigger_day"],
            "condition": pyramid_step["condition"],
            "outcome": row["outcome"],
        })
    # Verify each row against the pyramid walk
    _verify_replay(loan_id, rows, book, record)
    return tuple(rows)


def vault():
    """The log's integrity: every logged action must be inferable from the pyramid.

    Walks every loan in the book's history under the pyramid and compares the
    generated rows against `workout.py`'s log. Returns a tuple of
    `(loan, explanation)` for each row the pyramid could not justify.

    A vault that returns an empty tuple is honest: the log matches the pyramid.
    """
    book = book_module.Book.build(7)
    gaps = []
    for loan_record in book.loans():
        loan_id = loan_record["loan"]
        try:
            generated = _pyramid_walk(book, loan_record)
            logged = tuple(row for row in col.log_of(loan_id))
            # Compare: every logged row must be justifiable
            for log_row in logged:
                justifiable = False
                for gen_row in generated:
                    if gen_row["date"] == log_row["date"] and                        gen_row["action"] == log_row["action"]:
                        justifiable = True
                        break
                if not justifiable:
                    gaps.append((loan_id,
                        "row at %s for %s cannot be justified by the pyramid"
                        % (log_row["date"], log_row["action"])))
        except Exception:
            gaps.append((loan_id, "walk failed"))
    return tuple(gaps)


# --- private helpers --------------------------------------------------------

def _resolve(book, loan):
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    for record in book.loans():
        if _loan_id(record) == name:
            return record
    raise ReplayError("the book holds no loan %r" % (name,))


def _loan_id(record):
    if isinstance(record, dict):
        return record.get("loan", record.get("id"))
    return record


def _pyramid_step(action):
    for step in col.PYRAMID:
        if step["action"] == action:
            return step
    raise ReplayError(
        "the action %r is not one of the pyramid steps %r"
        % (action, tuple(s["action"] for s in col.PYRAMID)))


def _pyramid_walk(book, record):
    """The pyramid walk for one loan, producing the same rows workout.py does."""
    loan_id = _loan_id(record)
    window_start = col.WINDOW_START
    window_end = col.WINDOW_END
    # Get dpd grid
    from stage_02 import _dpd_grid, _next_day, _loan_history, _forborne_at
    flows, payments = _loan_history(book, record)
    dpd_by_day = _dpd_grid(flows, payments)

    defaults = tuple(row for row in book.defaults() if row["loan"] == loan_id)
    cures = tuple(row["cured_on"] for row in defaults if row["cured_on"] is not None)

    # Find write-off
    write_off = None
    for event in book.events(record):
        if event["kind"] == "write-off":
            write_off = event["date"]
            break

    day = window_start
    letter = None
    call = None
    referred = False
    result = []

    while day <= window_end:
        if write_off is not None and day >= write_off:
            break
        if day in cures:
            letter = None
            call = None
        dpd_val = dpd_by_day.get(day, 0)
        if dpd_val == 0:
            letter = None
            call = None
        if _forborne_at(book, record, day):
            day = _next_day(day)
            continue
        if dpd_val >= col.PYRAMID[0]["trigger_day"] and letter is None:
            result.append({"loan": loan_id, "date": day,
                          "action": col.PYRAMID[0]["action"],
                          "outcome": "dpd-%d" % (dpd_val,)})
            letter = day
        if dpd_val >= col.PYRAMID[1]["trigger_day"] and letter is not None and call is None:
            result.append({"loan": loan_id, "date": day,
                          "action": col.PYRAMID[1]["action"],
                          "outcome": "dpd-%d" % (dpd_val,)})
            call = day
        if dpd_val >= col.PYRAMID[2]["trigger_day"] and call is not None:
            result.append({"loan": loan_id, "date": day,
                          "action": col.PYRAMID[2]["action"],
                          "outcome": "dpd-%d" % (dpd_val,)})
            break  # referral leaves the pyramid
        day = _next_day(day)
    return result


def _verify_replay(loan_id, rows, book, record):
    """Verify each row can be justified by the pyramid walk."""
    generated = _pyramid_walk(book, record)
    for row in rows:
        matching = [g for g in generated
                    if g["date"] == row["date"] and g["action"] == row["action"]]
        if not matching:
            raise ReplayError(
                "row at %s for %s cannot be justified by the pyramid"
                % (row["date"], row["action"]))


if __name__ == "__main__":
    book = book_module.Book.build(7)
    print("stage 3 — replaying the action log")
    for loan_name in ("L-01", "L-06", "L-07", "L-09", "L-11"):
        try:
            result = replay(book, loan_name)
            print("  %-5s -> %d row(s)" % (loan_name, len(result)))
            for row in result:
                print("        %s %s %-20s trigger=%-3d outcome=%s"
                      % (row["date"], row["action"], "", row["trigger_day"], row["outcome"]))
        except ReplayError as error:
            print("  %-5s refused: %s" % (loan_name, error))
    gaps = vault()
    if gaps:
        print("  VAULT: %d gap(s)" % len(gaps))
        for loan_id, explanation in gaps:
            print("        %-5s %s" % (loan_id, explanation))
    else:
        print("  VAULT: clean — every row justifiable")
