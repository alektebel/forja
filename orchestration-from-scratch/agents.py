"""agents.py — the model as a callable, PROVIDED COMPLETE.

An `Agent` is a script, not a model: attempt 1, 2, 3 … are the entries of its
plan, and a plan that runs out repeats its last entry. It answers a `Reply` —
the text it produced, and what the call cost in tokens — and `calls` counts how
many times it was invoked, which is what a rework check asserts ("the node was
called twice, not once and not three times").

What the text *means* is not this file's business. `VERDICTS` is what a reviewer
may say and `APPROVALS` is what a human may say, and turning a `Reply` into
"accepted", "rework", "denied" or "failed" is stage 5's and stage 7's. What the
call *cost* is this file's business: `Reply.tokens` is an int — the budget in
stage 8 spends exactly this number — so nothing here ever builds a float.

Every factory takes `tokens=`: what one call of that script costs. It defaults
to `DEFAULT_TOKENS` (nothing), so a script that is supposed to spend has to be
told what it spends — `worker("index the pages", tokens=32)`.

Nothing here reads a clock, a network or a file, and nothing here is module
level state: an `Agent` counts its own calls, the factories build fresh ones,
and two runs of the same script answer the same bytes.
"""

from dataclasses import dataclass
import types

#: What one call of a script costs when the script does not say: nothing.
DEFAULT_TOKENS = 0

#: What a reviewer may say about a result. Anything that is not one of these
#: two texts is not a verdict, and a result is never accepted on a guess.
VERDICTS = ("accept", "reject")

#: What a human may say about an effect. Anything that is not one of these two
#: texts is not an approval, and an effect is never dispatched on a guess.
APPROVALS = ("approve", "deny")


class AgentError(ValueError):
    """A script, a plan or an answer the model refuses.

    The model's own refusal — a verdict outside `VERDICTS`, an approval outside
    `APPROVALS`, an empty plan, a shape `bad_shape` does not have, an attempt
    that is not a positive int — travels as this type, so a check can tell "your
    script is wrong" from "the work went wrong".
    """


