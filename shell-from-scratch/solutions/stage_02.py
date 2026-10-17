"""Shell From Scratch — stage 2: Expansion, in the order a shell must.

One text goes in and a tuple of words comes out, and the whole of the stage is
the order the five phases run in: **parameter**, **tilde**, **split**, **glob**,
**quote-removal** (`rules.EXPANSION_ORDER`). Parameter expansion is what puts
whitespace and glob metacharacters into a word that had none, the tilde is what
puts a path where one byte was, and the split and the glob are the two phases that
cut and match what the two before them produced — so a stage that runs them in
another order is not a stage that is slightly worse, it is a stage that answers a
different question. `expand` cuts the whole text and `expand_word` cuts one word;
the split is the one phase whose input is the *provenance* of a byte rather than
the byte, because a space inside a word is the word's own and a space a parameter
put there is a boundary.

The stage never writes the machine and never asks it for a process, a descriptor
or a byte. It knocks on two doors and no others: `machine.files()`, which is the
whole population a pattern is matched against (never a real directory), and
`machine.env()`, which is the only variable source a here-document has, because
§4.2 gives `here_document` no third argument. A failure is an `error` record —
`kind`, `offset`, `detail` — and it answers no payload at all, and a caller's
mistake (a text that is not a string, a state that is neither the shell's own
record nor a mapping of name to string) raises `machine.MachineError` naming the
offender, before a byte of the text is looked at.
"""

import machine

EXPAND_KEYS = ("text", "words", "error")

EXPAND_ERRORS = ("bad-substitution", "unset-variable", "bad-glob",
                 "here-document-unterminated")

_LITERAL = "literal"
_RESULT = "result"
_QUOTED = "quoted"
_ESCAPE = "escape"
_MARK = "mark"
_SPACE = " \t\n"
_METACHARS = "*?["
_FIRST = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"
_REST = _FIRST + "0123456789"


def _refuse(message):
    """A caller's mistake: the offender is named and the machine is not touched."""
    raise machine.MachineError(message)


def _record(kind, offset, detail):
    """§4.1's error shape: what failed, the byte in the text that failed, and the detail."""
    return {"kind": kind, "offset": offset, "detail": detail}


def _as_text(text, what):
    """The text, or the refusal naming what was handed over instead of one."""
    if not isinstance(text, str):
        _refuse("stage 2: %s is a string, and %r is not" % (what, text))
    return text


def _state(variables):
    """The variable table and the flags out of the shell's own state.

    The state is the house record — `{"variables": {name: value}, "flags":
    {"nounset": bool}}` — and a bare `{name: value}` mapping is that state with no
    flags on, so the plain call needs no ceremony. The fields another stage owns
    (`exported`, `traps`, `jobs`, `cwd`, `exit`, `args`, `stdin`) are read by
    nobody here and written by nobody here; a mapping that is neither shape, a
    variable whose value is not a string, or an option that is not a bool refuses
    with `machine.MachineError` naming the offender.
    """
    if not isinstance(variables, dict):
        _refuse("stage 2: the shell's variables are a mapping of name to value, and "
                "%r is not" % (variables,))
    inner = variables.get("variables")
    if inner is not None and not isinstance(inner, dict):
        _refuse("stage 2: the state's `variables` is a mapping of name to value, and "
                "%r is not" % (inner,))
    table = variables
    flags = {}
    if isinstance(inner, dict):
        if "flags" not in variables:
            _refuse("stage 2: the state holds a `variables` mapping but no `flags`, so "
                    "%r is neither a state nor a table" % (variables,))
        flags = variables["flags"]
        if not isinstance(flags, dict):
            _refuse("stage 2: the state's `flags` is a mapping of option to bool, and "
                    "%r is not" % (flags,))
        table = inner
    for name in table:
        if not isinstance(name, str):
            _refuse("stage 2: %r is not a variable name" % (name,))
        if not isinstance(table[name], str):
            _refuse("stage 2: the value of the variable %r is %r, and a variable's "
                    "value is a string" % (name, table[name]))
    for option in flags:
        if not isinstance(option, str):
            _refuse("stage 2: %r is not an option name" % (option,))
        if not isinstance(flags[option], bool):
            _refuse("stage 2: the option %r is %r, and an option is a bool"
                    % (option, flags[option]))
    return table, flags


