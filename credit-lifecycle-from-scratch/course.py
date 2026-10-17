"""Credit Lifecycle From Scratch — a loan's whole life as numbers.

Ten graded stages over a provided book (`book.py`, `dates.py`, `rules.py`), the
way the rest of this repository teaches a mechanism: the world is data and holds
the ground truth, a stage is a file you write, a check is what happens to it, and
every number is an integer count of basis points or cents because accounting is a
fixed-point discipline.

What the course is about, in one line: *the arithmetic a bank runs over a loan's
life, and the labelling a supervisor would ask it to reproduce by hand.*

    the schedule and the rate that discounts it
    the delinquency bucket, the materiality threshold and the default
    the migration matrix, the term structure and the lifetime PD
    the recovery cash flows and the loss given default
    the drawn balance, the undrawn limit and the exposure at default
    the expected credit loss, its horizon and its scenarios
    the three stages and the significant increase in credit risk
    the provision roll-forward, line by line
    the reporting pack and the reconciliation that holds it
    the backtest, the model artifact and the journal of the delta

The house laws hold here (`.m1-dev/CONTRACT.md` §1): standard library only, no
`float` literal, no `math`, no `statistics`, no `decimal`, no `fractions`, no
`random`, no clock, no socket, no process — and no `/` between two ints. The book
is never written: a stage reads it and answers, and the bank's own records
(`schedule`, `status`, `rollforward`, `migrations`) are the answer key it has to
reproduce from the raw facts. Where a division happens, the contract pins the
rounding: truncation, the largest remainder, or the whole remainder to one column.
That is not pedantry — an expected credit loss is a product of three rates and an
exposure, and the arithmetic a reviewer recomputes by hand is exactly the
arithmetic a float would hide.

What the course does **not** do is fit a model or make a business decision. The
models arrive as versioned artifacts, the policy arrives as a rulebook
(`rules.py`, `POLICY_VERSION`), the scenarios arrive with their weights, and the
portfolio arrives with its history. What is left — and what a bank actually
spends its time on — is measuring, staging, provisioning, decomposing, reporting,
backtesting and attributing: ten stages, one surface each, and a check that says
in its own arithmetic whether the answer holds.

    python3 codecraft/cli.py run credit-lifecycle-from-scratch
"""

from codecraft.api import stage

TITLE = "Credit Lifecycle From Scratch"
DESCRIPTION = ("A loan's whole life as numbers, over a provided book and a provided "
               "policy: the contractual schedule and the effective interest rate "
               "found by integer bisection, days past due and the materiality "
               "threshold behind the new definition of default, a rating migration "
               "matrix rounded to basis points and the lifetime PD built from it, "
               "recovery cash flows discounted to the default date into an LGD, the "
               "drawn and undrawn balances and a credit conversion factor estimated "
               "from the bank's own defaults, the expected credit loss over the "
               "stage's own horizon and weighted over the scenarios, IFRS 9's three "
               "stages with the significant-increase-in-credit-risk test, the "
               "provision roll-forward decomposed line by line with its P&L and OCI "
               "split, the reporting pack with its coverage ratios, forbearance, "
               "vintage and migration matrices and the reconciliation that holds it, "
               "and the backtesting, validation and attribution of a model the "
               "course did not fit.")

