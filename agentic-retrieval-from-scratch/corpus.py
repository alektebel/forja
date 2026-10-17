"""corpus.py — the customer's contract library: documents, analyzer, labels and log.

Provided, frozen, and never written by the course. This module is the customer's own
library, and it holds four things the course is graded against:

* the **documents** — eight contracts as their lawyers wrote them, numbered clauses at
  three levels (`1.`, `1.1`, `1.1(a)`), cross-references (`see 4.2(a)`), defined terms
  (`"Force Majeure" means …`), one clause number printed twice and one that skips;
* the **record** — `clause_index(doc)` is the customer's own answer to *what is a
  clause*, and it is what the course's chunker is held against; `subjects()` tags each
  clause with the subject it is about, so two clauses that disagree about the same
  subject can be found without reading English;
* the **labels** — `questions` (the evaluation set, each with the clauses an answer
  must cite and the conversation that preceded it) and `failures` (the old pipeline's
  labelled mistakes, one stage per row);
* the **analyzer and the embedder** — `terms(text)` is the customer's tokenizer with a
  clause reference kept whole (`"4.2(a)"`), `idf(term)` is an inverse document
  frequency in basis points computed with an integer logarithm (this course has no
  `math`), and `embed(text)` hands back a unit-scaled integer vector so a similarity is
  a plain dot product: no division, no square root, no float anywhere.

Nothing here is random and nothing here reads a clock. `Corpus.build(seed)` is a
function of its seed, every counter is recomputed from the module's own log (`stats()`),
and a refusal names the offender: the document, the term, the question, the clause.

A **chunk id** — the unit of citation this course adds — is the string
`"<doc>:<clause>"`, for example `"msa-3:4.2(a)"`. `clause_index` keeps answering bare
clause numbers in document order (`("1.", "1.1", "1.1(a)", …)`); the labels, the
subjects and the failures speak in chunk ids, because that is how the customer's own
document management system exports a clause.
"""

import hashlib

VECTOR_DIM = 32
VECTOR_SCALE = 1000

IDF_UNIT_BP = 10000
IDF_PRECISION = 1024
IDF_ZERO = 10

SCALE_KEYS = ("documents", "clauses", "terms", "bytes_per_clause", "hot_bp")
DOCUMENT_KEYS = ("doc", "title", "version", "superseded_by", "text")
QUESTION_KEYS = ("qid", "text", "expected", "conversation")
TURN_KEYS = ("speaker", "text")
FAILURE_KEYS = ("fid", "qid", "chunks", "retrieved", "kept", "cited", "answer_ok",
                "stage")
LOG_KEYS = ("call", "argument")

FAILURE_STAGES = ("chunk", "rewrite", "retrieve", "rerank", "ground", "answer", "none")

SCALE = {
    "documents": 10000000,
    "clauses": 140000000,
    "terms": 250000,
    "bytes_per_clause": 480,
    "hot_bp": 2000,
}

CORPUS_ERROR = "corpus: "


class CorpusError(ValueError):
    """The library's refusal: a shape it cannot accept, or a term it does not hold."""


def _need(mapping, keys, what):
    """Check a mapping's keys are exactly `keys`, in order, and answer it."""
    if not isinstance(mapping, dict):
        raise CorpusError(CORPUS_ERROR + ("%s is a %s, not a mapping"
                                          % (what, type(mapping).__name__)))
    got = tuple(mapping)
    if got != tuple(keys):
        raise CorpusError(CORPUS_ERROR + ("%s has the keys %r, not %r"
                                          % (what, got, tuple(keys))))
    return mapping