def _value(table, name, nounset, offset):
    """The value of `name`: itself, nothing, or the `unset-variable` record of the refusal.

    A name that is not set and has no word of its own expands to nothing, and
    under `nounset` to the record that names it — with the offset of the `$` that
    asked for it.
    """
    if name in table:
        return table[name], None
    if nounset:
        return None, _record("unset-variable", offset,
                             "the variable %r is not set, and `nounset` is on" % (name,))
    return "", None


def _environment(machine):
    """The machine's own environment as a variable table: a here-document's only source."""
    table = {}
    for entry in machine.env():
        name, _, value = entry.partition("=")
        table[name] = value
    return table


def _flat(parts):
    """The bytes of `parts` in order: what a phase has produced, quotes and all."""
    return "".join(text for _, text in parts)


def _report(parts):
    """The parts written back as the text they came from: quote characters where they stood.

    `_flat` answers the bytes; this answers the text — the marker segments write
    the `'` and the `"` back exactly where the text had them, an escaped byte
    behind its `\\`, and a phase's own insertion as the bare bytes it put there —
    so an expansion's `text` is the word with its quoting still as written and
    its parameters already substituted. It is not the caller's input: `"$X"` with
    `X=a b` reports `"a b"`, and a text nothing touched reports itself.
    """
    out = []
    for kind, text in parts:
        if kind == _ESCAPE:
            out.append("\\" + text)
        else:
            out.append(text)
    return "".join(out)


def _has_metachar(text):
    """True when `text` holds a byte a pathname pattern would read as a metacharacter."""
    for byte in _METACHARS:
        if byte in text:
            return True
    return False


# --- phase one: the parameters -------------------------------------------------

def _name_is(name):
    """True when `name` is a name a variable may have: a letter or `_`, then letters, digits, `_`."""
    if name == "" or name[0] not in _FIRST:
        return False
    for byte in name:
        if byte not in _REST:
            return False
    return True


def _parameter(text, table, flags, base):
    """Phase one: `text` with its parameters expanded, its quotes still as written.

    Answers `(parts, error)`. `parts` is the text cut into runs — `literal` (as
    written and unquoted), `result` (what an expansion or a tilde inserted, also
    unquoted), `quoted` (a run inside `'` or `"`, whose bytes are content like any
    other but never split and never glob), `escape` (the one byte a backslash
    quoted) and `mark` (a quote character itself, which is not content at all and
    is written back only when the text's quoting is reported) — and `error` is
    `None` or §4.1's record, its offset counted from the start of the text this
    phase was handed, `base` being where that text begins in the caller's own. An
    expansion is never applied to its own result: what a `$NAME` is worth is
    bytes, and they are not scanned again.
    """
    parts = []
    kind = _LITERAL
    buffered = []
    at = 0
    size = len(text)

    def flush(which):
        if buffered:
            parts.append([which, "".join(buffered)])
            del buffered[:]

    while at < size:
        byte = text[at]
        if byte == "'" and kind != _QUOTED:
            flush(kind)
            close = text.find("'", at + 1)
            parts.append([_MARK, "'"])
            if close < 0:
                parts.append([_QUOTED, text[at + 1:]])
                at = size
            else:
                parts.append([_QUOTED, text[at + 1:close]])
                parts.append([_MARK, "'"])
                at = close + 1
            kind = _LITERAL
            continue
        if byte == '"':
            flush(kind)
            parts.append([_MARK, '"'])
            kind = _LITERAL if kind == _QUOTED else _QUOTED
            at = at + 1
            continue
        if byte == "\\":
            if at + 1 < size:
                flush(kind)
                parts.append([_ESCAPE, text[at + 1]])
                at = at + 2
                continue
            buffered.append(byte)
            at = at + 1
            continue
        if byte == "$":
            value, end, error = _at_dollar(text, at, table, flags, base)
            if error is not None:
                return None, error
            flush(kind)
            if value:
                parts.append([_QUOTED if kind == _QUOTED else _RESULT, value])
            at = end
            continue
        buffered.append(byte)
        at = at + 1
    flush(kind)
    return parts, None


