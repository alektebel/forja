"""Agentic Retrieval From Scratch — stage 4: The reranker that must earn its place.

The solution: a cross-scorer whose score is the sum of its own printed signals, the
comparison of stage 3's own measurement against the same measurement with the
reranker in it, and the plain decision that comparison implies.
"""

import stage_03

RERANK_KEYS = ("chunk", "score", "signals")

COMPARE_KEYS = ("before", "after", "delta_bp", "verdict")

COVERAGE_WEIGHT = 3

PROXIMITY_WEIGHT = 2

WEIGHT_TOTAL = 5

PROXIMITY_WINDOW = 12

LEVEL_BONUS_BP = 500

NOISE_BP = 200

WHOLE_BP = 10000

OUTERMOST = 1


def _whole(value, what):
    """`value` as a whole number; a `bool` is not one here, exactly as in the world."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("stage 4: %s is %r, not a whole number" % (what, value))
    return value


def _analyzed(index, text):
    """The customer's analyzer, as the index answers it, over one text."""
    terms = getattr(index, "terms", None)
    if not callable(terms):
        raise ValueError("stage 4: the index %r does not answer terms()" % (index,))
    return tuple(terms(text))


def _whole_hits(index, hits):
    """Every hit as `(chunk id, chunk record)`, each naming a chunk this index holds."""
    found = []
    for hit in hits:
        if not isinstance(hit, dict) or not isinstance(hit.get("chunk"), str):
            raise ValueError("stage 4: %r is not a hit" % (hit,))
        chunk = index.of(hit["chunk"])
        if chunk is None:
            raise ValueError("stage 4: %r is not a chunk this index holds"
                             % (hit["chunk"],))
        found.append((hit["chunk"], chunk))
    return tuple(found)


def _distinct(terms):
    """The terms in first-appearance order, each one once."""
    seen = []
    for term in terms:
        if term not in seen:
            seen.append(term)
    return tuple(seen)


def _covered(query_terms, chunk_terms):
    """The query's distinct terms the chunk's text holds, in the query's own order."""
    held = set(chunk_terms)
    return tuple(term for term in query_terms if term in held)


def _coverage_bp(covered, terms):
    """The share of the query's distinct terms the chunk holds, in basis points."""
    if not terms:
        return 0
    return len(covered) * WHOLE_BP // terms


def _near(chunk_terms, term, others):
    """Whether another of the covered terms sits within the window of one of `term`'s."""
    for place, token in enumerate(chunk_terms):
        if token != term:
            continue
        for index, other in enumerate(chunk_terms):
            if other in others and -PROXIMITY_WINDOW <= place - index <= PROXIMITY_WINDOW:
                return True
    return False


def _proximity_bp(chunk_terms, covered):
    """The share of the covered terms with another distinct covered term in the window."""
    if not covered:
        return 0
    near = 0
    for term in covered:
        others = tuple(other for other in covered if other != term)
        if _near(chunk_terms, term, others):
            near += 1
    return near * WHOLE_BP // len(covered)


def _signals(index, chunk, query_terms):
    """The three named signals a rerank score is built from, sorted by name."""
    chunk_terms = _analyzed(index, chunk["text"])
    covered = _covered(query_terms, chunk_terms)
    return (
        ("coverage", _coverage_bp(covered, len(query_terms))),
        ("level-bonus", LEVEL_BONUS_BP if chunk["level"] == OUTERMOST else 0),
        ("proximity", _proximity_bp(chunk_terms, covered)),
    )


def _score(signals):
    """The rerank score, recomputable from the signals alone."""
    values = dict(signals)
    return (values["coverage"] * COVERAGE_WEIGHT // WEIGHT_TOTAL
            + values["proximity"] * PROXIMITY_WEIGHT // WEIGHT_TOTAL
            + values["level-bonus"])


def _descending(record):
    """The sort key that puts the highest score first and keeps the input order on a tie."""
    return -record["score"]


def rerank(index, query, hits, limit):
    """The hits, rescored from their own signals and reordered, cut to `limit`."""
    limit = _whole(limit, "the limit")
    if limit < 0:
        raise ValueError("stage 4: the limit is %d, not a count of hits" % (limit,))
    resolved = _whole_hits(index, hits)
    query_terms = _distinct(_analyzed(index, query))
    ranked = []
    for chunk_id, chunk in resolved:
        signals = _signals(index, chunk, query_terms)
        ranked.append({"chunk": chunk_id, "score": _score(signals), "signals": signals})
    ranked.sort(key=_descending)
    return tuple(ranked[:limit])


def _asked(questions):
    """Every question as a record this stage can measure, or the refusal naming it."""
    found = []
    for question in questions:
        if not isinstance(question, dict):
            raise ValueError("stage 4: %r is not a question" % (question,))
        if not isinstance(question.get("text"), str):
            raise ValueError("stage 4: question %r carries no text"
                             % (question.get("qid"),))
        expected = question.get("expected")
        if not isinstance(expected, (tuple, list)):
            raise ValueError("stage 4: question %r carries no expected tuple"
                             % (question.get("qid"),))
        found.append(question)
    return tuple(found)


def _retrieved(index, questions, limit):
    """Each question's retrieval: the whole fused ranking, reranked down to `limit`."""
    found = []
    for question in questions:
        candidates = stage_03.search(index, question["text"], len(index.chunks),
                                     "hybrid")
        ranked = rerank(index, question["text"], candidates, limit)
        found.append(tuple(hit["chunk"] for hit in ranked))
    return tuple(found)


def _measure(retrieved, questions):
    """One retrieval per question, counted by stage 3's own answered/hit_bp/missed rules."""
    answered = 0
    covered = 0
    total = 0
    missed = []
    for question, found in zip(questions, retrieved):
        expected = tuple(question["expected"])
        total += len(expected)
        here = sum(1 for wanted in expected if wanted in found)
        covered += here
        if here == len(expected):
            answered += 1
        else:
            missed.append(question["qid"])
    return {"mode": "hybrid",
            "answered": answered,
            "hit_bp": 0 if total == 0 else covered * WHOLE_BP // total,
            "missed": tuple(sorted(missed))}


def compare(index, questions, limit):
    """The measurement without the reranker against the measurement with it."""
    limit = _whole(limit, "the limit")
    questions = _asked(questions)
    before = stage_03.measure(index, questions, limit, "hybrid")
    after = _measure(_retrieved(index, questions, limit), questions)
    delta = after["hit_bp"] - before["hit_bp"]
    if delta < 0:
        verdict = "hurt"
    elif delta < NOISE_BP:
        verdict = "within-noise"
    else:
        verdict = "earned"
    return {"before": before, "after": after, "delta_bp": delta, "verdict": verdict}


def keep(index, questions, limit):
    """`"keep"` exactly when `compare` says `"earned"`, and `"remove"` otherwise."""
    return ("keep" if compare(index, questions, limit)["verdict"] == "earned"
            else "remove")
