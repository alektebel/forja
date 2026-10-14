"""Sandbox & Capabilities From Scratch — stage 3: The path jail, and the escape that is a string test.

An agent's power is not only what its tools may do and what its principal
granted; it is also *where* a tool is allowed to act, and a path a caller hands
in is not yet a place. `/home/agent/../../etc/passwd` resolves to `/etc/passwd`,
outside every root this course grants; `/home/agent-other/notes.md` merely
*starts with* `/home/agent`, character for character, while living in another
agent's tree. So this stage fixes the two halves of the answer — resolve a
request into an absolute, normalised path, then decide containment on components
and never on strings — and refuses the escape a `startswith` test hands over.

Every later stage reads this door and none of them re-derives it: stage 8 asks
the jail of the *resolved* path before a path tool acts, and the capstone's
broken plan carries a `..` path that resolves outside the root precisely so that
a jail which is a string test is caught before any file is read. A jail decided
per-stage is two stages disagreeing about which file a path names, and the whole
course rests on the opposite.

    SEPARATOR   the character a path is split on
    CURRENT     the component that names the path's own directory
    PARENT      the component that names the directory above it
    JailError   a request that will not resolve, a root that is not a jail, or a
                resolution outside one
    resolve     a request normalised into an absolute path: `.` dropped, `..`
                applied, a trailing slash not a component
    inside      whether a resolved path is inside a root, component by component
    jail        resolve, then inside, else a refusal naming all three

DESIGN DECISION — why does `resolve` name a `root` it does not use to build the
answer?
    Because a path is only meaningful against the jail it is resolved for, and
    the two halves of the decision — resolve, then inside — must agree about
    which root is spoken of. `resolve` validates the root it is handed (absolute,
    normalised, no `.` or `..`) so that no caller can resolve a request against a
    jail nobody can read: a root of `/home/agent/../agent` is the same directory
    as `/home/agent`, but a jail whose own root carries a `..` is a comparison a
    reader cannot check by eye, so it is refused rather than silently folded.

DESIGN DECISION — why is containment decided by components and never by a string
test?
    Because `"/home/agent-other/notes.md"` starts with `"/home/agent"` character
    for character, and the sibling root `vfs.SIBLING` exists in this course's
    fixtures precisely so that a `startswith` jail hands it over. A root is a
    sequence of directory names, and a path is inside it when the root's whole
    sequence is a prefix of the path's sequence — `["home", "agent"]` is not a
    prefix of `["home", "agent-other", "notes.md"]`, however the characters line
    up. The comparison is on the list, not the string, and the fixture decides
    which one was written.

DESIGN DECISION — why is a root that is not already normalised refused instead of
resolved first?
    Because a jail is the thing being *built*, and one that repaired its own root
    would be answering the question it asks. If the root is
    `/home/agent/../agent`, a reader of the policy cannot tell whether the jail is
    `/home/agent` or a mistake, and a `startswith`-shaped bug and a `..`-shaped
    bug would look the same. So the root must arrive already absolute and
    normalised — the same shape `resolve` hands back — and a root that is not is
    refused by name, because the course's one escape is the comparison, and it
    must be made against a root a reader can read.

DESIGN DECISION — why is `..` *applied* rather than clamped to the root?
    Because clamping is a second, hidden jail, and it is the wrong one.
    `/home/agent/../../etc/passwd` is not "inside the root, near `/etc`": it *is*
    `/etc/passwd`, and a jail that answered "inside" to a path whose own text
    names another directory would be lying about the filesystem C2 taught the
    reader. The resolver applies `..` exactly as a real filesystem does — a pop,
    and popping past `/` stays `/` — so the string the decision is made about is
    the file the path really names, and the only thing left to decide is
    containment.

DESIGN DECISION — why does `jail` raise, when a denial elsewhere is returned?
    Because a request that resolves outside the root is the *caller* getting
    something wrong, not the policy deciding. A policy decision — a missing
    grant, a host that is not allowed, a cost the meter cannot pay — is a normal
    outcome of a run and is returned as data so the loop keeps going; a request
    that resolves outside the jail is a caller who has confused two roots, and
    the refusal that stops them spells out all three: the request, what it
    resolved to, and the root it is outside of. `jail` is the door a run should
    use, and the door names the reason it did not open.

TODO: implement `resolve`, `inside` and `jail`.
"""

from stage_01 import SandboxError

#: The separator a path is split on: a component is what lies between two of
#: them, and `a/b` names two components, not one string.
SEPARATOR = "/"

#: The component that names the directory a path is already in. Resolving drops
#: it, because it changes nothing.
CURRENT = "."

#: The component that names the directory above. Resolving applies it, because
#: dropping it is exactly the escape this stage exists to stop.
PARENT = ".."


class JailError(SandboxError):
    """A path this stage refuses.

    Raised for a request that will not resolve — a non-str, an empty string, a
    relative path — for a root that is not already absolute and normalised, and
    for a request that resolves to a path outside the root it was resolved for.
    Every message names the offender: the request, what it resolved to, and the
    root it is outside of.
    """


def resolve(root, requested):
    """A request normalised into an absolute path, or a refusal that names it.

    The root is validated first, so a request is never resolved against a jail
    nobody can read. `requested` must be a non-empty absolute `str`; empty
    components and `.` drop, `..` pops a component (popping past `/` stays `/`),
    and a trailing slash is not a component. The result is absolute and carries
    no `.` or `..`.
    """
    raise NotImplementedError("stage 3: implement resolve()")


def inside(root, resolved):
    """Whether a resolved path is inside a root, compared component by component.

    `root` and `resolved` must both be absolute and normalised; a root that is
    not is refused by name, because a jail whose root carries a `.` or a `..` is
    a comparison a reader cannot check by eye. A root contains itself, and a path
    is inside it when the root's components are a prefix of the path's
    components — never when the root's *characters* are a prefix of the path's.
    """
    raise NotImplementedError("stage 3: implement inside()")


def jail(root, requested):
    """The resolved path, if it is inside the root, else a refusal naming all three.

    Resolve first, then decide: a request that lands outside the root raises
    `JailError` naming the request, what it resolved to, and the root it is
    outside of.
    """
    raise NotImplementedError("stage 3: implement jail()")
