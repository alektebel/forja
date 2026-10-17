"""Agentic Retrieval From Scratch — stage 3: Two scorers, and the fusion that has to beat both.

The customer's library already holds an analyzer, an inverse document frequency and a
unit-scaled vector, and it will not tell you which of the three modes to run: that is
the decision this stage exists to make. So the stage builds one index over the chunks
stage 1 produced, scores those chunks two different ways, fuses the two rankings, and
then answers the only question that matters — *which mode does the customer's own
labelled evaluation set prefer?* — as data rather than as an opinion about embeddings.

The index is the stage's own record: it chunks every document with stage 1's chunker,
analyzes each chunk's text once, embeds each chunk's text once, and keeps the per-chunk
term counts, the chunk lengths, the term-to-chunk postings and the vectors. A hit is
not a number: it is the chunk, the score and the arithmetic that produced the score, so
a reader can recompute every ranking the index ever answers. That is the whole point of
a fixed point — a score whose explanation is exactly the terms that make it.

Two scorers, one vocabulary. BM25 is lexical: an inverse document frequency in basis
points multiplied by a term frequency saturated and length-normalised, all in integers,
so a rare term matters more, a repeated term matters less and less, and a long clause is
not punished for being long. Dense is a plain dot product: the library hands back
vectors of the same scale, so a similarity needs no division, no square root and no
float anywhere. Fusion is reciprocal rank fusion — ranks, not scores, because two
scorers have two different scales and only their order is comparable — and it is the
mode that has to beat both.

The last half is the measurement. `measure` runs a mode over the customer's sixteen
labelled questions and answers how many of them were fully retrieved, what share of the
expected clauses came back, and which questions missed. `pick` runs all three, names
the best and — this is the stage's verdict — says `"no-difference"` when the best beats
the runner-up by less than `NO_DIFFERENCE_BP`, because a mode that is not demonstrably
better is not better.

    HIT_KEYS                                     the three fields of a hit, in order
    MEASURE_KEYS                                 the four fields of a measurement, in order
    SEARCH_MODES                                 the three modes a search may run in
    BM25_K1_BP                                   the BM25 term-saturation fixed point
    BM25_B_BP                                    the BM25 length-normalisation fixed point
    RRF_K                                        the reciprocal rank fusion constant
    SCORE_SCALE                                  the fixed point a whole score is written in
    NO_DIFFERENCE_BP                             the gap below which two modes are the same
    Index                                        the chunks, their counts, their vectors and the postings
    Index.build(corpus)                          -> the index over every chunk of every document
    Index.corpus                                 the corpus this index was built from
    Index.chunks                                 every chunk of every document, in document order
    Index.of(chunk_id)                           -> the chunk record, or None
    Index.terms(text)                            -> the corpus's analyzer, and one ask it made
    Index.vector(text)                           -> the corpus's embedder, and one ask it made
    Index.lexical(query, limit)                  -> the BM25 ranking of hits
    Index.dense(query, limit)                    -> the dot-product ranking of hits
    Index.fused(query, limit)                    -> the fusion of this index's two rankings
    Index.analysis()                             -> the index's own counts
    bm25(index, query, limit)                    -> the lexical ranking of hits
    dense(index, query, limit)                   -> the dense ranking of hits
    fuse(lexical, dense, limit)                  -> the fused ranking of hits
    search(index, query, limit, mode)            -> the ranking the mode asked for
    measure(index, questions, limit, mode)       -> MEASURE_KEYS over the labelled set
    pick(index, questions, limit)                -> the best mode, or no difference

DESIGN DECISION — why does a hit carry its own arithmetic rather than a bare score?
Because a ranking nobody can recompute is a ranking nobody can check. A score is a
number the index chose, and the only honest defence of it is the terms that produced
it: `why` is a tuple of `(name, contribution)` pairs, sorted by name, and the score is
their sum. A reader, a check or a later stage can add them up and get the score back —
BM25's sum of per-term contributions, dense's single `dot` and the `scale` it is
measured against, the fusion's two ranks and the reciprocal-rank sum. A score with no
explanation is the first place a retrieval system starts lying.

DESIGN DECISION — why a fixed point instead of a float?
Because this course has no float and no logarithm anywhere, and a similarity has to be
an integer to be compared exactly. So a ratio is basis points, the BM25 parameters are
fixed points (`BM25_K1_BP = 120` is `k1` of one and two tenths), and the score is
computed by integer division in one order and only one order. Determinism is the
reason: two runs of one query must produce the same ranking and the same numbers, and a
threshold the caller never supplied must never decide anything.

DESIGN DECISION — why does the index embed and analyze, and `corpus_asks` count both?
Because the two scorers need the two things the library owns — the analyzer and the
embedder — and a stage that reached around the index into the corpus would have two
places to keep straight instead of one. The index is what the corpus was asked, so it is
what remembers being asked: `terms` and `vector` are the index's own door to the
library, each one ask it made, and `analysis()["corpus_asks"]` is the tally. A chunk's
vector is asked for once, when the index is built, because a chunk does not move; a
query's vector is asked for again on every search, because a query is not the index's
and pretending otherwise would hide a real cost.

DESIGN DECISION — why does fusion use ranks rather than scores?
Because the two scorers do not share a scale and never will: BM25's score is a sum of
basis-point contributions and dense's is a dot product of thousand-scale vectors, and a
sum of the two would let whichever scorer happens to produce larger numbers decide the
ranking. Reciprocal rank fusion throws the magnitudes away and keeps the only thing the
two lists can be compared on — position — so a chunk that ranks first in either list
contributes the same weight, a chunk in both lists contributes twice, and a chunk in
only one contributes once. `why` records both ranks (zero when the chunk is absent from
a list) so the fused score is exactly the sum of what the ranks say.

DESIGN DECISION — why is the choice of mode a measurement and not a preference?
Because "hybrid is better" is a claim about embeddings, and the customer paid for the
answer to a different question: which mode retrieves *their* labelled clauses. So the
stage does not assert it — it runs all three over `corpus.questions`, counts the
questions fully retrieved and the share of expected clauses found, and reports the best
one. And when the best beats the runner-up by less than `NO_DIFFERENCE_BP`, the verdict
is `"no-difference"`: a difference inside the noise is not a difference, and the honest
answer to "which of the three" is sometimes "it does not matter".

TODO: implement `Index`, `bm25`, `dense`, `fuse`, `search`, `measure` and `pick` in
this file: the index that owns its analyzer, its embedder and every chunk's counts and
vector; the two scorers, each scoring an integer and explaining it; the fusion that
keeps both; and the measurement against the customer's own labelled questions that
chooses between them.
"""

