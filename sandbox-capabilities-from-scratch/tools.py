"""tools.py — the environment an agent acts in, PROVIDED COMPLETE.

An agent's power is whatever its tools can do, so this module is the thing the
course has to *bound*: a catalogue of tools that each declare the capabilities
they need, what one call costs, and what kind of thing they act on; five hosts
that answer; three secrets; the principals' grants, roots and allowed hosts as
plain data; and the five raw plans a run is drawn from.

There are four objects here that *do* something, and each of them keeps its own
record of what it was asked to do:

    Meter   the counters a call spends: cpu, memory, ticks, calls. Its `spend()`
            is raw and does not check anything — a counter may read past its
            limit, because a meter that policed itself would be stage 5's answer.
    Wire    the modelled network. `dial()` refuses a host or port it has never
            heard of and records every dial it did make.
    Vault   the secrets. `read()` hands over any value on request and records
            every handle it was asked for, because the world is not the policy
            engine: keeping a value out of the model's hands is the course's job.
    Audit   the sink the course writes its audit lines into.

`VFS` is the fifth actor and lives in `vfs.py`; this module imports nothing from
there, so the two can be read in either order.

Everything else is data: `TOOLS`, `HOSTS`, `SECRETS`, `PLANS`, `GRANTS`,
`ALLOWED`, `ROOTS` and `SHELLS` are read-only mappings of plain dictionaries, and
the accessors (`tool`, `call`, `plan`, `host`, `secret`) hand back fresh mutable
copies so a check can bend a fixture without bending the course.

The names this module owns:

    CAPABILITIES     what a tool may demand: six names, and no others
    COST_KEYS        what one call spends: cpu, memory, ticks
    LIMIT_KEYS       what a meter counts: cpu, memory, ticks, calls
    TARGET_KINDS     what a tool acts on: a path, a host, a process, or nothing
    TOOL_KEYS        the fields of a tool declaration
    CALL_KEYS        the fields of a call
    DEFAULT_LIMITS   the counters a fresh Meter starts with
    TOOLS HOSTS SECRETS PLANS GRANTS ALLOWED ROOTS SHELLS
    Meter Wire Vault Audit
    ToolError WireError VaultError
    tool call plan host secret run_shell

Nothing here checks a permission, judges a path against a root, or writes an
audit line — that is the course.
"""

from collections.abc import Mapping
from types import MappingProxyType

#: Every capability a tool in this world may demand. A tool demanding anything
#: else (see `teleport` below) is a declaration this world does not know how to
#: grant, and the course refuses it rather than inventing a meaning for it.
CAPABILITIES = (
    "fs:read",
    "fs:write",
    "fs:delete",
    "net:connect",
    "proc:spawn",
    "secret:read",
)

#: What one call spends. Every cost declares all three, and a counter left out is
#: a counter nobody counted.
COST_KEYS = ("cpu", "memory", "ticks")

#: What a meter counts: the three a call spends, plus the call itself.
LIMIT_KEYS = ("cpu", "memory", "ticks", "calls")

#: What kind of thing a tool acts on. Four kinds carry a target — a path, a host,
#: a process (whose target is the directory it runs in) and a secret (whose
#: target is the handle) — and one carries none. A tool with a target the kind
#: does not carry, and a tool with no target at all, are two different mistakes.
TARGET_KINDS = ("path", "host", "process", "secret", "none")

#: The fields of a tool declaration.
TOOL_KEYS = ("name", "description", "capabilities", "cost", "target_kind")

#: The fields of a call.
CALL_KEYS = ("tool", "target", "value")

#: The counters a fresh `Meter` starts with: generous enough that a plan of a few
#: calls never stops for a limit nobody asked about, small enough that one plan
#: meets the wall.
DEFAULT_LIMITS = {"cpu": 64, "memory": 65536, "ticks": 32, "calls": 8}

#: The distance within which a name the world does not have is assumed to be a
#: typo for one it does — the same rule the course's stages use.
_NEAR = 2


class ToolError(ValueError):
    """Something about a tool, a call, a plan or an accessor is not usable."""


class WireError(ToolError):
    """A dial this world cannot make: a host or a port it has never heard of."""


class VaultError(ToolError):
    """A secret this world does not hold."""


def _near(name, known):
    """The known name closest to `name`, if one is close enough to be a typo."""
    best = None
    best_distance = _NEAR + 1
    for candidate in sorted(known):
        distance = _levenshtein(name, candidate)
        if distance < best_distance:
            best, best_distance = candidate, distance
    if best is None or best_distance > _NEAR:
        return ""
    return " (did you mean %r?)" % (best,)


