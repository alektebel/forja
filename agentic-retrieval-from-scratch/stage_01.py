"""Agentic Retrieval From Scratch — stage 1: The clause, the cross-reference and the chunk that cites itself.

Ten stages of retrieval that checks itself, and this is the rung the other nine
stand on. Everything later — a rank, a critique, a claim, a citation — speaks in
chunk ids, and a chunk id is worth nothing unless the chunk it names is the span the
customer's own document management system calls a clause. So the stage's first job
is not to invent a splitter: it is to read the document the way the document is
written, and to be held against `clause_index(doc)` — the customer's record of what
a clause is, in document order, duplicates and skips and all — rather than against a
second parser the course also wrote.

A contract is not prose. It is numbered: `1. Interpretation`, `2.1 Payment is due`,
`4.2(a) the cap is`, and the number is what a citation is *to*. A clause begins where
a line's first token is a numbering token and runs until the next one; the level is
the shape of that number; and the text is the rest of the heading line plus every
following line that does not open a new clause, joined with single spaces. The dot
belongs to the id at level 1 (`"1."`) and not at level 2 (`"2.1"`), and the level-3
form keeps its letter, because the customer's record prints them that way and a
chunker that tidies them up no longer reproduces it.

The cross-reference is the second half of the same decision. A clause that says
"subject to the fees in 7.2" is not, on its own, the answer to anything: its meaning
is partly *there*, and the thing that gives it meaning is a bare clause id. This
stage keeps those ids — every numbering token the clause's own text carries,
normalized and deduplicated in first-appearance order — and resolves them **within
the document**: a reference the document does not hold stays in `refs`, and `resolve`
answers `None` for it, because a dangling reference is a fact stage 6 has to name
rather than one this stage may quietly repair.

The chunk that cites itself is the third: `chunk_id` is `"<doc>:<clause>"`, and it is
the unit every later stage ranks, critiques and cites. A clause number the document
uses twice yields two chunks *with the same id* — the chunker reports the duplicate
and does not renumber, because an auditor asks what the document says, not what the
course wishes it said.

    CHUNK_KEYS                              the six fields of a chunk, in order
    PARSE_PROBLEMS                          the closed vocabulary a parse problem is spelled in
    LEVELS                                  the three levels a clause number sits at
    chunk(document)                         -> (the document's chunks, the problems it shows)
    problems_of(chunks)                     -> the problems an existing chunk list still shows
    chunk_id(chunk)                         -> "<doc>:<clause>", the unit of every citation
    resolve(chunks, ref)                    -> the chunk a bare clause id names, or None
    definitions(chunks)                     -> term -> the chunk id of its first definition
    refs_of(chunks, id)                     -> the chunk ids reachable from a chunk by its refs
    outline(chunks)                         -> the (chunk id, level) pairs, in document order

DESIGN DECISION — why is the customer's clause index the ground truth rather than a
second parser the course writes?
Because a parser the course writes agrees with the course by construction. The
question "is this a clause" is the customer's to answer, and they answer it in
`clause_index(doc)`: the numbers and their order, including the one the document
uses twice and the one it skips. So `chunk` is not compared with an opinion about
where clauses end — it is compared with the record, and the record does not care how
elegant the splitter is. That is also why the level and the id are preserved exactly
as the document prints them: a chunker that normalises `2.1` to `2.1.` or drops the
`(a)` has reproduced something, but not the customer's document.

DESIGN DECISION — why is a cross-reference a bare clause id resolved within its own
document, and why is a dangling one kept?
Because meaning is often in another clause, and a chunk that loses the reference
loses the half of itself that says where to look. The reference is bare — `7.2`, not
`msa-3:7.2` — because it is a fact about *this* document, and one that resolved
against another document would be a citation the contract never wrote. The document
is the whole world of a reference, so a number the document does not hold is not an
error to raise or a reference to drop: it stays in `refs`, `resolve` answers `None`,
and the stage that critiques retrieved chunks is the one that names it. Repairing it
here would hide exactly the failure this course exists to catch.

DESIGN DECISION — why is a duplicate reported and never repaired?
Because the document is the evidence, and renumbering it would make the chunker's
output disagree with the record it is held against. The customer's agreement prints
two clauses numbered `5.2`, and both are clauses: `chunk` returns both, in document
order, with the same chunk id, and `problems_of` reports `duplicate-clause` once for
that number rather than once per occurrence. A later stage may refuse to cite an
ambiguous id — and it should — but that refusal is only possible because this stage
kept the ambiguity instead of choosing between the two.

DESIGN DECISION — why is `definitions` first-wins rather than last-wins?
Because a defined term is a fact *introduced* where it first appears, and the
question a definition answers is "where does this term come from". A later clause
that redefines it is a second definition, not a correction of the first, and a map
that let the last one win would silently move the term's origin to the end of the
document — an answer that changes depending on how far you read. So the first
definition holds, a redefinition shadows nothing, and the stage that cares about a
term's meaning can argue with the clause the map points at.

DESIGN DECISION — why are parse problems returned rather than raised?
Because a document with a duplicated number or a skipped one is not a document the
stage cannot read — it is a document it read and found odd. The two shapes that
cannot be the thing at all (a mapping that is not a `DOCUMENT_KEYS` record, and a
chunk id asked of something that has no `doc` and `clause`) raise and name the
offender; everything a real contract does — the duplicate, the skip, an empty clause,
a document with no clauses at all — is returned as `(problem, offender)` data,
because the caller is the one who has to decide what to do about it.

TODO: implement `chunk`, `problems_of`, `chunk_id`, `resolve`, `definitions`,
`refs_of` and `outline` in this file: the clause splitter that reproduces the
customer's clause index, the cross-references it keeps and resolves, and the chunk
id every later stage cites.
"""

