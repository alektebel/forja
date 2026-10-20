"""collections.py — the bank's collections operation as data.

Provided, frozen, and never written by the course. Where `book.py` holds the
bank's raw facts and its own accounting records, this module holds the
*operation* the bank ran over those facts between a loan's first missed
instalment and the day the workout closes: the pyramid of actions a delinquent
loan walks, the forbearance remedies the bank may grant, the waterfall every
payment splits through, the actions the bank actually took (`LOG`), the
payment-long ledger the waterfall produced (`LEDGER`, over the claims the desk
billed, `CLAIMS`), the workout records the desk compiled against its defaulted
collateralised loans (`SALES`), and the forbearance grants the bank actually
made (`GRANTS`).

Everything here is **generated at import, deterministically, from the book**:
the module builds `book.Book.build(7)` once, walks each loan's own histories
day by day under the pyramid (`STRATEGY_VERSION "COL-1.0"`), and answers the
same tables every import. Nothing reads the clock, nothing is random, no float
is ever taken: every amount is an integer count of cents, every rate an integer
count of basis points, and every division carries the rounding the contract
pins (the same pinning `book.py` keeps its own records on, so a stage that
recomputes a slice of the operation agrees with these tables exactly).

The desk's rules, pinned here once:

1. **The pyramid.** Three steps, each with a trigger day of the loan's days
   past due (`dpd`, the arithmetic `book.py` keeps its statuses on: the arrears
   must clear BOTH halves of the materiality test before they accrue a day).
   A letter at day 10, a phone call at day 30, a referral to the workout desk
   at day 60. A step fires on the first day the loan's `dpd` reaches the
   trigger **while its condition still holds**; all three may fire on one day
   when a loan's `dpd` jumps from zero past sixty. The conditions the loan's
   own history answers: the *letter* and the *call* fire once per delinquency
   window (a window opens the day `dpd` first becomes positive and closes the
   day `dpd` returns to zero or a valid cure of the book's own signalling
   lands); a loan that has already been *referred* is not re-referred and takes
   no further pyramid steps at all — it sits at the desk; a loan with a
   *standing forbearance* is under probation and takes no steps while the
   probation stands (from the grant's day, for the length the remedies carry,
   `rules.CURE_MONTHS` — the loan's cure-day, when the book's own walk records
   one, closes the window too); and the day a loan is written off ends its log
   for good.
2. **The log.** `LOG` is the record of the steps that actually fired: one row
   per action, keyed `(loan, date, action, outcome)`, in loan order and then
   date order. The outcome is the desk's own token for what the step found:
   `"dpd-<n>"`, the days past due the action was taken at. The log is the
   bank's own record, and stage 3 proves the pyramid reproduces it — the log
   writes what the pyramid generated, never the reverse.
3. **The claims and the waterfall.** The desk keeps every loan on `CLAIMS`:
   principal lines, one per contractual instalment, billed at their due date if
   any payment of the loan remembers the due by then; recoverable-interest
   lines, billed once each — at `add_months(due, INTEREST_GRACE_MONTHS)`, and
   only where the instalment is still short there, counting every instalment
   row whose `paid_on` is at or before the billing — for
   `amount * period_bp * INTEREST_GRACE_MONTHS // 10000` cents (the grace is
   inside the pin: the bill lands at the lapse of the second month of lateness
   and charges that second month's interest, once); and fee lines, one per fee
   row the borrower paid, billed the day it was paid. Every payment row the
   book recorded is then walked in the book's own order — fee row to the fee
   tier, instalment row to interest then principal, prepayment row to
   principal — paying the open lines of the tier in billing order, each to the
   cent, a line taking `min(cash left, what it still owes)`. The cash left when
   no line still owes is the payment's *carried* excess; the shortfall the
   claims keep is open on the lines that still owe. `LEDGER` keeps one row per
   payment: `(loan, index, paid_on, cash_cents, fees_cents, interest_cents,
   principal_cents, carried_cents, open_cents)`, where `index` is the row's
   one-based position in the loan's own payment rows and `open_cents` is the
   total still owing on every claim line billed by then — the bank's own
   step-for-step record, and stage 6 reproduces every row of it. Two views of
   one loan are not to be confused: the *covered-arrears* view (the one
   `book.py` books statuses on) waives recoverable interest; the desk's claim
   lines do not — a catch-up that clears an instalment to the cent still
   carries the interest once billed, and the last open line keeps it.
4. **The forbearance remedies.** Three, in `REMEDIES`, each with its own belief
   about what the loan's history must show (`flags`) and one probation length,
   `probation_months` — `rules.CURE_MONTHS`, the policy's own. The flags the
   loan's own history answers, as of the day the remedy is asked for (an event
   the desk is booking *on* that day never stands against itself; a grant is
   asked, the history is asked as it stands on entry): `arrears-material` (the
   two-half materiality test passes at the day), `no-forbearance-standing`
   (another forbearance is not on record, granted strictly earlier and not yet
   expired), `not-defaulted` (no default signalled strictly before the day,
   the `dpd` at the day below the backstop, and no uncured pre-existing UTP
   flag standing), `not-written-off`, and `instalments-remaining` (dues still
   ahead). A remedy is eligible when every flag it demands passes, and the loan
   is granted the **first** eligible remedy in `REMEDIES` order.
   `GRANTS` records the forbearance grants the bank actually made: which
   remedy, which flags passed, and the probation the grant opened
   (`probation_until`). A grant the rules cannot book is refused by name —
   the desk reports rather than hides.
5. **The workout.** Every defaulted collateralised loan is sold, and `SALES`
   holds one record each: the day the bank signalled the default
   (`defaulted_on`, the book's own `defaults()` row — not the desk's earlier
   calendar), the sale date and the gross proceeds (the face of the book's own
   collateral recovery row; where the credit walk recorded none, the desk sells
   `SALE_MONTHS` after the signal at the collateral's face), the costs line by
   line (one `agent-fee` per sale; the book's negative costs row is that fee as
   the credit records it, and where the desk has no credit row it books
   `AGENT_FEE_BP` of the gross), the net proceeds (`gross - costs`), the
   exposure at the default (the loan's outstanding principal on the signalled
   day, the arithmetic `book.py` pins: each period's interest truncated on the
   balance before the payment, the principal portion the payment left over),
   the settlement (the cash the workout collected in `(defaulted_on,
   sale_date]`: the bank's own cash recovery rows and the instalments the
   borrower kept paying), and the deficiency the workout closed with:

       exposure_at_default = settlement + net_proceeds + deficiency

   clipped at zero, which is the identity every workout record satisfies, plus
   the cover the policy asks for: `net_proceeds` against the exposure, in
   basis points. A sale whose costs exceed its proceeds is still a row.
6. **The refusal family.** `StrategyError` is what the operation raises for
   anything it does not recognise: an action outside `ACTIONS`, a remedy
   outside `REMEDIES`, a loan the operation holds nothing on, a date outside
   the window, and — thrown by `collections.split_off`, the reference split the
   stages are held to — a waterfall that does not balance to the cent.
"""

