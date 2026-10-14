"""stage_08.py — the call that never happens.

The composer, and the first stage that answers a question instead of making one:
a *call* is asked of the six stages below it, in their order, and the first "no"
is the decision. Nothing here re-implements a rule — the catalogue is stage 1's,
the grant is stage 2's `missing`, the jail is stage 3's `jail`, the network is
stage 4's `reachable`, the meter is stage 5's `affordable`, the secret question is
stage 6's `observe`/the vault's and the line is stage 7's `line`/`write_line` —
because a composer that re-decides is a second policy that can disagree with the
first.

The order *is* the design (§3.1): is the tool in the catalogue (`unknown`), does
the grant cover the whole demand (`capability`), does the target resolve inside
the root (`jail`), is the host reachable (`host`), does the meter fit the tool's
cost plus one call (`limit`), does the vault hold the handle (`secret`). The
first question that answers no is the decision, and nothing after it is asked.

A **refusal is raised and a denial is returned**, the course's oldest rule: a
call that is not a mapping, does not name a tool, or names a field that is not a
`str` is a `CallError` (unreadable, the caller's mistake), while `unknown`,
`capability`, `jail`, `host`, `limit` and `secret` are *data* — a denial is a
normal outcome and the run has to keep going.

`invoke` is the order that makes the class worth having: **decide, write the
line, act if allowed**. The line is written for a denial too — the log holds the
intent of a call that never happened — and a denied call never reaches the world
and never charges the meter. The decision also predicts the bytes the act *would*
touch, so the line's `bytes` is knowable before the act; a `stat` is a question
and not a touch, so asking the world how long a file is does not enter its log.
"""

from collections.abc import Mapping

import stage_01 as s1
import stage_02 as s2
import stage_03 as s3
import stage_04 as s4
import stage_05 as s5
import stage_06 as s6
import stage_07 as s7
import tools

#: The five fields a decision carries, in the order a decision writes them.
DECISION_KEYS = ("allowed", "reason", "target", "bytes", "detail")

#: The six fields an observation carries, in the order an observation writes
#: them: what was called, what it acted on, how it was decided, and the act's own
#: answer — `None` for every denial.
OBSERVATION_KEYS = ("tool", "target", "decision", "reason", "bytes", "value")

#: The four fields a policy carries; a mapping without them is not a policy and
#: is not a decision either, so it is a refusal.
_POLICY_KEYS = ("principal", "root", "capabilities", "hosts")

#: The reasons, read from stage 7's own constant so the vocabulary has exactly
#: one home: a composer that re-spelled `"unknown"` would be a second vocabulary
#: that can drift from the one the line is checked against.
(_GRANTED, _UNKNOWN, _CAPABILITY, _JAIL, _HOST, _LIMIT,
 _SECRET) = s7.REASONS

#: The two decisions, read the same way.
_ALLOWED, _DENIED = s7.DECISIONS

#: The kinds whose target is a path and has to resolve inside the root.
_PATH_KINDS = ("path", "process")

#: The port a host name the world does not have is read with, so that its *shape*
#: — a lower-case name, and not the empty one — is stage 4's question before the
#: catalogue is consulted. The number is never used to dial anything.
_UNKNOWN_PORT = 1


class CallError(s1.SandboxError):
    """A call this stage cannot read at all: not a mapping, no tool, or a field
    that is not a `str`. A question the *policy* can answer is a decision, never
    a refusal; this is only for the shapes nothing can be said about."""


def _denial(reason, target, detail):
    """A denial: the reason, the target, no bytes, and the detail that says why."""
    return {"allowed": False, "reason": reason, "target": target, "bytes": 0,
            "detail": dict(detail)}


def _granted(target, count):
    """An allowed decision: `granted`, the target, the predicted bytes."""
    return {"allowed": True, "reason": _GRANTED, "target": target,
            "bytes": count, "detail": {}}


def _call_fields(call):
    """A call's `(tool, target, value)`, or a refusal that names the field.

    A decision is about one call whether that call was just built or was handed
    back by stage 1, so this reads the same three fields either way and defaults
    `target` and `value` the way a call does. What it will not do is guess: a
    `tool`, `target` or `value` that is not a `str` is a call nobody can ask a
    question about, and it is refused by field and by type.
    """
    if not isinstance(call, Mapping):
        raise CallError("a call must be a mapping, got %s"
                        % (type(call).__name__,))
    if "tool" not in call:
        raise CallError("a call must name a tool, got a mapping with %s"
                        % (", ".join(sorted(map(repr, call))) or "no fields",))
    name = call["tool"]
    if not isinstance(name, str):
        raise CallError("a call's 'tool' must be a str, got %s"
                        % (type(name).__name__,))
    target = call.get("target", "")
    if not isinstance(target, str):
        raise CallError("a call's 'target' must be a str, got %s"
                        % (type(target).__name__,))
    value = call.get("value", "")
    if not isinstance(value, str):
        raise CallError("a call's 'value' must be a str, got %s"
                        % (type(value).__name__,))
    return name, target, value


