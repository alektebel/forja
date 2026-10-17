"""Agentic Retrieval From Scratch — stage 5: The ambiguous question, rewritten and recorded.

Half of "the RAG is wrong" is the question. This stage is the three ways a
question hides its own subject — the pronoun that points back at the
conversation, the acronym only the customer's glossary spells out, and the short
question that leans on the turn before it — plus the two-hop question whose
answer sits one cross-reference away. Every fix is applied to the text the
earlier fixes produced and recorded with the kind, the text before, the text
after and why, so the sequence replays. The analyzer is the customer's
(`corpus.terms`) and the acronyms are the customer's (`corpus.glossary`):
nothing here invents a tokenization or an expansion the library does not hold.
"""

import corpus
import stage_01

_CORPUS_ERROR = corpus.CorpusError
_QUESTION_KEYS = corpus.QUESTION_KEYS

REWRITE_KEYS = ("kind", "before", "after", "why")

REWRITE_KINDS = ("pronoun", "acronym", "elliptical", "decomposition", "none")

PRONOUNS = ("he", "her", "hers", "him", "his", "i", "it", "its", "me", "mine",
            "my", "our", "ours", "she", "that", "their", "theirs", "them", "these",
            "they", "this", "those", "us", "we", "you", "your", "yours")

REFERENT_STOP = ("a", "about", "an", "and", "are", "as", "at", "be", "both", "but",
                 "by", "could", "did", "do", "does", "for", "from", "had", "has",
                 "have", "he", "her", "his", "i", "if", "in", "is", "it", "its",
                 "may", "me", "mention", "mentions", "might", "must", "my", "not",
                 "of", "on", "one", "only", "or", "our", "said", "say", "says",
                 "she", "so", "tell", "that", "the", "their", "them", "these",
                 "they", "this", "those", "to", "told", "us", "was", "we", "were",
                 "will", "with", "would", "you", "your")

QUESTION_STOP = ("a", "an", "and", "are", "as", "at", "be", "been", "by", "can",
                 "could", "did", "do", "does", "for", "from", "had", "has", "have",
                 "he", "her", "him", "his", "how", "i", "in", "is", "it", "its",
                 "may", "me", "might", "must", "my", "not", "of", "on", "or",
                 "our", "she", "should", "that", "the", "their", "them", "then",
                 "there", "these", "they", "this", "those", "to", "under", "us",
                 "was", "we", "were", "what", "when", "where", "which", "who",
                 "whom", "whose", "why", "will", "with", "would", "you", "your")

MIN_INTERROGATIVE_TERMS = 3

SUBSET_WORDS = 8


def _library(corpus):
    """The customer's library, or the mistake naming what arrived instead."""
    if not callable(getattr(corpus, "terms", None)) \
            or not isinstance(getattr(corpus, "glossary", None), dict):
        raise _CORPUS_ERROR("the corpus is a %s, and this stage asks a Corpus for "
                            "terms() and glossary" % (type(corpus).__name__,))
    return corpus


def _question(question):
    """The question record, or the mistake naming the record that arrived."""
    if not isinstance(question, dict):
        raise _CORPUS_ERROR("a question is a record of %s, and %r is a %s"
                            % (", ".join(_QUESTION_KEYS), question,
                               type(question).__name__))
    for key in _QUESTION_KEYS:
        if key not in question:
            raise _CORPUS_ERROR("the question %r carries no %r"
                                % (question.get("qid", question), key))
    return question


def _chunks(chunks):
    """The chunk tuple, or the mistake naming the chunk that is not a chunk."""
    if not isinstance(chunks, (tuple, list)):
        raise _CORPUS_ERROR("the chunks are a tuple of records, and %r is a %s"
                            % (chunks, type(chunks).__name__))
    for chunk in chunks:
        if not isinstance(chunk, dict):
            raise _CORPUS_ERROR("a chunk is a record of %s, and %r is a %s"
                                % (", ".join(stage_01.CHUNK_KEYS), chunk,
                                   type(chunk).__name__))
        for key in stage_01.CHUNK_KEYS:
            if key not in chunk:
                raise _CORPUS_ERROR("the chunk %r carries no %r"
                                    % (chunk.get("clause", chunk), key))
    return chunks


def _words(text):
    """The (start, end, token) spans of `text`'s whole words, in order."""
    spans = []
    index = 0
    while index < len(text):
        if not text[index].isalnum():
            index = index + 1
            continue
        end = index
        while end < len(text) and text[end].isalnum():
            end = end + 1
        spans.append((index, end, text[index:end]))
        index = end
    return tuple(spans)


