"""FDE From Scratch — stage 3: The invoice, the reconciliation and the hybrid store.

Thirty years of the customer's paperwork reached you as scans, and the scans
reached you through an OCR pass nobody can re-run. What arrived is text: a vendor
whose name a machine split in half, a PO whose `1` came back as an `l`, an amount
written `1.234,56` on one invoice and `987.65` on the next, a field the scanner
simply left empty, and a currency the customer does not price in. None of this is
an error the pipeline may throw away — it is the *data*, and a model fed it
without reading it fails quietly, on the invoice nobody looked at.

So this stage is the reading, the placing and the store. `parse` turns one scan
into a record and a tuple of problems; `reconcile` places that record against the
row the customer has kept for thirty years and answers a verdict, the row's id
and the fields that disagree; `hybrid_load` builds the store the retrieval stages
will search — the records, the postings over their text, and the ACL of the row
each record reconciled to — and `report` accounts for every document, including
the ones that did not reconcile and are therefore in no store at all. The
quarantine is the point: a record nobody can place is a record nobody can say who
may read, so it sits outside the store while the report still counts it.

Nothing here writes to the estate. Every row is read through the estate's own
accessors, the audit trail is left exactly as long as it was found, and the only
structure this stage remembers anything in is the store it hands back.

    RECORD_KEYS                 the seven fields of one parsed invoice, in order
    PARSE_PROBLEMS              every defect a reading can have, in print order
    CURRENCIES                  the currencies this customer prices in
    VERDICTS                    matched, mismatch, unmatched
    MISMATCHES                  the fields a record may disagree with its row on
    STORE_KEYS                  records, postings, counts, acls
    EtlError                    this stage's refusal
    parse(document)             -> (record, problems), problems in PARSE_PROBLEMS order
    tokens(text)                -> the text's searchable tokens, first-seen order
    reconcile(record, estate)   -> (verdict, row id or None, detail)
    hybrid_load(estate, documents) -> STORE_KEYS over the documents handed in
    report(store)               -> {"counts", "by_verdict", "problems"}, every tuple sorted

A detail is what the third element of `reconcile` carries: the differing fields in
`MISMATCHES` order for a record that found its row, and the one-element reason
`no-po`, `no-amount` or `no-row` — in that order of precedence, because the
document's own unreadable field is the first thing to fix — for a record that did
not. `parse` answers problems, `reconcile` answers a verdict, and neither raises
for dirty data: the only things that raise here are the shapes that cannot be the
thing at all, and they name what arrived.

DESIGN DECISION — why does a dirty scan come back as data rather than an exception?
Because the dirty scan is the customer's reality and the pipeline has to carry it.
An exception at the first unreadable amount throws away the other seven documents,
and the operator learns nothing about which field, on which scan, was wrong; the
quarantine this stage builds is the difference between "eight scans, two of them
need a human" and "the load failed". A shape that cannot be an invoice, on the
other hand — a document that is a string, a record missing its `po` key — is not
data about the paperwork at all, and it raises, naming the offender.

DESIGN DECISION — why is the decimal separator the *last* one in the number?
Because the customer's scanners print money in both conventions and the last
separator is the only one that tells them apart: `1.234,56` and `1,234.56` are the
same amount, and a rule that read `.` as a decimal point would turn the first into
one hundred and twenty-three thousand-four hundred and fifty-six cents' worth of
nothing. The same rule rejects the third case rather than resolving it: one
separator and a decimal part that is not exactly two digits is `amount-ambiguous`
and its cents are `None`, because guessing what a scanner meant is how a
reconciliation starts disagreeing with the invoice it was supposed to check.

DESIGN DECISION — why does `report` account for documents the store does not hold?
Because a quarantine that is not counted is indistinguishable from data loss. The
retrieval stages need a store whose postings only point at records that have an
ACL, so a record that never found its row cannot be in it; but the customer's
question is "what did you do with my eight scans", and the answer has to be four
matched, two mismatched, two waiting for a human — with the problem of each one
named. The store keeps that census beside the records, and `report` reads it; a
document that reconciled and a document that did not are both accounted for once.

DESIGN DECISION — why is the ACL the row's, and not a guess made from the scan?
Because the scan says nothing about who may read it and the row says everything.
The tenant and the classification live in the customer's own record, so the store
takes the pair from the row a record reconciled to — a `mismatch` reconciled just
as much as a `matched` — and a stage that reads the scan for a tenant would be
inventing the one field whose invention leaks another tenant's data. That is why
the store's fourth half is built here, in the stage that owns the reconciliation,
and not in the retriever that merely asks.

DESIGN DECISION — why is the vendor compared with its whitespace removed?
Because the machine that read `Baltic Steel` split it, and the row never did. A
comparison that required the two strings to be equal would call every split vendor
a mismatch and flood the reconciliation with false alarms; removing every run of
whitespace and folding case makes `Bal tic  Steel` the same vendor as
`Baltic Steel`, while `Baltic Steel Ltd` — a different vendor with a different
name — stays a mismatch. The rule is about *this* customer's scanners, and it is
narrow on purpose: it forgives the split, and nothing else.

DESIGN DECISION — why are postings sorted tuples of record ids?
Because the store is the thing two runs of one seed have to agree about. A
posting built in the order the documents happened to arrive makes one load of one
estate different from the next, and a retriever that scores ties by what it saw
first would then answer two runs differently on the same data — the failure mode
that looks like flakiness and is really a missing sort. Building the postings
sorted, over the records that reconciled, makes the store a function of the
estate and the corpus, and that is what the check runs twice.

TODO: implement
"""