def _int(value, what):
    """Check a whole number and answer it (a `bool` is not a whole number here)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise CorpusError(CORPUS_ERROR + ("%s is %r, not a whole number" % (what, value)))
    return value


def _text(value, what):
    """Check a string and answer it."""
    if not isinstance(value, str):
        raise CorpusError(CORPUS_ERROR + ("%s is a %s, not a string"
                                          % (what, type(value).__name__)))
    return value


def _stream(seed):
    """A seed's deterministic integer stream — this module's only source of variety."""
    state = _int(seed, "the seed") % 2147483648
    while True:
        state = (state * 1103515245 + 12345) % 2147483648
        yield state


def _clause_number(line):
    """The clause number a line opens with, or `None`.

    A clause opens at column 0 with a number: digits, then a full stop, or the same
    with one or more `.digits` parts, and optionally a `(a)`-style letter at the end.
    The number must be followed by a space, and it must contain a full stop — so
    `1. Interpretation`, `2.1 Payment is due …` and `4.2(a) the cap is …` are clause
    headings while `thirty days …` is the body of the clause before it.
    """
    index = 0
    if not line[:1].isdigit():
        return None
    while index < len(line) and line[index].isdigit():
        index = index + 1
    while index < len(line) and line[index] == ".":
        index = index + 1
        if index < len(line) and line[index].isdigit():
            while index < len(line) and line[index].isdigit():
                index = index + 1
        else:
            break
    if line[index:index + 1] == "(":
        close = index + 2
        if line[close:close + 1] == ")" and line[index + 1:index + 2].isalpha():
            index = close + 1
    number = line[:index]
    if "." not in number or line[index:index + 1] not in (" ", ""):
        return None
    return number


def _reference(text, start):
    """The clause reference beginning at `start`, or `None` — `4.2(a)`, `1.2`.

    A reference is digits, then one or more `.digits` parts, and optionally a `(a)`
    letter. The full stop that ends a sentence is the sentence's, not the
    reference's: `see 7.2.` holds the reference `7.2`.
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
    if text[index:index + 1] == "(":
        if text[index + 1:index + 2].isalpha() and text[index + 2:index + 3] == ")":
            index = index + 3
    return text[start:index]


def _clause_ids(text):
    """The clause numbers of `text`, in document order, duplicates and all."""
    numbers = []
    for line in text.split("\n"):
        number = _clause_number(line)
        if number is not None:
            numbers.append(number)
    return tuple(numbers)


def _terms(text):
    """The customer's analyzer: lowercase alphanumeric tokens, references kept whole.

    `_terms("see 4.2(a) and Clause 12")` is `("see", "4.2(a)", "and", "clause",
    "12")`: a clause reference is one token, everything else is a run of letters and
    digits folded to lower case.
    """
    _text(text, "the text")
    tokens = []
    index = 0
    while index < len(text):
        if not text[index].isalnum():
            index = index + 1
            continue
        reference = _reference(text, index)
        if reference is not None:
            tokens.append(reference)
            index = index + len(reference)
            continue
        end = index
        while end < len(text) and text[end].isalnum():
            end = end + 1
        tokens.append(text[index:end].lower())
        index = end
    return tuple(tokens)


def _chunk(document, number):
    """The chunk id this course cites: `"<doc>:<clause>"`."""
    return "%s:%s" % (document, number)


_SUPPLIERS = ("Northwind Systems", "Contoso Cloud", "Fabrikam Ltd")
_CUSTOMERS = ("Aalborg Cement", "Baltic Steel", "Oslo Fasteners")
_TERM_YEARS = (2, 3, 5)
_PAYMENT_DAYS = (30, 45, 60)
_INTEREST = ("one", "two", "three")

# The customer's own list, keyed the way their analyzer writes it: a question's token
# folded to lower case is the key (§4.5's acronym rule matches `token.lower()`), and the
# expansion is appended in parentheses by the rewrite exactly as it is written here.
GLOSSARY = {
    "msa": "master services agreement",
    "dpa": "data processing addendum",
    "sla": "service level agreement",
    "sow": "statement of work",
    "pii": "personal data",
}

_SUBJECT_TAGS = {
    ("lic-2", "6.1"): "liability",
    ("amd-3", "3.1"): "liability",
    ("msa-3", "3.2"): "payment",
    ("sow-1", "4.1"): "payment",
    ("dpa-1", "6.1"): "deletion",
    ("lic-2", "7.1"): "termination",
    ("res-1", "5.1"): "termination",
}


