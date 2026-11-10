"""Un intérprete mínimo de SAS para las etapas de este curso.

No pretende ser SAS: implementa el subconjunto que usan las etapas y lo hace
determinista, sin reloj ni red. El objetivo es que el alumno escriba DATA steps
y PROC reales, y que el corrector ejecute ese código en vez de mirar el texto.

Soporta:

  data / set / merge / by / where
  asignación, suma automática (`total + importe;`)
  if / then / else / do / end
  do i = a to b [by c]
  retain, output, delete, keep, drop
  first.variable / last.variable / _n_
  expresiones con + - * / **, comparaciones, and/or/not
  funciones sum, mean, min, max, int, round, abs, coalesce, missing, nmiss,
             upcase, lowcase, compress, substr, index, strip
  proc sort, proc means (sum/n/mean/min/max)

Lo que no soporta lo rechaza con `SasError`; una etapa nunca pasa por ignorar
silencio. Las tablas de entrada son `list[dict]` y todas las salidas quedan en
memoria. El dinero se lleva en céntimos y los tipos en puntos básicos: no hay
coma flotante en los datos del curso.
"""

from __future__ import annotations

import re
from pathlib import Path


class SasError(ValueError):
    """El programa usa una construcción que este intérprete no acepta."""


class Table:
    """Una tabla SAS: filas homogéneas y acceso por columna."""

    def __init__(self, rows=None):
        self.rows = [dict(row) for row in (rows or [])]

    def __len__(self):
        return len(self.rows)

    def __iter__(self):
        return iter(self.rows)

    def __getitem__(self, index):
        return self.rows[index]

    def column(self, name):
        return [row.get(name) for row in self.rows]

    def sum(self, name):
        return sum(value for value in self.column(name) if value is not None)

    def one(self):
        if len(self.rows) != 1:
            raise SasError(f"se esperaba una fila y hay {len(self.rows)}")
        return self.rows[0]


def _round(value, unit=1):
    """Redondeo SAS: mitad fuera de cero, no el empate al par de Python."""
    if unit == 0:
        return value
    scaled = value / unit
    if scaled >= 0:
        return int(scaled + 0.5) * unit
    return -int(-scaled + 0.5) * unit


def _sum(*values):
    return sum(value for value in values if value is not None)


def _mean(*values):
    clean = [value for value in values if value is not None]
    return sum(clean) / len(clean) if clean else None


def _min(*values):
    clean = [value for value in values if value is not None]
    return min(clean) if clean else None


def _max(*values):
    clean = [value for value in values if value is not None]
    return max(clean) if clean else None


