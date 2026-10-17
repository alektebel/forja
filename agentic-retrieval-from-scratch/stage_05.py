"""Agentic Retrieval From Scratch — stage 5: The ambiguous question, rewritten and recorded.

Half of "the RAG is wrong" is the question. A reader asks "Is its cap still in
force?" and the question no longer names what it is about: the pronoun points at
whatever the conversation last named, the acronym stands for something only the
customer's glossary spells out, and a question of two terms was never really
asked on its own — it leans on the turn before it. A two-hop question hides a
second subject behind a cross-reference: the clause that answers it says "see
4.2", and a retriever given only the question's own words never looks at 4.2.

This stage resolves each of those and, because a fix nobody recorded is a fix
nobody can price, repeat or debug, writes each one down as `REWRITE_KEYS`: the
kind of fix, the text before it, the text after it, and why. Stage 8 searches
what this stage recorded; stage 10 blames this stage when an ambiguous question
was never rewritten.

The surface this stage adds:

    REWRITE_KEYS             one recorded fix: kind, before, after, why
    REWRITE_KINDS            the closed vocabulary of fixes, in the order they apply
    PRONOUNS                 the pronouns a question can hide its subject behind
    REFERENT_STOP            the words a referent may not be made of
    QUESTION_STOP            the words that do not count towards a question's own terms
    MIN_INTERROGATIVE_TERMS  the fewest terms a question may carry and stand alone
    SUBSET_WORDS             how many terms of a referenced clause its sub-query keeps
    ambiguous(corpus, question)      one row per fix found, or `()`
    rewrite(corpus, question)        the rewritten text and the rows it recorded
    decompose(corpus, question, chunks)  the queries the question needs: one, or two

DESIGN DECISION — where does a pronoun's referent come from? Not from the
question, which does not name it, and not from the first turn, which the
conversation has already moved past. It is the last run of the last turn's
analyzer tokens: the last thing the customer actually named before asking. A
turn whose every token is a `REFERENT_STOP` word names nothing, and then no
pronoun is rewritten rather than a wrong one.

DESIGN DECISION — is a fix applied to the question or to the text the earlier
fixes produced? Each fix applies to the text the fixes before it produced, and
the row's `before` is that text, so a reader can replay the rows in
`REWRITE_KINDS` order and land exactly on the answer `rewrite` gives.

DESIGN DECISION — when is a question elliptical? When its own analyzer terms,
with `QUESTION_STOP` removed, number fewer than `MIN_INTERROGATIVE_TERMS`, and
there is a referent to lean on. Then the referent is appended, and the appended
text is the appended row's `after`.

DESIGN DECISION — what does a two-hop question become? The question's own text
first, and the referenced clause's text cut to its first `SUBSET_WORDS` analyzer
terms second: the first query finds the clause that points, the second finds what
it points at. A question whose expected ids point at nothing decomposes to
itself, and one entry is a complete answer — not a failure.

TODO: implement
"""

import corpus
import stage_01

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


def ambiguous(corpus, question):
    """One `REWRITE_KEYS` row per fix the question needs, in `REWRITE_KINDS` order.

    Answers `()` for a question that already says what it means: no pronoun to
    resolve, no acronym the customer's glossary can expand, and enough terms of
    its own to stand without the turn before it.
    """
    raise NotImplementedError("stage 5: implement ambiguous()")


def rewrite(corpus, question):
    """The question's text after every fix, and the rows the fixes recorded.

    Answers `(question["text"], ())` when there was nothing to fix, and otherwise
    the text the last row's `after` holds together with every row, in order.
    """
    raise NotImplementedError("stage 5: implement rewrite()")


def decompose(corpus, question, chunks):
    """The queries this question needs, in the order they must be searched.

    One entry when a single retrieval answers it; two when its expected ids are
    two hops apart — the question's own text, then the clause the first hop's
    chunk points at, cut to its first `SUBSET_WORDS` terms.
    """
    raise NotImplementedError("stage 5: implement decompose()")
