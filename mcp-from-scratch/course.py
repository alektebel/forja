"""MCP From Scratch — course manifest.

Ten graded stages that build an MCP server from the bytes up: the JSON-RPC
envelope and the four ways to answer it, the transports that frame it (a stdio
line, an SSE event, an HTTP POST), the handshake that negotiates a revision and a
capability table that cannot lie, tools whose arguments are validated and whose
errors are split into protocol and execution, resources and prompt templates
(including the one "not found" the spec pins), out-of-band messages where a
cancelled request gets no answer at all, read-only-first tool design with the
allowlisted report in the middle, idempotency keys for a caller that retries, a
confirmation dialog that shows the diff it is about to apply, and the trajectory
policy plus the audit line that has no clock and no payload.

The domain is provided (`erp.py`); the protocol is the exercise. No sockets, no
network, no wall clock: every transport reads and writes in-memory streams, so a
test can hand the server bytes and read what came back.

    python3 codecraft/cli.py run mcp-from-scratch
"""

from codecraft.api import stage

TITLE = "MCP From Scratch"
DESCRIPTION = ("A standards-shaped MCP server from the bytes up: the JSON-RPC "
               "envelope and its error codes, stdio/SSE/HTTP framing and stdout "
               "purity, the lifecycle handshake and derived capabilities, tools "
               "and the protocol-versus-execution error split, resources and "
               "prompt templates, subscriptions, progress and cancellation, a "
               "read-only-first toolset with an allowlisted report, idempotency "
               "keys, a confirmation that shows the diff, and the trajectory "
               "policy with an audit line that carries no clock and no payload.")
LEVEL = "intermediate"
ORDER = 12
# --- imports hoisted from the check sources ---
import json
import stage_01
import stage_03
import stage_10
import importlib
import os
import shutil
import sys
import tempfile

# --- from checks/check_mine.py
def check_1():
    """The envelope: what a message is, and the four ways to answer it."""
    from stage_01 import (ERRORS, Dispatcher, ProtocolError, decode, encode, error,
                          notification, request, result)

    def error_code(response):
        """The JSON-RPC error code of a response, or None. A mutation that answers
        where it should have refused must fail an assertion, not a lookup."""
        if not isinstance(response, dict):
            return None
        error = response.get("error")
        return error.get("code") if isinstance(error, dict) else None


    # -- the shapes ---------------------------------------------------------
    message = request(7, "tools/call", {"name": "report"})
    assert message == {"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                       "params": {"name": "report"}}, (
        "request() must build the exact envelope, got %r" % (message,))
    assert request("a", "ping") == {"jsonrpc": "2.0", "id": "a", "method": "ping"}, (
        "a request without params must not carry a params key")
    assert notification("notifications/cancelled", {"requestId": 1}) == {
        "jsonrpc": "2.0", "method": "notifications/cancelled",
        "params": {"requestId": 1}}, "a notification has no id key at all"
    assert result(3, {}) == {"jsonrpc": "2.0", "id": 3, "result": {}}, (
        "an empty result is still a result")
    built = error(3, -32601, "nope", {"method": "x"})
    assert built == {"jsonrpc": "2.0", "id": 3,
                     "error": {"code": -32601, "message": "nope",
                               "data": {"method": "x"}}}, (
        "error() must nest the code and message under 'error', got %r" % (built,))
    assert "data" not in error(3, -32603, "x")["error"], (
        "an error without data must not carry a data key")

    # -- the codes ----------------------------------------------------------
    assert ERRORS["parse"] == -32700 and ERRORS["invalid_request"] == -32600, (
        "the JSON-RPC codes are fixed numbers")
    assert ERRORS["method_not_found"] == -32601 and ERRORS["invalid_params"] == -32602, (
        "inventing a code is how a client stops being able to classify an error")
    assert ERRORS["internal"] == -32603, "the internal-error code is -32603"
    assert ERRORS["resource_not_found"] == -32002, (
        "MCP pins resource-not-found to -32002, not to a -326xx code")

    # -- the wire -----------------------------------------------------------
    text = encode(result(1, {"b": [1, 2], "a": 1}))
    assert text == '{"id":1,"jsonrpc":"2.0","result":{"a":1,"b":[1,2]}}', (
        "encode() must sort keys and emit no spaces, so a byte diff is a "
        "behaviour diff: got %s" % text)
    assert "\n" not in text, (
        "a stdio frame is one line: an embedded newline splits one message into two")
    assert decode(text) == result(1, {"b": [1, 2], "a": 1}), (
        "decode must be the inverse of encode")
    for garbage in ("{oops", "", "not json at all"):
        out = decode(garbage)
        assert error_code(out) == -32700 and out["jsonrpc"] == "2.0", (
            "a message that is not JSON is a parse error (-32700) with id null, "
            "got %r" % (out,))
        assert out["id"] is None, (
            "when the bytes do not parse, the id cannot be known: null")
        assert isinstance((out.get("error") or {}).get("message"), str) and (out.get("error") or {}).get("message"), (
            "a parse error must carry a message a human can read")
    assert decode("[1,2]") == [1, 2], (
        "decode parses; only dispatch decides that a batch is not an MCP message")

    # -- dispatch -----------------------------------------------------------
    dispatcher = Dispatcher()
    seen = []
    dispatcher.add("echo", lambda params: {"echo": params.get("text")})
    assert dispatcher.dispatch(request(1, "echo", {"text": "hi"})) == result(
        1, {"echo": "hi"}), "a known method answers result(id, value)"
    assert dispatcher.dispatch(request("i-2", "echo")) == result("i-2", {"echo": None}), (
        "params absent means {} for the handler, not None")

    out = dispatcher.dispatch(request(2, "nope"))
    assert error_code(out) == -32601 and out["id"] == 2, (
        "an unknown method is -32601 with the request's id, got %r" % (out,))

    for bad, why in [
            ({"id": 3, "method": "echo"}, "a missing jsonrpc version"),
            ({"jsonrpc": "1.0", "id": 3, "method": "echo"}, "jsonrpc 1.0"),
            ({"jsonrpc": "2.0", "id": None, "method": "echo"}, "a null id"),
            ({"jsonrpc": "2.0", "id": True, "method": "echo"},
             "a boolean id: True is an int in Python, and it is not a RequestId"),
            ({"jsonrpc": "2.0", "id": 3, "method": ""}, "an empty method"),
            ({"jsonrpc": "2.0", "id": 3, "method": "echo", "params": []},
             "params that are a list"),
            ("not-an-object", "a message that is not an object"),
            ([{"jsonrpc": "2.0", "id": 1, "method": "echo"}], "a JSON-RPC batch"),
    ]:
        out = dispatcher.dispatch(bad)
        assert out is not None and error_code(out) == -32600, (
            "%s must be answered with -32600, got %r" % (why, out))
        assert "result" not in out, "an error response must not carry a result key"
    assert dispatcher.dispatch({"jsonrpc": "2.0", "id": None, "method": "echo"})["id"] is None, (
        "when the id itself is invalid the response's id is null: it cannot be "
        "matched to the request")

    # -- failures with nobody to answer to ----------------------------------
    failures_before = len(dispatcher.failures)
    assert dispatcher.dispatch(notification("nope")) is None, (
        "a notification is never answered, not even when the method is unknown")
    assert len(dispatcher.failures) == failures_before + 1, (
        "a notification the server could not serve belongs in failures, or it is "
        "lost with no trace")
    assert "nope" in str(dispatcher.failures[-1]), (
        "the failure record must name the method, got %r" % (dispatcher.failures[-1],))

    def boom(params):
        raise ProtocolError(-32602, "bad params", {"field": "text"})

    dispatcher.add("boom", boom)
    out = dispatcher.dispatch(request(4, "boom"))
    assert (out.get("error") or {}) == {"code": -32602, "message": "bad params",
                            "data": {"field": "text"}}, (
        "a ProtocolError is the handler's way to answer with a specific code, "
        "got %r" % (out,))

    def crash(params):
        raise ValueError("something broke inside")

    dispatcher.add("crash", crash)
    out = dispatcher.dispatch(request(5, "crash"))
    assert error_code(out) == -32603, (
        "any other exception is an internal error (-32603), got %r" % (out,))
    assert "ValueError" in (out.get("error") or {}).get("message"), (
        "the internal error must name the exception type so the author can find "
        "it, got %r" % ((out.get("error") or {}).get("message"),))
    assert "Traceback" not in (out.get("error") or {}).get("message"), (
        "a traceback on the wire is an information leak, not an error message")

    crashed_before = len(dispatcher.failures)
    assert dispatcher.dispatch(notification("crash")) is None, (
        "a notification whose handler crashed is not answered")
    assert len(dispatcher.failures) == crashed_before + 1 and \
        "ValueError" in dispatcher.failures[-1]["error"], (
        "a crashed notification is recorded with its exception type, got %r"
        % (dispatcher.failures[-1:],))

    dispatcher.add("ugly", lambda params: {"bad": {1, 2}})
    out = dispatcher.dispatch(request(6, "ugly"))
    assert error_code(out) == -32603, (
        "a handler that returns something JSON cannot encode is an internal "
        "error, not a crash after the result was promised, got %r" % (out,))


# --- from checks/check_02.py
def check_2():
    import json

    import stage_02 as s
    from stage_01 import Dispatcher, ERRORS, decode, encode, notification, request

    class Recorder:
        """A writer/sink that keeps every string it was handed."""

        def __init__(self):
            self.text = ""

        def write(self, text):
            self.text += text

    def reader_from(*chunks):
        """A chunk-producing callable: the chunks in order, then ""."""
        queue = list(chunks)

        def read():
            if queue:
                return queue.pop(0)
            return ""

        return read

    def wire(text):
        """Every complete line the writer received must parse as a message."""
        parts = text.split("\n")
        assert parts[-1] == "", (
            "the wire does not end on a newline: every message is one "
            "newline-terminated line and nothing else")
        parsed = []
        for part in parts[:-1]:
            parsed.append(json.loads(part))  # a log line is not JSON, so this fails
        return parsed

    # send: exactly encode(message) + "\n", and the newline is reserved
    encoded = encode(request(1, "ping", {"n": 1}))
    writer = Recorder()
    transport = s.LineTransport(reader_from(), writer)
    written = transport.send(request(1, "ping", {"n": 1}))
    assert written == encoded + "\n", (
        f"send wrote {written!r}: a stdio message is exactly encode(message) + '\\n'")
    assert writer.text == written, "send must write exactly the string it returns"
    assert "\n" not in encoded, (
        "encode() produced an embedded newline: the framing byte must never "
        "appear inside a message")

    # receive: the last line of a stream needs no trailing newline
    transport = s.LineTransport(reader_from('{"half"'), Recorder())
    assert transport.receive() == '{"half"', (
        "a final line without a trailing newline was dropped")
    assert transport.receive() is None, (
        "an exhausted reader with an empty buffer is None")

    # receive: bytes read but not yet a complete line stay in .buffer
    transport = s.LineTransport(reader_from("first\nsecond"), Recorder())
    assert transport.receive() == "first"
    assert transport.buffer == "second", (
        f".buffer is {transport.buffer!r}: the tail read after a line is kept there "
        f"until a newline arrives")
    assert transport.receive() == "second"
    assert transport.receive() is None

    # receive: a message split across two chunks is ONE message
    first = encode(request(1, "ping"))
    second = encode(request(2, "pong"))
    transport = s.LineTransport(
        reader_from(first[:5], first[5:] + "\n" + second + "\n"), Recorder())
    assert transport.receive() == first, (
        "a line that arrives in two reads is one message, not two (and not half)")
    assert transport.receive() == second
    assert transport.receive() is None

    # receive: three messages in one chunk are three calls, then None
    messages = [encode(request(i, "ping")) for i in (1, 2, 3)]
    transport = s.LineTransport(reader_from("\n".join(messages)), Recorder())
    got = [transport.receive() for _ in range(3)]
    assert got == messages, (
        f"three messages in one chunk were not three messages: {got!r}")
    assert transport.receive() is None, (
        "the reader is exhausted and the buffer is empty: receive() is None")

    # receive: a \r\n ending is framing, not part of the message
    transport = s.LineTransport(
        reader_from('{"jsonrpc":"2.0","method":"ping"}\r\n'), Recorder())
    assert transport.receive() == '{"jsonrpc":"2.0","method":"ping"}', (
        "a lone \\r was left at the end of the line: with \\r\\n the \\r is framing")

    # log: the sink gets the tagged line, the writer gets nothing
    writer = Recorder()
    sink = Recorder()
    transport = s.LineTransport(reader_from(), writer, sink)
    transport.log("info", "starting")
    assert transport.log_lines == ["[info] starting"], transport.log_lines
    assert sink.text == "[info] starting\n", (
        "log() must hand the tagged line to the sink")
    assert writer.text == "", (
        "a log line reached the writer: stdout carries messages and nothing else")

    # run: one response per request, none for a notification, -32700 off decode
    writer = Recorder()
    sink = Recorder()
    server = Dispatcher()
    seen = []

    def ping(params):
        return {"pong": params}

    def noisy(params):
        seen.append("noisy")
        transport.log("debug", "a handler logging")
        return {}

    server.add("ping", ping)
    server.add("noisy", noisy)

    lines = [encode(request(1, "ping", {"n": 1})),
             encode(notification("noisy")),
             "this is not json",
             encode(request(2, "ping"))]
    transport = s.LineTransport(reader_from("\n".join(lines) + "\n"), writer, sink)
    handled = transport.run(server)

    assert handled == 4, f"run handled {handled} of the 4 lines it was given"
    assert transport.handled == 4, (
        "run must leave the count on .handled")
    assert seen == ["noisy"], "a notification still runs its handler"
    assert transport.log_lines == ["[debug] a handler logging"]
    assert sink.text == "[debug] a handler logging\n", (
        "the handler's log() went somewhere other than the sink")
    assert "a handler logging" not in writer.text, (
        "log() output appeared in the writer: stdout carries messages and nothing else")

    sent = wire(writer.text)  # also proves no log text is on the wire
    assert len(sent) == 3, (
        f"{len(sent)} messages on the wire: one response per request, and none at "
        f"all for a notification")
    assert [message.get("id") for message in sent] == [1, None, 2], sent
    assert sent[0]["result"] == {"pong": {"n": 1}}
    assert sent[2]["result"] == {"pong": {}}
    assert sent[1]["error"]["code"] == ERRORS["parse"], (
        "a line that is not JSON is the -32700 response decode() built, sent as-is")
    assert sent[1]["id"] is None, (
        "the parse error cannot know the id, so it carries null")
    assert all(message.get("jsonrpc") == "2.0" for message in sent), (
        "something that is not a message reached the wire")

    # run(limit=...) stops early and leaves the rest of the stream alone
    tail = encode(request(2, "ping"))
    transport = s.LineTransport(
        reader_from(encode(request(1, "ping")) + "\n" + tail + "\n"), Recorder())
    assert transport.run(server, limit=1) == 1, "limit caps the messages handled"
    assert transport.receive() == tail, (
        "run(limit=1) consumed more than one message")

    # SseWriter: the exact framing, and the JSON survives it
    sse = s.SseWriter()
    message = {"jsonrpc": "2.0", "id": 1, "result": {"text": "a\nb"}}
    event = sse.event(message)
    assert event == "event: message\ndata: " + encode(message) + "\n\n", (
        f"SSE framing is 'event: message\\ndata: {{json}}\\n\\n', got {event!r}")
    assert sse.lines == [event], sse.lines
    assert event.count("\n") == 3, (
        "an SSE event is three lines: the event name, the data, and the blank "
        "separator")
    data = event.split("\n")[1]
    assert data.startswith("data: "), data
    assert json.loads(data[len("data: "):]) == message, (
        "the JSON on a data line must contain no raw newline: it has to survive "
        "the one-line-per-field framing")

    # HttpTransport.post: 200 for a request, 202 for a notification, -32700 for junk
    sink = Recorder()
    server = Dispatcher()
    server.add("ping", lambda params: {"pong": params})
    http = s.HttpTransport(server, sink)
    assert http.sse_events == [], (
        "a plain POST is answered with JSON; SSE is a choice the client makes, "
        "not this stage")

    status, content_type, body = http.post(encode(request(7, "ping", {"n": 2})))
    assert (status, content_type) == (200, "application/json"), (status, content_type)
    assert json.loads(body) == {"jsonrpc": "2.0", "id": 7,
                                "result": {"pong": {"n": 2}}}, body

    status, content_type, body = http.post(encode(notification("ping")))
    assert (status, content_type, body) == (202, "", ""), (
        f"a notification POST answered {(status, content_type, body)!r}: 202 with "
        f"no body, because there is nothing to send and the client must not wait")

    status, content_type, body = http.post("this is not json")
    assert (status, content_type) == (200, "application/json"), (status, content_type)
    parsed = json.loads(body)
    assert parsed["error"]["code"] == ERRORS["parse"] and parsed["id"] is None, parsed

    # SSE is produced through the SseWriter, and .sse_events is what it wrote
    event = http.sse.event({"jsonrpc": "2.0", "id": 9, "result": {}})
    assert http.sse_events == [event] and event.startswith("event: message\ndata: "), (
        f".sse_events is {http.sse_events!r}: the events written through SseWriter")