def _levenshtein(left, right):
    """The edit distance between two short names, the plain way."""
    if left == right:
        return 0
    previous = list(range(len(right) + 1))
    for i, lchar in enumerate(left, 1):
        current = [i]
        for j, rchar in enumerate(right, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (0 if lchar == rchar else 1),
            ))
        previous = current
    return previous[-1]


def _counters(value, keys, what):
    """The counters in `value`, refusing anything that is not one.

    Accepts a mapping with every key in `keys` or `None` for "nothing", and
    refuses a value that is not a non-negative int per key — a bool is not a
    counter, and neither is a float, however much Python would like it to be.
    """
    if value is None:
        return dict.fromkeys(keys, 0)
    if not isinstance(value, Mapping):
        raise ToolError("%s must be a mapping of %s, got %r"
                        % (what, "/".join(keys), type(value).__name__))
    for key in value:
        if key not in keys:
            raise ToolError("%s has no counter %r%s"
                            % (what, key, _near(key, keys)))
    out = {}
    for key in keys:
        number = value.get(key, 0)
        if isinstance(number, bool) or not isinstance(number, int):
            raise ToolError("%s: %r must be an int, got %r"
                            % (what, key, number))
        if number < 0:
            raise ToolError("%s: %r must not be negative, got %r"
                            % (what, key, number))
        out[key] = number
    return out


# ---------------------------------------------------------------------------
# The catalogue
# ---------------------------------------------------------------------------

_RAW_TOOLS = {
    "read_file": {
        "description": "read one file from the workspace",
        "capabilities": ("fs:read",),
        "cost": {"cpu": 1, "memory": 0, "ticks": 1},
        "target_kind": "path",
    },
    "list_dir": {
        "description": "list the entries of one directory",
        "capabilities": ("fs:read",),
        "cost": {"cpu": 1, "memory": 0, "ticks": 1},
        "target_kind": "path",
    },
    "write_file": {
        "description": "write a file, creating it if it is not there",
        "capabilities": ("fs:write",),
        "cost": {"cpu": 2, "memory": 64, "ticks": 2},
        "target_kind": "path",
    },
    "remove_file": {
        "description": "delete one file",
        "capabilities": ("fs:delete",),
        "cost": {"cpu": 2, "memory": 0, "ticks": 1},
        "target_kind": "path",
    },
    "http_get": {
        "description": "fetch a path from an internal host",
        "capabilities": ("net:connect",),
        "cost": {"cpu": 1, "memory": 0, "ticks": 2},
        "target_kind": "host",
    },
    "shell": {
        "description": "run one scripted command in the workspace",
        "capabilities": ("proc:spawn",),
        "cost": {"cpu": 4, "memory": 4096, "ticks": 3},
        "target_kind": "process",
    },
    "get_secret": {
        "description": "read one secret, by handle",
        "capabilities": ("secret:read",),
        "cost": {"cpu": 1, "memory": 0, "ticks": 1},
        "target_kind": "secret",
    },
    "env_dump": {
        "description": "dump this process's environment, every secret included",
        "capabilities": ("secret:read",),
        "cost": {"cpu": 2, "memory": 64, "ticks": 1},
        "target_kind": "none",
    },
    "debug_dump": {
        "description": "write a diagnostic file and post it upstream",
        "capabilities": ("fs:read", "net:connect"),
        "cost": {"cpu": 2, "memory": 128, "ticks": 2},
        "target_kind": "path",
    },
    "teleport": {
        "description": "move a file without reading it (demands a capability this world does not have)",
        "capabilities": ("fs:teleport",),
        "cost": {"cpu": 3, "memory": 0, "ticks": 1},
        "target_kind": "path",
    },
}

#: Every tool this world has, by name. Each entry carries all of `TOOL_KEYS`.
TOOLS = MappingProxyType({
    name: dict({"name": name}, **fields) for name, fields in _RAW_TOOLS.items()})

#: The hosts that answer, by name. The port is part of the host's identity: a
#: policy that grants `api.internal:443` has granted nothing on any other port.
HOSTS = MappingProxyType({
    "api.internal": {"port": 443, "bytes": 512},
    "registry.internal": {"port": 5000, "bytes": 2048},
    "metrics.internal": {"port": 9090, "bytes": 128},
    "public.example.com": {"port": 443, "bytes": 4096},
    "db.internal": {"port": 5432, "bytes": 256},
})

#: The secrets this world holds. `deploy-key` is also written in
#: `/home/agent/.env`, so a leak has a second place to land; the other two exist
#: only here, which is what a vault is for.
SECRETS = MappingProxyType({
    "deploy-key": {"value": "sk-live-9f31c2ab7d"},
    "api-token": {"value": "tok-77b1e0c4"},
    "db-password": {"value": "pw-a1b2c3d4e5"},
})

