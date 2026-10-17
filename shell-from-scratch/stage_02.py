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


DESIGN DECISION — Why do the five phases run in exactly `rules.EXPANSION_ORDER`'s order?
Because the order *is* the answer: a parameter that expands to `a b` must be cut
into two words (parameter before split), a `~` that becomes `$HOME` must cut too
(tilde before split), a quoted space must not cut (split sees provenance), and a
glob metacharacter a parameter produced must match (glob after parameter). Run
the phases in any other order and every one of those answers flips — which is
why the check asks two questions no single phase can answer alone.

DESIGN DECISION — Why is the split the one phase that runs on a byte's provenance rather than the
byte itself?
Because a space is not whitespace everywhere: the space in `'a b'` is content,
the space in `a b` is a boundary, and the two are the same byte. So the phases
carry runs — `literal`, `result`, `quoted`, `escape`, `mark` — and the split cuts
only the boundaries a `result` or an unquoted run made. A flat string would have
thrown the provenance away in phase one.

DESIGN DECISION — Why does `glob` match against `machine.files()` and never against a real
directory?
Because the machine is the world: its filesystem is data, its population is
`files()`, and a pattern's answer has to be reproducible on a machine with no
disk at all. Sorted order is part of the contract — a glob is a set, but a
command line is a sequence — and a pattern that matches nothing answers itself,
because that is what a shell's command line keeps.

DESIGN DECISION — Why does an expansion never apply to its own result?
Because one pass is what a shell does: `$X` where `X='$(echo hi)'` is not
another expansion, it is bytes. Running the scanner again over what a phase
produced would make the answer depend on the *content* of a variable rather
than the line, which is how injection bugs are born. The phases are a pipeline
over the original text, and the result is written back with its quoting
reported — not re-read.
    EXPAND_KEYS     the three fields of an expansion answer, in order
    EXPAND_ERRORS   the four ways an expansion refuses
    expand(m, text, vars)        -> EXPAND_KEYS, the whole text
    expand_word(m, text, vars)   -> EXPAND_KEYS, one word only
    substitute(m, text, vars)    -> {"text", "error"}, phase one alone
    glob(m, pattern)             -> {"paths", "error"}, the machine's own files
    here_document(m, body, q)    -> {"bytes", "error"}, a << body

TODO: implement `expand`, `expand_word`, `substitute`, `glob`, `here_document`
in this file.
"""

import machine

EXPAND_KEYS = ('text', 'words', 'error')

EXPAND_ERRORS = ('bad-substitution', 'unset-variable', 'bad-glob', 'here-document-unterminated')

_LITERAL = 'literal'

_RESULT = 'result'

_QUOTED = 'quoted'

_ESCAPE = 'escape'

_MARK = 'mark'

_SPACE = ' \t\n'

_METACHARS = '*?['

_FIRST = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_'

_REST = _FIRST + "0123456789"


def _refuse(message):
    """A caller's mistake: the offender is named and the machine is not touched."""
    raise NotImplementedError("stage 2: implement _refuse()")


def _record(kind, offset, detail):
    """§4.1's error shape: what failed, the byte in the text that failed, and the detail."""
    raise NotImplementedError("stage 2: implement _record()")


def _as_text(text, what):
    """The text, or the refusal naming what was handed over instead of one."""
    raise NotImplementedError("stage 2: implement _as_text()")


def _state(variables):
    """The variable table and the flags out of the shell's own state.

    The state is the house record — `{"variables": {name: value}, "flags":
    {"nounset": bool}}` — and a bare `{name: value}` mapping is that state with no
    flags on, so the plain call needs no ceremony. The fields another stage owns
    (`exported`, `traps`, `jobs`, `cwd`, `exit`, `args`, `stdin`) are read by
    nobody here and written by nobody here; a mapping that is neither shape, a
    variable whose value is not a string, or an option that is not a bool refuses
    with `machine.MachineError` naming the offender."""
    raise NotImplementedError("stage 2: implement _state()")


def _value(table, name, nounset, offset):
    """The value of `name`: itself, nothing, or the `unset-variable` record of the refusal.

    A name that is not set and has no word of its own expands to nothing, and
    under `nounset` to the record that names it — with the offset of the `$` that
    asked for it."""
    raise NotImplementedError("stage 2: implement _value()")


def _environment(machine):
    """The machine's own environment as a variable table: a here-document's only source."""
    raise NotImplementedError("stage 2: implement _environment()")