import corpus

CHUNK_KEYS = ("doc", "clause", "level", "text", "refs", "defines")

PARSE_PROBLEMS = ("no-clauses", "duplicate-clause", "skipped-number", "empty-clause")

LEVELS = (1, 2, 3)


def chunk(document):
    """The document's chunks and the odd things it shows, in `CHUNK_KEYS` order.

    A clause opens at a line whose first token is a numbering token — `N.` at level
    1, `N.M` at level 2, `N.M.L(a)` at level 3 — and its text is the rest of that
    line plus every following line that does not open a new clause, joined with
    single spaces and stripped. The clause numbers, in order, are exactly
    `corpus.clause_index(document["doc"])`, the duplicated and the skipped one
    included. A `document` that is not a `DOCUMENT_KEYS` record raises, naming it.
    """
    raise NotImplementedError("stage 1: implement chunk()")


def problems_of(chunks):
    """The problems an existing chunk list still shows, in `PARSE_PROBLEMS` order.

    `duplicate-clause` once per clause number that appears more than once,
    `skipped-number` for a level-2 number that is neither one more than the previous
    level-2 number under its parent nor `1`, and `empty-clause` for a chunk whose
    text is empty. The `no-clauses` case belongs to `chunk`, which is the only call
    that holds a document: a chunk list with no chunks has no document to name, and
    a parse problem is returned rather than raised.
    """
    raise NotImplementedError("stage 1: implement problems_of()")


def chunk_id(chunk):
    """The chunk's id, `"<doc>:<clause>"` — the unit every later citation is.

    A chunk that is not a record with a `doc` and a `clause` raises, naming it.
    """
    raise NotImplementedError("stage 1: implement chunk_id()")


def resolve(chunks, ref):
    """The first chunk whose clause is the bare `ref`, or `None`.

    A reference resolves within the list it is looked up in — the document's own
    chunks — so a ref the list does not hold answers `None`: that is the dangling
    case stage 6 names, not an error here.
    """
    raise NotImplementedError("stage 1: implement resolve()")


def definitions(chunks):
    """Term -> the chunk id of its first definition, across the chunks in order.

    The first definition wins and a later redefinition shadows nothing.
    """
    raise NotImplementedError("stage 1: implement definitions()")


def refs_of(chunks, id):
    """The chunk ids reachable from `id` by following `refs`, in discovery order.

    The closure excludes `id` itself and is safe against a cycle, so a clause that
    refers to a clause that refers back to it terminates. An `id` the chunk list
    does not hold raises, naming it.
    """
    raise NotImplementedError("stage 1: implement refs_of()")


def outline(chunks):
    """The `(chunk id, level)` pairs, in the chunks' own document order."""
    raise NotImplementedError("stage 1: implement outline()")
