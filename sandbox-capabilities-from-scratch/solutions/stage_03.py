"""stage_03.py — the path jail, and the escape that is a string test.

Sandbox & Capabilities From Scratch — stage 3: The path jail, and the escape that is a string test

An agent's power is not only what its tools may do and what its principal
granted; it is also *where* a tool is allowed to act, and a path a caller hands
in is not yet a place. `/home/agent/../../etc/passwd` resolves to `/etc/passwd`,
outside every root this course grants; and `/home/agent-other/notes.md` merely
*starts with* `/home/agent`, character for character, while living in another
agent's tree. This stage is the two halves of the answer — resolve a request
into an absolute, normalised path, then decide containment on components and
never on strings — and the escape it refuses is exactly the one a `startswith`
test hands over.

    SEPARATOR   the character a path is split on
    CURRENT     the component that names the path's own directory
    PARENT      the component that names the directory above it
    JailError   a request that will not resolve, a root that is not a jail, or a
                resolution outside one
    resolve     a request normalised into an absolute path
    inside      whether a resolved path is inside a root, component by component
    jail        resolve, then inside, else a refusal naming all three
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


def _split(path, what):
    """The components of an absolute, normalised path, or a refusal naming it.

    A path here names its components: absolute, with no `.` or `..` in it. The
    root of a jail and the result of a resolve are both written this way, and a
    path that is not is refused rather than compared, because a comparison made
    against a path that was never resolved is the bug this stage exists for.
    """
    if not isinstance(path, str):
        raise JailError("%s must be a str, got %r" % (what, path))
    if not path:
        raise JailError("%s must not be empty: there is nothing to name" % (what,))
    if not path.startswith(SEPARATOR):
        raise JailError("%s must be absolute, got %r" % (what, path))
    parts = []
    for component in path.split(SEPARATOR):
        if not component:
            continue
        if component == CURRENT:
            raise JailError(
                "%s carries a %r component: %r names the directory it is already "
                "in, and a jail is decided on a resolved path"
                % (what, CURRENT, path))
        if component == PARENT:
            raise JailError(
                "%s carries a %r component: %r has to be resolved before it can be "
                "compared, and resolving is the caller's job"
                % (what, PARENT, path))
        parts.append(component)
    return tuple(parts)


def resolve(root, requested):
    """A request normalised into an absolute path, or a refusal that names it.

    The root is validated first, so a request is never resolved against a jail
    nobody can read. `requested` must be a non-empty absolute `str`; empty
    components and `.` drop, `..` pops a component (popping past `/` stays `/`),
    and a trailing slash is not a component. The result is absolute and carries
    no `.` or `..`.
    """
    _split(root, "a root")
    if not isinstance(requested, str):
        raise JailError("a requested path must be a str, got %r" % (requested,))
    if not requested:
        raise JailError(
            "a requested path must not be empty: there is nothing to name")
    if not requested.startswith(SEPARATOR):
        raise JailError(
            "a requested path must be absolute, got %r: resolving does not invent "
            "the root a relative path would need" % (requested,))
    parts = []
    for component in requested.split(SEPARATOR):
        if component == "" or component == CURRENT:
            continue
        if component == PARENT:
            if parts:
                parts.pop()
            continue
        parts.append(component)
    return SEPARATOR + SEPARATOR.join(parts)


def inside(root, resolved):
    """Whether a resolved path is inside a root, compared component by component.

    `root` and `resolved` must both be absolute and normalised; a root that is
    not is refused by name, because a jail whose root carries a `.` or a `..` is
    a comparison a reader cannot check by eye. A root contains itself, and a path
    is inside it when the root's components are a prefix of the path's
    components — never when the root's *characters* are a prefix of the path's.
    """
    root_parts = _split(root, "a root")
    resolved_parts = _split(resolved, "a resolved path")
    return resolved_parts[:len(root_parts)] == root_parts


def jail(root, requested):
    """The resolved path, if it is inside the root, else a refusal naming all three.

    Resolve first, then decide: a request that lands outside the root raises
    `JailError` naming the request, what it resolved to, and the root it is
    outside of.
    """
    resolved = resolve(root, requested)
    if inside(root, resolved):
        return resolved
    raise JailError(
        "the request %r resolves to %r, which is outside the root %r"
        % (requested, resolved, root))
