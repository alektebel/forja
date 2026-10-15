"""Agent Harness From Scratch — course manifest.

Ten graded stages that build the runtime UNDER an agent, with the model as a
callable: the event stream one model call returns and its single reduction into a
turn, a prompt budget recomputed from the bytes rather than trusted to a
tokenizer, the loop whose exhaustion is an outcome and not an exception, dispatch
where an unknown tool is a message the model can read and repair, streaming with
the arrival timings of a turn, retries that stop the moment anything has been
forwarded, compaction that summarizes the middle while pinning the system message
and never orphaning an observation, the trace that keeps the shape of a run and
none of its payloads, the process reward that makes every step earn its place by
citing the result before it, and the verifier plus the self-generated data loop
whose accuracy is measured where the agent has not been.

The domain is provided (`tiny_env.py`: three tables, a scripted model, a manual
clock, four analytic tasks and the question templates). The harness is the
exercise: no network, no sockets, no wall clock — every model is scripted and
every backoff waits on a clock the test moves by hand.

    python3 codecraft/cli.py run agent-harness-from-scratch
"""

from codecraft.api import stage

TITLE = "Agent Harness From Scratch"
DESCRIPTION = ("The runtime under an agent, with the model as a callable: collect "
               "an event stream into one turn, keep the prompt inside a token "
               "budget, run the loop where a spent budget is an outcome, dispatch "
               "tool calls so an unknown tool is an observation, stream a turn "
               "with TTFT and inter-token timings, retry only before anything was "
               "forwarded, compact by summarizing the middle while pinning the "
               "system message, trace six keys of shape and no payloads, reward a "
               "step for being grounded and novel, and verify answers the "
               "generator drew from the executor — with a self-improving round "
               "measured on tasks it did not make.")
LEVEL = "intermediate"
ORDER = 13

# --- the checks. Each one is self-contained: its fixtures are nested
# inside it because `course.py` is one namespace for ten stages.

import os
import sys
import tempfile
import shutil
import json


def check_1():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    import stage_01 as s
    from tiny_env import HarnessError, ScriptedModel, text_events, tool_call_events

    def refused(call, where):
        try:
            value = call()
        except HarnessError as exc:
            return str(exc)
        raise AssertionError(
            "%s: expected a HarnessError, got %r — a harness that guesses here "
            "makes a dropped connection look like a finished turn" % (where, value))

    # --- text deltas append, usage sums --------------------------------------
    turn = s.collect([{"type": "text", "text": "Hel"},
                      {"type": "text", "text": "lo"},
                      {"type": "usage", "input_tokens": 7, "output_tokens": 2},
                      {"type": "usage", "input_tokens": 3, "output_tokens": 1},
                      {"type": "end", "reason": "stop"}])
    assert turn["text"] == "Hello", (
        "text events are DELTAS and append; keeping the last one is how a streamed "
        "answer becomes a one-word answer: %r" % (turn["text"],))
    assert turn["usage"] == {"input_tokens": 10, "output_tokens": 3}, (
        "every usage event is summed; a call that reports usage twice must be "
        "billed once and correctly: %r" % (turn["usage"],))
    assert turn["reason"] == "stop", turn["reason"]
    assert turn["tool_calls"] == [], (
        "a turn with no tool calls carries an empty list: %r" % (turn["tool_calls"],))

    # a model that never reported usage costs zero, not None
    quiet = s.collect([{"type": "end", "reason": "stop"}])
    assert quiet["usage"] == {"input_tokens": 0, "output_tokens": 0}, (
        "usage nobody reported is zeros, so a caller can sum a run without a "
        "special case: %r" % (quiet["usage"],))

    # the reason is the model's, and "length" is not "stop"
    truncated = s.collect([{"type": "text", "text": "half"},
                           {"type": "end", "reason": "length"}])
    assert truncated["reason"] == "length", (
        "the end event is the ONLY source of the reason: a truncated turn is not a "
        "finished one, got %r" % (truncated["reason"],))

    # --- tool calls keep their order, their id, and do not alias the events ---
    events = tool_call_events(("run_sql", {"sql": "SELECT 1"}),
                              ("run_sql", {"sql": "SELECT 2"}))
    turn = s.collect(events)
    assert [call["name"] for call in turn["tool_calls"]] == ["run_sql", "run_sql"], (
        "tool calls keep the order the model asked in, or the answers land on the "
        "wrong questions: %r" % (turn["tool_calls"],))
    assert [call["id"] for call in turn["tool_calls"]] == ["call_0_run_sql",
                                                          "call_1_run_sql"], (
        "the ids travel with the calls: %r" % (turn["tool_calls"],))
    events[0]["arguments"]["sql"] = "DROP TABLE sales"
    assert turn["tool_calls"][0]["arguments"] == {"sql": "SELECT 1"}, (
        "the turn must COPY a tool call's arguments: a harness holding the "
        "provider's own dict hands out a live wire, %r"
        % (turn["tool_calls"][0]["arguments"],))

    # --- a tool call with no id is not a call you can answer ------------------
    refused(lambda: s.collect([{"type": "tool_call", "name": "run_sql",
                                "arguments": {}},
                               {"type": "end", "reason": "tool_calls"}]),
            "a tool_call with no id")

    # --- no end, or more after the end ---------------------------------------
    refused(lambda: s.collect([{"type": "text", "text": "half a sentence"}]),
            "a stream that ended without an end event")
    refused(lambda: s.collect([{"type": "end", "reason": "stop"},
                               {"type": "text", "text": "and one more thing"}]),
            "an event after the end event")
    refused(lambda: s.collect([{"type": "end", "reason": "stop"},
                               {"type": "usage", "input_tokens": 1}]),
            "a usage event after the end event")
    refused(lambda: s.collect([{"type": "audio", "bytes": "…"},
                               {"type": "end", "reason": "stop"}]),
            "an event type nobody knows")

    # --- it is a stream: consumed once, and it works on a real model ----------
    model = ScriptedModel([tool_call_events(("run_sql", {"sql": "SELECT 1"}),
                                            text="let me look")])
    turn = s.collect(model([{"role": "user", "content": "how many sales?"}]))
    assert turn["text"] == "let me look" and turn["reason"] == "tool_calls", (
        "collect must work on a streamed turn from the model callable: %r" % (turn,))

    # --- the wire message ----------------------------------------------------
    turn = s.collect([{"type": "text", "text": "done"},
                      {"type": "end", "reason": "stop"}])
    message = s.assistant_message(turn)
    assert message == {"role": "assistant", "content": "done"}, (
        "an assistant message with no tool calls carries NO tool_calls key — not "
        "an empty list: several providers reject the empty list, and the key "
        "itself means 'this message asks for tools': %r" % (message,))
    asked = s.assistant_message(s.collect(tool_call_events(("run_sql",
                                                            {"sql": "SELECT 1"}))))
    assert asked["role"] == "assistant" and asked["tool_calls"][0]["name"] == "run_sql", (
        "a message that asked for a tool carries the calls: %r" % (asked,))
    assert asked["content"] == "", (
        "a turn that only called tools has empty text, not a missing key: %r"
        % (asked,))

    turn = s.collect([{"type": "text", "text": "hi"},
                      {"type": "end", "reason": "stop"}])
    first = s.assistant_message(turn)
    first["content"] = "tampered"
    assert s.assistant_message(turn)["content"] == "hi", (
        "assistant_message must return a FRESH message: the caller appends it to "
        "the conversation and then edits the conversation, and the turn it came "
        "from may not change under it")

    # --- usage arithmetic ----------------------------------------------------
    assert s.usage_add({"input_tokens": 1}, {"output_tokens": 2}) == \
        {"input_tokens": 1, "output_tokens": 2}, "missing keys default to 0"
    assert s.usage_add(s.EMPTY_USAGE, s.EMPTY_USAGE) == s.EMPTY_USAGE
    refused(lambda: s.usage_add({"input_tokens": True}, {}),
            "a boolean token count")
    refused(lambda: s.usage_add({"output_tokens": -1}, {}),
            "a negative token count")
    refused(lambda: s.usage_add({"input_tokens": "10"}, {}),
            "a token count that is a string")