def _policy_fields(policy):
    """The policy itself, or a refusal naming the field it does not carry.

    A decision is read against a principal, a root, a capability set and an
    allowlist; a mapping that does not carry all four is not a policy and no
    question can be asked of it, which makes it a refusal and not a denial.
    """
    if not isinstance(policy, Mapping):
        raise CallError("a policy must be a mapping, got %s"
                        % (type(policy).__name__,))
    for key in _POLICY_KEYS:
        if key not in policy:
            raise CallError("a policy must carry %r, got a mapping with %s"
                            % (key,
                               ", ".join(sorted(map(repr, policy)))
                               or "no fields"))
    return policy


def _host_spec(target):
    """The `host:port` spec a bare host name is read as, for its shape alone.

    A host call's target is the host's *name*; the port is the world's own fact
    about that name. Stage 4's reader reads a `host:port` spec and decides
    whether the name in it is a name this world can read, so the name is read
    with the world's port for it — or, for a name the world does not have, with a
    port that is never dialled, because the name's *shape* is still the first
    question and a lower-case non-empty name is the answer.
    """
    declared = tools.HOSTS.get(target)
    port = declared["port"] if declared is not None else _UNKNOWN_PORT
    return "%s:%d" % (target, port)


def _prediction(name, kind, target, value, vfs):
    """The bytes the act would touch, knowable before the act.

    `0` for a tool whose target is not a byte count: a directory's shape is not
    bytes, what a scripted command will touch is not knowable before it runs, and
    a secret travels as a fingerprint. A `write` is its value's length, which
    needs no question; a `read` or a `remove` of a file that is there is that
    file's own size, asked with `VFS.stat` — a question, not a touch; and a host
    tool is the pair's declared bytes from the world's catalogue.
    """
    if kind == "host":
        return tools.HOSTS[target]["bytes"]
    if kind != "path":
        return 0
    if name == "write_file":
        return len(value)
    if name == "list_dir":
        return 0
    return vfs.stat(target)["bytes"]


def decide(call, policy, *, vfs, wire, meter, vault):
    """§3.1's six questions, in order, and the first "no" is the decision.

    Raises `CallError` for a call nothing can be said about, and returns a fresh
    decision mapping otherwise: `unknown` when the catalogue does not have the
    tool, `capability` when the grant does not cover the whole demand (or the
    demand itself cannot be read — the tool exists and it is its demand that
    cannot be met, so it is never `unknown`), `jail` when the target resolves
    outside the root, `host` when the pair is not reachable, `limit` when the
    meter cannot pay, `secret` when the vault does not hold the handle, and
    `granted` when every answer is yes — with the bytes the act would touch.
    """
    name, target, value = _call_fields(call)
    policy = _policy_fields(policy)

    # 1 — is the tool in the catalogue?
    if name not in tools.TOOLS:
        return _denial(_UNKNOWN, target, {"tool": name})
    declaration = tools.TOOLS[name]
    kind = declaration["target_kind"]
    if kind == "none" and target:
        raise CallError(
            "%r acts on nothing: a target on it is a field the kind does not "
            "carry, got %r" % (name, target))

    principal = policy["principal"]

    # 2 — does the principal's grant cover the whole demand? A declaration this
    # world cannot read (`teleport` demands `fs:teleport`) is a demand that
    # cannot be met, so it is `capability` and never `unknown`.
    grants = {principal: tuple(policy["capabilities"])}
    try:
        absent = s2.missing(grants, principal, declaration)
    except s1.SandboxError as refused:
        return _denial(_CAPABILITY, target, {"unreadable": str(refused)})
    if absent:
        return _denial(_CAPABILITY, target, {"missing": absent})

    # 3 — does the target resolve inside the root? A `path`/`process` tool is
    # jailed on its resolved path, and a jail that is a string test is caught
    # here because the decision is made against what it resolved to.
    if kind in _PATH_KINDS:
        try:
            target = s3.jail(policy["root"], target)
        except s3.JailError:
            raised = target
            try:
                shown = s3.resolve(policy["root"], target)
            except s3.JailError:
                shown = raised
            return _denial(_JAIL, shown,
                           {"target": raised, "root": policy["root"]})

    # 4 — is the host reachable on that port? The name's shape is a refusal (a
    # name this world would fold or never read), the catalogue's absence and the
    # policy's refusal are denials.
    if kind == "host":
        try:
            s4.parse_host(_host_spec(target))
        except s4.HostError as refused:
            raise CallError(
                "the call's target %r is not a host name this world can read: %s"
                % (target, refused)) from refused
        if target not in tools.HOSTS:
            return _denial(_HOST, target,
                           {"host": target, "known": tuple(sorted(tools.HOSTS))})
        port = tools.HOSTS[target]["port"]
        if not s4.reachable(wire, tuple(policy["hosts"]), target, port):
            return _denial(_HOST, target,
                           {"host": target, "specs": tuple(policy["hosts"]),
                            "wildcard": "*" in policy["hosts"]})

    # 5 — does the meter fit the tool's cost plus one call? A question; the
    # charge happens at act time, never here.
    fits = s5.affordable(meter, declaration)
    if not fits["allowed"]:
        return _denial(_LIMIT, target, {"short": tuple(fits["short"])})

    # 6 — for a tool whose target is a handle, does the vault hold it? Asked with
    # `holds`, which is a question, so a refusal enters no record. `env_dump`
    # carries no target and asks nobody.
    if kind == "secret" and not vault.holds(target):
        return _denial(_SECRET, target, {"handle": target})

    return _granted(target, _prediction(name, kind, target, value, vfs))


