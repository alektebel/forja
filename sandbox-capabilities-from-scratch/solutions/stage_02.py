"""stage_02.py — the grant, and the intersection that decides.

Sandbox & Capabilities From Scratch — stage 2: The grant, and the intersection that decides

A tool's declaration is what the tool asks for; a principal's *grant* is what it
is allowed to hand over; and neither one decides a call. The decision is their
intersection, and the answer to "may this tool run" is the *difference* of the
two sets — sorted, named, and returned — because a difference says what was
missing while a boolean can only say no. `effective` is the intersection,
`missing` is what the intersection does not reach, `permits` is the one caller
who has no use for the difference, and `policy_for` assembles the four fields a
later guard decides against. A principal the grants do not name holds `()`, which
is nothing — not "no restriction".

    POLICY_KEYS     the four fields a policy carries, in writing order
    GRANTS ALLOWED ROOTS   the three fixtures a policy is assembled from
    GrantError      a grant, or a policy for a principal, this stage refuses
    grant           a principal's capabilities, as one sorted tuple
    granted         what the grants say a principal holds, or nothing
    effective       the intersection of a tool's demand and a principal's grant
    missing         the part of the demand the grant does not cover, sorted
    permits         whether the grant covers the whole demand
    policy_for      the four policy fields for a principal the fixtures name
"""

from collections.abc import Mapping

import tools

from stage_01 import SandboxError, capability, declares

#: The four fields a policy carries, in the order a policy writes them.
POLICY_KEYS = ("principal", "root", "capabilities", "hosts")

#: The three fixtures a policy is assembled from: what each principal holds, the
#: hosts it may reach and the root it works inside. They are the world's own
#: mappings, never copies, so a policy cannot drift from the fixtures it was
#: assembled out of.
GRANTS = tools.GRANTS
ALLOWED = tools.ALLOWED
ROOTS = tools.ROOTS

#: The distance within which a principal nobody configured is assumed to be a
#: typo for one the fixtures name.
_NEAR = 2


class GrantError(SandboxError):
    """A grant, or a policy for a principal, that this stage refuses."""


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


def _near(name, known):
    """`" (did you mean 'x'?)"` for the closest known name, or `""`."""
    if not isinstance(name, str):
        return ""
    best, best_distance = None, _NEAR + 1
    for candidate in sorted(known):
        distance = _levenshtein(name, candidate)
        if distance < best_distance:
            best, best_distance = candidate, distance
    if best is None or best_distance > _NEAR:
        return ""
    return " (did you mean %r?)" % (best,)


def _capability(name):
    """Stage 1's vocabulary gate, reported as this stage's refusal.

    The vocabulary and the suggestion within two edits are stage 1's
    (`capability`), because two readings of one vocabulary is how a policy
    matches in one stage and not in the next; the *family* is this stage's,
    because a caller who caught a `GrantError` asked stage 2 a question and
    should not have to know where the vocabulary lives.
    """
    try:
        return capability(name)
    except SandboxError as refused:
        raise GrantError(str(refused)) from refused


def _capabilities(raw, what):
    """A grant's capabilities: a sorted, deduplicated tuple of real names."""
    if isinstance(raw, str):
        raise GrantError(
            "%s is the str %r, not a set of capabilities: iterating it would read "
            "one character at a time" % (what, raw))
    if not isinstance(raw, (tuple, list)):
        raise GrantError("%s must be a tuple of capabilities, got %r"
                         % (what, raw))
    granted = []
    for name in raw:
        cap = _capability(name)
        if cap in granted:
            raise GrantError(
                "%s repeats %r: a grant is a set, and a set with a repeat is a "
                "caller who does not know that" % (what, cap))
        granted.append(cap)
    return tuple(sorted(granted))


def _as_granted(raw, principal):
    """What the fixtures say a principal holds, read as one tuple of names."""
    if isinstance(raw, str):
        raise GrantError(
            "the capabilities of %r must be a tuple of capabilities, not the str "
            "%r: iterating it would read one character at a time"
            % (principal, raw))
    if not isinstance(raw, (tuple, list)):
        raise GrantError(
            "the capabilities of %r must be a tuple of capabilities, got %r"
            % (principal, raw))
    return tuple(_capability(name) for name in raw)


def grant(principal, capabilities):
    """A principal's capabilities, as one sorted tuple."""
    if not isinstance(principal, str):
        raise GrantError("a grant's principal must be a str, got %r"
                         % (principal,))
    if not principal.strip():
        raise GrantError("a grant's principal must not be blank, got %r"
                         % (principal,))
    return {"principal": principal,
            "capabilities": _capabilities(capabilities,
                                          "the grant for %r" % (principal,))}


def granted(grants, principal):
    """What the grants say a principal holds, or nothing at all."""
    if not isinstance(grants, Mapping):
        raise GrantError(
            "the grants must be a mapping from a principal to the capabilities it "
            "holds, got %r" % (grants,))
    if not isinstance(principal, str):
        raise GrantError("a principal must be a str, got %r" % (principal,))
    if principal in grants:
        return grants[principal]
    return ()


def missing(grants, principal, tool):
    """The part of a tool's demand the principal's grant does not cover."""
    return tuple(sorted(set(declares(tool)) - set(granted(grants, principal))))


def effective(grants, principal, tool):
    """The capabilities the principal actually handed the tool."""
    return tuple(sorted(set(declares(tool)) & set(granted(grants, principal))))


def permits(grants, principal, tool):
    """Whether the grant covers the whole demand, and nothing more than that."""
    return missing(grants, principal, tool) == ()


def policy_for(principal, *, grants=GRANTS, hosts=ALLOWED, roots=ROOTS):
    """The four policy fields for a principal the three fixtures name."""
    for table, what in ((grants, "grants"), (hosts, "hosts"), (roots, "roots")):
        if not isinstance(table, Mapping):
            raise GrantError(
                "the %s table must be a mapping from a principal to its entry, "
                "got %r" % (what, table))
    known = set(grants) | set(hosts) | set(roots)
    if not isinstance(principal, str) or principal not in known:
        raise GrantError("no such principal: %r%s"
                         % (principal, _near(principal, known)))
    root = roots.get(principal)
    if not isinstance(root, str) or not root.startswith("/"):
        raise GrantError(
            "the root of %r must be a non-empty absolute path, got %r"
            % (principal, root))
    raw_hosts = hosts.get(principal, ())
    if isinstance(raw_hosts, str):
        raise GrantError("the hosts of %r must be a tuple of host specs, not the "
                         "str %r: iterating it would read one character at a time"
                         % (principal, raw_hosts))
    if not isinstance(raw_hosts, (tuple, list)):
        raise GrantError("the hosts of %r must be a tuple of host specs, got %r"
                         % (principal, raw_hosts))
    for spec in raw_hosts:
        if not isinstance(spec, str):
            raise GrantError("the hosts of %r carry %r, which is not a host spec"
                             % (principal, spec))
    return {"principal": principal,
            "root": root,
            "capabilities": _as_granted(grants.get(principal, ()), principal),
            "hosts": raw_hosts}
