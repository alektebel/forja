"""Agentic Retrieval From Scratch — stage 9: What the checking cost, against the naive answer.

The last stage before the customer's own failures. A pipeline that checks itself
has to be worth what the checking cost, and the null hypothesis it has to beat is
the pipeline nobody would write a book about: retrieve the hybrid top `limit` and
answer from all of it. No critique, no rewrite, no abstention — the naive row
cannot abstain, because there was never a gate for it to fail.

Against it stands the loop of stage 8, priced out of the meter's own log. Each row
is a `kind`, the cents the meter charged while it ran, how many questions it
answered, and the share of every expected id it brought to the customer.
"""

import stage_01
import stage_03
import stage_07
import stage_08

BASELINE_KEYS = ("kind", "cost_cents", "answered", "hit_bp")
ROLLUP_KEYS = ("cost_cents", "answered", "cents_per_answer", "delta_cents",
               "delta_answered")
MIN_WORTH_IT_GAIN_BP = 400

_RETRIEVE_UNITS = 1
_GENERATE_UNITS = 1


def _questions_of(questions, who):
    """The question records a price runs over, or the mistake named.

    A price over something that is not a tuple of question records cannot be a
    price at all, so it raises rather than guessing, and the message says which
    call refused and what arrived.
    """
    if isinstance(questions, str) or not isinstance(questions, (tuple, list)):
        raise ValueError("%s: questions is %r, not a tuple of question records"
                         % (who, type(questions).__name__))
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("%s: a question is %r, not a record" % (who, question))
    return tuple(questions)


def _limit_of(limit, who):
    """A limit that is a count of hits, or the mistake named."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("%s: limit is %r, not a count of hits" % (who, limit))
    return limit


def _pair_of(rows, who):
    """The two rows a price answered, the naive one first, or the mistake named.

    A rollup or a verdict is a statement about exactly the naive row and the
    checked row, so a row of another kind — or something that is not a row at all
    — is refused with its offender in the message rather than added up as if it
    were one.
    """
    rows = tuple(rows)
    if len(rows) != 2:
        raise ValueError("%s: a price answers two rows, got %d" % (who, len(rows)))
    for position, wanted in enumerate(("naive", "checked")):
        row = rows[position]
        kind = row["kind"] if isinstance(row, dict) else row
        if kind != wanted:
            raise ValueError("%s: the %s row is %r" % (who, wanted, kind))
    return rows


def _brought(question, ids):
    """How many of the question's expected ids were put in front of the customer."""
    return sum(1 for expected in question["expected"] if expected in ids)


def _coverage_bp(questions, delivered):
    """Stage 3's coverage over the ids brought to the customer, in basis points.

    The expected ids brought over every expected id of the question set, and `0`
    when the set expects nothing at all — a price over no questions is a
    comparison of nothing to nothing, not a division by nothing.
    """
    wanted = sum(len(question["expected"]) for question in questions)
    found = sum(_brought(question, ids) for question, ids in zip(questions, delivered))
    if wanted == 0:
        return 0
    return found * 10000 // wanted


def _naive_answer(corpus, question, hits, index):
    """The answer the null hypothesis gives: one claim per retrieved hit.

    It quotes the chunks' own text and cites them by stage 1's own chunk id, and
    its grounding is stage 7's own rule over the whole of what it was handed —
    there is no gate to fail here, so it never abstains.
    """
    chunks = []
    claims = []
    for hit in hits:
        chunk = index.of(hit["chunk"])
        chunks.append(chunk)
        claims.append({"text": chunk["text"], "cite": stage_01.chunk_id(chunk)})
    return {"query": question["text"], "claims": tuple(claims),
            "citations": tuple(claim["cite"] for claim in claims),
            "grounding_bp": stage_07.grounding_bp(corpus, question["text"],
                                                  tuple(chunks)),
            "abstained": False, "reason": None}


def _naive_pass(index, corpus, meter, question, tick, limit):
    """One question through the null hypothesis: its cents, and the ids it handed over.

    One retrieval charged at `tick`, one generation, and the answer built from
    every hit — no critique, so nothing is dropped and nothing abstains.
    """
    before = meter.total_cents()
    meter.charge("retrieve", _RETRIEVE_UNITS, tick)
    hits = stage_03.search(index, question["text"], limit, "hybrid")
    meter.charge("generate", _GENERATE_UNITS, tick)
    answer = _naive_answer(corpus, question, hits, index)
    return meter.total_cents() - before, tuple(answer["citations"])


def _checked_pass(index, corpus, meter, question, tick, limit, budget_cents,
                  round_cap):
    """One question through stage 8's loop: its cents, its citations, whether it answered.

    The loop prices its own rounds through the meter the caller handed it, so the
    checked pipeline's cost is the meter's delta here and nowhere else. The budget
    is one question's — a price runs many questions against one meter, so the loop
    is handed `budget_cents` on top of what the meter already holds, or the second
    question would be judged against the first one's spending. A loop that could
    not afford a single round answered nothing and cites nothing.
    """
    before = meter.total_cents()
    loop = stage_08.ask(index, corpus, meter, question, tick, limit,
                        before + budget_cents, round_cap)
    answer = loop["answer"]
    spent = meter.total_cents() - before
    if answer is None:
        return spent, (), False
    return spent, tuple(answer["citations"]), not answer["abstained"]


