"""stage_07.py — grounded or abstain, and never a claim without a citation.

Stage 6 hands back survivors, and this is the stage that turns them into the only
two things a pipeline is allowed to say: an answer made of claims, each one the
verbatim text of the chunk it came from and the id of that chunk, or an
abstention with a reason from `ABSTENTIONS`. Nothing here writes a sentence, and
nothing here answers partly: an answer is every survivor or none of them, which
is why the abstention is decided in the pinned order — nothing survived, then a
conflict no one resolved, then a surviving id the input prints twice, and only
then the arithmetic of grounding.

Grounding is the share of the query's distinct analyzed terms that the surviving
chunks carry, in basis points, read with the library's own analyzer and reported
for the abstentions too, so that the reason a refusal prints is a number the
caller can recompute. `check_citations` is deliberately not a method of the
answer: it scans any answer at all, in `CITATION_PROBLEMS` order, which is what
makes "there is no third shape" a fact about the course rather than a promise.
"""

from corpus import CorpusError

from stage_01 import chunk_id

from stage_06 import survivors

CLAIM_KEYS = ("text", "cite")

ANSWER_KEYS = ("query", "claims", "citations", "grounding_bp", "abstained",
               "reason")

ABSTENTIONS = ("nothing-survived", "conflict-unresolved", "not-grounding",
               "ambiguous-cite")

CITATION_PROBLEMS = ("missing-cite", "unknown-cite", "ambiguous-cite",
                     "abstained-with-claims")

GROUNDING_MIN_BP = 5000

_FULL_BP = 10000

_NOT_GROUNDING = "not-grounding: grounding %dbp < %dbp"


def _text(value, what):
    """`value` as a string, or the refusal naming what arrived instead."""
    if not isinstance(value, str):
        raise CorpusError("%s is %r, not a string" % (what, value))
    return value


def _whole(value, what):
    """`value` as a whole number, or the refusal naming it — a `bool` is not one."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CorpusError("%s is %r, not a whole number" % (what, value))
    return value


def _mapping(value, what):
    """`value` as a mapping, or the refusal naming what arrived instead."""
    if not isinstance(value, dict):
        raise CorpusError("%s is %r, not a mapping" % (what, value))
    return value


def _record(value, what):
    """`value` as a sequence of records, or the refusal naming what arrived."""
    if isinstance(value, (str, bytes, dict)) or not hasattr(value, "__iter__"):
        raise CorpusError("%s is %r, not a sequence" % (what, value))
    return tuple(value)


def _span(chunk):
    """A chunk record's own text — the words a claim is allowed to quote."""
    record = _mapping(chunk, "a chunk")
    text = record.get("text")
    if not isinstance(text, str):
        raise CorpusError("a chunk's text is %r, not a string" % (text,))
    return text


def _distinct(terms):
    """The terms once each, in the order they first appeared."""
    found = []
    for term in terms:
        if term not in found:
            found.append(term)
    return tuple(found)


def grounding_bp(corpus, query, chunks):
    """The share of the query's distinct analyzed terms that these chunks carry.

    `query` is the question's own text and `chunks` are the chunks an answer
    would quote; `corpus` is the library whose analyzer both are read with. The
    answer is basis points of the query's **distinct** terms — a term the
    question repeats is one term — and `0` when the query has no terms at all,
    which is the only case in which the share is not defined.

    A `query` that is not a string is refused, naming what arrived, before the
    library is asked anything: the analyzer is the ground this number is measured
    against, and a stage that guessed at it would be inventing that ground.
    """
    wanted = _distinct(corpus.terms(_text(query, "the query")))
    spans = _record(chunks, "the chunks")
    if not wanted:
        return 0
    held = []
    for chunk in spans:
        held.extend(corpus.terms(_span(chunk)))
    present = len([term for term in wanted if term in held])
    return present * _FULL_BP // len(wanted)


