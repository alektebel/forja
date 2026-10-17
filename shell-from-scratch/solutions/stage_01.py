"""Shell From Scratch — stage 1: The line, the word and the operator.

A line of text, and the two things a shell has to do before anything can run:
split it into the tokens its grammar is written in, and group those tokens into
the lists, pipelines and commands a plan can be made from. Nothing here has a
machine, a program or a descriptor table behind it, which is why every number a
check makes of this stage is a number of bytes and words.

Between the text and the tokens sit the two rules that make a shell's lexer
awkward: a token's bytes are kept exactly as they were written — a quote is not
stripped here, because §4.2 is what decides what a word finally means — and an
operator is matched longest first, because `2>&1` is one operator and not three.
A line a shell cannot read is data, not an exception: `parse` answers the byte
that failed and what it expected there.
"""

import machine
import rules

TOKEN_KEYS = ("kind", "text", "quote", "offset")

TOKEN_KINDS = ("word", "operator")

QUOTE_KINDS = ("none", "single", "double", "backslash", "mixed")

PARSE_KEYS = ("line", "lists", "error")

COMMAND_KEYS = ("words", "redirects", "assignment", "background")

PARSE_ERRORS = ("unterminated-quote", "trailing-operator", "unexpected-operator",
                "bad-redirect", "empty")

_SPACE = " \t\n"
_COMMENT = "#"
_DIGITS = "0123456789"
_NAME_BYTES = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
_ASSIGNMENT = rules.ASSIGNMENT
#: Every operator the policy holds, longest first, so `2>&1` is tried before `2>`
#: and `>>` before `>`. The sort is stable, so operators of one length keep the
#: policy's own order.
_OPERATORS = tuple(sorted(rules.OPERATORS, key=len, reverse=True))
#: An operator that opens with a digit can only open a token: `2>` is an operator
#: where an operator may begin, and `x2>y` is one word, one `>` and one word.
_TOKEN_OPERATORS = tuple(op for op in _OPERATORS if op[0] not in _DIGITS)
#: The two operators that separate lists and still need a right-hand list.
_AND_OR = ("&&", "||")
#: The operators that redirect, derived from the policy: the ones that are not
#: separators.
_REDIRECTS = tuple(op for op in rules.OPERATORS if op not in rules.SEPARATORS)


def tokenize(line):
    """Every token of `line`, in order, with the offset of the token's first byte.

    A token is a word or an operator. `text` is the bytes exactly as they were
    written — quotes and backslashes included, because what a word *means* is
    §4.2's business and this stage only says what was written — and `quote` is the
    one quoting form that built it: `none` for plain bytes, `single`, `double` or
    `backslash`, and `mixed` when more than one form did, which is why `a"b"` and
    `'a'b` are both `mixed` while `'a'` is `single`.

    An operator's `text` is the operator and its `quote` is `none`. Operators are
    matched longest first, so `>>` is one token and `2>&1` is one token and not
    three; `2>` and `2>&1` are operators only where an operator may begin, while a
    punctuation operator ends the word it abuts. `#` opens a comment only where a
    word would begin, so `a#b` is one word.

    A word whose quote never closes is not a token: `tokenize` answers the tokens
    it could read, and `parse` is what reports the failure. A line that is not a
    string is a caller's mistake and raises `MachineError` naming it; nothing else
    raises, and the machine is never asked anything.
    """
    _refuse(line)
    return _scan(line)[0]


