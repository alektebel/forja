"""stage_03.py — the customer's paperwork: read, reconciled and quarantined.

The scan is text and the system of record is a row, and the two have to meet.
`parse` reads one scanned invoice into a `RECORD_KEYS` record and the tuple of
things that were wrong with the reading; `reconcile` places that record against
the customer's own rows and answers `matched`, `mismatch` or `unmatched`, naming
the row and every field that disagrees; `hybrid_load` keeps what reconciled —
the record, the postings over its text, and the `(tenant, classification)` pair
the row itself gives it, because a record nobody can place is a record nobody
may read — and `report` accounts for every document, including the ones that did
not reconcile and are therefore in no store at all.

Nothing here writes to the estate: the rows are read through the estate's own
accessors, the audit trail is left exactly as long as it was found, and the
quarantine is the point rather than an embarrassment.
"""

from estate import DOCUMENT_KEYS, Estate, EstateError

RECORD_KEYS = ("id", "vendor", "amount_cents", "currency", "day", "po", "text")
PARSE_PROBLEMS = ("amount-missing", "amount-ambiguous", "vendor-missing",
                  "day-missing", "po-missing", "currency-unknown")
CURRENCIES = ("EUR", "USD", "GBP")
VERDICTS = ("matched", "mismatch", "unmatched")
MISMATCHES = ("amount", "vendor", "day", "po")
STORE_KEYS = ("records", "postings", "counts", "acls")

_CENTS = ".,"
_CONFUSIONS = {"O": "0", "l": "1", "I": "1"}
_AMOUNT_LABEL = "amount:"
_VENDOR_LABEL = "vendor:"
_DAY_LABEL = "date:"
_PO_MARK = "po-"
_INVOICE_FOR = " invoice for "
_ROW_FIELD = {"amount": "amount_cents", "vendor": "vendor", "day": "day",
              "po": "po"}


class EtlError(EstateError):
    """This stage's refusal: a shape the load cannot read, naming what arrived."""


def _mapping(value, what):
    """The mapping itself, or a refusal naming what arrived instead."""
    if not isinstance(value, dict):
        raise EtlError("%s is a %s, not a mapping" % (what, type(value).__name__))
    return value


def _keys(mapping, keys, what):
    """The mapping itself once its keys are exactly `keys`, in order, or a refusal."""
    got = tuple(mapping)
    if got != tuple(keys):
        raise EtlError("%s has the keys %r, not %r" % (what, got, tuple(keys)))
    return mapping


def _after(text, label):
    """The value the first line carrying `label` holds, or None when it holds none.

    A label with nothing after it answers None too: the scanner read nothing,
    and the empty string is not a vendor.
    """
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.lower().startswith(label):
            return stripped[len(label):].strip() or None
    return None


def _digits(run):
    """A run of characters with the scanners' confusions repaired.

    The table is closed and small, because the customer's machines make three
    mistakes and only three: `O` is a zero, and `l` and `I` are ones.
    """
    return "".join(_CONFUSIONS.get(char, char) for char in run)


def _po(text):
    """The document's PO, its digit run repaired, or None when it carries none."""
    found = text.lower().find(_PO_MARK)
    if found < 0:
        return None
    run = ""
    for char in text[found + len(_PO_MARK):]:
        if not char.isalnum():
            break
        run += char
    digits = _digits(run)
    if not digits.isdigit():
        return None
    return _PO_MARK.upper() + digits


def _day(value):
    """The day of a `DD/MM` date with its digits repaired, or None."""
    if value is None or "/" not in value:
        return None
    reading = _digits(value.split("/")[0]).strip()
    if not reading.isdigit():
        return None
    return int(reading)


def _number(value):
    """The first run of digits and separators in `value` that holds a digit."""
    run = ""
    for char in value + " ":
        if char.isdigit() or char in _CENTS:
            run += char
        elif any(digit.isdigit() for digit in run):
            return run
        else:
            run = ""
    return None


def _plain(part):
    """A run of digits with every separator removed: thousands separators drop out."""
    return "".join(char for char in part if char not in _CENTS)


