"""Sandbox & Capabilities From Scratch — stage 4: The network policy, and the host nobody can read.

A tool that dials is the one tool whose target is not a path, and the policy that
bounds it is the one place where a `*` is either a decision or a hole. So this
stage fixes what a principal's allowlist *is*, before anything is dialled: a
list of `"host:port"` specs — or the single spec `"*"` — read one at a time into
a `(host, port)` pair, matched exactly, and answered against the world's own
catalogue, because a policy cannot grant a host that does not exist.

Every later stage reads this the same way and none of them re-reads a spec out of
its own invention: stage 8 asks `reachable` before it dials and calls `target`
for the record it will write into the audit line, and stage 9 checks the line's
hosts against what the wire was actually asked to dial. A spec whose meaning is
decided per-stage is a policy two stages disagree about, and the whole course
rests on the opposite.

    WILDCARD      the one spec that means "any host the world knows", alone
    SandboxError  the course's one refusal family (a ValueError), from stage 1
    HostError     what a spec, an allowlist or a target this stage refuses
    parse_host    one spec, read as a `(host, port)` pair, or `("*", 0)`
    allows        the allowlist, an exact match on the pair with `*` the one escape
    reachable     allowed *and* in the world's catalogue — the policy's answer
    target        the world's own record for the pair, `{"host", "port", "bytes"}`

DESIGN DECISION — why is the port part of the host's identity instead of a
default?
    Because `api.internal:443` and `api.internal:8443` are two different targets,
    and a policy that names one has said nothing about the other. A spec with no
    port at all — `"api.internal"` — is refused rather than read as "the usual
    port", because "the usual port" is a number this course would have to invent
    and a reader of the policy could not see: the fixture set has a host the
    catalogue answers on 5432 that no principal's allowlist names, and that
    fixture only means anything if the missing port is a hole rather than a
    default. A host with no port is a policy with a hole, so it is spelled as the
    hole it is.

DESIGN DECISION — why is `"*.internal"` refused rather than matched as a suffix?
    Because a policy a reader cannot evaluate is not a policy. `"*.internal"`
    *looks* like it means every internal host, and every reader of it would have
    to guess whether it also means `"api.internal.evil.com"`, whether it matches
    one label or any depth, and whether it is case sensitive — and two
    implementations of those guesses differ exactly where an attacker looks. So
    `*` is allowed only as the *whole* spec, where it has one reading and it is
    the world's own ("any host the world knows"), and a `*` anywhere else in a
    spec is refused, naming the spec that carried it. The rule is not "no
    patterns"; it is "no rule whose language is undecided".

DESIGN DECISION — why is an upper-case host refused rather than folded with
`.lower()`?
    Because folding is where a policy starts matching in the check and failing in
    production. This world's host names are lower case — the catalogue has no
    upper-case entry — so a spec that carries one is a spec that would be
    compared against a name this world never answers to. A `.lower()` in the
    comparison hides that: the check passes on `"API.INTERNAL"` and the real
    resolver, which does not fold, matches nothing. The name is refused by name
    instead, so the offender is visible at the policy and not inside a comparison
    nobody reads twice.

DESIGN DECISION — why does `reachable` consult the world, and why is the `wire`
never asked anything?
    Because a policy cannot grant a host that does not exist: an allowlist of
    `"*"` for a principal that holds no `net:connect` is one fixture, and `"*"`
    for a principal allowed every host the *catalogue* has is another, and the
    second is a real answer rather than a hole. The catalogue of record is the
    world's (`tools.HOSTS`), read as data. The `wire` is carried in the signature
    because stage 8's decision carries the world it acts in, and it is never
    dialled and never asked: the only question a `Wire` answers is `dial()`, a
    dial is a *touch*, and a touch is what stage 9 audits. Asking whether a host
    is reachable must not put a dial in the record — reaching for the world's
    catalogue is a question, and a question is not a touch.

DESIGN DECISION — why is `target`'s refusal the world's own, and not a record
this stage builds?
    Because the bytes a call will touch are the world's fact and not the policy's
    opinion. `target` hands the pair to the world (`tools.host`) and returns the
    record the world already keeps — `{"host", "port", "bytes"}` — so a spec that
    named a host the catalogue does not have, or the right host on the wrong
    port, is refused *by the world* with the name and the port it does have, in
    this stage's refusal family. A `bytes` copied out of the allowlist, or
    invented as a default, would be a number the audit line carries and the wire
    never agreed to.

TODO: implement `parse_host`, `allows`, `reachable` and `target`.
"""

import tools

from stage_01 import SandboxError

#: The one spec that means "any host the world knows". It is a spec in its own
#: right and the whole of one: a `*` mixed with anything else is not a rule a
#: reader can evaluate, so it is refused.
WILDCARD = "*"


class HostError(SandboxError):
    """A host spec, an allowlist or a target this stage refuses.

    The refusal always names the offender — the spec, the host, the port, the
    allowlist — and the world's own refusal is carried through this family rather
    than raised raw, so that a caller who catches the course's `SandboxError`
    catches a broken network policy with it.
    """


def parse_host(spec):
    """One spec, read as a `(host, port)` pair, or `("*", 0)` for the wildcard.

    A spec is `"host:port"` or exactly `"*"`. A spec with no port, a port that is
    not a positive int, a host with an upper-case letter, an empty spec, and a
    `*` mixed with anything else are each refused, naming the offender: a
    wildcard a reader cannot evaluate is not a policy.
    """
    raise NotImplementedError("stage 4: implement parse_host()")


def allows(hosts, host, port):
    """Whether the allowlist grants this exact `(host, port)` pair.

    `hosts` is a sequence of specs, each read by `parse_host` — an unreadable spec
    in an allowlist is refused by name, because a policy is read whole or not at
    all. The match is exact on the pair, with the single spec `"*"` meaning "any
    host the world knows".
    """
    raise NotImplementedError("stage 4: implement allows()")


def reachable(wire, hosts, host, port):
    """Whether the pair is both granted and in the world's catalogue.

    `allows(...)` and the catalogue: a policy cannot grant a host that does not
    exist. `wire` is the world that would dial, carried for identity and never
    asked — a question is not a touch.
    """
    raise NotImplementedError("stage 4: implement reachable()")


def target(wire, hosts, host, port):
    """The world's own record for the pair, `{"host", "port", "bytes"}`.

    The pair is validated as a pair and the allowlist is read whole, then the
    record comes from the world (`tools.host`), which refuses an unknown host or
    a known host on the wrong port by name — bytes are the world's fact, never
    the policy's.
    """
    raise NotImplementedError("stage 4: implement target()")