import book as book_module
import dates
import rules

STRATEGY_VERSION = "COL-1.0"

#: The four fields of one logged action, in order.
LOG_KEYS = ("loan", "date", "action", "outcome")

#: The actions the pyramid can take, in the order the ladder climbs.
ACTIONS = ("dunning-letter", "call", "workout-referral")

#: The three steps of the pyramid, each a record of action, trigger day and
#: the condition the loan's own history answers.
PYRAMID_KEYS = ("action", "trigger_day", "condition")

PYRAMID = (
    {"action": "dunning-letter", "trigger_day": 10,
     "condition": "a window is open and no letter is on record in it"},
    {"action": "call", "trigger_day": 30,
     "condition": "a letter is on record in the window and no call is"},
    {"action": "workout-referral", "trigger_day": 60,
     "condition": "a call is on record and the desk has not been reached"},
)

#: The three claim tiers, in the order cash arriving pays them.
WATERFALL = ("fees", "interest", "principal")

#: The five fields of one claim line: who owes it, which tier it sits in, the
#: line's own name (the due date it was billed against), the day it was billed
#: and the cents it charges.
CLAIM_KEYS = ("loan", "tier", "line", "billed_on", "amount_cents")

#: The nine fields of one ledger row, in order.
LEDGER_KEYS = ("loan", "index", "paid_on", "cash_cents", "fees_cents",
               "interest_cents", "principal_cents", "carried_cents",
               "open_cents")

#: The three remedies, in the order the desk settles for: a loan takes the
#: first whose flags all pass. Every remedy runs one probation long enough to
#: cure under the policy's own rule.
REMEDY_KEYS = ("remedy", "probation_months", "flags")

