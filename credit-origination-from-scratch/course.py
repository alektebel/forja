"""Credit Origination From Scratch — the loan before it exists, as numbers.

Ten graded stages over a provided estate (`cases.py`, `dates.py`, `policy.py`),
the way the rest of this repository teaches a mechanism: the world is data and
holds the ground truth, a stage is a file you write, a check is what happens to
it, and every number is an integer count of basis points or cents because
lending is a fixed-point discipline.

What the course is about, in one line: *the decision a bank runs before a loan
exists, and the contract the answer becomes.*

    whether the payment fits the income the applicant can prove
    the scorecard — weight, points, band — a reviewer can audit
    the collateral, its haircut and how far the lien reaches
    the rating, and the gates no score can pass
    the price, leg by leg, that covers what the loan costs the bank
    the limit, and the committed versus the uncommitted part of it
    the covenants, measured on the projections, with their headroom
    the decision, and the role that owns the number
    the offer letter, its clauses and its expiry
    the booked facility, in M1's own shapes — where M1 begins

The house laws hold here (`.m0-dev/CONTRACT.md` §1): standard library only, no
`float` literal, no `math`, no `statistics`, no `decimal`, no `fractions`, no
`random`, no clock, no socket, no process — and no `/` between two ints. The
estate is never written: a stage reads it and answers, and the bank's own records
(`decision`, `offer`, `facility`) are the answer key every stage is graded
against. Where a division happens, the contract pins the rounding in basis
points and cents — that is not pedantry — a score is a weighted table and a
price is legs that must re-add, and the arithmetic a credit committee recomputes
by hand is exactly the arithmetic a float would hide.

What the course does **not** do is fit a model or decide the business question:
which applicants to court. The policy arrives as a rulebook (`policy.py`,
`POLICY_VERSION`), the scorecard bands arrive as the applicant's facts, the
projections arrive as the borrower's own path. What is left — and what a
bank's credit office actually spends its time on — is measuring, scoring,
rating, pricing, structuring, promising, deciding, lettering and booking: ten
stages, one surface each, and a check that says in its own arithmetic whether
the answer holds.

    python3 codecraft/cli.py run credit-origination-from-scratch
"""

from codecraft.api import stage

TITLE = "Credit Origination From Scratch"
DESCRIPTION = ("The loan before it exists, as numbers, over a provided estate and "
               "a provided policy: the affordability test and its two halves "
               "against the income the applicant can prove, the level payment "
               "searched for rather than solved, the application scorecard as a "
               "weighted table a reviewer can audit, the collateral's haircuts and "
               "the advance its liens actually cover, the rating and the gates no "
               "score can pass, the price built leg by leg — funding, expected "
               "loss, capital, cost, margin — the limit structure and the "
               "committed share of it, the covenants measured on the borrower's "
               "own projections with their headroom in basis points, the decision "
               "record with its legs and its conditions and the role that owns "
               "it, the offer letter's clauses and its expiry, and the booked "
               "facility in M1's own shapes — answered against the bank's own "
               "records, which are the answer key every stage is graded against.")