def _money(value):
    """The cents an amount line's value holds, and what was wrong with it.

    The decimal separator is the *last* `.` or `,` in the number — so `1.234,56`
    and `1,234.56` are both 123456, the other separator being thousands — and an
    amount the reading cannot settle on two decimal digits is ambiguous, because
    this stage does not guess what a scanner meant.
    """
    if not value:
        return None, "amount-missing"
    number = _number(value)
    if number is None:
        return None, "amount-missing"
    at = max(number.rfind("."), number.rfind(","))
    if at < 0:
        return int(number) * 100, None
    cents = number[at + 1:]
    if len(cents) != 2:
        return None, "amount-ambiguous"
    return int(_plain(number[:at]) + cents), None


def _currency(value):
    """The currency code the amount line writes, and whether we price in it.

    A code the customer does not price in is carried as it was read *and*
    reported: the record keeps what the document said and the problem tuple
    keeps the judgement. An amount line with no code at all is not a problem —
    there is nothing there the reading could have got wrong.
    """
    if not value:
        return None, None
    code = ""
    for char in value + " ":
        if char.isalpha():
            code += char
            continue
        if code:
            break
    code = code.upper()
    if not code:
        return None, None
    if code in CURRENCIES:
        return code, None
    return code, "currency-unknown"


def parse(document):
    """One scanned document as `(record, problems)`: what it says, what it got wrong.

    The record is a `RECORD_KEYS` record, and a field the reading could not
    settle is `None` with its problem in the tuple rather than defaulted to
    something plausible. The problems come back in `PARSE_PROBLEMS` order, so
    two runs of one scan print the same line.
    """
    _keys(_mapping(document, "a document"), DOCUMENT_KEYS, "a document")
    text = document["text"]
    if not isinstance(text, str):
        raise EtlError("the document %r has a %s for text, not a string"
                       % (document["id"], type(text).__name__))
    vendor = _after(text, _VENDOR_LABEL)
    day = _day(_after(text, _DAY_LABEL))
    amount = _after(text, _AMOUNT_LABEL)
    cents, money = _money(amount)
    currency, pricing = _currency(amount)
    record = {"id": document["id"], "vendor": vendor, "amount_cents": cents,
              "currency": currency, "day": day, "po": _po(text), "text": text}
    found = [money, pricing]
    if vendor is None:
        found.append("vendor-missing")
    if day is None:
        found.append("day-missing")
    if record["po"] is None:
        found.append("po-missing")
    return record, tuple(problem for problem in PARSE_PROBLEMS if problem in found)


def tokens(text):
    """A text's searchable tokens: lowercase, digits kept, punctuation gone, deduped.

    Duplicates are dropped in first-seen order, because a token counted twice
    would score one record above another for the same sentence.
    """
    if not isinstance(text, str):
        raise EtlError("a text is a %s, not a string" % (type(text).__name__,))
    found = []
    for chunk in text.lower().split():
        token = "".join(char for char in chunk if char.isalnum())
        if token and token not in found:
            found.append(token)
    return tuple(found)


def _vendor_key(value):
    """A vendor as it is compared: case folded, every run of whitespace removed.

    `Bal tic  Steel` is how the scanner split `Baltic Steel`, so the split is
    not a mismatch; `Baltic Steel Ltd` is another vendor, and it is.
    """
    if value is None:
        return ""
    return "".join(value.split()).lower()


def _vendor_of(text):
    """The vendor a row's own line names: everything before its invoice's PO."""
    return text.split(_INVOICE_FOR)[0]


def _view(row):
    """A row seen through the fields a record is compared with it on."""
    return {"amount_cents": row["amount_cents"], "vendor": _vendor_of(row["text"]),
            "day": row["day"], "po": row["po"]}


def _agrees(field, record, row):
    """Whether the record and that row say the same thing about one field."""
    if field == "vendor":
        return _vendor_key(record["vendor"]) == _vendor_key(row["vendor"])
    return record[_ROW_FIELD[field]] == row[_ROW_FIELD[field]]


def _one_row(rows, po):
    """The row a PO answers, or a refusal naming the two rows that disagree.

    The customer's own duplicates share a PO and agree on the amount, and the
    lowest id is the row the PO answers. Two rows that share the PO and disagree
    are a shape this stage cannot reconcile, so it names which two rather than
    picking one of them.
    """
    first = rows[0]
    for other in rows[1:]:
        if other["amount_cents"] != first["amount_cents"]:
            raise EtlError("PO %s is claimed by %s and %s, which disagree: %d and %d"
                           % (po, first["id"], other["id"], first["amount_cents"],
                              other["amount_cents"]))
    return min(rows, key=lambda row: row["id"])


