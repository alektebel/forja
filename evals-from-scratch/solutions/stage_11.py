"""Evals From Scratch — stage 11: fields, not strings

Typed comparison of structured extractions against a schema. Product evals for
document intelligence live here: a wrong IBAN is not a missing IBAN, and
`"100"` is not `100` unless the schema says string.

Cite: Hamel Husain's product-eval loop (error analysis on the failures that
matter); Anyformat-shaped field reports (per-field correctness, schema
validity, confidence gated elsewhere in stage 12).

DESIGN DECISION — four statuses, not a boolean.
    `correct` / `incorrect` / `missing` / `extra`. Collapsing missing into
    incorrect hides the two fixes (emit the field vs. fix the value) and
    makes precision/recall lie about which problem dominates.

DESIGN DECISION — type lives in the schema, not in Python's equality.
    `100 == "100"` is False in Python and True in half the harnesses that
    json.loads one side and leave the other as a model string. Coerce both
    sides through the declared type; a value that cannot coerce is incorrect.

DESIGN DECISION — micro over cells, macro over field names.
    Micro pools every (doc, path) cell. Macro averages per-field-name F1
    (list indices normalised to `[*]`). A rare billing field that is always
    wrong barely moves micro and tanks macro — that is the number a product
    owner asks for.
"""

from __future__ import annotations

from collections import defaultdict


def coerce(value, typ):
    """Coerce `value` to `typ` (str|int|float|bool). Raises ValueError on failure.

    bool is not int: isinstance(True, int) is True in Python, and a model that
    sent `true` for a count must not silently become 1.
    """
    if typ is str:
        if isinstance(value, (dict, list)):
            raise ValueError(f"cannot coerce {type(value).__name__} to str")
        return str(value)
    if typ is bool:
        if isinstance(value, bool):
            return value
        raise ValueError(f"cannot coerce {value!r} to bool")
    if typ is int:
        if isinstance(value, bool):
            raise ValueError("bool is not int")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value == int(value):
            return int(value)
        if isinstance(value, str):
            text = value.strip()
            if text.lstrip("-").isdigit() and text.count("-") <= 1:
                return int(text)
        raise ValueError(f"cannot coerce {value!r} to int")
    if typ is float:
        if isinstance(value, bool):
            raise ValueError("bool is not float")
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value.strip())
        raise ValueError(f"cannot coerce {value!r} to float")
    raise ValueError(f"unsupported type {typ!r}")


def _fmt(parts):
    out = []
    for p in parts:
        if isinstance(p, int):
            out.append(f"[{p}]")
        elif not out:
            out.append(str(p))
        else:
            out.append(f".{p}")
    return "".join(out)


def flatten(obj, schema, prefix=()):
    """Map path-string -> (raw_value, typ) for every schema leaf under obj.

    `schema` leaves are the types str/int/float/bool. A list field is written
    `[item_schema]` — one exemplar — and expands against each concrete item.
    Missing branches simply omit the path (caller distinguishes missing).
    """
    out = {}
    if isinstance(schema, dict):
        if not isinstance(obj, dict):
            return out
        for key, sub in schema.items():
            if key not in obj:
                continue
            out.update(flatten(obj[key], sub, prefix + (key,)))
        return out
    if isinstance(schema, list):
        if len(schema) != 1:
            raise ValueError("list schema must be a single exemplar: [item]")
        if not isinstance(obj, list):
            return out
        for i, item in enumerate(obj):
            out.update(flatten(item, schema[0], prefix + (i,)))
        return out
    # leaf
    out[_fmt(prefix)] = (obj, schema)
    return out


def _undeclared(obj, schema, prefix=()):
    """Yield (path, value) for keys present in obj but not in schema."""
    if not isinstance(schema, dict):
        return
    if not isinstance(obj, dict):
        return
    for key, value in obj.items():
        path = prefix + (key,)
        if key not in schema:
            yield _fmt(path), value
            continue
        sub = schema[key]
        if isinstance(sub, dict) and isinstance(value, dict):
            yield from _undeclared(value, sub, path)
        elif isinstance(sub, list) and isinstance(value, list) and sub:
            if isinstance(sub[0], dict):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        yield from _undeclared(item, sub[0], path + (i,))


def _expected_paths(gold, schema, prefix=()):
    """Every path the schema requires given this gold document's shape.

    List lengths come from gold (the reference). A gold list of length 2
    expects indices 0 and 1; the prediction is missing if it has fewer.
    """
    paths = set()
    if isinstance(schema, dict):
        if not isinstance(gold, dict):
            return paths
        for key, sub in schema.items():
            if key not in gold:
                # gold itself omitted a required field: still a required path
                # with no value — record the leaf paths as expected-empty.
                paths.update(_schema_paths(sub, prefix + (key,)))
            else:
                paths.update(_expected_paths(gold[key], sub, prefix + (key,)))
        return paths
    if isinstance(schema, list):
        if len(schema) != 1:
            raise ValueError("list schema must be a single exemplar: [item]")
        if not isinstance(gold, list):
            return _schema_paths(schema, prefix)
        for i, item in enumerate(gold):
            paths.update(_expected_paths(item, schema[0], prefix + (i,)))
        return paths
    paths.add(_fmt(prefix))
    return paths


def _schema_paths(schema, prefix=()):
    """Paths a schema declares, using [*] for list slots when no gold length."""
    if isinstance(schema, dict):
        out = set()
        for key, sub in schema.items():
            out.update(_schema_paths(sub, prefix + (key,)))
        return out
    if isinstance(schema, list):
        if len(schema) != 1:
            raise ValueError("list schema must be a single exemplar: [item]")
        return _schema_paths(schema[0], prefix + ("*",))
    return {_fmt(prefix)}


