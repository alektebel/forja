"""LBO Model From Scratch — solutions, stage 1: The sources and the uses, balanced to the cent.

The deal starts as two tables a banker writes on one page: everything that
paid in, and everything that paid out, the two sides of the same cent. This
stage produces that page from the world's own facts — the sponsor's
committed equity and each tranche's drawn amount on the pay-in side, the
equity purchase struck on an entry multiple, the transaction fees, and the
cash the balance sheet starts with on the pay-out side — and holds the two
tables to the identity that makes a close possible: total sources equal
total uses, exactly, to the cent, with no float and no remainder.

The identity is the stage's own duty, not the world's. The estate records
the deal at one entry multiple; struck at any other multiple the world
quotes, the purchase and the fees grow while the financing stays what the
term sheet says it is, and the tables do not balance — that is a refusal,
naming the imbalance in cents, and not an answer with a rounding hole in
it. Every line is a record with its own name, its own kind and its own
amount, so the audit a later stage runs can point at the exact line it
costs from.

The world is read by accessors and never written; the financing market's
quoting table lives in `estate.entry_quotes()`, and a multiple that is not
on it has no range and no purchase.

    SU_KEYS             the five fields of the sources-and-uses record, in order
    LINE_KEYS           the three fields of one line, in order
    SOURCES_KINDS       the kinds a source line may answer
    USES_KINDS          the kinds a use line may answer
    AGENT_KIND          the kind the sponsor's own cheque answers
    CASH_KIND           the kind the balance sheet's opening cash answers
    SourcesUseError     the refusal this stage raises
    sources_uses(estate, entry_multiple_bp)
                        -> SU_KEYS: the deal's two tables, balanced

    A purchase at a multiple the market table does not quote is refused by
    name, and a financing that does not pay for the purchase is refused
    with the difference in cents.
"""

import estate

SU_KEYS = ("entry_multiple_bp", "sources", "uses", "total_sources_cents",
           "total_uses_cents")

LINE_KEYS = ("name", "kind", "amount_cents")

SOURCES_KINDS = ("equity", "term")

USES_KINDS = ("equity", "fees", "cash")

AGENT_KIND = "equity"

CASH_KIND = "cash"


class SourcesUseError(ValueError):
    """The refusal this stage raises: a close the tables cannot price.

    It names the offender — the multiple the market table does not quote,
    the tranche the term sheet does not carry — or, when the two tables are
    apart, the imbalance itself in cents, because an imbalance a banker
    cannot name is an imbalance a reviewer cannot reconcile.
    """


def _line(name, kind, amount_cents):
    return dict(zip(LINE_KEYS, (name, kind, amount_cents)))


def sources_uses(estate, entry_multiple_bp):
    """The deal's sources and its uses, balanced to the cent.

    Sources: the sponsor's committed equity cheque, then each tranche the
    term sheet carries at its drawn amount — the revolver funds nothing at
    this close and answers a line of zero. Uses: the equity purchase struck
    on `entry_multiple_bp` (entry EBITDA times the multiple, in basis
    points), one fee line per fee row the term sheet carries — the advisor's
    fee is a share of the purchase, the arrangement fees a share of each
    tranche's drawn amount, both truncated to the cent — and the opening
    cash the balance sheet starts with.

    The whole record sums to the two tables' totals, and an imbalance of a
    single cent is refused with the imbalance named. A multiple the market
    table does not quote is refused by name: the purchase it would strike
    was never offered.
    """
    if isinstance(entry_multiple_bp, bool) or not isinstance(entry_multiple_bp, int):
        raise SourcesUseError("sources and uses: %s is not a multiple in basis points"
                              % (entry_multiple_bp,))
    if entry_multiple_bp not in estate.entry_quotes():
        raise SourcesUseError("sources and uses: %d is not a multiple the market "
                              "table quotes for an entry" % (entry_multiple_bp,))
    purchase = estate.entry_ebitda_cents() * entry_multiple_bp // 10000
    sources = [_line("sponsor", AGENT_KIND, estate.equity_cheque_cents())]
    for terms in estate.tranches():
        sources.append(_line(terms["name"], "term", terms["drawn_cents"]))
    uses = [_line("equity purchase", "equity", purchase)]
    for fee in estate.fee_rows():
        if fee["basis"] == "purchase":
            amount = purchase * fee["bp"] // 10000
        else:
            terms = estate.tranche(fee["name"].replace("arrangement-", ""))
            amount = terms["drawn_cents"] * fee["bp"] // 10000
        uses.append(_line(fee["name"], "fees", amount))
    uses.append(_line("opening cash", CASH_KIND, estate.min_cash_cents()))
    total_sources = sum(line["amount_cents"] for line in sources)
    total_uses = sum(line["amount_cents"] for line in uses)
    if total_sources != total_uses:
        raise SourcesUseError("sources and uses: the tables are %d cents apart "
                              "(%d of sources against %d of uses) at a purchase struck "
                              "on %d bp of entry EBITDA"
                              % (total_uses - total_sources, total_sources, total_uses,
                                 entry_multiple_bp))
    return dict(zip(SU_KEYS, (entry_multiple_bp, tuple(sources), tuple(uses),
                              total_sources, total_uses)))


if __name__ == "__main__":
    record = sources_uses(estate, estate.entry_multiple_bp())
    print("the close at %d bp of entry EBITDA, balanced"
          % (record["entry_multiple_bp"],))
    for line in record["sources"]:
        print("%-34s %15d" % ("source: " + line["name"], line["amount_cents"]))
    for line in record["uses"]:
        print("%-34s %15d" % ("use: " + line["name"], line["amount_cents"]))
    print("%-34s %15d" % ("total sources", record["total_sources_cents"]))
    print("%-34s %15d" % ("total uses", record["total_uses_cents"]))