def reconcile(record, estate):
    """One record against the customer's rows: `(verdict, row id, detail)`.

    The row is found by PO. A record the rows cannot place is quarantined with
    its reason — `no-po`, `no-amount`, `no-row` — and is never counted as
    matched for the customer's convenience. A record whose row answers is
    `matched` when every `MISMATCHES` field agrees, and `mismatch` otherwise,
    with the differing fields named in `MISMATCHES` order.
    """
    _keys(_mapping(record, "a record"), RECORD_KEYS, "a record")
    if not isinstance(estate, Estate):
        raise EtlError("a record is reconciled against an Estate, not a %s"
                       % (type(estate).__name__,))
    if record["po"] is None:
        return "unmatched", None, ("no-po",)
    if record["amount_cents"] is None:
        return "unmatched", None, ("no-amount",)
    rows = [row for row in estate.rows() if row["po"] == record["po"]]
    if not rows:
        return "unmatched", None, ("no-row",)
    row = _one_row(rows, record["po"])
    differing = tuple(field for field in MISMATCHES
                      if not _agrees(field, record, _view(row)))
    return ("mismatch" if differing else "matched"), row["id"], differing


def hybrid_load(estate, documents):
    """The estate's documents as the hybrid store: records, postings, counts, acls.

    `records` and `postings` carry what reconciled and nothing else, and every
    one of those records carries the `(tenant, classification)` pair of the row
    it reconciled to — a `mismatch` reconciled just as much as a `matched`.
    `counts` is the census the load kept over *every* document it read: for each
    verdict, the record ids that landed there and the problems each carried, so
    the quarantine is accountable without being stored.
    """
    if not isinstance(estate, Estate):
        raise EtlError("the corpus is loaded from an Estate, not a %s"
                       % (type(estate).__name__,))
    if not isinstance(documents, (tuple, list)):
        raise EtlError("the corpus is a %s, not a tuple of documents"
                       % (type(documents).__name__,))
    records = []
    postings = {}
    acls = {}
    census = {verdict: {} for verdict in VERDICTS}
    for document in documents:
        record, problems = parse(document)
        if any(record["id"] in census[verdict] for verdict in VERDICTS):
            raise EtlError("document %r is in the corpus twice" % (record["id"],))
        verdict, row_id, detail = reconcile(record, estate)
        census[verdict][record["id"]] = tuple(problems)
        if verdict == "unmatched":
            continue
        row = estate.row(row_id)
        records.append(record)
        acls[record["id"]] = (row["tenant"], row["classification"])
        for token in tokens(record["text"]):
            postings.setdefault(token, []).append(record["id"])
    records.sort(key=lambda record: record["id"])
    return {
        "records": tuple(records),
        "postings": {token: tuple(sorted(postings[token]))
                     for token in sorted(postings)},
        "counts": {verdict: {rid: census[verdict][rid]
                             for rid in sorted(census[verdict])}
                   for verdict in VERDICTS},
        "acls": {rid: acls[rid] for rid in sorted(acls)},
    }


def report(store):
    """The store's own account: how many of each verdict, which ones, what was wrong.

    Every document the load read is in one of the three verdicts whether or not
    it reconciled, so a caller sees the quarantine whole; the problems are
    reported for every document too, because the document that failed to read is
    the one whose problem the customer most needs named.
    """
    _keys(_mapping(store, "a store"), STORE_KEYS, "a store")
    census = _keys(_mapping(store["counts"], "a store's counts"), VERDICTS,
                   "a store's counts")
    for verdict in VERDICTS:
        _mapping(census[verdict], "the %s census" % (verdict,))
    counts = {verdict: len(census[verdict]) for verdict in VERDICTS}
    by_verdict = {verdict: tuple(sorted(census[verdict])) for verdict in VERDICTS}
    problems = {}
    for problem in PARSE_PROBLEMS:
        found = []
        for verdict in VERDICTS:
            found.extend(rid for rid, felt in census[verdict].items()
                         if problem in felt)
        problems[problem] = tuple(sorted(found))
    return {"counts": counts, "by_verdict": by_verdict, "problems": problems}