REMEDIES = (
    {"remedy": "restructure", "probation_months": rules.CURE_MONTHS,
     "flags": ("arrears-material", "no-forbearance-standing", "not-defaulted",
               "not-written-off", "instalments-remaining")},
    {"remedy": "term-extension", "probation_months": rules.CURE_MONTHS,
     "flags": ("no-forbearance-standing", "not-defaulted", "not-written-off",
               "instalments-remaining")},
    {"remedy": "capitalisation", "probation_months": rules.CURE_MONTHS,
     "flags": ("arrears-material", "no-forbearance-standing",
               "instalments-remaining")},
)

#: The flags a remedy may demand, in the order the rules name them.
FLAG_NAMES = ("arrears-material", "no-forbearance-standing", "not-defaulted",
              "not-written-off", "instalments-remaining")

#: The six fields of one forbearance grant, in order.
GRANT_KEYS = ("loan", "granted_on", "remedy", "flags", "probation_until",
              "detail_cents")

#: The eleven fields of one workout record, in order.
SALE_KEYS = ("loan", "borrower", "defaulted_on", "sale_date",
             "gross_proceeds_cents", "costs", "net_proceeds_cents",
             "exposure_at_default_cents", "settlement_cents",
             "deficiency_cents", "cover_bp")

#: The three fields of one cost line of a sale, in order.
SALE_COST_KEYS = ("date", "concept", "amount_cents")

#: The gap that distinguishes a re-default from a fresh default: a signalled
#: default that lands at or before this many months after the same loan's cure
#: is the borrower re-defaulting, not the bank's first sight of them.
REDEFAULT_MONTHS = 6

#: The smallest cohort the desk will publish a cure rate for. A rate over one
#: or two loans is an anecdote, and the desk refuses to publish anecdotes.
MIN_COHORT = 2

#: An instalment is in grace for its first month of lateness; its recoverable
#: interest is billed once, at this many months, and charges this many months.
INTEREST_GRACE_MONTHS = 2

#: The workout desk sells a defaulted collateralised loan this many months after
#: the bank signalled the default, where the credit records carry no sale of
#: their own.
SALE_MONTHS = 5

#: The agent fee, in basis points of a sale's gross proceeds, on the sales the
#: desk compiled its own records for.
AGENT_FEE_BP = 400

#: The agent fee's name, as the desk books it line by line.
AGENT_FEE_CONCEPT = "agent-fee"

#: The first day the operation walks: the month before the book's first
#: reporting date, so no event of the book's is missed.
WINDOW_START = "2031-01-01"

#: The last day the operation walks (`book.LAST_REPORTING_DATE`).
WINDOW_END = "2033-12-31"

STRATEGY_ERROR = "collections: "


class StrategyError(ValueError):
    """The refusal the operation raises: something the strategy cannot accept.

    It names the offender — the loan it holds nothing on, the action outside
    `ACTIONS`, the remedy outside `REMEDIES`, the date outside the window, or
    the waterfall that does not balance — because an operation this stiff must
    say what it was asked for rather than answer a row nobody can defend.
    """


# --- contract helpers ---------------------------------------------------------


def _whole(value, what):
    """A whole number, and a `bool` is not one here."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise StrategyError(STRATEGY_ERROR + ("%s is a %s, not a whole number"
                                              % (what, type(value).__name__)))
    return value


def _text(value, what):
    """A text, or the refusal naming what arrived."""
    if not isinstance(value, str):
        raise StrategyError(STRATEGY_ERROR + ("%s is a %s, not a text"
                                              % (what, type(value).__name__)))
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


def _days(start, end):
    """Every date from `start` to `end` inclusive, in order."""
    days = []
    day = start
    while day <= end:
        days.append(day)
        day = _next_day(day)
    return days


def _period_bp(rate_bp):
    """The loan's own rate for one period, on the basis the book keeps records on."""
    return rules.period_rate(rate_bp, rules.DEFAULT_BASIS)


def _resolve(loan):
    """One loan's id, from a record or an id, refusal-shaped for callers."""
    if isinstance(loan, dict):
        name = loan.get("loan", loan.get("id"))
    else:
        name = loan
    if not isinstance(name, str):
        raise StrategyError(STRATEGY_ERROR + ("a loan arrives as %r, which is "
                                              "neither a record nor an id"
                                              % (loan,)))
    return name


def _loan(index, loan_id):
    """A loan the book holds, or a refusal naming what was asked for."""
    if loan_id not in index:
        raise StrategyError(STRATEGY_ERROR + ("the operation holds nothing on loan %r"
                                              % (loan_id,)))
    return index[loan_id]


