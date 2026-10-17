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


DESIGN DECISION — Why are a token's bytes kept exactly as they were written, quotes included?
Because what a word *means* is expansion's business, not the lexer's: `'$X'` and
`"$X"` are the same bytes to a splitter that strips quotes, and two different
answers to the stage that expands them. This stage records what the line wrote —
the quote characters inside `text`, and which form built the word in `quote` —
so every later stage can read the intent off the token instead of guessing it
back from bytes that no longer say. A `quote` field of `mixed` is the honest
answer for `a"b"`: no single form built it, and pretending one did would let a
later stage drop an escape the line wrote deliberately.

DESIGN DECISION — Why are operators matched longest first, and why is `2>&1` one operator?
Because the lexer's greed is the grammar: `>>` read as two `>` tokens is not a
worse answer, it is a different redirection (`>` twice, appending nothing), and
`2>&1` read as `2>`, `&`, `1` is a file named `&1` instead of a copy of fd 1.
Matching longest first is also what makes `2>` an operator only where a token
begins — a digit that opens a word is a byte of that word, so `a2>b` redirects
nothing and names one word — which is the one place a shell's lexer has to know
where it is, not just what it is looking at.

DESIGN DECISION — Why does `parse` answer a failure instead of raising it?
Because a line a shell cannot read is an event, not a crash: a real shell prints
`syntax error` and gives the user the prompt back. So the answer carries the
byte that failed, the rule that broke (`PARSE_ERRORS`), and a sentence naming
what was expected there — and every later stage composes over that shape without
a try/except. The one thing that *does* raise is a line that is not a string at
all, because that is the caller's mistake and not the line's.

DESIGN DECISION — Why is a leading `NAME=value` word kept in `words` as well as in `assignment`?
Because this stage records the line and a later stage decides what the word
becomes: dropping it here would make the splitter the stage that invented the
rule about assignments, and the rule (§4.7: a bare assignment persists, a prefix
does not) is not this stage's to apply. Keeping the word costs nothing and
keeps the record faithful — `X=1` and `X=1 env` are written differently, and the
parse answer says so.
    TOKEN_KEYS      the four fields of one token, in order
    TOKEN_KINDS     the two kinds a token can be
    QUOTE_KINDS     the quoting forms a word can be built from
    PARSE_KEYS      the three fields of a parse answer, in order
    COMMAND_KEYS    the four fields of one command, in order
    PARSE_ERRORS    the five ways a line refuses to read
    tokenize(line)  -> tuple[TOKEN_KEYS], quotes kept as written
    parse(line)     -> PARSE_KEYS, lists or the error that says why not