def _documents(seed):
    """The eight documents, as the customer's lawyers wrote them."""
    stream = _stream(seed)
    supplier = _SUPPLIERS[next(stream) % 3]
    customer = _CUSTOMERS[next(stream) % 3]
    years = _TERM_YEARS[next(stream) % 3]
    days = _PAYMENT_DAYS[next(stream) % 3]
    interest = _INTEREST[next(stream) % 3]
    texts = {
        "msa-3": (
            "1. Interpretation\n"
            "1.1 In this Agreement, \"Services\" means the services described in each "
            "Statement of Work.\n"
            "1.2 \"Confidential Information\" means information disclosed by either "
            "party and marked confidential.\n"
            "2. Term\n"
            "2.1 This Agreement begins on the Effective Date and continues for %d "
            "years.\n"
            "2.2 Either party may renew this Agreement by written notice given at "
            "least sixty days before 2.1 expires.\n"
            "2.3 A renewal under 2.2 is subject to the fees in 7.2.\n"
            "3. Fees\n"
            "3.1 The Customer pays the fees stated in the applicable Statement of "
            "Work.\n"
            "3.2 Payment is due within %d days of a valid invoice.\n"
            "3.3 Overdue amounts carry interest at %s per cent per month, as "
            "described in 4.2(a).\n"
            "4. Liability\n"
            "4.1 Neither party excludes liability for death or personal injury caused "
            "by negligence.\n"
            "4.2 The Supplier's total liability under this Agreement is limited as "
            "follows:\n"
            "4.2(a) the cap is the fees paid in the twelve months before the claim, "
            "see 3.3.\n"
            "4.2(b) the cap does not apply to a breach of 8.1.\n"
            "5. Notices\n"
            "5.1 Notices are delivered to the addresses in the Order.\n"
            "5.2 Notices must be copied to the Supplier's legal department.\n"
            "5.2 A notice is effective on delivery.\n"
            "6. Force Majeure\n"
            "6.1 \"Force Majeure\" means an event beyond a party's reasonable "
            "control.\n"
            "6.2 The affected party notifies the other party within five days of the "
            "event.\n"
            "7. Charges\n"
            "7.1 Fees are invoiced monthly in arrears.\n"
            "7.2 The rate card is fixed for the first year and reviewed after that.\n"
            "8. Confidentiality\n"
            "8.1 Each party keeps the other party's Confidential Information secret "
            "under 1.2.\n" % (years, days, interest)),
        "dpa-1": (
            "1. Processing\n"
            "1.1 The Supplier processes Personal Data only on the Customer's "
            "documented instructions.\n"
            "2. Sub-processors\n"
            "2.1 The Supplier engages a sub-processor only with the Customer's prior "
            "written consent.\n"
            "2.2 The list of sub-processors is kept current and shared each "
            "quarter.\n"
            "2.3 Sub-processors are bound by the terms set out in 9.9.\n"
            "3. Security\n"
            "3.1 The measures in the Security Annex apply to all Personal Data.\n"
            "4. Breach\n"
            "4.1 The Supplier notifies the Customer of a Personal Data breach "
            "without undue delay.\n"
            "5. Audit\n"
            "5.1 The Customer may audit the Supplier once a year.\n"
            "6. Deletion\n"
            "6.1 Personal Data is deleted on termination, except where 5.1 requires "
            "retention.\n"),
        "lic-2": (
            "1. Licence\n"
            "1.1 The Supplier grants the Customer a non-exclusive licence to use the "
            "Software.\n"
            "1.2 The licence is limited to the seats stated in the Order.\n"
            "2. Term\n"
            "2.1 The licence continues for twelve months from delivery, see 4.1.\n"
            "3. Restrictions\n"
            "3.1 The Customer must not copy the Software except for backup and "
            "disaster recovery.\n"
            "4. Support\n"
            "4.1 Support is provided under the Support Schedule.\n"
            "5. Fees\n"
            "5.1 The licence fee is payable annually in advance.\n"
            "6. Liability\n"
            "6.1 The Supplier's total liability under this Licence is limited to the "
            "fees paid in the twelve months before the claim.\n"
            "6.2 Nothing in this Licence excludes liability for death or personal "
            "injury.\n"
            "7. Termination\n"
            "7.1 Either party may terminate for a material breach not cured within "
            "thirty days.\n"),
        "amd-3": (
            "1. Amendment\n"
            "1.1 This Amendment replaces the liability terms of the Licence "
            "described in 2.1.\n"
            "2. Interpretation\n"
            "2.1 In this Amendment, \"Licence\" means the Software Licence Agreement "
            "it replaces.\n"
            "3. Liability\n"
            "3.1 The Supplier's total liability under the Licence is unlimited and "
            "the cap in the replaced agreement does not apply.\n"
            "3.2 The Customer remains liable for the licence fees.\n"
            "4. Effect\n"
            "4.1 All other terms of the Licence continue in force.\n"),
        "sup-1": (
            "1. Support Hours\n"
            "1.1 Support is available from eight in the morning to six in the "
            "evening on business days.\n"
            "2. Severity Levels\n"
            "2.1 A Severity 1 incident is a total loss of service.\n"
            "2.2 A Severity 2 incident is a material loss of service that has a "
            "workaround.\n"
            "3. Response Times\n"
            "3.1 The Supplier responds to a Severity 1 incident within one hour.\n"
            "3.3 The Supplier responds to a Severity 3 incident within one business "
            "day.\n"
            "4. Service Credits\n"
            "4.1 \"Service Credits\" means the credits set out in 4.2.\n"
            "4.2 A missed response time earns a credit of five per cent of the "
            "monthly fee.\n"),
        "sec-1": (
            "1. Access Control\n"
            "1.1 Access to the Customer's systems is granted to named personnel "
            "only.\n"
            "1.2 Each account is removed within one business day of a person "
            "leaving.\n"
            "2. Encryption\n"
            "2.1 Data at rest is encrypted with the approved algorithm, see 4.1.\n"
            "2.2 Data in transit is encrypted with the approved protocol.\n"
            "3. Incident Notification\n"
            "3.1 The Supplier notifies the Customer of a security incident within "
            "seventy-two hours.\n"
            "4. Audit\n"
            "4.1 The Supplier provides an independent audit report once a year.\n"),
        "res-1": (
            "1. Appointment\n"
            "1.1 The Customer is appointed as a non-exclusive reseller of the "
            "Products.\n"
            "2. Orders\n"
            "2.1 The reseller submits orders under the terms set out in 5.1.\n"
            "3. Pricing\n"
            "3.1 The reseller buys at the discount stated in the current price "
            "list.\n"
            "4. Branding\n"
            "4.1 The reseller uses the Supplier's marks only as approved in "
            "writing.\n"
            "5. Term\n"
            "5.1 Either party may terminate on ninety days' written notice.\n"),
        "sow-1": (
            "1. Scope\n"
            "1.1 The Supplier provides the consulting days described in the "
            "Order.\n"
            "2. Deliverables\n"
            "2.1 Each deliverable is accepted or rejected within ten business days, "
            "see 4.2.\n"
            "3. Personnel\n"
            "3.1 The Supplier's personnel are not employees of the Customer.\n"
            "4. Acceptance\n"
            "4.1 Accepted deliverables are invoiced monthly in arrears.\n"
            "4.2 A rejected deliverable is corrected once at no charge.\n"),
    }
    titles = {
        "msa-3": "Master Services Agreement between %s and %s" % (customer, supplier),
        "dpa-1": "Data Processing Addendum",
        "lic-2": "Software Licence Agreement",
        "amd-3": "Software Licence Agreement, Amendment 2",
        "sup-1": "Support Schedule",
        "sec-1": "Security Annex",
        "res-1": "Reseller Agreement",
        "sow-1": "Consulting Statement of Work",
    }
    versions = {"msa-3": 3, "dpa-1": 1, "lic-2": 2, "amd-3": 3, "sup-1": 1,
                "sec-1": 1, "res-1": 1, "sow-1": 1}
    superseded = {"lic-2": "amd-3"}
    documents = []
    for document in sorted(texts):
        documents.append({"doc": document, "title": titles[document],
                          "version": versions[document],
                          "superseded_by": superseded.get(document),
                          "text": texts[document]})
    return tuple(documents)


