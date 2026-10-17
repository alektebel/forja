"""Agentic Retrieval From Scratch — stage 1: The clause, the cross-reference and the chunk that cites itself.

The document is numbered, so the clause is the number and not the paragraph: this
file reads a document's text the way the customer's own record reads it, reproducing
`clause_index(doc)` number for number, and keeps hold of what a clause points at.
Nothing here asks the library to analyze anything — a chunker that could only see
what the corpus sees would not be reading the document — so the world's own log stays
empty and the customer's record is the only ground truth that moves.
"""

import corpus

CHUNK_KEYS = ("doc", "clause", "level", "text", "refs", "defines")

PARSE_PROBLEMS = ("no-clauses", "duplicate-clause", "skipped-number", "empty-clause")

LEVELS = (1, 2, 3)


def _number(line):
    """The numbering token a line opens with, or `None` — the library's own rule.

    Digits, then one or more `.digits` parts, optionally a `(a)` letter, followed by
    a space or the end of the line. A line that does not open with such a token is
    the body of the clause before it.
    """
    if not line[:1].isdigit():
        return None
    index = 0
    while index < len(line) and line[index].isdigit():
        index = index + 1
    while index < len(line) and line[index] == ".":
        index = index + 1
        if index < len(line) and line[index].isdigit():
            while index < len(line) and line[index].isdigit():
                index = index + 1
        else:
            break
    if (line[index:index + 1] == "(" and line[index + 1:index + 2].isalpha()
            and line[index + 2:index + 3] == ")"):
        index = index + 3
    number = line[:index]
    if "." not in number or line[index:index + 1] not in (" ", ""):
        return None
    return number


def _reference(text, start):
    """The clause reference beginning at `start`, or `None` — `7.2`, `4.2(a)`.

    Digits, then one or more `.digits` parts, optionally a `(a)` letter. A full stop
    that ends a sentence is the sentence's, not the reference's, so `see 7.2.` holds
    the reference `7.2`.
    """
    index = start
    if not text[index:index + 1].isdigit():
        return None
    while text[index:index + 1].isdigit():
        index = index + 1
    if text[index:index + 1] != "." or not text[index + 1:index + 2].isdigit():
        return None
    while text[index:index + 1] == "." and text[index + 1:index + 2].isdigit():
        index = index + 1
        while text[index:index + 1].isdigit():
            index = index + 1
    if (text[index:index + 1] == "(" and text[index + 1:index + 2].isalpha()
            and text[index + 2:index + 3] == ")"):
        index = index + 3
    return text[start:index]


def _level(number):
    """The level a numbering token sits at: 3 with a letter, 1 with a lone dot, 2 else."""
    if number.endswith(")"):
        return 3
    if number.endswith("."):
        return 1
    return 2


def _scan_refs(text):
    """Every clause reference `text` carries, normalized and deduplicated, in order.

    A reference is a numbering token standing anywhere in the clause's own text —
    `subject to the fees in 7.2`, `see 3.3` — and the same number twice is one
    reference. The sentence's own full stop is not part of it.
    """
    refs = []
    index = 0
    while index < len(text):
        if text[index].isdigit():
            reference = _reference(text, index)
            if reference is not None:
                if reference not in refs:
                    refs.append(reference)
                index = index + len(reference)
                continue
        index = index + 1
    return tuple(refs)


def _scan_defines(text):
    """The terms `text` defines, as written without quotes, in first-appearance order.

    A quoted span followed by `means` or `shall mean` is a definition: `"Force
    Majeure" means …`.
    """
    terms = []
    index = 0
    while True:
        start = text.find('"', index)
        if start < 0:
            break
        end = text.find('"', start + 1)
        if end < 0:
            break
        term = text[start + 1:end]
        after = text[end + 1:].lstrip(" ").lower()
        if after.startswith("means") or after.startswith("shall mean"):
            if term not in terms:
                terms.append(term)
        index = end + 1
    return tuple(terms)


def _document(document):
    """The `DOCUMENT_KEYS` record, or the mistake naming what arrived."""
    if not isinstance(document, dict) or tuple(document) != corpus.DOCUMENT_KEYS:
        raise ValueError(
            "chunk: a document is a %r record, and it was %r"
            % (corpus.DOCUMENT_KEYS, document))
    if not isinstance(document["doc"], str) or not isinstance(document["text"], str):
        raise ValueError(
            "chunk: a document's doc and text are strings, and it was %r"
            % (document,))
    return document