def compare_extraction(pred, gold, schema):
    """Compare one prediction to one gold under `schema`.

    Returns a list of {"path", "status", "pred", "gold"} with status in
    correct | incorrect | missing | extra.
    """
    if not isinstance(schema, dict):
        raise ValueError("schema must be a dict")
    pred_obj = pred if isinstance(pred, dict) else {}
    gold_obj = gold if isinstance(gold, dict) else {}

    gold_flat = flatten(gold_obj, schema)
    pred_flat = flatten(pred_obj, schema)
    expected = _expected_paths(gold_obj, schema)

    results = []
    for path in sorted(expected | set(pred_flat)):
        g = gold_flat.get(path)
        p = pred_flat.get(path)
        if g is not None and p is None:
            results.append({"path": path, "status": "missing",
                            "pred": None, "gold": g[0]})
            continue
        if g is None and p is not None:
            # pred has a schema leaf gold did not (e.g. longer list): incorrect
            results.append({"path": path, "status": "incorrect",
                            "pred": p[0], "gold": None})
            continue
        if g is None and p is None:
            continue
        g_raw, typ = g
        p_raw, _ = p
        try:
            g_c = coerce(g_raw, typ)
            p_c = coerce(p_raw, typ)
        except (ValueError, TypeError):
            results.append({"path": path, "status": "incorrect",
                            "pred": p_raw, "gold": g_raw})
            continue
        if typ is float:
            ok = abs(g_c - p_c) <= 1e-9
        else:
            ok = g_c == p_c
        results.append({"path": path,
                        "status": "correct" if ok else "incorrect",
                        "pred": p_raw, "gold": g_raw})

    for path, value in _undeclared(pred_obj, schema):
        results.append({"path": path, "status": "extra",
                        "pred": value, "gold": None})

    order = {"missing": 0, "incorrect": 1, "extra": 2, "correct": 3}
    results.sort(key=lambda r: (r["path"], order[r["status"]]))
    return results


def micro_scores(results):
    """Precision/recall/F1 over field cells.

    TP = correct; FP = incorrect + extra; FN = missing + incorrect.
    An incorrect value is both a bad prediction and a missed gold.
    """
    results = list(results)
    tp = sum(1 for r in results if r["status"] == "correct")
    fp = sum(1 for r in results if r["status"] in ("incorrect", "extra"))
    fn = sum(1 for r in results if r["status"] in ("missing", "incorrect"))
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * precision * recall / (precision + recall)
          if precision + recall else 0.0)
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": f1}


def _macro_key(path):
    out = []
    i = 0
    while i < len(path):
        if path[i] == "[":
            j = path.index("]", i)
            out.append("[*]")
            i = j + 1
        else:
            out.append(path[i])
            i += 1
    return "".join(out)


def macro_f1(results):
    """Mean of per-field-name F1s (list indices collapsed to [*])."""
    by = defaultdict(list)
    for r in results:
        by[_macro_key(r["path"])].append(r)
    if not by:
        return 1.0
    return sum(micro_scores(group)["f1"] for group in by.values()) / len(by)


def schema_valid(pred, schema):
    """True iff every declared leaf is present and coerces to its type.

    Extra keys do not invalidate — validity is 'can a downstream system read
    this', not 'is it right'. An empty list is valid for a list field.
    """
    if not isinstance(pred, dict) or not isinstance(schema, dict):
        return False
    return _valid(pred, schema)


def _valid(obj, schema):
    if isinstance(schema, dict):
        if not isinstance(obj, dict):
            return False
        for key, sub in schema.items():
            if key not in obj:
                return False
            if not _valid(obj[key], sub):
                return False
        return True
    if isinstance(schema, list):
        if not isinstance(obj, list) or len(schema) != 1:
            return False
        return all(_valid(item, schema[0]) for item in obj)
    try:
        coerce(obj, schema)
        return True
    except (ValueError, TypeError):
        return False


def extraction_report(pairs, schema):
    """Aggregate micro, macro and schema-validity over (pred, gold) pairs."""
    pairs = list(pairs)
    all_results = []
    n_valid = 0
    per_doc = []
    for pred, gold in pairs:
        results = compare_extraction(pred, gold, schema)
        all_results.extend(results)
        valid = schema_valid(pred, schema)
        n_valid += int(valid)
        per_doc.append({"micro_f1": micro_scores(results)["f1"],
                        "schema_valid": valid})
    micro = micro_scores(all_results) if all_results else {
        "tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0}
    return {
        "n": len(pairs),
        "schema_valid_rate": (n_valid / len(pairs)) if pairs else 1.0,
        "micro": micro,
        "macro_f1": macro_f1(all_results) if all_results else 1.0,
        "per_doc": per_doc,
    }


if __name__ == "__main__":
    schema = {
        "vendor": str,
        "amount": float,
        "line_items": [{"sku": str, "qty": int}],
    }
    gold = {"vendor": "Acme", "amount": 100.0,
            "line_items": [{"sku": "A", "qty": 2}]}
    pred = {"vendor": "Acme", "amount": "100",
            "line_items": [{"sku": "A", "qty": 2}], "notes": "x"}
    r = compare_extraction(pred, gold, schema)
    print([(x["path"], x["status"]) for x in r])
    print(micro_scores(r))
    print("valid", schema_valid(pred, schema))