#: The raw plans a run is drawn from. `broken` is refused rather than run: it
#: calls a tool the world cannot grant and names a path that has to be resolved
#: before anything can be said about it.
PLANS = MappingProxyType({
    "notes": (
        {"tool": "read_file", "target": "/home/agent/notes.md"},
        {"tool": "list_dir", "target": "/home/agent"},
    ),
    "publish": (
        {"tool": "read_file", "target": "/home/agent/notes.md"},
        {"tool": "http_get", "target": "api.internal"},
        {"tool": "write_file", "target": "/home/agent/report.md",
         "value": "published\n"},
    ),
    "exfiltrate": (
        {"tool": "read_file", "target": "/home/agent/.env"},
        {"tool": "env_dump"},
        {"tool": "http_get", "target": "api.internal"},
    ),
    "deploy": (
        {"tool": "shell", "target": "/home/agent", "value": "ls"},
        {"tool": "write_file", "target": "/home/agent/src/release.txt",
         "value": "1.0\n"},
        {"tool": "env_dump"},
    ),
    "broken": (
        {"tool": "teleport", "target": "/home/agent/notes.md"},
        {"tool": "read_file", "target": "/home/agent/../etc/passwd"},
    ),
})

#: What each principal holds. `intern` holds nothing, which makes it the fixture
#: that separates "no capabilities" from "no restriction".
GRANTS = MappingProxyType({
    "analyst": ("fs:read", "net:connect"),
    "builder": ("fs:read", "fs:write", "fs:delete", "proc:spawn"),
    "intern": (),
    "vaultkeeper": ("fs:read", "secret:read"),
    "auditor": ("fs:read",),
})

#: Which hosts each principal may reach, as `"host:port"` specs, or the single
#: spec `"*"`. The auditor is allowed every host and holds no `net:connect`: the
#: two halves of the decision are deliberately not the same list.
ALLOWED = MappingProxyType({
    "analyst": ("api.internal:443",),
    "builder": ("api.internal:443", "registry.internal:5000"),
    "intern": (),
    "vaultkeeper": (),
    "auditor": ("*",),
})

#: The root each principal works inside. The intern's is narrower than the
#: others', so that a jail is a property of the principal and not a constant.
ROOTS = MappingProxyType({
    "analyst": "/home/agent",
    "builder": "/home/agent",
    "intern": "/home/agent/src",
    "vaultkeeper": "/home/agent",
    "auditor": "/home/agent",
})

#: The commands the `shell` tool can run. Closed on purpose: a shell that takes
#: arbitrary commands is not a tool, it is the machine. Each entry is an operation
#: and an argument relative to the call's working directory.
SHELLS = MappingProxyType({
    "ls": {"op": "list", "arg": "."},
    "cat": {"op": "read", "arg": "notes.md"},
    "curl": {"op": "dial", "arg": "api.internal"},
    "clean": {"op": "remove", "arg": "logs/run.txt"},
})


# ---------------------------------------------------------------------------
# The accessors
# ---------------------------------------------------------------------------

def _pick(table, name, what, error=ToolError):
    if not isinstance(name, str):
        raise error("a %s name must be a str, got %r" % (what, name))
    if name not in table:
        raise error("no such %s: %r%s" % (what, name, _near(name, table)))
    return name


def tool(name, **overrides):
    """A fresh, mutable declaration for a tool in the catalogue.

    Unknown ids are refused by name, and unknown fields are refused too: a check
    that misspells `target_kind` is a check that is no longer checking anything.
    """
    _pick(TOOLS, name, "tool")
    fields = dict(TOOLS[name])
    for key, value in overrides.items():
        if key not in TOOL_KEYS:
            raise ToolError("%r is not a field of a tool%s"
                            % (key, _near(key, TOOL_KEYS)))
        fields[key] = value
    return fields


def call(name, target="", value=""):
    """A fresh call of the named tool, with its target and its value."""
    return {"tool": name, "target": target, "value": value}


def plan(name, *calls):
    """A fresh list of call dicts: a named plan, or one built call by call.

    `plan("notes")` copies the fixture; `plan("notes", call("list_dir",
    "/home/agent"))` copies it and appends. The fixture is never handed out, so a
    stage that bends a plan does not bend the next check.
    """
    _pick(PLANS, name, "plan")
    out = [dict(entry) for entry in PLANS[name]]
    for extra in calls:
        if not isinstance(extra, Mapping):
            raise ToolError("a call must be a mapping, got %r" % (extra,))
        out.append(dict(extra))
    return out


