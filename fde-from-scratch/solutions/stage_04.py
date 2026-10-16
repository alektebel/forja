"""stage_04.py — retrieval that cannot leak a row.

The store stage 3 built carries the records, the postings over their text, and
the `(tenant, classification)` pair of the row each record reconciled to; this
stage is the one question the customer's user actually asks of it: which of these
may I read, and what do they say. `search` ranks the store by how many distinct
query tokens a record carries; `filtered` asks stage 1's own `refuse_reason` about
the pair the store kept, so the tenant-then-clearance rule is *called* rather than
copied; and `answer` runs the filter *before* the caller's limit, because a
retriever that takes the first `n` rows and then asks who may read them has
already read them — a small `n` hides that leak instead of preventing it.

An answer that cannot cite anything is not an empty answer: it abstains with a
reason, `no-hits` then `below-threshold` then `all-refused`, decided in that
order. Every answer, an abstention included, writes exactly one audit line
recording who asked and how many rows were used and how many refused, and never a
row's text. Nothing else here writes to the estate.
"""

from estate import Estate, EstateError
from stage_01 import refuse_reason
from stage_03 import STORE_KEYS, tokens

HIT_KEYS = ("id", "score", "tokens")
SCORE_UNIT = 1
ABSTENTIONS = ("no-hits", "below-threshold", "all-refused")
MIN_SCORE = 2
ANSWER_KEYS = ("query", "citations", "texts", "refused", "abstained", "reason")

_ANSWER_ACTION = "answer"
_ANSWERED = "answered"
_ABSTAINED = "abstained"


class RagError(EstateError):
    """This stage's refusal: a shape a retrieval cannot read, naming what arrived."""


def _mapping(value, what):
    """`value` as a mapping, or the mistake naming what arrived."""
    if not isinstance(value, dict):
        raise RagError("the %s is a %s, not a mapping" % (what, type(value).__name__))
    return value


def _keys(mapping, keys, what):
    """The mapping itself once its keys are exactly `keys`, in order, or a refusal."""
    got = tuple(mapping)
    if got != tuple(keys):
        raise RagError("the %s has the keys %r, not %r" % (what, got, tuple(keys)))
    return mapping


def _field(mapping, key, what):
    """`mapping[key]`, or the mistake naming the key that is missing."""
    if key not in mapping:
        raise RagError("the %s carries no %r" % (what, key))
    return mapping[key]