def answer(corpus, query, chunks, critiques, min_grounding_bp):
    """The `ANSWER_KEYS` record these survivors earn: claims, or an abstention.

    The survivors are stage 6's, taken from `critiques`; `chunks` is everything
    that was retrieved, so a surviving id can still be found in it. The
    abstention is decided in `ABSTENTIONS` order — nothing survived, then a
    conflict the critiques hold, then a surviving id the input prints twice, then
    this stage's own grounding below `min_grounding_bp` — and a run that does not
    abstain answers one claim per surviving chunk, in the survivors' order,
    quoting each chunk's own text and citing it. An abstention holds no claims,
    no citations and the reason it abstained for; the grounding is measured
    either way, because it is a fact about the run rather than about the verdict.

    A minimum that is not a whole number is refused naming it, and so is a
    survivor whose chunk id the input chunks do not hold: a claim that cannot be
    traced back to a span it was given is not a claim. The one reason that
    carries arithmetic is `not-grounding`, and it is printed as the reason and the
    two numbers it was decided on — `"not-grounding: grounding 3200bp < 5000bp"` —
    so a refusal is a member of the vocabulary and a sum a caller can recompute.
    """
    text = _text(query, "the query")
    floor = _whole(min_grounding_bp, "the minimum grounding")
    spans = _record(chunks, "the chunks")
    rows = _record(critiques, "the critiques")
    held = []
    first = {}
    for chunk in spans:
        cid = chunk_id(chunk)
        held.append(cid)
        if cid not in first:
            first[cid] = chunk
    survived = survivors(rows)
    conflicted = any(row["verdict"] == "conflicting" for row in rows)
    repeated = [cid for cid in survived if held.count(cid) > 1]
    picked = []
    for cid in survived:
        chunk = first.get(cid)
        if chunk is None:
            raise CorpusError("survivor %r is not among the chunks this answer was "
                              "given" % (cid,))
        picked.append(chunk)
    grounding = grounding_bp(corpus, text, picked)
    reason = None
    if not survived:
        reason = "nothing-survived"
    elif conflicted:
        reason = "conflict-unresolved"
    elif repeated:
        reason = "ambiguous-cite"
    elif grounding < floor:
        reason = _NOT_GROUNDING % (grounding, floor)
    if reason is not None:
        return {"query": text, "claims": (), "citations": (),
                "grounding_bp": grounding, "abstained": True, "reason": reason}
    claims = tuple({"text": _span(chunk), "cite": chunk_id(chunk)}
                   for chunk in picked)
    citations = tuple(claim["cite"] for claim in claims)
    return {"query": text, "claims": claims, "citations": citations,
            "grounding_bp": grounding, "abstained": False, "reason": None}


def check_citations(answer, chunks):
    """The `(problem, offender)` pairs this answer's citations earn, in order.

    A scanner over **any** answer, not only one this stage built: `missing-cite`
    when a claim's `cite` is empty or absent from the answer's own `citations`,
    `unknown-cite` for a citation no chunk of `chunks` carries, `ambiguous-cite`
    for a citation whose id `chunks` holds more than once, and
    `abstained-with-claims` when an answer that abstained carries claims anyway.
    The pairs come back grouped by fault in `CITATION_PROBLEMS` order, each
    fault's offenders in the order the answer names them, and a clean answer
    scans to `()`.
    """
    record = _mapping(answer, "the answer")
    held = [chunk_id(chunk) for chunk in _record(chunks, "the chunks")]
    claims = _record(record.get("claims") or (), "the claims")
    citations = _record(record.get("citations") or (), "the citations")
    found = {"missing-cite": [], "unknown-cite": [], "ambiguous-cite": [],
             "abstained-with-claims": []}
    for claim in claims:
        cite = _mapping(claim, "a claim").get("cite")
        if not isinstance(cite, str) or cite == "" or cite not in citations:
            found["missing-cite"].append(cite if isinstance(cite, str) else "")
    for citation in citations:
        if citation not in held:
            found["unknown-cite"].append(citation)
        elif held.count(citation) > 1:
            found["ambiguous-cite"].append(citation)
    if record.get("abstained") and claims:
        reason = record.get("reason")
        found["abstained-with-claims"].append(reason if isinstance(reason, str)
                                              else "")
    pairs = []
    for problem in CITATION_PROBLEMS:
        for offender in found[problem]:
            pairs.append((problem, offender))
    return tuple(pairs)