#: The walk's grid, and the day of it every date asks for by index.
_DAY_LIST = tuple(_days(WINDOW_START, WINDOW_END))
_DAY_INDEX = {day: index for index, day in enumerate(_DAY_LIST)}


# --- the bank's own delinquency arithmetic ------------------------------------
#
# The same rules book.py keeps its statuses on, re-derived here once per loan
# so the desk's own walks never read the book's answer key. One chronological
# pass per loan lays the whole day-grid down: the arrears, the drawn exposure,
# the reference due and the materiality-tested days past due.


class _LoanLens:
    """One loan's facts on a per-day grid the operation's walks read."""

    def __init__(self, book, loan_record):
        self.loan_id = loan_record["loan"]
        self.record = loan_record
        self.period_bp = _period_bp(loan_record["rate_bp"])
        self.dues = tuple((flow["date"], flow["amount_cents"])
                          for flow in book.schedule(loan_record)["flows"])
        self.payments = tuple(book.payments(loan_record))
        self.events = tuple(book.events(loan_record))
        self.recoveries = tuple(book.recoveries(loan_record))
        self.defaults = tuple(row for row in book.defaults()
                              if row["loan"] == self.loan_id)
        self.write_off = None
        for event in self.events:
            if event["kind"] == "write-off":
                self.write_off = event["date"]
        self.cures = tuple(sorted(row["cured_on"] for row in self.defaults
                                  if row["cured_on"]))
        self._arr = [0] * len(_DAY_LIST)
        self._drawn = [0] * len(_DAY_LIST)
        self._dpd = [0] * len(_DAY_LIST)
        self._ref = 0
        self._lay()

    def _lay(self):
        """One pass over the window: running totals, then the grid."""
        owed = 0
        covered = 0
        instalment_paid = 0
        prepaid = 0
        first = _DAY_LIST[0]
        owe_at = {flow[0]: flow[1] for flow in self.dues}
        pay_at = {}
        for row in self.payments:
            pay_at.setdefault(row["paid_on"], []).append(row)
        cov = {}
        grid = self._arr
        # seed the walk with everything that landed before the window
        for flow in self.dues:
            if flow[0] <= first:
                owed = owed + flow[1]
        for row in self.payments:
            if row["paid_on"] <= first:
                if row["kind"] == "instalment":
                    instalment_paid = instalment_paid + row["amount_cents"]
                    cov[row["due"]] = cov.get(row["due"], 0) + row["amount_cents"]
                    if row["due"] <= first:
                        covered = covered + row["amount_cents"]
                elif row["kind"] == "prepayment":
                    prepaid = prepaid + row["amount_cents"]
        for index, day in enumerate(_DAY_LIST):
            if day != first:
                owed = owed + owe_at.get(day, 0)
            for row in pay_at.get(day, ()):
                if row["kind"] == "instalment":
                    instalment_paid = instalment_paid + row["amount_cents"]
                    cov[row["due"]] = cov.get(row["due"], 0) + row["amount_cents"]
                    covered = covered + row["amount_cents"]
                elif row["kind"] == "prepayment":
                    prepaid = prepaid + row["amount_cents"]
            arrears = owed - covered
            if arrears < 0:
                arrears = 0
            drawn = instalment_paid - prepaid
            if drawn < 0:
                drawn = 0
            limit = len(self.dues)
            while self._ref < limit and self.dues[self._ref][0] <= day \
                    and cov.get(self.dues[self._ref][0], 0) \
                    >= self.dues[self._ref][1]:
                self._ref = self._ref + 1
            if self._ref < limit and self.dues[self._ref][0] <= day:
                due_day = self.dues[self._ref][0]
            else:
                due_day = None
            if due_day is not None and arrears >= rules.MATERIALITY_ABSOLUTE_CENTS \
                    and arrears * rules.DISCOUNT_SCALE \
                    >= rules.MATERIALITY_RELATIVE_BP * drawn:
                dpd = dates.days_between(due_day, day)
            else:
                dpd = 0
            grid[index] = arrears
            self._drawn[index] = drawn
            self._dpd[index] = dpd

    def dpd(self, day):
        """The days past due at `day`, zero unless the arrears are material."""
        return self._dpd[_DAY_INDEX[day]]

    def arrears(self, day):
        """The covered-arrears view at `day`: owed less covered, floored at 0."""
        return self._arr[_DAY_INDEX[day]]

    def drawn(self, day):
        """What the borrower has actually drawn at `day`: instalments due and made,
        less the amounts it pre-paid."""
        return self._drawn[_DAY_INDEX[day]]

    def flags_at(self, day):
        """The pre-existing UTP flag kinds standing at `day`.

        A kind stands from its event until one of the book's own valid cures
        (a default the walk cleared) lands after it; the forbearance the desk
        is booking *on* `day` itself does not stand — the history is asked as
        it stands on entry, and the event that event row would put on the
        record is not yet there when the desk asks.
        """
        standing = []
        for event in self.events:
            if event["kind"] not in rules.UTP_FLAGS or event["date"] >= day:
                continue
            cleared = False
            for cured in self.cures:
                if event["date"] < cured <= day:
                    cleared = True
            if not cleared:
                standing.append(event["kind"])
        return standing

    def forborne_at(self, day):
        """Whether a forbearance's probation stands at `day`: granted on or
        before `day`, for the length the remedies carry, from its grant."""
        for event in self.events:
            if event["kind"] == "forbearance" and event["date"] <= day:
                until = dates.add_months(event["date"], rules.CURE_MONTHS)
                if day < until:
                    return True
        return False

    def outstanding(self, day):
        """The loan's outstanding principal at `day`, on the book's own rule.

        The contractual principal less the *principal portions* of the
        instalments actually paid by then — a period's interest is truncated on
        the balance before the payment and the principal portion is what the
        payment left over — less prepayments, floored at zero. This walk is the
        one `book.py` keeps its own records with; the desk never rounds it a
        different way.
        """
        balance = self.record["principal_cents"]
        for due, _amount in self.dues:
            if due > day:
                break
            interest = balance * self.period_bp // rules.DISCOUNT_SCALE
            paid = 0
            for row in self.payments:
                if row["kind"] == "instalment" and row["due"] == due \
                        and row["paid_on"] <= day:
                    paid = paid + row["amount_cents"]
            portion = paid - interest
            if portion > 0:
                balance = balance - (balance if portion > balance else portion)
        prepaid = 0
        for row in self.payments:
            if row["kind"] == "prepayment" and row["paid_on"] <= day:
                prepaid = prepaid + row["amount_cents"]
        return balance - prepaid if balance >= prepaid else 0


