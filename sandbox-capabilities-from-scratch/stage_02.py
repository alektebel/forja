"""Sandbox & Capabilities From Scratch — stage 2: The grant, and the intersection that decides.

A tool's declaration is what the tool asks for. A principal's **grant** is what
that principal is allowed to hand over. Neither one decides a call: the decision
is their intersection, and the answer to "may this tool run" is the *difference*
of the two sets — sorted, named, and returned as data. So this stage fixes three
things and refuses to blur them: a grant is a value (a principal and what it
holds), the intersection is the decision (`effective`, `missing`, `permits`), and
a policy is the four fields a later guard decides against — who the principal is,
the root it works inside, what it holds, and which hosts it may reach.

    POLICY_KEYS     the four fields a policy carries, in writing order
    GRANTS ALLOWED ROOTS   the three fixtures a policy is assembled from
    GrantError      a grant, or a policy for a principal, this stage refuses
    grant           a principal's capabilities, as one sorted tuple
    granted         what the grants say a principal holds, or nothing
    effective       the intersection of a tool's demand and a principal's grant
    missing         the part of the demand the grant does not cover, sorted
    permits         whether the grant covers the whole demand
    policy_for      the four policy fields for a principal the fixtures name

DESIGN DECISION — why is the answer the *difference* of two sets, when a boolean
would do?
    Because a boolean is the one shape of an answer that cannot say why. `permits`
    exists, but it is defined as `missing(...) == ()`: the caller that only needs
    to know whether the call runs asks `permits`, and the caller that has to write
    the reason into an audit line — stage 8 — asks `missing` and names what was
    not there. A `permits` spelled `set(demand) <= set(grant)` would answer the
    same question and lose the answer stage 8 needs, and the two spellings would
    be free to disagree the first time one of them was edited. One reading of the
    decision, two questions asked of it.

DESIGN DECISION — why does `effective` intersect while `missing` subtracts, and
why is neither of them a check on the other?
    `effective` is `demand & grant` — what the principal actually handed the tool
    — and `missing` is `demand - grant` — what the demand asked for and the grant
    did not have. They are the two halves of one comparison, and both are computed
    from stage 1's `declares` and this stage's `granted`, so neither can drift from
    the other: `permits` is exactly `missing == ()`, and a stage that later wants
    to *report* what a run used (stage 9) reads the intersection, while the denial
    names the difference. Subtracting the other way round (`grant - demand`) would
    answer with the capabilities the tool did not need, which is a set nobody
    asked about.

DESIGN DECISION — why must a grant be sorted and deduplicated, while the
capabilities a *policy* reports keep the fixture's own order?
    Because one of them is a value this stage computes and the other is a
    configuration this stage hands on. A grant carries no order — a set compared
    positionally answers differently depending on how somebody typed a tuple — so
    `grant` sorts it once, and a repeat is refused rather than folded, because a
    caller who wrote `("fs:read", "fs:read")` does not know they wrote a set. A
    policy, by contrast, *reports what the world configured*: re-sorting
    `tools.GRANTS["builder"]` here would make the policy a value nobody wrote down,
    and the next reader comparing it against the fixture would find a difference
    that no one introduced.

DESIGN DECISION — why is a principal the grants do not name `()` rather than a
refusal, and why then does `policy_for` refuse one by name?
    Because the two questions are different and only one of them is a
    configuration error. "What does this principal hold?" has an answer for every
    principal — nothing — and `"intern": ()` is in the fixtures precisely because
    a principal with nothing must never read as "no restriction". "Build the policy
    of principal X" is a question about a principal somebody was supposed to
    configure, and a policy for nobody is a mistake that has to be caught at the
    one place it can be: `policy_for`, naming X and the closest configured
    principal within two edits. A `granted` that refused would make the intern's
    empty tuple indistinguishable from a typo in every later stage.

DESIGN DECISION — why is a set handed over as a `str` the refusal this stage was
written for?
    Because a `str` *is* iterable, so `grant("analyst", "fs:read")` does not fail
    — it quietly becomes six one-character capabilities, one of which will match
    nothing and none of which will be caught by a check that compares lengths. The
    same shape reaches `policy_for` down the `hosts` and `capabilities` entries,
    so all three doors refuse a `str` by name, exactly as stage 1's demand does:
    the container is refused where it is not a set, and the *members* are refused
    where they are not names.

DESIGN DECISION — why does `policy_for` validate the *shape* of a root and of a
hosts entry but not their contents?
    Because judging a root and judging a host are stage 3's and stage 4's
    business, and a policy that pre-empted them would be a second reading of the
    same rule. So `policy_for` insists only on what its own contract is: the root
    is a non-empty absolute `str` (a relative root is a jail nobody can read) and
    the hosts entry is a tuple or list of `str` (a `str` would be iterated a
    character at a time). Whether `"/home/agent/../agent"` is a root worth having,
    and whether `"*.internal"` is a spec worth granting, are answered one stage
    down where the resolver and the policy of exact hosts live.

TODO: implement `grant`, `granted`, `missing`, `effective`, `permits` and
`policy_for`.
"""

