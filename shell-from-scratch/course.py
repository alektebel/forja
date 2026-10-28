"""Shell From Scratch — a shell over a provided machine.

Ten graded stages over a machine provided as data (`machine.py`, `programs.py`,
`rules.py`, `scripts.py`), the way the rest of this repository teaches a
mechanism: the world is data and holds the ground truth, a stage is a file you
write, a check is what happens to it, and every promise the kernel makes is on
show because a shell is what a kernel looks like from the outside.

What the course is about, in one line: *a line of text becomes a process tree, and
every step of that becoming is a rule you have to get right.*

    the line, the word and the operator
    expansion, in the order a shell must
    the pipeline, the descriptor table and what a pipe costs
    the process tree: fork, exec, wait and the status
    the job table: background, stopped, and who waits for whom
    signals, traps, and what a signal does to a job
    the builtins that must not fork
    lists, conditions and the rules of `set -e`
    the session, replayed byte for byte
    exit codes, and the audit of a session's statuses

The house laws hold here (`.g7-dev/CONTRACT.md` §1): standard library only, no
`float` literal, no `math`, no `statistics`, no `random`, no clock, no thread, no
socket and no process of your own — and, this course's own two additions, no `io`
and no `open(`: the filesystem is the machine's, and the machine is the only I/O a
stage is allowed. The machine is never written: a stage calls its accessors and
answers, and the machine's own transcript — the statuses in order, the children
born and reaped, the signals sent, the job table at the end and the bytes on the
terminal — is the answer key it has to reproduce.

What the course does **not** do is call anything real. There is no `fork(2)`
behind `machine.fork`, no pipe behind `machine.pipe`, and no sleeping process
behind `tick`: the scheduler is a rule, the tick is a number, a deadlock is a
record rather than a hang, and the whole course is deterministic enough that a
session's transcript is compared byte for byte.

    python3 codecraft/cli.py run shell-from-scratch
"""

from codecraft.api import stage

TITLE = "Shell From Scratch"
DESCRIPTION = ("A shell over a provided machine: a line of text becomes a process "
               "tree, and every promise the kernel makes is on show. Ten stages "
               "that turn words and operators into a parse and a plan, run the "
               "five expansions in the order a shell must, build a descriptor "
               "table before anything runs, fork, exec and wait for real exit "
               "codes, keep a job table that knows a background job from a "
               "stopped one, deliver signals and run traps at command boundaries, "
               "keep the builtins that must not fork in the shell's own process, "
               "decide when `set -e` stops and when it is required not to, replay "
               "a whole session byte for byte against the machine's own "
               "transcript, and audit why every step's status was the number it "
               "was — with a deterministic scheduler, a deadlock that is data "
               "rather than a hang, no float and no clock anywhere.")