import corpus
import stage_01

HIT_KEYS = ("chunk", "score", "why")

MEASURE_KEYS = ("mode", "answered", "hit_bp", "missed")

SEARCH_MODES = ("lexical", "dense", "hybrid")

BM25_K1_BP = 120

BM25_B_BP = 75

RRF_K = 60

SCORE_SCALE = 10000

NO_DIFFERENCE_BP = 100


class Index:
    """The chunks, their counts, their vectors and the postings between them.

    `Index.build(corpus)` is the way one is made: it chunks every document with
    stage 1, analyzes and embeds each chunk's text once, and holds the index of
    term to chunks so a query only ever looks at the chunks a term can reach. The
    index also owns its own door to the library — `terms` and `vector` — so
    `analysis()["corpus_asks"]` is the index's own tally of what it asked.
    """

    def __init__(self, corpus, chunks):
        """Hold a corpus and its chunks: `build` is the interface, this is not."""
        raise NotImplementedError("stage 3: implement Index.__init__()")

    @classmethod
    def build(cls, corpus):
        """The index over every chunk of every document of `corpus`, in order.

        Each document goes through stage 1's chunker; each chunk's text is
        analyzed once and embedded once, and the term counts, the chunk lengths,
        the vectors and the postings are kept. The corpus's own analyzer and
        embedder are reached only through `terms` and `vector`.
        """
        raise NotImplementedError("stage 3: implement Index.build()")

    @property
    def corpus(self):
        """The corpus this index was built from, for a later stage with no corpus."""
        raise NotImplementedError("stage 3: implement Index.corpus()")

    @property
    def chunks(self):
        """Every chunk of every document, in document order."""
        raise NotImplementedError("stage 3: implement Index.chunks()")

    def of(self, chunk_id):
        """The chunk record `chunk_id` names, or `None` when the index holds none."""
        raise NotImplementedError("stage 3: implement Index.of()")

    def terms(self, text):
        """The corpus's analyzer over `text`, and one ask the index made."""
        raise NotImplementedError("stage 3: implement Index.terms()")

    def vector(self, text):
        """The corpus's embedder over `text`, and one ask the index made."""
        raise NotImplementedError("stage 3: implement Index.vector()")

    def lexical(self, query, limit):
        """The BM25 ranking of this index's chunks for `query`, cut to `limit`."""
        raise NotImplementedError("stage 3: implement Index.lexical()")

    def dense(self, query, limit):
        """The dot-product ranking of this index's chunks for `query`."""
        raise NotImplementedError("stage 3: implement Index.dense()")

    def fused(self, query, limit):
        """The reciprocal rank fusion of this index's two rankings of `query`."""
        raise NotImplementedError("stage 3: implement Index.fused()")

    def analysis(self):
        """The index's own counts: `chunks`, `terms`, `postings`, `embeds`, `corpus_asks`."""
        raise NotImplementedError("stage 3: implement Index.analysis()")


