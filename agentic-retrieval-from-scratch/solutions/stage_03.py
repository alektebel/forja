"""Agentic Retrieval From Scratch — stage 3: Two scorers, and the fusion that has to beat both.

The library gives a corpus, a chunker already gave citable clauses, and this stage turns
the two into three ranked lists — BM25, dense, and the fusion of both — and then into a
verdict about which one the customer's own labelled questions prefer. Every score is an
integer and carries its own arithmetic in `why`, every tie is broken by the chunk's id,
and the index owns the one door through which the corpus is asked anything at all.
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


def _bm25_contribution(idf, tf, length, avg_len):
    """One term's BM25 share in the course's fixed point: integers, one order only.

    `idf` is in basis points and `tf` is the term's count in the chunk; `k1` and
    `b` are fixed points and `scale` is a whole score. The numerator multiplies,
    the denominator saturates the term frequency and normalises by the chunk's
    length, and the two integer divisions are applied in exactly this order.
    """
    k1 = BM25_K1_BP
    b = BM25_B_BP
    scale = SCORE_SCALE
    numerator = idf * tf * (k1 + scale) * scale
    denominator = tf * scale + k1 * (scale - b + b * length * scale // avg_len)
    return numerator // denominator // scale


def _ranks(hits):
    """The 1-based rank of every chunk a ranking holds: the first occurrence wins."""
    found = {}
    for rank, hit in enumerate(hits, start=1):
        found.setdefault(hit["chunk"], rank)
    return found


def _rank(hits, limit):
    """The hits by score descending, ties by chunk id ascending, cut to `limit`.

    One entry per chunk id: the corpus prints one clause number twice, and a
    ranking is a function from a chunk to its place, so where two chunks share an
    id the better-scoring one represents it and the other is dropped.
    """
    ordered = sorted(hits, key=lambda hit: (-hit["score"], hit["chunk"]))
    kept = []
    seen = set()
    for hit in ordered:
        if hit["chunk"] not in seen:
            seen.add(hit["chunk"])
            kept.append(hit)
    return tuple(kept[:limit])


class Index:
    """The chunks, their counts, their vectors and the postings between them.

    Built once by `build(corpus)`: every document goes through stage 1's chunker,
    every chunk's text is analyzed once and embedded once, and the term counts,
    lengths, vectors and postings are the index's own from then on. `terms` and
    `vector` are the index's only door to the corpus, so `analysis()["corpus_asks"]`
    is the tally of what it asked.
    """

    def __init__(self, corpus, chunks):
        """Hold a corpus and its chunks, and build everything a scorer needs."""
        self._corpus = corpus
        self._chunks = tuple(chunks)
        self._first = {}
        self._counts = []
        self._lengths = []
        self._vectors = []
        self._places = {}
        self._asks = 0
        for position, chunk in enumerate(self._chunks):
            identify = stage_01.chunk_id(chunk)
            if identify not in self._first:
                self._first[identify] = position
            tokens = self.terms(chunk["text"])
            tally = {}
            for token in tokens:
                tally[token] = tally.get(token, 0) + 1
            self._counts.append(tally)
            self._lengths.append(len(tokens))
            self._vectors.append(self.vector(chunk["text"]))
            for token in tally:
                self._places.setdefault(token, []).append(position)
        self._postings = dict((term, tuple(places))
                              for term, places in self._places.items())

    @classmethod
    def build(cls, corpus):
        """The index over every chunk of every document of `corpus`, in order."""
        chunks = []
        for document in corpus.documents:
            parsed, _problems = stage_01.chunk(document)
            chunks.extend(parsed)
        return cls(corpus, chunks)

    @property
    def corpus(self):
        """The corpus this index was built from, for a caller with none in hand."""
        return self._corpus

    @property
    def chunks(self):
        """Every chunk of every document, in document order."""
        return self._chunks

    def of(self, chunk_id):
        """The chunk record `chunk_id` names, or `None` when the index holds none."""
        position = self._first.get(chunk_id)
        if position is None:
            return None
        return self._chunks[position]

    def terms(self, text):
        """The corpus's analyzer over `text`, and one ask the index made."""
        self._asks = self._asks + 1
        return self._corpus.terms(text)

    def vector(self, text):
        """The corpus's embedder over `text`, and one ask the index made."""
        self._asks = self._asks + 1
        return self._corpus.embed(text)

    def lexical(self, query, limit):
        """The BM25 ranking of this index's chunks for `query`, cut to `limit`."""
        return bm25(self, query, limit)

    def dense(self, query, limit):
        """The dot-product ranking of this index's chunks for `query`."""
        return dense(self, query, limit)

    def fused(self, query, limit):
        """The reciprocal rank fusion of this index's two rankings of `query`."""
        return fuse(self.lexical(query, limit), self.dense(query, limit), limit)

    def analysis(self):
        """The index's own counts: `chunks`, `terms`, `postings`, `embeds`, `corpus_asks`."""
        return {"chunks": len(self._chunks), "terms": len(self._postings),
                "postings": sum(len(ids) for ids in self._postings.values()),
                "embeds": len(self._vectors), "corpus_asks": self._asks}

    def _average(self):
        """The average chunk length, at least 1 so the divisor is never zero."""
        return max(1, sum(self._lengths) // len(self._chunks))


def bm25(index, query, limit):
    """The BM25 ranking of `index`'s chunks for the query's text, cut to `limit`.

    Only chunks holding at least one of the query's distinct terms score; each
    contributes one pair, so `score` is the sum of `why`, and `why` is sorted by
    term. The order is by score descending and then by chunk id ascending.
    """
    wanted = tuple(dict.fromkeys(index.terms(query)))
    avg_len = index._average()
    held = {}
    for term in wanted:
        places = index._postings.get(term)
        if not places:
            continue
        idf = index.corpus.idf(term)
        for position in places:
            length = index._lengths[position]
            value = _bm25_contribution(idf, index._counts[position][term], length,
                                       avg_len)
            held.setdefault(position, []).append((term, value))
    hits = []
    for position, pairs in held.items():
        why = tuple(sorted(pairs))
        hits.append({"chunk": stage_01.chunk_id(index._chunks[position]),
                     "score": sum(value for _, value in why), "why": why})
    return _rank(hits, limit)


def dense(index, query, limit):
    """The dot-product ranking of `index`'s chunks for `query`, cut to `limit`.

    Every chunk scores, because a unit-scaled vector is comparable with every
    other; the score is the dot product in the scale's own fixed point and `why`
    keeps both the `dot` and the `scale` it is read in.
    """
    vector = index.vector(query)
    hits = []
    for position in range(len(index._vectors)):
        dot = sum(a * b for a, b in zip(vector, index._vectors[position]))
        hits.append({"chunk": stage_01.chunk_id(index._chunks[position]),
                     "score": dot // 100,
                     "why": (("dot", dot),
                             ("scale", corpus.VECTOR_SCALE * corpus.VECTOR_SCALE))})
    return _rank(hits, limit)


def fuse(lexical, dense, limit):
    """The reciprocal rank fusion of two rankings of the same query.

    Each list contributes a 1-based rank and a chunk's score is the sum over the
    lists it appears in of the fixed point divided by the rank constant plus the
    rank; `why` records both ranks, zero where the chunk is absent from a list.
    """
    ranks = {"dense": _ranks(dense), "lexical": _ranks(lexical)}
    hits = []
    for identify in dict.fromkeys([hit["chunk"] for hit in lexical]
                                  + [hit["chunk"] for hit in dense]):
        here = (ranks["dense"].get(identify, 0), ranks["lexical"].get(identify, 0))
        score = sum(SCORE_SCALE // (RRF_K + rank) for rank in here if rank)
        hits.append({"chunk": identify, "score": score,
                     "why": (("dense", here[0]), ("lexical", here[1]),
                             ("rrf", score))})
    return _rank(hits, limit)


def search(index, query, limit, mode):
    """The ranking `mode` asks for: `"lexical"`, `"dense"` or `"hybrid"`."""
    if mode == "lexical":
        return index.lexical(query, limit)
    if mode == "dense":
        return index.dense(query, limit)
    if mode == "hybrid":
        return index.fused(query, limit)
    raise ValueError("stage 3: %r is not one of the search modes %r"
                     % (mode, SEARCH_MODES))


def measure(index, questions, limit, mode):
    """How one mode does over the customer's labelled questions.

    `answered` counts the questions whose every expected chunk id came back
    within `limit`; `hit_bp` is the expected ids retrieved over all expected ids,
    in basis points, zero when there are none; `missed` is the sorted qids that
    missed at least one expected id.
    """
    answered = 0
    expected_total = 0
    found_total = 0
    missed = []
    for question in questions:
        expected = tuple(question["expected"])
        found = set(hit["chunk"]
                    for hit in search(index, question["text"], limit, mode))
        present = [clause for clause in expected if clause in found]
        expected_total = expected_total + len(expected)
        found_total = found_total + len(present)
        if len(present) == len(expected):
            answered = answered + 1
        else:
            missed.append(question["qid"])
    if expected_total:
        hit_bp = 10000 * found_total // expected_total
    else:
        hit_bp = 0
    return {"mode": mode, "answered": answered, "hit_bp": hit_bp,
            "missed": tuple(sorted(missed))}


def pick(index, questions, limit):
    """The best of the three modes, and whether it beat the runner-up at all."""
    rows = tuple(measure(index, questions, limit, mode) for mode in SEARCH_MODES)
    order = sorted(rows, key=lambda row: (-row["hit_bp"], -row["answered"],
                                          SEARCH_MODES.index(row["mode"])))
    best = order[0]
    runner_up = order[1]
    if best["hit_bp"] - runner_up["hit_bp"] < NO_DIFFERENCE_BP:
        verdict = "no-difference"
    else:
        verdict = best["mode"]
    return {"best": best["mode"], "rows": rows, "verdict": verdict}