def _flat(parts):
    """The bytes of `parts` in order: what a phase has produced, quotes and all."""
    raise NotImplementedError("stage 2: implement _flat()")


def _report(parts):
    """The parts written back as the text they came from: quote characters where they stood.

    `_flat` answers the bytes; this answers the text — the marker segments write
    the `'` and the `"` back exactly where the text had them, an escaped byte
    behind its `\`, and a phase's own insertion as the bare bytes it put there —
    so an expansion's `text` is the word with its quoting still as written and
    its parameters already substituted. It is not the caller's input: `"$X"` with
    `X=a b` reports `"a b"`, and a text nothing touched reports itself."""
    raise NotImplementedError("stage 2: implement _report()")


def _has_metachar(text):
    """True when `text` holds a byte a pathname pattern would read as a metacharacter."""
    raise NotImplementedError("stage 2: implement _has_metachar()")


def _name_is(name):
    """True when `name` is a name a variable may have: a letter or `_`, then letters, digits, `_`."""
    raise NotImplementedError("stage 2: implement _name_is()")


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
    bytes, and they are not scanned again."""
    raise NotImplementedError("stage 2: implement _parameter()")


def _at_dollar(text, at, table, flags, base):
    """The expansion that starts at `text[at]`: its value, the byte after it, its error.

    A `$` that starts nothing — the last byte of the text, or one followed by a
    byte no name and no `{` can begin with — is a `$` like any other, and stands."""
    raise NotImplementedError("stage 2: implement _at_dollar()")


def _braced(text, at, table, flags, base):
    """The `${...}` that starts at `text[at]`: its value, the byte after its `}`, its error.

    The grammar is exactly `${NAME}`, `${NAME:-word}`, `${NAME:+word}`,
    `${NAME#prefix}`, `${NAME%Suffix}` and `${#NAME}`: braces do not nest, the
    word of `:-` and `:+` is expanded once itself, the operand of `#` and `%` is
    literal, and anything else is a `bad-substitution`."""
    raise NotImplementedError("stage 2: implement _braced()")


def _tilde(parts, table, one_word):
    """Phase two: a leading `~` of a word becomes `HOME`, and nothing else does.

    A tilde is the first byte of a word — the text's own first byte, or the byte
    after an unquoted space — and only when a `/` or the end of the word follows
    it: `~user` is left alone, because this machine has no user table, and a
    quoted or backslashed `~` is a byte like any other. The path arrives as an
    unquoted insertion, so the split that follows cuts it: a `HOME` that carries
    a space makes two words, which is what running this phase before that one
    means. A table with no `HOME` leaves the `~` where it was."""
    raise NotImplementedError("stage 2: implement _tilde()")


def _split(parts, one_word):
    """Phase three: the parts cut into fields on unquoted whitespace.

    A run of unquoted whitespace is a boundary and is not itself a field, an
    empty field is not a word — except a field that was quoted, because `""` is a
    word and `$UNSET` is not. `one_word` is the whole of the `expand` /
    `expand_word` difference: a word the lexer handed over is one word, so its
    own literal whitespace stays inside it and only the whitespace a `result`
    segment carries cuts, while a text that may hold several words is cut on
    every unquoted space it has."""
    raise NotImplementedError("stage 2: implement _split()")


def _class_end(pattern, at):
    """The byte of the `]` closing the class opened at `pattern[at]`, or `-1`.

    A `]` in the class's first position is a member and not the end — `[]a]` is
    the class of `]` and `a` — and a class the pattern never closes is not a
    class at all."""
    raise NotImplementedError("stage 2: implement _class_end()")


def _in_class(pattern, at, close, byte):
    """True when `byte` is a member of the class `pattern[at:close + 1]` names."""
    raise NotImplementedError("stage 2: implement _in_class()")


def _match_at(pattern, at, path, which):
    """True when `pattern[at:]` matches `path[which:]`, no part of a pattern crossing a `/`."""
    raise NotImplementedError("stage 2: implement _match_at()")


def _matches(pattern, path):
    """True when the whole `path` matches `pattern`."""
    raise NotImplementedError("stage 2: implement _matches()")


def _class_error(pattern):
    """The byte of a `[` whose class is never closed, or `None` when every class closes."""
    raise NotImplementedError("stage 2: implement _class_error()")


def _matched(machine, pattern):
    """The paths of `machine.files()` that `pattern` matches, or the `bad-glob` record.

    A pattern with no metacharacter is not a pattern: it answers itself, and the
    machine is not asked at all. A pattern that matches nothing answers itself
    too, because that is the word the command line keeps. Everything else is the
    machine's own population, in sorted order."""
    raise NotImplementedError("stage 2: implement _matched()")