def check_2():
    REPO = os.environ.get("COURSE_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    COURSE = os.path.join(REPO, "agent-harness-from-scratch")

    def build():
        """A temp dir holding the course as the runner assembles it: `*.py` copied and
        `solutions/*.py` overlaid flat, then that dir (and the repo root) on sys.path."""
        work = tempfile.mkdtemp(prefix="e1-check02-")
        for name in sorted(os.listdir(COURSE)):
            source = os.path.join(COURSE, name)
            if os.path.isfile(source) and name.endswith(".py"):
                shutil.copy(source, os.path.join(work, name))
        solutions = os.path.join(COURSE, "solutions")
        for name in sorted(os.listdir(solutions)):
            if name.endswith(".py"):
                shutil.copy(os.path.join(solutions, name), os.path.join(work, name))
        for path in (REPO, work):
            if path in sys.path:
                sys.path.remove(path)
            sys.path.insert(0, path)
        return work

    import json

    def _fail(message):
        raise AssertionError(message)

    def _tokens(message):
        """The DOCUMENTED rule, computed here independently of the stage, so a
        wrong estimator cannot agree with the budget arithmetic below: 4 chars
        per token rounded up, +4 per message, plus the canonical JSON of
        `tool_calls` when there is one."""
        chars = len(message.get("content") or "")
        calls = message.get("tool_calls")
        if calls:
            chars += len(json.dumps(calls, sort_keys=True, separators=(",", ":")))
        return 4 + -(-chars // 4)

    def _harness_error(fn, where, parts=()):
        """Fail unless fn() refuses with a HarnessError naming the mistake."""
        try:
            result = fn()
        except tiny_env.HarnessError as exc:
            for part in parts:
                if part not in str(exc):
                    _fail("%s: the error must name the mistake (%r), got %r"
                          % (where, part, str(exc)))
            return exc
        except AssertionError:
            raise
        except Exception as exc:
            _fail("%s: expected HarnessError, got %s: %s"
                  % (where, type(exc).__name__, exc))
        _fail("%s: expected HarnessError, but the call returned %r" % (where, result))

    def _message(role, content="", **extra):
        message = {"role": role, "content": content}
        message.update(extra)
        return message

    def _assistant(call_id, sql, text=""):
        return _message("assistant", text,
                        tool_calls=[{"id": call_id, "name": "run_sql",
                                     "arguments": {"sql": sql}}])

    def _render(result):
        """A warehouse result as the text table an observation carries."""
        lines = [" | ".join(result["columns"])]
        for row in result["rows"]:
            lines.append(" | ".join("" if cell is None else str(cell) for cell in row))
        lines.append("(%d rows)" % len(result["rows"]))
        return "\n".join(lines)

    def _kept_tokens(messages):
        return sum(_tokens(message) for message in messages)

    def _pairs_whole(messages, history, where):
        """A call and its observation are kept or dropped TOGETHER: nothing may
        read an observation whose request is gone, and nothing may keep a request
        whose observation the history answered."""
        answered = {m["tool_call_id"] for m in history if m["role"] == "tool"}
        kept_answers = {m["tool_call_id"] for m in messages if m["role"] == "tool"}
        held = set()
        for message in messages:
            if message["role"] == "tool" and message["tool_call_id"] not in held:
                _fail("%s: the observation for %r was kept while the assistant "
                      "message that asked for it was dropped — a call/observation "
                      "pair was split"
                      % (where, message["tool_call_id"]))
            for call in message.get("tool_calls") or ():
                held.add(call["id"])
                if call["id"] in answered and call["id"] not in kept_answers:
                    _fail("%s: the assistant message that asked for %r was kept "
                          "while its observation was dropped — a call/observation "
                          "pair was split" % (where, call["id"]))

    import tiny_env
    import stage_02 as stage

    for name in ("estimate_tokens", "Context", "assemble"):
        if not hasattr(stage, name):
            _fail("stage_02 must define %s" % name)

    # -- the estimator is a fixed rule, and it is arithmetic ----------------
    for message, expected, why in (
            (_message("user", ""), 4, "an empty message costs the +4 envelope"),
            (_message("user", "abc"), 5, "3 characters round UP to 1 token"),
            (_message("user", "abcd"), 5, "4 characters are 1 token"),
            (_message("user", "abcde"), 6, "5 characters round UP to 2 tokens"),
            (_message("tool", "x" * 400, tool_call_id="call_1", is_error=False),
             104, "400 characters are 100 tokens"),
            (_message("assistant", "", tool_calls=[]), 4,
             "an EMPTY tool_calls list adds nothing (the wire shape omits it)")):
        got = stage.estimate_tokens(message)
        if got != expected:
            _fail("estimate_tokens: %s, so %d characters must be %d tokens, got %d"
                  % (why, len(message.get("content") or ""), expected, got))
        if got != _tokens(message):
            _fail("estimate_tokens does not follow the documented rule (4 chars per "
                  "token rounded up, +4 per message, plus the canonical JSON of "
                  "tool_calls): got %d, the rule says %d for %r"
                  % (got, _tokens(message), message))

    env = tiny_env.SQLEnv()
    sql = ("SELECT c.country, s.category, SUM(s.revenue) AS total "
           "FROM sales AS s JOIN customers AS c ON c.country = s.country "
           "WHERE s.category IN ('furniture', 'electronics', 'books') "
           "GROUP BY c.country, s.category ORDER BY total DESC, c.country ASC")
    observation = _render(env.exec(sql))
    long_sql = ("SELECT category, SUM(revenue) AS total FROM sales WHERE "
                + " OR ".join("(country = 'ZZ%03d' AND category <> 'none')" % index
                              for index in range(60))
                + " GROUP BY category ORDER BY total DESC")
    long_observation = _render(env.exec(long_sql))

    asking = _assistant("call_1_run_sql", sql, text="I will query the warehouse.")
    bare = _message("assistant", "I will query the warehouse.")
    if stage.estimate_tokens(asking) != _tokens(asking):
        _fail("estimate_tokens is not pricing tool_calls by the documented rule: the "
              "canonical JSON of the calls (compact, keys sorted — the bytes a "
              "provider sends), not repr() and not zero: got %d, the rule says %d for "
              "a %d-character SQL argument"
              % (stage.estimate_tokens(asking), _tokens(asking), len(sql)))
    delta = stage.estimate_tokens(asking) - stage.estimate_tokens(bare)
    if delta < len(sql) // 4:
        _fail("tool_calls missing from the estimate: the %d-character SQL query must "
              "cost at least %d tokens more than the same message without it, it cost "
              "%d — a 2 KB statement must not be free"
              % (len(sql), len(sql) // 4, delta))

    huge = _assistant("call_2_run_sql", long_sql)
    if stage.estimate_tokens(huge) < 500:
        _fail("estimate_tokens: a %d-character SQL statement in tool_calls must cost "
              "hundreds of tokens, got %d — tool_calls is priced at zero"
              % (len(long_sql), stage.estimate_tokens(huge)))

    system = _message("system", "You are a careful analyst.")
    system_tokens = _tokens(system)

    # -- the whole history fits: system FIRST, newest LAST -------------------
    history = [
        _message("user", "Which category has the highest total revenue?"),
        asking,
        _message("tool", observation, tool_call_id="call_1_run_sql", is_error=False),
        _message("assistant", "Furniture."),
        _message("user", "Now break that down by country."),
    ]
    everything = system_tokens + _kept_tokens(history)

    result = stage.assemble(system, history, budget_tokens=everything)
    if not isinstance(result, list):
        _fail("assemble must return a list of messages, got %s"
              % type(result).__name__)
    if result[0] != system or result[0]["role"] != "system":
        _fail("the system message is dropped or not first: the prompt budget is not a "
              "reason to forget the harness's own instructions (got %r first)"
              % (result[0],))
    if result != [system] + history:
        _fail("with room for everything, assemble must keep the history in order "
              "(oldest kept first, NEWEST LAST, system first): got %r"
              % ([message.get("content") for message in result],))
    if stage.assemble(system, history, budget_tokens=everything) != result:
        _fail("assemble is not deterministic: two identical calls disagreed")

    context = stage.Context(system, budget_tokens=everything)
    if context.messages is context.messages:
        _fail("Context.messages hands out its own list: a caller appending to it "
              "would corrupt the context")
    if context.messages != [system]:
        _fail("a fresh context holds exactly its system message, got %r"
              % (context.messages,))
    if context.budget != everything:
        _fail("with no reserve the prompt budget is the whole window: expected %d, "
              "got %d" % (everything, context.budget))
    for message in history:
        context.add(message)
    if context.messages != [system] + history:
        _fail("the context kept everything (the budget was exactly enough) but its "
              "messages are %r"
              % ([message.get("content") for message in context.messages],))
    if context.tokens() != everything:
        _fail("Context.tokens() must be the sum of estimate_tokens() over .messages "
              "(the system message included): expected %d, got %d"
              % (everything, context.tokens()))
    if context.fits() is not True:
        _fail("a prompt exactly at the budget fits: fits() said %r" % (context.fits(),))

    # -- the reserve is the completion's room: it shrinks the PROMPT budget ---
    reserve = 30
    pressured = stage.Context(system, budget_tokens=everything, reserve_tokens=reserve)
    if pressured.budget != everything - reserve:
        _fail("the reserve is not subtracted from the budget: at a window of %d with a "
              "reserve of %d the prompt budget must be %d, got %d"
              % (everything, reserve, everything - reserve, pressured.budget))
    for message in history:
        pressured.add(message)
    if pressured.tokens() > pressured.budget:
        _fail("the trimmed prompt is still over its budget: %d tokens against a prompt "
              "budget of %d" % (pressured.tokens(), pressured.budget))
    if len(pressured.messages) >= len(history) + 1:
        _fail("the reserve was ignored: a prompt that exactly fills the window leaves "
              "the completion no tokens, so at least one message must be dropped "
              "(kept %d of %d)" % (len(pressured.messages) - 1, len(history)))
    if pressured.messages[0] != system:
        _fail("the system message was dropped while trimming against the reserve")
    if pressured.messages[-1] != history[-1]:
        _fail("newest wins: the newest message must still be last, got %r"
              % (pressured.messages[-1],))

    # -- fits() is the PROMPT budget, not the window -------------------------
    over = stage.Context(system, budget_tokens=200, reserve_tokens=100)
    over.add(_message("user", "x" * 400))          # 104 tokens of message
    if over.tokens() != system_tokens + 104:
        _fail("a context holding the system message and a 400-character message is "
              "%d tokens, got %d" % (system_tokens + 104, over.tokens()))
    if over.fits() is not False:
        _fail("fits() ignored the reserve: %d tokens against a prompt budget of %d "
              "(the window is 200, but 100 of it is the completion's) must not fit"
              % (over.tokens(), over.budget))

    # -- the newest unit stays even when it is what does not fit -------------
    tight = stage.Context(system, budget_tokens=everything)
    for message in history:
        tight.add(message)
    tight.add(_message("user", "y" * 4000))
    if tight.messages[-1].get("content") != "y" * 4000:
        _fail("newest wins: an over-budget newest message must stay (the context "
              "reports it through fits(), it does not drop the question it was "
              "built around)")
    if tight.fits() is not False:
        _fail("an over-budget context must report fits() False, got %r"
              % (tight.fits(),))

    # -- tool_calls is counted when the budget decides -----------------------
    newest = _message("user", "and now?")
    long_request = _assistant("call_2_run_sql", long_sql)
    long_obs = _message("tool", long_observation, tool_call_id="call_2_run_sql",
                        is_error=False)
    long_history = [long_request, long_obs, newest]
    # Room for: the envelope of the request (+4, which is ALL it costs if its SQL
    # is priced at zero), its observation, and the newest question. An estimator
    # that ignores tool_calls keeps the whole 2 KB turn; the real price of the
    # statement does not fit, so the pair goes and the question stays.
    room = system_tokens + 4 + _tokens(long_obs) + _tokens(newest)
    kept = stage.assemble(system, long_history, budget_tokens=room)
    # The pair check comes first: a trim that walks messages instead of turns
    # leaves the observation behind, and that is a SPLIT, not a pricing bug.
    _pairs_whole(kept, long_history, "assemble with a 2 KB tool call")
    if kept != [system, newest]:
        _fail("tool_calls is missing from the estimate: the %d-character SQL request "
              "and the observation it earned do not fit these %d tokens (only the "
              "newest question does), got %r"
              % (len(long_sql), room,
                 [message.get("content") for message in kept]))

    # -- a pair is dropped or kept TOGETHER ---------------------------------
    # After dropping the assistant that asked for the SQL, the observation alone
    # would fit exactly; a trim that walks MESSAGES instead of turns leaves it
    # orphaned, and the result would start with an observation whose request is
    # gone.
    obs = _message("tool", observation, tool_call_id="call_1_run_sql", is_error=False)
    pair_history = [_message("user", "hi"), asking, obs, newest]
    exact = system_tokens + _tokens(obs) + _tokens(newest)
    pair_result = stage.assemble(system, pair_history, budget_tokens=exact)
    if pair_result != [system, newest]:
        _fail("a call/observation pair was split: with exactly enough room for the "
              "observation and the newest question, the assistant message that asked "
              "for it must go WITH it; got %r"
              % ([message.get("content") for message in pair_result],))
    _pairs_whole(pair_result, pair_history, "assemble over a call/observation pair")

    # -- the front door: an orphan observation and a second system message ---
    guard = stage.Context(system, budget_tokens=1000)
    guard.add(_message("user", "hi"))
    _harness_error(
        lambda: guard.add(_message("tool", "(0 rows)", tool_call_id="call_9",
                                   is_error=False)),
        "add() of a tool observation whose assistant message is not in the context",
        parts=("call_9",))
    _harness_error(lambda: guard.add(_message("system", "Be terse.")),
                   "add() of a second system message", parts=("system",))

    # -- an impossible prompt is refused, not truncated ---------------------
    too_big = _message("system", "x" * 4000)          # 1004 tokens
    _harness_error(lambda: stage.assemble(too_big, history, budget_tokens=100),
                   "assemble with a system message over the prompt budget",
                   parts=("system",))
    _harness_error(lambda: stage.Context(too_big, budget_tokens=100),
                   "Context with a system message over the prompt budget",
                   parts=("system",))
    _harness_error(lambda: stage.Context(system, budget_tokens=100, reserve_tokens=100),
                   "Context whose reserve leaves no prompt budget at all",
                   parts=("system",))

    # -- a negative reserve is not free completion tokens -------------------
    _harness_error(lambda: stage.Context(system, budget_tokens=100, reserve_tokens=-1),
                   "Context with a negative reserve (it would GROW the prompt budget)",
                   parts=("reserve_tokens",))

def check_3():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    class FakeTrace:
        """Whatever stage 3 needs of stage 8: a `.step(**kwargs)` sink."""

        def __init__(self):
            self.lines = []

        def step(self, **line):
            self.lines.append(dict(line))
            return line

    import stage_03 as s
    from tiny_env import (EnvError, HarnessError, ManualClock, ScriptedModel,
                          SQLEnv, text_events, tool_call_events)

    env = SQLEnv()
    TOOLS = [{"name": "run_sql", "description": "run one read",
              "inputSchema": {"type": "object",
                              "properties": {"sql": {"type": "string"}},
                              "required": ["sql"]}}]
    called = []

    def dispatch(call):
        """A stand-in for stage 4: it records the call and answers it."""
        called.append(call["name"])
        try:
            rows = env.exec(call["arguments"]["sql"])["rows"]
        except EnvError as exc:
            return {"role": "tool", "tool_call_id": call["id"],
                    "content": str(exc), "is_error": True}
        return {"role": "tool", "tool_call_id": call["id"],
                "content": "%d row(s)" % len(rows), "is_error": False}

    def roles(messages):
        return [message["role"] for message in messages]

    # --- a two-step run: ask for a tool, then answer -------------------------
    model = ScriptedModel([
        tool_call_events(("run_sql", {"sql": "SELECT COUNT(*) FROM sales"}),
                         text="Let me check."),
        text_events("There are 10 sales."),
    ])
    bill = {}
    trace = FakeTrace()
    result = s.run(model, dispatch, "How many sales?", system="You are an analyst.",
                   tools=TOOLS, trace=trace, usage=bill, clock=ManualClock())
    assert result["status"] == "done", (
        "a turn that ends with reason 'stop' finishes the run: %r" % (result,))
    assert result["answer"] == "There are 10 sales.", (
        "the answer is the LAST text the model produced, not the first: %r"
        % (result["answer"],))
    assert roles(result["messages"]) == ["system", "user", "assistant", "tool",
                                        "assistant"], (
        "the conversation is system, question, the turn that asked for a tool, its "
        "observation, and the answering turn — in that order: %r"
        % (roles(result["messages"]),))
    assert result["steps"] == 2, "two model calls, two steps: %r" % (result["steps"],)
    assert model.tools_seen == [TOOLS, TOOLS], (
        "every model call is offered the same tools: %r" % (model.tools_seen,))
    asked = result["messages"][2]
    observation = result["messages"][3]
    assert asked["tool_calls"][0]["id"] == observation["tool_call_id"], (
        "the observation answers the call by id: %r"
        % (asked["tool_calls"][0]["id"], observation.get("tool_call_id")))
    assert result["usage"] == {"input_tokens": 20, "output_tokens": 10}, (
        "usage is summed over the run's calls: %r" % (result["usage"],))
    assert bill == {"input_tokens": 20, "output_tokens": 10}, (
        "the caller's usage dict is UPDATED in place (it is the run's bill and it "
        "survives the run): %r" % (bill,))
    assert [line["kind"] for line in trace.lines] == ["model", "tool", "model"], (
        "the trace holds one model step per call and one tool step per tool call: %r"
        % (trace.lines,))
    assert [line.get("tool") for line in trace.lines] == [None, "run_sql", None], (
        "a tool step names its tool: %r" % (trace.lines,))

    # --- the budget: a state, with the work that happened --------------------
    called.clear()
    model = ScriptedModel([
        tool_call_events(("run_sql", {"sql": "SELECT COUNT(*) FROM sales"})),
        text_events("never reached"),
    ])
    result = s.run(model, dispatch, "How many sales?", max_steps=1)
    assert result["status"] == "budget", (
        "running out of steps is an OUTCOME, not an exception: %r" % (result,))
    assert result["steps"] == 1 and len(model.calls) == 1, (
        "the budget counts MODEL CALLS and the model is not asked once more to "
        "finish cleanly: steps=%r calls=%r" % (result["steps"], len(model.calls)))
    assert called == ["run_sql"], (
        "the tool the last allowed turn asked for still runs: %r" % (called,))
    assert roles(result["messages"]) == ["user", "assistant", "tool"], (
        "the partial conversation is returned, in order: %r"
        % (roles(result["messages"]),))
    assert result["answer"] == "", result["answer"]

    # zero steps means the model is never called at all
    model = ScriptedModel([text_events("should not be reached")])
    result = s.run(model, dispatch, "anything", max_steps=0)
    assert result["status"] == "budget" and result["steps"] == 0, (
        "max_steps=0 is a run with no calls, not a run with one: %r" % (result,))
    assert model.calls == [], (
        "the model was called with max_steps=0: %r" % (model.calls,))

    # --- a truncated turn is not a finished one ------------------------------
    called.clear()
    model = ScriptedModel([[{"type": "text", "text": "half a sentence"},
                            {"type": "end", "reason": "length"}]])
    result = s.run(model, dispatch, "anything")
    assert result["status"] == "truncated", (
        "reason 'length' means the model was cut off; calling that done sends half "
        "a sentence to a person: %r" % (result,))
    assert result["answer"] == "half a sentence", result["answer"]
    assert called == [], "a truncated turn asked for no tools: %r" % (called,)

    # --- a reason the turn cannot back up ------------------------------------
    model = ScriptedModel([[{"type": "usage", "input_tokens": 1, "output_tokens": 1},
                            {"type": "end", "reason": "tool_calls"}]])
    try:
        s.run(model, dispatch, "anything")
    except HarnessError as exc:
        assert "tool_calls" in str(exc), str(exc)
    else:
        raise AssertionError(
            "a turn that says 'tool_calls' and asks for none was accepted: treating "
            "that as done ends the conversation while the model believes it is "
            "mid-action")

    # --- a stop reason nobody defined is not a finish ------------------------
    model = ScriptedModel([[{"type": "text", "text": "I cannot help with that."},
                            {"type": "end", "reason": "content_filter"}]])
    try:
        s.run(model, dispatch, "anything")
    except HarnessError:
        pass
    else:
        raise AssertionError(
            "an end reason this harness has never seen was treated as a finished "
            "run: a stop reason is a contract, and guessing at a new one is how a "
            "refusal becomes an answer")

    # --- two tool calls in one turn: both run, in order, and pair up ---------
    called.clear()
    model = ScriptedModel([tool_call_events(("run_sql", {"sql": "SELECT 1"}),
                                            ("run_sql", {"sql": "SELECT 2"})),
                           text_events("done")])
    result = s.run(model, dispatch, "two queries")
    assert called == ["run_sql", "run_sql"], (
        "every tool call in a turn is dispatched, in order: %r" % (called,))
    assert roles(result["messages"]) == ["user", "assistant", "tool", "tool",
                                        "assistant"], (
        "both observations follow the turn that asked for them: %r"
        % (roles(result["messages"]),))
    assert [message["tool_call_id"] for message in result["messages"]
            if message["role"] == "tool"] == ["call_0_run_sql", "call_1_run_sql"], (
        "each observation answers its own call: %r" % (result["messages"],))

    # --- a bug in the tool layer is a bug, not a message to the model --------
    def broken(call):
        raise RuntimeError("the dispatcher has a bug")

    model = ScriptedModel([tool_call_events(("run_sql", {"sql": "SELECT 1"}))])
    try:
        s.run(model, broken, "anything")
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "an exception from the tool layer was swallowed: a harness that turns "
            "every crash into an observation teaches the model to read stack traces "
            "as if they were answers")

    # --- an error observation is traced as a failure -------------------------
    def refusing(call):
        return {"role": "tool", "tool_call_id": call["id"],
                "content": "no such table", "is_error": True}

    trace = FakeTrace()
    model = ScriptedModel([tool_call_events(("run_sql", {"sql": "SELECT * FROM nope"})),
                           text_events("the table does not exist")])
    result = s.run(model, refusing, "anything", trace=trace)
    assert result["status"] == "done", result
    assert [line["ok"] for line in trace.lines] == [True, False, True], (
        "a failing tool step is recorded with ok=False, or the trace says a run "
        "that hit an error was clean: %r" % (trace.lines,))

def check_4():
    REPO = os.environ.get("COURSE_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    COURSE = os.path.join(REPO, "agent-harness-from-scratch")

    def build():
        """A temp dir holding the course as the runner assembles it: `*.py` copied and
        `solutions/*.py` overlaid flat, then that dir (and the repo root) on sys.path."""
        work = tempfile.mkdtemp(prefix="e1-check04-")
        for name in sorted(os.listdir(COURSE)):
            source = os.path.join(COURSE, name)
            if os.path.isfile(source) and name.endswith(".py"):
                shutil.copy(source, os.path.join(work, name))
        solutions = os.path.join(COURSE, "solutions")
        for name in sorted(os.listdir(solutions)):
            if name.endswith(".py"):
                shutil.copy(os.path.join(solutions, name), os.path.join(work, name))
        for path in (REPO, work):
            if path in sys.path:
                sys.path.remove(path)
            sys.path.insert(0, path)
        return work

    def _fail(message):
        raise AssertionError(message)

    import tiny_env
    import stage_04 as stage

    for name in ("Dispatcher", "render_result"):
        if not hasattr(stage, name):
            _fail("stage_04 must define %s" % name)

    # -- a real tool body, over the provided warehouse -------------------------
    env = tiny_env.SQLEnv()
    ran = []                       # every fn that actually got entered, in order

    def run_sql(arguments):
        ran.append(dict(arguments))
        return env.exec(arguments.get("sql", ""))

    def list_tables(arguments):
        ran.append(dict(arguments))
        return {"columns": ["table"], "rows": [[name] for name in env.tables()]}

    tools = {
        "run_sql": {
            "description": "run one read-only SQL query",
            "input_schema": {
                "type": "object",
                "properties": {"sql": {"type": "string"},
                               "limit": {"type": "integer"}},
                "required": ["sql"],
            },
            "fn": run_sql,
        },
        "list_tables": {
            "description": "list the tables this warehouse exposes",
            "input_schema": {"type": "object", "properties": {}},
            "fn": list_tables,
        },
    }

    # A pathological imports check: the module must not need a clock or a network.
    if "time" in getattr(stage, "__dict__", {}):
        _fail("stage_04 must not import `time`: the clock is injected (ManualClock), and a stage "
              "that reads a wall clock is not deterministic")

    def _observe(call, where):
        """One `observe()` that must NOT raise. Any exception out of a call the
        model got wrong (or that the world refused) is the mistake this stage
        exists to prevent."""
        try:
            message = dispatcher.observe(call)
        except AssertionError:
            raise
        except Exception as exc:
            _fail("%s: observe() raised %s (%s) — it must RETURN a tool message instead: a call "
                  "the model can repair is a message it reads, never an exception that ends the "
                  "turn (and the model is the only party that can fix the call)"
                  % (where, type(exc).__name__, exc))
        if not isinstance(message, dict):
            _fail("%s: observe() must return a tool message, got %s"
                  % (where, type(message).__name__))
        for key in ("role", "tool_call_id", "content", "is_error"):
            if key not in message:
                _fail("%s: a tool message is {role, tool_call_id, content, is_error}, missing %r: %r"
                      % (where, key, message))
        if message["role"] != "tool":
            _fail("%s: a tool message has role 'tool', got %r" % (where, message["role"]))
        if not isinstance(message["content"], str):
            _fail("%s: a tool message's content is ALWAYS a string (it is what the model reads), "
                  "got %s" % (where, type(message["content"]).__name__))
        if not isinstance(message["is_error"], bool):
            _fail("%s: is_error is a bool, got %r" % (where, message["is_error"]))
        if message["tool_call_id"] != call.get("id"):
            _fail("%s: the observation must carry the call's id (%r), got %r — a result that "
                  "loses its id answers the wrong call"
                  % (where, call.get("id"), message["tool_call_id"]))
        return message

    # -- registration ----------------------------------------------------------
    dispatcher = stage.Dispatcher(tools)
    definitions = dispatcher.definitions()
    if [entry["name"] for entry in definitions] != ["run_sql", "list_tables"]:
        _fail("definitions() must offer the tools in REGISTRATION order ([run_sql, list_tables]): "
              "got %r" % ([entry["name"] for entry in definitions],))
    for entry, definition in zip(definitions, tools.values()):
        if set(entry) != {"name", "description", "inputSchema"}:
            _fail("an advertised definition is exactly {name, description, inputSchema}, got %r"
                  % (entry,))
        if entry["description"] != definition["description"]:
            _fail("the advertised description must be the registered one, got %r"
                  % (entry["description"],))
        if entry["inputSchema"] != definition["input_schema"]:
            _fail("the advertised inputSchema must be the registered one, got %r"
                  % (entry["inputSchema"],))
    definitions[0]["name"] = "hacked"
    definitions[0]["inputSchema"]["properties"].clear()
    if [entry["name"] for entry in dispatcher.definitions()] != ["run_sql", "list_tables"] \
            or dispatcher.definitions()[0]["inputSchema"].get("properties") != {"sql": {"type": "string"},
                                                                               "limit": {"type": "integer"}}:
        _fail("definitions() hands out the registry itself: keeping what it returned must not let "
              "a caller rewrite the tools the model is offered (or the schema they are validated "
              "against)")

    # -- a registration fault is named once, at construction -------------------
    for bad, why in ((None, "a table that is not a dict"),
                     ({"nosuch": {"description": "x", "input_schema": {}}}, "a tool with no fn")):
        try:
            stage.Dispatcher(bad)
        except ValueError:
            pass
        except AssertionError:
            raise
        except Exception as exc:
            _fail("Dispatcher must refuse %s with a ValueError naming it (a registration bug is "
                  "the harness author's), got %s: %s" % (why, type(exc).__name__, exc))
        else:
            _fail("Dispatcher must refuse %s: a registration bug is the harness author's, and it "
                  "is better named once at construction than at the third tool call" % why)

    # -- a valid call runs, renders, and is recorded ---------------------------
    query = "SELECT country, SUM(revenue) AS total FROM sales GROUP BY country ORDER BY country"
    message = _observe({"id": "c1", "name": "run_sql", "arguments": {"sql": query}},
                       "a valid call")
    if message["is_error"] is not False:
        _fail("a valid call is is_error=False, got %r: %r"
              % (message["is_error"], message["content"]))
    expected = "country | total\nCN | 360.0\nDE | 70.0\nES | 440.0\nFR | 80.0\n(4 rows)"
    if message["content"] != expected:
        _fail("the observation must be the rendered table — a header line, cells joined by ' | ', "
              "numbers as SQL gave them, a trailing '(N rows)' — not str(dict) and not JSON. "
              "expected %r, got %r" % (expected, message["content"]))
    if ran != [{"sql": query}]:
        _fail("the fn must run with exactly the arguments the model sent, got %r" % (ran,))
    if dispatcher.called != ["run_sql"]:
        _fail("a tool whose fn ran is recorded in .called, in order: got %r" % (dispatcher.called,))

    # -- every bad argument is an observation that NAMES the argument, and the
    #    fn is never entered for a call the schema does not admit --------------
    bad_calls = [
        ("a call missing the required argument 'sql'",
         {"id": "c2", "name": "run_sql", "arguments": {}}, "sql"),
        ("an argument of the wrong JSON type",
         {"id": "c3", "name": "run_sql", "arguments": {"sql": query, "limit": "five"}}, "limit"),
        ("an argument the schema does not declare",
         {"id": "c4", "name": "run_sql", "arguments": {"sql": query, "limmit": 5}}, "limmit"),
        ("arguments that are not an object",
         {"id": "c5", "name": "run_sql", "arguments": ["sql"]}, "arguments"),
    ]
    for where, call, argument in bad_calls:
        before = len(ran)
        message = _observe(call, where)
        if len(ran) != before:
            _fail("%s: the fn RAN — arguments are validated against input_schema BEFORE the fn is "
                  "entered, or a side effect happens for a call that was never valid: %r"
                  % (where, ran[before:]))
        if message["is_error"] is not True:
            _fail("%s: must come back as an observation with is_error=True, got is_error=%r (%r)"
                  % (where, message["is_error"], message["content"]))
        if argument not in message["content"]:
            _fail("%s: the observation must NAME the offending argument %r, got %r"
                  % (where, argument, message["content"]))

    # -- True is not an integer, however much Python says so -------------------
    before = len(ran)
    message = _observe({"id": "c6", "name": "run_sql", "arguments": {"sql": query, "limit": True}},
                       "a boolean where the schema declares an integer")
    if message["is_error"] is not True or "limit" not in message["content"]:
        _fail("a JSON boolean is not an integer: `True` must not satisfy a property declared "
              "integer (`True IS an int` in Python, so the body would compare 1 to a flag). "
              "got is_error=%r (%r)" % (message["is_error"], message["content"]))
    if len(ran) != before:
        _fail("the fn RAN for a boolean passed where the schema declares an integer: %r"
              % (ran[before:],))

    # -- an unknown tool is a message that names it and lists the alternatives,
    #    and the run continues ------------------------------------------------
    before = len(ran)
    message = _observe({"id": "c7", "name": "run_query", "arguments": {"sql": query}},
                       "an unknown tool")
    if message["is_error"] is not True:
        _fail("an unknown tool must be an observation with is_error=True, not an exception and "
              "not a silent success: a model told 'unknown tool' fixes its call, one that gets an "
              "exception loses the turn")
    if "run_query" not in message["content"]:
        _fail("the unknown-tool observation must NAME the tool the model asked for, got %r"
              % (message["content"],))
    for available in ("run_sql", "list_tables"):
        if available not in message["content"]:
            _fail("the unknown-tool observation must list what IS available (%r is missing), got %r"
                  % (available, message["content"]))
    if len(ran) != before:
        _fail("no fn may run for a name that is not registered: %r" % (ran[before:],))
    if dispatcher.unknown != ["run_query"]:
        _fail(".unknown must record every name that is not registered, in order: got %r"
              % (dispatcher.unknown,))
    if dispatcher.called != ["run_sql"]:
        _fail(".called records the tools whose fn RAN: a name nobody registered is not one of "
              "them, got %r" % (dispatcher.called,))

    message = _observe({"id": "c8", "name": "list_tables", "arguments": {}},
                       "the call after an unknown tool")
    if message["is_error"] is not False:
        _fail("the call after an unknown tool must simply run — the run does not die on a name the "
              "model invented: %r" % (message["content"],))
    expected = "table\ncustomers\nregions\nsales\n(3 rows)"
    if message["content"] != expected:
        _fail("the second tool's observation must be its rendered table %r, got %r"
              % (expected, message["content"]))
    if dispatcher.called != ["run_sql", "list_tables"]:
        _fail(".called is the tools that ran, in the order they ran: got %r" % (dispatcher.called,))

    # -- EnvError is an outcome: the observation carries the driver's words -----
    before = len(ran)
    message = _observe({"id": "c9", "name": "run_sql",
                        "arguments": {"sql": "SELECT revenu FROM sales"}},
                       "a query the warehouse refuses")
    if message["is_error"] is not True:
        _fail("an EnvError from the fn is an observation with is_error=True — the world said no, "
              "and the model reads it: %r" % (message,))
    if "revenu" not in message["content"]:
        _fail("the EnvError observation must carry the DRIVER's message (the warehouse says "
              "'no such column: revenu'), got %r" % (message["content"],))
    if len(ran) != before + 1:
        _fail("the fn must have RUN — the warehouse refused the query, the tool did not fail to "
              "be called: %r" % (ran[before:],))

    # -- any other exception is a bug, and a bug propagates --------------------
    class ToolBug(Exception):
        pass

    def explode(arguments):
        raise ToolBug("a bug in the tool's body")

    buggy = stage.Dispatcher({
        "explode": {"description": "raise a bug", "input_schema": {"type": "object", "properties": {}},
                    "fn": explode},
    })
    try:
        buggy.observe({"id": "b1", "name": "explode", "arguments": {}})
    except ToolBug:
        pass
    except Exception as exc:
        _fail("an exception that is not EnvError is a bug in OUR code and must propagate unchanged, "
              "got %s: %s" % (type(exc).__name__, exc))
    else:
        _fail("an exception that is not EnvError is a bug and must PROPAGATE: catching everything "
              "turns a bug into a message the model reads forever while the fault sits in the tool")

    # -- calls run in order, one at a time ------------------------------------
    mark = len(ran)
    _observe({"id": "c10", "name": "run_sql", "arguments": {"sql": "SELECT 1"}},
             "a second valid call")
    _observe({"id": "c11", "name": "run_sql", "arguments": {"sql": "SELECT 2"}},
             "a third valid call")
    if [entry["sql"] for entry in ran[mark:]] != ["SELECT 1", "SELECT 2"]:
        _fail("calls run in order and never concurrently: the fns must be entered SELECT 1 then "
              "SELECT 2, got %r" % ([entry["sql"] for entry in ran[mark:]],))

    # -- .called / .unknown are records, not handles --------------------------
    snapshot = dispatcher.called
    snapshot.append("hacked")
    if "hacked" in dispatcher.called:
        _fail(".called hands out the internal list: a caller mutating what it got must not rewrite "
              "the record")
    snapshot = dispatcher.unknown
    snapshot.append("hacked")
    if "hacked" in dispatcher.unknown:
        _fail(".unknown hands out the internal list: a caller mutating what it got must not rewrite "
              "the record")

    # -- render_result is a text table with a row count -----------------------
    text = stage.render_result({"columns": ["country", "total"],
                                "rows": [["CN", 360.0], ["ES", 440.0]]})
    expected = "country | total\nCN | 360.0\nES | 440.0\n(2 rows)"
    if text != expected:
        _fail("render_result must be a text table: a header line from the columns, one line per "
              "row with cells joined by ' | ', numbers as SQL gave them, and a trailing '(N rows)' "
              "line — never str(dict) and never JSON. expected %r, got %r" % (expected, text))
    empty = stage.render_result({"columns": ["x"], "rows": []})
    if empty != "x\n(0 rows)":
        _fail("an empty result still renders its header and a '(0 rows)' line: got %r" % (empty,))
    counted = stage.render_result({"columns": ["n"], "rows": [[1], [2], [3]]})
    if counted != "n\n1\n2\n3\n(3 rows)":
        _fail("the row-count line must be the number of rows printed: got %r" % (counted,))

def check_5():
    REPO = os.environ.get("COURSE_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    COURSE = os.path.join(REPO, "agent-harness-from-scratch")

    def build():
        """A temp dir holding the course as the runner assembles it: `*.py` copied and
        `solutions/*.py` overlaid flat, then that dir (and the repo root) on sys.path."""
        work = tempfile.mkdtemp(prefix="e1-check05-")
        for name in sorted(os.listdir(COURSE)):
            source = os.path.join(COURSE, name)
            if os.path.isfile(source) and name.endswith(".py"):
                shutil.copy(source, os.path.join(work, name))
        solutions = os.path.join(COURSE, "solutions")
        for name in sorted(os.listdir(solutions)):
            if name.endswith(".py"):
                shutil.copy(os.path.join(solutions, name), os.path.join(work, name))
        for path in (REPO, work):
            if path in sys.path:
                sys.path.remove(path)
            sys.path.insert(0, path)
        return work

    def _fail(message):
        raise AssertionError(message)

    def _types(events):
        return [event.get("type") if isinstance(event, dict) else event
                for event in events]

    import stage_01
    import stage_05 as stage
    from tiny_env import (HarnessError, ManualClock, ModelError, ScriptedModel,
                          broken_stream)

    for name in ("stream", "timings"):
        if not hasattr(stage, name):
            _fail("stage_05 must define %s" % name)

    MESSAGES = [{"role": "user", "content": "how did furniture sell?"}]
    TOOLS = [{"name": "sql", "description": "run a query",
              "inputSchema": {"type": "object", "properties": {}}}]

    def scripted(script, clock, arrivals, seen):
        """A turn callable: advance the clock, then yield each event. Before it
        produces event i+1 it notes how many events the sink had ALREADY seen —
        the proof that the harness streams instead of buffering."""
        def turn(messages, tools=None):
            for index, (delay, event) in enumerate(script):
                if index:
                    arrivals.append(len(seen))
                clock.advance(delay)
                yield event
        return turn

    # --- the events arrive one at a time, and the turn is measured in ms -------
    script = [
        (2.0, {"type": "tool_call", "id": "call_0_sql", "name": "sql",
               "arguments": {"q": "select 1"}}),
        (0.5, {"type": "text", "text": "Hel"}),
        (0.25, {"type": "text", "text": "lo"}),
        (0.125, {"type": "usage", "input_tokens": 10, "output_tokens": 5}),
        (0.0, {"type": "end", "reason": "stop"}),
    ]
    expected_events = [event for _, event in script]
    want_ats = [2.0, 2.5, 2.75, 2.875, 2.875]

    clock = ManualClock()
    seen = []           # (event, clock.now()) at each sink call, in order
    arrivals = []       # events the sink had seen when the model produced the next
    model = ScriptedModel([scripted(script, clock, arrivals, seen)])
    turn = stage.stream(model, MESSAGES, TOOLS,
                        sink=lambda event: seen.append((event, clock.now())),
                        clock=clock)

    if model.tools_seen != [TOOLS]:
        _fail("the tools the caller offered must reach the model unchanged: the model was "
              "offered %r" % (model.tools_seen,))
    if model.calls != [MESSAGES]:
        _fail("the messages the caller passed must reach the model unchanged: the model was "
              "handed %r" % (model.calls,))

    got_events = [event for event, _ in seen]
    if got_events != expected_events:
        _fail("sink(event) must be called exactly ONCE per event, in order, as it arrives: "
              "the sink got %r, expected %r" % (_types(got_events), _types(expected_events)))
    if arrivals != [1, 2, 3, 4]:
        _fail("the sink must be called AS THE EVENTS ARRIVE, not after the stream is read: "
              "when the model produced event i+1 the sink had seen %r event(s), expected "
              "[1, 2, 3, 4] — this is a harness that buffered the whole stream" % (arrivals,))
    got_ats = [at for _, at in seen]
    if got_ats != want_ats:
        _fail("the sink must be called while the events are arriving, not once at the end: "
              "the clock read %r at the sink calls, expected %r" % (got_ats, want_ats))

    reference = stage_01.collect(list(expected_events))
    if set(turn) != {"text", "tool_calls", "usage", "reason", "timings"}:
        _fail("the returned turn is stage 1's collect result plus exactly \"timings\": got "
              "the keys %r" % (sorted(turn),))
    got_turn = {key: value for key, value in turn.items() if key != "timings"}
    if got_turn != reference:
        _fail("the returned turn must be exactly what `collect` produces for the same events "
              "(every text delta appended, every usage summed, the tool calls in order, the "
              "`end`'s reason): got %r, `collect` says %r" % (got_turn, reference))

    got_timings = turn["timings"]
    if not isinstance(got_timings, dict) or set(got_timings) != {"ttft_ms", "itl_ms", "events"}:
        _fail("timings(turn) is exactly {'ttft_ms', 'itl_ms', 'events'}: got %r"
              % (got_timings,))
    if got_timings["ttft_ms"] != 2500.0:
        _fail("ttft_ms is the clock delta from the CALL to the first TEXT event, in ms: the "
              "tool_call lands at 2.0 s and the first text at 2.5 s, so 2500.0 — measuring "
              "from the first event of any type would say 2000.0. got %r"
              % (got_timings["ttft_ms"],))
    if got_timings["itl_ms"] != [250.0]:
        _fail("itl_ms is the gap between CONSECUTIVE TEXT events in MILLISECONDS: the two "
              "text events are 0.25 s apart, so [250.0] — seconds ([0.25]) or all-events gaps "
              "([500.0, 250.0, 125.0, 0.0]) are both wrong. got %r" % (got_timings["itl_ms"],))
    if got_timings["events"] != 5:
        _fail("timings()['events'] counts every event the stream delivered, `end` included: "
              "expected 5, got %r" % (got_timings["events"],))
    if stage.timings(turn) != got_timings:
        _fail("timings(turn) must answer the turn's own numbers for the turn `stream` "
              "returned: turn[\"timings\"] is %r, timings(turn) says %r"
              % (got_timings, stage.timings(turn)))

    # --- a turn with no text has no time to first token ------------------------
    script_b = [
        (1.0, {"type": "tool_call", "id": "call_0_sql", "name": "sql", "arguments": {}}),
        (0.5, {"type": "usage", "input_tokens": 4, "output_tokens": 1}),
        (0.0, {"type": "end", "reason": "tool_calls"}),
    ]
    clock_b = ManualClock()
    seen_b = []
    model_b = ScriptedModel([scripted(script_b, clock_b, [], seen_b)])
    turn_b = stage.stream(model_b, MESSAGES, sink=seen_b.append, clock=clock_b)
    if turn_b["timings"]["ttft_ms"] is not None:
        _fail("a turn with no text event has no time to first token: ttft_ms must be None, "
              "not a delta measured from a tool call or 0.0. got %r"
              % (turn_b["timings"]["ttft_ms"],))
    if turn_b["timings"]["itl_ms"] != []:
        _fail("one text event (or none) has no gap to the next: itl_ms must be [], got %r"
              % (turn_b["timings"]["itl_ms"],))
    if turn_b["timings"]["events"] != 3:
        _fail("timings()['events'] counts all three events here (tool_call, usage, end): "
              "got %r" % (turn_b["timings"]["events"],))

    # --- a stream that dies mid-way is not a finished turn ---------------------
    partial = [{"type": "text", "text": "Hel"},
               {"type": "text", "text": "lo"},
               {"type": "text", "text": "!!!"}]
    seen_c = []
    model_c = ScriptedModel([broken_stream(partial, 2)])
    try:
        result = stage.stream(model_c, MESSAGES, sink=seen_c.append, clock=ManualClock())
    except ModelError as exc:
        if not exc.retryable:
            _fail("the ModelError of a broken stream must propagate with its retryable flag "
                  "intact (stage 6 retries it): got retryable=%r" % (exc.retryable,))
    except Exception as exc:
        _fail("a stream that dies mid-way must propagate its own ModelError, not %s: %s — a "
              "harness that catches every exception turns a dropped connection into a "
              "message the model reads forever" % (type(exc).__name__, exc))
    else:
        _fail("the mid-stream error was SWALLOWED: the caller was told the turn finished with "
              "%r — a half stream reported as a finished turn is a half answer sent to a "
              "person, and a retry layer that is told there is nothing to retry" % (result,))
    if seen_c != partial[:2]:
        _fail("the sink must keep the events that DID arrive before the stream died: expected "
              "%r, got %r — a sink that saw nothing is a harness that buffered" % (partial[:2],
                                                                                   seen_c))

    # --- nothing goes to the sink after `end` ----------------------------------
    late = [{"type": "text", "text": "a"},
            {"type": "end", "reason": "stop"},
            {"type": "text", "text": "late"}]
    seen_d = []
    model_d = ScriptedModel([late])
    try:
        stage.stream(model_d, MESSAGES, sink=seen_d.append, clock=ManualClock())
    except HarnessError:
        pass
    except Exception as exc:
        _fail("an event after `end` must be refused with HarnessError, got %s: %s — the harness "
              "refuses what it cannot interpret instead of guessing" % (type(exc).__name__, exc))
    else:
        _fail("an event after `end` was silently DROPPED: the harness must refuse a stream that "
              "keeps talking after the end of a turn, not stop reading so it never notices")
    if seen_d != late[:2]:
        _fail("nothing may be sent to the sink AFTER the `end` event (the `end` event itself is "
              "sent): the sink got %r, expected %r" % (_types(seen_d), _types(late[:2])))

    # --- no sink is fine, and a single text event has no gap -------------------
    plain = [{"type": "text", "text": "hi"},
             {"type": "usage", "input_tokens": 3, "output_tokens": 2},
             {"type": "end", "reason": "stop"}]
    quiet = ScriptedModel([list(plain)])
    turn_e = stage.stream(quiet, MESSAGES, clock=ManualClock())
    if set(turn_e) != {"text", "tool_calls", "usage", "reason", "timings"}:
        _fail("stream without a sink must still return the turn: got the keys %r"
              % (sorted(turn_e),))
    if {k: v for k, v in turn_e.items() if k != "timings"} != stage_01.collect(list(plain)):
        _fail("stream(sink=None) must return the same turn `collect` would produce: got %r"
              % (turn_e,))
    if turn_e["timings"]["ttft_ms"] != 0.0:
        _fail("a clock that never moved (the call and the first text are both at 0.0) gives "
              "ttft_ms 0.0 — a delta, not None: got %r" % (turn_e["timings"]["ttft_ms"],))
    if turn_e["timings"]["itl_ms"] != []:
        _fail("a single text event has no next text event, so itl_ms is []: got %r"
              % (turn_e["timings"]["itl_ms"],))

    # --- the clock is injected: time.time() is never read ----------------------
    import time

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("the harness read the wall clock (time.time/time.monotonic): it "
                             "is handed a clock, or `clock=None` means the deltas are 0.0")

    wall_time, wall_monotonic = time.time, time.monotonic
    time.time, time.monotonic = _forbidden, _forbidden
    try:
        turn_f = stage.stream(ScriptedModel([list(plain)]), MESSAGES)
    finally:
        time.time, time.monotonic = wall_time, wall_monotonic
    if "timings" not in turn_f:
        _fail("stream without a clock must still return a turn carrying its timings: got %r"
              % (turn_f,))

def check_6():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    import time

    import stage_06 as s
    from tiny_env import (HarnessError, ManualClock, ModelError, ScriptedModel,
                          broken_stream, text_events)

    if not hasattr(s, "Retrying"):
        raise AssertionError("stage_06 must define Retrying")

    MESSAGES = [{"role": "user", "content": "how many sales in ES?"}]
    TOOLS = [{"name": "run_sql", "description": "run SQL",
              "inputSchema": {"type": "object"}}]

    def rate_limited():
        return ModelError("429 rate limit", retryable=True)

    def permanent():
        return ModelError("400 bad request", retryable=False)

    def drain(events):
        return list(events)

    def text_of(events):
        return "".join(event.get("text", "") for event in events
                       if event.get("type") == "text")

    def raises(exc_type, fn, where):
        try:
            value = fn()
        except exc_type as exc:
            return exc
        except AssertionError:
            raise
        except Exception as exc:
            raise AssertionError(
                "%s: expected %s, got %s: %s"
                % (where, exc_type.__name__, type(exc).__name__, exc))
        raise AssertionError(
            "%s: expected %s, but the call went through with %r"
            % (where, exc_type.__name__, value))

    # `time.sleep` is banned here on purpose: a harness that calls it cannot be
    # tested (the check could not tell a real wait from none), and this proves the
    # solution did not.
    real_sleep = time.sleep

    def _forbid_sleep(seconds):
        raise AssertionError(
            "the retry wait reached time.sleep(%r): the backoff must go through "
            "the injected clock (`clock.sleep`), or the wait cannot be asserted "
            "and the suite pays the wall clock" % (seconds,))

    time.sleep = _forbid_sleep
    try:
        # -- a permanent failure is NOT retried ------------------------------
        clock = ManualClock()
        model = ScriptedModel([text_events("never happens")], fail=[permanent()])
        retrying = s.Retrying(model, attempts=3, clock=clock)
        raises(ModelError, lambda: drain(retrying(MESSAGES)),
               "a non-retryable ModelError must propagate, not be retried")
        if retrying.calls != 1:
            raise AssertionError(
                "a permanent failure must be tried ONCE: retrying it spends money "
                "to get the same refusal again. got calls=%r" % (retrying.calls,))
        if retrying.retries != 0:
            raise AssertionError(
                "a permanent failure is not a retry: retries=%r" % (retrying.retries,))
        if clock.slept:
            raise AssertionError(
                "nothing was retried, so nothing was waited: slept=%r" % (clock.slept,))
        if model.turns_left != 1:
            raise AssertionError(
                "the model was asked a second time after a permanent failure: "
                "turns_left=%r" % (model.turns_left,))

        # -- a retryable failure is retried, the wait goes through the clock
        clock = ManualClock()
        model = ScriptedModel([text_events("hello")], fail=[rate_limited()])
        retrying = s.Retrying(model, attempts=3, backoff=0.5, clock=clock)
        events = drain(retrying(MESSAGES, tools=TOOLS))
        if text_of(events) != "hello":
            raise AssertionError(
                "a retryable failure must be retried until it succeeds: %r"
                % (events,))
        if retrying.calls != 2 or retrying.retries != 1:
            raise AssertionError(
                "one failed attempt + one success is calls=2, retries=1: got "
                "calls=%r retries=%r" % (retrying.calls, retrying.retries))
        if clock.slept != [0.5]:
            raise AssertionError(
                "the first retry must wait `backoff` through the injected clock "
                "(clock.sleep), got slept=%r" % (clock.slept,))
        if clock.now() != 0.5:
            raise AssertionError(
                "the wait must move the injected clock, not a real one: now=%r"
                % (clock.now(),))
        if len(model.calls) != 2 or model.calls[0] != MESSAGES or model.calls[1] != MESSAGES:
            raise AssertionError(
                "a retry must re-send the SAME messages: %r" % (model.calls,))
        if model.tools_seen[0] != TOOLS or model.tools_seen[1] != TOOLS:
            raise AssertionError(
                "a retry must re-send the SAME tools: %r" % (model.tools_seen,))

        # -- the delay DOUBLES per retry -------------------------------------
        clock = ManualClock()
        model = ScriptedModel([text_events("done")], fail=[rate_limited(),
                                                           rate_limited()])
        retrying = s.Retrying(model, attempts=3, backoff=0.5, clock=clock)
        events = drain(retrying(MESSAGES))
        if text_of(events) != "done":
            raise AssertionError("two failures then a success must return the turn")
        if retrying.calls != 3 or retrying.retries != 2:
            raise AssertionError(
                "two failures then a success is calls=3, retries=2: got calls=%r "
                "retries=%r" % (retrying.calls, retrying.retries))
        if clock.slept != [0.5, 1.0]:
            raise AssertionError(
                "the delay must DOUBLE per retry (0.5 then 1.0): a constant backoff "
                "hammers the provider at the rate that just refused it. got %r"
                % (clock.slept,))
        if clock.now() != 1.5:
            raise AssertionError(
                "the waits must accumulate on the injected clock: now=%r"
                % (clock.now(),))

        # -- attempts is PER CALL; .calls is the REAL count ------------------
        clock = ManualClock()
        # call 1: fail then A. call 2: fail then B.
        model = ScriptedModel([], fail=[rate_limited(), text_events("A"),
                                        rate_limited(), text_events("B")])
        retrying = s.Retrying(model, attempts=3, backoff=0.5, clock=clock)
        try:
            first = text_of(drain(retrying(MESSAGES)))
        except ModelError as exc:
            raise AssertionError(
                "each call must get its OWN attempt allowance: the first call "
                "(fail then success) had to retry to A, but got %s: %s"
                % (type(exc).__name__, exc))
        if first != "A":
            raise AssertionError("the first call retried to A, got %r" % (first,))
        try:
            second = text_of(drain(retrying(MESSAGES)))
        except ModelError as exc:
            raise AssertionError(
                "each call must get its OWN attempt allowance: after the first call "
                "spent two attempts, the second must still be able to spend its own, "
                "but it failed with %s: %s" % (type(exc).__name__, exc))
        if second != "B":
            raise AssertionError("the second call retried to B, got %r" % (second,))
        if retrying.calls != 4 or retrying.retries != 2:
            raise AssertionError(
                "two calls of two attempts each is calls=4, retries=2 (counted at the "
                "ATTEMPT level, not once per __call__): got calls=%r retries=%r"
                % (retrying.calls, retrying.retries))
        if len(model.calls) != 4:
            raise AssertionError(
                "the model must have been invoked four times, got %d"
                % (len(model.calls),))
        if retrying.usage != {"input_tokens": 20, "output_tokens": 10}:
            raise AssertionError(
                "usage must ACCUMULATE across calls and attempts (two successful "
                "turns of 10/5 each is 20/10): resetting it per attempt forgets the "
                "money earlier attempts spent. got %r" % (retrying.usage,))

        # -- usage from a FAILED attempt still bills -------------------------
        clock = ManualClock()
        # Two events (text + usage) forwarded, then the stream dies retryably.
        events = [{"type": "text", "text": "He"},
                  {"type": "usage", "input_tokens": 10, "output_tokens": 5},
                  {"type": "text", "text": "llo"},
                  {"type": "end", "reason": "stop"}]
        model = ScriptedModel([broken_stream(events, after=2),
                               text_events("SHOULD NOT RUN")])
        retrying = s.Retrying(model, attempts=3, backoff=0.5, clock=clock)
        got = []
        error = None
        try:
            for event in retrying(MESSAGES):
                got.append(event)
        except ModelError as exc:
            error = exc
        if error is None or not error.retryable:
            raise AssertionError(
                "a stream that died AFTER forwarding events must PROPAGATE the "
                "error: retrying it would hand the caller the prefix a second time. "
                "got events=%r error=%r" % (got, error))
        if got != events[:2]:
            raise AssertionError(
                "the caller must see exactly the events the dying stream forwarded "
                "before it failed, no more: got %r" % (got,))
        if retrying.calls != 1 or retrying.retries != 0:
            raise AssertionError(
                "once an event was forwarded the attempt is committed: calls=1, "
                "retries=0. got calls=%r retries=%r"
                % (retrying.calls, retrying.retries))
        if clock.slept:
            raise AssertionError(
                "a committed attempt is not retried, so it does not wait: slept=%r"
                % (clock.slept,))
        if model.turns_left != 1:
            raise AssertionError(
                "the second scripted turn must be untouched (no retry ran): "
                "turns_left=%r" % (model.turns_left,))
        if retrying.usage != {"input_tokens": 10, "output_tokens": 5}:
            raise AssertionError(
                "a failed attempt that reported usage must still be billed: the "
                "usage event was forwarded (and the provider will charge it). got %r"
                % (retrying.usage,))

        # -- budget is the WHOLE-RUN cap, not per call ------------------------
        clock = ManualClock()
        model = ScriptedModel([], fail=[rate_limited(), text_events("A"),
                                        rate_limited(), text_events("B")])
        retrying = s.Retrying(model, attempts=2, budget=2, backoff=0.5, clock=clock)
        if text_of(drain(retrying(MESSAGES))) != "A":
            raise AssertionError("the first call must retry to A within budget=2")
        if retrying.calls != 2:
            raise AssertionError(
                "the first call used both budgeted attempts, calls=%r" % (retrying.calls,))
        raises(HarnessError, lambda: drain(retrying(MESSAGES)),
               "the second call finds the whole-run budget spent and must refuse "
               "the call (HarnessError), not silently spend a fresh allowance")
        if retrying.calls != 2:
            raise AssertionError(
                "a refused call makes no attempt: calls=%r" % (retrying.calls,))

        # -- budget caps attempts WITHIN a call, too --------------------------
        clock = ManualClock()
        model = ScriptedModel([text_events("A")], fail=[rate_limited()])
        retrying = s.Retrying(model, attempts=3, budget=1, backoff=0.5, clock=clock)
        exc = raises(ModelError, lambda: drain(retrying(MESSAGES)),
                     "budget=1 allows a single attempt, so the retryable failure "
                     "must propagate (attempts ran out, not a fresh budget)")
        if not exc.retryable:
            raise AssertionError("a spent budget must propagate the retryable error")
        if retrying.calls != 1 or retrying.retries != 0 or clock.slept:
            raise AssertionError(
                "budget=1: one attempt, no retry, no wait. got calls=%r retries=%r "
                "slept=%r" % (retrying.calls, retrying.retries, clock.slept))

        # -- all attempts failing retryably is still a failure, not empty ----
        clock = ManualClock()
        model = ScriptedModel([], fail=[rate_limited(), rate_limited()])
        retrying = s.Retrying(model, attempts=3, backoff=0.5, clock=clock)
        exc = raises(ModelError, lambda: drain(retrying(MESSAGES)),
                     "every attempt failing retryably must propagate the last "
                     "ModelError, not yield an empty iterator")
        if retrying.calls != 3 or retrying.retries != 2:
            raise AssertionError(
                "attempts=3: three invocations, two of them retries. got calls=%r "
                "retries=%r" % (retrying.calls, retrying.retries))

        # -- arguments are validated, and the wrapper is an iterator ----------
        for bad in (0, -1, "3", True):
            raises(ValueError, lambda bad=bad: s.Retrying(lambda m, t=None: iter(()),
                                                          attempts=bad),
                   "attempts=%r must be rejected" % (bad,))
        raises(ValueError, lambda: s.Retrying(lambda m, t=None: iter(()), budget=-1),
               "a negative budget must be rejected")
        iterator = s.Retrying(ScriptedModel([text_events("x")]))(MESSAGES)
        if not hasattr(iterator, "__next__") or not hasattr(iterator, "__iter__"):
            raise AssertionError(
                "__call__ must return an iterator of events, got %r" % (iterator,))
    finally:
        time.sleep = real_sleep

def check_7():
    REPO = os.environ.get("COURSE_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    COURSE = os.path.join(REPO, "agent-harness-from-scratch")

    def build():
        """A temp dir holding the course as the runner assembles it: `*.py` copied and
        `solutions/*.py` overlaid flat, then that dir (and the repo root) on sys.path."""
        work = tempfile.mkdtemp(prefix="e1-check07-")
        for name in sorted(os.listdir(COURSE)):
            source = os.path.join(COURSE, name)
            if os.path.isfile(source) and name.endswith(".py"):
                shutil.copy(source, os.path.join(work, name))
        solutions = os.path.join(COURSE, "solutions")
        for name in sorted(os.listdir(solutions)):
            if name.endswith(".py"):
                shutil.copy(os.path.join(solutions, name), os.path.join(work, name))
        for path in (REPO, work):
            if path in sys.path:
                sys.path.remove(path)
            sys.path.insert(0, path)
        return work

    import stage_07 as stage
    from tiny_env import HarnessError

    def _fail(message):
        raise AssertionError(message)

    # The estimator stage_07 is expected to price the budget in: stage_02's if it
    # is on disk and implemented, the same fixed rule otherwise. The check and the
    # stage must agree on every "fits", or the boundary assertions are noise.
    def estimate(message):
        try:
            from stage_02 import estimate_tokens
        except Exception:
            estimator = None
        else:
            estimator = estimate_tokens
        if estimator is not None:
            try:
                return int(estimator(message))
            except NotImplementedError:
                pass
        content = message.get("content")
        chars = len(content) if isinstance(content, str) else 0
        calls = message.get("tool_calls")
        if calls:
            chars += len(json.dumps(calls, sort_keys=True, separators=(",", ":"),
                                    default=str))
        return -(-chars // 4) + 4

    def tokens(messages):
        return sum(estimate(message) for message in messages)

    def flat(turns):
        return [message for turn in turns for message in turn]

    def turn(index, *, calls=1, filler=180):
        """One turn: an assistant message asking for `calls` observations, then the
        observations. The newest turn has two of them, so a cut that is not
        turn-aware has somewhere to split a pair."""
        ids = ["call_%d_%d" % (index, k) for k in range(calls)]
        messages = [{"role": "assistant", "content": "step %d: querying" % index,
                     "tool_calls": [{"id": call_id, "name": "sql",
                                     "arguments": {"sql": "SELECT %d" % index}}
                                    for call_id in ids]}]
        for call_id in ids:
            messages.append({"role": "tool", "tool_call_id": call_id,
                             "content": "row " + call_id + " " + "x" * filler,
                             "is_error": False})
        return messages

    def audit(block, where):
        """No tool message without its call, no call without its observation."""
        asked = set()
        for message in block:
            if message.get("role") == "assistant":
                for call in message.get("tool_calls") or []:
                    asked.add(call["id"])
        for message in block:
            if message.get("role") == "tool" and message.get("tool_call_id") not in asked:
                _fail("%s: the result holds a tool message for %r and no assistant "
                      "message that asked for it — a real provider answers 400 to an "
                      "orphaned observation, which is what walking TURNS (not messages) "
                      "is for" % (where, message.get("tool_call_id")))
        answered = {message.get("tool_call_id") for message in block
                    if message.get("role") == "tool"}
        for message in block:
            for call in message.get("tool_calls") or []:
                if call["id"] not in answered:
                    _fail("%s: the result keeps the assistant call %r and its "
                          "observation is gone — a call and its observation are kept "
                          "or dropped TOGETHER" % (where, call["id"]))

    if not hasattr(stage, "SUMMARY_PREFIX") or not hasattr(stage, "compact"):
        _fail("stage_07 must define SUMMARY_PREFIX and compact()")
    if stage.SUMMARY_PREFIX != "Summary of the earlier conversation: ":
        _fail("SUMMARY_PREFIX must be the contract's string exactly, got %r"
              % (stage.SUMMARY_PREFIX,))

    system = {"role": "system", "content": "You are an analyst. " + "S" * 60}
    question = {"role": "user", "content": "Which category sold most? " + "Q" * 80}
    turns = [turn(0, calls=2), turn(1), turn(2), turn(3), turn(4, calls=2)]
    messages = [system, question] + flat(turns)
    tail = turns[4]
    middle = [question] + flat(turns[:4])
    hint = "the model searched five times; nothing conclusive"
    expected = [system,
                {"role": "user",
                 "content": stage.SUMMARY_PREFIX + "%s (%d messages)" % (hint, len(middle))}]
    expected += tail
    budget = tokens(expected) + 4
    if tokens(messages) <= budget:
        _fail("the fixture must not fit the budget it is compacted against")

    # -- a context that already fits is the SAME list, and summarize is not called
    fitting = [system, question]
    probe = []
    for label, limit in (("a generous budget", tokens(fitting) + 1000),
                         ("a budget the context fits EXACTLY", tokens(fitting))):
        probe[:] = []
        try:
            out = stage.compact(fitting, budget_tokens=limit,
                                summarize=lambda block: probe.append(block) or "summary")
        except Exception as exc:
            _fail("a context that already fits must be a NO-OP (idempotent: compacting "
                  "every round would shrink the context into nothing), but %s raised %s: "
                  "%s" % (label, type(exc).__name__, exc))
        if out is not fitting:
            _fail("a context that already fits must be returned as the SAME messages, "
                  "not compacted or copied (%s): %r" % (label, out))
        if probe:
            _fail("an already-fitting context must not call summarize at all (%s): "
                  "the budget is checked before there is a middle to summarize" % label)

    # -- compaction: one summary message, the system prompt, the newest turn
    seen = []

    def summarize(block):
        seen.append(block)
        return "%s (%d messages)" % (hint, len(block))

    try:
        result = stage.compact(messages, budget_tokens=budget, summarize=summarize)
    except HarnessError as exc:
        _fail("this context fits once the middle is replaced by ONE summary message, "
              "so compact must not raise here: %s. A context that is over budget "
              "AFTER the replacement means the middle was not replaced (kept "
              "alongside its own summary), or the tail kept more than the newest turn"
              % (exc,))

    if len(seen) != 1:
        _fail("summarize must be called AT MOST ONCE per compaction (never a summary "
              "of a summary), got %d call(s)" % len(seen))
    if any(message is system for message in seen[0]):
        _fail("summarize was handed the SYSTEM prompt — the system message is the "
              "instruction the harness runs under and never becomes history")
    if not isinstance(seen[0], list) or len(seen[0]) != len(middle) \
            or any(a is not b for a, b in zip(seen[0], middle)):
        _fail("summarize must be handed exactly the middle — the older turns and "
              "nothing else, never the system prompt and never the kept tail (the "
              "newest turn is what the model just did; summarizing it makes it "
              "forget). got %d message(s): %r" % (len(seen[0]), seen[0]))
    if any(message is tail[0] for message in seen[0]):
        _fail("summarize was handed the newest turn, which must stay verbatim")

    if not result or result[0] is not system:
        _fail("the system prompt must stay, unchanged and first: the compacted "
              "context starts with %r" % (result[0] if result else None))
    if len(result) < 2 or result[1].get("role") != "user" \
            or not isinstance(result[1].get("content"), str) \
            or not result[1]["content"].startswith(stage.SUMMARY_PREFIX):
        _fail("everything older than the newest turn must become exactly ONE user "
              "message whose content is SUMMARY_PREFIX + summarize(middle); got %r"
              % (result[1] if len(result) > 1 else result))
    if result[1]["content"] != expected[1]["content"]:
        _fail("the summary message must carry SUMMARY_PREFIX followed by what "
              "summarize returned, from the middle only: expected %r, got %r"
              % (expected[1]["content"], result[1]["content"]))

    audit(result, "after compaction")

    if not any(message is tail[0] for message in result):
        _fail("the newest turn must be kept VERBATIM in the compacted context: "
              "summarizing or dropping what the model just did is how a harness makes "
              "it forget; the assistant message %r is gone" % (tail[0],))
    if len(result) < len(tail) \
            or any(a is not b for a, b in zip(result[-len(tail):], tail)):
        _fail("the newest turn must be kept VERBATIM, same messages in the same order: "
              "kept %r, expected %r" % (result[-len(tail):], tail))
    if len(result) != 2 + len(tail):
        _fail("the compacted context must be exactly the system prompt, ONE summary "
              "message and the newest turn (%d message(s)); the summarized middle is "
              "replaced, not kept alongside its own summary — got %d message(s): %r"
              % (2 + len(tail), len(result), result))
    for message in middle:
        if any(kept_message is message for kept_message in result):
            _fail("a message of the summarized middle survived verbatim (%r): the "
                  "middle is REPLACED by the summary" % (message,))
    if tokens(result) > budget:
        _fail("the compacted context must fit the prompt budget: %d token(s) against "
              "%d" % (tokens(result), budget))

    # -- the reserve is room for the completion, and it comes off the prompt budget
    reserve = tokens(messages) - tokens(expected) + 1
    reserved = []
    out = stage.compact(messages, budget_tokens=tokens(messages) + 100,
                        reserve_tokens=reserve,
                        summarize=lambda block: reserved.append(block) or
                        "%s (%d messages)" % (hint, len(block)))
    if out is messages:
        _fail("the reserve is room for the completion: the PROMPT budget is "
              "budget_tokens - reserve_tokens, and a context over that must be "
              "compacted even though it is under budget_tokens — reserve_tokens was "
              "ignored")
    if out != expected or len(reserved) != 1:
        _fail("the reserve must change only how much room the prompt has, not what "
              "the compaction keeps: got %r" % (out,))
    if stage.compact(expected, budget_tokens=tokens(expected) + reserve,
                     reserve_tokens=reserve, summarize=lambda block: "x") is not expected:
        _fail("a context that fits the PROMPT budget exactly still fits: the reserve "
              "is subtracted once, not twice")

    # -- what cannot fit is a HarnessError naming what is too big
    try:
        over = stage.compact(messages, budget_tokens=budget,
                             summarize=lambda block: "Z" * 4000)
    except HarnessError as exc:
        if "budget" not in str(exc).lower():
            _fail("the HarnessError must name what is too big (the budget and the "
                  "parts that need it), got %r" % (str(exc),))
    except Exception as exc:
        _fail("an uncompressible context must raise HarnessError, not %s: %s"
              % (type(exc).__name__, exc))
    else:
        _fail("the system prompt, the summary and the newest turn do not fit the "
              "budget, and the newest turn is never summarized away: compact must "
              "raise HarnessError instead of returning a %d-token context against a "
              "%d-token prompt budget" % (tokens(over), budget))

    only = [system] + turn(9, calls=1)
    lonely = []
    try:
        out = stage.compact(only, budget_tokens=tokens([system]) + 1,
                            summarize=lambda block: lonely.append(block) or "summary")
    except HarnessError as exc:
        if "summar" not in str(exc).lower() and "newest" not in str(exc).lower():
            _fail("the HarnessError for a context with no older turn must say why "
                  "(there is nothing to summarize, and the newest turn is not "
                  "dropped), got %r" % (str(exc),))
    except Exception as exc:
        _fail("an over-budget context whose only turn is the newest one must raise "
              "HarnessError, not %s: %s" % (type(exc).__name__, exc))
    else:
        _fail("an over-budget context that is only the system prompt and the newest "
              "turn has no middle to summarize and may drop neither: compact must "
              "raise HarnessError, not return %r" % (out,))
    if lonely:
        _fail("summarize was called with an empty middle (and then thrown away): a "
              "summary of nothing is a message the model pays for and learns nothing "
              "from")

    # -- idempotent: a second compaction of a fitting context changes nothing
    before = len(seen)
    again = stage.compact(result, budget_tokens=budget, summarize=summarize)
    if again is not result:
        _fail("compacting an already-fitting context must be a NO-OP returning the "
              "SAME messages; it returned a different context, so running compaction "
              "every round shrinks the context into nothing: %r" % (again,))
    if len(seen) != before:
        _fail("the no-op must not call summarize at all: a summary of a summary grows "
              "every round (summarize calls %d -> %d)" % (before, len(seen)))
    if stage.compact(result, budget_tokens=tokens(result),
                     summarize=summarize) is not result:
        _fail("a context that fits the budget EXACTLY still fits: the comparison is "
              "<=, not <")

def check_8():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    KEYS = ("turn", "kind", "tokens", "duration_ms", "tool", "ok")

    SUMMARY_KEYS = {"turns", "calls", "tokens", "errors", "duration_ms"}

    import time

    import stage_08 as s
    from tiny_env import HarnessError, ManualClock

    def _fail(message):
        raise AssertionError(message)

    def _raises(fn, exc, where, must_mention=()):
        """Fail unless fn() raises `exc` — and keep the subprocess's exit code
        non-zero with a message that NAMES the mistake."""
        try:
            value = fn()
        except exc as caught:
            text = str(caught)
            for part in must_mention:
                if part not in text:
                    _fail("%s: the message must mention %r, got %r"
                          % (where, part, text))
            return caught
        except AssertionError:
            raise
        except Exception as caught:
            _fail("%s: expected %s, got %s: %s"
                  % (where, exc.__name__, type(caught).__name__, caught))
        _fail("%s: expected %s, but the call went through: %r"
              % (where, exc.__name__, value))

    # -- the surface ---------------------------------------------------------
    if not hasattr(s, "Trace"):
        _fail("stage_08 must define Trace")
    if tuple(s.Trace.KEYS) != KEYS:
        _fail("Trace.KEYS is the shape of a line and the whole design: expected "
              "%r, got %r — a line is the SHAPE of the run, not a copy of it, so "
              "there is no room for a prompt, an argument or a result"
              % (KEYS, tuple(s.Trace.KEYS)))

    # -- one real run, timed by a ManualClock --------------------------------
    # turn 1: a model step, two tool steps, the second one failed.
    # turn 2: the model step, a retry of it, the model step that worked, a
    # compaction, and the run ending.
    clock = ManualClock(now=100.0)
    trace = s.Trace()
    trace.step(kind="model", turn=1, tokens=120, clock=clock)
    clock.advance(0.25)
    trace.step(kind="tool", turn=1, tool="run_sql", tokens=40, clock=clock)
    clock.advance(0.125)
    trace.step(kind="tool", turn=1, tool="run_sql", tokens=0, ok=False,
               clock=clock)
    clock.advance(2.0)
    trace.step(kind="model", turn=2, tokens=80, clock=clock)
    clock.advance(1.0)
    trace.step(kind="retry", turn=2, tokens=5, clock=clock)
    clock.advance(0.5)
    trace.step(kind="model", turn=2, tokens=90, clock=clock)
    clock.advance(0.25)
    # a duration the caller measured itself: it is used as given, clock or not.
    # The compaction failed: an error of a kind that is neither a tool nor a
    # retry, which is what `errors` has to count.
    trace.step(kind="compact", turn=2, tokens=12, ok=False, duration_ms=7.5,
               clock=clock)
    trace.step(kind="end", turn=2)

    lines = trace.lines
    if len(lines) != 8:
        _fail("eight steps were recorded, so .lines holds eight lines; got %d"
              % (len(lines),))
    for index, line in enumerate(lines):
        if tuple(line) != KEYS:
            _fail("line %d is not exactly KEYS in order: a line is the six fields "
                  "of the shape and nothing else — a payload smuggled in here (a "
                  "prompt, a tool's arguments, a result, a clock reading) is a "
                  "second copy of somebody's data in the one place nobody guards, "
                  "got %r" % (index, line))

    durations = [line["duration_ms"] for line in lines]
    expected_durations = [0.0, 250.0, 125.0, 2000.0, 1000.0, 500.0, 7.5, None]
    if durations != expected_durations:
        _fail("a duration is the gap since the previous step, read from the "
              "INJECTED clock and in MILLISECONDS (ManualClock ticks in seconds); "
              "the first timed step has no predecessor to measure from and records "
              "0.0, and a duration the caller measured is used as given; expected "
              "%r, got %r" % (expected_durations, durations))
    if [line["tool"] for line in lines] != [None, "run_sql", "run_sql", None,
                                            None, None, None, None]:
        _fail("`tool` is the tool's NAME and None for a step that touched no "
              "tool, got %r" % ([line["tool"] for line in lines],))
    if [line["turn"] for line in lines] != [1, 1, 1, 2, 2, 2, 2, 2]:
        _fail("`turn` is the caller's numbering, recorded as given, got %r"
              % ([line["turn"] for line in lines],))

    # -- summary(): a fold over the lines, and the fold's traps --------------
    summary = trace.summary()
    if set(summary) != SUMMARY_KEYS:
        _fail("summary() is exactly %r, got %r"
              % (sorted(SUMMARY_KEYS), sorted(summary)))
    expected = {"turns": 3, "calls": 2, "tokens": 347, "errors": 2,
                "duration_ms": 3882.5}
    if summary["turns"] != expected["turns"]:
        _fail("`turns` counts MODEL steps, and a retry is not a turn — the model "
              "was asked twice, the turn is one; this run has 3 model steps and 1 "
              "retry, got turns=%r" % (summary["turns"],))
    if summary["calls"] != expected["calls"]:
        _fail("`calls` counts the TOOL steps of the run (2 of the 8 lines), got "
              "%r — counting every step tells an operator the model called 8 "
              "tools" % (summary["calls"],))
    if summary["tokens"] != expected["tokens"]:
        _fail("`tokens` is the SUM over every step (120+40+0+80+5+90+12 = 347); a "
              "total that is the last step's bill is the wrong bill, got %r"
              % (summary["tokens"],))
    if summary["errors"] != expected["errors"]:
        _fail("`errors` counts steps with ok=False of ANY kind — this run has a "
              "failed tool step AND a failed compaction (2), and there is exactly "
              "one retry, so errors is not retries: got %r" % (summary["errors"],))
    if summary["duration_ms"] != expected["duration_ms"]:
        _fail("`duration_ms` totals what was MEASURED (the untimed end step is "
              "skipped, the given 7.5 is included): expected %r, got %r"
              % (expected["duration_ms"], summary["duration_ms"]))
    folded = {
        "turns": len([line for line in lines if line["kind"] == "model"]),
        "calls": len([line for line in lines if line["kind"] == "tool"]),
        "tokens": sum(line["tokens"] for line in lines),
        "errors": len([line for line in lines if line["ok"] is False]),
        "duration_ms": sum(line["duration_ms"] for line in lines
                           if line["duration_ms"] is not None),
    }
    if summary != folded:
        _fail("summary() is a fold over .lines — one source of truth, or the "
              "audit needs an audit: folded %r, got %r" % (folded, summary))

    # -- replay(): the shape, and no payloads --------------------------------
    expected_replay = [(1, "model", None), (1, "tool", "run_sql"),
                       (1, "tool", "run_sql"), (2, "model", None),
                       (2, "retry", None), (2, "model", None),
                       (2, "compact", None), (2, "end", None)]
    if trace.replay() != expected_replay:
        _fail("replay() is [(turn, kind, tool), ...] in step order — the shape of "
              "the run is what makes it replayable; expected %r, got %r"
              % (expected_replay, trace.replay()))

    # -- .lines hands out a copy: neither the list nor a line is the trace's --
    handed = trace.lines
    handed[0]["tokens"] = 999999
    handed.append({"turn": 9, "kind": "model", "tokens": 0, "duration_ms": None,
                   "tool": None, "ok": True})
    del handed[3:]
    after = trace.lines
    if len(after) != 8:
        _fail(".lines hands out a COPY of the list: a caller that appends to or "
              "truncates what it was given must not be able to rewrite the trace "
              "(8 lines were recorded, now %d read back)" % (len(after),))
    if after[0]["tokens"] != 120:
        _fail(".lines hands out a copy of every LINE too — a fresh list of the "
              "trace's own dicts is not a copy: a caller edited one line and the "
              "recorded step changed to %r" % (after[0]["tokens"],))
    if trace.summary() != folded:
        _fail("a caller that edited what .lines returned changed the trace's "
              "summary: the artifact must be immutable from the outside")

    # -- step() hands out a copy of the line it recorded ---------------------
    probe = s.Trace()
    line = probe.step(kind="end", turn=1)
    line["ok"] = False
    line["tokens"] = 1000000
    if probe.summary()["errors"] != 0 or probe.lines[0]["tokens"] != 0:
        _fail("step() must return a copy of the line it recorded: a caller that "
              "edits what it was handed rewrote the audit, lines=%r"
              % (probe.lines,))

    # -- the turn number is the caller's; the trace does not invent one ------
    unnamed = s.Trace()
    guessed = unnamed.step(kind="model").get("turn")
    if guessed is not None:
        _fail("`turn` is the CALLER's numbering: a trace that invents one (a step "
              "with no turn became turn %r) disagrees with the run it recorded, "
              "and the replay of an audit must be the audit" % (guessed,))

    # -- the clock is the injected one, never time.time() --------------------
    real_time = time.time

    def _boom(*args, **kwargs):
        raise AssertionError("time.time() was called")

    time.time = _boom
    try:
        try:
            clock = ManualClock(now=0.0)
            wall = s.Trace(clock=clock)
            wall.step(kind="model", turn=1, tokens=1)
            clock.advance(0.5)
            wall.step(kind="tool", turn=1, tool="run_sql", tokens=1)
            measured = [line["duration_ms"] for line in wall.lines]
        finally:
            time.time = real_time
    except AssertionError as caught:
        _fail("a trace reads the clock it was handed and NEVER time.time(): the "
              "contract forbids a wall clock, and a duration from one cannot be "
              "asserted, reproduced or merged (%s)" % (caught,))
    if measured != [0.0, 500.0]:
        _fail("a Trace(clock=...) times every step against that clock, in "
              "milliseconds: 0.5 s is 500.0 ms (a value in seconds is the ms/s "
              "mix-up), expected [0.0, 500.0], got %r" % (measured,))

    # -- no clock, no duration: None, and the total skips it -----------------
    untimed = s.Trace()
    untimed.step(kind="model", turn=1, tokens=3)
    untimed.step(kind="end", turn=1)
    if [line["duration_ms"] for line in untimed.lines] != [None, None]:
        _fail("a step with no clock and no given duration is recorded as None — "
              "'nobody measured this' is a fact, and 0.0 would be the trace "
              "inventing an instant step: got %r"
              % ([line["duration_ms"] for line in untimed.lines],))
    if untimed.summary()["duration_ms"] != 0:
        _fail("summary()['duration_ms'] totals the durations that were measured "
              "and skips the untimed lines: got %r"
              % (untimed.summary()["duration_ms"],))

    # -- there is no payload channel, and the secret never reaches a line ----
    secret = "sk-live-9f3c2b1a42dd"
    call = {"name": "http_get", "arguments": {"api_key": secret}}
    smuggle = s.Trace()
    smuggle.step(kind="model", turn=1, tokens=10)
    smuggle.step(kind="tool", turn=1, tool="http_get", tokens=3, ok=False)
    for where, attempt in [
        ("a tool step whose `tool` is the whole call, arguments and all",
         lambda: smuggle.step(kind="tool", turn=1, tool=call, ok=True)),
        ("a step handed the arguments 'just for the log'",
         lambda: smuggle.step(kind="tool", turn=1, tool="http_get", ok=True,
                              arguments={"api_key": secret})),
    ]:
        try:
            attempt()
        except AssertionError:
            raise
        except (HarnessError, TypeError):
            continue                       # refused at the door: fine
        except Exception as caught:
            _fail("%s: a payload-shaped argument must be refused cleanly (a "
                  "HarnessError naming it) or raise TypeError from the signature, "
                  "got %s: %s" % (where, type(caught).__name__, caught))
    blob = repr(smuggle.lines) + repr(smuggle.summary()) + repr(smuggle.replay())
    if secret in blob:
        _fail("the trace is the SHAPE of the run, never a copy of it — an audit "
              "that keeps a prompt, a tool's arguments or a result is a second "
              "copy of somebody's data in the one place nobody guards, and the "
              "secret-shaped argument reached it")
    if any(tuple(line) != KEYS for line in smuggle.lines):
        _fail("a line stayed exactly KEYS wide after a caller tried to hand the "
              "trace a payload: %r" % (smuggle.lines,))

    # -- a step nobody can count is refused, not recorded --------------------
    strict = s.Trace()
    _raises(lambda: strict.step(kind="modle", turn=1), HarnessError,
            "a step kind outside the vocabulary", must_mention=("modle",))
    _raises(lambda: strict.step(kind="model", turn=1, tokens="10"), HarnessError,
            "a token count that is a string")
    _raises(lambda: strict.step(kind="model", turn=1, tokens=True), HarnessError,
            "a boolean token count")
    _raises(lambda: strict.step(kind="model", turn=1, tokens=-1), HarnessError,
            "a negative token count")
    _raises(lambda: strict.step(kind="tool", tool="run_sql", ok="yes"),
            HarnessError, "an ok that is a string")
    _raises(lambda: strict.step(kind="model", turn="1"), HarnessError,
            "a turn that is not an index")
    _raises(lambda: strict.step(kind="model", turn=1, duration_ms="fast"),
            HarnessError, "a duration that is a string")
    if strict.lines != []:
        _fail("a step the trace refused is not a step, and nothing was recorded: "
              "got %r" % (strict.lines,))

    # -- same script, same bytes --------------------------------------------
    def run_script():
        clock = ManualClock(now=7.0)
        one = s.Trace(clock=clock)
        one.step(kind="model", turn=1, tokens=11)
        clock.advance(0.75)
        one.step(kind="tool", turn=1, tool="run_sql", tokens=2, ok=False)
        clock.advance(0.125)
        one.step(kind="end", turn=1)
        return one.lines, one.summary(), one.replay()

    if run_script() != run_script():
        _fail("the same script must render the same bytes: this artifact is read "
              "by a diff, a dashboard and a human, and two runs that disagree are "
              "a coin flip")

def check_9():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    import stage_09 as s
    from tiny_env import ANALYTIC_TASKS, EnvError, HarnessError, SQLEnv

    env = SQLEnv()

    def result_of(sql):
        return env.exec(sql)

    totals = result_of("SELECT category, SUM(revenue) AS total FROM sales "
                       "GROUP BY category ORDER BY total DESC")

    # --- cite_values walks the result --------------------------------------
    values = s.cite_values(totals)
    assert "furniture" in values, (
        "the cells of a result are what a reasoning can cite, and the first one is "
        "a string: %r" % (values,))
    assert "490.0" in values and "490" in values, (
        "490.0 comes back from SUM and every person writes it as 490: the integer "
        "spelling of an exact float is one of the forms a value has, got %r"
        % (values,))
    assert values.count("490.0") == 1, (
        "the same value spelled once: %r" % (values,))
    assert s.cite_values({"columns": ["total"], "rows": [[None]]}) == [], (
        "a NULL is the absence of a value and cites nothing: %r"
        % (s.cite_values({"columns": ["total"], "rows": [[None]]}),))
    assert s.cite_values([["a", ["b", 2]]]) == ["a", "b", "2"], (
        "cells nest, so the walk is recursive: %r" % (s.cite_values([["a", ["b", 2]]]),))
    assert s.cite_values(None) == [] and s.cite_values([]) == [], (
        "no result is no values, not an exception")

    # --- citing: what came back, how it was written, on boundaries ---------
    assert s.cites_previous_result("revenue was 600.0 for furniture",
                                   [["furniture", 600.0]]) is True, (
        "the reasoning names a value the previous step returned")
    assert s.cites_previous_result("furniture leads", None) is False, (
        "with no previous result there is nothing to cite, and a step that claims "
        "an unsupported conclusion must not be credited")
    assert s.cites_previous_result("furniture leads", []) is False
    assert s.cites_previous_result("furniture leads",
                                   {"columns": [], "rows": []}) is False
    assert s.cites_previous_result("the total was 160", [[160.0]]) is True, (
        "160.0 comes back as a float and the model writes 160: both spellings cite "
        "the same number")
    assert s.cites_previous_result("the total was 160.0", [[160.0]]) is True
    assert s.cites_previous_result("THE FURNITURE TOTAL", [["furniture"]]) is True, (
        "reasoning is prose and prose is not case-sensitive")
    assert s.cites_previous_result("the   value\nwas\t160", [[160.0]]) is True, (
        "a newline inside a number is not a different number: whitespace is "
        "collapsed before matching")
    assert s.cites_previous_result("we met Ana   Ferrer from the ES region",
                                   [["Ana Ferrer"]]) is True, (
        "a value with a space in it is cited when the reasoning's spacing differs: "
        "a model writing 'Ana   Ferrer' named the same person, and collapsing "
        "whitespace on both sides is what makes that visible")
    assert s.cites_previous_result("we scanned 1600 rows", [[160.0]]) is False, (
        "160 is inside 1600: a bare substring test credits a step with a number "
        "that never appeared")
    assert s.cites_previous_result("there were 13 sales", [[3]]) is False, (
        "3 is inside 13: numeric values match on boundaries, not anywhere")
    assert s.cites_previous_result("furniture-and-appliances did well",
                                   [["furniture"]]) is True, (
        "a category name inside a longer word is still the same category")

    # --- the reward --------------------------------------------------------
    assert s.process_reward([]) == 0.0, (
        "an empty episode is 0.0: a reward function is called on whatever the "
        "rollout produced, including nothing")
    grounded = [
        {"sql": "SELECT category, SUM(revenue) AS total FROM sales GROUP BY category",
         "ok": True, "result": totals,
         "reasoning": "furniture leads with 490"},
        {"sql": "SELECT MAX(revenue) FROM sales WHERE category = 'furniture'",
         "ok": True,
         "result": result_of("SELECT MAX(revenue) FROM sales WHERE category = 'furniture'"),
         "reasoning": "the largest single furniture sale is 180, which fits"},
    ]
    score = s.process_reward(grounded)
    assert 0.0 <= score <= 1.0, "the reward is a mean of three booleans: %r" % (score,)
    assert score == 1.0, (
        "an episode where every step ran, cited its predecessor and asked something "
        "new is perfect: %r" % (score,))

    hallucinated = [
        grounded[0],
        {"sql": "SELECT MAX(revenue) FROM sales WHERE category = 'books'",
         "ok": True, "result": result_of("SELECT MAX(revenue) FROM sales WHERE category = 'books'"),
         "reasoning": "the drop is driven by returns and seasonality"},  # cites nothing that came back
    ]
    assert s.process_reward(hallucinated) < score, (
        "a step whose reasoning cites nothing the previous step returned must score "
        "below the grounded one: %r vs %r"
        % (s.process_reward(hallucinated), score))

    # the repeat is TWO steps back, and the reasoning stays grounded: the only
    # thing that changed is that the query already ran
    repeat_of_one = [grounded[0], grounded[1],
                     dict(grounded[1], sql=grounded[0]["sql"],
                          reasoning=grounded[1]["reasoning"])]
    assert s.process_reward(repeat_of_one) < 1.0, (
        "running a query that already ran two steps ago is not a new step, and a "
        "novelty check that only looks at the step before it pays for it every "
        "time: %r" % (s.process_reward(repeat_of_one),))

    failed = [dict(grounded[0], ok=False)]
    assert s.process_reward(failed) < 1.0, (
        "a step whose query did not run loses the point it was worth: %r"
        % (s.process_reward(failed),))
    # (1.0 + 2/3) / 2: the failed step still counts in the denominator, or the
    # reward silently renormalises itself around the steps that worked
    mixed = s.process_reward([grounded[0], dict(grounded[1], ok=False)])
    assert abs(mixed - (1.0 + 2.0 / 3.0) / 2.0) < 1e-9, (
        "the mean is over every step in the episode, including the ones that "
        "failed: dividing by the steps that ran turns a bad episode into a good "
        "one, got %r" % (mixed,))

    # grounding is about the PREVIOUS step, not any step that ever ran
    step_one = {"sql": "SELECT category, SUM(revenue) AS total FROM sales "
                       "GROUP BY category ORDER BY total DESC LIMIT 1", "ok": True,
                "result": [["furniture", 490.0]],
                "reasoning": "start with the biggest category"}
    step_two = {"sql": "SELECT COUNT(*) FROM sales", "ok": True,
                "result": [[10]], "reasoning": "ten sales in total, so 490 is 49 a sale"}
    step_three = {"sql": "SELECT COUNT(*) FROM customers", "ok": True,
                  "result": [[3]],
                  "reasoning": "furniture is where the money is"}   # cites step ONE
    last_only = s.process_reward([step_one, step_two, step_three])
    assert last_only < 1.0, (
        "the third step cites a value from the FIRST step, not from the one it "
        "followed: grounding is a claim about causality, and a step that reaches "
        "back three steps for its evidence is rationalising after the fact: %r"
        % (last_only,))
    assert s.process_reward([step_one, step_two,
                             dict(step_three, reasoning="the 10 sales are spread "
                                                        "over three customers")]) > last_only, (
        "and citing step TWO's numbers must score above citing step one's, or the "
        "reward cannot tell the two apart")

    # the first step is credited as grounded (it has no predecessor)
    first = [{"sql": "SELECT 1", "ok": True, "result": [[1]],
              "reasoning": "I will start with the total"}]
    assert s.process_reward(first) == 1.0, (
        "charging the first step for not citing a predecessor would make every "
        "honest episode start at 2/3: %r" % (s.process_reward(first),))

    # --- ok is a bool, not a truthy string ---------------------------------
    for value in ("false", "no", 1, None):
        try:
            s.process_reward([{"sql": "SELECT 1", "ok": value, "result": [[1]],
                               "reasoning": "x"}])
        except HarnessError:
            continue
        raise AssertionError(
            "'ok': %r was accepted: a non-empty string is truthy, so a reward "
            "built on `if step['ok']` pays a step whose query failed" % (value,))

def check_10():
    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _ghost_template():
        return {"name": "ghost_country",
                "question": "What was the best sale in {country}?",
                "sql": "SELECT MAX(revenue) FROM sales WHERE country = '{country}'",
                "table": "sales", "values": {"country": ["Z1", "Z2", "Z3", "Z4"]},
                "kind": "number"}

    def _two_cell_template():
        return {"name": "two_cells", "question": "How did we do?",
                "sql": "SELECT MAX(revenue), COUNT(*) FROM sales",
                "table": "sales", "kind": "number"}

    def _repeating_template():
        return {"name": "same_country",
                "question": "How many sales in {country}?",
                "sql": "SELECT COUNT(*) FROM sales WHERE country = '{country}'",
                "table": "sales", "values": {"country": ["ES", "ES", "ES"]},
                "kind": "number"}

    import stage_10 as s
    from tiny_env import (ANALYTIC_TASKS, HarnessError, SQLEnv, TEMPLATES, Task,
                          numeric_columns)

    env = SQLEnv()
    assert s.NUMERIC_TOLERANCE > 0 and s.ATTEMPT_LIMIT > 0, (
        "the tolerance and the attempt limit are the caller's knobs, not magic "
        "numbers buried in a loop")

    # --- the verifier: what counts as the same answer -----------------------
    text = s.make_verifier("furniture")
    assert text("furniture") == 1.0, (
        "the answer the task asked for is the answer the task asked for")
    assert text(" Furniture ") == 1.0 and text("FURNITURE") == 1.0, (
        "a model writing ' Furniture ' or 'FURNITURE' answered the question: "
        "strip and fold case before comparing, or half of them score zero")
    assert text("electronics") == 0.0, ("a different category is a wrong answer")
    assert text("the furniture category") == 0.0, (
        "the answer is compared, not searched: a sentence that CONTAINS the "
        "category is not the category, and a substring match pays for rambling")
    assert text([("furniture",)]) == 1.0 and text([["furniture"]]) == 1.0, (
        "a result arrives wrapped — [('furniture',)] is a one-cell row and "
        "[['furniture']] is the same thing from another driver: comparing the "
        "wrapper to the gold marks every correct answer wrong")
    assert text({"columns": ["category"], "rows": [["furniture"]]}) == 1.0, (
        "and one layer up: a result dict's rows are unwrapped the same way")
    assert text(None) == 0.0 and text([]) == 0.0 and text(3) == 0.0, (
        "no answer, an empty answer and the wrong type are all wrong answers")

    number = s.make_verifier(160.0)
    assert number(160) == 1.0 and number(160.0) == 1.0 and number("160") == 1.0, (
        "160, 160.0 and '160' are the same answer to a question about a sum")
    assert number("  160.0 ") == 1.0 and number([(160.0,)]) == 1.0, (
        "and whitespace and wrappers do not change an answer")
    assert number(160.0000001) == 1.0, (
        "SUM(revenue) is a float and a model types a handful of digits: an exact "
        "== marks a right answer wrong at the first rounding")
    assert number(160.1) == 0.0 and number("170") == 0.0, (
        "the tolerance is a tolerance, not a licence: 160.1 is not 160")
    assert number("170 apples") == 0.0 and number("not a number") == 0.0, (
        "text where a number belongs is a wrong answer, not an exception")
    assert number(None) == 0.0 and number(True) == 0.0, (
        "no answer is wrong, and True is not 1: a bool scoring against a count "
        "is a verifier that pays a yes/no answer for a number")
    assert s.make_verifier(1.0)(True) == 0.0, (
        "especially when the count IS 1: True == 1 in Python and it is still not "
        "an answer to how many sales there were")
    assert s.make_verifier(0)("0") == 1.0 and s.make_verifier(0)(0.0) == 1.0, (
        "zero is a number: a verifier that picks its branch by truthiness sends "
        "a answer of '0' down the string path and fails a correct answer")
    zero_gold = s.make_verifier(None)
    assert zero_gold(None) == 0.0 and zero_gold("anything") == 0.0, (
        "a task with no gold answer is a task nobody can answer: 0.0 for every "
        "answer, including the None that happens to match it")

    # --- the verifier never raises -----------------------------------------
    class Hostile:
        def __eq__(self, other):
            raise RuntimeError("hostile __eq__")

        def __repr__(self):
            return "<hostile>"

    hostile = Hostile()
    recursive = []
    recursive.append(recursive)
    nasty = [object(), hostile, recursive, {"rows": recursive}, {}, [[]],
             [[None]], float("nan"), float("inf"), b"furniture", 3.5, "x" * 80]
    for verifier in (text, number, zero_gold):
        for answer in nasty:
            score = verifier(answer)
            assert score in (0.0, 1.0), (
                "a verifier returns a score, got %r for %r" % (score, answer))
    assert text(hostile) == 0.0, (
        "a verifier is called on whatever a solver produced, including an object "
        "whose __eq__ raises: 0.0, never an exception — a crash here loses the "
        "episode")

    # --- the generator: deterministic, answerable, honest -------------------
    first = s.generate_tasks(env, 6)
    assert len(first) == 6, (
        "asked for 6 tasks and got %d: the generator returns what was asked for "
        "or it raises" % (len(first),))
    again = s.generate_tasks(env, 6)
    assert [(t.aid, t.question, t.reference_sql, t.gold, t.kind) for t in first] == \
        [(t.aid, t.question, t.reference_sql, t.gold, t.kind) for t in again], (
            "the same env and templates give the same tasks in the same order, or "
            "a round cannot be reproduced")
    assert len({t.aid for t in first}) == 6, (
        "every task has its own id: %r" % ([t.aid for t in first],))
    assert len({t.reference_sql for t in first}) == 6, (
        "the same question twice is one question, and a training round that pays "
        "for the same answer twice learns it twice: %r"
        % ([t.reference_sql for t in first],))
    for task in first:
        assert task.gold is not None, ("no task's answer is a NULL: %r" % (task,))
        assert isinstance(task, Task), ("the generator makes Task objects: %r" % (task,))
        assert task.kind in ("text", "number"), (
            "a task's kind says how it is verified: %r" % (task.kind,))
        got = env.exec(task.reference_sql)["rows"][0][0]
        assert got == task.gold, (
            "the gold comes from the executor, never from the template's idea of "
            "the answer: %r says %r, the world says %r"
            % (task.reference_sql, task.gold, got))

    # `max_in_country` lists a country nobody sold to: that candidate answers NULL
    max_hole = [t for t in TEMPLATES if t["name"] == "max_in_country"]
    assert len(max_hole) == 1 and "ZZ" in max_hole[0]["values"]["country"], (
        "tiny_env's largest-sale template lists a country nobody sold to: %r"
        % (max_hole,))
    maxed = s.generate_tasks(env, 1, templates=tuple(max_hole))
    assert maxed[0].gold == 180.0, (
        "the largest single sale in ES is 180.0 (440.0 is the country's TOTAL, "
        "which is a different question): the gold comes from the executor that ran "
        "the SQL, not from the template's idea of the answer: %r" % (maxed[0],))
    assert "'ES'" in maxed[0].reference_sql, (
        "the filling that was kept is the one that has an answer: %r"
        % (maxed[0].reference_sql,))
    try:
        s.generate_tasks(env, 2, templates=tuple(max_hole))
    except HarnessError:
        pass
    else:
        raise AssertionError(
            "of that template's two listed countries, one has no sales: a "
            "candidate whose answer is NULL is dropped, so there is one task to "
            "be had and asking for two must say so instead of handing out a NULL")

    # the trap: `AVG({column}) FROM {table}` on a table with no numeric column
    avg = [t for t in TEMPLATES if t.get("needs_number") and t.get("table") == "{table}"]
    assert len(avg) == 1, (
        "tiny_env ships one template that walks the tables with a numeric column, "
        "got %d" % (len(avg),))

    class SloppyEnv:
        """An env that would answer AVG(region) FROM regions with a number. The
        generator must never ask: the schema says that table has no number, so
        the question is not a question."""

        def tables(self):
            return ["regions"]

        def schema(self):
            return {"tables": {"regions": {"columns": {"region": "TEXT",
                                                       "manager": "TEXT"},
                                           "numeric": []}}}

        def exec(self, sql):
            return {"columns": ["avg"], "rows": [[1.0]]}

    sloppy = SloppyEnv()
    assert numeric_columns(sloppy, "regions") == [], (
        "the fixture env advertises a table with no numeric column")
    try:
        bogus = s.generate_tasks(sloppy, 1, templates=tuple(avg))
    except HarnessError:
        bogus = None
    assert bogus is None, (
        "a template that needs a number cannot be filled on a table that has "
        "none: averaging a region's NAME is not a question, and a generator that "
        "asks it hands out garbage: %r" % (bogus,))

    # a template whose every filling answers NULL: dropped, and then the count
    try:
        s.generate_tasks(env, 1, templates=(_ghost_template(),), limit=3)
    except HarnessError as error:
        message = str(error)
        assert "after 3 candidate" in message, (
            "the attempt bound is the caller's limit, not however many candidates "
            "the templates can be filled with: this template has 4 fillings and "
            "limit=3, so the log says 3, and a loop that does not count its "
            "attempts says 4 (or never stops): message was %r" % (message,))
    else:
        raise AssertionError(
            "a template whose every answer is NULL cannot make a task: a gold of "
            "None is a task every solver fails, and the generator must say so "
            "instead of returning a shorter list")

    # a question with two answers is not a question with one answer
    try:
        s.generate_tasks(env, 1, templates=(_two_cell_template(),))
    except HarnessError:
        pass
    else:
        raise AssertionError(
            "a row of two cells is a table, not an answer: a one-cell result is "
            "what a task can be verified against")

    # the same template filled with the same value is not a second question
    try:
        s.generate_tasks(env, 2, templates=(_repeating_template(),))
    except HarnessError:
        pass
    else:
        raise AssertionError(
            "a template listing the same value three times makes ONE question, "
            "and asking for two is asking for something these templates cannot "
            "give: a generator that hands out the same question twice pays for "
            "the same answer twice")

    # --- the round: where the number comes from -----------------------------
    calls = []

    def perfect(task):
        calls.append(task)
        return task.gold

    result = s.self_improve_round(env, perfect, 4)
    assert result["generated"] == 4 and len(result["kept"]) == 4, (
        "a solver that answers every task correctly keeps every task: %r"
        % (result,))
    assert result["failed"] == [], (
        "and fails none: %r" % (result["failed"],))
    assert result["accuracy"] == 1.0, (
        "accuracy 1.0, got %r" % (result["accuracy"],))
    assert len(calls) == 4, (
        "a task is solved once: 4 tasks, %d agent calls (accuracy on the generated "
        "set comes from the split that was just made, not from a second sweep)"
        % (len(calls),))

    wrapped = s.self_improve_round(env, lambda task: [(task.gold,)], 3)
    assert len(wrapped["kept"]) == 3, (
        "an agent answering [(gold,)] answered the question: the verifier inside "
        "the round unwraps like every other caller: %r" % (wrapped,))

    broken = s.self_improve_round(env, lambda task: "no idea", 4)
    assert broken["accuracy"] == 0.0 and len(broken["failed"]) == 4, (
        "a solver that answers nothing keeps nothing, and its failures are the "
        "curriculum: %r" % (broken,))
    assert broken["generated"] == len(broken["kept"]) + len(broken["failed"]), (
        "every generated task is kept or failed, never both and never neither")

    def exploding(task):
        raise RuntimeError("the solver crashed")

    crashed = s.self_improve_round(env, exploding, 3)
    assert crashed["accuracy"] == 0.0 and len(crashed["failed"]) == 3, (
        "an agent that raises on a task failed THAT task: a crash is a wrong "
        "answer, not the end of the round: %r" % (crashed,))

    selective = s.self_improve_round(
        env, lambda task: task.gold if task.kind == "number" else "no", 6)
    assert selective["accuracy"] == len(selective["kept"]) / 6.0, (
        "without a holdout the number is the solver's accuracy on the generated "
        "set, which is a smoke test of the plumbing: %r" % (selective["accuracy"],))
    assert 0.0 < selective["accuracy"] < 1.0, (
        "the fixture is a solver that answers some tasks: %r"
        % (selective["accuracy"],))

    # the number that matters: measured where the agent has not been. The first
    # task the generator makes is the category one, whose answer is "furniture":
    # this agent keeps it and fails the held-out country question.
    holdout = [Task("H1", "Which country spends the most?",
                    "SELECT country FROM sales GROUP BY country "
                    "ORDER BY SUM(revenue) DESC LIMIT 1", "ES", "text")]
    honest = s.self_improve_round(env, lambda task: "furniture", 1,
                                 holdout=holdout)
    assert len(honest["kept"]) == 1 and honest["kept"][0].gold == "furniture", (
        "the generated task's answer is 'furniture' and the agent says "
        "'furniture': the round kept it: %r" % (honest,))
    assert honest["accuracy"] == 0.0, (
        "and the accuracy must be 0.0 anyway, because the holdout asks a different "
        "question whose answer is 'ES': the number a self-improving loop plots is "
        "measured on tasks this round did not make, got %r" % (honest["accuracy"],))
    assert honest["generated"] == len(honest["kept"]) + len(honest["failed"]), (
        "the split is the split, whatever the reported accuracy is: %r" % (honest,))

    holdout_solved = s.self_improve_round(env, lambda task: task.gold, 1,
                                          holdout=holdout)
    assert holdout_solved["accuracy"] == 1.0, (
        "an agent that answers the held-out task scores on it: %r"
        % (holdout_solved["accuracy"],))

    seen = []

    def counting(task):
        seen.append(task)
        return task.gold

    s.self_improve_round(env, counting, 3, holdout=holdout)
    assert len(seen) == 4, (
        "3 generated tasks and 1 held-out task: 3 + 1 agent calls, got %d — the "
        "held-out tasks are solved once, and the generated ones are not solved "
        "twice to compute a number nobody plots" % (len(seen),))

    try:
        s.self_improve_round(env, perfect, 2, holdout=[])
    except HarnessError:
        pass
    else:
        raise AssertionError(
            "a holdout with no tasks is not a measurement: accuracy on no tasks is "
            "0.0 or 1.0 depending on which way the loop divides, and either number "
            "is a lie")

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The model is a callable returning an event stream",
        tags=["streaming", "reduction"],
        action="Write `collect`, `assistant_message`, `usage_add`, `EVENT_TYPES` "
               "and `EMPTY_USAGE` in stage_01.py.",
        predict="How many events `text_events('hi')` emits, and what `collect` "
                "returns for a stream that never sends `end`.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The context window is a budget, not a list",
        tags=["context", "tokens"],
        action="Write `estimate_tokens`, `Context` and `assemble` in stage_02.py.",
        predict="The token estimate of the system message, and whether the newest "
                "turn survives a budget it cannot fit in.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="The loop, and what a budget exhaustion returns",
        tags=["agent-loop", "outcomes"],
        action="Write `run` in stage_03.py.",
        predict="The `status` when `max_steps` runs out in the middle of a tool "
                "call, and how many tool observations the conversation holds.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="Dispatch: an unknown tool is a message, a failing tool is an "
              "observation",
        tags=["tools", "errors"],
        action="Write `Dispatcher` and `render_result` in stage_04.py.",
        predict="What the model reads when it calls a tool that does not exist, "
                "and which exception from a tool body ends the run.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Streaming, and the timings of a turn",
        tags=["streaming", "latency"],
        action="Write `stream` and `timings` in stage_05.py.",
        predict="The time-to-first-token of a turn whose first event is a tool "
                "call, and the events one turn contributes to the sink.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Retries: the model call, never the tool call",
        tags=["retries", "backoff"],
        action="Write `Retrying` in stage_06.py.",
        predict="How long the clock slept after two retries with `backoff=0.5`, "
                "and what a stream that already yielded an event does.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Compaction: summarize the middle",
        tags=["context", "compaction"],
        action="Write `compact` and `SUMMARY_PREFIX` in stage_07.py.",
        predict="How many messages a compacted context has, which message is "
                "never summarized, and whether compacting twice calls the "
                "summarizer twice.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The trace, the artifact you can replay",
        tags=["observability", "tracing"],
        action="Write `Trace` in stage_08.py.",
        predict="The summary of a run with one retry in it, and whether the "
                "model's arguments can appear in it.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="Process reward: a step has to be grounded in what came back",
        tags=["reward", "grounding"],
        action="Write `cite_values`, `cites_previous_result` and `process_reward` "
               "in stage_09.py.",
        predict="The reward for an episode whose third step cites its FIRST step's "
                "result instead of the one before it.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="Verification and the self-generated data loop",
        tags=["verification", "self-improvement"],
        action="Write `make_verifier`, `generate_tasks` and "
               "`self_improve_round` in stage_10.py.",
        predict="The accuracy reported for an agent that solves every task it "
                "generated and fails the held-out ones.",
        check=check_10,
    ),
]