# --- generation: the tables the operation holds --------------------------------


def _pyramid_rows(book):
    """The action log the pyramid generates, walked day by day per loan.

    A step fires the first day the loan's `dpd` reaches its trigger with the
    step's condition still met, all three on one day when the `dpd` jumps past
    sixty. A referral leaves the pyramid for good; the write-off ends the walk.
    """
    rows = []
    for loan_record in book.loans():
        lens = _LoanLens(book, loan_record)
        letter = None
        call = None
        for day in _DAY_LIST:
            if lens.write_off is not None and day >= lens.write_off:
                break
            if lens.cures and day in lens.cures:
                letter = None
                call = None
            dpd = lens.dpd(day)
            if dpd == 0:
                letter = None
                call = None
                continue
            if lens.forborne_at(day):
                continue
            if dpd >= PYRAMID[0]["trigger_day"] and letter is None:
                rows.append({"loan": lens.loan_id, "date": day,
                             "action": PYRAMID[0]["action"],
                             "outcome": "dpd-%d" % (dpd,)})
                letter = day
            if dpd >= PYRAMID[1]["trigger_day"] and letter is not None \
                    and call is None:
                rows.append({"loan": lens.loan_id, "date": day,
                             "action": PYRAMID[1]["action"],
                             "outcome": "dpd-%d" % (dpd,)})
                call = day
            if dpd >= PYRAMID[2]["trigger_day"] and call is not None:
                rows.append({"loan": lens.loan_id, "date": day,
                             "action": PYRAMID[2]["action"],
                             "outcome": "dpd-%d" % (dpd,)})
                break
    rows.sort(key=lambda row: (row["loan"], row["date"]))
    return tuple(rows)


