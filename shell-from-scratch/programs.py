"""Programs — the ten programs the machine's own process table can become.

Each program is deterministic data: a name, the argv it is normally written
with, a one-line usage, the number of machine steps it costs, and what it does
with its standard input — which the machine itself executes, step by step, so a
pipeline's cost is a number a check can assert and not an approximation.
"""

PROGRAM_NAMES = ("cat", "echo", "env", "false", "grep", "head", "pwd", "sort",
                 "tick", "wc")     # alphabetically sorted, exactly these ten

#: The name, the argv a user usually writes, the usage, the steps it costs, and
#: whether it transforms its input rather than producing from its argv alone.
_PROGRAMS = {
    "cat": {"argv": ("cat",), "usage": "cat",
            "steps": 4, "stream": True},
    "echo": {"argv": ("echo",), "usage": "echo [words]...",
             "steps": 2, "stream": False},
    "env": {"argv": ("env",), "usage": "env",
            "steps": 3, "stream": False},
    "false": {"argv": ("false",), "usage": "false",
              "steps": 1, "stream": False},
    "grep": {"argv": ("grep", "PATTERN"), "usage": "grep PATTERN",
             "steps": 6, "stream": True},
    "head": {"argv": ("head", "-n", "N"), "usage": "head [-n N]",
             "steps": 5, "stream": True},
    "pwd": {"argv": ("pwd",), "usage": "pwd",
            "steps": 2, "stream": False},
    "sort": {"argv": ("sort",), "usage": "sort",
             "steps": 6, "stream": True},
    "tick": {"argv": ("tick", "N"), "usage": "tick [N]",
             "steps": 3, "stream": False},
    "wc": {"argv": ("wc",), "usage": "wc [-l | -c]",
           "steps": 5, "stream": True},
}


def program(name):
    """The record of one program: `{"name", "argv", "usage", "steps", "stdin"}`.

    `steps` is the number of machine steps the program costs, which is the
    number `stage_03.cost_of` sums; `stdin` says whether the program transforms
    what it reads (`True`) or produces from its argv and the machine alone
    (`False`). A name the machine holds no program for is a caller's mistake and
    raises, naming it — because a program that does not exist is a fact about
    the caller's text, and this table is the world's own.
    """
    if not isinstance(name, str) or name not in _PROGRAMS:
        raise ValueError("programs: %r is not a program this machine holds"
                         % (name,))
    spec = _PROGRAMS[name]
    return {"name": name, "argv": spec["argv"], "usage": spec["usage"],
            "steps": spec["steps"], "stdin": spec["stream"]}


def usage_of(name):
    """The one-line usage of `name`, as the machine would print it."""
    if not isinstance(name, str) or name not in _PROGRAMS:
        raise ValueError("programs: %r is not a program this machine holds"
                         % (name,))
    return _PROGRAMS[name]["usage"]