def _whole(value, what):
    """`value` as a whole number; a `bool` is not one here, exactly as in the world."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise RagError("the %s is %r, not a whole number" % (what, value))
    return value


def _text(value, what):
    """`value` as a string, or the mistake naming what arrived."""
    if not isinstance(value, str):
        raise RagError("the %s is a %s, not a string" % (what, type(value).__name__))
    return value


def _sequence(value, what):
    """`value` as a tuple of records, or the mistake naming what arrived."""
    if not isinstance(value, (tuple, list)):
        raise RagError("the %s is a %s, not a tuple" % (what, type(value).__name__))
    return tuple(value)


def _store(value):
    """The store itself once it is one: stage 3's four halves, in stage 3's order.

    This stage reads the store rather than rebuilding it, so the parts it reads
    are checked: the four keys `STORE_KEYS` names, an index and an ACL map that
    are mappings. Everything else about the store is stage 3's business.
    """
    store = _mapping(value, "store")
    _keys(store, STORE_KEYS, "store")
    for half in ("postings", "acls"):
        _mapping(store[half], "store's %s" % (half,))
    return store


def _hit(value):
    """One search result, once it is a `HIT_KEYS` record, or the mistake."""
    hit = _mapping(value, "hit")
    _keys(hit, HIT_KEYS, "hit")
    return hit


def _hits(value):
    """Every hit `filtered` was handed, once each one is a `HIT_KEYS` record."""
    return tuple(_hit(hit) for hit in _sequence(value, "hits"))


def _acl(value, record_id):
    """The `(tenant, classification)` pair the store keeps for `record_id`.

    A pair, not a row: the store keeps exactly what stage 3's reconciliation
    took from the row, and a store that kept something else is a store whose ACLs
    this stage cannot read, so it is refused by name rather than guessed at.
    """
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise RagError("the ACL of %r is %r, not a (tenant, classification) pair"
                       % (record_id, value))
    return (_text(value[0], "tenant of %s" % (record_id,)),
            _text(value[1], "classification of %s" % (record_id,)))


def _text_of(store, record_id):
    """The text the store holds for `record_id`, or the refusal naming the id.

    A citation that cannot show its text is a citation the stage would have to
    invent, and a store that keeps an ACL and a posting for a record it does not
    hold is a store whose answer would cite nothing.
    """
    for record in store["records"]:
        if isinstance(record, dict) and record.get("id") == record_id:
            return _text(record.get("text"), "text of %s" % (record_id,))
    raise RagError("the store carries no record %r, so it cannot cite it"
                   % (record_id,))


def _verdict(hits, refusals):
    """Why this answer abstains, or `(False, None)`: the three reasons, in order.

    Nothing retrieved at all is `no-hits`; a ranking in which no row carries
    `MIN_SCORE` query tokens is `below-threshold`; a ranking in which every hit
    was refused is `all-refused`. The precedence is the rule rather than an
    accident of the branches: a ranking that is both too weak and entirely
    refused answers `below-threshold`, because saying "you may see none of these"
    about rows that were never good enough to cite tells the caller which rows
    the customer holds. A ranking that abstains nowhere is not an abstention.
    """
    if not hits:
        return True, ABSTENTIONS[0]
    if all(hit["score"] < MIN_SCORE for hit in hits):
        return True, ABSTENTIONS[1]
    if len(refusals) == len(hits):
        return True, ABSTENTIONS[2]
    return False, None


def search(store, query, limit):
    """The store's records ranked by how many distinct query tokens each one carries.

    The score is `SCORE_UNIT` for every distinct query token the record carries.
    The query's tokens are stage 3's own `tokens`, so a word the query repeats is
    one token, its punctuation is gone, and a record is a hit exactly when it
    carries at least one of them. Ties are broken by record id ascending and the
    caller's limit is applied to the ranking last, so the ranking is a function
    of the store's content rather than of the order its index happens to be in.

    The limit is a count of rows and never an instruction about how many rows to
    look at: a negative one is refused by name, and one past the end of the
    ranking is simply the whole ranking.
    """
    store = _store(store)
    query = _text(query, "query")
    limit = _whole(limit, "limit")
    if limit < 0:
        raise RagError("a limit is a count of rows, and %d is not" % (limit,))
    carried = {}
    score = {}
    for token in tokens(query):
        for record_id in store["postings"].get(token, ()):
            if record_id not in score:
                score[record_id] = 0
                carried[record_id] = []
            score[record_id] = score[record_id] + SCORE_UNIT
            carried[record_id].append(token)
    ranked = sorted(score, key=lambda record_id: (-score[record_id], record_id))
    return tuple({"id": record_id, "score": score[record_id],
                  "tokens": tuple(carried[record_id])}
                 for record_id in ranked[:limit])


def filtered(store, principal, hits):
    """`(allowed, refusals)` for these hits: stage 1's rule, against the store's ACLs.

    Each hit is looked up in `store["acls"]` — the `(tenant, classification)` pair
    of the row its record reconciled to — and that pair is handed to stage 1's
    `refuse_reason`, which is the only place in this course where the
    tenant-then-clearance rule lives. A refusal is `(record id, reason)` and
    carries no text and no row: the caller learns that a row was refused and on
    which of the two grounds, and nothing about what the row said.

    The order of `hits` is preserved on both sides of the answer, and a hit whose
    record the store keeps no ACL for is refused by name rather than passed
    through: a row nobody has classified is a row nobody may read.
    """
    store = _store(store)
    hits = _hits(hits)
    _mapping(principal, "the principal")
    allowed = []
    refusals = []
    for hit in hits:
        record_id = hit["id"]
        if record_id not in store["acls"]:
            raise RagError("the store keeps no ACL for the hit %r" % (record_id,))
        tenant, classification = _acl(store["acls"][record_id], record_id)
        reason = refuse_reason(principal, {"tenant": tenant,
                                          "classification": classification})
        if reason is None:
            allowed.append(hit)
        else:
            refusals.append((record_id, reason))
    return tuple(allowed), tuple(refusals)


def answer(estate, principal, store, query, limit, tick):
    """The store's answer to one question for one principal, and one audit line.

    The whole store is ranked — `len(store["records"])` is the only bound this
    stage has on what the ranking may contain — and the filter runs over that
    whole ranking before the caller's limit is applied to what came back. That
    order is the stage: a limit handed to `search` would decide which rows were
    *read* before anything asked who may read them, and a small limit would then
    hide the refusal rather than prevent the leak, so the `limit` here is applied
    to rows that have already been allowed, and the refusals it does not reach
    are still reported.

    The answer is `ANSWER_KEYS`: the query, the ids of the rows it cites and
    their texts in that order, every refusal as `(id, reason)`, and whether it
    abstained with the reason it abstained for. An abstention cites nothing —
    the rows it could have shown are what `search` and `filtered` answer, and an
    answer that declines to answer does not hand them over as though it had — and
    a caller that asked for no rows at all gets no citations rather than a
    refusal. The verdict is written through `audit_answer` before the answer is
    handed back, so an answer the caller never audits is an answer that did not
    happen.
    """
    if not isinstance(estate, Estate):
        raise RagError("an answer is audited against an Estate, not a %s"
                       % (type(estate).__name__,))
    store = _store(store)
    query = _text(query, "query")
    limit = _whole(limit, "limit")
    if limit < 0:
        raise RagError("a limit is a count of rows, and %d is not" % (limit,))
    tick = _whole(tick, "tick")
    hits = search(store, query, len(store["records"]))
    allowed, refusals = filtered(store, principal, hits)
    abstained, reason = _verdict(hits, refusals)
    used = () if abstained else allowed[:limit]
    result = {"query": query,
              "citations": tuple(hit["id"] for hit in used),
              "texts": tuple(_text_of(store, hit["id"]) for hit in used),
              "refused": refusals,
              "abstained": abstained,
              "reason": reason}
    audit_answer(estate, principal, result, tick)
    return result


def audit_answer(estate, principal, answer, tick):
    """The one `AUDIT_KEYS` line an answer writes, and the line itself.

    The line carries who asked, that an answer was given or abstained from, the
    question, and how many rows were used and how many refused — counts, never
    ids and never a row's text, because the audit trail is read by people who
    have no right to the rows themselves. An answer that abstained is audited
    like any other: the refusal is the thing the customer's auditor asks about,
    and the line the customer keeps says whether the stage answered or declined.
    """
    if not isinstance(estate, Estate):
        raise RagError("an answer is audited against an Estate, not a %s"
                       % (type(estate).__name__,))
    answer = _keys(_mapping(answer, "answer"), ANSWER_KEYS, "answer")
    principal = _mapping(principal, "the principal")
    subject = _text(_field(principal, "subject", "principal"),
                    "principal's subject")
    tick = _whole(tick, "tick")
    abstained = answer["abstained"]
    if not isinstance(abstained, bool):
        raise RagError("the answer's abstained is %r, not a bool" % (abstained,))
    used = _sequence(answer["citations"], "answer's citations")
    refused = _sequence(answer["refused"], "answer's refusals")
    return estate.audit(subject, _ANSWER_ACTION, answer["query"],
                        _ABSTAINED if abstained else _ANSWERED,
                        "%d used, %d refused" % (len(used), len(refused)), tick)
