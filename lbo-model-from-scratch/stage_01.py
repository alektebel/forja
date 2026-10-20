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


    raise NotImplementedError("1: implement sources_uses()")