def bm25(index, query, limit):
    """The BM25 ranking of `index`'s chunks for the query's text, cut to `limit`.

    Only chunks holding at least one of the query's distinct terms score at all;
    each contributing term adds its own contribution, so `score` is the sum of the
    `why` pairs, which are sorted by term. The order is by score descending and
    then by chunk id ascending, so a tie is a fact about the ids and not about the
    order the postings happened to be built in.
    """
    raise NotImplementedError("stage 3: implement bm25()")


def dense(index, query, limit):
    """The dot-product ranking of `index`'s chunks for `query`, cut to `limit`.

    The vectors are unit-scaled, so the similarity is a plain dot product of the
    query's own vector and the chunk's, divided by the fixed point the scale is
    read in; the whole `dot` and the `scale` are kept in `why`, because a
    similarity that hides its own scale cannot be recomputed.
    """
    raise NotImplementedError("stage 3: implement dense()")


def fuse(lexical, dense, limit):
    """The reciprocal rank fusion of two rankings of the same query.

    Each list contributes a 1-based rank; a chunk's fused score is the sum over
    the lists it appears in of the fixed point divided by the rank constant plus
    the rank, so a chunk in both lists contributes twice and a chunk in one list
    contributes once. `why` records both ranks, zero where the chunk is absent.
    """
    raise NotImplementedError("stage 3: implement fuse()")


def search(index, query, limit, mode):
    """The ranking `mode` asks for: `"lexical"`, `"dense"` or `"hybrid"`.

    A mode that is not one of `SEARCH_MODES` is refused by name rather than
    quietly treated as one of the three.
    """
    raise NotImplementedError("stage 3: implement search()")


def measure(index, questions, limit, mode):
    """How one mode does over the customer's labelled questions.

    `answered` counts the questions whose every expected chunk id came back
    within `limit`; `hit_bp` is the expected ids retrieved over all expected ids,
    in basis points, zero when there are none; `missed` is the sorted qids that
    missed at least one expected id.
    """
    raise NotImplementedError("stage 3: implement measure()")


def pick(index, questions, limit):
    """The best of the three modes, and whether it beat the runner-up at all.

    One `MEASURE_KEYS` row per mode in `SEARCH_MODES` order; `best` the highest
    `hit_bp`, ties by `answered` and then by `SEARCH_MODES` order; `verdict` is
    the best mode's name, or `"no-difference"` when the best beats the runner-up
    by less than `NO_DIFFERENCE_BP`.
    """
    raise NotImplementedError("stage 3: implement pick()")