def chunk(document):
    """The document's chunks and the odd things it shows, in `CHUNK_KEYS` order.

    A clause opens at a line whose first token is a numbering token — `N.` at level
    1, `N.M` at level 2, `N.M.L(a)` at level 3 — and its text is the rest of that
    line plus every following line that does not open a new clause, joined with
    single spaces and stripped. The clause numbers, in order, are exactly
    `corpus.clause_index(document["doc"])`, the duplicated and the skipped one
    included. A `document` that is not a `DOCUMENT_KEYS` record raises, naming it.
    """
    record = _document(document)
    opened = []
    current = None
    for line in record["text"].split("\n"):
        number = _number(line)
        if number is not None:
            current = [number, _level(number), line[len(number):].strip()]
            opened.append(current)
        elif current is not None:
            body = line.strip()
            if body:
                current[2] = (current[2] + " " + body).strip()
    built = tuple(
        {"doc": record["doc"], "clause": number, "level": level, "text": text,
         "refs": _scan_refs(text), "defines": _scan_defines(text)}
        for number, level, text in opened)
    if not built:
        return built, (("no-clauses", record["doc"]),)
    return built, problems_of(built)


def problems_of(chunks):
    """The problems an existing chunk list still shows, in `PARSE_PROBLEMS` order.

    `duplicate-clause` once per clause number that appears more than once,
    `skipped-number` for a level-2 number that is neither one more than the previous
    level-2 number under its parent nor `1`, and `empty-clause` for a chunk whose
    text is empty. The `no-clauses` case belongs to `chunk`, which is the only call
    that holds a document: a chunk list with no chunks has no document to name, and
    a parse problem is returned rather than raised.
    """
    pairs = [(chunk_id(chunk), chunk["clause"]) for chunk in chunks]
    counts = {}
    order = []
    for cid, clause in pairs:
        if cid not in counts:
            counts[cid] = 0
            order.append((cid, clause))
        counts[cid] = counts[cid] + 1
    duplicates = [clause for cid, clause in order if counts[cid] > 1]
    skips = []
    parent = None
    previous = {}
    for chunk in chunks:
        if chunk["level"] == 1:
            parent = chunk["clause"]
        elif chunk["level"] == 2:
            minor = int(chunk["clause"].split(".")[1])
            last = previous.get(parent)
            if minor != 1 and (last is None or minor != last + 1):
                skips.append(chunk["clause"])
            previous[parent] = minor
    empties = [chunk_id(chunk) for chunk in chunks if chunk["text"].strip() == ""]
    problems = []
    for clause in duplicates:
        problems.append(("duplicate-clause", clause))
    for clause in skips:
        problems.append(("skipped-number", clause))
    for cid in empties:
        problems.append(("empty-clause", cid))
    return tuple(problems)


def chunk_id(chunk):
    """The chunk's id, `"<doc>:<clause>"` — the unit every later citation is.

    A chunk that is not a record with a `doc` and a `clause` raises, naming it.
    """
    if (not isinstance(chunk, dict) or not isinstance(chunk.get("doc"), str)
            or not isinstance(chunk.get("clause"), str)):
        raise ValueError(
            "chunk id: a chunk is a doc and a clause, and it was %r" % (chunk,))
    return "%s:%s" % (chunk["doc"], chunk["clause"])


def resolve(chunks, ref):
    """The first chunk whose clause is the bare `ref`, or `None`.

    A reference resolves within the list it is looked up in — the document's own
    chunks — so a ref the list does not hold answers `None`: that is the dangling
    case stage 6 names, not an error here.
    """
    for chunk in chunks:
        if chunk["clause"] == ref:
            return chunk
    return None


def definitions(chunks):
    """Term -> the chunk id of its first definition, across the chunks in order.

    The first definition wins and a later redefinition shadows nothing.
    """
    found = {}
    for chunk in chunks:
        cid = chunk_id(chunk)
        for term in chunk["defines"]:
            if term not in found:
                found[term] = cid
    return found


def refs_of(chunks, id):
    """The chunk ids reachable from `id` by following `refs`, in discovery order.

    The closure excludes `id` itself and is safe against a cycle, so a clause that
    refers to a clause that refers back to it terminates. An `id` the chunk list
    does not hold raises, naming it.
    """
    held = {}
    for chunk in chunks:
        cid = chunk_id(chunk)
        if cid not in held:
            held[cid] = chunk
    if id not in held:
        raise ValueError("refs of: no chunk %r in this list" % (id,))
    seen = {id}
    found = []
    queue = [id]
    while queue:
        current = queue.pop(0)
        for ref in held[current]["refs"]:
            target = resolve(chunks, ref)
            if target is None:
                continue
            cid = chunk_id(target)
            if cid in seen:
                continue
            seen.add(cid)
            found.append(cid)
            queue.append(cid)
    return tuple(found)


def outline(chunks):
    """The `(chunk id, level)` pairs, in the chunks' own document order."""
    return tuple((chunk_id(chunk), chunk["level"]) for chunk in chunks)