def _at_dollar(text, at, table, flags, base):
    """The expansion that starts at `text[at]`: its value, the byte after it, its error.

    A `$` that starts nothing — the last byte of the text, or one followed by a
    byte no name and no `{` can begin with — is a `$` like any other, and stands.
    """
    size = len(text)
    after = at + 1
    if after >= size:
        return "$", after, None
    if text[after] == "{":
        return _braced(text, at, table, flags, base)
    if text[after] in _FIRST:
        end = after
        while end < size and text[end] in _REST:
            end = end + 1
        value, error = _value(table, text[after:end],
                              flags.get("nounset", False) is True, base + at)
        if error is not None:
            return None, end, error
        return value, end, None
    return "$", after, None


def _braced(text, at, table, flags, base):
    """The `${...}` that starts at `text[at]`: its value, the byte after its `}`, its error.

    The grammar is exactly `${NAME}`, `${NAME:-word}`, `${NAME:+word}`,
    `${NAME#prefix}`, `${NAME%Suffix}` and `${#NAME}`: braces do not nest, the
    word of `:-` and `:+` is expanded once itself, the operand of `#` and `%` is
    literal, and anything else is a `bad-substitution`.
    """
    close = text.find("}", at + 2)
    if close < 0:
        return None, len(text), _record("bad-substitution", base + at,
                                        "the substitution that starts here is never "
                                        "closed: `${...}` needs its `}`")
    body = text[at + 2:close]
    if "{" in body:
        return None, close + 1, _record("bad-substitution", base + at,
                                        "the body %r holds a `{`, and braces do not nest"
                                        % (body,))
    nounset = flags.get("nounset", False) is True
    if body.startswith("#"):
        name = body[1:]
        if not _name_is(name):
            return None, close + 1, _record("bad-substitution", base + at,
                                            "%r is not a variable name" % (name,))
        value, error = _value(table, name, nounset, base + at)
        if error is not None:
            return None, close + 1, error
        return str(len(value)), close + 1, None
    end = 0
    while end < len(body) and body[end] in _REST:
        end = end + 1
    name = body[:end]
    if not _name_is(name):
        return None, close + 1, _record("bad-substitution", base + at,
                                        "%r does not begin with a variable name"
                                        % (body,))
    rest = body[end:]
    if rest == "":
        value, error = _value(table, name, nounset, base + at)
        if error is not None:
            return None, close + 1, error
        return value, close + 1, None
    if rest[0] == ":":
        if len(rest) < 2 or rest[1] not in ("-", "+"):
            return None, close + 1, _record("bad-substitution", base + at,
                                            "the operator %r is not one of `${NAME:-}`, "
                                            "`${NAME:+}`, `${NAME#}`, `${NAME%%}`"
                                            % (rest,))
        value, error = _value(table, name, False, base + at)
        if error is not None:
            return None, close + 1, error
        wanted = (rest[1] == "-" and value == "") or (rest[1] == "+" and value != "")
        if not wanted:
            return ("" if rest[1] == "+" else value), close + 1, None
        operand = rest[2:]
        parts, error = _parameter(operand, table, flags, base + close - len(operand))
        if error is not None:
            return None, close + 1, error
        return _flat(parts), close + 1, None
    if rest[0] in ("#", "%"):
        operand = rest[1:]
        if operand.startswith(rest[0]):
            return None, close + 1, _record("bad-substitution", base + at,
                                            "`%s%s` is a pattern's operator, and this "
                                            "grammar's operand is one literal"
                                            % (rest[0], rest[0]))
        value, error = _value(table, name, nounset, base + at)
        if error is not None:
            return None, close + 1, error
        if rest[0] == "#" and value.startswith(operand):
            value = value[len(operand):]
        if rest[0] == "%" and operand != "" and value.endswith(operand):
            value = value[:len(value) - len(operand)]
        return value, close + 1, None
    return None, close + 1, _record("bad-substitution", base + at,
                                    "the operator %r is not one of `${NAME:-}`, "
                                    "`${NAME:+}`, `${NAME#}`, `${NAME%%}`" % (rest,))


# --- phase two: the tilde ------------------------------------------------------