def _globbed(machine, fields):
    """Phase four itself: every field that holds an unquoted metacharacter becomes its matches.

    Answers `(words, error)`: `words` is the fields, each globbed one replaced by
    its paths — several words where one was — and `error` is `None` or the
    `bad-glob` record. A metacharacter inside quotes, or one a backslash quoted,
    is a byte like any other and does not make the field a pattern."""
    raise NotImplementedError("stage 2: implement _globbed()")


def _word(field):
    """The field's bytes with its quoting resolved: phase five's answer for one field.

    A quote character is not content — it stops splitting and globbing while the
    phases run and it is gone when they are over — and an escaped byte is the
    byte it escaped."""
    raise NotImplementedError("stage 2: implement _word()")


def _unquoted(fields):
    """Phase five: the fields with their quotes and their backslashes resolved away."""
    raise NotImplementedError("stage 2: implement _unquoted()")


def _delimiter(line):
    """The delimiter a here-document's first line names: its quotes removed, nothing expanded.

    A `$` in the line is a `$`: the delimiter is a word, not a word to be
    expanded, and what its quoting decides is whether the document expands, which
    the caller states with `quoted`."""
    raise NotImplementedError("stage 2: implement _delimiter()")


def _nothing(error):
    """The record a failed expansion answers: the error, and no payload at all."""
    raise NotImplementedError("stage 2: implement _nothing()")


def _expanded(machine, text, variables, one_word):
    """The five phases in `rules.EXPANSION_ORDER`'s order, and the record they answer.

    `text` is the text after the parameter and tilde phases — quotes as written,
    before the split cut it and before the glob replaced it — and `words` is what
    the five left. `one_word` is the whole difference between `expand` and
    `expand_word`."""
    raise NotImplementedError("stage 2: implement _expanded()")


def expand(machine, text, variables):
    """The words a whole `text` expands to, by the five phases in their order.

    `text` may hold several words, so the split cuts it on every unquoted space;
    the record is `EXPAND_KEYS` and a failed expansion answers `text = None` with
    no words. `variables` is the shell's state or a bare table, and a record that
    is neither refuses with `machine.MachineError` before a byte is looked at."""
    raise NotImplementedError("stage 2: implement expand()")


def expand_word(machine, text, variables):
    """The words one word expands to: the same phases, cut only where an expansion cut.

    The word the lexer handed over is one word, so a space that was already in it
    stays in it; the whitespace a parameter or a tilde put there splits, because
    that phase ran before this one."""
    raise NotImplementedError("stage 2: implement expand_word()")


def substitute(machine, text, variables):
    """Phase one and nothing else: `text` with its parameters expanded, quotes as written.

    The whole grammar — `${NAME}`, `$NAME`, `${NAME:-word}`, `${NAME:+word}`,
    `${NAME#prefix}`, `${NAME%Suffix}`, `${#NAME}` — and the answer is
    `{"text", "error"}`: the text after the phase, or `None` with the record of a
    `bad-substitution` whose body is outside the grammar, or of an
    `unset-variable` under `nounset`. Nothing here splits, globs, expands a
    tilde or removes a quote."""
    raise NotImplementedError("stage 2: implement substitute()")


def glob(machine, pattern):
    """The machine's own paths that `pattern` matches, in sorted order.

    `machine.files()` is the whole population and a pattern that matches nothing
    comes back as written; a pattern with no metacharacter answers itself without
    asking the machine. Answers `{"paths", "error"}` — `paths` is `None` when
    `error` is the record of a class that is never closed — and a `pattern` that
    is not a string raises `machine.MachineError` naming it."""
    raise NotImplementedError("stage 2: implement glob()")


def here_document(machine, body, quoted):
    """The bytes of a `<<` body: its delimiter's line first, its terminator line last.

    The document is every line between the delimiter line and the first line that
    is exactly the delimiter with its quotes removed, each with its newline, and
    `quoted` says whether that delimiter was quoted: quoted, the bytes stand as
    written; unquoted, parameters expand from the machine's own environment and
    nothing else happens — no split, no glob, because a here-document is bytes
    and not words. Answers `{"bytes", "error"}`, `bytes` being `None` when a
    `here-document-unterminated` or a `bad-substitution` is named instead."""
    raise NotImplementedError("stage 2: implement here_document()")
