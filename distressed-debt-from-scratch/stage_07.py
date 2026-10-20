"""Distressed Debt Investing From Scratch — stage 7: The distressed exchange.

The pool the close paid is only half the settlement. The other half is the
exchange itself: holders of one instrument tendered their claims into NEW paper,
a majority of the unsecured's face onto `paper` at a `9000` issue price — ten
hundred basis points of par handed over at the box — against a maturity pushed
out fifty-four months. This stage recomputes the exchange's terms from the
world's own `ballots`, and then answers the ballot per holder: a tenderer
holds his face in paper worth what the issue price prices it at, and a holder
who would not tender — the one who asked for CASH — is NOT paid at par by the
exchange, is told so by name in the ballot record, and receives whatever the
waterfall's cash gives the claim's whole non-tendered face, prorated.

The prorata is the heart of the stage. The class's cash from the close belongs
to the faces that did NOT exchange; a tenderer gave up his right to it when he
tendered, and a hold-out keeps it. So `holder_face * class_cash //
non_tendered_face`, truncated — and the check builds a hold-out the world does
not have (two and a half million more of face refusing to tender), rebuilds
the settlement's ballots and faces to cover the claim again, and pins both
holders' answers: the hold-out rides the waterfall and the exchange's answer
to him comes through it, never by decree.

    EXCHANGE_KEYS                 the nine fields of the club's terms, in order
    S7_BALLOT_KEYS                the six fields of one holder's answer, in order
    ExchangeError                 the refusal this stage raises
    tender(restructuring, claim)  -> EXCHANGE_KEYS: the exchange's own terms
    ballot(restructuring, holder) -> S7_BALLOT_KEYS: one holder's answer

DESIGN DECISION — why is the exchange's reaction to a cash ballot the
waterfall rather than a refusal?
Because the exchange accepts three votes and refuses none of them: tender, or
hold, or the insistence on cash. A cash ballot is a position in the negotiation
— pay me at par or I hold — and the settlement answered it the only consistent
way: no cash at par, but your face rides whatever the waterfall pays the class.
The refusal-by-name is reserved for a ballot the structure cannot rank at all —
a vote outside `VOTES` — because a vote that is not tender, hold or cash is a
ballot nobody can answer through any machinery.

DESIGN DECISION — why must the ballots cover the whole face of the claim?
Because the prorata's denominator is the non-tendered face, and that number
only means something if the ballots account for every cent of the instrument:
tendered, held, cash-asked. A sheet that collects a minority of holders can
compute a club tender but cannot say what the OTHERS ride — the missing face
is neither in nor out — so `tender` refuses and names the covered cents against
the claim's face. The check builds exactly that: a rebuild where two of four
holders answered and the exchange is asked to proceed anyway.

DESIGN DECISION — why does a tenderer's answer value the paper at the issue
price and nothing else?
Because the received cents of a POSITION are what the close actually handed
over, and the close handed over paper: `holder_face * issue_bp // 10000`. The
market's view of that paper is another stage's business — what the paper is
really worth is what the waterfall and the quotes together will decide
downstream — but the settlement's own answer has to be its own issue price,
truncated to the cent, or the exchange would be booking a valuation into its
settlement record.

DESIGN DECISION — why is the maturity extension computed and not echoed?
Because the stage's one dated claim is the paper's own maturity, and the
extension is a NUMBER the world implies: `months_between(old, new)` of the
record's two maturity dates. Echoing it would trust the record; computing it
makes the datedness a fact anyone can reproduce with the world's calendar —
and the check pins the extension to fifty-four months with
`add_months(old, 54) == new`, so a record whose dates drifted shows as a
disagreement inside the world itself.

DESIGN DECISION — why does a holder get exactly one ballot?
Because the ballot is the holder's vote, not a ledger of his lots: one holder,
one face, one answer. A rebuild with the same holder named twice is refused by
name — the exchange could average or sum his two answers, and both would
invent a holder nobody voted as.

TODO: implement `ExchangeError`, `tender` and `ballot` in this file: the
club's terms from the ballots — the tendered face, the paper it became, the
value at the issue price, the dated extension — and the per-holder answer,
tender into paper or the waterfall's prorated cash.

    `tender` is refused by name when the record carries none of the
    settlement's own fields, when the claim carries no ballots or no faces
    row, when a ballot carries a vote outside `VOTES`, and when the ballots
    cover less than the whole face. `ballot` is refused by name when the
    holder carries no ballot, two ballots, a vote outside `VOTES`, and when
    his claim's ballots do not cover the claim's face.
"""

import claims as market
import rules
import dates

PAR_BP = 10000

EXCHANGE_KEYS = ("claim", "paper", "issue_bp", "tendered_cents",
                 "received_cents", "value_cents", "old_maturity",
                 "new_maturity", "extension_months")

S7_BALLOT_KEYS = ("holder", "claim", "face_cents", "vote", "received_cents",
                  "moves")

TENDER_MOVE = "exchange"

WATERFALL_MOVE = "waterfall"


class ExchangeError(ValueError):
    """The refusal this stage raises: a ballot the exchange cannot answer.

    It names the offender — the holder whose vote nobody can rank, the claim
    whose ballots cover a minority, the claim with no faces row — because an
    exchange nobody can trace to its own ballots must say what it was asked
    for rather than exchange somebody's claim twice.
    """


def tender(restructuring, claim):
    """The exchange's own terms for one claim: what tendered, and what it became.

    The ballots of `claim` — every holder by name, tender or hold or cash —
    account for the whole face, and the tendering face is what the club gave
    up. The club received the same face in `paper`, worth
    `tendered * issue_bp // 10000`, and the maturity the paper was granted is
    the record's `old_maturity` pushed to `new_maturity`: whole months apart,
    by the calendar the world runs on.

    A claim with no ballots or no faces row, a vote outside `VOTES`, and a
    ballot sheet that covers less than the claim's face, are refused by name.
    """
    raise NotImplementedError("stage 7: implement tender()")


def ballot(restructuring, holder):
    """One holder's answer from the exchange, through the ballot and the pool.

    A tenderer keeps his face in paper: `received_cents` is
    `face_cents * issue_bp // 10000`, the move `exchange`. A holder who voted
    hold or cash is told the exchange pays no cash at par — and his face rides
    the class's waterfall cash prorated over every face that did not tender:
    `face_cents * class_cash // non_tendered_face`, the move `waterfall`.

    A holder with no ballot, two ballots, a vote outside `VOTES`, and a claim
    whose ballots do not cover its face, are refused by name.
    """
    raise NotImplementedError("stage 7: implement ballot()")