_QUESTIONS = (
    ("q-01", "What is the cap on the Supplier's total liability under the MSA?",
     ("msa-3:4.2(a)",), ()),
    ("q-02", "How long after a valid invoice is payment due?", ("msa-3:3.2",), ()),
    ("q-03", "When must the renewal notice be given, and which fees govern the renewal?",
     ("msa-3:2.3", "msa-3:7.2"), ()),
    ("q-04", "What do overdue amounts carry, and where is that described?",
     ("msa-3:3.3", "msa-3:4.2(a)"), ()),
    ("q-05", "Does it require deletion on termination?", ("dpa-1:6.1",),
     (("auditor", "The MSA and the DPA both say something about Personal Data at the "
                  "end of the term."),
      ("auditor", "Your team told me one of them governs deletion."))),
    ("q-06", "Is its cap still in force?", ("amd-3:3.1",),
     (("buyer", "We signed the Licence first and the Amendment later."),
      ("buyer", "The Amendment changed the liability terms."))),
    ("q-07", "What does the SLA say about a Severity 1 incident?", ("sup-1:3.1",), ()),
    ("q-08", "How often is it provided?", ("sec-1:4.1",),
     (("engineer", "The Support Schedule and the Security Annex both mention an audit."),
      ("engineer", "Only one of them sets how often it happens."))),
    ("q-09", "What must the reseller do before using the Supplier's marks?",
     ("res-1:4.1",), ()),
    ("q-10", "How long do we have to accept it under the SOW?",
     ("sow-1:2.1", "sow-1:4.2"),
     (("lawyer", "The DPA and the SOW both have an acceptance step."),
      ("lawyer", "The DPA is the one about processing."))),
    ("q-11", "Who is told about a personal data breach under the DPA, and how quickly?",
     ("dpa-1:4.1",), ()),
    ("q-12", "Which clause binds the sub-processors?", ("dpa-1:2.3",), ()),
    ("q-13", "Can a party terminate the Licence for a material breach?",
     ("lic-2:7.1",), ()),
    ("q-14", "Which one limits what we can claim?", ("lic-2:6.1",),
     (("cfo", "The Licence and the Amendment disagree about liability."),
      ("cfo", "One of them removes the cap entirely."))),
    ("q-15", "What is owed when a response time is missed?", ("sup-1:4.2",), ()),
    ("q-16", "How quickly must a party notify Force Majeure under the MSA?",
     ("msa-3:6.2",), ()),
)