def _tick(guard):
    """The tick the line is stamped with: the clock's, or the line count."""
    if guard.clock is not None:
        return guard.clock()
    return len(guard.audit.lines())


def _observation(name, decision, value):
    """The frozen six-key observation: the denial carries the reason and nothing
    else, which is why `value` is `None` for every denial."""
    return {"tool": name, "target": decision["target"],
            "decision": _ALLOWED if decision["allowed"] else _DENIED,
            "reason": decision["reason"], "bytes": decision["bytes"],
            "value": value}


def _act(guard, call, declaration, target):
    """The world's own act, by `target_kind`, through the world's own records."""
    name = call["tool"]
    kind = declaration["target_kind"]
    if kind == "path":
        if name == "write_file":
            return guard.vfs.write(target, call["value"])
        if name == "remove_file":
            return guard.vfs.remove(target)
        if name == "list_dir":
            return guard.vfs.list(target)
        return guard.vfs.read(target)
    if kind == "host":
        return guard.wire.dial(target, tools.HOSTS[target]["port"])
    if kind == "process":
        return tools.run_shell(guard.vfs, guard.wire, call["value"], cwd=target)
    if kind == "secret":
        return s6.observe(guard.vault, target)
    if kind == "none":
        return tuple(s6.observe(guard.vault, handle)
                     for handle in guard.vault.handles())
    raise CallError("no such target kind: %r" % (kind,))


def invoke(guard, call):
    """Decide, write the line, then act if allowed — in that order, always.

    The line is written for a denial too, so the log holds the intent of a call
    that never happened; a denial stops here, returns an observation whose
    `value` is `None`, and touches nothing and spends nothing. An allowed call
    charges the meter once, all or nothing, *before* the work, and then the act
    happens through the world. A *world* refusal — a missing file, an unknown
    shell command — propagates as its own error: it is a broken script, not a
    decision, and the line already says the call was allowed.
    """
    decision = decide(call, guard.policy, vfs=guard.vfs, wire=guard.wire,
                      meter=guard.meter, vault=guard.vault)
    tick = _tick(guard)
    entry = {"tick": tick, "principal": guard.policy["principal"],
             "tool": call["tool"], "target": decision["target"],
             "decision": _ALLOWED if decision["allowed"] else _DENIED,
             "reason": decision["reason"], "bytes": decision["bytes"]}
    s7.write_line(guard.audit, entry)
    if not decision["allowed"]:
        return _observation(call["tool"], decision, None)
    declaration = tools.TOOLS[call["tool"]]
    s5.charge(guard.meter, declaration["cost"])
    value = _act(guard, call, declaration, decision["target"])
    return _observation(call["tool"], decision, value)


class Guard:
    """A policy and the world it decides against, with the line written first.

    The guard owns nothing but the four fixtures and the sink: the decision is
    stage 1–6's, the line is stage 7's, and `invoke` is the order that puts them
    together. `clock` is an optional zero-argument callable returning the tick to
    stamp; `None` stamps the line count, so a guard with no clock writes a line
    per call and numbers them that way.
    """

    def __init__(self, policy, *, vfs, wire, vault, meter, audit, clock=None):
        self.policy = policy
        self.vfs = vfs
        self.wire = wire
        self.vault = vault
        self.meter = meter
        self.audit = audit
        self.clock = clock

    def decide(self, call):
        """§3.1's six questions, in order, against this guard's world."""
        return decide(call, self.policy, vfs=self.vfs, wire=self.wire,
                      meter=self.meter, vault=self.vault)

    def invoke(self, call):
        """Decide, write the line, then act if allowed — through the world."""
        return invoke(self, call)

    def __repr__(self):
        return "<Guard %r %d capability(ies), %d line(s)>" % (
            self.policy.get("principal", "?"),
            len(tuple(self.policy.get("capabilities", ()))),
            len(self.audit.lines()))
