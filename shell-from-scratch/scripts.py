"""Shell From Scratch — the world's own fixture sessions, and the answer key.

The eight sessions a replay must agree with byte for byte and number for
number. Each one is a name, the lines the shell reads, and the record the
session must answer on a fresh machine: the bytes on the terminal, the status,
every command's `(index, status, kind)` in order, how many processes it
spawned, the signal names it sent, the job table's rows at the end and how
many deadlocks the machine recorded — `SESSION_KEYS`, which is the shape
`stage_09.run_session` answers, so the acceptance is a comparison and not a
judgement call.

The eight cover what the course must see at least once: a plain pipeline, a
redirection set applied in order, a background job plus a wait, a trap firing
on a signalled job, `set -e` stopping a session, a glob answered in sorted
order, a here-document carried inside one line, and a deadlock on purpose (a
stopped writer whose reader waits forever — the machine records it, the wait
reports it, and nothing raises).

The answer key holds no judgement the machine did not make: `stdout` is the
terminal's delta, `children` the spawn ledger's delta, `signals` the
transcript's own `signal` calls, `deadlocks` the machine's own count. A
fixture the world cannot justify is not in this file.
"""

SESSION_NAMES = ("background", "deadlock", "errexit", "glob", "heredoc",
                 "pipeline", "redirect", "signal")

_SESSIONS = {
    "background":
        (("echo hi &", "wait"),
         {"name": "background", "stdout": b"hi\n", "status": 0,
          "statuses": ((0, 0, "plain"), (1, 0, "plain")), "children": 1,
          "signals": (),
          "jobs": ({"job": 1, "pid": 1, "state": "done", "status": 0,
                    "command": "echo hi"},),
          "deadlocks": 0}),
    "deadlock":
        (("tick 5 | cat &", "kill -STOP 1", "wait %1"),
         {"name": "deadlock", "stdout": b"", "status": 1,
          "statuses": ((0, 0, "pipeline-but-last"), (1, 0, "plain"),
                       (2, 0, "plain"), (3, 1, "plain")),
          "children": 2, "signals": ("STOP",),
          "jobs": ({"job": 1, "pid": 2, "state": "running", "status": None,
                    "command": "tick 5 | cat"},),
          "deadlocks": 1}),
    "errexit":
        (("set -e", "false", "echo hi"),
         {"name": "errexit", "stdout": b"", "status": 1,
          "statuses": ((0, 0, "plain"), (1, 1, "plain")), "children": 1,
          "signals": (), "jobs": (), "deadlocks": 0}),
    "glob":
        (("echo /home/*",),
         {"name": "glob",
          "stdout": b"/home/.hidden /home/notes.txt /home/readme.txt "
                    b"/home/z-a.txt\n",
          "status": 0, "statuses": ((0, 0, "plain"),), "children": 1,
          "signals": (), "jobs": (), "deadlocks": 0}),
    "heredoc":
        (("cat << EOF\none\ntwo\nEOF",),
         {"name": "heredoc", "stdout": b"one\ntwo\n", "status": 0,
          "statuses": ((0, 0, "plain"),), "children": 1, "signals": (),
          "jobs": (), "deadlocks": 0}),
    "pipeline":
        (("echo hi | cat",),
         {"name": "pipeline", "stdout": b"hi\n", "status": 0,
          "statuses": ((0, 0, "pipeline-but-last"), (1, 0, "plain")),
          "children": 2, "signals": (), "jobs": (), "deadlocks": 0}),
    "redirect":
        (("echo one > /home/out.txt", "cat /home/out.txt"),
         {"name": "redirect", "stdout": b"one\n", "status": 0,
          "statuses": ((0, 0, "plain"), (1, 0, "plain")), "children": 2,
          "signals": (), "jobs": (), "deadlocks": 0}),
    "signal":
        (("trap 'echo done' TERM", "tick 5 &", "kill -TERM %1"),
         {"name": "signal", "stdout": b"done\n", "status": 143,
          "statuses": ((0, 0, "plain"), (1, 0, "plain"), (2, 143, "plain")),
          "children": 2, "signals": ("TERM",),
          "jobs": ({"job": 1, "pid": 2, "state": "done", "status": 143,
                    "command": "tick 5"},),
          "deadlocks": 0}),
}


def names():
    """The fixture sessions' names, sorted."""
    return SESSION_NAMES


def session(name):
    """The fixture `name` names: `{"name", "lines", "expected"}`, or a refusal."""
    if not isinstance(name, str) or name not in _SESSIONS:
        raise ValueError("scripts: %r is not a session this world holds; its "
                         "sessions are %s" % (name, ", ".join(SESSION_NAMES)))
    lines, expected = _SESSIONS[name]
    return {"name": name, "lines": lines, "expected": expected}