# fid, qid, the clause numbers the old pipeline's chunker dropped, the clause numbers
# it retrieved in rank order, how many it kept, what it cited, whether its answer was
# right, and the customer's own diagnosis — every row decided by stage 10's tree from
# this evidence alone, its first match winning. Two rows answer correctly (`none`), two
# lost a clause to the chunker, two were never rewritten although the question was
# ambiguous, two lost the clause to the ranking, one cited something else, and one
# cited exactly what the question asked for and was still wrong.
_FAILURES = (
    ("f-01", "q-01", ("4.2(a)",), ("4.2", "4.1", "3.1", "3.2"), 2, ("4.2",), False,
     "chunk"),
    ("f-02", "q-09", ("4.1",), ("3.1", "1.1", "5.1", "2.1"), 2, ("1.1",), False, "chunk"),
    ("f-03", "q-02", (), ("3.1", "7.2", "1.1", "4.1"), 2, ("3.1",), False, "retrieve"),
    ("f-04", "q-13", (), ("6.1", "6.2", "5.1", "1.2"), 3, ("6.1",), False, "retrieve"),
    ("f-05", "q-05", (), ("4.1", "5.1", "2.3", "1.1"), 2, ("4.1",), False, "rewrite"),
    ("f-06", "q-07", (), ("3.3", "2.1", "2.2", "1.1"), 2, ("3.3",), False, "rewrite"),
    ("f-07", "q-12", (), ("2.1", "2.2", "1.1", "2.3"), 2, ("2.1",), False, "rerank"),
    ("f-08", "q-08", (), ("2.1", "1.1", "1.2", "4.1"), 2, ("2.1",), False, "rerank"),
    ("f-09", "q-11", (), ("4.1", "1.1", "2.1", "2.2"), 2, ("1.1",), False, "ground"),
    ("f-10", "q-15", (), ("4.2", "4.1", "3.3", "3.1"), 3, ("4.2",), False, "answer"),
    ("f-11", "q-03", (), ("2.3", "7.2", "2.2", "2.1"), 4, ("2.3", "7.2"), True, "none"),
    ("f-12", "q-16", (), ("6.2", "6.1", "6.", "2.2"), 3, ("6.2",), True, "none"),
)

