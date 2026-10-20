"""LBO Model From Scratch — solutions, stage 2: The operating build, revenue to free cash flow.

Every number downstream — the debt that pays itself down, the covenants that
measure it, the exit that prices it — is fed by one arithmetic: from the
revenue the company booked to the free cash flow it had left. This stage
mechanises that build from the world's own facts, and holds it to the oldest
discipline in the craft: the build lands on the path the company actually
took, line by line, to the cent. A build that does not land is not a slightly
wrong build; it is a different company.

Four things happen between revenue and cash, each named in the record.

* The margin, in integer ten-thousandths of revenue — so two years can be
  compared without a decimal anywhere.
* The earnings before interest, tax, depreciation and amortisation minus the
  depreciation the fleet carries, which is the taxable base the satellites
  price at.
* The taxes, through the policy's own bands: the first `top_cents` of the
  taxable base at the low rate, the remainder at the high rate, truncated to
  the cent twice — never once at the blended rate, because the blended rate
  is a float wearing a suit.
* The working capital the balance sheet absorbs against the year before, and
  the capex split between maintenance and growth.

The record carries the record year's actuals as the source of every input —
the inputs are facts, the outputs are arithmetic — and the recorded tax and
free cash flow are what the build has to land on: the checks pin the landing.

    OPERATE_KEYS        the fifteen fields of one year's build, in order
    OperatingError      the refusal this stage raises
    build(estate, year) -> OPERATE_KEYS: the year from revenue to free cash

    A year the walk does not walk is refused by name, and so is the walk's
    own landing: an operating build that misses the recorded tax or the
    recorded free cash flow is a different company, and the record says so.
"""

# --- a build that lands on the world, or refuses by name ---------------------

OPERATE_KEYS = ("year", "year_end", "revenue_cents", "ebitda_cents", "margin_bp",
                "depreciation_cents", "ebit_cents", "taxable_cents", "tax_cents",
                "capex_maintenance_cents", "capex_growth_cents", "capex_cents",
                "working_capital_cents", "absorption_cents", "free_cash_flow_cents")


class OperatingError(ValueError):
    """The refusal this stage raises: a build that cannot be booked.

    It names the offender — the walk year that does not exist, a build whose
    own arithmetic disagrees with the estate's recorded line — because an
    operating build that refuses to say where it is wrong is a build nobody
    can audit.
    """


def build(estate, year):
    """One walk year's operating build, from revenue to free cash, landing on
    the estate's recorded line.

    The record answers the build's inputs as the world records them and its
    outputs as the contract's arithmetic produces them: the margin in
    ten-thousandths, the taxable base, the tax through the policy's bands —
    the first `top_cents` at the low rate, the remainder at the high rate,
    each truncated to the cent — the working capital absorption against the
    year before, and the free cash flow the build lands on. When the build
    disagrees with the year's recorded tax or with the year's recorded free
    cash flow, it refuses: a model that will not argue with its own paths
    does not get to be wrong quietly.

    A year outside the walk, or a year whose build the estate does not have
    to hold, is refused by name.
    """
    if isinstance(year, bool) or not isinstance(year, int):
        raise OperatingError("the operating build: %s is not a walk year" % (year,))
    if year < 1 or year > len(estate.year_ends()):
        raise OperatingError("the operating build: %d is not a year the walk walks" % (year,))
    actual = estate.actuals(year)
    bands = estate.tax_bands()
    prev_wc = estate.entry_working_capital_cents() if year == 1 \
        else estate.actuals(year - 1)["working_capital_cents"]
    revenue = actual["revenue_cents"]
    ebitda = actual["ebitda_cents"]
    margin = ebitda * 10000 // revenue
    depreciation = actual["depreciation_cents"]
    taxable = ebitda - depreciation
    if taxable < 0:
        raise OperatingError("the operating build: year %d's base of %d is a loss the "
                             "bands do not tax" % (year, taxable))
    low = taxable if taxable <= bands["top_cents"] else bands["top_cents"]
    high = taxable - low
    tax = low * bands["low_bp"] // 10000 + high * bands["high_bp"] // 10000
    capex = actual["capex_maintenance_cents"] + actual["capex_growth_cents"]
    absorption = actual["working_capital_cents"] - prev_wc
    free = ebitda - tax - capex - absorption
    if tax != actual["tax_cents"]:
        raise OperatingError("the operating build: year %d taxes %d but the estate "
                             "recorded %d — the build and the company have come apart"
                             % (year, tax, actual["tax_cents"]))
    if free != actual["free_cash_flow_cents"]:
        raise OperatingError("the operating build: year %d's build lands on %d of free "
                             "cash and the estate recorded %d — a different company, "
                             "and one that does not share this model"
                             % (year, free, actual["free_cash_flow_cents"]))
    return dict(zip(OPERATE_KEYS, (
        year, actual["year_end"], revenue, ebitda, margin, depreciation,
        ebitda - depreciation, taxable, tax,
        actual["capex_maintenance_cents"], actual["capex_growth_cents"], capex,
        actual["working_capital_cents"], absorption, free)))