# --- from checks/check_mine.py
def check_3():
    """The handshake: a gate, a negotiated revision, and a capability table that
    only claims what is there."""
    from stage_01 import notification, request
    from stage_03 import Server

    def error_code(response):
        """The JSON-RPC error code of a response, or None. A mutation that answers
        where it should have refused must fail an assertion, not a lookup."""
        if not isinstance(response, dict):
            return None
        error = response.get("error")
        return error.get("code") if isinstance(error, dict) else None


    def wired(**kw):
        server = Server("erp-mcp", "0.1.0", **kw)
        server.add("tools/list", lambda params, session: {"tools": []})
        server.add("resources/list", lambda params, session: {"resources": []})
        server.add("resources/subscribe", lambda params, session: {})
        return server

    handshake = request(1, "initialize", {
        "protocolVersion": "2025-06-18", "clientInfo": {"name": "claude"},
        "capabilities": {"elicitation": {}}, "_meta": {"identity": "user:ana"}})

    server = wired()
    assert server.initialized is False and server.capabilities == {}, (
        "before the handshake there is nothing negotiated: capabilities must be "
        "empty and initialized false")
    out = server.dispatch(handshake)
    assert "error" not in out, "a supported revision must be accepted, got %r" % (out,)
    body = (out.get("result") or {})
    assert body.get("protocolVersion") == "2025-06-18", (
        "the server echoes the revision it will speak, got %r" % (body.get("protocolVersion"),))
    assert body.get("serverInfo") == {"name": "erp-mcp", "version": "0.1.0"}, (
        "serverInfo carries the server's name and version, got %r" % (body.get("serverInfo"),))
    assert body.get("capabilities") == {"tools": {"listChanged": True},
                                    "resources": {"subscribe": True,
                                                  "listChanged": True}}, (
        "capabilities are derived from the methods that exist: tools/* gives "
        "tools, resources/subscribe gives subscribe, got %r" % (body.get("capabilities"),))
    assert server.initialized is False, (
        "the response to initialize does not finish the handshake: only "
        "notifications/initialized does")
    assert server.session["identity"] == "user:ana", (
        "the handshake is where the session's identity comes from")
    assert server.supports("elicitation") is True and server.supports("roots") is False, (
        "a client declaring \"elicitation\": {} supports elicitation: the "
        "declaration is the key's presence, not the truthiness of its options")
    assert server.client_info == {"name": "claude"}, (
        "clientInfo is part of the handshake result and must be kept")

    out = server.dispatch(request(2, "tools/list"))
    assert error_code(out) == -32600, (
        "a request between initialize and notifications/initialized is refused "
        "with -32600 (the method exists; the session is what is wrong), got %r" % (out,))
    assert server.initialized is False

    assert server.dispatch(notification("notifications/initialized")) is None, (
        "notifications/initialized is a notification: it answers nothing")
    assert server.initialized is True and server.dispatcher.failures == [], (
        "the initialized notification completes the handshake, got failures %r"
        % (server.dispatcher.failures,))
    assert server.dispatch(request(3, "tools/list"))["result"] == {"tools": []}, (
        "after the handshake the server serves")

    out = server.dispatch(request(4, "initialize", {"protocolVersion": "2025-06-18"}))
    assert error_code(out) == -32600, (
        "a second initialize is a protocol violation (-32600), got %r" % (out,))
    out = server.dispatch(request(5, "initialize", {"protocolVersion": "2024-11-05"}))
    assert error_code(out) == -32600, (
        "the second initialize is refused before the version is even looked at, "
        "got %r" % (out,))

    # a fresh server: the version negotiation itself
    fresh_server = wired()
    assert fresh_server.dispatch(request(1, "ping"))["result"] == {}, (
        "ping must work before the handshake: a liveness check that needs a "
        "handshake cannot check liveness")
    out = fresh_server.dispatch(request(2, "tools/list"))
    assert error_code(out) == -32600, (
        "a request before initialize is refused, got %r" % (out,))
    out = fresh_server.dispatch(request(3, "initialize", {"protocolVersion": "2024-11-05"}))
    assert error_code(out) == -32602, (
        "an unsupported revision is -32602, got %r" % (out,))
    assert (out.get("error") or {}).get("data") == {"supported": ["2025-06-18"],
                                    "requested": "2024-11-05"}, (
        "the error tells the client which revisions ARE supported, got %r"
        % (out["error"],))
    assert fresh_server.initialized is False and fresh_server.protocol_version is None, (
        "a refused version must not half-initialize the session")
    out = fresh_server.dispatch(request(4, "initialize", {}))
    assert error_code(out) == -32600, (
        "initialize without a protocolVersion is malformed, got %r" % (out,))
    ok = fresh_server.dispatch(request(5, "initialize", {"protocolVersion": "2025-06-18"}))
    assert ok["result"]["protocolVersion"] == "2025-06-18", (
        "after a refused attempt the same session may still handshake")

    # a capability with no method behind it
    liar = Server("erp-mcp", "0.1.0", capabilities={"resources": {"subscribe": True}})
    liar.add("resources/list", lambda params, session: {})
    out = liar.dispatch(request(1, "initialize", {"protocolVersion": "2025-06-18"}))
    assert error_code(out) == -32603, (
        "declaring a capability nothing backs is a server bug: it must surface as "
        "-32603, not as a promise the client will plan against, got %r" % (out,))
    assert "subscribe" in (out.get("error") or {}).get("message"), (
        "the message must name the capability, got %r" % ((out.get("error") or {}).get("message"),))
    honest = Server("erp-mcp", "0.1.0", capabilities={"tools": {"listChanged": False}})
    honest.add("tools/list", lambda params, session: {})
    out = honest.dispatch(request(1, "initialize", {"protocolVersion": "2025-06-18"}))
    assert (out.get("result") or {})["capabilities"] == {"tools": {"listChanged": False}}, (
        "a declared capability that IS backed may be narrowed, got %r"
        % ((out.get("result") or {})["capabilities"],))

    # no tools at all: capabilities stay empty
    bare = Server("erp-mcp", "0.1.0")
    out = bare.dispatch(request(1, "initialize", {"protocolVersion": "2025-06-18"}))
    assert (out.get("result") or {})["capabilities"] == {}, (
        "a server with no methods declares nothing, got %r"
        % ((out.get("result") or {})["capabilities"],))

    # notifications/initialized before initialize
    early = wired()
    assert early.dispatch(notification("notifications/initialized")) is None, (
        "a notification is never answered")
    assert early.initialized is False, (
        "an initialized notification before initialize must not open the gate")
    assert len(early.dispatcher.failures) == 1, (
        "that notification belongs in failures, got %r" % (early.dispatcher.failures,))

    # the tool table
    table = Server("erp-mcp", "0.1.0")
    definition = table.add_tool("report", "read a report", {"type": "object"},
                                lambda params, session: {}, mutates=False)
    assert table.tools["report"] is definition, "add_tool returns the definition it stored"
    assert definition == {"name": "report", "description": "read a report",
                          "inputSchema": {"type": "object"},
                          "fn": definition.get("fn"), "mutates": False,
                          "enabled": True}, (
        "a definition carries exactly these keys, got %r" % (definition,))
    try:
        table.add_tool("report", "again", {}, lambda params, session: {})
        raise AssertionError(
            "re-registering a tool name must raise: a duplicate that silently "
            "replaces a definition is how a read-only server grows a write tool")
    except ValueError:
        pass
    assert table.set_tool_enabled("report", False, reason="read-only")["enabled"] is False, (
        "set_tool_enabled flips the flag and returns the definition")
    assert table.tools["report"].get("reason") == "read-only", (
        "the reason a tool is hidden must be recorded: the operator needs it")
    try:
        table.set_tool_enabled("nope", True)
        raise AssertionError("enabling a tool that does not exist must raise")
    except ValueError:
        pass

    # a mutating tool on a read-only server arrives disabled, with a reason
    guarded = Server("erp-mcp", "0.1.0")
    reader = guarded.add_tool("report", "read", {"type": "object"},
                              lambda arguments, session: {})
    assert reader["enabled"] is True, "a read-only tool is listed by default"
    writer = guarded.add_tool("apply_change", "write", {"type": "object"},
                              lambda arguments, session: {}, mutates=True)
    assert writer["enabled"] is False, (
        "a server with no author's blessing is read-only, and a mutating tool "
        "registered on it must arrive DISABLED: a tool the model can see is a tool "
        "the model will call")
    assert "read-only" in (writer.get("reason") or ""), (
        "the reason it is hidden must be recorded, or an operator seeing an empty "
        "tools/list has nothing to read; got %r" % (writer.get("reason"),))
    assert guarded.read_only is True, (
        "the read-only flag belongs to the server, so another stage's install can "
        "consult it and stage 7's flip can clear it")
    guarded.read_only = False
    assert guarded.set_tool_enabled("apply_change", True, reason=None)["enabled"] is True, (
        "the flip is what exposes the mutating tool")

    # notify + on_notify
    seen = []
    talker = Server("erp-mcp", "0.1.0", on_notify=seen.append)
    sent = talker.notify("notifications/tools/list_changed")
    assert sent == {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}, (
        "notify sends a notification and returns it, got %r" % (sent,))
    assert talker.notifications == [sent] and seen == [sent], (
        "a notification must be reachable twice: on the server and on the "
        "callback a transport prints from")
    assert "id" not in sent, "a notification has no id"

    # the cancellation seams
    class FakeCancellations:
        def __init__(self):
            self.cancelled = set()
            self.protected = set()
            self.in_flight = set()
            self.answered = []

        def answer_for(self, request_id, response):
            self.answered.append((request_id, request_id in self.in_flight))
            self.in_flight.discard(request_id)
            return None if request_id in self.cancelled else response

    cancellations = FakeCancellations()
    cancelling = wired()
    cancelling.cancellations = cancellations
    out = cancelling.dispatch(request(11, "initialize", {"protocolVersion": "2025-06-18"}))
    assert 11 in cancellations.protected, (
        "the initialize request's id must be protected: the spec forbids "
        "cancelling it, and a cancelled handshake leaves a session with no "
        "revision")
    assert out["id"] == 11, "a protected request is still answered"
    cancelling.dispatch(notification("notifications/initialized"))
    cancellations.cancelled.add(12)
    assert cancelling.dispatch(request(12, "tools/list")) is None, (
        "a cancelled request gets NO response: dispatch must consult "
        "cancellations.answer_for and send nothing")
    cancellations.cancelled.discard(12)
    assert (cancelling.dispatch(request(12, "tools/list")) or {}).get("id") == 12, (
        "an uncancelled request is answered normally")
    assert cancellations.answered == [(11, True), (12, True), (12, True)], (
        "every answer goes through the registry, and each arrives with the request "
        "announced as STARTED; got %r" % (cancellations.answered,))
    assert all(announced for _, announced in cancellations.answered), (
        "the registry is only asked about a request the server has announced as "
        "STARTED: without that announcement a cancellation for work in progress is "
        "indistinguishable from one that arrived after the answer, and the "
        "cancellation path is dead code; got %r" % (cancellations.answered,))
    assert cancellations.in_flight == set(), (
        "an answered request leaves in-flight, which is what makes a late "
        "notifications/cancelled ignorable; got %r" % (cancellations.in_flight,))

    # install()
    class Module:
        installed = []

        def install(self, server):
            Module.installed.append(server)

    target = Server("erp-mcp", "0.1.0")
    assert target.install(Module()) is not None, "install returns something harmless"
    assert Module.installed == [target], (
        "install(module) must call module.install(self) so a stage can join a server")