_VECTOR_MAGNITUDES = (
    188, 195, 189, 188, 192, 172, 171, 192, 190, 171, 166, 188, 179, 169, 165, 194,
    162, 185, 188, 170, 160, 193, 164, 163, 162, 172, 175, 161, 196, 166, 160, 156,
)


def _questions():
    """The evaluation set: sixteen questions, five of them carrying a conversation."""
    questions = []
    for qid, text, expected, conversation in _QUESTIONS:
        questions.append({"qid": qid, "text": text, "expected": tuple(expected),
                          "conversation": tuple({"speaker": speaker, "text": turn}
                                                for speaker, turn in conversation)})
    return tuple(questions)


def _failures(questions, documents):
    """The old pipeline's labelled mistakes, in the customer's own words.

    `chunks` is what the old chunker produced for the question's document: the
    customer's own clause index of that document, minus the clauses the chunker
    dropped — which is the only way stage 10's tree can reach the `chunk` branch.
    """
    by_qid = {}
    for question in questions:
        by_qid[question["qid"]] = question
    rows = []
    for fid, qid, dropped, retrieved, kept, cited, answer_ok, stage in _FAILURES:
        document = by_qid[qid]["expected"][0].split(":")[0]
        rows.append({
            "fid": fid, "qid": qid,
            "chunks": tuple(_chunk(document, number)
                            for number in _clause_ids(documents[document]["text"])
                            if number not in dropped),
            "retrieved": tuple(_chunk(document, number) for number in retrieved),
            "kept": kept,
            "cited": tuple(_chunk(document, number) for number in cited),
            "answer_ok": answer_ok, "stage": stage})
    return tuple(rows)


def _subjects(clauses):
    """Each clause's subject tag — the label two disagreeing clauses can share.

    A clause the customer tagged by hand keeps its tag (`liability` for the capped
    clause and the amendment that uncaps it); every other clause is tagged by its
    article, which is the subject a clause number already announces.
    """
    subjects = {}
    for document in sorted(clauses):
        for number in clauses[document]:
            tag = _SUBJECT_TAGS.get((document, number))
            if tag is None:
                tag = "article %s" % (number.split(".")[0],)
            subjects[_chunk(document, number)] = tag
    return subjects


def _embed(text):
    """A unit-scaled integer vector: `VECTOR_DIM` signed ints of integer norm 1000.

    The magnitudes are fixed and their squares sum to `VECTOR_SCALE * VECTOR_SCALE`,
    so every vector this function answers sits on the same sphere of radius 1000;
    the text chooses the order and the signs, which is why two calls with one text
    answer equal tuples and a similarity is a plain dot product.
    """
    _text(text, "the text")
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    stream = _stream(int.from_bytes(digest, "big"))
    remaining = list(_VECTOR_MAGNITUDES)
    components = []
    for _ in range(VECTOR_DIM):
        magnitude = remaining.pop(next(stream) % len(remaining))
        sign = 1 if next(stream) % 2 else -1
        components.append(sign * magnitude)
    return tuple(components)