def _tilde(parts, table, one_word):
    """Phase two: a leading `~` of a word becomes `HOME`, and nothing else does.

    A tilde is the first byte of a word — the text's own first byte, or the byte
    after an unquoted space — and only when a `/` or the end of the word follows
    it: `~user` is left alone, because this machine has no user table, and a
    quoted or backslashed `~` is a byte like any other. The path arrives as an
    unquoted insertion, so the split that follows cuts it: a `HOME` that carries
    a space makes two words, which is what running this phase before that one
    means. A table with no `HOME` leaves the `~` where it was.
    """
    home = table.get("HOME")
    if home is None:
        return parts
    flat = _flat(parts)
    starts = []
    offset = 0
    fresh = True
    for kind, text in parts:
        if kind in (_LITERAL, _RESULT):
            local = 0
            for byte in text:
                if byte in _SPACE:
                    if not one_word:
                        fresh = True
                elif fresh:
                    starts.append(offset + local)
                    fresh = False
                local = local + 1
        elif text:
            fresh = False
        offset = offset + len(text)
    chosen = []
    for where in starts:
        if flat[where] == "~" and (where + 1 == len(flat) or flat[where + 1] == "/"):
            chosen.append(where)
    if not chosen:
        return parts
    made = []
    offset = 0
    which = 0
    for kind, text in parts:
        here = []
        while which < len(chosen) and chosen[which] < offset + len(text):
            here.append(chosen[which] - offset)
            which = which + 1
        if not here:
            made.append([kind, text])
        else:
            cut = 0
            for local in here:
                head = text[cut:local]
                if head:
                    made.append([kind, head])
                made.append([_RESULT, home])
                cut = local + 1
            tail = text[cut:]
            if tail:
                made.append([kind, tail])
        offset = offset + len(text)
    return made


# --- phase three: the split ----------------------------------------------------

def _split(parts, one_word):
    """Phase three: the parts cut into fields on unquoted whitespace.

    A run of unquoted whitespace is a boundary and is not itself a field, an
    empty field is not a word — except a field that was quoted, because `""` is a
    word and `$UNSET` is not. `one_word` is the whole of the `expand` /
    `expand_word` difference: a word the lexer handed over is one word, so its
    own literal whitespace stays inside it and only the whitespace a `result`
    segment carries cuts, while a text that may hold several words is cut on
    every unquoted space it has.
    """
    fields = []
    field = []

    def close():
        if field:
            fields.append(tuple(field))
            del field[:]

    for kind, text in parts:
        if kind == _RESULT or (kind == _LITERAL and not one_word):
            buffered = []
            for byte in text:
                if byte not in _SPACE:
                    buffered.append(byte)
                    continue
                if buffered:
                    field.append((kind, "".join(buffered)))
                    del buffered[:]
                close()
            if buffered:
                field.append((kind, "".join(buffered)))
        else:
            field.append((kind, text))
    close()
    return fields


# --- phase four: the glob ------------------------------------------------------

def _class_end(pattern, at):
    """The byte of the `]` closing the class opened at `pattern[at]`, or `-1`.

    A `]` in the class's first position is a member and not the end — `[]a]` is
    the class of `]` and `a` — and a class the pattern never closes is not a
    class at all.
    """
    index = at + 1
    if index < len(pattern) and pattern[index] in ("!", "^"):
        index = index + 1
    if index < len(pattern) and pattern[index] == "]":
        index = index + 1
    while index < len(pattern) and pattern[index] != "]":
        index = index + 1
    if index >= len(pattern):
        return -1
    return index


def _in_class(pattern, at, close, byte):
    """True when `byte` is a member of the class `pattern[at:close + 1]` names."""
    body = pattern[at + 1:close]
    negate = False
    if body.startswith("!") or body.startswith("^"):
        negate = True
        body = body[1:]
    hit = False
    index = 0
    while index < len(body):
        if index + 2 < len(body) and body[index + 1] == "-":
            if body[index] <= byte <= body[index + 2]:
                hit = True
            index = index + 3
        else:
            if body[index] == byte:
                hit = True
            index = index + 1
    if hit == negate:
        return False
    return True


