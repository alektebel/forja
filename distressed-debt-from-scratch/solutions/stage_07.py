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

import os
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.dirname(_DIR) if os.path.basename(_DIR) == "solutions" else _DIR
if _PATH not in sys.path:
    sys.path.insert(0, _PATH)

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




def _months_between(start, end):
    """The whole months from `start` to `end`, the calendar's clamping honoured."""
    year, month, _day = dates.parse(start)
    other_year, other_month, _other_day = dates.parse(end)
    months = (other_year - year) * rules.PERIODS_PER_YEAR + (other_month - month)
    if months > 0 and dates.add_months(start, months) > end:
        months = months - 1
    if months < 0 and dates.add_months(start, months) < end:
        months = months + 1
    return months

def _r(restructuring):
    """The settlement's own record, refused by name when a field is absent."""
    if not isinstance(restructuring, dict):
        raise ExchangeError("the settlement is a %s, not a RESTRUCTURING_KEYS "
                            "record" % (type(restructuring).__name__,))
    for field in market.RESTRUCTURING_KEYS:
        if field not in restructuring:
            raise ExchangeError("the settlement carries no %r" % (field,))
    return restructuring


def _claim_faces(restructuring, claim):
    """The faces row of `claim`, refused by name when the close has none."""
    for row in restructuring["faces"]:
        if row.get("claim") == claim:
            return row
    raise ExchangeError("the close settles no par line named %r, and the exchange "
                        "cannot lean on a claim that was not in it"
                        % (claim,))


def _claim_ballots(restructuring, claim):
    """Every ballot row the claim carries, refused when it carries none."""
    rows = tuple(row for row in restructuring["ballots"]
                 if row.get("claim") == claim)
    if not rows:
        raise ExchangeError("the exchange's ballots touch no face of claim %r"
                            % (claim,))
    return rows


def _checked(rows, cover):
    """The ballots counted: the votes the exchange knows, and the face they cover.

    A vote outside `VOTES` is refused by name — tender, hold and cash are the
    three the settlement can answer, and a fourth vote is a ballot nobody
    ranks.
    """
    for row in rows:
        holder = row.get("holder")
        vote = row.get("vote")
        if holder is None or vote is None or "face_cents" not in row:
            raise ExchangeError("a ballot of the exchange carries no holder, vote "
                                "or face: %r" % (row,))
        if vote not in market.VOTES:
            raise ExchangeError("holder %r voted %r on the exchange, and the votes "
                                "it answers are %r" % (holder, vote, market.VOTES))
    return sum(row["face_cents"] for row in rows)


def _cover(rows, face, claim):
    """A ballot sheet that accounts for every cent of the claim, or a refusal.

    The prorata's denominator is the non-tendered face, and that only means
    something if the ballots account for tendered, held and cash-asked alike:
    a minority sheet leaves the other holders neither in nor out.
    """
    cover = _checked(rows, face)
    if cover != face:
        raise ExchangeError("the ballots of claim %r cover %d of its %d cents of "
                            "face, and the exchange cannot proceed on a minority"
                            % (claim, cover, face))
    return cover


def _class_cash(restructuring, claim):
    """The waterfall cash the close paid `claim`'s whole class.

    The same recomputation stage 6 runs — the breaks lifted out of the pool
    first, then the remaining pool down the faces — restated here so the
    holder's answer is traceable to the settlement's own facts.
    """
    pool = restructuring["proceeds_cents"]
    for break_row in restructuring["breaks"]:
        pool = pool - break_row["paid_cents"]
        if pool < 0:
            raise ExchangeError("the breaks of the close overdraw its pool: the "
                                "decree leaves %d of %d" % (pool,
                                                            restructuring["proceeds_cents"]))
    remaining = pool
    cash = 0
    for row in restructuring["faces"]:
        take = row["face_cents"]
        if remaining < take:
            take = remaining
        remaining = remaining - take
        if row["claim"] == claim:
            cash = take
    return cash


class ExchangeError(ValueError):
    """The refusal this stage raises: a ballot the exchange cannot answer.

    It names the offender — the holder whose vote nobody can rank, the claim
    whose ballots cover a minority, the claim with no faces row — because an
    exchange nobody can trace to its own ballots must say what it was asked
    for rather than exchange somebody's claim twice.
    """




def _extension(restructuring):
    """Whole months between the two maturities, the calendar's answer."""
    return _months_between(restructuring["old_maturity"],
                           restructuring["new_maturity"])



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


    restructuring = _r(restructuring)
    faces = _claim_faces(restructuring, claim)
    rows = _claim_ballots(restructuring, claim)
    _cover(rows, faces["face_cents"], claim)
    tendered = sum(row["face_cents"] for row in rows if row["vote"] == "tender")
    value = tendered * restructuring["issue_bp"] // PAR_BP
    return {"claim": claim, "paper": restructuring["paper"],
            "issue_bp": restructuring["issue_bp"], "tendered_cents": tendered,
            "received_cents": tendered, "value_cents": value,
            "old_maturity": restructuring["old_maturity"],
            "new_maturity": restructuring["new_maturity"],
            "extension_months": _extension(restructuring)}


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

    restructuring = _r(restructuring)
    rows = tuple(row for row in restructuring["ballots"]
                 if row.get("holder") == holder)
    if not rows:
        raise ExchangeError("no ballot of the exchange names holder %r"
                            % (holder,))
    if len(rows) > 1:
        raise ExchangeError("holder %r answers %d ballots, and a holder votes "
                            "once" % (holder, len(rows)))
    row = rows[0]
    vote = row.get("vote")
    if vote not in market.VOTES:
        raise ExchangeError("holder %r voted %r on the exchange, and the votes it "
                            "answers are %r" % (holder, vote, market.VOTES))
    claim = row["claim"]
    face = _claim_faces(restructuring, claim)["face_cents"]
    _cover(_claim_ballots(restructuring, claim), face, claim)
    if vote == "tender":
        received = row["face_cents"] * restructuring["issue_bp"] // PAR_BP
        return {"holder": holder, "claim": claim,
                "face_cents": row["face_cents"], "vote": vote,
                "received_cents": received, "moves": (TENDER_MOVE,)}
    tendered = sum(b["face_cents"] for b in restructuring["ballots"]
                   if b["claim"] == claim and b.get("vote") == "tender")
    class_cash = _class_cash(restructuring, claim)
    non_tendered = face - tendered
    received = class_cash * row["face_cents"] // non_tendered
    return {"holder": holder, "claim": claim,
            "face_cents": row["face_cents"], "vote": vote,
            "received_cents": received, "moves": (WATERFALL_MOVE,)}

if __name__ == "__main__":
    r = market.restructuring()
    club = tender(r, "BL-UNSEC")
    print("the club's terms:")
    print("  tendered %d of face -> %d of %r at %d bp of par = %d"
          % (club["tendered_cents"], club["received_cents"], club["paper"],
             club["issue_bp"], club["value_cents"]))
    print("  maturity %r extended to %r: %d months"
          % (club["old_maturity"], club["new_maturity"],
             club["extension_months"]))
    print("the ballot, holder by holder:")
    for row in r["ballots"]:
        answer = ballot(r, row["holder"])
        print("  %-20s %-6r %-12d -> %d via %r"
              % (answer["holder"], answer["vote"], answer["face_cents"],
                 answer["received_cents"], answer["moves"][0]))