def _replace(text, wanted, build):
    """`text` with every whole word whose lower case is in `wanted` replaced.

    Answers the new text and the tokens that were replaced, as they were written.
    A word no `wanted` entry names is left exactly as it came.
    """
    pieces = []
    matched = []
    cursor = 0
    for start, end, token in _words(text):
        if token.lower() not in wanted:
            continue
        pieces.append(text[cursor:start])
        pieces.append(build(token))
        matched.append(token)
        cursor = end
    if not matched:
        return text, ()
    pieces.append(text[cursor:])
    return "".join(pieces), tuple(matched)


def _referent(corpus, question):
    """The last run of the last turn's analyzer tokens, or `None`.

    `None` when there is no conversation, and `None` when every token of the last
    turn is a `REFERENT_STOP` word — a turn that names nothing names no referent.
    """
    conversation = question["conversation"]
    if not conversation:
        return None
    runs = []
    run = []
    for token in corpus.terms(conversation[-1]["text"]):
        if token in REFERENT_STOP:
            if run:
                runs.append(run)
                run = []
            continue
        run.append(token)
    if run:
        runs.append(run)
    if not runs:
        return None
    return " ".join(runs[-1])


def _acronyms(corpus):
    """The customer's own acronyms, exactly as the library keeps them.

    The library's keys are already the analyzer's folded form, so a token is
    matched as `token.lower()` and nothing here re-cases either half: the
    expansion goes into the text as the customer wrote it, and only the acronym
    keeps the case the question wrote it in.
    """
    return dict(corpus.glossary)


def _row(kind, before, after, why):
    """One `REWRITE_KEYS` record, in the keys' own order."""
    return {"kind": kind, "before": before, "after": after, "why": why}


def _fixes(corpus, question):
    """The text after every fix, and the row each fix recorded, in `REWRITE_KINDS` order.

    Every fix is applied to the text the fixes before it produced, so the rows
    replay in order; a question no fix applies to answers its own text and no
    rows at all.
    """
    text = question["text"]
    rows = []
    referent = _referent(corpus, question)
    acronyms = _acronyms(corpus)
    if referent is not None:
        before = text
        text, matched = _replace(text, tuple(PRONOUNS), lambda token: referent)
        if matched:
            rows.append(_row("pronoun", before, text,
                             "%s -> %s" % (matched[0].lower(), referent)))
    before = text
    text, matched = _replace(text, tuple(acronyms),
                             lambda token: "%s (%s)" % (token, acronyms[token.lower()]))
    if matched:
        rows.append(_row("acronym", before, text,
                         "%s -> %s" % (matched[0], acronyms[matched[0].lower()])))
    before = text
    content = tuple(term for term in corpus.terms(question["text"])
                    if term not in QUESTION_STOP)
    if len(content) < MIN_INTERROGATIVE_TERMS and referent is not None:
        text = text + " " + referent
        rows.append(_row("elliptical", before, text, "referent -> %s" % (referent,)))
    return text, tuple(rows)


def ambiguous(corpus, question):
    """One `REWRITE_KEYS` row per fix the question needs, in `REWRITE_KINDS` order.

    Answers `()` for a question that already says what it means: no pronoun to
    resolve, no acronym the customer's glossary can expand, and enough terms of
    its own to stand without the turn before it.
    """
    _library(corpus)
    _question(question)
    return _fixes(corpus, question)[1]


def rewrite(corpus, question):
    """The question's text after every fix, and the rows the fixes recorded.

    Answers `(question["text"], ())` when there was nothing to fix, and otherwise
    the text the last row's `after` holds together with every row, in order.
    """
    _library(corpus)
    _question(question)
    return _fixes(corpus, question)


def _clause_of(chunk_id):
    """The bare clause number a chunk id names."""
    return chunk_id.split(":", 1)[-1]


def _subset(corpus, text):
    """`text`'s first `SUBSET_WORDS` analyzer terms, joined with single spaces."""
    return " ".join(corpus.terms(text)[:SUBSET_WORDS])


def _chunk_of(chunks, wanted):
    """The chunk of `chunks` whose id is `wanted`, or `None`."""
    for chunk in chunks:
        if stage_01.chunk_id(chunk) == wanted:
            return chunk
    return None


def decompose(corpus, question, chunks):
    """The queries this question needs, in the order they must be searched.

    One entry when a single retrieval answers it; two when its expected ids are
    two hops apart — the question's own text, then the clause the first hop's
    chunk points at, cut to its first `SUBSET_WORDS` terms.
    """
    _library(corpus)
    _question(question)
    _chunks(chunks)
    expected = question["expected"]
    if len(expected) < 2:
        return (question["text"],)
    first = _chunk_of(chunks, expected[0])
    second = _chunk_of(chunks, expected[1])
    if first is None or second is None:
        return (question["text"],)
    if _clause_of(expected[1]) not in first["refs"]:
        return (question["text"],)
    return (question["text"], _subset(corpus, second["text"]))