def _ledger_and_claims(book):
    """The claims the desk bills and the ledger the waterfall writes, per loan.

    One walk per loan, over the book's own payment rows in the book's own
    order. Principal lines bill at their due; interest lines at
    `add_months(due, INTEREST_GRACE_MONTHS)` where the instalment is still
    short there; fee lines at the fee row's `paid_on`. Every claim line's
    applied amount is tracked as the walk pays it, so the ledger row's
    `open_cents` is the total still owing after that payment's split.
    """
    claims = []
    ledger = []
    for loan_record in book.loans():
        lens = _LoanLens(book, loan_record)
        loan_id = lens.loan_id
        lines = []
        billed_principal = {}
        billed_interest = {}
        fee_rows = [row for row in lens.payments if row["kind"] == "fee"]
        fee_at = 0
        for index, row in enumerate(lens.payments, 1):
            paid_on = row["paid_on"]
            for due, amount in lens.dues:
                if due <= paid_on and due not in billed_principal:
                    billed_principal[due] = True
                    lines.append({"loan": loan_id, "tier": "principal",
                                  "line": due, "billed_on": due,
                                  "amount_cents": amount,
                                  "applied_cents": 0})
            for due, amount in lens.dues:
                if due in billed_interest:
                    continue
                billing = dates.add_months(due, INTEREST_GRACE_MONTHS)
                if billing > paid_on:
                    continue
                paid = 0
                for pay in lens.payments:
                    if pay["kind"] == "instalment" and pay["due"] == due \
                            and pay["paid_on"] <= billing:
                        paid = paid + pay["amount_cents"]
                if paid < amount:
                    billed_interest[due] = True
                    lines.append({"loan": loan_id, "tier": "interest",
                                  "line": due, "billed_on": billing,
                                  "amount_cents": amount * lens.period_bp
                                  * INTEREST_GRACE_MONTHS
                                  // rules.DISCOUNT_SCALE,
                                  "applied_cents": 0})
            while fee_at < len(fee_rows) \
                    and fee_rows[fee_at]["paid_on"] <= paid_on:
                fee_row = fee_rows[fee_at]
                lines.append({"loan": loan_id, "tier": "fees",
                              "line": fee_row["due"],
                              "billed_on": fee_row["paid_on"],
                              "amount_cents": fee_row["amount_cents"],
                              "applied_cents": 0})
                fee_at = fee_at + 1
            cash = row["amount_cents"]
            fees_cents = interest_cents = principal_cents = 0
            route = {"fee": ("fees",), "prepayment": ("principal",),
                     "instalment": ("interest", "principal")}[row["kind"]]
            for tier in route:
                for line in lines:
                    if line["tier"] != tier or cash <= 0:
                        continue
                    owed = line["amount_cents"] - line["applied_cents"]
                    if owed <= 0:
                        continue
                    applied = owed if owed <= cash else cash
                    line["applied_cents"] = line["applied_cents"] + applied
                    cash = cash - applied
                    if tier == "fees":
                        fees_cents = fees_cents + applied
                    elif tier == "interest":
                        interest_cents = interest_cents + applied
                    else:
                        principal_cents = principal_cents + applied
            carried = cash
            open_cents = 0
            for line in lines:
                if line["billed_on"] <= paid_on:
                    open_cents = open_cents + line["amount_cents"] \
                        - line["applied_cents"]
            ledger.append({"loan": loan_id, "index": index, "paid_on": paid_on,
                           "cash_cents": row["amount_cents"],
                           "fees_cents": fees_cents,
                           "interest_cents": interest_cents,
                           "principal_cents": principal_cents,
                           "carried_cents": carried,
                           "open_cents": open_cents})
        for line in lines:
            claims.append({key: line[key] for key in CLAIM_KEYS})
    claims.sort(key=lambda line: (line["loan"], line["billed_on"],
                                  line["tier"], line["line"]))
    return tuple(claims), tuple(ledger)


def _flag_states(lens, at):
    """The flags one remedy's eligibility answers at `at`, per the pinned rules."""
    flags = {}
    arrears = lens.arrears(at)
    drawn = lens.drawn(at)
    flags["arrears-material"] = (
        arrears >= rules.MATERIALITY_ABSOLUTE_CENTS
        and arrears * rules.DISCOUNT_SCALE
        >= rules.MATERIALITY_RELATIVE_BP * drawn)
    standing = []
    for event in lens.events:
        if event["kind"] == "forbearance" and event["date"] < at:
            standing.append(event)
    flags["no-forbearance-standing"] = not standing
    defaulted_earlier = any(row["signalled_on"] < at
                            for row in lens.defaults)
    flags["not-defaulted"] = (not defaulted_earlier
                              and lens.dpd(at) < rules.DEFAULT_DAYS_PAST_DUE
                              and not lens.flags_at(at))
    flags["not-written-off"] = lens.write_off is None or lens.write_off > at
    flags["instalments-remaining"] = any(due > at for due, _amount in lens.dues)
    return flags