LEVEL = "advanced"
ORDER = 31


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    S1_FLOW_KEYS = ("date", "amount_cents")

    S1_SCHEDULE_KEYS = ("loan", "flows", "principal_cents", "rate_bp", "term_months",
                        "first_due", "level_payment_cents")

    S1_EIR_KEYS = ("loan", "eir_bp", "pv_cents", "carrying_cents", "residual_cents",
                   "periods", "basis")

    S1_BASES = ("actual-365", "thirty-360")

    S1_MAX_EIR_BP = 10000

    S1_EIR_TOLERANCE_BP = 1

    S1_SYNTH_LOANS = (
        {"loan": "S1-31ST", "principal_cents": 250000, "rate_bp": 725, "term_months": 6,
         "first_due": "2031-01-31", "basis": "thirty-360"},
        {"loan": "S1-DRIFT", "principal_cents": 250000, "rate_bp": 725, "term_months": 6,
         "first_due": "2031-01-30", "basis": "actual-365"},
        {"loan": "S1-FEE", "principal_cents": 200000, "rate_bp": 900, "term_months": 4,
         "first_due": "2031-05-31", "basis": "actual-365"},
        {"loan": "S1-NOFEE", "principal_cents": 200000, "rate_bp": 900, "term_months": 4,
         "first_due": "2031-05-31", "basis": "actual-365"},
        {"loan": "S1-WALL", "principal_cents": 100000, "rate_bp": 500, "term_months": 12,
         "first_due": "2031-02-28", "basis": "actual-365"},
        {"loan": "S1-ONE", "principal_cents": 500000, "rate_bp": 1200, "term_months": 1,
         "first_due": "2031-07-31", "basis": "actual-365"},
        {"loan": "S1-THIRTY", "principal_cents": 900000, "rate_bp": 1400, "term_months": 9,
         "first_due": "2031-04-30", "basis": "thirty-360"},
        {"loan": "S1-NOBASIS", "principal_cents": 900000, "rate_bp": 1400,
         "term_months": 9, "first_due": "2031-04-30"},
    )

    S1_SYNTH_FEES = {"S1-FEE": 30000, "S1-WALL": 99999}

    S1_SYNTH_DATES = ("2031-01-31", "2031-02-28", "2031-03-31", "2031-04-30",
                      "2031-05-31", "2031-06-30")

    S1_SYNTH_DRIFT = ("2031-01-30", "2031-02-28", "2031-03-30", "2031-04-30",
                      "2031-05-30", "2031-06-30")

    S1_EDGE_LOANS = (
        {"loan": "S1-EXACT", "principal_cents": 51000, "rate_bp": 1200, "term_months": 12,
         "first_due": "2031-03-31", "basis": "actual-365"},
        {"loan": "S1-SHORT", "principal_cents": 40500, "rate_bp": 900, "term_months": 12,
         "first_due": "2031-06-30", "basis": "thirty-360"},
    )

    S1_EDGE_FEES = {}

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("course.py", "book.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _period(rates, rate_bp, basis):
        """The world's own rate for one period: the day count is never re-done here."""
        return rates.period_rate(rate_bp, basis)

    def _walk(principal_cents, period_bp, payment_cents, term_months):
        """An independent amortisation: interest on the opening balance, then payment."""
        balance = principal_cents
        for _ in range(term_months):
            if balance <= 0:
                return balance
            balance = balance + balance * period_bp // 10000 - payment_cents
        return balance

    def _pv(flows, period_bp):
        """An independent stepped present value: one factor per flow, truncated."""
        factor = 10000
        total = 0
        for flow in flows:
            factor = factor * 10000 // (10000 + period_bp)
            total = total + flow["amount_cents"] * factor // 10000
        return total

    def _pv_at(flows, rates, rate_bp, basis):
        """The present value of `flows` at a rate and a day count."""
        return _pv(flows, _period(rates, rate_bp, basis))

    def _smallest(lo, hi, pays):
        """The smallest integer in `lo..hi` the predicate answers true for."""
        assert pays(hi), "the search's own wall does not pay, so there is no answer"
        while lo < hi:
            middle = (lo + hi) // 2
            if pays(middle):
                hi = middle
            else:
                lo = middle + 1
        return lo

    def _smallest_period(flows, carrying, highest):
        """The smallest period rate, over `0..highest`, whose present value pays."""
        return _smallest(0, highest, lambda bp: _pv(flows, bp) <= carrying)

    def _fees(payments):
        """The fees a loan's own payment rows carry."""
        return sum(row["amount_cents"] for row in payments if row["kind"] == "fee")

    def _sum_flows(flows):
        """What the instalments add up to."""
        return sum(flow["amount_cents"] for flow in flows)

    def _edge_flows(principal_cents, period_bp, term_months):
        """The contract's own instalments from a principal, a period rate and a term.

        The smallest payment whose walk clears the loan, then every instalment at it
        except the last, which is the balance plus its own period's interest. Written
        here so the two edge fixtures below are proved to land on the search's edge by
        the check's own arithmetic rather than asserted from the stage.
        """
        payment = _smallest(
            0, 2 * principal_cents,
            lambda cents: _walk(principal_cents, period_bp, cents, term_months) <= 0)
        balance = principal_cents
        amounts = []
        for step in range(term_months):
            interest = balance * period_bp // 10000
            amount = payment if step < term_months - 1 else balance + interest
            amounts.append(amount)
            balance = balance + interest - amount
        return tuple(amounts), payment

    class _S1Synthetic:
        """A book of the synthetic loans, so every branch is reachable.

        It answers the three things a book is asked for here — a loan by its id, the
        loan's payment rows and its own refusal family — and records every ask, which
        is what makes it a proof that the stage asked for nothing else.
        """

        def __init__(self, book_module, loans, fees):
            self._error = book_module.BookError
            self._loans = tuple(loans)
            self._index = dict((loan["loan"], loan) for loan in self._loans)
            self._fees = dict(fees)
            self._asked = []

        def loans(self):
            """Every synthetic loan, in the order it was written."""
            return self._loans

        def loan(self, which):
            """One synthetic loan, or a refusal naming the id that arrived."""
            identify = which["loan"] if isinstance(which, dict) else which
            self._asked.append(("loan", identify))
            if identify not in self._index:
                raise self._error("the synthetic book holds no loan %r" % (identify,))
            return self._index[identify]

        def payments(self, which):
            """The loan's payment rows: one fee, where the fixture gives it one."""
            identify = which["loan"] if isinstance(which, dict) else which
            self._asked.append(("payments", identify))
            amount = self._fees.get(identify)
            if amount is None:
                return ()
            return ({"loan": identify, "due": "2031-01-31", "paid_on": "2031-01-31",
                     "amount_cents": amount, "kind": "fee"},)

        def asked(self):
            """Every ask the stage made of this book, in order."""
            return tuple(self._asked)

    def _s1_constants(s, dates, rates):
        """The three key tuples in order, and the policy's own numbers, echoed."""
        assert tuple(s.FLOW_KEYS) == S1_FLOW_KEYS, s.FLOW_KEYS
        assert tuple(s.SCHEDULE_KEYS) == S1_SCHEDULE_KEYS, s.SCHEDULE_KEYS
        assert tuple(s.EIR_KEYS) == S1_EIR_KEYS, s.EIR_KEYS
        assert tuple(s.BASES) == S1_BASES == tuple(dates.BASES), s.BASES
        assert s.MAX_EIR_BP == rates.MAX_EIR_BP == S1_MAX_EIR_BP, s.MAX_EIR_BP
        assert s.EIR_TOLERANCE_BP == rates.EIR_TOLERANCE_BP == S1_EIR_TOLERANCE_BP
        assert issubclass(s.ScheduleError, ValueError), s.ScheduleError
        assert s.ScheduleError is not ValueError, "the stage must refuse, not defer"
        assert rates.period_rate(725, "thirty-360") == 725 * 30 // 360
        assert rates.period_rate(725, "actual-365") == 725 * 30 // 365
        assert rates.period_rate(725, "thirty-360") != rates.period_rate(725, "actual-365"), (
            "the two day counts must not agree, or the stage's day count is invisible")

    def _s1_loan(s, b, dates, rates, loan):
        """One loan's schedule, against the contract's walk and the book's own record."""
        basis = loan["basis"]
        period_bp = _period(rates, loan["rate_bp"], basis)
        principal = loan["principal_cents"]
        term = loan["term_months"]
        record = s.schedule(b, loan)
        assert tuple(record.keys()) == s.SCHEDULE_KEYS, record
        assert record["loan"] == loan["loan"], record
        assert record["principal_cents"] == principal, record
        assert record["rate_bp"] == loan["rate_bp"], record
        assert record["term_months"] == term, record
        assert record["first_due"] == loan["first_due"], record
        flows = record["flows"]
        assert isinstance(flows, tuple), flows
        assert len(flows) == term, (loan["loan"], len(flows))
        level = record["level_payment_cents"]
        assert level == s.level_payment(principal, loan["rate_bp"], term, basis), record
        assert _walk(principal, period_bp, level, term) <= 0, (
            "loan %s's level payment does not clear it" % (loan["loan"],))
        assert _walk(principal, period_bp, level - 1, term) > 0, (
            "loan %s's level payment is not the smallest that clears it" % (loan["loan"],))
        balance = principal
        charged = 0
        paid = 0
        for step, flow in enumerate(flows):
            assert tuple(flow.keys()) == s.FLOW_KEYS, flow
            assert isinstance(flow["date"], str), flow
            assert isinstance(flow["amount_cents"], int), flow
            assert flow["date"] == dates.add_months(loan["first_due"], step), (
                "instalment %d of %s is dated %r, and the world's calendar says %r"
                % (step, loan["loan"], flow["date"],
                   dates.add_months(loan["first_due"], step)))
            interest = balance * period_bp // 10000
            if step < term - 1:
                assert flow["amount_cents"] == level, (loan["loan"], step, flow, level)
                assert balance > 0, (
                    "loan %s's balance cleared before its last instalment" % (loan["loan"],))
            else:
                assert flow["amount_cents"] == balance + interest, (flow, balance, interest)
            charged = charged + interest
            paid = paid + flow["amount_cents"]
            balance = balance + interest - flow["amount_cents"]
        assert balance == 0, (
            "loan %s's last instalment left %d cents on the balance" % (loan["loan"], balance))
        assert paid == principal + charged, (
            "loan %s's instalments add up to %d cents; the principal and the interest the "
            "walk charged come to %d" % (loan["loan"], paid, principal + charged))
        theirs = b.schedule(loan)
        if isinstance(theirs, dict):
            theirs = theirs.get("flows", theirs)
        assert tuple(theirs) == flows, (
            "loan %s: the stage's flows are %r and the book's own record is %r"
            % (loan["loan"], flows, theirs))
        return record

    def _s1_schedule(s, b, dates, rates):
        """Every loan the book holds, reproduced from the contract's own arithmetic."""
        records = []
        for loan in b.loans():
            records.append(_s1_loan(s, b, dates, rates, loan))
        return tuple(records)

    def _s1_effective_rate(s, b, rates):
        """Every loan's effective rate, against the search's own smallest answer."""
        for loan in b.loans():
            basis = loan["basis"]
            flows = s.schedule(b, loan)["flows"]
            fees = _fees(b.payments(loan))
            carrying = loan["principal_cents"] - fees
            at_wall = _pv_at(flows, rates, s.MAX_EIR_BP, basis)
            if at_wall > carrying:
                _refuses(s.ScheduleError, "loan %s against the search's wall" % (loan["loan"],),
                         lambda: s.effective_rate(b, loan), [loan["loan"]])
                continue
            record = s.effective_rate(b, loan)
            assert tuple(record.keys()) == s.EIR_KEYS, record
            assert record["loan"] == loan["loan"], record
            assert record["basis"] == basis, record
            assert record["periods"] == len(flows), record
            assert record["carrying_cents"] == carrying, record
            eir = record["eir_bp"]
            assert 0 <= eir < s.MAX_EIR_BP, (
                "loan %s answered with the wall (%r), which is not a rate" % (loan["loan"], eir))
            assert _pv_at(flows, rates, eir, basis) <= carrying, (
                "loan %s's rate of %d basis points pays more than the carrying amount"
                % (loan["loan"], eir))
            assert eir == 0 or _pv_at(flows, rates, eir - 1, basis) > carrying, (
                "loan %s's rate of %d basis points is not the smallest that pays"
                % (loan["loan"], eir))
            assert record["pv_cents"] == _pv_at(flows, rates, eir, basis), record
            assert record["residual_cents"] == carrying - record["pv_cents"], record
            assert record["residual_cents"] >= 0, record
            if eir > 0:
                assert record["residual_cents"] < (
                    _pv_at(flows, rates, eir - 1, basis) - record["pv_cents"]), (
                    "loan %s's residue is wider than a basis point's worth" % (loan["loan"],))
            assert _period(rates, eir, basis) == _smallest_period(
                flows, carrying, _period(rates, s.MAX_EIR_BP, basis)), (
                "loan %s's rate does not land on the smallest period rate that pays"
                % (loan["loan"],))
            if fees:
                assert _period(rates, eir, basis) > _period(rates, loan["rate_bp"], basis), (
                    "loan %s pays %d cents of fees and still discounts at its contract rate"
                    % (loan["loan"], fees))
            else:
                assert _period(rates, eir, basis) <= _period(rates, loan["rate_bp"], basis), (
                    "loan %s pays no fee and discounts above its contract period rate"
                    % (loan["loan"],))

    def _s1_synthetic(s, book_module, dates, rates):
        """The cases no book loan need have, on a book the check builds itself."""
        synthetic = _S1Synthetic(book_module, S1_SYNTH_LOANS, S1_SYNTH_FEES)
        records = {}
        for loan in synthetic.loans():
            if loan["loan"] == "S1-NOBASIS":
                continue
            records[loan["loan"]] = s.schedule(synthetic, loan)
        # a first due date on the 31st keeps to the month's last day, and one on the 30th
        # clamps once and drifts: the clamping rule is the world's, not a local one
        asserted = tuple(flow["date"] for flow in records["S1-31ST"]["flows"])
        assert asserted == S1_SYNTH_DATES, (
            "the instalments of a loan first due on the 31st are %r, and the world's own "
            "`add_months` says %r" % (asserted, S1_SYNTH_DATES))
        drifted = tuple(flow["date"] for flow in records["S1-DRIFT"]["flows"])
        assert drifted == S1_SYNTH_DRIFT, (
            "the instalments of a loan first due on the 30th are %r, and the world's own "
            "`add_months` says %r" % (drifted, S1_SYNTH_DRIFT))
        assert drifted != tuple(dates.month_end(date) for date in drifted), (
            "the stage's dates are month ends, so a local clamping rule answered for "
            "`dates.add_months`")
        # a single month is the principal plus that period's own interest
        one = records["S1-ONE"]
        assert len(one["flows"]) == 1 and one["flows"][0]["amount_cents"] == (
            500000 + 500000 * _period(rates, 1200, "actual-365") // 10000), one
        # the fees are netted off the carrying amount rather than ignored
        fee = records["S1-FEE"]
        answered = s.effective_rate(synthetic, "S1-FEE")
        assert answered["carrying_cents"] == 200000 - 30000, answered
        assert _pv_at(fee["flows"], rates, answered["eir_bp"], "actual-365") <= 170000, answered
        assert answered["eir_bp"] > s.effective_rate(synthetic, "S1-NOFEE")["eir_bp"], (
            "a loan's fee must raise the rate it discounts at")
        assert s.effective_rate(synthetic, "S1-NOFEE")["carrying_cents"] == 200000, (
            "a loan with no fees carries its principal")
        # a loan nothing can pay for is refused at the wall rather than answered
        _refuses(s.ScheduleError, "the loan the wall cannot pay for",
                 lambda: s.effective_rate(synthetic, "S1-WALL"), ["S1-WALL"])
        # the other day count is charged as the world charges it
        assert records["S1-THIRTY"]["level_payment_cents"] == s.level_payment(
            900000, 1400, 9, "thirty-360"), records["S1-THIRTY"]
        assert s.present_value(records["S1-THIRTY"]["flows"], 1400, "thirty-360") != \
            s.present_value(records["S1-THIRTY"]["flows"], 1400, "actual-365"), (
            "the two day counts answered the same present value for one loan")
        other = s.effective_rate(synthetic, "S1-THIRTY")
        assert other["basis"] == "thirty-360", (
            "a loan written on thirty-360 echoed %r as its day count" % (other["basis"],))
        assert other["carrying_cents"] == 900000, other
        assert _pv_at(records["S1-THIRTY"]["flows"], rates, other["eir_bp"],
                      "thirty-360") <= 900000, other
        # a loan with no day count at all is refused by name
        _refuses(s.ScheduleError, "a loan carrying no day count",
                 lambda: s.schedule(synthetic, "S1-NOBASIS"), ["S1-NOBASIS"])
        # an id is a loan, and the stage asked this book for nothing but loans and fees
        assert s.schedule(synthetic, "S1-THIRTY")["loan"] == "S1-THIRTY"
        for asked in synthetic.asked():
            assert asked[0] in ("loan", "payments"), (
                "the stage asked the book for %r, and a schedule is not the book's to give"
                % (asked,))
        return records

    def _s1_edge(s, book_module, dates, rates):
        """The search's inclusive edge, on two loans built to land on it exactly.

        Both sides of the edge are pinned: at the smallest rate that pays the present
        value must be allowed to *equal* the carrying amount (`S1-EXACT`), and one basis
        point below it the rate must be refused for being one cent short (`S1-SHORT`).
        A search comparing with `<` fails the first and answers one basis point high; one
        comparing with `<= carrying + 1` fails the second and answers one basis point low.
        """
        synthetic = _S1Synthetic(book_module, S1_EDGE_LOANS, S1_EDGE_FEES)
        for loan in synthetic.loans():
            name = loan["loan"]
            basis = loan["basis"]
            carrying = loan["principal_cents"]
            highest = _period(rates, s.MAX_EIR_BP, basis)
            amounts, level = _edge_flows(carrying, _period(rates, loan["rate_bp"], basis),
                                         loan["term_months"])
            flows = tuple({"amount_cents": amount} for amount in amounts)
            record = s.schedule(synthetic, loan)
            assert tuple(flow["amount_cents"] for flow in record["flows"]) == amounts, (
                "%s's instalments are not the contract's own arithmetic: %r against %r"
                % (name, tuple(flow["amount_cents"] for flow in record["flows"]), amounts))
            assert tuple(flow["date"] for flow in record["flows"]) == tuple(
                dates.add_months(loan["first_due"], step)
                for step in range(loan["term_months"])), (
                "%s's instalments are not one month apart from its first due date"
                % (name,))
            assert record["level_payment_cents"] == level, record
            edge = _smallest_period(flows, carrying, highest)
            assert 0 < edge < highest, (
                "%s's fixture no longer has an edge to test: the smallest rate that pays "
                "is %d of a possible %d" % (name, edge, highest))
            answer = s.effective_rate(synthetic, loan)
            assert answer["carrying_cents"] == carrying, answer
            assert _period(rates, answer["eir_bp"], basis) == edge, (
                "%s answered the period rate %d, and the smallest that pays is %d"
                % (name, _period(rates, answer["eir_bp"], basis), edge))
            assert answer["pv_cents"] == _pv(flows, edge), answer
            assert answer["residual_cents"] == carrying - _pv(flows, edge), answer
            assert _pv_at(flows, rates, answer["eir_bp"] - 1, basis) > carrying, (
                "%s answered a rate one basis point below the one that pays" % (name,))
            if name == "S1-EXACT":
                assert _pv(flows, edge) == carrying, (
                    "%s's fixture no longer pays the carrying amount exactly: %d against %d"
                    % (name, _pv(flows, edge), carrying))
            else:
                assert _pv(flows, edge - 1) == carrying + 1, (
                    "%s's fixture no longer leaves exactly one cent unrecouped a basis "
                    "point below: %d against %d" % (name, _pv(flows, edge - 1), carrying + 1))
        return synthetic

    def _s1_level_payment(s, rates):
        """The smallest payment, both sides of it, over both bases and every bound."""
        for basis in s.BASES:
            for principal, term in ((1000, 4), (123457, 36), (999999, 360)):
                zero = s.level_payment(principal, 0, term, basis)
                assert zero == (principal + term - 1) // term, (principal, term, zero)
                assert _walk(principal, 0, zero, term) <= 0, (principal, term, zero)
                assert _walk(principal, 0, zero - 1, term) > 0, (principal, term, zero)
            for rate in (1, 350, 725, 1900, s.MAX_EIR_BP):
                period_bp = _period(rates, rate, basis)
                for term in (1, 2, 13, 360):
                    principal = 765432
                    payment = s.level_payment(principal, rate, term, basis)
                    assert _walk(principal, period_bp, payment, term) <= 0, (
                        "the payment %d is not enough at %d basis points over %d months"
                        % (payment, rate, term))
                    assert _walk(principal, period_bp, payment - 1, term) > 0, (
                        "the payment %d is not the smallest at %d basis points over %d "
                        "months" % (payment, rate, term))
                    assert payment == _smallest(
                        0, 2 * principal,
                        lambda cents, p=principal, bp=period_bp, t=term:
                        _walk(p, bp, cents, t) <= 0), (rate, term, payment)
                # a single month is the principal plus that one period's interest
                assert s.level_payment(250000, rate, 1, basis) == (
                    250000 + 250000 * _period(rates, rate, basis) // 10000), (rate, basis)
            assert s.level_payment(0, 500, 12, basis) == 0, "a zero principal owes nothing"
            assert s.level_payment(1, s.MAX_EIR_BP, 1, basis) == (
                1 + 1 * _period(rates, s.MAX_EIR_BP, basis) // 10000)

    def _s1_present_value(s, b, rates):
        """The step and not the power: a zero rate, both bases, and a monotone fall."""
        flows = s.schedule(b, b.loans()[0])["flows"]
        for basis in s.BASES:
            assert s.present_value(flows, 0, basis) == _sum_flows(flows), (
                "a zero rate must discount nothing")
            assert s.present_value((), 900, basis) == 0, "no flows are worth nothing"
            previous = None
            for rate in range(0, s.MAX_EIR_BP + 1, 125):
                got = s.present_value(flows, rate, basis)
                assert got == _pv_at(flows, rates, rate, basis), (rate, basis, got)
                if previous is not None:
                    assert got <= previous, (
                        "the present value rose from %d to %d as the rate went up to %d "
                        "basis points" % (previous, got, rate))
                previous = got
            assert s.present_value(flows, s.MAX_EIR_BP, basis) < \
                s.present_value(flows, 0, basis), "the wall must discount something"
        assert s.present_value(flows, 725, "actual-365") != \
            s.present_value(flows, 725, "thirty-360"), (
            "the two day counts answered the same present value")

    def _s1_refusals(s, b, rates):
        """Every shape that cannot be a schedule, refused by name, asking nothing."""
        loan = b.loans()[0]
        flows = s.schedule(b, loan)["flows"]
        wall = str(s.MAX_EIR_BP + 1)
        wrong_flows = (
            ("a single flow where a sequence belongs", flows[0]),
            ("a flow that is not a record", ("2031-01-31", 100)),
            ("a flow with no amount", ({"date": "2031-01-31"},)),
            ("a flow with no date", ({"amount_cents": 100},)),
            ("a flow whose amount is not a count of cents",
             ({"date": "2031-01-31", "amount_cents": "100"},)),
            ("a flow whose date is not a date",
             ({"date": 20310131, "amount_cents": 100},)),
            ("a stream of flows that is a string", "2031-01-31"),
        )
        calls = [
            ("a loan id the book does not hold", s.ScheduleError,
             lambda: s.schedule(b, "S1-NOT-HELD"), ["S1-NOT-HELD"]),
            ("a loan record the book does not hold", s.ScheduleError,
             lambda: s.schedule(b, {"loan": "S1-NOT-HELD"}), ["S1-NOT-HELD"]),
            ("a loan record the book does not hold, under its other name", s.ScheduleError,
             lambda: s.schedule(b, {"id": "S1-NOT-HELD"}), ["S1-NOT-HELD"]),
            ("a record that names no loan at all", s.ScheduleError,
             lambda: s.schedule(b, {"principal_cents": 1}), ["loan"]),
            ("a schedule with the loan argument missing", s.ScheduleError,
             lambda: s.schedule(b, None), ["None"]),
            ("the effective rate of a loan the book does not hold", s.ScheduleError,
             lambda: s.effective_rate(b, "S1-NOT-HELD"), ["S1-NOT-HELD"]),
            ("a basis outside the world's two", s.ScheduleError,
             lambda: s.level_payment(100000, 500, 12, "monthly"), ["monthly"]),
            ("a basis outside the world's two, in a present value", s.ScheduleError,
             lambda: s.present_value(flows, 500, "30/360"), ["30/360"]),
            ("a term of no months", s.ScheduleError,
             lambda: s.level_payment(100000, 500, 0, "thirty-360"), ["0"]),
            ("a term of minus one month", s.ScheduleError,
             lambda: s.level_payment(100000, 500, -1, "thirty-360"), ["-1"]),
            ("a term that is not a count of months", s.ScheduleError,
             lambda: s.level_payment(100000, 500, "12", "thirty-360"), ["'12'"]),
            ("a negative rate", s.ScheduleError,
             lambda: s.level_payment(100000, -1, 12, "thirty-360"), ["-1"]),
            ("a rate above the wall", s.ScheduleError,
             lambda: s.level_payment(100000, s.MAX_EIR_BP + 1, 12, "thirty-360"), [wall]),
            ("a rate above the wall, in a present value", s.ScheduleError,
             lambda: s.present_value(flows, s.MAX_EIR_BP + 1, s.BASES[0]), [wall]),
            ("a rate that is not a count of basis points", s.ScheduleError,
             lambda: s.present_value(flows, "725", s.BASES[0]), ["'725'"]),
            ("a negative principal", s.ScheduleError,
             lambda: s.level_payment(-1, 500, 12, "thirty-360"), ["-1"]),
            ("a principal that is not a count of cents", s.ScheduleError,
             lambda: s.level_payment(100000.0, 500, 12, "thirty-360"), ["100000.0"]),
        ]
        for what, bad in wrong_flows:
            calls.append((what, s.ScheduleError,
                          lambda bad=bad: s.present_value(bad, 500, s.BASES[0]), []))
        before = b.stats()
        for what, refused, call, names in calls:
            _refuses(refused, what, call, names)
        assert b.stats() == before, (
            "a refused call touched the book's ledger: %r became %r" % (before, b.stats()))

    def _s1_ledger(s, b, dates, rates):
        """The stage recomputes the schedule and never reads the book's own answer key."""
        before = b.stats()
        assert isinstance(before, dict), before
        for key in ("schedules", "statuses", "migrations", "recoveries", "models"):
            assert key in before, "the book's ledger has no %r" % (key,)
        for loan in b.loans():
            s.schedule(b, loan)
            try:
                s.effective_rate(b, loan)
            except s.ScheduleError:
                continue
        after = b.stats()
        for key in ("schedules", "statuses", "migrations", "recoveries", "models"):
            assert after[key] == before[key], (
                "the stage asked the book for its own %s: %r became %r"
                % (key, before, after))
        assert after["lookups"] >= before["lookups"], (
            "the stage asked the book nothing at all: %r became %r" % (before, after))

    def _s1_workload(s, b, book_module, dates, rates):
        """One whole pass of the stage over the book and the check's own fixtures."""
        answers = []
        for loan in b.loans():
            record = s.schedule(b, loan)
            answers.append((record["loan"], record["level_payment_cents"],
                            tuple((flow["date"], flow["amount_cents"])
                                  for flow in record["flows"])))
            try:
                answers.append(s.effective_rate(b, loan))
            except s.ScheduleError as walled:
                answers.append(("wall", str(walled)))
            for basis in s.BASES:
                for rate in (0, 1, 725, s.MAX_EIR_BP):
                    answers.append(s.present_value(record["flows"], rate, basis))
                answers.append(s.level_payment(loan["principal_cents"], loan["rate_bp"],
                                               loan["term_months"], basis))
        synthetic = _S1Synthetic(book_module, S1_SYNTH_LOANS, S1_SYNTH_FEES)
        for loan in synthetic.loans():
            if loan["loan"] == "S1-NOBASIS":
                continue
            answers.append(s.schedule(synthetic, loan))
        answers.append(_s1_synthetic(s, book_module, dates, rates)["S1-THIRTY"])
        return tuple(answers)

    def _s1_twice(s, b, book_module, dates, rates):
        """Two runs of one workload, which a stage that reads a dict or a set would fail."""
        one = _s1_workload(s, b, book_module, dates, rates)
        two = _s1_workload(s, b, book_module, dates, rates)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    """Every assertion the contract's §4.1 makes about this stage."""
    import book
    import dates
    import rules
    import stage_01 as s
    b = book.Book.build(7)
    _s1_constants(s, dates, rules)
    _s1_schedule(s, b, dates, rules)
    _s1_effective_rate(s, b, rules)
    _s1_synthetic(s, book, dates, rules)
    _s1_edge(s, book, dates, rules)
    _s1_level_payment(s, rules)
    _s1_present_value(s, b, rules)
    _s1_refusals(s, b, rules)
    _s1_ledger(s, b, dates, rules)
    _s1_twice(s, b, book, dates, rules)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    S2_BUCKET_KEYS = ("loan", "date", "dpd", "bucket", "arrears_cents", "material",
                      "triggers")

    S2_DEFAULT_KEYS = ("loan", "signalled_on", "triggers", "cured_on", "probation_until")

    S2_BUCKETS = ("performing", "1-30", "31-60", "61-90", "default")

    S2_UTP_FLAGS = ("forbearance", "distressed-restructuring", "cross-default", "bankruptcy")

    S2_DAYS_PAST_DUE = "days-past-due"

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), os.environ.get("K1_REPO"),
                                start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                course = os.path.join(candidate, COURSE)
                if os.path.isfile(os.path.join(course, "book.py")):
                    return candidate
                if os.path.isfile(os.path.join(course, "course.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked against the
        message: an exception of the right family raised for the wrong reason is not the
        refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _key(loan):
        return loan.get("loan", loan) if isinstance(loan, dict) else loan

    def _own_picture(payments, flows, date):
        """The exposure, the reference due and the arrears the check recomputes itself.

        A payment of kind `instalment` covers the due it names, so the reference due is the
        first due those payments leave short; the arrears are what was owed by then less what
        was covered, floored at zero, exactly as the book has them.
        """
        covered = {}
        paid = 0
        prepaid = 0
        for payment in payments:
            if payment["paid_on"] > date:
                continue
            if payment["kind"] == "instalment":
                paid = paid + payment["amount_cents"]
                covered[payment["due"]] = covered.get(payment["due"], 0) \
                    + payment["amount_cents"]
            elif payment["kind"] == "prepayment":
                prepaid = prepaid + payment["amount_cents"]
        exposure = paid - prepaid
        if exposure < 0:
            exposure = 0
        owed = 0
        matched = 0
        oldest = None
        for flow in flows:
            if flow["date"] > date:
                break
            owed = owed + flow["amount_cents"]
            matched = matched + covered.get(flow["date"], 0)
            if oldest is None and covered.get(flow["date"], 0) < flow["amount_cents"]:
                oldest = flow["date"]
        arrears = owed - matched
        if arrears < 0:
            arrears = 0
        return exposure, oldest, arrears

    def _own_material(arrears, exposure, rules):
        """The policy's two-part test: both halves, never either one alone."""
        return (arrears >= rules.MATERIALITY_ABSOLUTE_CENTS
                and arrears * rules.DISCOUNT_SCALE
                >= exposure * rules.MATERIALITY_RELATIVE_BP)

    def _own_days(payments, flows, date, dates, rules):
        """The days the check recomputes: zero unless the arrears clear both halves."""
        exposure, oldest, arrears = _own_picture(payments, flows, date)
        if oldest is None or not _own_material(arrears, exposure, rules):
            return 0
        return dates.days_between(oldest, date)

    def _own_cures(events):
        return tuple(sorted(event["date"] for event in events if event["kind"] == "cure"))

    def _own_windows(rows, loan_id, cures, dates, rules):
        """The signalled defaults of one loan: `(signalled_on, probation_until, cured_on)`."""
        windows = []
        for row in rows:
            if row["loan"] != loan_id:
                continue
            probation_until = dates.add_months(row["signalled_on"], rules.CURE_MONTHS)
            cured_on = None
            for cured in cures:
                if cured >= probation_until:
                    cured_on = cured
                    break
            windows.append((row["signalled_on"], probation_until, cured_on))
        windows.sort()
        return tuple(windows)

    def _own_flags(events, windows, date):
        """The flags standing at `date`: raised by an event, cleared only by a valid cure."""
        cleared = None
        for _signalled_on, _probation_until, cured_on in windows:
            if cured_on is not None and cured_on <= date:
                if cleared is None or cured_on > cleared:
                    cleared = cured_on
        standing = set()
        for event in events:
            if event["date"] > date or event["kind"] not in S2_UTP_FLAGS:
                continue
            if cleared is None or event["date"] > cleared:
                standing.add(event["kind"])
        return standing

    def _own_named(days, flags, rules):
        """The trigger tuple the check builds: the backstop first, then `UTP_FLAGS` order."""
        named = []
        if days >= rules.DEFAULT_DAYS_PAST_DUE:
            named.append(S2_DAYS_PAST_DUE)
        for flag in S2_UTP_FLAGS:
            if flag in flags:
                named.append(flag)
        return tuple(named)

    def _own_standing(windows, date):
        """True while a signalled default the check knows of has no valid cure yet."""
        for signalled_on, _probation_until, cured_on in windows:
            if cured_on is None and signalled_on <= date:
                return True
        return False

    def _own_bucket(days, defaulted, rules):
        """`BUCKET_DAYS` walked in order, with a default's own flag forcing the last bucket."""
        if defaulted:
            return S2_BUCKETS[-1]
        for upper, name in zip(rules.BUCKET_DAYS, S2_BUCKETS):
            if days <= upper:
                return name
        return S2_BUCKETS[-1]

    _SYN_REPORT = ("2031-01-31", "2031-02-28", "2031-03-31", "2031-04-30",
                   "2031-05-31", "2031-06-30")

    _SYN_LOANS = ("syn-perform", "syn-days", "syn-rel", "syn-rel-1", "syn-abs",
                  "syn-abs-1", "syn-utp", "syn-cure", "syn-stream", "syn-days-utp",
                  "syn-stand", "syn-prepay", "syn-prepay-due")

    _SYN_FLOWS = {
        "syn-days": (("2031-01-31", 20000), ("2031-02-28", 20000), ("2031-03-31", 20000),
                     ("2031-04-30", 20000), ("2031-05-31", 20000), ("2031-06-30", 20000)),
        "syn-rel": (("2031-01-31", 2020000),),
        "syn-rel-1": (("2031-01-31", 2020000),),
        "syn-abs": (("2031-01-31", 30000),),
        "syn-abs-1": (("2031-01-31", 29999),),
        "syn-days-utp": (("2031-01-31", 20000), ("2031-02-28", 20000), ("2031-03-31", 20000),
                         ("2031-04-30", 20000), ("2031-05-31", 20000), ("2031-06-30", 20000)),
        "syn-stand": (("2031-01-31", 20000), ("2031-02-28", 20000), ("2031-03-31", 20000),
                      ("2031-04-30", 20000), ("2031-05-31", 20000)),
        "syn-prepay": (("2031-01-31", 2020001),),
        "syn-prepay-due": (("2031-01-31", 20000),),
    }

    _SYN_PAYMENTS = {
        "syn-rel": (("2031-01-31", "2031-01-31", 2000000, "instalment"),),
        "syn-rel-1": (("2031-01-31", "2031-01-31", 2000001, "instalment"),),
        "syn-abs": (("2031-01-31", "2031-01-31", 20000, "instalment"),),
        "syn-abs-1": (("2031-01-31", "2031-01-31", 20000, "instalment"),),
        "syn-stand": (("2031-01-31", "2031-06-20", 20000, "instalment"),
                      ("2031-02-28", "2031-06-20", 20000, "instalment"),
                      ("2031-03-31", "2031-06-20", 20000, "instalment"),
                      ("2031-04-30", "2031-06-20", 20000, "instalment")),
        "syn-prepay": (("2031-01-31", "2031-06-20", 2000001, "instalment"),
                       ("2031-01-31", "2031-06-20", 1, "prepayment")),
        "syn-prepay-due": (("2031-01-31", "2031-06-20", 20000, "prepayment"),),
    }

    _SYN_EVENTS = {
        "syn-utp": (("2031-01-15", "forbearance"), ("2031-02-20", "distressed-restructuring"),
                    ("2031-03-10", "cross-default"), ("2031-04-05", "bankruptcy"),
                    ("2031-05-01", "write-off")),
        "syn-cure": (("2031-01-15", "forbearance"), ("2031-02-10", "cure"),
                     ("2031-03-05", "bankruptcy"), ("2031-05-15", "cure")),
        "syn-stream": (("2031-01-15", "forbearance"), ("2031-04-30", "cure")),
        "syn-days-utp": (("2031-05-01", "bankruptcy"),),
    }

    _SYN_SIGNALLED = {
        "syn-utp": "2031-01-31",
        "syn-cure": "2031-01-31",
        "syn-stream": "2031-01-31",
        "syn-days-utp": "2031-05-31",
        "syn-days": "2031-05-31",
        "syn-stand": "2031-05-31",
    }

    class _FakeBook:
        """A book the check builds by hand, duck-typed to the rows the stage reads.

        Its `defaults()` rows are the check's own record of what was signalled, not the
        stage's arithmetic: the probation and the valid cure are what the stage has to
        compute. Its roster answers bare and called, the way the world's does.
        """

        def __init__(self, loans, payments, events, flows, defaults, report, error):
            self._loans = tuple(loans)
            self._payments = payments
            self._events = events
            self._flows = flows
            self._defaults = tuple(defaults)
            self.reporting_dates = tuple(report)
            self._error = error

        def loans(self):
            return self._loans

        def loan(self, ident):
            for held in self._loans:
                if held["loan"] == _key(ident):
                    return held
            raise self._error("the book does not hold the loan %r" % (_key(ident),))

        def payments(self, loan):
            return self._payments.get(_key(loan), ())

        def events(self, loan):
            return self._events.get(_key(loan), ())

        def schedule(self, loan):
            return {"flows": self._flows.get(_key(loan), ())}

        def defaults(self):
            return self._defaults

    def _synthetic(dates, rules, book):
        """The hand-built book, built from the fixtures above and nothing else."""
        loans = []
        for ident in _SYN_LOANS:
            loans.append({"loan": ident, "borrower": "syn", "segment": "consumer",
                          "grade_origination": "A", "principal_cents": 0, "rate_bp": 0,
                          "term_months": 6, "first_due": "2031-01-31",
                          "origination": "2031-01-01", "collateral_kind": "none",
                          "collateral_cents": 0, "undrawn_limit_cents": 0,
                          "measured_at": "2031-01-01"})
        payments = dict((ident, tuple({"loan": ident, "due": due, "paid_on": paid_on,
                                       "amount_cents": cents, "kind": kind}
                                      for due, paid_on, cents, kind in rows))
                        for ident, rows in _SYN_PAYMENTS.items())
        events = dict((ident, tuple({"loan": ident, "date": date, "kind": kind,
                                     "detail_cents": 0} for date, kind in rows))
                      for ident, rows in _SYN_EVENTS.items())
        flows = dict((ident, tuple({"date": date, "amount_cents": cents}
                                   for date, cents in rows))
                     for ident, rows in _SYN_FLOWS.items())
        defaults = []
        for ident in _SYN_LOANS:
            if ident not in _SYN_SIGNALLED:
                continue
            signalled_on = _SYN_SIGNALLED[ident]
            probation_until = dates.add_months(signalled_on, rules.CURE_MONTHS)
            cured_on = None
            for row in events.get(ident, ()):
                if row["kind"] != "cure" or row["date"] < probation_until:
                    continue
                if cured_on is None or row["date"] < cured_on:
                    cured_on = row["date"]
            defaults.append({"loan": ident, "signalled_on": signalled_on,
                             "triggers": (), "cured_on": cured_on,
                             "probation_until": probation_until})
        return _FakeBook(loans, payments, events, flows, defaults, _SYN_REPORT, book.BookError)

    def _s2_constants(s, rules):
        """The frozen tuples, in the policy's own order, and the rules agree with them."""
        assert tuple(s.BUCKET_KEYS) == S2_BUCKET_KEYS, (
            "a bucket record is its seven fields in order, and the stage declares %r"
            % (tuple(s.BUCKET_KEYS),))
        assert tuple(s.DEFAULT_KEYS) == S2_DEFAULT_KEYS, (
            "a signalled default is its five fields in order, and the stage declares %r"
            % (tuple(s.DEFAULT_KEYS),))
        assert tuple(s.BUCKETS) == S2_BUCKETS, (
            "the buckets are the policy's own five, and the stage declares %r"
            % (tuple(s.BUCKETS),))
        assert tuple(s.UTP_FLAGS) == S2_UTP_FLAGS, (
            "the flags are the policy's own four in the policy's order, and the stage "
            "declares %r" % (tuple(s.UTP_FLAGS),))
        assert tuple(rules.BUCKETS) == S2_BUCKETS, (
            "the rules module's buckets moved: %r" % (tuple(rules.BUCKETS),))
        assert tuple(rules.UTP_FLAGS) == S2_UTP_FLAGS, (
            "the rules module's flags moved: %r" % (tuple(rules.UTP_FLAGS),))

    def _s2_world(s, book, dates, rules):
        """Every loan at every reporting date, against the book's record and the check's own."""
        b = book.Book.build(7)
        report = tuple(b.reporting_dates)
        assert report, "the book holds no reporting dates"
        recorded = tuple(b.defaults())
        traps = 0
        spoken = 0
        exposures = 0
        for loan in b.loans():
            ident = loan["loan"]
            payments = tuple(b.payments(loan))
            flows = tuple(b.schedule(loan)["flows"])
            events = tuple(b.events(loan))
            windows = _own_windows(recorded, ident, _own_cures(events), dates, rules)
            for date in report:
                record = s.bucket(b, loan, date)
                status = b.status(loan, date)
                where = "%r at %s" % (ident, date)
                assert tuple(record) == S2_BUCKET_KEYS, (
                    "%s: a bucket record is its seven fields in order, and it was %r"
                    % (where, tuple(record)))
                assert record["loan"] == ident, (
                    "%s: a bucket record names its own loan, and it named %r"
                    % (where, record["loan"]))
                assert record["date"] == date, (
                    "%s: a bucket record echoes its date, and it echoed %r"
                    % (where, record["date"]))
                assert isinstance(record["dpd"], int) and record["dpd"] >= 0, (
                    "%s: the days are a count of days, and they were %r" % (where, record["dpd"]))
                assert record["material"] is True or record["material"] is False, (
                    "%s: `material` is a verdict, and it was %r" % (where, record["material"]))
                assert record["dpd"] == status["dpd"], (
                    "%s: the book records %r days past due and the stage answered %r"
                    % (where, status["dpd"], record["dpd"]))
                assert record["bucket"] == status["bucket"], (
                    "%s: the book records the bucket %r and the stage answered %r"
                    % (where, status["bucket"], record["bucket"]))
                assert ((record["bucket"] == S2_BUCKETS[-1])
                        == bool(status["default"])), (
                    "%s: the default bucket is the bucket of a loan the book calls defaulted, "
                    "and the two disagree: %r" % (where, record))
                exposure, oldest, arrears = _own_picture(payments, flows, date)
                assert record["arrears_cents"] == arrears, (
                    "%s: the arrears are %r and the stage said %r"
                    % (where, arrears, record["arrears_cents"]))
                assert record["material"] == _own_material(arrears, exposure, rules), (
                    "%s: the two-part test on %r arrears against %r exposure is %r, and the "
                    "stage answered %r" % (where, arrears, exposure,
                                           _own_material(arrears, exposure, rules),
                                           record["material"]))
                assert record["dpd"] == _own_days(payments, flows, date, dates, rules), (
                    "%s: the days recomputed from the book's own facts are %r and the stage "
                    "said %r" % (where, _own_days(payments, flows, date, dates, rules),
                                 record["dpd"]))
                named = _own_named(record["dpd"], _own_flags(events, windows, date), rules)
                assert record["triggers"] == named, (
                    "%s: the triggers recomputed are %r and the stage said %r"
                    % (where, named, record["triggers"]))
                defaulted = bool(named) or _own_standing(windows, date)
                assert record["bucket"] == _own_bucket(record["dpd"], defaulted, rules), (
                    "%s: the bucket recomputed is %r and the stage answered %r"
                    % (where, _own_bucket(record["dpd"], defaulted, rules), record["bucket"]))
                assert s.dpd(b, loan, date) == record["dpd"], (
                    "%s: `dpd` and `bucket` disagree about the days" % (where,))
                assert s.triggers(b, loan, date) == record["triggers"], (
                    "%s: `triggers` and `bucket` disagree about the triggers" % (where,))
                for trigger in record["triggers"]:
                    assert trigger == S2_DAYS_PAST_DUE or trigger in S2_UTP_FLAGS, (
                        "%s: a trigger is the backstop or a policy flag, and %r is neither"
                        % (where, trigger))
                if record["dpd"] >= rules.DEFAULT_DAYS_PAST_DUE:
                    assert record["bucket"] == S2_BUCKETS[-1], (
                        "%s: %r days past due is the backstop, so the bucket is `default`, "
                        "and the stage answered %r" % (where, record["dpd"], record["bucket"]))
                if not named and not defaulted:
                    assert record["bucket"] != S2_BUCKETS[-1], (
                        "%s: a loan with no trigger and no standing default is not in the "
                        "default bucket, and the stage put it there" % (where,))
                if record["material"]:
                    assert record["arrears_cents"] >= rules.MATERIALITY_ABSOLUTE_CENTS, (
                        "%s: material arrears are at least the absolute floor, and %r is not"
                        % (where, record["arrears_cents"]))
                if (record["bucket"] == S2_BUCKETS[-1]
                        and record["dpd"] < rules.DEFAULT_DAYS_PAST_DUE
                        and record["triggers"]):
                    spoken += 1
                if (oldest is not None and not record["material"]
                        and dates.days_between(oldest, date)
                        >= rules.DEFAULT_DAYS_PAST_DUE):
                    traps += 1
                if loan["undrawn_limit_cents"] == 0:
                    exposures += 1
                    assert exposure == status["ead_cents"], (
                        "%s: with no undrawn limit the exposure is the drawn balance %r, and "
                        "the book records %r" % (where, exposure, status["ead_cents"]))
        assert traps >= 1, (
            "the book holds no loan whose arrears are immaterial while the backstop has "
            "passed, so the threshold is not reachable")
        assert spoken >= 1, (
            "the book holds no loan in the default bucket at fewer than %r days with a "
            "trigger named, so a flag alone never speaks" % (rules.DEFAULT_DAYS_PAST_DUE,))
        assert exposures >= 1, (
            "the book holds no loan without an undrawn limit, so the exposure definition was "
            "never checked against the book's own")

    def _s2_boundaries(s, book, dates, rules):
        """A hand-built book: every boundary one cent, one day and one flag either side."""
        fake = _synthetic(dates, rules, book)
        ask = s.bucket

        clean = ask(fake, "syn-perform", "2031-06-30")
        assert clean["dpd"] == 0 and clean["arrears_cents"] == 0, (
            "a loan that owes nothing has no days and no arrears, and it answered %r"
            % (clean,))
        assert clean["bucket"] == "performing" and clean["material"] is False, (
            "a loan that owes nothing is performing and not material, and it answered %r"
            % (clean,))
        assert clean["triggers"] == (), (
            "a loan with no arrears and no event is not a default, and it answered %r"
            % (clean["triggers"],))

        for date, days, bucket, named in (
                ("2031-01-31", 0, "performing", ()),
                ("2031-03-02", 30, "1-30", ()),
                ("2031-03-03", 31, "31-60", ()),
                ("2031-04-01", 60, "31-60", ()),
                ("2031-04-02", 61, "61-90", ()),
                ("2031-04-30", 89, "61-90", ()),
                ("2031-05-01", 90, "default", (S2_DAYS_PAST_DUE,)),
                ("2031-05-02", 91, "default", (S2_DAYS_PAST_DUE,))):
            assert dates.days_between("2031-01-31", date) == days, (
                "the check's own calendar says %s is %r days after the due, not %r"
                % (date, dates.days_between("2031-01-31", date), days))
            record = ask(fake, "syn-days", date)
            assert record["dpd"] == days, (
                "the days at %s are %r, and the stage answered %r" % (date, days, record["dpd"]))
            assert record["bucket"] == bucket, (
                "%r days past due is the bucket %r, and the stage answered %r"
                % (days, bucket, record["bucket"]))
            assert record["triggers"] == named, (
                "%r days past due names the triggers %r, and the stage named %r"
                % (days, named, record["triggers"]))
            assert record["material"] is True, (
                "the arrears at %s clear both halves of the threshold, and the stage said %r"
                % (date, record["material"]))
            assert s.dpd(fake, "syn-days", date) == days, (
                "`dpd` answers %r at %s, not %r" % (s.dpd(fake, "syn-days", date), date, days))
        assert ask(fake, "syn-days", "2031-01-31")["arrears_cents"] == 20000, (
            "one instalment is uncovered at its own due, and the stage counted %r"
            % (ask(fake, "syn-days", "2031-01-31")["arrears_cents"],))

        exact = ask(fake, "syn-rel", "2031-01-31")
        assert exact["arrears_cents"] == 20000 and exact["material"] is True, (
            "arrears at exactly one per cent of the exposure are material, and the stage "
            "answered %r" % (exact,))
        under = ask(fake, "syn-rel-1", "2031-01-31")
        assert under["arrears_cents"] == 19999 and under["material"] is False, (
            "one cent under the relative half is not material, and the stage answered %r"
            % (under,))
        assert under["dpd"] == 0, (
            "an immaterial shortfall leaves the days at zero, and the stage counted %r"
            % (under["dpd"],))
        prepaid = ask(fake, "syn-prepay", "2031-06-30")
        assert prepaid["arrears_cents"] == 20000 and prepaid["material"] is True, (
            "the exposure is the instalments paid less what was prepaid, so arrears at "
            "exactly one per cent of the netted exposure are material, and the stage "
            "answered %r" % (prepaid,))
        assert prepaid["dpd"] == 150 and prepaid["triggers"] == (S2_DAYS_PAST_DUE,), (
            "a prepayment that does not move the exposure out of the relative half leaves "
            "150 days counted, and the stage answered %r" % (prepaid,))
        covered_by = ask(fake, "syn-prepay-due", "2031-06-30")
        assert covered_by["dpd"] == 150 and covered_by["arrears_cents"] == 20000, (
            "a prepayment booked against an uncovered due does not cover it, and the stage "
            "answered %r" % (covered_by,))

        floor = ask(fake, "syn-abs", "2031-01-31")
        assert floor["arrears_cents"] == 10000 and floor["material"] is True, (
            "arrears at exactly the absolute floor are material, and the stage answered %r"
            % (floor,))
        below = ask(fake, "syn-abs-1", "2031-01-31")
        assert below["arrears_cents"] == 9999 and below["material"] is False, (
            "one cent under the absolute floor is not material, and the stage answered %r"
            % (below,))
        assert below["dpd"] == 0, (
            "the absolute half alone does not count days, and the stage counted %r"
            % (below["dpd"],))

        for date, named in (("2031-01-31", ("forbearance",)),
                            ("2031-02-20", ("forbearance", "distressed-restructuring")),
                            ("2031-05-01", S2_UTP_FLAGS)):
            record = ask(fake, "syn-utp", date)
            assert record["dpd"] == 0 and record["bucket"] == "default", (
                "a flagged loan with no arrears is in the default bucket at zero days, and it "
                "answered %r" % (record,))
            assert record["triggers"] == named, (
                "the flags standing at %s are %r, and the stage named %r"
                % (date, named, record["triggers"]))
        assert ask(fake, "syn-utp", "2031-06-30")["triggers"] == S2_UTP_FLAGS, (
            "an event that is not a policy flag raises no trigger, and the stage named %r"
            % (ask(fake, "syn-utp", "2031-06-30")["triggers"],))

        for date, named in (("2031-02-20", ("forbearance",)),
                            ("2031-03-20", ("forbearance", "bankruptcy")),
                            ("2031-05-14", ("forbearance", "bankruptcy")),
                            ("2031-05-15", ())):
            assert ask(fake, "syn-cure", date)["triggers"] == named, (
                "the flags standing at %s are %r, and the stage named %r"
                % (date, named, ask(fake, "syn-cure", date)["triggers"]))
        for date, named in (("2031-04-29", ("forbearance",)),
                            ("2031-04-30", ())):
            record = ask(fake, "syn-stream", date)
            assert record["triggers"] == named, (
                "a cure at the probation cures and a cure the day before does not, so the "
                "flags at %s are %r, and the stage named %r" % (date, named, record["triggers"]))
            assert record["bucket"] == ("default" if named else "performing"), (
                "the bucket follows the triggers at %s, and the stage answered %r"
                % (date, record["bucket"]))

        both = ask(fake, "syn-days-utp", "2031-05-02")
        assert both["dpd"] == 91, "the days are 91, and the stage counted %r" % (both["dpd"],)
        assert both["triggers"] == (S2_DAYS_PAST_DUE, "bankruptcy"), (
            "the backstop is named before the flags, and the stage named %r"
            % (both["triggers"],))

        rows = tuple(s.defaults(fake))
        assert len(rows) == len(_SYN_SIGNALLED), (
            "the hand-built book signals %d defaults, and the stage answered %d"
            % (len(_SYN_SIGNALLED), len(rows)))
        by_loan = {}
        for row in rows:
            assert tuple(row) == S2_DEFAULT_KEYS, (
                "a signalled default is its five fields in order, and it was %r" % (tuple(row),))
            assert row["probation_until"] == dates.add_months(row["signalled_on"],
                                                              rules.CURE_MONTHS), (
                "%r's probation is three months after it was signalled, and the stage said %r"
                % (row["loan"], row["probation_until"]))
            by_loan[row["loan"]] = row
        assert sorted(by_loan) == sorted(_SYN_SIGNALLED), (
            "the defaults signalled are %r and the stage answered %r"
            % (sorted(_SYN_SIGNALLED), sorted(by_loan)))
        for ident in _SYN_SIGNALLED:
            events = tuple(fake.events(ident))
            payments = tuple(fake.payments(ident))
            flows = tuple(fake.schedule(ident)["flows"])
            windows = _own_windows(fake.defaults(), ident, _own_cures(events), dates, rules)
            first = None
            for date in _SYN_REPORT:
                if _own_named(_own_days(payments, flows, date, dates, rules),
                              _own_flags(events, windows, date), rules):
                    first = date
                    break
            assert by_loan[ident]["signalled_on"] == first, (
                "the hand-built book is world-shaped, so %r was signalled on %r, the first "
                "date a trigger holds, and the stage answered %r"
                % (ident, first, by_loan[ident]["signalled_on"]))
        for ident, cured_on in (("syn-utp", None), ("syn-cure", "2031-05-15"),
                                ("syn-stream", "2031-04-30"), ("syn-days-utp", None),
                                ("syn-days", None), ("syn-stand", None)):
            assert by_loan[ident]["cured_on"] == cured_on, (
                "%r cures on %r, and the stage said %r"
                % (ident, cured_on, by_loan[ident]["cured_on"]))
        assert by_loan["syn-cure"]["probation_until"] == "2031-04-30", (
            "a default signalled on a month end has its probation on a month end, and the "
            "stage said %r" % (by_loan["syn-cure"]["probation_until"],))
        for ident, named in (("syn-utp", ("forbearance",)), ("syn-cure", ("forbearance",)),
                             ("syn-stream", ("forbearance",)),
                             ("syn-days-utp", (S2_DAYS_PAST_DUE, "bankruptcy")),
                             ("syn-days", (S2_DAYS_PAST_DUE,)),
                             ("syn-stand", (S2_DAYS_PAST_DUE,))):
            assert by_loan[ident]["triggers"] == named, (
                "%r was signalled by %r, and the stage named %r"
                % (ident, named, by_loan[ident]["triggers"]))

        spoke = ask(fake, "syn-stand", "2031-05-31")
        assert spoke["dpd"] == 120 and spoke["triggers"] == (S2_DAYS_PAST_DUE,) \
                and spoke["bucket"] == "default", (
            "the backstop signals a default at 120 days on a loan whose later payments "
            "clear the oldest dues, and the stage answered %r" % (spoke,))
        stayed = ask(fake, "syn-stand", "2031-06-30")
        assert stayed["dpd"] == 30 and stayed["material"] is True, (
            "the later payments leave 30 days behind, and the stage answered %r" % (stayed,))
        assert stayed["triggers"] == () and stayed["bucket"] == "default", (
            "a signalled default that has not validly cured is still a default at 30 days "
            "with no flag standing, and the stage answered %r" % (stayed,))
        assert stayed["bucket"] != _own_bucket(stayed["dpd"], False, rules), (
            "the days alone put %r at 30 days, so only the standing default can put it in "
            "the default bucket" % (stayed["loan"],))

    def _s2_book_defaults(s, book, dates, rules):
        """The world's own defaults, the probation on top of them and the check's own rule."""
        b = book.Book.build(7)
        report = tuple(b.reporting_dates)
        recorded = tuple(b.defaults())
        rows = tuple(s.defaults(b))
        assert len(rows) == len(recorded), (
            "the book records %d signalled defaults and the stage answered %d"
            % (len(recorded), len(rows)))
        assert [(_key(row["loan"]), row["signalled_on"]) for row in rows] == \
            [(row["loan"], row["signalled_on"]) for row in recorded], (
                "the stage answers the defaults the book records, in the book's own order — "
                "loan order, then by date — and it answered %r"
                % ([(_key(row["loan"]), row["signalled_on"]) for row in rows],))
        cured = standing = early = 0
        for row in rows:
            assert tuple(row) == S2_DEFAULT_KEYS, (
                "a signalled default is its five fields in order, and it was %r" % (tuple(row),))
            loan = b.loan(row["loan"])
            payments = tuple(b.payments(loan))
            flows = tuple(b.schedule(loan)["flows"])
            events = tuple(b.events(loan))
            cures = _own_cures(events)
            probation_until = dates.add_months(row["signalled_on"], rules.CURE_MONTHS)
            assert row["probation_until"] == probation_until, (
                "%r's probation is %r and the stage said %r"
                % (row["loan"], probation_until, row["probation_until"]))
            wanted = None
            for event in cures:
                if event >= probation_until:
                    wanted = event
                    break
            assert row["cured_on"] == wanted, (
                "%r cured on %r and the stage said %r" % (row["loan"], wanted, row["cured_on"]))
            assert row["triggers"], (
                "%r was signalled a default by something, and the stage named nothing"
                % (row["loan"],))
            windows = _own_windows(recorded, row["loan"], cures, dates, rules)
            assert row["triggers"] == _own_named(
                _own_days(payments, flows, row["signalled_on"], dates, rules),
                _own_flags(events, windows, row["signalled_on"]), rules), (
                    "%r's triggers at %s are not the ones the check recomputes: %r"
                    % (row["loan"], row["signalled_on"], row["triggers"]))
            at_signalled = s.bucket(b, loan, row["signalled_on"])
            assert at_signalled["bucket"] == S2_BUCKETS[-1], (
                "%r is in the default bucket on the day it was signalled, and the stage "
                "answered %r" % (row["loan"], at_signalled["bucket"]))
            assert at_signalled["triggers"] == row["triggers"], (
                "%r's bucket and its default disagree about the triggers" % (row["loan"],))
            if row["cured_on"] is None:
                standing += 1
                assert b.status(loan, report[-1])["default"] is True, (
                    "%r has no valid cure, so the book calls it defaulted at the last "
                    "reporting date, and it does not" % (row["loan"],))
                assert s.bucket(b, loan, report[-1])["bucket"] == S2_BUCKETS[-1], (
                    "%r has no valid cure, so the stage keeps it in the default bucket at "
                    "the last reporting date" % (row["loan"],))
            else:
                cured += 1
            if any(event < probation_until for event in cures):
                early += 1
        assert cured >= 1, "the book signals no default that cures"
        assert standing >= 1, "the book signals no default still standing at the last date"
        assert early >= 1, (
            "the book signals no default with a cure before its probation, so the probation "
            "is not reachable")
        assert any(row["cured_on"] is None for row in rows), (
            "a default with no valid cure answers `cured_on` None")

    def _s2_refusals(s, book, dates, rules):
        """A loan the book does not hold is refused by name, and the book is left alone."""
        b = book.Book.build(7)
        report = tuple(b.reporting_dates)
        fake = _synthetic(dates, rules, book)
        _refuses(book.BookError, "a loan the hand-built book does not hold",
                 lambda: s.dpd(fake, "nowhere", "2031-06-30"), names=("nowhere",))
        _refuses(book.BookError, "a bucket for a loan the hand-built book does not hold",
                 lambda: s.bucket(fake, {"loan": "nowhere"}, "2031-06-30"),
                 names=("nowhere",))
        _refuses(book.BookError, "triggers for a loan the hand-built book does not hold",
                 lambda: s.triggers(fake, {"loan": "nowhere"}, "2031-06-30"),
                 names=("nowhere",))
        _refuses(book.BookError, "a loan that is neither a record nor an id",
                 lambda: s.dpd(fake, 7, "2031-06-30"), names=("7",))
        loan = b.loans()[0]
        before = dict(b.stats())
        s.bucket(b, loan, report[-1])
        assert dict(b.stats()) != before, "the stage asked the book nothing at all"
        before = dict(b.stats())
        _refuses(book.BookError, "a loan the book does not hold",
                 lambda: s.dpd(b, {"loan": "nope"}, report[-1]), names=("nope",))
        _refuses(book.BookError, "a bucket for a loan the book does not hold",
                 lambda: s.bucket(b, {"loan": "nope"}, report[-1]), names=("nope",))
        _refuses(book.BookError, "triggers for a loan the book does not hold",
                 lambda: s.triggers(b, {"loan": "nope"}, report[-1]), names=("nope",))
        _refuses(book.BookError, "a loan that is neither a record nor an id",
                 lambda: s.bucket(b, ("L-01",), report[-1]), names=("L-01",))
        assert dict(b.stats()) == before, (
            "a refused call asked the book for something: %r" % (b.stats(),))

    def _s2_workload(s, book, dates, rules):
        """One whole pass of the stage over the world's book and the hand-built one."""
        b = book.Book.build(7)
        report = tuple(b.reporting_dates)
        answers = []
        for loan in b.loans():
            for date in report:
                answers.append(s.bucket(b, loan, date))
            answers.append(s.dpd(b, loan, report[-1]))
            answers.append(s.triggers(b, loan, report[-1]))
        answers.append(s.defaults(b))
        fake = _synthetic(dates, rules, book)
        for ident in _SYN_LOANS:
            for date in _SYN_REPORT:
                answers.append(s.bucket(fake, ident, date))
            answers.append(s.dpd(fake, ident, _SYN_REPORT[-1]))
            answers.append(s.triggers(fake, ident, _SYN_REPORT[-1]))
        answers.append(s.defaults(fake))
        return tuple(answers)

    def _s2_twice(s, book, dates, rules):
        one = _s2_workload(s, book, dates, rules)
        two = _s2_workload(s, book, dates, rules)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of its "
            "inputs")

    import book
    import dates
    import rules
    import stage_02 as s
    _s2_constants(s, rules)
    _s2_world(s, book, dates, rules)
    _s2_boundaries(s, book, dates, rules)
    _s2_book_defaults(s, book, dates, rules)
    _s2_refusals(s, book, dates, rules)
    _s2_twice(s, book, dates, rules)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    S3_MATRIX_KEYS = ("from_date", "to_date", "grades", "counts", "rates_bp", "row_totals")

    S3_PD_KEYS = ("grade", "horizon_months", "marginal_bp", "cumulative_bp")

    S3_GRADES = ("A", "B", "C", "D", "E", "F", "default")

    S3_DEFAULT = "default"

    S3_SCALE = 10000

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "book.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s3_grade_at(portfolio, loan, date):
        """The grade the book recorded for one loan at one date: total, so it always answers."""
        return portfolio.grade(loan, date)

    def _s3_moves(portfolio, start, end):
        """The check's own counts: every loan of the book, grade at `start` against `end`.

        The bank's grade record is total over its reporting dates, so every loan is
        counted at every date and nothing is filtered out by origination or write-off.
        """
        counts = {}
        for loan in portfolio.loans:
            came = _s3_grade_at(portfolio, loan, start)
            went = _s3_grade_at(portfolio, loan, end)
            counts[(came, went)] = counts.get((came, went), 0) + 1
        return counts

    def _s3_matrix(counts, grades=S3_GRADES):
        """A `MATRIX_KEYS` record the check builds itself, so `rates` needs no book.

        The row totals are the check's own sum of the counts it wrote, and `rates_bp`
        starts empty — the caller fills it with what the stage answered, because what
        `rates` returns and what the matrix carries are two things that must agree.
        """
        totals = {}
        for grade in grades:
            totals[grade] = 0
        for came, went in counts:
            totals[came] = totals.get(came, 0) + counts[(came, went)]
        return {"from_date": "2031-01-31", "to_date": "2031-02-28", "grades": grades,
                "counts": dict(counts), "rates_bp": (), "row_totals": totals}

    def _s3_rows(grades, counts, totals):
        """The check's own row normalization: the `default` column is what the row left.

        Every other column is `count * 10000 // row_total` truncated, and the `default`
        column is `10000` less their sum, which is the same number the contract pins and
        a different expression of it: a row must sum to exactly 10000.
        """
        place = grades.index(S3_DEFAULT)
        rows = []
        for came in grades:
            row = [0] * len(grades)
            total = totals.get(came, 0)
            if total == 0:
                row[place] = S3_SCALE
                rows.append(tuple(row))
                continue
            for there, grade in enumerate(grades):
                if grade != S3_DEFAULT:
                    row[there] = counts.get((came, grade), 0) * S3_SCALE // total
            row[place] = S3_SCALE - sum(row)
            rows.append(tuple(row))
        return tuple(rows)

    def _s3_walk(grades, rows, grade, months):
        """The check's own survival walk, answering `(grade, step, marginal, cumulative)`.

        The mass of the loans still alive moves one month at a time and the products
        are truncated one by one. A step's marginal is the flow *into* `default` from
        that mass, and the mass that lands there is dropped rather than carried,
        because a defaulted loan is not at risk again: a matrix whose `default` row
        carries a cure out of the column would otherwise pump the cumulative past
        10000, which is the one thing §4.3 says a cumulative may never do. A walk that
        starts in `default` has already defaulted, so its cumulative is the scale and
        nothing more lands.
        """
        place = grades.index(S3_DEFAULT)
        start = grades.index(grade)
        alive = {}
        cumulative = 0
        if start == place:
            cumulative = S3_SCALE
        else:
            alive[start] = S3_SCALE
        answer = []
        for step in range(1, months + 1):
            moved = {}
            landed = 0
            for here_at in sorted(alive):
                here = alive[here_at]
                if here == 0:
                    continue
                row = rows[here_at]
                for there in range(len(grades)):
                    if there != place and row[there]:
                        moved[there] = moved.get(there, 0) + here * row[there] // S3_SCALE
                landed = landed + here * row[place] // S3_SCALE
            cumulative = cumulative + landed
            alive = moved
            answer.append((grade, step, landed, cumulative))
        return tuple(answer)

    def _s3_term_matrix(counts, grades=S3_GRADES):
        """A hand-built matrix whose `rates_bp` the check filled in itself."""
        matrix = _s3_matrix(counts, grades)
        matrix["rates_bp"] = _s3_rows(grades, matrix["counts"], matrix["row_totals"])
        return matrix

    def _s3_constants(s, rules):
        """The six fields of a matrix, the four of a term, and the scale itself."""
        assert tuple(s.MATRIX_KEYS) == S3_MATRIX_KEYS, (
            "MATRIX_KEYS is %r, and a migration matrix is the six fields %r"
            % (s.MATRIX_KEYS, S3_MATRIX_KEYS))
        assert tuple(s.PD_KEYS) == S3_PD_KEYS, (
            "PD_KEYS is %r, and one PD term is the four fields %r"
            % (s.PD_KEYS, S3_PD_KEYS))
        assert tuple(s.GRADES) == S3_GRADES, (
            "GRADES is %r, and the rating scale is %r" % (s.GRADES, S3_GRADES))
        assert tuple(s.GRADES) == tuple(rules.GRADES), (
            "GRADES is %r, and the policy's own scale is %r" % (s.GRADES, rules.GRADES))
        assert s.GRADES[-1] == S3_DEFAULT, (
            "GRADES ends with %r, and `default` is the absorbing state" % (s.GRADES[-1],))

    def _s3_windows(portfolio):
        """The windows worth counting: the first year, the last, and the whole history."""
        dates = tuple(portfolio.reporting_dates)
        assert len(dates) >= 2, (
            "the book holds %d reporting dates, and a migration needs two" % (len(dates),))
        if len(dates) > 13:
            return ((dates[0], dates[12]), (dates[12], dates[-1]), (dates[0], dates[-1]))
        return ((dates[0], dates[-1]),)

    def _s3_migration(s, portfolio):
        """The matrix is the book's movements: one row per grade, every row summing to 10000."""
        for start, end in _s3_windows(portfolio):
            matrix = s.migration(portfolio, start, end)
            where = "the migration from %s to %s" % (start, end)
            assert isinstance(matrix, dict), (
                "%s is %r, and a matrix is a MATRIX_KEYS record" % (where, matrix))
            assert tuple(matrix) == S3_MATRIX_KEYS, (
                "%s has the fields %r, and a matrix is %r"
                % (where, tuple(matrix), S3_MATRIX_KEYS))
            assert matrix["from_date"] == start and matrix["to_date"] == end, (
                "%s is dated %r..%r" % (where, matrix["from_date"], matrix["to_date"]))
            grades = tuple(matrix["grades"])
            assert grades == S3_GRADES, (
                "%s holds the grades %r, and every grade of the scale gets its row"
                % (where, grades))
            counts = matrix["counts"]
            for pair, count in counts.items():
                assert isinstance(pair, tuple) and len(pair) == 2, (
                    "%s counts %r, and a count is keyed by a `(from, to)` pair"
                    % (where, pair))
                assert pair[0] in S3_GRADES and pair[1] in S3_GRADES, (
                    "%s counts the pair %r, which is not a pair of grades" % (where, pair))
                assert isinstance(count, int) and count >= 1, (
                    "%s counts %r as %r, and a recorded pair is a pair a loan made"
                    % (where, pair, count))
            mine = _s3_moves(portfolio, start, end)
            assert counts == mine, (
                "%s counted %r, and the grades the book recorded at the two dates count %r"
                % (where, counts, mine))
            assert any(came != went for came, went in mine), (
                "%s has nothing to tell apart: every loan kept its grade, so the check "
                "cannot see whether the row is the grade at the start or at the end"
                % (where,))
            totals = matrix["row_totals"]
            assert sorted(totals) == sorted(S3_GRADES), (
                "%s has the row totals %r, and every grade of the scale gets one"
                % (where, sorted(totals)))
            for grade in S3_GRADES:
                want = sum(count for (came, _went), count in mine.items() if came == grade)
                assert totals[grade] == want, (
                    "%s totals the row of %s at %r, and %r left it"
                    % (where, grade, totals[grade], want))
            rows = tuple(matrix["rates_bp"])
            assert rows == s.rates(matrix), (
                "%s carries the rates %r, and `rates` of the same matrix is %r"
                % (where, rows, s.rates(matrix)))
            assert len(rows) == len(S3_GRADES), (
                "%s has %d rows for %d grades" % (where, len(rows), len(S3_GRADES)))
            for came, row in zip(S3_GRADES, rows):
                assert isinstance(row, tuple) and len(row) == len(S3_GRADES), (
                    "%s answers the row of %s as %r, and a row is one cell per grade"
                    % (where, came, row))
                assert sum(row) == S3_SCALE, (
                    "%s sums the row of %s to %d, and a row of a distribution is exactly "
                    "%d: the basis points the divisions left belong to the default column"
                    % (where, came, sum(row), S3_SCALE))
            assert rows == _s3_rows(S3_GRADES, mine, totals), (
                "%s answers the rows %r, and the check's own row of every count is %r"
                % (where, rows, _s3_rows(S3_GRADES, mine, totals)))
            _s3_truncation(rows, mine, totals, where)
            place = S3_GRADES.index(S3_DEFAULT)
            absorbing = tuple(S3_SCALE if at == place else 0
                              for at in range(len(S3_GRADES)))
            for came, row in zip(S3_GRADES, rows):
                others = sum(row[at] for at in range(len(S3_GRADES)) if at != place)
                assert row[place] == S3_SCALE - others, (
                    "%s gives the row of %s %d basis points to %r, and the remainder of "
                    "its other divisions is %d"
                    % (where, came, row[place], S3_DEFAULT, S3_SCALE - others))
                if totals[came] == 0:
                    assert row == absorbing, (
                        "%s answers the row of %s, which no loan sat in, as %r: a row "
                        "with no loans is the absorb-the-rest row %r"
                        % (where, came, row, absorbing))
            exits = sum(count for (came, went), count in mine.items()
                        if came == S3_DEFAULT and went != S3_DEFAULT)
            if exits == 0:
                assert rows[place] == absorbing, (
                    "%s counted no loan leaving %r, so the row of %r is the absorbing "
                    "row %r, and it answered %r"
                    % (where, S3_DEFAULT, S3_DEFAULT, absorbing, rows[place]))

    def _s3_truncation(rows, counts, totals, where):
        """Every cell of a row is `count * 10000 // row_total`, truncated, on both sides."""
        for at, came in enumerate(S3_GRADES):
            total = totals[came]
            if total == 0:
                continue
            for there, went in enumerate(S3_GRADES):
                if went == S3_DEFAULT:
                    continue
                count = counts.get((came, went), 0)
                bp = rows[at][there]
                assert bp * total <= count * S3_SCALE < (bp + 1) * total, (
                    "%s rates %s -> %s at %r basis points, and the count %d of %d is "
                    "%d: the cell is the truncated `count * 10000 // row_total`"
                    % (where, came, went, bp, count, total, count * S3_SCALE // total))

    def _s3_answer_key(s, portfolio):
        """The book's own record of the movements and the stage's matrix agree exactly."""
        for start, end in _s3_windows(portfolio):
            recorded = portfolio.migrations(start, end)
            assert isinstance(recorded, dict), (
                "the book's own migrations record for %s..%s is %r" % (start, end, recorded))
            observed = {pair: count for pair, count in recorded.items() if count}
            matrix = s.migration(portfolio, start, end)
            assert matrix["counts"] == observed, (
                "the matrix from %s to %s counts %r, and the book itself recorded %r"
                % (start, end, matrix["counts"], observed))

    def _s3_sum_rows(rows, what):
        """Every row of a rate grid is a distribution: exactly 10000 basis points."""
        for came, row in zip(S3_GRADES, rows):
            assert sum(row) == S3_SCALE, (
                "%s sums the row of %s to %d, and it has to be exactly %d"
                % (what, came, sum(row), S3_SCALE))

    def _s3_rates_edges(s, world):
        """The remainder, the empty row, the absorbing row, and every refusal of a shape."""
        place = S3_GRADES.index(S3_DEFAULT)
        empty = tuple(S3_SCALE if at == place else 0 for at in range(len(S3_GRADES)))

        one = s.rates(_s3_matrix({("A", "B"): 1, ("A", "C"): 2}))
        assert one[0] == (0, 3333, 6666, 0, 0, 0, 1), (
            "a row of 3333 and 6666 basis points left one basis point, and `rates` "
            "answered the row of A as %r: the remainder belongs to the %r column"
            % (one[0], S3_DEFAULT))
        _s3_sum_rows(one, "a row with a remainder of one basis point")

        two = s.rates(_s3_matrix({("A", "B"): 1, ("A", "C"): 1, ("A", "D"): 1,
                                  ("B", "A"): 2, ("B", "C"): 1}))
        assert two[0] == (0, 3333, 3333, 3333, 0, 0, 1), (
            "the whole remainder of a row goes to %r, and the row of A came back %r"
            % (S3_DEFAULT, two[0]))
        assert two[1] == (6666, 0, 3333, 0, 0, 0, 1), (
            "the row of B is two loans to A and one to C, and `rates` answered %r"
            % (two[1],))
        _s3_sum_rows(two, "two rows that both need the remainder")

        three = s.rates(_s3_matrix({("B", "B"): 1, ("B", "C"): 1, ("B", S3_DEFAULT): 1}))
        assert three[1] == (0, 3333, 3333, 0, 0, 0, 3334), (
            "the %r column takes the remainder of its row, not its own truncated cell, "
            "and the row of B came back %r" % (S3_DEFAULT, three[1]))

        four = s.rates(_s3_matrix({("C", "C"): 1}))
        assert four[2] == (0, 0, S3_SCALE, 0, 0, 0, 0), (
            "a row whose only loan stayed in C leaves nothing over, and `rates` answered "
            "%r" % (four[2],))

        five = s.rates(_s3_matrix({}))
        for came, row in zip(S3_GRADES, five):
            assert row == empty, (
                "no loan sat in %s, so its row is the absorb-the-rest row %r, and "
                "`rates` answered %r" % (came, empty, row))

        six = s.rates(_s3_matrix({(S3_DEFAULT, S3_DEFAULT): 5}))
        assert six[place] == empty, (
            "the row of %r is absorbing, and `rates` answered %r" % (S3_DEFAULT, six[place]))

        # A row whose counts carry a cure out of the default column: the per-cell rule is
        # the rule for that row too, so the cure's own rate shows up there. A stage that
        # forced the row to 10000 has adjusted the book's own record rather than read it.
        cured = s.rates(_s3_matrix({(S3_DEFAULT, S3_DEFAULT): 3, (S3_DEFAULT, "A"): 1}))
        assert cured[place] == (2500, 0, 0, 0, 0, 0, 7500), (
            "the row of %r is one loan cured to A and three that stayed, and `rates` "
            "answered %r: every cell is `count * 10000 // row_total` truncated and the "
            "remainder of the row goes to the %r column" % (S3_DEFAULT, cured[place],
                                                            S3_DEFAULT))
        _s3_sum_rows(cured, "a row of the default column with a cure in it")

        short = _s3_matrix({("A", "B"): 1})
        del short["row_totals"]
        _refuses(world.BookError, "a matrix with no row totals",
                 lambda: s.rates(short), names=("row_totals",))
        _refuses(world.BookError, "a matrix that is not a mapping",
                 lambda: s.rates(()), names=("mapping",))
        _refuses(world.BookError, "a matrix with no %r column" % (S3_DEFAULT,),
                 lambda: s.rates(_s3_matrix({("A", "B"): 1}, grades=S3_GRADES[:-1])),
                 names=(S3_DEFAULT,))
        _refuses(world.BookError, "a matrix holding a grade the scale does not hold",
                 lambda: s.rates(_s3_matrix({("A", "B"): 1},
                                            grades=("A", "B", "Z", S3_DEFAULT))),
                 names=("Z",))
        _refuses(world.BookError, "a matrix with no grades at all",
                 lambda: s.rates(_s3_matrix({}, grades=())), names=("grades",))
        outside = _s3_matrix({("A", "B"): 1})
        outside["counts"][("A", "Z")] = 1
        _refuses(world.BookError, "a count keyed by a grade the matrix does not hold",
                 lambda: s.rates(outside), names=("('A', 'Z')",))
        keyed = _s3_matrix({("A", "B"): 1})
        keyed["counts"]["A"] = 1
        _refuses(world.BookError, "a count keyed by something that is not a pair",
                 lambda: s.rates(keyed), names=())

    def _s3_term(s, portfolio):
        """The term structure of every grade over every window, and its boundaries.

        The invariants of §4.3 are checked on all three windows, because the book's own
        counts do carry a cure out of the `default` column inside one of them: a walk
        that carried that mass back would answer a cumulative above 10000 there and
        nowhere else.
        """
        for start, end in _s3_windows(portfolio):
            matrix = s.migration(portfolio, start, end)
            grades = tuple(matrix["grades"])
            rows = tuple(matrix["rates_bp"])
            place = grades.index(S3_DEFAULT)
            where = "the migration from %s to %s" % (start, end)
            for grade in S3_GRADES:
                for months in (0, 1, 2, 12, 360):
                    answer = s.term_structure(matrix, grade, months)
                    at = "%s, over %d months" % (where, months)
                    assert isinstance(answer, tuple), (
                        "the term structure of %s is %r, and a term structure is a tuple "
                        "of PD_KEYS rows" % (at, answer))
                    assert len(answer) == months, (
                        "the term structure of %s answers %d rows, and every step gets one"
                        % (at, len(answer)))
                    last = 0
                    for step, row in enumerate(answer, start=1):
                        assert tuple(row) == S3_PD_KEYS, (
                            "the term structure of %s has the fields %r at step %d, and a "
                            "PD term is %r" % (at, tuple(row), step, S3_PD_KEYS))
                        assert row["grade"] == grade, (
                            "the term structure of %s names the grade %r at step %d"
                            % (at, row["grade"], step))
                        assert row["horizon_months"] == step, (
                            "the term structure of %s counts the horizon %r at step %d, "
                            "and a horizon counts from 1"
                            % (at, row["horizon_months"], step))
                        assert 0 <= row["marginal_bp"] <= S3_SCALE, (
                            "the term structure of %s answers the marginal %r at step %d"
                            % (at, row["marginal_bp"], step))
                        assert last <= row["cumulative_bp"] <= S3_SCALE, (
                            "the term structure of %s answers the cumulative %r at step "
                            "%d, after %r, and a cumulative never falls and never passes "
                            "%d" % (at, row["cumulative_bp"], step, last, S3_SCALE))
                        last = row["cumulative_bp"]
                    want = _s3_walk(grades, rows, grade, months)
                    got = _s3_got(answer)
                    assert got == want, (
                        "the term structure of %s answers %r, and the check's own survival "
                        "walk of the same matrix answers %r: the marginal is the mass that "
                        "lands in %r at that step, on the distribution of the loans still "
                        "alive, and the cumulative is the running sum of those marginals"
                        % (at, got, want, S3_DEFAULT))
                    assert s.lifetime_pd(matrix, grade, months) == (last if answer else 0), (
                        "the lifetime PD of %s over %d months is the cumulative at the "
                        "last step, and it answered %r for a last cumulative of %r"
                        % (grade, months, s.lifetime_pd(matrix, grade, months), last))
                first = s.term_structure(matrix, grade, 1)
                if grade != S3_DEFAULT:
                    assert first[0]["marginal_bp"] == rows[grades.index(grade)][place], (
                        "the first marginal of %s in %s is the transition of its own row "
                        "into %r, and it answered %r for a row that says %r"
                        % (grade, where, S3_DEFAULT, first[0]["marginal_bp"],
                           rows[grades.index(grade)][place]))
                else:
                    assert _s3_got(first) == ((S3_DEFAULT, 1, 0, S3_SCALE),), (
                        "a walk that starts in %r has already defaulted, and the "
                        "cumulative of %s answers %r"
                        % (S3_DEFAULT, where, _s3_got(first)))

    def _s3_got(row):
        """A PD term read as its four fields, for a comparison the check writes out."""
        return tuple((term["grade"], term["horizon_months"], term["marginal_bp"],
                      term["cumulative_bp"]) for term in row)

    def _s3_fixture_term(s, world):
        """The walk on hand-built matrices, where every marginal is a number the check wrote.

        The first fixture is one grade that survives at 4000 basis points a month and a
        `default` column that takes the rest, so the marginals are `6000`, `2400`, `960`
        and `384`: the second month's marginal is the first month's *survivors* falling
        into default, not the whole default column again. The second fixture is three
        grades whose rates truncate, where truncating each product and truncating their
        sum differ by a basis point.
        """
        one = _s3_term_matrix({("A", "A"): 4, ("A", S3_DEFAULT): 6})
        want = (("A", 1, 6000, 6000), ("A", 2, 2400, 8400), ("A", 3, 960, 9360),
                ("A", 4, 384, 9744))
        assert _s3_walk(S3_GRADES, one["rates_bp"], "A", 4) == want, (
            "the check's own walk of the surviving fixture is %r" % (want,))
        got = _s3_got(s.term_structure(one, "A", 4))
        assert got == want, (
            "the term structure of A over a fixture the check wrote is %r, and the "
            "survival arithmetic says %r: the marginal of a step is the mass that lands "
            "in %r from the grades still alive, on the distribution the previous step "
            "left" % (got, want, S3_DEFAULT))
        assert s.lifetime_pd(one, "A", 4) == 9744, (
            "the lifetime PD of A over four months is the fourth cumulative, and it "
            "answered %r" % (s.lifetime_pd(one, "A", 4),))
        assert s.lifetime_pd(one, "A", 0) == 0, (
            "a horizon of no months has defaulted nothing, and the lifetime PD answered %r"
            % (s.lifetime_pd(one, "A", 0),))
        empty = _s3_got(s.term_structure(one, "B", 1))
        assert empty == (("B", 1, S3_SCALE, S3_SCALE),), (
            "no loan sat in B, so its row is the absorb-the-rest row and one step puts "
            "the whole mass there, and the stage answered %r" % (empty,))

        three = ("A", "B", S3_DEFAULT)
        two = _s3_term_matrix({("A", "A"): 3333, ("A", "B"): 3334,
                               ("A", S3_DEFAULT): 3333,
                               ("B", "A"): 3333, ("B", "B"): 3334,
                               ("B", S3_DEFAULT): 3333}, grades=three)
        assert two["rates_bp"][0] == (3333, 3334, 3333), (
            "the fixture's own rows are its counts over 10000, and the check built %r"
            % (two["rates_bp"][0],))
        walked = (("A", 1, 3333, 3333), ("A", 2, 2221, 5554))
        assert _s3_walk(three, two["rates_bp"], "A", 2) == walked, (
            "the check's own walk of the truncating fixture is %r" % (walked,))
        got = _s3_got(s.term_structure(two, "A", 2))
        assert got == walked, (
            "the stage walks the truncating fixture to %r, and every product truncated "
            "one by one gives %r — truncating the sum of the products answers a basis "
            "point more" % (got, walked))
        assert s.lifetime_pd(two, "B", 2) == 5554, (
            "B's rates are A's rates in this fixture, so its lifetime PD is 5554, and it "
            "answered %r" % (s.lifetime_pd(two, "B", 2),))

        _refuses(world.BookError, "a grade the fixture's matrix has no row for",
                 lambda: s.term_structure(two, "C", 3), names=("C",))
        _refuses(world.BookError, "a grade the scale does not hold",
                 lambda: s.term_structure(two, "ZZ", 3), names=("ZZ",))

        # A default row the book's own counts can produce: three loans stayed defaulted,
        # one was re-rated back to A. A walk that carried that mass back would answer a
        # cumulative above the scale on the third step.
        leaky = _s3_term_matrix({("A", S3_DEFAULT): 4, (S3_DEFAULT, "A"): 1,
                                 (S3_DEFAULT, S3_DEFAULT): 3},
                                grades=("A", S3_DEFAULT))
        assert leaky["rates_bp"] == ((0, S3_SCALE), (2500, 7500)), (
            "the check built the leaking fixture's rows as %r" % (leaky["rates_bp"],))
        want = (("A", 1, S3_SCALE, S3_SCALE), ("A", 2, 0, S3_SCALE),
                ("A", 3, 0, S3_SCALE), ("A", 4, 0, S3_SCALE))
        assert _s3_walk(("A", S3_DEFAULT), leaky["rates_bp"], "A", 4) == want, (
            "the check's own survival walk of the leaking fixture is %r" % (want,))
        got = _s3_got(s.term_structure(leaky, "A", 4))
        assert got == want, (
            "the term structure of a matrix whose %r row carries a cure out of the column "
            "answers %r, and a defaulted loan is not at risk again: the mass that reaches "
            "%r is counted and dropped, so the walk answers %r"
            % (S3_DEFAULT, got, S3_DEFAULT, want))
        already = (("default", 1, 0, S3_SCALE), ("default", 2, 0, S3_SCALE),
                   ("default", 3, 0, S3_SCALE))
        got = _s3_got(s.term_structure(leaky, S3_DEFAULT, 3))
        assert got == already, (
            "a walk that starts in %r has already defaulted, and the stage answered %r"
            % (S3_DEFAULT, got))
        assert s.lifetime_pd(leaky, S3_DEFAULT, 3) == S3_SCALE, (
            "the lifetime PD of a grade that is %r already is the whole scale, and it "
            "answered %r" % (S3_DEFAULT, s.lifetime_pd(leaky, S3_DEFAULT, 3)))
        assert s.lifetime_pd(leaky, "A", 4) == S3_SCALE, (
            "every path out of A ends in %r within four steps, and the lifetime PD "
            "answered %r" % (S3_DEFAULT, s.lifetime_pd(leaky, "A", 4)))
        _refuses(world.BookError, "a horizon below zero",
                 lambda: s.term_structure(two, "A", -1), names=("-1",))
        _refuses(world.BookError, "a horizon that is not a number",
                 lambda: s.term_structure(two, "A", "3"), names=("3",))
        _refuses(world.BookError, "a lifetime over a horizon below zero",
                 lambda: s.lifetime_pd(two, "A", -1), names=("-1",))
        _refuses(world.BookError, "a grade the matrix has no row for",
                 lambda: s.lifetime_pd(two, "C", 1), names=("C",))

    def _s3_refusals(s, world, portfolio):
        """A date the book does not cover is refused by name, and asks only for the dates.

        The book counts its own `reporting_dates` accessor under `lookups`, so a stage
        that refuses a date has already paid for the list it validated against — that
        read is the whole of what a refusal may cost. Nothing else in the ledger may
        move: in particular no loan's grade may have been asked for, which is what a
        stage that looked its dates up one loan at a time would do twelve times.
        """
        dates = tuple(portfolio.reporting_dates)
        outside = "1999-01-31"
        assert outside not in dates, (
            "the book's history starts at %s, and this check needs a date before it"
            % (dates[0],))
        for start, end, names in ((outside, dates[-1], (outside,)),
                                  (dates[0], outside, (outside,)),
                                  ("not-a-date", dates[-1], ("not-a-date",)),
                                  (0, dates[-1], ("0",)),
                                  (None, dates[-1], ("None",)),
                                  (dates[0], None, ("None",))):
            before = dict(portfolio.stats())
            _refuses(world.BookError, "a migration from %r to %r" % (start, end),
                     lambda: s.migration(portfolio, start, end), names=names)
            after = dict(portfolio.stats())
            moved = {key: after[key] - before[key] for key in after}
            assert all(moved[key] == 0 for key in moved if key != "lookups"), (
                "a migration refused for %r..%r moved the ledger's %r: %r -> %r"
                % (start, end, {k: v for k, v in moved.items() if v and k != "lookups"},
                   before, after))
            assert 0 <= moved["lookups"] <= 1, (
                "a migration refused for %r..%r asked the book for %d reads, and the "
                "only thing a refusal may cost is one read of the book's own list of "
                "dates: a stage that asked for a grade per loan before refusing is what "
                "this catches" % (start, end, moved["lookups"]))

    def _s3_ledger(s, portfolio):
        """The stage recomputes the book's record; it never reads the book's own count of it."""
        start, end = _s3_windows(portfolio)[0]
        before = dict(portfolio.stats())
        s.migration(portfolio, start, end)
        after = dict(portfolio.stats())
        assert after.get("migrations") == before.get("migrations"), (
            "a migration from %s to %s read the book's own migrations record instead of "
            "recomputing it: %r -> %r" % (start, end, before, after))

    def _s3_twice(s, world):
        """One whole workload run twice: the two answers are equal."""
        portfolio = world.Book.build(7)

        def once():
            answers = []
            for start, end in _s3_windows(portfolio):
                matrix = s.migration(portfolio, start, end)
                answers.append((start, end, tuple(sorted(matrix["counts"].items())),
                                tuple(matrix["rates_bp"]),
                                tuple(sorted(matrix["row_totals"].items()))))
                for grade in S3_GRADES:
                    answers.append(_s3_got(s.term_structure(matrix, grade, 24)))
                    answers.append(s.lifetime_pd(matrix, grade, 12))
            return tuple(answers)

        assert once() == once(), (
            "two runs of one workload answered differently, so an answer is not a "
            "function of the book it was computed from")

    import book as world
    import rules
    import stage_03 as s
    _s3_constants(s, rules)
    portfolio = world.Book.build(7)
    _s3_migration(s, portfolio)
    _s3_answer_key(s, portfolio)
    _s3_rates_edges(s, world)
    _s3_term(s, portfolio)
    _s3_fixture_term(s, world)
    _s3_refusals(s, world, portfolio)
    _s3_ledger(s, portfolio)
    _s3_twice(s, world)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    S4_RECOVERY_KEYS = ("loan", "flows", "recovered_cents", "undiscounted_cents")

    S4_LGD_KEYS = ("loan", "balance_cents", "recovered_cents", "lgd_bp", "workout_months",
                   "haircut_bp")

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "book.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked against
        the message: an exception of the right family raised for the wrong reason is not
        the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _want_months(dates, start, end):
        """The calendar months from `start` to `end`, by the world's own `add_months`."""
        months = 0
        while dates.add_months(start, months + 1) <= end:
            months += 1
        return months

    def _want_discount(amount, periods, period_rate_bp):
        """`amount` discounted `periods` periods, stage 1's stepwise truncation."""
        factor = 10000
        for _ in range(periods):
            factor = factor * 10000 // (10000 + period_rate_bp)
        return amount * factor // 10000

    def _defaulted(book):
        """The loan ids the book records a default for, each one's first signalled date.

        A default that has since cured still counts: the loss was fixed at the date it was
        signalled, so a cured loan answers like any other, at its first default.
        """
        found = {}
        for record in book.defaults():
            identified = record["loan"]
            when = record["signalled_on"]
            if identified not in found or when < found[identified]:
                found[identified] = when
        return found

    def _uncured(book):
        """The loan ids whose default the book has not cured: the segment's live defaults."""
        return set(record["loan"] for record in book.defaults()
                   if record.get("cured_on") is None)

    def _cured(book):
        """The loan ids whose default the book has cured: healthy now, defaulted once."""
        return set(record["loan"] for record in book.defaults()
                   if record.get("cured_on") is not None)

    def _want_period_rate(rules, stage_01, book, loan):
        """The loan's effective rate as one period's rate, from stage 1's own answer."""
        effective = stage_01.effective_rate(book, loan)
        return rules.period_rate(effective["eir_bp"], effective["basis"])

    def _want_recoveries(dates, rules, stage_01, book, loan, default_date):
        """The check's own `recoveries`: the book's rows discounted to the default."""
        period_rate_bp = _want_period_rate(rules, stage_01, book, loan)
        haircut_bp = rules.COLLATERAL_HAIRCUT_BP[loan["collateral_kind"]]
        rows = tuple(book.recoveries(loan))
        recovered = 0
        undiscounted = 0
        for row in rows:
            amount = row["amount_cents"]
            if row["source"] == "collateral":
                amount = amount * (10000 - haircut_bp) // 10000
            recovered += _want_discount(
                amount, _want_months(dates, default_date, row["date"]), period_rate_bp)
            undiscounted += row["amount_cents"]
        return {"loan": loan["loan"], "flows": rows, "recovered_cents": recovered,
                "undiscounted_cents": undiscounted}

    def _want_balance(rules, book, loan, default_date):
        """The check's own balance: the schedule's amortisation after what was repaid.

        The contractual principal less the principal portions of the instalments actually
        paid by then, less prepayments, floored at zero: each due's payments summed and
        applied once against the balance before it, the period's interest truncated, only
        what the payment left over reducing the balance and never more than the balance.
        """
        period_rate_bp = rules.period_rate(loan["rate_bp"], rules.DEFAULT_BASIS)
        balance = loan["principal_cents"]
        payments = list(book.payments(loan))
        paid_by_due = {}
        for payment in payments:
            if payment["kind"] == "instalment" and payment["paid_on"] <= default_date:
                due = payment["due"]
                paid_by_due[due] = paid_by_due.get(due, 0) + payment["amount_cents"]
        for due in sorted(paid_by_due):
            interest = balance * period_rate_bp // 10000
            balance -= min(balance, max(0, paid_by_due[due] - interest))
        prepaid = 0
        for payment in payments:
            if payment["kind"] == "prepayment" and payment["paid_on"] <= default_date:
                prepaid += payment["amount_cents"]
        return max(0, balance - prepaid)

    def _want_lgd(dates, rules, book, loan, default_date, recovered):
        """The check's own `lgd` record: the capped recovery and the clamped loss."""
        rows = tuple(book.recoveries(loan))
        balance = _want_balance(rules, book, loan, default_date)
        capped = recovered if recovered <= balance else balance
        lgd_bp = 10000 - capped * 10000 // balance
        if lgd_bp < rules.LGD_FLOOR_BP:
            lgd_bp = rules.LGD_FLOOR_BP
        elif lgd_bp > rules.LGD_CAP_BP:
            lgd_bp = rules.LGD_CAP_BP
        if rows:
            workout_months = _want_months(dates, default_date,
                                          max(row["date"] for row in rows))
        else:
            workout_months = 0
        return {"loan": loan["loan"], "balance_cents": balance,
                "recovered_cents": capped, "lgd_bp": lgd_bp,
                "workout_months": workout_months,
                "haircut_bp": rules.COLLATERAL_HAIRCUT_BP[loan["collateral_kind"]]}

    class _Graft:
        """The real book with one loan's recovery rows, record or default list swapped.

        The world's facts are not the check's to invent, so this wraps the real book and
        replaces exactly what a boundary needs; every other door — the schedule, the
        payments, the effective rate stage 1 searches for — is the real book's own.
        """

        def __init__(self, real, loan_id, rows=None, record=None, defaults=None):
            self._real = real
            self._loan_id = loan_id
            self._rows = None if rows is None else tuple(rows)
            self._record = record
            self._defaults = defaults

        def loan(self, loan):
            identified = loan["loan"] if isinstance(loan, dict) else loan
            if self._record is not None and identified == self._loan_id:
                return self._record
            return self._real.loan(identified)

        def loans(self):
            base = [loan for loan in self._real.loans()
                    if loan["loan"] != self._loan_id]
            if self._record is not None:
                base.append(self._record)
            return tuple(base)

        def recoveries(self, loan):
            identified = loan["loan"] if isinstance(loan, dict) else loan
            if self._rows is not None and identified == self._loan_id:
                return self._rows
            return self._real.recoveries(identified)

        def defaults(self):
            if self._defaults is not None:
                return self._defaults
            return self._real.defaults()

        def __getattr__(self, name):
            return getattr(self._real, name)

    def _s4_constants(s, rules):
        """The constants, in order: a mutation that moves one is caught."""
        assert tuple(s.RECOVERY_KEYS) == S4_RECOVERY_KEYS, (
            "RECOVERY_KEYS is %r, and a recovery record is the four keys %r"
            % (s.RECOVERY_KEYS, S4_RECOVERY_KEYS))
        assert tuple(s.LGD_KEYS) == S4_LGD_KEYS, (
            "LGD_KEYS is %r, and a loss record is the six keys %r"
            % (s.LGD_KEYS, S4_LGD_KEYS))
        assert s.LGD_FLOOR_BP == rules.LGD_FLOOR_BP, (
            "LGD_FLOOR_BP is %r, and the policy's floor is %r"
            % (s.LGD_FLOOR_BP, rules.LGD_FLOOR_BP))
        assert s.LGD_CAP_BP == rules.LGD_CAP_BP, (
            "LGD_CAP_BP is %r, and the policy's cap is %r"
            % (s.LGD_CAP_BP, rules.LGD_CAP_BP))
        assert dict(s.COLLATERAL_HAIRCUT_BP) == dict(rules.COLLATERAL_HAIRCUT_BP), (
            "COLLATERAL_HAIRCUT_BP is %r, and the policy's table is %r"
            % (s.COLLATERAL_HAIRCUT_BP, rules.COLLATERAL_HAIRCUT_BP))

    def _s4_flows_and_lgd(s, book, dates, rules, stage_01):
        """Every defaulted loan's flows and loss, recomputed from the world alone."""
        defaulted = _defaulted(book)
        assert defaulted, "the book holds no default for this stage to measure"
        for loan in book.loans():
            if loan["loan"] not in defaulted:
                continue
            default_date = defaulted[loan["loan"]]
            flow = s.recoveries(book, loan)
            assert tuple(flow) == S4_RECOVERY_KEYS, (
                "recoveries(%r)'s keys are %r, and they are %r"
                % (loan["loan"], tuple(flow), S4_RECOVERY_KEYS))
            want = _want_recoveries(dates, rules, stage_01, book, loan, default_date)
            assert flow == want, (
                "recoveries(%r) is %r, and the book's own rows discounted are %r"
                % (loan["loan"], flow, want))
            assert flow["flows"] == tuple(book.recoveries(loan)), (
                "%r's flows are not the book's own recovery rows" % (loan["loan"],))
            assert flow["undiscounted_cents"] == sum(
                row["amount_cents"] for row in book.recoveries(loan)), (
                "%r's undiscounted total is not the plain sum of its own rows"
                % (loan["loan"],))
            if flow["undiscounted_cents"] >= 0:
                assert flow["recovered_cents"] <= flow["undiscounted_cents"], (
                    "%r's discounting added to its recovery: %r over %r"
                    % (loan["loan"], flow["recovered_cents"],
                       flow["undiscounted_cents"]))
            record = s.lgd(book, loan)
            assert tuple(record) == S4_LGD_KEYS, (
                "lgd(%r)'s keys are %r, and they are %r"
                % (loan["loan"], tuple(record), S4_LGD_KEYS))
            want_lgd = _want_lgd(dates, rules, book, loan, default_date,
                                 want["recovered_cents"])
            assert record == want_lgd, (
                "lgd(%r) is %r, and the balance and the capped recovery say %r"
                % (loan["loan"], record, want_lgd))
            assert rules.LGD_FLOOR_BP <= record["lgd_bp"] <= rules.LGD_CAP_BP, (
                "%r's LGD %r is outside the policy's floor and cap"
                % (loan["loan"], record["lgd_bp"]))
            assert record["recovered_cents"] <= record["balance_cents"], (
                "%r's recovery %r exceeds its balance %r"
                % (loan["loan"], record["recovered_cents"], record["balance_cents"]))

    def _s4_segments(s, book, dates, rules, stage_01):
        """The exposure-weighted loss of every segment, recomputed from the world alone."""
        defaulted = _defaulted(book)
        live = _uncured(book)
        segments = {}
        for loan in book.loans():
            segments.setdefault(loan["segment"], []).append(loan)
        for segment in rules.SEGMENTS:
            answer = s.lgd_by_segment(book, segment)
            wanted = [loan for loan in segments.get(segment, [])
                      if loan["loan"] in live]
            if not wanted:
                assert answer is None, (
                    "%s has no defaults and answered %r instead of None"
                    % (segment, answer))
                continue
            top = 0
            bottom = 0
            for loan in wanted:
                default_date = defaulted[loan["loan"]]
                want = _want_recoveries(dates, rules, stage_01, book, loan, default_date)
                record = _want_lgd(dates, rules, book, loan, default_date,
                                   want["recovered_cents"])
                top += record["lgd_bp"] * record["balance_cents"]
                bottom += record["balance_cents"]
            assert answer == top // bottom, (
                "%s's exposure-weighted LGD is %r, and its balances say %r"
                % (segment, answer, top // bottom))

    def _s4_no_defaults(s, book, rules):
        """A book with no default at all answers `None` for every segment."""
        hidden = _Graft(book, "", defaults=())
        for segment in rules.SEGMENTS:
            assert s.lgd_by_segment(hidden, segment) is None, (
                "%s answered a number for a book with no default" % (segment,))

    def _s4_cap(s, book, dates, rules, stage_01, world):
        """Both sides of the cap, both sides of the floor, a cost and an empty stream."""
        defaulted = _defaulted(book)
        target = [loan for loan in book.loans() if loan["loan"] in defaulted][0]
        default_date = defaulted[target["loan"]]
        balance = _want_balance(rules, book, target, default_date)
        assert balance > 1, "the check needs a defaulted loan with a balance to cap"

        def graft(rows):
            return _Graft(book, target["loan"], rows=rows)

        def row(amount, source="cash"):
            return {"loan": target["loan"], "date": default_date,
                    "amount_cents": amount, "source": source}

        over = s.lgd(graft((row(balance + 1),)), target)
        assert over["recovered_cents"] == balance, (
            "a recovery one cent over the balance is %r, not the cap %r"
            % (over["recovered_cents"], balance))
        assert over["lgd_bp"] == rules.LGD_FLOOR_BP, (
            "a recovery at the cap has loss %r, not the floor %r"
            % (over["lgd_bp"], rules.LGD_FLOOR_BP))

        under = s.lgd(graft((row(balance - 1),)), target)
        assert under["recovered_cents"] == balance - 1, (
            "a recovery one cent under the balance is %r, not %r"
            % (under["recovered_cents"], balance - 1))
        assert under["lgd_bp"] == 10000 - (balance - 1) * 10000 // balance, (
            "a recovery one cent under the balance has loss %r, not %r"
            % (under["lgd_bp"], 10000 - (balance - 1) * 10000 // balance))

        even = s.lgd(graft((row(balance),),), target)
        assert even["recovered_cents"] == balance and even["lgd_bp"] == rules.LGD_FLOOR_BP, (
            "a recovery exactly at the balance is %r, not the cap with a zero loss" % (even,))

        mixed = graft((row(600, "cash"), row(-200, "costs")))
        flow = s.recoveries(mixed, target)
        assert flow["recovered_cents"] == 400 and flow["undiscounted_cents"] == 400, (
            "a cost is not subtracted from the recovery: %r" % (flow,))

        empty = graft(())
        flow = s.recoveries(empty, target)
        assert flow == {"loan": target["loan"], "flows": (), "recovered_cents": 0,
                        "undiscounted_cents": 0}, (
            "a default with no recovery flow is not the empty record: %r" % (flow,))
        record = s.lgd(empty, target)
        assert record["recovered_cents"] == 0 and record["lgd_bp"] == 10000, (
            "a default with no recovery flow has loss %r, not all of it" % (record,))
        assert record["workout_months"] == 0 and record["balance_cents"] == balance, (
            "a default with no recovery flow has a workout of %r and a balance of %r"
            % (record["workout_months"], record["balance_cents"]))

        with_rows = [loan for loan in book.loans()
                     if loan["loan"] in defaulted and book.recoveries(loan)][0]
        broken = dict(with_rows, collateral_kind="gold")
        bad = _Graft(book, with_rows["loan"], record=broken)
        _refuses(world.BookError, "recoveries of a loan whose collateral the policy "
                 "does not hold", lambda: s.recoveries(bad, broken), names=("gold",))

    def _s4_refusals(s, book, dates, stage_01, world, rules):
        """A loan with no default refuses by name; a cured default still answers."""
        defaulted = _defaulted(book)
        cured = _cured(book)
        healthy = [loan for loan in book.loans() if loan["loan"] not in defaulted]
        assert healthy, "the book holds no loan with no default for the refusal"
        assert cured, "the book holds no cured default to answer for"
        healed = [loan for loan in book.loans() if loan["loan"] in cured][0]
        target = healthy[0]
        _refuses(world.BookError, "lgd of a loan that never defaulted",
                 lambda: s.lgd(book, target), names=(target["loan"],))
        _refuses(world.BookError, "recoveries of a loan that never defaulted",
                 lambda: s.recoveries(book, target), names=(target["loan"],))
        healed_date = _defaulted(book)[healed["loan"]]
        want_flow = _want_recoveries(dates, rules, stage_01, book, healed, healed_date)
        assert s.recoveries(book, healed) == want_flow, (
            "%r defaulted and cured, and its recoveries are %r, not %r"
            % (healed["loan"], s.recoveries(book, healed), want_flow))
        want_lgd = _want_lgd(dates, rules, book, healed, healed_date,
                             want_flow["recovered_cents"])
        assert s.lgd(book, healed) == want_lgd, (
            "%r defaulted and cured, and its loss is %r, not %r"
            % (healed["loan"], s.lgd(book, healed), want_lgd))
        _refuses(world.BookError, "lgd of a loan the book does not hold",
                 lambda: s.lgd(book, {"loan": "nope-04"}), names=("nope-04",))
        _refuses(world.BookError, "recoveries of a loan the book does not hold",
                 lambda: s.recoveries(book, {"loan": "nope-04"}), names=("nope-04",))
        _refuses(world.BookError, "lgd of something that is not a loan",
                 lambda: s.lgd(book, "not-a-loan-04"), names=("not-a-loan-04",))
        _refuses(world.BookError, "lgd_by_segment of a segment the policy does not hold",
                 lambda: s.lgd_by_segment(book, "zzz-04"), names=("zzz-04",))

    def _s4_ledger(s, book, world, rules):
        """A refused call does no schedule, status or recovery work on the book."""
        healthy = [loan for loan in book.loans() if loan["loan"] not in _defaulted(book)]
        before = book.stats()
        _refuses(world.BookError, "lgd of a loan that never defaulted",
                 lambda: s.lgd(book, healthy[0]), names=(healthy[0]["loan"],))
        after = book.stats()
        for key in ("schedules", "statuses", "recoveries"):
            assert after[key] == before[key], (
                "a refused lgd asked the book for %s: %r then %r" % (key, before, after))
        fresh = world.Book.build(7)
        _refuses(world.BookError, "lgd of a loan the book does not hold",
                 lambda: s.lgd(fresh, {"loan": "nope-04"}), names=("nope-04",))
        assert fresh.stats()["recoveries"] == 0, (
            "a refused lgd asked the book for recoveries: %r" % (fresh.stats(),))

    def _s4_workload(s, book, rules):
        """One whole pass of the stage over the book's defaults."""
        defaulted = _defaulted(book)
        answers = []
        for loan in book.loans():
            if loan["loan"] not in defaulted:
                continue
            answers.append(s.recoveries(book, loan))
            answers.append(s.lgd(book, loan))
        for segment in rules.SEGMENTS:
            answers.append(s.lgd_by_segment(book, segment))
        return tuple(answers)

    def _s4_twice(s, book, rules):
        one = _s4_workload(s, book, rules)
        two = _s4_workload(s, book, rules)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import book as world
    import dates
    import rules
    import stage_01
    import stage_04 as s
    b = world.Book.build(7)
    _s4_constants(s, rules)
    _s4_flows_and_lgd(s, b, dates, rules, stage_01)
    _s4_segments(s, b, dates, rules, stage_01)
    _s4_no_defaults(s, b, rules)
    _s4_refusals(s, b, dates, stage_01, world, rules)
    _s4_ledger(s, b, world, rules)
    _s4_cap(s, b, dates, rules, stage_01, world)
    _s4_twice(s, b, rules)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    S5_EAD_KEYS = ("loan", "date", "drawn_cents", "undrawn_cents", "ccf_bp", "ead_cents")

    def _repo(start=None):
        """The repo holding the course, found from `M1_REPO`, `start`, cwd or the default."""
        for candidate_start in (os.environ.get("M1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                here = os.path.join(candidate, COURSE)
                if (os.path.isfile(os.path.join(here, "book.py"))
                        or os.path.isfile(os.path.join(here, "course.py"))):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked against the
        message: an exception of the right family raised for the wrong reason is not the
        refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _ident(loan):
        """A loan record's own id, by the contract's key with the world's other spelling."""
        if isinstance(loan, str):
            return loan
        if "loan" in loan:
            return loan["loan"]
        return loan["id"]

    def _truncate(top, bottom):
        """`top` over `bottom`, truncated toward zero — the course's own reading of it."""
        negative = (top < 0) != (bottom < 0)
        value = abs(top) // abs(bottom)
        return -value if negative else value

    def _want_clamp(value, rules):
        """The policy's floor and cap applied to a factor, in the one order that works."""
        if value < rules.CCF_FLOOR_BP:
            return rules.CCF_FLOOR_BP
        if value > rules.CCF_CAP_BP:
            return rules.CCF_CAP_BP
        return value

    def _want_drawn(b, loan, date):
        """The contract's drawn amount: instalments paid by `date`, less prepayments, at zero."""
        drawn = 0
        for payment in b.payments(loan):
            if payment["paid_on"] > date:
                continue
            if payment["kind"] == "instalment":
                drawn = drawn + payment["amount_cents"]
            elif payment["kind"] == "prepayment":
                drawn = drawn - payment["amount_cents"]
        return max(0, drawn)

    def _want_plan(b, loan, date):
        """The schedule's own plan at `date`: every flow of the schedule due by then."""
        return sum(flow["amount_cents"] for flow in b.schedule(loan)["flows"]
                   if flow["date"] <= date)

    def _want_undrawn(b, loan, date):
        """The limit less the drawn amount above the plan, and never negative."""
        above = _want_drawn(b, loan, date) - _want_plan(b, loan, date)
        return max(0, loan["undrawn_limit_cents"] - max(0, above))

    def _want_signalled(b, loan):
        """The date this check reads as the loan's default date out of the book's record."""
        found = [record["signalled_on"] for record in b.defaults()
                 if record["loan"] == _ident(loan)]
        if not found:
            return None
        return min(found)

    def _want_defaulted(b, segment):
        """The check's own list of (loan record, default date) for a segment."""
        found = []
        for loan in b.loans():
            if loan["segment"] != segment:
                continue
            when = _want_signalled(b, loan)
            if when is not None:
                found.append((loan, when))
        return found

    def _want_ccf(b, segment, rules):
        """The contract's aggregate factor: sums first, one division, then the clamp."""
        drawdown = 0
        undrawn = 0
        for loan, when in _want_defaulted(b, segment):
            drawdown = drawdown + (_want_drawn(b, loan, when)
                                   - _want_drawn(b, loan, loan["origination"]))
            undrawn = undrawn + _want_undrawn(b, loan, loan["origination"])
        if undrawn <= 0:
            return rules.CCF_FLOOR_BP
        return _want_clamp(_truncate(drawdown * 10000, undrawn), rules)

    def _want_ead(b, loan, date, rules):
        """The contract's exposure record, recomputed from the loan and its payments."""
        drawn = _want_drawn(b, loan, date)
        undrawn = _want_undrawn(b, loan, date)
        rate = _want_ccf(b, loan["segment"], rules)
        return {"loan": _ident(loan), "date": date, "drawn_cents": drawn,
                "undrawn_cents": undrawn, "ccf_bp": rate,
                "ead_cents": drawn + undrawn * rate // 10000}

    S5_LONG = "2031-12-31"

    class _ToyBook:
        """A book by hand: loans, payments and defaults, with the world's own accessors."""

        def __init__(self, rules, dates):
            self._rules = rules
            self._dates = dates
            self._loans = []
            self._by_id = {}
            self._payments = {}
            self._flows = {}
            self._defaults = []
            self._stats = {"lookups": 0, "schedules": 0, "statuses": 0, "migrations": 0,
                           "recoveries": 0, "models": 0}
            self.log = []

        def add(self, ident, segment, limit, origination, flows, payments,
                signalled=None):
            """One loan, its schedule's flows, its payments and its default date."""
            loan = {"loan": ident, "borrower": "toy", "segment": segment,
                    "grade_origination": "B", "principal_cents": 1000000, "rate_bp": 600,
                    "term_months": 12, "first_due": S5_LONG, "origination": origination,
                    "collateral_kind": "none", "collateral_cents": 0,
                    "undrawn_limit_cents": limit, "measured_at": "amortised-cost"}
            self._loans.append(loan)
            self._by_id[ident] = loan
            self._flows[ident] = tuple({"date": when, "amount_cents": amount}
                                       for when, amount in flows)
            self._payments[ident] = tuple(
                {"loan": ident, "due": when, "paid_on": when, "amount_cents": amount,
                 "kind": kind} for when, amount, kind in payments)
            if signalled is not None:
                self._defaults.append({"loan": ident, "signalled_on": signalled,
                                       "triggers": ("days-past-due",), "cured_on": None,
                                       "probation_until": self._probation(signalled)})
            return loan

        def _probation(self, signalled):
            """The probation a signalled default carries: three months after it."""
            return self._dates.add_months(signalled, 3)

        def loans(self):
            """Every loan of the fixture, in the order it was built."""
            return tuple(self._loans)

        def loan(self, ident):
            """One loan record by id."""
            return self._by_id[ident]

        def payments(self, loan):
            """The payment rows of a loan."""
            return self._payments[_ident(loan)]

        def schedule(self, loan):
            """The loan's contractual flows, in the schedule's own shape."""
            return {"loan": _ident(loan), "flows": self._flows[_ident(loan)],
                    "principal_cents": 1000000, "rate_bp": 600, "term_months": 12,
                    "first_due": S5_LONG, "level_payment_cents": 100000}

        def defaults(self):
            """The fixture's signalled defaults, in the book's own shape."""
            return tuple(self._defaults)

        def status(self, loan, date):
            """The bank's own record for that date, with the exposure on the same read."""
            record = _want_ead(self, self._by_id[_ident(loan)], date, self._rules)
            record.update({"grade": "B", "dpd": 0, "bucket": "performing", "stage": 1,
                           "default": False, "cured": None, "ecl_cents": 0})
            self._stats["statuses"] = self._stats["statuses"] + 1
            return record

        @property
        def reporting_dates(self):
            """One month end a month, from the earliest origination, long enough to hold."""
            return tuple("2030-%02d-28" % (month,) for month in range(1, 13))

        def stats(self):
            """The fixture's own ledger: every counter a refused call must leave alone."""
            return dict(self._stats)

    def _toy_book(rules, dates):
        """The fixture: six segments, the floor and the cap both binding, by hand."""
        b = _ToyBook(rules, dates)
        # The aggregate ratio of this segment is 1166, while the mean of its three per-loan
        # ratios is 1666: the two readings of the contract are 500 basis points apart. CC-2
        # carries a flow due at its own origination, so measuring the drawdown against the
        # schedule rather than against the origination leaves a different numerator. CC-4
        # is paid after the date its default was signalled, so reading its probation date
        # where the signalled date belongs changes the numerator too.
        b.add("CC-1", "credit-card", 100000, "2030-01-31", ((S5_LONG, 100000),),
              (("2030-03-31", 40000, "instalment"),), signalled="2030-06-30")
        b.add("CC-2", "credit-card", 1000000, "2030-01-31",
              (("2030-01-31", 50000), (S5_LONG, 100000)),
              (("2030-02-28", 100000, "instalment"),), signalled="2030-06-30")
        b.add("CC-3", "credit-card", 1005, "2030-01-31", ((S5_LONG, 100000),), ())
        b.add("CC-4", "credit-card", 100000, "2030-01-31", ((S5_LONG, 100000),),
              (("2030-08-31", 60000, "instalment"),), signalled="2030-06-30")
        # Nothing undrawn at origination: the denominator is zero, not the numerator.
        b.add("CO-1", "consumer", 0, "2030-01-31", ((S5_LONG, 100000),),
              (("2030-03-31", 30000, "instalment"),), signalled="2030-06-30")
        # A prepayment larger than the instalments paid: the raw ratio is negative.
        b.add("MO-1", "mortgage", 100000, "2030-03-31", ((S5_LONG, 100000),),
              (("2030-01-31", 90000, "instalment"), ("2030-04-30", 100000, "prepayment")),
              signalled="2030-06-30")
        # One basis point below the cap: 9999 drawn against 10000 undrawn is not clamped.
        b.add("PO-1", "corporate", 10000, "2030-01-31", ((S5_LONG, 100000),),
              (("2030-03-31", 9999, "instalment"),), signalled="2030-06-30")
        # One basis point above the cap: 10001 of raw ratio, clamped down to the policy's.
        b.add("LE-1", "leasing", 10000, "2030-01-31", ((S5_LONG, 100000),),
              (("2030-03-31", 10001, "instalment"),), signalled="2030-06-30")
        # A segment that never defaulted at all.
        b.add("SM-1", "sme", 100000, "2030-01-31", ((S5_LONG, 100000),), ())
        # The undrawn limit, exactly at the limit, one cent above and one cent below. The
        # corporate segment converts at 9999 (PO-1 drew 9999 against 10000 undrawn), so a
        # cent of undrawn is worth nothing here and the drawn amount is what these rows
        # measure.
        b.add("PO-2", "corporate", 100000, "2030-01-31", ((S5_LONG, 100000),),
              (("2030-03-31", 100000, "instalment"),))
        b.add("PO-3", "corporate", 100000, "2030-01-31", ((S5_LONG, 100000),),
              (("2030-03-31", 100001, "instalment"),))
        b.add("PO-4", "corporate", 100000, "2030-01-31", ((S5_LONG, 100000),),
              (("2030-03-31", 99999, "instalment"),))
        # The plan moves on the day the schedule's own flow falls due, and not before.
        b.add("PO-5", "corporate", 50000, "2030-01-31",
              (("2030-06-30", 20000),), (("2030-05-31", 30000, "instalment"),))
        # A fee is not principal; a prepayment is taken off the drawn amount.
        b.add("PO-6", "corporate", 100000, "2030-01-31", ((S5_LONG, 100000),),
              (("2030-03-31", 40000, "instalment"), ("2030-03-31", 5000, "fee"),
               ("2030-04-30", 1000, "prepayment")))
        return b

    def _s5_constants(s, rules):
        assert tuple(s.EAD_KEYS) == S5_EAD_KEYS, (
            "an exposure is its loan, its date, what is drawn, what is undrawn, the "
            "segment's factor and the exposure itself, in that order, and EAD_KEYS was %r"
            % (tuple(s.EAD_KEYS),))
        assert s.CCF_FLOOR_BP == rules.CCF_FLOOR_BP == 0, (
            "the policy's floor for a conversion factor is the policy's zero, and the "
            "stage's CCF_FLOOR_BP was %r against the world's %r"
            % (s.CCF_FLOOR_BP, rules.CCF_FLOOR_BP))
        assert s.CCF_CAP_BP == rules.CCF_CAP_BP == 10000, (
            "the policy's cap for a conversion factor is the policy's whole, and the "
            "stage's CCF_CAP_BP was %r against the world's %r"
            % (s.CCF_CAP_BP, rules.CCF_CAP_BP))

    def _s5_readings(s, b, rules):
        """The drawn amount, the plan, the undrawn limit and the exposure, date by date."""
        assert b.loans(), "the book holds no loans to expose"
        watched = (b.reporting_dates[0], b.reporting_dates[12], b.reporting_dates[-1])
        for loan in b.loans():
            for date in watched:
                got = s.ead(b, loan, date)
                assert tuple(got.keys()) == tuple(s.EAD_KEYS), (
                    "%r's exposure has the fields %r rather than %r"
                    % (_ident(loan), tuple(got.keys()), tuple(s.EAD_KEYS)))
                want = _want_ead(b, loan, date, rules)
                assert got == want, (
                    "%r's exposure at %s is not the contract's reading of its payments: "
                    "got %r, wanted %r" % (_ident(loan), date, got, want))
                assert got["drawn_cents"] >= 0 and got["undrawn_cents"] >= 0, (
                    "neither the drawn amount nor the undrawn limit is ever negative, and "
                    "%r's exposure at %s was %r" % (_ident(loan), date, got))
                assert rules.CCF_FLOOR_BP <= got["ccf_bp"] <= rules.CCF_CAP_BP, (
                    "%r's factor at %s is outside the policy: %r"
                    % (_ident(loan), date, got["ccf_bp"]))
                assert got["ccf_bp"] == s.ccf(b, loan["segment"]), (
                    "%r's factor at %s is not its own segment's" % (_ident(loan), date))
                assert got["ead_cents"] >= got["drawn_cents"], (
                    "the exposure is never below what is drawn, and %r's was %r"
                    % (_ident(loan), got))
                bank = b.status(loan, date)
                assert got["ead_cents"] == bank["ead_cents"], (
                    "the bank recorded %r of exposure for %r at %s and the stage answered "
                    "%r" % (bank["ead_cents"], _ident(loan), date, got["ead_cents"]))

    def _s5_ccf(s, b, rules):
        """One aggregate ratio per segment, inside the policy, and the book's own segments."""
        for segment in rules.SEGMENTS:
            got = s.ccf(b, segment)
            assert isinstance(got, int) and not isinstance(got, bool), (
                "%s's factor is an integer count of basis points, and it was %r"
                % (segment, got))
            assert rules.CCF_FLOOR_BP <= got <= rules.CCF_CAP_BP, (
                "%s's factor is outside the policy: %r" % (segment, got))
            assert got == _want_ccf(b, segment, rules), (
                "%s's factor is not the ratio of the sums the contract pins: got %r, "
                "wanted %r" % (segment, got, _want_ccf(b, segment, rules)))
            assert got == s.ccf(b, segment), (
                "%s's factor answered differently the second time" % (segment,))

    def _s5_defaults(s, b, world, rules):
        """`ead_at_default` is the exposure at the date the book signalled the default."""
        by_id = dict((_ident(loan), loan) for loan in b.loans())
        signalled = tuple(b.defaults())
        assert signalled, "the book records no defaults to expose at default"
        for record in signalled:
            loan = by_id[record["loan"]]
            when = record["signalled_on"]
            got = s.ead_at_default(b, loan)
            want = s.ead(b, loan, when)["ead_cents"]
            assert got == want, (
                "%r's exposure at default is %r and its exposure at %s is %r"
                % (_ident(loan), got, when, want))
            assert got == _want_ead(b, loan, when, rules)["ead_cents"], (
                "%r's exposure at default is not the contract's reading: %r"
                % (_ident(loan), got))
            assert got >= _want_drawn(b, loan, when), (
                "%r's exposure at default is below what it had drawn" % (_ident(loan),))
        healthy = [loan for loan in b.loans() if _want_signalled(b, loan) is None]
        assert healthy, "the book holds no loan that never defaulted"
        for loan in healthy[:2]:
            _refuses(world.BookError, "%r's exposure at default" % (_ident(loan),),
                     lambda: s.ead_at_default(b, loan), [_ident(loan)])

    def _s5_toy(s, rules, dates, world):
        """The fixture: the floor and the cap on both sides, and the aggregate ratio."""
        b = _toy_book(rules, dates)
        for segment in rules.SEGMENTS:
            assert s.ccf(b, segment) == _want_ccf(b, segment, rules), (
                "the fixture's %s factor is recomputed as %r and the stage answered %r"
                % (segment, _want_ccf(b, segment, rules), s.ccf(b, segment)))
        assert s.ccf(b, "credit-card") == 1166, (
            "140000 drawn against 1200000 undrawn is 1166 basis points, while the mean of "
            "the three per-loan ratios is 1666, and the stage answered %r"
            % (s.ccf(b, "credit-card"),))
        assert s.ccf(b, "sme") == rules.CCF_FLOOR_BP, (
            "a segment that never defaulted answers the policy's floor, and sme answered %r"
            % (s.ccf(b, "sme"),))
        assert s.ccf(b, "consumer") == rules.CCF_FLOOR_BP, (
            "a segment whose defaults had nothing undrawn at origination answers the "
            "policy's floor rather than dividing by an empty limit, and consumer answered "
            "%r" % (s.ccf(b, "consumer"),))
        assert s.ccf(b, "mortgage") == rules.CCF_FLOOR_BP, (
            "a ratio below the floor clamps up to it, and mortgage answered %r"
            % (s.ccf(b, "mortgage"),))
        assert s.ccf(b, "corporate") == rules.CCF_CAP_BP - 1, (
            "9999 drawn against 10000 undrawn is one basis point inside the cap and is "
            "not clamped, and corporate answered %r" % (s.ccf(b, "corporate"),))
        assert s.ccf(b, "leasing") == rules.CCF_CAP_BP, (
            "10001 drawn against 10000 undrawn is one basis point above the cap and "
            "clamps down to it, and leasing answered %r" % (s.ccf(b, "leasing"),))
        for record in b.defaults():
            loan = b.loan(record["loan"])
            when = record["signalled_on"]
            got = s.ead_at_default(b, loan)
            assert got == _want_ead(b, loan, when, rules)["ead_cents"], (
                "%s's exposure at default is %r, and the contract's reading of the %s "
                "signalled date is %r" % (record["loan"], got, when,
                                          _want_ead(b, loan, when, rules)["ead_cents"]))
            assert got == s.ead(b, loan, when)["ead_cents"], (
                "%s's exposure at default is not its exposure at the signalled date"
                % (record["loan"],))
        for loan in b.loans():
            if _want_signalled(b, loan) is not None:
                continue
            _refuses(world.BookError, "%s's exposure at default" % (loan["loan"],),
                     lambda: s.ead_at_default(b, loan), [loan["loan"]])

    def _s5_boundaries(s, rules, dates):
        """Cents that move a boundary: a day, the limit, the plan and the truncation."""
        b = _toy_book(rules, dates)
        wanted = (
            # a payment counts on the day it arrived and not a day earlier
            ("CC-1", "2030-03-30", 0, 100000, 1166, 11660),
            ("CC-1", "2030-03-31", 40000, 60000, 1166, 46996),
            # the exposure truncates once, so 1005 * 1166 // 10000 is 117 and never 118
            ("CC-3", "2030-03-31", 0, 1005, 1166, 117),
            # the limit exactly: at it, one cent above it and one cent below it
            ("PO-2", "2030-03-31", 100000, 0, 9999, 100000),
            ("PO-3", "2030-03-31", 100001, 0, 9999, 100001),
            ("PO-4", "2030-03-31", 99999, 1, 9999, 99999),
            # the schedule's own plan moves on the day its flow falls due, and not before
            ("PO-5", "2030-06-29", 30000, 20000, 9999, 49998),
            ("PO-5", "2030-06-30", 30000, 40000, 9999, 69996),
            # a fee is not principal and a prepayment is taken off the drawn amount
            ("PO-6", "2030-03-31", 40000, 60000, 9999, 99994),
            ("PO-6", "2030-04-30", 39000, 61000, 9999, 99993),
            # the floor clamps the factor of a loan that repaid more than it drew
            ("MO-1", "2030-06-30", 0, 100000, 0, 0),
        )
        for ident, date, drawn, undrawn, rate, exposure in wanted:
            got = s.ead(b, b.loan(ident), date)
            assert got == {"loan": ident, "date": date, "drawn_cents": drawn,
                           "undrawn_cents": undrawn, "ccf_bp": rate,
                           "ead_cents": exposure}, (
                "%s at %s: got %r, wanted %r" % (ident, date, got,
                                                 {"drawn_cents": drawn,
                                                  "undrawn_cents": undrawn,
                                                  "ccf_bp": rate,
                                                  "ead_cents": exposure}))

    def _s5_refusals(s, b, world, dates, rules):
        """Every shape that cannot be the thing raises, naming what arrived."""
        loan = b.loans()[0]
        date = b.reporting_dates[-1]
        before = b.stats()
        _refuses(world.BookError, "a segment that is not one of the six",
                 lambda: s.ccf(b, "payday"), ["payday"])
        _refuses(dates.DateError, "a date that is not an ISO date",
                 lambda: s.ead(b, loan, "31/03/2031"), ["31/03/2031"])
        assert b.stats() == before, (
            "a refusal decided without asking the book left its ledger moved: %r became %r"
            % (before, b.stats()))
        _refuses(world.BookError, "a loan the book does not hold",
                 lambda: s.ead(b, {"loan": "no-such-loan"}, date), ["no-such-loan"])
        _refuses(world.BookError, "a loan the book does not hold, at default",
                 lambda: s.ead_at_default(b, {"loan": "no-such-loan"}), ["no-such-loan"])

    def _s5_twice(s, b, rules, dates):
        """The whole workload twice: a run is a function of its inputs and nothing else."""
        by_id = dict((_ident(loan), loan) for loan in b.loans())
        watch = (b.reporting_dates[0], b.reporting_dates[12], b.reporting_dates[-1])

        def workload():
            rows = []
            for loan in b.loans():
                for date in watch:
                    rows.append(s.ead(b, loan, date))
            rows.append(tuple(s.ccf(b, segment) for segment in rules.SEGMENTS))
            rows.append(tuple(s.ead_at_default(b, by_id[record["loan"]])
                              for record in b.defaults()))
            toy = _toy_book(rules, dates)
            for ident in ("CC-1", "CC-4", "PO-4", "PO-5", "MO-1", "LE-1"):
                for date in ("2030-03-31", "2030-06-30"):
                    rows.append(s.ead(toy, toy.loan(ident), date))
            return tuple(rows)

        assert workload() == workload(), (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import book as world
    import dates
    import rules
    import stage_05 as s
    assert dates.BASES == ("actual-365", "thirty-360"), (
        "the world's calendars moved under this check: %r" % (dates.BASES,))
    _s5_constants(s, rules)
    b = world.Book.build(7)
    _s5_readings(s, b, rules)
    _s5_ccf(s, b, rules)
    _s5_defaults(s, b, world, rules)
    _s5_toy(s, rules, dates, world)
    _s5_boundaries(s, rules, dates)
    _s5_refusals(s, b, world, dates, rules)
    _s5_twice(s, b, rules, dates)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    S6_SCENARIOS = ("base", "adverse", "upside")

    S6_WEIGHTS_BP = {"base": 5000, "adverse": 2500, "upside": 2500}

    S6_MULTIPLIER_BP = {"base": 10000, "adverse": 18000, "upside": 7000}

    S6_WEIGHTS_BP_ALT = {"base": 0, "adverse": 10000, "upside": 0}

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("book.py", "course.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked against the
        message: an exception of the right family raised for the wrong reason is not the
        refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _loans(book):
        """The book's own loans, in the book's own order."""
        loans = book.loans
        return tuple(loans() if callable(loans) else loans)

    def _dates(book):
        """The reporting dates the book covers."""
        dates = book.reporting_dates
        return tuple(dates() if callable(dates) else dates)

    def _rows(book):
        """Every model artifact the book holds, in the book's own order."""
        models = book.models
        return tuple(models() if callable(models) else models)

    def _loan_id(loan):
        """The identifier the book's records key a loan by."""
        return loan["loan"]

    def _in_force(book, date):
        """The contract's own rule, recomputed: greatest `as_of` not after the date.

        A tie is broken by the greater `version`, which is the whole reason two versions of
        one artifact can both answer for a date.
        """
        rows = [row for row in _rows(book) if row["as_of"] <= date]
        assert rows, "the book holds no artifact in force at %r" % (date,)
        newest = max(row["as_of"] for row in rows)
        rows = [row for row in rows if row["as_of"] == newest]
        return max(rows, key=lambda row: row["version"])

    def _want_pd(series, months):
        """The pinned reading of an artifact's per-year cumulative PD series, in months.

        The series is cumulative, so the months are read linearly between the two years they
        fall between, truncated; a horizon past the artifact's last entry is that entry.
        """
        whole = months // 12
        rest = months - whole * 12
        if whole >= len(series):
            return series[-1]
        if whole == 0:
            return series[0] * months // 12
        left = series[whole - 1]
        if rest == 0:
            return left
        return left + (series[whole] - left) * rest // 12

    def _want_scenario_pd(model, grade, months, scenario, multipliers):
        """The artifact's PD over the horizon, scaled by the scenario's multiplier and capped."""
        pd_bp = _want_pd(model["pd_bp"][grade], months) * multipliers[scenario] // 10000
        return min(pd_bp, 10000)

    def _want_present(rules, amount_cents, rate_bp, basis, steps):
        """The contract's stepwise discounting, recomputed: one truncated factor per period."""
        period = rules.period_rate(rate_bp, basis)
        factor = 10000
        total = 0
        for _ in range(steps):
            factor = factor * 10000 // (10000 + period)
            total += amount_cents * factor // 10000
        return total

    def _facts(w, book, loan, date):
        """What one loan's provision at one date is made of, recomputed from the book.

        The remaining flows, the rate that discounts and the exposure come from the stages
        that own them; the record is the bank's own answer for the stage and the default.
        """
        flows = w["s1"].schedule(book, loan)["flows"]
        return {"record": book.status(loan, date),
                "remaining": tuple(flow for flow in flows if flow["date"] > date),
                "rate": w["s1"].effective_rate(book, loan),
                "exposure": w["s5"].ead(book, loan, date)}

    def _want_ecl(w, s, book, loan, date, scenario, model, stage, facts, ccf_bp=None):
        """The contract's ECL for one pair, recomputed end to end in the pinned order.

        `ccf_bp` is the artifact's own CCF where the caller supplied an artifact: the
        contract replaces stage 5's estimated factor with the artifact's own one and leaves
        everything else — the two products, the horizon, the discount — exactly where it was.
        """
        record = facts["record"]
        grade = model["grades"][_loan_id(loan)]
        horizon = (w["rules"].PERIODS_PER_YEAR if stage == 1
                   else len(facts["remaining"]))
        pd_bp = _want_scenario_pd(model, grade, horizon, scenario,
                                  s.SCENARIO_PD_MULTIPLIER_BP)
        if record["default"]:
            lgd_bp = w["s4"].lgd(book, loan)["lgd_bp"]
        else:
            lgd_bp = model["lgd_bp"][grade]
        if ccf_bp is None:
            ead_cents = facts["exposure"]["ead_cents"]
        else:
            ead_cents = (facts["exposure"]["drawn_cents"]
                         + facts["exposure"]["undrawn_cents"] * ccf_bp // 10000)
        loss_cents = pd_bp * lgd_bp // 10000 * ead_cents // 10000
        if stage == 1:
            cents = _want_present(w["rules"], loss_cents, facts["rate"]["eir_bp"],
                                  facts["rate"]["basis"], 1)
        elif not facts["remaining"]:
            cents = 0
        else:
            cents = _want_present(w["rules"], loss_cents // len(facts["remaining"]),
                                  facts["rate"]["eir_bp"], facts["rate"]["basis"],
                                  len(facts["remaining"]))
        return {"loan": _loan_id(loan), "date": date, "stage": stage,
                "horizon_months": horizon, "pd_bp": pd_bp, "lgd_bp": lgd_bp,
                "ead_cents": ead_cents, "ecl_cents": cents, "scenario": scenario}

    def _s6_constants(s, rules):
        """The two key tuples and the policy's own tables, exactly as the contract writes them."""
        assert tuple(s.ECL_KEYS) == ("loan", "date", "stage", "horizon_months", "pd_bp",
                                     "lgd_bp", "ead_cents", "ecl_cents", "scenario"), (
            "ECL_KEYS is %r, and the provision's fields are pinned in order" % (s.ECL_KEYS,))
        assert tuple(s.WEIGHTED_KEYS) == ("loan", "date", "scenario_ecls", "weights_bp",
                                          "weighted_cents"), (
            "WEIGHTED_KEYS is %r, and the weighted provision's fields are pinned"
            % (s.WEIGHTED_KEYS,))
        assert tuple(s.SCENARIOS) == S6_SCENARIOS, (
            "SCENARIOS is %r, and the policy's order is %r" % (s.SCENARIOS, S6_SCENARIOS))
        assert tuple(s.SCENARIOS) == tuple(rules.SCENARIOS), (
            "the stage prints the scenarios as %r and the policy holds %r"
            % (s.SCENARIOS, rules.SCENARIOS))
        assert dict(s.SCENARIO_WEIGHTS_BP) == S6_WEIGHTS_BP, (
            "SCENARIO_WEIGHTS_BP is %r, and the policy's weights are %r"
            % (s.SCENARIO_WEIGHTS_BP, S6_WEIGHTS_BP))
        assert dict(s.SCENARIO_WEIGHTS_BP) == dict(rules.SCENARIO_WEIGHTS_BP), (
            "the stage's weights are not the policy's: %r versus %r"
            % (s.SCENARIO_WEIGHTS_BP, rules.SCENARIO_WEIGHTS_BP))
        assert dict(s.SCENARIO_PD_MULTIPLIER_BP) == S6_MULTIPLIER_BP, (
            "SCENARIO_PD_MULTIPLIER_BP is %r, and the policy's multipliers are %r"
            % (s.SCENARIO_PD_MULTIPLIER_BP, S6_MULTIPLIER_BP))
        assert dict(s.SCENARIO_PD_MULTIPLIER_BP) == dict(rules.SCENARIO_PD_MULTIPLIER_BP), (
            "the stage's PD multipliers are not the policy's: %r versus %r"
            % (s.SCENARIO_PD_MULTIPLIER_BP, rules.SCENARIO_PD_MULTIPLIER_BP))
        assert sum(s.SCENARIO_WEIGHTS_BP[scenario] for scenario in s.SCENARIOS) == 10000, (
            "the policy's weights sum to %r"
            % (sum(s.SCENARIO_WEIGHTS_BP.values()),))

    def _s6_stage(record):
        """The stage the bank's record carries, as a number."""
        stage = record["stage"]
        return int(stage) if isinstance(stage, str) else stage

    def _s6_answers(s, w, book):
        """Every provision of every loan, date and scenario, against this check's own arithmetic."""
        answers = []
        for loan in _loans(book):
            for date in _dates(book):
                facts = _facts(w, book, loan, date)
                stage = _s6_stage(facts["record"])
                model = _in_force(book, date)
                for scenario in s.SCENARIOS:
                    answer = s.ecl(book, loan, date, scenario)
                    want = _want_ecl(w, s, book, loan, date, scenario, model, stage, facts)
                    assert answer == want, (
                        "the provision for %s at %s under %r is\n  %r\nand the contract's "
                        "arithmetic, recomputed here, is\n  %r"
                        % (_loan_id(loan), date, scenario, answer, want))
                    if facts["exposure"]["ead_cents"] == 0:
                        assert answer["ecl_cents"] == 0, (
                            "%s has no exposure at %s and the stage provisions %r"
                            % (_loan_id(loan), date, answer["ecl_cents"]))
                    answers.append(answer)
        return tuple(answers)

    def _s6_stub(s, book):
        """The stage's own two answers first: a template reports itself, not the world's stages."""
        loan = _loans(book)[0]
        date = _dates(book)[-1]
        s.ecl(book, loan, date, s.SCENARIOS[0])
        s.weighted_ecl(book, loan, date)

    def _s6_book(s, w, book):
        """The bank's own record is the answer key: the weighted provision and the exposure."""
        counted = 0
        for loan in _loans(book):
            for date in _dates(book):
                record = book.status(loan, date)
                weighted = s.weighted_ecl(book, loan, date)
                cents = []
                for scenario in s.SCENARIOS:
                    answer = s.ecl(book, loan, date, scenario)
                    assert answer["stage"] == _s6_stage(record), (
                        "%s at %s provisions in stage %r and the book records %r"
                        % (_loan_id(loan), date, answer["stage"], record["stage"]))
                    cents.append(answer["ecl_cents"])
                assert weighted["loan"] == _loan_id(loan) and weighted["date"] == date, (
                    "the weighted provision for %s at %s names %r at %r"
                    % (_loan_id(loan), date, weighted["loan"], weighted["date"]))
                assert tuple(weighted["scenario_ecls"]) == tuple(cents), (
                    "the weighted provision for %s at %s holds %r and the scenarios answer "
                    "%r in the policy's own order"
                    % (_loan_id(loan), date, weighted["scenario_ecls"], tuple(cents)))
                weights = tuple(s.SCENARIO_WEIGHTS_BP[scenario] for scenario in s.SCENARIOS)
                assert tuple(weighted["weights_bp"]) == weights, (
                    "the weighted provision for %s at %s weights the scenarios %r"
                    % (_loan_id(loan), date, weighted["weights_bp"]))
                want = 0
                for ecl_cents, weight_bp in zip(cents, weights):
                    want += ecl_cents * weight_bp // 10000
                assert weighted["weighted_cents"] == want, (
                    "the weighted provision for %s at %s is %r, and each product truncated "
                    "before it is added gives %r"
                    % (_loan_id(loan), date, weighted["weighted_cents"], want))
                assert weighted["weighted_cents"] == record["ecl_cents"], (
                    "the bank recorded an ECL of %r for %s at %s and the stage weights it to "
                    "%r (base %r, scenarios %r)"
                    % (record["ecl_cents"], _loan_id(loan), date,
                       weighted["weighted_cents"], cents[0], tuple(cents)))
                base = s.ecl(book, loan, date, "base")
                assert base["ead_cents"] == record["ead_cents"], (
                    "stage 5's exposure for %s at %s is %r and the bank recorded %r"
                    % (_loan_id(loan), date, base["ead_cents"], record["ead_cents"]))
                counted += 1
        assert counted == len(_loans(book)) * len(_dates(book)), (
            "%d pairs walked, and the book holds %d loans over %d reporting dates"
            % (counted, len(_loans(book)), len(_dates(book))))

    def _s6_tie_break(s, w):
        """Two versions of one artifact that share an `as_of`: the greater version is in force."""
        blank = {"name": "synthetic", "grades": {}, "pd_bp": {}, "lgd_bp": {}, "ccf_bp": {}}
        early = dict(blank, version=1, as_of="2031-01-31")
        later = dict(blank, version=3, as_of="2032-01-31")
        tie = dict(blank, version=2, as_of="2032-01-31")

        class _Roster(object):
            """A book stand-in carrying nothing but a roster: the rule needs no more."""

            def __init__(self, models):
                self.models = models

        assert s._in_force(_Roster((early, later, tie)), "2033-12-31")["version"] == 3, (
            "the artifact with the greatest `as_of` not after the date is in force")
        assert s._in_force(_Roster((tie, later)), "2033-12-31")["version"] == 3, (
            "two versions that share an `as_of` are broken by the greater version, not by "
            "their place on the shelf")
        assert s._in_force(_Roster((early, later, tie)), "2031-06-30")["version"] == 1, (
            "an artifact written after the date is not in force yet")
        _refuses(w["book"].BookError, "a date before any artifact was written",
                 lambda: s._in_force(_Roster((early, later, tie)), "2030-01-01"),
                 ["2030-01-01"])

    def _s6_horizon(s, w, book):
        """The stage's own horizon, measured: twelve months performing, the remaining life after."""
        spread = 0
        for loan in _loans(book):
            flows = w["s1"].schedule(book, loan)["flows"]
            for date in _dates(book):
                stage = _s6_stage(book.status(loan, date))
                answer = s.ecl(book, loan, date, "base")
                if stage == 1:
                    assert answer["horizon_months"] == w["rules"].PERIODS_PER_YEAR, (
                        "a stage 1 loan measures %r months of horizon at %s, and the policy "
                        "says %d" % (answer["horizon_months"], date,
                                     w["rules"].PERIODS_PER_YEAR))
                    continue
                after = sum(1 for flow in flows if flow["date"] > date)
                due = sum(1 for flow in flows if flow["date"] == date)
                assert answer["horizon_months"] == after, (
                    "%s in stage %d at %s has %d periods strictly after the date (%d of them "
                    "due that day) and the stage measures %r"
                    % (_loan_id(loan), stage, date, after, due, answer["horizon_months"]))
                if after >= 2:
                    spread += 1
        assert spread, ("no loan of the book has more than one period left in stage 2 or 3, so "
                        "a lifetime loss spread over its remaining periods is not exercised")

    def _s6_overrides(s, w, book):
        """`stage=` moves the horizon and nothing else; `model=` moves the artifact, CCF included."""
        rows = _rows(book)
        names = {}
        for row in rows:
            names.setdefault(row["name"], []).append(row)
        twinned = [group for group in names.values() if len(group) > 1]
        assert twinned, ("the book holds no two versions of one artifact name, so an artifact "
                         "swap cannot be exercised")
        old, new = sorted(twinned[0], key=lambda row: row["version"])[:2]
        date = _dates(book)[-1]
        in_force = _in_force(book, date)
        assert in_force["version"] == new["version"], (
            "the artifact in force at %s is %r and the newer version of %r is %r"
            % (date, in_force["version"], new["name"], new["version"]))
        swapped = staged = exposed = different = moved = 0
        for loan in _loans(book):
            facts = _facts(w, book, loan, date)
            stage = _s6_stage(facts["record"])
            answer = s.ecl(book, loan, date, "base")
            for model in (old, new):
                counter = s.ecl(book, loan, date, "base", model=model)
                want = _want_ecl(w, s, book, loan, date, "base", model, stage, facts,
                                 ccf_bp=model["ccf_bp"][loan["segment"]])
                assert counter == want, (
                    "the provision for %s at %s under the artifact %s %s is\n  %r\nand the "
                    "contract's arithmetic is\n  %r"
                    % (_loan_id(loan), date, model["name"], model["version"], counter, want))
            if (old["pd_bp"][new["grades"][_loan_id(loan)]]
                    != new["pd_bp"][new["grades"][_loan_id(loan)]]):
                swapped += 1
            if facts["exposure"]["undrawn_cents"] > 0:
                exposed += 1
                if facts["exposure"]["ccf_bp"] != old["ccf_bp"][loan["segment"]]:
                    different += 1
            if stage != 1:
                forced = s.ecl(book, loan, date, "base", stage=1)
                want = _want_ecl(w, s, book, loan, date, "base", in_force, 1, facts)
                assert forced == want, (
                    "forcing stage 1 for %s at %s answers\n  %r\nand the contract's "
                    "arithmetic is\n  %r" % (_loan_id(loan), date, forced, want))
                assert forced["horizon_months"] == w["rules"].PERIODS_PER_YEAR, (
                    "a forced stage 1 measures %r months" % (forced["horizon_months"],))
                if (len(facts["remaining"]) != w["rules"].PERIODS_PER_YEAR
                        and answer["ecl_cents"] > 0):
                    assert forced["ecl_cents"] != answer["ecl_cents"], (
                        "forcing stage 1 for %s at %s moved nothing: %r"
                        % (_loan_id(loan), date, forced["ecl_cents"]))
                    moved += 1
                staged += 1
            if facts["record"]["default"]:
                assert s.ecl(book, loan, date, "base", stage=1)["lgd_bp"] == \
                    w["s4"].lgd(book, loan)["lgd_bp"], (
                    "a defaulted loan's loss given default follows the record's default flag "
                    "and not the forced stage: %s" % (_loan_id(loan),))
        paired = s.weighted_ecl(book, _loans(book)[0], date, stage=1, model=old)
        counters = tuple(s.ecl(book, _loans(book)[0], date, scenario, stage=1, model=old)
                         ["ecl_cents"] for scenario in s.SCENARIOS)
        assert tuple(paired["scenario_ecls"]) == counters, (
            "the weighted provision under a counterfactual stage and artifact holds %r and the "
            "scenarios answer %r" % (paired["scenario_ecls"], counters))
        assert paired["weighted_cents"] == sum(
            cents * weight // 10000
            for cents, weight in zip(counters, paired["weights_bp"])), (
            "the counterfactual weighting of %s is %r"
            % (_loan_id(_loans(book)[0]), paired))
        assert swapped, ("the two versions of %s do not differ on this book's loans, so an "
                         "artifact swap cannot be exercised" % (new["name"],))
        assert staged, ("no loan of the book is outside stage 1 at %s, so a forced stage "
                        "cannot be exercised" % (date,))
        assert exposed, ("no loan of the book has an undrawn part at %s, so the artifact's "
                         "own CCF cannot be exercised" % (date,))
        assert different, ("no loan's artifact CCF differs from the one the book observed at "
                           "%s, so a counterfactual CCF cannot be exercised" % (date,))
        assert moved, ("forcing stage 1 never moved a provision at %s, so the stage argument "
                       "cannot be exercised" % (date,))

    def _s6_boundaries(s, w, book):
        """The cap, the weights and the policy's own tables, on both sides of their bounds."""
        loan = _loans(book)[0]
        date = _dates(book)[-1]
        facts = _facts(w, book, loan, date)
        stage = _s6_stage(facts["record"])
        model = _in_force(book, date)
        grade = model["grades"][_loan_id(loan)]
        horizon = (w["rules"].PERIODS_PER_YEAR if stage == 1
                   else len(facts["remaining"]))
        pd_bp = _want_pd(model["pd_bp"][grade], horizon)
        keep = dict(s.SCENARIO_PD_MULTIPLIER_BP)
        keep_weights = dict(s.SCENARIO_WEIGHTS_BP)
        try:
            if pd_bp > 0:
                edge = 10000 * 10000 // pd_bp
                for multiplier in (edge - 1, edge, edge + 1, edge + 10000):
                    s.SCENARIO_PD_MULTIPLIER_BP = dict(keep, base=multiplier)
                    answer = s.ecl(book, loan, date, "base")
                    want = _want_ecl(w, s, book, loan, date, "base", model, stage, facts)
                    assert answer == want, (
                        "a %r PD multiplier for %s at %s answers\n  %r\nand the contract's "
                        "arithmetic, cap included, is\n  %r"
                        % (multiplier, _loan_id(loan), date, answer, want))
                s.SCENARIO_PD_MULTIPLIER_BP = dict(keep, base=edge + 10000)
                stressed = s.ecl(book, loan, date, "base")["pd_bp"]
                assert stressed == w["rules"].DISCOUNT_SCALE, (
                    "a scenario can stress a probability but not past certainty: %r"
                    % (stressed,))
            s.SCENARIO_PD_MULTIPLIER_BP = dict(keep, base=keep["base"])
            s.SCENARIO_WEIGHTS_BP = dict(S6_WEIGHTS_BP_ALT)
            weighted = s.weighted_ecl(book, loan, date)
            adverse = s.ecl(book, loan, date, "adverse")["ecl_cents"]
            assert tuple(weighted["weights_bp"]) == (0, 10000, 0), (
                "the policy's weights are read at call time and were not: %r"
                % (weighted["weights_bp"],))
            assert weighted["weighted_cents"] == adverse, (
                "a policy that weights the adverse scenario alone weights the provision to "
                "%r, not %r" % (adverse, weighted["weighted_cents"]))
            s.SCENARIO_WEIGHTS_BP = dict(keep_weights, base=4000)
            before = dict(book.stats())
            _refuses(w["book"].BookError, "a policy whose weights do not add up",
                     lambda: s.weighted_ecl(book, loan, date), ["9000"])
            assert dict(book.stats()) == before, (
                "a refused weighting asked the book for something: %r" % (book.stats(),))
            s.SCENARIO_WEIGHTS_BP = {"base": 5000, "adverse": 5000}
            _refuses(w["book"].BookError, "a policy with no weight for a scenario",
                     lambda: s.weighted_ecl(book, loan, date), ["upside"])
            s.SCENARIO_WEIGHTS_BP = {"base": 10000}
            s.SCENARIO_PD_MULTIPLIER_BP = {"base": 10000}
            _refuses(w["book"].BookError, "a policy with no multiplier for a scenario",
                     lambda: s.ecl(book, loan, date, "adverse"), ["adverse"])
        finally:
            s.SCENARIO_WEIGHTS_BP = keep_weights
            s.SCENARIO_PD_MULTIPLIER_BP = keep

    def _s6_refusals(s, w, book):
        """Every refusal names its offender, and the argument-only ones cost the book nothing."""
        loan = _loans(book)[0]
        date = _dates(book)[-1]
        before = dict(book.stats())
        _refuses(w["book"].BookError, "a scenario outside the policy",
                 lambda: s.ecl(book, loan, date, "stress"), ["stress"])
        assert dict(book.stats()) == before, (
            "a refused scenario asked the book for something: %r" % (book.stats(),))
        _refuses(w["book"].BookError, "a stage outside the three",
                 lambda: s.ecl(book, loan, date, "base", stage=4), ["4"])
        assert dict(book.stats()) == before, (
            "a refused stage asked the book for something: %r" % (book.stats(),))
        _refuses(w["book"].BookError, "a loan the book does not hold",
                 lambda: s.ecl(w["book"].Book.build(7), {"loan": "L-9999"}, date, "base"),
                 ["L-9999"])
        row = _in_force(book, date)
        unrated = {"name": row["name"], "version": row["version"], "as_of": row["as_of"],
                   "grades": {}, "pd_bp": row["pd_bp"], "lgd_bp": row["lgd_bp"],
                   "ccf_bp": row["ccf_bp"]}
        _refuses(w["book"].BookError, "an artifact that does not rate the loan",
                 lambda: s.ecl(book, loan, date, "base", model=unrated),
                 [_loan_id(loan)])
        after = dict(book.stats())
        for key in after:
            assert after[key] >= before[key], (
                "the book's %s count fell from %r to %r over one pass"
                % (key, before[key], after[key]))
        assert any(after[key] > before[key] for key in after), (
            "a whole pass of the stage asked the book for nothing: %r" % (after,))

    def _s6_twice(s, w, book):
        """Two runs of one workload answer equal: a provision is a function of its arguments."""
        def workload():
            answers = []
            for loan in _loans(book):
                for date in _dates(book):
                    for scenario in s.SCENARIOS:
                        answers.append(s.ecl(book, loan, date, scenario))
                    answers.append(s.weighted_ecl(book, loan, date))
            return tuple(answers)

        one = workload()
        assert one == workload(), (
            "two runs of one workload answered differently, so a provision is not a function "
            "of its arguments")

    import book as world_book
    import dates as world_dates
    import rules as world_rules
    import stage_01 as one
    import stage_04 as four
    import stage_05 as five
    import stage_06 as s
    w = {"book": world_book, "dates": world_dates, "rules": world_rules,
         "s1": one, "s4": four, "s5": five}
    _s6_constants(s, world_rules)
    book = world_book.Book.build(7)
    _s6_stub(s, book)
    _s6_answers(s, w, book)
    _s6_tie_break(s, w)
    _s6_book(s, w, book)
    _s6_horizon(s, w, book)
    _s6_overrides(s, w, book)
    _s6_boundaries(s, w, book)
    _s6_refusals(s, w, book)
    _s6_twice(s, w, book)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    C7_STAGE_KEYS = ("loan", "date", "stage", "reason", "sicr", "pd_bp", "origination_pd_bp")

    C7_TRANSFER_KEYS = ("loan", "date", "from_stage", "to_stage", "reason")

    C7_REASONS = ("credit-impaired", "significant-increase", "days-past-due",
                  "no-significant-increase", "return-not-yet")

    C7_GRADES = ("A", "B", "C", "D", "E", "F", "default")

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "book.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _keys_of(record, keys, what):
        """The record's fields in the order the contract prints them."""
        assert isinstance(record, dict), "%s is %r, not a record" % (what, record)
        assert tuple(record) == tuple(keys), (
            "%s's fields are %r, not %r" % (what, tuple(record), tuple(keys)))
        return record

    def _c7_pd(series, months):
        """The contract's reading of a yearly cumulative series, recomputed here.

        Whole years are read off the series, a horizon inside the first year is
        proportioned, a horizon between two years is interpolated in months and
        truncated, and a horizon past the end is the series' own last figure.
        """
        years = months // 12
        if years >= len(series):
            return series[-1]
        rest = months - 12 * years
        if years == 0:
            return series[0] * months // 12
        if rest == 0:
            return series[years - 1]
        return series[years - 1] + (series[years] - series[years - 1]) * rest // 12

    def _c7_in_force(b, date):
        """The artifact in force at a date, recomputed from the book's own list."""
        best = None
        for model in b.models:
            if model["as_of"] > date:
                continue
            if best is None or (model["as_of"], model["version"]) > (best["as_of"],
                                                                     best["version"]):
                best = model
        assert best is not None, "the book leaves %s with no model in force" % (date,)
        return best

    def _c7_months(b, loan, date):
        """The loan's remaining life at a date: its flows strictly after it."""
        return sum(1 for flow in b.schedule(loan)["flows"] if flow["date"] > date)

    def _c7_want(b, loan, date, model=None):
        """The check's own two-part test: `(months, current_bp, origination_bp, sicr)`."""
        model = model if model is not None else _c7_in_force(b, date)
        months = _c7_months(b, loan, date)
        current = _c7_pd(model["pd_bp"][b.grade(loan, date)], months)
        origination = _c7_pd(model["pd_bp"][loan["grade_origination"]], months)
        fired = (current * 10000 >= origination * 20000
                 or current - origination >= 300)
        return months, current, origination, fired

    def _c7_toy(b, current_grade, origination_grade, current_bp, origination_bp):
        """An artifact the check builds: a flat yearly series per grade, its own edges."""
        table = {}
        for grade in C7_GRADES:
            table[grade] = (1000, 1000, 1000, 1000)
        table[origination_grade] = (origination_bp,) * 4
        table[current_grade] = (current_bp,) * 4
        return {"name": "toy", "version": 1, "as_of": "1999-12-31", "grades": {},
                "pd_bp": table, "lgd_bp": {}, "ccf_bp": {}}

    def _c7_fixture(b):
        """A loan and a date with a whole-year horizon, its grade no longer its first."""
        for loan in b.loans:
            for date in b.reporting_dates:
                if _c7_months(b, loan, date) < 12:
                    continue
                if b.grade(loan, date) != loan["grade_origination"]:
                    return loan, date
        raise AssertionError("the book holds no loan whose grade moved by a whole year")

    def _c7_maze(s, b):
        """Every staging of every loan at every reporting date, asked once."""
        return dict(((loan["loan"], date), s.stage(b, loan, date))
                    for loan in b.loans for date in b.reporting_dates)

    def _c7_constants(s, policy):
        """The two key orders and the four policy figures the stage has to read."""
        assert tuple(s.STAGE_KEYS) == C7_STAGE_KEYS, (
            "the staging's fields are %r, not %r" % (tuple(s.STAGE_KEYS), C7_STAGE_KEYS))
        assert tuple(s.TRANSFER_KEYS) == C7_TRANSFER_KEYS, (
            "the transfer's fields are %r, not %r"
            % (tuple(s.TRANSFER_KEYS), C7_TRANSFER_KEYS))
        assert s.SICR_MULTIPLIER_BP == policy.SICR_MULTIPLIER_BP, (
            "the multiplier is %r, not %r" % (s.SICR_MULTIPLIER_BP,
                                              policy.SICR_MULTIPLIER_BP))
        assert s.SICR_ABSOLUTE_BP == policy.SICR_ABSOLUTE_BP, (
            "the absolute rise is %r, not %r" % (s.SICR_ABSOLUTE_BP,
                                                 policy.SICR_ABSOLUTE_BP))
        assert s.SICR_DAYS_PAST_DUE == policy.SICR_DAYS_PAST_DUE, (
            "the backstop is %r, not %r" % (s.SICR_DAYS_PAST_DUE,
                                            policy.SICR_DAYS_PAST_DUE))
        assert s.SICR_RETURN_PERIODS == policy.SICR_RETURN_PERIODS, (
            "the quiet reporting dates are %r, not %r" % (s.SICR_RETURN_PERIODS,
                                                          policy.SICR_RETURN_PERIODS))
        assert s.SICR_DAYS_PAST_DUE < policy.DEFAULT_DAYS_PAST_DUE, (
            "the staging backstop %r is not below the default backstop %r"
            % (s.SICR_DAYS_PAST_DUE, policy.DEFAULT_DAYS_PAST_DUE))

    def _c7_history(s, b, world, policy, maze):
        """Every staging is the bank's own, and the record's fields are the test's."""
        report = list(b.reporting_dates)
        seen = {1: 0, 2: 0, 3: 0}
        waits = crossings = rated = 0
        for loan in b.loans:
            for date in report:
                record = _keys_of(maze[(loan["loan"], date)], s.STAGE_KEYS,
                                  "%r at %s" % (loan["loan"], date))
                bank = b.status(loan, date)
                assert record["loan"] == loan["loan"], (
                    "a staging answers for %r" % (record["loan"],))
                assert record["date"] == date, (
                    "a staging is dated %r" % (record["date"],))
                assert record["stage"] in (1, 2, 3), (
                    "%r is stage %r, and there are three"
                    % (loan["loan"], record["stage"]))
                assert record["stage"] == bank["stage"], (
                    "%r at %s is stage %r in the record and %r in the bank's own"
                    % (loan["loan"], date, record["stage"], bank["stage"]))
                assert isinstance(record["sicr"], bool), (
                    "the test answered %r, which is not a verdict" % (record["sicr"],))
                assert record["reason"] in C7_REASONS or record["reason"] in policy.UTP_FLAGS, (
                    "%r's reason is %r, which is not what fired"
                    % (loan["loan"], record["reason"]))
                months, current, origination, fired = _c7_want(b, loan, date)
                assert record["pd_bp"] == current, (
                    "%r at %s printed %r basis points and the artifact gives %r over %r "
                    "months" % (loan["loan"], date, record["pd_bp"], current, months))
                assert record["origination_pd_bp"] == origination, (
                    "%r at %s started at %r basis points, not %r"
                    % (loan["loan"], date, record["origination_pd_bp"], origination))
                assert record["sicr"] is fired, (
                    "%r at %s answered %r to a test the contract makes %r"
                    % (loan["loan"], date, record["sicr"], fired))
                assert s.sicr(b, loan, date) is fired, (
                    "%r at %s's own verdict is not the record's" % (loan["loan"], date))
                if record["stage"] == 3:
                    assert bank["default"], (
                        "%r is stage 3 at %s and the book does not record a default"
                        % (loan["loan"], date))
                if record["reason"] == "credit-impaired":
                    assert record["stage"] == 3, (
                        "a credit-impaired record is not stage 3: %r" % (record,))
                if record["reason"] == "no-significant-increase":
                    assert record["stage"] == 1, (
                        "a record with no significant increase is not stage 1: %r"
                        % (record,))
                if record["reason"] == "return-not-yet":
                    assert record["stage"] == 2, (
                        "a loan waiting out the return is not in stage 2: %r" % (record,))
                if record["reason"] == "days-past-due":
                    assert record["stage"] == 2, (
                        "a backstop record is not stage 2: %r" % (record,))
                if record["reason"] in policy.UTP_FLAGS:
                    assert record["stage"] == 2, (
                        "a flag record is not stage 2: %r" % (record,))
                if record["reason"] == "significant-increase":
                    assert record["stage"] == 2 and record["sicr"], (
                        "a significant increase that is not stage 2: %r" % (record,))
                if not bank["default"] and record["sicr"]:
                    assert record["reason"] == "significant-increase", (
                        "%r's test fired at %s and the record says %r instead"
                        % (loan["loan"], date, record["reason"]))
                seen[record["stage"]] += 1
                if record["reason"] == "return-not-yet":
                    waits += 1
                if record["reason"] == "days-past-due":
                    crossings += 1
                if record["reason"] == "significant-increase":
                    rated += 1
        assert seen[1] and seen[2] and seen[3], (
            "the book holds all three regimes, and it showed %r" % (seen,))
        assert waits >= 1, (
            "the book holds a loan that came back after its quiet reporting dates, and "
            "no record waited (%r)" % (seen,))
        assert crossings >= 1, (
            "the book holds a loan past the days-past-due backstop, and none was (%r)"
            % (seen,))
        assert rated >= 1, (
            "the test is the point of the stage, and no loan was rated into stage 2 (%r)"
            % (seen,))

    def _c7_boundaries(s, b, world):
        """Both sides of each half of the test, on artifacts the check builds."""
        loan, date = _c7_fixture(b)
        now = b.grade(loan, date)
        started = loan["grade_origination"]
        cases = ((200, 100, True, "the multiplier at exactly twice"),
                 (199, 100, False, "the multiplier one basis point under"),
                 (1300, 1000, True, "the absolute rise at exactly three hundred"),
                 (1299, 1000, False, "the absolute rise one basis point under"),
                 (1000, 1000, False, "a loan that has not moved"),
                 (1000, 1300, False, "a loan that improved"))
        for current_bp, origination_bp, want, what in cases:
            toy = _c7_toy(b, now, started, current_bp, origination_bp)
            months, cur, orig, fired = _c7_want(b, loan, date, toy)
            assert (cur, orig) == (current_bp, origination_bp), (
                "the check's own reader gave %r and %r for a flat series" % (cur, orig))
            assert s.sicr(b, loan, date, model=toy) is want, (
                "%s at %r over %s months is %r, and the stage said otherwise"
                % (what, (cur, orig), months, want))
            record = _keys_of(s.stage(b, loan, date, model=toy), s.STAGE_KEYS,
                              "a staging under a built artifact")
            assert record["sicr"] is want, (
                "%s: the record's verdict moved with the model" % (what,))
            assert record["pd_bp"] == current_bp, (
                "%s: the record printed %r basis points under that artifact"
                % (what, record["pd_bp"]))
            assert record["origination_pd_bp"] == origination_bp, (
                "%s: the record printed %r as the origination figure"
                % (what, record["origination_pd_bp"]))
        calm = _c7_toy(b, now, started, 1000, 1000)
        lit = _c7_toy(b, now, started, 1300, 1000)
        assert s.sicr(b, loan, date, model=calm) is False, (
            "an artifact that gives a loan the same PD twice cannot fire the test")
        assert s.sicr(b, loan, date, model=lit) is True, (
            "the model argument did not reach the test")
        quiet = s.stage(b, loan, date, model=calm)
        if quiet["stage"] == 1:
            fired = s.stage(b, loan, date, model=lit)
            assert fired["stage"] == 2 and fired["reason"] == "significant-increase", (
                "a clean date rated into the test is stage 2 for the test's own reason, "
                "and it answered %r" % (fired,))
        _refuses(world.BookError, "an artifact that cannot answer the grade",
                 lambda: s.sicr(b, loan, date, model={"name": "nope", "version": 1}),
                 ["nope", now])
        _refuses(world.BookError, "an artifact that is not an artifact",
                 lambda: s.sicr(b, loan, date, model="nope"), ["nope"])

    def _c7_transfers(s, b, maze):
        """One row per loan that moved, in the book's order, dated and reasoned."""
        report = list(b.reporting_dates)
        windows = ((report[0], report[12]), (report[12], report[-1]),
                   (report[0], report[-1]), (report[0], report[0]))
        for start, end in windows:
            rows = s.transfers(b, start, end)
            assert isinstance(rows, tuple), (
                "the transfers of %s..%s are %r" % (start, end, rows))
            want = []
            for loan in b.loans:
                was = maze[(loan["loan"], start)]["stage"]
                now = maze[(loan["loan"], end)]["stage"]
                if was != now:
                    want.append((loan["loan"], was, now))
            got = tuple((row["loan"], row["from_stage"], row["to_stage"]) for row in rows)
            assert got == tuple(want), (
                "the transfers of %s..%s are %r and the stages that moved are %r"
                % (start, end, got, tuple(want)))
            for row in rows:
                _keys_of(row, s.TRANSFER_KEYS, "a transfer of %s..%s" % (start, end))
                assert start < row["date"] <= end, (
                    "%r moved on %s, outside %s..%s"
                    % (row["loan"], row["date"], start, end))
                moved = maze[(row["loan"], row["date"])]
                assert moved["stage"] != row["from_stage"], (
                    "%r's transfer is dated %s, where it was already stage %r"
                    % (row["loan"], row["date"], row["from_stage"]))
                assert row["reason"] == moved["reason"], (
                    "%r's transfer carries %r and the record at %s says %r"
                    % (row["loan"], row["reason"], row["date"], moved["reason"]))
                for moment in report:
                    if start < moment < row["date"]:
                        assert maze[(row["loan"], moment)]["stage"] == row["from_stage"], (
                            "%r had already moved at %s, before the date its transfer "
                            "carries" % (row["loan"], moment))
        assert s.transfers(b, report[0], report[0]) == (), (
            "a window that does not move answers no transfers")

    def _c7_refusals(s, b, world):
        """Every shape that cannot be asked refuses, and names what arrived."""
        report = list(b.reporting_dates)
        loan = b.loans[0]
        before = b.stats()
        _refuses(world.BookError, "a date that is not a date",
                 lambda: s.stage(b, loan, "not-a-date"), ["not-a-date"])
        _refuses(world.BookError, "a window that does not run forwards",
                 lambda: s.transfers(b, report[-1], report[0]))
        assert b.stats() == before, (
            "a refused call asked the book for something: %r" % (b.stats(),))
        _refuses(world.BookError, "a date the book does not cover",
                 lambda: s.stage(b, loan, "1999-01-31"), ["1999"])
        _refuses(world.BookError, "a date the transfers do not cover",
                 lambda: s.transfers(b, "1999-01-31", report[-1]), ["1999"])
        _refuses(world.BookError, "a loan the book does not hold",
                 lambda: s.stage(b, {"loan": "nope"}, report[-1]), ["nope"])
        _refuses(world.BookError, "the test on a loan the book does not hold",
                 lambda: s.sicr(b, "nope", report[-1]), ["nope"])

    class _C7Book:
        """A book the check built: one loan, one artifact and four reporting dates.

        The world's own flags are unreachable *as flags*: every unlikeliness-to-pay flag
        `Book.build(7)` records sits on a loan the bank already calls defaulted, so the
        flag can never be the thing that moved a loan, and the check's own recomputation
        of the world could not tell a stage that reads flags apart from one that does not.
        So the rules the contract pins are proved here, on facts the check decides and
        through the same `stage_02` the stage under test reads: the test outranks the
        backstop, a standing flag is not a branch of the decision (it is stage 3's, by way
        of a default the built book does not record), and a date that carries one is not a
        quiet date, so a stage-2 loan owes more of them before it returns.
        """

        def __init__(self, world, calendar, grade, origination, events, pays,
                     current_bp=1000, models=None, table=None, report=None):
            self._error = world.BookError
            self._grade = grade
            self._due = tuple(calendar.add_months("2030-12-31", step)
                              for step in range(24))
            self._events = tuple({"loan": "T-1", "date": moment, "kind": kind,
                                  "detail_cents": 0} for moment, kind in events)
            self._pays = pays
            self._loan = {"loan": "T-1", "borrower": "T", "segment": "consumer",
                          "grade_origination": origination, "principal_cents": 2400000,
                          "rate_bp": 500, "term_months": 24, "first_due": "2030-12-31",
                          "origination": "2030-12-01", "collateral_kind": "none",
                          "collateral_cents": 0, "undrawn_limit_cents": 0,
                          "measured_at": "amortised-cost"}
            self.reporting_dates = report if report is not None else (
                "2031-01-31", "2031-02-28", "2031-03-31", "2031-04-30")
            moved = table if table is not None else {grade: current_bp}
            self.models = models if models is not None else (
                {"name": "toy", "version": 1, "as_of": "2030-12-31", "grades": {},
                 "pd_bp": _c7_table(moved), "lgd_bp": {}, "ccf_bp": {}},)

        def loans(self):
            """The one loan this book holds."""
            return (self._loan,)

        def loan(self, loan):
            """That loan's record, whatever shape it was asked for."""
            loan_id = loan["loan"] if isinstance(loan, dict) else loan
            if loan_id != "T-1":
                raise self._error("check: the built book holds no loan %r" % (loan_id,))
            return self._loan

        def schedule(self, loan):
            """The contractual flows the built book's schedule holds."""
            return {"loan": "T-1", "flows": tuple({"date": due, "amount_cents": 100000}
                                                  for due in self._due),
                    "principal_cents": 2400000, "rate_bp": 500, "term_months": 24,
                    "first_due": "2030-12-31", "level_payment_cents": 100000}

        def payments(self, loan):
            """The instalments booked: on time, on time but for the first due, or never."""
            if self._pays == "never":
                return ()
            rows = []
            for index, due in enumerate(self._due):
                if due > self.reporting_dates[-1]:
                    continue
                paid_on = "2031-02-28" if self._pays == "late" and index == 0 else due
                rows.append({"loan": "T-1", "due": due, "paid_on": paid_on,
                             "amount_cents": 100000, "kind": "instalment"})
            return tuple(rows)

        def events(self, loan):
            """The events the built book was given, in the order it was given them."""
            return self._events

        def defaults(self):
            """Nothing is a signalled default in the built book: the flag branch stands."""
            return ()

        def grade(self, loan, date):
            """The grade the built book records: the one the check chose."""
            return self._grade

    def _c7_table(values):
        """A flat yearly series per grade, with `values` giving the grades that moved."""
        table = {}
        for name in C7_GRADES:
            table[name] = (1000, 1000, 1000, 1000)
        for name, bp in values.items():
            table[name] = (bp,) * 4
        return table

    def _c7_built(s, world, calendar):
        """The rules the contract pins, on a book whose facts the check decides."""
        plain = _C7Book(world, calendar, "B", "B", (), "on-time")
        for moment in plain.reporting_dates:
            record = _keys_of(s.stage(plain, plain.loan("T-1"), moment), s.STAGE_KEYS,
                              "a staging of the built book")
            assert record["stage"] == 1, (
                "a loan that pays, has no flag and whose PD has not moved is stage 1, "
                "and the built book answered %r" % (record,))
            assert record["reason"] == "no-significant-increase", (
                "the fall-through's reason is `no-significant-increase`: %r" % (record,))
        flagged = _C7Book(world, calendar, "B", "B", (("2030-12-01", "forbearance"),),
                          "on-time")
        for moment in flagged.reporting_dates:
            record = s.stage(flagged, flagged.loan("T-1"), moment)
            assert record["stage"] == 1 and record["sicr"] is False, (
                "an uncured flag is not a branch of the decision — it is what stage 2's "
                "definition of default is made of, and the built book records no default, "
                "so this loan is stage 1 and the built book answered %r" % (record,))
        backed = _C7Book(world, calendar, "B", "B", (), "never")
        for moment in backed.reporting_dates:
            record = s.stage(backed, backed.loan("T-1"), moment)
            assert record["stage"] == 2 and record["reason"] == "days-past-due", (
                "a loan past the backstop and nothing else is stage 2 for the days, "
                "and the built book answered %r" % (record,))
            assert record["sicr"] is False, (
                "the built book's backstop case must not rest on the PD test: %r"
                % (record,))
        ranked = _C7Book(world, calendar, "C", "B", (), "never",
                         table={"B": 400, "C": 700})
        record = s.stage(ranked, ranked.loan("T-1"), ranked.reporting_dates[-1])
        assert record["sicr"] is True and record["reason"] == "significant-increase", (
            "the absolute half alone has to fire the test, and to outrank a backstop "
            "that is also crossed: %r" % (record,))
        assert (record["pd_bp"] - record["origination_pd_bp"] >= s.SICR_ABSOLUTE_BP
                and record["pd_bp"] * 10000 < record["origination_pd_bp"]
                * s.SICR_MULTIPLIER_BP), (
            "this fixture is the *absolute* half alone, and the built book answered %r"
            % (record,))
        multi = _C7Book(world, calendar, "C", "B", (), "on-time",
                        table={"B": 100, "C": 250})
        record = s.stage(multi, multi.loan("T-1"), multi.reporting_dates[-1])
        assert record["sicr"] is True and record["reason"] == "significant-increase", (
            "the multiplier half alone has to fire the test: %r" % (record,))
        assert (record["pd_bp"] * 10000 >= record["origination_pd_bp"]
                * s.SICR_MULTIPLIER_BP
                and record["pd_bp"] - record["origination_pd_bp"] < s.SICR_ABSOLUTE_BP), (
            "this fixture is the *multiplier* half alone, and the built book answered %r"
            % (record,))
        edge = _C7Book(world, calendar, "B", "B", (), "late",
                       report=("2031-01-29", "2031-01-30"))
        behind = s.stage(edge, edge.loan("T-1"), edge.reporting_dates[0])
        assert behind["stage"] == 1 and behind["reason"] == "no-significant-increase", (
            "twenty-nine days past due is short of the backstop's thirty: %r" % (behind,))
        level = s.stage(edge, edge.loan("T-1"), edge.reporting_dates[1])
        assert level["stage"] == 2 and level["reason"] == "days-past-due", (
            "exactly thirty days past due is the backstop, inclusive: %r" % (level,))
        assert s.sicr(edge, edge.loan("T-1"), edge.reporting_dates[1]) is False, (
            "the backstop's own edge must not rest on the PD test: %r" % (level,))
        twin = _C7Book(world, calendar, "C", "B", (), "on-time", models=(
            {"name": "dual", "version": 1, "as_of": "2030-12-31", "grades": {},
             "pd_bp": _c7_table({"C": 1000}), "lgd_bp": {}, "ccf_bp": {}},
            {"name": "dual", "version": 2, "as_of": "2030-12-31", "grades": {},
             "pd_bp": _c7_table({"C": 1300}), "lgd_bp": {}, "ccf_bp": {}}))
        record = s.stage(twin, twin.loan("T-1"), twin.reporting_dates[-1])
        assert record["sicr"] is True and record["reason"] == "significant-increase", (
            "two artifacts share an `as_of`, and the greater version is the one in "
            "force: the built book answered %r" % (record,))
        assert s.stage(twin, twin.loan("T-1"), twin.reporting_dates[-1],
                       model=twin.models[0])["sicr"] is False, (
            "the older version read explicitly has not moved the loan: %r" % (record,))
        waited = _C7Book(world, calendar, "B", "B", (), "late")
        assert tuple(s.stage(waited, waited.loan("T-1"), moment)["reason"]
                     for moment in waited.reporting_dates) == (
            "days-past-due", "return-not-yet", "no-significant-increase",
            "no-significant-increase"), (
            "a late instalment puts the loan in stage 2 once, the loan owes two quiet "
            "reporting dates before it returns, and the built book answered %r"
            % ([s.stage(waited, waited.loan("T-1"), moment)["reason"]
                for moment in waited.reporting_dates],))
        held = _C7Book(world, calendar, "B", "B", (("2031-03-01", "forbearance"),),
                       "late")
        assert tuple(s.stage(held, held.loan("T-1"), moment)["reason"]
                     for moment in held.reporting_dates) == (
            "days-past-due", "return-not-yet", "return-not-yet", "return-not-yet"), (
            "a date that carries a standing flag is not a quiet date, so the flag keeps "
            "the loan in stage 2 past the date it would otherwise have returned: the "
            "built book answered %r"
            % ([s.stage(held, held.loan("T-1"), moment)["reason"]
                for moment in held.reporting_dates],))
        _refuses(world.BookError, "a loan the built book does not hold",
                 lambda: s.stage(plain, {"loan": "nope"}, plain.reporting_dates[-1]),
                 ["nope"])

    def _c7_twice(s, b, world):
        """One workload, twice: a run has to be a function of its inputs."""
        report = list(b.reporting_dates)
        moments = (report[0], report[12], report[-1])

        def workload():
            return (tuple(s.stage(b, loan, date) for loan in b.loans for date in moments),
                    tuple(s.sicr(b, loan, date) for loan in b.loans for date in moments),
                    s.transfers(b, report[0], report[-1]))

        assert workload() == workload(), (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import book as world
    import dates as calendar
    import rules as policy
    import stage_07 as s
    b = world.Book.build(7)
    _c7_constants(s, policy)
    maze = _c7_maze(s, b)
    _c7_history(s, b, world, policy, maze)
    _c7_boundaries(s, b, world)
    _c7_built(s, world, calendar)
    _c7_transfers(s, b, maze)
    _c7_refusals(s, b, world)
    _c7_twice(s, b, world)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    S8_KEYS = ("start", "end", "opening_cents", "lines", "pl_cents", "oci_cents",
               "closing_cents", "difference_cents")

    S8_LINES = ("derecognitions", "new-business", "stage-transfers", "parameter", "scenario",
                "unwind", "write-offs", "recoveries", "other")

    S8_PL = "amortised-cost"

    S8_OCI = "fvoci"

    S8_BASE = "base"

    S8_WRITE_OFF = "write-off"

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "book.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _Bent(object):
        """The book with one field of one loan bent, so a stage's own guards are reachable.

        Two of §4.8's refusals are about records no honest book holds — a loan whose stage
        cannot be one, a loan measured neither at amortised cost nor at fair value through
        OCI — so the check bends exactly that field of exactly that loan and asks again.
        """

        def __init__(self, book, loan_id, field, value):
            self._book = book
            self._loan_id = loan_id
            self._field = field
            self._value = value

        @property
        def loans(self):
            bent = []
            for loan in self._book.loans:
                if loan["loan"] == self._loan_id:
                    loan = dict(loan, **{self._field: self._value})
                bent.append(loan)
            return tuple(bent)

        def status(self, loan, date):
            record = self._book.status(loan, date)
            if self._field == "stage" and loan["loan"] == self._loan_id:
                return dict(record, stage=self._value)
            return record

        def __getattr__(self, name):
            return getattr(self._book, name)

    def _s8_provision(s6, b, loan, date):
        """Stage 6's own scenario-weighted provision for one loan at one date."""
        return s6.weighted_ecl(b, loan, date)["weighted_cents"]

    def _s8_base(s6, b, loan, date, stage, model):
        """Stage 6's own base-scenario loss at a counterfactual stage and artifact."""
        return s6.ecl(b, loan, date, S8_BASE, stage=stage, model=model)["ecl_cents"]

    def _s8_in_force(b, date):
        """The artifact in force at a date: the newest `as_of` not after it."""
        chosen = None
        for model in b.models:
            if model["as_of"] <= date and (chosen is None or (
                    (model["as_of"], model["version"])
                    > (chosen["as_of"], chosen["version"]))):
                chosen = model
        assert chosen is not None, "the book has no artifact in force at %s" % (date,)
        return chosen

    def _s8_months(start, end):
        """Whole months between two month ends, counted from their own labels."""
        return ((int(end[:4]) - int(start[:4])) * 12 + int(end[5:7]) - int(start[5:7]))

    def _s8_record(b, loan, date):
        """The stage the book records for a loan at a date."""
        recorded = b.status(loan, date)["stage"]
        assert recorded in (1, 2, 3), (
            "the book records %r at %s with stage %r" % (loan["loan"], date, recorded))
        return recorded

    def _s8_last_live(b, loan, end):
        """The last reporting date at or before `end` at which the book held the loan."""
        for date in reversed(tuple(b.reporting_dates)):
            if date <= end and loan["loan"] in b.on_book(date):
                return date
        return None

    def _s8_written(b, loan, start, end):
        """Whether the loan carries a write-off event after `start` and by `end`."""
        return any(event["kind"] == S8_WRITE_OFF and start < event["date"] <= end
                   for event in b.events(loan))

    def _s8_written_by(b, loan, date):
        """Whether the loan carries a write-off event at or before a date."""
        return any(event["kind"] == S8_WRITE_OFF and event["date"] <= date
                   for event in b.events(loan))

    def _s8_unwind(s1, r, b, loan, opening, months):
        """The opening provision accreted over the months, at the loan's own period rate."""
        eir = s1.effective_rate(b, loan)
        period_bp = r.period_rate(eir["eir_bp"], eir["basis"])
        accrued = 0
        for _ in range(months):
            accrued += opening * period_bp // 10000
        return accrued

    def _s8_expected(s6, s1, r, b, start, end, side=None):
        """The ten steps summed line by line, over one measurement election or all of them.

        Answers `(opening, closing, lines)`: the two totals over the book's own live sets, and
        one entry per name in `S8_LINES` plus `difference`, each summed over the population the
        contract gives it. With `side` set, only the loans whose own `measured_at` is that
        election are counted, which partitions every line.
        """
        loans = tuple(loan for loan in b.loans
                      if side is None or loan["measured_at"] == side)
        on_start = set(b.on_book(start))
        on_end = set(b.on_book(end))
        both = tuple(loan for loan in loans
                     if loan["loan"] in on_start and loan["loan"] in on_end)
        old = _s8_in_force(b, start)
        new = _s8_in_force(b, end)
        months = _s8_months(start, end)
        opening = sum(_s8_provision(s6, b, loan, start) for loan in loans
                      if loan["loan"] in on_start)
        closing = sum(_s8_provision(s6, b, loan, end) for loan in loans
                      if loan["loan"] in on_end)
        lines = {}
        lines["derecognitions"] = -sum(
            _s8_provision(s6, b, loan, start) for loan in loans
            if loan["loan"] in on_start and loan["loan"] not in on_end
            and not _s8_written(b, loan, start, end))
        lines["write-offs"] = -sum(
            _s8_provision(s6, b, loan, _s8_last_live(b, loan, end))
            for loan in loans
            if _s8_written(b, loan, start, end) and _s8_last_live(b, loan, end) is not None)
        lines["new-business"] = sum(
            _s8_provision(s6, b, loan, end) for loan in loans
            if loan["loan"] in on_end and loan["loan"] not in on_start)
        lines["stage-transfers"] = sum(
            _s8_base(s6, b, loan, end, _s8_record(b, loan, end), old)
            - _s8_base(s6, b, loan, end, _s8_record(b, loan, start), old)
            for loan in both)
        lines["parameter"] = sum(
            _s8_base(s6, b, loan, end, _s8_record(b, loan, end), new)
            - _s8_base(s6, b, loan, end, _s8_record(b, loan, end), old)
            for loan in both)
        lines["scenario"] = sum(
            _s8_provision(s6, b, loan, end)
            - _s8_base(s6, b, loan, end, _s8_record(b, loan, end), new)
            for loan in both)
        lines["unwind"] = sum(
            _s8_unwind(s1, r, b, loan, _s8_provision(s6, b, loan, start), months)
            for loan in loans if loan["loan"] in on_start)
        lines["recoveries"] = sum(
            flow["amount_cents"] for loan in loans if _s8_written_by(b, loan, start)
            for flow in b.recoveries(loan) if start < flow["date"] <= end)
        lines["other"] = (closing - opening
                          - sum(lines[name] for name in S8_LINES[:-1]))
        lines["difference"] = (closing - opening - sum(lines[name] for name in S8_LINES))
        return opening, closing, lines

    def _s8_windows(b):
        """The windows the check asks about, both ends of the book's history included."""
        report = tuple(b.reporting_dates)
        return ((report[0], report[12]), (report[12], report[24]), (report[0], report[-1]),
                (report[-2], report[-1]), (report[0], report[0]), (report[0], report[1]),
                (report[16], report[30]))

    def _s8_constants(s):
        """The two pinned constants, in the order every record and every `why` is printed."""
        assert tuple(s.ROLLFORWARD_KEYS) == S8_KEYS, (
            "ROLLFORWARD_KEYS is %r, not %r" % (tuple(s.ROLLFORWARD_KEYS), S8_KEYS))
        assert tuple(s.LINES) == S8_LINES, (
            "LINES is %r, not the nine movements in their pinned order %r"
            % (tuple(s.LINES), S8_LINES))

    def _s8_numbers(record):
        """A record's numbers: everything but the sentence each line explains itself with."""
        assert tuple(record) == S8_KEYS, (
            "the record's fields are %r, not %r" % (tuple(record), S8_KEYS))
        lines = record["lines"]
        assert isinstance(lines, tuple) and len(lines) == len(S8_LINES), (
            "the record carries %r lines, not one triple per name in LINES" % (lines,))
        return (record["start"], record["end"], record["opening_cents"],
                tuple((line, cents) for line, cents, _ in lines),
                record["pl_cents"], record["oci_cents"], record["closing_cents"],
                record["difference_cents"])

    def _s8_shape(s, b, window):
        """The eight fields, the nine triples, and the sentence each line explains itself with."""
        start, end = window
        record = s.rollforward(b, start, end)
        _s8_numbers(record)
        assert record["start"] == start and record["end"] == end, (
            "the record echoes %r..%r, not the window it was asked about (%s..%s)"
            % (record["start"], record["end"], start, end))
        whys = []
        for line, cents, why in record["lines"]:
            assert isinstance(line, str) and isinstance(cents, int), (
                "the %r line is %r / %r, not a name and an int count of cents"
                % (line, line, cents))
            assert isinstance(why, str) and why.strip(), (
                "the %s line carries no why" % (line,))
            assert line in why and str(cents) in why, (
                "the %s line's why is %r, which does not name the line and its own %d cents"
                % (line, why, cents))
            whys.append(why)
        assert len(set(whys)) == len(whys), (
            "two lines explain themselves the same way: %r" % (whys,))
        lines = sum(cents for _, cents, _ in record["lines"])
        assert record["pl_cents"] + record["oci_cents"] == lines, (
            "P&L (%d) and OCI (%d) do not add up to the nine lines (%d), so the split is not "
            "a partition of the same money"
            % (record["pl_cents"], record["oci_cents"], lines))
        assert (record["opening_cents"] + record["pl_cents"] + record["oci_cents"]
                == record["closing_cents"]), (
            "the opening (%d) plus the split (%d + %d) is not the closing (%d)"
            % (record["opening_cents"], record["pl_cents"], record["oci_cents"],
               record["closing_cents"]))
        assert record["difference_cents"] == 0, (
            "the record reports %d cents unexplained while carrying `other`, which is the "
            "line that explains them" % (record["difference_cents"],))

    def _s8_book(s, b, window):
        """The stage's record against the book's own account of the same window."""
        start, end = window
        try:
            theirs = b.rollforward(start, end)
        except ValueError:
            return          # the book may not hold a window of no length; the stage may
        mine = _s8_numbers(s.rollforward(b, start, end))
        assert mine == _s8_numbers(theirs), (
            "the stage's own roll-forward of %s..%s is %r and the book's is %r"
            % (start, end, mine, _s8_numbers(theirs)))

    def _s8_steps(s, s6, s1, r, b, window):
        """Every line, the opening and the closing against the check's own ten steps."""
        start, end = window
        record = s.rollforward(b, start, end)
        opening, closing, mine = _s8_expected(s6, s1, r, b, start, end)
        assert record["opening_cents"] == opening, (
            "the opening is %d cents and the book's own total provision at %s is %d"
            % (record["opening_cents"], start, opening))
        assert record["closing_cents"] == closing, (
            "the closing is %d cents and the book's own total provision at %s is %d, so the "
            "closing was derived from the lines rather than recomputed"
            % (record["closing_cents"], end, closing))
        theirs = dict((line, cents) for line, cents, _ in record["lines"])
        for name in S8_LINES:
            assert theirs[name] == mine[name], (
                "the %s line is %d cents and the check's own decomposition of %s..%s makes "
                "it %d" % (name, theirs[name], start, end, mine[name]))
        assert record["difference_cents"] == closing - opening - sum(theirs.values()), (
            "difference_cents is not the closing less the opening and the nine lines")

    def _s8_split(s, s6, s1, r, b, window):
        """The split: the same eight lines, once per measurement election, plus other in P&L."""
        start, end = window
        record = s.rollforward(b, start, end)
        theirs = dict((line, cents) for line, cents, _ in record["lines"])
        shares = {}
        for side in (S8_PL, S8_OCI):
            _, _, part = _s8_expected(s6, s1, r, b, start, end, side)
            shares[side] = sum(part[name] for name in S8_LINES[:-1])
        assert record["pl_cents"] == shares[S8_PL] + theirs["other"], (
            "P&L is %d cents and the amortised-cost loans own %d of the eight lines plus the "
            "%d cents of other" % (record["pl_cents"], shares[S8_PL], theirs["other"]))
        assert record["oci_cents"] == shares[S8_OCI], (
            "OCI is %d cents and the fvoci loans own %d of the eight lines"
            % (record["oci_cents"], shares[S8_OCI]))

    def _s8_elections(s, b):
        """Both measurement elections are in the book, so the split is not a column of zeroes."""
        elections = {}
        for loan in b.loans:
            elections[loan["measured_at"]] = elections.get(loan["measured_at"], 0) + 1
        assert elections.get(S8_PL) and elections.get(S8_OCI), (
            "the book measures %r, so the split exercises only one side" % (elections,))

    def _s8_reachable(s, b, windows):
        """The book's own estate: no line of the decomposition is left unexercised."""
        moved = {}
        for start, end in windows:
            for line, cents, _ in s.rollforward(b, start, end)["lines"]:
                if cents != 0:
                    moved[line] = moved.get(line, 0) + 1
        for name in ("stage-transfers", "parameter", "scenario", "unwind", "write-offs",
                     "recoveries", "new-business"):
            assert moved.get(name), (
                "no window of the book moves the %s line, so the decomposition is "
                "unexercised there: %r" % (name, moved))

    def _s8_dates(s, dates, b, exc):
        """The windows that cannot be a window, refused before the book is asked anything."""
        report = tuple(b.reporting_dates)
        first = dates.parse(report[0])
        middle = dates.parse(report[6])
        for start, end in ((report[1], report[0]), (report[-1], report[2])):
            before = b.stats()
            _refuses(exc, "a start date after the end date (%s..%s)" % (start, end),
                     lambda: s.rollforward(b, start, end), names=(start, end))
            assert b.stats() == before, (
                "a refused window asked the book for %r" % (b.stats(),))
        uncovered = (dates.iso(first[0], first[1], first[2] - 1),
                     dates.add_months(report[-1], 1),
                     dates.iso(middle[0], middle[1], 15))
        for date in uncovered:
            before = b.stats()
            _refuses(exc, "the date %s, which the book does not cover" % (date,),
                     lambda: s.rollforward(b, report[6], date), names=(date,))
            _refuses(exc, "the date %s, which the book does not cover" % (date,),
                     lambda: s.rollforward(b, date, report[6]), names=(date,))
            assert b.stats() == before, (
                "a refused date asked the book for %r" % (b.stats(),))
        _refuses(ValueError, "a date that is no date",
                 lambda: s.rollforward(b, "2031-1-3", report[6]), names=("2031-1-3",))

    def _s8_guards(s, b, exc):
        """The two records no honest book holds, reached by bending one field of one loan."""
        report = tuple(b.reporting_dates)
        start, end = report[6], report[18]
        live = set(b.on_book(start)) & set(b.on_book(end))
        held = [loan for loan in b.loans if loan["loan"] in live]
        assert held, "the book holds no loan at both %s and %s" % (start, end)
        loan = held[0]
        _refuses(exc, "a book whose record gives a loan a stage it cannot have",
                 lambda: s.rollforward(_Bent(b, loan["loan"], "stage", 7), start, end),
                 names=(loan["loan"],))
        _refuses(exc, "a book whose loan is measured neither way",
                 lambda: s.rollforward(_Bent(b, loan["loan"], "measured_at", "trading"),
                                       start, end),
                 names=(loan["loan"], "trading"))

    def _s8_workload(s, b, windows):
        """One whole pass of the stage over the book's own windows."""
        return tuple(_s8_numbers(s.rollforward(b, start, end)) for start, end in windows)

    def _s8_twice(s, b, windows):
        one = _s8_workload(s, b, windows)
        two = _s8_workload(s, b, windows)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    import book as world
    import dates
    import rules
    import stage_01 as s1
    import stage_06 as s6
    import stage_08 as s
    b = world.Book.build(7)
    windows = _s8_windows(b)
    _s8_constants(s)
    _s8_elections(s, b)
    for window in windows:
        _s8_shape(s, b, window)
        _s8_book(s, b, window)
        _s8_steps(s, s6, s1, rules, b, window)
        _s8_split(s, s6, s1, rules, b, window)
    _s8_reachable(s, b, windows)
    _s8_dates(s, dates, b, world.BookError)
    _s8_guards(s, b, world.BookError)
    _s8_twice(s, b, windows)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    S9_PACK_KEYS = ("date", "lines", "exposures", "ecl", "coverage_bp", "by_stage",
                    "by_grade", "by_bucket", "by_segment", "forbearance", "vintage",
                    "migration")

    S9_PACK_PROBLEMS = ("missing-loan", "double-counted", "coverage-mismatch",
                        "stage-mismatch", "total-mismatch")

    S9_LINE_KEYS = ("loan", "stage", "grade", "bucket", "segment", "exposure_cents",
                    "ecl_cents")

    S9_DIMENSIONS = (("by_stage", 1), ("by_grade", 2), ("by_bucket", 3),
                     ("by_segment", 4))

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "book.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _EmptyBook:
        """The world's own book with no loan on it at one reporting date.

        `Book.build` never leaves a reporting date bare, but "an empty pack is
        answered, not refused" is a rule about the pack and not about the portfolio,
        so the check reaches it the way it reaches any boundary the world cannot
        print: with the smallest stand-in that answers the book's own doors. Only
        `reporting_dates` and `on_book` are ever asked.
        """

        def __init__(self, date):
            self.reporting_dates = (date,)
            self.loans = ()

        def on_book(self, date):
            """No loan is live at a date of an empty book."""
            return ()

    class _World:
        """The world's calendar and rulebook, so a helper can read them where it stands."""

        def __init__(self, dates, rules, error):
            self.dates = dates
            self.rules = rules
            self.error = error

        def month(self, date):
            """The origination month a cohort is keyed by, off the world's own calendar."""
            year, month, _day = self.dates.parse(date)
            return "%04d-%02d" % (year, month)

        def order(self, keys, dimension):
            """A dimension's keys in the dimension's own order.

            The rulebook owns the order of the grades, the buckets and the segments;
            the stages have no tuple in the rulebook, so they are ordered by their own
            value — which is what both the pack and the migration matrix print.
            """
            rulebook = {"by_grade": self.rules.GRADES,
                        "by_bucket": self.rules.BUCKETS,
                        "by_segment": self.rules.SEGMENTS}.get(dimension)
            if rulebook is None:
                return tuple(sorted(keys))
            return tuple(key for key in rulebook if key in keys)

    def _s9_coverage(ecl_cents, exposure_cents):
        """The ratio the contract pins: truncated, and `0` where there is no exposure."""
        if exposure_cents == 0:
            return 0
        return ecl_cents * 10000 // exposure_cents

    def _s9_constants(s):
        """The two public constants, in the order the contract pins them."""
        assert tuple(s.PACK_KEYS) == S9_PACK_KEYS, (
            "stage 9: PACK_KEYS is %r, not %r" % (tuple(s.PACK_KEYS), S9_PACK_KEYS))
        assert tuple(s.PACK_PROBLEMS) == S9_PACK_PROBLEMS, (
            "stage 9: PACK_PROBLEMS is %r, not %r"
            % (tuple(s.PACK_PROBLEMS), S9_PACK_PROBLEMS))

    def _s9_aggregate(rows):
        """The four fields a set of lines makes, coverage included."""
        exposure = sum(row[5] for row in rows)
        ecl = sum(row[6] for row in rows)
        return (len(rows), exposure, ecl, _s9_coverage(ecl, exposure))

    def _s9_by(lines, slot):
        """The lines grouped by one of their own fields, each group in line order."""
        found = {}
        for line in lines:
            if line[slot] not in found:
                found[line[slot]] = []
            found[line[slot]].append(line)
        return found

    def _s9_edges(b):
        """The dates where the pack's population changes, plus the first and the last.

        A pack that counts every loan the book holds, written-off ones included, is
        caught here rather than on a mid-history date where the two populations agree.
        """
        report = b.reporting_dates
        edges = [report[0], report[-1]]
        for index in range(1, len(report)):
            if len(b.on_book(report[index])) != len(b.on_book(report[index - 1])):
                edges.extend((report[index - 1], report[index]))
        edges.append(report[len(report) // 2])
        return tuple(dict.fromkeys(edges))

    def _s9_dimension(s, world, name, slot, record):
        """One dimension: every cell is the pack's own lines aggregated, in order."""
        cells = record[name]
        assert isinstance(cells, dict), (
            "stage 9: %s is not a dict of cells, it is %r" % (name, cells))
        grouped = _s9_by(record["lines"], slot)
        want = world.order(grouped.keys(), name)
        assert tuple(cells) == want, (
            "stage 9: %s's keys are %r, and its own order is %r"
            % (name, tuple(cells), want))
        for key in want:
            cell = cells[key]
            assert isinstance(cell, tuple) and len(cell) == 4, (
                "stage 9: %s[%r] is not a four-field cell: %r" % (name, key, cell))
            made = _s9_aggregate(tuple(grouped[key]))
            assert cell == made, (
                "stage 9: %s[%r] is %r, and the pack's own lines aggregate to %r"
                % (name, key, cell, made))
            assert cell[3] == _s9_coverage(cell[2], cell[1]), (
                "stage 9: %s[%r] prints the coverage %d, and its own exposure %d and loss "
                "%d make %d" % (name, key, cell[3], cell[1], cell[2],
                                _s9_coverage(cell[2], cell[1])))
        assert sum(cell[0] for cell in cells.values()) == len(record["lines"]), (
            "stage 9: %s's cells count %d loans and the pack holds %d lines"
            % (name, sum(cell[0] for cell in cells.values()), len(record["lines"])))
        assert sum(cell[1] for cell in cells.values()) == record["exposures"], (
            "stage 9: %s's cells hold %d cents of exposure and the pack's total is %d"
            % (name, sum(cell[1] for cell in cells.values()), record["exposures"]))
        assert sum(cell[2] for cell in cells.values()) == record["ecl"], (
            "stage 9: %s's cells hold %d cents of loss and the pack's total is %d"
            % (name, sum(cell[2] for cell in cells.values()), record["ecl"]))

    def _s9_flagged(b, date):
        """The loans the bank's own default records call forborne at `date`.

        Read off `defaults()`, not off stage 2: a default signalled on or before the
        date and not cured by it, whose own triggers name a forbearance. That is the
        answer key for the pack's memo, and it is computed here independently of the
        stage that produces it.
        """
        found = []
        for row in b.defaults():
            if row["signalled_on"] > date or row["loan"] in found:
                continue
            if row["cured_on"] is not None and row["cured_on"] <= date:
                continue
            if "forbearance" in row["triggers"]:
                found.append(row["loan"])
        return tuple(found)

    def _s9_forbearance(s, world, b, date, record):
        """The flagged subset: its own coverage, and still inside the dimensions."""
        memo = record["forbearance"]
        assert isinstance(memo, tuple) and len(memo) == 4, (
            "stage 9: the forbearance block at %s is not a four-field cell: %r"
            % (date, memo))
        flagged = _s9_flagged(b, date)
        rows = tuple(line for line in record["lines"] if line[0] in flagged)
        assert len(rows) == len(flagged), (
            "stage 9: the book calls %r forborne at %s and the pack's lines hold %d of them"
            % (flagged, date, len(rows)))
        made = _s9_aggregate(rows)
        assert memo == made, (
            "stage 9: the forbearance block at %s is %r, and the flagged lines aggregate "
            "to %r" % (date, memo, made))
        assert memo[3] == _s9_coverage(memo[2], memo[1]), (
            "stage 9: the forbearance block prints the coverage %d, and its own exposure "
            "%d and loss %d make %d"
            % (memo[3], memo[1], memo[2], _s9_coverage(memo[2], memo[1])))
        assert memo[1] <= record["exposures"], (
            "stage 9: the forbearance block at %s holds more exposure than the pack" % date)
        if flagged:
            inside = sum(cell[1] for cell in record["by_stage"].values())
            assert inside == record["exposures"], (
                "stage 9: the flagged loans at %s are reported instead of the portfolio: "
                "the stage dimension holds %d cents and the pack reports %d"
                % (date, inside, record["exposures"]))

    def _s9_vintage(s, world, b, date, record):
        """The cohort matrix: rows in date order, cells the lines that belong to them."""
        cohorts = record["vintage"]
        assert isinstance(cohorts, dict), (
            "stage 9: the vintage at %s is not a matrix of months: %r" % (date, cohorts))
        months = tuple(cohorts)
        assert months == tuple(sorted(months)), (
            "stage 9: the vintage rows at %s are %r, not in date order" % (date, months))
        assert months, "stage 9: the vintage at %s has no row at all" % (date,)
        grouped = {}
        for line in record["lines"]:
            month = world.month(b.loan(line[0])["origination"])
            if month not in grouped:
                grouped[month] = {}
            stage = line[1]
            if stage not in grouped[month]:
                grouped[month][stage] = []
            grouped[month][stage].append(line)
        made = {}
        for month in sorted(grouped):
            cells = {}
            for stage in sorted(grouped[month]):
                rows = tuple(grouped[month][stage])
                exposure = sum(row[5] for row in rows)
                ecl = sum(row[6] for row in rows)
                cells[stage] = (len(rows), exposure, _s9_coverage(ecl, exposure))
            made[month] = cells
        assert cohorts == made, (
            "stage 9: the vintage matrix at %s is %r, and the pack's own lines make %r"
            % (date, cohorts, made))
        for month in cohorts:
            assert tuple(cohorts[month]) == world.order(cohorts[month].keys(), "by_stage"), (
                "stage 9: the vintage columns at %s are %r, not the stages' own order"
                % (date, tuple(cohorts[month])))
            for stage in cohorts[month]:
                cell = cohorts[month][stage]
                assert isinstance(cell, tuple) and len(cell) == 3, (
                    "stage 9: vintage[%r][%r] is not a cohort cell: %r" % (month, stage, cell))
                assert cell[0] >= 1, (
                    "stage 9: vintage[%r][%r] holds %r loans" % (month, stage, cell[0]))
        held = sum(cell[1] for cells in cohorts.values() for cell in cells.values())
        assert held == record["exposures"], (
            "stage 9: the vintages at %s hold %d cents of exposure and the pack's total is "
            "%d" % (date, held, record["exposures"]))

    def _s9_migration(s, world, b, date, record):
        """The stage migration: the year's window, the book's own stages, rows of 10000."""
        matrix = record["migration"]
        assert isinstance(matrix, dict), (
            "stage 9: the migration at %s is not a matrix: %r" % (date, matrix))
        start = world.dates.add_months(date, -12)
        assert matrix["from_date"] == start, (
            "stage 9: the migration's window starts at %r, and a year before %s is %r"
            % (matrix["from_date"], date, start))
        assert matrix["to_date"] == date, (
            "stage 9: the migration's window ends at %r and the pack is at %s"
            % (matrix["to_date"], date))
        before = {}
        if start in b.reporting_dates:
            before = dict((holder, b.status(holder, start)["stage"])
                          for holder in b.on_book(start))
        after = dict((holder, b.status(holder, date)["stage"])
                     for holder in b.on_book(date))
        counts = {}
        if start in b.reporting_dates:
            for holder in b.on_book(start):
                if holder in before and holder in after:
                    pair = (before[holder], after[holder])
                    counts[pair] = counts.get(pair, 0) + 1
        assert matrix["counts"] == counts, (
            "stage 9: the migration's counts at %s are %r, and the bank's own stage records "
            "make %r" % (date, matrix["counts"], counts))
        stages = tuple(sorted(set(before.values()) | set(after.values())))
        assert tuple(matrix["stages"]) == stages, (
            "stage 9: the migration's dimension at %s is %r, not %r"
            % (date, tuple(matrix["stages"]), stages))
        totals = dict((stage, sum(counts.get((stage, column), 0) for column in stages))
                      for stage in stages)
        assert matrix["row_totals"] == totals, (
            "stage 9: the migration's row totals at %s are %r, not %r"
            % (date, matrix["row_totals"], totals))
        rates = {}
        for stage in stages:
            total = totals[stage]
            row = {}
            running = 0
            for column in stages[:-1]:
                rate = counts.get((stage, column), 0) * 10000 // total if total else 0
                row[column] = rate
                running = running + rate
            row[stages[-1]] = 10000 - running if total else 10000
            rates[stage] = row
        assert matrix["rates_bp"] == rates, (
            "stage 9: the migration's rates at %s are %r, and the contract's own arithmetic "
            "makes %r" % (date, matrix["rates_bp"], rates))
        for stage in stages:
            assert sum(matrix["rates_bp"][stage].values()) == 10000, (
                "stage 9: the migration row %r sums to %d, not 10000"
                % (stage, sum(matrix["rates_bp"][stage].values())))

    def _s9_pack(s, world, b, date):
        """The whole pack at one date: its lines, its totals, its cells, its cohorts."""
        record = s.pack(b, date)
        assert isinstance(record, dict), (
            "stage 9: the pack at %s is not a record: %r" % (date, record))
        assert tuple(record) == S9_PACK_KEYS, (
            "stage 9: the pack's keys are %r, not %r" % (tuple(record), S9_PACK_KEYS))
        assert record["date"] == date, (
            "stage 9: the pack is dated %r and was asked for %s" % (record["date"], date))
        live = tuple(b.on_book(date))
        lines = record["lines"]
        assert isinstance(lines, tuple), (
            "stage 9: the pack's lines are not a tuple: %r" % (lines,))
        assert tuple(line[0] for line in lines) == live, (
            "stage 9: the pack's lines are %r, and the loans live at %s are %r"
            % (tuple(line[0] for line in lines), date, live))
        for line in lines:
            assert isinstance(line, tuple) and len(line) == len(S9_LINE_KEYS), (
                "stage 9: a line is not seven fields: %r" % (line,))
            holder = line[0]
            state = b.status(holder, date)
            loan = b.loan(holder)
            want = (holder, state["stage"], b.grade(holder, date), state["bucket"],
                    loan["segment"], state["ead_cents"], state["ecl_cents"])
            assert line == want, (
                "stage 9: %s's line at %s is %r, and the bank records %r"
                % (holder, date, line, want))
        exposure = sum(b.status(holder, date)["ead_cents"] for holder in live)
        ecl = sum(b.status(holder, date)["ecl_cents"] for holder in live)
        assert record["exposures"] == exposure, (
            "stage 9: the pack reports %d cents of exposure at %s and the bank's own "
            "records hold %d" % (record["exposures"], date, exposure))
        assert record["ecl"] == ecl, (
            "stage 9: the pack reports %d cents of loss at %s and the bank's own records "
            "hold %d" % (record["ecl"], date, ecl))
        assert record["coverage_bp"] == _s9_coverage(ecl, exposure), (
            "stage 9: the pack's coverage at %s is %d, and %d over %d is %d"
            % (date, record["coverage_bp"], ecl, exposure, _s9_coverage(ecl, exposure)))
        for name, slot in S9_DIMENSIONS:
            _s9_dimension(s, world, name, slot, record)
        _s9_forbearance(s, world, b, date, record)
        assert record["vintage"] == s.vintage(b, date), (
            "stage 9: the pack's vintage at %s is not what vintage() answers" % (date,))
        _s9_vintage(s, world, b, date, record)
        _s9_migration(s, world, b, date, record)
        return record

    def _s9_empty(s, world):
        """An empty book is answered, not refused, and every part of it is empty."""
        date = "2031-01-31"
        book = _EmptyBook(date)
        record = s.pack(book, date)
        assert tuple(record) == S9_PACK_KEYS, (
            "stage 9: an empty pack's keys are %r, not %r" % (tuple(record), S9_PACK_KEYS))
        assert record["lines"] == (), (
            "stage 9: an empty pack holds %r" % (record["lines"],))
        assert record["exposures"] == 0 and record["ecl"] == 0, (
            "stage 9: an empty pack reports %r exposure and %r loss"
            % (record["exposures"], record["ecl"]))
        assert record["coverage_bp"] == 0, (
            "stage 9: an empty pack's coverage is %r, and a ratio with no denominator is 0"
            % (record["coverage_bp"],))
        for name, _slot in S9_DIMENSIONS:
            assert record[name] == {}, (
                "stage 9: an empty pack's %s is %r" % (name, record[name]))
        assert record["forbearance"] == (0, 0, 0, 0), (
            "stage 9: an empty pack's forbearance block is %r" % (record["forbearance"],))
        assert record["vintage"] == {}, (
            "stage 9: an empty pack's vintage is %r" % (record["vintage"],))
        matrix = record["migration"]
        assert matrix["from_date"] == world.dates.add_months(date, -12), (
            "stage 9: an empty pack's migration window is %r" % (matrix["from_date"],))
        assert matrix["stages"] == () and matrix["counts"] == {}, (
            "stage 9: an empty pack's migration is %r" % (matrix,))
        assert s.vintage(book, date) == {}, (
            "stage 9: an empty book's vintage is %r" % (s.vintage(book, date),))
        assert s.reconcile(record, book) == (), (
            "stage 9: an empty pack over an empty book scans to %r, not ()"
            % (s.reconcile(record, book),))

    def _s9_disagreement(world, line, slot):
        """A value of the line's own kind that the bank's record cannot be holding.

        A stage the bank does not have (`4`), another grade, bucket or segment out of
        the rulebook, or an amount a thousand cents away: each one keeps the line the
        same *shape*, so the only finding is that it disagrees with the book — and the
        dollar amounts stay inside the dimension the line belongs to, so the cells the
        check rebuilds still add up to the lines it rebuilt them from.
        """
        if slot == 1:
            return 4
        if slot == 2:
            return world.rules.GRADES[-1] if line[slot] != world.rules.GRADES[-1] else "A"
        if slot == 3:
            return "performing" if line[slot] != "performing" else "1-30"
        if slot == 4:
            return "mortgage" if line[slot] != "mortgage" else "leasing"
        return line[slot] + 1000

    def _s9_rebuild(world, b, record, lines):
        """A pack holding `lines`, with every aggregate of it rebuilt from those lines.

        The check's own aggregation, written out here instead of reached for in the
        stage: a hand-broken pack is only a test of the scanner if its cells still add
        up to the lines it now holds, and it is the check's job to break exactly one
        thing at a time. The forbearance block is left as it was, because breaking it
        is not one of the five things the scanner is asked.
        """
        fixed = dict(record)
        fixed["lines"] = tuple(lines)
        exposure = sum(line[5] for line in lines)
        ecl = sum(line[6] for line in lines)
        fixed["exposures"] = exposure
        fixed["ecl"] = ecl
        fixed["coverage_bp"] = _s9_coverage(ecl, exposure)
        for name, slot in S9_DIMENSIONS:
            grouped = _s9_by(lines, slot)
            cells = {}
            for key in world.order(grouped.keys(), name):
                cells[key] = _s9_aggregate(tuple(grouped[key]))
            fixed[name] = cells
        grouped = {}
        for line in lines:
            month = world.month(b.loan(line[0])["origination"])
            if month not in grouped:
                grouped[month] = {}
            if line[1] not in grouped[month]:
                grouped[month][line[1]] = []
            grouped[month][line[1]].append(line)
        cohorts = {}
        for month in sorted(grouped):
            cells = {}
            for stage in sorted(grouped[month]):
                rows = tuple(grouped[month][stage])
                held = sum(row[5] for row in rows)
                loss = sum(row[6] for row in rows)
                cells[stage] = (len(rows), held, _s9_coverage(loss, held))
            cohorts[month] = cells
        fixed["vintage"] = cohorts
        return fixed

    def _s9_broken(s, world, b, record):
        """Each of the five problems, planted one at a time and named by the scanner."""
        date = record["date"]
        lines = list(record["lines"])
        victim = lines[0][0]
        # a line removed, and the pack rebuilt so that only the population is broken
        short = _s9_rebuild(world, b, record, [line for line in lines if line[0] != victim])
        assert s.reconcile(short, b) == (("missing-loan", victim),), (
            "stage 9: a pack whose lines lost %s at %s scans to %r, not to that loan's "
            "missing-loan pair" % (victim, date, s.reconcile(short, b)))
        # the same break without rebuilding: the cells still count the line they lost
        stale = dict(record)
        stale["lines"] = tuple(line for line in lines if line[0] != victim)
        kinds = tuple(pair[0] for pair in s.reconcile(stale, b))
        assert "missing-loan" in kinds, (
            "stage 9: a pack whose lines lost %s at %s scans to %r" % (victim, date, kinds))
        assert "total-mismatch" in kinds, (
            "stage 9: a pack whose lines lost %s while its cells kept counting it scans to "
            "%r, and its cells no longer add up to its own detail" % (victim, kinds))
        # a line duplicated
        doubled = _s9_rebuild(world, b, record, lines + [lines[0]])
        assert s.reconcile(doubled, b) == (("double-counted", victim),), (
            "stage 9: a pack counting %s twice at %s scans to %r, not to that loan's "
            "double-counted pair" % (victim, date, s.reconcile(doubled, b)))
        # a line disagreeing with the bank's own record, one field at a time
        for slot in (1, 2, 3, 4, 5, 6):
            edited = _s9_rebuild(world, b, record,
                                 [line[:slot] + (_s9_disagreement(world, line, slot),)
                                  + line[slot + 1:] if line[0] == victim else line
                                  for line in lines])
            assert s.reconcile(edited, b) == (("stage-mismatch", victim),), (
                "stage 9: a pack whose line for %s says another %s at %s scans to %r, not "
                "to that loan's stage-mismatch pair"
                % (victim, S9_LINE_KEYS[slot], date, s.reconcile(edited, b)))
        # a cell's coverage edited
        cells = dict(record["by_grade"])
        key = tuple(cells)[0]
        cell = cells[key]
        cells[key] = (cell[0], cell[1], cell[2], cell[3] + 7)
        twisted = dict(record)
        twisted["by_grade"] = cells
        assert s.reconcile(twisted, b) == (("coverage-mismatch", "by_grade:%s" % (key,)),), (
            "stage 9: a pack whose by_grade:%s coverage is off by seven at %s scans to %r"
            % (key, date, s.reconcile(twisted, b)))
        # a total edited, with its own coverage kept consistent
        for total in ("exposures", "ecl"):
            broken = dict(record)
            broken[total] = record[total] + 100
            broken["coverage_bp"] = _s9_coverage(broken["ecl"], broken["exposures"])
            assert s.reconcile(broken, b) == (("total-mismatch", total),), (
                "stage 9: a pack whose %s total is out by 100 cents at %s scans to %r"
                % (total, date, s.reconcile(broken, b)))
        # the forbearance block's own coverage
        broken = dict(record)
        memo = record["forbearance"]
        broken["forbearance"] = (memo[0], memo[1], memo[2], memo[3] + 7)
        assert s.reconcile(broken, b) == (("coverage-mismatch", "forbearance"),), (
            "stage 9: a pack whose forbearance coverage is off by seven at %s scans to %r"
            % (date, s.reconcile(broken, b)))
        # a dimension whose amounts no longer add up to the lines, its coverage honest
        broken = dict(record)
        cells = dict(record["by_segment"])
        key = tuple(cells)[0]
        cell = cells[key]
        cells[key] = (cell[0], cell[1] + 100, cell[2], _s9_coverage(cell[2], cell[1] + 100))
        broken["by_segment"] = cells
        assert s.reconcile(broken, b) == (("total-mismatch", "by_segment"),), (
            "stage 9: a pack whose by_segment:%s cell holds 100 cents more than its lines "
            "at %s scans to %r" % (key, date, s.reconcile(broken, b)))
        # a cohort cell the pack's own lines do not add up to
        broken = dict(record)
        cohorts = dict((month, dict(cells)) for month, cells in record["vintage"].items())
        month = tuple(cohorts)[0]
        stage = tuple(cohorts[month])[0]
        cell = cohorts[month][stage]
        cohorts[month][stage] = (cell[0], cell[1] + 100, cell[2])
        broken["vintage"] = cohorts
        assert s.reconcile(broken, b) == (("total-mismatch", "vintage"),), (
            "stage 9: a pack whose cohorts hold 100 cents more than its lines at %s scans "
            "to %r" % (date, s.reconcile(broken, b)))
        # a line for a loan the book does not hold at the date
        gone = [row["loan"] for row in b.loans if row["loan"] not in b.on_book(date)]
        if gone:
            stray = b.status(gone[0], date)
            row = (gone[0], stray["stage"], b.grade(gone[0], date), stray["bucket"],
                   b.loan(gone[0])["segment"], stray["ead_cents"], stray["ecl_cents"])
            crowded = _s9_rebuild(world, b, record, lines + [row])
            assert s.reconcile(crowded, b) == (("missing-loan", gone[0]),), (
                "stage 9: a pack counting %s, which the book does not hold at %s, scans to "
                "%r" % (gone[0], date, s.reconcile(crowded, b)))
        # two problems at once: answered in PACK_PROBLEMS order, and both of them
        both = _s9_rebuild(world, b, record, [line for line in lines if line[0] != victim])
        cells = dict(both["by_grade"])
        key = tuple(cells)[0]
        cell = cells[key]
        cells[key] = (cell[0], cell[1], cell[2], cell[3] + 7)
        both["by_grade"] = cells
        assert s.reconcile(both, b) == (("missing-loan", victim),
                                        ("coverage-mismatch", "by_grade:%s" % (key,))), (
            "stage 9: a pack with two problems at %s scans to %r, and a scan answers every "
            "problem in PACK_PROBLEMS order" % (date, s.reconcile(both, b)))

    def _s9_refusals(s, world, b, record):
        """Every shape that cannot be the thing refuses by name, and asks the book nothing."""
        before = b.stats()
        _refuses(world.error, "stage 9: a pack at a date the book does not report",
                 lambda: s.pack(b, "1999-01-31"), ["1999"])
        _refuses(world.error, "stage 9: a vintage at a date the book does not report",
                 lambda: s.vintage(b, "1999-01-31"), ["1999"])
        stray = dict(record)
        stray["date"] = "1999-01-31"
        _refuses(world.error, "stage 9: a pack dated where the book does not report",
                 lambda: s.reconcile(stray, b), ["1999"])
        thin = dict(record)
        thin.pop("migration")
        _refuses(world.error, "stage 9: a pack with no migration",
                 lambda: s.reconcile(thin, b), ["migration"])
        stub = dict(record)
        stub["lines"] = [(1, 2, 3)]
        _refuses(world.error, "stage 9: a line that is not a line",
                 lambda: s.reconcile(stub, b), ["line"])
        rude = dict(record)
        rude["by_stage"] = "not a dimension"
        _refuses(world.error, "stage 9: a dimension that is not a dimension",
                 lambda: s.reconcile(rude, b), ["by_stage"])
        rude = dict(record)
        rude["by_bucket"] = {"performing": (1, 2)}
        _refuses(world.error, "stage 9: a cell that is not a cell",
                 lambda: s.reconcile(rude, b), ["by_bucket"])
        rude = dict(record)
        rude["by_bucket"] = {"performing": (1, "x", 3, 4)}
        _refuses(world.error, "stage 9: a cell holding something that is not a count",
                 lambda: s.reconcile(rude, b), ["by_bucket"])
        rude = dict(record)
        rude["exposures"] = "lots of cents"
        _refuses(world.error, "stage 9: an exposure total that is not a number",
                 lambda: s.reconcile(rude, b), ["exposures"])
        rude = dict(record)
        rude["ecl"] = (1,)
        _refuses(world.error, "stage 9: a loss total that is not a number",
                 lambda: s.reconcile(rude, b), ["ecl"])
        rude = dict(record)
        rude["coverage_bp"] = (1, 2)
        _refuses(world.error, "stage 9: a cell where the totals row belongs",
                 lambda: s.reconcile(rude, b), ["coverage"])
        _refuses(world.error, "stage 9: a pack that is not a pack",
                 lambda: s.reconcile((), b), ["pack"])
        after = b.stats()
        moved = {key: (before[key], after[key]) for key in before
                 if before[key] != after[key]}
        # The book's calendar is itself one of its doors: every guard has to read
        # `reporting_dates` to know that a date is not the book's, and the world
        # counts that read. What a refusal must never do is reach a loan's record.
        assert set(moved) <= {"lookups"}, (
            "stage 9: a refused call asked the book for a loan: %r" % (moved,))
        assert after["lookups"] - before["lookups"] <= 3, (
            "stage 9: the refusals read the book's calendar %d times, more than the "
            "three refused dates: %r" % (after["lookups"] - before["lookups"], moved))

    def _s9_workload(s, world, b):
        """One whole pass of the stage over the dates the population changes at."""
        answers = []
        for date in _s9_edges(b)[:4]:
            record = s.pack(b, date)
            answers.append((date, record, s.vintage(b, date), s.reconcile(record, b)))
        return tuple(answers)

    def _s9_twice(s, world, b):
        """The same workload twice: a pack read off a dict's order would differ here."""
        one = _s9_workload(s, world, b)
        two = _s9_workload(s, world, b)
        assert one == two, (
            "stage 9: two passes of the same workload answer differently — the pack is not "
            "a function of its inputs")

    import book
    import dates
    import rules
    import stage_09 as s
    world = _World(dates, rules, book.BookError)
    _s9_constants(s)
    b = book.Book.build(7)
    for date in _s9_edges(b):
        record = _s9_pack(s, world, b, date)
        assert s.reconcile(record, b) == (), (
            "stage 9: a pack this stage built at %s scans to %r, not to ()"
            % (date, s.reconcile(record, b)))
    last = _s9_pack(s, world, b, b.reporting_dates[-1])
    _s9_broken(s, world, b, last)
    _s9_refusals(s, world, b, last)
    _s9_empty(s, world)
    _s9_twice(s, world, b)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-lifecycle-from-scratch"

    B10_KEYS = ("grade", "predicted_bp", "observed_bp", "loans", "defaults",
                "chi2_x100", "verdict")

    J10_KEYS = ("component", "delta_cents", "why")

    C10_CHECKS = ("monotonic", "in-range", "row-sum", "as-of", "versioned")

    C10_COMPONENTS = ("pd", "lgd", "ccf", "grades", "other")

    C10_GRADED = ("A", "B", "C", "D", "E", "F")

    def _repo(start=None):
        for candidate_start in (os.environ.get("M1_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "book.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M1_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked against
        the message: an exception of the right family raised for the wrong reason is not
        the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _b10_pd(pd_bp, grade, months):
        """The artifact's cumulative PD over `months` months, linear in months, truncated."""
        row = pd_bp[grade]
        whole = months // 12
        rest = months - whole * 12
        if whole >= len(row):
            return row[-1]
        if whole == 0:
            return row[0] * months // 12
        left = row[whole - 1]
        return left if rest == 0 else left + (row[whole] - left) * rest // 12

    def _b10_signalled(book):
        """Every date the book signalled a default, by loan id."""
        found = {}
        for row in book.defaults():
            found.setdefault(row["loan"], []).append(row["signalled_on"])
        return found

    def _b10_within(signalled, loan_id, start, end):
        for date in signalled.get(loan_id, ()):
            if start < date <= end:
                return True
        return False

    def _b10_population(book, start, end, grade):
        """The check's own cohort and its default count, from the book's own two records."""
        signalled = _b10_signalled(book)
        population = [loan for loan in book.loans() if book.grade(loan, start) == grade]
        defaults = len([loan for loan in population
                        if _b10_within(signalled, loan["loan"], start, end)])
        return population, defaults

    def _b10_term(defaults, expected):
        """The grade's own share of the statistic: zero where its expectation truncates."""
        if expected == 0:
            return 0
        return (defaults - expected) ** 2 * 100 // expected

    def _b10_months(start, end, dates):
        first = dates.parse(start)
        last = dates.parse(end)
        return (last[0] - first[0]) * 12 + (last[1] - first[1])

    def _b10_verdict(statistic, realised, wanted, counted, rules):
        """The portfolio's verdict: the table at this many cohorts' freedom, then the way."""
        if counted < 2:
            return "insufficient-data"
        if statistic <= rules.CHI2_CRITICAL_X100[counted - 1]:
            return "within-tolerance"
        return "under-predicting" if realised > wanted else "over-predicting"

    def _b10_artifact(book, rows, lgd_bp=None, ccf_bp=None, grades=None,
                      name="syn-backtest", version=9, as_of="2032-01-31"):
        """A synthetic artifact with the contract's seven fields, everything valid."""
        if lgd_bp is None:
            lgd_bp = dict((grade, 4500) for grade in rules.GRADES)
        if ccf_bp is None:
            ccf_bp = dict((segment, 6000) for segment in rules.SEGMENTS)
        if grades is None:
            grades = dict((loan["loan"], loan["grade_origination"]) for loan in book.loans())
        return {"name": name, "version": version, "as_of": as_of, "grades": grades,
                "pd_bp": rows, "lgd_bp": lgd_bp, "ccf_bp": ccf_bp}

    def _b10_flat(book, prediction, **rest):
        """The book's own model with every grade's term structure flat at one rate."""
        rows = dict((grade, (prediction, prediction, prediction, prediction))
                    for grade in rules.GRADES)
        return _b10_artifact(book, rows, **rest)

    def _b10_expected(book, model, start, end, dates, rules):
        """The rows the check's own arithmetic says the stage must answer."""
        months = _b10_months(start, end, dates)
        rows = []
        statistic = realised = wanted = counted = 0
        for grade in C10_GRADED:
            population, defaults = _b10_population(book, start, end, grade)
            loans = len(population)
            predicted = _b10_pd(model["pd_bp"], grade, months)
            term = 0
            if loans:
                expected = predicted * loans // 10000
                term = _b10_term(defaults, expected)
                statistic += term
                realised += defaults
                wanted += expected
                if expected:
                    counted += 1
            rows.append({"grade": grade, "predicted_bp": predicted,
                         "observed_bp": None if loans == 0 else defaults * 10000 // loans,
                         "loans": loans, "defaults": defaults, "chi2_x100": term})
        verdict = _b10_verdict(statistic, realised, wanted, counted, rules)
        return tuple(dict(row, verdict=verdict) for row in rows)

    def _b10_check_rows(s, book, model, start, end, dates, rules):
        """One whole backtest, held against the check's own arithmetic, row for row."""
        expected = _b10_expected(book, model, start, end, dates, rules)
        got = s.backtest(book, model, start, end)
        for row in got:
            assert tuple(row.keys()) == B10_KEYS, (
                "a backtest row's fields are %r, not %r" % (tuple(row.keys()), B10_KEYS))
        assert got == expected, (
            "the backtest over %s..%s answered\n  %r\nand the check's own arithmetic says"
            "\n  %r" % (start, end, got, expected))
        return got

    def _b10_rows(book, windows, rise=True):
        """Rows that keep every cohort of every window expecting a default.

        The floor for a grade is the tightest of its cohorts over the windows: with
        `loans` loans there, `ceil(10000 / loans)` is the lowest predicted rate that
        still expects one default, and the contract refuses below it. The rows start at
        that floor and rise to the lifetime so the term structure's own interpolation is
        reachable; `rise=False` flattens them at the lifetime instead.
        """
        rows = {}
        for grade in C10_GRADED:
            smallest = None
            for start, end in windows:
                population, _ = _b10_population(book, start, end, grade)
                if population and (smallest is None or len(population) < smallest):
                    smallest = len(population)
            floor = 10000 if smallest is None else (10000 + smallest - 1) // smallest
            if floor >= 10000 or not rise:
                rows[grade] = (10000, 10000, 10000, 10000)
                continue
            step = (10000 - floor) // 3
            rows[grade] = (floor, floor + step, floor + 2 * step, 10000)
        rows["default"] = (10000, 10000, 10000, 10000)
        return rows

    def _b10_high(book, windows):
        """An artifact whose every cohort of every window expects at least one default."""
        return _b10_artifact(book, _b10_rows(book, windows), name="syn-high")

    def _b10_short(book, windows):
        """The same artifact with a two-year table, so the clamp past it is reachable."""
        rows = dict((grade, (row[0], row[-1],))
                    for grade, row in _b10_rows(book, windows).items())
        return _b10_artifact(book, rows, name="syn-short")

    def _b10_backtest(s, world, dates, rules):
        """The cohort counts, the book's own rate, the statistic and the verdict."""
        book = world.Book.build(7)
        report = book.reporting_dates
        windows = ((report[0], report[6]), (report[0], report[12]),
                   (report[12], report[-1]), (report[0], report[-1]))
        models = (book.model_in_force(report[-1]), _b10_high(book, windows),
                  _b10_short(book, windows), _b10_flat(book, 10000))
        for model in models:
            for start, end in windows:
                rows = _b10_check_rows(s, book, model, start, end, dates, rules)
                months = _b10_months(start, end, dates)
                for row in rows:
                    population, defaults = _b10_population(book, start, end, row["grade"])
                    if not population:
                        assert row["observed_bp"] is None, (
                            "a grade with no loans cannot have an observed rate, and %s "
                            "answered %r" % (row["grade"], row["observed_bp"]))
                    assert row["observed_bp"] == book.observed_default_rate(
                        row["grade"], months, start, end), (
                        "grade %s's rate is not the book's own answer for %s..%s"
                        % (row["grade"], start, end))
        rows = _b10_check_rows(s, book, models[0], report[0], report[-1], dates, rules)
        assert tuple(row["grade"] for row in rows) == C10_GRADED, (
            "the rows must be the graded ratings in GRADES order and no default row, "
            "and they were %r" % (tuple(row["grade"] for row in rows),))
        return book, report

    def _b10_direction(s, world, dates, rules):
        """The direction on the book's own data: the window where it is reachable.

        `lgd-workout` v1 is the artifact the world keeps out of force — its `as_of` is
        after the last reporting date — and its term structure predicts a whole horizon
        of default for the two grades that are still performing at the start of
        2032-09-30. Over the twelve months to 2033-09-30 those two grades carry five
        loans between them, nothing defaults, and the terms are 300 and 200: five hundred
        against the table's one-freedom value of 384, with no defaults against five
        expected. That is the book's own data answering `over-predicting`, not a
        synthetic artifact, and it is the only window family in the book where the
        statistic clears its own critical value at all.
        """
        book = world.Book.build(7)
        report = book.reporting_dates
        model = book.model("lgd-workout", 1)
        assert model["as_of"] > report[-1], (
            "the check aimed this case at an artifact the book would have in force")
        start, end = "2032-09-30", "2033-09-30"
        assert start in report and end in report, (
            "the window the check aims the direction at is not a window of the book")
        got = _b10_check_rows(s, book, model, start, end, dates, rules)
        counted = [row for row in got if row["loans"] and row["loans"] * row["predicted_bp"] // 10000]
        assert tuple(row["grade"] for row in counted) == ("C", "E"), (
            "the buckets this window measures are %r, and the check aims at C and E"
            % (tuple(row["grade"] for row in counted),))
        assert [row["chi2_x100"] for row in counted] == [300, 200], (
            "the window's own terms are %r, and the check aims at 500 between them"
            % ([row["chi2_x100"] for row in counted],))
        total = sum(row["chi2_x100"] for row in got)
        assert total > rules.CHI2_CRITICAL_X100[len(counted) - 1], (
            "the statistic of %d is inside the table's %d-freedom value %d, so the "
            "direction is not reachable after all"
            % (total, len(counted) - 1, rules.CHI2_CRITICAL_X100[len(counted) - 1]))
        assert sum(row["defaults"] for row in got) < sum(
            row["loans"] * row["predicted_bp"] // 10000 for row in counted), (
            "the window's defaults do not fall short, so the direction aimed is wrong")
        assert got[0]["verdict"] == "over-predicting", (
            "no defaults against five expected past the table's %d-freedom value is "
            "over-predicting on the book's own data, and the verdict was %r"
            % (len(counted) - 1, got[0]["verdict"]))

    def _b10_windows(s, world, dates, rules):
        """Every twelve-month window of the book, and the defaults each one earns."""
        book = world.Book.build(7)
        report = book.reporting_dates
        signalled = _b10_signalled(book)
        assert signalled, "the book must signal at least one default"
        windows = tuple((report[first], report[first + 12])
                        for first in range(len(report) - 12))
        model = _b10_high(book, windows)
        endings = 0
        for start, end in windows:
            expected = _b10_expected(book, model, start, end, dates, rules)
            assert expected is not None, (
                "the check aimed a model that must refuse at %s..%s" % (start, end))
            got = s.backtest(book, model, start, end)
            assert got == expected, (
                "the window %s..%s answered\n  %r\nand the check's own counts say\n  %r"
                % (start, end, got, expected))
            for row in got:
                population, defaults = _b10_population(book, start, end, row["grade"])
                assert row["defaults"] == defaults, (
                    "the window %s..%s counts %d defaults in grade %s and the book signals "
                    "%d" % (start, end, row["defaults"], row["grade"], defaults))
            if any(signalled.get(loan, ()) and signalled[loan][0] == end
                   for loan in signalled):
                endings += 1
        assert endings >= 1, (
            "no twelve-month window of the book ends on a signalled default, so the "
            "window's own closed end is not reachable and the check cannot see it")

    class _B10Ledger:
        """A stand-in book: the records the backtest reads, sized by the check.

        The world's own book is twelve loans, so no cohort of it can push a statistic
        past the table's critical value and no window of it can empty every cohort. The
        backtest reads four things — `loans()`, `grade(loan, date)`, `defaults()` and
        `reporting_dates` — so the check can hand it a ledger exactly as large and as
        shaped as the boundary being checked, one loan of one grade at a time.
        """

        def __init__(self, reporting_dates, cohorts, start, end):
            self.reporting_dates = reporting_dates
            self._start = start
            self._records = []
            self._grades = {}
            self._signalled = {}
            self._defaults = []
            for grade in sorted(cohorts):
                loans, defaults = cohorts[grade]
                for index in range(loans):
                    loan_id = "%s-%04d" % (grade, index)
                    self._records.append({"loan": loan_id})
                    self._grades[loan_id] = grade
                    if index < defaults:
                        self._signalled[loan_id] = end
                        self._defaults.append({"loan": loan_id, "signalled_on": end})

        def loans(self):
            """Every record the ledger carries, in the grades' own order."""
            return tuple(self._records)

        def grade(self, loan, date):
            """The grade the ledger recorded at the date: the signal makes it defaulted."""
            loan_id = loan["loan"] if isinstance(loan, dict) else loan
            signalled = self._signalled.get(loan_id)
            if signalled is not None and date >= signalled:
                return "default"
            return self._grades[loan_id]

        def defaults(self):
            """Every signalled default the ledger carries."""
            return tuple(self._defaults)

    def _b10_ledger_model(ledger, rates):
        """A flat artifact over the check's own ledger: a rate per grade, or one for all."""
        rows = {}
        for grade in C10_GRADED + ("default",):
            rate = rates.get(grade, 10000) if isinstance(rates, dict) else rates
            rows[grade] = (rate, rate, rate, rate)
        grades = dict((loan["loan"], ledger.grade(loan, ledger.reporting_dates[0]))
                      for loan in ledger.loans())
        return _b10_artifact(ledger, rows, grades=grades, name="syn-ledger")

    def _b10_ledger_rows(s, ledger, rates, start, end, dates):
        """One backtest over the check's own ledger, held against the check's own arithmetic."""
        model = _b10_ledger_model(ledger, rates)
        got = s.backtest(ledger, model, start, end)
        expected = _b10_expected(ledger, model, start, end, dates, rules)
        assert got == expected, (
            "the ledger of %d loans answered\n  %r\nand the check's own arithmetic says\n"
            "  %r" % (len(ledger.loans()), got, expected))
        return got

    def _b10_ledgers(s, world, dates, rules):
        """The verdict's own boundaries: its table, its direction and its empty case.

        Every cohort here is the check's own ledger, because the statistic's headroom is
        the cohort's size: twelve loans that realise three defaults against one expected
        default is a term of `400`, past the one-freedom value and inside the two-freedom
        one, and no cohort the world's twelve-loan book carries can reach either. Each
        case is aimed at a statistic that sits one side of the value its own count of
        cohorts gives and the other side of the neighbouring value, so a stage that read
        the table at any other freedom answers differently.
        """
        report = world.Book.build(7).reporting_dates
        start, end = report[0], report[12]
        table = rules.CHI2_CRITICAL_X100

        def ledger(cohorts):
            return _B10Ledger(report, cohorts, start, end)

        # 1. one cohort: the table carries no value at zero degrees of freedom, so
        #    there is nothing to read and the answer says so rather than raising.
        got = _b10_ledger_rows(s, ledger({"A": (12, 3)}), 1000, start, end, dates)
        assert got[0]["verdict"] == "insufficient-data", (
            "one cohort leaves no freedom for the table and the verdict was %r"
            % (got[0]["verdict"],))

        # 2. two cohorts: five hundred — past the one-freedom value, inside the
        #    two-freedom one — and three defaults against two expected, so under.
        got = _b10_ledger_rows(s, ledger({"A": (12, 3), "B": (12, 0)}), 1000,
                               start, end, dates)
        total = sum(row["chi2_x100"] for row in got)
        assert table[1] < total <= table[2], (
            "the check aimed a statistic of %d and the two-freedom value is %d, so it "
            "cannot see which freedom the stage read" % (total, table[2]))
        assert got[0]["verdict"] == "under-predicting", (
            "a statistic of %d with three defaults against two expected is "
            "under-predicting, and the verdict was %r" % (total, got[0]["verdict"]))

        # 3. and nothing against five expected is over-predicting.
        got = _b10_ledger_rows(s, ledger({"A": (12, 0), "B": (12, 0)}),
                               {"A": 1000, "B": 3400}, start, end, dates)
        total = sum(row["chi2_x100"] for row in got)
        assert table[1] < total <= table[2], (
            "the check aimed a statistic of %d and the two-freedom value is %d"
            % (total, table[2]))
        assert got[0]["verdict"] == "over-predicting", (
            "a statistic of %d with nothing defaulted against five expected is "
            "over-predicting, and the verdict was %r" % (total, got[0]["verdict"]))

        # 4. three cohorts, four hundred and fifty: inside the three-freedom value it
        #    should be read at, and past the two-freedom one below it.
        got = _b10_ledger_rows(s, ledger({"A": (12, 5), "B": (12, 1), "C": (12, 2)}),
                               {"A": 1700, "B": 1000, "C": 1700}, start, end, dates)
        total = sum(row["chi2_x100"] for row in got)
        assert table[1] < total <= table[2], (
            "the check aimed a statistic of %d and the three-freedom value is %d"
            % (total, table[2]))
        assert got[0]["verdict"] == "within-tolerance", (
            "a statistic of %d is inside the three-freedom value %d and the verdict was "
            "%r" % (total, table[2], got[0]["verdict"]))

        # 5. three cohorts, seven hundred: past the three-freedom value, inside the
        #    four-freedom one above it.
        got = _b10_ledger_rows(s, ledger({"A": (12, 0), "B": (12, 0), "C": (12, 0)}),
                               {"A": 1000, "B": 1700, "C": 3400}, start, end, dates)
        total = sum(row["chi2_x100"] for row in got)
        assert table[2] < total <= table[3], (
            "the check aimed a statistic of %d and the four-freedom value is %d"
            % (total, table[3]))
        assert got[0]["verdict"] == "over-predicting", (
            "a statistic of %d past the three-freedom value %d with nothing defaulted is "
            "over-predicting, and the verdict was %r"
            % (total, table[2], got[0]["verdict"]))

        # 6. a cohort whose expectation truncates to zero answers its counts and a term
        #    of zero, and it is not a freedom: with it counted the table would be read at
        #    two freedoms, and four hundred is inside that value and past the one.
        empty = ledger({"A": (12, 0), "B": (12, 1), "C": (12, 3)})
        got = _b10_ledger_rows(s, empty, {"A": 100, "B": 1000, "C": 1000},
                               start, end, dates)
        assert [(row["loans"], row["defaults"], row["chi2_x100"])
                for row in got[:3]] == [(12, 0, 0), (12, 1, 0), (12, 3, 400)], (
            "the ledger's own three cohorts answered %r"
            % ([(row["loans"], row["defaults"], row["chi2_x100"]) for row in got[:3]],))
        assert got[0]["observed_bp"] == 0 and got[0]["predicted_bp"] == 100, (
            "the truncated cohort's own rates are %r"
            % ({key: got[0][key] for key in ("predicted_bp", "observed_bp")},))
        total = sum(row["chi2_x100"] for row in got)
        assert table[1] < total <= table[2], (
            "the check aimed a statistic of %d against the one-freedom value %d"
            % (total, table[1]))
        assert got[0]["verdict"] == "under-predicting", (
            "four defaults against two expected past the one-freedom value is "
            "under-predicting, and the verdict was %r (statistic %d)"
            % (got[0]["verdict"], total))
        got = _b10_ledger_rows(s, ledger({"A": (12, 0)}), 100, start, end, dates)
        assert got[0]["verdict"] == "insufficient-data", (
            "one truncated cohort leaves no freedom for the table and the verdict was %r"
            % (got[0]["verdict"],))

        # 7. no cohort at all: there is nothing to read a tolerance from either.
        none = ledger({"default": (3, 0)})
        got = _b10_ledger_rows(s, none, 100, start, end, dates)
        assert all(row["loans"] == 0 for row in got), (
            "a ledger with no graded loan has no cohort, and the rows carried %r"
            % ([row["loans"] for row in got],))
        assert all(row["verdict"] == "insufficient-data" for row in got), (
            "a backtest in which no grade carries a cohort is insufficient-data, and the "
            "verdicts were %r" % ([row["verdict"] for row in got],))

    def _b10_refuses(s, world, dates, rules):
        """Every shape the backtest cannot answer raises, and a refusal asks for nothing."""
        book = world.Book.build(7)
        report = book.reporting_dates
        model = book.model_in_force(report[-1])
        before = dict(book.stats())
        broken = dict(model)
        del broken["pd_bp"]
        _refuses(world.BookError, "an artifact with no term structure",
                 lambda: s.backtest(book, broken, report[0], report[-1]),
                 [model["name"]])
        _refuses(world.BookError, "an artifact that is not an artifact",
                 lambda: s.backtest(book, "pd-rating", report[0], report[-1]),
                 ["backtest's model"])
        assert dict(book.stats()) == before, (
            "a refused backtest asked the book for something: %r became %r"
            % (before, dict(book.stats())))
        _refuses(world.BookError, "a start the book does not cover",
                 lambda: s.backtest(book, model, "2030-01-31", report[-1]),
                 ["2030-01-31"])
        _refuses(world.BookError, "an end the book does not cover",
                 lambda: s.backtest(book, model, report[0], "2034-12-31"),
                 ["2034-12-31"])
        _refuses(world.BookError, "a window that ends before it starts",
                 lambda: s.backtest(book, model, report[-1], report[0]), [report[0]])

    def _b10_monotonic(model):
        for grade in model["pd_bp"]:
            row = model["pd_bp"][grade]
            for step in range(1, len(row)):
                if row[step] < row[step - 1]:
                    return "fail"
        return "pass"

    def _b10_in_range(model, rules):
        if any(value < 0 or value > 10000
               for grade in model["pd_bp"] for value in model["pd_bp"][grade]):
            return "fail"
        if any(value < rules.LGD_FLOOR_BP or value > rules.LGD_CAP_BP
               for value in model["lgd_bp"].values()):
            return "fail"
        if any(value < rules.CCF_FLOOR_BP or value > rules.CCF_CAP_BP
               for value in model["ccf_bp"].values()):
            return "fail"
        return "pass"

    def _b10_row_sum(model):
        for grade in model["pd_bp"]:
            row = model["pd_bp"][grade]
            if not row or row[-1] > 10000 or any(value > row[-1] for value in row):
                return "fail"
        return "pass"

    def _b10_asof(book, model, dates):
        dates.parse(model["as_of"])
        return "pass" if model["as_of"] <= book.reporting_dates[-1] else "fail"

    def _b10_versioned(book, model):
        name, version = model["name"], model["version"]
        if not isinstance(name, str) or not name or version < 1:
            return "fail"
        same = [row for row in book.models
                if row["name"] == name and row["version"] == version]
        return "pass" if len(same) <= 1 else "fail"

    def _b10_expected_checks(book, model, dates, rules):
        """The five verdicts the contract's own rules give, recomputed here."""
        return (("monotonic", _b10_monotonic(model)),
                ("in-range", _b10_in_range(model, rules)),
                ("row-sum", _b10_row_sum(model)),
                ("as-of", _b10_asof(book, model, dates)),
                ("versioned", _b10_versioned(book, model)))

    def _b10_validate(s, world, dates, rules):
        """One verdict per check and in order, on the book's artifacts and on broken ones."""
        book = world.Book.build(7)
        report = book.reporting_dates
        for model in book.models:
            got = s.validate(book, model)
            assert isinstance(got, tuple) and len(got) == len(C10_CHECKS), (
                "validate answered %r instead of one pair per check" % (got,))
            assert tuple(name for name, _ in got) == C10_CHECKS, (
                "the checks must come back in MODEL_CHECKS order, and they were %r"
                % (tuple(name for name, _ in got),))
            for name, verdict in got:
                assert verdict in ("pass", "fail"), (
                    "%s answered %r, and a check is `pass` or `fail`" % (name, verdict))
            assert got == _b10_expected_checks(book, model, dates, rules), (
                "the book's own artifact %r validated as %r and the rules say %r"
                % (model["name"], got, _b10_expected_checks(book, model, dates, rules)))
        good = _b10_flat(book, 120)
        synthetic = (
            ("a PD that falls with the horizon",
             dict(good, pd_bp=dict(good["pd_bp"], A=(40, 120, 60, 200)))),
            ("a lifetime PD above 10000",
             dict(good, pd_bp=dict(good["pd_bp"], A=(40, 120, 200, 10001)))),
            ("an LGD above the policy's cap",
             dict(good, lgd_bp=dict((grade, rules.LGD_CAP_BP + 1) for grade in rules.GRADES))),
            ("a CCF below the policy's floor",
             dict(good, ccf_bp=dict((segment, rules.CCF_FLOOR_BP - 1)
                                    for segment in rules.SEGMENTS))),
            ("an as_of after the window the book covers",
             dict(good, as_of=dates.add_months(report[-1], 1))),
            ("an as_of inside the window the book covers",
             dict(good, as_of=report[-1])),
            ("a version the book already carries",
             dict(good, name=book.models[0]["name"], version=book.models[0]["version"])),
            ("a version below one", dict(good, version=0)),
        )
        for what, model in synthetic:
            got = s.validate(book, model)
            assert got == _b10_expected_checks(book, model, dates, rules), (
                "%s validated as %r and the rules say %r"
                % (what, got, _b10_expected_checks(book, model, dates, rules))
                )
        broken = dict(good)
        del broken["pd_bp"]
        before = dict(book.stats())
        _refuses(world.BookError, "an artifact with no term structure",
                 lambda: s.validate(book, broken), ["syn-backtest"])
        assert dict(book.stats()) == before, (
            "a refused validate asked the book for something: %r became %r"
            % (before, dict(book.stats())))

    def _b10_freeze(value):
        """A value's own content as a comparable structure, independent of dict order."""
        if isinstance(value, dict):
            return tuple(sorted((key, _b10_freeze(value[key])) for key in value))
        if isinstance(value, (tuple, list)):
            return tuple(_b10_freeze(item) for item in value)
        return value

    def _b10_stages(seven, book, date, model):
        """The stage each loan sits in at the date under one artifact, by loan id."""
        found = {}
        for loan_id in book.on_book(date):
            stage = seven.stage(book, book.loan(loan_id), date, model=model)
            found[loan_id] = stage["stage"]
        return found

    def _b10_provision(six, book, date, model, stages, rules):
        """The provision at the date under one artifact, weighted by the policy's own."""
        total = 0
        for loan_id in book.on_book(date):
            loan = book.loan(loan_id)
            for scenario in rules.SCENARIOS:
                record = six.ecl(book, loan, date, scenario, stage=stages[loan_id],
                                 model=model)
                total += record["ecl_cents"] * rules.SCENARIO_WEIGHTS_BP[scenario] // 10000
        return total

    def _b10_journal_rows(six, seven, book, date, old, new, rules):
        """The five components and their cents, recomputed by the pinned recipe."""
        stages = _b10_stages(seven, book, date, old)
        previous = _b10_provision(six, book, date, old, stages, rules)
        rows = []
        view = old
        for field, component in (("pd_bp", "pd"), ("lgd_bp", "lgd"),
                                 ("ccf_bp", "ccf"), ("grades", "grades")):
            view = dict(view)
            view[field] = new[field]
            reached = _b10_provision(six, book, date, view, stages, rules)
            rows.append((component, reached - previous))
            previous = reached
        total = _b10_provision(six, book, date, new,
                               _b10_stages(seven, book, date, new), rules)
        rows.append(("other", total - previous))
        return rows

    def _b10_journal(s, world, dates, rules, six, seven):
        """The journal's rows, its total movement, its residual — and the untouched book."""
        book = world.Book.build(7)
        report = book.reporting_dates
        old = book.model("pd-rating", 1)
        new = book.model("pd-rating", 2)
        before = tuple(_b10_freeze(model) for model in book.models)
        for date in (report[-1], report[12]):
            got = s.journal(book, old, new, date)
            assert isinstance(got, tuple), "the journal is a tuple of rows, and it was %r" % (got,)
            for row in got:
                assert tuple(row.keys()) == J10_KEYS, (
                    "a journal row's fields are %r, not %r" % (tuple(row.keys()), J10_KEYS))
                assert isinstance(row["delta_cents"], int), (
                    "a journal delta is an integer count of cents, and %r arrived"
                    % (row["delta_cents"],))
                assert isinstance(row["why"], str) and row["why"].strip(), (
                    "the %s row carries no reason: %r" % (row["component"], row["why"]))
            assert tuple(row["component"] for row in got) == C10_COMPONENTS, (
                "the components come back in the pinned order, and they were %r"
                % (tuple(row["component"] for row in got),))
            expected = _b10_journal_rows(six, seven, book, date, old, new, rules)
            assert [(row["component"], row["delta_cents"]) for row in got] == expected, (
                "the journal at %s answered\n  %r\nand the pinned recipe says\n  %r"
                % (date, [(row["component"], row["delta_cents"]) for row in got], expected))
            assert any(row["delta_cents"] for row in got[:4]), (
                "the two artifacts of %s differ and not one component moved, which is what "
                "a journal that ignored the artifact it was handed would answer"
                % (old["name"],))
            moved = sum(row["delta_cents"] for row in got)
            assert moved == got[-1]["delta_cents"] + sum(row["delta_cents"]
                                                         for row in got[:-1]), (
                "the deltas do not sum to the total movement the last row closes")
        after = tuple(_b10_freeze(model) for model in book.models)
        assert after == before, (
            "the journal changed the book's own artifacts, and the book is read-only")

        # The book's own two versions of one rating move the tables, not the staging: a
        # loan the record re-rated crosses no boundary under either. So the staging's own
        # step of the journal — the `other` row — is aimed here with a pair of synthetic
        # artifacts whose term structures put a re-rated loan in two different stages:
        # under the old one the current grade is as safe as the origination grade it is
        # compared with, and under the new one it is far worse, which is exactly the
        # movement the residual exists to report rather than absorb.
        flat = dict((grade, (1, 1, 1, 1)) for grade in C10_GRADED)
        flat["default"] = (10000, 10000, 10000, 10000)
        steep = dict(flat, C=(9000, 9000, 9000, 9000), D=(9000, 9000, 9000, 9000))
        old_syn = _b10_artifact(book, flat, name="syn-journal", version=1,
                                as_of=report[0])
        new_syn = _b10_artifact(book, steep, name="syn-journal", version=2,
                                as_of=report[0])
        got = s.journal(book, old_syn, new_syn, report[-1])
        expected = _b10_journal_rows(six, seven, book, report[-1], old_syn, new_syn, rules)
        assert [(row["component"], row["delta_cents"]) for row in got] == expected, (
            "the synthetic journal answered\n  %r\nand the pinned recipe says\n  %r"
            % ([(row["component"], row["delta_cents"]) for row in got], expected))
        assert got[0]["delta_cents"] != 0, (
            "the two artifacts' term structures differ by nine thousand basis points and "
            "the PD row moved nothing: %r" % (got[0],))
        assert got[-1]["delta_cents"] != 0, (
            "the new artifact stages a loan the old one does not, and the residual that "
            "reports it answered %d" % (got[-1]["delta_cents"],))
        assert got[-1]["delta_cents"] != got[0]["delta_cents"], (
            "the residual is not the PD row's own movement: %r" % (got,))
        _refuses(world.BookError, "a date the book does not cover",
                 lambda: s.journal(book, old, new, "2034-01-31"), ["2034-01-31"])
        stats = dict(book.stats())
        broken = dict(old)
        del broken["ccf_bp"]
        _refuses(world.BookError, "an old artifact with no CCF table",
                 lambda: s.journal(book, broken, new, report[-1]), [old["name"]])
        _refuses(world.BookError, "a new artifact with no CCF table",
                 lambda: s.journal(book, old, broken, report[-1]), [old["name"]])
        assert dict(book.stats()) == stats, (
            "a refused journal asked the book for something: %r became %r"
            % (stats, dict(book.stats())))

    def _b10_constants(s):
        """The three public constants, in order: a mutation that moves one is caught."""
        assert tuple(s.BACKTEST_KEYS) == B10_KEYS, (
            "BACKTEST_KEYS is %r, and a backtest row is (%s)"
            % (s.BACKTEST_KEYS, ", ".join(B10_KEYS)))
        assert tuple(s.JOURNAL_KEYS) == J10_KEYS, (
            "JOURNAL_KEYS is %r, and a journal row is (%s)"
            % (s.JOURNAL_KEYS, ", ".join(J10_KEYS)))
        assert tuple(s.MODEL_CHECKS) == C10_CHECKS, (
            "MODEL_CHECKS is %r, and `validate` returns (%s)"
            % (s.MODEL_CHECKS, ", ".join(C10_CHECKS)))

    def _b10_twice(s, world, dates, rules):
        """One whole workload, twice: a stage is a function of its inputs."""

        def workload():
            book = world.Book.build(7)
            report = book.reporting_dates
            return (s.backtest(book, book.model_in_force(report[-1]),
                               report[0], report[-1]),
                    s.validate(book, book.model("pd-rating", 2)),
                    s.journal(book, book.model("pd-rating", 1),
                              book.model("pd-rating", 2), report[-1]))

        assert workload() == workload(), (
            "two runs of one workload answered differently, so a run is not a function "
            "of its inputs")

    global dates, rules
    import book as world
    import dates
    import rules
    import stage_06 as six
    import stage_07 as seven
    import stage_10 as s
    _b10_constants(s)
    _b10_backtest(s, world, dates, rules)
    _b10_windows(s, world, dates, rules)
    _b10_direction(s, world, dates, rules)
    _b10_ledgers(s, world, dates, rules)
    _b10_refuses(s, world, dates, rules)
    _b10_validate(s, world, dates, rules)
    _b10_journal(s, world, dates, rules, six, seven)
    _b10_twice(s, world, dates, rules)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The schedule, the day count and the rate that discounts it",
        tags=["eir", "amortisation", "discounting"],
        action="Write `FLOW_KEYS`, `SCHEDULE_KEYS`, `EIR_KEYS`, `schedule`, "
               "`level_payment`, `present_value` and `effective_rate` in "
               "stage_01.py.",
        predict="How a loan is paid off when the rate is an integer count of "
                "basis points and the balance is truncated to the cent at every "
                "step, and what an interest rate leaves behind when it is searched "
                "for in whole basis points.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The bucket, the materiality threshold and the new definition of default",
        tags=["default", "dpd", "policy"],
        action="Write `BUCKET_KEYS`, `DEFAULT_KEYS`, `dpd`, `bucket`, `defaults` "
               "and `triggers` in stage_02.py.",
        predict="What the 90-days-past-due backstop does to a loan whose arrears "
                "are small enough not to count, and how long a cure has to hold "
                "before a default ends.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The migration matrix, the term structure and the lifetime PD",
        tags=["pd", "migration", "survival"],
        action="Write `MATRIX_KEYS`, `PD_KEYS`, `migration`, `rates`, "
               "`term_structure` and `lifetime_pd` in stage_03.py.",
        predict="What rounding a transition row to basis points does to its total, "
                "and how a marginal default probability differs from the "
                "cumulative one a lifetime PD needs.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The recovery cash flows and the loss given default",
        tags=["lgd", "recovery", "discounting"],
        action="Write `RECOVERY_KEYS`, `LGD_KEYS`, `recoveries`, `lgd` and "
               "`lgd_by_segment` in stage_04.py.",
        predict="Why a recovery collected two years after a default is worth less "
                "than its amount, and which denominator makes a loss given default "
                "a loss.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The drawn balance, the undrawn limit and the exposure at default",
        tags=["ead", "ccf", "facilities"],
        action="Write `EAD_KEYS`, `ccf`, `ead` and `ead_at_default` in stage_05.py.",
        predict="What a revolving facility's undrawn limit does to an exposure, and "
                "how a credit conversion factor is estimated from the bank's own "
                "defaults rather than assumed.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The expected credit loss, its horizon and its scenarios",
        tags=["ecl", "provisioning", "scenarios"],
        action="Write `ECL_KEYS`, `WEIGHTED_KEYS`, `ecl` and `weighted_ecl` in "
               "stage_06.py.",
        predict="Why the same loan provisions twelve months or its whole life "
                "depending on a test elsewhere, and where the cent of an expected "
                "loss is won and lost.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The three stages and the significant increase in credit risk",
        tags=["ifrs9", "staging", "sicr"],
        action="Write `STAGE_KEYS`, `TRANSFER_KEYS`, `stage`, `sicr` and "
               "`transfers` in stage_07.py.",
        predict="When a loan has deteriorated enough to leave stage 1, and how many "
                "reporting dates of improvement it takes to come back.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The provision roll-forward, line by line",
        tags=["roll-forward", "pl", "oci"],
        action="Write `ROLLFORWARD_KEYS`, `LINES` and `rollforward` in "
               "stage_08.py.",
        predict="Which of the movements between two reporting dates is the passage "
                "of time and which is a change of model, and what a bank does with "
                "the part its own lines do not explain.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The reporting pack and the reconciliation that holds it",
        tags=["reporting", "coverage", "vintage"],
        action="Write `PACK_KEYS`, `PACK_PROBLEMS`, `pack`, `reconcile` and "
               "`vintage` in stage_09.py.",
        predict="What a coverage ratio's denominator has to be for the number to "
                "mean anything, and where a pack can count a loan twice without "
                "noticing.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The backtest, the model artifact and the journal of the delta",
        tags=["backtest", "validation", "attribution"],
        action="Write `BACKTEST_KEYS`, `JOURNAL_KEYS`, `MODEL_CHECKS`, `backtest`, "
               "`validate` and `journal` in stage_10.py.",
        predict="How a bank says that a model it did not fit was wrong, and how it "
                "explains a provision that moved between two versions of it.",
        check=check_10,
    ),
]