def host(name, port=None):
    """A fresh record for a host the world has, `{"host", "port", "bytes"}`."""
    _pick(HOSTS, name, "host", WireError)
    declared = HOSTS[name]
    if port is None:
        port = declared["port"]
    if port != declared["port"]:
        raise WireError("no such host: %r on port %r (this world has it on %r)"
                        % (name, port, declared["port"]))
    return {"host": name, "port": port, "bytes": declared["bytes"]}


def secret(handle, **overrides):
    """A fresh, mutable record for a secret, `{"handle", "value"}`."""
    _pick(SECRETS, handle, "secret")
    fields = {"handle": handle, "value": SECRETS[handle]["value"]}
    for key, value in overrides.items():
        if key not in ("handle", "value"):
            raise ToolError("%r is not a field of a secret%s"
                            % (key, _near(key, ("handle", "value"))))
        fields[key] = value
    return fields


def run_shell(vfs, wire, command, *, cwd):
    """Run one scripted command in the world, and report what it touched.

    The command must be one of `SHELLS` and the working directory must be an
    absolute path with no empty, `.` or `..` component; the argument is joined
    onto it the same way, so a scripted command can never walk out of the
    directory it was given. The operation goes through the filesystem or the
    wire, which means it lands in *their* records, and the returned mapping says
    what happened: `{"command", "op", "target", "bytes"}`.
    """
    if not isinstance(command, str) or command not in SHELLS:
        raise ToolError("no such command: %r%s"
                        % (command, _near(str(command), SHELLS)))
    spec = SHELLS[command]
    cwd = _require_cwd(cwd)
    op, arg = spec["op"], spec["arg"]
    if op == "dial":
        port = HOSTS[arg]["port"] if arg in HOSTS else 0
        record = wire.dial(arg, port)
        return {"command": command, "op": op, "target": record["host"],
                "bytes": record["bytes"]}
    if op == "list":
        entries = vfs.list(cwd)
        return {"command": command, "op": op, "target": cwd,
                "bytes": len(entries)}
    path = _join(cwd, arg)
    if op == "read":
        text = vfs.read(path)
        return {"command": command, "op": op, "target": path,
                "bytes": len(text)}
    if op == "remove":
        length = vfs.remove(path)
        return {"command": command, "op": op, "target": path, "bytes": length}
    raise ToolError("the command %r carries an operation this world cannot run: %r"
                    % (command, op))


def _require_cwd(cwd):
    if not isinstance(cwd, str) or not cwd.startswith("/"):
        raise ToolError("a working directory must be an absolute path, got %r"
                        % (cwd,))
    for part in cwd.split("/")[1:]:
        if part == "" and cwd != "/":
            raise ToolError(
                "a working directory must not carry an empty component, got %r"
                % (cwd,))
        if part in (".", ".."):
            raise ToolError(
                "a working directory with a %r component reached the shell "
                "unresolved: %r" % (part, cwd))
    return cwd


def _join(cwd, arg):
    if not isinstance(arg, str) or not arg or arg.startswith("/"):
        raise ToolError("a shell argument must be a relative path, got %r"
                        % (arg,))
    for part in arg.split("/"):
        if part in ("", ".", ".."):
            raise ToolError(
                "a shell argument with a %r component reached the shell "
                "unresolved: %r" % (part, arg))
    return cwd.rstrip("/") + "/" + arg


# ---------------------------------------------------------------------------
# The objects that do something
# ---------------------------------------------------------------------------

class Meter:
    """The counters a call spends: cpu, memory, ticks and the calls themselves.

    A meter counts; it does not judge. `spend()` adds whatever it is given, so a
    caller can spend past a limit and *see* it in `used()` — deciding whether a
    cost fits, and charging all or nothing, is the course's job. `left()` is the
    other side of that: a reading, floored at zero, per counter or for one of
    them by name.
    """

    def __init__(self, limits=None):
        if limits is None:
            limits = DEFAULT_LIMITS
        self.limits = _counters(limits, LIMIT_KEYS, "limits")
        self._spent = dict.fromkeys(LIMIT_KEYS, 0)

    def left(self, name=None):
        """What is left, floored at zero: one counter by name, or all of them."""
        if name is not None:
            if name not in LIMIT_KEYS:
                raise ToolError("no such counter: %r%s"
                                % (name, _near(name, LIMIT_KEYS)))
            return max(0, self.limits[name] - self._spent[name])
        return {key: max(0, self.limits[key] - self._spent[key])
                for key in LIMIT_KEYS}

    def spend(self, cost, *, calls=1):
        """Add a cost (and a number of calls) to the counters. Raw on purpose."""
        if isinstance(calls, bool) or not isinstance(calls, int) or calls < 0:
            raise ToolError("calls must be a non-negative int, got %r" % (calls,))
        spent = _counters(cost, COST_KEYS, "cost")
        for key in COST_KEYS:
            self._spent[key] += spent[key]
        self._spent["calls"] += calls
        return dict(self._spent)

    def used(self):
        """A copy of what has been spent, so far."""
        return dict(self._spent)

    def __repr__(self):
        return "<Meter calls %d/%d cpu %d/%d>" % (
            self._spent["calls"], self.limits["calls"],
            self._spent["cpu"], self.limits["cpu"])


