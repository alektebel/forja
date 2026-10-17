"""Agentic Retrieval From Scratch — stage 6: The critique of what came back.

Retrieval hands back chunks; this stage is the one that refuses to trust them. A
chunk from a document the estate has already replaced, a chunk whose own
cross-reference points at a clause its document never held, a chunk that disagrees
with another chunk in the same answer about the same subject, and a chunk with
nothing to do with the question are each named here — with the offender they are
against — before stage 7 is allowed to write a sentence out of any of them. The
verdict is data: one row per chunk that came back, in the order it came back, so the
pipeline that follows is held to what it retrieved rather than to what it says about
itself.

The order is the whole decision. Supersession is a fact about the document, a dangling
reference is a fact about the chunk's own text, a conflict is a fact about the other
chunks that came back with it, and only then is the question's own vocabulary
consulted. A chunk that is true of more than one of those is named by the first thing
true of it in `VERDICT_ORDER` and never by a later one, because a caller reading
`stale` must not be told `off-topic` instead.

Surface:

    CRITIQUE_KEYS      the four fields of one row: chunk, verdict, reason, against
    CRITIQUE_VERDICTS  the closed vocabulary a verdict is drawn from
    VERDICT_ORDER      the priority the verdicts are decided in, first true wins
    critique           chunks, query, corpus → one row per chunk, in input order
    survivors          the `supported` chunk ids, in the order the rows arrived
    by_verdict         every verdict of the vocabulary → its chunk ids, sorted

DESIGN DECISION — why is the order of the verdicts a constant rather than a chain of
`if`s written where they happen to fall? Because the order *is* this stage's answer to
the item it exists for: a chunk can be stale and off-topic at once, and which of the
two the caller is told is a decision, not an accident of how the comparisons were
laid out. `VERDICT_ORDER` is that decision written down and pinned, so a later
refactor that reorders the checks fails rather than silently changing a verdict.

DESIGN DECISION — why is a conflict measured against the chunk's *input* rather than
against the whole corpus? Because the critique is about what came back for *this*
question. Two clauses of the estate may share a subject and never both be retrieved,
and calling that a conflict would make every answer conflict with documents that are
not in it. The subject tag is the library's own label, but the disagreement is a fact
only about the chunks this call was handed.

DESIGN DECISION — why is `against` a field of its own rather than prose inside
`reason`? Because a reason is for a person and the offender is data: the stages that
follow must know what a chunk was judged against — the superseding document, the
missing clause, the other chunk — without parsing a sentence. A row that names its
offender only in its `reason` is a row nothing downstream can act on.

DESIGN DECISION — why does a dangling reference resolve against the document's own
clause index rather than against the chunks that came back? Because the fault is the
chunk's, not the retrieval's: a clause its document never held is broken text, while a
clause the document holds and the retrieval merely missed is a retrieval miss, which
belongs to the loop and not here. Reading the dangling case off the retrieved set
would blame the wrong stage for the same failure.

TODO: implement `critique`, `survivors` and `by_verdict` in this file: the verdict
over each retrieved chunk and the offender it is against, the ids that survived it in
the order the rows arrived, and the whole vocabulary's chunk ids.
"""

import stage_01

CRITIQUE_KEYS = ("chunk", "verdict", "reason", "against")

CRITIQUE_VERDICTS = ("supported", "conflicting", "stale", "off-topic", "unresolvable")

VERDICT_ORDER = ("stale", "unresolvable", "conflicting", "off-topic", "supported")


def critique(chunks, query, corpus):
    """One `CRITIQUE_KEYS` row per chunk, in input order: the first fault true of it.

    The verdicts are decided in `VERDICT_ORDER`:

    `stale` when the chunk's own document has been superseded, the reason naming the
    document that superseded it; `unresolvable` when the chunk carries a reference to
    a clause its own document's index does not hold, the reason naming that clause;
    `conflicting` when another chunk of the same input shares the chunk's subject tag
    and carries different text, the reason naming that chunk; `off-topic` when none of
    the query's distinct analyzed terms appears in the chunk's text, the reason naming
    the first term the query's own analyzer order makes absent; and `supported`
    otherwise, the reason counting the query's terms the chunk does carry. A call
    with no chunks answers `()`.

    `query` is the question's own text, analyzed through `corpus.terms`; a query with
    no terms at all leaves every chunk `supported`. A chunk that is not one of the
    chunk records, or one whose document the corpus does not hold, is refused naming
    the offender.
    """
    raise NotImplementedError("stage 6: implement critique()")


def survivors(critiques):
    """The `supported` chunk ids of `critiques`, in the order the rows arrived."""
    raise NotImplementedError("stage 6: implement survivors()")


def by_verdict(critiques):
    """Every verdict of `CRITIQUE_VERDICTS` → its chunk ids, each sorted by id.

    A verdict no row carries is present with an empty tuple, so a caller may index
    the report by verdict without first checking whether the run happened to produce
    it, and the dict's own order is the vocabulary's.
    """
    raise NotImplementedError("stage 6: implement by_verdict()")