from collections.abc import Mapping

import tools

from stage_01 import SandboxError, capability, declares

#: The four fields a policy carries, in the order a policy writes them. An order
#: is a claim, so it is written down once, and stage 8 reads a policy through
#: these names rather than through whatever a caller happened to build.
POLICY_KEYS = ("principal", "root", "capabilities", "hosts")

#: The three fixtures a policy is assembled from: what each principal holds, the
#: hosts it may reach and the root it works inside. These are the world's own
#: mappings, never copies, so a policy cannot drift from the fixtures it was
#: assembled out of — and every entry is validated by shape here and by content
#: in the stage that knows the content (stage 3 for a root, stage 4 for a host
#: spec), never defaulted to something generous.
GRANTS = tools.GRANTS
ALLOWED = tools.ALLOWED
ROOTS = tools.ROOTS

#: The distance within which a principal nobody configured is assumed to be a
#: typo for one the fixtures name.
_NEAR = 2


class GrantError(SandboxError):
    """A grant, or a policy for a principal, that this stage refuses.

    The refusal always names the offender — the principal, the capability, the
    root, the host spec — and, when the offender is within edit distance two of a
    configured principal, the real name too, because a principal nobody
    configured is exactly where a typo silently becomes an empty policy.
    """


def _levenshtein(left, right):
    """The edit distance between two short names, the plain way."""
    raise NotImplementedError("stage 2: implement _levenshtein()")


def _near(name, known):
    """`" (did you mean 'x'?)"` for the closest known name, or `""`."""
    raise NotImplementedError("stage 2: implement _near()")


def _capability(name):
    """Stage 1's vocabulary gate, reported as this stage's refusal.

    The vocabulary and the suggestion within two edits are stage 1's
    (`capability`), because two readings of one vocabulary is how a policy
    matches in one stage and not in the next; the *family* is this stage's,
    because a caller who caught a `GrantError` asked stage 2 a question and
    should not have to know where the vocabulary lives.
    """
    raise NotImplementedError("stage 2: implement _capability()")


def _capabilities(raw, what):
    """A grant's capabilities: a sorted, deduplicated tuple of real names."""
    raise NotImplementedError("stage 2: implement _capabilities()")


def _as_granted(raw, principal):
    """What the fixtures say a principal holds, read as one tuple of names."""
    raise NotImplementedError("stage 2: implement _as_granted()")


def grant(principal, capabilities):
    """A principal's capabilities, as one sorted tuple.

    The record carries exactly `{"principal", "capabilities"}`, in that order.
    The principal must be a non-blank `str`; the capabilities are validated one
    by one through stage 1's `capability` and read back sorted and deduplicated,
    so a repeat, a name the vocabulary does not have, a set that is not a
    sequence at all and a set handed over as a `str` are each refused by name.
    """
    raise NotImplementedError("stage 2: implement grant()")


def granted(grants, principal):
    """What the grants say a principal holds, or nothing at all.

    The principal's own tuple when the grants name it, and `()` when they do not
    — never a raise and never `None`: a principal with nothing is a value, and
    `policy_for` is the one door where a principal nobody configured is refused.
    """
    raise NotImplementedError("stage 2: implement granted()")


def missing(grants, principal, tool):
    """The part of a tool's demand the principal's grant does not cover.

    `declares(tool)` minus `granted(grants, principal)`, as a sorted, duplicate-
    free tuple — the answer a denial is written from.
    """
    raise NotImplementedError("stage 2: implement missing()")


def effective(grants, principal, tool):
    """The capabilities the principal actually handed the tool.

    The *intersection* of what the tool demands and what the principal holds,
    sorted: the demand is not the decision, and neither is the grant.
    """
    raise NotImplementedError("stage 2: implement effective()")


def permits(grants, principal, tool):
    """Whether the grant covers the whole demand, and nothing more than that.

    The boolean exists for the caller that has no use for the difference; its
    whole definition is `missing(grants, principal, tool) == ()`.
    """
    raise NotImplementedError("stage 2: implement permits()")


def policy_for(principal, *, grants=GRANTS, hosts=ALLOWED, roots=ROOTS):
    """The four policy fields for a principal the three fixtures name.

    The record carries exactly `POLICY_KEYS`, in that order: the principal, its
    root from `roots`, its capabilities from `grants` and its host specs from
    `hosts`. A principal nobody configured is refused by name, with the closest
    configured one within two edits suggested; a root that is not a non-empty
    absolute `str` and a hosts value that is not a tuple or list of `str` are
    refused here too, while the *contents* of both are left to stage 3 and
    stage 4.
    """
    raise NotImplementedError("stage 2: implement policy_for()")
