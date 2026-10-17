"""Agentic Retrieval From Scratch — stage 6: The critique of what came back.

The library says which clause is superseded, which clauses share a subject and what a
clause's own words are; this stage turns those facts into a verdict about the chunks
that came back, and a verdict is data. Each row names the chunk, the verdict, a reason
and the offender the verdict is against, and the offender is a field rather than a
sentence because the stages that follow have to act on it. The decisions are made in
`VERDICT_ORDER`, first true wins, so a chunk that is stale and off-topic at once is
reported as `stale` for every caller on every run.
"""

import stage_01

CRITIQUE_KEYS = ("chunk", "verdict", "reason", "against")

CRITIQUE_VERDICTS = ("supported", "conflicting", "stale", "off-topic", "unresolvable")

VERDICT_ORDER = ("stale", "unresolvable", "conflicting", "off-topic", "supported")

_FIELDS = ("doc", "clause", "text", "refs")


def _records(chunks):
    """The chunk records of `chunks`, or the shape this stage will not accept."""
    if not isinstance(chunks, (tuple, list)):
        raise ValueError("stage 6: chunks is a %s, not a tuple of chunk records"
                         % (type(chunks).__name__,))
    records = []
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise ValueError("stage 6: %r is not a chunk record" % (chunk,))
        for field in _FIELDS:
            if field not in chunk:
                raise ValueError("stage 6: the chunk %r carries no %r"
                                 % (chunk.get("clause"), field))
        records.append(chunk)
    return tuple(records)


def _distinct(terms):
    """The analyzer's terms with each kept once, in the order the analyzer gave them."""
    found = {}
    for term in terms:
        found[term] = None
    return tuple(found)


def _conflict(records, tags, position):
    """The id of the first other input chunk that shares this chunk's tag and disagrees.

    `None` when no other chunk of the input shares the subject tag or when every chunk
    that does carries the same text — an equal text is a repetition, not a conflict.
    """
    chunk = records[position]
    tag = tags.get(stage_01.chunk_id(chunk))
    for other in range(len(records)):
        if other == position:
            continue
        if tags.get(stage_01.chunk_id(records[other])) == tag and \
                records[other]["text"] != chunk["text"]:
            return stage_01.chunk_id(records[other])
    return None


def _terms_present(words, qterms):
    """How many of the query's distinct terms the chunk carries, and the first absent."""
    present = 0
    absent = None
    for term in qterms:
        if term in words:
            present += 1
        elif absent is None:
            absent = term
    return present, absent


def critique(chunks, query, corpus):
    """One `CRITIQUE_KEYS` row per chunk, in input order: the first fault true of it.

    The verdicts are decided in `VERDICT_ORDER`: `stale` when the chunk's own document
    has been superseded, the row against the document that superseded it;
    `unresolvable` when the chunk carries a reference to a clause its own document's
    index does not hold, the row against that clause; `conflicting` when another chunk
    of the input shares the chunk's subject tag and carries different text, the row
    against that chunk; `off-topic` when none of the query's distinct analyzed terms
    appears in the chunk's text, the reason naming the first term the query's own
    analyzer order makes absent; and `supported` otherwise, the reason counting the
    query's terms the chunk does carry.

    `query` is the question's own text, analyzed through `corpus.terms`; a query with
    no terms at all leaves every chunk `supported`, and a call with no chunks answers
    `()`. A chunk that is not one of the chunk records, or one whose document the
    corpus does not hold, is refused naming the offender.
    """
    records = _records(chunks)
    if not records:
        return ()
    qterms = _distinct(corpus.terms(query))
    tags = corpus.subjects()
    rows = []
    for position, chunk in enumerate(records):
        identity = stage_01.chunk_id(chunk)
        document = corpus.document(chunk["doc"])
        verdict = None
        against = None
        reason = None
        if document["superseded_by"] is not None:
            verdict = "stale"
            against = document["superseded_by"]
            reason = "superseded by %s" % (against,)
        else:
            held = corpus.clause_index(chunk["doc"])
            for ref in chunk["refs"]:
                if ref not in held:
                    verdict = "unresolvable"
                    against = ref
                    reason = "dangling ref %s" % (ref,)
                    break
            if verdict is None:
                against = _conflict(records, tags, position)
                if against is not None:
                    verdict = "conflicting"
                    reason = "contradicts %s" % (against,)
            if verdict is None:
                present, absent = _terms_present(set(corpus.terms(chunk["text"])),
                                                 qterms)
                if qterms and present == 0:
                    verdict = "off-topic"
                    reason = "no query term: %s" % (absent,)
                else:
                    verdict = "supported"
                    reason = "%d query terms present" % (present,)
        rows.append({"chunk": identity, "verdict": verdict, "reason": reason,
                     "against": against})
    return tuple(rows)


def survivors(critiques):
    """The `supported` chunk ids of `critiques`, in the order the rows arrived."""
    return tuple(row["chunk"] for row in critiques if row["verdict"] == "supported")


def by_verdict(critiques):
    """Every verdict of `CRITIQUE_VERDICTS` → its chunk ids, each sorted by id.

    A verdict no row carries is present with an empty tuple, so the report may be
    indexed by verdict without first asking whether the run produced one, and the
    dict's own order is the vocabulary's.
    """
    grouped = dict((verdict, []) for verdict in CRITIQUE_VERDICTS)
    for row in critiques:
        grouped[row["verdict"]].append(row["chunk"])
    return dict((verdict, tuple(sorted(grouped[verdict])))
                for verdict in CRITIQUE_VERDICTS)
