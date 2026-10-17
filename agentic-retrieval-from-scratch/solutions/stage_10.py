"""Agentic Retrieval From Scratch — stage 10: Which stage failed, and whether the checker beat the baseline.

The ten stages end where the customer's own records are: a labelled failure set
and a labelled evaluation set. This file reads both and believes neither. The
diagnosis is derived from the evidence in a failure row — what the chunker
produced against the document's clause index, what retrieval ranked, what the
kept line left out, what was cited — and the row's own `stage` field is compared
with afterwards, never consulted. The verdict is derived from what the loop
actually answered, priced on the meter it was handed, and held against the
naive retrieval on the same questions with a sample floor under it, so the
checker cannot call a pipeline better on the strength of four answers.

Every shape this stage can judge on its own is judged before it asks the world
anything, and every refusal names the offender: a failure row that is not a
mapping, a question the corpus does not hold, a chunk id belonging to another
document, a diagnosis that blames a stage outside `FAILURE_STAGES`. The
library's own log is what proves the discipline: an answered row is diagnosed
without asking the library anything at all.
"""

import corpus
import meter
import stage_03
import stage_05
import stage_08

DIAGNOSIS_KEYS = ("fid", "stage", "reason")

FAILURE_STAGES = ("chunk", "rewrite", "retrieve", "rerank", "ground", "answer",
                  "none")

EVAL_KEYS = ("answered", "hit_bp", "unsupported_bp", "abstained_correctly",
             "cost_cents", "verdict")

EVAL_MIN_SAMPLE = 4

EVAL_MIN_GAIN_BP = 400

#: The evidence `diagnose` decides from: every `FAILURE_KEYS` field but `stage`.
EVIDENCE_FIELDS = ("fid", "qid", "chunks", "retrieved", "kept", "cited",
                   "answer_ok")


def _mapping(value, what):
    """`value` as a mapping, or the mistake naming what arrived."""
    if not isinstance(value, dict):
        raise ValueError("the %s is a %s, not a mapping" % (what, type(value).__name__))
    return value


def _field(mapping, key, what):
    """`mapping[key]`, or the mistake naming the key that is missing."""
    if key not in mapping:
        raise ValueError("the %s carries no %r" % (what, key))
    return mapping[key]


def _text(value, what):
    """`value` as a string, or the mistake naming what arrived."""
    if not isinstance(value, str):
        raise ValueError("the %s is %r, not a string" % (what, value))
    return value


def _whole(value, what):
    """`value` as a whole number; a `bool` is not one here, exactly as in the world."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("the %s is %r, not a whole number" % (what, value))
    return value


def _names(value, what):
    """`value` as a tuple of names: a bare string is one name, not a tuple of them."""
    if not isinstance(value, (tuple, list)):
        raise ValueError("%s is a tuple of names, not %r" % (what, value))
    for name in value:
        if not isinstance(name, str):
            raise ValueError("a name is a string, and %r is not" % (name,))
    return tuple(value)


def _library(value):
    """The customer's library, or the mistake: this stage reads it and nothing else."""
    if not isinstance(value, corpus.Corpus):
        raise ValueError("the corpus is a %s, not a Corpus" % (type(value).__name__,))
    return value


def _meter(value):
    """The customer's meter, or the mistake: a cost is only ever its own delta."""
    if not isinstance(value, meter.Meter):
        raise ValueError("the meter is a %s, not a Meter" % (type(value).__name__,))
    return value


def _index(value):
    """The index the loops search, or the mistake naming what arrived."""
    if not isinstance(value, stage_03.Index):
        raise ValueError("the index is a %s, not an Index" % (type(value).__name__,))
    return value


def _question(library, qid):
    """The customer's own question record for `qid`, or the mistake naming it."""
    for question in library.questions:
        if question["qid"] == qid:
            return question
    raise ValueError("failure row answers question %r, which the corpus does not hold"
                     % (qid,))


def _clause_of(chunk_id, doc):
    """The clause number `chunk_id` names in `doc`, or the mistake naming both."""
    prefix = doc + ":"
    if not chunk_id.startswith(prefix):
        raise ValueError("chunk %r is not a chunk of document %r" % (chunk_id, doc))
    return chunk_id[len(prefix):]


def _evidence(failure):
    """The seven fields `diagnose` decides from, each checked, and never `stage`."""
    record = _mapping(failure, "failure row")
    for field in EVIDENCE_FIELDS:
        _field(record, field, "failure row")
    fid = _text(record["fid"], "the failure's fid")
    if not isinstance(record["answer_ok"], bool):
        raise ValueError("failure row %r answers %r, not a bool"
                         % (fid, record["answer_ok"]))
    return {"fid": fid,
            "qid": _text(record["qid"], "the failure's qid"),
            "chunks": _names(record["chunks"], "the failure's chunks"),
            "retrieved": _names(record["retrieved"], "the failure's retrieved"),
            "kept": _whole(record["kept"], "the failure's kept"),
            "cited": _names(record["cited"], "the failure's cited"),
            "answer_ok": record["answer_ok"]}