def _match_at(pattern, at, path, which):
    """True when `pattern[at:]` matches `path[which:]`, no part of a pattern crossing a `/`."""
    while at < len(pattern):
        byte = pattern[at]
        if byte == "*":
            rest = at
            while rest < len(pattern) and pattern[rest] == "*":
                rest = rest + 1
            here = which
            while True:
                if _match_at(pattern, rest, path, here):
                    return True
                if here >= len(path) or path[here] == "/":
                    return False
                here = here + 1
        if byte == "?":
            if which >= len(path) or path[which] == "/":
                return False
            at = at + 1
            which = which + 1
            continue
        if byte == "[":
            close = _class_end(pattern, at)
            if close < 0 or which >= len(path) or path[which] == "/" \
                    or not _in_class(pattern, at, close, path[which]):
                return False
            at = close + 1
            which = which + 1
            continue
        if which >= len(path) or path[which] != byte:
            return False
        at = at + 1
        which = which + 1
    if which == len(path):
        return True
    return False


def _matches(pattern, path):
    """True when the whole `path` matches `pattern`."""
    return _match_at(pattern, 0, path, 0)


def _class_error(pattern):
    """The byte of a `[` whose class is never closed, or `None` when every class closes."""
    at = 0
    while at < len(pattern):
        if pattern[at] != "[":
            at = at + 1
            continue
        close = _class_end(pattern, at)
        if close < 0:
            return at
        at = close + 1
    return None


def _matched(machine, pattern):
    """The paths of `machine.files()` that `pattern` matches, or the `bad-glob` record.

    A pattern with no metacharacter is not a pattern: it answers itself, and the
    machine is not asked at all. A pattern that matches nothing answers itself
    too, because that is the word the command line keeps. Everything else is the
    machine's own population, in sorted order.
    """
    if not _has_metachar(pattern):
        return (pattern,), None
    broken = _class_error(pattern)
    if broken is not None:
        return None, _record("bad-glob", broken,
                             "the class that opens at byte %d of %r is never closed"
                             % (broken, pattern))
    matches = []
    for path in machine.files():
        if _matches(pattern, path):
            matches.append(path)
    if not matches:
        return (pattern,), None
    return tuple(sorted(matches)), None


def _globbed(machine, fields):
    """Phase four itself: every field that holds an unquoted metacharacter becomes its matches.

    Answers `(words, error)`: `words` is the fields, each globbed one replaced by
    its paths — several words where one was — and `error` is `None` or the
    `bad-glob` record. A metacharacter inside quotes, or one a backslash quoted,
    is a byte like any other and does not make the field a pattern.
    """
    words = []
    for field in fields:
        unquoted = False
        for kind, text in field:
            if kind in (_LITERAL, _RESULT) and _has_metachar(text):
                unquoted = True
        if not unquoted:
            words.append(field)
            continue
        paths, error = _matched(machine, _word(field))
        if error is not None:
            return None, error
        for path in paths:
            words.append(((_LITERAL, path),))
    return words, None


# --- phase five, and the two texts a here-document needs -----------------------

def _word(field):
    """The field's bytes with its quoting resolved: phase five's answer for one field.

    A quote character is not content — it stops splitting and globbing while the
    phases run and it is gone when they are over — and an escaped byte is the
    byte it escaped.
    """
    return "".join(text for kind, text in field if kind != _MARK)


def _unquoted(fields):
    """Phase five: the fields with their quotes and their backslashes resolved away."""
    return tuple(_word(field) for field in fields)


def _delimiter(line):
    """The delimiter a here-document's first line names: its quotes removed, nothing expanded.

    A `$` in the line is a `$`: the delimiter is a word, not a word to be
    expanded, and what its quoting decides is whether the document expands, which
    the caller states with `quoted`.
    """
    out = []
    at = 0
    size = len(line)
    while at < size:
        byte = line[at]
        if byte in ("'", '"'):
            close = line.find(byte, at + 1)
            if close < 0:
                out.append(line[at + 1:])
                at = size
            else:
                out.append(line[at + 1:close])
                at = close + 1
            continue
        if byte == "\\" and at + 1 < size:
            out.append(line[at + 1])
            at = at + 2
            continue
        out.append(byte)
        at = at + 1
    return "".join(out)


# --- the surface ---------------------------------------------------------------

def _nothing(error):
    """The record a failed expansion answers: the error, and no payload at all."""
    return {"text": None, "words": (), "error": error}