def parse(line):
    """The lists `line` reads as, or the record that says why it does not read.

    `lists` is a tuple of lists; a list is `(pipelines, connector)`, where
    `pipelines` is the tuple of the list's pipelines and `connector` is the operator
    that joined this list to the previous one — `None` for the first — and a
    pipeline is a tuple of `COMMAND_KEYS` records in the order they were written.
    A list ends where the line writes `;`, `&`, `&&` or `||`, so `a | b && c ; d` is
    three lists whose connectors are `None`, `&&` and `;`, and the first of them
    holds one pipeline of two commands; a list ended by `&` is the one the shell
    puts in the background, and every command of it says `background` true. A
    command's `words` are its word tokens as written, `redirects` are the
    redirections it wrote in the order it wrote them, and `assignment` is its
    leading `NAME=value` word — which stays in `words`, because this stage records
    the line and a later stage decides what it becomes.

    `parse` never raises on a line a shell cannot read: the answer is the line, the
    lists it did read, and an `error` of `kind` (one of `PARSE_ERRORS`), `offset`
    (the byte that failed) and `detail` (a sentence naming what was expected). An
    empty line and a line that is only a comment are not failures: they read as no
    lists at all. A line that is not a string raises `MachineError` naming it.
    """
    _refuse(line)
    tokens, error = _scan(line)
    if error is not None:
        return {"line": line, "lists": (), "error": error}
    lists, error = _lists(tokens)
    return {"line": line, "lists": lists, "error": error}


def _refuse(line):
    """Refuse a line that is not a string, naming it, before a byte is read."""
    if not isinstance(line, str):
        raise machine.MachineError("stage 1: %r is not a line" % (line,))


def _failure(kind, offset, detail):
    """A parse failure: which rule of `PARSE_ERRORS` broke, the byte, and what was due."""
    return {"kind": kind, "offset": offset, "detail": detail}


def _operator_at(line, at, token_start):
    """The longest operator of the policy that starts at `at`, or `None`.

    `token_start` says whether `at` is where a token begins: an operator opening
    with a digit is an operator only there, because a digit is otherwise a byte of
    a word, while every other operator is punctuation and ends the word it abuts.
    """
    for operator in (_OPERATORS if token_start else _TOKEN_OPERATORS):
        if line.startswith(operator, at):
            return operator
    return None


def _close_of(line, at, quote):
    """The byte that closes the quote at `at`, or `-1` when the line never closes it.

    A backslash escapes the next byte inside double quotes, so `"a\\"b"` is one
    section; inside single quotes nothing escapes.
    """
    scan = at + 1
    end = len(line)
    while scan < end:
        if quote == '"' and line[scan] == "\\" and scan + 1 < end:
            scan += 2
            continue
        if line[scan] == quote:
            return scan
        scan += 1
    return -1


def _form_of(forms):
    """The one quoting form that built a word, or `mixed` when more than one did."""
    first = forms[0]
    for form in forms:
        if form != first:
            return "mixed"
    return first


def _word_at(line, at, end):
    """`(token, next byte, failure)`: the word that starts at `at`.

    A word ends at the first byte of unquoted whitespace, or at the first
    punctuation operator that abuts it. A backslash escapes exactly the next byte,
    so `a\\ b` is one word of three bytes, and a quoted section is taken whole, so
    the bytes inside it are not looked at again.
    """
    start = at
    text = ""
    forms = []
    while at < end and line[at] not in _SPACE:
        byte = line[at]
        if byte == "\\":
            if at + 1 >= end:
                return None, end, _failure(
                    "unterminated-quote", at, "expected the byte the backslash escapes")
            text += line[at:at + 2]
            forms.append("backslash")
            at += 2
            continue
        if byte in ("'", '"'):
            form = "single" if byte == "'" else "double"
            close = _close_of(line, at, byte)
            if close < 0:
                return None, end, _failure(
                    "unterminated-quote", at,
                    "expected the closing %s quote before the end of the line" % (byte,))
            text += line[at:close + 1]
            forms.append(form)
            at = close + 1
            continue
        if _operator_at(line, at, False) is not None:
            break
        text += byte
        forms.append("none")
        at += 1
    return {"kind": "word", "text": text, "quote": _form_of(forms),
            "offset": start}, at, None