def _grants(book):
    """The forbearance grants the bank actually made, one per remedy event.

    For each `forbearance` event row the book records, the desk asks which
    remedy the loan's own history made eligible on the event's date — the
    flags as they stand on entry, the event row itself never standing against
    itself — and grants the **first** remedy in `REMEDIES` order whose flags
    all pass. A grant no remedy's flags book is refused by name, which is the
    desk's own honesty; the credit walk never books one that way.
    """
    grants = []
    for loan_record in book.loans():
        lens = _LoanLens(book, loan_record)
        for event in lens.events:
            if event["kind"] != "forbearance":
                continue
            at = event["date"]
            flags = _flag_states(lens, at)
            granted = None
            for remedy in REMEDIES:
                if all(flags[name] for name in remedy["flags"]):
                    granted = remedy
                    break
            if granted is None:
                raise StrategyError(STRATEGY_ERROR + (
                    "loan %s's forbearance of %s makes no remedy eligible"
                    % (lens.loan_id, at)))
            grants.append({"loan": lens.loan_id, "granted_on": at,
                           "remedy": granted["remedy"],
                           "flags": granted["flags"],
                           "probation_until": dates.add_months(
                               at, granted["probation_months"]),
                           "detail_cents": event["detail_cents"]})
    grants.sort(key=lambda row: (row["loan"], row["granted_on"]))
    return tuple(grants)


