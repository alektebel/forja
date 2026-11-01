"""Evals From Scratch — stage 11: fields, not strings

DESIGN DECISION — four statuses, not a boolean.
    `correct` / `incorrect` / `missing` / `extra`. Collapsing missing into
    incorrect hides the two fixes (emit the field vs. fix the value) and
    makes precision/recall lie about which problem dominates.

DESIGN DECISION — type lives in the schema, not in Python's equality.
    `100 == "100"` is False in Python and True in half the harnesses that
    json.loads one side and leave the other as a model string. Coerce both
    sides through the declared type; a value that cannot coerce is incorrect.
    bool is not int.

DESIGN DECISION — micro over cells, macro over field names.
    Micro pools every (doc, path) cell. Macro averages per-field-name F1
    (list indices normalised to `[*]`). A rare billing field that is always
    wrong barely moves micro and tanks macro.

TODO: implement

    coerce(value, typ) -> value
        typ is str | int | float | bool. Raises ValueError on failure.
        bool must NOT coerce to int/float.

    compare_extraction(pred, gold, schema) -> list[dict]
        schema leaves are types; a list field is written [item_schema].
        Each cell: {"path", "status", "pred", "gold"} with status in
        correct | incorrect | missing | extra. Paths look like
        "vendor", "line_items[0].sku". Extra = key present in pred but not
        declared in the schema.

    micro_scores(results) -> dict
        tp=correct; fp=incorrect+extra; fn=missing+incorrect.
        Returns {tp, fp, fn, precision, recall, f1}. Empty → precision=recall=1.

    macro_f1(results) -> float
        Mean of per-field-name F1s; collapse [0]/[1]/… to [*]. Empty → 1.0.

    schema_valid(pred, schema) -> bool
        Every declared leaf present and coercible. Extra keys do not invalidate.

    extraction_report(pairs, schema) -> dict
        pairs: iterable of (pred, gold). Returns
        {n, schema_valid_rate, micro, macro_f1, per_doc}.
"""


def coerce(value, typ):
    raise NotImplementedError("stage 11: implement coerce()")


def compare_extraction(pred, gold, schema):
    raise NotImplementedError("stage 11: implement compare_extraction()")


def micro_scores(results):
    raise NotImplementedError("stage 11: implement micro_scores()")


def macro_f1(results):
    raise NotImplementedError("stage 11: implement macro_f1()")


def schema_valid(pred, schema):
    raise NotImplementedError("stage 11: implement schema_valid()")


def extraction_report(pairs, schema):
    raise NotImplementedError("stage 11: implement extraction_report()")