def _scan(line):
    """`(tokens, error)`: every token of `line`, and the first failure or `None`.

    A here-document is the one token stream this stage rewrites: the body that
    follows a `<<` word on the line's later lines is not words of the command —
    it is the document the redirection carries, so the scanner stops the line at
    the body and marks the delimiter's token, and `parse` answers the body as
    the redirect's target (§4.2: the plan's `<<` file is the body, already
    expanded by the stage that owns expansion).
    """
    line, body = _take_body(line)
    tokens, error = _words(line, body)
    if error is not None:
        return tuple(tokens), error
    return tuple(tokens), None


def _take_body(line):
    """`(line cut at the body, body or None)`: where a here-document begins.

    A `<<` word followed by a newline and lines that close with the delimiter
    alone is a here-document: the scanner keeps the line up to the delimiter
    word and hands the document back separately. A line with no later lines is
    a `<<` with a file-name word, exactly as a check writes it.
    """
    marker = line.find("<<")
    if marker < 0 or "\n" not in line:
        return line, None
    tail = line[marker + 2:]
    head = tail.split("\n", 1)[0]
    quoted = head[:1] in "'\"" and len(head) >= 2 and head[-1] == head[0]
    delimiter = head[1:-1] if quoted else head.strip()
    if not delimiter:
        return line, None
    lines = tail.split("\n")
    for stop in range(1, len(lines)):
        if lines[stop].strip() == delimiter:
            body = "".join(part + "\n" for part in lines[1:stop])
            return line[:marker + 2] + head + " \x00", body
    return line, None


def _words(line, body):
    """The tokens of the cut line, with the here-document written onto the target."""
    tokens = []
    at = 0
    end = len(line)
    while at < end:
        byte = line[at]
        if byte == "\x00":
            tokens[-1]["text"] = body
            tokens[-1]["quote"] = "none"
            at += 1
            continue
        if byte in _SPACE:
            at += 1
            continue
        if byte == _COMMENT:
            break
        operator = _operator_at(line, at, True)
        if operator is not None:
            tokens.append({"kind": "operator", "text": operator, "quote": "none",
                           "offset": at})
            at += len(operator)
            continue
        token, at, error = _word_at(line, at, end)
        if error is not None:
            return tuple(tokens), error
        tokens.append(token)
    return tuple(tokens), None


def _lists(tokens):
    """`(lists, error)`: the tokens grouped into the lists, pipelines and commands.

    Every one of `&&`, `||`, `;` and `&` ends the list it follows and begins the
    next, so a list holds one pipeline — unless the line writes `|`, which joins
    commands inside it — and a list is `(pipelines, connector)`: the operator that
    joined this list to the previous one, or `None` for the first. `&` is a
    connector like the others, and the commands of the list it ended keep
    `background` true, so a trailing `&` is visible even though it names no list.
    """
    lists = []
    at = 0
    count = len(tokens)
    connector = None
    while at < count:
        commands = []
        while True:
            command, at, error = _command(tokens, at)
            if error is not None:
                return tuple(lists), error
            commands.append(command)
            if at < count and tokens[at]["text"] == "|":
                if at + 1 >= count:
                    return tuple(lists), _missing(tokens[at], "command")
                at += 1
                continue
            break
        background = False
        following = None
        if at < count:
            separator = tokens[at]["text"]
            if separator in _AND_OR and at + 1 >= count:
                return tuple(lists), _missing(tokens[at], "command")
            background = separator == "&"
            following = separator
            at += 1
        if background:
            for command in commands:
                command["background"] = True
        lists.append(((tuple(commands),), connector))
        connector = following
    return tuple(lists), None