def _require_int(value, what, *, minimum=0):
    """The house guard: a bool is not an int, and neither is a string."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise AgentError("%s must be an int, got %r" % (what, value))
    if value < minimum:
        raise AgentError("%s must be >= %d, got %r" % (what, minimum, value))
    return value


def _require_text(value, what):
    """The other half of the guard: a script answers strings."""
    if not isinstance(value, str):
        raise AgentError("%s must be a string, got %r" % (what, value))
    return value


@dataclass(frozen=True)
class Reply:
    """What an agent answered: its text, and what the call cost.

    `tokens` is money: stage 8 spends exactly this number, so it is an int and
    never a float. It is *not* the verdict — a verdict lives in `text`, and a
    reply read from its tokens is the mistake stage 5 exists to prevent.

    The record is frozen but not policed: `Reply` is what a well-formed answer
    is, and an answer that is not one — a bare string, a record with no
    `tokens`, a negative cost — is built by `bad_shape` and refused by the
    caller, not by this class.
    """

    text: str
    tokens: int = DEFAULT_TOKENS


class Agent:
    """A scripted agent: `agent(prompt, *, attempt=1) -> Reply`.

    `calls` counts invocations and `attempts` counts them per prompt, which is
    what a rework check asserts ("the node was called twice, not once and not
    three times"). The agent never reads the clock and never guesses: it answers
    what its plan says for that attempt.

    An answer is passed through exactly as the script gives it — an agent that
    answers something that is not a `Reply` (`bad_shape`) is a defect the caller
    has to refuse, not one this class hides by inventing a reply.
    """

    def __init__(self, fn, *, label=None):
        if not callable(fn):
            raise AgentError("Agent needs a callable, got %r"
                             % (type(fn).__name__,))
        self._fn = fn
        self.label = label or getattr(fn, "__name__", "agent")
        self.calls = 0
        self.attempts = {}

    def __call__(self, prompt, *, attempt=1):
        _require_int(attempt, "attempt", minimum=1)
        key = prompt if isinstance(prompt, str) else repr(prompt)
        self.calls += 1
        self.attempts[key] = self.attempts.get(key, 0) + 1
        return self._fn(prompt, attempt)

    def __repr__(self):
        return "<Agent %s calls=%d>" % (self.label, self.calls)


def _script(steps, *, label, tokens):
    """A plan of `steps`, one per attempt, repeating its last entry: the
    scheduler's script, with the cost every call of it reports."""
    steps = tuple(steps)
    if not steps:
        raise AgentError("%s() needs at least one entry" % (label,))
    for step in steps:
        _require_text(step, "%s() entry" % (label,))

    def fn(prompt, attempt):
        step = steps[min(attempt, len(steps)) - 1]
        return Reply(step, tokens)
    return Agent(fn, label=label)


def _verdict_script(steps, allowed, *, label, tokens):
    """The same plan, with every entry checked against what that actor may say:
    a reviewer that can answer "maybe" is a graph nobody can decide."""
    steps = tuple(steps)
    if not steps:
        raise AgentError("%s() needs at least one verdict" % (label,))
    for verdict in steps:
        if verdict not in allowed:
            raise AgentError("%s(%s): %r is not one of %r"
                             % (label, ", ".join(repr(step) for step in steps),
                                verdict, allowed))
    return _script(steps, label=label, tokens=tokens)


def planner(*texts, tokens=DEFAULT_TOKENS):
    """A planner, scripted by attempt: attempt 1 answers `texts[0]`, attempt 2
    answers `texts[1]`, and a plan that runs out repeats its last entry."""
    _require_int(tokens, "tokens")
    return _script(texts, label="planner", tokens=tokens)


def worker(*texts, tokens=DEFAULT_TOKENS):
    """A worker, scripted by attempt, like fleet's `scripted`:
    `worker("index 12 files")` answers the same thing on every attempt."""
    _require_int(tokens, "tokens")
    return _script(texts, label="worker", tokens=tokens)


def reviewer(*verdicts, tokens=DEFAULT_TOKENS):
    """A reviewer, scripted by attempt, in `VERDICTS`: `reviewer("reject",
    "accept")` rejects the first attempt and accepts the rework."""
    _require_int(tokens, "tokens")
    return _verdict_script(verdicts, VERDICTS, label="reviewer", tokens=tokens)


def approver(*verdicts, tokens=DEFAULT_TOKENS):
    """A human, scripted by attempt, in `APPROVALS`: `approver("deny",
    "approve")` denies the first ask and approves the second."""
    _require_int(tokens, "tokens")
    return _verdict_script(verdicts, APPROVALS, label="approver", tokens=tokens)


def flaky_agent(*texts, failures=2, tokens=DEFAULT_TOKENS):
    """A script that fails the first `failures` attempts and then works: attempt
    `failures + 1` answers `texts[0]`, the next `texts[1]`, and so on.

    A failed attempt answers `"reject"` — in this course what a bad call looks
    like is an answer that is not an acceptance — so `flaky_agent("accept",
    failures=2)` rejects twice and accepts the third attempt, which is how far
    `MAX_REWORK` lets a node go. Every attempt costs `tokens`, the failures
    included: the call happened.
    """
    _require_int(failures, "failures")
    _require_int(tokens, "tokens")
    steps = tuple(texts)
    if not steps:
        raise AgentError("flaky_agent() needs at least one entry")
    for step in steps:
        _require_text(step, "flaky_agent() entry")

    def fn(prompt, attempt):
        if attempt <= failures:
            return Reply("reject", tokens)
        return Reply(steps[min(attempt - failures, len(steps)) - 1], tokens)
    return Agent(fn, label="flaky_agent")


def refuser(reason, *, tokens=DEFAULT_TOKENS):
    """An actor that never accepts: every attempt answers `reason` — the text a
    reviewer that rejects puts in its `Reply`, and the reason a rework prompt
    carries back to the node."""
    _require_text(reason, "refuser() reason")
    _require_int(tokens, "tokens")

    def fn(prompt, attempt):
        return Reply(reason, tokens)
    return Agent(fn, label="refuser")


def bad_shape(shape="string"):
    """An agent that answers something that is not a `Reply` at all, so the
    caller has to refuse the answer instead of filing it as a success:

    `string`     the whole answer is a `str`, not a record;
    `no_tokens`  a record without the `tokens` field;
    `bad_tokens` a `tokens` that is not an int;
    `negative`   a negative cost, which no call can have.
    """
    shapes = {
        "string": lambda prompt, attempt: "done",
        "no_tokens": lambda prompt, attempt: types.SimpleNamespace(text="done"),
        "bad_tokens": lambda prompt, attempt: Reply("done", "0"),
        "negative": lambda prompt, attempt: Reply("done", -1),
    }
    if shape not in shapes:
        raise AgentError("bad_shape(%r): want one of %r" % (shape, tuple(shapes)))
    return Agent(shapes[shape], label="bad_shape_%s" % shape)