class Wire:
    """The modelled network: a dial per host and port, and a record of each.

    `dial()` refuses a host or a port this world has never heard of, naming both,
    and it records every dial it *did* make in `dialled()`, in order. It does not
    know who is allowed to dial what: that is the policy's job.
    """

    def __init__(self, hosts=None):
        source = HOSTS if hosts is None else hosts
        self._hosts = {}
        for name, fields in source.items():
            if name not in HOSTS:
                raise WireError("no such host: %r%s" % (name, _near(name, HOSTS)))
            self._hosts[name] = {"port": fields["port"], "bytes": fields["bytes"]}
        self._dialled = []

    def dial(self, host, port):
        """Dial a host on a port the world has, and return what it answered."""
        _pick(self._hosts, host, "host", WireError)
        declared = self._hosts[host]
        if port != declared["port"]:
            raise WireError("no such host: %r on port %r (this world has it on %r)"
                            % (host, port, declared["port"]))
        self._dialled.append((host, port))
        return {"host": host, "port": port, "bytes": declared["bytes"]}

    def dialled(self):
        """Every dial this wire made, in order, as `(host, port)` pairs."""
        return tuple(self._dialled)

    def __repr__(self):
        return "<Wire %d host(s), %d dial(s)>" % (
            len(self._hosts), len(self._dialled))


class Vault:
    """The secrets, and every handle it was asked for.

    `read()` hands over the value on request and records the handle: a vault
    cannot keep a value out of the model's hands, because a vault is a cupboard
    with a log book and not a policy. `meta()` is what a caller may look at
    without reading: the handle and the value's length, never the value.
    """

    def __init__(self, secrets=None):
        source = SECRETS if secrets is None else secrets
        self._secrets = {}
        for handle, fields in source.items():
            if not isinstance(handle, str):
                raise VaultError("a handle must be a str, got %r" % (handle,))
            value = fields["value"] if isinstance(fields, Mapping) else fields
            if not isinstance(value, str):
                raise VaultError("the value of %r must be a str, got %r"
                                 % (handle, value))
            self._secrets[handle] = value
        self._reads = []

    def holds(self, handle):
        """Is there a secret under this handle?"""
        if not isinstance(handle, str):
            raise VaultError("a handle must be a str, got %r" % (handle,))
        return handle in self._secrets

    def read(self, handle):
        """The value, recorded: this is the only way a value leaves the vault."""
        _pick(self._secrets, handle, "secret", VaultError)
        self._reads.append(handle)
        return self._secrets[handle]

    def meta(self, handle):
        """`{"handle", "bytes"}` — everything about a value except the value."""
        _pick(self._secrets, handle, "secret", VaultError)
        return {"handle": handle, "bytes": len(self._secrets[handle])}

    def reads(self):
        """Every handle this vault was asked to read, in order."""
        return tuple(self._reads)

    def handles(self):
        """Every handle this vault holds, sorted."""
        return tuple(sorted(self._secrets))

    def __repr__(self):
        return "<Vault %d secret(s), %d read(s)>" % (
            len(self._secrets), len(self._reads))


class Audit:
    """The sink audit lines are written into: text in, text out, in order.

    It holds strings and knows nothing about their shape — the course's stages
    decide what a line is, and `record()` accepts whatever it is handed so that a
    malformed line is the course's own bug to catch rather than the world's to
    refuse.
    """

    def __init__(self):
        self._lines = []

    def record(self, text):
        """Append one line, and return how many lines are now in the sink."""
        if not isinstance(text, str):
            raise ToolError("an audit line must be a str, got %r" % (text,))
        self._lines.append(text)
        return len(self._lines)

    def lines(self):
        """Every line, in the order it was written."""
        return tuple(self._lines)

    def text(self):
        """The whole sink as one string, one line per line, newline-terminated."""
        return "".join(line + "\n" for line in self._lines)

    def __repr__(self):
        return "<Audit %d line(s)>" % (len(self._lines),)