def _sale(lens):
    """One workout record, or `None` where the desk never sold."""
    if lens.record["collateral_kind"] == "none" or not lens.defaults:
        return None
    defaulted = lens.defaults[0]["signalled_on"]
    collateral_rows = [row for row in lens.recoveries
                       if row["source"] == "collateral"]
    if collateral_rows:
        sale_date = collateral_rows[0]["date"]
        gross = collateral_rows[0]["amount_cents"]
        costs = [{"date": row["date"], "concept": AGENT_FEE_CONCEPT,
                  "amount_cents": -(row["amount_cents"])}
                 for row in lens.recoveries if row["source"] == "costs"]
    else:
        sale_date = dates.add_months(defaulted, SALE_MONTHS)
        gross = lens.record["collateral_cents"]
        costs = [{"date": sale_date, "concept": AGENT_FEE_CONCEPT,
                  "amount_cents": gross * AGENT_FEE_BP // rules.DISCOUNT_SCALE}]
    net = gross - sum(row["amount_cents"] for row in costs)
    exposure = lens.outstanding(defaulted)
    settlement = 0
    for row in lens.recoveries:
        if row["source"] == "cash" and defaulted < row["date"] <= sale_date:
            settlement = settlement + row["amount_cents"]
    for row in lens.payments:
        if row["kind"] == "instalment" \
                and defaulted < row["paid_on"] <= sale_date:
            settlement = settlement + row["amount_cents"]
    deficiency = exposure - settlement - net
    if deficiency < 0:
        deficiency = 0
    cover = net * rules.DISCOUNT_SCALE // exposure
    return {"loan": lens.loan_id, "borrower": lens.record["borrower"],
            "defaulted_on": defaulted, "sale_date": sale_date,
            "gross_proceeds_cents": gross, "costs": tuple(costs),
            "net_proceeds_cents": net, "exposure_at_default_cents": exposure,
            "settlement_cents": settlement, "deficiency_cents": deficiency,
            "cover_bp": cover}


def _sales(book):
    """The workout records: one per defaulted collateralised loan, loan order."""
    sales = []
    for loan_record in book.loans():
        lens = _LoanLens(book, loan_record)
        record = _sale(lens)
        if record is not None:
            sales.append({key: record[key] for key in SALE_KEYS})
    sales.sort(key=lambda row: row["loan"])
    return tuple(sales)


def _table(book):
    """Build and keep every table the operation holds, from the book once."""
    log = _pyramid_rows(book)
    claims, ledger = _ledger_and_claims(book)
    sales = _sales(book)
    grants = _grants(book)
    return log, claims, ledger, sales, grants


# --- the reference split: what the stages are held to -------------------------


def split_off(cash_cents, dues, waterfall):
    """The reference waterfall split: tiers in `waterfall` order, lines too.

    `dues` is a sequence of records with `tier` (one of `waterfall`'s), `line`
    (a name of the caller's choosing) and `amount_cents` (what the line owes);
    `cash_cents` is what arrived. The split pays the tiers in `waterfall`
    order, and within a tier the lines in the order given, each to the cent:
    a line takes `min(cash left, what it still owes)`. Every line still owing
    after the cash is exhausted keeps its remainder in `balance` — the
    remainder falls to the last line that still owes — and when no line still
    owes and cash is left, the leftover lands in `carried`, not on a line.
    The identity every split satisfies is `cash == sum(applied) + carried`, and
    it is refused by name when it does not balance or the shapes do not fit.
    """
    _whole(cash_cents, "the cash")
    if cash_cents < 0:
        raise StrategyError(STRATEGY_ERROR + ("a payment of %d cents is negative"
                                              % (cash_cents,)))
    if waterfall is None or tuple(waterfall) != WATERFALL:
        raise StrategyError(STRATEGY_ERROR + ("a waterfall %r must be %r"
                                              % (waterfall, WATERFALL)))
    rows = tuple(dues) if dues is not None else ()
    for due in rows:
        if not isinstance(due, dict):
            raise StrategyError(STRATEGY_ERROR + ("a claim arrives as %r"
                                                  % (due,)))
        tier = due.get("tier")
        if tier not in waterfall:
            raise StrategyError(STRATEGY_ERROR + ("the tier %r is not one of %r"
                                                  % (tier, tuple(waterfall))))
        amount = _whole(due.get("amount_cents"), "the claim's amount")
        if amount < 0:
            raise StrategyError(STRATEGY_ERROR + (
                "the claim %r owes a negative %d cents" % (due.get("line"), amount)))
        if not isinstance(due.get("line"), str):
            raise StrategyError(STRATEGY_ERROR + ("the claim %r carries no line"
                                                  % (due.get("tier"),)))
    split = []
    cash = cash_cents
    open_claims = [dict(row) for row in rows]
    for tier in waterfall:
        for row in open_claims:
            if row["tier"] != tier or cash <= 0:
                continue
            owed = row["amount_cents"]
            applied = owed if owed <= cash else cash
            split.append({"tier": tier, "line": row["line"],
                          "applied_cents": applied})
            cash = cash - applied
            row["amount_cents"] = row["amount_cents"] - applied
    balance = [{"tier": row["tier"], "line": row["line"],
                "deficit_cents": row["amount_cents"]}
               for row in open_claims if row["amount_cents"] > 0]
    applied_total = sum(row["applied_cents"] for row in split)
    if applied_total + cash != cash_cents:
        raise StrategyError(STRATEGY_ERROR + (
            "the split of %d cents does not balance: %d applied, %d carried"
            % (cash_cents, applied_total, cash)))
    return {"cash_cents": cash_cents, "applied": tuple(split),
            "balance": tuple(balance), "carried_cents": cash}


# --- the assembled operation ---------------------------------------------------

_BOOK = book_module.Book.build(7)

#: The loans the operation holds, by id — the accessor's index for refusals.
_LOANS = {record["loan"]: record for record in _BOOK.loans()}

(LOG, CLAIMS, LEDGER, SALES, GRANTS) = _table(_BOOK)


def log_of(loan):
    """The log rows of one loan, in date order — or the empty tuple when the
    pyramid never fired for it; refused by name when the operation holds
    nothing on the loan."""
    name = _resolve(loan)
    _loan(_LOANS, name)
    return tuple(row for row in LOG if row["loan"] == name)


def claims_of(loan):
    """The claim lines the desk billed on one loan, in billing order — or the
    empty tuple when it billed nothing; refused by name when the operation
    holds nothing on the loan."""
    name = _resolve(loan)
    _loan(_LOANS, name)
    return tuple(line for line in CLAIMS if line["loan"] == name)


def ledger_of(loan):
    """One loan's own ledger rows, in the order the book paid them — refused
    by name when the operation holds nothing on the loan."""
    name = _resolve(loan)
    _loan(_LOANS, name)
    return tuple(row for row in LEDGER if row["loan"] == name)


def grant_of(loan):
    """The forbearance grant the bank actually made on one loan, or `None` when
    the bank never granted one — refused by name when the operation holds
    nothing on the loan."""
    name = _resolve(loan)
    _loan(_LOANS, name)
    found = None
    for row in GRANTS:
        if row["loan"] == name:
            found = row
    return None if found is None else dict(found)