# --- from checks/check_04.py
def check_4():
    HERE = os.path.dirname(os.path.abspath(__file__))

    def _c4_course_dir(start=None):
        """The `mcp-from-scratch` directory, found from the cwd upward."""
        here = os.path.abspath(start or os.environ.get("D1_REPO") or os.getcwd())
        while True:
            candidate = os.path.join(here, "mcp-from-scratch")
            if os.path.isfile(os.path.join(candidate, "stage_01.py")):
                return candidate
            parent = os.path.dirname(here)
            if parent == here:
                raise RuntimeError(f"mcp-from-scratch/ was not found above {here}")
            here = parent

    def _c4_build_env(dest=None, course=None):
        """A directory holding the stages: the course's `*.py` templates, then
        `solutions/*.py` overlaid on top."""
        course = course or _c4_course_dir()
        dest = dest or tempfile.mkdtemp(prefix="d1-stage04-")
        if not os.path.isdir(dest):
            os.makedirs(dest)
        for name in sorted(os.listdir(course)):
            if name.endswith(".py"):
                shutil.copy(os.path.join(course, name), os.path.join(dest, name))
        solutions = os.path.join(course, "solutions")
        for name in sorted(os.listdir(solutions)):
            if name.endswith(".py"):
                shutil.copy(os.path.join(solutions, name), os.path.join(dest, name))
        return dest

    def _c4_run_check(env):
        """Import this file fresh with `env` first on sys.path, and press check()."""
        env = os.path.abspath(env)
        for name in ("stage_01", "stage_04", "erp", "check_04"):
            sys.modules.pop(name, None)
        sys.path.insert(0, env)
        try:
            importlib.invalidate_caches()
            spec = importlib.util.spec_from_file_location(
                "check_04", os.path.join(HERE, "check_04.py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.check()
        finally:
            sys.path.remove(env)

    def _c4_main():
        env = _c4_build_env()
        _c4_run_check(env)
        print("check_04: PASS")

    import json
    import stage_04 as s
    from stage_01 import Dispatcher, ERRORS, ProtocolError, request
    from erp import Erp

    VENDOR_SCHEMA = {
        "type": "object",
        "properties": {"vendor_id": {"type": "string"},
                       "detail": {"type": "boolean"}},
        "required": ["vendor_id"],
    }
    QUERY_SCHEMA = {
        "type": "object",
        "properties": {"table": {"type": "string", "enum": ["vendors", "items"]},
                       "limit": {"type": "integer"}},
        "required": ["table"],
    }
    NO_ARGS = {"type": "object", "properties": {}}
    CREDIT_HOLD = "vendor v1 is on credit hold - do not retry, ask the user"
    TABLE = "vendor_id  name\nv1  Northwind Fasteners\nv2  Acme Industrial"

    erp = Erp()

    class FakeServer:
        """What stage 4 is allowed to assume of stage 3, and nothing more."""

        def __init__(self):
            self.handlers = {}
            self.notifications = []
            self.tools = {}
            self.session = {"identity": None, "steps": [], "data": {}}

        def add(self, method, handler):
            self.handlers[method] = handler

        def notify(self, method, params=None):
            self.notifications.append({"jsonrpc": "2.0", "method": method,
                                       "params": params})

        def add_tool(self, name, description, input_schema, fn, *,
                     mutates=False, enabled=True):
            definition = {"name": name, "description": description,
                          "inputSchema": input_schema, "fn": fn,
                          "mutates": mutates, "enabled": enabled}
            self.tools[name] = definition
            return definition

        def set_tool_enabled(self, name, enabled, *, reason=None):
            definition = self.tools[name]
            definition["enabled"] = bool(enabled)
            definition["reason"] = reason
            return definition

    ran = []                 # (name, arguments, the session it was handed)

    def recorder(name, fn):
        """The tool body. It records that it was reached, with what, and which
        session it was handed — `fn(arguments, session)`, like every handler."""
        def called(arguments, session):
            ran.append((name, dict(arguments), session))
            return fn(arguments, session)
        return called

    def shaped(result, where):
        """Every result this stage returns has the same two keys, and isError is
        a real bool — no client ever has to assume."""
        assert isinstance(result, dict), (
            f"{where}: a tool result is a dict, got {type(result).__name__}")
        assert set(result) == {"content", "isError"}, (
            f"{where}: a tool result is exactly content + isError; got "
            f"{sorted(result)}")
        assert isinstance(result["isError"], bool), (
            f"{where}: isError must be a real bool, got {result['isError']!r} — a "
            f"client that has to assume it is a client that guesses")
        blocks = result["content"]
        assert isinstance(blocks, list) and blocks, (
            f"{where}: content is always a non-empty list of blocks, got {blocks!r}")
        for block in blocks:
            assert isinstance(block, dict) and block.get("type") == "text", (
                f"{where}: content carries text blocks; got {block!r}")
            assert isinstance(block.get("text"), str), (
                f"{where}: a text block's text is a str; got {type(block.get('text')).__name__}")
        return result

    def refused_with(call, where, code=None):
        """A protocol error, and the RIGHT one."""
        code = ERRORS["invalid_params"] if code is None else code
        try:
            value = call()
        except ProtocolError as exc:
            assert exc.code == code, (
                f"{where}: a bad request is {code} (Invalid params), not "
                f"{exc.code} ({exc.message!r})")
            return exc
        except Exception as exc:                       # noqa: BLE001
            raise AssertionError(
                f"{where}: expected ProtocolError({code}), got "
                f"{type(exc).__name__}: {exc}") from None
        raise AssertionError(
            f"{where}: a bad request must not come back as a result — the tool "
            f"never ran, so the model has nothing to read; got {value!r}")

    # --- the surface ---------------------------------------------------------
    assert s.PAGE == 2, (
        f"PAGE is the page size tools/list pages at unless told otherwise: 2, "
        f"got {s.PAGE!r}")

    demo = s.Tool("demo", "a demo tool", VENDOR_SCHEMA,
                  lambda a, session: "ok", side_effect=True)
    assert demo.definition() == {"name": "demo", "description": "a demo tool",
                                 "inputSchema": VENDOR_SCHEMA}, (
        f"definition() is the spec's Tool shape with the schema verbatim; got "
        f"{demo.definition()!r}")
    assert demo.side_effect is True, (
        "side_effect is carried: a later stage gates the tools that change the world")
    assert s.Tool("d", "d", NO_ARGS, lambda a, session: None).side_effect is False, (
        "side_effect defaults to False: a tool that does not say it changes the "
        "world is treated as a read")

    # --- tools/list: the pages, and the end that is not a page ---------------
    def lister(name):
        return lambda arguments, session: name

    listing = s.ToolRegistry()
    for name in ("vendors", "items", "orders", "balances", "audit"):
        listing.add(s.Tool(name, f"the {name} report", NO_ARGS, lister(name)))

    assert listing.names == ["vendors", "items", "orders", "balances", "audit"], (
        f"registration order IS the list order and is stable, not sorted; got "
        f"{listing.names!r}")
    assert list(listing.tools) == listing.names, (
        f".tools is the same table as .names, in the same order; got "
        f"{list(listing.tools)!r}")
    assert all(isinstance(t, s.Tool) for t in listing.tools.values()), (
        f".tools maps name -> Tool; got "
        f"{[type(t).__name__ for t in listing.tools.values()]}")

    empty = s.ToolRegistry()
    assert empty.list_tools({}) == {"tools": []}, (
        f"an empty registry lists an empty page and nothing else; got "
        f"{empty.list_tools({})!r}")

    first = listing.list_tools({})
    assert set(first) == {"tools", "nextCursor"}, (
        f"there are more tools, so the first page carries a cursor; got "
        f"{sorted(first)}")
    assert [t["name"] for t in first["tools"]] == ["vendors", "items"], (
        f"the first page holds exactly PAGE={s.PAGE} tools; got "
        f"{[t['name'] for t in first['tools']]}")
    second = listing.list_tools({"cursor": first["nextCursor"]})
    assert [t["name"] for t in second["tools"]] == ["orders", "balances"], (
        f"the cursor asks for what comes after it; got "
        f"{[t['name'] for t in second['tools']]}")
    assert second["nextCursor"] == "4", (
        f"the cursor is an opaque string for the next offset; got "
        f"{second['nextCursor']!r}")
    last = listing.list_tools({"cursor": second["nextCursor"]})
    assert [t["name"] for t in last["tools"]] == ["audit"], (
        f"the last page is the rest of the list; got "
        f"{[t['name'] for t in last['tools']]}")
    assert "nextCursor" not in last, (
        f'the LAST page carries no nextCursor KEY — not None, not "": a client '
        f"reads a missing nextCursor as the end of the results, and "
        f"{last.get('nextCursor')!r} is a page that never ends")

    assert listing.list_tools({"cursor": "0"}) == first, (
        "the cursor we hand out is how you ask for the same page again")
    assert listing.list_tools({"cursor": 0}) == first, (
        "an integer cursor is the same request as its string form")
    assert listing.list_tools({"cursor": None}) == first, (
        "a null cursor is the absent cursor, not an error: there is no page "
        "before the first one")

    one_at_a_time = s.ToolRegistry(page=1)
    for name in ("vendors", "items", "orders"):
        one_at_a_time.add(s.Tool(name, f"the {name} report", NO_ARGS, lister(name)))
    assert len(one_at_a_time.list_tools({})["tools"]) == 1, (
        "the registry's own page size wins over PAGE")
    assert one_at_a_time.list_tools({"cursor": "2"})["tools"][0]["name"] == "orders", (
        "page=1 means one tool per page, so cursor '2' is the third tool")

    for cursor in ("99", "banana", "-1", "1.5", 99, 2.5, True, [0], {"offset": 2}):
        exc = refused_with(lambda c=cursor: listing.list_tools({"cursor": c}),
                           f"the cursor {cursor!r}")
        assert exc.data == {"cursor": cursor}, (
            f"the cursor error carries the offending cursor in data so a client "
            f"can see which one it sent; got {exc.data!r}")

    # --- tools/call: a request that is wrong never reaches a tool ------------
    session = {"identity": "diego", "steps": [], "data": {}}

    def run_query(arguments, session):
        table = arguments["table"]
        report = erp.report(table, columns=["vendor_id"] if table == "vendors"
                            else ["item_id"])
        if "limit" in arguments:
            report = {"columns": report["columns"],
                      "rows": report["rows"][:arguments["limit"]]}
        return report

    def on_credit_hold(arguments, session):
        raise s.ToolError(CREDIT_HOLD)

    def render_table(arguments, session):
        return s.text_result(TABLE)

    def render_failure(arguments, session):
        return s.text_result(CREDIT_HOLD, is_error=True)

    registry = s.ToolRegistry()
    registry.add(s.Tool("read_vendor", "read a vendor", VENDOR_SCHEMA,
                        recorder("read_vendor", lambda a, session: erp.read(a["vendor_id"]))))
    registry.add(s.Tool("name_of", "the vendor's name", VENDOR_SCHEMA,
                        recorder("name_of", lambda a, session: erp.read(a["vendor_id"])["name"])))
    registry.add(s.Tool("count_vendors", "how many vendors", NO_ARGS,
                        recorder("count_vendors", lambda a, session: len(erp.vendors))))
    registry.add(s.Tool("unrenderable", "returns something JSON cannot hold",
                        NO_ARGS, recorder("unrenderable", lambda a, session: object())))
    registry.add(s.Tool("render_table", "a tool that builds its own result",
                        NO_ARGS, recorder("render_table", render_table)))
    registry.add(s.Tool("render_failure", "a tool that reports its own failure",
                        NO_ARGS, recorder("render_failure", render_failure)))
    registry.add(s.Tool("content_column", "a value dict with a content key",
                        NO_ARGS, recorder("content_column",
                                          lambda a, session: {"content": ["M8 bolt"],
                                                              "vendor_id": "v1"})))
    registry.add(s.Tool("string_flag", "a value dict with a non-bool isError",
                        NO_ARGS, recorder("string_flag",
                                          lambda a, session: {"content": [{"type": "text",
                                                                           "text": "hi"}],
                                                              "isError": "false"})))
    registry.add(s.Tool("query", "run a report", QUERY_SCHEMA,
                        recorder("query", run_query)))
    registry.add(s.Tool("credit_hold", "a tool the world says no to",
                        VENDOR_SCHEMA, recorder("credit_hold", on_credit_hold)))
    registry.add(s.Tool("broken", "a tool with a bug", NO_ARGS,
                        recorder("broken", lambda a, session: 1 / 0)))

    def refused(call, where):
        """Refused as a protocol error — AND the tool did not run."""
        steps_before = list(session["steps"])
        calls_before = len(ran)
        exc = refused_with(lambda: registry.call_tool(call, session), where)
        assert session["steps"] == steps_before, (
            f"{where}: a rejected request never reached a tool, so "
            f"session['steps'] is untouched at {steps_before!r}; got "
            f"{session['steps']!r}")
        assert len(ran) == calls_before, (
            f"{where}: the tool's function must NOT run for a request that was "
            f"refused; it ran with {ran[calls_before:]!r}")
        return exc

    exc = refused({"name": "no_such_tool", "arguments": {}}, "an unknown tool name")
    assert exc.data == {"tool": "no_such_tool"}, (
        f"an unknown tool's error carries data={{'tool': name}} so a client can "
        f"route it without parsing English; got {exc.data!r}")
    assert "no_such_tool" in exc.message, (
        f"the message names the tool that was not found; got {exc.message!r}")

    exc = refused({}, "a call with no tool name")
    assert exc.data == {"tool": None}, (
        f"a missing name is a bad request too, with the name it did not get; got "
        f"{exc.data!r}")

    exc = refused({"name": "read_vendor", "arguments": {}},
                  "a missing required argument")
    assert "vendor_id" in exc.message, (
        f"the error names the argument that was missing; got {exc.message!r}")
    exc = refused({"name": "read_vendor"}, "no arguments key at all")
    assert "vendor_id" in exc.message, (
        f"the schema is checked even when the caller sent no arguments at all; "
        f"got {exc.message!r}")

    exc = refused({"name": "read_vendor", "arguments": {"vendor_id": 7}},
                  "an argument of the wrong JSON type")
    assert "vendor_id" in exc.message and "string" in exc.message, (
        f"the error names the argument and the type the schema wanted; got "
        f"{exc.message!r}")

    exc = refused({"name": "read_vendor",
                   "arguments": {"vendor_id": "v1", "vendorId": "v1"}},
                  "an argument the schema does not declare")
    assert "vendorId" in exc.message, (
        f"the error names the argument nobody declared (the caller mistyped one "
        f"letter); got {exc.message!r}")

    exc = refused({"name": "read_vendor", "arguments": []},
                  "arguments that are not an object")
    assert exc.data == {"tool": "read_vendor"}, (
        f"the error is still about the tool; got {exc.data!r}")

    exc = refused({"name": "query", "arguments": {"table": "orders"}},
                  "an argument outside its enum")
    assert "table" in exc.message, (
        f"the error names the argument that is not in the enum; got {exc.message!r}")

    exc = refused({"name": "query", "arguments": {"table": "vendors", "limit": True}},
                  "JSON true where an integer was declared")
    assert "limit" in exc.message, (
        f"JSON true is not an integer (isinstance(True, int) is True in Python, "
        f"and that is the trap); got {exc.message!r}")

    # --- the tool has the request now: nothing it does is a protocol error ---
    result = shaped(registry.call_tool(
        {"name": "read_vendor", "arguments": {"vendor_id": "v1"}}, session),
        "tools/call of read_vendor")
    assert result["isError"] is False, (
        f"a call that worked carries isError False explicitly, not a missing "
        f"key; got {result!r}")
    expected = erp.read("v1")
    text = result["content"][0]["text"]
    assert text == json.dumps(expected, sort_keys=True), (
        f"a dict result is json.dumps(value, sort_keys=True); got {text!r}")
    assert text.index('"balance"') < text.index('"name"') < text.index('"vendor_id"'), (
        f"the keys are SORTED, not in the dict's insertion order (vendor_id, "
        f"name, balance): the same call must render to the same bytes every "
        f"run; got {text!r}")
    called_name, called_args, called_session = ran[-1]
    assert (called_name, called_args) == ("read_vendor", {"vendor_id": "v1"}), (
        f"the tool's function is called as fn(arguments, session): the validated "
        f"arguments dict, exactly what the caller sent; got {ran[-1]!r}")
    assert called_session is session, (
        f"the fn's second argument is the SESSION the call belongs to — not "
        f"None and not a copy of it: the session is the only channel a tool has "
        f"to the identity, the steps and the data stages 7-9 keep there; got "
        f"{called_session!r}")
    assert called_session["identity"] == "diego", (
        f"the tool can read who is asking; got identity "
        f"{called_session['identity']!r}")
    assert session["steps"] == ["tools/call:read_vendor"], (
        f"'tools/call:name' is appended for every call that reached a tool; got "
        f"{session['steps']!r}")

    result = shaped(registry.call_tool(
        {"name": "name_of", "arguments": {"vendor_id": "v1"}}, session),
        "a tool returning a str")
    assert result["content"][0]["text"] == "Northwind Fasteners" and \
        result["isError"] is False, (
        f"a str result is the text verbatim — no quotes, no JSON wrapper; got "
        f"{result['content'][0]['text']!r}")

    result = shaped(registry.call_tool({"name": "count_vendors"}, session),
                    "a tool called with no arguments key")
    assert result["content"][0]["text"] == "3" and result["isError"] is False, (
        f"a schema with no required keys accepts a missing arguments object, and "
        f"an int renders as JSON; got {result['content'][0]['text']!r}")

    result = shaped(registry.call_tool({"name": "unrenderable", "arguments": {}},
                                       session),
                    "a tool returning something JSON cannot hold")
    assert result["isError"] is True, (
        "a result that cannot be rendered is a tool execution error, not a "
        "crash and not a protocol error")
    text = result["content"][0]["text"]
    assert "object" in text, (
        f"the failure names the type it got; got {text!r}")
    assert "0x" not in text, (
        f"never str(value)/repr(value): an address makes the same call render "
        f"differently every run; got {text!r}")

    # A tool that returns a COMPLETE result keeps it: the stages above build the
    # text the model has to read, and a result is not a value to render.
    result = shaped(registry.call_tool({"name": "render_table"}, session),
                    "a tool returning a complete result")
    assert result == {"content": [{"type": "text", "text": TABLE}],
                      "isError": False}, (
        f"a returned result comes back verbatim — same text, same isError; got "
        f"{result!r}")
    assert '"type": "text"' not in result["content"][0]["text"], (
        f"the result was re-encoded: the model must read the table, not JSON of "
        f"the envelope it arrived in; got {result['content'][0]['text']!r}")

    result = shaped(registry.call_tool({"name": "render_failure"}, session),
                    "a tool returning its own failure result")
    assert result["isError"] is True and \
        result["content"][0]["text"] == CREDIT_HOLD, (
        f"a returned result keeps its isError True and its words; got {result!r}")

    plain = {"content": ["M8 bolt"], "vendor_id": "v1"}
    result = shaped(registry.call_tool({"name": "content_column"}, session),
                    "a value dict that merely has a content key")
    assert result["isError"] is False and \
        result["content"][0]["text"] == json.dumps(plain, sort_keys=True), (
        f"a dict with a `content` key but no bool isError is the VALUE it is (a "
        f"vendor row with a content column), not a result: it is rendered as "
        f"sorted JSON; got {result['content'][0]['text']!r}")

    not_a_result = {"content": [{"type": "text", "text": "hi"}],
                    "isError": "false"}
    result = shaped(registry.call_tool({"name": "string_flag"}, session),
                    "a value dict whose isError is not a bool")
    assert result["isError"] is False and \
        result["content"][0]["text"] == json.dumps(not_a_result, sort_keys=True), (
        f"an isError that is not a bool is not the field this protocol defines, "
        f"so this is a value, not a result; got {result['content'][0]['text']!r}")

    result = shaped(registry.call_tool(
        {"name": "credit_hold", "arguments": {"vendor_id": "v1"}}, session),
        "a ToolError")
    assert result["isError"] is True, (
        "a tool's own failure is reported INSIDE the result with isError true: "
        "the request was fine, the tool ran, and the model is the only thing "
        "that can act on it")
    assert result["content"][0]["text"] == CREDIT_HOLD, (
        f"the tool's message is the text the model reads, verbatim; got "
        f"{result['content'][0]['text']!r}")

    result = shaped(registry.call_tool({"name": "broken", "arguments": {}}, session),
                    "a tool with a bug")
    assert result["isError"] is True, (
        "a bug inside the tool is still not a protocol error: the client's "
        "request was valid")
    text = result["content"][0]["text"]
    assert text.startswith("ZeroDivisionError"), (
        f"a failure the tool did not choose names its type so the client can "
        f"tell it from the tool's own words; got {text!r}")

    result = shaped(registry.call_tool(
        {"name": "read_vendor", "arguments": {"vendor_id": "v9"}}, session),
        "a business failure from the ERP")
    assert result["isError"] is True, (
        "the world saying no (ErpError: unknown vendor) is a tool execution "
        "error, not a protocol error: the request was well-formed")
    text = result["content"][0]["text"]
    assert "ErpError" in text and "v9" in text, (
        f"the failure names what went wrong and which vendor; got {text!r}")

    assert session["steps"] == [
        "tools/call:read_vendor", "tools/call:name_of",
        "tools/call:count_vendors", "tools/call:unrenderable",
        "tools/call:render_table", "tools/call:render_failure",
        "tools/call:content_column", "tools/call:string_flag",
        "tools/call:credit_hold", "tools/call:broken", "tools/call:read_vendor",
    ], (
        f"session['steps'] records exactly the calls that REACHED a tool, in "
        f"order — none of the refusals above are in it; got {session['steps']!r}")

    # --- the same two methods on a server, through a real Dispatcher ---------
    server = FakeServer()

    def server_tool(name, schema, fn, **kwargs):
        return server.add_tool(name, f"the {name} tool", schema,
                               recorder(name, fn), **kwargs)

    server_tool("vendor_balance", VENDOR_SCHEMA,
                lambda a, session: erp.read(a["vendor_id"])["balance"])

    s.install(server)                      # no registry: the server's own table
    assert set(server.handlers) == {"tools/list", "tools/call"}, (
        f"stage 4 registers exactly the two tool methods — a tool is not a "
        f"method; got {sorted(server.handlers)}")

    dispatcher = Dispatcher()

    def bind(handler):
        return lambda params: handler(params, server.session)

    for method, handler in server.handlers.items():
        dispatcher.add(method, bind(handler))

    response = dispatcher.dispatch(request(1, "tools/list"))
    assert set(response) == {"jsonrpc", "id", "result"}, (
        f"tools/list answers as a result; got {response!r}")
    assert [t["name"] for t in response["result"]["tools"]] == ["vendor_balance"], (
        f"a registry installed without one lists the SERVER's tools; got "
        f"{[t['name'] for t in response['result']['tools']]}")
    assert "nextCursor" not in response["result"], (
        "one tool, one page, so there is no next page and no cursor key")

    # A tool registered AFTER install(), and after a listing that did not have
    # it, is listed by the same tools/list: this is the one entry point every
    # other stage registers into, so the registry must read the table live.
    server_tool("void_order", VENDOR_SCHEMA, lambda a, session: "voided", mutates=True)
    server_tool("credit_hold", VENDOR_SCHEMA, on_credit_hold)
    server_tool("audit_trail", NO_ARGS, lambda a, session: "nothing yet")

    response = dispatcher.dispatch(request(2, "tools/list"))
    page = response["result"]
    assert [t["name"] for t in page["tools"]] == ["vendor_balance", "void_order"], (
        f"a tool registered after install() still appears in tools/list — "
        f"otherwise stage 7's tools do not exist; got "
        f"{[t['name'] for t in page['tools']]}")
    assert page["tools"][0] == {"name": "vendor_balance",
                                "description": "the vendor_balance tool",
                                "inputSchema": VENDOR_SCHEMA}, (
        f"the wire shape is the spec's: name, description, inputSchema; got "
        f"{page['tools'][0]!r}")

    response = dispatcher.dispatch(request(3, "tools/list", {"cursor": "2"}))
    assert [t["name"] for t in response["result"]["tools"]] == ["credit_hold",
                                                                "audit_trail"], (
        f"the last page is the rest of the server's table; got "
        f"{[t['name'] for t in response['result']['tools']]}")
    assert "nextCursor" not in response["result"], (
        "the last page carries no nextCursor key")

    server.set_tool_enabled("void_order", False, reason="read-only mode")
    response = dispatcher.dispatch(request(4, "tools/list"))
    names = [t["name"] for t in response["result"]["tools"]]
    assert "void_order" not in names and names == ["vendor_balance", "credit_hold"], (
        f"a disabled tool is not listed — a read-only mode is exactly "
        f"'everything that mutates is off'; got {names!r}")

    calls_before = len(ran)
    steps_before = list(server.session["steps"])
    response = dispatcher.dispatch(request(5, "tools/call",
                                           {"name": "void_order",
                                            "arguments": {"vendor_id": "v1"}}))
    assert set(response) == {"jsonrpc", "id", "error"}, (
        f"calling a disabled tool is a PROTOCOL error (-32602): the request is "
        f"refused, it is not a tool that ran and failed; got {response!r}")
    assert response["error"]["code"] == ERRORS["invalid_params"], (
        f"a disabled tool is Invalid params, not {response['error']['code']}")
    assert response["error"]["data"] == {"tool": "void_order"}, (
        f"the refusal names the tool; got {response['error']['data']!r}")
    assert "read-only mode" in response["error"]["message"], (
        f"the refusal carries the reason the tool was disabled, which is the "
        f"only thing that tells the caller how to proceed; got "
        f"{response['error']['message']!r}")
    assert len(ran) == calls_before, (
        f"a disabled tool's function is NEVER called; it ran with "
        f"{ran[calls_before:]!r}")
    assert server.session["steps"] == steps_before, (
        f"a refused call leaves session['steps'] untouched; got "
        f"{server.session['steps']!r}")

    # THE case the stage exists for: a well-formed request whose work failed.
    response = dispatcher.dispatch(request(6, "tools/call",
                                           {"name": "credit_hold",
                                            "arguments": {"vendor_id": "v1"}}))
    assert set(response) == {"jsonrpc", "id", "result"}, (
        f"a ToolError comes back as an ORDINARY RESULT, not a JSON-RPC error: "
        f"the request was well-formed and the tool ran, so the message belongs "
        f"where the model can read it; got {response!r}")
    assert "error" not in response, (
        f"a tool execution error is NEVER a protocol error; got {response!r}")
    shaped(response["result"], "a ToolError through the dispatcher")
    assert response["result"]["isError"] is True
    assert response["result"]["content"][0]["text"] == CREDIT_HOLD, (
        f"the text is the tool's message; got "
        f"{response['result']['content'][0]['text']!r}")
    assert server.session["steps"] == steps_before + ["tools/call:credit_hold"], (
        f"the call reached the tool, so it is recorded; got "
        f"{server.session['steps']!r}")

    response = dispatcher.dispatch(request(7, "tools/call", {"name": "nope"}))
    assert set(response) == {"jsonrpc", "id", "error"}, (
        f"an unknown tool is a protocol error at the envelope level too; got "
        f"{response!r}")
    assert response["error"]["code"] == ERRORS["invalid_params"] and \
        response["error"]["data"] == {"tool": "nope"}, (
        f"an unknown tool is -32602 with data.tool; got {response['error']!r}")

    calls_before = len(ran)
    steps_before = list(server.session["steps"])
    response = dispatcher.dispatch(request(8, "tools/call",
                                           {"name": "vendor_balance",
                                            "arguments": {"vendorId": "v1"}}))
    assert set(response) == {"jsonrpc", "id", "error"} and \
        response["error"]["data"] == {"tool": "vendor_balance"}, (
        f"an argument the schema does not declare is -32602 naming the tool; got "
        f"{response!r}")
    assert len(ran) == calls_before and server.session["steps"] == steps_before, (
        f"the tool did not run and was not recorded; ran={ran[calls_before:]!r}, "
        f"steps={server.session['steps']!r}")

    response = dispatcher.dispatch(request(9, "tools/call",
                                           {"name": "vendor_balance",
                                            "arguments": {"vendor_id": "v2"}}))
    shaped(response["result"], "a successful call through the dispatcher")
    assert response["result"]["isError"] is False and \
        response["result"]["content"][0]["text"] == "3400", (
        f"a working tool's result is a result with isError False; got "
        f"{response['result']!r}")
    assert server.session["steps"] == ["tools/call:credit_hold",
                                       "tools/call:vendor_balance"], (
        f"both methods recorded only the calls that reached a tool; got "
        f"{server.session['steps']!r}")
    assert server.notifications == [], (
        f"stage 4 sends no notifications; got {server.notifications!r}")

    # --- install() with a registry of your own ------------------------------
    other = FakeServer()
    mine = s.ToolRegistry(page=1)
    mine.add(s.Tool("ping", "say pong", NO_ARGS,
                    recorder("ping", lambda a, session: "pong")))
    other.add_tool("unused", "a tool on the server's own table", NO_ARGS,
                   recorder("unused", lambda a, session: "unused"))
    s.install(other, mine)

    listed = other.handlers["tools/list"]({}, other.session)
    assert [t["name"] for t in listed["tools"]] == ["ping"], (
        f"an explicit registry is what gets served — INSTEAD of the server's "
        f"table, not on top of it; got {[t['name'] for t in listed['tools']]}")
    result = other.handlers["tools/call"]({"name": "ping"}, other.session)
    shaped(result, "a call through an explicit registry")
    assert result["content"][0]["text"] == "pong" and result["isError"] is False, (
        f"the registered handlers are handler(params, session) and return the "
        f"registry's result; got {result!r}")
    assert ran[-1] == ("ping", {}, other.session), (
        f"the tool is handed the session the CALL came with, not the registry's; "
        f"got {ran[-1]!r}")
    assert other.session["steps"] == ["tools/call:ping"], (
        f"the session handed to the handler is the one that is recorded; got "
        f"{other.session['steps']!r}")


# --- from checks/check_05.py
def check_5():
    def _load(name):
        """The course's copy of `name`, whichever layout put it on the path."""
        try:
            return importlib.import_module(name)
        except ModuleNotFoundError:
            for entry in list(sys.path):
                for candidate in (os.path.join(entry, "mcp-from-scratch"), entry):
                    if os.path.isfile(os.path.join(candidate, name + ".py")):
                        sys.path.insert(0, candidate)
                        return importlib.import_module(name)
            raise

    stage_01 = _load("stage_01")
    s = _load("stage_05")

    class FakeServer:
        """The stage-3 subset a stage registers into (stage 5 uses add/notify)."""

        def __init__(self):
            self.handlers = {}
            self.notifications = []
            self.tools = {}
            self.session = {"identity": None, "steps": [], "data": {}}

        def add(self, method, handler):
            self.handlers[method] = handler
            return handler

        def notify(self, method, params=None):
            message = {"jsonrpc": "2.0", "method": method}
            if params is not None:
                message["params"] = params
            self.notifications.append(message)
            return message

        def add_tool(self, name, description, input_schema, fn, *, mutates=False,
                     enabled=True):
            definition = {"name": name, "description": description,
                          "inputSchema": input_schema, "fn": fn,
                          "mutates": mutates, "enabled": enabled}
            self.tools[name] = definition
            return definition

        def set_tool_enabled(self, name, enabled, *, reason=None):
            definition = self.tools[name]
            definition["enabled"] = enabled
            definition["reason"] = reason
            return definition

    def wire(resources, prompts):
        """install() into the fake server, then hand the same handlers to a real
        Dispatcher: a ProtocolError only becomes a code on the wire because
        stage 1's envelope says so, and that is the path worth exercising."""
        server = FakeServer()
        assert s.install(server, resources, prompts) is None, (
            "install() registers the four methods and returns None")
        assert set(server.handlers) == {"resources/list", "resources/read",
                                        "prompts/list", "prompts/get"}, (
            f"install() registers exactly the four methods, got "
            f"{sorted(server.handlers)}")
        assert server.notifications == [], (
            "install() registers methods; it does not notify anybody")
        dispatcher = stage_01.Dispatcher()
        for method, handler in server.handlers.items():
            dispatcher.add(method,
                           (lambda h: lambda params: h(params, server.session))(handler))
        return server, dispatcher

    def call(dispatcher, method, params=None):
        return dispatcher.dispatch(stage_01.request(1, method, params))

    def result_of(dispatcher, method, params=None):
        response = call(dispatcher, method, params)
        assert "result" in response, (
            f"{method} {params!r} should have answered, got "
            f"{response.get('error')}")
        return response["result"]

    def error_of(dispatcher, method, params=None):
        response = call(dispatcher, method, params)
        assert "error" in response, (
            f"{method} {params!r} should have failed, got "
            f"{response.get('result')!r}")
        return response["error"]

    def walk(dispatcher, method):
        """Follow nextCursor to the end, exactly as a client would."""
        pages = []
        cursor = None
        while True:
            params = {} if cursor is None else {"cursor": cursor}
            page = result_of(dispatcher, method, params)
            pages.append(page)
            if "nextCursor" not in page:
                return pages
            assert len(pages) <= 8, (
                f"{method} never reached a last page: the last page must leave "
                f"'nextCursor' OFF entirely — a 'nextCursor' of None reads as "
                f"'there is more, I am not telling you where' and sends a paging "
                f"loop back to page one. Last page: {pages[-1]!r}")
            cursor = page["nextCursor"]

    # --- resources/read: an address the server owns -------------------------
    loaded = []

    def loader(uri, text):
        def load():
            loaded.append(uri)
            return text
        return load

    resources = s.ResourceRegistry()
    resources.add(s.Resource("erp://vendors/V-1", "vendor 1",
                             loader("V-1", "V-1 balance 10.00")))
    resources.add(s.Resource("erp://items/I-9", "item 9", loader("I-9", '{"item": "I-9"}'),
                             mime_type="application/json"))
    server, dispatcher = wire(resources, s.PromptRegistry())

    error = error_of(dispatcher, "resources/read", {"uri": "erp://vendors/V-404"})
    assert error["code"] == -32002, (
        f"resources/read of an unregistered URI is -32002 resource not found, got "
        f"{error['code']}: the URI is an address the server owns, and the spec "
        f"gives exactly this failure its own code. A client that keys on -32602 "
        f"tells the user their request was malformed about a resource that simply "
        f"is not there")
    assert error.get("data") == {"uri": "erp://vendors/V-404"}, (
        f"the resource_not_found error carries the uri it could not find, got "
        f"{error.get('data')!r}")
    assert loaded == [], (
        f"a URI nobody registered reached a loader ({loaded!r}): the registry must "
        f"look the name up BEFORE it loads anything, or the whitelist is decoration "
        f"and a typo becomes a read of a path nobody asked for")

    assert result_of(dispatcher, "resources/read", {"uri": "erp://vendors/V-1"}) == {
        "contents": [{"uri": "erp://vendors/V-1", "mimeType": "text/plain",
                      "text": "V-1 balance 10.00"}]}, (
        "resources/read answers the spec's shape exactly: one 'contents' LIST of "
        "{'uri', 'mimeType', 'text'}, with the uri and mimeType echoed from the "
        "registration")
    assert result_of(dispatcher, "resources/read", {"uri": "erp://items/I-9"}) == {
        "contents": [{"uri": "erp://items/I-9", "mimeType": "application/json",
                      "text": '{"item": "I-9"}'}]}, (
        "a resource's own mimeType is echoed, not a text/plain default")
    assert loaded == ["V-1", "I-9"], (
        f"only the registered URI's own loader runs, once per read: {loaded!r}")

    # --- paging: two entries a page, and no cursor on the last one ----------
    order = ["erp://things/T-3", "erp://things/T-1", "erp://things/T-5",
             "erp://things/T-2", "erp://things/T-4"]
    listed = s.ResourceRegistry()
    for uri in order:
        listed.add(s.Resource(uri, "thing " + uri[-1], lambda u=uri: "text of " + u))
    server, dispatcher = wire(listed, s.PromptRegistry())

    pages = walk(dispatcher, "resources/list")
    assert [len(p["resources"]) for p in pages] == [2, 2, 1], (
        f"with PAGE == 2 a five-entry registry pages 2/2/1, got "
        f"{[len(p['resources']) for p in pages]}")
    assert "nextCursor" not in pages[-1], (
        f"the last page carries no 'nextCursor' KEY at all — not null and not an "
        f"empty string: got {pages[-1]!r}")
    for page in pages[:-1]:
        assert isinstance(page["nextCursor"], str) and page["nextCursor"], (
            f"every page but the last carries a non-empty string nextCursor: "
            f"{page!r}")
    seen = [r["uri"] for page in pages for r in page["resources"]]
    assert seen == order, (
        f"listing order is REGISTRATION order and the same list every time — not "
        f"sorted, not hash order: registered {order}, listed {seen}")
    for page in pages:
        for resource in page["resources"]:
            assert set(resource) == {"uri", "name", "mimeType"}, (
                f"a listed resource is exactly uri/name/mimeType, got "
                f"{sorted(resource)}")
    assert walk(dispatcher, "resources/list") == pages, (
        "two walks over an unchanged registry must hand back identical pages: a "
        "listing that reorders itself makes the cursor meaningless")

    # --- a cursor this registry never minted is refused, not rounded --------
    for bad in (9, "nope", len(order), str(len(order))):
        error = error_of(dispatcher, "resources/list", {"cursor": bad})
        assert error["code"] == -32602, (
            f"the cursor {bad!r} is not a position in a five-entry list and must be "
            f"-32602 invalid params, got {error['code']}: a bad parameter is not a "
            f"missing resource, and a cursor past the end must be refused rather "
            f"than answered with an empty page")
        assert error.get("data") == {"cursor": bad}, (
            f"the -32602 names the cursor it refused in data, got "
            f"{error.get('data')!r}")

    # --- prompts/get: a name the caller passed to a method ------------------
    seen = []

    def build_review(values):
        seen.append(dict(values))
        return [{"role": "user",
                 "content": {"type": "text", "text": "review " + values["topic"]}},
                {"role": "assistant",
                 "content": {"type": "text", "text": "will do"}}]

    prompts = s.PromptRegistry()
    prompts.add(s.Prompt("review", "review a thing",
                         [{"name": "topic", "description": "what to review",
                           "required": True},
                          {"name": "tone", "description": "how to say it"}],
                         build_review))
    server, dispatcher = wire(s.ResourceRegistry(), prompts)

    assert result_of(dispatcher, "prompts/get",
                     {"name": "review", "arguments": {"topic": "invoices"}}) == {
        "description": "review a thing",
        "messages": [{"role": "user",
                      "content": {"type": "text", "text": "review invoices"}},
                     {"role": "assistant",
                      "content": {"type": "text", "text": "will do"}}]}, (
        f"prompts/get carries the declared description and the rendered messages, "
        f"each one exactly {{'role', 'content'}} with content.type == 'text'")
    assert seen == [{"topic": "invoices"}], (
        f"an OPTIONAL argument that is absent is passed as ABSENT so the builder "
        f"keeps its own default; the builder saw {seen!r}")

    error = error_of(dispatcher, "prompts/get", {"name": "review", "arguments": {}})
    assert error["code"] == -32602, (
        f"a missing REQUIRED argument is -32602 invalid params, got {error['code']}")
    assert "topic" in error["message"], (
        f"the error names the missing required argument, got {error['message']!r}")

    error = error_of(dispatcher, "prompts/get",
                     {"name": "review", "arguments": {"topic": "x", "volumn": "loud"}})
    assert error["code"] == -32602, (
        f"an argument the prompt never declared is -32602, got {error['code']}")
    assert "volumn" in error["message"], (
        f"the error names the argument nobody declared, got {error['message']!r}")

    error = error_of(dispatcher, "prompts/get", {"name": "summarise"})
    assert error["code"] == -32602, (
        f"an unknown PROMPT name is -32602 invalid params, got {error['code']}: a "
        f"prompt name is a parameter of prompts/get, not an address the server owns "
        f"(-32002 is for resources/read, and a client that hears -32002 here goes "
        f"hunting for a resource that never existed)")
    assert error.get("data") == {"name": "summarise"}, (
        f"the invalid-params error names the prompt in data, got "
        f"{error.get('data')!r}")

    # --- the builder's mistakes belong to the SERVER, and only stage 1's
    #     envelope turns them into a code: assert on the response ------------
    prompts.add(s.Prompt("broken", "renders a role the spec does not have", [],
                         lambda values: [{"role": "tool",
                                          "content": {"type": "text", "text": "x"}}]))
    error = error_of(dispatcher, "prompts/get", {"name": "broken"})
    assert error["code"] == -32603, (
        f"a builder rendering an impossible message is the server's bug, so the "
        f"envelope answers -32603, got {error['code']}: it is never -32602 and "
        f"never a code this stage invents")
    assert "tool" in error["message"], (
        f"the -32603 message names the offending role, got {error['message']!r}")
    assert "ValueError" in error["message"], (
        f"the -32603 message names the exception TYPE so the server's own logs can "
        f"be grepped for it, got {error['message']!r}")

    # --- a loader that raises, and a loader that returns the wrong type -----
    def explode():
        raise OSError("the shelf fell over")

    resources = s.ResourceRegistry()
    resources.add(s.Resource("erp://boom", "boom", explode))
    resources.add(s.Resource("erp://bytes", "bytes", lambda: b"raw"))
    server, dispatcher = wire(resources, s.PromptRegistry())

    error = error_of(dispatcher, "resources/read", {"uri": "erp://boom"})
    assert error["code"] == -32603, (
        f"a loader that raises is the server breaking, so -32603, got "
        f"{error['code']}: the client asked for a resource the server itself "
        f"declared, so it is not an invalid parameter")
    assert "OSError" in error["message"], (
        f"-32603's message names the exception type, got {error['message']!r}")
    assert "Traceback" not in error["message"], (
        f"the envelope reports a type and a message, never a traceback: "
        f"{error['message']!r}")

    error = error_of(dispatcher, "resources/read", {"uri": "erp://bytes"})
    assert error["code"] == -32603, (
        f"a loader returning bytes where the spec says text is the server's bug, "
        f"so -32603, got {error['code']}: do not mint a new code for it")
    assert "TypeError" in error["message"], (
        f"the non-string return surfaces as TypeError for the envelope to name, "
        f"got {error['message']!r}")

    # --- prompts/list: the same page discipline, registration order ---------
    other = s.PromptRegistry()
    other.add(s.Prompt("zeta", "zeta prompt", [], lambda values: []))
    other.add(s.Prompt("alpha", "alpha prompt", [{"name": "who", "required": True}],
                       lambda values: []))
    other.add(s.Prompt("mu", "mu prompt", [], lambda values: []))
    server, dispatcher = wire(s.ResourceRegistry(), other)

    pages = walk(dispatcher, "prompts/list")
    prompt_list = [p for page in pages for p in page["prompts"]]
    assert [p["name"] for p in prompt_list] == ["zeta", "alpha", "mu"], (
        f"prompts/list hands them back in registration order, not sorted: "
        f"{[p['name'] for p in prompt_list]}")
    assert [len(p["prompts"]) for p in pages] == [2, 1], (
        f"prompts page like resources do: {[len(p['prompts']) for p in pages]}")
    assert "nextCursor" not in pages[-1], (
        "the last page of prompts carries no nextCursor key either")
    assert prompt_list[0] == {"name": "zeta", "description": "zeta prompt",
                              "arguments": []}, (
        f"a listed prompt is exactly name/description/arguments, got "
        f"{sorted(prompt_list[0])}")
    assert prompt_list[1]["arguments"] == [{"name": "who", "required": True}], (
        f"the declaration rides along verbatim, including which argument is "
        f"required: {prompt_list[1]['arguments']!r}")
    prompt_list[1]["arguments"][0]["required"] = False
    assert other.prompts["alpha"].arguments == [{"name": "who", "required": True}], (
        "a listing hands out a copy of the declaration: a client editing the "
        "arguments it got back must not rewrite the server's prompt")


# --- from checks/check_06.py
def check_6():
    from stage_01 import Dispatcher, ERRORS, ProtocolError, notification, result
    from stage_06 import Cancellations, Progress, Subscriptions, install

    class FakeServer:
        """The stage 3 subset: register a method, record a notification, carry a
        session. Nothing else is needed to install and drive this stage."""

        def __init__(self):
            self.handlers = {}
            self.notifications = []
            self.session = {"identity": None, "steps": [], "data": {}}

        def add(self, method, handler):
            self.handlers[method] = handler
            return handler

        def notify(self, method, params=None):
            self.notifications.append(notification(method, params))

    def _assert(condition, message):
        if not condition:
            raise AssertionError(message)

    def _raises(exc_type, fn, *args, **kwargs):
        try:
            fn(*args, **kwargs)
        except exc_type as exc:
            return exc
        except Exception as exc:  # noqa: BLE001 - a wrong type is still a catch
            raise AssertionError(f"expected {exc_type.__name__}, got "
                                 f"{type(exc).__name__}: {exc}") from None
        raise AssertionError(f"expected {exc_type.__name__}, nothing was raised")

    session = {"identity": None, "steps": [], "data": {}}

    # --------------------------------------- a cancelled request gets NO response
    # The whole point of the stage. answer_for is the rule in one place.
    cancellations = Cancellations()
    cancellations.protected.add("init-1")
    cancellations.in_flight.add("req-7")
    outcome = cancellations.cancel({"requestId": "req-7",
                                    "reason": "the user pressed stop"}, session)
    _assert(outcome is None,
            f"cancel() has nobody to answer to, so it returns None; got "
            f"{outcome!r}. It is a notification handler: a return value is a "
            f"response to a message that has no id")
    _assert(cancellations.cancelled == {"req-7"},
            f"a cancellation for a request that is in flight marks that id: "
            f".cancelled must be {{'req-7'}}, got {cancellations.cancelled!r}. "
            f"Reading params['id'] instead of params['requestId'] finds nothing, "
            f"so nothing is ever cancelled")
    _assert(cancellations.is_cancelled("req-7") is True,
            "is_cancelled() must answer for the id that was cancelled")
    _assert(cancellations.is_cancelled("req-8") is False,
            f"is_cancelled('req-8') is False: a request nobody cancelled is not "
            f"cancelled, got {cancellations.is_cancelled('req-8')!r}")
    _assert(cancellations.ignored == [],
            f"a cancellation that lands is not an ignored one; .ignored holds "
            f"the cancellations that could not land, got "
            f"{cancellations.ignored!r}")

    response = result("req-7", {"content": [{"type": "text", "text": "done"}]})
    answer = cancellations.answer_for("req-7", response)
    _assert(answer is None,
            f"a cancelled request gets NO response (spec: \"Not send a response "
            f"for the cancelled request\"), but answer_for('req-7', ...) returned "
            f"{answer!r}. Any code — -32800 included — is an answer the client "
            f"cannot match to a request it already gave up on")
    error_response = {"jsonrpc": "2.0", "id": "req-7",
                      "error": {"code": -32800, "message": "Request cancelled"}}
    _assert(cancellations.answer_for("req-7", error_response) is None,
            f"a cancelled request gets no response of ANY kind, error responses "
            f"included: answer_for returned {error_response!r} instead of None. "
            f"Answering is exactly what the spec says not to do")
    untouched = result("req-8", "ok")
    _assert(cancellations.answer_for("req-8", untouched) == untouched,
            f"answer_for must hand back the response it was given for a request "
            f"that was not cancelled, got "
            f"{cancellations.answer_for('req-8', untouched)!r} instead of "
            f"{untouched!r}")

    # --------------------------------------- a cancellation nobody is waiting for
    ghost = Cancellations()
    _assert(ghost.cancel({"requestId": "req-ghost", "reason": "client gave up"},
                         session) is None,
            "cancelling a request that was never in flight raises nothing: a "
            "notification cannot be answered with an error")
    _assert(ghost.cancelled == set(),
            f"an id that was never in flight must not be marked cancelled, got "
            f"{ghost.cancelled!r}: the server is not working on it, so there is "
            f"nothing to stop")
    _assert(len(ghost.ignored) == 1
            and ghost.ignored[0]["requestId"] == "req-ghost",
            f"the ignored cancellation is recorded as "
            f"[{{'requestId': 'req-ghost', 'reason': ...}}], got "
            f"{ghost.ignored!r}")
    ghost_reason = ghost.ignored[0]["reason"]
    _assert(isinstance(ghost_reason, str) and any(
        word in ghost_reason.lower() for word in ("flight", "answered", "unknown")),
            f"the .ignored record carries a reason that says why the cancellation "
            f"could not land — that the request is not in flight — got "
            f"{ghost_reason!r}")

    # The interesting race: the work finished first, so the cancellation that
    # arrives afterwards is a no-op (the spec allows exactly this).
    late = Cancellations()
    late.in_flight.add("req-3")
    late.answer_for("req-3", result("req-3", "answered"))
    late.cancel({"requestId": "req-3", "reason": "too late"}, session)
    _assert(late.cancelled == set() and len(late.ignored) == 1,
            f"a cancellation that arrives after the request was answered is "
            f"ignored — the request is no longer in flight — got "
            f".cancelled={late.cancelled!r} .ignored={late.ignored!r}. "
            f".in_flight is what makes 'already answered' checkable")

    twice = Cancellations()
    twice.in_flight.add("req-5")
    twice.cancel({"requestId": "req-5"}, session)
    twice.cancel({"requestId": "req-5"}, session)
    _assert(twice.cancelled == {"req-5"},
            f"cancelling twice is still one cancellation, got "
            f"{twice.cancelled!r}")
    _assert(len(twice.ignored) == 1 and isinstance(twice.ignored[0]["reason"], str)
            and "cancel" in twice.ignored[0]["reason"].lower(),
            f"the second cancellation is ignored with a reason that says the "
            f"request was already cancelled, got {twice.ignored!r}")

    bad_id = Cancellations()
    bad_id.cancel({"requestId": True}, session)
    _assert(bad_id.cancelled == set() and len(bad_id.ignored) == 1,
            f"a boolean is not a request id (isinstance(True, int) is True): the "
            f"notification is ignored, got .cancelled={bad_id.cancelled!r} "
            f".ignored={bad_id.ignored!r}")

    # --------------------------------------- initialize is never cancellable
    handshake = Cancellations()
    handshake.protected.add("init-1")
    handshake.in_flight.add("init-1")
    _assert(handshake.cancel({"requestId": "init-1",
                              "reason": "impatient client"}, session) is None,
            "a protected id is ignored, never raised about: the sender is a "
            "notification with no id to answer")
    _assert(handshake.cancelled == set(),
            f"a protected request is never cancelled: .protected holds the ids "
            f"that MUST NOT be cancelled — the spec says a client MUST NOT "
            f"cancel its initialize request — got {handshake.cancelled!r}")
    _assert(len(handshake.ignored) == 1
            and handshake.ignored[0]["requestId"] == "init-1",
            f"the protected cancellation is recorded as an ignored one, got "
            f"{handshake.ignored!r}")
    reason = handshake.ignored[0]["reason"]
    _assert(isinstance(reason, str) and any(
        word in reason.lower() for word in ("protected", "initialize")),
            f"the reason for ignoring a protected id says why — that the request "
            f"is protected, or that initialize must never be cancelled — got "
            f"{reason!r}")
    _assert(handshake.is_cancelled("init-1") is False,
            "is_cancelled() must stay False for a protected id")
    kept = handshake.answer_for("init-1", result("init-1",
                                                 {"protocolVersion": "2025-06-18"}))
    _assert(kept is not None and "result" in kept,
            f"a protected request still gets its response: the handshake is the "
            f"one thing a cancelled session cannot recover, got {kept!r}")

    # --------------------------------------- through a real Dispatcher
    server = FakeServer()
    cancellations = Cancellations()
    install(server, cancellations=cancellations)
    handler = server.handlers.get("notifications/cancelled")
    _assert(handler is not None,
            f"install(server, cancellations=...) must register "
            f"notifications/cancelled, got handlers "
            f"{sorted(server.handlers)}")
    cancellations.in_flight.add("req-42")

    def drive(params):
        # stage 1's Dispatcher calls handler(params); a server calls
        # handler(params, session). The installed handler is the second one.
        return handler(params, server.session)

    dispatcher = Dispatcher()
    dispatcher.add("notifications/cancelled", drive)
    wire = dispatcher.dispatch(notification("notifications/cancelled",
                                            {"requestId": "req-42",
                                             "reason": "stop"}))
    _assert(wire is None,
            f"driving notifications/cancelled through a real Dispatcher must put "
            f"NOTHING on the wire (a notification has no id to answer), got "
            f"{wire!r}")
    _assert(cancellations.is_cancelled("req-42") is True,
            f"the installed handler is the registry's cancel(): after the "
            f"notification the id is cancelled, got "
            f"{cancellations.cancelled!r}")
    dispatcher.dispatch(notification("notifications/cancelled",
                                     {"requestId": "req-404"}))
    _assert(cancellations.cancelled == {"req-42"},
            f"a second notification for an id that is not in flight changes "
            f"nothing, got {cancellations.cancelled!r}")

    # --------------------------------------- subscriptions
    server = FakeServer()
    known = {"erp://vendors/v-1", "erp://orders/o-1"}
    subscriptions = Subscriptions(server.notify, known=lambda uri: uri in known)
    _assert(len(subscriptions.subscribed) == 0,
            f"nothing is subscribed before a resource is: got "
            f"{subscriptions.subscribed!r}")
    _assert(subscriptions.subscribe({"uri": "erp://vendors/v-1"},
                                    server.session) == {},
            "resources/subscribe answers with an empty result object")
    _assert("erp://vendors/v-1" in subscriptions.subscribed,
            f"subscribe() records the uri in .subscribed, got "
            f"{subscriptions.subscribed!r}")
    subscriptions.subscribe({"uri": "erp://vendors/v-1"}, server.session)

    count = subscriptions.updated("erp://vendors/v-1")
    _assert(len(server.notifications) == 1,
            f"subscribing twice then updating sends exactly ONE "
            f"notifications/resources/updated, got "
            f"{len(server.notifications)}: a second subscription that appends "
            f"instead of being absorbed by the set doubles every later "
            f"notification")
    _assert(count == 1,
            f"updated() returns how many notifications it sent: one subscribed "
            f"uri is 1, got {count!r}")
    _assert(server.notifications[0]["method"] == "notifications/resources/updated"
            and server.notifications[0]["params"] == {"uri": "erp://vendors/v-1"},
            f"the notification is "
            f"notifications/resources/updated with params {{'uri': ...}}, got "
            f"{server.notifications[0]!r}")

    before = set(subscriptions.subscribed)
    exc = _raises(ProtocolError, subscriptions.subscribe, {"uri": "erp://vendors/nope"},
                  server.session)
    _assert(exc.code == ERRORS["resource_not_found"] == -32002,
            f"an unknown uri is -32002 (Resource not found), got code "
            f"{exc.code!r}: a subscribe that silently succeeds makes the "
            f"connection wait for updates that will never come")
    _assert(exc.data == {"uri": "erp://vendors/nope"},
            f"the error carries data={{'uri': ...}}, the same shape "
            f"resources/read uses, got {exc.data!r}")
    _assert(subscriptions.subscribed == before,
            f"a uri the server cannot serve must NOT end up subscribed, got "
            f"{subscriptions.subscribed!r}")

    _assert(subscriptions.updated("erp://orders/o-1") == 0,
            "updated() for a uri nobody subscribed to sends nothing and returns 0")
    _assert(len(server.notifications) == 1,
            f"an unsubscribed uri produces no notification, got "
            f"{len(server.notifications)} messages")

    _assert(subscriptions.unsubscribe({"uri": "erp://vendors/v-1"},
                                      server.session) == {},
            "resources/unsubscribe answers with an empty result object")
    _assert(subscriptions.subscribed == set(),
            f"unsubscribe() removes the uri, got {subscriptions.subscribed!r}")
    _assert(subscriptions.unsubscribe({"uri": "erp://vendors/v-1"},
                                      server.session) == {},
            "unsubscribing something that is not subscribed is a no-op "
            "returning {} — the client is allowed to be confused")
    _assert(subscriptions.updated("erp://vendors/v-1") == 0
            and len(server.notifications) == 1,
            f"after unsubscribe the uri no longer produces notifications, got "
            f"{len(server.notifications)} messages")

    permissive = Subscriptions(server.notify).subscribe({"uri": "any://thing"},
                                                        server.session)
    _assert(permissive == {},
            f"with no known() oracle the registry has nothing to test a uri "
            f"against and accepts it, got {permissive!r}")

    # --------------------------------------- progress: who asked, and how far
    server = FakeServer()
    progress = Progress(server.notify)
    _assert(progress.track({"name": "slow",
                            "_meta": {"progressToken": 7}}) == 7,
            "track() returns params['_meta']['progressToken'] — the request's "
            "own token — got something else")
    _assert(progress.track({}) is None,
            "without _meta the request did not ask for progress: track() "
            "returns None, never an invented token")
    _assert(progress.track({"_meta": {}}) is None,
            "an _meta without a progressToken is the same as no token at all")
    _assert(progress.track({"_meta": {"progressToken": "abc"}}) == "abc",
            "MCP's ProgressToken is string | integer: a string token is a token")
    _assert(progress.track({"_meta": {"progressToken": True}}) is None,
            "a boolean is not a progress token: isinstance(True, int) is True, "
            "so a token check without a bool guard accepts True and then sends "
            "progress for a token the client never sent")
    _assert(progress.track({"_meta": {"progressToken": 1.5}}) is None,
            "MCP's ProgressToken is string | integer: 1.5 is neither")
    _assert(progress.track({"_meta": {"progressToken": None}}) is None,
            "a null progressToken is not a token")

    message = progress.report(7, 1)
    _assert(message["method"] == "notifications/progress",
            f"report() sends notifications/progress, got {message['method']!r}")
    _assert(message.get("jsonrpc") == "2.0" and "id" not in message,
            f"a progress notification is an MCP message: jsonrpc 2.0 and no id "
            f"member, got {message!r}")
    _assert("total" not in message["params"],
            f"report() includes `total` only when it was given, got "
            f"{message['params']!r}: `total: None` is a total the client draws "
            f"an axis for, and it is not the same message")
    _assert(message["params"] == {"progressToken": 7, "progress": 1},
            f"the params carry progressToken and progress and nothing else when "
            f"nothing else was given, got {message['params']!r}")

    message = progress.report(7, 2, total=10, message="halfway")
    _assert(message["params"] == {"progressToken": 7, "progress": 2,
                                  "total": 10, "message": "halfway"},
            f"`total` and `message` are included when given, got "
            f"{message['params']!r}")
    _assert(progress.sent == [notification("notifications/progress",
                                           {"progressToken": 7, "progress": 1}),
                              message],
            f".sent records every notification the registry sent, got "
            f"{progress.sent!r}")
    _assert(server.notifications == progress.sent,
            f"report() must SEND the notification it returns (server.notify "
            f"here), got {server.notifications!r} against .sent="
            f"{progress.sent!r}")

    exc = _raises(ValueError, progress.report, 7, 1)
    text = str(exc)
    _assert("2" in text and "1" in text,
            f"a progress value that is not greater than the last one for that "
            f"token raises ValueError naming both values (2 then 1), got "
            f"{text!r}: a non-monotone progress bar is a bug in the server, not "
            f"a message to send")
    _raises(ValueError, progress.report, 7, 2)
    _assert(len(progress.sent) == 2 and len(server.notifications) == 2,
            f"a rejected report sends nothing: it must validate before it "
            f"notifies and before it records, got .sent={len(progress.sent)} "
            f"notifications={len(server.notifications)}")

    message = progress.report(8, 1)
    _assert(message["params"]["progressToken"] == 8
            and message["params"]["progress"] == 1,
            f"a different token starts clean, at 1, got {message['params']!r}")
    _assert(progress.report(8, 2, total=5)["params"]["total"] == 5,
            "a different token may carry a different total")
    exc = _raises(ValueError, progress.report, 8, 3, total=6)
    text = str(exc)
    _assert("5" in text and "6" in text,
            f"`total` must not change for a token once it has been sent — the "
            f"client drew the axis already — and the ValueError names both "
            f"values (5 then 6), got {text!r}")
    _assert("total" not in progress.report(8, 4)["params"],
            "omitting `total` later is not a change of total: it stays optional")

    # --------------------------------------- install
    bare = FakeServer()
    install(bare)
    _assert(set(bare.handlers) == {"notifications/cancelled"},
            f"install(server) registers notifications/cancelled and, with no "
            f"Subscriptions registry, nothing else (subscribe/unsubscribe need a "
            f"registry to point at), got {sorted(bare.handlers)}")
    _assert(bare.handlers["notifications/cancelled"]({"requestId": "nobody"},
                                                     bare.session) is None,
            "the default cancellation handler drops a request that is not in "
            "flight instead of raising")

    full = FakeServer()
    subscriptions = Subscriptions(full.notify, known=lambda uri: uri in known)
    progress = Progress(full.notify)
    cancellations = Cancellations()
    install(full, subscriptions=subscriptions, progress=progress,
            cancellations=cancellations)
    _assert(set(full.handlers) == {"notifications/cancelled",
                                   "resources/subscribe",
                                   "resources/unsubscribe"},
            f"install registers notifications/cancelled, resources/subscribe and "
            f"resources/unsubscribe, got {sorted(full.handlers)}")
    _assert(full.handlers["resources/subscribe"]({"uri": "erp://orders/o-1"},
                                                 full.session) == {},
            "the installed resources/subscribe handler is the registry's own "
            "subscribe()")
    _assert(subscriptions.subscribed == {"erp://orders/o-1"},
            f"the installed handler reaches the registry, got "
            f"{subscriptions.subscribed!r}")
    _assert(full.session["data"].get("progress") is progress,
            f"install hangs the outbound progress registry on the session "
            f"(session['data']['progress']), where the handlers that report "
            f"progress can find it, got {full.session['data']!r}")
    _assert(full.session["data"].get("cancellations") is cancellations
            and full.session["data"].get("subscriptions") is subscriptions,
            f"the registries install was given are reachable from the session, "
            f"got {full.session['data']!r}")


# --- from checks/check_07.py
def check_7():
    REPO = os.environ.get("COURSE_REPO", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    COURSE = os.path.join(REPO, "mcp-from-scratch")

    def build():
        """A temp dir holding the course as the runner assembles it: `*.py` copied and
        `solutions/*.py` overlaid flat, then that dir (and the repo root) on sys.path."""
        work = tempfile.mkdtemp(prefix="d1-check07-")
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

    def _protocol_error(fn, where, data=None, message_parts=()):
        """Fail unless fn() raises the -32602 the protocol uses for a bad call."""
        try:
            fn()
        except stage_01.ProtocolError as exc:
            if exc.code != stage_01.ERRORS["invalid_params"]:
                _fail("%s: expected -32602, got %d (%s)" % (where, exc.code, exc.message))
            for key, value in (data or {}).items():
                if (exc.data or {}).get(key) != value:
                    _fail("%s: the error must name %s=%r in data, got %r"
                          % (where, key, value, exc.data))
            for part in message_parts:
                if part not in (exc.message or ""):
                    _fail("%s: the message must mention %r, got %r"
                          % (where, part, exc.message))
            return exc
        except AssertionError:
            raise
        except Exception as exc:
            _fail("%s: expected ProtocolError, got %s: %s"
                  % (where, type(exc).__name__, exc))
        _fail("%s: expected ProtocolError, but the call went through" % where)

    def _names(payload):
        return [tool["name"] for tool in payload["tools"]]

    def _ok(text):
        return {"content": [{"type": "text", "text": text}], "isError": False}

    def _rows(text):
        """The rendered table's data rows, as token lists (the header is line 0)."""
        return [line.split() for line in text.splitlines()[1:]]

    def _rpc(server, method, params=None, id=1):
        """One request through a real Server, the whole response back."""
        response = server.dispatch({"jsonrpc": "2.0", "id": id, "method": method,
                                    "params": {} if params is None else params})
        if response is None:
            _fail("the server sent no response to %r" % method)
        return response

    def _result(server, method, params=None, id=1):
        response = _rpc(server, method, params, id)
        if "result" not in response:
            _fail("%r answered with an error: %r" % (method, response))
        return response["result"]

    def _all_tools(server):
        """Every listed name, following the registry's nextCursor (it pages)."""
        found, cursor, pages = [], None, 0
        while True:
            page = _result(server, "tools/list",
                           {} if cursor is None else {"cursor": cursor}, id=100 + pages)
            found.extend(tool["name"] for tool in page["tools"])
            cursor = page.get("nextCursor")
            pages += 1
            if cursor is None:
                return found
            if pages > 20:
                _fail("tools/list kept handing out a cursor: %r" % (cursor,))

    import json

    import erp as erp_module
    import stage_01
    import stage_07 as stage

    for name in ("REPORT_SCHEMA", "Toolset", "Reports", "install", "make_tools"):
        if not hasattr(stage, name):
            _fail("stage_07 must define %s" % name)

    # -- the schema is the whole vocabulary, and it is given
    expected = {
        "open_orders": ("orders", ("reference", "vendor_id", "item_id", "quantity", "status")),
        "vendor_balance": ("vendors", ("vendor_id", "name", "balance")),
    }
    if set(stage.REPORT_SCHEMA) != set(expected):
        _fail("REPORT_SCHEMA is the allowlist: expected the reports %r, got %r"
              % (sorted(expected), sorted(stage.REPORT_SCHEMA)))
    for report, (table, columns) in expected.items():
        entry = stage.REPORT_SCHEMA[report]
        if entry["table"] != table or tuple(entry["columns"]) != columns:
            _fail("report %r must read table %r and declare columns %r in that order, got %r / %r"
                  % (report, table, list(columns), entry["table"], list(entry["columns"])))

    class SpyErp(erp_module.Erp):
        """The provided domain plus two things: a record of the request `Reports`
        generated, and rows handed back in an order nobody should rely on."""

        def __init__(self, **kwargs):
            erp_module.Erp.__init__(self, **kwargs)
            self.requests = []

        def report(self, table, where=None, columns=None):
            self.requests.append({"table": table, "where": dict(where or {}),
                                  "columns": list(columns or [])})
            answer = erp_module.Erp.report(self, table, where=where, columns=columns)
            answer["rows"] = list(reversed(answer["rows"]))
            return answer

    class FakeServer:
        """The subset of stage 3's Server this stage touches: a method table, a
        notification sink, a session, the read-only switch, and the tool table
        tools live in. It keeps the server's own rule too: a mutating tool
        registered while the server is read-only arrives disabled."""

        def __init__(self):
            self.handlers = {}
            self.notifications = []
            self.session = {"identity": "user:ana", "steps": [], "data": {}}
            self.read_only = True
            self.tools = {}

        def add(self, method, handler):
            self.handlers[method] = handler
            return handler

        def notify(self, method, params=None):
            self.notifications.append({"jsonrpc": "2.0", "method": method,
                                       "params": {} if params is None else params})

        def add_tool(self, name, description, input_schema, fn, *, mutates=False, enabled=True):
            definition = {"name": name, "description": description,
                          "inputSchema": input_schema, "fn": fn,
                          "mutates": mutates, "enabled": bool(enabled)}
            if mutates and self.read_only:
                definition["enabled"] = False
                definition["reason"] = "this server is read-only"
            self.tools[name] = definition
            return definition

        def set_tool_enabled(self, name, enabled, *, reason=None):
            definition = self.tools[name]
            definition["enabled"] = bool(enabled)
            if reason is not None:
                definition["reason"] = reason
            return definition

        def call(self, method, params):
            return self.handlers[method](params, self.session)

    # A fixture whose ERP order (and whose executor's order) is NOT the sorted one.
    orders = {
        "PO-3": {"reference": "PO-3", "vendor_id": "v1", "item_id": "i2",
                 "quantity": 9, "status": "approved"},
        "PO-1": {"reference": "PO-1", "vendor_id": "v1", "item_id": "i1",
                 "quantity": 5, "status": "draft"},
        "PO-2": {"reference": "PO-2", "vendor_id": "v2", "item_id": "i1",
                 "quantity": 2, "status": "approved"},
    }
    session = {"identity": "user:ana", "steps": [], "data": {}}
    erp = SpyErp(orders=orders)
    calls = []

    # -- read-only first: the default toolset exposes the report tool and nothing else
    toolset = stage.make_tools(erp)
    if toolset.read_only is not True:
        _fail("make_tools must hand back a read-only toolset, got read_only=%r"
              % (toolset.read_only,))
    if toolset.enabled != ["report"]:
        _fail("a read-only toolset must expose exactly the report tool, got %r"
              % (toolset.enabled,))
    if toolset.disabled != []:
        _fail("make_tools registers nothing hidden, got disabled=%r" % (toolset.disabled,))
    report_tool = toolset.list_tools({})["tools"][0]
    for key in ("name", "description", "inputSchema"):
        if key not in report_tool:
            _fail("a listed tool needs %r: %r" % (key, report_tool))
    if report_tool["inputSchema"].get("type") != "object":
        _fail("the report tool's inputSchema must be an object schema: %r"
              % (report_tool["inputSchema"],))
    if "vendor_balance" not in json.dumps(report_tool["inputSchema"]):
        _fail("the tool the model sees must carry its own allowlist, so discovering it "
              "does not cost a turn: %r" % (report_tool["inputSchema"],))

    # -- a mutating tool is not refused when called: it is NOT LISTED
    toolset.add("approve_order", "approve a draft purchase order",
                {"type": "object", "properties": {"reference": {"type": "string"}},
                 "required": ["reference"]},
                lambda args, sess: calls.append(("approve_order", args)) or _ok("approved"),
                mutates=True)
    toolset.add("set_quantity", "change the quantity of a draft order",
                {"type": "object", "properties": {"reference": {"type": "string"},
                                                  "quantity": {"type": "integer"}},
                 "required": ["reference", "quantity"]},
                lambda args, sess: calls.append(("set_quantity", args)) or _ok("changed"),
                mutates=True)
    if toolset.enabled != ["report"] or toolset.disabled != ["approve_order", "set_quantity"]:
        _fail("while read_only a mutating tool is registered but not exposed: enabled=%r "
              "disabled=%r" % (toolset.enabled, toolset.disabled))
    payload = toolset.list_tools({})
    if _names(payload) != ["report"]:
        _fail("tools/list while read-only must be the report tool only: a tool the model can "
              "see is a tool the model will call. got %r" % (_names(payload),))
    if "approve_order" in json.dumps(payload) or "set_quantity" in json.dumps(payload):
        _fail("tools/list must not mention a disabled tool anywhere, not even in a "
              "description: %s" % json.dumps(payload))

    _protocol_error(lambda: toolset.call_tool(
        {"name": "approve_order", "arguments": {"reference": "PO-1"}}, session),
        "calling a disabled tool", data={"tool": "approve_order"},
        message_parts=("approve_order", "read-only"))
    _protocol_error(lambda: toolset.call_tool({"name": "no_such_tool"}, session),
                    "calling an unknown tool", data={"tool": "no_such_tool"})
    if calls:
        _fail("the fn of a disabled tool RAN: %r — a hidden tool is not a tool that failed, "
              "it is one that is not there" % (calls,))

    # -- a capability flip needs a name attached, or nothing moves
    for empty in ("", "   ", None):
        try:
            toolset.enable_writes(approved_by=empty)
        except ValueError:
            pass
        else:
            _fail("enable_writes(approved_by=%r) must raise ValueError: an unattributed flip "
                  "is how a read-only server becomes a write server with nobody to blame"
                  % (empty,))
        if toolset.read_only is not True:
            _fail("a refused flip must not flip anything, got read_only=%r"
                  % (toolset.read_only,))
        if toolset.approvals:
            _fail("a refused flip must not be recorded, got %r" % (toolset.approvals,))

    count = toolset.enable_writes(approved_by="user:ana")
    if count != 2:
        _fail("enable_writes must return how many tools APPEARED (2), got %r" % (count,))
    if toolset.read_only is not False:
        _fail("enable_writes must flip read_only, got %r" % (toolset.read_only,))
    if toolset.enabled != ["report", "approve_order", "set_quantity"] or toolset.disabled != []:
        _fail("after the flip every tool must be exposed, in registration order: enabled=%r "
              "disabled=%r" % (toolset.enabled, toolset.disabled))
    recorded = [(entry["tool"], entry["approved_by"]) for entry in toolset.approvals]
    if recorded != [("approve_order", "user:ana"), ("set_quantity", "user:ana")]:
        _fail("the flip must record the approver against every tool it exposed, got %r"
              % (recorded,))
    payload = toolset.list_tools({})
    if _names(payload) != ["report", "approve_order", "set_quantity"]:
        _fail("the next tools/list must contain what the flip exposed: %r" % (_names(payload),))
    result = toolset.call_tool({"name": "approve_order", "arguments": {"reference": "PO-1"}}, session)
    if calls != [("approve_order", {"reference": "PO-1"})]:
        _fail("after the flip the fn must run, got calls=%r" % (calls,))
    if result != _ok("approved"):
        _fail("a toolset returns what the tool returned, unchanged: %r" % (result,))
    if toolset.enable_writes(approved_by="user:bob") != 0:
        _fail("a second flip exposes nothing and must return 0")
    _protocol_error(lambda: toolset.call_tool({"name": "report", "arguments": []}, session),
                    "arguments that are not an object", data={"tool": "report"})

    # -- the report tool: an allowlist of reports, of filter columns, and of types
    reports = stage.Reports(erp)
    if reports.names != ["open_orders", "vendor_balance"]:
        _fail("Reports.names must be the allowlist in schema order, got %r" % (reports.names,))

    _protocol_error(lambda: reports.run({"report": "orders", "filters": {}}, session),
                    "an unlisted report name", data={"report": "orders"},
                    message_parts=("'orders'",))
    _protocol_error(lambda: reports.run({"report": ["open_orders"]}, session),
                    "a report name that is not even a string", data={"report": ["open_orders"]})
    _protocol_error(lambda: toolset.call_tool(
        {"name": "report", "arguments": {"report": "all_orders"}}, session),
        "an unlisted report through tools/call", data={"report": "all_orders"})

    # a filter that IS allowlisted — for a different report
    _protocol_error(lambda: reports.run(
        {"report": "vendor_balance", "filters": {"status": "approved"}}, session),
        "a filter valid for another report only", data={"filter": "status"},
        message_parts=("'status'",))
    _protocol_error(lambda: reports.run(
        {"report": "open_orders", "filters": {"balance": 0}}, session),
        "a filter key outside the report's allowlist", data={"filter": "balance"},
        message_parts=("'balance'",))

    # declared types
    _protocol_error(lambda: reports.run(
        {"report": "vendor_balance", "filters": {"vendor_id": 7}}, session),
        "a filter value of the wrong declared type", data={"filter": "vendor_id"},
        message_parts=("'vendor_id'", "string"))
    _protocol_error(lambda: reports.run(
        {"report": "open_orders", "filters": {"status": True}}, session),
        "a bool is not a string", data={"filter": "status"},
        message_parts=("'status'", "string"))

    if erp.requests:
        _fail("a refused report reached the executor: %r — the request is built only after "
              "every name and value has been checked" % (erp.requests,))

    # -- the happy path: sorted, allowlisted, deterministic
    columns = list(stage.REPORT_SCHEMA["open_orders"]["columns"])
    result = reports.run({"report": "open_orders"}, session)
    if result.get("isError") is not False or result["content"][0]["type"] != "text":
        _fail("a report is a text result with isError False: %r" % (result,))
    text = result["content"][0]["text"]
    if text.splitlines()[0].split() != columns:
        _fail("the header must be the allowlisted columns in schema order (%r), got %r"
              % (columns, text.splitlines()[0].split()))
    firsts = [row[0] for row in _rows(text)]
    if firsts != ["PO-1", "PO-2", "PO-3"]:
        _fail("rows must be sorted by the report's first column, got %r — the executor makes "
              "no ordering promise, the render does" % (firsts,))
    if len(_rows(text)) != 3:
        _fail("the unfiltered open_orders report must return the three orders, got %r"
              % (_rows(text),))
    if "{" in text or "}" in text:
        _fail("a report is a table, not str(dict): %r" % (text,))
    request = erp.requests[-1]
    if request["table"] != "orders" or request["columns"] != columns:
        _fail("the request must name the schema's table and columns, got %r" % (request,))
    if request["where"] != {}:
        _fail("a report with no filters must not invent a where, got %r" % (request["where"],))
    if reports.run({"report": "open_orders"}, session)["content"][0]["text"] != text:
        _fail("the same report twice must render the same bytes")

    # filters travel as data, in the schema's order, and are ANDed
    result = reports.run({"report": "open_orders",
                          "filters": {"vendor_id": "v1", "status": "draft"}}, session)
    request = erp.requests[-1]
    if list(request["where"]) != ["status", "vendor_id"]:
        _fail("the request's where must follow the SCHEMA's filter order (%r), got %r"
              % (["status", "vendor_id"], list(request["where"])))
    if request["where"] != {"status": "draft", "vendor_id": "v1"}:
        _fail("the where must carry the caller's values verbatim, got %r" % (request["where"],))
    if [row[0] for row in _rows(result["content"][0]["text"])] != ["PO-1"]:
        _fail("several filters must be applied together: expected PO-1, got %r"
              % (_rows(result["content"][0]["text"]),))

    # an empty result set is a successful result with a header
    result = reports.run({"report": "open_orders", "filters": {"status": "cancelled"}}, session)
    if result.get("isError") is not False:
        _fail("a report with no matches is an answer, not an error: %r" % (result,))
    lines = result["content"][0]["text"].splitlines()
    if lines != ["  ".join(column for column in columns)] and lines[0].split() != columns:
        _fail("a report with no matches must be a header and no rows, got %r" % (lines,))
    if len(lines) != 1:
        _fail("a report with no matches must have no rows, got %r" % (lines,))

    result = reports.run({"report": "vendor_balance", "filters": {"vendor_id": "v2"}}, session)
    rows = _rows(result["content"][0]["text"])
    if rows != [["v2", "Acme", "Industrial", "3400"]]:
        _fail("vendor_balance filtered by v2 must return its one row, got %r" % (rows,))
    result = reports.run({"report": "vendor_balance"}, session)
    if [row[0] for row in _rows(result["content"][0]["text"])] != ["v1", "v2", "v3"]:
        _fail("vendor_balance must be sorted by vendor_id, got %r"
              % (_rows(result["content"][0]["text"]),))

    # -- values are data: "1 OR 1=1" is a literal that matches nothing
    injection = "1 OR 1=1"
    try:
        result = reports.run({"report": "vendor_balance",
                              "filters": {"vendor_id": injection}}, session)
    except Exception as exc:
        _fail("a filter VALUE must travel as data, never as a name: running vendor_balance with "
              "%r raised %s: %s" % (injection, type(exc).__name__, exc))
    request = erp.requests[-1]
    if request["table"] != "vendors":
        _fail("the table comes from REPORT_SCHEMA, never from a value: got %r"
              % (request["table"],))
    if request["columns"] != ["vendor_id", "name", "balance"]:
        _fail("the columns come from REPORT_SCHEMA, never from a value: got %r"
              % (request["columns"],))
    if list(request["where"]) != ["vendor_id"]:
        _fail("a value must land as a VALUE, under a column name from the schema: where=%r"
              % (request["where"],))
    if request["where"]["vendor_id"] != injection:
        _fail("the value must travel verbatim as a value (%r), got %r"
              % (injection, request["where"]["vendor_id"]))
    names = [request["table"]] + list(request["columns"]) + list(request["where"])
    leaked = [name for name in names
              if any(part in name for part in (injection, "1=1", "OR"))]
    if leaked:
        _fail("a value, or a piece of one, reached a NAME: %r in %r — values are compared, "
              "never parsed" % (injection, leaked))
    if result.get("isError") is not False or len(result["content"][0]["text"].splitlines()) != 1:
        _fail("an injected-looking value must match literally or nothing: %r" % (result,))

    result = reports.run({"report": "vendor_balance",
                          "filters": {"vendor_id": "v1 OR 1=1"}}, session)
    if _rows(result["content"][0]["text"]) != []:
        _fail("a near-miss value must not match: %r" % (result,))

    # -- the declared types are a vocabulary, and the schema is the one handed in
    custom = {"big_orders": {"table": "orders", "filters": {"quantity": "integer"},
                             "columns": ("reference", "quantity")}}
    typed = stage.Reports(erp, schema=custom)
    if typed.names != ["big_orders"]:
        _fail("Reports must run the schema it was handed, got %r" % (typed.names,))
    _protocol_error(lambda: typed.run(
        {"report": "big_orders", "filters": {"quantity": True}}, session),
        "a bool is not the declared integer", data={"filter": "quantity"},
        message_parts=("'quantity'", "integer"))
    result = typed.run({"report": "big_orders", "filters": {"quantity": 5}}, session)
    if _rows(result["content"][0]["text"]) != [["PO-1", "5"]]:
        _fail("a filter declared integer must compare as a number, got %r"
              % (_rows(result["content"][0]["text"]),))
    if erp.requests[-1]["where"] != {"quantity": 5}:
        _fail("an integer filter value must travel as an integer, got %r"
              % (erp.requests[-1]["where"],))

    # -- install: the tools reach the server's table, and the copy follows the switch
    server = FakeServer()
    erp2 = SpyErp(orders=orders)
    toolset2 = stage.Toolset()
    reports2 = stage.Reports(erp2)
    toolset2.add("vendor_lookup", "read one vendor",
                 {"type": "object", "properties": {"vendor_id": {"type": "string"}},
                  "required": ["vendor_id"]},
                 lambda args, sess: calls.append(("vendor_lookup", args)) or _ok("v1"))
    toolset2.add("approve_order", "approve a draft purchase order",
                 {"type": "object", "properties": {"reference": {"type": "string"}},
                  "required": ["reference"]},
                 lambda args, sess: calls.append(("approve_order", args)) or _ok("approved"),
                 mutates=True)
    stage.install(server, toolset2, reports2)
    for method in ("tools/list", "tools/call"):
        if method not in server.handlers:
            _fail("install must register %s: a tool is a definition the client reaches through "
                  "the server, not a fn it calls" % method)
    payload = server.call("tools/list", {})
    # Registration order: the tools added above, then the report tool that
    # reports2.install() added inside install().
    if _names(payload) != ["vendor_lookup", "report"]:
        _fail("a read-only install must list every registered read-only tool and no mutating "
              "one, in registration order: %r" % (_names(payload),))
    if "approve_order" in json.dumps(payload):
        _fail("the server's tools/list must not mention a mutating tool in read-only mode: %s"
              % json.dumps(payload))
    if "report" not in server.tools:
        _fail("install must publish the tools into the server's own table (server.add_tool): "
              "got %r" % (sorted(server.tools),))
    hidden = server.tools["approve_order"]
    if hidden["enabled"] is not False:
        _fail("a server whose tools/list is served by its own table must not have the mutating "
              "tool enabled either: %r" % (hidden,))
    if "read-only" not in (hidden.get("reason") or ""):
        _fail("a published-but-disabled definition must carry the reason: reason=%r"
              % (hidden.get("reason"),))

    # A server that does NOT know stage 3's read-only rule (it stores what it is
    # told and nothing else): `_publish` must not lean on the server to hide what
    # the toolset hides, or the copy is only as honest as the server it lands on.
    class DumbServer:
        """add_tool/set_tool_enabled, and no opinions."""

        def __init__(self):
            self.handlers = {}
            self.tools = {}
            self.told = []

        def add(self, method, handler):
            self.handlers[method] = handler
            return handler

        def notify(self, method, params=None):
            return None

        def add_tool(self, name, description, input_schema, fn, *,
                     mutates=False, enabled=True):
            definition = {"name": name, "description": description,
                          "inputSchema": input_schema, "fn": fn,
                          "mutates": mutates, "enabled": bool(enabled)}
            self.tools[name] = definition
            return definition

        def set_tool_enabled(self, name, enabled, *, reason=None):
            self.told.append((name, bool(enabled), reason))
            definition = self.tools[name]
            definition["enabled"] = bool(enabled)
            if reason is not None:
                definition["reason"] = reason
            return definition

    dumb = DumbServer()
    dumb_toolset = stage.Toolset()
    dumb_toolset.add("approve_order", "approve a draft purchase order",
                     {"type": "object", "properties": {"reference": {"type": "string"}},
                      "required": ["reference"]},
                     lambda arguments, sess: _ok("approved"), mutates=True)
    stage.install(dumb, dumb_toolset, stage.Reports(SpyErp(orders=orders)))
    copy = dumb.tools.get("approve_order")
    if copy is None:
        _fail("install must publish into the server's table (server.add_tool): got %r"
              % (sorted(dumb.tools),))
    if copy["enabled"] is not False:
        _fail("the published copy of a mutating tool must arrive DISABLED even on a server "
              "that knows nothing about read-only mode: %r" % (copy,))
    if "read-only" not in (copy.get("reason") or ""):
        _fail("_publish must say WHY it disabled the copy (server.set_tool_enabled(name, "
              "False, reason=...)): a client that shows an empty tool list has nothing to "
              "explain it with, and the reason is what stage 3's rule and stage 10's flip "
              "agree on; reason=%r, told=%r" % (copy.get("reason"), dumb.told))
    _protocol_error(lambda: server.call("tools/call",
                                        {"name": "approve_order", "arguments": {}}),
                    "a disabled tool through the server's tools/call",
                    data={"tool": "approve_order"})
    if ("approve_order", {}) in calls:
        _fail("the server's tools/call ran the fn of a disabled tool: %r" % (calls,))

    count = toolset2.enable_writes(approved_by="user:ana")
    if count != 1:
        _fail("the flip must report the one tool it exposed, got %r" % (count,))
    if server.read_only is not False:
        _fail("the flip must release the SERVER's own switch too, got read_only=%r"
              % (server.read_only,))
    if server.tools["approve_order"]["enabled"] is not True:
        _fail("the published copy must follow the flip (server.set_tool_enabled), or a server "
              "listing its own table keeps hiding a tool that is now reachable")
    payload = server.call("tools/list", {})
    if _names(payload) != ["vendor_lookup", "approve_order", "report"]:
        _fail("the next tools/list must contain the tool the flip exposed, in registration "
              "order: %r" % (_names(payload),))
    result = server.call("tools/call", {"name": "report", "arguments": {"report": "vendor_balance"}})
    if result["isError"] is not False or result["content"][0]["type"] != "text":
        _fail("a report through the server's tools/call must be a text result: %r" % (result,))
    if server.notifications:
        _fail("this stage sends no notification: stage 10 owns notifications/tools/list_changed "
              "and only the caller that flipped knows why. got %r" % (server.notifications,))

    # -- an install that finds tools/list already served leaves it alone
    server2 = FakeServer()
    server2.add("tools/list", lambda params, session: {"tools": [], "served_by": "stage 4"})
    stage.install(server2, stage.Toolset(), stage.Reports(SpyErp()))
    if server2.call("tools/list", {}) != {"tools": [], "served_by": "stage 4"}:
        _fail("install must not clobber tools/list when the server already serves it: stage 4 "
              "owns those two methods for the whole server, and replacing the handler narrows "
              "the client's view to one stage's tools")
    if "tools/call" not in server2.handlers:
        _fail("install must still register tools/call when only tools/list is served")

    # -- both supported compositions end in ONE report tool, and it is the same one
    canonical = FakeServer()
    stage.install(canonical, stage.Toolset(read_only=True), stage.Reports(SpyErp()))
    convenience = FakeServer()
    erp4 = SpyErp()
    toolset4 = stage.make_tools(erp4)
    # White-box on purpose: the only way to see the tool the toolset ALREADY holds
    # before install() runs is to look at the definition the toolset carries.
    held = toolset4._definition("report")["fn"]
    stage.install(convenience, toolset4, stage.Reports(erp4))
    for label, server_x in (("Toolset + Reports + install", canonical),
                            ("make_tools + install", convenience)):
        names = _names(server_x.call("tools/list", {}))
        if names != ["report"]:
            _fail("%s must end in exactly ONE report tool, got %r" % (label, names))
        if len(server_x.tools) != 1:
            _fail("%s published %d definitions: installing the same tool twice installs it "
                  "once" % (label, len(server_x.tools)))
    if convenience.tools["report"]["fn"] is not held:
        _fail("install must ADOPT the report tool the toolset already holds, not register a "
              "second one: the fn changed")
    for label, server_x in (("Toolset + Reports + install", canonical),
                            ("make_tools + install", convenience)):
        out = server_x.call("tools/call", {"name": "report",
                                          "arguments": {"report": "vendor_balance",
                                                        "filters": {"vendor_id": "v2"}}})
        if _rows(out["content"][0]["text"]) != [["v2", "Acme", "Industrial", "3400"]]:
            _fail("%s must expose the same working report tool, got %r" % (label, out))

    # ... and a DIFFERENT tool under a taken name is still a collision
    other_schema = {"mine": {"table": "vendors", "filters": {}, "columns": ("vendor_id",)}}
    try:
        stage.Reports(SpyErp(), schema=other_schema).install(toolset4)
    except ValueError:
        pass
    else:
        _fail("a report built from a DIFFERENT schema is a different tool: installing it under "
              "'report' must be a ValueError, not a silent adoption of the wrong tool")
    try:
        toolset4.add("report", "not the report tool", {"type": "object"}, lambda a, s: {})
    except ValueError:
        pass
    else:
        _fail("Toolset.add stays strict: a name that is taken is a ValueError")

    # -- the REAL server: the switch belongs to it, and both registration orders
    import stage_03 as stage_03_module
    import stage_04 as stage_04_module

    def _assembled(outside_first, toolset, reports):
        """stage 3 + stage 4 + stage 7, with another stage's mutating tool
        registered EITHER before OR after this stage's install."""
        server = stage_03_module.Server("erp", "1.0")
        server.initialized = True          # the handshake is stage 3's check, not this one
        stage_04_module.install(server)
        outside = []

        def create_purchase_order(arguments, session):
            outside.append(arguments)
            return _ok("created")

        if outside_first:
            server.add_tool("create_purchase_order", "another stage's mutating tool",
                            {"type": "object"}, create_purchase_order, mutates=True)
        stage.install(server, toolset, reports)
        if not outside_first:
            server.add_tool("create_purchase_order", "another stage's mutating tool",
                            {"type": "object"}, create_purchase_order, mutates=True)
        return server, outside

    for order in ("registered BEFORE stage 7", "registered AFTER stage 7"):
        erp_r = SpyErp(orders=orders)
        toolset_r = stage.Toolset(read_only=True)
        toolset_r.add("void_order", "void a draft order", {"type": "object"},
                      lambda args, sess: _ok("voided"), mutates=True)
        server_r, outside = _assembled(order.startswith("registered BEFORE"), toolset_r,
                                       stage.Reports(erp_r))
        if server_r.read_only is not True:
            _fail("nobody flipped the switch, so the server must still be read-only (%s): %r"
                  % (order, server_r.read_only))
        listed = _all_tools(server_r)
        if listed != ["report"]:
            _fail("read-only (%s): tools/list must hold the report tool only — a tool the model "
                  "can see is a tool the model will call — got %r" % (order, listed))
        if "create_purchase_order" in json.dumps(_result(server_r, "tools/list")):
            _fail("read-only (%s): another stage's mutating tool must not be advertised at all"
                  % order)
        error = _rpc(server_r, "tools/call",
                     {"name": "create_purchase_order", "arguments": {}}).get("error") or {}
        if error.get("code") != stage_01.ERRORS["invalid_params"] \
                or (error.get("data") or {}).get("tool") != "create_purchase_order":
            _fail("read-only (%s): another stage's disabled tool must be -32602 with data[tool]: %r"
                  % (order, error))
        if outside:
            _fail("read-only (%s): the fn of a disabled tool RAN: %r" % (order, outside))
        count = toolset_r.enable_writes(approved_by="user:ana")
        if count != 2:
            _fail("the flip must count every tool that BECAME VISIBLE (%s): this stage's void_order "
                  "plus the outside create_purchase_order is 2, got %r" % (order, count))
        if server_r.read_only is not False:
            _fail("the flip must release the SERVER's own switch (%s): read_only is still %r"
                  % (order, server_r.read_only))
        after = sorted(_all_tools(server_r))
        if after != ["create_purchase_order", "report", "void_order"]:
            _fail("after the flip (%s) every mutating tool must be listed, whoever registered it: "
                  "%r" % (order, after))
        _result(server_r, "tools/call", {"name": "create_purchase_order", "arguments": {}})
        if not outside:
            _fail("after the flip (%s) another stage's tool must run" % order)


# --- from checks/check_08.py
def check_8():
    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    """Raise AssertionError naming the mistake; return None when correct."""
    for name in ("stage_01", "erp", "stage_08"):
        sys.modules.pop(name, None)

    from erp import Erp
    from stage_01 import ERRORS, ProtocolError
    import stage_08 as s

    TOOL = "create_purchase_order"

    class FakeServer:
        """The stage 3 subset this stage may touch, plus the stage 4 tool table."""

        def __init__(self):
            self.handlers = {}
            self.notifications = []
            self.tools = {}
            self.session = {"identity": "user:ana", "steps": [], "data": {}}

        def add(self, method, handler):
            self.handlers[method] = handler
            return handler

        def notify(self, method, params=None):
            self.notifications.append(
                {"jsonrpc": "2.0", "method": method, "params": params})

        def add_tool(self, name, description, input_schema, fn, *, mutates=False,
                     enabled=True):
            definition = {"name": name, "description": description,
                          "inputSchema": input_schema, "fn": fn,
                          "mutates": mutates, "enabled": enabled}
            self.tools[name] = definition
            return definition

        def set_tool_enabled(self, name, enabled, *, reason=None):
            definition = self.tools[name]
            definition["enabled"] = enabled
            definition["reason"] = reason
            return definition

        def call_tool(self, name, arguments, id=1):
            definition = self.tools[name]
            try:
                return {"jsonrpc": "2.0", "id": id,
                        "result": definition["fn"](arguments, self.session)}
            except ProtocolError as exc:
                return exc.to_error(id)

    def harness(erp=None, identity="user:ana"):
        erp = Erp() if erp is None else erp
        ledger = s.Ledger(erp)
        server = FakeServer()
        server.session["identity"] = identity
        s.install(server, ledger)
        return erp, ledger, server

    def call(server, arguments):
        return server.call_tool(TOOL, arguments)

    def text_of(response):
        return response["result"]["content"][0]["text"]

    def code_of(response):
        return response.get("error", {}).get("code")

    # --- the registration: a tool, not a method ---------------------------

    erp, ledger, server = harness()
    assert TOOL in server.tools, (
        f"install() did not register the tool {TOOL!r}: {sorted(server.tools)}")
    assert server.handlers == {}, (
        f"a tool is not a JSON-RPC method, so a client should not have to know "
        f"{TOOL!r} as a method; registered: {sorted(server.handlers)}")
    definition = server.tools[TOOL]
    assert definition["mutates"] is True, (
        f"mutates={definition['mutates']!r}: stage 7 disables exactly the tools "
        f"that change the world")
    schema = definition["inputSchema"]
    assert "idempotencyKey" in schema["required"], (
        f"the key is not in `required`, so the model is never told it must invent "
        f"one: {schema['required']}")
    assert schema["properties"]["idempotencyKey"]["minLength"] == 8, schema
    assert schema is s.CREATE_ORDER_SCHEMA, "install() ignored CREATE_ORDER_SCHEMA"

    # --- a missing key is -32602, and nothing was attempted ---------------

    erp, ledger, server = harness()
    incomplete = {"reference": "PO-1", "vendor_id": "v1", "item_id": "i1",
                  "quantity": 2}
    response = call(server, dict(incomplete))
    assert code_of(response) == ERRORS["invalid_params"] == -32602, (
        f"a missing idempotencyKey has to be the protocol error the model can act "
        f"on (-32602 naming the parameter), not a generated key: {response}")
    assert "idempotencyKey" in response["error"]["message"], response
    assert response["error"].get("data") == {"tool": TOOL}, response
    assert erp.orders == {}, (
        f"the ERP was written by a call that never reached the tool: {erp.orders}")
    assert ledger.applied == {}, (
        f"nothing was attempted, so there is nothing to remember: {ledger.applied}")

    # --- a key the caller is not really trying with is refused too --------

    response = call(server, dict(incomplete, idempotencyKey="1"))
    assert code_of(response) == -32602, (
        f"the schema says minLength 8, and a key of '1' is the caller telling you "
        f"it is not trying: {response}")
    assert "idempotencyKey" in response["error"]["message"], response
    assert erp.orders == {} and ledger.applied == {}, (
        f"a validation failure is not an outcome, so the key is not consumed: "
        f"{ledger.applied}")

    # --- the retry with a real key then works -----------------------------

    args = {"idempotencyKey": "key-000000001", "reference": "PO-1",
            "vendor_id": "v1", "item_id": "i1", "quantity": 2}
    first = call(server, dict(args))
    assert "result" in first, (
        f"the retry after a validation failure has to work, because nothing was "
        f"remembered from it: {first}")
    assert first["result"]["isError"] is False, first
    text1 = text_of(first)
    assert "PO-1" in text1 and "draft" in text1, (
        f"the text names the order reference and its status: {text1!r}")
    assert erp.orders["PO-1"]["status"] == "draft", erp.orders

    # --- the same key twice is one order and one identical answer ---------

    again = call(server, dict(args))
    text2 = text_of(again)
    assert text1 == text2, (
        f"a client that timed out cannot tell the two calls apart unless the "
        f"reply is the same bytes:\n  {text1!r}\n  {text2!r}")
    assert len(erp.orders) == 1, (
        f"{len(erp.orders)} orders after one key: the replay created the order "
        f"again, which is the failure this whole stage exists to prevent")
    assert ledger.reused == 1, (
        f"reused={ledger.reused}: the answered-from-the-ledger calls are counted, "
        f"and this one was answered from the ledger")

    # --- dict order is not part of the request ----------------------------

    reordered = {"quantity": 2, "item_id": "i1", "vendor_id": "v1",
                 "reference": "PO-1", "idempotencyKey": "key-000000001"}
    third = call(server, reordered)
    assert text_of(third) == text1, (
        f"the same arguments in another dict order are the same request, so the "
        f"fingerprint has to be canonical: {text_of(third)!r} != {text1!r}")
    assert ledger.reused == 2 and len(erp.orders) == 1, (ledger.reused, erp.orders)

    # --- the same key for a different request is a client bug -------------

    conflict = call(server, dict(args, quantity=99))
    assert conflict.get("result", {}).get("isError") is True, (
        f"a different request under a spent key is not a second operation: "
        f"{conflict}")
    conflict_text = text_of(conflict)
    assert "key-000000001" in conflict_text, (
        f"the error text names the key, because that is what the model has to "
        f"change: {conflict_text!r}")
    assert "do not retry" in conflict_text.lower(), (
        f"error text is part of the interface: it must say that retrying will not "
        f"help — do not retry, ask the user: {conflict_text!r}")
    assert len(erp.orders) == 1 and erp.orders["PO-1"]["quantity"] == 2, (
        f"the conflicting request was applied: {erp.orders}")
    assert ledger.reused == 2, (
        f"reused={ledger.reused}: a refused conflicting call is not an answer "
        f"from the ledger, so it does not count as reused")

    # --- a business failure is an outcome, and it is replayed -------------

    class CountingErp(Erp):
        """Counts the attempts that reached the ERP, not the calls that arrived."""

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.attempts = 0

        def draft(self, *call_args, **call_kwargs):
            self.attempts += 1
            return super().draft(*call_args, **call_kwargs)

    erp, ledger, server = harness(CountingErp())
    refused_args = {"idempotencyKey": "key-bad-0001", "reference": "PO-2",
                    "vendor_id": "v9", "item_id": "i1", "quantity": 1}
    refused = call(server, dict(refused_args))
    assert refused["result"]["isError"] is True, (
        f"a business failure is an isError result, not a protocol error: {refused}")
    refused_text = text_of(refused)
    assert "v9" in refused_text, (
        f"the refusal says why: {refused_text!r}")
    entry = ledger.applied.get("key-bad-0001")
    assert entry is not None and entry["outcome"] == "error", (
        f"a business failure consumes the key and is stored as an outcome: "
        f"{ledger.applied}")
    assert erp.attempts == 1, erp.attempts

    replay = call(server, dict(refused_args))
    assert text_of(replay) == refused_text, (
        f"the retry of a stored failure returns the same failure text:\n"
        f"  {refused_text!r}\n  {text_of(replay)!r}")
    assert replay["result"]["isError"] is True, replay
    assert erp.attempts == 1, (
        f"the retry re-attempted the write ({erp.attempts} attempts): a business "
        f"failure is an answer, and a client retrying must not turn one refusal "
        f"into a storm of them")
    assert ledger.reused == 1, ledger.reused
    assert erp.orders == {}, erp.orders

    # --- a quantity the ERP refuses is a business failure, not a schema one

    erp, ledger, server = harness()
    negative = {"idempotencyKey": "key-neg-0001", "reference": "PO-4",
                "vendor_id": "v1", "item_id": "i1", "quantity": -1}
    response = call(server, dict(negative))
    assert response.get("result", {}).get("isError") is True, (
        f"the schema says `integer`, and the ERP is the one that refuses a "
        f"negative quantity — that refusal is an outcome, not -32602: {response}")
    assert ledger.applied["key-neg-0001"]["outcome"] == "error", ledger.applied
    assert erp.orders == {}, erp.orders


# --- from checks/check_09.py
def check_9():
    DEFAULT_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    HERE = os.path.dirname(os.path.abspath(__file__))

    def _importable():
        """The harness sets PYTHONPATH; a bare `python check_09.py` does not, so find
        the course the same way the mutation harness does."""
        import importlib.util

        if importlib.util.find_spec("stage_09") and importlib.util.find_spec("erp"):
            return
        start = os.environ.get("D1_REPO") or os.getcwd()
        tried = []
        for candidate in (start, DEFAULT_REPO):
            path = os.path.abspath(candidate)
            tried.append(path)
            while True:
                if os.path.isfile(os.path.join(path, "mcp-from-scratch", "stage_09.py")):
                    sys.path.insert(0, path)
                    sys.path.insert(0, os.path.join(path, "mcp-from-scratch"))
                    return
                parent = os.path.dirname(path)
                if parent == path:
                    break
                path = parent
        raise AssertionError(
            f"check_09: set D1_REPO=/path/to/learn-stuff-from-scratch — no "
            f"mcp-from-scratch/stage_09.py was found above {tried}")

    _importable()
    import stage_09 as stage
    from erp import Erp

    ACCEPT = {"action": "accept", "content": {"approve": True}}
    DECLINE = {"action": "decline"}
    CANCEL = {"action": "cancel"}

    class ProtocolError(Exception):
        """Stage 1's exception, cut down to the field this check reads."""

        def __init__(self, code, message, data=None):
            super().__init__(message)
            self.code = code
            self.message = message
            self.data = data

    class Client:
        """The client's half of `elicitation/create`, played by a person with a
        written script: what they were shown, and what they answered."""

        def __init__(self, *answers):
            self.answers = list(answers)
            self.calls = []

        def __call__(self, message, requested_schema):
            self.calls.append({"message": message, "requestedSchema": requested_schema})
            if not self.answers:
                return DECLINE
            return self.answers.pop(0)

    class FakeServer:
        """The subset of `Server` stage 9 may use. Stages 3 and 4 are other
        people's files, so this check does not import them — but a tool goes
        through `tools/call`, so `call_tool` below applies the two rules this
        stage's definition depends on."""

        def __init__(self, identity="user:ana"):
            self.methods = {}
            self.notifications = []
            self.tools = {}
            self.session = {"identity": identity, "steps": [], "data": {}}

        def add(self, method, handler):
            self.methods[method] = handler
            return handler

        def notify(self, method, params=None):
            self.notifications.append({"jsonrpc": "2.0", "method": method,
                                       "params": params or {}})

        def add_tool(self, name, description, input_schema, fn, *,
                     mutates=False, enabled=True):
            self.tools[name] = {"name": name, "description": description,
                                "inputSchema": input_schema, "fn": fn,
                                "mutates": mutates, "enabled": enabled}
            return self.tools[name]

        def set_tool_enabled(self, name, enabled, *, reason=None):
            self.tools[name]["enabled"] = enabled
            if reason is not None:
                self.tools[name]["reason"] = reason
            return self.tools[name]

    def session(identity="user:ana"):
        return {"identity": identity, "steps": [], "data": {}}

    def make_erp():
        return Erp(orders={"PO-1": {"reference": "PO-1", "vendor_id": "v1",
                                    "item_id": "i1", "quantity": 10,
                                    "status": "draft", "identity": "user:ana"}})

    def text_of(result):
        assert isinstance(result, dict), f"a tool result is a dict, got {result!r}"
        content = result.get("content")
        assert isinstance(content, list) and content, (
            f"a tool result carries content, got {result!r}")
        assert content[0].get("type") == "text", (
            f"the content of a tool result is text, got {content[0]!r}")
        return content[0]["text"]

    def refused(result, where, *phrases):
        assert result.get("isError") is True, (
            f"{where}: isError must be True, got {result!r}")
        text = text_of(result)
        for phrase in phrases:
            assert phrase in text, f"{where}: {phrase!r} is missing from {text!r}"
        return text

    def call_tool(server, name, arguments):
        """Stage 4's entry point, cut down to the two rules this stage leans on:
        a tool that is not in the table, and arguments the definition does not
        declare, are -32602 — the handler never runs."""
        definition = server.tools.get(name)
        if definition is None:
            raise ProtocolError(-32602, f"unknown tool {name!r}", {"tool": name})
        schema = definition["inputSchema"]
        properties = set(schema.get("properties", {}))
        unknown = sorted(set(arguments) - properties)
        if unknown:
            raise ProtocolError(-32602, f"invalid arguments for {name!r}: "
                                        f"unknown parameter {unknown[0]!r}",
                                {"tool": name})
        missing = sorted(set(schema.get("required", [])) - set(arguments))
        if missing:
            raise ProtocolError(-32602, f"invalid arguments for {name!r}: "
                                        f"missing parameter {missing[0]!r}",
                                {"tool": name})
        assert schema.get("additionalProperties") is False, (
            "the tool's inputSchema must refuse the parameters it does not "
            "declare, or 'no identity argument' is decoration")
        return definition["fn"](arguments, server.session)

    # --- the approval's identity is the diff -------------------------------
    diff_25 = [{"field": "quantity", "from": 10, "to": 25}]
    token = stage.diff_token(diff_25)
    assert isinstance(token, str) and len(token) == 64 and all(
        character in "0123456789abcdef" for character in token), (
        f"diff_token is documented as sha256 hex, got {token!r}")
    assert stage.diff_token([{"field": "quantity", "from": 10, "to": 25}]) == token, (
        "two identical diffs must give the same token, or nobody can re-validate "
        "an approval")
    assert stage.diff_token([{"to": 25, "from": 10, "field": "quantity"}]) == token, (
        "the token is over the CANONICAL diff: key order must not matter")
    assert stage.diff_token([{"field": "quantity", "from": 10, "to": 250}]) != token, (
        "a different 'to' must give a different token, or an approval for one "
        "quantity approves every quantity")
    assert stage.diff_token([{"field": "quantity", "from": 20, "to": 25}]) != token, (
        "a different 'from' must give a different token: the approval is of a "
        "change of state, and the state it was approved against is part of it")

    # --- format_diff is prose, not the arguments ---------------------------
    lines = stage.format_diff([{"field": "status", "from": "draft", "to": "approved"},
                               {"field": "quantity", "from": None, "to": 25}])
    assert len(lines.splitlines()) == 2, (
        f"one line per field, got {lines!r}")
    for piece in ("status", "draft", "approved", "quantity", "25"):
        assert piece in lines, f"{piece!r} is missing from the shown diff: {lines!r}"
    assert '"' not in lines and ":" not in lines, (
        f"the shown diff is prose, not a JSON dump of the arguments: {lines!r}")

    # --- an affirmative accept applies, and the prompt was the diff --------
    erp = make_erp()
    client = Client(ACCEPT)
    confirmation = stage.Confirmation(erp, client)
    change = erp.set_quantity("PO-1", 25, identity="user:ana")
    before = erp.diff(change)
    assert before == [{"field": "quantity", "from": 10, "to": 25}], (
        f"the fixture is not what this check assumes: {before!r}")
    result = confirmation.propose(change, session())
    assert result["isError"] is False, (
        f"an explicit approve:true must apply the change, got {result!r}")
    applied_text = text_of(result)
    assert "PO-1" in applied_text and "draft" in applied_text, (
        f"the applied result must name the reference and the new status, got "
        f"{applied_text!r}")
    assert erp.orders["PO-1"]["quantity"] == 25, (
        f"the ERP still reads {erp.orders['PO-1']['quantity']}: the change was "
        f"approved and not applied")

    assert len(client.calls) == 1, (
        f"one round asks once, got {len(client.calls)} elicitations")
    message = client.calls[0]["message"]
    asked = client.calls[0]["requestedSchema"]
    assert stage.format_diff(before) in message, (
        f"the prompt is not the diff: expected {stage.format_diff(before)!r} in "
        f"{message!r}")
    for piece in ("quantity", "PO-1", "10", "25"):
        assert piece in message, f"{piece!r} is missing from the prompt: {message!r}"
    for fragment in ('"quantity":25', '"quantity": 25', '"kind"', "set_quantity"):
        assert fragment not in message, (
            f"{fragment!r} is in the prompt: the dialog is showing the tool "
            f"call's arguments, not what would change — and the fortieth dialog "
            f"of the morning is then approved without being read")
    assert asked["properties"]["approve"]["type"] == "boolean", (
        f"the elicitation must ask for an explicit boolean, got {asked!r}")
    assert "approve" in asked["required"], (
        "the elicitation must require the boolean: an absent answer is not an "
        "approval")

    assert len(confirmation.approvals) == 1, (
        f"one round, one entry, got {confirmation.approvals!r}")
    entry = confirmation.approvals[0]
    assert entry["token"] == stage.diff_token(before), (
        "the recorded token is not diff_token() of the diff that was shown: the "
        "approval's identity must be the diff, not the call")
    assert entry["diff"] == before and entry["identity"] == "user:ana", (
        f"the round must record its diff and its identity, got {entry!r}")
    assert entry["action"] == "accept" and entry["applied"] is True, (
        f"the applied round records accept/applied: {entry!r}")
    assert entry["token"] in confirmation.pending, (
        f"the accepted token is not in .pending ({confirmation.pending!r}): a "
        f"replayed token cannot be checked against the change it was issued for")
    assert confirmation.pending[entry["token"]]["reference"] == "PO-1", (
        f".pending must keep the change the token was issued for, got "
        f"{confirmation.pending[entry['token']]!r}")
    assert confirmation.pending[entry["token"]]["quantity"] == 25, (
        "the pending change must carry the quantity that was approved")

    # --- the applied result names the new status ---------------------------
    erp = make_erp()
    confirmation = stage.Confirmation(erp, Client(ACCEPT))
    order = erp.approve("PO-1", identity="user:ana")
    result = confirmation.require(order, session())
    assert result["isError"] is False, f"approve_order must apply, got {result!r}"
    approved_text = text_of(result)
    assert "PO-1" in approved_text and "approved" in approved_text, (
        f"the applied result must name the reference and the new status, got "
        f"{approved_text!r}")
    assert erp.orders["PO-1"]["status"] == "approved", (
        f"the status moved from draft to {erp.orders['PO-1']['status']!r}")

    # --- a non-affirmative answer is a decline -----------------------------
    for label, answer in (("a boolean no", {"action": "accept",
                                            "content": {"approve": False}}),
                          ("a truthy string", {"action": "accept",
                                               "content": {"approve": "yes"}}),
                          ("no answer at all", {"action": "accept",
                                                "content": {}})):
        erp = make_erp()
        confirmation = stage.Confirmation(erp, Client(answer))
        change = erp.set_quantity("PO-1", 25, identity="user:ana")
        result = confirmation.require(change, session())
        refused(result, f"a non-affirmative accept ({label})",
                "no change was made", "declined")
        assert erp.orders["PO-1"]["quantity"] == 10, (
            f"{label}: the ERP reads {erp.orders['PO-1']['quantity']} — an "
            f"approval must be affirmative, and anything else must leave the "
            f"world alone")
        entry = confirmation.approvals[-1]
        assert entry["action"] == "decline" and entry["applied"] is False, (
            f"{label}: the round must be recorded as a decline that wrote "
            f"nothing, got {entry!r}")

    # --- decline and cancel both refuse, and read differently --------------
    erased = make_erp()
    declared = stage.Confirmation(erased, Client(DECLINE))
    declined = refused(declared.require(
        erased.set_quantity("PO-1", 25, identity="user:ana"), session()),
        "a decline", "no change was made")
    assert "declined" in declined, declined
    cancelled_erp = make_erp()
    cancelled_conf = stage.Confirmation(cancelled_erp, Client(CANCEL))
    cancelled = refused(cancelled_conf.require(
        cancelled_erp.set_quantity("PO-1", 25, identity="user:ana"), session()),
        "a cancel", "no change was made")
    assert "cancelled" in cancelled or "canceled" in cancelled, cancelled
    assert declined != cancelled, (
        f"decline and cancel read the same in the log ({declined!r}): the "
        f"operator cannot tell whether the person said no or walked away")
    assert erased.orders["PO-1"]["quantity"] == 10, (
        "a decline wrote to the ERP")
    assert cancelled_erp.orders["PO-1"]["quantity"] == 10, (
        "a cancel wrote to the ERP")
    assert declared.approvals[-1]["action"] == "decline", (
        f"a decline records the decline: {declared.approvals[-1]!r}")
    assert cancelled_conf.approvals[-1]["action"] == "cancel", (
        f"a cancel records the cancel: {cancelled_conf.approvals[-1]!r}")
    assert declared.approvals[-1]["applied"] is False, (
        "a declined round is not an applied round")
    assert cancelled_conf.approvals[-1]["applied"] is False, (
        "a cancelled round is not an applied round")

    # --- the token authorises a change of state, not a call ----------------
    erp = make_erp()
    client = Client(ACCEPT)
    confirmation = stage.Confirmation(erp, client)
    change = erp.set_quantity("PO-1", 25, identity="user:ana")
    approved_diff = erp.diff(change)
    assert confirmation.require(change, session())["isError"] is False, (
        "the fixture's first round must apply")
    token = confirmation.approvals[-1]["token"]
    assert token == stage.diff_token(approved_diff) and token in confirmation.pending
    assert erp.orders["PO-1"]["quantity"] == 25

    bigger = erp.set_quantity("PO-1", 250, identity="user:ana")
    # put the world back where it was when the token was issued, so the replay is
    # the brief's case exactly: an approval for 10 -> 25 offered for 10 -> 250
    erp.apply(erp.set_quantity("PO-1", 10, identity="user:bob"), identity="user:bob")
    assert erp.diff(bigger) == [{"field": "quantity", "from": 10, "to": 250}], (
        f"the fixture is not what this check assumes: {erp.diff(bigger)!r}")
    refused(confirmation.require(bigger, session(), token=token),
            "a token issued for 10 -> 25 replayed for 10 -> 250",
            "quantity", "10", "25", "250")
    assert erp.orders["PO-1"]["quantity"] == 10, (
        f"the ERP reads {erp.orders['PO-1']['quantity']}: a token issued for "
        f"10 -> 25 was spent on a change nobody approved")
    assert confirmation.approvals[-1]["action"] != "accept", (
        f"the refused round is recorded as an accept: {confirmation.approvals[-1]!r}")
    assert confirmation.approvals[-1]["applied"] is False, (
        "a refusal is not an applied round")
    assert len(client.calls) == 1, (
        "a replayed token re-opened the dialog: the person already answered this "
        "diff, and asking again is how an approval becomes a rubber stamp")

    # the same words, a state that moved: still a different change
    erp.apply(erp.set_quantity("PO-1", 20, identity="user:bob"), identity="user:bob")
    refused(confirmation.require(change, session(), token=token),
            "the same change at a state that moved", "quantity", "20")
    assert erp.orders["PO-1"]["quantity"] == 20, (
        f"the ERP reads {erp.orders['PO-1']['quantity']}: the token was validated "
        f"against the words of the call instead of the diff it was issued for")
    unknown = confirmation.require(bigger, session(), token="0" * 64)
    refused(unknown, "a token this session never issued", "never approved")

    # a token from a round the person declined is not an approval
    erp = make_erp()
    confirmation = stage.Confirmation(erp, Client(DECLINE))
    change = erp.set_quantity("PO-1", 25, identity="user:ana")
    refused(confirmation.require(change, session()), "the round the person declined")
    declined_token = confirmation.approvals[-1]["token"]
    assert declined_token == stage.diff_token(erp.diff(change)), (
        "the declined round's token is the diff's token, which is exactly why the "
        "token cannot be the only check")
    refused(confirmation.require(change, session(), token=declined_token),
            "a token from a declined round", "never approved")
    assert erp.orders["PO-1"]["quantity"] == 10, (
        f"the ERP reads {erp.orders['PO-1']['quantity']}: a person said no to this "
        f"change, and the caller then applied it with the token from the round")

    # --- no identity, no round --------------------------------------------
    for label, sess in (("missing", {"steps": [], "data": {}}),
                        ("None", session(identity=None)),
                        ("empty", session(identity=""))):
        erp = make_erp()
        client = Client(ACCEPT)
        confirmation = stage.Confirmation(erp, client)
        change = erp.set_quantity("PO-1", 25, identity="user:ana")
        denied = refused(confirmation.require(change, sess),
                         f"a mutation with a {label} identity", "no identity")
        assert "denied" in denied, denied
        assert client.calls == [], (
            f"a {label} identity still asked a person to approve: nothing may be "
            f"shown until the server knows who it is asking on behalf of")
        assert confirmation.approvals == [], (
            f"a {label} identity produced an approval entry {confirmation.approvals!r}: "
            f"a request that was never made is not a round")
        assert erp.orders["PO-1"]["quantity"] == 10, (
            f"a {label} identity wrote to the ERP")

    # --- the tool: registered, and the identity cannot be injected ---------
    server = FakeServer(identity="user:ana")
    erp = make_erp()
    client = Client(ACCEPT)
    confirmation = stage.Confirmation(erp, client)
    stage.install(server, confirmation)
    assert "apply_change" in server.tools, (
        f"install registered {sorted(server.tools)}: the mutating tool belongs in "
        f"the server's tool table")
    assert server.methods == {}, (
        f"install added the JSON-RPC methods {sorted(server.methods)}: a tool is "
        f"not a method, or a client has to know it by name to call it")
    definition = server.tools["apply_change"]
    assert definition["mutates"] is True, (
        "apply_change mutates the world, and stage 7's read-only mode is "
        "'everything that mutates is disabled'")
    tool_schema = definition["inputSchema"]
    assert "identity" not in tool_schema.get("properties", {}), (
        "the tool declares an 'identity' argument: a caller could then claim to "
        "be someone else, which is the injection this stage refuses")
    assert tool_schema.get("required") == ["change"], (
        f"the tool requires a change and nothing else, got {tool_schema!r}")

    forged = erp.set_quantity("PO-1", 25, identity="user:mallory")
    result = call_tool(server, "apply_change", {"change": forged})
    assert result["isError"] is False, (
        f"the tool call must apply the approved change, got {result!r}")
    assert erp.orders["PO-1"]["quantity"] == 25, "the tool call did not write"
    assert erp.orders["PO-1"]["identity"] == "user:ana", (
        f"the order records {erp.orders['PO-1']['identity']!r}: the mutation runs "
        f"as the session's identity, never as the identity written into the "
        f"change it was handed")

    try:
        call_tool(server, "apply_change",
                  {"change": forged, "identity": "user:root"})
    except Exception as exc:
        assert getattr(exc, "code", None) == -32602, (
            f"an 'identity' tool argument was answered with {exc!r}: the tool does "
            f"not declare it, so tools/call refuses it with -32602")
    else:
        raise AssertionError(
            "a caller passed 'identity' as a tool argument and got a result: the "
            "mutation would have run as whoever the caller claimed to be")
    assert len(client.calls) == 1, (
        f"{len(client.calls)} elicitations: a call with an undeclared parameter "
        f"must be refused before a person is asked anything")

    # --- one entry per round, with its action and its flag -----------------
    erp = make_erp()
    client = Client(ACCEPT, DECLINE, CANCEL)
    confirmation = stage.Confirmation(erp, client)
    rounds = [erp.set_quantity("PO-1", 25, identity="user:ana"),
              erp.set_quantity("PO-1", 26, identity="user:ana"),
              erp.set_quantity("PO-1", 27, identity="user:ana")]
    outcomes = [confirmation.require(item, session()) for item in rounds]
    assert [outcome["isError"] for outcome in outcomes] == [False, True, True], (
        f"the three rounds answered {outcomes!r}")
    assert [item["action"] for item in confirmation.approvals] == \
        ["accept", "decline", "cancel"], (
        f".approvals records one entry per round with the effective action, got "
        f"{confirmation.approvals!r}")
    assert [item["applied"] for item in confirmation.approvals] == [True, False, False], (
        f"only the round that wrote is applied, got {confirmation.approvals!r}")
    assert erp.orders["PO-1"]["quantity"] == 25, (
        f"the ERP reads {erp.orders['PO-1']['quantity']}: only the accepted round "
        f"may write")
    assert len({item["token"] for item in confirmation.approvals}) == 3, (
        "three different changes, three different tokens")
    for item in confirmation.approvals:
        assert {"token", "diff", "identity", "action", "applied"} <= set(item), (
            f"an approval entry is missing a field: {item!r}")
        assert item["identity"] == "user:ana", (
            f"every round records the identity it ran as: {item!r}")
        assert item["diff"], f"every round records the diff it showed: {item!r}"
    assert list(confirmation.pending) == [confirmation.approvals[0]["token"]], (
        f"only an accepted change is pending, got {confirmation.pending!r}")

    # --- a business failure behind an approval is text, not a crash --------
    erp = make_erp()
    confirmation = stage.Confirmation(erp, Client(ACCEPT, ACCEPT))
    assert confirmation.require(erp.approve("PO-1", identity="user:ana"),
                                session())["isError"] is False
    stale = {"kind": "approve_order", "reference": "PO-1", "status": "approved",
             "identity": "user:ana"}
    result = confirmation.require(stale, session())
    stale_text = refused(result, "an approval the ERP answers no to",
                         "already approved")
    assert "approved" in stale_text, stale_text
    assert confirmation.approvals[-1]["action"] == "accept", (
        f"the person did approve, and the log says so: {confirmation.approvals[-1]!r}")
    assert confirmation.approvals[-1]["applied"] is False, (
        "the ERP refused the change, so the round did not apply")


# --- from checks/check_mine.py
def check_10():
    """The trajectory: a window of writes with two limits, an approval bound to a
    state, and an audit line with no clock and no payload."""
    from stage_01 import notification, request
    from stage_03 import Server
    from stage_10 import Audit, SessionPolicy, announce_tools_changed, guard, impact

    def error_code(response):
        """The JSON-RPC error code of a response, or None. A mutation that answers
        where it should have refused must fail an assertion, not a lookup."""
        if not isinstance(response, dict):
            return None
        error = response.get("error")
        return error.get("code") if isinstance(error, dict) else None

    def result_text(response):
        result = (response or {}).get("result")
        if not isinstance(result, dict):
            return None
        content = result.get("content")
        if not isinstance(content, list) or not content:
            return None
        first = content[0]
        return first.get("text") if isinstance(first, dict) else None


    assert impact({"arguments": {"quantity": 40}}) == 40, (
        "impact is the quantity a write moves")
    assert impact({"arguments": {"quantity": -40}}) == 40, (
        "a quantity is measured by how far it moves, not by its sign")
    assert impact({"arguments": {"quantity": True}}) == 0, (
        "True is not a quantity: isinstance(True, int) is True, and a boolean "
        "quantity is a bug that must not spend a budget")
    assert impact({"arguments": {"reference": "p1"}}) == 0, (
        "approving an order moves no quantity by itself")
    assert impact({"arguments": {"change": {"kind": "set_quantity",
                                            "quantity": 25}}}) == 25, (
        "stage 9's tool takes the CHANGE, so the quantity to police lives inside "
        "it: reading only arguments['quantity'] makes a window of apply_change "
        "calls total zero and never reach its ceiling")
    assert impact({"change": {"quantity": 30}}) == 30, (
        "a bare change is read the same way")
    assert impact({"arguments": {"change": {"kind": "approve_order"}}}) == 0

    session = {"identity": "user:ana", "steps": [], "data": {}}

    # -- a read is never refused, whatever the window spent ------------------
    policy = SessionPolicy(max_mutations=1, max_total_quantity=10)
    assert policy.classify({"tool": "report", "mutates": False}) == "read", (
        "a tool that does not mutate is a read")
    assert policy.classify({"tool": "set_quantity", "mutates": True}) == "write", (
        "a mutating tool call is a write")
    assert policy.classify({"change": {"kind": "set_quantity"}}) == "write", (
        "a bare change is a write even without a tool name")
    assert policy.decide(session, {"tool": "set_quantity", "mutates": True,
                                   "arguments": {"quantity": 10}})["allowed"], (
        "the first write inside the window is allowed")
    policy.record(session, {"tool": "set_quantity", "mutates": True,
                            "arguments": {"quantity": 10}})
    blocked = policy.decide(session, {"tool": "set_quantity", "mutates": True,
                                      "arguments": {"quantity": 1}})
    assert not blocked.get("allowed"), "the window is full: the cap must refuse"
    assert "1" in blocked.get("reason") and "approval" in blocked.get("reason"), (
        "the refusal must name the limit and say that the batch needs one "
        "approval, got %r" % (blocked.get("reason"),))
    verdict = policy.decide(session, {"tool": "report", "mutates": False})
    assert verdict["allowed"], (
        "a session that cannot read cannot explain itself: reads are never "
        "refused, not even over the cap")
    assert len(policy.refused) == 1 and policy.refused[0]["call"]["tool"] == "set_quantity", (
        "a refusal is recorded once, naming the call")
    assert len(policy.window) == 1, (
        "a refused call spends nothing: the window records what HAPPENED")

    # -- the aggregate ------------------------------------------------------
    policy = SessionPolicy(max_mutations=5, max_total_quantity=100)
    for _ in range(2):
        call = {"tool": "set_quantity", "mutates": True, "arguments": {"quantity": 40}}
        assert policy.decide(session, call)["allowed"], "40 units each are individually fine"
        policy.record(session, call)
    third = {"tool": "set_quantity", "mutates": True, "arguments": {"quantity": 40}}
    blocked = policy.decide(session, third)
    assert not blocked.get("allowed"), (
        "three calls of 40 each are individually safe and together move 120: the "
        "third must be refused")
    assert "100" in blocked.get("reason") and "80" in blocked.get("reason"), (
        "the refusal must name the aggregate and the ceiling, got %r"
        % (blocked.get("reason"),))
    assert "aggregate" in blocked.get("reason") or "whole diff" in blocked.get("reason"), (
        "the reason must say the aggregate needs one approval showing the whole "
        "diff, got %r" % (blocked.get("reason"),))
    assert len(policy.window) == 2, "a refused call must not enter the window"

    # -- identity -----------------------------------------------------------
    anonymous = {"identity": None, "steps": [], "data": {}}
    policy = SessionPolicy()
    blocked = policy.decide(anonymous, {"tool": "set_quantity", "mutates": True,
                                        "arguments": {"quantity": 1}})
    assert not blocked.get("allowed") and "identity" in blocked.get("reason"), (
        "a write with no identity has nobody to attribute it to: refused with a "
        "reason naming identity, got %r" % (blocked.get("reason"),))

    # -- an approval is bound to a state ------------------------------------
    policy = SessionPolicy()
    change = {"tool": "set_quantity", "mutates": True,
              "arguments": {"quantity": 25}}
    policy.approve(session, change, token="tok-1")
    assert policy.accept(change, token="tok-1")["accepted"], (
        "a live approval for this very change is accepted")
    assert not policy.accept({"tool": "set_quantity", "mutates": True,
                              "arguments": {"quantity": 250}},
                             token="tok-1")["accepted"], (
        "an approval for 25 must not authorise 250: the token is bound to the "
        "change, not to the tool")
    assert not policy.accept(change, token="tok-9")["accepted"], (
        "a token nobody issued is not accepted")
    policy.record(session, change, outcome="ok")
    verdict = policy.accept(change, token="tok-1")
    assert not verdict.get("accepted"), (
        "a write makes every earlier approval stale: it describes a state that "
        "no longer exists")
    assert "stale" in verdict.get("reason"), (
        "the refusal must say the approval is stale and why, got %r"
        % (verdict.get("reason"),))
    assert policy.stale and policy.stale[0]["token"] == "tok-1", (
        "the invalidated approval belongs in .stale, not in .approvals")
    assert policy.approvals == [], "a stale approval is not live"
    policy.record(session, change, outcome="error")
    assert len(policy.window) == 1, (
        "a business failure changed nothing and must not spend the window")

    # -- guard: refused before the tool runs, as a RESULT --------------------
    server = Server("erp-mcp", "0.1.0")
    ran = []

    def call_tool(params, sess):
        ran.append(params.get("name"))
        if params.get("name") == "create_order":
            # a tool that tried and was refused by the business: isError, and no
            # change happened, so nothing may be spent
            return {"content": [{"type": "text", "text": "the vendor said no"}],
                    "isError": True}
        return {"content": [{"type": "text", "text": "changed"}], "isError": False}

    server.add("tools/call", call_tool)
    server.add_tool("set_quantity", "move a quantity", {"type": "object"},
                    call_tool, mutates=True)
    server.add_tool("report", "read", {"type": "object"}, call_tool)
    server.add_tool("create_order", "create", {"type": "object"},
                    call_tool, mutates=True)
    policy = SessionPolicy(max_mutations=2, max_total_quantity=1000)
    audit = Audit()
    dispatch = guard(server, policy, audit)

    assert dispatch(request(1, "initialize",
                            {"protocolVersion": "2025-06-18",
                             "_meta": {"identity": "user:ana"}}))["result"], (
        "the guarded dispatcher is a dispatcher: the handshake still works")
    dispatch(notification("notifications/initialized"))
    write = lambda id, quantity: request(id, "tools/call", {
        "name": "set_quantity", "arguments": {"quantity": quantity}})

    assert dispatch(write(2, 40))["result"] == {"content": [{"type": "text",
                                                             "text": "changed"}],
                                                "isError": False}, (
        "the first write inside the window reaches the tool")
    assert ran == ["set_quantity"] and len(policy.window) == 1, (
        "a write that happened must enter the window")
    assert server.session["steps"], (
        "a write that happened belongs in the session's steps: that list is the "
        "trajectory the policy reasons about")
    assert (dispatch(request(3, "tools/call", {"name": "create_order",
                                              "arguments": {}})).get("result") or {}).get("isError"), (
        "a tool that reported isError did not change anything")
    assert len(policy.window) == 1, (
        "an isError result must not spend the window: nothing changed")
    assert dispatch(write(4, 40))["result"]["isError"] is False, "the second write fits"
    out = dispatch(write(5, 40))
    assert "error" not in out, (
        "a policy refusal is an EXECUTION outcome, not a protocol error: the "
        "model must be able to read it, got %r" % (out,))
    assert (out.get("result") or {})["isError"] is True, (
        "a refused call answers an ordinary result with isError true, got %r" % (out,))
    assert "approval" in (out.get("result") or {})["content"][0]["text"], (
        "the refusal's text is the reason, got %r" % ((out.get("result") or {}),))
    assert ran.count("set_quantity") == 2, (
        "the refused call must not reach the tool's fn at all")
    assert policy.refused and (policy.refused[-1].get("call") or {}).get("tool") == "set_quantity", (
        "every refusal is recorded")
    assert (dispatch(request(6, "tools/call", {"name": "report",
                                              "arguments": {}})).get("result") or {}).get("isError") is False, (
        "a read is still served with the window full")

    # -- the audit ----------------------------------------------------------
    assert len(audit.lines) == len(audit.text) == 7, (
        "one line per message, requests and notifications alike: expected 7, "
        "got %d" % len(audit.lines))
    line = audit.lines[0]
    assert set(line) == {"code", "id", "identity", "method", "mutations", "ok"}, (
        "the audit line has exactly these six keys: a clock or a payload copy "
        "creeps in as a seventh, got %r" % (sorted(line),))
    assert line == {"method": "initialize", "id": 1, "ok": True, "code": None,
                    "identity": "user:ana", "mutations": 0}, (
        "the handshake's line shows the identity the call established and no "
        "mutations yet, got %r" % (line,))
    notification_line = audit.lines[1]
    assert notification_line.get("method") == "notifications/initialized", (
        "a notification is audited too, got %r" % (notification_line,))
    assert notification_line.get("ok") is True and notification_line.get("code") is None, (
        "a notification has no answer and did not fail, got %r" % (notification_line,))
    refused_line = audit.lines[5]
    assert refused_line.get("ok") is True and refused_line.get("code") is None, (
        "a refused call is a successful exchange with an isError result: the "
        "audit records what the protocol did, got %r" % (refused_line,))
    assert refused_line.get("mutations") == 2, (
        "the audit's mutation count is the window the session has spent, got %r"
        % (refused_line.get("mutations"),))
    assert any(l.get("identity") == "user:ana" for l in audit.lines[2:]), (
        "every line after the handshake carries the session's identity, got %r"
        % ([l.get("identity") for l in audit.lines],))
    assert audit.text == [json.dumps(l, sort_keys=True, separators=(",", ":"))
                          for l in audit.lines], (
        "the text is the canonical serialization of the line: no clock, no "
        "window state, so the same exchange always produces the same bytes")
    secret = dispatch(request(7, "tools/call", {"name": "report",
                                                "arguments": {"filter": "secret-4f2a"}}))
    assert secret is not None
    assert "secret-4f2a" not in audit.text[-1], (
        "the audit line must never carry the params: an audit that copies "
        "payloads is a second copy of the customer's data in the one place "
        "nobody guards")
    sink_lines = []
    sink_audit = Audit(sink_lines.append)
    sink_audit.record(request(1, "ping"), {"jsonrpc": "2.0", "id": 1, "result": {}},
                      session={"identity": "user:ana"})
    assert sink_lines == sink_audit.text, (
        "the sink receives every line, so an audit can be a file")
    error_line = sink_audit.record(request(2, "nope"),
                                   {"jsonrpc": "2.0", "id": 2,
                                    "error": {"code": -32601, "message": "x"}},
                                   session={"identity": "user:ana"})
    assert error_line.get("ok") is False and error_line.get("code") == -32601, (
        "a failed exchange is audited with its code, got %r" % (error_line,))

    # -- announcing the switch ---------------------------------------------
    before = len(server.notifications)
    announce_tools_changed(server)
    assert server.notifications[-1] == {
        "jsonrpc": "2.0", "method": "notifications/tools/list_changed"}, (
        "the flip and the notification are one operation: a client that cached "
        "tools/list keeps offering the old set until somebody tells it")
    assert len(server.notifications) == before + 1, (
        "exactly one notification per flip, got %r" % (server.notifications,))


STAGES = [
    stage(
        1, file="stage_01.py", title="the envelope, and the four ways to answer it",
        tags=["jsonrpc", "errors"],
        action=("Implement the message builders, decode/encode and Dispatcher: "
                "the RequestId types, the five pinned error codes, and the two "
                "messages that have nobody to answer to."),
        predict=('A client sends {"jsonrpc": "2.0", "id": null, "method": "ping"}: '
                 "what comes back, and with which id?"),
        hints=["an id that cannot be determined is answered with null, and a null "
               "id is not a RequestId",
               "isinstance(True, int) is True in Python, and a boolean id cannot "
               "be matched to a response",
               "a notification is never answered, not even when the method is "
               "unknown: the failure goes in the log, not on the wire"],
        check=check_1, solution="solutions/stage_01.py: Dispatcher.dispatch"),
    stage(
        2, file="stage_02.py", title="the transports: one line, one event, one POST",
        tags=["stdio", "framing"],
        action=("Implement LineTransport, SseWriter and HttpTransport: newline-"
                "delimited frames read from a stream, the SSE event a streamable "
                "server writes, and the POST that answers a notification with 202 "
                "and an empty body."),
        predict=("A tool's fn prints to stdout while the server is running: what "
                 "does the client see, and what should it have seen?"),
        hints=["the server MUST NOT write anything to stdout that is not a valid "
               "MCP message, so a log line is not a message: send it to stderr",
               "a frame may arrive split across chunks, and the tail is not a "
               "message until its newline arrives",
               "a notification has no response, so a POST that carries one is "
               "accepted (202) with nothing to read"],
        check=check_2, solution="solutions/stage_02.py: LineTransport.run"),
    stage(
        3, file="stage_03.py", title="the handshake, and the session it creates",
        tags=["lifecycle", "capabilities"],
        action=("Implement Server: the initialize result with a negotiated "
                "revision and a DERIVED capability table, the gate that refuses "
                "everything before the handshake completes, the session dict, and "
                "the tool table stages 4-9 fill."),
        predict=("A server registers tools/list and resources/subscribe, and the "
                 "client asks for protocolVersion 2024-11-05: what is the answer, "
                 "and is the session initialized?"),
        hints=["capabilities describe what is there: no tools/*, no tools "
               "capability, and a declared capability nothing backs is a bug",
               "the response to initialize does not finish the handshake — only "
               "notifications/initialized does",
               "a client declaring \"elicitation\": {} supports elicitation: the "
               "declaration is the key's presence, not the truthiness of its "
               "options"],
        check=check_3, solution="solutions/stage_03.py: Server.initialize"),
    stage(
        4, file="stage_04.py", title="the tools the model can see",
        tags=["tools", "schemas"],
        action=("Implement Tool, ToolRegistry and text_result: the definition a "
                "model reads, argument validation that answers -32602 with the "
                "tool named, the split between a protocol error and an execution "
                "error, and paging whose last page has no nextCursor at all."),
        predict=("A tool's fn raises KeyError because the vendor is unknown to the "
                 "ERP: -32602, -32603, or isError?"),
        hints=["a schema violation means the call never happened; a failure "
               "inside the tool means it happened and did not work",
               "an unknown tool is an invalid tool for THIS server, which is "
               "-32602 with the tool named, not -32601",
               "a cursor that is not a position you handed out is invalid params, "
               "never a crash and never a silent page 0"],
        check=check_4, solution="solutions/stage_04.py: ToolRegistry.call_tool"),
    stage(
        5, file="stage_05.py", title="resources and prompts, and the not-found splits",
        tags=["resources", "prompts"],
        action=("Implement Resource, Prompt and their registries: contents as a "
                "list, a prompt template that refuses an argument it does not "
                "declare, and the three different 'not found' answers the spec "
                "distinguishes."),
        predict=("A client reads a resource URI the server never published, and "
                 "then gets a prompt name that does not exist: the same code?"),
        hints=["the spec pins -32002 with data.uri for a resource URI, and that "
               "is the only place it is pinned",
               "an unknown prompt name is invalid params (-32602), not a resource "
               "problem: a prompt is not addressable by URI",
               "a required argument the client did not send is a validation "
               "failure, which is -32602 with the argument named"],
        check=check_5, solution="solutions/stage_05.py: ResourceRegistry.read"),
    stage(
        6, file="stage_06.py", title="out of band: subscriptions, progress, cancellation",
        tags=["notifications", "cancellation"],
        action=("Implement Subscriptions, Progress, Cancellations and install: who "
                "hears about an update, a progress token that only moves forward, "
                "and the rule that a cancelled request sends no response at all."),
        predict=("A client cancels request 7 while the tool is running, and the "
                 "handler finishes anyway: what is on the wire?"),
        hints=["the spec says not to send a response for the cancelled request: "
               "-32800 looks helpful and is a message the client cannot match",
               "a notification that arrives after the work finished is ignored, "
               "not an error, because a notification has nobody to answer to",
               "a client MUST NOT cancel initialize, and a server that lets it "
               "happen has a session with no handshake"],
        check=check_6, solution="solutions/stage_06.py: Cancellations.answer_for"),
    stage(
        7, file="stage_07.py", title="read-only first, and the report in the middle",
        tags=["tools", "read-only"],
        action=("Implement Toolset, Reports, make_tools and install: a mutating "
                "tool that is not merely refused but NOT LISTED, a switch that "
                "needs an approver, and one report tool with an allowlist of "
                "report names, filter columns and types."),
        predict=('A caller passes vendor_id = "1 OR 1=1" to the report tool: what '
                 "does the ERP receive?"),
        hints=["a tool the model can see is a tool the model will call: hiding it "
               "is the mechanism, refusing it is the backstop",
               "an unattributed capability flip is how a read-only server becomes "
               "a write server with nobody to blame",
               "the allowlist is the design: column names come from the schema "
               "and values travel as data"],
        check=check_7, solution="solutions/stage_07.py: Toolset.call_tool"),
    stage(
        8, file="stage_08.py", title="idempotency, because the caller will retry",
        tags=["idempotency", "retries"],
        action=("Implement CREATE_ORDER_SCHEMA and Ledger: the key is a required "
                "argument, a retry returns the same bytes and creates nothing, a "
                "key reused for a different request is a client bug, and a "
                "business failure is an outcome that consumes the key."),
        predict=("The vendor was unknown and the tool answered isError: does the "
                 "key still work, and what does the retry do?"),
        hints=["a server-generated key dedupes nothing: the retry brings its own",
               "the fingerprint is the canonical arguments, so a retry that "
               "reorders them is the same request",
               "a validation failure never reached the tool, so there is nothing "
               "to remember"],
        check=check_8, solution="solutions/stage_08.py: Ledger.create_order"),
    stage(
        9, file="stage_09.py", title="the confirmation shows the diff",
        tags=["confirmation", "identity"],
        action=("Implement diff_token, format_diff, Confirmation and install: an "
                "elicitation whose message is the change, an approval that must be "
                "affirmative, a token bound to the diff it was issued for, and an "
                "identity that comes from the session."),
        predict=("A person approved quantity 10 -> 25 a minute ago, and the agent "
                 "now wants 10 -> 250: what happens to that token?"),
        hints=["a dialog that shows the tool call tells a person what the agent "
               "wanted, not what will change",
               "an approval is affirmative or it is a decline: the absence of a "
               "no is not a yes",
               "an identity that travels as a tool argument is a claim the caller "
               "makes about itself"],
        check=check_9, solution="solutions/stage_09.py: Confirmation.require"),
    stage(
        10, file="stage_10.py", title="the trajectory, and the audit line",
        tags=["policy", "audit"],
        action=("Implement impact, SessionPolicy, Audit, announce_tools_changed "
                "and guard: a window of writes with a cap and an aggregate "
                "ceiling, approvals that a later write makes stale, refusals the "
                "model can read, and an audit line with no clock and no payload."),
        predict=("Three approved calls move 40 units each, and the session's "
                 "ceiling is 100: which one is refused, and with what?"),
        hints=["safety is a property of the sequence: three safe calls can compose "
               "into an unsafe batch",
               "a refusal is an execution outcome, so it is an isError result: the "
               "model must read it, and the tool must not have run",
               "an audit that records the payload is a second copy of the "
               "customer's data in the one place nobody guards"],
        check=check_10, solution="solutions/stage_10.py: SessionPolicy.decide"),
]