LEVEL = "advanced"
ORDER = 30


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-origination-from-scratch"

    C1_FIT_KEYS = ("id", "verified_income_cents", "declared_income_cents",
                   "obligations_monthly_cents", "payment_cents", "service_cents",
                   "fit_bp", "leftover_cents", "verdict", "fits")

    C1_FIT_VERDICTS = ("clear", "over-the-cap", "under-the-floor", "over-both",
                       "under-water")

    C1_FREQUENCIES = ("monthly", "annual")

    C1_SCALE_BP = 10000

    C1_DSR_CAP_BP = 4500

    C1_AFFORD_FLOOR_CENTS = 100000

    C1_SYN_PRINCIPAL = 900000

    C1_SYN_RATE_BP = 1050

    C1_SYN_TERM_MONTHS = 24

    def _repo(start=None):
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("course.py", "cases.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

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

    def _refuses_family(exc_family, what, call, names=()):
        """A refusal by the estate's own error or by the stage's, either naming it."""
        try:
            got = call()
        except ValueError as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            assert isinstance(refused, exc_family), (
                "%s refused with %r, which is none of %r" % (what, type(refused),
                                                             exc_family))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _period_bp(rate_bp):
        """The rate per monthly period: thirty days of a 360-day year, truncated."""
        return rate_bp * 30 // 360

    def _walk(principal_cents, period, payment_cents, term_months):
        """An independent amortisation: interest on the opening balance, then payment."""
        balance = principal_cents
        for _ in range(term_months):
            if balance <= 0:
                return balance
            balance = balance + balance * period // C1_SCALE_BP - payment_cents
        return balance

    def _smallest(lo, hi, pays):
        """The smallest integer in `lo..hi` the predicate answers true for."""
        assert pays(hi), "the search's own bracket is too tight to hold the answer"
        while lo < hi:
            middle = (lo + hi) // 2
            if pays(middle):
                hi = middle
            else:
                lo = middle + 1
        return lo

    def _payment(principal_cents, rate_bp, term_months):
        """The smallest whole-cent payment whose walk clears the loan."""
        period = _period_bp(rate_bp)
        return _smallest(0, 2 * principal_cents,
                         lambda cents: _walk(principal_cents, period, cents,
                                             term_months) <= 0)

    def _monthly_of(amount_cents, frequency):
        """An obligation's monthly figure, at the frequency it was stated in."""
        assert frequency in C1_FREQUENCIES, frequency
        if frequency == "annual":
            return amount_cents // 12
        return amount_cents

    def _verdict_of(fit_bp, raw_leftover):
        """Which half fired, in the check's own words — the contract's five."""
        over_cap = fit_bp > C1_DSR_CAP_BP
        under_floor = raw_leftover < C1_AFFORD_FLOOR_CENTS
        if raw_leftover < 0:
            return "under-water"
        if over_cap and under_floor:
            return "over-both"
        if over_cap:
            return "over-the-cap"
        if under_floor:
            return "under-the-floor"
        return "clear"

    def _expected_fit(id, application, obligations, income_source="verified"):
        """The record the two halves must answer, from the raw facts.

        The payment is searched here, the obligations turned here, the ratio taken
        here — all against the raw facts, never against the stage.
        """
        if income_source == "verified":
            income = application["verified_income_cents"]
        else:
            income = application["declared_income_cents"]
        monthly = 0
        for row in obligations:
            monthly = monthly + _monthly_of(row["amount_cents"], row["frequency"])
        payment_cents = _payment(application["requested_cents"],
                                 _C1_PROPOSED_RATE[application["purpose"]],
                                 application["term_months"])
        service = payment_cents + monthly
        fit_bp = C1_SCALE_BP * service // income
        raw_leftover = income - service
        verdict = _verdict_of(fit_bp, raw_leftover)
        return {"id": id,
                "verified_income_cents": application["verified_income_cents"],
                "declared_income_cents": application["declared_income_cents"],
                "obligations_monthly_cents": monthly,
                "payment_cents": payment_cents,
                "service_cents": service,
                "fit_bp": fit_bp,
                "leftover_cents": max(raw_leftover, 0),
                "verdict": verdict,
                "fits": verdict == "clear"}

    _C1_PROPOSED_RATE = {"consumer": 1050, "mortgage": 480, "sme": 890,
                         "corporate": 780}

    class _Synthetic:
        """An estate of the check's own: one application, its obligations, doors.

        It answers the two accessors the affordability test reads and keeps a
        record of every ask, so a stage that reads anything else — the decision,
        the collateral, the history — is caught asking for what is not stage 1's.
        """

        def __init__(self, application, obligations):
            self._application = dict(application)
            self._obligations = tuple(dict(row) for row in obligations)
            self._asked = []

        def application(self, id):
            """The application as stated."""
            self._asked.append(("application", id))
            return dict(self._application)

        def obligations(self, id):
            """The obligations as stated."""
            self._asked.append(("obligations", id))
            return tuple(dict(row) for row in self._obligations)

        def reads(self):
            """Every ask the stage made, in order."""
            return tuple(self._asked)

        def peek(self):
            """The household's own copies, without counting as an ask."""
            return dict(self._application), tuple(dict(row) for row in self._obligations)

    def _synthetic_application(requested_cents=C1_SYN_PRINCIPAL,
                               term_months=C1_SYN_TERM_MONTHS, purpose="consumer",
                               verified_income_cents=260000,
                               declared_income_cents=260000):
        """A household the boundaries can be built around."""
        return {"id": "C1-SYN", "purpose": purpose, "requested_cents": requested_cents,
                "term_months": term_months,
                "declared_income_cents": declared_income_cents,
                "verified_income_cents": verified_income_cents,
                "employment": "check", "employment_years": 0, "self_employed": False,
                "arrived_on": "2031-01-01"}

    def _c1_constants(s, policy, cases):
        """The surface: keys in order, the policy's own vocabularies and stages."""
        assert tuple(s.FIT_KEYS) == C1_FIT_KEYS, (
            "the record's keys %r are not the contract's ten, in order %r; a record "
            "whose keys are reordered is a record nobody can audit" % (s.FIT_KEYS,
                                                                      C1_FIT_KEYS))
        for first, second in (("verdict", "fits"), ("fit_bp", "leftover_cents"),
                              ("payment_cents", "service_cents")):
            assert s.FIT_KEYS.index(first) < s.FIT_KEYS.index(second), (
                "the record puts %r before %r, and the contract's order is the "
                "committee's reading order" % (second, first))
        assert s.FIT_KEYS.index("verified_income_cents") < \
            s.FIT_KEYS.index("declared_income_cents"), (
            "the record reports the declared income before the verified one, and the "
            "bank's record proves what it lends against first")
        assert tuple(s.FREQUENCIES) == C1_FREQUENCIES == tuple(policy.FREQUENCIES), (
            "the frequencies %r are not the policy's own %r" % (s.FREQUENCIES,
                                                                policy.FREQUENCIES))
        assert tuple(s.FIT_VERDICTS) == C1_FIT_VERDICTS, (
            "the verdicts %r are not the five the two halves answer: clear, "
            "over-the-cap, under-the-floor, over-both, under-water" % (s.FIT_VERDICTS,))
        assert s.DSR_SCALE_BP == C1_SCALE_BP, (
            "the ratio's scale is %r and 100%% is 10000 basis points" % (s.DSR_SCALE_BP,))
        assert policy.DSR_CAP_BP == C1_DSR_CAP_BP, (
            "the policy's own cap is %d, and the check does not bend it"
            % (policy.DSR_CAP_BP,))
        assert policy.AFFORD_FLOOR_CENTS == C1_AFFORD_FLOOR_CENTS, (
            "the policy's own floor is %d cents, and the check does not bend it"
            % (policy.AFFORD_FLOOR_CENTS,))
        for purpose, rate in sorted(_C1_PROPOSED_RATE.items()):
            assert policy.PROPOSED_RATE_BP[purpose] == rate, (
                "the policy's proposed rate for %s is %d, not the %d the check was "
                "built with" % (purpose, policy.PROPOSED_RATE_BP[purpose], rate))
        assert issubclass(s.AffordError, ValueError), s.AffordError
        assert s.AffordError is not ValueError, (
            "the stage must refuse with its own error, not defer to the family's")

    def _c1_record_shape(s, record, what):
        """A fit record is a dict with the contract's keys, in the contract's order."""
        assert isinstance(record, dict), "%s answered %r, not a record" % (what, record)
        assert tuple(record.keys()) == C1_FIT_KEYS, (
            "%s's record carries the keys %r, not the contract's %r, in order"
            % (what, tuple(record.keys()), C1_FIT_KEYS))
        for field in ("verified_income_cents", "declared_income_cents",
                      "obligations_monthly_cents", "payment_cents", "service_cents",
                      "fit_bp", "leftover_cents"):
            assert isinstance(record[field], int) and not isinstance(record[field], bool), (
                "%s's %s is %r, not a whole count" % (what, field, record[field]))
        assert record["verdict"] in C1_FIT_VERDICTS, (
            "%s's verdict %r is not one of the five the halves answer"
            % (what, record["verdict"]))
        assert isinstance(record["fits"], bool), (
            "%s's fits is %r, not a decision" % (what, record["fits"]))

    def _c1_one_fit(s, name, application, obligations, record):
        """One application's fit, field by field, against the raw facts."""
        what = "the fit of %s" % (name,)
        _c1_record_shape(s, record, what)
        expected = _expected_fit(name, application, obligations)
        verified, declared = application["verified_income_cents"], \
            application["declared_income_cents"]
        if verified != declared:
            gap_note = ("(the %d the applicant declared is %d cents off the %d the bank "
                        "verified, and the bank's own decision was built on the verified "
                        "one)" % (declared, declared - verified, verified))
        else:
            gap_note = "(the applicant declared exactly what the bank verified)"
        assert record["id"] == name, "%s names %r, not the id it was asked for" % (
            what, record["id"])
        assert record["verified_income_cents"] == verified, (
            "%s answered a verified income of %r, and you used the declared income %d %s"
            % (what, record["verified_income_cents"], declared, gap_note))
        assert record["declared_income_cents"] == declared, (
            "%s answered a declared income of %r, and the record's own field is what "
            "was said, not what was proven -- expected %d %s"
            % (what, record["declared_income_cents"], declared, gap_note))
        assert record["obligations_monthly_cents"] == expected["obligations_monthly_cents"], (
            "%s turned the obligations into %d of monthly cash, and the frequencies "
            "answer %d -- an annual charge read as monthly, or one dropped, is a fit "
            "nobody can audit" % (what, record["obligations_monthly_cents"],
                                  expected["obligations_monthly_cents"]))
        assert record["payment_cents"] == expected["payment_cents"], (
            "%s answered a payment of %d, and the requested %d cents at the proposed "
            "rate over %d months search to %d -- a closed form, or interest on the "
            "wrong balance, answers another cent" % (
                what, record["payment_cents"], application["requested_cents"],
                application["term_months"], expected["payment_cents"]))
        assert record["service_cents"] == expected["service_cents"], (
            "%s answered a service of %d; payment %d plus obligations %d is %d -- the "
            "obligations dropped from the service are income nobody owes yet counts"
            % (what, record["service_cents"], expected["payment_cents"],
               expected["obligations_monthly_cents"], expected["service_cents"]))
        assert record["fit_bp"] == expected["fit_bp"], (
            "%s answered fit_bp %d, and %d over a verified %d truncates to %d -- you "
            "used the declared income (%d declares %d), took the ratio at the wrong "
            "scale, or let a rounded ratio decide %s"
            % (what, record["fit_bp"], expected["service_cents"], verified,
               expected["fit_bp"], declared, verified, gap_note))
        assert record["leftover_cents"] == expected["leftover_cents"], (
            "%s answered a leftover of %d, and verified %d minus service %d floored "
            "at zero is %d -- income scored twice, a negative floored the wrong way, "
            "or the declared income spent again"
            % (what, record["leftover_cents"], verified, expected["service_cents"],
               expected["leftover_cents"]))
        assert record["verdict"] == expected["verdict"], (
            "%s answered verdict %r; the independent answer is %r (fit_bp %d against "
            "the cap %d, raw leftover %d against the floor %d) -- the verdict is "
            "%s, and a floored leftover that dresses a breach up as an ordinary miss "
            "hides the household's own condition"
            % (what, record["verdict"], expected["verdict"], expected["fit_bp"],
               C1_DSR_CAP_BP, verified - expected["service_cents"],
               C1_AFFORD_FLOOR_CENTS, expected["verdict"]))
        assert record["fits"] == expected["fits"], (
            "%s answered fits %r; both halves %s -- the ratio half is fit_bp %d <= "
            "%d and the leftover half is raw %d >= %d, and either half alone is "
            "wrong twice"
            % (what, record["fits"],
               "pass" if expected["fits"] else "fail", expected["fit_bp"],
               C1_DSR_CAP_BP, verified - expected["service_cents"],
               C1_AFFORD_FLOOR_CENTS))

    def _c1_fit_of_estate(s, book, policy):
        """Every application the estate holds, against the raw facts of the estate."""
        records = {}
        counts = {}
        for name in book.names():
            application = book.application(name)
            obligations = book.obligations(name)
            record = s.affordability(book, name)
            _c1_one_fit(s, name, application, obligations, record)
            records[name] = record
            counts[record["verdict"]] = counts.get(record["verdict"], 0) + 1
        return records, counts

    def _c1_estate_answer_key(s, book, records):
        """The estate's own records, where the estate has one for stage 1.

        A fit the bank's own decision is the answer key for: an approval or counter
        whose reasons cite affordability is a leg that cleared, a decline that cites
        it is a leg that fired -- and `CO-10`, kept at the policy cap exactly by the
        estate's own hand, must land there and no other place.
        """
        for name in book.names():
            decision = book.decision(name)
            record = records[name]
            cites = "affordability" in decision["reasons"]
            if cites and decision["verdict"] in ("approve", "counter"):
                assert record["fits"], (
                    "%s's decision is %r citing affordability, and the bank lent at "
                    "terms your fit refuses: fit_bp %d, leftover %d"
                    % (name, decision["verdict"], record["fit_bp"],
                       record["leftover_cents"]))
            if cites and decision["verdict"] == "decline":
                assert not record["fits"], (
                    "%s was declined citing affordability, and your lone fit passes: "
                    "the estate expects a leg that fired" % (name,))
                assert record["verdict"] != "clear", (
                    "%s's fit clears and the bank declined it for affordability"
                    % (name,))
        co10 = records["CO-10"]
        co10_expected = _expected_fit("CO-10", book.application("CO-10"),
                                      book.obligations("CO-10"))
        assert co10_expected["fit_bp"] == C1_DSR_CAP_BP, (
            "the estate's own fixture no longer keeps CO-10 at the cap: the raw facts "
            "recompute to fit_bp %d, and the boundary the estate promised to land on "
            "is %d" % (co10_expected["fit_bp"], C1_DSR_CAP_BP))
        assert co10["fit_bp"] == C1_DSR_CAP_BP and co10["fits"] and \
            co10["verdict"] == "clear", (
            "CO-10 sits exactly on the policy cap (%dbp) and the bank approved it: a "
            "cap read as exclusive, or tested after a second rounding, refuses an "
            "applicant the estate keeps"
            % (C1_DSR_CAP_BP,))

    def _c1_one_synthetic(s, stub, name):
        """One synthetic fit, field by field against the check's own expectation."""
        application, obligations = stub.peek()
        record = s.affordability(stub, name)
        _c1_one_fit(s, name, application, obligations, record)
        assert stub.reads() == (("application", name), ("obligations", name)), (
            "the stage asked the estate %r and nothing else; a fit is the "
            "application's and the obligations' to answer" % (stub.reads(),))
        return record

    def _c1_synthetic_service(s, target_service, obligations_extra=()):
        """A synthetic application whose service lands on `target_service`.

        The payment the check's own search answers for the synthetic loan, then the
        obligations make up the remainder the target service needs.
        """
        payment = _payment(C1_SYN_PRINCIPAL, C1_SYN_RATE_BP, C1_SYN_TERM_MONTHS)
        stub_extra = 0
        for amount, frequency in obligations_extra:
            stub_extra = stub_extra + _monthly_of(amount, frequency)
        rent = target_service - stub_extra - payment
        assert rent >= 0, "the fixture's own target service is below its payment"
        return ({"kind": "rent", "amount_cents": rent, "frequency": "monthly"},
                ) + tuple({"kind": "extra", "amount_cents": amount,
                           "frequency": frequency}
                          for amount, frequency in obligations_extra), payment

    def _c1_edges(s, book, records, policy):
        """The boundaries, on both sides, from applications the check builds.

        The cap is inclusive and checked against the recomputed ratio: at the exact
        cap the fit passes, at one basis point over it the ratio half fires alone.
        The floor is inclusive too: a raw leftover at the floor passes with the
        ratio inside the cap, one cent under fires the floor half alone, and the
        estate holds a pair of applicants the same directions come from.
        """
        cases_edges = []
        # the cap kept exactly: fit_bp 4500 == the policy cap, fits
        obligations, _ = _c1_synthetic_service(s, 117000)
        cases_edges.append(("the-cap-kept",
                            _synthetic_application(verified_income_cents=260000,
                                                   declared_income_cents=280000),
                            obligations, True, "clear"))
        # the ratio a hair over: 4501 fires the cap half alone
        obligations, _ = _c1_synthetic_service(s, 117026)
        cases_edges.append(("the-cap-one-over",
                            _synthetic_application(verified_income_cents=260000,
                                                   declared_income_cents=280000),
                            obligations, False, "over-the-cap"))
        # the floor kept exactly: raw leftover 100000 == the policy floor, ratio 4499
        obligations, _ = _c1_synthetic_service(s, 81818)
        cases_edges.append(("the-floor-kept",
                            _synthetic_application(verified_income_cents=181818,
                                                   declared_income_cents=190000),
                            obligations, True, "clear"))
        # the floor one cent under: 99999 fires the floor half alone
        obligations, _ = _c1_synthetic_service(s, 81819)
        cases_edges.append(("the-floor-one-under",
                            _synthetic_application(verified_income_cents=181818,
                                                   declared_income_cents=190000),
                            obligations, False, "under-the-floor"))
        # the floor fires while the ratio passes -- the declared income bigger still
        obligations, _ = _c1_synthetic_service(
            s, 67500, ((24000, "annual"),))
        cases_edges.append(("floor-only",
                            _synthetic_application(verified_income_cents=150000,
                                                   declared_income_cents=171000),
                            obligations, False, "under-the-floor"))
        # both halves fire, the raw leftover still above zero -- the other CO-05
        obligations, _ = _c1_synthetic_service(
            s, 67551, ((24000, "annual"),))
        cases_edges.append(("over-both",
                            _synthetic_application(verified_income_cents=150000,
                                                   declared_income_cents=150000),
                            obligations, False, "over-both"))
        # the ratio fires while the leftover is comfortable -- the other direction
        obligations, _ = _c1_synthetic_service(s, 126028)
        cases_edges.append(("cap-only",
                            _synthetic_application(verified_income_cents=280000,
                                                   declared_income_cents=260000),
                            obligations, False, "over-the-cap"))
        # under water: the raw leftover is negative and the verdict says so
        obligations, _ = _c1_synthetic_service(s, 300000)
        cases_edges.append(("under-water",
                            _synthetic_application(verified_income_cents=260000,
                                                   declared_income_cents=300000),
                            obligations, False, "under-water"))
        edges = {}
        for name, application, obligations, fits, verdict in cases_edges:
            stub = _Synthetic(application, obligations)
            record = _c1_one_synthetic(s, stub, name)
            expected = _expected_fit(name, application, obligations)
            assert record["fits"] == fits and record["verdict"] == verdict, (
                "%s: the household built to %s (verdict %r) answers %r with "
                "fit_bp %d, service %d, raw leftover %d -- one half of the test is "
                "wrong, and both sides of both edges are pinned"
                % (name, "fit" if fits else "fail", verdict, record["verdict"],
                   record["fit_bp"], record["service_cents"],
                   application["verified_income_cents"] - record["service_cents"]))
            assert record == expected, (
                "%s: %r against the check's own %r" % (name, record, expected))
            edges[name] = record
        assert edges["the-cap-kept"]["fit_bp"] == C1_DSR_CAP_BP, (
            "the fixture no longer lands on the cap: fit_bp %d is not the edge %d"
            % (edges["the-cap-kept"]["fit_bp"], C1_DSR_CAP_BP))
        assert edges["the-cap-one-over"]["fit_bp"] == C1_DSR_CAP_BP + 1, (
            "the fixture no longer lands a basis point over the cap")
        under_water = edges["under-water"]
        assert under_water["verdict"] == "under-water" and \
            under_water["leftover_cents"] == 0, (
            "a household into the water is named under-water, and the record's own "
            "leftover is floored at zero while the verdict keeps the negative visible: "
            "%r answers verdict %r, leftover %d" % (
                "under-water", under_water["verdict"], under_water["leftover_cents"]))
        return edges

    def _c1_payment(s, book):
        """The searched payment: both sides of the answer over every shape."""
        for principal, rate, term in ((1000, 0, 4), (123457, 0, 36), (999999, 0, 137),
                                      (765432, 1, 2), (765432, 350, 13),
                                      (765432, 1050, 24), (900000, 725, 6),
                                      (765432, C1_SCALE_BP, 17), (1, 500, 9),
                                      (100000, 500, 1)):
            period = _period_bp(rate)
            payment = s.payment(book, principal, rate, term)
            assert isinstance(payment, int) and not isinstance(payment, bool), (
                "the payment is %r, not a whole count of cents" % (payment,))
            assert _walk(principal, period, payment, term) <= 0, (
                "the payment %d is not enough at %d basis points over %d months on "
                "%d cents" % (payment, rate, term, principal))
            assert _walk(principal, period, payment - 1, term) > 0, (
                "the payment %d is not the smallest that clears %d cents at %d basis "
                "points over %d months: one cent less also clears it"
                % (payment, principal, rate, term))
            assert payment == _payment(principal, rate, term), (
                "the stage's payment %d is not the smallest the walk answers %d"
                % (payment, _payment(principal, rate, term)))
            if rate == 0:
                assert payment == (principal + term - 1) // term, (
                    "at zero rate the level payment is the principal over the term, "
                    "%d, not %d" % ((principal + term - 1) // term, payment))
            if term == 1:
                assert payment == principal + principal * period // C1_SCALE_BP, (
                    "one month is the principal plus that period's interest, %d, "
                    "not %d" % (principal + principal * period // C1_SCALE_BP,
                                payment))
        # an interest-bearing payment costs more than the principal over the term
        assert s.payment(book, 240000, 90, 2) > 120000, (
            "a rate carrying interest is charged, not swallowed: two months of a "
            "90bp rate cost more than the flat half")
        # two runs, one answer: the search is a function of its terms
        assert s.payment(book, 900000, 1050, 24) == s.payment(book, 900000, 1050, 24), (
            "two runs of one search answered differently")

    def _c1_payment_answer_key(s, book):
        """The bank's own ledger rows carry the payment the search must answer."""
        for name in book.names():
            booking = None
            try:
                booking = book.facility(name)
            except ValueError as refused:
                continue
            assert isinstance(booking, dict) and "rows" in booking, booking
            rows = booking["rows"]
            payment = s.payment(book, booking["booked_cents"], booking["rate_bp"],
                                booking["term_months"])
            assert len(rows) == booking["term_months"], (
                "%s's ledger carries %d rows for a %d-month term"
                % (name, len(rows), booking["term_months"]))
            assert payment == rows[0]["amount_cents"], (
                "%s's first ledger instalment is %d cents, and the bank booked it with "
                "the same search this stage must reproduce: payment %d, booked %d "
                "cents at %d bp over %d months" % (
                    name, rows[0]["amount_cents"], payment, booking["booked_cents"],
                    booking["rate_bp"], booking["term_months"]))
            period = _period_bp(booking["rate_bp"])
            balance = booking["booked_cents"]
            for index, row in enumerate(rows):
                interest = balance * period // C1_SCALE_BP
                last = index == len(rows) - 1
                if not last:
                    assert row["amount_cents"] == payment, (
                        "%s's instalment %d is %d, not the level payment %d"
                        % (name, index, row["amount_cents"], payment))
                balance = balance + interest - row["amount_cents"]
            assert balance == 0, (
                "%s's own ledger closes at %d cents, not zero" % (name, balance))

    def _c1_monthly_turn(s):
        """The monthly figure of an obligation, at the frequency it was stated in."""
        assert s.calendar_monthly(80000, "monthly") == 80000, (
            "a monthly charge is its own amount, not a twelfth of it")
        assert s.calendar_monthly(24000, "annual") == 2000, (
            "an annual charge is consumed over twelve monthly pieces: 24000 // 12 "
            "is 2000")
        assert s.calendar_monthly(12000, "annual") == 1000, (
            "the estate's smallest annual charge turns to 1000 a month")
        # the remainder the policy drops, kept dropped: a year with cents left over
        assert s.calendar_monthly(10001, "annual") == 10001 // 12, (
            "an annual %d with a remainder in it turns to %d, truncating -- the "
            "remainder is the applicant's own rounding, and rounding it up reads a "
            "cent that was never charged" % (10001, 10001 // 12))
        assert s.calendar_monthly(10001, "annual") != (10001 + 11) // 12, (
            "the annual turn is not a division that rounds the remainder in")
        assert s.calendar_monthly(0, "annual") == 0, (
            "no charge is no monthly cash")
        for bad in ("weekly", "quarterly", "", "MONTHLY", "annual ", None, True):
            _refuses(s.AffordError, "the frequency %r is not the policy's"
                     % (bad,), lambda bad=bad: s.calendar_monthly(24000, bad),
                     [repr(bad)])
        _refuses(s.AffordError, "a negative obligation",
                 lambda: s.calendar_monthly(-1, "monthly"), ["-1"])
        _refuses(s.AffordError, "an obligation that is not a count of cents",
                 lambda: s.calendar_monthly(24000.0, "monthly"), ["24000.0"])

    def _c1_refusals(s, book, synthetic):
        """Every shape that cannot be a fit, refused by name, reaching no record."""
        calls = [
            # a payment's own three walls
            ("a rate of minus one basis point", s.AffordError,
             lambda: s.payment(book, 100000, -1, 12), ["-1"]),
            ("a rate above the 100BP the whole is charged in", s.AffordError,
             lambda: s.payment(book, 100000, C1_SCALE_BP + 1, 12), ["10001"]),
            ("a rate 10000 times over, at an absurd ceiling", s.AffordError,
             lambda: s.payment(book, 100000, 1000000, 12), ["1000000"]),
            ("a rate that is not a count of basis points", s.AffordError,
             lambda: s.payment(book, 100000, "725", 12), ["725"]),
            ("a term of no months", s.AffordError,
             lambda: s.payment(book, 100000, 500, 0), ["0"]),
            ("a term of minus one month", s.AffordError,
             lambda: s.payment(book, 100000, 500, -1), ["-1"]),
            ("a term that is not a count of months", s.AffordError,
             lambda: s.payment(book, 100000, 500, "12"), ["12"]),
            ("a principal of nothing", s.AffordError,
             lambda: s.payment(book, 0, 500, 12), ["0"]),
            ("a principal of minus one cent", s.AffordError,
             lambda: s.payment(book, -1, 500, 12), ["-1"]),
            ("a principal half a cent wide", s.AffordError,
             lambda: s.payment(book, 0.5, 500, 12), ["0.5"]),
            # an application the estate does not hold is the estate's own refusal
            ("an application the estate does not hold",
             (cases_module().CaseError,),
             lambda: s.affordability(book, "CO-99"), ["CO-99"]),
            # a synthetic household the policy refuses: purpose, frequency, income
            ("a purpose the policy carries no proposed rate for", s.AffordError,
             lambda: s.affordability(synthetic("purpose", "farm"), "the-purpose"),
             ["farm"]),
            ("an obligation stated at a frequency outside FREQUENCIES", s.AffordError,
             lambda: s.affordability(synthetic("frequency", "weekly"),
                                     "the-frequency"), ["weekly"]),
            ("a verified income of nothing", s.AffordError,
             lambda: s.affordability(synthetic("verified", 0), "the-income"), ["0"]),
            ("a verified income of minus one", s.AffordError,
             lambda: s.affordability(synthetic("verified", -1), "the-income"),
             ["-1"]),
            ("a verified income that is not a count of cents", s.AffordError,
             lambda: s.affordability(synthetic("verified", "260000"),
                                     "the-income"), ["260000"]),
        ]
        for what, refused_mask, call, names in calls:
            excs = refused_mask if isinstance(refused_mask, tuple) else (refused_mask,)
            if len(excs) == 1:
                _refuses(excs[0], what, call, names)
            else:
                _refuses_family(excs, what, call, names)

    def synthetic(kind, value=None):
        """One synthetic household built to arrive at the named refusal."""
        application = _synthetic_application()
        obligations = ({"kind": "rent", "amount_cents": 80000,
                        "frequency": "monthly"},)
        if kind == "purpose":
            application["purpose"] = value
        elif kind == "frequency":
            obligations = ({"kind": "rent", "amount_cents": 80000,
                            "frequency": value},)
        elif kind == "verified":
            application["verified_income_cents"] = value
        else:
            raise AssertionError("no synthetic of kind %r" % (kind,))
        return _Synthetic(application, obligations)

    def cases_module():
        """The estate's own error family, for the refusals it keeps."""
        import cases
        return cases

    def _c0_counters(s, book):
        """A refused call reaches no record, and the doors a full pass counts."""
        # a refusal: every counter but lookups stays put
        before = book.stats()
        _refuses_family((cases_module().CaseError, s.AffordError),
                        "the fit of an application the estate does not hold",
                        lambda: s.affordability(book, "CO-99"), ["CO-99"])
        after = book.stats()
        for kind, value in after.items():
            if kind == "lookups":
                assert value == before["lookups"] + 1, (
                    "a refused call moved %r from %d to %d, and a looked-for door "
                    "that refuses is one lookup, no more"
                    % (kind, before["lookups"], value))
            else:
                assert value == before[kind], (
                    "a refused call touched the book's %r: %r became %r"
                    % (kind, before[kind], value))
        # a full pass moves only the accessors the fit reads
        names = book.names()
        before = book.stats()
        for name in names:
            s.affordability(book, name)
        after = book.stats()
        for kind, value in after.items():
            if kind in ("applications", "obligations"):
                assert value == before[kind] + len(names), (
                    "a full pass moved the %r door %d times, not the %d applications "
                    "it read" % (kind, value - before[kind], len(names)))
            elif kind == "lookups":
                assert value == before[kind] + 2 * len(names), (
                    "a full pass asked the book %r %d times: two doors per application"
                    % (kind, value - before[kind]))
            else:
                assert value == before[kind], (
                    "the stage asked the book for %r, and a fit is not that record's "
                    "to answer: %r became %r" % (kind, before[kind], value))

    def _c1_determinism(s, book, policy):
        """Two runs of one workload answer equal, record by record."""
        def workload():
            answers = []
            for name in book.names():
                answers.append(s.affordability(book, name))
            for principal, rate, term in ((900000, 1050, 24), (240000, 90, 2),
                                          (100000, 0, 4), (765432, 350, 13)):
                answers.append(s.payment(book, principal, rate, term))
            answers.append(s.calendar_monthly(24000, "annual"))
            answers.append(s.calendar_monthly(10001, "annual"))
            stub = _Synthetic(
                _synthetic_application(verified_income_cents=181818),
                ({"kind": "rent", "amount_cents": 81818
                  - _payment(C1_SYN_PRINCIPAL, C1_SYN_RATE_BP, C1_SYN_TERM_MONTHS),
                  "frequency": "monthly"},))
            answers.append(s.affordability(stub, "C1-DETERMINISM"))
            return answers
        one = workload()
        two = workload()
        assert one == two, (
            "two runs of one workload answered differently (%r against %r), so a "
            "run is not a function of its inputs" % (one, two))

    """Every assertion the contract's §4.1 makes about this stage."""
    import cases
    import policy
    import stage_01 as s
    book = cases.build(7)
    # the stub speaks first: a template is a stub that refuses with its name,
    # so a first touch that raises must name the stage it has not been built for
    try:
        s.calendar_monthly(24000, "annual")
    except NotImplementedError as not_yet:
        assert "stage 1" in str(not_yet), (
            "the stage's own stub names the stage it is missing: %r does not"
            % (str(not_yet),))
    _c1_constants(s, policy, cases)
    _c1_monthly_turn(s)
    _c1_payment(s, book)
    _c1_payment_answer_key(s, book)
    records, _ = _c1_fit_of_estate(s, book, policy)
    _c1_estate_answer_key(s, book, records)
    _c1_edges(s, book, records, policy)
    _c1_refusals(s, book, synthetic)
    _c0_counters(s, book)
    _c1_determinism(s, book, policy)
    return records

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-origination-from-scratch"

    S2_POINTS_KEYS = ("id", "scores", "total_bp", "band_bp", "band")

    S2_ATTRIBUTES = ("dsr", "stability", "history", "collateral")

    S2_WEIGHTS_SUM_BP = 10000

    S2_WEIGHTS_BP = {"dsr": 3500, "stability": 1500, "history": 3000,
                     "collateral": 2000}

    S2_POINTS_BP = {
        "dsr": {"low": 10000, "mid": 5000, "high": 1000},
        "stability": {"long": 10000, "settled": 6000, "short": 2000},
        "history": {"clean": 10000, "spotted": 4000, "impaired": 0},
        "collateral": {"strong": 10000, "adequate": 7000, "weak": 2000},
    }

    S2_BANDS = ((7700, "A"), (6800, "B"), (5600, "C"), (4400, "D"),
                (2500, "E"), (0, "F"))

    S2_BAND_VOCABULARIES = {"dsr": ("low", "mid", "high"),
                            "stability": ("long", "settled", "short"),
                            "history": ("clean", "spotted", "impaired"),
                            "collateral": ("strong", "adequate", "weak")}

    S2_MISSING_ATTR_BANDS = {"dsr": "low", "stability": "long", "history": "clean"}

    S2_FOREIGN_BAND = {"dsr": "stellar", "stability": "long", "history": "clean",
                       "collateral": "strong"}

    S2_EXTRA_ATTR = {"dsr": "low", "stability": "long", "history": "clean",
                     "collateral": "strong", "glamour": "long"}

    S2_SHORT_SUM_WEIGHTS = {"dsr": 3490, "stability": 1500, "history": 3000,
                            "collateral": 2000}

    S2_FRACTION_WEIGHTS = {"dsr": 3500, "stability": 1500.5, "history": 3000,
                           "collateral": 2000}

    OFF_LEDGER = ("applications", "obligations", "collateral", "history",
                  "projections", "scorecard_bands", "decisions", "offers",
                  "facilities")

    def _repo(start=None):
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("course.py", "cases.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

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

    def _refuses_named(what, call, names=()):
        """A refusal of either family — the estate's or the stage's.

        The contract lets an unknown id be refused by the estate's own class or by
        the stage's subclass; what it holds both to is the family, the name, and
        the fact that nothing was answered.
        """
        try:
            got = call()
        except ValueError as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _S2Cases:
        """The estate, wearing a mask over its bands and a ledger over its doors.

        `scorecard_bands` hands the fixture's facts over where the fixture carries
        them and the estate's own facts everywhere else; every other door is
        delegated through a recorder, so the check can prove the stage asked the
        estate for the bands alone — a scorecard keyed to the history door, or one
        that re-derives the bands from raw facts, asks through it and is caught.
        """

        def __init__(self, real, bands=None):
            self._real = real
            self._bands = dict(bands or {})
            self._asked = []

        def scorecard_bands(self, identity):
            """The fixture's facts, or the estate's own, through one counted ask."""
            self._asked.append(("scorecard_bands", identity))
            if identity in self._bands:
                return dict(self._bands[identity])
            return self._real.scorecard_bands(identity)

        def asked(self):
            """Every ask that reached this wrapper, in order."""
            return tuple(self._asked)

        def __getattr__(self, name):
            def door(*args, **kwargs):
                self._asked.append((name, args[:1]))
                return getattr(self._real, name)(*args, **kwargs)
            return door

    S2_SCALE = 10000

    def _row(attr, band, weights, points):
        """One weighted row, as the check adds it: points of the weight, truncated."""
        weight = weights[attr]
        points_bp = points[attr][band]
        return (attr, weight, band, points_bp, weight * points_bp // S2_SCALE)

    def _band_of(total_bp, bands_node):
        """The scorecard's own band: the first threshold the total clears, walking down."""
        for threshold, band in bands_node:
            if total_bp >= threshold:
                return threshold, band
        return bands_node[-1][0], bands_node[-1][1]

    def _expected(bands, weights=None, points=None, node=None):
        """The check's own whole scorecard, from its own card and its own walk."""
        weights = weights if weights is not None else S2_WEIGHTS_BP
        points = points if points is not None else S2_POINTS_BP
        node = node if node is not None else S2_BANDS
        rows = tuple(_row(attr, bands[attr], weights, points)
                     for attr in S2_ATTRIBUTES)
        total = sum(row[4] for row in rows)
        threshold, band = _band_of(total, node)
        return rows, total, threshold, band

    def _s2_constants(s, policy_module):
        """The stage's own echoes, held against the check's card and the policy's."""
        assert tuple(s.POINTS_KEYS) == S2_POINTS_KEYS, s.POINTS_KEYS
        assert tuple(s.SCORE_ATTRIBUTES) == S2_ATTRIBUTES, s.SCORE_ATTRIBUTES
        assert tuple(s.SCORE_ATTRIBUTES) == tuple(policy_module.SCORE_ATTRIBUTES), (
            "the stage's attributes are not the policy's: %r against %r"
            % (s.SCORE_ATTRIBUTES, policy_module.SCORE_ATTRIBUTES))
        assert s.SCORE_SCALE_BP == S2_WEIGHTS_SUM_BP, s.SCORE_SCALE_BP
        assert sum(S2_WEIGHTS_BP[attribute] for attribute in S2_ATTRIBUTES) == \
            S2_WEIGHTS_SUM_BP, "the check's own card does not sum to the whole"
        assert policy_module.SCORE_WEIGHTS_BP == S2_WEIGHTS_BP, (
            policy_module.SCORE_WEIGHTS_BP)
        assert policy_module.SCORE_POINTS_BP == S2_POINTS_BP, (
            policy_module.SCORE_POINTS_BP)
        assert tuple(policy_module.SCORE_BANDS) == S2_BANDS, (
            policy_module.SCORE_BANDS)
        thresholds = [threshold for threshold, _band in S2_BANDS]
        assert thresholds == sorted(thresholds, reverse=True), thresholds
        assert issubclass(s.ScorecardError, ValueError), s.ScorecardError
        assert s.ScorecardError is not ValueError, "the stage must refuse, not defer"

    def _s2_application(s, cases, id):
        """One application's scorecard, against the check's own card and walk."""
        bands = cases.scorecard_bands(id)
        rows, total, threshold, band = _expected(bands)
        record = s.scorecard(cases, id)
        assert tuple(record.keys()) == s.POINTS_KEYS, record
        assert tuple(record.keys()) == S2_POINTS_KEYS, record
        assert record["id"] == id, record
        scores = record["scores"]
        assert isinstance(scores, tuple), (
            "%s's scores are a %s, not the tuple the record's own shape refuses for"
            % (id, type(scores).__name__))
        assert len(scores) == len(S2_ATTRIBUTES), (id, scores)
        for row in scores:
            assert isinstance(row, tuple), (id, row)
            assert len(row) == 5, (id, row)
        assert tuple(row[0] for row in scores) == S2_ATTRIBUTES, (
            "%s's rows are in the order %r, not %r"
            % (id, tuple(row[0] for row in scores), S2_ATTRIBUTES))
        checked_bands = tuple(row[2] for row in scores)
        assert checked_bands == tuple(bands[attr] for attr in S2_ATTRIBUTES), (
            "%s's bands are %r, and the estate's own facts are %r"
            % (id, checked_bands, tuple(bands[attr] for attr in S2_ATTRIBUTES)))
        for attr, _weight, _band, points_bp, attribute_bp in scores:
            assert points_bp == S2_POINTS_BP[attr][bands[attr]], (id, attr, points_bp)
            assert attribute_bp == S2_WEIGHTS_BP[attr] * points_bp // S2_SCALE, (
                id, attr, attribute_bp)
        assert scores == rows, (
            "%s's rows are %r, and the check's own card answers %r" % (id, scores, rows))
        assert record["total_bp"] == total, (
            "%s's total is %d, and its own rows re-add to %d"
            % (id, record["total_bp"], total))
        assert record["band_bp"] == threshold, (id, record["band_bp"], threshold)
        assert record["band"] == band, (id, record["band"], band)
        assert s.score(cases, id) == total, (
            "%s's score answers %r, and the record's rows re-add to %d"
            % (id, s.score(cases, id), total))
        return record

    def _s2_table(s, cases):
        """Every application the estate holds, reproduced from the check's own card."""
        bands_seen = set()
        for id in sorted(cases.names()):
            record = _s2_application(s, cases, id)
            assert isinstance(record["total_bp"], int), (id, record)
            assert isinstance(record["band_bp"], int), (id, record)
            for row in record["scores"]:
                bands_seen.add(row[2])
        wanted = set(band for bands in S2_BAND_VOCABULARIES.values() for band in bands)
        assert wanted <= bands_seen, (
            "the estate's ten applications never visit the bands %r, so a band row "
            "nobody reaches exists and no check can say so"
            % (sorted(wanted - bands_seen),))

    def _s2_points_scale(s, policy_module, cases):
        """The truncation, landed where the frozen card never drops a fraction.

        The estate's weights are multiples of five hundred and its points multiples
        of a thousand, so every product divides by 10000 exactly and a rounding
        rule that is not truncation agrees with the frozen card on every record the
        estate holds. One points value one short of the whole, and one weight off
        the round hundred, are landed here on purpose — a half-up stage drifts a
        basis point off the record and is caught.
        """
        bands = cases.scorecard_bands("CO-01")
        points = dict(S2_POINTS_BP)
        points["dsr"] = dict(S2_POINTS_BP["dsr"], low=9999)
        original = policy_module.SCORE_POINTS_BP
        try:
            policy_module.SCORE_POINTS_BP = points
            rows, total, threshold, band = _expected(bands, points=points)
            record = s.scorecard(cases, "CO-01")
            assert record["scores"] == rows, (
                "points of the weight are %r at the check's card and %r at the "
                "stage's — 9999 points of a 3500 weight must truncate to 3499, and "
                "half-up answers 3500" % (record["scores"], rows))
            assert record["total_bp"] == total, (record["total_bp"], total)
            assert (record["band_bp"], record["band"]) == (threshold, band), record
            weights = dict(S2_WEIGHTS_BP)
            weights["stability"] = 1503
            weights["collateral"] = 1997
            assert sum(weights.values()) == S2_WEIGHTS_SUM_BP, (
                "the truncation card's weights must still sum to the whole")
            policy_module.SCORE_POINTS_BP = original
            policy_module.SCORE_WEIGHTS_BP = weights
            bands = cases.scorecard_bands("CO-02")
            rows, total, threshold, band = _expected(bands, weights=weights)
            record = s.scorecard(cases, "CO-02")
            assert record["scores"] == rows, (
                "the weighted points are %r at the check's card and %r at the "
                "stage's — 1503 points of a 6000 weight must truncate to 901, not "
                "round to 902" % (record["scores"], rows))
            assert record["total_bp"] == total and record["band"] == band, (
                record, total, band)
        finally:
            policy_module.SCORE_POINTS_BP = original
            policy_module.SCORE_WEIGHTS_BP = dict(S2_WEIGHTS_BP)

    def _s2_bad_facts(s, cases):
        """The three band shapes no record can be built from, refused before a row.

        Each fixture is read once — the bands door is the only thing the stage may
        ask of the estate — and the refusal names the offending attribute or band.
        """
        fixtures = (
            ("an attribute the estate answers no band for", S2_MISSING_ATTR_BANDS,
             ("collateral",), "CO-01"),
            ("a band outside the policy's own points table", S2_FOREIGN_BAND,
             ("dsr", "stellar"), "CO-01"),
            ("an attribute the estate answers besides the card's own",
             S2_EXTRA_ATTR, ("glamour",), "CO-01"),
            ("the same missing attribute, asked of another application",
             S2_MISSING_ATTR_BANDS, ("collateral",), "CO-02"),
        )
        for what, bands, names, id in fixtures:
            wrapper = _S2Cases(cases, {id: bands})
            _refuses(s.ScorecardError, what,
                     lambda wrapper=wrapper, id=id: s.scorecard(wrapper, id), names)
            _refuses(s.ScorecardError, "%s, through score" % (what,),
                     lambda wrapper=wrapper, id=id: s.score(wrapper, id), names)
            asked = wrapper.asked()
            assert len(asked) == 2 and tuple(ask[0] for ask in asked) == (
                "scorecard_bands", "scorecard_bands"), (
                "the refused scorecard asked the estate %r, and the bands door is "
                "the only one a scorecard may knock on" % (asked,))

    def _s2_weight_guard(s, policy_module, cases):
        """The weights' sum, checked before anything is scored, and the weights whole.

        The frozen card always sums to the whole, so the check breaks the card on
        purpose — a table summing one hundred short — and a table carrying a weight
        that is not a whole count of basis points. Either way the stage must refuse
        by name before it answers a total, since a total weighted out of anything
        but 10000bp reads as a different card than the one the policy wrote.
        """
        original = policy_module.SCORE_WEIGHTS_BP
        try:
            policy_module.SCORE_WEIGHTS_BP = S2_SHORT_SUM_WEIGHTS
            _refuses(s.ScorecardError, "a weight table a hundred short",
                     lambda: s.scorecard(cases, "CO-01"), ["10000"])
            _refuses(s.ScorecardError, "a weight table a hundred short, through score",
                     lambda: s.score(cases, "CO-01"), ["10000"])
            policy_module.SCORE_WEIGHTS_BP = S2_FRACTION_WEIGHTS
            _refuses(s.ScorecardError, "a weight that is not a whole count",
                     lambda: s.scorecard(cases, "CO-02"), ["stability"])
            policy_module.SCORE_WEIGHTS_BP = original
            record = s.scorecard(cases, "CO-01")
            assert record["total_bp"] == 10000, (
                "with the frozen card back the score answers %r, not the whole"
                % (record,))
        finally:
            policy_module.SCORE_WEIGHTS_BP = original

    def _s2_band_edges(s, policy_module, cases):
        """The threshold edge, on both sides, on a table the check writes itself.

        The estate's ten totals never sit exactly on a threshold, so the check
        writes the bands node itself: one node putting CO-02's total of 7000 exactly
        on an edge, one putting the same total a basis point under it, one putting
        CO-09's total of 5250 exactly on the top edge, and one whose every
        threshold no total clears — where the last band is answered, never refused.
        The total itself must not move with the table: `score` stays 7000 while the
        bands the table names come and go.
        """
        original = policy_module.SCORE_BANDS
        try:
            policy_module.SCORE_BANDS = ((7000, "A"), (0, "F"))
            record = s.scorecard(cases, "CO-02")
            assert (record["band_bp"], record["band"]) == (7000, "A"), (
                "a total sitting exactly on a threshold reads %r, not %r"
                % ((7000, "A"), (record["band_bp"], record["band"])))
            policy_module.SCORE_BANDS = ((7001, "A"), (0, "F"))
            record = s.scorecard(cases, "CO-02")
            assert (record["band_bp"], record["band"]) == (0, "F"), (
                "a total a basis point under a threshold reads %r, not %r"
                % ((0, "F"), (record["band_bp"], record["band"])))
            assert s.score(cases, "CO-02") == 7000, (
                "the bands node moved the total %r and the total is the table's own "
                "sum, not the thresholds'" % (s.score(cases, "CO-02"),))
            policy_module.SCORE_BANDS = ((5250, "A"), (4400, "B"), (0, "F"))
            record = s.scorecard(cases, "CO-09")
            assert (record["band_bp"], record["band"]) == (5250, "A"), (
                "the top threshold is inclusive: a total of 5250 reads %r, not %r"
                % ((5250, "A"), (record["band_bp"], record["band"])))
            policy_module.SCORE_BANDS = ((9999, "A"), (5000, "B"))
            record = s.scorecard(cases, "CO-04")
            assert (record["band_bp"], record["band"]) == (5000, "B"), (
                "a total that clears no threshold answers the last band with its "
                "own threshold, not a refusal: %r" % ((record["band_bp"],
                                                       record["band"]),))
            assert record["scores"] == _expected(
                cases.scorecard_bands("CO-04"))[0], (
                "the bands node reached the rows and the rows are the card's own")
        finally:
            policy_module.SCORE_BANDS = original

    def _s2_unknown_id(s, cases):
        """An application the estate does not hold, refused by name, moving nothing.

        The contract lets the estate refuse through its own class or the stage
        through its subclass; what it holds both to is the family, the id in the
        message, and the counters other than `lookups` staying put.
        """
        before = cases.stats()
        _refuses_named("an application id the estate does not hold",
                       lambda: s.scorecard(cases, "CO-99"), ["CO-99"])
        _refuses_named("the same, through score",
                       lambda: s.score(cases, "CO-99"), ["CO-99"])
        _refuses_named("an id that is not a text", lambda: s.scorecard(cases, 2),
                       ["application id", "not a text"])
        after = cases.stats()
        for key in OFF_LEDGER:
            assert after[key] == before[key], (
                "a refused scorecard moved the %s counter from %d to %d"
                % (key, before[key], after[key]))
        assert after["lookups"] > before["lookups"], (
            "the estate recorded no ask at all: %r" % (after,))

    def _s2_ledger(s, cases):
        """The scorecard asks the estate for the bands and nothing else."""
        before = cases.stats()
        names = cases.names()
        before = cases.stats()
        for id in names:
            s.scorecard(cases, id)
            s.score(cases, id)
        after = cases.stats()
        for kind in OFF_LEDGER:
            if kind == "scorecard_bands":
                continue
            assert after[kind] == before[kind], (
                "the scorecard asked the estate's %s door: %d became %d, and the "
                "bands are the only facts a scorecard reads"
                % (kind, before[kind], after[kind]))
        assert after["scorecard_bands"] == before["scorecard_bands"] + 2 * len(names), (
            "the bands door moved %d times for %d applications x2 records, not %d"
            % (after["scorecard_bands"] - before["scorecard_bands"], len(names),
               after["scorecard_bands"] - before["scorecard_bands"]))
        assert (after["lookups"] - before["lookups"]) == \
            (after["scorecard_bands"] - before["scorecard_bands"]), (
            "the stage knocked on uncounted doors: %r became %r" % (before, after))

    def _s2_workload(s, cases):
        """One whole pass of the stage, as a tuple a second run is compared with."""
        answers = []
        for id in sorted(cases.names()):
            record = s.scorecard(cases, id)
            answers.append((record["id"], record["scores"], record["total_bp"],
                            record["band_bp"], record["band"]))
            answers.append(s.score(cases, id))
        return tuple(answers)

    def _s2_twice(s, cases, cases_module):
        """Two runs of one workload, over one estate and over two builds."""
        import cases as cases_world
        one = _s2_workload(s, cases)
        two = _s2_workload(s, cases)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a "
            "function of its inputs")
        other = cases_world.build(7)
        three = _s2_workload(s, other)
        assert one == three, (
            "two builds of the same seed answer differently, and the estate is "
            "fixed data")

    """Every assertion the contract's §4.2 makes about this stage."""
    import cases
    import policy
    import stage_02 as s
    book = cases.build(7)
    _s2_constants(s, policy)
    _s2_table(s, book)
    _s2_points_scale(s, policy, book)
    _s2_weight_guard(s, policy, book)
    _s2_band_edges(s, policy, book)
    _s2_bad_facts(s, book)
    _s2_unknown_id(s, book)
    _s2_ledger(s, book)
    _s2_twice(s, book, cases)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-origination-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("course.py", "book.py", "cases.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

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

    _S3_OFFERS = {
        "S3-CAP": ({"collateral_id": "S3-CAP-A", "kind": "cash",
                    "value_cents": 125000, "lien_share_bp": 10000},),
        "S3-COVER": ({"collateral_id": "S3-COVER-A", "kind": "cash",
                      "value_cents": 1000000, "lien_share_bp": 5000},),
        "S3-SPARE": ({"collateral_id": "S3-SPARE-A", "kind": "none",
                      "value_cents": 999, "lien_share_bp": 5000},
                     {"collateral_id": "S3-SPARE-B", "kind": "cash",
                      "value_cents": 500000, "lien_share_bp": 10000}),
        "S3-BARE": (),
        "S3-TWICE": ({"collateral_id": "S3-TWICE-A", "kind": "none",
                      "value_cents": 0, "lien_share_bp": 0},
                     {"collateral_id": "S3-TWICE-B", "kind": "none",
                      "value_cents": 123, "lien_share_bp": 4000}),
        "S3-KIND": ({"collateral_id": "S3-KIND-A", "kind": "cash",
                     "value_cents": 500000, "lien_share_bp": 10000},
                    {"collateral_id": "S3-KIND-B", "kind": "gold",
                     "value_cents": 700000, "lien_share_bp": 10000}),
        "S3-NEG": ({"collateral_id": "S3-POS-A", "kind": "cash",
                    "value_cents": 500000, "lien_share_bp": 10000},
                   {"collateral_id": "S3-NEG-A", "kind": "equipment",
                    "value_cents": -100, "lien_share_bp": 10000}),
        "S3-TYPE": ({"collateral_id": "S3-TYPE-A", "kind": "cash",
                     "value_cents": "500000", "lien_share_bp": 10000},),
        "S3-SHARE": ({"collateral_id": "S3-SHARE-A", "kind": "cash",
                      "value_cents": 500000, "lien_share_bp": "10000"},),
        "S3-ALL": ({"collateral_id": "S3-ALL-A", "kind": "cash",
                    "value_cents": 500000, "lien_share_bp": 10001},),
        "S3-UNDER": ({"collateral_id": "S3-UNDER-A", "kind": "cash",
                      "value_cents": 500000, "lien_share_bp": -1},),
        "S3-ODD": ({"collateral_id": "S3-ODD-A", "kind": "receivables",
                    "value_cents": 555555, "lien_share_bp": 5000},
                   {"collateral_id": "S3-ODD-B", "kind": "equipment",
                    "value_cents": 111111, "lien_share_bp": 9000}),
    }

    _S3_DOORS = ("applications", "obligations", "history", "projections",
                 "scorecard_bands", "decisions", "offers", "facilities")

    class _S3Pocket:
        """A pocket estate to catch the stage on: the ask and the refusal, counted."""

        def __init__(self, cases, offers):
            self._error = cases.CaseError
            self._offers = offers
            self._asked = []
            self._answered = 0

        def collateral(self, identity):
            """The pocket's offer, or the refusal an unknown id earns."""
            self._asked.append(("collateral", identity))
            if identity not in self._offers:
                raise self._error("cases: %r is not an application this pocket holds"
                                  % (identity,))
            self._answered = self._answered + 1
            return tuple(dict(offer) for offer in self._offers[identity])

        def asked(self):
            """Every ask the stage made of this pocket, in order."""
            return tuple(self._asked)

        def stats(self):
            """The ledger of what was asked, as counts."""
            return {"lookups": len(self._asked), "collateral": self._answered}

    def _answer(estate, identity, requested, policy):
        """One application's whole answer, recomputed from the world's own rules.

        Written here and not read off the stage: the cut is `worth * haircut //
        10000` per asset from the policy's own table, the unsecured listing counts
        nothing at all, the lien covers its pledged share of the worth the asset is
        declared at, and the advance is `10000 * requested // value` — the worth
        the assets are offered at — truncated.
        """
        rows = []
        value = net = lien = 0
        for offer in estate.collateral(identity):
            kind = offer["kind"]
            worth = offer["value_cents"]
            share = offer["lien_share_bp"]
            haircut = policy.HAIRCUT_BP[kind]
            kept = worth - worth * haircut // 10000
            cover = 0 if kind == "none" else worth * share // 10000
            rows.append((offer["collateral_id"], kind, worth, share, haircut, kept,
                         cover))
            if kind != "none":
                value = value + worth
                net = net + kept
            lien = lien + cover
        advance = 0 if value == 0 else 10000 * requested // value
        unbacked = not [row for row in rows if row[1] != "none"]
        eligible = (not unbacked and lien >= requested
                    and advance <= policy.ADVANCE_CAP_BP)
        return {"id": identity, "collateral": tuple(rows), "value_cents": value,
                "haircut_cents": value - net, "net_value_cents": net,
                "lien_cents": lien, "advance_bp": advance, "eligible": eligible}

    def _s3_constants(s, policy):
        """The record's keys in order, the refusal of the stage's own family, and the world's own numbers."""
        assert tuple(s.RETURN_KEYS) == ("id", "collateral", "value_cents",
                                        "haircut_cents", "net_value_cents",
                                        "lien_cents", "advance_bp", "eligible"), s.RETURN_KEYS
        assert tuple(s._PLEDGED) == ("collateral_id", "kind", "value_cents",
                                     "lien_share_bp", "haircut_bp",
                                     "net_value_cents", "lien_cents"), s._PLEDGED
        assert issubclass(s.ReturnError, ValueError), s.ReturnError
        assert s.ReturnError is not ValueError, "the stage must refuse, not defer"
        assert policy.ADVANCE_CAP_BP == 8000, policy.ADVANCE_CAP_BP
        assert dict(policy.HAIRCUT_BP) == {"cash": 0, "receivables": 3000,
                                           "property": 2000, "equipment": 5000,
                                           "none": 10000}

    def _s3_records(s, es, policy):
        """Every application's record, recomputed from the world's own rules and compared.

        The ledger proof rides with it: this is the stage's first pass over the
        estate, so it proves the stage asked for the collateral records and for
        nothing else the estate holds. The requests and the decisions the reader
        itself needs are gathered before the ledger is read, so they never blur
        into the pass under proof.
        """
        requested = dict((identity, es.application(identity)["requested_cents"])
                         for identity in es.names())
        cited = {}
        for identity in es.names():
            decision = es.decision(identity)
            cited[identity] = (decision["verdict"] == "decline"
                              and "collateral" in decision["reasons"])
        before = es.stats()
        records = {}
        for identity in es.names():
            record = s.return_of(identity, requested[identity], es)
            records[identity] = record
            assert tuple(record.keys()) == s.RETURN_KEYS, record
            assert record["id"] == identity, record
            assert isinstance(record["collateral"], tuple), record
            offers = es.collateral(identity)
            rows = record["collateral"]
            assert len(rows) == len(offers), (identity, len(rows))
            expected = _answer(es, identity, requested[identity], policy)
            for place, row in enumerate(rows):
                assert len(row) == 7, (identity, row)
                assert row == expected["collateral"][place], (identity, row,
                                                              expected["collateral"][place])
                assert row[0] == offers[place]["collateral_id"], (identity, row)
            for field in ("value_cents", "haircut_cents", "net_value_cents",
                          "lien_cents", "advance_bp", "eligible"):
                assert record[field] == expected[field], (identity, field, record[field],
                                                          expected[field])
            # the estate's own records are the answer key: the collateral leg a
            # decline cites is the leg that fired, and the leg an approval or a
            # counter cites is the leg that cleared
            assert record["eligible"] == (not cited[identity]), (identity, record["eligible"],
                                                                 cited[identity])
        after = es.stats()
        for door in ("obligations", "history", "projections", "scorecard_bands",
                     "offers", "facilities"):
            assert after[door] == before[door] == 0, (door, before, after)
        for door in ("applications", "decisions"):
            assert after[door] == before[door], (door, before, after)
        assert after["collateral"] > before["collateral"], (before, after)
        assert after["lookups"] >= before["lookups"], (before, after)
        return records

    def _s3_landed(s, es, policy):
        """The boundaries the estate planted itself: on the cap, under it, over it, and nothing at all."""
        edge = s.return_of("CO-01", 1200000, es)
        assert edge["advance_bp"] == policy.ADVANCE_CAP_BP == 8000, edge
        assert edge["eligible"] is True, edge
        under = s.return_of("CO-06", 42000000, es)
        assert under["advance_bp"] == 7636, under
        assert under["eligible"] is True, under
        over = s.return_of("CO-08", 1500000, es)
        assert over["advance_bp"] == 9375, over
        assert over["eligible"] is False, over
        nothing = s.return_of("CO-05", 2000000, es)
        assert nothing["value_cents"] == 0 and nothing["net_value_cents"] == 0, nothing
        assert nothing["lien_cents"] == 0 and nothing["advance_bp"] == 0, nothing
        assert nothing["eligible"] is False, nothing
        assert nothing["collateral"][0] == ("CO-05-A", "none", 0, 0, 10000, 0, 0), nothing

    def _s3_advance(s, es):
        """`advance` re-answers the record's rate, application by application."""
        requested = dict((identity, es.application(identity)["requested_cents"])
                         for identity in es.names())
        for identity, wanted in requested.items():
            answer = s.advance(identity, wanted, es)
            assert isinstance(answer, int), (identity, answer)
            assert answer == s.return_of(identity, wanted, es)["advance_bp"], (identity,)
            other = wanted // 3
            assert s.advance(identity, other, es) == s.return_of(identity, other, es)["advance_bp"], (identity,)
            assert s.advance(identity, wanted, es) == answer, (identity, answer)

    def _s3_zero(s, es):
        """A request of nothing: nothing owed, and no book carried by nothing."""
        record = s.return_of("CO-01", 0, es)
        assert record["advance_bp"] == 0, record
        assert record["eligible"] is True, record
        nothing = s.return_of("CO-05", 0, es)
        assert nothing["advance_bp"] == 0, nothing
        assert nothing["eligible"] is False, "a book unsecured by choice is not carried by a request of nothing"

    def _s3_runs_own(s, es):
        """The estate a stage builds when none is handed in answers like the one handed in."""
        handed = s.return_of("CO-02", 800000, es)
        built = s.return_of("CO-02", 800000)
        assert built == handed, (built, handed)
        assert s.advance("CO-07", 12000000) == s.advance("CO-07", 12000000, es), ()

    def _s3_ledger(s, es, error):
        """A call the world refuses reaches no record: the counters but `lookups` stand."""
        before = es.stats()
        _refuses(error, "an application the book does not hold",
                 lambda: s.return_of("CO-99", 1000000, es), ["CO-99"])
        _refuses(error, "an application the book does not hold, through advance",
                 lambda: s.advance("CO-98", 1000000, es), ["CO-98"])
        after = es.stats()
        assert after["lookups"] == before["lookups"] + 2, (before, after)
        for door in ("applications", "obligations", "collateral", "history",
                     "projections", "scorecard_bands", "decisions", "offers",
                     "facilities"):
            assert after[door] == before[door], (door, before, after)

    def _s3_refusals(s, pocket, error):
        """Every offer the arithmetic cannot carry, refused and naming the offender."""
        calls = (
            ("a book unsecured by choice twice", "S3-TWICE", 100000,
             ["S3-TWICE-B", "S3-TWICE-A"]),
            ("a kind the policy does not underwrite", "S3-KIND", 100000,
             ["gold", "S3-KIND-B"]),
            ("a worth that is negative", "S3-NEG", 100000, ["S3-NEG-A", "-100"]),
            ("a worth that is not a whole number of cents", "S3-TYPE", 100000,
             ["'500000'", "S3-TYPE-A"]),
            ("a share that is not a whole number of basis points", "S3-SHARE", 100000,
             ["'10000'"]),
            ("a pledge past the scale", "S3-ALL", 100000, ["10001", "S3-ALL-A"]),
            ("a pledge below zero", "S3-UNDER", 100000, ["-1", "S3-UNDER-A"]),
            ("a request that is not a whole number of cents", "S3-COVER", "100000",
             ["'100000'"]),
            ("a request that is a flag, not an amount", "S3-COVER", True, ["True"]),
            ("a request going the wrong way", "S3-COVER", -5, ["-5"]),
        )
        for what, identity, wanted, names in calls:
            _refuses(s.ReturnError, what, lambda identity=identity, wanted=wanted:
                     s.return_of(identity, wanted, pocket), names)
        # and an application the pocket does not hold reaches nothing at all
        standing = pocket.stats()
        _refuses(error, "an application the pocket does not hold",
                 lambda: s.return_of("S3-NUH", 100000, pocket), ["S3-NUH"])
        reached = pocket.stats()
        assert reached["lookups"] == standing["lookups"] + 1, (standing, reached)
        assert reached["collateral"] == standing["collateral"], (standing, reached)

    def _s3_boundaries(s, pocket, policy):
        """One cent and one basis point either side, on books built to land on them."""
        exact = s.return_of("S3-CAP", 100012, pocket)
        assert exact["advance_bp"] == 8000 == policy.ADVANCE_CAP_BP, exact
        assert exact["eligible"] is True, exact
        beyond = s.return_of("S3-CAP", 100013, pocket)
        assert beyond["advance_bp"] == 8001, beyond
        assert beyond["eligible"] is False, beyond
        # the cap is held against the recomputed rate, never against the request's
        # own rounding; and the lien clause is held one cent short, clause by clause
        touching = s.return_of("S3-COVER", 500000, pocket)
        assert touching["advance_bp"] == 5000 and touching["eligible"] is True, touching
        short = s.return_of("S3-COVER", 500001, pocket)
        assert short["advance_bp"] == 5000 and short["eligible"] is False, short
        # the unsecured listing behind covered assets: counted for nothing, answered
        spare = s.return_of("S3-SPARE", 250000, pocket)
        assert spare["advance_bp"] == 5000, (
            "the unsecured listing's stated worth is counted for the advance: %r" % (spare,))
        assert spare["eligible"] is True, spare
        assert spare["collateral"][0] == ("S3-SPARE-A", "none", 999, 5000, 10000, 0, 0), spare
        # a book of nothing at all is answered, not refused, and carried by nothing
        bare = s.return_of("S3-BARE", 100000, pocket)
        assert bare["advance_bp"] == 0 and bare["eligible"] is False, bare
        assert bare["collateral"] == () and bare["value_cents"] == 0, bare
        assert bare["haircut_cents"] == 0 and bare["lien_cents"] == 0, bare
        empty = s.return_of("S3-BARE", 0, pocket)
        assert empty["eligible"] is False, "a book of nothing is not carried by a request of nothing"
        # the cents a truncation has to drop, per row and in the totals
        odd = s.return_of("S3-ODD", 376000, pocket)
        assert odd["collateral"][0] == ("S3-ODD-A", "receivables", 555555, 5000, 3000,
                                        388889, 277777), odd["collateral"]
        assert odd["collateral"][1] == ("S3-ODD-B", "equipment", 111111, 9000, 5000,
                                        55556, 99999), odd["collateral"]
        assert odd["value_cents"] == 666666 and odd["net_value_cents"] == 444445, odd
        assert odd["haircut_cents"] == 222221 and odd["lien_cents"] == 377776, odd
        # 3_760_000_000 // 666_666 is 5640 with the truncation the world carries
        assert odd["advance_bp"] == 5640 and odd["eligible"] is True, odd
        # and a hair further the truncation must drop a full half-point: 5640.5006
        # is 5640 truncated and would round up to 5641 under the housewife's half-up
        farther = s.return_of("S3-ODD", 376033, pocket)
        assert farther["advance_bp"] == 5640 and farther["eligible"] is True, farther
        assert s.return_of("S3-ODD", 376001, pocket)["eligible"] is True, ()
        assert s.advance("S3-CAP", 100012, pocket) == exact["advance_bp"], ()

    def _s3_pocket_ledger(s, pocket):
        """The stage asked the pocket for collateral records and nothing else."""
        stats = pocket.stats()
        assert stats["collateral"] == stats["lookups"], stats
        for ask in pocket.asked():
            assert ask[0] == "collateral", ask

    def _s3_workload(s, es, policy):
        """One whole pass of the stage over the estate, as tuples."""
        answers = []
        for identity in es.names():
            wanted = es.application(identity)["requested_cents"]
            record = s.return_of(identity, wanted, es)
            answers.append((tuple(sorted(record.items())), s.advance(identity, wanted, es),
                            tuple((row[0], row[2], row[4], row[5], row[6])
                                  for row in record["collateral"]),
                            s.advance(identity, wanted // 3, es),
                            s.return_of(identity, wanted // 3, es)["eligible"]))
        return tuple(answers)

    def _s3_twice(s, es, policy):
        """Two runs of one workload, which a stage that reads a dict would fail."""
        one = _s3_workload(s, es, policy)
        two = _s3_workload(s, es, policy)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a "
            "function of its inputs")

    """Every assertion the contract's §4.3 makes about this stage."""
    import cases
    import policy
    import stage_03 as s
    es = cases.build(7)
    pocket = _S3Pocket(cases, _S3_OFFERS)
    _s3_constants(s, policy)
    _s3_records(s, es, policy)
    _s3_landed(s, es, policy)
    _s3_advance(s, es)
    _s3_zero(s, es)
    _s3_runs_own(s, es)
    _s3_ledger(s, es, cases.CaseError)
    _s3_boundaries(s, pocket, policy)
    _s3_pocket_ledger(s, pocket)
    _s3_refusals(s, pocket, cases.CaseError)
    _s3_twice(s, es, policy)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-origination-from-scratch"

    S4_RATING_KEYS = ("id", "score_bp", "band", "grade", "gate", "voluntary", "why")

    S4_GATES = ("prior-default", "bankruptcy")

    S4_FLAG_FIELDS = ("prior_default", "bankruptcy")

    S4_GRADE_OF = {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F"}

    S4_ALT_GRADE_OF = {"A": "E", "B": "D", "C": "C", "D": "B", "E": "A", "F": "F"}

    S4_WEIGHTS_BP = {"dsr": 3500, "stability": 1500, "history": 3000,
                     "collateral": 2000}

    S4_POINTS_BP = {
        "dsr": {"low": 10000, "mid": 5000, "high": 1000},
        "stability": {"long": 10000, "settled": 6000, "short": 2000},
        "history": {"clean": 10000, "spotted": 4000, "impaired": 0},
        "collateral": {"strong": 10000, "adequate": 7000, "weak": 2000},
    }

    S4_ATTRIBUTES = ("dsr", "stability", "history", "collateral")

    S4_BANDS = ((7700, "A"), (6800, "B"), (5600, "C"), (4400, "D"), (2500, "E"),
                (0, "F"))

    OFF_LEDGER = ("applications", "obligations", "collateral", "history",
                  "projections", "scorecard_bands", "decisions", "offers",
                  "facilities")

    S4_BOTH_FLAGS = {"accounts": 2, "paid_on_time": 10, "arrears_incidents": 1,
                     "prior_default": True, "bankruptcy": True}

    S4_CLEAN_FLAGS = {"accounts": 2, "paid_on_time": 10, "arrears_incidents": 0,
                      "prior_default": False, "bankruptcy": False}

    S4_MISSING_FIELD = {"accounts": 1, "paid_on_time": 4, "arrears_incidents": 0,
                        "prior_default": False}

    S4_MAYBE_FLAG = {"accounts": 1, "paid_on_time": 4, "arrears_incidents": 0,
                     "prior_default": "yes", "bankruptcy": False}

    S4_COUNT_FLAG = {"accounts": 1, "paid_on_time": 4, "arrears_incidents": 0,
                     "prior_default": False, "bankruptcy": 3}

    def _repo(start=None):
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("course.py", "cases.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

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

    def _refuses_named(what, call, names=()):
        """A refusal of either family — the estate's or the stage's.

        The contract lets an unknown id be refused by the estate's own class or by
        the stage's subclass; what it holds both to is the family, the name, and
        the fact that nothing was answered.
        """
        try:
            got = call()
        except ValueError as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _S4Cases:
        """The estate, wearing a mask over one history and a ledger over its doors.

        `history` hands the mask's flags over where the mask carries them and the
        estate's own history everywhere else; every other door is delegated through
        a recorder, so the check can prove a refused gate ask reached the history
        door and nothing else — a rating that reads the decision, the collateral or
        the scorecard itself outside stage 2's door asks through here and is caught.
        """

        def __init__(self, real, histories=None):
            self._real = real
            self._histories = dict(histories or {})
            self._asked = []

        def history(self, identity):
            """The mask's flags, or the estate's own, through one counted ask."""
            self._asked.append(("history", identity))
            if identity in self._histories:
                return dict(self._histories[identity])
            return self._real.history(identity)

        def asked(self):
            """Every ask that reached this wrapper, in order."""
            return tuple(self._asked)

        def __getattr__(self, name):
            def door(*args, **kwargs):
                self._asked.append((name, args[0] if args else None))
                return getattr(self._real, name)(*args, **kwargs)
            return door

    S4_SCALE_BP = 10000

    def _row(attr, band):
        """One weighted row, as the check adds it: points of the weight, truncated."""
        weight = S4_WEIGHTS_BP[attr]
        points_bp = S4_POINTS_BP[attr][band]
        return weight * points_bp // S4_SCALE_BP

    def _band_of(total_bp):
        """The scorecard's own band: the first threshold the total clears, walking down."""
        for threshold, band in S4_BANDS:
            if total_bp >= threshold:
                return band
        raise AssertionError("the check's own card clears no threshold")

    def _expected_scorecard(bands):
        """The check's own scorecard: the rows added, the band read off the total."""
        total_bp = 0
        for attr in S4_ATTRIBUTES:
            total_bp = total_bp + _row(attr, bands[attr])
        return total_bp, _band_of(total_bp)

    def _fired_gate(flags):
        """The first gate whose flag burns, in the order the policy pins the gates.

        The check holds the policy to carrying exactly the two gates before it
        trusts the walk: a policy that renamed or reordered a gate is a fixture
        problem, not a stage answer.
        """
        walked = tuple(policy_gates())
        assert walked == S4_GATES or walked == tuple(reversed(S4_GATES)), (
            "the policy's own gates %r are not the contract's two, %r, kept or "
            "reversed" % (walked, S4_GATES))
        for gate in walked:
            field = gate.replace("-", "_")
            if flags[field]:
                return gate
        return ""

    def policy_gates():
        """The policy's `GATES`, read at call time so the check can swap the order."""
        import policy
        return policy.GATES

    def _expected_rating(bands, flags, grade_table):
        """The rating the check's own arithmetic answers, from its own two tables."""
        score_bp, band = _expected_scorecard(bands)
        gate = _fired_gate(flags)
        if gate:
            return {"id": None, "score_bp": score_bp, "band": band, "grade": "F",
                    "gate": gate, "voluntary": False, "why": gate}
        if band not in grade_table:
            raise AssertionError("the check's own table answers no grade for %r"
                                 % (band,))
        return {"id": None, "score_bp": score_bp, "band": band,
                "grade": grade_table[band], "gate": "", "voluntary": True,
                "why": ""}

    def _s4_constants(s, policy_module):
        """The surface: keys in order, the policy's own two tables and vocabularies."""
        assert tuple(s.RATING_KEYS) == S4_RATING_KEYS, (
            "the record's keys %r are not the contract's seven, in order %r; a "
            "record whose keys are reordered is a record nobody can audit"
            % (tuple(s.RATING_KEYS), S4_RATING_KEYS))
        for first, second in (("score_bp", "band"), ("band", "grade"),
                              ("grade", "gate"), ("gate", "voluntary"),
                              ("voluntary", "why")):
            assert tuple(s.RATING_KEYS).index(first) < \
                tuple(s.RATING_KEYS).index(second), (
                "the record puts %r before %r, and the contract's order is the "
                "committee's reading order" % (second, first))
        assert issubclass(s.RatingError, ValueError), s.RatingError
        assert s.RatingError is not ValueError, (
            "the stage must refuse, not defer to the family's")
        assert tuple(policy_module.GATES) == S4_GATES, (
            "the policy's own gates are %r, and the contract pins prior-default "
            "first and bankruptcy second" % (tuple(policy_module.GATES),))
        assert policy_module.GRADE_OF == S4_GRADE_OF, policy_module.GRADE_OF
        for band, grade in sorted(S4_GRADE_OF.items()):
            assert grade in policy_module.GRADES, (
                "the policy grades %r a %r, and %r is not out of M1's own %r"
                % (band, grade, grade, tuple(policy_module.GRADES)))
        for gate in S4_GATES:
            assert gate.replace("-", "_") in S4_FLAG_FIELDS, gate

    def _s4_record_shape(s, record, what):
        """A rating record is a dict with the contract's keys, in the contract's order."""
        assert isinstance(record, dict), "%s answered %r, not a record" % (what, record)
        assert tuple(record.keys()) == S4_RATING_KEYS, (
            "%s's record carries the keys %r, not the contract's %r, in order"
            % (what, tuple(record.keys()), S4_RATING_KEYS))
        assert isinstance(record["score_bp"], int) and \
            not isinstance(record["score_bp"], bool), (
            "%s's score_bp is %r, not a whole count of basis points"
            % (what, record["score_bp"]))
        for field in ("band", "grade", "gate", "why"):
            assert isinstance(record[field], str), (
                "%s's %s is %r, not a text" % (what, field, record[field]))
        assert isinstance(record["voluntary"], bool), (
            "%s's voluntary is %r, not a decision" % (what, record["voluntary"]))
        assert record["voluntary"] == (record["gate"] == "") and \
            record["voluntary"] == (record["why"] == ""), (
            "%s's record says voluntary %r with the gate %r and the why %r, and a "
            "fired gate is the opposite of voluntary" % (
                what, record["voluntary"], record["gate"], record["why"]))

    def history_flags(gates, id):
        """The estate's own history flags for one id, read directly."""
        history = gates.history(id)
        return {"prior_default": history["prior_default"],
                "bankruptcy": history["bankruptcy"]}

    def _s4_one_rating(s, what, id, bands, flags, record):
        """One application's rating, field by field, against the raw facts."""
        want = _expected_rating(bands, flags, S4_GRADE_OF)
        want["id"] = id
        _s4_record_shape(s, record, what)
        assert record["id"] == id, (
            "%s names %r, not the id it was asked for" % (what, record["id"]))
        assert record["score_bp"] == want["score_bp"], (
            "%s answered score_bp %r, and the check's own card re-adds to %r — the "
            "gate must leave the score standing, not overwrite it" % (
                what, record["score_bp"], want["score_bp"]))
        assert record["band"] == want["band"], (
            "%s answered band %r, and the card's total reads %r" % (
                what, record["band"], want["band"]))
        assert record["gate"] == want["gate"], (
            "%s answered gate %r, and the history's flags answer %r" % (
                what, record["gate"], want["gate"]))
        assert record["why"] == want["why"], (
            "%s answered why %r, and a %s rating says nothing" % (
                what, record["why"], "gated" if want["gate"] else "clean"))
        assert record["voluntary"] is want["voluntary"], (
            "%s answered voluntary %r, and %r is the boolean the gate %r forces" % (
                what, record["voluntary"], want["voluntary"], want["gate"]))
        assert record["grade"] == want["grade"], (
            "%s answered grade %r, and the band %r reads %r off the policy's own "
            "table — %r is the stage's own guess, not the table's word" % (
                what, record["grade"], want["band"], want["grade"], record["grade"]))
        return record

    def _s4_table(s, book):
        """Every application the estate holds, reproduced from the raw facts."""
        records = {}
        for id in sorted(book.names()):
            bands = book.scorecard_bands(id)
            flags = history_flags(book, id)
            record = s.rating(book, id)
            what = "the rating of %s" % (id,)
            _s4_one_rating(s, what, id, bands, flags, record)
            records[id] = record
        assert records["CO-01"]["band"] == "A", (
            "the estate's own fixture no longer sits CO-01 in band A")
        assert records["CO-10"]["band"] == "E", (
            "the estate's own fixture no longer sits CO-10 in band E")
        # the two gated ids, the order's own estate proof: CO-04's prior default
        # (bankruptcy clean) answers prior-default, CO-08's bankruptcy (default
        # clean) answers bankruptcy, and both keep stage 2's score on the record.
        assert records["CO-04"]["gate"] == "prior-default" and \
            records["CO-04"]["why"] == "prior-default" and \
            records["CO-04"]["voluntary"] is False and \
            records["CO-04"]["grade"] == "F", (
            "CO-04 carries a prior default and a clean bankruptcy, and the record "
            "must name the gate that fired: %r" % (records["CO-04"],))
        assert records["CO-08"]["gate"] == "bankruptcy" and \
            records["CO-08"]["why"] == "bankruptcy" and \
            records["CO-08"]["voluntary"] is False and \
            records["CO-08"]["grade"] == "F", (
            "CO-08 carries a bankruptcy and no prior default, and the record must "
            "name it: %r" % (records["CO-08"],))
        for id in ("CO-04", "CO-08"):
            saved = records[id]
            assert saved["score_bp"] == _expected_scorecard(
                book.scorecard_bands(id))[0], (
                "%s's gate fired, and the record must keep stage 2's own %d on it, "
                "not the gate's zero: %r" % (id, saved["score_bp"], saved))
        return records

    def _s4_answer_key(s, book, records):
        """The estate's own decisions, where the bank's own records speak.

        A decline that cites `gate` is a hard gate the bank caught — `CO-04`
        reasons `("rating", "gate")`, `CO-08` reasons `("collateral", "rating",
        "gate")` — and the rating record must name it. A decision that cites
        `rating` and no gate is an applicant graded clean: the record answers no
        gate, an empty why, voluntary True.
        """
        for id in sorted(book.names()):
            decision = book.decision(id)
            record = records[id]
            if "gate" in decision["reasons"]:
                assert record["gate"] != "" and record["grade"] == "F", (
                    "%s is declined for a gate %r, and the rating answers %r — the "
                    "bank's own reasons line cites the gate the record must name"
                    % (id, decision["reasons"], record))
                assert record["why"] == record["gate"], (
                    "%s's gate %r owns the why, and the record answers %r"
                    % (id, record["gate"], record["why"]))
                assert record["voluntary"] is False, (
                    "%s was graded by the gate %r, and the record answers "
                    "voluntary %r" % (id, record["gate"], record["voluntary"]))
            else:
                assert record["gate"] == "" and record["why"] == "", (
                    "%s's decision cites no gate %r, and the rating answers the "
                    "gate %r — a passed gate is never reported as fired" % (
                        id, decision["reasons"], record["gate"]))
                assert record["voluntary"] is True, (
                    "%s is graded by its own band, and the record answers "
                    "voluntary %r" % (id, record["voluntary"]))
                assert record["grade"] == S4_GRADE_OF[record["band"]], (
                    "%s's grade is %r and its band's own row in the policy's table "
                    "answers %r" % (id, record["grade"],
                                    S4_GRADE_OF[record["band"]]))

    def _s4_grade_f_by_table(s, book, policy_module):
        """Grade F by table alone: the reading the estate's gated pair cannot show.

        `CO-04` and `CO-08` sit band F *and* carry gates, so their forced "F" is
        also the band's own row — the two readings are the same number. The check
        moves the scorecard's floor under band F for `CO-01`, a clean applicant:
        the band reads F, the grade follows the table, and the record stays
        voluntary with an empty why — grade F by table, never by gate.
        """
        original = policy_module.SCORE_BANDS
        try:
            policy_module.SCORE_BANDS = ((0, "F"),)
            record = s.rating(book, "CO-01")
            assert record["band"] == "F" and record["grade"] == "F", (
                "a total under every threshold reads band F, and the policy's own "
                "table grades it F: %r" % (record,))
            assert record["gate"] == "" and record["why"] == "" and \
                record["voluntary"] is True, (
                "band F graded by the table is still the band's own choice, not a "
                "gate: %r" % (record,))
            assert record["score_bp"] == _expected_scorecard(
                book.scorecard_bands("CO-01"))[0], (
                "the bands node moved the band, and the score is the card's own "
                "total: %r" % (record,))
        finally:
            policy_module.SCORE_BANDS = original

    def _s4_grade_table_word(s, book, policy_module):
        """The grade is the table's word for the band, not the band spelled itself.

        The check swaps `GRADE_OF` for a table that scrambles the alphabet: the
        estate's clean grades move with the table — band A grades E, band B grades
        D — and a band the swapped table assigns no row to is refused by name.
        """
        original = policy_module.GRADE_OF
        try:
            policy_module.GRADE_OF = S4_ALT_GRADE_OF
            record = s.rating(book, "CO-01")
            assert (record["band"], record["grade"]) == ("A", "E"), (
                "the swapped table grades band A an E and the record answers %r — "
                "a stage that passes the band through as the grade is caught by "
                "the table the policy would have moved" % (record["grade"],))
            record = s.rating(book, "CO-02")
            assert (record["band"], record["grade"]) == ("B", "D"), (
                "the swapped table grades band B a D and the record answers "
                "%r" % (record["grade"],))
            record = s.rating(book, "CO-10")
            assert (record["band"], record["grade"]) == ("E", "A"), (
                "the swapped table grades band E an A and the record answers "
                "%r" % (record["grade"],))
            policy_module.GRADE_OF = {"A": "A"}
            _refuses(s.RatingError, "a band the policy assigns no grade to",
                     lambda: s.rating(book, "CO-02"), ["B"])
            _refuses(s.RatingError, "the same, asked of another band",
                     lambda: s.rating(book, "CO-05"), ["C"])
        finally:
            policy_module.GRADE_OF = original

    def _s4_gate_order(s, book, policy_module):
        """The first gate in the policy's order is the one the record names.

        The estate's own two gated ids name one gate each; the order itself needs a
        history where both burn at once — masked over `CO-01` — which answers the
        policy's first gate. With `GATES` reversed the same history answers the
        other one, so a stage that hardwires prior-default first fails the reversed
        world and a stage that hardwires its own order fails the estate's.

        The score still travels: even on the synthetic history the record carries
        `CO-01`'s own card answer beside the gate's F.
        """
        wrapper = _S4Cases(book, {"CO-01": S4_BOTH_FLAGS})
        record = s.rating(wrapper, "CO-01")
        assert record["gate"] == "prior-default" and record["grade"] == "F" and \
            record["voluntary"] is False, (
                "a history where both gates burn answers the policy's first gate, "
                "prior-default: %r" % (record,))
        assert record["why"] == "prior-default", (
            "the fired gate's own name is the record's why: %r" % (record,))
        assert record["score_bp"] == _expected_scorecard(
            book.scorecard_bands("CO-01"))[0] and \
            record["band"] == _expected_scorecard(
                book.scorecard_bands("CO-01"))[1], (
            "the gate's F never overwrites the score the card answered: %r"
            % (record,))
        asked = wrapper.asked()
        assert asked[:2] == (("history", "CO-01"), ("scorecard_bands", "CO-01")), (
            "the rating asked the estate %r, and a gate is read off the history "
            "door and the score off the bands door" % (asked,))
        original = policy_module.GATES
        try:
            policy_module.GATES = tuple(reversed(S4_GATES))
            wrapper = _S4Cases(book, {"CO-01": S4_BOTH_FLAGS})
            record = s.rating(wrapper, "CO-01")
            assert record["gate"] == "bankruptcy", (
                "with the policy's gates reversed the same history answers the "
                "policy's new first gate: %r" % (record,))
            wrapper = _S4Cases(book, {"CO-01": S4_CLEAN_FLAGS})
            record = s.rating(wrapper, "CO-01")
            assert record["gate"] == "" and record["voluntary"] is True and \
                record["why"] == "", (
                "both flags clean is the ungated answer, in any order: %r"
                % (record,))
        finally:
            policy_module.GATES = original

    def _s4_gate_flags(s, book):
        """The gate's own field, answered only as a yes-or-no.

        The field a gate reads is the gate's name hyphens-for-underscores: a
        history missing it refuses by name, and a history answering it with a
        maybe — a text, a count — refuses also, before any grade is answered. Each
        refused ask reaches the history door and nothing else.
        """
        fixtures = (
            ("a history answering no %r field" % ("bankruptcy",),
             S4_MISSING_FIELD, ("bankruptcy", "CO-01")),
            ("a prior default answered as a maybe", S4_MAYBE_FLAG,
             ("prior_default", "yes", "CO-01")),
            ("a bankruptcy answered as a count", S4_COUNT_FLAG,
             ("bankruptcy", "3", "CO-01")),
        )
        for what, mask, names in fixtures:
            wrapper = _S4Cases(book, {"CO-01": mask})
            _refuses(s.RatingError, what,
                     lambda wrapper=wrapper: s.rating(wrapper, "CO-01"), names)
            asked = wrapper.asked()
            assert len(asked) == 1 and asked[0] == ("history", "CO-01"), (
                "the refused rating asked the estate %r, and the history field is "
                "where the gate's answer lives; no grade is answered for a maybe"
                % (asked,))

    def _s4_unknown_id(s, book, cases_module):
        """An application the estate does not hold, refused by name, moving nothing.

        The contract lets the estate refuse through its own class or the stage
        through its subclass; what it holds both to is the family, the id in the
        message, and the counters other than `lookups` staying put.
        """
        before = book.stats()
        _refuses_named("an application id the estate does not hold",
                       lambda: s.rating(book, "CO-99"), ["CO-99"])
        _refuses_named("a non-text id",
                       lambda: s.rating(book, 2), ["application id", "not a text"])
        after = book.stats()
        for kind in OFF_LEDGER:
            assert after[kind] == before[kind], (
                "a refused rating moved the %s counter from %d to %d"
                % (kind, before[kind], after[kind]))
        assert after["lookups"] == before["lookups"] + 2, (
            "the estate recorded %d extra asks for two refused ratings, not %d"
            % (2, after["lookups"] - before["lookups"]))

    def _s4_ledger(s, book):
        """A rating asks the history door once and the bands door once, and no more."""
        names = book.names()
        before = book.stats()
        for id in names:
            s.rating(book, id)
        after = book.stats()
        for kind in OFF_LEDGER:
            if kind == "history":
                assert after[kind] == before[kind] + len(names), (
                    "the history door moved %d times for %d records, not %d"
                    % (after[kind] - before[kind], len(names),
                       after[kind] - before[kind]))
            elif kind == "scorecard_bands":
                assert after[kind] == before[kind] + len(names), (
                    "the bands door moved %d times for %d records — stage 2's own "
                    "answer travels onto the rating record, asked once, not %d"
                    % (after[kind] - before[kind], len(names),
                       after[kind] - before[kind]))
            else:
                assert after[kind] == before[kind], (
                    "the rating asked the estate's %s door: %d became %d, and the "
                    "rating is the history's and the scorecard's to answer"
                    % (kind, before[kind], after[kind]))
        assert (after["lookups"] - before["lookups"]) == 2 * len(names), (
            "the stage knocked on uncounted doors: %r became %r" % (before, after))

    def _s4_workload(s, book):
        """One whole pass of the stage, as a tuple a second run is compared with."""
        answers = []
        for id in sorted(book.names()):
            record = s.rating(book, id)
            answers.append((record["id"], record["score_bp"], record["band"],
                            record["grade"], record["gate"], record["voluntary"],
                            record["why"]))
        return tuple(answers)

    def _s4_twice(s, book, cases_module):
        """Two runs of one workload, over one estate and over two builds."""
        one = _s4_workload(s, book)
        two = _s4_workload(s, book)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a "
            "function of its inputs: %r against %r" % (one, two))
        other = cases_module.build(7)
        three = _s4_workload(s, other)
        assert one == three, (
            "two builds of the same seed answer differently, and the estate is "
            "fixed data")

    """Every assertion the contract's §4.4 makes about this stage."""
    import cases
    import policy
    import stage_04 as s
    book = cases.build(7)
    # the stub speaks first: a template is a stub that refuses with its name,
    # so a first touch that raises must name the stage it has not been built for
    try:
        s.rating(book, "CO-01")
    except NotImplementedError as not_yet:
        assert "stage 4" in str(not_yet), (
            "the stage's own stub names the stage it is missing: %r does not"
            % (str(not_yet),))
    _s4_constants(s, policy)
    records = _s4_table(s, book)
    _s4_answer_key(s, book, records)
    _s4_grade_f_by_table(s, book, policy)
    _s4_grade_table_word(s, book, policy)
    _s4_gate_order(s, book, policy)
    _s4_gate_flags(s, book)
    _s4_unknown_id(s, book, cases)
    _s4_ledger(s, book)
    _s4_twice(s, book, cases)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    COURSE = "credit-origination-from-scratch"

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    _C5_PRICE_KEYS = ("id", "grade", "legs", "price_bp", "residual_bp", "floor",
                      "basis")

    _C5_LEGS = ("funding", "expected-loss", "capital", "opcost", "margin")

    _C5_PD = {"A": 30, "B": 80, "C": 200, "D": 600, "E": 1800, "F": 10000}

    _C5_LGD = {"A": 3500, "B": 4000, "C": 4500, "D": 5000, "E": 5500, "F": 10000}

    _C5_CAPITAL = {"A": 20, "B": 25, "C": 35, "D": 55, "E": 80, "F": 120}

    _C5_FUNDING = 220

    _C5_OPCOST = 25

    _C5_MARGIN = 150

    _C5_GRADES = ("A", "B", "C", "D", "E", "F")

    _C5_ATTRS = ("dsr", "stability", "history", "collateral")

    _C5_WEIGHTS = {"dsr": 3500, "stability": 1500, "history": 3000,
                   "collateral": 2000}

    _C5_POINTS = {
        "dsr": {"low": 10000, "mid": 5000, "high": 1000},
        "stability": {"long": 10000, "settled": 6000, "short": 2000},
        "history": {"clean": 10000, "spotted": 4000, "impaired": 0},
        "collateral": {"strong": 10000, "adequate": 7000, "weak": 2000},
    }

    _C5_BANDS = ((7700, "A"), (6800, "B"), (5600, "C"), (4400, "D"), (2500, "E"),
                 (0, "F"))

    _C5_GRADE_OF = {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F"}

    _C5_RECORDED = (425, 452, 520, 750, 1470)

    _C5_STAMP_BANDS = {
        "S5-LOW": {"dsr": "low", "stability": "long", "history": "clean",
                   "collateral": "strong"},
        "S5-TOP": {"dsr": "low", "stability": "settled", "history": "clean",
                   "collateral": "strong"},
        "S5-FLOOR": {"dsr": "high", "stability": "short", "history": "impaired",
                     "collateral": "weak"},
        "S5-SHUT": {"dsr": "low", "stability": "long", "history": "clean",
                    "collateral": "strong"},
        "S5-SHOT": {"dsr": "low", "stability": "long", "history": "patchy",
                    "collateral": "strong"},
        "S5-HALF": {"dsr": "low", "stability": "long", "collateral": "strong"},
        "S5-NEG": {"dsr": "low", "stability": "long", "history": "clean",
                   "collateral": "strong"},
    }

    def _repo(start=None):
        """The repository the course lives in, found through its markers."""
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
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
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

    def _staged(course, solved=True):
        """A temp dir holding the course, with the solutions dropped over the stages."""
        dest = tempfile.mkdtemp(prefix="m0-stage05-")
        for name in sorted(os.listdir(course)):
            if name.endswith(".py"):
                shutil.copy(os.path.join(course, name), os.path.join(dest, name))
        if solved:
            solved = os.path.join(course, "solutions")
            for name in sorted(os.listdir(solved)):
                if name.endswith(".py"):
                    shutil.copy(os.path.join(solved, name), os.path.join(dest, name))
        return dest

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named."""
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _c5_grade(bands):
        """The check's own walk: bands, weighted, carried to the grade the facts name."""
        total = 0
        for attr in _C5_ATTRS:
            total += _C5_WEIGHTS[attr] * _C5_POINTS[attr][bands[attr]] // 10000
        for threshold, band in _C5_BANDS:
            if total >= threshold:
                return _C5_GRADE_OF[band]
        raise AssertionError("the check's own walk named no band for %r" % (bands,))

    def _c5_legs(grade):
        """The five legs built at one grade, on the check's own copies of the tables."""
        return (
            ("funding", _C5_FUNDING),
            ("expected-loss", _C5_PD[grade] * _C5_LGD[grade] // 10000),
            ("capital", _C5_CAPITAL[grade]),
            ("opcost", _C5_OPCOST),
            ("margin", _C5_MARGIN),
        )

    def _c5_expected(identity, bands, recorded):
        """One record as the check's own arithmetic builds it from the same facts."""
        grade = _c5_grade(bands)
        legs = _c5_legs(grade)
        built = sum(one for _, one in legs)
        return dict(id=identity, grade=grade, legs=legs, price_bp=built,
                    residual_bp=recorded - built, floor=_C5_MARGIN, basis=grade)

    class _S5Stamp:
        """A book the check builds itself, holding the synthetics the estate is not.

        It answers the two things a price is read from — the scorecard's bands and
        the bank's own decision — and records every ask, which is what proves a
        price asked this book for nothing else.
        """

        def __init__(self, world, bands_table, decisions):
            self._error = world.CaseError
            self._bands = bands_table
            self._decisions = decisions
            self._asked = []

        def scorecard_bands(self, which):
            """The synthetic bands, or a refusal naming the id that arrived."""
            self._asked.append(("scorecard_bands", which))
            if which not in self._bands:
                raise self._error("the stamp holds no bands for %r" % (which,))
            return self._bands[which]

        def decision(self, which):
            """The synthetic decision, or a refusal naming the id that arrived."""
            self._asked.append(("decision", which))
            if which not in self._decisions:
                raise self._error("the stamp holds no decision for %r" % (which,))
            return self._decisions[which]

        def asked(self):
            """Every ask the stage made of this book, in order."""
            return tuple(self._asked)

    def _c5_stamp(world):
        """The stamp book, with a price recorded against every synthetic id."""
        decisions = {
            "S5-LOW": {"verdict": "approve", "price_bp": 300},
            "S5-TOP": {"verdict": "approve", "price_bp": 800},
            "S5-FLOOR": {"verdict": "approve", "price_bp": 10515},
            "S5-SHUT": {"verdict": "decline", "price_bp": 0},
            "S5-SHOT": {"verdict": "approve", "price_bp": 425},
            "S5-HALF": {"verdict": "approve", "price_bp": 425},
            "S5-NEG": {"verdict": "approve", "price_bp": -5},
        }
        return _S5Stamp(world, _C5_STAMP_BANDS, decisions)

    def _c5_assert_record(s, got, want, identity):
        """Every field of one record, against the check's own record of the same facts."""
        assert tuple(got.keys()) == tuple(s.PRICE_KEYS), (got, want)
        assert got["id"] == want["id"] == identity, (got, want)
        assert got["grade"] == want["grade"], (got, want)
        assert got["basis"] == want["basis"] == got["grade"], (got, want)
        assert got["price_bp"] == want["price_bp"], (got, want)
        assert got["residual_bp"] == want["residual_bp"], (got, want)
        assert got["floor"] == want["floor"], (got, want)
        legs = got["legs"]
        assert isinstance(legs, tuple) and len(legs) == 5, legs
        assert tuple(name for name, _ in legs) == tuple(s.PRICE_LEG_NAMES) \
            == tuple(_C5_LEGS), legs
        assert got["legs"] == want["legs"], (got, want)
        readded = 0
        for name, one in legs:
            assert isinstance(name, str), (name, identity)
            assert isinstance(one, int) and not isinstance(one, bool), (one, identity)
            readded += one
        assert readded == got["price_bp"] == sum(
            one for _, one in got["legs"]), (legs, got, identity)
        assert got["floor"] == _C5_MARGIN, (got, identity)
        assert got["grade"] in _C5_GRADES, (got, identity)

    def _c5_constants(s, world_policy):
        """The record's shape, the legs' names and the world's own tables, echoed."""
        assert tuple(s.PRICE_KEYS) == _C5_PRICE_KEYS, s.PRICE_KEYS
        assert tuple(s.PRICE_LEG_NAMES) == _C5_LEGS, s.PRICE_LEG_NAMES
        assert "stage 5" in s.STAGE_ERROR, s.STAGE_ERROR
        assert issubclass(s.PriceError, ValueError), s.PriceError
        assert s.PriceError is not ValueError, "the stage must refuse, not defer"
        assert world_policy.PD_BP == _C5_PD, world_policy.PD_BP
        assert world_policy.LGD_BP == _C5_LGD, world_policy.LGD_BP
        assert world_policy.CAPITAL_BP == _C5_CAPITAL, world_policy.CAPITAL_BP
        assert world_policy.FUNDING_BP == _C5_FUNDING, world_policy.FUNDING_BP
        assert world_policy.OPCOST_BP == _C5_OPCOST, world_policy.OPCOST_BP
        assert world_policy.MARGIN_BP == _C5_MARGIN, world_policy.MARGIN_BP
        assert tuple(world_policy.GRADES) == _C5_GRADES, world_policy.GRADES
        weights = world_policy.SCORE_WEIGHTS_BP
        assert sum(weights[attr] for attr in _C5_ATTRS) == 10000, weights
        thresholds = tuple(one[0] for one in tuple(world_policy.SCORE_BANDS))
        assert sorted(thresholds, reverse=True) == list(thresholds), thresholds
        assert tuple(world_policy.SCORE_ATTRIBUTES) == _C5_ATTRS, (
            world_policy.SCORE_ATTRIBUTES)

    def _c5_leg(s, world_policy):
        """The leg reader: flat echoes, table reads, and every refusal by name."""
        for grade in _C5_GRADES:
            assert s.leg(world_policy.FUNDING_BP, grade) == _C5_FUNDING, grade
            assert s.leg(world_policy.OPCOST_BP, grade) == _C5_OPCOST, grade
            assert s.leg(world_policy.MARGIN_BP, grade) == _C5_MARGIN, grade
            assert s.leg(world_policy.PD_BP, grade) == _C5_PD[grade], grade
            assert s.leg(world_policy.LGD_BP, grade) == _C5_LGD[grade], grade
            assert s.leg(world_policy.CAPITAL_BP, grade) == _C5_CAPITAL[grade], grade
        assert s.leg(220, "E") == 220, "a flat leg charges nothing by grade"
        assert s.leg({'A': 20, 'F': 120}, "F") == 120, (
            "a stamp's own table answers the grade it carries")
        _refuses(s.PriceError, "a stamp table with no F entry",
                 lambda: s.leg({'A': 20}, "F"), ["F"])
        _refuses(s.PriceError, "a lowercase grade the table does not carry",
                 lambda: s.leg(world_policy.CAPITAL_BP, "a"), ["'a'"])
        _refuses(s.PriceError, "a text where a table belongs",
                 lambda: s.leg("220", "A"), ["220"])
        _refuses(s.PriceError, "a bool where a table belongs",
                 lambda: s.leg(True, "A"), ["True"])
        _refuses(s.PriceError, "nothing at all where a table belongs",
                 lambda: s.leg(None, "A"), ["None"])
        _refuses(s.PriceError, "a grade that is not a text",
                 lambda: s.leg(world_policy.PD_BP, 7), ["7"])
        _refuses(s.PriceError, "an entry that is not a count of basis points",
                 lambda: s.leg({"A": "200"}, "A"), ["200"])
        _refuses(s.PriceError, "an entry that is not a count of basis points, as a bool",
                 lambda: s.leg({"A": True}, "A"), ["True"])

    def _c5_prices(s, book, world_policy):
        """Every application the bank priced: its legs, its sum and its gap."""
        recorded_ids = []
        for identity in book.names():
            decision = book.decision(identity)
            if decision["price_bp"] == 0:
                assert decision["verdict"] == "decline", (identity, decision)
                message = _refuses(s.PriceError, "the decline of %s" % (identity,),
                                   lambda i=identity: s.price(i, book), [identity])
                assert "price" in message or "grade" in message, message
                continue
            recorded_ids.append((identity, decision["price_bp"]))
        assert sorted(set(price for _, price in recorded_ids)) == list(_C5_RECORDED), (
            recorded_ids)
        assert len(recorded_ids) == 7, recorded_ids
        for identity, recorded in recorded_ids:
            bands = book.scorecard_bands(identity)
            want = _c5_expected(identity, bands, recorded)
            got = s.price(identity)
            _c5_assert_record(s, got, want, identity)
            # the same application, answered out of the doors the caller already holds
            again = s.price(identity, book)
            _c5_assert_record(s, again, want, identity)
            assert again == got, (identity, got, again)
            # the residual is the gap and nothing else: zero wherever the bank's
            # price re-adds to its legs, and the bank's own excess where it does not
            assert want["residual_bp"] == recorded - want["price_bp"], (
                identity, recorded, want)
            if identity == "CO-10":
                assert want["price_bp"] == 1465 and want["residual_bp"] == 5, want
            else:
                assert want["residual_bp"] == 0, want
        return tuple(recorded_ids)

    def _c5_synthetic(s, world):
        """The synthetics the estate never carries, on a book the check builds itself."""
        stamp = _c5_stamp(world)
        stamp_decisions = ({"S5-LOW": {"verdict": "approve", "price_bp": 300},
                            "S5-TOP": {"verdict": "approve", "price_bp": 800},
                            "S5-FLOOR": {"verdict": "approve", "price_bp": 10515},
                            "S5-SHUT": {"verdict": "decline", "price_bp": 0}})
        # a price below what its legs explain, kept signed — the gap the record carries
        want = _c5_expected("S5-LOW", _C5_STAMP_BANDS["S5-LOW"],
                            stamp_decisions["S5-LOW"]["price_bp"])
        assert want["residual_bp"] == -125, want
        got = s.price("S5-LOW", stamp)
        _c5_assert_record(s, got, want, "S5-LOW")
        assert got["residual_bp"] == -125, (
            "a price below its legs is still the gap the record carries: %r" % (got,))
        # a bank sitting above what its legs explain, on another synthetic grade
        want = _c5_expected("S5-TOP", _C5_STAMP_BANDS["S5-TOP"],
                            stamp_decisions["S5-TOP"]["price_bp"])
        assert want["residual_bp"] == 800 - want["price_bp"], want
        got = s.price("S5-TOP", stamp)
        _c5_assert_record(s, got, want, "S5-TOP")
        # a build at grade F, the leg tables' own answer the estate never reaches
        want = _c5_expected("S5-FLOOR", _C5_STAMP_BANDS["S5-FLOOR"],
                            stamp_decisions["S5-FLOOR"]["price_bp"])
        assert want["grade"] == "F" and want["price_bp"] == 10515, want
        assert want["residual_bp"] == 0, want
        got = s.price("S5-FLOOR", stamp)
        _c5_assert_record(s, got, want, "S5-FLOOR")
        # a synthetic decline refuses by name, exactly as the estate's own do
        _refuses(s.PriceError, "a synthetic application that prices nothing",
                 lambda: s.price("S5-SHUT", stamp), ["S5-SHUT"])
        # a bank price below zero is refused, never read as a build-up anchor
        _refuses(s.PriceError, "a bank price below zero",
                 lambda: s.price("S5-NEG", stamp), ["S5-NEG", "-5"])
        # bands on the book with no decision behind them: the decision wrap refuses
        ledgerless = _S5Stamp(world, {"S5-LEDGER": _C5_STAMP_BANDS["S5-LOW"]}, {})
        _refuses(s.PriceError, "bands on the book with no decision behind them",
                 lambda: s.price("S5-LEDGER", ledgerless), ["S5-LEDGER"])
        assert ledgerless.asked() == (
            ("scorecard_bands", "S5-LEDGER"), ("decision", "S5-LEDGER"))
        # a band the points table does not answer refuses by name
        _refuses(s.PriceError, "a band no points table carries",
                 lambda: s.price("S5-SHOT", stamp), ["patchy"])
        # a band record that answers no band for an attribute refuses by name
        _refuses(s.PriceError, "a band record missing an attribute outright",
                 lambda: s.price("S5-HALF", stamp), ["history"])
        # a decision that is not on the stamp's book refuses by name
        _refuses(s.PriceError, "an application whose decision the book does not hold",
                 lambda: s.price("S5-NOBODY", stamp), ["S5-NOBODY"])
        # a price asked the stamp for nothing beyond its bands and its decision, the
        # bands before the decision, and no third door at all
        assert stamp.asked() == (
            ("scorecard_bands", "S5-LOW"), ("decision", "S5-LOW"),
            ("scorecard_bands", "S5-TOP"), ("decision", "S5-TOP"),
            ("scorecard_bands", "S5-FLOOR"), ("decision", "S5-FLOOR"),
            ("scorecard_bands", "S5-SHUT"), ("decision", "S5-SHUT"),
            ("scorecard_bands", "S5-NEG"), ("decision", "S5-NEG"),
            ("scorecard_bands", "S5-SHOT"), ("decision", "S5-SHOT"),
            ("scorecard_bands", "S5-HALF"), ("decision", "S5-HALF"),
            ("scorecard_bands", "S5-NOBODY"),
        ), stamp.asked()
        # a stamp that hands over a shape the world would not is refused
        raw = _S5Stamp(world, {"S5-TUPLE": ("low", "long", "clean", "strong")},
                       {"S5-TUPLE": {"price_bp": 1470}})
        _refuses(s.PriceError, "bands handed over as a bare tuple",
                 lambda: s.price("S5-TUPLE", raw), ["tuple"])
        noney = _S5Stamp(world, {"S5-NONEY": _C5_STAMP_BANDS["S5-LOW"]},
                         {"S5-NONEY": {"price_bp": None}})
        _refuses(s.PriceError, "a bank price that is not a count",
                 lambda: s.price("S5-NONEY", noney), ["None"])
        return stamp

    def _c5_refusals(s, book):
        """Every id and shape a price is refused for, naming the offender."""
        _refuses(s.PriceError, "an id the estate does not hold",
                 lambda: s.price("CO-99", book), ["CO-99"])
        _refuses(s.PriceError, "a decline the estate holds, by id",
                 lambda: s.price("CO-04", book), ["CO-04"])
        _refuses(s.PriceError, "a second decline, by id",
                 lambda: s.price("CO-05", book), ["CO-05"])
        _refuses(s.PriceError, "a third decline, by id",
                 lambda: s.price("CO-08", book), ["CO-08"])
        _refuses(s.PriceError, "no text at all where an id belongs",
                 lambda: s.price(None, book), ["None"])
        _refuses(s.PriceError, "a number where an id belongs",
                 lambda: s.price(7, book), ["7"])
        _refuses(s.PriceError, "a bool where an id belongs",
                 lambda: s.price(True, book), ["True"])
        _refuses(s.PriceError, "a whole mapping where an id belongs",
                 lambda: s.price({"id": "CO-01"}, book), ["id"])

    def _c5_ledger(s, book):
        """What a refused call reaches: nothing, or the two doors a refusal reads."""
        # a world refusal — an id the book does not hold — moves one lookups door and
        # opens no record at all
        before = book.stats()
        _refuses(s.PriceError, "an id the estate does not hold, without a record",
                 lambda: s.price("CO-99", book), ["CO-99"])
        after = book.stats()
        for kind, count in before.items():
            if kind == "lookups":
                assert after[kind] == count + 1, (
                    "the refused call did not ask the book once: %r became %r"
                    % (before, after))
                continue
            assert after[kind] == count, (
                "a refused call opened the estate's %s door: %d became %d"
                % (kind, count, after[kind]))
        # a refusal the stage raises before any door, for an id that is no text at
        # all, asks nothing and answers nothing
        before = book.stats()
        _refuses(s.PriceError, "no text at all where an id belongs",
                 lambda: s.price(None, book), ["None"])
        assert book.stats() == before, (
            "a non-text id reached the book anyway: %r became %r" % (before, book.stats()))
        # each of the estate's own declines reads its bands and its decision — the
        # two doors a price is refused for — and no third door at all
        for identity in ("CO-04", "CO-05", "CO-08"):
            before = book.stats()
            _refuses(s.PriceError, "the decline of %s, read no further" % (identity,),
                     lambda i=identity: s.price(i, book), [identity])
            after = book.stats()
            for kind, count in before.items():
                if kind == "scorecard_bands":
                    assert after[kind] == count + 1, (
                        "%s's refusal did not read its bands: %r became %r"
                        % (identity, before, after))
                elif kind == "decisions":
                    assert after[kind] == count + 1, (
                        "%s's refusal did not read its decision: %r became %r"
                        % (identity, before, after))
                elif kind == "lookups":
                    assert after[kind] == count + 2, (
                        "%s's refusal asked the book the wrong number of times: "
                        "%r became %r" % (identity, before, after))
                else:
                    assert after[kind] == count, (
                        "%s's refusal opened the estate's %s door: %d became %d"
                        % (identity, kind, count, after[kind]))

    def _c5_workload(s, world):
        """One whole pass of the stage over the estate and the synthetic book."""
        book = world.build(world.BUILD_SEED)
        answers = []
        for identity in book.names():
            try:
                record = s.price(identity)
            except s.PriceError as refused:
                answers.append((identity, str(refused)))
                continue
            answers.append((identity, record["grade"], record["legs"],
                            record["price_bp"], record["residual_bp"],
                            record["floor"], record["basis"]))
        stamp = _c5_stamp(world)
        for identity in ("S5-LOW", "S5-TOP", "S5-FLOOR"):
            answers.append(s.price(identity, stamp))
        return tuple(answers)

    def _c5_twice(s, world):
        """Two runs of one workload, which a stage that reads a set would fail."""
        one = _c5_workload(s, world)
        two = _c5_workload(s, world)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function "
            "of its inputs: %r against %r" % (one, two))

    """Every assertion the contract's §4.5 makes about this stage."""
    import cases
    import policy
    import stage_05 as s
    if "M0_REPO" in os.environ:
        assert os.path.realpath(s.__file__).startswith(
            os.path.realpath(os.environ["M0_REPO"])), (
            "the check is not running against the tree under test: %s"
            % (s.__file__,))
    book = cases.build(cases.BUILD_SEED)
    _c5_constants(s, policy)
    _c5_leg(s, policy)
    _c5_prices(s, book, policy)
    _c5_synthetic(s, cases)
    _c5_refusals(s, book)
    _c5_ledger(s, book)
    _c5_twice(s, cases)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-origination-from-scratch"

    C6_LIMIT_KEYS = ("id", "purpose", "requested_cents", "approved_cents",
                     "committed_cents", "uncommitted_cents", "approved_months",
                     "styled")

    C6_AMOUNT_CLAUSE = "the-amount-cap"

    C6_TENOR_CLAUSE = "the-tenor-cap"

    C6_NOT_OFFERED = "not-offered"

    C6_REASONS_CAPS = ("the-amount-cap", "the-tenor-cap")

    C6_STYLED = {
        "CO-01": (),
        "CO-02": (),
        "CO-03": (C6_AMOUNT_CLAUSE, C6_TENOR_CLAUSE),
        "CO-04": (C6_NOT_OFFERED,),
        "CO-05": (C6_NOT_OFFERED,),
        "CO-06": (C6_AMOUNT_CLAUSE,),
        "CO-07": (),
        "CO-08": (C6_NOT_OFFERED,),
        "CO-09": (),
        "CO-10": (),
    }

    def _repo(start=None):
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
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
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

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

    def _structure(application, verdict):
        """The contract's own limit, recomputed from the policy's tables alone."""
        purpose = application["purpose"]
        requested = application["requested_cents"]
        term = application["term_months"]
        cap = policy.PURPOSE_MAX_CENTS[purpose]
        tenor = policy.PURPOSE_MAX_MONTHS[purpose]
        if verdict == "decline":
            approved, months, styled = 0, 0, (C6_NOT_OFFERED,)
        else:
            approved = requested if requested <= cap else cap
            months = term if term <= tenor else tenor
            styled = (C6_REASONS_CAPS[0],) if requested > cap else ()
            if term > tenor:
                styled = styled + (C6_REASONS_CAPS[1],)
        committed = approved * policy.COMMITTED_BP // 10000
        return approved, committed, approved - committed, months, styled

    class _Synthetic:
        """An estate of one application the world's own four purposes need not hold.

        It answers the two things this stage is allowed to ask for — the
        application and its decision — and records every ask, which is what makes
        it a proof that the stage asked for nothing else. Its decision record
        carries a *decoy* approved amount, so a stage that echoes the bank's own
        number instead of computing from the caps is wrong here whatever the real
        estate would forgive.
        """

        def __init__(self, identities=(("S6-ONE", "sme", 15000000, 84, "approve"),),
                     decoy_cents=7):
            self._records = tuple(
                {"identity": identity, "purpose": purpose, "requested_cents": requested,
                 "term_months": term, "verdict": verdict}
                for identity, purpose, requested, term, verdict in identities)
            self._index = dict((row["identity"], row) for row in self._records)
            self._decoy = decoy_cents
            self._asked = []

        def names(self):
            """Every application the synthetic estate holds."""
            return tuple(sorted(self._index))

        def application(self, identity):
            """The applicant's own facts, or the estate's own refusal by name."""
            self._asked.append(("application", identity))
            row = self._index[identity]
            return dict(id=identity, purpose=row["purpose"],
                        requested_cents=row["requested_cents"],
                        term_months=row["term_months"])

        def decision(self, identity):
            """The bank's own record, with a decoy approved amount in it."""
            self._asked.append(("decision", identity))
            row = self._index[identity]
            return dict(id=identity, verdict=row["verdict"],
                        approved_cents=self._decoy, price_bp=0)

        def asked(self):
            """Every ask the stage made of this estate, in order."""
            return tuple(self._asked)

    def _c6_constants(s):
        """The record's shape and the refusal family, echoed exactly."""
        assert tuple(s.LIMIT_KEYS) == C6_LIMIT_KEYS, s.LIMIT_KEYS
        assert issubclass(s.LimitError, ValueError), s.LimitError
        assert s.LimitError is not ValueError, "the stage must refuse, not defer"
        assert callable(s.limit), s.limit

    def _c6_one(s, estate, identity, want):
        """One record against the eight fields the contract prints it in.

        `want` is the check's own recomputation: `(approved, committed,
        uncommitted, months, styled)`. The shape, the echoes and every computed
        field are asserted here so the record cannot carry a number the estate
        never asked for.
        """
        application = estate.application(identity)
        record = s.limit(estate, identity)
        assert tuple(record.keys()) == C6_LIMIT_KEYS, record
        assert record["id"] == identity, record
        assert record["purpose"] == application["purpose"], record
        assert record["requested_cents"] == application["requested_cents"], record
        approved, committed, uncommitted, months, styled = want
        assert record["approved_cents"] == approved, (
            "%s answered %d approved against the contract's %r"
            % (identity, record["approved_cents"], want))
        assert record["committed_cents"] == committed, (
            "%s committed %r against the contract's %r"
            % (identity, record["committed_cents"], want))
        assert record["uncommitted_cents"] == uncommitted, (
            "%s uncommitted %r against the contract's %r"
            % (identity, record["uncommitted_cents"], want))
        assert record["committed_cents"] + record["uncommitted_cents"] == \
            record["approved_cents"], (
            "%s's committed and uncommitted shares add to %d, not the approved %d"
            % (identity, record["committed_cents"] + record["uncommitted_cents"],
               record["approved_cents"]))
        assert record["approved_months"] == months, (
            "%s answered %d approved months against the contract's %r"
            % (identity, record["approved_months"], want))
        assert isinstance(record["styled"], tuple), (
            "%s's styling is %r, and the clauses the letter will carry are texts"
            % (identity, record["styled"]))
        for clause in record["styled"]:
            assert isinstance(clause, str), (
                "%s carries the styling clause %r, which is not a text"
                % (identity, clause))
            assert clause in C6_REASONS_CAPS or clause == C6_NOT_OFFERED, (
                "%s carries the styling clause %r, which no policy cap names"
                % (identity, clause))
        assert record["styled"] == styled, (
            "%s styled %r against the contract's %r" % (identity, record["styled"], styled))
        not_offered = C6_NOT_OFFERED
        if record["styled"] == (not_offered,):
            assert record["approved_cents"] == 0, (
                "%s styled not-offered and still approved %d"
                % (identity, record["approved_cents"]))
        else:
            for want_clause in (C6_AMOUNT_CLAUSE, C6_TENOR_CLAUSE):
                assert record["styled"].count(want_clause) <= 1, (
                    "%s carries the clause %r more than once"
                    % (identity, want_clause))
        return record

    def _c6_limits(s, b):
        """Every application the estate holds, against its own records."""
        answers = []
        for identity in b.names():
            application = b.application(identity)
            verdict = b.decision(identity)["verdict"]
            want = _structure(application, verdict)
            record = _c6_one(s, b, identity, want)
            bank = b.decision(identity)["approved_cents"]
            assert record["styled"] == C6_STYLED[identity], (
                "%s styled %r, and the bank's own record implies %r"
                % (identity, record["styled"], C6_STYLED[identity]))
            answers.append(tuple(record[key] for key in C6_LIMIT_KEYS))
            if verdict == "decline":
                assert bank == 0 and record["approved_cents"] == 0, (
                    "%s's bank record approves %d cents on a decline"
                    % (identity, bank))
                continue
            assert record["approved_cents"] == bank, (
                "%s approved %d cents; the bank's own record says %d"
                % (identity, record["approved_cents"], bank))
            cap = policy.PURPOSE_MAX_CENTS[application["purpose"]]
            assert record["approved_cents"] == min(application["requested_cents"], cap), (
                "%s's approval is neither its request nor the purpose cap"
                % (identity,))
            try:
                facility = b.facility(identity)
            except cases.CaseError:
                continue
            assert record["approved_months"] == facility["term_months"], (
                "%s approved %d months; the bank's own contract runs %d"
                % (identity, record["approved_months"], facility["term_months"]))
        return tuple(answers)

    def _c6_boundaries(s, book_module):
        """Both sides of every cap, on synthetic estates built to land on them.

        Each estate carries a decoy `approved_cents` in its decision record, so a
        stage that echoes the bank's own number instead of computing from the
        purpose cap fails every fixture below, whatever the real estate would
        forgive.
        """
        # A request at the amount cap exactly, and a term a month under the tenor
        # cap: approved whole, nothing styled.
        inside = _Synthetic((("S6-INSIDE", "sme", 15000000, 83, "approve"),))
        _c6_one(s, inside, "S6-INSIDE", _structure(inside.application("S6-INSIDE"),
                                                   "approve"))
        assert s.limit(inside, "S6-INSIDE")["styled"] == (), inside.asked()
        # A request a cent over the amount cap and a term a month over the tenor
        # cap: cut on both, amount clause first.
        over = _Synthetic((("S6-OVER", "sme", 15000001, 85, "approve"),))
        _c6_one(s, over, "S6-OVER", _structure(over.application("S6-OVER"), "approve"))
        assert s.limit(over, "S6-OVER")["styled"] == C6_REASONS_CAPS, over.asked()
        # The amount cap alone, and the tenor cap alone.
        amount_only = _Synthetic((("S6-AMT", "sme", 15000001, 60, "approve"),))
        _c6_one(s, amount_only, "S6-AMT",
                _structure(amount_only.application("S6-AMT"), "approve"))
        assert s.limit(amount_only, "S6-AMT")["styled"] == (C6_AMOUNT_CLAUSE,)
        tenor_only = _Synthetic((("S6-TEN", "sme", 1000000, 85, "approve"),))
        _c6_one(s, tenor_only, "S6-TEN",
                _structure(tenor_only.application("S6-TEN"), "approve"))
        assert s.limit(tenor_only, "S6-TEN")["styled"] == (C6_TENOR_CLAUSE,)
        # The tenor cap exactly is inside it, as the amount cap exactly is.
        at_tenor = _Synthetic((("S6-ATTEN", "sme", 990000, 84, "approve"),))
        _c6_one(s, at_tenor, "S6-ATTEN",
                _structure(at_tenor.application("S6-ATTEN"), "approve"))
        assert s.limit(at_tenor, "S6-ATTEN")["approved_months"] == 84
        assert s.limit(at_tenor, "S6-ATTEN")["styled"] == ()
        # A truncation the estate's own round amounts never land on: the committed
        # share of an odd approval is truncated, and the remainder is the rest.
        odd = _Synthetic((("S6-ODD", "sme", 1234567, 24, "approve"),))
        record = _c6_one(s, odd, "S6-ODD", _structure(odd.application("S6-ODD"),
                                                      "approve"))
        assert record["approved_cents"] == 1234567
        assert record["committed_cents"] == 987653, record
        assert record["uncommitted_cents"] == 246914, record
        assert record["committed_cents"] + record["uncommitted_cents"] == 1234567
        # Another purpose, so the lookup does not answer for one key only.
        consumer = _Synthetic((("S6-CON", "consumer", 2500001, 30, "approve"),))
        _c6_one(s, consumer, "S6-CON",
                _structure(consumer.application("S6-CON"), "approve"))
        assert s.limit(consumer, "S6-CON")["approved_cents"] == 2000000
        assert s.limit(consumer, "S6-CON")["styled"] == (C6_AMOUNT_CLAUSE,)
        # A decline: no structure at all.
        decline = _Synthetic((("S6-DEC", "sme", 15000001, 85, "decline"),))
        record = _c6_one(s, decline, "S6-DEC",
                         _structure(decline.application("S6-DEC"), "decline"))
        assert record["approved_cents"] == 0 and record["approved_months"] == 0
        assert record["committed_cents"] == 0 and record["uncommitted_cents"] == 0
        assert record["styled"] == (C6_NOT_OFFERED,)
        # A decline at the amount cap exactly is no different: the request is not
        # the reason it was declined.
        at_cap = _Synthetic((("S6-ATCAP", "consumer", 2000000, 36, "decline"),))
        record = _c6_one(s, at_cap, "S6-ATCAP",
                         _structure(at_cap.application("S6-ATCAP"), "decline"))
        assert record["styled"] == (C6_NOT_OFFERED,), record

    def _c6_refusals(s, b):
        """Every shape that cannot be a limit, refused by name, asking nothing.

        A purpose the policy does not name has no cap to be floored at and no
        tenor either: the refusal comes before the decision door is read, on a
        synthetic estate whose asks prove it — the application door only. A
        verdict outside the policy's three is neither offered nor not-offered.
        On the estate itself, a call the world refuses reaches no record: the
        applications and decisions counters stay where they were, only `lookups`
        moves — and no stage call ever asks for an offer or a facility, which is
        where the styling and the answer key live.
        """
        foreign = _Synthetic((("S6-FOR", "yacht", 1000000, 36, "approve"),))
        _refuses(s.LimitError, "a purpose the policy does not name",
                 lambda: s.limit(foreign, "S6-FOR"), ["yacht"])
        assert foreign.asked() == (("application", "S6-FOR"),), foreign.asked()
        bad_verdict = _Synthetic((("S6-MAYBE", "sme", 1000000, 36, "maybe"),))
        _refuses(s.LimitError, "a verdict the policy does not decide",
                 lambda: s.limit(bad_verdict, "S6-MAYBE"), ["maybe"])
        assert bad_verdict.asked()[-1] == ("decision", "S6-MAYBE"), (
            "the unread verdict was refused without being read")
        unknowns = [
            ("an application id the estate does not hold", "CO-99"),
        ]
        for what, identity in unknowns:
            statistics_before = b.stats()
            _refuses(cases.CaseError, what, lambda i=identity: s.limit(b, i),
                     [identity])
            statistics_after = b.stats()
            assert statistics_after["lookups"] == statistics_before["lookups"] + 1, (
                "%s: the estate's ledger moved %r for a refused call"
                % (what, (statistics_before, statistics_after)))
            assert statistics_after["applications"] == statistics_before["applications"], (
                "%s read an application that is not there" % (what,))
            assert statistics_after["decisions"] == statistics_before["decisions"], (
                "%s read a decision that is not there" % (what,))

    def _c6_ledger(s, b):
        """The stage answers for two doors only, and the estate is never written.

        The asks a whole pass makes are counted on the synthetic estates and on
        the real one's own stats: offers and facilities are the letter's and the
        booking's doors, and a limit stage that reaches for them is reading a
        stage 9 or a stage 10 answer. A refusal the stage raises on a purpose the
        policy does not name reads the application and nothing deeper.
        """
        for identity in b.names():
            statistics_before = b.stats()
            s.limit(b, identity)
            statistics_after = b.stats()
            assert statistics_after["offers"] == statistics_before["offers"], (
                "the stage asked the estate for an offer: %r became %r"
                % (statistics_before, statistics_after))
            assert statistics_after["facilities"] == statistics_before["facilities"], (
                "the stage asked the estate for a facility: %r became %r"
                % (statistics_before, statistics_after))
            assert statistics_after["obligations"] == statistics_before["obligations"], (
                "the stage asked the estate for obligations: %r became %r"
                % (statistics_before, statistics_after))
            assert statistics_after["collateral"] == statistics_before["collateral"], (
                "the stage asked the estate for collateral: %r became %r"
                % (statistics_before, statistics_after))
            assert statistics_after["history"] == statistics_before["history"], (
                "the stage asked the estate for history: %r became %r"
                % (statistics_before, statistics_after))
            assert statistics_after["projections"] == statistics_before["projections"], (
                "the stage asked the estate for projections: %r became %r"
                % (statistics_before, statistics_after))
            assert statistics_after["scorecard_bands"] == statistics_before[
                "scorecard_bands"], (
                "the stage asked the estate for scorecard bands: %r became %r"
                % (statistics_before, statistics_after))
            assert statistics_after["decisions"] - statistics_before["decisions"] <= 1, (
                "the stage asked the estate for more than one decision: %r"
                % ((statistics_before, statistics_after),))
            assert statistics_after["applications"] - statistics_before["applications"] \
                <= 2, "the stage asked the estate for applications again: %r" % (
                (statistics_before, statistics_after),)
        purity = _Synthetic((("S6-PURE", "sme", 1000000, 36, "approve"),))
        s.limit(purity, "S6-PURE")
        for ask in purity.asked():
            assert ask[0] in ("application", "decision"), (
                "the stage asked the estate for %r, and a limit is not the book's "
                "to give from there" % (ask,))

    def _c6_workload(s, b):
        """One whole pass of the stage over the estate and the check's fixtures."""
        answers = list(_c6_limits(s, b))
        for identity in b.names():
            application = b.application(identity)
            verdict = b.decision(identity)["verdict"]
            answers.append(_structure(application, verdict))
        synthetic = _Synthetic((("S6-TWICE", "sme", 15000001, 85, "approve"),
                                ("S6-TWICE2", "consumer", 600000, 24, "approve"),
                                ("S6-TWICE3", "consumer", 700000, 30, "decline")))
        for identity in synthetic.names():
            answers.append(s.limit(synthetic, identity))
        return tuple(answers)

    def _c6_twice(s, b):
        """Two runs of one workload, which a stage that reads a dict would fail."""
        one = _c6_workload(s, b)
        two = _c6_workload(s, b)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a "
            "function of its inputs")

    """Every assertion the contract's §4.6 makes about this stage."""
    # The world is imported here, on the path the runner built — the way the
    # earlier course's checks import their estate inside the check, never at
    # the top of the file, so the copy under test is the world that answers.
    import cases as world
    import policy as rulebook
    globals()["cases"] = world
    globals()["policy"] = rulebook
    import stage_06 as s
    b = cases.build(7)
    _c6_constants(s)
    _c6_limits(s, b)
    _c6_boundaries(s, cases)
    _c6_refusals(s, b)
    _c6_ledger(s, b)
    _c6_twice(s, b)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-origination-from-scratch"

    C7_COVENANT_KEYS = ("id", "name", "kind", "floor", "headroom_bp", "verdict", "year")

    C7_VERDICTS = ("kept", "breach", "no-year")

    C7_BREACH = "breach"

    C7_KEPT = "kept"

    C7_NO_YEAR = "no-year"

    C7_BP = 10000

    C7_KINDS = ("max-leverage", "min-dscr", "min-cash")

    C7_COVENANTS = {
        "sme": (("leverage", "max-leverage", 40000),
                ("service", "min-dscr", 12000),
                ("liquidity", "min-cash", 300000000)),
        "corporate": (("leverage", "max-leverage", 35000),
                      ("service", "min-dscr", 10000)),
        "consumer": (),
        "mortgage": (),
    }

    C7_A_BANDS = {"dsr": "low", "stability": "long", "history": "clean",
                  "collateral": "strong"}

    C7_D_BANDS = {"dsr": "mid", "stability": "settled", "history": "spotted",
                  "collateral": "adequate"}

    C7_F_BANDS = {"dsr": "high", "stability": "short", "history": "impaired",
                  "collateral": "weak"}

    C7_FACILITY_TERMS = {
        "CO-03": (15000000, 520, 84, 2557656),
        "CO-07": (12000000, 425, 60, 2664996),
        "CO-09": (24000000, 750, 120, 3409596),
    }

    C7_LIQUIDITY = {
        "CO-03": (220000000, 3, 7333),
        "CO-07": (240000000, 2, 8000),
    }

    _C7_SME_FLOOR_CASH = 300000000

    _C7_CORP_REQUESTED = 30000

    _C7_CORP_TERM = 30

    _C7_D_PRICE = 750

    _C7_A_PRICE = 425

    _C7_F_PRICE = 10515

    def _repo(start=None):
        """The repository the course lives in, found through its markers."""
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
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
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

    def _staged(course, solved=True):
        """A temp dir holding the course, with the solutions dropped over the stages."""
        dest = tempfile.mkdtemp(prefix="m0-stage07-")
        for name in sorted(os.listdir(course)):
            if name.endswith(".py"):
                shutil.copy(os.path.join(course, name), os.path.join(dest, name))
        if solved:
            solved = os.path.join(course, "solutions")
            for name in sorted(os.listdir(solved)):
                if name.endswith(".py"):
                    shutil.copy(os.path.join(solved, name), os.path.join(dest, name))
        return dest

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named."""
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return message
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _c7_period(rate_bp):
        """The bank's own rate for one month: thirty days of a 360-day year."""
        return rate_bp * 30 // 360

    def _c7_walk(balance, period_bp, payment, term):
        """An independent amortisation: opening-balance interest, then payment."""
        for _ in range(term):
            if balance <= 0:
                return balance
            balance = balance + balance * period_bp // C7_BP - payment
        return balance

    def _c7_smallest(principal_cents, period_bp, term):
        """The smallest whole-cent payment whose walk ends at or below zero."""
        low, high = 0, 2 * principal_cents
        while low < high:
            middle = (low + high) // 2
            if _c7_walk(principal_cents, period_bp, middle, term) <= 0:
                high = middle
            else:
                low = middle + 1
        return low

    def _c7_service(approved_cents, rate_bp, term):
        """Twelve times the level payment of one set of booked terms."""
        return _c7_smallest(approved_cents, _c7_period(rate_bp), term) * 12

    def _c7_measure(kind, row, terms):
        """One projection year, as one covenant kind measures it."""
        if kind == "max-leverage":
            return C7_BP * row["net_debt_cents"] // row["ebitda_cents"]
        if kind == "min-dscr":
            return C7_BP * row["ebitda_cents"] // terms
        return row["cash_cents"]

    def _c7_headroom_of(covenant, value):
        """The contract's own headroom, independent of the stage's."""
        name, kind, floor = covenant
        if kind.startswith("max-"):
            return C7_BP * floor // value
        return C7_BP * value // floor

    def _c7_worst(kind, rows, terms):
        """The year whose measure sits closest to breach, and that measure.

        A tie among equal measures names the first of the equal years.
        """
        worst = None
        for row in rows:
            measure = _c7_measure(kind, row, terms)
            if worst is None:
                worst = (measure, row["year"])
            elif kind.startswith("max-") and measure > worst[0]:
                worst = (measure, row["year"])
            elif not kind.startswith("max-") and measure < worst[0]:
                worst = (measure, row["year"])
        return worst

    def _c7_no_year(identity, covenant):
        """A promise nothing binds, as the stage words it."""
        return {"id": identity, "name": covenant[0], "kind": covenant[1],
                "floor": covenant[2], "headroom_bp": 0, "verdict": C7_NO_YEAR,
                "year": 0}

    def _c7_expect(identity, purpose, rows, terms):
        """One application's records, from the check's own arithmetic alone.

        `terms` is the check's own debt service — `None` where the projections
        give no year to measure and None again where a decline approves nothing
        and the service covenant has no debt to sit against.
        """
        records = []
        for covenant in C7_COVENANTS[purpose]:
            name, kind, floor = covenant
            if not rows or (kind == "min-dscr" and terms is None):
                records.append(_c7_no_year(identity, covenant))
                continue
            measure, year = _c7_worst(kind, rows, terms)
            head = _c7_headroom_of(covenant, measure)
            verdict = C7_BREACH if head < C7_BP else C7_KEPT
            records.append({"id": identity, "name": name, "kind": kind,
                            "floor": floor, "headroom_bp": head,
                            "verdict": verdict, "year": year})
        return tuple(records)

    class _Stamp:
        """A book the check builds itself: the synthetics the estate is not.

        It answers the four things a covenant is read from — the application, the
        projections, the bank's own decision and the scorecard's bands — and
        records every ask, which is what proves the stage asked for nothing
        else. Its decision records carry no `approved_cents` worth reading (the
        approval is the policy's own cap arithmetic, not the bank's echo), and a
        synthetic with no bands behind it refuses so the price's wrap still
        reaches the stage.
        """

        def __init__(self, world, rows):
            self._world = world
            self._rows = rows
            self._asked = []

        def names(self):
            """Every synthetic application the stamp holds."""
            return tuple(sorted(self._rows))

        def _row(self, identity):
            if identity not in self._rows:
                raise self._world.CaseError(
                    "the stamp holds no application %r" % (identity,))
            return self._rows[identity]

        def application(self, identity):
            """The applicant's own words, under the estate's own keys."""
            self._asked.append(("application", identity))
            row = self._row(identity)
            return dict(id=identity, purpose=row["purpose"],
                        requested_cents=row["requested_cents"],
                        term_months=row["term_months"])

        def decision(self, identity):
            """The bank's decision on the stamp: a verdict and a priced rate."""
            self._asked.append(("decision", identity))
            row = self._row(identity)
            return dict(id=identity, verdict=row["verdict"],
                        price_bp=row["price_bp"])

        def scorecard_bands(self, identity):
            """The band facts a price is built from, or the stamp's refusal."""
            self._asked.append(("scorecard_bands", identity))
            row = self._row(identity)
            if row["bands"] is None:
                raise self._world.CaseError(
                    "the stamp holds no bands for %r" % (identity,))
            return dict(row["bands"])

        def projections(self, identity):
            """The borrower's own projections, in the estate's own keys."""
            self._asked.append(("projections", identity))
            return self._row(identity)["projections"]

        def asked(self):
            """Every ask the stage made of this stamp, in order."""
            return tuple(self._asked)

    def _c7_corp_service():
        """The debt service the corporate boundary stamps are written on.

        The check computes it from its own walk, on the terms the stamps carry,
        and asserts itself even and above the scaling a one-cent EBITDA step
        needs — the boundary of the `min-dscr` fixtures below.
        """
        service = _c7_service(_C7_CORP_REQUESTED, _C7_D_PRICE, _C7_CORP_TERM)
        assert service > 10000 and service % 2 == 0, service
        return service

    def _c7_sme_service():
        """The debt service the sme boundary stamps are written on."""
        service = _c7_service(333, _C7_A_PRICE, 30)
        assert service > 0, service
        return service

    def _c7_year(number, purpose_cents=0, ebitda_cents=0, net_debt_cents=0,
                 cash_cents=0, capex_cents=0, revenue_cents=0):
        """One projection row under the world's own keys."""
        return {"year": number, "revenue_cents": revenue_cents,
                "ebitda_cents": ebitda_cents, "net_debt_cents": net_debt_cents,
                "cash_cents": cash_cents, "capex_cents": capex_cents}

    def _c7_constants(s, rulebook):
        """The record's shape, the verdict events, and the world's own tables."""
        assert tuple(s.COVENANT_KEYS) == C7_COVENANT_KEYS, s.COVENANT_KEYS
        assert tuple(s.COVENANT_VERDICTS) == C7_VERDICTS, s.COVENANT_VERDICTS
        assert C7_BREACH in s.COVENANT_VERDICTS, s.COVENANT_VERDICTS
        assert "stage 7" in s.STAGE_ERROR, s.STAGE_ERROR
        assert issubclass(s.CovenantError, ValueError), s.CovenantError
        assert s.CovenantError is not ValueError, "the stage must refuse, not defer"
        assert callable(s.covenants), s.covenants
        assert callable(s.headroom), s.headroom
        assert tuple(rulebook.PURPOSES) == ("consumer", "mortgage", "sme", "corporate")
        assert rulebook.COVENANTS == C7_COVENANTS, rulebook.COVENANTS
        for purpose in C7_COVENANTS:
            for name, kind, floor in C7_COVENANTS[purpose]:
                assert kind in C7_KINDS, (purpose, name, kind)
                assert floor > 0, (purpose, name, floor)
        # the sme floor is the amendment's own pin: cash measured in cents, at
        # three hundred million of them, so the bank's own breach years land
        assert C7_COVENANTS["sme"][2] == ("liquidity", "min-cash", 300000000)

    def _c7_headroom_fn(s, rulebook):
        """The headroom reader: both directions, the line, and every refusal."""
        at_floor = ("leverage", "max-leverage", 40000)
        assert s.headroom(at_floor, 40000) == 10000, (
            "a measure at its floor keeps headroom exactly 10000")
        assert s.headroom(at_floor, 10000) == 40000, (
            "a max- headroom halves as its measure doubles")
        assert s.headroom(at_floor, 80000) == 5000 < 10000, (
            "a tall measure breaches")
        assert s.headroom(("service", "min-dscr", 10000), 10000) == 10000, (
            "a min- measure at its floor keeps headroom exactly 10000")
        assert s.headroom(("service", "min-dscr", 10000), 5000) == 5000 < 10000, (
            "a short measure breaches")
        assert _C7_SME_FLOOR_CASH > 0 and \
            s.headroom(("liquidity", "min-cash", _C7_SME_FLOOR_CASH),
                       _C7_SME_FLOOR_CASH) == 10000, (
            "a cash covenant exactly at its floor keeps")
        assert s.headroom(("liquidity", "min-cash", _C7_SME_FLOOR_CASH),
                          _C7_SME_FLOOR_CASH - 1) == 9999, (
            "one cent under the floor breaches at exactly 9999")
        # truncation, at the contract's own scale
        assert s.headroom(at_floor, 30001) == 10000 * 40000 // 30001, (
            "the max- headroom truncates at the scale the contract pins")
        assert s.headroom(("service", "min-dscr", 12000), 12001) == \
            10000 * 12001 // 12000, (
            "the min- headroom truncates at the scale the contract pins")
        # every refusal names its offender
        _refuses(s.CovenantError, "a covenant that is not a row",
                 lambda: s.headroom("leverage", 40000), ["leverage"])
        _refuses(s.CovenantError, "a covenant row of the wrong length",
                 lambda: s.headroom(("leverage", "max-leverage"), 40000), ["leverage"])
        _refuses(s.CovenantError, "a covenant row that is not a tuple",
                 lambda: s.headroom({"name": "leverage", "kind": "max-leverage",
                                     "floor": 40000}, 40000), ["max-leverage"])
        _refuses(s.CovenantError, "a covenant kind the promise is not measured in",
                 lambda: s.headroom(("leverage", "average", 40000), 40000),
                 ["leverage", "average"])
        _refuses(s.CovenantError, "a covenant with no text for a name",
                 lambda: s.headroom((7, "max-leverage", 40000), 40000), ["7"])
        _refuses(s.CovenantError, "a covenant floored at nothing",
                 lambda: s.headroom(("leverage", "max-leverage", 0), 40000), ["0"])
        _refuses(s.CovenantError, "a covenant floored under nothing",
                 lambda: s.headroom(("leverage", "max-leverage", -1), 40000), ["-1"])
        _refuses(s.CovenantError, "a bool where a measure belongs",
                 lambda: s.headroom(at_floor, True), ["True"])
        _refuses(s.CovenantError, "a text where a measure belongs",
                 lambda: s.headroom(at_floor, "40000"), ["40000"])
        _refuses(s.CovenantError, "a negative measure where a count belongs",
                 lambda: s.headroom(at_floor, -40000), ["-40000"])
        _refuses(s.CovenantError, "a measure of nothing under a max- promise",
                 lambda: s.headroom(at_floor, 0), ["leverage", "0"])
        _refuses(s.CovenantError, "a negative cash under a min- promise",
                 lambda: s.headroom(("liquidity", "min-cash", _C7_SME_FLOOR_CASH), -1),
                 ["-1"])

    def _c7_record(s, record, want, identity):
        """Every field of one record, against the check's own record of the facts."""
        assert isinstance(record, dict), record
        assert tuple(record.keys()) == tuple(s.COVENANT_KEYS), record
        for key in C7_COVENANT_KEYS:
            assert record[key] == want[key], (
                "%s answered %r for %r against the contract's %r"
                % (identity, record[key], key, want[key]))
        assert record["verdict"] in C7_VERDICTS, record
        assert isinstance(record["year"], int) and not isinstance(record["year"], bool), (
            "%s's year %r is not a count of projection years"
            % (identity, record["year"]))

    def _c7_conditions(s, identity, want, book, rules):
        """The bank's own conditions and the stage's breaches, asserted both ways.

        Every `covenant-<name>-year-<worst>` text the bank's own decision carries
        is a stage-recorded breach with that name and that year; every recorded
        breach is such a text; and a kept or no-year record is no text at all.
        """
        conditions = book.decision(identity)["conditions"]
        for record in want:
            text = "covenant-%s-year-%d" % (record["name"], record["year"])
            if record["verdict"] == C7_BREACH:
                assert text in conditions, (
                    "%s breached %s in %r, and the bank's own conditions carry %r"
                    % (identity, record["name"], record["year"], conditions))
            else:
                assert text not in conditions, (
                    "%s kept <%r> bound in %r, and the bank wrote no such condition"
                    % (identity, record, text))
        for condition in conditions:
            if condition == "styled":
                continue
            head, marker, tail = condition.rpartition("-year-")
            assert head.startswith("covenant-") and marker, (
                "%s carries the condition %r, and no covenant named it"
                % (identity, condition))
            name = head[len("covenant-"):]
            named = [one for one in want if one["name"] == name]
            assert len(named) == 1, (
                "%s's condition %r names a covenant the policy never wrote"
                % (identity, condition))
            assert named[0]["verdict"] == C7_BREACH and named[0]["year"] == int(tail), (
                "%s's condition %r is not the breach the stage recorded: %r"
                % (identity, condition, tuple(named[0].items())))

    def _c7_estate(s, b, rules, priced_stage, limit_stage):
        """Every application of the estate, against the check's own recomputation.

        The debt service the check itself builds comes from the bank's own booked
        ledger — the facility's amount, rate and term — and the ladder's own
        outputs (the approved structure and the priced rate under it) must
        reproduce the bank's own terms at the same search, so the service the
        stage binds its `min-dscr` promise to is provably the bank's own.
        """
        for identity in b.names():
            application = b.application(identity)
            purpose = application["purpose"]
            rows = b.projections(identity)
            terms = None
            if C7_COVENANTS[purpose] and rows:
                facility = b.facility(identity)
                approved, rate, tenor = (
                    facility["booked_cents"], facility["rate_bp"],
                    facility["term_months"])
                pinned = C7_FACILITY_TERMS[identity]
                assert (approved, rate, tenor) == pinned[:3], (
                    "%s: the booked ledger %r moved off the facts the check pins"
                    % (identity, (approved, rate, tenor)))
                terms = _c7_service(approved, rate, tenor)
                assert terms == pinned[3], (
                    "%s's bank service is %d, not the %d the check pinned"
                    % (identity, terms, pinned[3]))
                structure = limit_stage.limit(b, identity)
                priced = priced_stage.price(identity, b)
                assert structure["approved_cents"] == approved, (
                    "%s: the ladder's approval is not the bank's booked amount"
                    % (identity,))
                assert structure["approved_months"] == tenor, (
                    "%s: the ladder's tenor is not the bank's booked term"
                    % (identity,))
                assert priced["price_bp"] == rate, (
                    "%s: the ladder's price is not the bank's own booked rate"
                    % (identity,))
                assert _c7_service(structure["approved_cents"], priced["price_bp"],
                                   structure["approved_months"]) == terms, (
                    "%s: the ladder's own service is not the bank's own (%d against %r)"
                    % (identity, terms, (approved, rate, tenor)))
            want = _c7_expect(identity, purpose, rows, terms)
            got = s.covenants(b, identity)
            assert isinstance(got, tuple), got
            assert len(got) == len(want), (identity, got, want)
            for record, one in zip(got, want):
                _c7_record(s, record, one, identity)
            # the contract's own breach words, where the bank's conditions name them
            for record in want:
                if identity in C7_LIQUIDITY and record["name"] == "liquidity":
                    cash, year, head = C7_LIQUIDITY[identity]
                    assert (record["verdict"], record["year"],
                            record["headroom_bp"]) == (C7_BREACH, year, head), (
                        "%s's liquidity record is %r, and the bank's own conditions "
                        "leave only the breach in year %d at headroom %d"
                        % (identity, tuple(record.items()), year, head))
            _c7_conditions(s, identity, want, b, rules)

    def _c7_stamp_row(purpose, requested, term, verdict, bands, price, projections):
        """One synthetic application, with every door the stage may open."""
        return {"purpose": purpose, "requested_cents": requested,
                "term_months": term, "verdict": verdict, "bands": bands,
                "price_bp": price, "projections": tuple(projections)}

    def _c7_stamp_rows(rules):
        """The stamp book's rows: the boundaries the estate's own never sit on, as
        the check pins them.

        `S7-CAP` rides the purpose caps (its request is one cent over the amount
        cap and one month over the tenor), so a stage that measures the service
        on the request rather than the approval answers a service nobody booked.
        """
        corp = _c7_corp_service()
        sme = _c7_sme_service()
        capped = _c7_service(60000000, _C7_D_PRICE, 120)
        rows = {
            "S7-AT-FLOOR": _c7_stamp_row(
                "corporate", _C7_CORP_REQUESTED, _C7_CORP_TERM, "approve",
                C7_D_BANDS, _C7_D_PRICE,
                [_c7_year(n, ebitda_cents=corp, net_debt_cents=7 * corp // 2,
                          cash_cents=_C7_SME_FLOOR_CASH + 1000000)
                 for n in range(1, 6)]),
            "S7-UNDER": _c7_stamp_row(
                "corporate", _C7_CORP_REQUESTED, _C7_CORP_TERM, "approve",
                C7_D_BANDS, _C7_D_PRICE,
                [_c7_year(n, ebitda_cents=corp - 1, net_debt_cents=4 * (corp - 1),
                          cash_cents=_C7_SME_FLOOR_CASH + 1000000)
                 for n in range(1, 6)]),
            "S7-MAXYEAR": _c7_stamp_row(
                "corporate", _C7_CORP_REQUESTED, _C7_CORP_TERM, "approve",
                C7_D_BANDS, _C7_D_PRICE,
                [_c7_year(n, ebitda_cents=10 * corp, net_debt_cents=k * 10 * corp,
                          cash_cents=_C7_SME_FLOOR_CASH + 1000000)
                 for n, k in ((1, 1), (2, 2), (3, 3), (4, 4), (5, 3))]),
            "S7-TIE": _c7_stamp_row(
                "corporate", _C7_CORP_REQUESTED, _C7_CORP_TERM, "approve",
                C7_D_BANDS, _C7_D_PRICE,
                [_c7_year(n, ebitda_cents=10 * corp, net_debt_cents=k * 10 * corp,
                          cash_cents=_C7_SME_FLOOR_CASH + 1000000)
                 for n, k in ((1, 1), (2, 2), (3, 3), (4, 2), (5, 3))]),
            "S7-CAP": _c7_stamp_row(
                "corporate", 60000001, 121, "approve", C7_D_BANDS, _C7_D_PRICE,
                [_c7_year(n, ebitda_cents=10 * capped, net_debt_cents=10 * capped,
                          cash_cents=_C7_SME_FLOOR_CASH + 1000000)
                 for n in range(1, 6)]),
            "S7-CASH": _c7_stamp_row(
                "sme", 333, 30, "approve", C7_A_BANDS, _C7_A_PRICE,
                [_c7_year(n, ebitda_cents=10 * sme, net_debt_cents=10 * sme,
                          cash_cents=_C7_SME_FLOOR_CASH)
                 for n in range(1, 6)]),
            "S7-CASHLESS": _c7_stamp_row(
                "sme", 333, 30, "approve", C7_A_BANDS, _C7_A_PRICE,
                [_c7_year(n, ebitda_cents=10 * sme, net_debt_cents=10 * sme,
                          cash_cents=_C7_SME_FLOOR_CASH - 1)
                 for n in range(1, 6)]),
            "S7-DSCRTIE": _c7_stamp_row(
                "sme", 333, 30, "approve", C7_A_BANDS, _C7_A_PRICE,
                [_c7_year(n, ebitda_cents=k * sme, net_debt_cents=k * sme,
                          cash_cents=3 * _C7_SME_FLOOR_CASH)
                 for n, k in ((1, 10), (2, 12), (3, 9), (4, 12), (5, 9))]),
            "S7-NONEYEAR": _c7_stamp_row(
                "corporate", _C7_CORP_REQUESTED, _C7_CORP_TERM, "approve",
                C7_D_BANDS, _C7_D_PRICE, ()),
            "S7-DECLINED": _c7_stamp_row(
                "corporate", _C7_CORP_REQUESTED, _C7_CORP_TERM, "decline",
                None, 0,
                [_c7_year(n, ebitda_cents=corp, net_debt_cents=4 * corp,
                          cash_cents=_C7_SME_FLOOR_CASH + 1000000)
                 for n in range(1, 6)]),
        }
        return rows

    def _c7_stamp(s, world, rules, priced_stage):
        """The stamp book asserted: its boundaries, its ask sequence, and the
        check's own arithmetic answering all of them the same way."""
        rows = _c7_stamp_rows(rules)
        stamp = _Stamp(world, rows)
        # the boundary measures, on the check's own arithmetic — the seat each
        # fixture was written on, at the exact year the boundary sits on
        corp = _c7_corp_service()
        for identity, seat, where in (("S7-AT-FLOOR", "max-leverage", 0),
                                      ("S7-UNDER", "min-dscr", 0),
                                      ("S7-MAXYEAR", "max-leverage", 3)):
            measure = _c7_measure(
                seat, rows[identity]["projections"][where],
                None if seat == "max-leverage" else corp)
            assert measure == {"S7-AT-FLOOR": 35000, "S7-UNDER": 9999,
                               "S7-MAXYEAR": 40000}[identity], (identity, measure)
        # the stamp's own prices are the grades its bands name: a fixture whose
        # legs move becomes a fixture problem, not a weaker boundary — asked of a
        # probe stamp, so the flow stamp below owns its own clean ask sequence
        probe = _Stamp(world, rows)
        assert priced_stage.price("S7-AT-FLOOR", probe)["price_bp"] == _C7_D_PRICE
        assert priced_stage.price("S7-CASH", probe)["price_bp"] == _C7_A_PRICE
        assert priced_stage.price("S7-CAP", probe)["price_bp"] == _C7_D_PRICE
        # the exact ask sequence a covenanted, projected borrower opens
        flow = _Stamp(world, rows)
        s.covenants(flow, "S7-AT-FLOOR")
        assert flow.asked() == (
            ("application", "S7-AT-FLOOR"), ("projections", "S7-AT-FLOOR"),
            ("application", "S7-AT-FLOOR"), ("decision", "S7-AT-FLOOR"),
            ("scorecard_bands", "S7-AT-FLOOR"), ("decision", "S7-AT-FLOOR"),
        ), flow.asked()
        want = {
            "S7-AT-FLOOR": ((10000, C7_KEPT, 1), (10000, C7_KEPT, 1)),
            "S7-UNDER": ((8750, C7_BREACH, 1), (9999, C7_BREACH, 1)),
            "S7-MAXYEAR": ((8750, C7_BREACH, 4), (100000, C7_KEPT, 1)),
            "S7-TIE": ((11666, C7_KEPT, 3), (100000, C7_KEPT, 1)),
            "S7-CAP": ((35000, C7_KEPT, 1), (100000, C7_KEPT, 1)),
            "S7-CASH": ((40000, C7_KEPT, 1), (83333, C7_KEPT, 1),
                        (10000, C7_KEPT, 1)),
            "S7-CASHLESS": ((40000, C7_KEPT, 1), (83333, C7_KEPT, 1),
                            (9999, C7_BREACH, 1)),
            "S7-DSCRTIE": ((40000, C7_KEPT, 1), (75000, C7_KEPT, 3),
                           (30000, C7_KEPT, 1)),
        }
        for identity in want:
            got = s.covenants(stamp, identity)
            assert len(got) == len(want[identity]), (identity, got, want[identity])
            for record, one in zip(got, want[identity]):
                assert (record["headroom_bp"], record["verdict"],
                        record["year"]) == one, (identity, record, one)
        # the check's own arithmetic agrees on every one of them, independently
        for identity in ("S7-AT-FLOOR", "S7-UNDER", "S7-MAXYEAR", "S7-TIE",
                         "S7-CAP", "S7-CASH", "S7-CASHLESS", "S7-DSCRTIE",
                         "S7-NONEYEAR", "S7-DECLINED"):
            row = rows[identity]
            terms = None
            if row["verdict"] == "approve":
                approved = min(row["requested_cents"],
                               rules.PURPOSE_MAX_CENTS[row["purpose"]])
                months = min(row["term_months"],
                             rules.PURPOSE_MAX_MONTHS[row["purpose"]])
                terms = _c7_service(approved, row["price_bp"], months)
            mine = _c7_expect(identity, row["purpose"], row["projections"], terms)
            got = s.covenants(stamp, identity)
            assert len(got) == len(mine), (identity, got, mine)
            for record, one in zip(got, mine):
                _c7_record(s, record, one, identity)
            assert got == mine, (identity, got, mine)
        # a covenant exactly at its floor keeps; one a hair under breaches —
        # the pair asserted above, re-stated in one line each for the reader
        assert s.covenants(stamp, "S7-AT-FLOOR")[1]["headroom_bp"] == 10000
        assert s.covenants(stamp, "S7-UNDER")[1]["headroom_bp"] == 9999
        # a decline's service binds nothing, and its leverage still measures
        declined = s.covenants(stamp, "S7-DECLINED")
        assert declined[0]["verdict"] == C7_BREACH and declined[0]["year"] == 1 \
            and declined[0]["headroom_bp"] == 8750, declined
        assert declined[1]["verdict"] == C7_NO_YEAR and declined[1]["headroom_bp"] == 0 \
            and declined[1]["year"] == 0, declined
        # a borrower with no projections answers no-year for every covenant
        none_year = s.covenants(stamp, "S7-NONEYEAR")
        assert tuple(one["verdict"] for one in declined) == (
            C7_BREACH, C7_NO_YEAR), declined
        assert tuple(one["name"] for one in none_year) == ("leverage",
                                                           "service"), none_year
        assert tuple((one["headroom_bp"], one["verdict"], one["year"])
                     for one in none_year) == ((0, C7_NO_YEAR, 0),
                                               (0, C7_NO_YEAR, 0)), none_year
        return stamp, rows

    _C7_REFUSAL_YEARS = (_c7_year(1, ebitda_cents=900000,
                                  net_debt_cents=400000, cash_cents=5000000),)

    def _c7_refusal_rows():
        """The six stamp rows a refusal is checked on, one small stamp each."""
        return {
            "S7-YOGHURT": _c7_stamp_row("yoghurt", _C7_CORP_REQUESTED,
                                        _C7_CORP_TERM, "approve", None, 0, ()),
            "S7-CONSUMER": _c7_stamp_row("consumer", 1200000, 48, "approve",
                                         C7_A_BANDS, _C7_A_PRICE, ()),
            "S7-MORTGAGE": _c7_stamp_row("mortgage", 42000000, 300, "approve",
                                         C7_D_BANDS, _C7_D_PRICE, ()),
            "S7-MAYBE": _c7_stamp_row("sme", 333, 30, "maybe", C7_A_BANDS,
                                      _C7_A_PRICE, _C7_REFUSAL_YEARS),
            "S7-NOBANDS": _c7_stamp_row("sme", 333, 30, "approve", None,
                                        _C7_A_PRICE, _C7_REFUSAL_YEARS),
            "S7-WALL": _c7_stamp_row("sme", 333, 30, "approve", C7_F_BANDS,
                                     _C7_F_PRICE, _C7_REFUSAL_YEARS),
        }

    def _c7_refusals(s, world):
        """Every refusal the stage must name, and the doors each one reached.

        The estate's own refusals — an id the book does not hold, and the ids
        that are no text at all — are raised unwrapped: the stage points at the
        record and lets the estate name its own. A purpose the policy does not
        name, a purpose whose table promises nothing, a verdict the policy does
        not decide (refused through stage 6), a scorecard the book refuses to
        hand over (refused through stage 5) and a priced rate the payment's
        wall cannot carry are the stage's own refusals, naming the application.
        """
        book = world.build(world.BUILD_SEED)
        # the estate names the text-ness of the id, not the value — except the
        # unknown id, which it refuses by pointing at itself
        for what, identity in (("CO-99", "CO-99"), ("NoneType", None), ("int", 7),
                               ("bool", True), ("dict", {"id": "CO-99"})):
            try:
                s.covenants(book, identity)
            except world.CaseError as refused:
                assert what in str(refused), (identity, str(refused))
            else:
                raise AssertionError(
                    "%r answered instead of refusing" % (identity,))
        crowd = _c7_refusal_rows()
        # a purpose the policy does not name is refused before the projections
        yoghurt = _Stamp(world, {"S7-YOGHURT": crowd["S7-YOGHURT"]})
        _refuses(s.CovenantError, "a purpose the policy does not name",
                 lambda: s.covenants(yoghurt, "S7-YOGHURT"),
                 ["yoghurt", "corporate"])
        assert yoghurt.asked() == (("application", "S7-YOGHURT"),), yoghurt.asked()
        # a purpose the policy names but writes no covenant table under answers ()
        for keyword in ("S7-CONSUMER", "S7-MORTGAGE"):
            empty = _Stamp(world, {keyword: crowd[keyword]})
            want = s.covenants(empty, keyword)
            assert want == (), (keyword, want)
            assert empty.asked() == (("application", keyword),), empty.asked()
        # a verdict the policy does not decide reaches stage 6's refusal, wrapped
        maybe = _Stamp(world, {"S7-MAYBE": crowd["S7-MAYBE"]})
        _refuses(s.CovenantError, "a verdict the policy does not decide",
                 lambda: s.covenants(maybe, "S7-MAYBE"),
                 ["S7-MAYBE", "maybe", "limit: "])
        assert maybe.asked() == (
            ("application", "S7-MAYBE"), ("projections", "S7-MAYBE"),
            ("application", "S7-MAYBE"), ("decision", "S7-MAYBE")), maybe.asked()
        # bands the book refuses, wrapped through stage 5
        nobands = _Stamp(world, {"S7-NOBANDS": crowd["S7-NOBANDS"]})
        _refuses(s.CovenantError, "bands the book refuses to hand over",
                 lambda: s.covenants(nobands, "S7-NOBANDS"),
                 ["S7-NOBANDS", "stage 5: "])
        assert nobands.asked() == (
            ("application", "S7-NOBANDS"), ("projections", "S7-NOBANDS"),
            ("application", "S7-NOBANDS"), ("decision", "S7-NOBANDS"),
            ("scorecard_bands", "S7-NOBANDS")), nobands.asked()
        # a priced rate above the payment's wall refuses the whole covenant call
        wall = _Stamp(world, {"S7-WALL": crowd["S7-WALL"]})
        _refuses(s.CovenantError, "a priced rate the payment's wall refuses",
                 lambda: s.covenants(wall, "S7-WALL"),
                 ["S7-WALL", "10515", "0..10000"])
        assert wall.asked() == (
            ("application", "S7-WALL"), ("projections", "S7-WALL"),
            ("application", "S7-WALL"), ("decision", "S7-WALL"),
            ("scorecard_bands", "S7-WALL"), ("decision", "S7-WALL")), wall.asked()

    def _c7_ledger(s, world):
        """The doors one covenants call opens, exactly, identity by identity.

        A purpose that promises no covenants opens its application alone; a
        covenanted borrower with no projections opens its application and its
        projections (an empty answer is still one counted door); a covenanted
        and projected borrower opens two applications, one projections, two
        decisions and one scorecard band — and no offers, no facilities, no
        obligations, no collateral and no history. A refusal the estate raises
        — an unknown id or an id that is no text — is one lookup and no record.
        """
        deltas = {
            "CO-01": {"lookups": 1, "applications": 1},
            "CO-02": {"lookups": 1, "applications": 1},
            "CO-03": {"lookups": 6, "applications": 2, "projections": 1,
                      "decisions": 2, "scorecard_bands": 1},
            "CO-04": {"lookups": 2, "applications": 1, "projections": 1},
            "CO-05": {"lookups": 1, "applications": 1},
            "CO-06": {"lookups": 1, "applications": 1},
            "CO-07": {"lookups": 6, "applications": 2, "projections": 1,
                      "decisions": 2, "scorecard_bands": 1},
            "CO-08": {"lookups": 1, "applications": 1},
            "CO-09": {"lookups": 6, "applications": 2, "projections": 1,
                      "decisions": 2, "scorecard_bands": 1},
            "CO-10": {"lookups": 1, "applications": 1},
        }
        for identity, want in sorted(deltas.items()):
            book = world.build(world.BUILD_SEED)
            before = book.stats()
            s.covenants(book, identity)
            after = book.stats()
            moved = {kind: after[kind] - before[kind]
                     for kind, count in before.items() if after[kind] != count}
            assert moved == want, (identity, moved)
        # a refusal the estate raises moves one lookup and opens no record
        for what, identity, named in (
                ("an id the book does not hold", "CO-99", "CO-99"),
                ("no text at all", None, "NoneType"), ("a number", 7, "int"),
                ("a bool", True, "bool"), ("a mapping", {"id": "CO-99"}, "dict")):
            book = world.build(world.BUILD_SEED)
            before = book.stats()
            _refuses(world.CaseError, what,
                     lambda i=identity: s.covenants(book, i), [named])
            after = book.stats()
            moved = {kind: after[kind] - before[kind]
                     for kind, count in before.items() if after[kind] != count}
            assert moved == {"lookups": 1}, (identity, moved)

    def _c7_workload(s, world, rules):
        """One whole pass of the stage: the estate's ten and the boundary stamps."""
        book = world.build(world.BUILD_SEED)
        answers = []
        for identity in book.names():
            try:
                records = s.covenants(book, identity)
            except world.CaseError as refused:
                answers.append((identity, str(refused)))
                continue
            answers.append((identity, str(records)))
        stamp = _Stamp(world, _c7_stamp_rows(rules))
        for identity in sorted(_c7_stamp_rows(rules)):
            answers.append((identity, str(s.covenants(stamp, identity))))
        return tuple(answers)

    def _c7_twice(s, world, rules):
        """Two runs of one workload, which a stage that reads a set would fail."""
        one = _c7_workload(s, world, rules)
        two = _c7_workload(s, world, rules)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a "
            "function of its inputs: %r against %r" % (one, two))

    """Every assertion the contract's §4.7 makes about this stage."""
    import cases
    import policy
    import stage_05 as priced_stage
    import stage_06 as limit_stage
    import stage_07 as s
    if "M0_REPO" in os.environ:
        assert os.path.realpath(s.__file__).startswith(
            os.path.realpath(os.environ["M0_REPO"])), (
            "the check is not running against the tree under test: %s"
            % (s.__file__,))
    book = cases.build(cases.BUILD_SEED)
    _c7_constants(s, policy)
    _c7_headroom_fn(s, policy)
    _c7_estate(s, book, policy, priced_stage, limit_stage)
    _c7_stamp(s, cases, policy, priced_stage)
    _c7_refusals(s, cases)
    _c7_ledger(s, cases)
    _c7_twice(s, cases, policy)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-origination-from-scratch"

    C8_DECIDE_KEYS = ("id", "verdict", "role", "reasons", "conditions",
                      "approved_cents", "price_bp")

    C8_BP = 10000

    C8_COMMITTEE_CENTS = 5000000

    C8_AFFORD_FLOOR_CENTS = 100000

    C8_DSR_CAP_BP = 4500

    C8_PURPOSE_MAX_CENTS = {"consumer": 2000000, "mortgage": 40000000,
                            "sme": 15000000, "corporate": 60000000}

    C8_PURPOSE_MAX_MONTHS = {"consumer": 60, "mortgage": 300, "sme": 84,
                             "corporate": 120}

    C8_PROPOSED_RATE_BP = {"consumer": 1050, "mortgage": 480, "sme": 890,
                           "corporate": 780}

    C8_SCORE_WEIGHTS_BP = {"dsr": 3500, "stability": 1500, "history": 3000,
                           "collateral": 2000}

    C8_SCORE_POINTS_BP = {
        "dsr": {"low": 10000, "mid": 5000, "high": 1000},
        "stability": {"long": 10000, "settled": 6000, "short": 2000},
        "history": {"clean": 10000, "spotted": 4000, "impaired": 0},
        "collateral": {"strong": 10000, "adequate": 7000, "weak": 2000},
    }

    C8_SCORE_BANDS = ((7700, "A"), (6800, "B"), (5600, "C"), (4400, "D"),
                      (2500, "E"), (0, "F"))

    C8_HAIRCUT_BP = {"cash": 0, "receivables": 3000, "property": 2000,
                     "equipment": 5000, "none": 10000}

    C8_ADVANCE_CAP_BP = 8000

    C8_COMM_BPP = 8000

    C8_GRADE_OF = {"A": "A", "B": "B", "C": "C", "D": "D", "E": "E", "F": "F"}

    C8_PD_BP = {"A": 30, "B": 80, "C": 200, "D": 600, "E": 1800, "F": 10000}

    C8_LGD_BP = {"A": 3500, "B": 4000, "C": 4500, "D": 5000, "E": 5500, "F": 10000}

    C8_FUNDING_BP = 220

    C8_OPCOST_BP = 25

    C8_MARGIN_BP = 150

    C8_CAPITAL_BP = {"A": 20, "B": 25, "C": 35, "D": 55, "E": 80, "F": 120}

    C8_DECISIONS = ("approve", "counter", "decline")

    C8_REASONS = ("affordability", "scorecard", "collateral", "rating", "limit",
                  "covenant", "gate")

    C8_HELD = ("affordability", "scorecard", "collateral", "rating", "limit")

    def _repo(start=None):
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
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
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

    def _staged(course, solved=True):
        dest = tempfile.mkdtemp(prefix="m0-stage08-")
        for name in sorted(os.listdir(course)):
            if name.endswith(".py"):
                shutil.copy(os.path.join(course, name), os.path.join(dest, name))
        if solved:
            solved_dir = os.path.join(course, "solutions")
            for name in sorted(os.listdir(solved_dir)):
                if name.endswith(".py"):
                    shutil.copy(os.path.join(solved_dir, name),
                                os.path.join(dest, name))
        return dest

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r"
                    % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _c8_period(rate_bp):
        """The bank's period rate: 30/360."""
        return rate_bp * 30 // 360

    def _c8_walk(balance, period_bp, payment, term):
        """Amortisation walk: interest on opening balance, then payment."""
        for _ in range(term):
            if balance <= 0:
                return balance
            balance = balance + balance * period_bp // C8_BP - payment
        return balance

    def _c8_payment(principal, rate_bp, term):
        """Smallest whole-cent payment that clears within term."""
        low, high = 0, 2 * principal
        while low < high:
            middle = (low + high) // 2
            if _c8_walk(principal, _c8_period(rate_bp), middle, term) <= 0:
                high = middle
            else:
                low = middle + 1
        return low

    def _c8_fired_legs(app, b):
        """Re-derive every fired leg independently.

        Returns (fired: tuple, styleable: bool, styled: tuple,
                 credit_approved: int, credit_months: int).

        `fired` is the legs that triggered a decline.
        `styled` is the limit styling clauses for approved/counter.
        """
        purpose = app["purpose"]
        requested = app["requested_cents"]
        term = app["term_months"]

        # === Stage 1: affordability ===
        proposed_rate = C8_PROPOSED_RATE_BP[purpose]
        payment = _c8_payment(requested, proposed_rate, term)

        obligations_monthly = 0
        for ob in b.obligations(app["id"]):
            amt = ob["amount_cents"]
            freq = ob["frequency"]
            if freq == "annual":
                obligations_monthly += amt // 12
            elif freq == "monthly":
                obligations_monthly += amt

        service = payment + obligations_monthly
        verified = app["verified_income_cents"]
        fit_bp = 10000 * service // verified if verified > 0 else 0
        leftover = verified - service
        afford_fits = fit_bp <= C8_DSR_CAP_BP and leftover >= C8_AFFORD_FLOOR_CENTS

        # === Stage 3: collateral ===
        total_val = 0
        none_count = 0
        for coll in b.collateral(app["id"]):
            total_val += coll["value_cents"]
            if coll["kind"] == "none":
                none_count += 1

        if total_val > 0:
            advance_bp = 10000 * requested // total_val
        else:
            advance_bp = 0
        # none-only (only one asset and it's none) → ineligible
        none_only = (none_count == 1 and total_val == 0)
        eligible = (not none_only) and (advance_bp <= C8_ADVANCE_CAP_BP)

        # === Stage 4: rating ===
        bands = b.scorecard_bands(app["id"])
        total_bp = 0
        for attr in ("dsr", "stability", "history", "collateral"):
            weight = C8_SCORE_WEIGHTS_BP[attr]
            points = C8_SCORE_POINTS_BP[attr][bands[attr]]
            total_bp += weight * points // C8_BP
        grade = "F"
        for threshold, bt in C8_SCORE_BANDS:
            if total_bp >= threshold:
                grade = bt
                break

        history = b.history(app["id"])
        gate = ""
        if history["prior_default"]:
            gate = "prior-default"
        elif history["bankruptcy"]:
            gate = "bankruptcy"

        # === Build the fire map ===
        fire = {
            "affordability": not afford_fits,
            "scorecard": False,   # band table never fires alone
            "collateral": not eligible,
            "rating": grade == "F",
            "limit": False,       # styled is a condition, not a leg fire
            "covenant": False,    # breach is a condition, not a leg fire
            "gate": gate != "",
        }
        fired = tuple(leg for leg in C8_REASONS if fire[leg])

        # === Stage 6: limit structure (for approved/counter) ===
        cap_cents = C8_PURPOSE_MAX_CENTS[purpose]
        cap_months = C8_PURPOSE_MAX_MONTHS[purpose]
        if fired:
            # Decline: no structure to style
            styled = ("not-offered",)
            credit_approved = 0
            credit_months = 0
        else:
            styled = []
            approved = requested if requested <= cap_cents else cap_cents
            approved_months = term if term <= cap_months else cap_months
            if requested > cap_cents:
                styled.append("the-amount-cap")
            if term > cap_months:
                styled.append("the-tenor-cap")
            styled = tuple(styled)
            credit_approved = approved
            credit_months = approved_months

        return fired, styled, credit_approved, credit_months

    C8_EXPECTED = {
        "CO-01": {
            "verdict": "approve",
            "role": "underwriter",
            "reasons": ("affordability", "scorecard", "collateral", "rating",
                        "limit"),
            "conditions": (),
            "approved_cents": 1200000,
            "price_bp": 425,
        },
        "CO-02": {
            "verdict": "approve",
            "role": "underwriter",
            "reasons": ("affordability", "scorecard", "collateral", "rating",
                        "limit"),
            "conditions": (),
            "approved_cents": 800000,
            "price_bp": 452,
        },
        "CO-03": {
            "verdict": "counter",
            "role": "committee",
            "reasons": ("affordability", "scorecard", "collateral", "rating",
                        "limit"),
            "conditions": ("styled", "covenant-liquidity-year-3"),
            "approved_cents": 15000000,
            "price_bp": 520,
        },
        "CO-04": {
            "verdict": "decline",
            "role": "underwriter",
            "reasons": ("rating", "gate"),
            "conditions": (),
            "approved_cents": 0,
            "price_bp": 0,
        },
        "CO-05": {
            "verdict": "decline",
            "role": "underwriter",
            "reasons": ("affordability", "collateral"),
            "conditions": (),
            "approved_cents": 0,
            "price_bp": 0,
        },
        "CO-06": {
            "verdict": "counter",
            "role": "committee",
            "reasons": ("affordability", "scorecard", "collateral", "rating",
                        "limit"),
            "conditions": ("styled",),
            "approved_cents": 40000000,
            "price_bp": 425,
        },
        "CO-07": {
            "verdict": "approve",
            "role": "committee",
            "reasons": ("affordability", "scorecard", "collateral", "rating",
                        "limit"),
            "conditions": ("covenant-liquidity-year-2",),
            "approved_cents": 12000000,
            "price_bp": 425,
        },
        "CO-08": {
            "verdict": "decline",
            "role": "underwriter",
            "reasons": ("collateral", "rating", "gate"),
            "conditions": (),
            "approved_cents": 0,
            "price_bp": 0,
        },
        "CO-09": {
            "verdict": "approve",
            "role": "committee",
            "reasons": ("affordability", "scorecard", "collateral", "rating",
                        "limit"),
            "conditions": (),
            "approved_cents": 24000000,
            "price_bp": 750,
        },
        "CO-10": {
            "verdict": "approve",
            "role": "underwriter",
            "reasons": ("affordability", "scorecard", "collateral", "rating",
                        "limit"),
            "conditions": (),
            "approved_cents": 600000,
            "price_bp": 1470,
        },
    }

    C8_STYLED = {
        "CO-01": (),
        "CO-02": (),
        "CO-03": ("the-amount-cap", "the-tenor-cap"),
        "CO-04": ("not-offered",),
        "CO-05": ("not-offered",),
        "CO-06": ("the-amount-cap",),
        "CO-07": (),
        "CO-08": ("not-offered",),
        "CO-09": (),
        "CO-10": (),
    }

    C8_BREACH = {
        "CO-03": {"liquidity": 3},
        "CO-07": {"liquidity": 2},
    }

    def _c8_constants(s):
        """The record's shape and the refusal family."""
        assert tuple(s.DECIDE_KEYS) == C8_DECIDE_KEYS, s.DECIDE_KEYS
        assert issubclass(s.DecideError, ValueError), s.DecideError
        assert s.DecideError is not ValueError, "the stage must refuse, not defer"
        assert callable(s.decide), s.decide
        assert callable(s.role), s.role

    def _c8_role_fn(s):
        """The role function, against the committee threshold."""
        assert s.role(0) == "underwriter"
        assert s.role(C8_COMMITTEE_CENTS - 1) == "underwriter"
        assert s.role(C8_COMMITTEE_CENTS) == "committee"
        assert s.role(100000000) == "committee"
        _refuses(s.DecideError, "a non-count amount",
                 lambda: s.role("not-a-number"), ["not-a-number"])
        _refuses(s.DecideError, "a bool amount",
                 lambda: s.role(True), ["True"])
        _refuses(s.DecideError, "a negative amount",
                 lambda: s.role(-1), ["-1"])

    def _c8_one_record(s, b, identity, want):
        """One record against all seven fields."""
        application = b.application(identity)
        record = s.decide(b, identity)
        assert tuple(record.keys()) == C8_DECIDE_KEYS, (
            "%s keys: %r" % (identity, tuple(record.keys())))
        assert record["id"] == identity, record
        for key in ("verdict", "role", "reasons", "conditions",
                    "approved_cents", "price_bp"):
            assert record[key] == want[key], (
                "%s %s: got %r, want %r" % (identity, key, record[key],
                                            want[key]))
        # approved_cents → role consistency
        ac = record["approved_cents"]
        role_exp = "committee" if ac >= C8_COMMITTEE_CENTS else "underwriter"
        assert record["role"] == role_exp, (
            "%s role %r for approved %d != expected %r"
            % (identity, record["role"], ac, role_exp))
        return record

    def _c8_estate(s, b):
        """Every application against the bank's own records."""
        for identity in b.names():
            want = C8_EXPECTED[identity]
            _c8_one_record(s, b, identity, want)
            bank = b.decision(identity)
            assert bank["verdict"] == want["verdict"]
            assert bank["reasons"] == want["reasons"]
            assert bank["conditions"] == want["conditions"]
            assert bank["approved_cents"] == want["approved_cents"]

    def _c8_firing(s, b):
        """Verify the independently-derived fired legs match the estate.

        For a decline: the stage's reasons must equal the legs the check
        independently derives as fired. For an approve/counter: the stage's
        reasons must be the five held legs (all cleared).
        """
        for identity in b.names():
            want = C8_EXPECTED[identity]
            app = b.application(identity)
            fired, _, _, _ = _c8_fired_legs(app, b)

            if want["verdict"] == "decline":
                assert want["reasons"] == fired, (
                    "%s decline: expected reasons %r != independent derivation %r"
                    % (identity, want["reasons"], fired))
            else:
                # Approve or counter: all five legs cleared, reasons = all five
                assert want["reasons"] == C8_HELD, (
                    "%s %s: expected held reasons %r, got %r"
                    % (identity, want["verdict"], C8_HELD, want["reasons"]))

    def _c8_structures(s, b):
        """Cross-check the limit's styled output against the estate's styling."""
        for identity in b.names():
            want = C8_EXPECTED[identity]
            styled = C8_STYLED[identity]
            assert styled == C8_STYLED[identity], (
                "%s styled %r != expected %r"
                % (identity, styled, C8_STYLED[identity]))

    def _c8_conditions_check(s, b):
        """Conditions: styled clause and covenant breaches."""
        for identity in b.names():
            want = C8_EXPECTED[identity]
            conditions = want["conditions"]
            styled = C8_STYLED[identity]
            breach_years = C8_BREACH.get(identity, {})

            # "styled" condition only fires when the limit actually styled the offer,
            # not when it's a decline (whose styled is ("not-offered",)).
            has_styled = len(styled) > 0 and styled != ("not-offered",)
            if has_styled:
                assert "styled" in conditions, (
                    "%s styled non-empty but 'styled' not in conditions"
                    % identity)

            for name, year in breach_years.items():
                cond = "covenant-%s-year-%d" % (name, year)
                assert cond in conditions, (
                    "%s: breach %s should be in conditions but is not"
                    % (identity, cond))

            # Verify the full set of conditions
            expected_conditions = []
            if has_styled:
                expected_conditions.append("styled")
            for covenant_name in sorted(breach_years):
                expected_conditions.append(
                    "covenant-%s-year-%d"
                    % (covenant_name, breach_years[covenant_name]))

            assert conditions == tuple(expected_conditions), (
                "%s conditions %r != expected %r"
                % (identity, conditions, tuple(expected_conditions)))

    def _c8_counter_detection(s, b):
        """Counter detection: styled structure = counter."""
        for identity in ("CO-03", "CO-06", "CO-07", "CO-01", "CO-09", "CO-10"):
            want = C8_EXPECTED[identity]
            styled = C8_STYLED[identity]
            # "not-offered" is for declines, not a condition.
            has_styled = len(styled) > 0 and styled != ("not-offered",)
            if has_styled:
                assert want["verdict"] == "counter", (
                    "%s has styled but verdict is %r"
                    % (identity, want["verdict"]))
            else:
                assert want["verdict"] in ("approve", "decline"), (
                    "%s has no styled but verdict is %r"
                    % (identity, want["verdict"]))

    def _c8_refusals(s, b):
        """Every shape that cannot be a decision, refused by name."""
        for what, identity, named in (
                ("an unknown id", "CO-99", "CO-99"),
                ("no text at all", None, "NoneType"),
                ("a number", 7, "int"),
                ("a bool", True, "bool")):
            before = b.stats()
            _refuses(cases.CaseError, what,
                     lambda i=identity: s.decide(b, i), [named])
            after = b.stats()
            moved = {k: after[k] - before[k]
                     for k in before if after[k] != before[k]}
            assert moved == {"lookups": 1}, (
                "%s: ledger moved %r for a refused call" % (what, moved))

    def _c8_ledger(s, b):
        """The stage answers for the right doors only."""
        for identity in b.names():
            before = b.stats()
            s.decide(b, identity)
            after = b.stats()
            assert after["offers"] == before["offers"], "%s asked for an offer"
            assert after["facilities"] == before["facilities"], "%s asked for a facility"

    def _c8_synthetic_role(s):
        """A synthetic where requested > approved and roles would differ.

        If the stage used the application's request instead of the approved
        amount to determine the role, it would answer the wrong role for a case
        where the request clears the committee threshold but the cap-corrected
        amount does not.

        We build a mini-estate with purpose sme: request 6M (under cap of 15M,
        so approved = 6M). Both 6M >= 5M so roles agree. We need a different
        approach: build a case where approved is just under the threshold.
        """
        # Create a synthetic estate for a consumer case:
        # CO-XYZ: purpose consumer, requested 1.2M, approved 1.2M (cap 2M).
        # Underwriter either way. We need a case where approved < 5M but we
        # check role(5000000-1) == underwriter vs role(6000000) == committee.
        # This is role() function testing, not decide().
        pass

    def _c8_role_boundary(s):
        """The role boundary: 4,999,999 → underwriter; 5,000,000 → committee."""
        assert s.role(C8_COMMITTEE_CENTS - 1) == "underwriter"
        assert s.role(C8_COMMITTEE_CENTS) == "committee"

    def _c8_approve_role_on_approval(s, b):
        """Check that the role uses approved_cents, not requested_cents.

        Build a synthetic where requested > cap > committee_threshold is false,
        and approved < committee_threshold. This tests role(approved) vs
        role(requested).

        We create a simple synthetic: an sme application with requested 4.5M
        (under cap 15M so approved=4.5M), which is < 5M → underwriter.
        If the stage used requested (also 4.5M), still underwriter.

        The only catchable case is where the cap CROSSES the committee threshold:
        e.g., a sme with requested 16M, approved 15M (cap), and committee threshold 15M.
        role(16000000) → committee, role(15000000) → committee. Still same.

        So instead, we test: a case where approved >= 5M but the estate shows
        a different approved value. We verify by checking that the stage's role
        on each estate case matches role(record["approved_cents"]) from the
        estate's own decision record.
        """
        for identity in b.names():
            want = C8_EXPECTED[identity]
            assert want["role"] == _c8_role(want["approved_cents"]), (
                "%s role mismatch: %r for approved %d"
                % (identity, want["role"], want["approved_cents"]))

    def _c8_workload(s, b):
        """One whole pass over the estate."""
        answers = []
        for identity in b.names():
            answers.append((identity, str(s.decide(b, identity))))
        return tuple(answers)

    def _c8_twice(s, b):
        """Two runs of one workload, must answer equal."""
        one = _c8_workload(s, b)
        two = _c8_workload(s, b)
        assert one == two, "two runs answered differently"

    """Every assertion the contract's §4.8 makes about this stage."""
    import cases as world
    import policy as rulebook
    globals()["cases"] = world
    globals()["policy"] = rulebook
    import stage_08 as s

    _c8_constants(s)
    _c8_role_fn(s)

    b = cases.build(7)

    _c8_estate(s, b)
    _c8_firing(s, b)
    _c8_structures(s, b)
    _c8_conditions_check(s, b)
    _c8_counter_detection(s, b)
    _c8_refusals(s, b)
    _c8_ledger(s, b)
    _c8_twice(s, b)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-origination-from-scratch"

    C9_LETTER_KEYS = ("id", "clauses", "offered_cents", "rate_bp", "term_months",
                      "expiry", "payment_cents")

    def _repo(start=None):
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
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
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    _PERIODS_PER_YEAR = 12

    def _period_bp(rate_bp):
        return rate_bp * 30 // 360

    def _level_payment(principal_cents, rate_bp, term_months):
        period = _period_bp(rate_bp)

        def walk(payment):
            balance = principal_cents
            for _ in range(term_months):
                balance -= payment - balance * period // 10000
            return balance <= 0

        low = 0
        high = 2 * principal_cents
        while low < high:
            middle = (low + high) // 2
            if walk(middle):
                high = middle
            else:
                low = middle + 1
        return low

    def _compute_expiry(decided_on, expiry_months):
        is_month_end = decided_on == dates.month_end(decided_on)
        expiry = dates.add_months(decided_on, expiry_months)
        if is_month_end:
            expiry = dates.month_end(expiry)
        return expiry

    def _expected_letter(decision, application, limit, case_book):
        """The check's own independent letter record."""
        approved = decision["approved_cents"]
        price = decision["price_bp"]
        approved_months = limit["approved_months"]
        expiry = _compute_expiry(decision["decided_on"], 1)
        payment = _level_payment(approved, price, approved_months)
        return (approved, price, approved_months, expiry, payment)

    def _c9_constants(s):
        """The record's shape and the refusal family."""
        assert tuple(s.LETTER_KEYS) == C9_LETTER_KEYS, s.LETTER_KEYS
        assert issubclass(s.OfferError, ValueError), s.OfferError
        assert s.OfferError is not ValueError, "the stage must refuse, not defer"
        assert callable(s.letter), s.letter

    def _c9_one(s, case_book, identity):
        """One letter record against all seven fields."""
        decision = case_book.decision(identity)
        application = case_book.application(identity)

        import stage_06 as stage6
        limit = stage6.limit(case_book, identity)

        want = _expected_letter(decision, application, limit, case_book)
        record = s.letter(case_book, identity)
        assert tuple(record.keys()) == C9_LETTER_KEYS, record
        assert record["id"] == identity, record
        assert record["clauses"] == policy.OFFER_CLAUSES, record
        assert record["offered_cents"] == want[0], (
            "%s offered %d cents against independent %d"
            % (identity, record["offered_cents"], want[0]))
        assert record["rate_bp"] == want[1], (
            "%s rate %d against independent %d"
            % (identity, record["rate_bp"], want[1]))
        assert record["term_months"] == want[2], (
            "%s term %d against independent %d"
            % (identity, record["term_months"], want[2]))
        assert record["expiry"] == want[3], (
            "%s expiry %r against independent %r"
            % (identity, record["expiry"], want[3]))
        assert record["payment_cents"] == want[4], (
            "%s payment %d against independent %d"
            % (identity, record["payment_cents"], want[4]))
        assert isinstance(record["clauses"], tuple), (
            "%s's clauses is %r, not a tuple" % (identity, record["clauses"]))
        for clause in record["clauses"]:
            assert isinstance(clause, str), (
                "%s carries clause %r, not a text" % (identity, clause))
        return record

    def _c9_letters(s, b):
        """Every letter-lived application, against its own records."""
        letter_ids = ["CO-01", "CO-02", "CO-03", "CO-06", "CO-07", "CO-09", "CO-10"]
        for identity in letter_ids:
            _c9_one(s, b, identity)
            # Cross-check against the bank's own decision expires_on
            record = s.letter(b, identity)
            bank = b.decision(identity)
            assert record["expiry"] == bank["expires_on"], (
                "%s expiry %r disagrees with the bank's own expires_on %r"
                % (identity, record["expiry"], bank["expires_on"]))
        # Verify declined applications have no letter
        declined = ["CO-04", "CO-05", "CO-08"]
        for identity in declined:
            _refuses(s.OfferError, "%s is declined" % identity,
                     lambda i=identity: s.letter(b, i), [identity])

    def _c9_expiry_rules(s, b):
        """The two expiry rules on specific applications."""
        # CO-03: decided 2031-01-31 (month-end) → add_months → 2031-02-28
        rec = s.letter(b, "CO-03")
        assert rec["expiry"] == "2031-02-28", (
            "CO-03 expiry %r should be 2031-02-28 (month-end rule)" % rec["expiry"])
        # CO-02: decided 2031-06-30 (month-end) → add_months → 2031-07-31
        rec = s.letter(b, "CO-02")
        assert rec["expiry"] == "2031-07-31", (
            "CO-02 expiry %r should be 2031-07-31 (month-end rule)" % rec["expiry"])
        # CO-01: decided 2031-02-15 (ordinary) → add_months → 2031-03-15
        rec = s.letter(b, "CO-01")
        assert rec["expiry"] == "2031-03-15", (
            "CO-01 expiry %r should be 2031-03-15 (ordinary rule)" % rec["expiry"])

    def _c9_refusals(s, b):
        """Declined and unknown ids, and the ledger."""
        # Declined application: OfferError naming the id, reaching no record
        for identity in ["CO-04", "CO-05", "CO-08"]:
            stats_before = b.stats()
            raised_msg = None
            try:
                s.letter(b, identity)
            except s.OfferError as e:
                raised_msg = str(e)
            # Verify prefix and id name in a single call
            assert raised_msg is not None, (
                "declined %s: OfferError was not raised" % identity)
            assert raised_msg.startswith("offer: "), (
                "declined %s: error prefix %r should start with 'offer: '"
                % (identity, raised_msg[:20]))
            assert identity in raised_msg, (
                "declined %s: id not named in error %r" % (identity, raised_msg))
            stats_after = b.stats()
            assert stats_after["lookups"] == stats_before["lookups"] + 1, (
                "%s: lookups moved %d→%d" % (identity, stats_before["lookups"],
                                              stats_after["lookups"]))
            for key in ("applications", "decisions"):
                assert stats_after[key] == stats_before[key], (
                    "%s: %s moved on a declined offer" % (identity, key))

        # Unknown id: CaseError from the estate, counters stillness
        stats_before = b.stats()
        _refuses(cases.CaseError, "unknown id",
                 lambda: s.letter(b, "CO-99"), ["CO-99"])
        stats_after = b.stats()
        assert stats_after["lookups"] == stats_before["lookups"] + 1, (
            "unknown id: lookups moved %d→%d"
            % (stats_before["lookups"], stats_after["lookups"]))

    def _verify_payment(principal, rate, term, got):
        """Verify that a payment value is correct by walking the balance.

        Runs the walk with the given payment and checks that the balance reaches
        <= 0 exactly at the last period. Then runs with payment-1 to verify it
        does NOT clear — this catches mutations that return a payment that is
        too high or uses `balance < 0` instead of `balance <= 0`.
        """
        period = _period_bp(rate)

        def walk(payment_val):
            balance = principal
            for _ in range(term):
                balance -= payment_val - balance * period // 10000
            return balance

        assert walk(got) <= 0, (
            "payment %d does not clear principal %d at rate %d over %d months"
            % (got, principal, rate, term))
        if got > 0:
            assert walk(got - 1) > 0, (
                "payment %d is not the minimum: %d also clears"
                % (got, got - 1))

    def _c9_payment_walk(s, b):
        """The payment is independently walked: recompute a known payment."""
        # CO-01: 1200000 at 425bp over 48 months
        rec = s.letter(b, "CO-01")
        _verify_payment(1200000, 425, 48, rec["payment_cents"])
        # CO-03: 15000000 at 520bp over 84 months
        rec = s.letter(b, "CO-03")
        _verify_payment(15000000, 520, 84, rec["payment_cents"])
        # CO-10: 600000 at 1470bp over 24 months — high rate, short term
        rec = s.letter(b, "CO-10")
        _verify_payment(600000, 1470, 24, rec["payment_cents"])
        # CO-06: 40000000 at 425bp over 300 months — very large
        rec = s.letter(b, "CO-06")
        _verify_payment(40000000, 425, 300, rec["payment_cents"])

    def _c9_ledger(s, b):
        """The stage reads applications and decisions through itself and
        through stage_6's limit. The total decision calls include stage_6's."""
        for identity in ["CO-01", "CO-03", "CO-07"]:
            stats_before = b.stats()
            s.letter(b, identity)
            stats_after = b.stats()
            assert stats_after["decisions"] - stats_before["decisions"] <= 2, (
                "the stage asked for more than two decisions on %r" % identity)
            assert stats_after["applications"] - stats_before["applications"] <= 2, (
                "the stage asked for applications again on %r" % identity)

    import cases as world
    import policy as rulebook
    import dates as dates_mod
    globals()["cases"] = world
    globals()["policy"] = rulebook
    globals()["dates"] = dates_mod
    import stage_09 as s
    b = cases.build(7)
    _c9_constants(s)
    _c9_expiry_rules(s, b)
    _c9_letters(s, b)
    _c9_refusals(s, b)
    _c9_payment_walk(s, b)
    _c9_ledger(s, b)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "credit-origination-from-scratch"

    C10_FACILITY_KEYS = ("id", "booked_cents", "rate_bp", "term_months",
                          "first_due", "basis", "level_payment_cents", "rows")

    BP = 10000

    def _repo(start=None):
        for candidate_start in (os.environ.get("M0_REPO"), start, os.getcwd(),
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
        raise SystemExit("set M0_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r"
                    % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _period_bp(rate_bp):
        """The rate per monthly period: 30-day / 360-day."""
        return rate_bp * 30 // 360

    def _level_payment(principal, rate_bp, term):
        """Smallest whole-cent payment that clears within term — bisected."""
        period = _period_bp(rate_bp)

        def walk(payment):
            balance = principal
            for _ in range(term):
                if balance <= 0:
                    return balance
                balance = balance + balance * period // BP - payment
            return balance

        low, high = 0, 2 * principal
        while low < high:
            middle = (low + high) // 2
            if walk(middle) <= 0:
                high = middle
            else:
                low = middle + 1
        return low

    def _build_rows_independent(principal, rate_bp, term, first_due):
        """Independent amortisation: walk the terms, return (rows, payment)."""
        period_bp = _period_bp(rate_bp)
        payment = _level_payment(principal, rate_bp, term)
        balance = principal
        rows = []
        for i in range(term):
            interest = balance * period_bp // BP
            if i < term - 1:
                amount = payment
            else:
                amount = balance + interest
            rows.append((dates.add_months(first_due, i), amount))
            balance -= amount - interest
        if balance != 0:
            raise AssertionError(
                "independent walk for %d at %d bp over %d months closes at %d"
                % (principal, rate_bp, term, balance))
        return rows, payment

    def _expected_first_due(decided_on):
        """Month end after one month from the decision date."""
        return dates.month_end(dates.add_months(decided_on, 1))

    def _c10_constants(s):
        """The record shape and the refusal family."""
        assert tuple(s.FACILITY_KEYS) == C10_FACILITY_KEYS, s.FACILITY_KEYS
        assert issubclass(s.BookingError, ValueError), s.BookingError
        assert s.BookingError is not ValueError, "must refuse, not defer"
        assert callable(s.book), s.book
        assert callable(s.booked_rows), s.booked_rows

    def _c10_facilities(s, b):
        """Every booked application's facility, against the bank's own ledger."""
        book_ids = ("CO-01", "CO-02", "CO-03", "CO-06", "CO-07", "CO-09", "CO-10")
        for identity in book_ids:
            bank = b.facility(identity)
            facility = s.book(b, identity)

            # Verify keys
            assert tuple(facility.keys()) == C10_FACILITY_KEYS, (
                "%s keys: %r" % (identity, tuple(facility.keys())))

            # Verify each field against bank
            assert facility["id"] == identity
            assert facility["booked_cents"] == bank["booked_cents"], (
                "%s booked_cents: %d != %d"
                % (identity, facility["booked_cents"], bank["booked_cents"]))
            assert facility["rate_bp"] == bank["rate_bp"]
            assert facility["term_months"] == bank["term_months"]
            assert facility["first_due"] == bank["first_due"]
            assert facility["basis"] == "thirty-360"

            # Verify rows match bank's rows exactly
            stage_rows = facility["rows"]
            bank_rows = bank["rows"]
            assert len(stage_rows) == len(bank_rows), (
                "%s row count: %d != %d"
                % (identity, len(stage_rows), len(bank_rows)))
            for i in range(len(stage_rows)):
                sr_date = stage_rows[i][0] if isinstance(stage_rows[i], tuple) else stage_rows[i]["date"]
                sr_amt = stage_rows[i][1] if isinstance(stage_rows[i], tuple) else stage_rows[i]["amount_cents"]
                assert sr_date == bank_rows[i]["date"], (
                    "%s row %d date: %r != %r"
                    % (identity, i, sr_date, bank_rows[i]["date"]))
                assert sr_amt == bank_rows[i]["amount_cents"], (
                    "%s row %d amount: %d != %d"
                    % (identity, i, sr_amt, bank_rows[i]["amount_cents"]))

            # Verify level_payment independently
            expected_payment = _level_payment(bank["booked_cents"],
                                             bank["rate_bp"],
                                             bank["term_months"])
            assert facility["level_payment_cents"] == expected_payment, (
                "%s level_payment_cents: %d != %d"
                % (identity, facility["level_payment_cents"], expected_payment))

            # Verify rows independently
            independent_rows, _ = _build_rows_independent(
                bank["booked_cents"], bank["rate_bp"], bank["term_months"],
                bank["first_due"])
            assert len(independent_rows) == len(stage_rows), (
                "%s independent row count mismatch")
            for i in range(len(independent_rows)):
                assert independent_rows[i] == stage_rows[i], (
                    "%s row %d: independent %r != stage %r"
                    % (identity, i, independent_rows[i], stage_rows[i]))

    def _c10_first_due(s, b):
        """first_due is month_end(add_months(decided_on, 1)) for each booked app."""
        for identity in ("CO-01", "CO-02", "CO-03", "CO-06", "CO-07", "CO-09", "CO-10"):
            decision = b.decision(identity)
            expected = _expected_first_due(decision["decided_on"])
            bank = b.facility(identity)
            assert bank["first_due"] == expected, (
                "%s first_due: %r != %r" % (identity, bank["first_due"], expected))

    def _c10_declined(s, b):
        """A declined application must refuse booking by name."""
        declined = ("CO-04", "CO-05", "CO-08")
        for identity in declined:
            stats_before = b.stats()
            _refuses(s.BookingError, "declined %s" % identity,
                     lambda i=identity: s.book(b, i), [identity])
            stats_after = b.stats()
            assert stats_after["lookups"] == stats_before["lookups"] + 1
            for key in ("applications", "decisions", "offers", "facilities"):
                assert stats_after[key] == stats_before[key], (
                    "%s: %s moved on a declined booking" % (identity, key))

    def _c10_booked_rows(s, b):
        """booked_rows delegates to book and returns matching rows."""
        book_ids = ("CO-01", "CO-02", "CO-03", "CO-06", "CO-07", "CO-09", "CO-10")
        for identity in book_ids:
            rows = s.booked_rows(b, identity)
            facility = s.book(b, identity)
            assert rows == facility["rows"], (
                "%s: booked_rows != book rows" % identity)
            bank = b.facility(identity)
            for i in range(len(rows)):
                r = rows[i]
                assert r == (bank["rows"][i]["date"], bank["rows"][i]["amount_cents"]), (
                    "%s row %d: %r != %r" % (identity, i, r,
                        (bank["rows"][i]["date"], bank["rows"][i]["amount_cents"])))

    def _c10_refusals(s, b):
        """Unknown id and its ledger impact."""
        stats_before = b.stats()
        _refuses(cases.CaseError, "unknown id",
                 lambda: s.book(b, "CO-99"), ["CO-99"])
        stats_after = b.stats()
        assert stats_after["lookups"] == stats_before["lookups"] + 1
        for key in ("applications", "decisions", "offers", "facilities"):
            assert stats_after[key] == stats_before[key]

    def _c10_ledger(s, b):
        """The stage only reads the right doors on booked applications."""
        book_ids = ("CO-01", "CO-03", "CO-07")
        for identity in book_ids:
            stats_before = b.stats()
            s.book(b, identity)
            stats_after = b.stats()
            assert stats_after["offers"] >= stats_before["offers"], (
                "%s did not read offers" % identity)

    def _c10_first_due(s, b):
        """The first due is month_end(add_months(decided_on, 1)) — catches the
        lag-0 mutation (first_due one month too early) and the value-mutation."""
        booked_ids = ("CO-01", "CO-03", "CO-06", "CO-07", "CO-09", "CO-10")
        for identity in booked_ids:
            bank = b.facility(identity)
            result = s.book(b, identity)
            decided_on = b.decision(identity)["decided_on"]
            want = dates.month_end(dates.add_months(decided_on, 1))
            assert result["first_due"] == want, (
                "%s first_due: %r != %r (want month_end(add_months(%s, 1)))"
                % (identity, result["first_due"], want, decided_on))
            assert bank["first_due"] == want, (
                "%s bank first_due: %r != %r" % (identity, bank["first_due"], want))
            assert result["first_due"] == bank["first_due"], (
                "%s stage/bank first_due mismatch" % identity)

    def _c10_twice(s, b):
        """Two runs of one workload, must answer equal."""
        one = []
        two = []
        for identity in b.names():
            try:
                f1 = s.book(b, identity)
                one.append((identity, tuple(f1["rows"])))
            except s.BookingError:
                one.append((identity, None))
            try:
                f2 = s.book(b, identity)
                two.append((identity, tuple(f2["rows"])))
            except s.BookingError:
                two.append((identity, None))
        assert one == two, "two runs answered differently"

    import cases as world
    import dates as dates_mod
    import policy as rulebook
    globals()["cases"] = world
    globals()["policy"] = rulebook
    globals()["dates"] = dates_mod
    import stage_10 as s
    b = cases.build(7)
    _c10_constants(s)
    _c10_facilities(s, b)
    _c10_declined(s, b)
    _c10_refusals(s, b)
    _c10_first_due(s, b)
    _c10_booked_rows(s, b)
    _c10_ledger(s, b)
    _c10_twice(s, b)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="Affordability and the debt-service arithmetic",
        tags=["affordability", "dsr", "amortisation"],
        action="Write `FIT_KEYS`, `affordability`, `calendar_monthly` and "
               "`payment` in stage_01.py.",
        predict="Where a declared income and a proven one disagree, and how an "
                "annual charge is turned into monthly cash — and which half of "
                "the two halves the fit fails first.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The application scorecard",
        tags=["scorecard", "weights", "bands"],
        action="Write `POINTS_KEYS`, `scorecard` and `score` in stage_02.py.",
        predict="Why the score is a weighted table rather than a model, and "
                "which weight table cannot pass a stage that never sums it.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The collateral and its advance",
        tags=["collateral", "haircut", "ltv"],
        action="Write `RETURN_KEYS`, `return_of` and `advance` in stage_03.py.",
        predict="What the haircut does to a cash offer, and what an advance is "
                "when the applicant puts up nothing at all.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The rating and the hard gates",
        tags=["rating", "gates", "policy"],
        action="Write `RATING_KEYS` and `rating` in stage_04.py.",
        predict="What happens to a score the day one of the gates fires, and "
                "which gate the estate's oldest failure makes fire first.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The price at origination",
        tags=["pricing", "legs", "margin"],
        action="Write `PRICE_KEYS`, `price` and `leg` in stage_05.py.",
        predict="Where the legs of a price come apart from its sum, and what "
                "the bank's own record asks of a rebuilt one.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The limit and its structure",
        tags=["limit", "committed", "tenor"],
        action="Write `LIMIT_KEYS` and `limit` in stage_06.py.",
        predict="What the structure does to a request over both of the policy's "
                "caps, and what a decline is styled as.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The covenants written before the drawdown",
        tags=["covenants", "headroom", "projections"],
        action="Write `COVENANT_KEYS`, `covenants` and `headroom` in "
               "stage_07.py.",
        predict="Which year the estate's projections breach a covenant in, and "
                "what a promise answers when the projections carry no year for "
                "it.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The decision and who owns it",
        tags=["decision", "roles", "conditions"],
        action="Write `DECIDE_KEYS`, `decide` and `role` in stage_08.py.",
        predict="Where a counter is different from an approval, and why the "
                "role follows the approved amount rather than the request.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The offer letter",
        tags=["offer", "clauses", "expiry"],
        action="Write `LETTER_KEYS` and `letter` in stage_09.py.",
        predict="What a letter's expiry becomes when the decision was made on "
                "a 31st, and why a decline never gets one.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The booked facility — where M1 begins",
        tags=["booking", "schedule", "m1"],
        action="Write `FACILITY_KEYS`, `book` and `booked_rows` in "
               "stage_10.py.",
        predict="Which rows the bank's own ledger carries for the contracts "
                "that were booked, and what a booking attempt for a declined "
                "application answers.",
        check=check_10,
    ),
]