TODO: implement `tokenize`, `parse` in this file.
"""

import machine
import rules

TOKEN_KEYS = ('kind', 'text', 'quote', 'offset')

TOKEN_KINDS = ('word', 'operator')

QUOTE_KINDS = ('none', 'single', 'double', 'backslash', 'mixed')

PARSE_KEYS = ('line', 'lists', 'error')

COMMAND_KEYS = ('words', 'redirects', 'assignment', 'background')

PARSE_ERRORS = ('unterminated-quote', 'trailing-operator', 'unexpected-operator', 'bad-redirect', 'empty')

_SPACE = ' \t\n'

_COMMENT = '#'

_DIGITS = '0123456789'

_NAME_BYTES = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'

_ASSIGNMENT = rules.ASSIGNMENT

_OPERATORS = tuple(sorted(rules.OPERATORS, key=len, reverse=True))

_TOKEN_OPERATORS = tuple(op for op in _OPERATORS if op[0] not in _DIGITS)

_AND_OR = ('&&', '||')

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
    raises, and the machine is never asked anything."""
    raise NotImplementedError("stage 1: implement tokenize()")


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
    lists at all. A line that is not a string raises `MachineError` naming it."""
    raise NotImplementedError("stage 1: implement parse()")


def _refuse(line):
    """Refuse a line that is not a string, naming it, before a byte is read."""
    raise NotImplementedError("stage 1: implement _refuse()")


def _failure(kind, offset, detail):
    """A parse failure: which rule of `PARSE_ERRORS` broke, the byte, and what was due."""
    raise NotImplementedError("stage 1: implement _failure()")


def _operator_at(line, at, token_start):
    """The longest operator of the policy that starts at `at`, or `None`.

    `token_start` says whether `at` is where a token begins: an operator opening
    with a digit is an operator only there, because a digit is otherwise a byte of
    a word, while every other operator is punctuation and ends the word it abuts."""
    raise NotImplementedError("stage 1: implement _operator_at()")


def _close_of(line, at, quote):
    """The byte that closes the quote at `at`, or `-1` when the line never closes it.

    A backslash escapes the next byte inside double quotes, so `"a\"b"` is one
    section; inside single quotes nothing escapes."""
    raise NotImplementedError("stage 1: implement _close_of()")


def _form_of(forms):
    """The one quoting form that built a word, or `mixed` when more than one did."""
    raise NotImplementedError("stage 1: implement _form_of()")


def _word_at(line, at, end):
    """`(token, next byte, failure)`: the word that starts at `at`.

    A word ends at the first byte of unquoted whitespace, or at the first
    punctuation operator that abuts it. A backslash escapes exactly the next byte,
    so `a\ b` is one word of three bytes, and a quoted section is taken whole, so
    the bytes inside it are not looked at again."""
    raise NotImplementedError("stage 1: implement _word_at()")


def _scan(line):
    """`(tokens, error)`: every token of `line`, and the first failure or `None`.

    A here-document is the one token stream this stage rewrites: the body that
    follows a `<<` word on the line's later lines is not words of the command —
    it is the document the redirection carries, so the scanner stops the line at
    the body and marks the delimiter's token, and `parse` answers the body as
    the redirect's target (§4.2: the plan's `<<` file is the body, already
    expanded by the stage that owns expansion)."""
    raise NotImplementedError("stage 1: implement _scan()")


def _take_body(line):
    """`(line cut at the body, body or None)`: where a here-document begins.

    A `<<` word followed by a newline and lines that close with the delimiter
    alone is a here-document: the scanner keeps the line up to the delimiter
    word and hands the document back separately. A line with no later lines is
    a `<<` with a file-name word, exactly as a check writes it."""
    raise NotImplementedError("stage 1: implement _take_body()")


def _words(line, body):
    """The tokens of the cut line, with the here-document written onto the target."""
    raise NotImplementedError("stage 1: implement _words()")


def _lists(tokens):
    """`(lists, error)`: the tokens grouped into the lists, pipelines and commands.

    Every one of `&&`, `||`, `;` and `&` ends the list it follows and begins the
    next, so a list holds one pipeline — unless the line writes `|`, which joins
    commands inside it — and a list is `(pipelines, connector)`: the operator that
    joined this list to the previous one, or `None` for the first. `&` is a
    connector like the others, and the commands of the list it ended keep
    `background` true, so a trailing `&` is visible even though it names no list."""
    raise NotImplementedError("stage 1: implement _lists()")


def _command(tokens, at):
    """`(record, next byte, failure)`: the `COMMAND_KEYS` record that starts at `at`.

    A command is the run of words and redirections up to the first operator that
    separates commands, pipelines or lists. A command of redirections only — `> out`
    on its own — is a command: it redirects a shell that runs nothing, which is
    §4.3's business and not this stage's.

    A command that has no word and no redirection is the one way this fails: an
    operator stands where a command has to begin. `|` there is an `empty` pipeline
    — the operator has nothing on its left — and `;`, `&`, `&&` and `||` there are
    an `unexpected-operator`, because a list that never began cannot be ended."""
    raise NotImplementedError("stage 1: implement _command()")


def _redirect(tokens, at):
    """`(record, next byte, failure)`: the redirection written at `at`.

    The record is `{"kind", "fd", "target", "quoted"}`: the operator exactly as
    written, the descriptor it redirects, the word it takes as its target — as
    written too, so a quoted file name keeps its quotes — and whether that target
    was quoted, which is the byte §4.2 reads to decide whether a here-document
    expands. `2>&1` takes no word: it makes fd 2 a copy of fd 1, so its target is
    the descriptor the operator itself names.

    A redirection whose word the line never writes is a `trailing-operator`, and one
    whose next byte is an operator instead of a word is a `bad-redirect`."""
    raise NotImplementedError("stage 1: implement _redirect()")


def _descriptor(operator):
    """The descriptor a redirection redirects.

    `>` and `>>` are fd 1 and `<` and `<<` are fd 0; an operator that carries a
    digit carries its own descriptor, which is why `2>` redirects fd 2 and `2>&1`
    is "fd 2 becomes whatever fd 1 is"."""
    raise NotImplementedError("stage 1: implement _descriptor()")


def _leading_assignment(words):
    """The `NAME=value` word a command leads with, or `None`.

    A name is a letter or `_` and then letters, digits and `_`; the value is
    everything the first `=` is followed by, empty included, exactly as written.
    The word stays in `words` as well: this stage records what the line wrote, and
    §4.2 and §4.7 are what decide that a leading assignment is not an argv word."""
    raise NotImplementedError("stage 1: implement _leading_assignment()")


def _at_a_command(token):
    """The failure for an operator that stands where a command has to begin."""
    raise NotImplementedError("stage 1: implement _at_a_command()")


def _missing(token, what):
    """The failure for an operator whose other side the line never writes.

    The byte that failed is the one the operand was due at — the byte after the
    operator — and not the operator's own first byte: `|` is a token the lexer read
    happily, and what the parser misses is whatever follows it."""
    raise NotImplementedError("stage 1: implement _missing()")