def _expanded(machine, text, variables, one_word):
    """The five phases in `rules.EXPANSION_ORDER`'s order, and the record they answer.

    `text` is the text after the parameter and tilde phases — quotes as written,
    before the split cut it and before the glob replaced it — and `words` is what
    the five left. `one_word` is the whole difference between `expand` and
    `expand_word`.
    """
    text = _as_text(text, "the text to expand")
    table, flags = _state(variables)
    parts, error = _parameter(text, table, flags, 0)          # 1 parameter
    if error is not None:
        return _nothing(error)
    parts = _tilde(parts, table, one_word)                    # 2 tilde
    fields = _split(parts, one_word)                          # 3 split
    fields, error = _globbed(machine, fields)                 # 4 glob
    if error is not None:
        return _nothing(error)
    return {"text": _report(parts),                            # 5 quote-removal
            "words": _unquoted(fields), "error": None}


def expand(machine, text, variables):
    """The words a whole `text` expands to, by the five phases in their order.

    `text` may hold several words, so the split cuts it on every unquoted space;
    the record is `EXPAND_KEYS` and a failed expansion answers `text = None` with
    no words. `variables` is the shell's state or a bare table, and a record that
    is neither refuses with `machine.MachineError` before a byte is looked at.
    """
    return _expanded(machine, text, variables, False)


def expand_word(machine, text, variables):
    """The words one word expands to: the same phases, cut only where an expansion cut.

    The word the lexer handed over is one word, so a space that was already in it
    stays in it; the whitespace a parameter or a tilde put there splits, because
    that phase ran before this one.
    """
    return _expanded(machine, text, variables, True)


def substitute(machine, text, variables):
    """Phase one and nothing else: `text` with its parameters expanded, quotes as written.

    The whole grammar — `${NAME}`, `$NAME`, `${NAME:-word}`, `${NAME:+word}`,
    `${NAME#prefix}`, `${NAME%Suffix}`, `${#NAME}` — and the answer is
    `{"text", "error"}`: the text after the phase, or `None` with the record of a
    `bad-substitution` whose body is outside the grammar, or of an
    `unset-variable` under `nounset`. Nothing here splits, globs, expands a
    tilde or removes a quote.
    """
    text = _as_text(text, "the text to substitute")
    table, flags = _state(variables)
    parts, error = _parameter(text, table, flags, 0)
    if error is not None:
        return {"text": None, "error": error}
    return {"text": _report(parts), "error": None}


def glob(machine, pattern):
    """The machine's own paths that `pattern` matches, in sorted order.

    `machine.files()` is the whole population and a pattern that matches nothing
    comes back as written; a pattern with no metacharacter answers itself without
    asking the machine. Answers `{"paths", "error"}` — `paths` is `None` when
    `error` is the record of a class that is never closed — and a `pattern` that
    is not a string raises `machine.MachineError` naming it.
    """
    if not isinstance(pattern, str):
        _refuse("stage 2: a pattern is a string, and %r is not" % (pattern,))
    paths, error = _matched(machine, pattern)
    return {"paths": paths, "error": error}


def here_document(machine, body, quoted):
    """The bytes of a `<<` body: its delimiter's line first, its terminator line last.

    The document is every line between the delimiter line and the first line that
    is exactly the delimiter with its quotes removed, each with its newline, and
    `quoted` says whether that delimiter was quoted: quoted, the bytes stand as
    written; unquoted, parameters expand from the machine's own environment and
    nothing else happens — no split, no glob, because a here-document is bytes
    and not words. Answers `{"bytes", "error"}`, `bytes` being `None` when a
    `here-document-unterminated` or a `bad-substitution` is named instead.
    """
    body = _as_text(body, "a here-document's body")
    if not isinstance(quoted, bool):
        _refuse("stage 2: whether a here-document's delimiter was quoted is a bool, "
                "and %r is not" % (quoted,))
    lines = body.split("\n")
    delimiter = _delimiter(lines[0])
    taken = []
    closed = False
    for line in lines[1:]:
        if line == delimiter:
            closed = True
            break
        taken.append(line)
    if not closed:
        return {"bytes": None,
                "error": _record("here-document-unterminated", len(body),
                                 "the delimiter %r never appears on a line of its own"
                                 % (delimiter,))}
    document = "".join(line + "\n" for line in taken)
    if quoted:
        return {"bytes": document.encode(), "error": None}
    parts, error = _parameter(document, _environment(machine), {},
                              len(lines[0]) + 1)
    if error is not None:
        return {"bytes": None, "error": error}
    return {"bytes": _flat(parts).encode(), "error": None}