from estate import DOCUMENT_KEYS, Estate, EstateError

RECORD_KEYS = ("id", "vendor", "amount_cents", "currency", "day", "po", "text")
PARSE_PROBLEMS = ("amount-missing", "amount-ambiguous", "vendor-missing",
                  "day-missing", "po-missing", "currency-unknown")
CURRENCIES = ("EUR", "USD", "GBP")
VERDICTS = ("matched", "mismatch", "unmatched")
MISMATCHES = ("amount", "vendor", "day", "po")
STORE_KEYS = ("records", "postings", "counts", "acls")


class EtlError(EstateError):
    """This stage's refusal: a shape the load cannot read, naming what arrived."""


def parse(document):
    """One scanned document as `(record, problems)`: what it says, what it got wrong.

    The document is a `DOCUMENT_KEYS` record from the estate, and the record it
    answers is a `RECORD_KEYS` record. The PO is the pattern `PO-<digits>` with
    its digit run repaired (the scanners' `O` is a zero, their `l` and `I` are
    ones); the day is the day of a `DD/MM` date repaired the same way; the amount
    is cents, read with the last separator as the decimal point; the currency is
    the code the amount line wrote. A field the reading could not settle is
    `None` and its problem is in the tuple, which comes back in `PARSE_PROBLEMS`
    order — `amount-missing` and `amount-ambiguous` are told apart by it, and
    neither is a zero.
    """
    raise NotImplementedError("stage 3: implement parse()")


def tokens(text):
    """A text's searchable tokens: lowercase, digits kept, punctuation dropped.

    Duplicates are removed in first-seen order, because a duplicated token would
    score one record above another for the same sentence.
    """
    raise NotImplementedError("stage 3: implement tokens()")


def reconcile(record, estate):
    """One record against the customer's rows: `(verdict, row id, detail)`.

    The row is found by PO, and the customer's own duplicate rows — several rows
    that share a PO and agree on the amount — collapse to the lowest id. Two rows
    that share a PO and disagree are a shape this stage cannot reconcile and
    raises for, naming the PO and both ids rather than picking one. Otherwise the
    verdict is `matched` when the record and its row agree on every field in
    `MISMATCHES`, `mismatch` when they do not (with every differing field named,
    in `MISMATCHES` order), and `unmatched` — with `no-po`, `no-amount` or
    `no-row` — when the record cannot be placed at all.
    """
    raise NotImplementedError("stage 3: implement reconcile()")


def hybrid_load(estate, documents):
    """The documents as the hybrid store: records, postings, counts, acls.

    `records` and `postings` carry what reconciled and nothing else; each of
    those records carries the `(tenant, classification)` pair of the row it
    reconciled to, which is what makes the retrieval stages able to filter at
    all. `counts` is the census over every document read — the record ids that
    landed under each verdict and the problems each of them carried — so the
    documents that did not reconcile are accounted for without being searchable.
    """
    raise NotImplementedError("stage 3: implement hybrid_load()")


def report(store):
    """The store's own account: how many of each verdict, which ones, what was wrong.

    Every document the load read is in one of the three verdicts whether or not
    it reconciled, and the problems are reported for every one of them, because
    the document that failed to read is the one whose problem the customer most
    needs named. Every tuple comes back sorted.
    """
    raise NotImplementedError("stage 3: implement report()")