def _naive_row(index, corpus, meter, questions, limit):
    """The naive row, priced by the meter it was handed."""
    start = meter.total_cents()
    delivered = []
    for tick, question in enumerate(questions):
        _, ids = _naive_pass(index, corpus, meter, question, tick, limit)
        delivered.append(ids)
    return {"kind": "naive", "cost_cents": meter.total_cents() - start,
            "answered": len(questions),
            "hit_bp": _coverage_bp(questions, delivered)}


def _checked_row(index, corpus, meter, questions, limit, budget_cents, round_cap):
    """The checked row, priced by the meter it was handed."""
    before = meter.total_cents()
    delivered = []
    answered = 0
    for tick, question in enumerate(questions):
        _, ids, took_it = _checked_pass(index, corpus, meter, question, tick, limit,
                                        budget_cents, round_cap)
        delivered.append(ids)
        if took_it:
            answered += 1
    return {"kind": "checked", "cost_cents": meter.total_cents() - before,
            "answered": answered,
            "hit_bp": _coverage_bp(questions, delivered)}


def price(index, corpus, meter, questions, limit, budget_cents, round_cap):
    """Both rows over one question set, the naive pipeline first and the checked second.

    Each row is a `BASELINE_KEYS` record: its `kind`, the cents the meter charged
    while that row ran, how many questions it answered, and the share of every
    expected id it brought to the customer, in basis points. The meter is never
    reset — a row's cost is its own delta — and the tick of a question's charges is
    its position in `questions`. A `questions` that is not a tuple of question
    records, or a `limit` that is not a count of hits, is refused by name. The
    budget is one question's, and a question whose budget buys no round at all
    answered nothing.
    """
    questions = _questions_of(questions, "price")
    limit = _limit_of(limit, "price")
    naive = _naive_row(index, corpus, meter, questions, limit)
    checked = _checked_row(index, corpus, meter, questions, limit, budget_cents,
                           round_cap)
    return (naive, checked)


def rollup(rows):
    """The two `BASELINE_KEYS` rows added up, in `ROLLUP_KEYS` order.

    `cost_cents` and `answered` are the two rows' sums; `cents_per_answer` is what
    one answer cost over both rows and `None` when nothing was answered at all;
    `delta_cents` and `delta_answered` are the checked row's minus the naive one's.
    Anything but exactly the two rows of a price, naive first, is refused by name.
    """
    naive, checked = _pair_of(rows, "rollup")
    cost_cents = naive["cost_cents"] + checked["cost_cents"]
    answered = naive["answered"] + checked["answered"]
    return {"cost_cents": cost_cents,
            "answered": answered,
            "cents_per_answer": cost_cents // answered if answered else None,
            "delta_cents": checked["cost_cents"] - naive["cost_cents"],
            "delta_answered": checked["answered"] - naive["answered"]}


def where_it_lost(index, corpus, meter, questions, limit, budget_cents, round_cap):
    """The qids the checked pipeline paid more for and answered no better.

    One entry per question, in the questions' own order: the checked row charged
    more cents for it than the naive row did, and its answers brought the customer
    no more of the question's expected ids than the naive row's retrieved hits did.
    Both rows are priced the way `price` prices them, against the meter handed in.
    """
    questions = _questions_of(questions, "where_it_lost")
    limit = _limit_of(limit, "where_it_lost")
    lost = []
    for tick, question in enumerate(questions):
        naive_cost, naive_ids = _naive_pass(index, corpus, meter, question, tick,
                                            limit)
        checked = _checked_pass(index, corpus, meter, question, tick, limit,
                                budget_cents, round_cap)
        checked_cost, checked_ids = checked[0], checked[1]
        cheaper = _brought(question, checked_ids) <= _brought(question, naive_ids)
        if checked_cost > naive_cost and cheaper:
            lost.append(question["qid"])
    return tuple(lost)


def worth_it(rows):
    """The verdict on the checked row against the naive one.

    `"within-noise"` when the checked row's `hit_bp` is within
    `MIN_WORTH_IT_GAIN_BP` of the naive one's either way; `"worth-it"` when it is at
    least that much better *and* answered no fewer questions; `"not-worth-it"`
    otherwise. The rows are the two a price answered, naive first, and anything
    else is refused by name.
    """
    naive, checked = _pair_of(rows, "worth_it")
    gain_bp = checked["hit_bp"] - naive["hit_bp"]
    if -MIN_WORTH_IT_GAIN_BP < gain_bp < MIN_WORTH_IT_GAIN_BP:
        return "within-noise"
    if gain_bp >= MIN_WORTH_IT_GAIN_BP and checked["answered"] >= naive["answered"]:
        return "worth-it"
    return "not-worth-it"