def _command(tokens, at):
    """`(record, next byte, failure)`: the `COMMAND_KEYS` record that starts at `at`.

    A command is the run of words and redirections up to the first operator that
    separates commands, pipelines or lists. A command of redirections only — `> out`
    on its own — is a command: it redirects a shell that runs nothing, which is
    §4.3's business and not this stage's.

    A command that has no word and no redirection is the one way this fails: an
    operator stands where a command has to begin. `|` there is an `empty` pipeline
    — the operator has nothing on its left — and `;`, `&`, `&&` and `||` there are
    an `unexpected-operator`, because a list that never began cannot be ended.
    """
    words = []
    redirects = []
    count = len(tokens)
    while at < count:
        token = tokens[at]
        if token["kind"] == "word":
            words.append(token["text"])
            at += 1
            continue
        if token["text"] not in _REDIRECTS:
            break
        redirect, at, error = _redirect(tokens, at)
        if error is not None:
            return None, at, error
        redirects.append(redirect)
    if not words and not redirects:
        return None, at, _at_a_command(tokens[at])
    return {"words": tuple(words), "redirects": tuple(redirects),
            "assignment": _leading_assignment(words), "background": False}, at, None


def _redirect(tokens, at):
    """`(record, next byte, failure)`: the redirection written at `at`.

    The record is `{"kind", "fd", "target", "quoted"}`: the operator exactly as
    written, the descriptor it redirects, the word it takes as its target — as
    written too, so a quoted file name keeps its quotes — and whether that target
    was quoted, which is the byte §4.2 reads to decide whether a here-document
    expands. `2>&1` takes no word: it makes fd 2 a copy of fd 1, so its target is
    the descriptor the operator itself names.

    A redirection whose word the line never writes is a `trailing-operator`, and one
    whose next byte is an operator instead of a word is a `bad-redirect`.
    """
    token = tokens[at]
    operator = token["text"]
    if operator == "2>&1":
        return {"kind": operator, "fd": _descriptor(operator), "target": "1",
                "quoted": False}, at + 1, None
    if at + 1 >= len(tokens):
        return None, at + 1, _missing(token, "file name")
    target = tokens[at + 1]
    if target["kind"] != "word":
        return None, at + 2, _failure(
            "bad-redirect", target["offset"],
            "expected a file name after `%s`, and `%s` is an operator"
            % (operator, target["text"]))
    return {"kind": operator, "fd": _descriptor(operator), "target": target["text"],
            "quoted": target["quote"] != "none"}, at + 2, None


def _descriptor(operator):
    """The descriptor a redirection redirects.

    `>` and `>>` are fd 1 and `<` and `<<` are fd 0; an operator that carries a
    digit carries its own descriptor, which is why `2>` redirects fd 2 and `2>&1`
    is "fd 2 becomes whatever fd 1 is".
    """
    if operator[0] in _DIGITS:
        return int(operator[0])
    return 0 if operator[0] == "<" else 1


def _leading_assignment(words):
    """The `NAME=value` word a command leads with, or `None`.

    A name is a letter or `_` and then letters, digits and `_`; the value is
    everything the first `=` is followed by, empty included, exactly as written.
    The word stays in `words` as well: this stage records what the line wrote, and
    §4.2 and §4.7 are what decide that a leading assignment is not an argv word.
    """
    if not words:
        return None
    word = words[0]
    name, sign, _ = word.partition(_ASSIGNMENT)
    if not sign or not name or name[0] in _DIGITS:
        return None
    for byte in name:
        if byte not in _NAME_BYTES:
            return None
    return word


def _at_a_command(token):
    """The failure for an operator that stands where a command has to begin."""
    if token["text"] == "|":
        return _failure("empty", token["offset"], "expected a command before `|`")
    return _failure("unexpected-operator", token["offset"],
                    "expected a command, and `%s` is an operator" % (token["text"],))


def _missing(token, what):
    """The failure for an operator whose other side the line never writes.

    The byte that failed is the one the operand was due at — the byte after the
    operator — and not the operator's own first byte: `|` is a token the lexer read
    happily, and what the parser misses is whatever follows it.
    """
    return _failure("trailing-operator", token["offset"] + len(token["text"]),
                    "expected a %s after `%s`" % (what, token["text"]))