def _diagnoses(diagnoses):
    """The diagnosis rows, each one a `DIAGNOSIS_KEYS` record of a known stage."""
    if not isinstance(diagnoses, (tuple, list)):
        raise ValueError("the diagnoses are a tuple of rows, not %r" % (diagnoses,))
    rows = []
    for diagnosis in diagnoses:
        record = _mapping(diagnosis, "diagnosis row")
        for key in DIAGNOSIS_KEYS:
            _field(record, key, "diagnosis row")
        fid = _text(record["fid"], "the diagnosis's fid")
        stage = _text(record["stage"], "the diagnosis's stage")
        if stage not in FAILURE_STAGES:
            raise ValueError("diagnosis for %r blames stage %r, not one of %r"
                             % (fid, stage, FAILURE_STAGES))
        rows.append({"fid": fid, "stage": stage,
                     "reason": _text(record["reason"], "the diagnosis's reason")})
    return tuple(rows)


def _asked(library, questions):
    """The corpus's own records for the questions asked, in the order asked."""
    if not isinstance(questions, (tuple, list)):
        raise ValueError("the questions are a tuple of rows, not %r" % (questions,))
    held = {}
    for question in library.questions:
        held[question["qid"]] = question
    rows = []
    for question in questions:
        record = _mapping(question, "question row")
        qid = _text(_field(record, "qid", "question row"), "the question's qid")
        if qid not in held:
            raise ValueError("question %r is not one the corpus holds" % (qid,))
        rows.append(held[qid])
    return tuple(rows)


def _verdict(answered, gain_bp):
    """The checker's verdict: the sample floor first, then the noise bound.

    `beat-baseline` needs both the floor and `EVAL_MIN_GAIN_BP`; fewer answers
    than the floor is `worse` whatever the coverage says, and a coverage that is
    lower at all is `worse`; everything between is `no-better`.
    """
    if answered >= EVAL_MIN_SAMPLE and gain_bp >= EVAL_MIN_GAIN_BP:
        return "beat-baseline"
    if answered < EVAL_MIN_SAMPLE or gain_bp < 0:
        return "worse"
    return "no-better"


def diagnose(corpus, failure):
    """The DIAGNOSIS_KEYS row a failure's own evidence implies, never its label.

    The tree, in order: an answer that was right is `none`; a document whose
    clause index holds clauses the failure's chunks lacks is `chunk`; a question
    stage 5's own `ambiguous` calls ambiguous with none of its expected ids
    retrieved is `rewrite`; an expected id missing from the failure's retrieved
    hits is `retrieve`; one that came back at an index at or past `kept` is
    `rerank`; one that was kept and never cited is `ground`; and anything else
    is `answer`. The reason names the offender — the count, the chunk id, the
    rewrite kind, or the rank and the kept line.
    """
    library = _library(corpus)
    row = _evidence(failure)
    question = _question(library, row["qid"])
    if row["answer_ok"]:
        return {"fid": row["fid"], "stage": "none", "reason": "answer was right"}
    expected = question["expected"]
    if not expected:
        raise ValueError("failure row %r answers question %r, which expects no clause"
                         % (row["fid"], row["qid"]))
    doc = expected[0].split(":", 1)[0]
    numbers = [_clause_of(chunk, doc) for chunk in row["chunks"]]
    held = library.clause_index(doc)
    dropped = len([number for number in held if number not in numbers])
    if dropped:
        return {"fid": row["fid"], "stage": "chunk",
                "reason": "chunker dropped %d of %d clauses" % (dropped, len(held))}
    retrieved = row["retrieved"]
    if not [chunk for chunk in expected if chunk in retrieved]:
        kinds = tuple(fix["kind"] for fix in stage_05.ambiguous(library, question))
        if kinds:
            return {"fid": row["fid"], "stage": "rewrite",
                    "reason": "ambiguous %s never rewritten, and no expected clause "
                              "was retrieved" % (",".join(kinds),)}
    late = [chunk for chunk in expected if chunk not in retrieved]
    if late:
        return {"fid": row["fid"], "stage": "retrieve",
                "reason": "expected %s was not retrieved" % (late[0],)}
    kept = row["kept"]
    ranks = [(chunk, retrieved.index(chunk)) for chunk in expected
             if retrieved.index(chunk) >= kept]
    if ranks:
        return {"fid": row["fid"], "stage": "rerank",
                "reason": "expected %s ranked %d of kept %d"
                          % (ranks[0][0], ranks[0][1], kept)}
    cited = row["cited"]
    uncited = [chunk for chunk in expected
               if chunk in retrieved[:kept] and chunk not in cited]
    if uncited:
        return {"fid": row["fid"], "stage": "ground",
                "reason": "expected %s was retrieved and not cited" % (uncited[0],)}
    return {"fid": row["fid"], "stage": "answer",
            "reason": "cited %s and answered wrong" % (expected[0],)}


