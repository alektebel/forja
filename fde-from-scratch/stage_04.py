"""FDE From Scratch — stage 4: Retrieval that cannot leak a row.

The store stage 3 built is the customer's paperwork read and placed: the records,
the postings over their text, and the `(tenant, classification)` pair of the row
each record reconciled to. This stage is the question the customer's user
actually asks of it — which of these may I read, and what do they say — and the
one way to get it wrong that ends the deal: handing back a row the caller had no
right to read.

`search` ranks the store by how many distinct query tokens a record carries.
`filtered` answers which of those hits the caller may see, by asking stage 1's own
`refuse_reason` about the pair the store kept for each one — the tenant first,
then the clearance — and refusing with a reason rather than a bare `False`.
`answer` puts the two together in the only order that is safe: the filter runs
over the whole ranking *before* the caller's limit is applied to what came back,
so what was read and what was refused is decided by the ACLs and not by how many
rows the caller asked for. A small limit is a limit, not a hiding place.
`audit_answer` writes the one line every answer leaves behind, abstentions
included, carrying who asked and how many rows were used and refused — and never
a row's text.

    HIT_KEYS          one search result: a record id, its score, what it carries
    SCORE_UNIT        the score one distinct query token contributes
    ABSTENTIONS       the three reasons an answer abstains for, in precedence order
    MIN_SCORE         the score below which nothing is worth answering with
    ANSWER_KEYS       the six fields of one answer, in order
    RagError          this stage's refusal
    search(store, query, limit)              -> the query's hits, best first
    filtered(store, principal, hits)         -> (allowed, refusals)
    answer(estate, principal, store, query, limit, tick) -> ANSWER_KEYS
    audit_answer(estate, principal, answer, tick)        -> the AUDIT_KEYS line

A hit's `tokens` are the query tokens that record carries, in the order the query
put them in, its `score` is `SCORE_UNIT` for each of them, and a record that
carries none of them is not a hit at all: an empty query, a query of punctuation
and a query the store has never heard of all retrieve nothing. An answer's
`citations` and `texts` are parallel tuples — the ids and the texts of the rows
the caller may read, in rank order, out of the whole ranking and only then cut to
the caller's limit — `refused` is the whole ranking's refusals as
`(record id, reason)`, and `abstained` with a `reason` from `ABSTENTIONS` is what
an answer that could not cite anything says instead of an empty citation list. An
abstention cites nothing.

DESIGN DECISION — why does the filter run before the limit?
Because the leak is not the answer, it is the reading. A retriever that ranks the
store, takes the caller's first `n` rows and only then asks which of them the
caller may read has already read the rows it discards, and — worse — the rows it
never looks at are the rows whose refusal the caller is never told about, so a
small `n` makes the leak *invisible* rather than absent. This stage therefore
ranks the whole store, filters the whole ranking, and applies the caller's limit
to the rows that survived; the bound it hands `search` is the size of the store,
which is the only bound an answer may have. That is also why `search` keeps a
limit of its own: an unfiltered retrieval is a legitimate thing to ask for, and
`search` is where the naive retriever lives, on purpose.

DESIGN DECISION — why does the filter call stage 1's `refuse_reason` instead of
deciding visibility itself?
Because the rule is one rule and it already exists. The store kept the pair of
`(tenant, classification)` that stage 3's reconciliation took from the row a
record belonged to, and that pair is exactly what stage 1's `refuse_reason` is
written against; asking it is what makes the tenant comparison exact, the
clearance comparison positional, and the tenant asked before the clearance —
without this stage owning a second copy of any of it. A retriever that wrote its
own `if` would be a retriever whose rule drifts from the row rule the moment
either one is touched, which is how a course about boundaries acquires two of
them.

DESIGN DECISION — why does a refusal name the row's id but never its text?
Because "you may not read this" and "here is what it said" are different
sentences. A refusal is `(record id, reason)` from the closed vocabulary stage 1
already uses, so the caller — and the customer's auditor — can see that a row was
held back and on which of the two grounds, and the id is what makes the refusal
checkable rather than a bare `False`; the text is what the caller has no right to,
so it appears in no citation, in no refusal, and in no audit line. The audit line
is narrower still: counts of rows used and refused, never the ids and never the
text.

DESIGN DECISION — why three reasons to abstain instead of an empty answer?
Because an empty answer is indistinguishable from a broken one. "Nothing
retrieved", "nothing above `MIN_SCORE`" and "everything refused" are three
different situations for the caller and three different things for the customer's
audit trail, and the order they are decided in is the rule rather than an
accident: when a ranking is both too weak and entirely refused, `below-threshold`
is the answer, because announcing "you may see none of these" about rows that
were never good enough to cite is itself a hint about what the customer holds.
`no-hits` comes before both, and the closed vocabulary is printed in the order it
is consulted.

DESIGN DECISION — why does an abstained answer cite nothing, and why is it
audited anyway?
Because an answer that abstains has decided not to answer, and the rows it could
have shown are what `search` and `filtered` are for — the caller who wants weak
matches asks for them directly rather than receiving them as an answer that
claims to be empty. And the audit line is written for an abstention the same as
for an answer, because the refusals are precisely what the auditor has come to
look at: a stage that logged only its successes would have an audit trail in which
every question it declined to answer is invisible, which is the trail's opposite.

TODO: implement
"""

