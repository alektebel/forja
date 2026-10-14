"""stage_04.py — the network policy, and the host nobody can read.

Sandbox & Capabilities From Scratch — stage 4: The network policy, and the host nobody can read

A tool that dials is the one tool whose target is not a path, and the policy that
bounds it is the one place where a `*` is either a decision or a hole. So this
stage fixes what a principal's allowlist *is*: a list of `"host:port"` specs — or
the single spec `"*"` — read one at a time into a `(host, port)` pair, matched
exactly, and answered against the world's own catalogue, because a policy cannot
grant a host that does not exist. Four functions, and one rule underneath all of
them: read what the policy says, do not fold it, and do not default it.

    WILDCARD / HostError   the one spec that means "any host", and this stage's refusal
    parse_host             one spec, read as `(host, port)` or `("*", 0)`
    allows                 the allowlist, exact on the pair, with `*` the one escape
    reachable              allowed *and* in the world's catalogue
    target                 the world's own record for the pair
"""

import tools

from stage_01 import SandboxError

#: The one spec that means "any host the world knows", and the whole of a spec:
#: a `*` mixed with anything else is refused rather than pattern-matched.
WILDCARD = "*"


class HostError(SandboxError):
    """A host spec, an allowlist or a target this stage refuses.

    The refusal names the offender — the spec, the host, the port, the allowlist
    — and the world's own refusal of a pair is carried through this family rather
    than raised raw, so one `except HostError` covers the policy and the world.
    """


def _name(host):
    """A host name this world could answer to, or a refusal that names it.

    Refused rather than folded: this world's host names are lower case and a
    comparison that lower-cases them would match in a check and in production
    would match nothing at all.
    """
    if host != host.lower():
        raise HostError(
            "%r carries an upper-case letter: this world's host names are lower "
            "case and are not folded, so a policy that folded them would match "
            "here and not in production" % (host,))
    return host


def _port(port):
    """A port this world could have: a positive int, and never a bool."""
    if isinstance(port, bool) or not isinstance(port, int):
        raise HostError("a port must be an int, got %r" % (port,))
    if port <= 0:
        raise HostError("a port must be positive, got %r" % (port,))
    return port


def _pair(host, port):
    """A `(host, port)` pair, or a refusal that names the half that is wrong."""
    if not isinstance(host, str):
        raise HostError("a host must be a str, got %r" % (host,))
    if not host:
        raise HostError("a host must be named, got the empty str")
    return (_name(host), _port(port))


def parse_host(spec):
    """One spec, read as a `(host, port)` pair, or `("*", 0)` for the wildcard."""
    if not isinstance(spec, str):
        raise HostError("a host spec must be a str, got %r" % (spec,))
    if not spec:
        raise HostError(
            "an empty host spec is not a policy: name a host and a port, or the "
            "single spec %r" % (WILDCARD,))
    if spec == WILDCARD:
        return (WILDCARD, 0)
    if WILDCARD in spec:
        raise HostError(
            "%r mixes %r with the rest of a spec: a wildcard a reader cannot "
            "evaluate is not a policy, so %r is the whole spec or it is nothing"
            % (spec, WILDCARD, WILDCARD))
    if ":" not in spec:
        raise HostError(
            "%r names no port: a host with no port is a policy with a hole, and "
            "the port is part of the host's identity" % (spec,))
    parts = spec.split(":")
    if len(parts) != 2:
        raise HostError(
            "%r is not a spec this world can read: a spec is 'host:port' or "
            "exactly %r" % (spec, WILDCARD))
    host, text = parts
    if not host:
        raise HostError("%r names no host: a spec is 'host:port'" % (spec,))
    if not text.isascii() or not text.isdigit():
        raise HostError(
            "%r is not a port: a port is a positive int, and the spec %r carries "
            "%r" % (text, spec, text))
    port = int(text)
    if port <= 0:
        raise HostError(
            "%r is not a port: a port is positive, and the spec %r carries %r"
            % (text, spec, text))
    return (_name(host), port)


def _specs(hosts):
    """The allowlist, read whole: every spec parsed, or the first refusal.

    A policy is read the same way by every caller, so a spec that no reader can
    evaluate is refused here rather than skipped quietly at each matching site.
    """
    if isinstance(hosts, str):
        raise HostError(
            "an allowlist must be a sequence of host specs, not the str %r: "
            "iterating it would read one character at a time" % (hosts,))
    if not isinstance(hosts, (tuple, list)):
        raise HostError("an allowlist must be a tuple of host specs, got %r"
                        % (hosts,))
    return tuple(parse_host(spec) for spec in hosts)


def _granted(specs, pair):
    """The allowlist's answer for one pair: exact, with `*` the one escape."""
    for spec in specs:
        if spec[0] == WILDCARD or spec == pair:
            return True
    return False


def _known(pair):
    """Whether the world's own catalogue has this pair — the port included."""
    declared = tools.HOSTS.get(pair[0])
    return declared is not None and declared["port"] == pair[1]


def allows(hosts, host, port):
    """Whether the allowlist grants this exact `(host, port)` pair."""
    return _granted(_specs(hosts), _pair(host, port))


def reachable(wire, hosts, host, port):
    """Whether the pair is both granted and in the world's catalogue.

    `wire` is the world that would dial, carried for identity and never asked: a
    dial is a touch, and a question is not a touch.
    """
    pair = _pair(host, port)
    return _granted(_specs(hosts), pair) and _known(pair)


def target(wire, hosts, host, port):
    """The world's own record for the pair, `{"host", "port", "bytes"}`.

    The allowlist is read whole so that a policy this stage cannot evaluate is
    refused wherever it is read, and the record itself comes from the world: the
    bytes a call touches are the wire's fact, never the policy's.
    """
    pair = _pair(host, port)
    _specs(hosts)
    try:
        return tools.host(pair[0], pair[1])
    except tools.WireError as refused:
        raise HostError(str(refused)) from refused