def _idf_bp(documents, count):
    """Inverse document frequency in basis points, from an integer logarithm.

    `count` is in how many of `documents` documents the term appears; one doubling of
    rarity is `IDF_UNIT_BP` basis points, and a term that appears everywhere still
    scores `IDF_UNIT_BP` — the logarithm here is `int.bit_length()`, because this
    course has no `math` and no float to put in a similarity.
    """
    scaled = (documents * IDF_PRECISION) // count
    return IDF_UNIT_BP * (scaled.bit_length() - IDF_ZERO)


class Corpus:
    """The customer's contract library: documents, analyzer, labels and log.

    `Corpus(documents, questions, glossary, failures)` takes the record as data — the
    `DOCUMENT_KEYS`, `QUESTION_KEYS` and `FAILURE_KEYS` records — and derives the
    rest: `clause_index(doc)` from each document's own text, `subjects()` from the
    clause numbers, and the document counts `idf` divides by. Every call the course
    makes is one line of `log()`, and `stats()` is recomputed from that log.
    """

    def __init__(self, documents, questions, glossary, failures):
        if not isinstance(documents, (tuple, list)) or not documents:
            raise CorpusError(CORPUS_ERROR % "a corpus needs documents")
        self._documents = {}
        for document in documents:
            record = _need(dict(document), DOCUMENT_KEYS, "a document")
            if record["doc"] in self._documents:
                raise CorpusError(CORPUS_ERROR + ("document %r appears twice"
                                                  % (record["doc"],)))
            self._documents[record["doc"]] = record
        self._clauses = {}
        for document, record in self._documents.items():
            self._clauses[document] = _clause_ids(record["text"])
        self._subjects = _subjects(self._clauses)
        self._questions = []
        for question in questions:
            record = _need(dict(question), QUESTION_KEYS, "a question")
            record["expected"] = tuple(record["expected"])
            record["conversation"] = tuple(_need(dict(turn), TURN_KEYS, "a turn")
                                           for turn in record["conversation"])
            for expected in record["expected"]:
                if expected not in self._subjects:
                    raise CorpusError(CORPUS_ERROR + (
                        "question %r expects %r, which is not a clause of this corpus"
                        % (record["qid"], expected)))
            self._questions.append(record)
        if not isinstance(glossary, dict) or not glossary:
            raise CorpusError(CORPUS_ERROR % "a glossary is a non-empty mapping")
        self._glossary = {}
        for acronym, expansion in glossary.items():
            self._glossary[_text(acronym, "an acronym")] = _text(expansion,
                                                                 "an expansion")
        self._failures = []
        for failure in failures:
            record = _need(dict(failure), FAILURE_KEYS, "a failure row")
            if record["qid"] not in [question["qid"] for question in self._questions]:
                raise CorpusError(CORPUS_ERROR + ("failing row %r answers question %r, "
                                                  "which the corpus does not hold"
                                                  % (record["fid"], record["qid"])))
            _int(record["kept"], "the kept count")
            if record["kept"] < 0:
                raise CorpusError(CORPUS_ERROR + ("failure row %r kept %d hits, not a "
                                                  "count" % (record["fid"], record["kept"])))
            if record["kept"] > len(record["retrieved"]):
                raise CorpusError(CORPUS_ERROR + (
                    "failure row %r kept %d of %d retrieved"
                    % (record["fid"], record["kept"], len(record["retrieved"]))))
            if not isinstance(record["answer_ok"], bool):
                raise CorpusError(CORPUS_ERROR + ("failure row %r answers %r, not a bool"
                                                  % (record["fid"], record["answer_ok"])))
            if record["stage"] not in FAILURE_STAGES:
                raise CorpusError(CORPUS_ERROR + (
                    "failure row %r blames stage %r, not one of %r"
                    % (record["fid"], record["stage"], FAILURE_STAGES)))
            for field in ("chunks", "retrieved", "cited"):
                record[field] = tuple(record[field])
                for chunk in record[field]:
                    if chunk not in self._subjects:
                        raise CorpusError(CORPUS_ERROR + (
                            "failure row %r names chunk %r, which is not a clause of "
                            "this corpus" % (record["fid"], chunk)))
            self._failures.append(record)
        self._df = self._count_terms()
        self._log = []

    # -- the library --------------------------------------------------------
    @property
    def documents(self):
        """Every document, in the order the corpus was given them."""
        return tuple(dict(record) for record in self._documents.values())

    @property
    def questions(self):
        """Every labelled question, in id order."""
        return tuple(dict(record) for record in self._questions)

    @property
    def glossary(self):
        """The customer's own acronyms, as written."""
        return dict(self._glossary)

    @property
    def failures(self):
        """The old pipeline's labelled failures, in id order."""
        return tuple(dict(record) for record in self._failures)

    @property
    def log(self):
        """Every line this library wrote, in order — `LOG_KEYS` records."""
        return tuple(dict(line) for line in self._log)

    def document(self, doc):
        """One document by id; an unknown id is refused by name."""
        self._write("document", doc)
        if doc not in self._documents:
            raise CorpusError(CORPUS_ERROR + ("no such document %r" % (doc,)))
        return dict(self._documents[doc])

    def clause_index(self, doc):
        """The clause numbers of `doc`, in document order — the customer's record.

        A number printed twice appears twice, in document order: the chunker has to
        reproduce this record and report the duplicate, not repair it.
        """
        self._write("clause_index", doc)
        if doc not in self._clauses:
            raise CorpusError(CORPUS_ERROR + ("no such document %r" % (doc,)))
        return tuple(self._clauses[doc])

    def subjects(self):
        """Chunk id → subject tag, for every clause of every document.

        Two clauses that share a tag are about the same subject, which is how a
        contradiction between two documents (`lic-2:6.1` and `amd-3:3.1`, both
        `liability`) can be found without reading English.
        """
        self._write("subjects", "all")
        return dict(self._subjects)

    def terms(self, text):
        """The customer's analyzer over `text`: lowercase tokens, references whole."""
        self._write("terms", text)
        return _terms(text)

    def idf(self, term):
        """The inverse document frequency of `term`, in basis points.

        Refused, naming the term, when the library does not hold it.
        """
        self._write("idf", term)
        count = self._df.get(term)
        if count is None:
            raise CorpusError(CORPUS_ERROR + ("no such term %r in this library" % (term,)))
        return _idf_bp(len(self._documents), count)

    def embed(self, text):
        """`VECTOR_DIM` signed ints on the sphere of radius `VECTOR_SCALE`."""
        self._write("embed", text)
        return _embed(text)

    # -- the record ---------------------------------------------------------
    def _count_terms(self):
        """How many documents each term appears in — the library's own counts."""
        counts = {}
        for document in self._documents:
            for term in sorted(set(_terms(self._documents[document]["text"]))):
                counts[term] = counts.get(term, 0) + 1
        return counts

    def _write(self, call, argument):
        self._log.append({"call": call, "argument": argument})

    def _calls(self, call):
        return len([line for line in self._log if line["call"] == call])

    def stats(self):
        """Counters recomputed from the log: what was asked, and what the library is."""
        return {
            "documents": len(self._documents),
            "clauses": sum(len(numbers) for numbers in self._clauses.values()),
            "analyses": self._calls("terms"),
            "idfs": self._calls("idf"),
            "embeds": self._calls("embed"),
            "lookups": self._calls("document") + self._calls("clause_index")
            + self._calls("subjects"),
        }

    @classmethod
    def build(cls, seed=7):
        """The customer's library: eight documents, sixteen questions, twelve failures.

        A function of `seed`: the parties, the term, the payment window and the
        interest rate are drawn from the seed's stream, and nothing else moves.
        """
        documents = _documents(seed)
        questions = _questions()
        failures = _failures(questions,
                             {record["doc"]: record for record in documents})
        return cls(documents, questions, GLOSSARY, failures)
