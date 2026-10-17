"""Agentic Retrieval From Scratch — stage 7: Grounded or abstain, and never a claim without a citation.

Six stages have produced the pieces of an answer and none of them has produced an
answer. The question was made unambiguous, chunks were ranked, a reranker earned
or lost its place, and stage 6 named every chunk that is stale, off-topic, in
conflict or unresolvable. What comes back from all of that is a list of
survivors, and this stage is the only one that turns survivals into something a
customer may read: an answer made of claims, each one tied to the span it came
from, or an abstention that says why it has nothing to say. There is no third
shape, and a scanner proves it.

The shape of an answer is the decision. The pipeline may quote and may not
invent, so a claim's `text` is the chunk's own text verbatim and its `cite` is
that chunk's id, and the answer's `citations` are those ids in the order the
claims are in — a citation list that has been sorted is a citation list that no
longer says which claim came from where. An answer that cannot do that does not
answer at all: `ABSTENTIONS` is a closed vocabulary of four reasons, and the
first one true of the run is the one reported, so two runs over one input never
disagree about why the pipeline stayed silent.

Grounding is the number that decides the commonest of those four. It is the share
of the query's **distinct** analyzed terms that the surviving chunks' texts
actually carry, in basis points — measured rather than felt, and measured over
the chunks that survived rather than over everything that was retrieved, because
the question is whether what the pipeline is about to quote can answer what was
asked. The comparison is *below* the minimum, so a run exactly at the minimum is
grounded: the threshold is a floor, and the reason a refusal prints names both
numbers so that an auditor can recompute the verdict instead of trusting it.

The scanner is the other half, and it is deliberately not a method of the answer.
`check_citations` reads **any** answer — one this stage built, one a caller typed,
one a later stage mangled — and reports what is wrong with it as data: a claim
whose cite is empty or absent from the citation list, a citation the input chunks
do not hold, a citation naming a clause the document prints twice, and an
abstention that carries claims anyway. `()` is what a clean answer scans to, and
that is the proof that the third shape does not exist.

    CLAIM_KEYS                                   the two fields of a claim, in order
    ANSWER_KEYS                                  the six fields of an answer, in order
    ABSTENTIONS                                  the four reasons an answer abstains for, in precedence order
    CITATION_PROBLEMS                            the four faults a scanner reports, in the order it reports them
    GROUNDING_MIN_BP                             the share of the query's terms a grounded answer has to carry
    grounding_bp(corpus, query, chunks)          -> the share, in basis points, of the query's terms the chunks carry
    answer(corpus, query, chunks, critiques, min_grounding_bp)   -> ANSWER_KEYS, claims or an abstention
    check_citations(answer, chunks)              -> the (problem, offender) pairs a scanner finds, in problem order

DESIGN DECISION — why is an answer a tuple of claims rather than one written
text?
Because a text is a claim nobody can check. The customer's auditors, and stages 8
to 10 after them, need to walk back from a sentence to the clause it came from,
and the only way that walk exists is if the drawing of the sentence — the claim's
`text` — is the span's own words rather than a paraphrase of them. Nothing in
this stage writes a word: a claim quotes a chunk and cites it, `citations` is
nothing but those ids in claim order, and an answer that would have to invent a
sentence to exist abstains instead. That is also why the claims are one per
surviving chunk rather than one per expected id: this stage answers from what
survived the critique, not from what the evaluation set believes.

DESIGN DECISION — why does an answer abstain rather than answer partly?
Because a partial answer is a false one. A pipeline that quotes the two clauses
it could ground and silently drops the third has told the customer that the third
does not exist, and there is no way for a reader to tell that apart from a
complete answer. So an answer is all of the survivors or none of them: the four
reasons in `ABSTENTIONS` are the only four things that can be true, they are
tested in the order they are written, and the reason is data the caller can
branch on rather than a sentence this stage made up.

DESIGN DECISION — why is `not-grounding` decided last, after `ambiguous-cite`?
Because a run that cannot cite what it found has a different problem from a run
whose survivors are too thin, and a caller fixing the pipeline needs to be told
which. The order is the order of certainty: nothing survived at all, then a
conflict no one resolved, then a surviving chunk whose id is printed twice in the
document and cannot be cited as if it were one, and only then the arithmetic of
grounding. Every one of those is a fact about the input, so reordering them would
change which fact the customer is told first — and a reason from a closed
vocabulary is only useful if the same input always answers with the same one.

DESIGN DECISION — why is grounding measured over the survivors rather than over
everything that was retrieved?
Because an answer quotes its survivors, and grounding is a statement about what
is about to be quoted. Measuring it over every retrieved hit would let a run
abstain for lack of grounding while holding the very chunk that answers the
question in its discard pile, and it would let a run claim to be grounded in a
chunk it never quotes. The number is recomputed the same way for the answer and
for the refusal, from the same chunk texts, so the reason a refused run prints
(`grounding 3200bp < 5000bp`) is a number the caller can recompute with the same
analyzer rather than a belief the stage wrote down.

DESIGN DECISION — why is the scanner a function over any answer rather than a
method of the answer?
Because the answers worth scanning are exactly the ones this stage did not
build. Stage 8 assembles a loop, stage 9 prices it, stage 10 holds it against the
customer's labelled failures, and each of them can hand back an answer that is
subtly wrong — a citation list sorted by a careless fold, a claim whose cite no
longer resolves after a rewrite, an abstention that kept its claims when the
reason changed. A scanner that only understood its own answer would agree with
itself by construction; a scanner that reads the four faults in
`CITATION_PROBLEMS` order, against the input chunks the answer cites, is a check
the rest of the course can lean on.

TODO: implement `grounding_bp`, `answer` and `check_citations` in this file:
grounding as the share of the query's distinct analyzed terms the surviving
chunks carry, the answer as claims that quote and cite or an abstention from the
pinned vocabulary decided in order, and the scanner as the four faults in
`CITATION_PROBLEMS` order.
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


def grounding_bp(corpus, query, chunks):
    """The share of the query's distinct analyzed terms that these chunks carry.

    `query` is the question's own text and `chunks` are the chunks an answer
    would quote; `corpus` is the library whose analyzer both are read with. The
    answer is basis points of the query's **distinct** terms — a term counted
    once however often the question repeats it — and `0` when the query has no
    terms at all, which is the only case in which the share is not defined.

    A `query` that is not a string is refused, naming what arrived: nothing else
    can be analyzed, and a stage that guessed would be inventing the ground it is
    measured against. The library's log is the record of the reading: one
    analysis of the query and one per chunk.
    """
    raise NotImplementedError("stage 7: implement grounding_bp()")


def answer(corpus, query, chunks, critiques, min_grounding_bp):
    """The `ANSWER_KEYS` record these survivors earn: claims, or an abstention.

    The survivors are stage 6's, taken from `critiques`; `chunks` is everything
    that was retrieved, so a surviving id can still be found in it. The
    abstention is decided in `ABSTENTIONS` order — nothing survived, then a
    conflict the critiques hold, then a surviving id the input prints twice, then
    `grounding_bp` below `min_grounding_bp` — and a run that does not abstain
    answers one claim per surviving chunk, in the survivors' order, quoting each
    chunk's own text and citing it, with `grounding_bp` recomputed over those
    same chunks. An abstention holds no claims, no citations and the reason it
    abstained for; the grounding it measured is reported in both cases, because
    it is a fact about the run rather than about the verdict.

    A minimum that is not a whole number is refused naming it, and so is a
    survivor whose chunk id the input chunks do not hold — a claim that cannot be
    traced back to a span is not a claim. The one reason that carries arithmetic
    is `not-grounding`: it is printed with both numbers, the share the survivors
    were measured at and the floor it missed, so the refusal is still the word
    from `ABSTENTIONS` and still a sum the caller can recompute.
    """
    raise NotImplementedError("stage 7: implement answer()")


def check_citations(answer, chunks):
    """The `(problem, offender)` pairs this answer's citations earn, in order.

    A scanner over **any** answer, not only one this stage built: `missing-cite`
    when a claim's `cite` is empty or absent from the answer's own `citations`,
    `unknown-cite` for a citation no chunk of `chunks` carries, `ambiguous-cite`
    for a citation whose id `chunks` holds more than once, and
    `abstained-with-claims` when an answer that abstained carries claims anyway.
    The pairs come back grouped by fault in `CITATION_PROBLEMS` order, and each
    fault's offenders in the order the answer names them; a clean answer scans to
    `()`.
    """
    raise NotImplementedError("stage 7: implement check_citations()")