from estate import EstateError
from stage_01 import refuse_reason
from stage_03 import STORE_KEYS, tokens

HIT_KEYS = ("id", "score", "tokens")
SCORE_UNIT = 1
ABSTENTIONS = ("no-hits", "below-threshold", "all-refused")
MIN_SCORE = 2
ANSWER_KEYS = ("query", "citations", "texts", "refused", "abstained", "reason")


class RagError(EstateError):
    """This stage's refusal: a shape a retrieval cannot read, naming what arrived."""


def search(store, query, limit):
    """The store's records ranked by how many distinct query tokens each one carries.

    The score is `SCORE_UNIT` per distinct query token the record carries — the
    query's tokens are stage 3's own `tokens`, so a word the query repeats is one
    token and its punctuation is gone — ties are broken by record id ascending,
    and the limit is applied to the ranking last. A record that carries none of
    the query's tokens is not a hit: an empty query, a query of punctuation and a
    query no record carries all answer `()`.
    """
    raise NotImplementedError("stage 4: implement search()")


def filtered(store, principal, hits):
    """`(allowed, refusals)` for these hits: stage 1's rule, against the store's ACLs.

    Each hit's record id is looked up in `store["acls"]` and the pair kept there
    is handed to stage 1's `refuse_reason`, which is the only place in this course
    where the tenant-then-clearance rule lives. `allowed` is the hits the
    principal may read, in the order they arrived; `refusals` is `(record id,
    reason)` for the rest, and carries no text.
    """
    raise NotImplementedError("stage 4: implement filtered()")


def answer(estate, principal, store, query, limit, tick):
    """One question answered for one principal: `ANSWER_KEYS`, and one audit line.

    The whole store is ranked and the whole ranking is filtered before the
    caller's limit is applied to the rows that were allowed, so a small limit
    cannot hide a refusal. An answer that can cite nothing abstains with a reason
    from `ABSTENTIONS` and cites nothing; every answer, that one included, is
    written to the estate's audit trail through `audit_answer` before it is
    handed back.
    """
    raise NotImplementedError("stage 4: implement answer()")


def audit_answer(estate, principal, answer, tick):
    """The one `AUDIT_KEYS` line an answer writes, and the line itself.

    It carries who asked, whether the stage answered or abstained, the question
    and how many rows were used and how many refused — counts, never ids, and
    never a row's text.
    """
    raise NotImplementedError("stage 4: implement audit_answer()")