LEVEL = "advanced"
ORDER = 32


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    S1_TOKEN_KEYS = ("kind", "text", "quote", "offset")

    S1_TOKEN_KINDS = ("word", "operator")

    S1_QUOTE_KINDS = ("none", "single", "double", "backslash", "mixed")

    S1_PARSE_KEYS = ("line", "lists", "error")

    S1_COMMAND_KEYS = ("words", "redirects", "assignment", "background")

    S1_ERROR_KEYS = ("kind", "offset", "detail")

    S1_REDIRECT_KEYS = ("kind", "fd", "target", "quoted")

    S1_PARSE_ERRORS = ("unterminated-quote", "trailing-operator", "unexpected-operator",
                       "bad-redirect", "empty")

    S1_PUBLIC = ("COMMAND_KEYS", "PARSE_ERRORS", "PARSE_KEYS", "QUOTE_KINDS",
                 "TOKEN_KEYS", "TOKEN_KINDS", "parse", "tokenize")

    S1_DOORS = ("spawn", "fork", "exec", "wait", "pipe", "open", "dup2", "close",
                "read", "write", "signal", "ticks", "steps", "deadlocks")

    S1_SPACE = " \t\n"

    S1_COMMENT = "#"

    S1_AT_THE_TOKEN = (
        ("unterminated-quote", 'echo "abc', '"', ("quote", '"')),
        ("unterminated-quote", "echo 'abc", "'", ("quote", "'")),
        ("unterminated-quote", "echo x\\", "\\", ("backslash", "byte")),
        ("unexpected-operator", "; a", ";", ("command", ";")),
        ("unexpected-operator", "& a", "&", ("command", "&")),
        ("unexpected-operator", "a ; ; b", ";", ("command", ";")),
        ("unexpected-operator", "a && && b", "&&", ("command", "&&")),
        ("empty", "| a", "|", ("command", "|")),
        ("empty", "a | | b", "|", ("command", "|")),
        ("bad-redirect", "a > ; b", ";", ("file", ";")),
        ("bad-redirect", "a 2> | b", "|", ("file", "|")),
        ("bad-redirect", "a << && b", "&&", ("file", "&&")),
    )

    S1_TRAILING = (
        ("echo hi |", "|", ("command", "|")),
        ("echo hi |  ", "|", ("command", "|")),
        ("a &&", "&&", ("command", "&&")),
        ("a ||", "||", ("command", "||")),
        ("a >", ">", ("file", ">")),
        ("a >  ", ">", ("file", ">")),
        ("a >>", ">>", ("file", ">>")),
        ("a <", "<", ("file", "<")),
        ("a <<", "<<", ("file", "<<")),
        ("a 2>", "2>", ("file", "2>")),
    )

    def _repo(start=None):
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "machine.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` is checked against
        the message: an exception of the right family raised for the wrong reason is
        not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    S1_QUOTED = (
        ("echo plain", (("word", "echo", "none"), ("word", "plain", "none"))),
        ("echo 'a b'", (("word", "echo", "none"), ("word", "'a b'", "single"))),
        ('echo "a b"', (("word", "echo", "none"), ("word", '"a b"', "double"))),
        ("echo a\\ b", (("word", "echo", "none"), ("word", "a\\ b", "mixed"))),
        ("echo \\a", (("word", "echo", "none"), ("word", "\\a", "backslash"))),
        ("echo ''", (("word", "echo", "none"), ("word", "''", "single"))),
        ('echo ""', (("word", "echo", "none"), ("word", '""', "double"))),
        ("echo a\"b\"c", (("word", "echo", "none"), ("word", 'a"b"c', "mixed"))),
        ("echo 'a'b", (("word", "echo", "none"), ("word", "'a'b", "mixed"))),
        ('echo "a\'b"', (("word", "echo", "none"), ("word", '"a\'b"', "double"))),
        ("echo 'a\"b'", (("word", "echo", "none"), ("word", "'a\"b'", "single"))),
        ('echo "a\\"b"', (("word", "echo", "none"), ("word", '"a\\"b"', "double"))),
        ("echo a\n", (("word", "echo", "none"), ("word", "a", "none"))),
        ("echo\ta", (("word", "echo", "none"), ("word", "a", "none"))),
    )

    S1_COMMENTED = (
        ("echo a#b", (("word", "echo", "none"), ("word", "a#b", "none"))),
        ("echo a #b", (("word", "echo", "none"), ("word", "a", "none"))),
        ("echo '#' x", (("word", "echo", "none"), ("word", "'#'", "single"),
                        ("word", "x", "none"))),
        ("2#x", (("word", "2#x", "none"),)),
    )

    S1_EMPTY = ("", "   ", "\t", "#", "# a comment", "   # comment")

    S1_RICH = (
        "a | b && c ; d",
        "a & b ; c || d && e",
        "a | b &",
        "a ;",
        "cat < in >> out 2> err 2>&1",
        'cat << "END"',
        'cat < "in" >> "out"',
        "2>out",
        "x2>y",
        "echo a#b",
        "FOO=1 echo hi",
        "FOO='a b' echo",
        'echo "a b" c',
        "cmd arg > out 2>&1",
    )

    def _fixture_lines():
        """Every line this check hands the stage, well-formed and malformed alike."""
        lines = [line for _kind, line, _marker, _fragments in S1_AT_THE_TOKEN]
        lines += [line for line, _operator, _fragments in S1_TRAILING]
        lines += [line for line, _expected in S1_QUOTED]
        lines += [line for line, _expected in S1_COMMENTED]
        lines += [line for line, _words, _assigned in S1_ASSIGNED]
        lines += list(S1_EMPTY) + list(S1_RICH)
        for operator in ("|", "&&", "||", ";", "&", ">", ">>", "<", "<<", "2>", "2>&1"):
            lines.append("a %s b" % (operator,))
        return tuple(lines)

    def _tiled(line, tokens):
        """Every byte of `line` is inside a token, inside whitespace, or behind a comment.

        The bytes between two tokens can only be whitespace — any other byte would have
        been part of a token — and what follows the last token is whitespace, the end of
        the line, or a comment. So a token the stage failed to answer cannot hide in a
        gap, and a stage that answered a token the line does not hold is named here.
        """
        previous = 0
        for token in tokens:
            offset = token["offset"]
            assert offset >= previous, (
                "%r answered a token at byte %d after a token ended at byte %d"
                % (line, offset, previous))
            gap = line[previous:offset]
            assert gap.strip(S1_SPACE) == "", (
                "%r holds %r at byte %d, and those bytes are neither a token nor "
                "whitespace" % (line, gap, previous))
            previous = offset + len(token["text"])
        tail = line[previous:]
        assert tail.strip(S1_SPACE) == "" or tail.lstrip(S1_SPACE).startswith(S1_COMMENT), (
            "%r leaves %r after its last token, and only whitespace or a comment may be "
            "there" % (line, tail))

    def _expect_tokens(s, line, expected):
        """The stage's tokens for `line`, against the offsets the line itself gives.

        `expected` is one `(kind, text, quote)` per token, in order. Every offset is
        asserted to be the byte the token's own text starts at, searched for after the
        previous token's end, so each offset is this check's arithmetic and not the
        stage's answer read back — and `text` has to be found in the line at all, which
        a stage that stripped a quote or invented a token cannot manage.
        """
        tokens = s.tokenize(line)
        assert isinstance(tokens, tuple), (
            "%r answered %r instead of a tuple of tokens" % (line, tokens))
        assert len(tokens) == len(expected), (
            "%r reads as %d tokens and the check wrote %d of them: %r"
            % (line, len(tokens), len(expected), tokens))
        at = 0
        for token, wanted in zip(tokens, expected):
            kind, text, quote = wanted
            assert tuple(token) == tuple(s.TOKEN_KEYS), (
                "%r answered the token %r, and a token is exactly TOKEN_KEYS"
                % (line, token))
            assert token["kind"] in s.TOKEN_KINDS, (
                "%r answered the token kind %r, which is not of TOKEN_KINDS"
                % (line, token["kind"]))
            assert token["kind"] == kind, (
                "%r answered the token %r as a %s, and it is a %s"
                % (line, text, token["kind"], kind))
            assert token["text"] == text, (
                "%r answered the token %r, and the check wrote %r" % (line, token["text"], text))
            assert token["quote"] == quote, (
                "%r answered %r as %r, and the form that built it is %r"
                % (line, text, token["quote"], quote))
            found = line.find(text, at)
            assert found >= 0, (
                "%r does not hold the token %r after byte %d" % (line, text, at))
            assert token["offset"] == found, (
                "%r reported %r at byte %r and the line holds it at byte %d"
                % (line, text, token["offset"], found))
            at = found + len(text)
        _tiled(line, tokens)
        return tokens

    def _parsed(s, line, connectors):
        """The stage's `parse` for `line`, against the shape and the connectors §4.1 pins.

        `connectors` are the operators that joined a list to the one before it, in the
        order the check wrote them into the line; the first list's connector is always
        `None`, because nothing preceded it, and the lists are exactly one more than the
        connectors — the check's own arithmetic, and not a number the stage may answer
        differently. A list is `(pipelines, connector)`, a pipeline is a non-empty tuple
        of commands and a command is exactly `COMMAND_KEYS`.
        """
        record = s.parse(line)
        assert isinstance(record, dict), (
            "%r answered %r instead of a record" % (line, record))
        assert tuple(record) == tuple(s.PARSE_KEYS), (
            "%r answered the record %r, and a parse record is exactly PARSE_KEYS"
            % (line, tuple(record)))
        assert record["line"] == line, (
            "the record's line is %r and the line is %r" % (record["line"], line))
        assert record["error"] is None, (
            "%r must read as a line, and it answered the error %r"
            % (line, record["error"]))
        lists = record["lists"]
        assert isinstance(lists, tuple), (
            "%r answered %r instead of a tuple of lists" % (line, lists))
        assert len(lists) == len(connectors) + 1, (
            "%r reads as %d lists, and the check wrote %d separators between them"
            % (line, len(lists), len(connectors)))
        for element, connector in zip(lists, (None,) + tuple(connectors)):
            assert isinstance(element, tuple) and len(element) == 2, (
                "%r answered the list %r, and a list is (pipelines, connector)"
                % (line, element))
            pipelines, got = element
            assert got == connector, (
                "%r joins this list by %r and the stage answered %r"
                % (line, connector, got))
            assert isinstance(pipelines, tuple) and pipelines, (
                "%r answered the list's pipelines as %r" % (line, pipelines))
            for pipeline in pipelines:
                assert isinstance(pipeline, tuple) and pipeline, (
                    "%r answered the pipeline %r" % (line, pipeline))
                for command in pipeline:
                    assert tuple(command) == tuple(s.COMMAND_KEYS), (
                        "%r answered the command %r, and a command is exactly "
                        "COMMAND_KEYS" % (line, command))
                    assert isinstance(command["words"], tuple), (
                        "%r answered the command's words as %r" % (line, command["words"]))
                    assert isinstance(command["redirects"], tuple), (
                        "%r answered the command's redirects as %r"
                        % (line, command["redirects"]))
                    assert isinstance(command["background"], bool), (
                        "%r answered the command's background as %r"
                        % (line, command["background"]))
        return record

    def _commands(lists):
        """Every command of every list, in the order the line wrote them."""
        return tuple(command
                     for pipelines, _connector in lists
                     for pipeline in pipelines
                     for command in pipeline)

    def _one_command(s, line):
        """The single command `line` reads as, with the record's shape already checked."""
        commands = _commands(_parsed(s, line, ())["lists"])
        assert len(commands) == 1, (
            "%r reads as %d commands and the check wrote one" % (line, len(commands)))
        return commands[0]

    def _error_record(s, line):
        """The error record `line` must answer, with its shape checked before its values.

        The lists read before the failure are the stage's business and the contract does
        not pin them; what is pinned is the record's keys, the kind's vocabulary, and
        that the byte that failed is a byte of the line (or the one just past its end).
        """
        record = s.parse(line)
        assert tuple(record) == tuple(s.PARSE_KEYS), (
            "%r answered the record %r, and a parse record is exactly PARSE_KEYS"
            % (line, tuple(record)))
        assert record["line"] == line, (
            "the record's line is %r and the line is %r" % (record["line"], line))
        assert isinstance(record["lists"], tuple), (
            "%r answered its lists as %r" % (line, record["lists"]))
        error = record["error"]
        assert isinstance(error, dict), (
            "%r cannot be read and it answered the error %r" % (line, error))
        assert tuple(error) == S1_ERROR_KEYS, (
            "%r answered the error %r, and an error is exactly (kind, offset, detail)"
            % (line, tuple(error)))
        assert error["kind"] in s.PARSE_ERRORS, (
            "%r answered the failure %r, which is not one of PARSE_ERRORS"
            % (line, error["kind"]))
        offset = error["offset"]
        assert isinstance(offset, int) and not isinstance(offset, bool), (
            "%r answered the failure byte %r" % (line, offset))
        assert 0 <= offset <= len(line), (
            "%r is %d bytes long and the failure is at byte %d" % (line, len(line), offset))
        assert isinstance(error["detail"], str) and error["detail"].strip(), (
            "%r answered the detail %r" % (line, error["detail"]))
        return error

    def _named(error, line, fragments):
        """The detail of a failure names what was expected and what stood there instead.

        `fragments` is what the check wrote into the fixture for this failure: the word
        for the operand the parser wanted (a `command`, a `file`), and the operator that
        arrived where it wanted it. A detail that says only "unexpected-operator" is a
        puzzle, and the contract asks for a sentence a user can act on.
        """
        for fragment in fragments:
            assert fragment in error["detail"], (
                "the detail %r of %r does not name %r" % (error["detail"], line, fragment))

    def _descriptor_of(kind):
        """The descriptor a redirection redirects, read from the operator's own bytes.

        The policy's operators carry their own descriptor when they open with a digit,
        and `<` and `<<` are the input side; everything else is fd 1.
        """
        if kind[0] in "0123456789":
            return int(kind[0])
        return 0 if kind[0] == "<" else 1

    def _s1_surface(s):
        """The stage's public surface is exactly the eight names §4.0 pins, and no more."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or isinstance(value, type(os)):
                continue
            public.add(name)
        assert public == set(S1_PUBLIC), (
            "the stage's public surface is %s and §4.0 pins %s"
            % (", ".join(sorted(public)), ", ".join(sorted(S1_PUBLIC))))
        assert callable(s.tokenize) and callable(s.parse), (
            "tokenize and parse are the stage's two ways in and both must be callable")

    def _s1_constants(s, rules):
        """The six key tuples and the failure kinds, in the order every record prints them.

        The operator vocabulary is cross-checked against the policy, because `tokenize`
        *is* the policy's operator list read longest first: a world whose operators are
        not §2.3's would make this stage's answers a different line's answers.
        """
        assert tuple(s.TOKEN_KEYS) == S1_TOKEN_KEYS
        assert tuple(s.TOKEN_KINDS) == S1_TOKEN_KINDS
        assert tuple(s.QUOTE_KINDS) == S1_QUOTE_KINDS
        assert tuple(s.PARSE_KEYS) == S1_PARSE_KEYS
        assert tuple(s.COMMAND_KEYS) == S1_COMMAND_KEYS
        assert tuple(s.PARSE_ERRORS) == S1_PARSE_ERRORS
        assert set(rules.OPERATORS) == set(("|", "&&", "||", ";", "&", ">", ">>", "<",
                                            "<<", "2>", "2>&1")), (
            "the policy's operators are %r and §2.3 pins eleven of them"
            % (rules.OPERATORS,))

    def _s1_operators(s, rules):
        """Every operator of the policy is one token, and the overlapping ones longest first.

        Each operator is written where an operator may begin, so a stage that tried `>`
        before `>>`, `&` before `&&`, `|` before `||`, `<` before `<<` or `2>` before
        `2>&1` answers more tokens than the line has fields — the count is the check's
        own, three for `a <op> b`. A digit is an ordinary byte of a word, so the digit
        operators are operators at a token boundary and nowhere else.
        """
        for operator in rules.OPERATORS:
            _expect_tokens(s, "a %s b" % (operator,),
                           (("word", "a", "none"), ("operator", operator, "none"),
                            ("word", "b", "none")))
        for line, longest in (("a >> b", ">>"), ("a && b", "&&"), ("a || b", "||"),
                              ("a << b", "<<"), ("a 2>&1 b", "2>&1")):
            assert line.count(longest) == 1, (
                "%r must hold one %s to be a boundary" % (line, longest))
            operators = tuple(token["text"] for token in s.tokenize(line)
                              if token["kind"] == "operator")
            assert operators == (longest,), (
                "%r is one %s and the stage read the operators %r"
                % (line, longest, operators))
            assert len(s.tokenize(line)) == len(line.split()) == 3, (
                "%r has three fields and the stage read %d tokens"
                % (line, len(s.tokenize(line))))
        for line, expected in (
                ("2>out", (("operator", "2>", "none"), ("word", "out", "none"))),
                ("x2>y", (("word", "x2", "none"), ("operator", ">", "none"),
                          ("word", "y", "none"))),
                ("12>x", (("word", "12", "none"), ("operator", ">", "none"),
                          ("word", "x", "none"))),
                ("echo y2>z", (("word", "echo", "none"), ("word", "y2", "none"),
                               ("operator", ">", "none"), ("word", "z", "none"))),
                ("a|b", (("word", "a", "none"), ("operator", "|", "none"),
                         ("word", "b", "none"))),
                ("a>b", (("word", "a", "none"), ("operator", ">", "none"),
                         ("word", "b", "none"))),
                ("a&&b", (("word", "a", "none"), ("operator", "&&", "none"),
                          ("word", "b", "none"))),
                ("a>>b", (("word", "a", "none"), ("operator", ">>", "none"),
                          ("word", "b", "none")))):
            _expect_tokens(s, line, expected)

    def _s1_quotes(s):
        """The bytes as written and the form that built the word, `mixed` included.

        Every form of `QUOTE_KINDS` is reached by a fixture of this check, and the check
        says so from the forms its own fixtures produced: a fixture that stopped landing
        on `mixed` would be an error here and not a quietly weaker test.
        """
        seen = []
        for line, expected in S1_QUOTED:
            seen += [token["quote"] for token in _expect_tokens(s, line, expected)]
        for form in S1_QUOTE_KINDS:
            assert form in seen, (
                "no fixture is a %s word, so that form of a word is untested" % (form,))

    def _s1_comments(s):
        """`#` opens a comment only where a word would begin."""
        for line, expected in S1_COMMENTED:
            _expect_tokens(s, line, expected)
        assert s.tokenize(S1_COMMENT) == () and s.tokenize("   # x") == (), (
            "a comment-only line holds no token")
        assert _one_command(s, "echo a #b")["words"] == ("echo", "a"), (
            "a comment is not a word of the command")
        assert _one_command(s, "echo a#b")["words"] == ("echo", "a#b"), (
            "`#` inside a word is an ordinary byte")

    def _s1_empty(s):
        """Empty, whitespace and comment-only lines read as no lists and no error.

        The `empty` error is a different fact from an empty line: it is a place where a
        command *had* to begin and an operator stood there instead — `|` with nothing on
        its left — while a separator that ends a list nobody began is an
        `unexpected-operator`.
        """
        for line in S1_EMPTY:
            tokens = s.tokenize(line)
            assert tokens == (), (
                "%r holds no token and the stage read %r" % (line, tokens))
            record = s.parse(line)
            assert tuple(record) == tuple(s.PARSE_KEYS)
            assert record["line"] == line, (
                "the record's line is %r and the line is %r" % (record["line"], line))
            assert record["lists"] == (), (
                "%r holds no command and the stage read the lists %r"
                % (line, record["lists"]))
            assert record["error"] is None, (
                "%r is not a failure and the stage answered %r"
                % (line, record["error"]))
        for line, kind in (("|", "empty"), ("| |", "empty"), ("; ;", "unexpected-operator")):
            error = _error_record(s, line)
            assert error["kind"] == kind, (
                "%r answered the failure %r and it is %r" % (line, error["kind"], kind))
            assert error["offset"] == 0, (
                "%r fails at its first byte and the stage answered byte %d"
                % (line, error["offset"]))

    def _s1_lists(s):
        """Every separator ends a list and begins the next; `|` joins commands inside one.

        The list count of a fixture is the separators the check wrote into it plus one
        (a trailing separator names no list, so it adds none), and the pipelines of a
        list are as many as the `|`s in that part of the line plus one.
        """
        line = "a | b && c ; d"
        separators = ("&&", ";")
        record = _parsed(s, line, separators)
        commands = _commands(record["lists"])
        assert tuple(command["words"] for command in commands) == (("a",), ("b",),
                                                                   ("c",), ("d",)), (
            "%r reads as the commands %r" % (line, tuple(c["words"] for c in commands)))
        assert tuple(element[1] for element in record["lists"]) == (None,) + separators, (
            "the connectors of %r are %r, and every one of them is in the answer"
            % (line, tuple(element[1] for element in record["lists"])))
        parts = ("a | b", "c", "d")
        sizes = tuple(len(pipeline) for element in record["lists"]
                      for pipeline in element[0])
        assert sizes == tuple(part.count("|") + 1 for part in parts), (
            "`|` joins commands inside one pipeline: %r" % (sizes,))
        line = "a & b ; c || d && e"
        record = _parsed(s, line, ("&", ";", "||", "&&"))
        commands = _commands(record["lists"])
        assert tuple(command["background"] for command in commands) == (True,) + (False,) * 4, (
            "only the list `&` ended is the background one: %r"
            % (tuple(command["background"] for command in commands),))
        line = "a | b &"
        commands = _commands(_parsed(s, line, ())["lists"])
        assert len(commands) == 2 and all(command["background"] for command in commands), (
            "a trailing `&` ends a list of two commands and both of them are background")
        for line in ("a ;", "a &"):
            commands = _commands(_parsed(s, line, ())["lists"])
            assert len(commands) == 1 and commands[0]["words"] == ("a",), (
                "%r is one list, because a trailing separator names no list after it"
                % (line,))
            assert commands[0]["background"] is line.endswith("&"), (
                "%r answers background %r for its one command"
                % (line, commands[0]["background"]))
        line = "a | b ; c | d | e"
        record = _parsed(s, line, (";",))
        sizes = tuple(len(pipeline) for element in record["lists"]
                      for pipeline in element[0])
        assert sizes == tuple(part.count("|") + 1 for part in ("a | b", "c | d | e")), (
            "%r reads as pipelines of %r commands" % (line, sizes))

    def _s1_redirects(s):
        """Each redirection: its operator, its descriptor, its target as written, its quoting.

        The target of `2>&1` is the descriptor the operator itself names — its own
        fourth byte — and a quoted target keeps its quotes, because `quoted` is what
        §4.2 reads to decide whether a here-document expands. A redirection's target is
        never a word of the argv.
        """
        line = "cat < in >> out 2> err 2>&1"
        command = _one_command(s, line)
        assert command["words"] == ("cat",), (
            "a redirection's target is not a word of the argv: %r" % (command["words"],))
        redirects = command["redirects"]
        wanted = (("<", "in"), (">>", "out"), ("2>", "err"), ("2>&1", "2>&1"[3]))
        assert len(redirects) == len(wanted), (
            "%r writes %d redirections and the stage answered %d"
            % (line, len(wanted), len(redirects)))
        for record, (kind, target) in zip(redirects, wanted):
            assert tuple(record) == S1_REDIRECT_KEYS, (
                "%r answered the redirection %r, and a redirection is exactly "
                "(kind, fd, target, quoted)" % (line, tuple(record)))
            assert record["kind"] == kind, (
                "%r wrote the redirection %r and the stage answered %r"
                % (line, kind, record["kind"]))
            assert record["fd"] == _descriptor_of(kind), (
                "the redirection %r redirects fd %d and the stage answered %r"
                % (kind, _descriptor_of(kind), record["fd"]))
            assert record["target"] == target, (
                "the redirection %r takes the target %r and the stage answered %r"
                % (kind, target, record["target"]))
            assert record["quoted"] is False, (
                "the target %r is not quoted" % (target,))
        line = 'cat << "END" < "in" >> "out"'
        command = _one_command(s, line)
        assert command["words"] == ("cat",), (
            "a here-document's delimiter is not a word of the argv: %r"
            % (command["words"],))
        for record, kind in zip(command["redirects"], ("<<", "<", ">>")):
            assert record["kind"] == kind
            assert record["fd"] == _descriptor_of(kind), (
                "the redirection %r redirects fd %d and the stage answered %r"
                % (kind, _descriptor_of(kind), record["fd"]))
            assert record["quoted"] is True, (
                "the target %r was written in quotes and §4.2 has to be able to see it"
                % (record["target"],))
            assert record["target"].startswith(("\"", "'")), (
                "a target is its bytes as written: %r" % (record["target"],))
        both = _one_command(s, "cat 2> err 2>&1")["redirects"]
        assert both[0]["fd"] == both[1]["fd"] == 2, (
            "`2>` and `2>&1` both redirect fd 2: %r" % (tuple(r["fd"] for r in both),))

    S1_ASSIGNED = (
        ("FOO=1 echo hi", ("FOO=1", "echo", "hi"), "FOO=1"),
        ("FOO=", ("FOO=",), "FOO="),
        ("FOO='a b'", ("FOO='a b'",), "FOO='a b'"),
        ("_x=1", ("_x=1",), "_x=1"),
        ("A=1 B=2 cmd", ("A=1", "B=2", "cmd"), "A=1"),
        ("echo a=b", ("echo", "a=b"), None),
        ("echo 1FOO=x", ("echo", "1FOO=x"), None),
        ("=x", ("=x",), None),
        ("FOO-1=x", ("FOO-1=x",), None),
        ("echo hi", ("echo", "hi"), None),
    )

    def _s1_assignment(s):
        """The leading `NAME=value` word, which stays in `words` as well."""
        for line, words, assignment in S1_ASSIGNED:
            command = _one_command(s, line)
            assert command["words"] == words, (
                "%r reads as the words %r and the check wrote %r"
                % (line, command["words"], words))
            assert command["assignment"] == assignment, (
                "%r answers the assignment %r and the check wrote %r"
                % (line, command["assignment"], assignment))
        command = _one_command(s, "FOO=1 cmd > out")
        assert command["assignment"] == "FOO=1" and command["words"] == ("FOO=1", "cmd"), (
            "a redirection does not move the leading word: %r" % (command,))
        _expect_tokens(s, "FOO='a b'", (("word", "FOO='a b'", "mixed"),))

    def _s1_errors(s):
        """Every way a line fails: its kind, the byte that failed, and what was expected.

        The byte is the marker's *last* occurrence in the line, which is the second one
        where the check wrote it twice: a stage that answered the first `;` of `a ; ; b`
        would be reporting the wrong failure. A trailing operator fails at the byte its
        operand was due at — the operator's own end — which is why a fixture that ends
        in whitespace does not fail at the line's length, and why the detail has to name
        what was expected rather than only which rule broke.
        """
        kinds = []
        for kind, line, marker, fragments in S1_AT_THE_TOKEN:
            error = _error_record(s, line)
            assert error["kind"] == kind, (
                "%r answered the failure %r and it is %r" % (line, error["kind"], kind))
            at = line.rindex(marker)
            assert error["offset"] == at, (
                "%r fails at byte %d, where its last %r stands, and the stage answered "
                "byte %d" % (line, at, marker, error["offset"]))
            _named(error, line, fragments)
            if kind == "unterminated-quote" or error["offset"] == 0:
                assert s.parse(line)["lists"] == (), (
                    "%r fails before its first command, so it has no lists: %r"
                    % (line, s.parse(line)["lists"]))
            kinds.append(kind)
        for line, operator, fragments in S1_TRAILING:
            error = _error_record(s, line)
            assert error["kind"] == "trailing-operator", (
                "%r ends inside the operator %r and the stage answered %r"
                % (line, operator, error["kind"]))
            at = line.index(operator) + len(operator)
            assert error["offset"] == at, (
                "%r fails where the operand was due, byte %d, and the stage answered "
                "byte %d" % (line, at, error["offset"]))
            _named(error, line, fragments)
            kinds.append("trailing-operator")
        for kind in s.PARSE_ERRORS:
            assert kind in kinds, (
                "no fixture of this check fails with %r, so that failure of a line is "
                "untested" % (kind,))
        # the lists a failed line did read are the ones its head reads: `a ; ; b` reads
        # the one list `a ;` reads before its second separator fails
        assert s.parse("a ; ; b")["lists"] == s.parse("a ; ")["lists"], (
            "`a ; ; b` answers the lists %r and its head `a ; ` answers %r"
            % (s.parse("a ; ; b")["lists"], s.parse("a ; ")["lists"]))

    def _s1_refusals(s, machine_module):
        """A line that is not a string is the caller's mistake, named; a bad line is data."""
        for line, name in ((5, "5"), (True, "True"), (None, "None"), (b"ls", "b'ls'"),
                           (["ls"], "'ls'"), (("ls",), "ls"), ({"line": "ls"}, "line")):
            _refuses(machine_module.MachineError, "tokenize(%r)" % (line,),
                     lambda line=line: s.tokenize(line), (name,))
            _refuses(machine_module.MachineError, "parse(%r)" % (line,),
                     lambda line=line: s.parse(line), (name,))
        for line in _fixture_lines():
            s.tokenize(line)
            s.parse(line)

    def _s1_ledger(s, machine_module):
        """The stage asks the machine nothing at all: every door of its ledger stays at zero.

        This stage is text in and records out — it is handed no machine and calls none —
        so the proof is the machine's own count of every door it has: not one of them
        moves across a whole pass over every fixture, malformed lines included.
        """
        m = machine_module.machine(7)
        before = dict(m.stats())
        for door in S1_DOORS:
            assert door in before, (
                "the machine's ledger has no %r count, and §2.1 pins it" % (door,))
            assert before[door] == 0, (
                "a fresh machine has already been asked for %r" % (door,))
        for line in _fixture_lines():
            s.tokenize(line)
            s.parse(line)
        after = dict(m.stats())
        assert after == before, (
            "the stage moved the machine's ledger: %r became %r" % (before, after))
        assert m.deadlocks() == (), (
            "the stage cannot deadlock a machine it never asks: %r" % (m.deadlocks(),))

    def _s1_twice(s):
        """Two runs of one workload answer equal records: a line is a function of its bytes."""
        first = tuple((s.tokenize(line), s.parse(line)) for line in _fixture_lines())
        second = tuple((s.tokenize(line), s.parse(line)) for line in _fixture_lines())
        assert first == second, (
            "two runs of one workload answered differently, so the stage is holding "
            "state between lines")

    """Every assertion the contract's §4.1 makes about this stage."""
    import machine
    import rules
    import stage_01 as s
    _s1_surface(s)
    _s1_constants(s, rules)
    _s1_operators(s, rules)
    _s1_quotes(s)
    _s1_comments(s)
    _s1_empty(s)
    _s1_lists(s)
    _s1_redirects(s)
    _s1_assignment(s)
    _s1_errors(s)
    _s1_refusals(s, machine)
    _s1_ledger(s, machine)
    _s1_twice(s)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    S2_KEYS = ("text", "words", "error")

    S2_ERRORS = ("bad-substitution", "unset-variable", "bad-glob",
                 "here-document-unterminated")

    S2_ORDER = ("parameter", "tilde", "split", "glob", "quote-removal")

    S2_DOORS = ("spawn", "fork", "exec", "wait", "pipe", "open", "dup2", "close",
                "read", "write", "signal", "ticks", "steps", "deadlocks")

    S2_VARS = {"HOME": "/home/g7/a b", "NAME": "abcdef", "BOTH": "bee", "EMPTY": "",
               "TILDE": "~", "STAR": "*", "SPACE": "a b", "Q": 'a"b'}

    S2_UNSET = "__G7_STAGE02_NOT_SET__"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("stage_02.py", "machine.py", "rules.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s2_class_end(pattern, at):
        """The byte of the `]` closing the class opened at `pattern[at]`, or `-1`."""
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

    def _s2_members(body):
        """The class's body as its members: the bytes and the `a-z` ranges it names."""
        members = []
        index = 0
        while index < len(body):
            if index + 2 < len(body) and body[index + 1] == "-":
                members.append((body[index], body[index + 2]))
                index = index + 3
            else:
                members.append(body[index])
                index = index + 1
        return members

    def _s2_match_at(pattern, at, path, which, cross):
        """True when `pattern[at:]` matches `path[which:]`."""
        while at < len(pattern):
            byte = pattern[at]
            if byte == "*":
                rest = at
                while rest < len(pattern) and pattern[rest] == "*":
                    rest = rest + 1
                here = which
                while True:
                    if _s2_match_at(pattern, rest, path, here, cross):
                        return True
                    if here >= len(path) or (path[here] == "/" and not cross):
                        return False
                    here = here + 1
            elif byte == "?":
                if which >= len(path) or (path[which] == "/" and not cross):
                    return False
                at = at + 1
                which = which + 1
            elif byte == "[":
                close = _s2_class_end(pattern, at)
                if close < 0 or which >= len(path) or (path[which] == "/" and not cross):
                    return False
                body = pattern[at + 1:close]
                negate = body.startswith("!") or body.startswith("^")
                if negate:
                    body = body[1:]
                hit = False
                for member in _s2_members(body):
                    if isinstance(member, tuple):
                        if member[0] <= path[which] <= member[1]:
                            hit = True
                    elif member == path[which]:
                        hit = True
                if hit == negate:
                    return False
                at = close + 1
                which = which + 1
            else:
                if which >= len(path) or path[which] != byte:
                    return False
                at = at + 1
                which = which + 1
        return which == len(path)

    def _s2_matches(pattern, files, cross=False):
        """The paths of `files` the pattern matches, in the order `files` holds them."""
        return tuple(path for path in files if _s2_match_at(pattern, 0, path, 0, cross))

    def _s2_expected(pattern, files, cross=False):
        """What `glob` must answer: the matches, or the pattern as written when there are none."""
        matches = _s2_matches(pattern, files, cross)
        if not matches:
            return (pattern,)
        return tuple(sorted(matches))

    def _s2_error(got, kind, offset, what):
        """The error record `got` must be: §4.1's three fields, and the byte that failed."""
        assert isinstance(got, dict), "%s answered %r, and an error is a record" % (what, got)
        assert tuple(got) == ("kind", "offset", "detail"), (
            "%s answered the error %r, and an error is ('kind', 'offset', 'detail')"
            % (what, tuple(got)))
        assert got["kind"] == kind, (
            "%s answered the error %r, and its kind is %r" % (what, got, kind))
        assert got["offset"] == offset, (
            "%s answered the error %r, and the byte that failed is %d"
            % (what, got, offset))
        assert isinstance(got["detail"], str) and got["detail"], (
            "%s answered an error without a detail: %r" % (what, got))

    def _s2_expansion(got, text, words, what):
        """The `EXPAND_KEYS` record `got` must be, on a text that expanded."""
        assert isinstance(got, dict), "%s answered %r, and an expansion is a record" % (what, got)
        assert tuple(got) == S2_KEYS, (
            "%s answered %r, and an expansion is the fields %r" % (what, tuple(got), S2_KEYS))
        assert got["error"] is None, (
            "%s answered the error %r, and this text expands" % (what, got["error"]))
        assert got["words"] == words, (
            "%s answered the words %r, and it is %r" % (what, got["words"], words))
        assert got["text"] == text, (
            "%s answered the text %r, and after the parameter and tilde phases it is %r"
            % (what, got["text"], text))

    def _s2_failed(got, kind, offset, what):
        """The `EXPAND_KEYS` record of an expansion that failed: the error, and no payload."""
        assert isinstance(got, dict), "%s answered %r, and an expansion is a record" % (what, got)
        assert tuple(got) == S2_KEYS, (
            "%s answered %r, and an expansion is the fields %r" % (what, tuple(got), S2_KEYS))
        assert got["words"] == (), (
            "%s answered the words %r, and a failed expansion answers no words"
            % (what, got["words"]))
        assert got["text"] is None, (
            "%s answered the text %r, and a failed expansion answers none" % (what, got["text"]))
        _s2_error(got["error"], kind, offset, what)

    def _s2_paths(got, paths, what):
        """The `{"paths", "error"}` record `glob` must answer."""
        assert isinstance(got, dict), "%s answered %r, and a glob is a record" % (what, got)
        assert tuple(got) == ("paths", "error"), (
            "%s answered %r, and a glob is ('paths', 'error')" % (what, tuple(got)))
        assert got["error"] is None, (
            "%s answered the error %r, and this pattern is well formed" % (what, got["error"]))
        assert got["paths"] == paths, (
            "%s answered the paths %r, and they are %r" % (what, got["paths"], paths))

    def _s2_bytes(got, data, what):
        """The `{"bytes", "error"}` record a here-document must answer."""
        assert isinstance(got, dict), "%s answered %r, and a here-document is a record" % (what, got)
        assert tuple(got) == ("bytes", "error"), (
            "%s answered %r, and a here-document is ('bytes', 'error')"
            % (what, tuple(got)))
        assert got["error"] is None, (
            "%s answered the error %r, and this document is terminated" % (what, got["error"]))
        assert got["bytes"] == data, (
            "%s answered the bytes %r, and they are %r" % (what, got["bytes"], data))

    def _s2_state(vars, nounset=False):
        """The shell's own state record, as stage 9 builds it: a table and its flags."""
        table = dict(S2_VARS)
        table.update(vars)
        return {"variables": table, "flags": {"nounset": nounset},
                "exported": (), "traps": (), "jobs": (), "cwd": None, "exit": None,
                "args": (), "stdin": b""}

    def _s2_constants(s, rules):
        """The three constants, and the policy's own order behind the stage's five phases."""
        assert tuple(s.EXPAND_KEYS) == S2_KEYS, (
            "EXPAND_KEYS is %r, and an expansion is the three fields %r"
            % (tuple(s.EXPAND_KEYS), S2_KEYS))
        assert tuple(s.EXPAND_ERRORS) == S2_ERRORS, (
            "EXPAND_ERRORS is %r, and an expansion fails in the four ways %r"
            % (tuple(s.EXPAND_ERRORS), S2_ERRORS))
        assert tuple(rules.EXPANSION_ORDER) == S2_ORDER, (
            "the rules' expansion order is %r, and the five phases in order are %r"
            % (tuple(rules.EXPANSION_ORDER), S2_ORDER))

    def _s2_substituted(got, text, what):
        """The `{"text", "error"}` record `substitute` must answer."""
        assert isinstance(got, dict), "%s answered %r, and a substitution is a record" % (what, got)
        assert tuple(got) == ("text", "error"), (
            "%s answered %r, and a substitution is ('text', 'error')" % (what, tuple(got)))
        assert got["error"] is None, (
            "%s answered the error %r, and this text substitutes" % (what, got["error"]))
        assert got["text"] == text, (
            "%s answered the text %r, and this phase leaves %r" % (what, got["text"], text))

    def _s2_grammar(s, m):
        """`$NAME` to `${#NAME}`, and the four bodies outside that grammar."""
        plain = dict(S2_VARS)
        unset = S2_UNSET
        _s2_expansion(s.expand(m, "$BOTH", plain), "bee", ("bee",), "$BOTH")
        _s2_expansion(s.expand(m, "${BOTH}", plain), "bee", ("bee",), "${BOTH}")
        _s2_expansion(s.expand(m, "$NAME-x", plain), "abcdef-x", ("abcdef-x",), "$NAME-x")
        _s2_expansion(s.expand(m, "x$N/y", plain), "x/y", ("x/y",),
                      "$N: the name stops at the /, and an unset name writes nothing")
        _s2_expansion(s.expand(m, "$" + unset, plain), "", (), "$<unset>")
        _s2_expansion(s.expand(m, "x$" + unset, plain), "x", ("x",), "x$<unset>")
        _s2_expansion(s.expand(m, "${%s:-d}" % (unset,), plain), "d", ("d",), "${<unset>:-d}")
        _s2_expansion(s.expand(m, "${EMPTY:-d}", plain), "d", ("d",), "${EMPTY:-d}")
        _s2_expansion(s.expand(m, "${BOTH:-d}", plain), "bee", ("bee",), "${BOTH:-d}")
        _s2_expansion(s.expand(m, "${%s:-}" % (unset,), plain), "", (), "${<unset>:-}")
        _s2_expansion(s.expand(m, "${%s:-$BOTH}" % (unset,), plain), "bee", ("bee",),
                      "${<unset>:-$BOTH}, whose own word is expanded once")
        _s2_expansion(s.expand(m, "${%s:+d}" % (unset,), plain), "", (), "${<unset>:+d}")
        _s2_expansion(s.expand(m, "${EMPTY:+d}", plain), "", (), "${EMPTY:+d}")
        _s2_expansion(s.expand(m, "${BOTH:+d}", plain), "d", ("d",), "${BOTH:+d}")
        _s2_expansion(s.expand(m, "${%s:+$BOTH}" % (unset,), plain), "", (), "${<unset>:+$BOTH}")
        _s2_expansion(s.expand(m, "${NAME#abc}", plain), "def", ("def",), "${NAME#abc}")
        _s2_expansion(s.expand(m, "${NAME#ab}", plain), "cdef", ("cdef",), "${NAME#ab}")
        _s2_expansion(s.expand(m, "${NAME#x}", plain), "abcdef", ("abcdef",), "${NAME#x}")
        _s2_expansion(s.expand(m, "${NAME#}", plain), "abcdef", ("abcdef",), "${NAME#}")
        _s2_expansion(s.expand(m, "${NAME%def}", plain), "abc", ("abc",), "${NAME%def}")
        _s2_expansion(s.expand(m, "${NAME%ef}", plain), "abcd", ("abcd",), "${NAME%ef}")
        _s2_expansion(s.expand(m, "${NAME%x}", plain), "abcdef", ("abcdef",), "${NAME%x}")
        _s2_expansion(s.expand(m, "${NAME%}", plain), "abcdef", ("abcdef",), "${NAME%}")
        _s2_expansion(s.expand(m, "${BOTH#$BOTH}", plain), "bee", ("bee",),
                      "${BOTH#$BOTH}, whose operand is one literal and not a word")
        _s2_expansion(s.expand(m, "${#NAME}", plain), "6", ("6",), "${#NAME}")
        _s2_expansion(s.expand(m, "${#EMPTY}", plain), "0", ("0",), "${#EMPTY}")
        _s2_expansion(s.expand(m, "${#%s}" % (unset,), plain), "0", ("0",), "${#<unset>}")
        _s2_expansion(s.expand(m, "$", plain), "$", ("$",), "a lone $")
        _s2_expansion(s.expand(m, "x$", plain), "x$", ("x$",), "a $ that ends the text")
        _s2_expansion(s.expand(m, "$.", plain), "$.", ("$.",), "$. — no name begins with a .")
        _s2_expansion(s.expand(m, "$1", plain), "$1", ("$1",), "$1 — no name begins with a 1")
        _s2_substituted(s.substitute(m, "$BOTH/$NAME", plain), "bee/abcdef", "substitute")
        _s2_substituted(s.substitute(m, "${BOTH:-z}${#NAME}", plain), "bee6", "substitute")
        _s2_substituted(s.substitute(m, "'$BOTH'", plain), "'$BOTH'", "substitute, in quotes")
        _s2_substituted(s.substitute(m, "a\\b", plain), "a\\b",
                        "substitute, an escape's backslash written back")
        _s2_substituted(s.substitute(m, "\"$BOTH\"", plain), "\"bee\"",
                        "substitute, the double quotes written back")
        _s2_failed(s.expand(m, "${BOTH", plain), "bad-substitution", 0, "${BOTH, never closed")
        _s2_failed(s.expand(m, "${}", plain), "bad-substitution", 0, "${}, with no name")
        _s2_failed(s.expand(m, "${BOTH:z}", plain), "bad-substitution", 0, "${BOTH:z}")
        _s2_failed(s.expand(m, "${BOTH##ab}", plain), "bad-substitution", 0, "${BOTH##ab}")
        _s2_failed(s.expand(m, "${BOTH:-${BOTH}}", plain), "bad-substitution", 0,
                   "${BOTH:-${BOTH}}, whose braces would nest")
        _s2_failed(s.expand(m, "${#}", plain), "bad-substitution", 0, "${#}, with no name")
        _s2_failed(s.expand(m, "${!BOTH}", plain), "bad-substitution", 0, "${!BOTH}")
        _s2_failed(s.expand(m, "x${BOTH:z}", plain), "bad-substitution", 1,
                   "a bad body after a byte that is fine")
        _s2_failed(s.expand(m, "a $BOTH ${BOTH", plain), "bad-substitution", 8,
                   "a bad body in the second word of three")

    def _s2_order(s, m):
        """A pair of words per swapped pair of phases: only the right order gets both right."""
        plain = dict(S2_VARS)
        pattern = _s2_pattern_of(m)
        with_pattern = dict(S2_VARS)
        with_pattern["PAT"] = pattern
        expected = _s2_expected(pattern, tuple(sorted(m.files())))
        # parameter, then split: the expansion's own whitespace is a boundary and a
        # quoted expansion's is not, even when the two stand next to each other.
        _s2_expansion(s.expand(m, "$SPACE", plain), "a b", ("a", "b"),
                      "$SPACE — split after the parameter")
        _s2_expansion(s.expand(m, '"$SPACE"', plain), '"a b"', ("a b",),
                      '"$SPACE" — no split inside the quotes')
        _s2_expansion(s.expand(m, '"$SPACE"$SPACE', plain), '"a b"a b', ("a ba", "b"),
                      '"$SPACE"$SPACE — one boundary, on the unquoted side')
        # parameter, then glob: what the parameter put there is what the glob matches.
        _s2_expansion(s.expand(m, "$PAT", with_pattern), pattern, expected,
                      "$PAT — the pattern comes out of the parameter")
        _s2_expansion(s.expand(m, '"$PAT"', with_pattern), '"' + pattern + '"', (pattern,),
                      '"$PAT" — a quoted pattern is a word, not a pattern')
        # tilde, then split: the path the tilde inserted is unquoted text.
        _s2_expansion(s.expand(m, "~", plain), "/home/g7/a b", ("/home/g7/a", "b"),
                      "~ — the tilde runs before the split")
        _s2_expansion(s.expand_word(m, "~", plain), "/home/g7/a b", ("/home/g7/a", "b"),
                      "expand_word ~ — and it runs before that one's split too")
        # parameter, then tilde: a ~ the parameter produced is at the start of a word.
        _s2_expansion(s.expand(m, "$TILDE", plain), "/home/g7/a b", ("/home/g7/a", "b"),
                      "$TILDE — the tilde runs after the parameter")

    def _s2_quoting(s, m):
        """Single quotes stop everything, double quotes stop splitting and globbing, a backslash quotes one byte."""
        plain = dict(S2_VARS)
        _s2_expansion(s.expand(m, "'$SPACE'", plain), "'$SPACE'", ("$SPACE",),
                      "a single-quoted parameter")
        _s2_expansion(s.expand(m, "'a\"b'", plain), "'a\"b'", ('a"b',),
                      "a double quote inside single quotes")
        _s2_expansion(s.expand(m, "'a\\b'", plain), "'a\\b'", ("a\\b",),
                      "a backslash inside single quotes is a byte")
        _s2_expansion(s.expand(m, '"$BOTH"', plain), '"bee"', ("bee",),
                      "a double-quoted parameter expands")
        _s2_expansion(s.expand(m, 'x"$SPACE"', plain), 'x"a b"', ("xa b",),
                      "a quoted expansion inside a word")
        _s2_expansion(s.expand(m, "\\$BOTH", plain), "\\$BOTH", ("$BOTH",),
                      "a backslash before a $")
        _s2_expansion(s.expand(m, "a\\ b", plain), "a\\ b", ("a b",),
                      "a backslash before a space")
        _s2_expansion(s.expand(m, '"\\$BOTH"', plain), '"\\$BOTH"', ("$BOTH",),
                      "a backslash inside double quotes")
        _s2_expansion(s.expand(m, '"a\\"b"', plain), '"a\\"b"', ('a"b',),
                      "an escaped double quote ends nothing")
        _s2_expansion(s.expand(m, "x\\", plain), "x\\", ("x\\",),
                      "a trailing backslash escapes nothing")
        _s2_expansion(s.expand(m, "\\$SPACE", plain), "\\$SPACE", ("$SPACE",),
                      "an escaped $ is a byte, and the space after it is not expanded")

    def _s2_tilde(s, m):
        """A leading `~` of a word, and only that."""
        plain = dict(S2_VARS)
        _s2_expansion(s.expand(m, "~/x", plain), "/home/g7/a b/x", ("/home/g7/a", "b/x"),
                      "~ before a /")
        _s2_expansion(s.expand(m, "~user", plain), "~user", ("~user",),
                      "~user, and this machine has no user table")
        _s2_expansion(s.expand(m, '"~"', plain), '"~"', ("~",), "a double-quoted tilde")
        _s2_expansion(s.expand(m, "'~'", plain), "'~'", ("~",), "a single-quoted tilde")
        _s2_expansion(s.expand(m, '"~/x"', plain), '"~/x"', ("~/x",),
                      "a double-quoted tilde before a / is a byte like any other")
        _s2_expansion(s.expand(m, "\\~", plain), "\\~", ("~",), "an escaped tilde")
        _s2_expansion(s.expand(m, "a~b", plain), "a~b", ("a~b",), "a tilde inside a word")
        _s2_expansion(s.expand(m, "~x/y", plain), "~x/y", ("~x/y",), "~x, which is no tilde")
        _s2_expansion(s.expand(m, "~", {"variables": {}, "flags": {}}), "~", ("~",),
                      "a tilde with no HOME to expand it")
        _s2_expansion(s.expand(m, "$HOME", plain), "/home/g7/a b", ("/home/g7/a", "b"),
                      "$HOME, the parameter that is the whole point of the phase order")
        _s2_expansion(s.expand_word(m, "a ~", plain), "a ~", ("a ~",),
                      "a word's own space is not a boundary, so its tilde is not one either")

    def _s2_split(s, m):
        """Boundaries and fields: what a word is, and what an empty expansion leaves."""
        plain = dict(S2_VARS)
        unset = S2_UNSET
        _s2_expansion(s.expand(m, "a b", plain), "a b", ("a", "b"), "two words in the text")
        _s2_expansion(s.expand_word(m, "a b", plain), "a b", ("a b",),
                      "two words in a word, which is one word")
        _s2_expansion(s.expand(m, "a  b", plain), "a  b", ("a", "b"),
                      "a run of spaces is one boundary")
        _s2_expansion(s.expand(m, " a b ", plain), " a b ", ("a", "b"),
                      "spaces at the ends are boundaries and not words")
        _s2_expansion(s.expand(m, "   ", plain), "   ", (), "nothing but space")
        _s2_expansion(s.expand(m, "", plain), "", (), "an empty text")
        _s2_expansion(s.expand(m, "$" + unset, plain), "", (), "$<unset> leaves no word")
        _s2_expansion(s.expand(m, "''", plain), "''", ("",), "a single-quoted empty word")
        _s2_expansion(s.expand(m, '""', plain), '""', ("",), "a double-quoted empty word")
        _s2_expansion(s.expand(m, '"$' + unset + '"', plain), '""', ("",),
                      "an empty expansion inside quotes is still a word")
        _s2_expansion(s.expand(m, "a$" + unset, plain), "a", ("a",),
                      "an empty expansion after a byte")
        _s2_expansion(s.expand(m, "$" + unset + "$" + unset, plain), "", (),
                      "two empty expansions leave nothing at all")

    def _s2_plain(files):
        """The machine's paths that hold no metacharacter: patterns that are not patterns."""
        plain = tuple(path for path in files
                      if "*" not in path and "?" not in path and "[" not in path)
        assert plain, ("the machine holds no path without a metacharacter in it: this check "
                       "needs one to prove that a plain path is not a pattern")
        assert plain[0].startswith("/"), (
            "the machine's paths are absolute in this course, and %r is not" % (plain[0],))
        return plain

    def _s2_groups(files):
        """The machine's paths under the directory each one sits in."""
        groups = {}
        for path in files:
            head, _, tail = path.rpartition("/")
            groups.setdefault(head, []).append(path)
        return groups

    def _s2_directory(files):
        """The directory of the machine's that holds the most direct children, and those children."""
        groups = _s2_groups(files)
        best = ""
        for head in sorted(groups):
            if len(groups[head]) > len(groups.get(best, ())):
                best = head
        children = tuple(sorted(groups[best]))
        assert len(children) >= 2, (
            "the machine holds no directory with two paths in it: stage 2's glob has no "
            "population to answer in sorted order, and this check will not weaken itself "
            "into a fixture that cannot see the order")
        return best, children

    def _s2_pattern_of(m):
        """The `dir/*` pattern the machine's own filesystem fills, for the order blocks."""
        head, _ = _s2_directory(tuple(sorted(m.files())))
        return head + "/*"

    def _s2_tail_byte(children, banned):
        """A byte one of the children's names ends with, and that is not in `banned`."""
        for path in children:
            byte = path[-1]
            if byte not in banned:
                return byte
        return None

    def _s2_after(byte, banned):
        """A byte greater than `byte` and not in `banned`: the top of a range that cannot match."""
        for candidate in "!#%&+,-.0123456789:;<=>@ABCDEFGHIJKLMNOPQRSTUVWXYZ[]^_`abcdefghijklmnopqrstuvwxyz{|}~":
            if candidate not in banned and byte < candidate:
                return candidate
        return None

    def _s2_glob_error(got, kind, offset, what):
        """A glob that failed: the record, the kind, and the byte of the pattern that failed."""
        assert isinstance(got, dict), "%s answered %r, and a glob is a record" % (what, got)
        assert tuple(got) == ("paths", "error"), (
            "%s answered %r, and a glob is ('paths', 'error')" % (what, tuple(got)))
        assert got["paths"] is None, (
            "%s answered the paths %r, and a failed pattern answers none" % (what, got["paths"]))
        _s2_error(got["error"], kind, offset, what)

    def _s2_glob(s, m):
        """`machine.files()` as the population, and every rule the pattern has to obey."""
        files = tuple(sorted(m.files()))
        assert files, "the machine's filesystem is empty: stage 2's glob has no population"
        plain = _s2_plain(files)
        directory, children = _s2_directory(files)

        # a plain path is not a pattern, and a pattern that matches nothing stands
        for path in plain[:4]:
            _s2_paths(s.glob(m, path), (path,), "glob of the plain path %r" % (path,))
        missing = plain[0] + "-no-such-path"
        _s2_paths(s.glob(m, missing), (missing,), "a pattern the machine cannot match")
        _s2_paths(s.glob(m, directory + "/*"), _s2_expected(directory + "/*", files),
                  "the direct children of %r, in sorted order" % (directory,))

        # a `*`, a `?` and a class each stop at a `/`: the strict reading the contract
        # pins, against the loose one a mutant would take, on a pattern whose only
        # possible match is a path the machine itself holds.
        crossing = next(path for path in plain if path.count("/") >= 2)
        tail = crossing.rpartition("/")[2]
        assert tail, ("the crossing path %r ends in a /, and no basename follows it"
                      % (crossing,))
        for label, pattern in (("a * that would have to cross a /", "*" + tail),
                               ("a ? that would have to cross a /", "?" + crossing[1:]),
                               ("a class that would have to cross a /",
                                "[/]" + crossing[1:])):
            strict = _s2_matches(pattern, files)
            loose = _s2_matches(pattern, files, cross=True)
            assert not strict and loose, (
                "the machine's own paths do not separate %s (pattern %r): the strict reading "
                "matches %r and the loose one %r, and this check needs them to differ"
                % (label, pattern, strict, loose))
            _s2_paths(s.glob(m, pattern), (pattern,),
                      "%s, so %r is as written" % (label, pattern))

        # a range that cannot match, and a class that negates: the two readings of the
        # class's own letters, settled on a name the machine holds.
        tail = children[0].rpartition("/")[2]
        top = _s2_after(tail[-1] if tail else "a", "/")
        assert top is not None, (
            "no byte sorts above %r for a reversed range: this check needs one"
            % (tail[-1] if tail else "a",))
        reversed_range = directory + "/[" + top + "-" + (tail[-1] if tail else "a") + "]*"
        assert not _s2_matches(reversed_range, files), (
            "the reversed range %r matched a path, and a range whose ends are the wrong way "
            "round matches nothing" % (reversed_range,))
        _s2_paths(s.glob(m, reversed_range), (reversed_range,),
                  "a range whose ends are the wrong way round")
        last = _s2_tail_byte(children, "[]-!")
        assert last is not None, ("the machine's names all end in a class's own bytes: this "
                                  "check needs one that does not")
        quoted_class = directory + "/*[" + last + "]"
        _s2_paths(s.glob(m, quoted_class), _s2_expected(quoted_class, files),
                  "the children whose name ends in %r" % (last,))
        negated = directory + "/[!" + tail[0] + "]*"
        answer = s.glob(m, negated)
        _s2_paths(answer, _s2_expected(negated, files),
                  "the children whose name does not start with %r" % (tail[0],))
        assert children[0] not in answer["paths"], (
            "the negated class %r matched %r, and a `[!x]` never matches an `x`"
            % (negated, children[0]))

        # the class a `]` opens, and the two classes that are not classes at all
        _s2_paths(s.glob(m, directory + "/[]" + tail[-1] + "]*"),
                  _s2_expected(directory + "/[]" + tail[-1] + "]*", files),
                  "a class whose first member is a ]")
        broken = directory + "/[bad"
        _s2_glob_error(s.glob(m, broken), "bad-glob", len(directory) + 1,
                       "the class %r that is never closed" % (broken,))
        empty = directory + "/[]"
        _s2_glob_error(s.glob(m, empty), "bad-glob", len(directory) + 1,
                       "the class %r with no member at all" % (empty,))

        # the same rule inside a word: quoted metacharacters are bytes, an escaped one
        # is a byte, and a word is a pattern only where its metacharacter is unquoted.
        pattern = _s2_pattern_of(m)
        expected = _s2_expected(pattern, files)
        assert len(expected) >= 2, (
            "the pattern %r matches %r: stage 2's glob has nothing to sort"
            % (pattern, expected))
        _s2_expansion(s.expand(m, directory + "/*", {}), directory + "/*", expected,
                      "a word that is a pattern")
        _s2_expansion(s.expand(m, '"' + directory + '/*"', {}),
                      '"' + directory + '/*"', (directory + "/*",),
                      "a quoted pattern is a word")
        _s2_expansion(s.expand_word(m, "x/" + "*", {}), "x/*", ("x/*",),
                      "a pattern that matches nothing is the word as written")
        escaped = directory + "/\\*"
        _s2_expansion(s.expand(m, escaped, {}), escaped, (directory + "/*",),
                      "an escaped metacharacter is a byte and not a pattern")
        _s2_expansion(s.expand(m, '"' + directory + '/[bad"', {}),
                      '"' + directory + '/[bad"', (directory + "/[bad",),
                      "a quoted class is never closed and never a class")

    def _s2_here(s, m):
        """The document's bytes: its delimiter, its newlines, and the machine's own environment."""
        _s2_bytes(s.here_document(m, "EOF\none two\nEOF\n", True), b"one two\n",
                  "a quoted here-document is literal")
        _s2_bytes(s.here_document(m, "EOF\none two\nEOF\n", False), b"one two\n",
                  "an unquoted here-document with no parameter")
        env = {}
        for entry in m.env():
            name, _, value = entry.partition("=")
            env[name] = value
        assert env, ("the machine seeds no environment: §4.2 gives a here-document no "
                     "variable table, so its parameters come from `machine.env()` and this "
                     "check needs one entry to prove that they do")
        name = sorted(env)[0]
        value = env[name]
        _s2_bytes(s.here_document(m, "EOF\n$%s\nEOF\n" % (name,), False),
                  (value + "\n").encode(),
                  "an unquoted here-document expands $%s from the machine's environment"
                  % (name,))
        _s2_bytes(s.here_document(m, "EOF\n$%s\nEOF\n" % (name,), True),
                  ("$%s\n" % (name,)).encode(),
                  "a quoted here-document leaves $%s alone" % (name,))
        _s2_bytes(s.here_document(m, "EOF\n${%s:-fallback}\nEOF\n" % (S2_UNSET,), False),
                  b"fallback\n", "the word of a :- in a here-document")
        _s2_bytes(s.here_document(m, "EOF\na b $%s c\nEOF\n" % (S2_UNSET,), False),
                  b"a b  c\n", "a here-document is bytes, not words")
        _s2_bytes(s.here_document(m, "EOF\n~\nEOF\n", False), b"~\n",
                  "the tilde phase is not a here-document's business")
        _s2_bytes(s.here_document(m, "EOF\n$\nEOF\n", False), b"$\n",
                  "a `$` that starts nothing stands in a here-document too")
        _s2_bytes(s.here_document(m, "'EO F'\nx\nEO F\n", True), b"x\n",
                  "the delimiter's quotes are removed before it is compared")
        _s2_bytes(s.here_document(m, "\\EOF\nx\nEOF\n", True), b"x\n",
                  "an escaped delimiter is the same delimiter")
        _s2_bytes(s.here_document(m, "EOF\nx\nEOF y\nEOF\n", False), b"x\nEOF y\n",
                  "only a line that is exactly the delimiter ends the document")
        _s2_bytes(s.here_document(m, "EOF\nEOF\n", False), b"",
                  "an empty document")
        _s2_bytes(s.here_document(m, "EOF\na\nb\nEOF\n", False), b"a\nb\n",
                  "every line keeps its newline")
        _s2_bytes(s.here_document(m, "EOF\nx\nEOF", False), b"x\n",
                  "the last line need not end with a newline")
        _s2_bytes(s.here_document(m, "EOF\n$%s\nEOF j\nEOF\n" % (S2_UNSET,), False),
                  b"\nEOF j\n", "a line that only starts with the delimiter is not the delimiter")
        for what, body, offset in (
                ("a document that never ends", "EOF\nx\n", 6),
                ("a document whose delimiter is quoted and never repeated", "'EOF'\nx\n", 8)):
            got = s.here_document(m, body, False)
            assert isinstance(got, dict) and tuple(got) == ("bytes", "error"), (
                "the here-document %s answered %r" % (what, got))
            assert got["bytes"] is None, (
                "the here-document %s answered the bytes %r, and a failed document answers "
                "none" % (what, got["bytes"]))
            _s2_error(got["error"], "here-document-unterminated", offset, what)
        got = s.here_document(m, "EOF\n${X\nEOF\n", False)
        assert got["bytes"] is None, (
            "a here-document with a bad substitution answered the bytes %r" % (got["bytes"],))
        _s2_error(got["error"], "bad-substitution", 4,
                  "a here-document whose document holds a bad substitution")

    def _s2_nounset(s, m):
        """The one option this stage reads, and the two forms that carry their own word."""
        unset = S2_UNSET
        on = _s2_state({}, nounset=True)
        off = {"variables": dict(S2_VARS), "flags": {}}
        _s2_failed(s.expand(m, "$" + unset, on), "unset-variable", 0, "$<unset> under nounset")
        _s2_failed(s.expand(m, "a ${" + unset + "}", on), "unset-variable", 2,
                   "${<unset>} after a byte that is fine")
        for form in ("${%s}", "${#%s}", "${%s#x}", "${%s%%x}"):
            _s2_failed(s.expand(m, form % (unset,), on), "unset-variable", 0,
                       "%s under nounset" % (form % ("<unset>",),))
        got = s.substitute(m, "a $" + unset, on)
        assert tuple(got) == ("text", "error") and got["text"] is None, (
            "substitute answered %r, and a failed substitution answers no text" % (got,))
        _s2_error(got["error"], "unset-variable", 2, "substitute under nounset")
        for form in ("${%s:-d}", "${%s:+d}"):
            expected = "d" if form.endswith(":-d}") else ""
            _s2_expansion(s.expand(m, form % (unset,), on), expected,
                          ("d",) if expected else (), "%s carries its own word" % (form,))
        _s2_expansion(s.expand(m, "${EMPTY}", on), "", (), "${EMPTY}, set and empty")
        _s2_expansion(s.expand(m, "${#EMPTY}", on), "0", ("0",), "${#EMPTY}")
        _s2_expansion(s.expand(m, "${EMPTY:-d}", on), "d", ("d",),
                      "${EMPTY:-d}: :- counts an empty value as nothing")
        _s2_expansion(s.expand(m, "${EMPTY:+d}", on), "", (), "${EMPTY:+d}")
        _s2_expansion(s.expand(m, "$" + unset, off), "", (), "$<unset> with nounset off")
        _s2_expansion(s.expand(m, "$" + unset, dict(S2_VARS)), "", (),
                      "$<unset> through the bare table, which has no flags on")
        _s2_expansion(s.expand(m, "${#%s}" % (unset,), {"variables": {}, "flags": {}}),
                      "0", ("0",), "${#<unset>} with no flags")
        _s2_expansion(s.expand(m, "$" + unset,
                               {"variables": dict(S2_VARS), "flags": {"errexit": True}}),
                      "", (), "an option the flags do not mention is off")

    def _s2_refusals(s, m, machine):
        """A caller's mistake raises `machine.MachineError` naming the offender."""
        good = {"variables": dict(S2_VARS), "flags": {"nounset": False}}
        _refuses(machine.MachineError, "a text that is not a string",
                 lambda: s.expand(m, 5, good), names=("5",))
        _refuses(machine.MachineError, "a text that is not a string, from substitute",
                 lambda: s.substitute(m, b"x", good), names=("b'x'",))
        _refuses(machine.MachineError, "a table that is not a mapping",
                 lambda: s.expand(m, "$BOTH", ["BOTH"]), names=("['BOTH']",))
        _refuses(machine.MachineError, "a state whose own variables are not a mapping",
                 lambda: s.expand(m, "$BOTH", {"variables": "BOTH", "flags": {}}),
                 names=("variables",))
        _refuses(machine.MachineError, "a state with no flags",
                 lambda: s.expand(m, "$BOTH", {"variables": {"BOTH": "bee"}}),
                 names=("flags",))
        _refuses(machine.MachineError, "flags that are not a mapping",
                 lambda: s.expand(m, "$BOTH", {"variables": {}, "flags": 1}),
                 names=("1",))
        _refuses(machine.MachineError, "a variable whose value is not a string",
                 lambda: s.expand(m, "$BOTH", {"BOTH": 5}), names=("5",))
        _refuses(machine.MachineError, "a variable name that is not a string",
                 lambda: s.expand(m, "$BOTH", {5: "bee"}), names=("5",))
        _refuses(machine.MachineError, "an option that is not a bool",
                 lambda: s.expand(m, "$BOTH", {"variables": {}, "flags": {"nounset": 1}}),
                 names=("1",))
        _refuses(machine.MachineError, "a pattern that is not a string",
                 lambda: s.glob(m, 5), names=("5",))
        _refuses(machine.MachineError, "a pattern that is not a string, and not even a number",
                 lambda: s.glob(m, None), names=("None",))
        _refuses(machine.MachineError, "a body that is not a string",
                 lambda: s.here_document(m, 5, False), names=("5",))
        _refuses(machine.MachineError, "quoted that is not a bool",
                 lambda: s.here_document(m, "EOF\nEOF\n", None), names=("None",))

    def _s2_doors(s, m):
        """A whole pass of the surface moves no door, writes no path and touches no state."""
        before = dict(m.stats())
        paths = tuple(m.files())
        environment = tuple(m.env())
        state = _s2_state({"PAT": _s2_pattern_of(m)}, nounset=True)
        table = dict(state["variables"])
        flags = dict(state["flags"])
        for door in S2_DOORS:
            assert door in before, (
                "the machine's stats hold no %r: %r" % (door, tuple(sorted(before))))
        one = tuple(s.expand(m, "$PAT $BOTH ~", state)["words"])
        s.expand_word(m, "$SPACE", state)
        s.substitute(m, "${#NAME}", state)
        s.glob(m, _s2_pattern_of(m))
        s.glob(m, "/[never")
        s.here_document(m, "EOF\none\nEOF\n", False)
        s.here_document(m, "EOF\n", True)
        two = tuple(s.expand(m, "$PAT $BOTH ~", state)["words"])
        after = dict(m.stats())
        for door in S2_DOORS:
            assert before[door] == after[door], (
                "the door %r was counted %d times before an expansion and %d times after: "
                "expansion reads the machine and answers, and opens nothing"
                % (door, before[door], after[door]))
        assert tuple(m.files()) == paths, "an expansion wrote the machine's filesystem"
        plain = _s2_pattern_of(m).rpartition("/")[0]
        plain_door = dict(m.stats())["files"]
        s.glob(m, plain)
        assert dict(m.stats())["files"] == plain_door, (
            "a glob of the plain path %r asked the machine for its population, and a "
            "pattern with no metacharacter answers itself without asking" % (plain,))
        assert tuple(m.env()) == environment, "an expansion wrote the machine's environment"
        assert state["variables"] == table and state["flags"] == flags, (
            "an expansion wrote the shell's own state: %r" % (state,))
        assert one == two, (
            "two runs of one workload answered %r and %r, so an expansion is not a function "
            "of its inputs" % (one, two))
        assert one, "the workload expanded to no words at all, so it proves nothing"

    """Every assertion the contract's §4.2 makes about this stage."""
    import machine
    import rules
    import stage_02 as s
    m = machine.machine(7)
    _s2_constants(s, rules)
    _s2_grammar(s, m)
    _s2_order(s, m)
    _s2_quoting(s, m)
    _s2_tilde(s, m)
    _s2_split(s, m)
    _s2_glob(s, m)
    _s2_here(s, m)
    _s2_nounset(s, m)
    _s2_refusals(s, m, machine)
    _s2_doors(s, m)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    S3_PLAN_KEYS = ("commands", "pipes", "redirects", "steps", "error")

    S3_PLAN_ERRORS = ("bad-fd", "not-a-file", "ambiguous-redirect", "unknown-program",
                      "empty-pipeline")

    S3_COMMAND_KEYS = ("argv", "program", "fds", "redirects")

    S3_REDIRECT_KEYS = ("kind", "fd", "target", "append")

    S3_FD_KEYS = ("kind", "target", "append")

    S3_PIPE_KEYS = ("read", "write", "bytes")

    S3_ERROR_KEYS = ("kind", "target", "detail")

    S3_DOORS = ("spawn", "fork", "exec", "wait", "open", "dup2", "close", "read",
                "write", "signal")

    S3_TERMINAL = {"kind": "terminal", "target": "terminal", "append": False}

    def _repo(start=None):
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("machine.py", "course.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked against
        the message: an exception of the right family raised for the wrong reason is not
        the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _command(words, redirects=(), assignment=None, background=False):
        """One `COMMAND_KEYS` record as §4.1 pins it, from the check's own words."""
        return {"words": tuple(words), "redirects": tuple(redirects),
                "assignment": assignment, "background": background}

    def _redirect(kind, number, target, quoted=False):
        """One redirection record as §4.1 pins it, from the check's own numbers."""
        return {"kind": kind, "fd": number, "target": target, "quoted": quoted}

    def _fds(answer, index):
        """One command's descriptor table out of a plan the check asked for."""
        return answer["commands"][index]["fds"]

    def _applied(answer, index):
        """One command's applied redirections, as `(kind, fd, target, append)` rows."""
        return tuple((row["kind"], row["fd"], row["target"], row["append"])
                     for row in answer["commands"][index]["redirects"])

    def _leaving(answer):
        """Every redirection the plan applied, as `(command, kind, fd, target, append)`."""
        return tuple((row["command"], row["kind"], row["fd"], row["target"], row["append"])
                     for row in answer["redirects"])

    def _fresh(world, files=()):
        """A fresh machine holding the check's own files, and nothing else of it."""
        machine = world.machine(7)
        for path, data in files:
            machine.store(path, data)
        return machine

    def _shape(answer, where):
        """The keys a plan record carries, exactly the ones §4.0 pins and no others."""
        assert tuple(answer) == S3_PLAN_KEYS, (
            "%s answered the keys %r, not %r" % (where, tuple(answer), S3_PLAN_KEYS))
        for index, row in enumerate(answer["commands"]):
            assert tuple(row) == S3_COMMAND_KEYS, (
                "%s answered command %d with the keys %r, not %r"
                % (where, index, tuple(row), S3_COMMAND_KEYS))
            for row_record in row["redirects"]:
                assert tuple(row_record) == S3_REDIRECT_KEYS, (
                    "%s answered the redirect %r, not %r"
                    % (where, tuple(row_record), S3_REDIRECT_KEYS))
            for value in row["fds"].values():
                assert tuple(value) == S3_FD_KEYS, (
                    "%s answered the descriptor %r, not %r"
                    % (where, tuple(value), S3_FD_KEYS))
        for pipe in answer["pipes"]:
            assert tuple(pipe) == S3_PIPE_KEYS, (
                "%s answered the pipe %r, not %r" % (where, tuple(pipe), S3_PIPE_KEYS))
        for record in answer["redirects"]:
            assert tuple(record) == S3_REDIRECT_KEYS + ("command",), (
                "%s answered the applied redirection %r, not %r"
                % (where, tuple(record), S3_REDIRECT_KEYS + ("command",)))
        assert answer["error"] is None, "%s answered the refusal %r" % (where, answer["error"])
        return answer

    def _refusal(answer, kind, target, where):
        """A refusal record of the right kind, naming the offender, with an empty plan."""
        record = answer["error"]
        assert tuple(answer) == S3_PLAN_KEYS, (
            "%s refused with the keys %r, not %r" % (where, tuple(answer), S3_PLAN_KEYS))
        assert record is not None, "%s answered no refusal at all" % (where,)
        assert tuple(record) == S3_ERROR_KEYS, (
            "%s refused with the keys %r, not %r" % (where, tuple(record), S3_ERROR_KEYS))
        assert record["kind"] == kind, (
            "%s refused with %r, not %r" % (where, record["kind"], kind))
        assert record["target"] == target, (
            "%s refused %r, not the offender %r" % (where, record["target"], target))
        assert isinstance(record["detail"], str) and record["detail"], (
            "%s refused without a sentence naming what was expected: %r"
            % (where, record["detail"]))
        assert answer["commands"] == () and answer["pipes"] == (), (
            "%s refused but answered a table or a pipe: %r" % (where, answer))
        assert answer["redirects"] == () and answer["steps"] == 0, (
            "%s refused but answered a record or a cost: %r" % (where, answer))
        assert kind in S3_PLAN_ERRORS, "%r is not a PLAN_ERRORS kind" % (kind,)
        return record

    def _expanded_by_stage_02(machine, text, variables):
        """§4.2's own answer for a word, so a fixture that stopped landing on a boundary
        is an error and not a quietly weaker test."""
        import stage_02
        return stage_02.expand(machine, text, variables)

    def _s3_constants(s):
        """The two key tuples, in the order §4.0 pins them and member by member."""
        for name in ("PLAN_KEYS", "PLAN_ERRORS"):
            value = getattr(s, name)
            assert isinstance(value, tuple), "%s is %r, not a tuple" % (name, value)
            assert all(isinstance(member, str) for member in value), (name, value)
            assert len(set(value)) == len(value), "%s repeats a member: %r" % (name, value)
        assert s.PLAN_KEYS == S3_PLAN_KEYS, s.PLAN_KEYS
        assert s.PLAN_ERRORS == S3_PLAN_ERRORS, s.PLAN_ERRORS

    def _s3_counts(s, world, programs):
        """One, two and three commands: N rows, N - 1 pipes, and the ends that join them."""
        machine = _fresh(world)
        for names in (("cat",), ("cat", "wc"), ("cat", "sort", "head")):
            where = "a pipeline of %d command(s)" % (len(names),)
            before = machine.stats()
            pipeline = tuple(_command((name,)) for name in names)
            answer = _shape(s.plan(machine, pipeline, {}), where)
            after = machine.stats()
            assert len(answer["commands"]) == len(names), where
            assert len(answer["pipes"]) == len(names) - 1, (
                "%s made %d pipes, and N - 1 is %d" % (where, len(answer["pipes"]), len(names) - 1))
            assert after["pipe"] == before["pipe"] + len(names) - 1, (
                "%s moved the machine's pipe door by %d"
                % (where, after["pipe"] - before["pipe"]))
            ends = []
            for pipe in answer["pipes"]:
                for end in ("read", "write"):
                    assert isinstance(pipe[end], int) and not isinstance(pipe[end], bool), (
                        "%s answered %r for a pipe's %s" % (where, pipe[end], end))
                assert pipe["read"] != pipe["write"], where
                assert isinstance(pipe["bytes"], int) and pipe["bytes"] >= 0, where
                ends.extend((pipe["read"], pipe["write"]))
            assert len(set(ends)) == len(ends), "%s shares an end between two pipes" % (where,)
            for place, row in enumerate(answer["commands"]):
                assert tuple(sorted(row["fds"])) == (0, 1, 2), (
                    "%s gave command %d the descriptors %r" % (where, place, tuple(sorted(row["fds"]))))
                assert row["program"] == names[place], where
                assert row["argv"] == (names[place],), (
                    "%s gave command %d the argv %r" % (where, place, row["argv"]))
                assert row["fds"][0] == (S3_TERMINAL if not place else
                                         {"kind": "pipe",
                                          "target": answer["pipes"][place - 1]["read"],
                                          "append": False}), (where, place)
                assert row["fds"][1] == (S3_TERMINAL if place == len(names) - 1 else
                                         {"kind": "pipe",
                                          "target": answer["pipes"][place]["write"],
                                          "append": False}), (where, place)
                assert row["fds"][2] == S3_TERMINAL, (where, place)
                assert row["redirects"] == (), (where, place)
            assert answer["steps"] == sum(programs.program(name)["steps"] for name in names), (
                "%s cost %r steps, and the world's programs cost %r"
                % (where, answer["steps"],
                   sum(programs.program(name)["steps"] for name in names)))
        # The bytes a pipe carries, from the check's own numbers: `echo x` writes two.
        answer = _shape(s.plan(machine, (_command(("echo", "x")), _command(("cat",)),
                                         _command(("wc", "-l"))), {}), "echo x | cat | wc -l")
        assert len(answer["pipes"]) == 2
        assert answer["pipes"][0]["bytes"] == len("x\n"), answer["pipes"][0]
        assert answer["pipes"][1]["bytes"] == len("x\n"), answer["pipes"][1]
        assert answer["steps"] == sum(programs.program(name)["steps"]
                                     for name in ("echo", "cat", "wc"))
        # A pipeline of readers over the shell's own terminal carries nothing.
        answer = _shape(s.plan(machine, (_command(("cat",)), _command(("wc", "-l"))), {}),
                        "cat | wc -l")
        assert answer["pipes"][0]["bytes"] == 0, answer["pipes"][0]

    def _s3_orders(s, world):
        """The two readings of one redirection pair, both tables asserted whole."""
        machine = _fresh(world)
        file_f = {"kind": "file", "target": "f", "append": False}
        joined = _shape(s.plan(machine, (_command(("echo", "x"),
                                                  (_redirect(">", 1, "f"),
                                                   _redirect("2>&1", 2, "1"))),), {}),
                        "echo x >f 2>&1")
        apart = _shape(s.plan(machine, (_command(("echo", "x"),
                                                 (_redirect("2>&1", 2, "1"),
                                                  _redirect(">", 1, "f"))),), {}),
                       "echo x 2>&1 >f")
        assert _fds(joined, 0) == {0: S3_TERMINAL, 1: file_f, 2: file_f}, _fds(joined, 0)
        assert _fds(apart, 0) == {0: S3_TERMINAL, 1: file_f, 2: S3_TERMINAL}, _fds(apart, 0)
        assert _fds(joined, 0) != _fds(apart, 0), (
            "`>f 2>&1` and `2>&1 >f` answered the same descriptor table")
        assert _applied(joined, 0) == ((">", 1, "f", False), ("2>&1", 2, 1, False))
        assert _applied(apart, 0) == (("2>&1", 2, 1, False), (">", 1, "f", False))
        assert joined["redirects"] != apart["redirects"], (
            "the plan did not record the order it applied the redirections in")
        assert _leaving(joined) == ((0, ">", 1, "f", False), (0, "2>&1", 2, 1, False))
        # A third redirection must not disturb the copy: the table is resolved, not shared.
        third = _shape(s.plan(machine, (_command(("echo", "x"),
                                                 (_redirect(">", 1, "f"),
                                                  _redirect("2>&1", 2, "1"),
                                                  _redirect(">", 1, "g"))),), {}),
                       "echo x >f 2>&1 >g")
        assert _fds(third, 0) == {0: S3_TERMINAL,
                                  1: {"kind": "file", "target": "g", "append": False},
                                  2: file_f}, _fds(third, 0)
        # The pipeline's ends are installed before the command's own redirections.
        piped = _shape(s.plan(machine, (_command(("echo", "x"),
                                                 (_redirect("2>&1", 2, "1"),
                                                  _redirect(">", 1, "f"))),
                                         _command(("cat",))), {}), "echo x 2>&1 >f | cat")
        assert _fds(piped, 0)[2] == {"kind": "pipe", "target": piped["pipes"][0]["write"],
                                     "append": False}, _fds(piped, 0)
        assert _fds(piped, 0)[2] != S3_TERMINAL, (
            "a command in a pipeline copied the shell's terminal into fd 2 instead of "
            "the pipe")

    def _s3_numbers(s, world):
        """Every redirection's number and the file it names, including the defaults."""
        machine = _fresh(world, (("/in", b"data"),))
        answer = _shape(s.plan(machine, (_command(("cat",), (_redirect(">", 3, "out"),
                                                            _redirect(">>", 1, "log"),
                                                            _redirect("<", 0, "/in"))),), {}),
                        "3>out >>log <in")
        assert tuple(sorted(_fds(answer, 0))) == (0, 1, 2, 3), tuple(sorted(_fds(answer, 0)))
        assert _fds(answer, 0)[3] == {"kind": "file", "target": "out", "append": False}
        assert _fds(answer, 0)[1] == {"kind": "file", "target": "log", "append": True}
        assert _fds(answer, 0)[0] == {"kind": "file", "target": "/in", "append": False}
        assert _fds(answer, 0)[2] == S3_TERMINAL, "a redirect to fd 3 moved fd 2"
        assert _applied(answer, 0) == ((">", 3, "out", False), (">>", 1, "log", True),
                                       ("<", 0, "/in", False))
        # The numbers a record leaves out are the ones the kind implies.
        two = _shape(s.plan(machine, (_command(("cat",), (_redirect("2>", None, "err"),)),), {}),
                     "2>err with no number")
        assert _fds(two, 0)[2] == {"kind": "file", "target": "err", "append": False}
        assert _fds(two, 0)[1] == S3_TERMINAL
        assert _applied(two, 0) == (("2>", 2, "err", False),)
        plain = _shape(s.plan(machine, (_command(("cat",), (_redirect(">", None, "written"),
                                                          _redirect("<", None, "/in"))),), {}),
                       "a > and a < with no numbers")
        assert _fds(plain, 0)[1] == {"kind": "file", "target": "written", "append": False}
        assert _fds(plain, 0)[0] == {"kind": "file", "target": "/in", "append": False}
        # The argv is the expansion §4.2 answers, word for word.
        record = _expanded_by_stage_02(machine, "$F", {"F": "a b"})
        assert len(record["words"]) == 2, (
            "the split fixture no longer lands on the boundary: §4.2 answered %r" % (record,))
        words = _shape(s.plan(machine, (_command(("echo", "$F")),), {"F": "a b"}),
                       "echo $F with F split in two")
        assert words["commands"][0]["argv"] == ("echo", "a", "b"), words["commands"][0]["argv"]
        quoted = _shape(s.plan(machine, (_command(("echo", "'$F'")),), {"F": "a b"}),
                        "echo '$F'")
        assert quoted["commands"][0]["argv"] == ("echo", "$F"), (
            "a single-quoted word was expanded: %r" % (quoted["commands"][0]["argv"],))
        held = _shape(s.plan(machine, (_command(("echo", '"$F"')),), {"F": "a b"}),
                      'echo "$F"')
        assert held["commands"][0]["argv"] == ("echo", "a b"), (
            "a double-quoted word was split: %r" % (held["commands"][0]["argv"],))
        # A leading word that is the command's own assignment is not part of the argv.
        assigned = _shape(s.plan(machine, (_command(("X=1", "env"), assignment="X=1"),), {}),
                          "X=1 env")
        assert assigned["commands"][0]["argv"] == ("env",), (
            "a leading assignment word was run as the program: %r"
            % (assigned["commands"][0]["argv"],))
        assert assigned["commands"][0]["program"] == "env", assigned["commands"][0]
        after = _shape(s.plan(machine, (_command(("X=1", "env"), assignment="Y=2"),), {}),
                       "Y=2 X=1 env")
        assert after["commands"][0]["argv"] == ("env",), (
            "a word that is not the command's own assignment was not dropped: %r"
            % (after["commands"][0]["argv"],))

    def _s3_here(s, world):
        """A here-document is the machine's file, and the plan answers where it put it."""
        machine = _fresh(world)
        body = "one\ntwo\n"
        answer = _shape(s.plan(machine, (_command(("cat",), (_redirect("<<", 0, body),)),), {}),
                        "cat <<DELIM")
        path = _fds(answer, 0)[0]["target"]
        assert _fds(answer, 0)[0] == {"kind": "file", "target": path, "append": False}, path
        assert isinstance(path, str) and path, path
        assert machine.exists(path), (
            "the plan answered the here-document %r, which the machine does not hold" % (path,))
        assert machine.load(path) == body.encode(), machine.load(path)
        assert _applied(answer, 0) == (("<<", 0, path, False),)
        assert _leaving(answer) == ((0, "<<", 0, path, False),)
        again = _shape(s.plan(machine, (_command(("cat",), (_redirect("<<", 0, body),)),), {}),
                       "cat <<DELIM again")
        assert _fds(again, 0)[0]["target"] == path, (
            "two plans of one here-document answered two paths: %r and %r"
            % (path, _fds(again, 0)[0]["target"]))
        # Two here-documents in one pipeline are two files, each holding its own body.
        both = _shape(s.plan(machine, (_command(("cat",), (_redirect("<<", 0, "first\n"),)),
                                       _command(("cat",),
                                                (_redirect("<<", 0, "second\n"),))), {}),
                      "two here-documents in one pipeline")
        first = _fds(both, 0)[0]["target"]
        second = _fds(both, 1)[0]["target"]
        assert first != second, (
            "two here-documents in one pipeline share the file %r" % (first,))
        assert machine.load(first) == b"first\n", machine.load(first)
        assert machine.load(second) == b"second\n", machine.load(second)

    def _s3_cost(s, world, programs):
        """The cost is the world's own steps, summed, and the ledger does not move."""
        machine = _fresh(world)
        assert s.cost_of(machine, ()) == 0, "a pipeline of no programs costs nothing"
        for name in programs.PROGRAM_NAMES:
            assert s.cost_of(machine, (name,)) == programs.program(name)["steps"], (
                "%r cost %r steps, and the world's own program costs %r"
                % (name, s.cost_of(machine, (name,)), programs.program(name)["steps"]))
        names = ("echo", "cat", "wc")
        assert s.cost_of(machine, list(names)) == sum(programs.program(name)["steps"]
                                                      for name in names)
        assert s.cost_of(machine, ("sort", "head")) == (programs.program("sort")["steps"]
                                                        + programs.program("head")["steps"])
        before = machine.stats()
        plan_steps = s.plan(machine, (_command(("echo", "x")), _command(("cat",)),
                                     _command(("wc", "-l"))), {})["steps"]
        after = machine.stats()
        assert plan_steps == sum(programs.program(name)["steps"] for name in names), plan_steps
        for door in S3_DOORS:
            assert after[door] == before[door], (
                "planning a pipeline moved the machine's %r: %r became %r"
                % (door, before[door], after[door]))
        assert after["pipe"] == before["pipe"] + 2, after["pipe"] - before["pipe"]

    def _s3_ledger(s, world):
        """What a plan asks the machine for, and what a refused plan does not."""
        machine = _fresh(world, (("/in", b"data"), ("/dir/x", b"")))
        files = machine.files()
        processes = machine.processes()
        before = machine.stats()
        answer = _shape(s.plan(machine, (_command(("echo", "x"), (_redirect(">", 1, "out"),)),
                                         _command(("cat",), (_redirect("<", 0, "/in"),)),
                                         _command(("wc", "-l"))), {}), "a pipeline of three")
        after = machine.stats()
        assert after["pipe"] == before["pipe"] + 2, after["pipe"] - before["pipe"]
        for door in S3_DOORS:
            assert after[door] == before[door], (
                "a plan moved the machine's %r: %r became %r"
                % (door, before[door], after[door]))
        assert machine.processes() == processes, "a plan spawned a process"
        assert machine.reapable() == (), "a plan left something reapable"
        assert machine.files() == files, (
            "a plan that redirected to a new file made one: %r became %r"
            % (files, machine.files()))
        # A refused plan asks for no pipe and writes no file, here-documents included.
        before = machine.stats()
        files = machine.files()
        refused = s.plan(machine, (_command(("cat",), (_redirect("<<", 0, "body\n"),)),
                                   _command(("nope",))), {})
        _refusal(refused, "unknown-program", "nope", "a here-document before an unknown program")
        for door in S3_DOORS + ("pipe",):
            assert machine.stats()[door] == before[door], (
                "a refused plan spent the machine's %r door" % (door,))
        assert machine.files() == files, (
            "a refused plan wrote a file: %r became %r" % (files, machine.files()))

    def _s3_twice(s, world):
        """Two plans of one fixture answer the same bytes, argv and cost."""
        machine = _fresh(world, (("/in", b"data"),))
        fixture = (_command(("echo", "x"), (_redirect(">", 1, "out"),
                                            _redirect("2>&1", 2, "1"))),
                   _command(("cat",), (_redirect("<", 0, "/in"),)),
                   _command(("sort",)))
        one = _shape(s.plan(machine, fixture, {"X": "y"}), "the first run of one fixture")
        two = _shape(s.plan(machine, fixture, {"X": "y"}), "the second run of one fixture")
        assert [row["argv"] for row in one["commands"]] == \
               [row["argv"] for row in two["commands"]]
        assert [tuple(sorted(row["fds"])) for row in one["commands"]] == \
               [tuple(sorted(row["fds"])) for row in two["commands"]]
        assert [_applied(one, index) for index in range(3)] == \
               [_applied(two, index) for index in range(3)]
        assert [pipe["bytes"] for pipe in one["pipes"]] == \
               [pipe["bytes"] for pipe in two["pipes"]]
        assert one["steps"] == two["steps"] and one["redirects"] == two["redirects"]
        assert machine.reapable() == (), "a plan of this stage left a process to reap"

    def _untouched(machine, before, files, what):
        """The doors and the files a caller's mistake or a refusal must leave alone."""
        for door in S3_DOORS + ("pipe",):
            assert machine.stats()[door] == before[door], (
                "%s spent the machine's %r door: %r became %r"
                % (what, door, before[door], machine.stats()[door]))
        assert machine.files() == files, (
            "%s wrote a file: %r became %r" % (what, files, machine.files()))

    def _s3_refusals(s, world):
        """Every refusal `PLAN_ERRORS` names: returned, naming the offender, spending nothing."""
        machine = _fresh(world, (("/in", b"data"), ("/dir/x", b"")))
        unset = _expanded_by_stage_02(machine, "$S3_UNSET", {})
        assert unset["words"] == (), (
            "the unset-variable fixture no longer lands on the boundary: §4.2 answered %r"
            % (unset,))
        split = _expanded_by_stage_02(machine, "$S3_SPLIT", {"S3_SPLIT": "a b"})
        assert len(split["words"]) == 2, (
            "the split fixture no longer lands on the boundary: §4.2 answered %r"
            % (split,))
        once = _command(("cat",))
        calls = (
            ("a redirection that writes a directory", "not-a-file", "/dir",
             lambda: s.plan(machine, (_command(("echo", "x"), (_redirect(">", 1, "/dir"),)),), {})),
            ("a redirection that appends to a directory", "not-a-file", "/dir",
             lambda: s.plan(machine, (_command(("echo", "x"), (_redirect(">>", 1, "/dir"),)),), {})),
            ("a redirection that writes a directory on fd 2", "not-a-file", "/dir",
             lambda: s.plan(machine, (_command(("echo", "x"), (_redirect("2>", 2, "/dir"),)),), {})),
            ("a redirection that reads a file the machine does not hold", "not-a-file",
             "/missing",
             lambda: s.plan(machine, (_command(("cat",), (_redirect("<", 0, "/missing"),)),), {})),
            ("a redirection that reads a directory", "not-a-file", "/dir",
             lambda: s.plan(machine, (_command(("cat",), (_redirect("<", 0, "/dir"),)),), {})),
            ("a target that expands to no word", "ambiguous-redirect", "$S3_UNSET",
             lambda: s.plan(machine, (_command(("echo", "x"),
                                               (_redirect(">", 1, "$S3_UNSET"),)),), {})),
            ("a target that expands to two words", "ambiguous-redirect", "$S3_SPLIT",
             lambda: s.plan(machine, (_command(("echo", "x"),
                                               (_redirect(">", 1, "$S3_SPLIT"),)),),
                            {"S3_SPLIT": "a b"})),
            ("a descriptor of minus one", "bad-fd", -1,
             lambda: s.plan(machine, (_command(("echo", "x"), (_redirect(">", -1, "f"),)),), {})),
            ("a descriptor that is not a number", "bad-fd", "2",
             lambda: s.plan(machine, (_command(("echo", "x"), (_redirect(">", "2", "f"),)),), {})),
            ("a descriptor past the end of the machine's table", "bad-fd", world.SCALE["fds"],
             lambda: s.plan(machine, (_command(("echo", "x"),
                                               (_redirect(">", world.SCALE["fds"], "f"),)),), {})),
            ("a descriptor that is a bool", "bad-fd", True,
             lambda: s.plan(machine, (_command(("echo", "x"), (_redirect(">", True, "f"),)),), {})),
            ("a program the machine does not hold", "unknown-program", "nope",
             lambda: s.plan(machine, (_command(("nope",)),), {})),
            ("a program the machine does not hold, after one it does", "unknown-program",
             "nope",
             lambda: s.plan(machine, (_command(("echo", "x"), (_redirect(">", 1, "out"),)),
                                      _command(("nope",))), {})),
            ("a pipeline of no commands", "empty-pipeline", None,
             lambda: s.plan(machine, (), {})),
            ("a command whose words expand to nothing", "empty-pipeline", 0,
             lambda: s.plan(machine, (_command(("$S3_UNSET",)),), {})),
            ("a command with no words at all", "empty-pipeline", 0,
             lambda: s.plan(machine, (_command(()),), {})),
            ("a target that expands to one empty word", "not-a-file", "",
             lambda: s.plan(machine, (_command(("echo", "x"),
                                               (_redirect(">", 1, "''"),)),), {})),
        )
        for what, kind, target, call in calls:
            before = machine.stats()
            files = machine.files()
            _refusal(call(), kind, target, what)
            _untouched(machine, before, files, what)
        # `redirects_of` answers the same refusal in its own three keys.
        answer = s.redirects_of(machine, _command(("echo", "x"), (_redirect(">", 1, "/dir"),)),
                                {})
        assert tuple(answer) == ("fds", "redirects", "error"), tuple(answer)
        record = answer["error"]
        assert record is not None and tuple(record) == S3_ERROR_KEYS, record
        assert record["kind"] == "not-a-file" and record["target"] == "/dir", record
        assert answer["fds"] == {} and answer["redirects"] == (), answer
        good = s.redirects_of(machine, _command(("cat",), (_redirect("<", 0, "/in"),)), {})
        assert tuple(good) == ("fds", "redirects", "error"), tuple(good)
        assert good["error"] is None, good
        assert good["fds"][0] == {"kind": "file", "target": "/in", "append": False}, good
        assert good["redirects"] == ({"kind": "<", "fd": 0, "target": "/in",
                                      "append": False},), good

    def _s3_shape(s, world):
        """Every shape that cannot be a pipeline, refused by name, asking nothing."""
        machine = _fresh(world, (("/in", b"data"),))
        refused = world.MachineError
        calls = (
            ("a pipeline that is a string", refused,
             lambda: s.plan(machine, "echo x", {}), ["echo x", "not a pipeline"]),
            ("a pipeline that is None", refused,
             lambda: s.plan(machine, None, {}), ["None", "not a pipeline"]),
            ("a pipeline that is a mapping", refused,
             lambda: s.plan(machine, {"words": ()}, {}), ["not a pipeline"]),
            ("a command that is a string", refused,
             lambda: s.plan(machine, ("cat",), {}), ["cat", "not a command record"]),
            ("a command that is a list", refused,
             lambda: s.plan(machine, ([],), {}), ["not a command record"]),
            ("words that are a string", refused,
             lambda: s.plan(machine, ({"words": "cat", "redirects": ()},), {}),
             ["cat", "not a sequence"]),
            ("words that are a number", refused,
             lambda: s.plan(machine, ({"words": 7, "redirects": ()},), {}),
             ["7", "not a sequence"]),
            ("a word that is not a string", refused,
             lambda: s.plan(machine, ({"words": (42,), "redirects": ()},), {}),
             ["42", "not a string"]),
            ("redirects that are a string", refused,
             lambda: s.plan(machine, ({"words": ("cat",), "redirects": ">f"},), {}),
             [">f", "not a sequence"]),
            ("a redirection that is not a record", refused,
             lambda: s.plan(machine, ({"words": ("cat",), "redirects": ("x",)},), {}),
             ["x", "not a record"]),
            ("a redirection this shell does not know", refused,
             lambda: s.plan(machine, (_command(("cat",), (_redirect("&>", 1, "f"),)),), {}),
             ["&>", "not a redirection"]),
            ("a target that is not a string", refused,
             lambda: s.plan(machine, (_command(("cat",), (_redirect(">", 1, 42),)),), {}),
             ["42", "not a string"]),
            ("a here-document whose body is not a string", refused,
             lambda: s.plan(machine, (_command(("cat",), (_redirect("<<", 0, 7),)),), {}),
             ["7", "not a string"]),
            ("a command for redirects_of that is not a record", refused,
             lambda: s.redirects_of(machine, None, {}), ["None", "not a command record"]),
            ("a command for redirects_of that is a string", refused,
             lambda: s.redirects_of(machine, "cat", {}), ["cat", "not a command record"]),
            ("a cost of a pipeline that is a string", refused,
             lambda: s.cost_of(machine, "cat"), ["cat", "not a list"]),
            ("a cost of a pipeline that is a number", refused,
             lambda: s.cost_of(machine, 7), ["7", "not a list"]),
            ("a cost of a name that is not a string", refused,
             lambda: s.cost_of(machine, (7,)), ["7", "not a string"]),
            ("a cost of a name the machine does not hold", refused,
             lambda: s.cost_of(machine, ("nope",)), ["nope", "not a program"]),
            ("a cost of a name the machine does not hold, in a pipeline", refused,
             lambda: s.cost_of(machine, ("cat", "nope")), ["nope", "not a program"]),
        )
        before = machine.stats()
        files = machine.files()
        for what, family, call, names in calls:
            _refuses(family, what, call, names)
        _untouched(machine, before, files, "a refused shape")

    """Every assertion the contract's §4.3 makes about this stage."""
    import machine as world
    import programs
    import stage_03 as s
    _s3_constants(s)
    _s3_shape(s, world)
    _s3_counts(s, world, programs)
    _s3_orders(s, world)
    _s3_numbers(s, world)
    _s3_here(s, world)
    _s3_cost(s, world, programs)
    _s3_refusals(s, world)
    _s3_ledger(s, world)
    _s3_twice(s, world)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    R4_RUN_KEYS = ("pids", "status", "waited", "deadlock")

    R4_STAGE_CALLS = ("spawn", "fork", "exec", "wait", "give", "open", "dup2", "close",
                      "exit", "exists", "is_dir", "modes")

    R4_PATH = "/stage4/plain"

    R4_APPEND_PATH = "/stage4/log"

    R4_SHARED_PATH = "/stage4/both"

    R4_READ_PATH = "/stage4/in"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("course.py", "machine.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named."""
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _terminal():
        """The descriptor table's default entry: the child's own standard number."""
        return {"kind": "terminal", "target": "terminal", "append": False}

    def _pipe(number, fd):
        return {"kind": "pipe", "target": fd, "append": False}

    def _to_file(path, append=False):
        return {"kind": "file", "target": path, "append": append}

    def _from_file(path):
        return {"kind": "file", "target": path, "append": False}

    def _row(program, argv=None, fds=None):
        """One command row, in the plan's own shape."""
        return {"argv": tuple(argv) if argv else (program,), "program": program,
                "fds": dict(fds) if fds else {0: _terminal(), 1: _terminal(),
                                              2: _terminal()},
                "redirects": ()}

    def _plan(commands, pipes=(), error=None):
        """A `PLAN_KEYS` record out of rows this check built itself."""
        steps = 0
        return {"commands": tuple(commands), "pipes": tuple(pipes), "redirects": (),
                "steps": steps, "error": error}

    def _pipeline(machine, names, argv=None):
        """A plan of `names`, wired with the machine's own pipes, in the given order."""
        ends = [machine.pipe() for _ in range(len(names) - 1)]
        rows = []
        for index, name in enumerate(names):
            fds = {0: _terminal(), 1: _terminal(), 2: _terminal()}
            if index:
                fds[0] = _pipe(0, ends[index - 1][0])
            if index < len(ends):
                fds[1] = _pipe(1, ends[index][1])
            words = argv[index] if argv else None
            rows.append(_row(name, words, fds))
        pipes = tuple({"read": pair[0], "write": pair[1], "bytes": 0}
                      for pair in ends)
        return _plan(rows, pipes)

    def _door(machine):
        """A snapshot of the machine's counters and its transcript's length."""
        return machine.stats(), len(machine.transcript())

    def _since(machine, snap):
        """`(stats delta, call counts)` since the snapshot, from the machine's record."""
        before, length = snap
        after = machine.stats()
        delta = dict((key, after[key] - before[key]) for key in after)
        calls = {}
        for record in machine.transcript()[length:]:
            calls[record["call"]] = calls.get(record["call"], 0) + 1
        return delta, _stage_calls(calls)

    def _stage_calls(calls):
        """Only the calls this stage's own surface is defined to make."""
        return dict((name, count) for name, count in calls.items()
                    if name in R4_STAGE_CALLS)

    def _s4_constants(s, w, rules):
        """`RUN_KEYS` and the two statuses, in the world's own numbers."""
        assert s.RUN_KEYS == R4_RUN_KEYS, (
            "RUN_KEYS is %r, not %r" % (s.RUN_KEYS, R4_RUN_KEYS))
        assert rules.EXIT_NOT_FOUND == 127 and rules.EXIT_CANNOT_EXECUTE == 126, (
            "the world's two kingdoms moved: 127 is %r and 126 is %r"
            % (rules.EXIT_NOT_FOUND, rules.EXIT_CANNOT_EXECUTE))
        record = _plan((_row("tick"),))
        assert tuple(record) == ("commands", "pipes", "redirects", "steps", "error"), (
            "this check's own plan record is %r" % (tuple(record),))

    def _s4_status(s, w, rules):
        """`pipeline_status` is the last command's, and only the last command's."""
        for statuses, want in (((), rules.EXIT_OK), ((0,), 0), ((1,), 1), ((0, 1), 1),
                               ((1, 0), 0), ((5, 5), 5), ((127, 0), 0), ((0, 127), 127),
                               ((3, 2, 1), 1)):
            got = s.pipeline_status(statuses)
            assert got == want, (
                "pipeline_status(%r) is %r, not %r — the pipeline's status is the last "
                "command's and nothing else" % (statuses, got, want))
        assert s.pipeline_status([1, 0]) == 0, (
            "a list of statuses is a sequence too, and its last is still the answer")
        _refuses(w.MachineError, "a status that is a string",
                 lambda: s.pipeline_status(("0",)), names=("statuses",))
        _refuses(w.MachineError, "a status that is None",
                 lambda: s.pipeline_status((0, None)), names=("statuses",))
        _refuses(w.MachineError, "statuses that are not a sequence",
                 lambda: s.pipeline_status(0), names=("statuses",))

    def _s4_pair(s, w, rules):
        """A real pipeline whose first member fails answers the last member's status."""
        m = w.machine(7)
        rec = s.run_pipeline(m, _pipeline(m, ("false", "tick")))
        assert tuple(rec) == R4_RUN_KEYS, (
            "the run record's keys are %r, not %r" % (tuple(rec), R4_RUN_KEYS))
        assert len(rec["pids"]) == 2, (
            "a pipeline of two commands spawned %d children" % (len(rec["pids"]),))
        assert rec["waited"] == (rules.EXIT_FAILURE, rules.EXIT_OK), (
            "the children of `false | tick` answered %r, and the check's own reading "
            "of the world says (1, 0) in pid order" % (rec["waited"],))
        assert rec["status"] == rules.EXIT_OK, (
            "`false | tick` answered %r — the pipeline's status is the *last* command's "
            "even when an earlier one failed" % (rec["status"],))
        assert rec["deadlock"] is False, "`false | tick` is not a deadlock"

        other = w.machine(7)
        rec2 = s.run_pipeline(other, _pipeline(other, ("tick", "false")))
        assert rec2["waited"] == (rules.EXIT_OK, rules.EXIT_FAILURE), (
            "the same two commands the other way round answered %r" % (rec2["waited"],))
        assert rec2["status"] == rules.EXIT_FAILURE, (
            "`tick | false` answered %r, so the stage is not reading the last status"
            % (rec2["status"],))

    def _s4_tree(s, w, rules):
        """Every child is reaped, the machine says so, and the bytes arrive."""
        m = w.machine(7)
        plan = _pipeline(m, ("echo", "cat"), argv=(("echo", "hi"), ("cat",)))
        before = len(m.terminal())
        snap = _door(m)
        rec = s.run_pipeline(m, plan)
        delta, calls = _since(m, snap)
        assert m.terminal()[before:] == b"hi\n", (
            "`echo hi | cat` left %r on the machine's terminal, not b'hi\\n'"
            % (m.terminal()[before:],))
        assert len(rec["pids"]) == 2 and rec["status"] == rules.EXIT_OK, (
            "`echo hi | cat` answered %r with %d children"
            % (rec["status"], len(rec["pids"])))
        assert m.reapable() == (), (
            "the run left %r unwaited in the machine's table — a pipeline that leaves a "
            "zombie is wrong even when its status is right" % (m.reapable(),))
        assert m.stats()["wait"] == len(rec["pids"]) == 2, (
            "the machine waited %d times for %d children"
            % (m.stats()["wait"], len(rec["pids"])))
        assert delta["spawn"] == 2, "the machine spawned %d times" % (delta["spawn"],)
        for pid in rec["pids"]:
            assert m.state(pid) == "waited", (
                "child %d is %r after the run, not waited" % (pid, m.state(pid)))
        assert calls.get("spawn") == 2 and calls.get("wait") == 2, (
            "the run's own calls were %r" % (calls,))
        assert calls.get("give") == 2, (
            "a two-command pipeline has two pipe ends to hand over, and the run made %r "
            "gives" % (calls.get("give"),))
        assert delta["open"] == 0 and delta["dup2"] == 0 and delta["close"] == 0, (
            "a pipeline of two pipes and no file moved an open/dup2/close: %r" % (delta,))

    def _s4_not_found(s, w, rules):
        """A program the machine does not hold is 127, in a pipeline or alone."""
        m = w.machine(7)
        plan = _pipeline(m, ("nosuchprog4", "cat"))
        snap = _door(m)
        rec = s.run_pipeline(m, plan)
        delta, calls = _since(m, snap)
        assert rec["waited"] == (rules.EXIT_NOT_FOUND, rules.EXIT_OK), (
            "`nosuchprog4 | cat` answered %r, and the failure the check's own arithmetic "
            "expects is (127, 0)" % (rec["waited"],))
        assert rec["status"] == rules.EXIT_OK, (
            "`nosuchprog4 | cat` answered %r — the last command's status is still the "
            "pipeline's" % (rec["status"],))
        assert rec["deadlock"] is False, (
            "a missing program is not a deadlock: its pipe end is given and closed, so "
            "the reader meets EOF")
        assert m.reapable() == (), (
            "a pipeline with a missing program left %r unwaited" % (m.reapable(),))
        assert delta["spawn"] == 2 and delta["wait"] == 2, (
            "the run moved spawn %d and wait %d" % (delta["spawn"], delta["wait"]))
        assert calls.get("exists") == 1 and calls.get("exit") == 1, (
            "resolving a program the machine does not hold should look once and kill "
            "once; the calls were %r" % (calls,))

        alone = w.machine(7)
        rec2 = s.run_pipeline(alone, _plan((_row("nosuchprog4"),)))
        assert rec2["waited"] == (rules.EXIT_NOT_FOUND,), (
            "one missing program answered %r" % (rec2["waited"],))
        assert rec2["status"] == rules.EXIT_NOT_FOUND, (
            "one missing program answered the status %r, not 127" % (rec2["status"],))
        assert alone.reapable() == () and len(rec2["pids"]) == 1, (
            "a missing program still has a pid, and it is still reaped")

    def _s4_cannot_execute(s, w, rules):
        """A file the machine holds but cannot execute is 126, never 127."""
        m = w.machine(7)
        m.store(R4_PATH, b"data")
        assert m.exists(R4_PATH) and not m.is_dir(R4_PATH), (
            "this check's own fixture %r is not a file" % (R4_PATH,))
        rec = s.run_pipeline(m, _plan((_row(R4_PATH, (R4_PATH,)),)))
        assert rec["waited"] == (rules.EXIT_CANNOT_EXECUTE,), (
            "the file %r answered %r, and 'found but not executable' is 126"
            % (R4_PATH, rec["waited"]))
        assert rec["status"] == rules.EXIT_CANNOT_EXECUTE, (
            "the file %r answered the status %r, not 126" % (R4_PATH, rec["status"]))
        assert m.reapable() == () and len(rec["pids"]) == 1, (
            "a file that cannot be executed still answers a pid, and it is reaped")

        m.store("/stage4/dir/child", b"x")
        rec2 = s.run_pipeline(m, _plan((_row("/stage4/dir", ("/stage4/dir",)),)))
        assert rec2["waited"] == (rules.EXIT_CANNOT_EXECUTE,), (
            "a directory answered %r, and a directory is found but not executable"
            % (rec2["waited"],))

    def _s4_signalled(s, w, rules):
        """A child sent TERM answers 128 + 15, and the machine's row says signalled."""
        m = w.machine(7)
        pid = s.spawn_command(m, _row("tick", ("tick", "100")))
        assert isinstance(pid, int) and not isinstance(pid, bool), (
            "spawn_command answered %r, not a pid" % (pid,))
        m.signal(pid, "TERM")
        result = m.wait(pid)
        want = rules.SIGNAL_STATUS_BASE + rules.SIGNAL_NUMBERS["TERM"]
        assert result["status"] == want, (
            "the signalled child answered %r, and 128 + 15 is %r"
            % (result["status"], want))
        assert result["signalled"] is True and result["signal"] == "TERM", (
            "the machine's own wait row is %r — a signalled child is signalled"
            % (result,))
        assert m.reapable() == (), (
            "the signalled child is still reapable: %r" % (m.reapable(),))

        other = w.machine(7)
        pid2 = s.spawn_command(other, _row("tick", ("tick", "100")))
        other.signal(pid2, "TERM")
        assert s.collect(other, (pid2,)) == (want,), (
            "collect answered %r for the child that was sent TERM, not the machine's own "
            "128 + 15" % (s.collect(other, (pid2,)),))

    def _s4_deadlock(s, w, rules, scripts):
        """A pipe nobody writes and nobody closes is a deadlock, and it is data."""
        m = w.machine(7)
        read_fd, write_fd = m.pipe()
        row = _row("cat", ("cat",), {0: _pipe(0, read_fd), 1: _terminal(),
                                     2: _terminal()})
        rec = s.run_pipeline(m, _plan((row,)))
        assert tuple(rec) == R4_RUN_KEYS, (
            "the deadlock's run record keys are %r" % (tuple(rec),))
        assert rec["deadlock"] is True, (
            "`cat` on a pipe with no writer is the deadlock the machine records, and the "
            "run reported %r" % (rec["deadlock"],))
        assert rec["status"] == rules.EXIT_FAILURE, (
            "a deadlocked pipeline answers %r, and the contract's reading is 1"
            % (rec["status"],))
        assert len(rec["pids"]) == 1, (
            "the deadlocked pipeline's children are its pids, and it spawned %d"
            % (len(rec["pids"]),))
        assert rec["waited"] == (), (
            "a deadlocked pipeline has nothing to answer for: waited is %r"
            % (rec["waited"],))
        assert len(m.deadlocks()) == 1, (
            "the machine recorded %d deadlocks, not the one this fixture made"
            % (len(m.deadlocks()),))
        assert m.reapable() == (), (
            "the deadlocked child is blocked, not reapable: %r" % (m.reapable(),))

        held = [name for name in scripts.names()
                if scripts.session(name)["expected"].get("deadlocks", 0) > 0]
        assert held, (
            "the world's own fixture sessions hold no deadlock for this stage to agree "
            "with: %r" % (scripts.names(),))

    def _s4_redirects(s, w, rules):
        """The plan's files: a read redirect reads, an append appends, a copy shares."""
        m = w.machine(7)
        m.store(R4_READ_PATH, b"one\ntwo\n")
        before = len(m.terminal())
        plan = _plan((_row("cat", ("cat",), {0: _from_file(R4_READ_PATH),
                                             1: _terminal(), 2: _terminal()}),))
        snap = _door(m)
        rec = s.run_pipeline(m, plan)
        delta, calls = _since(m, snap)
        assert m.terminal()[before:] == b"one\ntwo\n", (
            "`cat < %s` left %r on the terminal" % (R4_READ_PATH,
                                                    m.terminal()[before:]))
        assert rec["status"] == rules.EXIT_OK and rec["waited"] == (rules.EXIT_OK,), (
            "`cat < f` answered %r" % (rec,))
        assert calls.get("open") == 1, (
            "one read redirect is one open; the calls were %r" % (calls,))
        assert delta["open"] == 1, "the machine opened %d files" % (delta["open"],)
        assert calls.get("dup2") in (0, 1) and calls.get("close") == calls.get("dup2"), (
            "a redirected number is either the open's own number or moved onto it and "
            "released: the calls were %r" % (calls,))

        appended = w.machine(7)
        appended.store(R4_APPEND_PATH, b"first\n")
        s.run_pipeline(appended, _plan((_row("echo", ("echo", "second"),
            {0: _terminal(), 1: _to_file(R4_APPEND_PATH, True), 2: _terminal()}),)))
        assert appended.load(R4_APPEND_PATH) == b"first\nsecond\n", (
            "`echo second >> %s` left %r — an append redirect appends"
            % (R4_APPEND_PATH, appended.load(R4_APPEND_PATH)))

        shared = w.machine(7)
        snap = _door(shared)
        s.run_pipeline(shared, _plan((_row("echo", ("echo", "both"),
            {0: _terminal(), 1: _to_file(R4_SHARED_PATH), 2: _to_file(R4_SHARED_PATH)}),)))
        delta, calls = _since(shared, snap)
        assert shared.load(R4_SHARED_PATH) == b"both\n", (
            "`echo both > f` with fd 2 copied onto fd 1 left %r"
            % (shared.load(R4_SHARED_PATH),))
        assert calls.get("open") == 1, (
            "two numbers of one command that name the same file are one open, and the "
            "run made %r" % (calls.get("open"),))

    def _s4_plan_error(s, w, rules):
        """A plan that already carries an error spawns nothing and answers its worth."""
        m = w.machine(7)
        snap = _door(m)
        rec = s.run_pipeline(m, _plan((), error={"kind": "unknown-program",
                                                 "target": "nosuchprog4",
                                                 "detail": "no such program"}))
        delta, calls = _since(m, snap)
        assert rec == {"pids": (), "status": rules.EXIT_NOT_FOUND, "waited": (),
                       "deadlock": False}, (
            "an unknown program's plan answered %r, and a missing program is 127 with "
            "nothing spawned" % (rec,))
        assert delta["spawn"] == 0 and delta["wait"] == 0 and delta["pipe"] == 0, (
            "a plan that already failed still moved the machine: %r" % (delta,))
        assert calls == {}, (
            "a plan that already failed asked the machine for %r" % (calls,))
        for kind in ("bad-fd", "not-a-file", "ambiguous-redirect", "empty-pipeline"):
            other = s.run_pipeline(m, _plan((), error={"kind": kind, "target": None,
                                                       "detail": "the plan's own bad news"}))
            assert other["status"] == rules.EXIT_FAILURE, (
                "the plan error %r answered %r, not a plain failure"
                % (kind, other["status"]))
            assert other["pids"] == () and other["waited"] == () \
                and other["deadlock"] is False, (
                "the plan error %r answered %r" % (kind, other))

    def _s4_refusals(s, w, rules):
        """A caller's mistake raises and names the offender; nothing is asked of the machine."""
        m = w.machine(7)
        good = _plan((_row("tick"),))
        bad_rows = (
            ("a row that is not a record at all", 3, "row"),
            ("a row that is a record without its fields",
             {"argv": ("true",), "program": "true"}, "fds"),
            ("a row whose argv is missing",
             {"program": "true", "fds": {0: _terminal()}}, "argv"),
            ("a row whose argv is empty",
             {"argv": (), "program": "tick", "fds": {0: _terminal()}}, "argv"),
            ("a row whose argv holds a number",
             {"argv": ("true", 3), "program": "true", "fds": {0: _terminal()}},
             "word"),
            ("a row whose program is empty",
             {"argv": ("true",), "program": "", "fds": {0: _terminal()}}, "program"),
            ("a row whose fds is not a table",
             {"argv": ("true",), "program": "true", "fds": 3}, "fds"),
            ("a descriptor number that is a string",
             {"argv": ("true",), "program": "true", "fds": {"0": _terminal()}},
             "descriptor"),
            ("a descriptor number that is negative",
             {"argv": ("true",), "program": "true", "fds": {-1: _terminal()}},
             "descriptor"),
            ("a descriptor that is not a record",
             {"argv": ("true",), "program": "true", "fds": {0: 3}}, "descriptor"),
            ("a descriptor with no kind",
             {"argv": ("true",), "program": "true", "fds": {0: {}}}, "descriptor"),
        )
        snap = _door(m)
        _refuses(w.MachineError, "a plan that is not a record",
                 lambda: s.run_pipeline(m, None), names=("plan",))
        _refuses(w.MachineError, "a plan whose commands are not rows",
                 lambda: s.run_pipeline(m, {"commands": 3, "error": None}),
                 names=("commands",))
        for what, row, name in bad_rows:
            _refuses(w.MachineError, what,
                     lambda row=row: s.run_pipeline(
                         m, {"commands": (row,), "error": None}), names=(name,))
            _refuses(w.MachineError, what + " (spawned alone)",
                     lambda row=row: s.spawn_command(m, row), names=(name,))
        _refuses(w.MachineError, "pids that are not a tuple",
                 lambda: s.collect(m, 3), names=("pids",))
        _refuses(w.MachineError, "a pid that is a string",
                 lambda: s.collect(m, ("1",)), names=("pid",))
        _refuses(w.MachineError, "a pid that is a bool",
                 lambda: s.collect(m, (True,)), names=("pid",))
        _refuses(w.MachineError, "a pid that is negative",
                 lambda: s.collect(m, (-1,)), names=("pid",))
        delta, calls = _since(m, snap)
        assert calls == {}, (
            "the refusals still asked the machine for %r" % (calls,))
        assert delta["spawn"] == 0 and delta["wait"] == 0, (
            "a refused call moved the machine: %r" % (delta,))
        assert m.reapable() == (), "the refusals left something to reap"
        assert s.run_pipeline(m, good)["status"] == rules.EXIT_OK, (
            "the machine is still usable after the refusals")

    def _s4_twice(s, w, rules):
        """The same fixture twice answers the same record, pids included."""
        def once():
            m = w.machine(7)
            return s.run_pipeline(m, _pipeline(m, ("echo", "cat"),
                                               argv=(("echo", "hi"), ("cat",))))

        one, two = once(), once()
        assert one == two, (
            "two runs of one fixture answered %r and %r" % (one, two))
        assert one["pids"] == two["pids"], (
            "two runs of one fixture spawned different pids")

    """Every assertion the contract's §4.4 makes about this stage."""
    import machine
    import programs
    import rules
    import scripts
    import stage_04 as s
    assert "cat" in programs.PROGRAM_NAMES and "tick" in programs.PROGRAM_NAMES, (
        "this check's fixtures are built on the world's own programs, and %r is not "
        "the list it expected" % (programs.PROGRAM_NAMES,))
    _s4_constants(s, machine, rules)
    _s4_status(s, machine, rules)
    _s4_pair(s, machine, rules)
    _s4_tree(s, machine, rules)
    _s4_not_found(s, machine, rules)
    _s4_cannot_execute(s, machine, rules)
    _s4_signalled(s, machine, rules)
    _s4_deadlock(s, machine, rules, scripts)
    _s4_redirects(s, machine, rules)
    _s4_plan_error(s, machine, rules)
    _s4_refusals(s, machine, rules)
    _s4_twice(s, machine, rules)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    S5_JOB_KEYS = ("job", "pid", "state", "status", "command")

    S5_JOB_STATES = ("running", "stopped", "done")

    S5_STATUS_KEYS = ("pid", "status", "signalled", "signal")

    TERMINAL = "terminal"

    def _repo(start=None):
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "machine.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, with every `names` word in its message."""
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _row(*argv):
        """One command row of a plan, on the terminal's three standard fds."""
        return {"argv": tuple(argv),
                "program": argv[0],
                "fds": {0: {"kind": "terminal", "target": TERMINAL, "append": False},
                        1: {"kind": "terminal", "target": TERMINAL, "append": False},
                        2: {"kind": "terminal", "target": TERMINAL, "append": False}},
                "redirects": ()}

    def _plan(*commands):
        """A plan built here, so the stage's own `plan` is never needed."""
        return {"commands": tuple(_row(*command) for command in commands),
                "pipes": (), "redirects": (), "steps": 0, "error": None}

    def _job(job, pid, command="tick 5", state="running", status=None):
        """One row of the shell's own table."""
        return {"job": job, "pid": pid, "state": state,
                "status": status, "command": command}

    def _run_until(machine, pid, cap=1000):
        """Advance the machine until `pid` is no longer runnable."""
        for _ in range(cap):
            if machine.state(pid) != "running":
                return
            machine.advance(1)
        raise AssertionError("pid %r is still running after %d ticks" % (pid, cap))

    def _keys(row):
        """The exact field tuple of one answered row."""
        return tuple(row)

    def _s5_constants(s):
        """The two tuples, in the contract's order, and nothing else on the surface."""
        assert tuple(s.JOB_KEYS) == S5_JOB_KEYS, (
            "JOB_KEYS is %r, not %r" % (tuple(s.JOB_KEYS), S5_JOB_KEYS))
        assert tuple(s.JOB_STATES) == S5_JOB_STATES, (
            "JOB_STATES is %r, not %r" % (tuple(s.JOB_STATES), S5_JOB_STATES))
        for name in ("background", "stop", "resume", "jobs", "resolve", "wait_for"):
            assert callable(getattr(s, name, None)), "the surface has no %s" % (name,)

    def _s5_background(world, s):
        """A job is spawned in plan order, the last pid is answered, and nothing waits."""
        m = world.machine()
        plan = _plan(("echo", "one"), ("echo", "two"))
        pid = s.background(m, plan)
        stats = m.stats()
        assert stats["spawn"] == 2, (
            "a two-command plan spawned %r processes, not 2" % (stats["spawn"],))
        assert stats["wait"] == 0, (
            "background waited %r times: a job is not waited for when it is born"
            % (stats["wait"],))
        assert m.state(pid) == "running", (
            "the answered pid is %r after background, not running" % (m.state(pid),))
        assert m.argv(pid)[0] == "echo" and m.argv(pid)[-1] == "two", (
            "background answered pid %r running %r, not the plan's last command"
            % (pid, m.argv(pid)))
        assert m.reapable() == (), (
            "background left reapable processes %r" % (m.reapable(),))

        other = world.machine()
        single = s.background(other, _plan(("tick", "5")))
        assert other.stats()["spawn"] == 1
        assert other.stats()["wait"] == 0
        assert other.state(single) == "running"
        return pid

    def _s5_background_refusals(world, s):
        """Every plan that cannot be a job is refused by name, spawning nothing."""
        m = world.machine()
        cases = (
            ("a plan that is not a record",
             lambda: s.background(m, 3), ("plan",)),
            ("a plan whose own parse failed",
             lambda: s.background(m, {"commands": (_row("echo", "x"),),
                                      "pipes": (), "redirects": (), "steps": 0,
                                      "error": "unknown-program"}), ("unknown-program",)),
            ("a plan with no commands",
             lambda: s.background(m, {"commands": (), "pipes": (), "redirects": (),
                                      "steps": 0, "error": None}), ("commands",)),
            ("a plan whose commands are not a sequence",
             lambda: s.background(m, {"commands": "echo x", "pipes": (),
                                      "redirects": (), "steps": 0, "error": None}),
             ("commands",)),
            ("a plan row that is not a record",
             lambda: s.background(m, {"commands": (3,), "pipes": (),
                                      "redirects": (), "steps": 0, "error": None}),
             ("row",)),
            ("a plan row with no argv",
             lambda: s.background(m, {"commands": ({"fds": {}},), "pipes": (),
                                      "redirects": (), "steps": 0, "error": None}),
             ("plan row",)),
            ("a plan row with an empty argv",
             lambda: s.background(m, {"commands": ({"argv": ()},), "pipes": (),
                                      "redirects": (), "steps": 0, "error": None}),
             ("plan row",)),
            ("a plan row whose argv holds a non-string",
             lambda: s.background(m, {"commands": ({"argv": ("echo", 3)},),
                                      "pipes": (), "redirects": (), "steps": 0,
                                      "error": None}), ("plan row",)),
        )
        for what, call, names in cases:
            _refuses(world.MachineError, what, call, names)
        assert m.stats()["spawn"] == 0 and m.stats()["wait"] == 0, (
            "a refused plan touched the machine: %r" % (m.stats(),))

    def _s5_jobs_running(world, s):
        """A running row is read, never waited for; a stopped row keeps its row."""
        m = world.machine()
        pid = s.background(m, _plan(("tick", "5")))
        table = (_job(1, pid, "tick 5"),)

        before = m.stats()
        rows = s.jobs(m, table)
        after = m.stats()
        assert after["wait"] == before["wait"], (
            "jobs waited %r times for a running job"
            % (after["wait"] - before["wait"],))
        assert len(rows) == 1, "jobs answered %r rows for a one-job table" % (len(rows),)
        assert _keys(rows[0]) == S5_JOB_KEYS, (
            "a job row's fields are %r, not %r" % (_keys(rows[0]), S5_JOB_KEYS))
        assert rows[0]["job"] == 1, "the job number became %r" % (rows[0]["job"],)
        assert rows[0]["pid"] == pid, "the pid became %r" % (rows[0]["pid"],)
        assert rows[0]["state"] == "running", (
            "a running job is %r" % (rows[0]["state"],))
        assert rows[0]["status"] is None, (
            "a running job carries the status %r" % (rows[0]["status"],))
        assert rows[0]["command"] == "tick 5", (
            "the command became %r" % (rows[0]["command"],))

        before = m.stats()
        s.stop(m, pid)
        after = m.stats()
        assert after["signal"] - before["signal"] == 1, (
            "stop sent %r signals, not 1" % (after["signal"] - before["signal"],))
        assert after["ticks"] - before["ticks"] == 1, (
            "stop advanced %r ticks, not the one that delivers the signal"
            % (after["ticks"] - before["ticks"],))
        assert m.state(pid) == "stopped", (
            "stop left the process %r" % (m.state(pid),))
        before = m.stats()
        rows = s.jobs(m, table)
        assert m.stats()["wait"] == before["wait"], "jobs waited for a stopped job"
        assert rows[0]["state"] == "stopped", (
            "a stopped job is %r after jobs" % (rows[0]["state"],))
        assert rows[0]["status"] is None, (
            "a stopped job carries the status %r" % (rows[0]["status"],))
        assert rows[0]["job"] == 1 and rows[0]["command"] == "tick 5", (
            "the stopped job lost its row: %r" % (rows[0],))

        before = m.stats()
        s.resume(m, pid)
        after = m.stats()
        assert after["signal"] - before["signal"] == 1, (
            "resume sent %r signals, not 1" % (after["signal"] - before["signal"],))
        assert after["ticks"] - before["ticks"] == 1, (
            "resume advanced %r ticks, not one" % (after["ticks"] - before["ticks"],))
        assert m.state(pid) == "running", (
            "resume left the process %r" % (m.state(pid),))
        rows = s.jobs(m, table)
        assert rows[0]["state"] == "running", (
            "a resumed job is %r after jobs" % (rows[0]["state"],))
        assert rows[0]["status"] is None, "a resumed job carries a status"

    def _s5_stop_refusals(world, s):
        """stop and resume refuse a spec that is not a pid, before the machine is asked."""
        m = world.machine()
        for call in (s.stop, s.resume):
            for bad in (0, -2, "7", None, True):
                before = m.stats()
                _refuses(world.MachineError, "%s(%r)" % (call.__name__, bad),
                         lambda call=call, bad=bad: call(m, bad), (str(bad),))
                assert m.stats() == before, (
                    "%s(%r) touched the machine before refusing" % (call.__name__, bad))

    def _s5_jobs_done(world, s, rules):
        """An exited job becomes done with its status; a done row costs no door."""
        m = world.machine()
        pid = s.background(m, _plan(("false",)))
        _run_until(m, pid)
        assert m.state(pid) == "exited", (
            "the false job is %r before jobs, not exited" % (m.state(pid),))
        table = (_job(1, pid, "false"),)

        before = m.stats()
        rows = s.jobs(m, table)
        after = m.stats()
        assert after["wait"] - before["wait"] == 1, (
            "jobs waited %r times for one exited job"
            % (after["wait"] - before["wait"],))
        assert m.state(pid) == "waited", (
            "the reaped job is %r, not waited" % (m.state(pid),))
        assert m.reapable() == (), (
            "jobs left reapable processes %r" % (m.reapable(),))
        assert rows[0]["state"] == "done", (
            "a reaped job is %r" % (rows[0]["state"],))
        assert rows[0]["status"] == rules.EXIT_FAILURE, (
            "false answered %r, not %r" % (rows[0]["status"], rules.EXIT_FAILURE))
        assert _keys(rows[0]) == S5_JOB_KEYS, (
            "a done row's fields are %r, not %r" % (_keys(rows[0]), S5_JOB_KEYS))

        before = m.stats()
        again = s.jobs(m, rows)
        assert again == rows, (
            "a done row did not keep its status: %r became %r" % (rows, again))
        assert m.stats() == before, (
            "a done row was taken back to the machine: %r became %r"
            % (before, m.stats()))

        before = m.stats()
        waited = s.jobs(m, table)
        assert waited[0]["state"] == "done" and waited[0]["status"] == rules.EXIT_FAILURE, (
            "a waited pid was not read for its own status: %r" % (waited[0],))
        assert m.stats()["wait"] == before["wait"], (
            "a waited pid was waited for a second time")

    def _s5_jobs_order(world, s):
        """jobs answers in job-number order, whatever order the rows arrived in."""
        m = world.machine()
        first = s.background(m, _plan(("tick", "50")))
        second = s.background(m, _plan(("tick", "50")))
        assert first != second, "the machine answered the same pid twice"
        table = (_job(2, first, "tick 50"), _job(1, second, "tick 51"))
        rows = s.jobs(m, table)
        assert tuple(row["job"] for row in rows) == (1, 2), (
            "jobs answered the jobs as %r, not in job-number order"
            % (tuple(row["job"] for row in rows),))
        assert rows[0]["pid"] == second and rows[1]["pid"] == first, (
            "the rows followed pid order, not job order: %r" % (rows,))
        assert tuple(row["command"] for row in rows) == ("tick 51", "tick 50"), (
            "the commands were reordered: %r" % (rows,))
        assert s.jobs(m, ()) == (), "an empty table did not answer no rows"

    def _s5_jobs_refusals(world, s):
        """A table that is not the shell's own bookkeeping is refused by name."""
        m = world.machine()
        pid = s.background(m, _plan(("tick", "5")))
        before = m.stats()
        cases = (
            ("a table that is not a sequence",
             lambda: s.jobs(m, "table"), ("sequence",)),
            ("a row that is not a record",
             lambda: s.jobs(m, (3,)), ("row",)),
            ("a row with no job",
             lambda: s.jobs(m, ({"pid": pid, "command": "tick 5"},)), ("job",)),
            ("a row with no pid",
             lambda: s.jobs(m, ({"job": 1, "command": "tick 5"},)), ("pid",)),
            ("a row with no command",
             lambda: s.jobs(m, ({"job": 1, "pid": pid},)), ("command",)),
            ("a job number of zero",
             lambda: s.jobs(m, (_job(0, pid),)), ("0",)),
            ("a pid that is not a number",
             lambda: s.jobs(m, ({"job": 1, "pid": "x", "command": "tick 5"},)), ("x",)),
            ("a command that is not a line",
             lambda: s.jobs(m, ({"job": 1, "pid": pid, "command": 3},)), ("command",)),
            ("a state the table does not know",
             lambda: s.jobs(m, (_job(1, pid, state="zombie"),)), ("zombie",)),
            ("a done row with no status",
             lambda: s.jobs(m, (_job(1, pid, state="done"),)), ("None",)),
            ("a done row with a boolean status",
             lambda: s.jobs(m, (_job(1, pid, state="done", status=True),)), ("True",)),
        )
        for what, call, names in cases:
            _refuses(world.MachineError, what, call, names)
        assert m.stats() == before, (
            "a refused table touched the machine: %r became %r" % (before, m.stats()))

    def _s5_resolve(s):
        """The four accepted specs, off a table written here."""
        table = (_job(1, 101, "cat a"), _job(2, 202, "cat b"),
                 _job(3, 303, "cat c"))
        assert s.resolve(table, "%1") == 101, "%%1 did not answer job 1's pid"
        assert s.resolve(table, "%2") == 202, "%%2 did not answer job 2's pid"
        assert s.resolve(table, "%3") == 303, "%%3 did not answer job 3's pid"
        assert s.resolve(table, "%+") == 303, (
            "%%+ did not answer the current job: %r" % (s.resolve(table, "%+"),))
        assert s.resolve(table, "%-") == 202, (
            "%%- did not answer the previous job: %r" % (s.resolve(table, "%-"),))
        assert s.resolve(table, 404) == 404, "a pid was not answered as itself"
        assert s.resolve(table, "404") == 404, (
            "a pid written as digits was not answered as itself")
        assert s.resolve((), 7) == 7, "a pid was asked of an empty table"
        single = (_job(1, 101, "cat a"),)
        assert s.resolve(single, "%+") == 101, "the only job is not the current one"
        assert s.resolve(single, "%1") == 101, "the only job is not job 1"

    def _s5_resolve_refusals(world, s):
        """Everything that is neither a held job nor a pid is refused by name."""
        table = (_job(1, 101, "cat a"), _job(2, 202, "cat b"))
        single = (_job(1, 101, "cat a"),)
        cases = (
            ("a job number the table does not hold", lambda: s.resolve(table, "%9"),
             ("%9",)),
            ("job zero", lambda: s.resolve(table, "%0"), ("%0",)),
            ("a lone percent", lambda: s.resolve(table, "%"), ("%",)),
            ("a percent word", lambda: s.resolve(table, "%x"), ("%x",)),
            ("a word", lambda: s.resolve(table, "abc"), ("abc",)),
            ("a negative number", lambda: s.resolve(table, "-1"), ("-1",)),
            ("a decimal", lambda: s.resolve(table, "1.5"), ("1.5",)),
            ("a spec that is not text", lambda: s.resolve(table, None), ("None",)),
            ("a boolean spec", lambda: s.resolve(table, True), ("True",)),
            ("a pid of zero", lambda: s.resolve(table, 0), ("0",)),
            ("a negative pid", lambda: s.resolve(table, -3), ("-3",)),
            ("no previous job", lambda: s.resolve(single, "%-"), ("%-",)),
            ("no current job", lambda: s.resolve((), "%+"), ("%+",)),
            ("no joined current job", lambda: s.resolve((), "%-"), ("%-",)),
            ("a table that is not a sequence", lambda: s.resolve(3, "%1"), ("table",)),
            ("a row with no pid",
             lambda: s.resolve(({"job": 1, "command": "cat a"},), "%1"), ("pid",)),
        )
        for what, call, names in cases:
            _refuses(world.MachineError, what, call, names)

    def _s5_wait(world, s, rules):
        """A wait on a done row costs no door; a wait reaps exactly what it names."""
        m = world.machine()
        pid = s.background(m, _plan(("false",)))
        _run_until(m, pid)
        done = s.jobs(m, (_job(1, pid, "false"),))[0]
        assert done["state"] == "done", "the false job did not finish"

        before = m.stats()
        answer = s.wait_for(m, (done,), pid)
        assert tuple(answer) == S5_STATUS_KEYS, (
            "the waited status row's fields are %r, not %r"
            % (tuple(answer), S5_STATUS_KEYS))
        assert answer == {"pid": pid, "status": rules.EXIT_FAILURE,
                          "signalled": False, "signal": None}, (
            "waiting a done job answered %r" % (answer,))
        assert m.stats() == before, (
            "a wait on a done job touched the machine: %r became %r"
            % (before, m.stats()))

        before = m.stats()
        assert s.wait_for(m, (done,), "%1") == answer, (
            "%%1 did not name the done job's status")
        assert m.stats() == before, "a wait on a done job by %%1 touched the machine"

        m2 = world.machine()
        pid2 = s.background(m2, _plan(("false",)))
        _run_until(m2, pid2)
        before = m2.stats()
        answer = s.wait_for(m2, (_job(1, pid2, "false"),), pid2)
        assert m2.stats()["wait"] - before["wait"] == 1, (
            "waiting an exited pid cost %r waits, not 1"
            % (m2.stats()["wait"] - before["wait"],))
        assert m2.state(pid2) == "waited", (
            "the waited pid is %r after wait" % (m2.state(pid2),))
        assert answer["pid"] == pid2 and answer["status"] == rules.EXIT_FAILURE, (
            "the waited pid's row is %r" % (answer,))
        assert answer["signalled"] is False and answer["signal"] is None, (
            "a plain exit was reported as a signal: %r" % (answer,))
        assert tuple(answer) == S5_STATUS_KEYS, (
            "the reaped status row's fields are %r, not %r"
            % (tuple(answer), S5_STATUS_KEYS))

        m3 = world.machine()
        first = s.background(m3, _plan(("false",)))
        second = s.background(m3, _plan(("echo", "done")))
        _run_until(m3, first)
        _run_until(m3, second)
        before = m3.stats()
        answer = s.wait_for(m3, (_job(2, second, "echo done"),
                                _job(1, first, "false")))
        assert m3.stats()["wait"] - before["wait"] == 2, (
            "waiting every job cost %r waits, not one per job"
            % (m3.stats()["wait"] - before["wait"],))
        assert answer["pid"] == second and answer["status"] == rules.EXIT_OK, (
            "waiting every job answered %r, not the last job's row" % (answer,))

        m4 = world.machine()
        third = s.background(m4, _plan(("false",)))
        fourth = s.background(m4, _plan(("echo", "done")))
        _run_until(m4, third)
        _run_until(m4, fourth)
        r3 = s.jobs(m4, (_job(1, third, "false"),))[0]
        table = (r3, _job(2, fourth, "echo done"))
        before = m4.stats()
        answer = s.wait_for(m4, table)
        assert m4.stats()["wait"] - before["wait"] == 1, (
            "waiting a table with one done row cost %r waits, not 1"
            % (m4.stats()["wait"] - before["wait"],))
        assert answer["pid"] == fourth and answer["status"] == rules.EXIT_OK, (
            "the all-jobs wait answered %r" % (answer,))

        assert s.wait_for(m4, ()) == {"pid": None, "status": 0,
                                      "signalled": False, "signal": None}, (
            "an empty table did not answer a successful no-op")
        _refuses(world.MachineError, "wait_for(%r)" % ("%9",),
                 lambda: s.wait_for(m4, table, "%9"), ("%9",))
        _refuses(world.MachineError, "a done row with a status that is not a number",
                 lambda: s.wait_for(m4, ({"job": 1, "pid": 900,
                                          "state": "done", "status": "x",
                                          "command": "false"},), 900), ("x",))

    """Every assertion the contract's §4.5 makes about this stage."""
    import machine as world
    import rules
    import stage_05 as s

    _s5_constants(s)
    _s5_background(world, s)
    _s5_background_refusals(world, s)
    _s5_jobs_running(world, s)
    _s5_stop_refusals(world, s)
    _s5_jobs_done(world, s, rules)
    _s5_jobs_order(world, s)
    _s5_jobs_refusals(world, s)
    _s5_resolve(s)
    _s5_resolve_refusals(world, s)
    _s5_wait(world, s, rules)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    MARKERS = ("machine.py", "course.py")

    S6_STATUS = {"HUP": 129, "INT": 130, "QUIT": 131, "TERM": 143, "CHLD": 145,
                 "STOP": 147, "CONT": 146}

    S6_TRAP_KEYS = ("name", "action", "fired")

    S6_STATUS_KEYS = ("pid", "status", "signalled", "signal")

    S6_TRAPPABLE = ("HUP", "INT", "QUIT", "TERM", "CHLD")

    S6_RAN_KEYS = ("name", "status", "output")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in MARKERS:
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _fresh(machine):
        """A machine of its own, so one case cannot leave a process for the next."""
        return machine.machine(7)

    def _alive(m, program="echo", word="hi"):
        """A process that is running and has not answered, on its way to finishing."""
        pid = m.spawn((program, word))
        assert m.state(pid) == "running", (
            "a freshly spawned process is %r, and this check needs a running one"
            % (m.state(pid),))
        return pid

    def _answered(m, program="echo", word="done"):
        """A pid that has exited and has **not** been reaped: the machine owes it a wait."""
        pid = m.spawn((program, word))
        for _ in range(16):
            if m.state(pid) != "running":
                break
            m.advance()
        assert m.state(pid) == "exited", (
            "the fixture's own process is %r, and this check needs an exited one"
            % (m.state(pid),))
        return pid

    def _ready(m):
        """A machine holding one pid that has exited and one that has been reaped."""
        exited = _answered(m)
        reaped_pid = m.spawn(("false",))
        answer = m.wait(reaped_pid)
        assert m.state(reaped_pid) == "waited", (
            "a process the machine reaped is %r, and this check needs `waited`"
            % (m.state(reaped_pid),))
        return exited, reaped_pid, answer

    def _s6_constants(s, machine, rules):
        """The three constants, and the world's own table they are derived from."""
        assert s.TRAP_KEYS == S6_TRAP_KEYS, (
            "TRAP_KEYS is %r; a trap is %r" % (s.TRAP_KEYS, S6_TRAP_KEYS))
        assert s.STATUS_KEYS == S6_STATUS_KEYS, (
            "STATUS_KEYS is %r; a signal's answer is %r" % (s.STATUS_KEYS, S6_STATUS_KEYS))
        assert s.TRAPPABLE == S6_TRAPPABLE, (
            "TRAPPABLE is %r; a shell may trap %r" % (s.TRAPPABLE, S6_TRAPPABLE))
        assert tuple(rules.SIGNAL_NAMES) == tuple(S6_STATUS), (
            "the world's signals are %r and this check's table holds %r"
            % (rules.SIGNAL_NAMES, tuple(S6_STATUS)))
        recomputed = dict((name, rules.SIGNAL_STATUS_BASE + rules.SIGNAL_NUMBERS[name])
                          for name in rules.SIGNAL_NAMES)
        assert recomputed == S6_STATUS, (
            "the world's own `128 + n` is %r, and this check's table is %r"
            % (recomputed, S6_STATUS))
        assert tuple(name for name in rules.SIGNAL_NAMES if name not in S6_TRAPPABLE) \
            == ("STOP", "CONT"), (
                "the signals that are not trappable are %r, and this stage pins STOP and "
                "CONT" % (tuple(name for name in rules.SIGNAL_NAMES
                                if name not in S6_TRAPPABLE),))

    def _s6_status_of(s, machine, rules):
        """`status_of` for every name in `SIGNAL_NAMES`, against the check's own table."""
        m = _fresh(machine)
        before = m.stats()
        for name in rules.SIGNAL_NAMES:
            want = S6_STATUS[name]
            got = s.status_of(name)
            assert got == want, (
                "status_of(%r) answered %r; a process that died of %r answers %r"
                % (name, got, name, want))
        assert m.stats() == before, (
            "status_of asked the machine something: %r became %r" % (before, m.stats()))
        for bad in ("KILL", "int", "9", "", "INT ", None, 2, True):
            _refuses(machine.MachineError, "status_of(%r)" % (bad,),
                     lambda name=bad: s.status_of(name), names=(repr(bad),))

    def _s6_deliver(s, machine, rules):
        """`deliver` on a live process, a stopped one, an answered one, a reaped one."""
        m = _fresh(machine)
        pid = _alive(m)
        before = m.stats()
        row = s.deliver(m, pid, "INT")
        after = m.stats()
        assert tuple(row) == S6_STATUS_KEYS, (
            "deliver answered %r; a signal's answer is %r" % (tuple(row), S6_STATUS_KEYS))
        assert row == {"pid": pid, "status": S6_STATUS["INT"],
                       "signalled": True, "signal": "INT"}, (
            "delivering INT to a live process answered %r" % (row,))
        assert m.state(pid) == "exited", (
            "a process that died of INT is %r" % (m.state(pid),))
        assert m.status(pid) == row["status"], (
            "deliver answered %r and the machine recorded %r for the same process"
            % (row["status"], m.status(pid)))
        assert after["signal"] == before["signal"] + 1, (
            "deliver sent %r signals, not one" % (after["signal"] - before["signal"],))
        assert after["ticks"] == before["ticks"] + 1, (
            "deliver advanced %r ticks, not the one a delivery needs"
            % (after["ticks"] - before["ticks"],))
        m.wait(pid)
        for name in ("HUP", "QUIT", "TERM"):
            pid = _alive(m)
            row = s.deliver(m, pid, name)
            assert row["status"] == S6_STATUS[name] == m.status(pid), (
                "delivering %r answered %r and the machine recorded %r"
                % (name, row["status"], m.status(pid)))
            assert row["signalled"] is True and row["signal"] == name, (
                "delivering %r answered %r" % (name, row,))
            m.wait(pid)

        pid = _alive(m)
        row = s.deliver(m, pid, "STOP")
        assert m.state(pid) == "stopped", (
            "a process that was sent STOP is %r" % (m.state(pid),))
        assert row == {"pid": pid, "status": rules.EXIT_OK,
                       "signalled": False, "signal": "STOP"}, (
            "delivering STOP to a live process answered %r" % (row,))
        row = s.deliver(m, pid, "CHLD")
        assert row == {"pid": pid, "status": rules.EXIT_OK,
                       "signalled": False, "signal": None}, (
            "delivering CHLD to a process that was already stopped answered %r" % (row,))
        assert m.state(pid) == "stopped", (
            "a stopped process that was sent CHLD is %r" % (m.state(pid),))
        row = s.deliver(m, pid, "CONT")
        assert row["signalled"] is False and row["signal"] is None, (
            "delivering CONT to a stopped process answered %r" % (row,))
        m.wait(pid)

        pid = _alive(m)
        row = s.deliver(m, pid, "CHLD")
        assert row["signalled"] is False and row["signal"] is None, (
            "delivering CHLD to a live process answered %r" % (row,))
        if m.state(pid) in ("exited", "waited"):
            assert row["status"] == m.status(pid), (
                "a process that answered during the tick answered %r and the machine "
                "recorded %r, so deliver read it as a signal's kill"
                % (row["status"], m.status(pid)))
        else:
            assert row["status"] == rules.EXIT_OK, (
                "a signal that left the process running answered %r" % (row,))
        m.wait(pid)

        exited, reaped_pid, answer = _ready(m)
        answered = s.deliver(m, exited, "TERM")
        assert answered == {"pid": exited, "status": m.status(exited),
                            "signalled": False, "signal": None}, (
            "delivering TERM to a process that had already exited answered %r"
            % (answered,))
        assert answered["status"] == m.status(exited), (
            "a process that had already exited answered %r and the machine holds %r"
            % (answered["status"], m.status(exited)))
        reaped = s.deliver(m, reaped_pid, "TERM")
        assert reaped == {"pid": reaped_pid, "status": answer["status"],
                          "signalled": False, "signal": None}, (
            "delivering TERM to a process that had been reaped answered %r" % (reaped,))
        assert reaped["status"] == rules.EXIT_FAILURE, (
            "the fixture's own reaped process answered %r, not the failure it ran for"
            % (reaped["status"],))
        m.wait(exited)
        for bad in ("KILL", "int", "", None, 2):
            _refuses(machine.MachineError, "deliver(pid, %r)" % (bad,),
                     lambda name=bad: s.deliver(m, exited, name), names=(repr(bad),))
        _refuses(machine.MachineError, "deliver(999, 'INT')",
                 lambda: s.deliver(m, 999, "INT"), names=("999",))
        assert m.reapable() == (), (
            "the check's own fixtures left %r unwaited" % (m.reapable(),))

    def _s6_trap(s, machine, rules):
        """`trap` arms every trappable name, resets, ignores, and refuses the rest."""
        m = _fresh(machine)
        before = m.stats()
        for name in S6_TRAPPABLE:
            row = s.trap(m, name, "echo armed")
            assert tuple(row) == S6_TRAP_KEYS, (
                "a trap row is %r; TRAP_KEYS is %r" % (tuple(row), S6_TRAP_KEYS))
            assert row == {"name": name, "action": "echo armed", "fired": False}, (
                "trap(%r) answered %r" % (name, row))
        assert s.trap(m, "INT", "")["action"] == "", (
            "a trap's `\"\"` is the signal's own default, and it answered %r"
            % (s.trap(m, "INT", "")["action"],))
        assert s.trap(m, "INT", "-")["action"] == "-", (
            "a trap's `\"-\"` is the shell ignoring the signal, and it answered %r"
            % (s.trap(m, "INT", "-")["action"],))
        assert m.stats() == before, (
            "trap asked the machine something: %r became %r" % (before, m.stats()))
        for name in ("STOP", "CONT"):
            _refuses(machine.MachineError, "trap(%r)" % (name,),
                     lambda trap_name=name: s.trap(m, trap_name, "echo no"),
                     names=(name,))
        for bad in ("KILL", "int", "", None, 2, True):
            _refuses(machine.MachineError, "trap(%r)" % (bad,),
                     lambda trap_name=bad: s.trap(m, trap_name, "echo no"),
                     names=(repr(bad),))
        for action in (None, 7, ("echo",), b"echo"):
            _refuses(machine.MachineError, "trap('INT', %r)" % (action,),
                     lambda a=action: s.trap(m, "INT", a), names=(repr(action),))
        assert m.stats() == before, (
            "a refused trap touched the machine: %r became %r" % (before, m.stats()))

    def _s6_fire(s, machine, rules):
        """Two traps due at once: the order, the once-each rule, the last status."""
        m = _fresh(machine)
        table = (s.trap(m, "TERM", "false"), s.trap(m, "INT", "echo"))
        boundary = m.wait(m.spawn(("echo", "boundary")))
        assert boundary["status"] == rules.EXIT_OK, (
            "the check's own boundary command answered %r" % (boundary["status"],))
        before = m.stats()
        rows = s.run_traps(m, table)
        unwaited = m.reapable()
        after = m.stats()
        assert isinstance(rows, tuple), "run_traps answered %r, not a tuple" % (rows,)
        assert tuple(row["name"] for row in rows) == ("INT", "TERM"), (
            "two traps due at once ran in the order %r; the order is the signal's number"
            % (tuple(row["name"] for row in rows),))
        for row in rows:
            assert tuple(row) == S6_RAN_KEYS, (
                "a fired trap answers %r; it answers %r" % (tuple(row), S6_RAN_KEYS))
        assert tuple(row["status"] for row in rows) == (rules.EXIT_OK,
                                                        rules.EXIT_FAILURE), (
            "the traps answered %r" % (tuple(row["status"] for row in rows),))
        assert rows[-1]["status"] == rules.EXIT_FAILURE, (
            "the shell's own status after two traps is the last trap's, and the last trap "
            "answered %r" % (rows[-1]["status"],))
        assert rows[-1]["status"] != boundary["status"], (
            "the shell carried the boundary command's status (%r) and not the last trap's "
            "(%r)" % (boundary["status"], rows[-1]["status"]))
        assert after["spawn"] == before["spawn"] + 2, (
            "the boundary spawned %r processes; two traps owed two runs"
            % (after["spawn"] - before["spawn"],))
        assert after["wait"] == before["wait"] + 2, (
            "the boundary waited %r times; every trap's child is reaped"
            % (after["wait"] - before["wait"],))
        assert unwaited == (), (
            "a trap left %r unwaited" % (unwaited,))
        assert tuple(table) == ({"name": "TERM", "action": "", "fired": True},
                                {"name": "INT", "action": "", "fired": True}), (
            "a fired trap is reset to its default, and the table came back %r"
            % (tuple(table),))
        again = s.run_traps(m, table)
        assert again == (), (
            "a trap that had fired fired again: %r" % (again,))
        assert m.stats() == after, (
            "a boundary with nothing due asked the machine something: %r became %r"
            % (after, m.stats()))

    def _s6_output(s, machine, rules):
        """A trap's output is the bytes its own program printed on the shell's stdout."""
        m = _fresh(machine)
        table = (s.trap(m, "HUP", "echo caught"),)
        before = m.terminal()
        rows = s.run_traps(m, table)
        after = m.terminal()
        assert len(rows) == 1 and rows[0]["name"] == "HUP", (
            "one trap was due and %r ran" % (rows,))
        assert rows[0]["status"] == rules.EXIT_OK, (
            "a trap whose command is `echo` answered %r" % (rows[0]["status"],))
        assert rows[0]["output"] == after[len(before):], (
            "the trap's output is %r and the shell's stdout grew by %r"
            % (rows[0]["output"], after[len(before):]))
        assert b"caught" in after[len(before):], (
            "the trap's program printed nothing on the shell's own stdout: %r"
            % (after[len(before):],))
        assert m.reapable() == (), (
            "a trap's child was left unwaited: %r" % (m.reapable(),))

    def _s6_ignore(s, machine, rules):
        """A signal the shell ignores is not run, not sent, and not even touched."""
        m = _fresh(machine)
        table = ({"name": "TERM", "action": "-", "fired": False},
                 {"name": "INT", "action": "", "fired": False},
                 {"name": "HUP", "action": "echo hup", "fired": True})
        before = m.stats()
        assert s.run_traps(m, table) == (), (
            "an ignored signal, a signal at its default and a trap that had already fired "
            "are all not due")
        assert m.stats() == before, (
            "a boundary with nothing due asked the machine something: %r became %r"
            % (before, m.stats()))
        assert tuple(table) == ({"name": "TERM", "action": "-", "fired": False},
                                {"name": "INT", "action": "", "fired": False},
                                {"name": "HUP", "action": "echo hup", "fired": True}), (
            "a boundary that ran nothing changed the table: %r" % (tuple(table),))

    def _s6_unknown(s, machine, rules):
        """A trap whose command is not a program answers 127 and costs no fork."""
        m = _fresh(machine)
        table = (s.trap(m, "INT", "frobnicate now"),)
        before = m.stats()
        rows = s.run_traps(m, table)
        after = m.stats()
        assert len(rows) == 1 and rows[0]["name"] == "INT", (
            "the trap ran and answered %r" % (rows,))
        assert rows[0]["status"] == rules.EXIT_NOT_FOUND, (
            "a command that is not a program answered %r, not `no such command`"
            % (rows[0]["status"],))
        assert rows[0]["output"] == b"", (
            "a command that does not exist printed %r" % (rows[0]["output"],))
        assert after == before, (
            "a trap whose command is not a program touched the machine: %r became %r"
            % (before, after))
        assert tuple(table) == ({"name": "INT", "action": "", "fired": True},), (
            "the row came back %r" % (tuple(table),))

    def _s6_again(s, machine, rules):
        """A trap that fired does not fire again unless it sets itself again."""
        m = _fresh(machine)
        table = (s.trap(m, "INT", "trap echo INT"),)
        rows = s.run_traps(m, table)
        assert len(rows) == 1 and rows[0]["name"] == "INT", (
            "the trap ran and answered %r" % (rows,))
        assert rows[0]["status"] == rules.EXIT_OK and rows[0]["output"] == b"", (
            "a trap that only set itself again answered %r" % (rows[0],))
        assert tuple(table) == ({"name": "INT", "action": "echo", "fired": False},), (
            "a trap that set itself again came back %r; it keeps the action it re-armed "
            "with and stays due" % (tuple(table),))
        before = m.terminal()
        rows = s.run_traps(m, table)
        after = m.terminal()
        assert len(rows) == 1 and rows[0]["name"] == "INT", (
            "the trap that had set itself again did not fire again: %r" % (rows,))
        assert rows[0]["status"] == rules.EXIT_OK, (
            "the re-armed trap answered %r" % (rows[0]["status"],))
        assert rows[0]["output"] == after[len(before):], (
            "the re-armed trap's output is %r and the shell's stdout grew by %r"
            % (rows[0]["output"], after[len(before):]))
        assert m.reapable() == (), "a re-armed trap left %r unwaited" % (m.reapable(),)
        assert tuple(table) == ({"name": "INT", "action": "", "fired": True},), (
            "a trap that fired without setting itself again came back %r"
            % (tuple(table),))
        assert s.run_traps(m, table) == (), (
            "the trap fired a third time: %r" % (s.run_traps(m, table),))

    def _s6_rearm(s, machine, rules):
        """A trap's own `trap` builtin arms, resets and ignores the other signals."""
        m = _fresh(machine)
        table = (s.trap(m, "INT", "trap - TERM"),
                 {"name": "TERM", "action": "old", "fired": True})
        rows = s.run_traps(m, table)
        assert len(rows) == 1 and rows[0]["name"] == "INT", (
            "only the trap that is due runs, and %r ran" % (rows,))
        assert tuple(table[1]) == S6_TRAP_KEYS, (
            "the other signal's row is a TRAP_KEYS row is %r" % (tuple(table[1]),))
        assert table[1] == {"name": "TERM", "action": "-", "fired": False}, (
            "a trap's own `trap - TERM` left TERM's row as %r; `-` is the shell ignoring "
            "that signal" % (table[1],))
        assert table[0] == {"name": "INT", "action": "", "fired": True}, (
            "a trap that re-armed another signal rather than itself came back %r"
            % (table[0],))

        table = (s.trap(m, "HUP", 'trap "" QUIT'),
                 {"name": "QUIT", "action": "old", "fired": True})
        s.run_traps(m, table)
        assert table[1] == {"name": "QUIT", "action": "", "fired": False}, (
            "a trap's own `trap \"\" QUIT` left QUIT's row as %r; `\"\"` is that signal's "
            "own default" % (table[1],))

        table = (s.trap(m, "HUP", "trap echo CHLD"),)
        s.run_traps(m, table)
        assert table[0] == {"name": "HUP", "action": "", "fired": True}, (
            "a trap that re-armed a signal that was not its own came back %r" % (table[0],))

    def _s6_arm_refusals(s, machine, rules):
        """A trap's own `trap` command that names no signal, or a signal it may not trap."""
        m = _fresh(machine)
        for action, named in (("trap", "trap"),
                              ("trap echo", "trap echo"),
                              ("trap echo STOP", "STOP"),
                              ("trap echo CONT", "CONT"),
                              ("trap echo KILL", "KILL")):
            table = (s.trap(m, "INT", action),)
            _refuses(machine.MachineError, "a trap whose action is %r" % (action,),
                     lambda t=table: s.run_traps(m, t), names=(named,))
            assert tuple(table) == ({"name": "INT", "action": action, "fired": False},), (
                "a refused trap command changed its own row: %r" % (tuple(table),))

    def _s6_refusals(s, machine, rules):
        """A trap table, and every row, is the shape §4.6 says or it is a refusal."""
        for bad in ("INT", 7, {"INT": "echo"}, None, b"INT"):
            _refuses(machine.MachineError, "run_traps(%r)" % (bad,),
                     lambda t=bad: s.run_traps(_fresh(machine), t),
                     names=(repr(bad),))
        rows = (({"name": "INT", "action": "echo"},),
                ({"name": "INT", "action": "echo", "fired": False, "extra": 1},),
                ("INT",),
                ({"name": "STOP", "action": "echo", "fired": False},),
                ({"name": "KILL", "action": "echo", "fired": False},),
                ({"name": 7, "action": "echo", "fired": False},),
                ({"name": "INT", "action": 7, "fired": False},),
                ({"name": "INT", "action": "echo", "fired": None},))
        for table in rows:
            _refuses(machine.MachineError, "run_traps(%r)" % (table,),
                     lambda t=table: s.run_traps(_fresh(machine), t),
                     names=(repr(table[0]),))

    def _s6_kill(s, machine, rules):
        """`kill` sends the signal the words name to the target §4.5 resolves."""
        m = _fresh(machine)
        pid = _alive(m)
        table = ({"job": 1, "pid": pid, "state": "running", "status": None,
                  "command": "echo hi"},)
        before = m.stats()
        row = s.run_kill(m, ("-INT", "%1"), table)
        after = m.stats()
        assert tuple(row) == S6_STATUS_KEYS, (
            "run_kill answered %r; a signal's answer is %r" % (tuple(row), S6_STATUS_KEYS))
        assert row == {"pid": pid, "status": S6_STATUS["INT"],
                       "signalled": True, "signal": "INT"}, (
            "`kill -INT %%1` answered %r" % (row,))
        assert m.status(pid) == row["status"], (
            "run_kill answered %r and the machine recorded %r" % (row["status"],
                                                                 m.status(pid)))
        assert after["signal"] == before["signal"] + 1 and \
            after["ticks"] == before["ticks"] + 1, (
                "`kill` sent %r signals in %r ticks, and a kill is one and one"
                % (after["signal"] - before["signal"], after["ticks"] - before["ticks"]))
        m.wait(pid)

        pid = _alive(m)
        table = ({"job": 2, "pid": pid, "state": "running", "status": None,
                  "command": "echo hi"},)
        row = s.run_kill(m, ("%2",), table)
        assert row["status"] == S6_STATUS["TERM"] and row["signal"] == "TERM", (
            "`kill %%2` answers the default signal's row, and it answered %r" % (row,))
        m.wait(pid)

        pid = _alive(m)
        row = s.run_kill(m, ("-15", str(pid)), ())
        assert row["pid"] == pid and row["signal"] == "TERM", (
            "`kill -15 PID` answered %r; the number is the signal's too" % (row,))
        assert row["status"] == S6_STATUS["TERM"], (
            "`kill -15 PID` answered the status %r" % (row["status"],))
        m.wait(pid)

        pid = _alive(m)
        row = s.run_kill(m, ("-STOP", str(pid)), ())
        assert row == {"pid": pid, "status": rules.EXIT_OK,
                       "signalled": False, "signal": "STOP"}, (
            "`kill -STOP PID` answered %r; STOP is the machine's and may be sent"
            % (row,))
        assert m.state(pid) == "stopped", (
            "`kill -STOP PID` left the process %r" % (m.state(pid),))
        row = s.run_kill(m, ("-CONT", str(pid)), ())
        assert row["signalled"] is False and row["signal"] is None, (
            "`kill -CONT PID` answered %r" % (row,))
        m.wait(pid)

        table = ({"job": 1, "pid": 11, "state": "running", "status": None, "command": "a"},
                 {"job": 3, "pid": 33, "state": "stopped", "status": None, "command": "b"})
        _refuses(machine.MachineError, "`kill %4`", lambda: s.run_kill(m, ("%4",), table),
                 names=("%4",))
        assert m.reapable() == (), "the check's own fixtures left %r unwaited" % (m.reapable(),)

    def _s6_kill_refusals(s, machine, rules):
        """Every usage error `kill` refuses, and no signal sent for any of them."""
        m = _fresh(machine)
        pid = _alive(m)
        table = ({"job": 1, "pid": pid, "state": "running", "status": None,
                  "command": "echo hi"},)
        before = m.stats()
        cases = (((), "nothing"),
                 (("-INT",), "nothing"),
                 (("-INT", "%1", "%1"), "'%1'"),
                 (("-INT", str(pid), "5"), "'5'"),
                 (("-KILL", "%1"), "-KILL"),
                 (("-9", "%1"), "-9"),
                 (("-", "%1"), "-"),
                 (("-INT", "%99"), "%99"),
                 (("echo hi",), "echo hi"))
        for argv, named in cases:
            _refuses(machine.MachineError, "run_kill(%r)" % (argv,),
                     lambda a=argv: s.run_kill(m, a, table), names=(named,))
        _refuses(machine.MachineError, "run_kill with a row that is not a word",
                 lambda: s.run_kill(m, (pid,), table), names=(str(pid),))
        _refuses(machine.MachineError, "run_kill with no argv at all",
                 lambda: s.run_kill(m, None, table), names=("None",))
        _refuses(machine.MachineError, "run_kill('%1') with an empty table",
                 lambda: s.run_kill(m, ("%1",), ()), names=("%1",))
        assert m.stats() == before, (
            "a refused kill touched the machine: %r became %r" % (before, m.stats()))
        assert m.state(pid) == "running", (
            "a refused kill left its own fixture %r" % (m.state(pid),))
        m.wait(pid)

    def _s6_fixtures(s, machine, rules, scripts):
        """Every signal a fixture session sends is one this stage can carry."""
        names = scripts.names()
        assert names, "the world holds no fixture sessions"
        seen = 0
        for name in names:
            session = scripts.session(name)
            for sent in session["expected"]["signals"]:
                assert sent in rules.SIGNAL_NAMES, (
                    "the fixture %r sends %r, which is not a signal of the policy"
                    % (name, sent))
                assert s.status_of(sent) == S6_STATUS[sent], (
                    "the fixture %r sends %r and status_of(%r) answered %r"
                    % (name, sent, sent, s.status_of(sent)))
                seen += 1
        assert seen > 0, (
            "no fixture session sends a signal, so the world's own sessions prove nothing "
            "about this stage")

    def _s6_pass(s, machine, rules):
        """One whole pass over the stage, from a fresh machine."""
        m = _fresh(machine)
        answers = []
        for name in rules.SIGNAL_NAMES:
            answers.append(("status", name, s.status_of(name)))
        pid = _alive(m)
        answers.append(("deliver", s.deliver(m, pid, "TERM")))
        table = (s.trap(m, "CHLD", "echo child"),
                 {"name": "INT", "action": "-", "fired": False},
                 {"name": "QUIT", "action": "false", "fired": False})
        answers.append(("traps", s.run_traps(m, table)))
        answers.append(("table", tuple((row["name"], row["action"], row["fired"])
                                       for row in table)))
        pid = _alive(m)
        answers.append(("kill", s.run_kill(m, ("-QUIT", str(pid)), ())))
        m.wait(pid)
        answers.append(("terminal", m.terminal()))
        return tuple(answers)

    def _s6_twice(s, machine, rules):
        """Two runs of one workload, which a stage that kept state between them would fail."""
        one = _s6_pass(s, machine, rules)
        two = _s6_pass(s, machine, rules)
        assert one == two, (
            "two runs of one workload answered differently, so a run is not a function of "
            "its inputs")

    """Every assertion the contract's §4.6 makes about this stage."""
    import machine
    import programs
    import rules
    import scripts
    import stage_06 as s
    assert programs.PROGRAM_NAMES, "the world holds no programs"
    _s6_constants(s, machine, rules)
    _s6_status_of(s, machine, rules)
    _s6_deliver(s, machine, rules)
    _s6_trap(s, machine, rules)
    _s6_fire(s, machine, rules)
    _s6_output(s, machine, rules)
    _s6_ignore(s, machine, rules)
    _s6_unknown(s, machine, rules)
    _s6_again(s, machine, rules)
    _s6_rearm(s, machine, rules)
    _s6_arm_refusals(s, machine, rules)
    _s6_refusals(s, machine, rules)
    _s6_kill(s, machine, rules)
    _s6_kill_refusals(s, machine, rules)
    _s6_fixtures(s, machine, rules, scripts)
    _s6_twice(s, machine, rules)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    S7_BUILTIN_KEYS = ("name", "status", "state", "output")

    S7_BUILTIN_STATES = ("unchanged", "cwd", "env", "variables", "options", "exit")

    S7_SHELL_KEYS = ("variables", "exported", "traps", "jobs", "flags", "cwd", "exit",
                     "args", "stdin")

    S7_ELSEWHERE = (("trap", "stage 6"), ("kill", "stage 6"), ("wait", "stage 5"))

    S7_OTHER_WORDS = ("echo", "cat", "pwd", "true", "ls", "env", "wc", "cdx", "C", "+",
                      "%1", "-", "-o", "builtin", "trap ", " cd", "cd cd", ":x")

    S7_DOORS = ("spawn", "fork", "exec", "wait", "pipe", "open", "dup2", "close", "read",
                "write", "signal", "ticks", "steps", "deadlocks")

    S7_CHILD_DOORS = ("spawn", "fork", "exec", "wait", "pipe")

    S7_USAGE = ((":", ": [arguments]"),
                ("cd", "cd [directory]"),
                ("exit", "exit [status]"),
                ("export", "export [NAME[=value]]..."),
                ("read", "read NAME..."),
                ("set", "set [-o option | +o option]"),
                ("shift", "shift [n]"),
                ("unset", "unset NAME..."))

    def _repo(start=None):
        """The repository the course lives in: the one holding `shell-from-scratch/machine.py`."""
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "machine.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked against
        the message: an exception of the right family raised for the wrong reason is not
        the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _usage_of(name):
        """The bytes a wrongly-called builtin must have written, from the check's own table."""
        for word, line in S7_USAGE:
            if word == name:
                return ("usage: %s\n" % (line,)).encode("utf-8")
        raise AssertionError("%r has no usage line in this check" % (name,))

    def _moved(before, after):
        """What each of the machine's counted doors did between two snapshots."""
        return {key: after[key] - before[key] for key in after}

    def _cost(machine, what, call, touches=False):
        """Run one builtin call and prove it did not spawn, fork, wait or open a descriptor.

        This is the law of the stage in one function: a state builtin is answered by the
        shell's own process, so `machine.stats()["spawn"]` does not move across it, and
        neither do the doors that need a pid at all. A call that touches no file and no
        environment — `:`, `shift`, `read`, `exit`, `set`, a bare assignment, and every
        refusal — is held to the stronger reading: *no* counted door may move.
        """
        before = dict(machine.stats())
        got = call()
        after = dict(machine.stats())
        moved = _moved(before, after)
        assert moved.get("spawn") == 0, (
            "%s moved machine.stats()[\"spawn\"]: %r -> %r — a state builtin runs in the "
            "shell's own process, and one that spawned a child would change nothing"
            % (what, before, after))
        shut = S7_DOORS if not touches else S7_CHILD_DOORS
        open_doors = {key: step for key, step in moved.items() if step and key in shut}
        assert not open_doors, (
            "%s moved the machine's own %r: %r -> %r" % (what, open_doors, before, after))
        assert tuple(got) == S7_BUILTIN_KEYS, (
            "%s answered the fields %r, and a builtin's answer is %r"
            % (what, tuple(got), S7_BUILTIN_KEYS))
        return got

    def _refused_quietly(machine, what, refuse, names=(), exc=None):
        """A shape refusal that must cost the machine nothing at all."""
        before = dict(machine.stats())
        refused = _refuses(exc, what, refuse, names=names)
        after = dict(machine.stats())
        moved = _moved(before, after)
        assert not any(step for key, step in moved.items() if key in S7_DOORS), (
            "%s moved the machine's own doors: %r -> %r" % (what, before, after))
        return refused

    def _record(**parts):
        """A shell record in the shape a session carries, with `parts` written over it.

        The keys are the parent's `SHELL_KEYS` ruling, which is the container stages 7, 8
        and 9 compose through: this stage must be answerable from exactly these.
        """
        record = {"variables": {}, "exported": (), "traps": (), "jobs": (),
                  "flags": {"errexit": False, "nounset": False}, "cwd": None,
                  "exit": None, "args": (), "stdin": b""}
        record.update(parts)
        return record

    def _s7_shell_keys(record):
        """The part of a record the parent's ruling names, in its own order."""
        return tuple(key for key in S7_SHELL_KEYS if key in record)

    def _under(base, name):
        """`name` under `base`, for a base that may be the root itself."""
        return base.rstrip("/") + "/" + name

    def _dir(machine, path):
        """Make `path` a directory of the machine's own filesystem and answer it."""
        machine.store(_under(path, "keep"), b"")
        return path

    def _s7_constants(s, rules):
        """The answer's four fields, the six kinds of state, and the words this stage owns."""
        assert tuple(s.BUILTIN_KEYS) == S7_BUILTIN_KEYS, (
            "BUILTIN_KEYS is %r, and a builtin's answer is the four fields %r"
            % (tuple(s.BUILTIN_KEYS), S7_BUILTIN_KEYS))
        assert tuple(s.BUILTIN_STATES) == S7_BUILTIN_STATES, (
            "BUILTIN_STATES is %r, and the kinds of state a builtin writes are %r"
            % (tuple(s.BUILTIN_STATES), S7_BUILTIN_STATES))
        assert len(set(S7_BUILTIN_STATES)) == len(S7_BUILTIN_STATES), (
            "this check's own kinds repeat: %r" % (S7_BUILTIN_STATES,))
        assert "unchanged" in s.BUILTIN_STATES, (
            "BUILTIN_STATES is %r, and a call that writes nothing answers %r"
            % (tuple(s.BUILTIN_STATES), "unchanged"))
        for key in ("variables", "exported", "flags", "cwd", "exit", "args", "stdin"):
            assert key in S7_SHELL_KEYS, (
                "this check's own record is missing %r" % (key,))
        for word, owner in S7_ELSEWHERE:
            assert word in rules.BUILTINS, (
                "%r is the shell's own builtin, and rules.BUILTINS is %r"
                % (word, tuple(rules.BUILTINS)))
            assert owner in ("stage 5", "stage 6"), (
                "this check has no owner for %r" % (word,))

    def _s7_is_builtin(s, world, rules):
        """`is_builtin` is true for `rules.BUILTINS` and for no other word at all."""
        words = tuple(rules.BUILTINS)
        assert len(set(words)) == len(words), (
            "rules.BUILTINS repeats a word: %r" % (words,))
        for word in words:
            assert s.is_builtin(word) is True, (
                "is_builtin(%r) is %r, and %r is one of the shell's own builtins"
                % (word, s.is_builtin(word), word))
        for word in S7_OTHER_WORDS:
            assert word not in words, (
                "this check's own fixture %r is a builtin after all" % (word,))
            assert s.is_builtin(word) is False, (
                "is_builtin(%r) is %r, and only %r are builtins of this shell"
                % (word, s.is_builtin(word), words))
        assert s.is_builtin("trap") is True and s.is_builtin("%1") is False, (
            "is_builtin answers a job spec as a builtin: %r/%r"
            % (s.is_builtin("trap"), s.is_builtin("%1")))
        for wrong in (7, None, b"cd", ("cd",), ["cd"], 0):
            _refuses(world.MachineError, "is_builtin(%r)" % (wrong,),
                     lambda wrong=wrong: s.is_builtin(wrong), names=(repr(wrong),))

    def _s7_wrong_shapes(s, world, rules, machine, record):
        """Every shape a caller can get wrong, refused by name and costing the machine nothing."""
        for word, owner in S7_ELSEWHERE:
            for words in (("INT", ""), (), ("%1",)):
                _refused_quietly(
                    machine, "run_builtin(%r, %r, ...)" % (word, words),
                    lambda word=word, words=words: s.run_builtin(machine, word, words, record),
                    names=(word, owner), exc=world.MachineError)
        for wrong in (7, None, b"cd", ("cd",), ["cd"], {"cd": 1}):
            _refused_quietly(
                machine, "run_builtin(%r, ...)" % (wrong,),
                lambda wrong=wrong: s.run_builtin(machine, wrong, (), record),
                names=(repr(wrong),), exc=world.MachineError)
        for wrong in ("cd", b"cd", 7, None, {"a": 1}):
            _refused_quietly(
                machine, "run_builtin(\"cd\", %r, ...)" % (wrong,),
                lambda wrong=wrong: s.run_builtin(machine, "cd", wrong, record),
                names=(repr(wrong),), exc=world.MachineError)
        for wrong, named in (((7,), "7"), (("cd", 7), "7"), ((b"x",), "b'x'"),
                             ((["x"],), "['x']"), ((None,), "None")):
            _refused_quietly(
                machine, "run_builtin(\"cd\", %r, ...)" % (wrong,),
                lambda wrong=wrong: s.run_builtin(machine, "cd", wrong, record),
                names=(named,), exc=world.MachineError)
        for wrong in (7, None, "state", [], ()):
            _refused_quietly(
                machine, "run_builtin(\"cd\", (), %r)" % (wrong,),
                lambda wrong=wrong: s.run_builtin(machine, "cd", (), wrong),
                names=(repr(wrong),), exc=world.MachineError)
        for wrong in ("x", 7, None, ["a"]):
            _refused_quietly(
                machine, "run_builtin(\"read\", (\"A\",), ...) with stdin %r" % (wrong,),
                lambda wrong=wrong: s.run_builtin(machine, "read", ("A",),
                                                  _record(stdin=wrong)),
                names=(repr(wrong),), exc=world.MachineError)
        for word in S7_OTHER_WORDS:
            _refused_quietly(
                machine, "run_builtin(%r, (), ...)" % (word,),
                lambda word=word: s.run_builtin(machine, word, (), record),
                names=(word,), exc=world.MachineError)

    def _s7_no_fork(s, world, rules):
        """Every builtin this stage answers, and the machine's own spawn count pinned across it.

        One machine, one record, one call per builtin: the wrapper asserts `["spawn"]` did
        not move for any of them, and the machine's process table at the end is the one a
        fresh machine of the same seed reported — so a stage that answered a state builtin
        in a child is caught here even when its statuses are all right.
        """
        machine = world.machine(7)
        fresh = world.machine(7)
        assert fresh.stats()["spawn"] == 0, (
            "a fresh machine reports %r spawns" % (fresh.stats()["spawn"],))
        before_processes = fresh.processes()
        assert machine.reapable() == (), (
            "a fresh machine already has %r reapable" % (machine.reapable(),))
        record = _record(args=("a", "b", "c"), stdin=b"one two\nthree\n")
        base = _dir(machine, _under(machine.cwd(), "s7fork"))
        calls = ((":", ("ignored", "words"), False),
                 ("cd", (base,), True),
                 ("exit", ("7",), False),
                 ("export", ("S7_FORK=1",), True),
                 ("read", ("A", "B"), False),
                 ("set", ("-o", "errexit"), False),
                 ("set", (), False),
                 ("shift", ("1",), False),
                 ("unset", ("S7_FORK",), True),
                 ("NAME=value", (), False))
        for name, words, touches in calls:
            got = _cost(machine, "run_builtin(%r, %r, ...)" % (name, words),
                        lambda name=name, words=words: s.run_builtin(machine, name, words,
                                                                    record),
                        touches=touches)
            assert got["name"] == name, (
                "run_builtin(%r, ...) answered the word %r" % (name, got["name"]))
            assert got["state"] in s.BUILTIN_STATES, (
                "run_builtin(%r, ...) answered the state %r, which is not one of %r"
                % (name, got["state"], tuple(s.BUILTIN_STATES)))
            assert isinstance(got["status"], int) and not isinstance(got["status"], bool), (
                "run_builtin(%r, ...) answered the status %r" % (name, got["status"]))
            assert isinstance(got["output"], bytes), (
                "run_builtin(%r, ...) answered the output %r, and a builtin writes bytes"
                % (name, got["output"]))
        assert machine.processes() == before_processes, (
            "the shell's builtins left the machine with the processes %r, and a fresh "
            "machine has %r" % (machine.processes(), before_processes))
        assert machine.reapable() == (), (
            "the shell's builtins left %r reapable — a state builtin that ran in a child "
            "would" % (machine.reapable(),))
        assert machine.stats()["spawn"] == 0, (
            "the whole workout spawned: %r" % (machine.stats(),))

    def _s7_colon(s, world, rules):
        """`:` answers 0 with unchanged state, its arguments ignored and nothing written."""
        machine = world.machine(7)
        record = _record(variables={"KEPT": "yes"}, args=("a",), stdin=b"line\n")
        before = (machine.cwd(), machine.env())
        for words in ((), ("anything", "at", "all"), ("1bad=2", "x")):
            got = _cost(machine, "run_builtin(':', %r, ...)" % (words,),
                        lambda words=words: s.run_builtin(machine, ":", words, record))
            assert got == {"name": ":", "status": rules.EXIT_OK, "state": "unchanged",
                           "output": b""}, (
                "`:` with %r answered %r, and `:` answers 0 with unchanged state and "
                "nothing written" % (words, got))
        assert (machine.cwd(), machine.env()) == before, (
            "`:` moved the machine: %r -> %r" % (before, (machine.cwd(), machine.env())))
        assert record == _record(variables={"KEPT": "yes"}, args=("a",), stdin=b"line\n"), (
            "`:` wrote into the shell's own record: %r" % (record,))

    def _s7_cd(s, world, rules):
        """`cd` moves the shell's own working directory, or leaves it exactly where it was."""
        machine = world.machine(7)
        record = _record()
        base = machine.cwd()
        home = _dir(machine, _under(base, "s7home"))
        other = _dir(machine, _under(base, "s7other"))
        a_file = _under(home, "file")
        machine.store(a_file, b"x")
        assert machine.is_dir(home) and machine.is_dir(other) and not machine.is_dir(a_file), (
            "the check built its own fixture wrongly: %r/%r" % (home, a_file))

        got = _cost(machine, "cd %r" % (home,),
                    lambda: s.run_builtin(machine, "cd", (home,), record), touches=True)
        assert got == {"name": "cd", "status": rules.EXIT_OK, "state": "cwd", "output": b""}, (
            "a cd into a directory answered %r" % (got,))
        assert machine.cwd() == home, (
            "cd answered the state %r and the machine's own cwd is %r, not %r"
            % (got["state"], machine.cwd(), home))
        assert record["cwd"] == home, (
            "cd left the shell's own cwd at %r, not %r" % (record["cwd"], home))

        # No argument: the shell's own HOME first, then the machine's own environment.
        record["variables"]["HOME"] = other
        machine.setenv("HOME", home)
        got = _cost(machine, "cd with no argument and a shell HOME",
                    lambda: s.run_builtin(machine, "cd", (), record), touches=True)
        assert machine.cwd() == other and record["cwd"] == other and got["state"] == "cwd", (
            "cd with no argument went to %r, and the shell's own HOME says %r"
            % (machine.cwd(), other))
        del record["variables"]["HOME"]
        got = _cost(machine, "cd with no argument and only the machine's HOME",
                    lambda: s.run_builtin(machine, "cd", (), record), touches=True)
        assert machine.cwd() == home and record["cwd"] == home, (
            "with no shell HOME, cd went to %r, and the machine's own HOME says %r"
            % (machine.cwd(), home))

        # A word that is not a directory: the failure is answered and nothing moves.
        for place, why in ((a_file, "a file"), (_under(home, "missing"), "nothing at all")):
            before = (machine.cwd(), record["cwd"])
            got = _cost(machine, "cd %r (%s)" % (place, why),
                        lambda place=place: s.run_builtin(machine, "cd", (place,), record),
                        touches=True)
            assert got["status"] == rules.EXIT_FAILURE and got["state"] == "unchanged", (
                "cd into %s answered %r, and a directory that is not one is EXIT_FAILURE "
                "with the state unchanged" % (why, got))
            assert got["output"] == b"", (
                "cd into %s wrote %r to the shell's stdout" % (why, got["output"]))
            assert (machine.cwd(), record["cwd"]) == before, (
                "cd into %s moved the working directory: %r -> %r"
                % (why, before, (machine.cwd(), record["cwd"])))

        # No HOME anywhere: a failure, not a crash and not a move.
        if machine.getenv("HOME") is not None:
            machine.unsetenv("HOME")
        assert machine.getenv("HOME") is None and "HOME" not in record["variables"]
        before = (machine.cwd(), record["cwd"])
        got = _cost(machine, "cd with no HOME at all",
                    lambda: s.run_builtin(machine, "cd", (), record), touches=True)
        assert got["status"] == rules.EXIT_FAILURE and got["state"] == "unchanged", (
            "cd with no HOME answered %r" % (got,))
        assert (machine.cwd(), record["cwd"]) == before, (
            "cd with no HOME moved the working directory: %r -> %r"
            % (before, (machine.cwd(), record["cwd"])))

        # Two words: a usage complaint, and the directory is not touched.
        machine.chdir(home)
        record["cwd"] = home
        before = (machine.cwd(), record["cwd"])
        got = _cost(machine, "cd %r %r" % (home, other),
                    lambda: s.run_builtin(machine, "cd", (home, other), record),
                    touches=False)
        assert got["status"] == rules.EXIT_BAD_USAGE and got["state"] == "unchanged", (
            "cd with two words answered %r" % (got,))
        assert got["output"] == _usage_of("cd"), (
            "cd with two words wrote %r, and its usage line is %r"
            % (got["output"], _usage_of("cd")))
        assert (machine.cwd(), record["cwd"]) == before, (
            "a refused cd moved the working directory: %r -> %r"
            % (before, (machine.cwd(), record["cwd"])))

        # A relative word is the shell's own arithmetic, resolved against machine.cwd().
        inside = _dir(machine, _under(home, "s7rel"))
        for word, want in (("s7rel", inside), ("./s7rel", inside), ("s7rel/../s7rel", inside),
                           ("..", base), ("../s7other", other), ("", home), ("/", "/"),
                           ("/s7home/./s7rel/..", home), ("/nope/..", "/")):
            got = _cost(machine, "cd %r, resolved against %r" % (word, machine.cwd()),
                        lambda word=word: s.run_builtin(machine, "cd", (word,), record),
                        touches=True)
            assert got["status"] == rules.EXIT_OK, (
                "cd %r from %r answered %r" % (word, machine.cwd(), got))
            assert machine.cwd() == want, (
                "cd %r from %r landed on %r, and the shell's own arithmetic says %r"
                % (word, machine.cwd(), machine.cwd(), want))
            assert record["cwd"] == want, (
                "cd %r left the shell's record at %r, not %r" % (word, record["cwd"], want))
            machine.chdir(home)
            record["cwd"] = home

    def _s7_export(s, world, rules):
        """`export` sets the shell's variable and the machine's environment together."""
        machine = world.machine(7)
        record = _record()
        got = _cost(machine, "export S7_A=1",
                    lambda: s.run_builtin(machine, "export", ("S7_A=1",), record),
                    touches=True)
        assert got == {"name": "export", "status": rules.EXIT_OK, "state": "env",
                       "output": b""}, (
            "export NAME=value answered %r" % (got,))
        assert machine.getenv("S7_A") == "1", (
            "export S7_A=1 left the machine's environment holding %r"
            % (machine.getenv("S7_A"),))
        assert record["variables"] == {"S7_A": "1"}, (
            "export left the shell's variables holding %r" % (record["variables"],))
        assert tuple(record["exported"]) == ("S7_A",), (
            "export left the shell's exported list at %r" % (record["exported"],))

        got = _cost(machine, "export S7_B=2 S7_C=3",
                    lambda: s.run_builtin(machine, "export", ("S7_B=2", "S7_C=3"), record),
                    touches=True)
        assert (machine.getenv("S7_B"), machine.getenv("S7_C")) == ("2", "3"), (
            "a second export did not reach the machine: %r" % (machine.env(),))
        assert tuple(record["exported"]) == ("S7_A", "S7_B", "S7_C"), (
            "the exported list is %r, and every exported name belongs in it"
            % (record["exported"],))
        assert machine.env() == tuple(sorted(machine.env())), (
            "the machine's own environment is not sorted: %r" % (machine.env(),))

        # `export NAME` exports a variable the shell already holds — and a bare
        # `NAME=value` word does not export one at all.
        s.run_builtin(machine, "S7_D=4", (), record)
        assert record["variables"]["S7_D"] == "4" and machine.getenv("S7_D") is None, (
            "a bare assignment reached the machine's own environment, which is the whole "
            "difference between it and an export: %r" % (machine.env(),))
        got = _cost(machine, "export S7_D",
                    lambda: s.run_builtin(machine, "export", ("S7_D",), record),
                    touches=True)
        assert got["status"] == rules.EXIT_OK and got["state"] == "env", (
            "export of a variable the shell holds answered %r" % (got,))
        assert machine.getenv("S7_D") == "4", (
            "export S7_D left the machine holding %r" % (machine.getenv("S7_D"),))
        assert "S7_D" in record["exported"]

        # `export NAME` for a name the shell does not hold: marked, and not in the machine.
        got = _cost(machine, "export S7_NOPE",
                    lambda: s.run_builtin(machine, "export", ("S7_NOPE",), record),
                    touches=True)
        assert got["status"] == rules.EXIT_OK and "S7_NOPE" in record["exported"], (
            "export of a name the shell does not hold answered %r and left %r"
            % (got, record["exported"]))
        assert machine.getenv("S7_NOPE") is None, (
            "the machine holds %r after an export of a name the shell never set"
            % (machine.getenv("S7_NOPE"),))

        # No argument: the machine's own environment, as the lines it holds.
        assert machine.env() != (), "the export fixture needs an environment to list"
        got = _cost(machine, "export with no argument",
                    lambda: s.run_builtin(machine, "export", (), record), touches=True)
        want = b"".join((line + "\n").encode("utf-8") for line in machine.env())
        assert got == {"name": "export", "status": rules.EXIT_OK, "state": "unchanged",
                       "output": want}, (
            "export with no argument answered %r, and the machine's own environment is %r"
            % (got, machine.env()))

        # One bad word and nothing at all is exported.
        record["exported"] = ()
        record["variables"] = {}
        machine2 = world.machine(7)
        for words in (("S7_F=5", "1bad=6"), ("S7_F=5", "=6"), ("1bad",), ("a b",),
                      ("S7_F=5", "bad-name")):
            before = (machine2.env(), dict(record["variables"]), record["exported"])
            got = _cost(machine2, "export %r" % (words,),
                        lambda words=words: s.run_builtin(machine2, "export", words, record))
            assert got["status"] == rules.EXIT_BAD_USAGE and got["state"] == "unchanged", (
                "export %r answered %r, and a word that is not a name is EXIT_BAD_USAGE"
                % (words, got))
            assert got["output"] == _usage_of("export"), (
                "export %r wrote %r instead of its usage line %r"
                % (words, got["output"], _usage_of("export")))
            assert (machine2.env(), dict(record["variables"]), record["exported"]) == before, (
                "export %r exported something before it found the bad word: %r -> %r"
                % (words, before, (machine2.env(), dict(record["variables"]),
                                   record["exported"])))

        # The policy's own limit on a name's length is the boundary, not one either side.
        limit = rules.LIMITS["var_name"]
        longest = "S" * limit
        got = _cost(machine2, "export of a name of exactly the limit",
                    lambda: s.run_builtin(machine2, "export", (longest + "=1",), record),
                    touches=True)
        assert got["status"] == rules.EXIT_OK and machine2.getenv(longest) == "1", (
            "a name of exactly rules.LIMITS[\"var_name\"] (%d) answered %r"
            % (limit, got))
        got = _cost(machine2, "export of a name one byte over the limit",
                    lambda: s.run_builtin(machine2, "export", (longest + "S=1",), record))
        assert got["status"] == rules.EXIT_BAD_USAGE and got["output"] == _usage_of("export"), (
            "a name one byte over the limit answered %r" % (got,))
        assert machine2.getenv(longest + "S") is None, (
            "a name over the policy's limit reached the machine's environment")

    def _s7_unset(s, world, rules):
        """`unset` removes the shell's variable and the machine's own, both or neither."""
        machine = world.machine(7)
        record = _record()
        s.run_builtin(machine, "export", ("S7_U=1",), record)
        assert machine.getenv("S7_U") == "1" and record["variables"]["S7_U"] == "1"
        got = _cost(machine, "unset S7_U",
                    lambda: s.run_builtin(machine, "unset", ("S7_U",), record), touches=True)
        assert got == {"name": "unset", "status": rules.EXIT_OK, "state": "env",
                       "output": b""}, (
            "unset NAME answered %r" % (got,))
        assert machine.getenv("S7_U") is None, (
            "unset left the machine's environment holding %r" % (machine.getenv("S7_U"),))
        assert "S7_U" not in record["variables"], (
            "unset left the shell's variables holding %r" % (record["variables"],))
        assert tuple(record["exported"]) == (), (
            "unset left the shell's exported list at %r" % (record["exported"],))

        # A name the shell never set is not a failure, and changes nothing.
        before = machine.env()
        got = _cost(machine, "unset S7_NOPE",
                    lambda: s.run_builtin(machine, "unset", ("S7_NOPE",), record), touches=True)
        assert got["status"] == rules.EXIT_OK and got["state"] == "env", (
            "unset of a name that was never set answered %r" % (got,))
        assert machine.env() == before, (
            "unset of a name that was never set moved the environment: %r -> %r"
            % (before, machine.env()))

        # A variable the shell holds but never exported is removed from the shell alone.
        s.run_builtin(machine, "S7_V=2", (), record)
        assert machine.getenv("S7_V") is None and record["variables"]["S7_V"] == "2"
        got = _cost(machine, "unset S7_V",
                    lambda: s.run_builtin(machine, "unset", ("S7_V",), record), touches=True)
        assert got["status"] == rules.EXIT_OK and "S7_V" not in record["variables"], (
            "unset of an unexported variable answered %r and left %r"
            % (got, record["variables"]))

        # No words: 0, unchanged, nothing written.
        got = _cost(machine, "unset with no words",
                    lambda: s.run_builtin(machine, "unset", (), record))
        assert got == {"name": "unset", "status": rules.EXIT_OK, "state": "unchanged",
                       "output": b""}, (
            "unset with no words answered %r" % (got,))

        # One bad word and nothing at all is removed.
        s.run_builtin(machine, "export", ("S7_W=3",), record)
        assert machine.getenv("S7_W") == "3"
        for words in (("S7_W", "1bad"), ("=1",), ("bad-name",), ("a b",)):
            before = (machine.env(), dict(record["variables"]), record["exported"])
            got = _cost(machine, "unset %r" % (words,),
                        lambda words=words: s.run_builtin(machine, "unset", words, record))
            assert got["status"] == rules.EXIT_BAD_USAGE and got["state"] == "unchanged", (
                "unset %r answered %r" % (words, got))
            assert got["output"] == _usage_of("unset"), (
                "unset %r wrote %r instead of its usage line %r"
                % (words, got["output"], _usage_of("unset")))
            assert (machine.env(), dict(record["variables"]), record["exported"]) == before, (
                "unset %r removed something before it found the bad word: %r -> %r"
                % (words, before, (machine.env(), dict(record["variables"]),
                                   record["exported"])))
        assert machine.getenv("S7_W") == "3", (
            "a refused unset removed the variable anyway")

    def _s7_set(s, world, rules):
        """`set` writes the shell's own flags, and answers a usage line for a bad one."""
        machine = world.machine(7)
        record = _record()
        got = _cost(machine, "set -o errexit",
                    lambda: s.run_builtin(machine, "set", ("-o", "errexit"), record))
        assert got == {"name": "set", "status": rules.EXIT_OK, "state": "options",
                       "output": b""}, (
            "set -o errexit answered %r" % (got,))
        assert record["flags"]["errexit"] is True, (
            "set -o errexit left the flags at %r" % (record["flags"],))

        got = _cost(machine, "set +o errexit",
                    lambda: s.run_builtin(machine, "set", ("+o", "errexit"), record))
        assert got["state"] == "options" and record["flags"]["errexit"] is False, (
            "set +o errexit answered %r and left %r" % (got, record["flags"]))

        # The letter and the name are the same flag, both ways round, and the two flags
        # do not overwrite each other.
        for words, want_e, want_u in ((("-e",), True, False), (("+e",), False, False),
                                      (("-e",), True, False), (("-u",), True, True),
                                      (("+u",), True, False), (("-o", "errexit"), True, False),
                                      (("-o", "nounset"), True, True)):
            got = _cost(machine, "set %r" % (words,),
                        lambda words=words: s.run_builtin(machine, "set", words, record))
            assert got["status"] == rules.EXIT_OK and got["state"] == "options", (
                "set %r answered %r" % (words, got))
            assert (record["flags"]["errexit"], record["flags"]["nounset"]) == (want_e, want_u), (
                "after set %r the flags are %r, and they should be errexit=%r nounset=%r"
                % (words, record["flags"], want_e, want_u))

        # A bare `-o` asks for the flags instead of setting one.
        got = _cost(machine, "set -o",
                    lambda: s.run_builtin(machine, "set", ("-o",), record))
        assert got["status"] == rules.EXIT_OK and got["state"] == "unchanged", (
            "a bare set -o answered %r" % (got,))
        assert got["output"] == b"errexit on\nnounset on\n", (
            "set -o wrote %r, and with both flags on it writes %r"
            % (got["output"], b"errexit on\nnounset on\n"))

        # No words at all: the shell's own variables, sorted, as NAME=value lines.
        record["variables"] = {"S7_B": "2", "S7_A": "1"}
        got = _cost(machine, "set with no words",
                    lambda: s.run_builtin(machine, "set", (), record))
        assert got == {"name": "set", "status": rules.EXIT_OK, "state": "unchanged",
                       "output": b"S7_A=1\nS7_B=2\n"}, (
            "set with no words answered %r" % (got,))

        # A call that is not an option this shell owns: the usage line, and no flag moved.
        record["flags"] = {"errexit": True, "nounset": False}
        before = dict(record["flags"])
        for words in (("-o", "nosuchoption"), ("-x",), ("+x",), ("-z",), ("-o", "e"),
                      ("-e", "errexit"), ("-o", "errexit", "nounset"), ("errexit",),
                      ("--errexit",), ("-",), ("+o", "nosuch"), ("-o", ""), ("-u", "1")):
            got = _cost(machine, "set %r" % (words,),
                        lambda words=words: s.run_builtin(machine, "set", words, record))
            assert got["status"] == rules.EXIT_BAD_USAGE and got["state"] == "unchanged", (
                "set %r answered %r, and an option this shell does not own is "
                "EXIT_BAD_USAGE" % (words, got))
            assert got["output"] == _usage_of("set"), (
                "set %r wrote %r instead of its usage line %r"
                % (words, got["output"], _usage_of("set")))
            assert record["flags"] == before, (
                "a refused set %r moved the flags: %r -> %r" % (words, before, record["flags"]))

    def _s7_shift(s, world, rules):
        """`shift` moves the shell's positional parameters, or refuses without moving them."""
        machine = world.machine(7)
        record = _record(args=("a", "b", "c"))
        got = _cost(machine, "shift with no argument",
                    lambda: s.run_builtin(machine, "shift", (), record))
        assert got == {"name": "shift", "status": rules.EXIT_OK, "state": "variables",
                       "output": b""}, (
            "shift with no argument answered %r" % (got,))
        assert tuple(record["args"]) == ("b", "c"), (
            "shift with no argument left the parameters at %r" % (record["args"],))

        # A count that is a count: the parameters move down by exactly that many, and a
        # count past the end is the failure with the parameters left where they were.
        for word, want in (("0", ("a", "b", "c")), ("00", ("a", "b", "c")), ("1", ("b", "c")),
                           ("2", ("c",)), ("3", ()), ("4", None), ("007", None),
                           ("10", None)):
            args = ("a", "b", "c")
            record["args"] = args
            got = _cost(machine, "shift %r of %r" % (word, args),
                        lambda word=word: s.run_builtin(machine, "shift", (word,), record))
            if want is None:
                assert got["status"] == rules.EXIT_FAILURE and got["state"] == "unchanged", (
                    "shift %r past the end of %r answered %r" % (word, args, got))
                assert got["output"] == b"", (
                    "shift %r past the end wrote %r" % (word, got["output"]))
                assert tuple(record["args"]) == args, (
                    "shift %r past the end left the parameters at %r, not %r"
                    % (word, record["args"], args))
                continue
            assert got["status"] == rules.EXIT_OK and got["state"] == "variables", (
                "shift %r of %r answered %r" % (word, args, got))
            assert tuple(record["args"]) == want, (
                "shift %r of %r left the parameters at %r, and this check says %r"
                % (word, args, record["args"], want))

        # A count that is not a count at all: a usage line, and the parameters are not
        # touched. A bare run of digits is the only thing `shift` takes.
        for word in ("x", "-1", "+1", "1 ", "1.0", "1x", " ", "one", "-", "--1", ""):
            record["args"] = ("a", "b")
            got = _cost(machine, "shift %r" % (word,),
                        lambda word=word: s.run_builtin(machine, "shift", (word,), record))
            assert got["status"] == rules.EXIT_BAD_USAGE and got["state"] == "unchanged", (
                "shift %r answered %r, and that is not a count" % (word, got))
            assert got["output"] == _usage_of("shift"), (
                "shift %r wrote %r instead of its usage line %r"
                % (word, got["output"], _usage_of("shift")))
            assert tuple(record["args"]) == ("a", "b"), (
                "a refused shift %r moved the parameters to %r" % (word, record["args"]))

        # Past the end from every end of the scale, an empty set included.
        for args, word in (((), "1"), (("a",), "2"), (("a", "b"), "3"),
                           (("a", "b", "c"), "4"), (("a", "b", "c"), "1000")):
            record["args"] = args
            got = _cost(machine, "shift %r with %r of parameters" % (word, args),
                        lambda word=word: s.run_builtin(machine, "shift", (word,), record))
            assert got["status"] == rules.EXIT_FAILURE and got["state"] == "unchanged", (
                "shift %r past the end of %r answered %r" % (word, args, got))
            assert tuple(record["args"]) == args, (
                "shift %r past the end left the parameters at %r, not %r"
                % (word, record["args"], args))

        # Two words are not a count either.
        record["args"] = ("a", "b")
        got = _cost(machine, "shift 1 1",
                    lambda: s.run_builtin(machine, "shift", ("1", "1"), record))
        assert got["status"] == rules.EXIT_BAD_USAGE and tuple(record["args"]) == ("a", "b"), (
            "shift with two words answered %r and left %r" % (got, record["args"]))

        # The count is the policy's own limit, not the word's digits: a huge count is
        # still a count, and it is still past the end.
        record["args"] = ("a",)
        huge = "9" * (rules.LIMITS["var_name"] + 1)
        got = _cost(machine, "shift %r" % (huge,),
                    lambda: s.run_builtin(machine, "shift", (huge,), record))
        assert got["status"] == rules.EXIT_FAILURE and tuple(record["args"]) == ("a",), (
            "a count of %d digits answered %r and left %r" % (len(huge), got, record["args"]))

    def _s7_read(s, world, rules):
        """`read` consumes one line of the shell's own input into the names it was given."""
        machine = world.machine(7)
        record = _record(stdin=b"alpha beta gamma\nsecond line\n")
        got = _cost(machine, "read A B",
                    lambda: s.run_builtin(machine, "read", ("A", "B"), record))
        assert got == {"name": "read", "status": rules.EXIT_OK, "state": "variables",
                       "output": b""}, (
            "read A B answered %r" % (got,))
        assert record["variables"] == {"A": "alpha", "B": "beta gamma"}, (
            "read A B put %r into the shell's variables, and the last name is given the "
            "rest of the line" % (record["variables"],))
        assert record["stdin"] == b"second line\n", (
            "read left the shell's input at %r, and the line it read is consumed"
            % (record["stdin"],))

        got = _cost(machine, "read A B C",
                    lambda: s.run_builtin(machine, "read", ("A", "B", "C"), record))
        assert record["variables"] == {"A": "second", "B": "line", "C": ""}, (
            "read A B C over a two-word line put %r into the variables, and a name past "
            "the line's fields is the empty word" % (record["variables"],))
        assert record["stdin"] == b""

        # A last line with no newline is still a line, and the fields' own spacing survives.
        for raw, words, want, rest in (
                (b"last", ("A",), {"A": "last"}, b""),
                (b"one\n", ("A", "B"), {"A": "one", "B": ""}, b""),
                (b"   spaced   out  \n", ("A",), {"A": "spaced   out  "}, b""),
                (b"   spaced   out  \n", ("A", "B"), {"A": "spaced", "B": "out  "}, b""),
                (b"\nstill here\n", ("A", "B"), {"A": "", "B": ""}, b"still here\n"),
                (b"a\tb\tc\n", ("A", "B"), {"A": "a", "B": "b\tc"}, b"")):
            record["variables"] = {}
            record["stdin"] = raw
            got = _cost(machine, "read %r over %r" % (words, raw),
                        lambda words=words: s.run_builtin(machine, "read", words, record))
            assert got["status"] == rules.EXIT_OK and got["state"] == "variables", (
                "read %r over %r answered %r" % (words, raw, got))
            assert record["variables"] == want, (
                "read %r over %r put %r into the variables, and this check says %r"
                % (words, raw, record["variables"], want))
            assert record["stdin"] == rest, (
                "read %r over %r left the input at %r, not %r"
                % (words, raw, record["stdin"], rest))

        # The end of input: a failure, and the variables the shell already held stay.
        record["variables"] = {"KEPT": "yes"}
        record["stdin"] = b""
        got = _cost(machine, "read at the end of input",
                    lambda: s.run_builtin(machine, "read", ("A", "B"), record))
        assert got == {"name": "read", "status": rules.EXIT_FAILURE, "state": "unchanged",
                       "output": b""}, (
            "read at the end of input answered %r, and the end of input is EXIT_FAILURE "
            "with the state unchanged" % (got,))
        assert record["variables"] == {"KEPT": "yes"}, (
            "read at the end of input wrote %r into the variables" % (record["variables"],))
        assert record["stdin"] == b""

        # A call with nothing to read into, and a name that is not a name: a usage line,
        # and the input is not consumed.
        for words, named in (((), None), (("1bad",), "1bad"), (("A", "1bad"), "1bad"),
                             (("bad-name",), "bad-name"), (("",), None)):
            record["stdin"] = b"one two\n"
            record["variables"] = {}
            got = _cost(machine, "read %r" % (words,),
                        lambda words=words: s.run_builtin(machine, "read", words, record))
            assert got["status"] == rules.EXIT_BAD_USAGE and got["state"] == "unchanged", (
                "read %r answered %r" % (words, got))
            assert got["output"] == _usage_of("read"), (
                "read %r wrote %r instead of its usage line %r"
                % (words, got["output"], _usage_of("read")))
            assert record["stdin"] == b"one two\n" and record["variables"] == {}, (
                "a refused read %r consumed the shell's own input: %r/%r"
                % (words, record["stdin"], record["variables"]))

    def _s7_exit(s, world, rules):
        """`exit` masks its status by the policy's own limit, and writes it to the record."""
        machine = world.machine(7)
        record = _record()
        limit = rules.LIMITS["status"]
        assert limit == 255, "rules.LIMITS[\"status\"] is %r" % (limit,)
        cases = (("0", 0), ("1", 1), ("2", 2), ("7", 7), ("127", 127), ("128", 128),
                 ("255", 255), ("256", 256 & limit), ("257", 257 & limit),
                 ("511", 511 & limit), ("512", 512 & limit), ("1000", 1000 & limit),
                 ("-1", -1 & limit), ("-2", -2 & limit), ("-255", -255 & limit),
                 ("-256", -256 & limit), ("-257", -257 & limit), ("007", 7),
                 ("0000", 0), ("999999", 999999 & limit))
        for word, want in cases:
            got = _cost(machine, "exit %s" % (word,),
                        lambda word=word: s.run_builtin(machine, "exit", (word,), record))
            assert got == {"name": "exit", "status": want, "state": "exit",
                           "output": b""}, (
                "exit %s answered %r, and %s & %d is %d"
                % (word, got, word, limit, want))
            assert record["exit"] == want, (
                "exit %s left the shell's own exit at %r, not %r"
                % (word, record["exit"], want))
            assert 0 <= got["status"] <= limit, (
                "exit %s answered the status %r, which is not a status"
                % (word, got["status"]))

        # A bare `exit`: the shell's own last status is the caller's, and with no
        # argument the answer is EXIT_OK.
        record["exit"] = None
        got = _cost(machine, "exit with no argument",
                    lambda: s.run_builtin(machine, "exit", (), record))
        assert got["status"] == rules.EXIT_OK and got["state"] == "exit", (
            "a bare exit answered %r" % (got,))
        assert record["exit"] == rules.EXIT_OK, (
            "a bare exit left the shell's own exit at %r" % (record["exit"],))

        # A word that is not an integer, and two words: a usage line and nothing written.
        for words, named in ((("x",), "x"), (("1.5",), "1.5"), (("",), ""), (("1 2",), "1 2"),
                             (("-",), "-"), (("+1",), "+1"), (("0x10",), "0x10"),
                             (("1", "2"), "1")):
            record["exit"] = 99
            got = _cost(machine, "exit %r" % (words,),
                        lambda words=words: s.run_builtin(machine, "exit", words, record))
            assert got["status"] == rules.EXIT_BAD_USAGE and got["state"] == "unchanged", (
                "exit %r answered %r" % (words, got))
            assert got["output"] == _usage_of("exit"), (
                "exit %r wrote %r instead of its usage line %r"
                % (words, got["output"], _usage_of("exit")))
            assert record["exit"] == 99, (
                "a refused exit %r wrote the shell's own exit: %r" % (words, record["exit"]))

        # The shell's own process is not in the machine's table: `exit` names no pid and
        # leaves no process behind.
        assert machine.processes() == () and machine.reapable() == (), (
            "exit left the machine holding %r/%r" % (machine.processes(),
                                                     machine.reapable()))

    def _s7_assignment(s, world, rules):
        """A bare `NAME=value` word sets the shell's variable and not the machine's environment."""
        machine = world.machine(7)
        seeded = machine.env()
        record = _record()
        got = _cost(machine, "the word S7_P=1",
                    lambda: s.run_builtin(machine, "S7_P=1", (), record))
        assert got == {"name": "S7_P=1", "status": rules.EXIT_OK, "state": "variables",
                       "output": b""}, (
            "the word S7_P=1 answered %r" % (got,))
        assert record["variables"] == {"S7_P": "1"}, (
            "the word S7_P=1 left the shell's variables at %r" % (record["variables"],))
        assert tuple(record["exported"]) == (), (
            "the word S7_P=1 exported the name: %r" % (record["exported"],))
        assert machine.getenv("S7_P") is None, (
            "a bare assignment reached the machine's own environment (%r), and §4.7 says "
            "the difference between it and an export is that it does not"
            % (machine.getenv("S7_P"),))
        assert machine.env() == seeded, (
            "a bare assignment left the machine holding %r, where the seed held %r"
            % (machine.env(), seeded))

        # The same name through `export` does reach it: that is the difference.
        got = _cost(machine, "export S7_P=1",
                    lambda: s.run_builtin(machine, "export", ("S7_P=1",), record),
                    touches=True)
        assert machine.getenv("S7_P") == "1", (
            "export S7_P=1 left the machine holding %r" % (machine.getenv("S7_P"),))

        # And after an unset, the assignment form alone does not put it back in the
        # environment while the shell's own variable comes back.
        s.run_builtin(machine, "unset", ("S7_P",), record)
        assert machine.getenv("S7_P") is None and "S7_P" not in record["variables"]
        got = _cost(machine, "the word S7_P=2",
                    lambda: s.run_builtin(machine, "S7_P=2", (), record))
        assert record["variables"]["S7_P"] == "2" and machine.getenv("S7_P") is None, (
            "the second assignment left %r/%r" % (record["variables"],
                                                  machine.getenv("S7_P")))

        # The value is the whole right-hand side, `=` and all; an empty value is a value.
        for word, name, value in (("S7_Q=a=b", "S7_Q", "a=b"), ("S7_R=", "S7_R", ""),
                                  ("S7_S= ", "S7_S", " "), ("S7_T=_", "S7_T", "_")):
            got = _cost(machine, "the word %r" % (word,),
                        lambda word=word: s.run_builtin(machine, word, (), record))
            assert got["name"] == word and got["state"] == "variables", (
                "the word %r answered %r" % (word, got))
            assert record["variables"][name] == value, (
                "the word %r left %r at %r, not %r"
                % (word, name, record["variables"].get(name), value))
            assert machine.getenv(name) is None, (
                "the word %r reached the machine's own environment" % (word,))

    def _s7_dump(machine, record, answers):
        """One comparable reading of a whole run: the answers, the record and the machine."""
        return (tuple(answers),
                tuple(sorted(record.get("variables", {}).items())),
                tuple(record.get("exported") or ()),
                tuple(sorted((record.get("flags") or {}).items())),
                tuple(record.get("args") or ()),
                record.get("stdin"), record.get("cwd"), record.get("exit"),
                tuple(record.get("traps") or ()), tuple(record.get("jobs") or ()),
                machine.cwd(), machine.env(), machine.stats()["spawn"])

    def _s7_twice(s, world, rules):
        """One whole workload run twice, on two fresh machines: the two readings are equal."""
        def once():
            machine = world.machine(7)
            record = _record(args=("a", "b", "c"), stdin=b"one two\nthree four\n")
            base = _dir(machine, _under(machine.cwd(), "s7twice"))
            answers = []
            for name, words in ((":", ()), ("cd", (base,)), ("set", ("-e",)),
                                ("export", ("S7_T=1",)), ("export", ()), ("set", ("-o",)),
                                ("read", ("A", "B")), ("shift", ("1",)), ("S7_U=2", ()),
                                ("unset", ("S7_T",)), ("export", ()), ("set", ()),
                                ("read", ("C",)), ("exit", ("257",)), ("cd", ()),
                                ("trap", ("INT", "")), ("kill", ("-TERM", "1")), ("wait", ())):
                if name in ("trap", "kill", "wait"):
                    try:
                        s.run_builtin(machine, name, words, record)
                    except world.MachineError as refused:
                        answers.append(("refused", name, str(refused)))
                        continue
                    raise AssertionError(
                        "%r was answered instead of refused — %s owns it"
                        % (name, dict(S7_ELSEWHERE)[name]))
                answers.append(s.run_builtin(machine, name, words, record))
            return _s7_dump(machine, record, answers)

        assert once() == once(), (
            "two runs of one workload answered differently, so an answer is not a function "
            "of the record it was handed: a stage that kept its own state between calls, or "
            "read a set where it should have read the record, is what this catches")

    """Every assertion the contract's §4.7 makes about this stage."""
    import machine as world
    import rules
    import stage_07 as s
    _s7_constants(s, rules)
    _s7_is_builtin(s, world, rules)
    _s7_wrong_shapes(s, world, rules, world.machine(7), _record())
    _s7_no_fork(s, world, rules)
    _s7_colon(s, world, rules)
    _s7_cd(s, world, rules)
    _s7_export(s, world, rules)
    _s7_unset(s, world, rules)
    _s7_set(s, world, rules)
    _s7_shift(s, world, rules)
    _s7_read(s, world, rules)
    _s7_exit(s, world, rules)
    _s7_assignment(s, world, rules)
    _s7_twice(s, world, rules)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    S8_LISTS_KEYS = ("statuses", "status", "stopped", "skipped", "error")

    S8_STATUS_KINDS = ("plain", "condition", "and-or-left", "negated",
                       "pipeline-but-last", "while-condition", "if-condition")

    S8_CONNECTORS = ("&&", "||", ";", "&")

    S8_JOB_KEYS = ("job", "pid", "state", "status", "command")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("course.py", "machine.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked against
        the message: an exception of the right family raised for the wrong reason is not
        the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return
        except NotImplementedError:
            raise
        except Exception as wrong:                               # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, wrong))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _state(machine, errexit=False, nounset=False, exit=None):
        """A shell state of the check's own, over a fresh machine's cwd."""
        return {"variables": {}, "exported": (), "traps": (), "jobs": (),
                "flags": {"errexit": errexit, "nounset": nounset},
                "cwd": machine.cwd(), "exit": exit, "args": (), "stdin": b""}

    def _row(answer, position):
        """The answer's `position`-th status row, or the mistake named."""
        assert position < len(answer["statuses"]), (
            "the line answered %d rows and the check asked for row %d"
            % (len(answer["statuses"]), position))
        return answer["statuses"][position]

    def _checked(answer, what):
        """The answer's shape: `LISTS_KEYS`, rows with a known kind and a status."""
        assert isinstance(answer, dict) and tuple(answer) == S8_LISTS_KEYS, (
            "%s answered %r, and a line answers %r" % (what, answer, S8_LISTS_KEYS))
        assert isinstance(answer["statuses"], tuple), (
            "%s answered statuses %r, and they are a tuple of rows"
            % (what, answer["statuses"]))
        for row in answer["statuses"]:
            assert isinstance(row, dict) and tuple(row) == ("status", "kind",
                                                            "command"), (
                "%s answered the row %r, and a row is (status, kind, command)"
                % (what, row))
            assert row["kind"] in S8_STATUS_KINDS, (
                "%s answered the kind %r, and a kind is one of the seven"
                % (what, row["kind"]))
            assert isinstance(row["status"], int) and not isinstance(row["status"],
                                                                     bool), (
                "%s answered the status %r, and a status is an int"
                % (what, row["status"]))
        assert isinstance(answer["status"], int) and not isinstance(answer["status"],
                                                                    bool), (
            "%s answered the status %r, and it is an int" % (what, answer["status"]))
        assert isinstance(answer["stopped"], bool), (
            "%s answered stopped %r, and it is a bool" % (what, answer["stopped"]))
        assert isinstance(answer["skipped"], int) and not isinstance(
            answer["skipped"], bool) and answer["skipped"] >= 0, (
            "%s answered skipped %r, and it is a count" % (what, answer["skipped"]))
        return answer

    def _s8_constants(s, rules):
        """`LISTS_KEYS`, the seven kinds, and `exempt` agreeing with the rules."""
        import machine as world
        assert tuple(s.LISTS_KEYS) == S8_LISTS_KEYS, (
            "LISTS_KEYS is %r; a line answers %r" % (s.LISTS_KEYS, S8_LISTS_KEYS))
        assert tuple(s.STATUS_KINDS) == S8_STATUS_KINDS, (
            "STATUS_KINDS is %r; the kinds are %r" % (s.STATUS_KINDS, S8_STATUS_KINDS))
        exempted = tuple(kind for kind in S8_STATUS_KINDS if s.exempt(kind))
        assert exempted == rules.ERREXIT_EXEMPTIONS, (
            "exempt() answered %r, and the exemptions the rules pin are %r"
            % (exempted, rules.ERREXIT_EXEMPTIONS))
        _refuses(world.MachineError, "exempt of a word that is not a kind",
                 lambda: s.exempt("nope"), names=("'nope'",))

    def _s8_connectors(s, machine):
        """`&&`, `||` and `;` decide from the left side's status; `status` is last."""
        line = s.run_lists(machine, _parse("echo one && echo two"), _state(machine))
        _checked(line, "the line `echo one && echo two`")
        assert line["status"] == 0 and not line["stopped"] and line["skipped"] == 0, (
            "the line `echo one && echo two` answered %r" % (line,))
        assert _row(line, 0)["kind"] == "and-or-left" and _row(line, 1)["kind"] == "plain", (
            "the line's kinds are %r, and the left of `&&` is `and-or-left` and the "
            "right is `plain`" % (line["statuses"],))

        skipped = s.run_lists(machine, _parse("false && echo two"), _state(machine))
        _checked(skipped, "the line `false && echo two`")
        assert skipped["skipped"] == 1 and skipped["status"] == 1, (
            "the line `false && echo two` answered %r" % (skipped,))
        assert len(skipped["statuses"]) == 1, (
            "the line `false && echo two` answered %d rows, and the skipped right "
            "ran nothing" % (len(skipped["statuses"]),))

        doubled = s.run_lists(machine, _parse("false && echo a | cat"),
                              _state(machine))
        _checked(doubled, "the line `false && echo a | cat`")
        assert doubled["skipped"] == 2, (
            "the line `false && echo a | cat` skipped %d commands, and a pipeline "
            "counts as its commands" % (doubled["skipped"],))

        held = s.run_lists(machine, _parse("false || echo two"), _state(machine))
        _checked(held, "the line `false || echo two`")
        assert held["status"] == 0 and held["skipped"] == 0 and \
            _row(held, 1)["status"] == 0, (
            "the line `false || echo two` answered %r" % (held,))

        notrun = s.run_lists(machine, _parse("echo a || echo two"), _state(machine))
        _checked(notrun, "the line `echo a || echo two`")
        assert notrun["skipped"] == 1 and notrun["status"] == 0, (
            "the line `echo a || echo two` answered %r" % (notrun,))

        both = s.run_lists(machine, _parse("echo a; echo b"), _state(machine))
        _checked(both, "the line `echo a; echo b`")
        assert both["status"] == 0 and len(both["statuses"]) == 2 and \
            both["skipped"] == 0, (
            "the line `echo a; echo b` answered %r" % (both,))

    def _s8_errexit(s, machine):
        """`errexit` stops a plain failure and the exemptions a line can record."""
        stopped = s.run_lists(machine, _parse("false; echo b"), _state(machine, True))
        _checked(stopped, "the stopped line `false; echo b`")
        assert stopped["stopped"] and stopped["status"] == 1 and \
            len(stopped["statuses"]) == 1, (
            "the line `false; echo b` under `errexit` answered %r" % (stopped,))

        left = s.run_lists(machine, _parse("false && echo b"), _state(machine, True))
        _checked(left, "the exempt left `false && echo b`")
        assert not left["stopped"] and left["skipped"] == 1, (
            "the line `false && echo b` under `errexit` answered %r, and an "
            "`and-or-left` never trips it" % (left,))

        negated = s.run_lists(machine, _parse("! false"), _state(machine, True))
        _checked(negated, "the exempt negation `! false`")
        assert not negated["stopped"] and negated["status"] == 0 and \
            _row(negated, 0)["kind"] == "negated", (
            "the line `! false` under `errexit` answered %r" % (negated,))

        still = s.run_lists(machine, _parse("! false; echo after"),
                            _state(machine, True))
        _checked(still, "the line past an exempt negation")
        assert still["status"] == 0 and len(still["statuses"]) == 2 and \
            not still["stopped"], (
            "the line `! false; echo after` under `errexit` answered %r" % (still,))

        butlast = s.run_lists(machine, _parse("echo hi | false | cat"),
                              _state(machine, True))
        _checked(butlast, "the exempt but-last `echo hi | false | cat`")
        assert not butlast["stopped"] and butlast["status"] == 0, (
            "the line `echo hi | false | cat` under `errexit` answered %r, and a "
            "but-last row is not a command's status" % (butlast,))

        rows = s.run_lists(machine, _parse("echo a | cat && echo b"),
                           _state(machine))
        _checked(rows, "the kinds of `echo a | cat && echo b`")
        assert [row["kind"] for row in rows["statuses"]] == \
            ["pipeline-but-last", "and-or-left", "plain"], (
            "the kinds are %r, and a pipeline's own rows are but-last until its last "
            "command carries the list's kind" % (rows["statuses"],))

        negated_bad = s.run_lists(machine, _parse("! kill"), _state(machine))
        _checked(negated_bad, "the negation of a bad usage `! kill`")
        assert negated_bad["status"] == 0, (
            "the line `! kill` answered %r, and a `!` turns any failure into 0"
            % (negated_bad["status"],))

    def _s8_background(s, machine):
        """A list ended by `&` launches without waiting; three lines share a state."""
        import machine as world
        alone = s.run_lists(machine, _parse("echo hi &"), _state(machine))
        _checked(alone, "the background line `echo hi &`")
        assert alone["status"] == 0 and not alone["stopped"], (
            "the line `echo hi &` answered %r" % (alone,))

        machine = world.machine(7)
        state = _state(machine)
        launched = s.run_lists(machine, _parse("tick 5 &"), state)
        _checked(launched, "the background line `tick 5 &`")
        assert launched["status"] == 0, (
            "the line `tick 5 &` answered %r" % (launched,))
        assert len(state["jobs"]) == 1, (
            "the line `tick 5 &` left %d jobs, and one launch is one job"
            % (len(state["jobs"]),))
        job = state["jobs"][0]
        assert isinstance(job, dict) and tuple(job) == S8_JOB_KEYS, (
            "the job row is %r, and a job carries %r" % (job, S8_JOB_KEYS))
        assert job["state"] == "running" and job["status"] is None, (
            "the launched job is %r" % (job,))

        killed = s.run_lists(machine, _parse("kill -TERM %1"), state)
        _checked(killed, "the routed `kill -TERM %1`")
        assert killed["status"] == 128 + 15, (
            "the line `kill -TERM %1` answered %d" % (killed["status"],))
        waited = s.run_lists(machine, _parse("wait %1"), state)
        _checked(waited, "the routed `wait %1`")
        assert waited["status"] == 128 + 15, (
            "the line `wait %1` answered %d, the job's own end"
            % (waited["status"],))

        mid = s.run_lists(machine, _parse("echo a & echo b"), _state(machine))
        _checked(mid, "the line `echo a & echo b`")
        assert mid["status"] == 0 and len(mid["statuses"]) == 2, (
            "the line `echo a & echo b` answered %r" % (mid,))

        two_jobs = _state(machine)
        for _ in range(2):
            s.run_lists(machine, _parse("tick 5 &"), two_jobs)
        assert [row["job"] for row in two_jobs["jobs"]] == [1, 2], (
            "two launches numbered their jobs %r, and one job number is never reused"
            % ([row["job"] for row in two_jobs["jobs"]],))

    def _s8_routed(s, machine):
        """`kill`, `trap` and `wait` run where their stages own them, anywhere."""
        import machine as world
        state = _state(machine)
        line = s.run_lists(machine, _parse("trap 'echo done' TERM && wait"), state)
        _checked(line, "the routed line `trap 'echo done' TERM && wait`")
        assert line["status"] == 0 and len(line["statuses"]) == 2, (
            "the routed line answered %r" % (line,))
        assert len(state["traps"]) == 1 and state["traps"][0]["name"] == "TERM" and \
            state["traps"][0]["action"] == "echo done", (
            "the routed line left the state's traps %r" % (state["traps"],))

        state = _state(machine)
        s.run_lists(machine, _parse("trap 'echo done' TERM INT"), state)
        assert len(state["traps"]) == 2 and \
            [row["name"] for row in state["traps"]] == ["TERM", "INT"], (
            "`trap ACTION SIG...` left the state's traps %r, one row per signal"
            % (state["traps"],))

        before = machine.stats()["spawn"]
        state = _state(machine)
        s.run_lists(machine, _parse("trap 'echo done' TERM; wait"), state)
        assert machine.stats()["spawn"] == before, (
            "the routed line spawned a process, and a routed builtin must not")

        bad = s.run_lists(machine, _parse("kill"), _state(machine))
        _checked(bad, "the bare `kill`")
        assert bad["status"] == _rules().EXIT_BAD_USAGE, (
            "the bare `kill` answered %r" % (bad,))
        bad = s.run_lists(machine, _parse("trap"), _state(machine))
        _checked(bad, "the bare `trap`")
        assert bad["status"] == _rules().EXIT_BAD_USAGE, (
            "the bare `trap` answered %r" % (bad,))

        _refuses(world.MachineError, "the routed `kill -TERM %1` with no job",
                 lambda: s.run_lists(machine, _parse("kill -TERM %1"),
                                     _state(machine)),
                 names=("%1",))

    def _s8_assignments(s, machine):
        """A bare assignment sets the state; a prefixed one sets nothing."""
        state = _state(machine)
        set_line = s.run_lists(machine, _parse("X=1"), state)
        _checked(set_line, "the bare assignment `X=1`")
        assert set_line["status"] == 0, ("the bare assignment answered %r" % (set_line,))
        assert state["variables"] == {"X": "1"} and state["exported"] == (), (
            "the bare assignment left variables %r and exported %r"
            % (state["variables"], state["exported"]))

        state = _state(machine)
        state["variables"]["Y"] = "bee"
        expanded = s.run_lists(machine, _parse("X=$Y"), state)
        _checked(expanded, "the assignment `X=$Y`")
        assert state["variables"] == {"Y": "bee", "X": "bee"}, (
            "the assignment `X=$Y` left variables %r, and the value is what the "
            "parameter expanded to" % (state["variables"],))

        state = _state(machine)
        prefix = s.run_lists(machine, _parse("X=1 echo hi"), state)
        _checked(prefix, "the prefixed assignment `X=1 echo hi`")
        assert prefix["status"] == 0 and state["variables"] == {}, (
            "the prefixed assignment answered %r and left variables %r"
            % (prefix, state["variables"]))

        state = _state(machine, nounset=True)
        nounset = s.run_lists(machine, _parse("X=$NOPE"), state)
        _checked(nounset, "the `nounset` assignment `X=$NOPE`")
        assert nounset["status"] == 1 and state["variables"] == {}, (
            "the `nounset` assignment answered %r and left variables %r"
            % (nounset, state["variables"]))

    def _s8_exit(s, machine):
        """A set `exit` answers immediately; `exit 3` mid-line stops the line."""
        state = _state(machine, exit=5)
        leaving = s.run_lists(machine, _parse("echo hi"), state)
        _checked(leaving, "the line against a state whose exit is set")
        assert leaving["status"] == 5 and leaving["stopped"] and \
            leaving["statuses"] == (), (
            "the line answered %r, and a set exit runs nothing" % (leaving,))

        state = _state(machine)
        mid = s.run_lists(machine, _parse("false; exit 3"), state)
        _checked(mid, "the line `false; exit 3`")
        assert mid["status"] == 3 and mid["stopped"] and state["exit"] == 3 and \
            len(mid["statuses"]) == 2, (
            "the line `false; exit 3` answered %r and left exit %r"
            % (mid, state["exit"]))

    def _s8_condition_of(s, machine):
        """`condition_of` runs with the kind the caller named and a state of its own."""
        import machine as world
        record = s.condition_of(machine, ({"words": ("false",)},))
        _checked(record, "the condition `(false,)`")
        assert record["status"] == 1 and record["stopped"] is False and \
            _row(record, 0)["kind"] == "condition", (
            "the condition answered %r" % (record,))

        named = s.condition_of(machine, {"kind": "while-condition",
                                         "pipelines": (({"words": ("echo", "hi")},),)})
        _checked(named, "the condition `while-condition`")
        assert _row(named, 0)["kind"] == "while-condition" and named["status"] == 0, (
            "the condition answered %r" % (named,))

        _refuses(world.MachineError,
                 "a condition of a kind the grammar has no room for",
                 lambda: s.condition_of(machine, {"kind": "for-condition",
                                                  "pipelines": (({"words": ("echo",)},
                                                                 ),)}),
                 names=("'for-condition'",))

        # A condition of one's own state: the caller's table untouched.
        seeded = _state(machine)
        seeded["variables"]["KEPT"] = "1"
        s.condition_of(machine, ({"words": (("echo",))},))
        assert seeded["variables"] == {"KEPT": "1"}, (
            "the condition moved the caller's variables to %r"
            % (seeded["variables"],))

        two = s.condition_of(machine, {"kind": "while-condition",
                                       "pipelines": (({"words": ("echo", "a")},),
                                                     ({"words": ("false",)},))})
        _checked(two, "the condition `while-condition` of two pipelines")
        assert [row["kind"] for row in two["statuses"]] == \
            ["pipeline-but-last", "while-condition"], (
            "the kinds are %r, and a but-last row of a condition is not the "
            "condition's kind" % (two["statuses"],))

        unknown = s.condition_of(machine, ({"words": ("nosuchprogram",)},))
        _checked(unknown, "the condition of an unknown program")
        assert unknown["status"] == 127 and _row(unknown, 0)["kind"] == "condition", (
            "the condition answered %r" % (unknown,))

    def _s8_refusals(s, machine):
        """The shapes a caller can get wrong, each refused with the offender named."""
        import machine as world
        _refuses(world.MachineError, "lists that are not a tuple",
                 lambda: s.run_lists(machine, "not a tuple", _state(machine)),
                 names=("not a tuple",))
        _refuses(world.MachineError, "a list that is not a pair",
                 lambda: s.run_lists(machine, (("x",),), _state(machine)),
                 names=("'x'",))
        _refuses(world.MachineError, "a connector that is not one of the four",
                 lambda: s.run_lists(machine, ((({"words": (("echo",))},), "then"),),
                                     _state(machine)),
                 names=("'then'",))
        _refuses(world.MachineError, "a list with no pipelines",
                 lambda: s.run_lists(machine, (((), "&&"),), _state(machine)),
                 names=("no pipelines",))
        _refuses(world.MachineError, "a command that is not a record",
                 lambda: s.run_lists(machine, (((("echo",),), None),),
                                     _state(machine)),
                 names=("not a command",))
        _refuses(world.MachineError, "a word that is not a word",
                 lambda: s.run_lists(machine, ((({"words": (7,)},), None),),
                                     _state(machine)),
                 names=("not a word: 7",))
        _refuses(world.MachineError, "an assignment that is not a string",
                 lambda: s.run_lists(machine, ((({"words": ("echo",),
                                                  "assignment": 7},), None),),
                                     _state(machine)),
                 names=("7",))
        _refuses(world.MachineError, "a state without its keys",
                 lambda: s.run_lists(machine, ((({"words": ("echo",)},), None),),
                                     {}),
                 names=("'variables'",))
        _refuses(world.MachineError, "a state whose exit is not a status",
                 lambda: s.run_lists(machine, ((({"words": ("echo",)},), None),),
                                     _state(machine, exit="nope")),
                 names=("nope",))

    def _parse(line):
        """The check's own parse of one line, through stage 1."""
        import stage_01
        parsed = stage_01.parse(line)
        assert parsed["error"] is None, (
            "the check's own line %r did not parse: %r" % (line, parsed["error"]))
        return parsed["lists"]

    def _rules():
        """The rules module, imported fresh."""
        import rules
        return rules

    """Every assertion the contract's §4.8 makes about this stage."""
    import machine as world
    import rules
    import stage_08 as s
    _s8_constants(s, rules)
    _s8_connectors(s, world.machine(7))
    _s8_errexit(s, world.machine(7))
    _s8_background(s, world.machine(7))
    _s8_routed(s, world.machine(7))
    _s8_assignments(s, world.machine(7))
    _s8_exit(s, world.machine(7))
    _s8_condition_of(s, world.machine(7))
    _s8_refusals(s, world.machine(7))

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    S9_SESSION_KEYS = ("name", "stdout", "status", "statuses", "children",
                       "signals", "jobs", "deadlocks")

    S9_SHELL_KEYS = ("variables", "exported", "traps", "jobs", "flags", "cwd",
                     "exit", "args", "stdin")

    S9_JOB_KEYS = ("job", "pid", "state", "status", "command")

    S9_JOB_STATES = ("running", "stopped", "done")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "machine.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked
        against the message: an exception of the right family raised for the wrong
        reason is not the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__,
                                    str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _fresh(world):
        """A machine no session has touched yet."""
        return world.machine(7)

    def _rows_of(record):
        """The `(index, status, kind)` rows a session answered, checked for shape."""
        rows = record["statuses"]
        assert isinstance(rows, tuple), (
            "statuses is a tuple, and %r is not" % (rows,))
        for at, row in enumerate(rows):
            assert isinstance(row, tuple) and len(row) == 3, (
                "statuses[%d] is (index, status, kind), and %r is not" % (at, row))
            index, status, kind = row
            assert index == at, (
                "statuses[%d] carries the index %r — the session's own index runs "
                "from zero without a gap" % (at, index))
            assert isinstance(status, int) and not isinstance(status, bool), (
                "statuses[%d]'s status is %r, and a status is an int" % (at, status))
            assert 0 <= status <= 255, (
                "statuses[%d]'s status is %r, outside a status's own range"
                % (at, status))
        return rows

    def _keys_of(record):
        """The keys of a record as written, in the order it wrote them."""
        return tuple(record)

    def _s9_constants(s, rules):
        """The two key tuples the contract pins, and the world's own decision list."""
        assert tuple(s.SESSION_KEYS) == S9_SESSION_KEYS, (
            "SESSION_KEYS is %r, not %r" % (s.SESSION_KEYS, S9_SESSION_KEYS))
        assert tuple(s.SHELL_KEYS) == S9_SHELL_KEYS, (
            "SHELL_KEYS is %r, not %r" % (s.SHELL_KEYS, S9_SHELL_KEYS))
        assert rules.EXIT_OK == 0 and rules.EXIT_BAD_USAGE == 2, (
            "this check's own arithmetic assumes EXIT_OK 0 and EXIT_BAD_USAGE 2, and "
            "the policy holds %r and %r" % (rules.EXIT_OK, rules.EXIT_BAD_USAGE))

    def _s9_fixtures(s, world, scripts):
        """Every fixture, on a fresh machine, against the world's own answer key.

        The comparison is key by key rather than record by record, so a failure says
        *which* field of *which* session disagreed with the world — and both sides are
        asserted to carry exactly `SESSION_KEYS`, because a stage that answers one key
        more than the answer key is as wrong as one that answers a key less.
        """
        names = scripts.names()
        assert tuple(names) == tuple(sorted(names)), (
            "scripts.names() is %r, and the world's session names are sorted" % (names,))
        assert names, "the world holds no fixture sessions to replay"
        answers = []
        for name in names:
            script = scripts.session(name)
            record = s.run_session(_fresh(world), script)
            expected = script["expected"]
            assert _keys_of(record) == S9_SESSION_KEYS, (
                "session %r answered the keys %r, and SESSION_KEYS is %r"
                % (name, _keys_of(record), S9_SESSION_KEYS))
            assert _keys_of(expected) == S9_SESSION_KEYS, (
                "the world's own expected record for %r carries %r, not SESSION_KEYS"
                % (name, _keys_of(expected)))
            for key in S9_SESSION_KEYS:
                assert record[key] == expected[key], (
                    "session %r: %s is %r, and the world's own expected is %r"
                    % (name, key, record[key], expected[key]))
            _rows_of(record)
            answers.append(record)
        return tuple(answers)

    def _s9_evidence(s, world, scripts, rules):
        """`children`, `deadlocks`, `signals` and `stdout` recomputed from the machine.

        The contract makes the machine's own ledger and transcript the answer key, so
        the check reads them too: a driver that counted its own spawns, remembered its
        own sends, or reported the terminal's whole history instead of the session's
        bytes disagrees here even where it matched a fixture by luck.
        """
        for name in scripts.names():
            machine = _fresh(world)
            stats = machine.stats()
            mark = len(machine.transcript())
            record = s.run_session(machine, scripts.session(name))
            after = machine.stats()
            assert record["children"] == after["spawn"] - stats["spawn"], (
                "session %r: children is %r, and the machine's own ledger moved %r "
                "spawns" % (name, record["children"], after["spawn"] - stats["spawn"]))
            assert record["deadlocks"] == after["deadlocks"] - stats["deadlocks"], (
                "session %r: deadlocks is %r, and the machine recorded %r"
                % (name, record["deadlocks"], after["deadlocks"] - stats["deadlocks"]))
            sent = tuple(entry["args"][-1] for entry in machine.transcript()[mark:]
                         if entry["call"] == "signal")
            assert record["signals"] == sent, (
                "session %r: signals is %r, and the machine's own transcript recorded "
                "%r" % (name, record["signals"], sent))
            assert record["stdout"] == machine.terminal(), (
                "session %r: stdout is %r, and the machine's terminal holds %r — a "
                "session reports the bytes it put there, not the terminal's history"
                % (name, record["stdout"], machine.terminal()))
            assert machine.reapable() == (), (
                "session %r left the machine with the unwaited pids %r"
                % (name, machine.reapable()))
            jobs = record["jobs"]
            assert isinstance(jobs, tuple), (
                "session %r: jobs is a tuple of rows, and %r is not" % (name, jobs))
            for row in jobs:
                assert isinstance(row, dict) and tuple(row) == S9_JOB_KEYS, (
                    "session %r: a job row carries the keys %r, and a JOB_KEYS row is %r"
                    % (name, tuple(row) if isinstance(row, dict) else row, S9_JOB_KEYS))
                assert row["state"] in S9_JOB_STATES, (
                    "session %r: the job row's state is %r, and a job is %s"
                    % (name, row["state"], " or ".join(S9_JOB_STATES)))

    def _s9_twice(s, world, scripts):
        """Every fixture run twice on fresh machines: the two records are equal."""
        for name in scripts.names():
            script = scripts.session(name)
            first = s.run_session(_fresh(world), script)
            second = s.run_session(_fresh(world), scripts.session(name))
            assert first == second, (
                "two runs of session %r answered differently (%r then %r), so the "
                "session is not a function of the script it was handed" % (name, first, second))

    def _s9_leaves_nothing(s, world, scripts):
        """A session leaves nothing behind: no zombie, and no row for the next session.

        The same session is run twice **on one machine**, which is the only way to see
        a job table or a terminal that was never cleaned up: the second run must answer
        the first run's own statuses, status, jobs, children and bytes, and the machine
        must hold no reapable pid in between. Two fixtures cannot be replayed on one
        machine and stay equal — their job rows name the *machine's* pids, and the
        deadlock record is the machine's memory of where it stopped — so `background`,
        `deadlock` and `signal` are replayed on one machine for the zombie law alone,
        and their equality is `_s9_twice`'s fresh-machine pair.
        """
        compared = ("stdout", "status", "statuses", "children", "signals", "jobs",
                    "deadlocks")
        shared = ("background", "deadlock", "signal")
        for name in scripts.names():
            machine = _fresh(world)
            script = scripts.session(name)
            first = s.run_session(machine, script)
            assert machine.reapable() == (), (
                "after session %r the machine still holds the unwaited pids %r"
                % (name, machine.reapable()))
            second = s.run_session(machine, script)
            for key in compared:
                if name in shared and key in ("jobs", "deadlocks", "status",
                                              "statuses"):
                    continue
                assert second[key] == first[key], (
                    "session %r run twice on one machine answered a different %s: %r "
                    "then %r — the first session left something behind"
                    % (name, key, first[key], second[key]))
            assert machine.reapable() == (), (
                "after the second run of session %r the machine holds the unwaited "
                "pids %r" % (name, machine.reapable()))

    def _s9_boundaries(s, world, rules):
        """Sessions the check builds itself, with the arithmetic asserted from its own numbers.

        Each case names only the fields the check can derive on its own: the bytes a
        program must write, the status `rules` pins, the rows the session's own index
        makes, and the spawns the session must have paid for. A case that asserted a
        field it could not derive would be a fixture, not a boundary.
        """
        cases = (
            ({"name": "empty", "lines": ()},
             {"stdout": b"", "status": rules.EXIT_OK, "statuses": (), "children": 0,
              "signals": (), "jobs": (), "deadlocks": 0}),
            ({"name": "one", "lines": ("echo hello",)},
             {"stdout": b"hello\n", "status": rules.EXIT_OK,
              "statuses": ((0, rules.EXIT_OK, "plain"),), "children": 1}),
            ({"name": "two", "lines": ("echo one", "echo two")},
             {"stdout": b"one\ntwo\n", "status": rules.EXIT_OK,
              "statuses": ((0, 0, "plain"), (1, 0, "plain")), "children": 2}),
            ({"name": "failure", "lines": ("false",)},
             {"stdout": b"", "status": rules.EXIT_FAILURE,
              "statuses": ((0, rules.EXIT_FAILURE, "plain"),), "children": 1}),
            ({"name": "missing", "lines": ("no-such-program-here",)},
             {"stdout": b"", "status": rules.EXIT_NOT_FOUND,
              "statuses": ((0, 127, "plain"),)}),
            ({"name": "negated", "lines": ("! false",)},
             {"stdout": b"", "status": rules.EXIT_OK,
              "statuses": ((0, 0, "negated"),), "children": 1}),
            ({"name": "colon", "lines": (":",)},
             {"stdout": b"", "status": rules.EXIT_OK,
              "statuses": ((0, 0, "plain"),), "children": 0}),
            ({"name": "exit", "lines": ("exit 3", "echo after")},
             {"stdout": b"", "status": 3, "statuses": ((0, 3, "plain"),),
              "children": 0}),
            ({"name": "unreadable", "lines": ("echo 'unterminated",)},
             {"stdout": b"", "status": rules.EXIT_BAD_USAGE, "statuses": (),
              "children": 0}),
            ({"name": "variables", "lines": ("X=1", "echo $X")},
             {"stdout": b"1\n", "status": rules.EXIT_OK, "children": 1}),
        )
        for script, want in cases:
            machine = _fresh(world)
            record = s.run_session(machine, script)
            assert record["name"] == script["name"], (
                "a session answered the name %r for the script named %r"
                % (record["name"], script["name"]))
            assert _keys_of(record) == S9_SESSION_KEYS, (
                "the session %r answered the keys %r" % (script["name"], _keys_of(record)))
            for key in want:
                assert record[key] == want[key], (
                    "session %r: %s is %r, and this check's own arithmetic says %r"
                    % (script["name"], key, record[key], want[key]))
            _rows_of(record)
            assert machine.reapable() == (), (
                "the boundary session %r left the unwaited pids %r"
                % (script["name"], machine.reapable()))
        _s9_boundary_file(s, world, rules)
        _s9_boundary_stop(s, world, rules)

    def _s9_boundary_file(s, world, rules):
        """`echo out > /w/f` puts its bytes in the machine's own file, not on the terminal."""
        machine = _fresh(world)
        record = s.run_session(machine, {"name": "redirect",
                                         "lines": ("echo out > /w/f",)})
        assert record["stdout"] == b"", (
            "a redirection must take the bytes off the terminal, and stdout is %r"
            % (record["stdout"],))
        assert record["status"] == rules.EXIT_OK, (
            "a redirection that can be made answers EXIT_OK, and this one answered %r"
            % (record["status"],))
        assert machine.load("/w/f") == b"out\n", (
            "the machine's own file holds %r, and the command wrote %r"
            % (machine.load("/w/f"), b"out\n"))
        assert machine.reapable() == (), (
            "the redirection session left the unwaited pids %r" % (machine.reapable(),))

    def _s9_boundary_stop(s, world, rules):
        """`set -e` with a failing command stops the session where §4.8 stops it."""
        machine = _fresh(world)
        record = s.run_session(machine, {"name": "errexit",
                                         "lines": ("set -e", "false", "echo after")})
        assert record["status"] == rules.EXIT_FAILURE, (
            "the session that `set -e` stopped answers the failing status, and this "
            "one answered %r" % (record["status"],))
        assert record["stdout"] == b"", (
            "nothing after the failing command may run, and the terminal holds %r"
            % (record["stdout"],))
        assert len(record["statuses"]) == 2, (
            "`set -e` and `false` are the two commands that ran, and the session "
            "recorded %r" % (record["statuses"],))
        assert machine.reapable() == (), (
            "the stopped session left the unwaited pids %r" % (machine.reapable(),))
        assert record["jobs"] == (), (
            "a stopped session still answers its job table, and it holds %r"
            % (record["jobs"],))

    def _s9_boundary_job(s, world, rules):
        """A background job and a `wait`: one child, one row, and the machine holds no zombie.

        §4.5's table is the session's own bookkeeping over the machine's pids, and the
        point of a session is that it does not leave one behind: the row says `done`
        with the child's status, and the machine has nothing reapable left.
        """
        machine = _fresh(world)
        record = s.run_session(machine, {"name": "background",
                                         "lines": ("tick 2 &", "wait")})
        assert record["children"] == 1, (
            "a background job is one child, and the session spawned %r"
            % (record["children"],))
        assert record["status"] == rules.EXIT_OK, (
            "the wait answers the job's own status, and the session answered %r"
            % (record["status"],))
        assert machine.reapable() == (), (
            "the waited job is not left reapable, and the machine holds %r"
            % (machine.reapable(),))
        assert len(record["jobs"]) == 1, (
            "one background job is one row, and the table holds %r" % (record["jobs"],))
        row = record["jobs"][0]
        assert row["job"] == 1 and row["state"] == "done", (
            "the session's one job is job 1 and it is done, and the row is %r" % (row,))
        assert row["status"] == rules.EXIT_OK, (
            "a done row carries the status the machine reaped, and this one carries %r"
            % (row["status"],))

    def _s9_boundary_trap(s, world, rules):
        """Two traps due at one boundary: the LAST one's status is the shell's own.

        §4.6 pins this reading with two traps precisely because the other obvious
        answers — the command's own status survives, or the first trap's status wins —
        are wrong. Both traps are registered by the one line, so both are due at the
        boundary that follows it: `INT` runs first (signal 2) and `TERM` last (signal
        15), and it is `TERM`'s `false`, not `INT`'s `echo` and not the `trap` builtin's
        own `EXIT_OK`, that the session carries into its own status.
        """
        machine = _fresh(world)
        record = s.run_session(machine,
                               {"name": "traps",
                                "lines": ("trap 'echo one' INT; trap 'false' TERM",)})
        assert len(record["statuses"]) == 2, (
            "the line runs two commands and the session recorded %r"
            % (record["statuses"],))
        assert record["status"] == rules.EXIT_FAILURE, (
            "the last trap to run answers the shell's own status, and the `false` trap "
            "ran last; the session answered %r" % (record["status"],))
        assert machine.reapable() == (), (
            "the trap boundary left the unwaited pids %r" % (machine.reapable(),))

    def _s9_refusals(s, world, rules):
        """Every shape that cannot be a session: refused by name, asking the machine nothing."""
        machine = _fresh(world)
        before = machine.stats()
        _refuses(world.MachineError, "a script that is not a mapping",
                 lambda: s.run_session(machine, "echo hi"), ("stage 9", "mapping"))
        _refuses(world.MachineError, "a script with no lines",
                 lambda: s.run_session(machine, {"name": "x"}), ("stage 9", "lines"))
        _refuses(world.MachineError, "a script with no name",
                 lambda: s.run_session(machine, {"lines": ()}), ("stage 9", "name"))
        _refuses(world.MachineError, "a name that is not a string",
                 lambda: s.run_session(machine, {"name": 7, "lines": ()}),
                 ("stage 9", "name"))
        _refuses(world.MachineError, "lines that are not a sequence",
                 lambda: s.run_session(machine, {"name": "x", "lines": "echo hi"}),
                 ("stage 9", "lines"))
        _refuses(world.MachineError, "a line that is not a string",
                 lambda: s.run_session(machine, {"name": "x", "lines": ("echo hi", 7)}),
                 ("stage 9", "line"))
        after = machine.stats()
        assert after == before, (
            "a refused session asked the machine something: %r became %r"
            % (before, after))

    """Every assertion the contract's §4.9 makes about this stage."""
    import machine as world
    import rules
    import scripts
    import stage_09 as s
    _s9_constants(s, rules)
    _s9_refusals(s, world, rules)
    _s9_boundaries(s, world, rules)
    _s9_boundary_job(s, world, rules)
    _s9_boundary_trap(s, world, rules)
    _s9_fixtures(s, world, scripts)
    _s9_evidence(s, world, scripts, rules)
    _s9_twice(s, world, scripts)
    _s9_leaves_nothing(s, world, scripts)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "shell-from-scratch"

    S10_AUDIT_KEYS = ("session", "steps", "verdict", "reasons")

    S10_AUDIT_REASONS = ("status-from-last-pipeline", "errexit-exempt-condition",
                         "errexit-exempt-and-or-left", "errexit-exempt-negated",
                         "not-found-127", "cannot-execute-126", "redirection-failed",
                         "signalled-128-plus-n", "trap-status", "job-not-waited",
                         "deadlock-reported")

    S10_VERDICTS = ("holds", "differs", "incomplete")

    S10_STEP_KEYS = ("index", "command", "status", "reason")

    S10_RECORD_KEYS = ("name", "stdout", "status", "statuses", "children", "signals",
                       "jobs", "deadlocks")

    S10_TOOL = "/tmp/g7-tool"

    S10_MISSING = "/tmp/g7-definitely-not-here"

    S10_SESSIONS = (
        ("plain", ("echo hi",)),
        ("not-found", ("nosuchprogram",)),
        ("cannot-execute", (S10_TOOL,)),
        ("redirect", ("cat < " + S10_MISSING,)),
        ("and-or-left", ("false && echo hi",)),
        ("negated", ("! false",)),
        ("background", ("echo hi &",)),
        ("signalled", ("tick 5 &", "kill -TERM %1")),
        ("trapped", ("trap 'echo done' TERM", "echo hi")),
    )

    S10_ERREXIT = ("false", "echo hi")

    S10_CONDITION = ("false",)

    def _repo(start=None):
        for candidate_start in (os.environ.get("G7_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                for marker in ("course.py", "machine.py"):
                    if os.path.isfile(os.path.join(candidate, COURSE, marker)):
                        return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G7_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named.

        Every refusal in this course names the offender, so `names` are checked against
        the message: an exception of the right family raised for the wrong reason is not
        the refusal the contract asked for.
        """
        try:
            got = call()
        except exc as refused:
            message = str(refused)
            for want in names:
                assert want in message, (
                    "%s refused with %r, which does not name %r" % (what, message, want))
            return refused
        except NotImplementedError:
            raise
        except Exception as wrong:                               # noqa: BLE001
            raise AssertionError("%s raised %s instead of %s: %r"
                                 % (what, type(wrong).__name__, exc.__name__, wrong))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _s10_constants(s):
        """`AUDIT_KEYS`, the eleven reasons in order, the verdicts, a step's keys."""
        assert tuple(s.AUDIT_KEYS) == S10_AUDIT_KEYS, (
            "AUDIT_KEYS is %r; an audit answers %r" % (s.AUDIT_KEYS, S10_AUDIT_KEYS))
        assert tuple(s.AUDIT_REASONS) == S10_AUDIT_REASONS, (
            "AUDIT_REASONS is %r; the reasons are %r in their rule order"
            % (s.AUDIT_REASONS, S10_AUDIT_REASONS))
        assert tuple(s.VERDICTS) == S10_VERDICTS, (
            "VERDICTS is %r; the verdicts are %r" % (s.VERDICTS, S10_VERDICTS))

    def _s10_shape(s, answer, what):
        """The answer's own shape: `AUDIT_KEYS`, rows of `STEP_KEYS`, reasons known."""
        assert isinstance(answer, dict) and tuple(answer) == S10_AUDIT_KEYS, (
            "%s answered %r, and an audit answers %r" % (what, answer, S10_AUDIT_KEYS))
        assert isinstance(answer["steps"], tuple), (
            "%s answered steps %r, and the steps are a tuple of rows"
            % (what, answer["steps"]))
        for row in answer["steps"]:
            assert isinstance(row, dict) and tuple(row) == S10_STEP_KEYS, (
                "%s answered the step row %r, and a step is %r"
                % (what, row, S10_STEP_KEYS))
            assert row["reason"] in S10_AUDIT_REASONS, (
                "%s answered the reason %r, and a reason is one of the eleven"
                % (what, row["reason"]))
            assert isinstance(row["status"], int) and not isinstance(row["status"], bool), (
                "%s answered the status %r, and a status is an int"
                % (what, row["status"]))
        used = []
        for row in answer["steps"]:
            if row["reason"] not in used:
                used.append(row["reason"])
        ordered = [reason for reason in S10_AUDIT_REASONS if reason in used]
        assert tuple(answer["reasons"]) == tuple(ordered), (
            "%s answered reasons %r, and the distinct reasons in rule order are %r"
            % (what, answer["reasons"], tuple(ordered)))
        assert answer["verdict"] in S10_VERDICTS, (
            "%s answered the verdict %r" % (what, answer["verdict"]))

    def _s10_fixtures(s, world, scripts):
        """Every fixture audited by name: `holds`, or `incomplete` for the deadlock.

        The expected record the verdict compares against is the world's own, so a
        verdict of `holds` is a fact about the world and not about this stage.
        """
        verdicts = {}
        for name in scripts.names():
            answer = s.audit(world.machine(7), name, {})
            _s10_shape(s, answer, "the audit of %r" % (name,))
            assert answer["session"] == name, (
                "the audit of %r answered session %r" % (name, answer["session"]))
            expected_verdict = "incomplete" if name == "deadlock" else "holds"
            assert answer["verdict"] == expected_verdict, (
                "the audit of %r answered %r, and the world's own expected record "
                "earns %r" % (name, answer["verdict"], expected_verdict))
            assert answer["steps"], (
                "the audit of %r answered no steps" % (name,))
            for position, row in enumerate(answer["steps"]):
                assert row["index"] == position, (
                    "the audit of %r numbered its rows %r" % (name, answer["steps"]))
            if name == "deadlock":
                assert answer["steps"][-1]["reason"] == "deadlock-reported", (
                    "the audit of the deadlock fixture charged its last row %r, and "
                    "a session the scheduler could not finish is reported as the "
                    "deadlock it is" % (answer["steps"][-1]["reason"],))
            verdicts[name] = answer
        # The same audits on a machine the check has already used: the record's
        # counters are the machine's own deltas from a nonzero mark, so an audit
        # that read the ledger absolutely answers a record no honest expected
        # record matches. The expected record comes from a twin — a second machine
        # warmed identically and replayed by the check's own stage_09 — so every
        # byte the two records carry was earned the same way. The warmer spawns,
        # echoes, waits, deadlocks a blocked reader and reaps it, so the transcript,
        # the spawn ledger, the deadlocks and the terminal all start nonzero. A
        # fixture whose own lines name a fresh machine's pids (`kill -STOP 1`)
        # cannot be replayed on a used machine, and the deadlock fixture is
        # replayed fresh alone.
        for name in scripts.names():
            if name == "deadlock":
                continue
            twin = _s10_warmed(world)
            script = scripts.session(name)
            import stage_09
            expected = stage_09.run_session(twin, {"name": name,
                                                   "lines": script["lines"]})
            machine = _s10_warmed(world)
            warm = s.audit(machine, {"name": name, "lines": script["lines"],
                                     "expected": expected}, {})
            _s10_shape(s, warm, "the audit of %r on a used machine" % (name,))
            assert warm["verdict"] == "holds", (
                "the audit of %r on a used machine answered %r, and the counters "
                "are deltas the mark owes" % (name, warm["verdict"]))
            assert warm["session"] == name
        return verdicts

    def _s10_warmed(world):
        """A machine with every counter already moved: the replay measures deltas.

        One echoed child puts entries on the transcript and bytes on the terminal;
        a blocked reader deadlocks the scheduler and is reaped, so the deadlock
        counter moves and no process is left running to spin a later wait.
        """
        machine = world.machine(7)
        warmer = machine.spawn(("echo", "warmed"))
        machine.advance(1)
        machine.wait(warmer)
        read_end, write_end = machine.pipe()
        reader = machine.spawn(("cat",))
        machine.give(reader, 0, read_end)
        machine.wait(reader)
        machine.signal(reader, "TERM")
        machine.advance(1)
        machine.close(0, write_end)
        return machine

    def _s10_evidence(s, world, scripts):
        """The reasons are the evidence's: a wrong expected record changes nothing.

        Each fixture is audited a second time with the world's own expected record
        replaced by one that disagrees on `stdout`, and the answer must keep the
        same steps' reasons — only the verdict moves, to `differs`, and the last
        step row names the key that differed.
        """
        for name in scripts.names():
            script = scripts.session(name)
            wrong = dict(script["expected"], stdout=b"check10: not the world's bytes\n")
            answer = s.audit(world.machine(7),
                             {"name": name, "lines": script["lines"],
                              "expected": wrong}, {})
            _s10_shape(s, answer, "the audit of %r against a wrong expected" % (name,))
            plain = s.audit(world.machine(7), {"name": name, "lines": script["lines"],
                                               "expected": script["expected"]}, {})
            assert answer["reasons"] == plain["reasons"], (
                "the audit of %r answered reasons %r against a wrong expected and %r "
                "against the world's own, and a reason is decided from the evidence"
                % (name, answer["reasons"], plain["reasons"]))
            expected_verdict = "incomplete" if name == "deadlock" else "differs"
            assert answer["verdict"] == expected_verdict, (
                "the audit of %r against a wrong expected answered %r"
                % (name, answer["verdict"]))
            if answer["verdict"] == "differs":
                assert answer["steps"][-1]["command"] in S10_RECORD_KEYS, (
                    "the audit of %r named the difference %r in its last step row, and "
                    "a difference is one of the record's own keys"
                    % (name, answer["steps"][-1]["command"]))
                assert answer["steps"][-1]["command"] == "stdout", (
                    "the audit of %r named %r as the difference, and the wrong record "
                    "disagreed on stdout" % (name, answer["steps"][-1]["command"]))

    def _s10_expected(world, lines, name):
        """The expected record a session earns, replayed by stage 9 on a fresh machine.

        The replay is the check's own, on a machine of its own, so the answer key a
        session is compared against is not the stage under test's work.
        """
        import stage_09
        return stage_09.run_session(world.machine(7), {"name": name, "lines": lines})

    def _s10_reasons(s, world):
        """The sessions the world need not hold, and the reason each must reach.

        The expected record each case is compared against is the check's own
        `run_session` replay, so a `holds` verdict says the stage's replay agreed
        with an independent one — and the reasons name why each status was what it
        was, which is what the case exists to reach.
        """
        wanted = {
            "plain": ("status-from-last-pipeline",),
            "not-found": ("not-found-127",),
            "cannot-execute": ("cannot-execute-126",),
            "redirect": ("redirection-failed",),
            "and-or-left": ("errexit-exempt-and-or-left",),
            "negated": ("errexit-exempt-negated",),
            "background": ("job-not-waited",),
            "signalled": ("signalled-128-plus-n", "job-not-waited"),
            "trapped": ("trap-status",),
        }
        seen = []
        for name, lines in S10_SESSIONS:
            expected = _s10_expected(world, lines, name)
            if name == "cannot-execute":
                machine = world.machine(7)
                machine.store(S10_TOOL, b"the check's own tool, not a program")
                expected = _s10_expected(world, lines, name)
                answer = s.audit(machine, {"name": name, "lines": lines,
                                           "expected": expected}, {})
            else:
                answer = s.audit(world.machine(7), {"name": name, "lines": lines,
                                                    "expected": expected}, {})
            _s10_shape(s, answer, "the audit of the check's own %r" % (name,))
            assert answer["verdict"] == "holds", (
                "the audit of the check's own %r answered %r against its own replay"
                % (name, answer["verdict"]))
            for reason in wanted[name]:
                assert reason in answer["reasons"], (
                    "the audit of the check's own %r answered reasons %r, and %r is "
                    "what the case exists to reach" % (name, answer["reasons"], reason))
            seen.extend(answer["reasons"])
        # `exit 143` is a status a user picked, not a signal's `128 + n`: the audit
        # must read the exit command's own number as a plain status even though it
        # lands in the signalled range.
        lines = ("exit 143",)
        expected = _s10_expected(world, lines, "exit-picked")
        answer = s.audit(world.machine(7), {"name": "exit-picked", "lines": lines,
                                            "expected": expected}, {})
        _s10_shape(s, answer, "the audit of the check's own 'exit-picked'")
        assert answer["verdict"] == "holds", (
            "the audit of the check's own 'exit-picked' answered %r against its own "
            "replay" % (answer["verdict"],))
        assert answer["steps"][0]["reason"] == "status-from-last-pipeline", (
            "the audit of 'exit 143' answered reason %r, and a status the exit "
            "command picked is a plain status however high it lands"
            % (answer["steps"][0]["reason"],))
        seen.extend(answer["reasons"])
        # A refusal inside a pipeline is charged to the refused command's own row,
        # not to whatever row happens to come last: the plan each row consults is the
        # row the alignment matched, and the first command of the pipeline is the one
        # whose redirection failed.
        lines = ("cat < " + S10_MISSING + " | echo hi",)
        expected = _s10_expected(world, lines, "pipeline-refused")
        answer = s.audit(world.machine(7), {"name": "pipeline-refused",
                                            "lines": lines,
                                            "expected": expected}, {})
        _s10_shape(s, answer, "the audit of the check's own 'pipeline-refused'")
        assert answer["verdict"] == "holds", (
            "the audit of the check's own 'pipeline-refused' answered %r against its "
            "own replay" % (answer["verdict"],))
        assert answer["steps"][0]["reason"] == "redirection-failed", (
            "the audit of a refused pipeline head answered reason %r, and the "
            "refusal is the head command's own" % (answer["steps"][0]["reason"],))
        seen.extend(answer["reasons"])
        # A command word that is a variable is matched to the kingdom of the word the
        # expansion put in its place, not the kingdom of the word as written: `$p`
        # here names a stored file only after expansion, so `cannot-execute-126` and
        # not `not-found-127` is what the evidence says.
        machine = world.machine(7)
        machine.store(S10_TOOL, b"the check's own tool, not a program")
        twin = world.machine(7)
        twin.store(S10_TOOL, b"the check's own tool, not a program")
        lines = ("p=" + S10_TOOL, "$p")
        import stage_09
        expected = stage_09.run_session(twin, {"name": "expanded-argv",
                                               "lines": lines})
        answer = s.audit(machine, {"name": "expanded-argv", "lines": lines,
                                   "expected": expected}, {})
        _s10_shape(s, answer, "the audit of the check's own 'expanded-argv'")
        assert answer["verdict"] == "holds", (
            "the audit of the check's own 'expanded-argv' answered %r against its own "
            "replay" % (answer["verdict"],))
        assert answer["steps"][1]["reason"] == "cannot-execute-126", (
            "the audit of '$p' answered reason %r, and the kingdom is the expanded "
            "word's, not the word as written" % (answer["steps"][1]["reason"],))
        seen.extend(answer["reasons"])
        # A line that cannot be parsed stops the session at the parse status, and the
        # session's own status is that number, not `EXIT_OK`.
        lines = ("| echo hi",)
        expected = _s10_expected(world, lines, "unparsable")
        answer = s.audit(world.machine(7), {"name": "unparsable", "lines": lines,
                                            "expected": expected}, {})
        _s10_shape(s, answer, "the audit of the check's own 'unparsable'")
        assert answer["verdict"] == "holds", (
            "the audit of the check's own 'unparsable' answered %r against its own "
            "replay" % (answer["verdict"],))
        seen.extend(answer["reasons"])
        return seen

    def _s10_options(s, world):
        """`errexit` honoured, `condition` believed, an unknown option refused."""
        import rules
        seen = []
        lines = S10_ERREXIT
        expected = _s10_expected(world, ("false",), "options")
        answer = s.audit(world.machine(7), {"name": "options", "lines": lines,
                                            "expected": expected},
                         {"errexit": True})
        _s10_shape(s, answer, "the audit of the options case")
        assert answer["verdict"] == "holds", (
            "the options case answered %r, and the option's replay is the check's own "
            "expected record" % (answer["verdict"],))
        assert [row["command"] for row in answer["steps"]] == ["false"], (
            "the options case's steps ran %r, and `errexit` stopped the session at "
            "`false`" % ([row["command"] for row in answer["steps"]],))
        assert answer["steps"][0]["status"] == rules.EXIT_FAILURE, (
            "the options case's `false` answered %r" % (answer["steps"][0]["status"],))
        seen.extend(answer["reasons"])

        # A condition's kind is the caller's word: no line records one, so the
        # audit believes `condition` for exactly the lines it names.
        condition_lines = S10_CONDITION
        expected = _s10_expected(world, condition_lines, "condition")
        answer = s.audit(world.machine(7),
                         {"name": "condition", "lines": condition_lines,
                          "expected": expected},
                         {"errexit": True, "condition": S10_CONDITION})
        _s10_shape(s, answer, "the audit of the condition case")
        assert "errexit-exempt-condition" in answer["reasons"], (
            "the condition case answered reasons %r, and the kind the check supplies "
            "is what the reason exists for" % (answer["reasons"],))
        assert answer["steps"][0]["reason"] == "errexit-exempt-condition", (
            "the condition case's step answered %r" % (answer["steps"][0],))
        seen.extend(answer["reasons"])

        # The same line without the option is the plain case: the kind is the
        # caller's word and not the line's.
        plain = s.audit(world.machine(7),
                        {"name": "condition", "lines": condition_lines,
                         "expected": expected}, {"errexit": True})
        assert plain["steps"][0]["reason"] == "status-from-last-pipeline", (
            "the same line without the option answered %r, and a kind is believed "
            "only for the lines the option names" % (plain["steps"][0],))

        _refuses(world.MachineError, "audit with an unknown option",
                 lambda: s.audit(world.machine(7), "pipeline", {"nope": True}),
                 names=("'nope'",))
        return seen

    def _s10_refusals(s, world):
        """A name no fixture holds, and a session that is not a session."""
        _refuses(world.MachineError, "audit of an unknown name",
                 lambda: s.audit(world.machine(7), "no-such-fixture-session", {}),
                 names=("no-such-fixture-session",))
        _refuses(world.MachineError, "audit of a number",
                 lambda: s.audit(world.machine(7), 42, {}), names=("42",))
        _refuses(world.MachineError, "audit of a record without a name",
                 lambda: s.audit(world.machine(7), {"lines": ("echo hi",)}, {}),
                 names=("name",))
        _refuses(world.MachineError, "audit of a record without lines",
                 lambda: s.audit(world.machine(7), {"name": "x"}, {}),
                 names=("lines",))
        _refuses(world.MachineError, "audit of a record whose lines are one string",
                 lambda: s.audit(world.machine(7),
                                 {"name": "x", "lines": "echo hi"}, {}),
                 names=("lines",))

    def _s10_twice(s, world, scripts):
        """Every fixture audited twice on fresh machines answers the same record."""
        for name in scripts.names():
            first = s.audit(world.machine(7), name, {})
            second = s.audit(world.machine(7), name, {})
            assert first == second, (
                "two audits of %r answered %r and %r, and an audit is a function of "
                "the session it was handed" % (name, first, second))

    """Every assertion the contract's §4.10 makes about this stage."""
    import machine as world
    import scripts
    import stage_10 as s
    _s10_constants(s)
    _s10_fixtures(s, world, scripts)
    _s10_evidence(s, world, scripts)
    seen = _s10_reasons(s, world)
    seen = seen + _s10_options(s, world)
    _s10_refusals(s, world)
    _s10_twice(s, world, scripts)
    for reason in S10_AUDIT_REASONS:
        assert reason in seen or reason == "deadlock-reported", (
            "the check's own cases never reached %r, and every reason the "
            "contract pins must be reachable" % (reason,))

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The line, the word and the operator",
        tags=["lexing", "quoting", "operators"],
        action="Write `TOKEN_KEYS`, `TOKEN_KINDS`, `QUOTE_KINDS`, `PARSE_KEYS`, "
               "`COMMAND_KEYS`, `PARSE_ERRORS`, `tokenize` and `parse` in "
               "stage_01.py.",
        predict="What a word is once the quotes are part of its bytes rather than "
                "decorations around it, and why the longest operator has to be "
                "recognised before the shortest one can be.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="Expansion, in the order a shell must",
        tags=["expansion", "globbing", "here-documents"],
        action="Write `EXPAND_KEYS`, `EXPAND_ERRORS`, `expand`, `expand_word`, "
               "`substitute`, `glob` and `here_document` in stage_02.py.",
        predict="How many words one word becomes, and why the answer depends on "
                "the order the five steps run in rather than on any one of them.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The pipeline, the descriptor table and what a pipe costs",
        tags=["redirection", "pipes", "planning"],
        action="Write `PLAN_KEYS`, `PLAN_ERRORS`, `plan`, `redirects_of` and "
               "`cost_of` in stage_03.py.",
        predict="Why `>f 2>&1` and `2>&1 >f` are two different tables, and how "
                "many machine steps a pipeline of three commands will cost before "
                "any of them has run.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The process tree: fork, exec, wait and the status",
        tags=["processes", "status", "reaping"],
        action="Write `RUN_KEYS`, `run_pipeline`, `spawn_command`, `collect` and "
               "`pipeline_status` in stage_04.py.",
        predict="Which command's status a pipeline answers with, and what a "
                "pipeline owes the machine when it is over.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="The job table: background, stopped, and who waits for whom",
        tags=["jobs", "background", "control"],
        action="Write `JOB_KEYS`, `JOB_STATES`, `background`, `stop`, `resume`, "
               "`jobs` and `resolve` in stage_05.py.",
        predict="What a shell has to remember about a process it decided not to "
                "wait for, and which of those facts a `jobs` listing is allowed "
                "to lose.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Signals, traps, and what a signal does to a job",
        tags=["signals", "traps", "status"],
        action="Write `TRAP_KEYS`, `STATUS_KEYS`, `deliver`, `trap`, `run_traps` "
               "and `status_of` in stage_06.py.",
        predict="What the shell's status is after a trap has run, and why a trap "
                "may not fire in the middle of a pipeline.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="The builtins that must not fork",
        tags=["builtins", "state", "fork"],
        action="Write `BUILTIN_KEYS`, `BUILTIN_STATES`, `is_builtin` and "
               "`run_builtin` in stage_07.py.",
        predict="Why `cd` in a child process changes nothing, and how a check can "
                "see the difference without reading the source.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="Lists, conditions and the rules of `set -e`",
        tags=["errexit", "conditions", "short-circuit"],
        action="Write `LISTS_KEYS`, `STATUS_KINDS`, `run_lists`, `exempt` and "
               "`condition_of` in stage_08.py.",
        predict="Which non-zero statuses stop a shell under `set -e` and which "
                "ones it is required to ignore, and what a short-circuited list "
                "still owes the record.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The session, replayed byte for byte",
        tags=["session", "replay", "transcript"],
        action="Write `SESSION_KEYS` and `run_session` in stage_09.py.",
        predict="What a whole session owes the world when the world already holds "
                "the transcript it has to produce, and what leaks between two "
                "sessions if a stage is careless.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="Exit codes, and the audit of a session's statuses",
        tags=["exit-codes", "audit", "diagnosis"],
        action="Write `AUDIT_KEYS`, `AUDIT_REASONS`, `VERDICTS` and `audit` in "
               "stage_10.py.",
        predict="Why 127 and 126 are two different kingdoms, what 128 plus a "
                "number is, and how a reason can be decided from the evidence "
                "without ever reading the expected answer.",
        check=check_10,
    ),
]
