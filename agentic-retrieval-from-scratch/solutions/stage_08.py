"""Agentic Retrieval From Scratch — stage 8: The loop that must terminate, priced every round.

The seven stages below this one each answer once; this one asks again, and the
whole of it is the bound on that asking. A round retrieves the hybrid top
`limit`, reranks it, critiques it and answers from the survivors, and the round
is charged to the customer's meter one retrieval, one rerank, one critique and
one generation at a time — its `cost_cents` is the meter's own delta and never
this stage's arithmetic. The budget is checked before the round, so the loop
never spends past what the caller allowed; a non-abstention ends it `answered`,
and an abstention rewrites once and carries on until the query would repeat, the
rewrites allowed run out, or the rewrite yields nothing at all. Nothing here
reads a clock: the tick is the caller's, and the only time this loop knows is
the count of rounds it has run.
"""

from corpus import QUESTION_KEYS as _QUESTION_KEYS
from meter import PRICE_CENTS as _PRICE_CENTS

import stage_03
import stage_04
import stage_05
import stage_06
import stage_07

ROUND_KEYS = ("round", "query", "rewrites", "retrieved", "survivors", "cost_cents")

LOOP_KEYS = ("question", "answer", "rounds", "cost_cents", "stopped", "reason")

STOPS = ("answered", "abstained", "budget", "round-cap", "repeat")

RETRIEVE_UNITS = 1

RERANK_UNITS = 1

CRITIQUE_UNITS = 1

GENERATE_UNITS = 1

DEFAULT_LIMIT = 5

_CHARGES = (("retrieve", RETRIEVE_UNITS), ("rerank", RERANK_UNITS),
            ("critique", CRITIQUE_UNITS), ("generate", GENERATE_UNITS))


def _whole(value, what):
    """`value` as a whole number; a `bool` is not one here, exactly as in the world."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("the %s is %r, not a whole number" % (what, value))
    return value


def _question(question):
    """`question` as a `QUESTION_KEYS` record, or the mistake naming what arrived."""
    if not isinstance(question, dict):
        raise ValueError("the question is a %s, not a mapping"
                         % (type(question).__name__,))
    keys = tuple(question)
    if keys != _QUESTION_KEYS:
        raise ValueError("the question carries %r, not %r" % (keys, _QUESTION_KEYS))
    return question


def _round_price():
    """One whole round's price, from the customer's own table rather than a belief."""
    return sum(_PRICE_CENTS[kind] * units for kind, units in _CHARGES)


def _record(question, text):
    """The question's own record with this round's query text in place of its own."""
    return dict(question, text=text)


def _kinds(rewrites):
    """The `REWRITE_KINDS` of a round's fixes, in the order the fixes were applied."""
    return tuple(fix["kind"] for fix in rewrites)


def ask(index, corpus, meter, question, tick, limit, budget_cents, round_cap):
    """Run the budgeted loop over one question and answer what it did."""
    question = _question(question)
    tick = _whole(tick, "tick")
    limit = _whole(limit, "the limit")
    budget_cents = _whole(budget_cents, "the budget")
    round_cap = _whole(round_cap, "the round cap")
    if limit < 1:
        raise ValueError("the limit is %d, and a round retrieves at least one hit"
                         % (limit,))
    if budget_cents < 0:
        raise ValueError("the budget is %d cents, not a budget" % (budget_cents,))
    if round_cap < 0:
        raise ValueError("the round cap is %d rewrites, not a cap" % (round_cap,))
    base = meter.total_cents()
    price = _round_price()
    rounds = []
    tried = [question["text"]]
    text = question["text"]
    rewrites = ()
    used = 0
    answer = None
    stopped = None
    reason = None
    while True:
        spent = meter.total_cents()
        if spent + price > budget_cents:
            stopped = "budget"
            reason = "spent %d of %d" % (spent + price, budget_cents)
            break
        before = meter.total_cents()
        hits = stage_03.search(index, text, limit, "hybrid")
        meter.charge("retrieve", RETRIEVE_UNITS, tick)
        ranked = stage_04.rerank(index, text, hits, limit)
        meter.charge("rerank", RERANK_UNITS, tick)
        chunks = tuple(index.of(hit["chunk"]) for hit in ranked)
        critiques = stage_06.critique(chunks, text, corpus)
        meter.charge("critique", CRITIQUE_UNITS, tick)
        answer = stage_07.answer(corpus, text, chunks, critiques,
                                 stage_07.GROUNDING_MIN_BP)
        meter.charge("generate", GENERATE_UNITS, tick)
        rounds.append({"round": len(rounds), "query": text, "rewrites": rewrites,
                       "retrieved": tuple(hit["chunk"] for hit in ranked),
                       "survivors": stage_06.survivors(critiques),
                       "cost_cents": meter.total_cents() - before})
        if not answer["abstained"]:
            stopped = "answered"
            break
        if used >= round_cap:
            stopped = "round-cap"
            reason = "round cap %d" % (round_cap,)
            break
        next_text, fixes = stage_05.rewrite(corpus, _record(question, text))
        if not fixes and used == 0:
            stopped = "abstained"
            reason = answer["reason"]
            break
        if next_text in tried:
            stopped = "repeat"
            reason = "already tried the query %r" % (next_text,)
            break
        tried.append(next_text)
        text = next_text
        rewrites = _kinds(fixes)
        used = used + 1
    return {"question": question["qid"], "answer": answer, "rounds": tuple(rounds),
            "cost_cents": meter.total_cents() - base, "stopped": stopped,
            "reason": reason}


def rounds_of(loop):
    """The rounds a loop ran, in the order it ran them."""
    if not isinstance(loop, dict):
        raise ValueError("the loop is a %s, not a mapping" % (type(loop).__name__,))
    keys = tuple(loop)
    if keys != LOOP_KEYS:
        raise ValueError("the loop carries %r, not %r" % (keys, LOOP_KEYS))
    return loop["rounds"]