def distribution(diagnoses):
    """The counts, the fids by stage and the worst failing stage.

    The counts hold every stage in `FAILURE_STAGES`, zeros included; `by_stage`
    maps each of them to a sorted tuple of fids; `worst` is the non-`none` stage
    with the most failures, ties broken by `FAILURE_STAGES` order.
    """
    rows = _diagnoses(diagnoses)
    counts = {}
    by_stage = {}
    for stage in FAILURE_STAGES:
        counts[stage] = 0
        by_stage[stage] = []
    for row in rows:
        counts[row["stage"]] = counts[row["stage"]] + 1
        by_stage[row["stage"]].append(row["fid"])
    worst = None
    for stage in FAILURE_STAGES:
        if stage == "none":
            continue
        if worst is None or counts[stage] > counts[worst]:
            worst = stage
    return {"counts": counts,
            "by_stage": {stage: tuple(sorted(by_stage[stage]))
                         for stage in FAILURE_STAGES},
            "worst": worst}


def agreement(diagnoses, corpus):
    """How many of these diagnoses the customer's own labels confirm.

    `agree` the count, `disagree` a sorted tuple of the fids that differ, and
    `bp` the share in basis points over the diagnoses given.
    """
    library = _library(corpus)
    rows = _diagnoses(diagnoses)
    labels = {}
    for failure in library.failures:
        labels[failure["fid"]] = failure["stage"]
    agree = 0
    disagree = []
    for row in rows:
        if row["fid"] not in labels:
            raise ValueError("diagnosis for %r, which the corpus has no failure for"
                             % (row["fid"],))
        if row["stage"] == labels[row["fid"]]:
            agree += 1
        else:
            disagree.append(row["fid"])
    return {"agree": agree, "disagree": tuple(sorted(disagree)),
            "bp": agree * 10000 // len(rows) if rows else 0}


def eval_checker(index, corpus, questions, meter, limit, budget_cents, round_cap):
    """The checker's own report, and its verdict against the naive baseline.

    Runs the checked loop over the questions and the naive hybrid retrieval
    beside it: EVAL_KEYS with `answered` the non-abstaining answers, `hit_bp`
    the share of the questions' expected ids the answers cited,
    `unsupported_bp` the share of citations that were not expected,
    `abstained_correctly` the abstentions on questions whose expected ids were
    not all retrieved, `cost_cents` the meter's own delta, and `verdict` one of
    `beat-baseline`, `no-better` or `worse`.

    `budget_cents` is one question's budget and not the run's: the naive row is
    priced on the meter before the checked one starts, so the loop is handed the
    budget on top of what the meter already holds, exactly as stage 9 prices its
    own row. A question whose budget buys no round at all ran no round, carries
    no answer, and is neither answered nor a right abstention.
    """
    searched = _index(index)
    library = _library(corpus)
    charged = _meter(meter)
    limit = _whole(limit, "the limit")
    if limit < 1:
        raise ValueError("the limit is %d, not a count of hits" % (limit,))
    budget_cents = _whole(budget_cents, "the budget")
    if budget_cents < 0:
        raise ValueError("the budget is %d cents, not a budget" % (budget_cents,))
    round_cap = _whole(round_cap, "the round cap")
    if round_cap < 0:
        raise ValueError("the round cap is %d, not a cap" % (round_cap,))
    asked = _asked(library, questions)
    naive = stage_03.measure(searched, asked, limit, "hybrid")
    missed = naive["missed"]
    spent = charged.total_cents()
    answered = 0
    expected_ids = 0
    covered = 0
    citations = 0
    unsupported = 0
    right = 0
    for position, question in enumerate(asked):
        held = charged.total_cents()
        loop = stage_08.ask(searched, library, charged, question, position, limit,
                            held + budget_cents, round_cap)
        answer = loop["answer"]
        if answer is None:
            continue
        if answer["abstained"]:
            if question["qid"] in missed:
                right += 1
            continue
        answered += 1
        expected = question["expected"]
        cited = answer["citations"]
        expected_ids += len(expected)
        citations += len(cited)
        covered += len([chunk for chunk in expected if chunk in cited])
        unsupported += len([chunk for chunk in cited if chunk not in expected])
    cost = charged.total_cents() - spent
    return {"answered": answered,
            "hit_bp": covered * 10000 // expected_ids if expected_ids else 0,
            "unsupported_bp": unsupported * 10000 // citations if citations else 0,
            "abstained_correctly": right,
            "cost_cents": cost,
            "verdict": _verdict(answered, (covered * 10000 // expected_ids
                                           if expected_ids else 0) - naive["hit_bp"])}