def _coalesce(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _missing(value):
    return value is None


def _nmiss(*values):
    return sum(1 for value in values if value is None)


def _upcase(value):
    return None if value is None else str(value).upper()


def _lowcase(value):
    return None if value is None else str(value).lower()


def _compress(value):
    return None if value is None else re.sub(r"\s+", "", str(value))


def _substr(value, start, length=None):
    if value is None:
        return None
    start = int(start) - 1
    return str(value)[start:] if length is None else str(value)[start:start + int(length)]


def _index(value, needle):
    if value is None or needle is None:
        return 0
    return str(value).find(str(needle)) + 1


def _strip(value):
    return None if value is None else str(value).strip()


FUNCTIONS = {
    "sum": _sum, "mean": _mean, "min": _min, "max": _max,
    "int": lambda value: int(value), "round": _round, "abs": abs,
    "coalesce": _coalesce, "missing": _missing, "nmiss": _nmiss,
    "upcase": _upcase, "lowcase": _lowcase, "compress": _compress,
    "substr": _substr, "index": _index, "strip": _strip,
}


def _clean_source(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.S)
    source = re.sub(r"(?m)^\s*\*[^;]*;", " ", source)
    return source


def _statements(source: str):
    parts = []
    current = []
    quote = None
    for char in _clean_source(source):
        if quote:
            current.append(char)
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
            current.append(char)
        elif char == ";":
            statement = "".join(current).strip()
            if statement:
                parts.append(statement)
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _name(token: str) -> str:
    return token.strip().lower().split(".")[-1]


def _split_names(text: str):
    return [part.strip() for part in text.replace(",", " ").split() if part.strip()]


def _split_assignment(statement: str):
    quote = None
    for index, char in enumerate(statement):
        if quote:
            if char == quote:
                quote = None
        elif char in ("'", '"'):
            quote = char
        elif char == "=":
            before = statement[index - 1] if index else ""
            after = statement[index + 1] if index + 1 < len(statement) else ""
            if before not in "<>!=" and after != "=":
                return statement[:index].strip(), statement[index + 1:].strip()
    return None, None


def _translate(expression: str) -> str:
    text = expression.strip()
    text = re.sub(r"\b(first|last)\.([A-Za-z_]\w*)", r"__\1_\2", text, flags=re.I)
    text = text.replace("<>", "!=").replace("^=", "!=")
    text = re.sub(r"(?<![<>=!])=(?!=)", "==", text)
    text = re.sub(r"(?<![\w.])\.(?![\w.])", "None", text)
    text = re.sub(r"\bmissing\s*\(", "_missing(", text, flags=re.I)
    return text


def _evaluate(expression: str, env: dict):
    try:
        text = " ".join(expression.split())
        return eval(_translate(text), {"__builtins__": {}}, {**FUNCTIONS, **env})
    except SasError:
        raise
    except Exception as exc:
        raise SasError(f"no se pudo evaluar «{expression}»: {exc}") from exc


def _condition(expression: str, env: dict):
    value = _evaluate(expression, env)
    return bool(value)


def _simple(statement: str):
    text = statement.strip()
    lower = text.lower()
    if lower in ("output", "delete", "stop"):
        return (lower,)
    if lower.startswith("retain "):
        rest = text[7:].strip()
        parts = rest.split(None, 1)
        return ("retain", parts[0], parts[1] if len(parts) > 1 else "0")
    if lower.startswith("keep "):
        return ("keep", _split_names(text[5:]))
    if lower.startswith("drop "):
        return ("drop", _split_names(text[5:]))
    if lower.startswith("where "):
        return ("where", text[6:].strip())
    if lower.startswith("set "):
        return ("set", _split_names(text[4:]))
    if lower.startswith("merge "):
        return ("merge", _split_names(text[6:]))
    if lower.startswith("by "):
        return ("by", _split_names(text[3:]))
    if lower.startswith(("length ", "format ", "informat ", "label ", "attrib ", "array ")):
        return ("noop",)
    if lower.startswith("put "):
        return ("noop",)
    name, value = _split_assignment(text)
    if name and re.match(r"^[A-Za-z_]\w*$", name) and value:
        return ("assign", name.lower(), value)
    match = re.match(r"^([A-Za-z_]\w*)\s*\+\s*(.+)$", text)
    if match:
        return ("sum", match.group(1).lower(), match.group(2))
    raise SasError(f"sentencia no soportada: {statement!r}")


def _parse_nodes(statements, index=0):
    nodes = []
    while index < len(statements):
        statement = statements[index].strip()
        lower = statement.lower()
        if lower in ("end", "run", "quit") or lower.startswith("else"):
            break
        if lower.startswith("if "):
            match = re.match(r"if\s+(.+?)\s+then\b\s*(.*)$", statement, re.I | re.S)
            if not match:
                nodes.append(("if", statement[2:].strip(), [], [("delete",)]))
                index += 1
                continue
            condition, rest = match.group(1).strip(), match.group(2).strip()
            if rest == "":
                index += 1
                rest = statements[index] if index < len(statements) else ""
                if not rest:
                    raise SasError("IF sin THEN ni sentencia")
            if rest.lower() == "do":
                body, index = _parse_nodes(statements, index + 1)
            else:
                body = [_simple(rest)]
                index += 1
            otherwise = []
            if index < len(statements) and statements[index].lower().startswith("else"):
                tail = re.sub(r"^else\b\s*", "", statements[index], flags=re.I).strip()
                index += 1
                if tail == "":
                    tail = statements[index] if index < len(statements) else ""
                    if not tail:
                        raise SasError("ELSE sin sentencia")
                    index += 1
                if tail.lower() == "do":
                    otherwise, index = _parse_nodes(statements, index + 1)
                else:
                    otherwise = [_simple(tail)]
            nodes.append(("if", condition, body, otherwise))
        elif lower == "do":
            body, index = _parse_nodes(statements, index + 1)
            nodes.append(("do", body))
        elif re.match(r"^do\s+[A-Za-z_]\w*\s*=\s*.+?\s+to\s+.+$", statement, re.I):
            match = re.match(
                r"^do\s+([A-Za-z_]\w*)\s*=\s*(.+?)\s+to\s+(.+?)(?:\s+by\s+(.+))?$",
                statement, re.I)
            body, index = _parse_nodes(statements, index + 1)
            nodes.append(("loop", match.group(1).lower(), match.group(2).strip(),
                          match.group(3).strip(), (match.group(4) or "1").strip(), body))
        elif lower == "end":
            index += 1
            break
        else:
            nodes.append(_simple(statement))
            index += 1
    return nodes, index


def _has_output(nodes):
    for node in nodes:
        if node[0] == "output":
            return True
        for part in node[1:]:
            if isinstance(part, list) and _has_output(part):
                return True
    return False


def _put(tables, name, rows):
    key = _name(name)
    table = Table(rows)
    tables[key] = table
    tables["work." + key] = table


def _get(tables, name):
    key = _name(name)
    for candidate in (key, "work." + key):
        if candidate in tables:
            return tables[candidate]
    raise SasError(f"no existe la tabla {name!r}")


def _rows(sorted_rows, by):
    rows = [dict(row) for row in sorted_rows]
    if not by:
        return rows
    previous = {}
    for row in rows:
        key = tuple(row.get(name) for name in by)
        for position, name in enumerate(by):
            row["__first_" + name] = previous.get(name) != key[position]
        previous = dict(zip(by, key))
    following = {}
    for row in reversed(rows):
        key = tuple(row.get(name) for name in by)
        for position, name in enumerate(by):
            row["__last_" + name] = following.get(name) != key[position]
        following = dict(zip(by, key))
    return rows


def _merge_tables(tables, names, by):
    tables_in = [_get(tables, name) for name in names]
    if not by:
        length = max(len(table) for table in tables_in)
        rows = []
        for index in range(length):
            merged = {}
            for table in tables_in:
                if index < len(table):
                    merged.update(table[index])
            rows.append(merged)
        return rows
    merged_by_key = {}
    order = []
    for table in tables_in:
        for row in table:
            key = tuple(row.get(name) for name in by)
            if key not in merged_by_key:
                merged_by_key[key] = {}
                order.append(key)
            merged_by_key[key].update(row)
    order.sort()
    return [merged_by_key[key] for key in order]


def _execute(nodes, env, output, state):
    for node in nodes:
        kind = node[0]
        if kind == "assign":
            env[node[1]] = _evaluate(node[2], env)
        elif kind == "sum":
            env[node[1]] = _sum(env.get(node[1]), _evaluate(node[2], env))
        elif kind == "if":
            branch = node[2] if _condition(node[1], env) else node[3]
            _execute(branch, env, output, state)
        elif kind == "do":
            _execute(node[1], env, output, state)
        elif kind == "loop":
            start = int(_evaluate(node[2], env))
            end = int(_evaluate(node[3], env))
            step = int(_evaluate(node[4], env))
            if step == 0:
                raise SasError("el paso de un DO no puede ser cero")
            for value in range(start, end + (1 if step > 0 else -1), step):
                env[node[1]] = value
                _execute(node[5], env, output, state)
        elif kind == "output":
            output.append(dict(env))
        elif kind == "delete":
            state["deleted"] = True
        elif kind == "retain":
            state["retain"].setdefault(node[1], _evaluate(node[2], env))
        elif kind == "keep":
            state["keep"] = [name.lower() for name in node[1]]
        elif kind == "drop":
            state["drop"] = [name.lower() for name in node[1]]
        elif kind in ("where", "set", "merge", "by", "noop", "stop"):
            continue
        else:
            raise SasError(f"nodo desconocido: {node!r}")


def _parse_data(statements, index, tables):
    header = statements[index]
    match = re.match(r"data\s+([\w.]+)", header, re.I)
    if not match:
        raise SasError(f"DATA inválido: {header!r}")
    dataset_name = match.group(1)
    index += 1
    body = []
    while index < len(statements) and statements[index].lower() not in ("run", "quit"):
        body.append(statements[index])
        index += 1
    index += 1

    inputs = []
    merged = []
    by = []
    where = None
    for statement in body:
        lower = statement.lower()
        if lower.startswith("set "):
            inputs = _split_names(statement[4:])
        elif lower.startswith("merge "):
            merged = _split_names(statement[6:])
        elif lower.startswith("where "):
            where = statement[6:].strip()
        elif lower.startswith("by "):
            by = _split_names(statement[3:])
    nodes, _ = _parse_nodes([statement for statement in body
                             if not re.match(r"^(set|merge|where|by)\b", statement, re.I)])

    if merged:
        rows = _merge_tables(tables, merged, by)
    elif inputs:
        rows = []
        for input_name in inputs:
            rows.extend(_get(tables, input_name).rows)
    else:
        rows = [{}]

    if where:
        rows = [row for row in rows if bool(_evaluate(where, {**row, "_n_": 0}))]
    rows = _rows(rows, by)

    retained = {}
    sum_vars = set()
    for node in nodes:
        if node[0] == "retain":
            retained[node[1]] = _evaluate(node[2], {})
        elif node[0] == "sum":
            sum_vars.add(node[1])
    sum_state = {}
    output = []
    has_output = _has_output(nodes)
    keep = None
    drop = set()
    for position, input_row in enumerate(rows, start=1):
        env = {key: value for key, value in input_row.items() if not key.startswith("__")}
        env["_n_"] = position
        for name, value in input_row.items():
            if name.startswith("__"):
                env[name] = value
        for name in retained:
            if name not in env:
                env[name] = retained[name]
        for name in sum_vars:
            env.setdefault(name, sum_state.get(name, 0))
        state = {"deleted": False, "retain": retained, "keep": keep, "drop": drop}
        _execute(nodes, env, output, state)
        keep = state["keep"]
        drop = state["drop"]
        for name in retained:
            retained[name] = env.get(name)
        for name in sum_vars:
            sum_state[name] = env.get(name, 0)
        if not state["deleted"] and not has_output:
            output.append(dict(env))

    final = []
    for row in output:
        clean = {key: value for key, value in row.items()
                 if not key.startswith("__") and key != "_n_"}
        if keep is not None:
            clean = {key: clean.get(key) for key in keep}
        for key in drop:
            clean.pop(key, None)
        final.append(clean)
    _put(tables, dataset_name, final)
    return index


def _parse_sort(statements, index, tables):
    header = statements[index]
    data_match = re.search(r"data\s*=\s*([\w.]+)", header, re.I)
    out_match = re.search(r"out\s*=\s*([\w.]+)", header, re.I)
    if not data_match:
        raise SasError("PROC SORT sin DATA=")
    index += 1
    by = []
    descending = set()
    while index < len(statements) and statements[index].lower() not in ("run", "quit"):
        statement = statements[index]
        if statement.lower().startswith("by "):
            for token in _split_names(statement[3:]):
                if token.lower() == "descending":
                    continue
                if token.lower().startswith("descending"):
                    descending.add(token[10:].lower())
                else:
                    by.append(token)
        index += 1
    index += 1
    rows = [dict(row) for row in _get(tables, data_match.group(1)).rows]
    for name in reversed(by):
        rows.sort(key=lambda row: (row.get(name) is None, row.get(name)),
                  reverse=name.lower() in descending)
    _put(tables, out_match.group(1) if out_match else data_match.group(1), rows)
    return index


def _parse_means(statements, index, tables):
    header = statements[index]
    data_match = re.search(r"data\s*=\s*([\w.]+)", header, re.I)
    if not data_match:
        raise SasError("PROC MEANS sin DATA=")
    index += 1
    class_vars = []
    var_vars = []
    output_out = None
    output_specs = []
    while index < len(statements) and statements[index].lower() not in ("run", "quit"):
        statement = statements[index]
        lower = statement.lower()
        if lower.startswith("class "):
            class_vars = _split_names(statement[6:])
        elif lower.startswith("var "):
            var_vars = _split_names(statement[4:])
        elif lower.startswith("output "):
            out_match = re.search(r"out\s*=\s*([\w.]+)", statement, re.I)
            output_out = out_match.group(1) if out_match else None
            for stat, targets in re.findall(r"(sum|n|mean|min|max)\s*=\s*([\w\s]+)", statement, re.I):
                names = _split_names(targets)
                for position, target in enumerate(names):
                    source = var_vars[position] if position < len(var_vars) else (var_vars[0] if var_vars else None)
                    if source:
                        output_specs.append((stat.lower(), source, target))
        index += 1
    index += 1
    if not output_out:
        return index
    rows = [dict(row) for row in _get(tables, data_match.group(1)).rows]
    groups = {}
    for row in rows:
        key = tuple(row.get(name) for name in class_vars)
        groups.setdefault(key, []).append(row)
    result = []
    for key, group in groups.items():
        row = dict(zip(class_vars, key))
        for stat, source, target in output_specs:
            values = [item.get(source) for item in group if item.get(source) is not None]
            if stat == "sum":
                row[target] = sum(values)
            elif stat == "n":
                row[target] = len(values)
            elif stat == "mean":
                row[target] = sum(values) / len(values) if values else None
            elif stat == "min":
                row[target] = min(values) if values else None
            elif stat == "max":
                row[target] = max(values) if values else None
        result.append(row)
    _put(tables, output_out, result)
    return index


def run(source: str, tables=None):
    """Ejecuta un programa SAS y devuelve todas las tablas resultantes."""
    tables = dict(tables or {})
    statements = _statements(source)
    index = 0
    while index < len(statements):
        statement = statements[index]
        lower = statement.lower()
        if lower.startswith("data "):
            index = _parse_data(statements, index, tables)
        elif lower.startswith("proc sort"):
            index = _parse_sort(statements, index, tables)
        elif lower.startswith("proc means"):
            index = _parse_means(statements, index, tables)
        elif lower.startswith(("proc print", "proc freq", "proc transpose", "proc sql")):
            while index < len(statements) and statements[index].lower() not in ("run", "quit"):
                index += 1
            index += 1
        elif lower.startswith(("libname", "options", "title", "footnote")):
            index += 1
        elif lower in ("run", "quit"):
            index += 1
        else:
            raise SasError(f"sentencia global no soportada: {statement!r}")
    return tables


def run_file(path, tables=None):
    source = Path(path).read_text(encoding="utf-8")
    return run(source, tables=tables)
