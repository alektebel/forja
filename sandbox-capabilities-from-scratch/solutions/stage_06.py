"""stage_06.py — the secret that never reaches the model.

Sandbox & Capabilities From Scratch — stage 6: The secret that never reaches the model

An agent's power is not what its tools can do; it is the intersection of what the
tools declare, what the principal granted, and what the world will still afford.
A secret is the one thing that intersection cannot merely *allow*: a value that
has reached a model's context cannot be recalled by any policy written
afterwards. So this stage splits a secret into the two things a run can hold
apart — the *identity* of a value (its handle, its length, a fingerprint) that may
travel anywhere, and the value itself, which leaves the vault through one door and
only when a policy opens it.

Everything a run shows is output, and output is where a value nobody meant to send
ends up, so a run that shows anything passes it through the four shapes a value is
written in first — and can *ask* whether it missed one. The name table:

    ENCODINGS      the four shapes a value is recognised in, in declared order
    SecretError    what a secret, a policy, a text or a value this stage refuses
    digest         a value's fingerprint: an int, and not cryptography
    observe        what a run may show the model: the handle, its length, its fingerprint
    reveal         the one door a value may leave through, and it answers to a policy
    redact         every occurrence of every value, in every shape it is written in
    leaks          the handles whose value is written in a text, in any of those shapes
"""

import base64
from collections.abc import Mapping

from stage_01 import SandboxError

#: The four shapes a value is recognised in, in the order the course declares
#: them. base64 and hex each carry two spellings — padded and stripped, lower and
#: upper — so four names are six forms, and every one of them is the same secret.
ENCODINGS = ("plain", "base64", "hex", "reversed")

#: The distance within which a field that is not a field is assumed to be a typo
#: for one that is.
_NEAR = 2

#: The one capability a value leaves a policy through: the vocabulary's own name,
#: spelled in one place, because a policy that holds something else has not
#: granted this door.
_READ = "secret:read"

#: What an occurrence of a value is replaced with. The replacement names the
#: *handle*: an output a reader sees says that a secret was there, and never
#: which value it was.
_PLACEHOLDER = "<redacted:%s>"


class SecretError(SandboxError):
    """A secret, a policy, a text or a value this stage refuses.

    The refusal always names the offender — the value, the text, the handle, the
    policy — and a field within edit distance two of a real one is refused *with*
    the real name, because a policy that misspelled `capabilities` is a policy
    nobody can read and everybody will believe.
    """


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
    """`" (did you mean 'x'?)"` for the closest known field, or `""`."""
    if not isinstance(name, str):
        return ""
    best, best_distance = None, _NEAR + 1
    for candidate in sorted(string for string in known
                            if isinstance(string, str)):
        distance = _levenshtein(name, candidate)
        if distance < best_distance:
            best, best_distance = candidate, distance
    if best is None or best_distance > _NEAR:
        return ""
    return " (did you mean %r?)" % (best,)


def _text(text):
    """A text to scan or to redact, refused by name when it is not one."""
    if not isinstance(text, str):
        raise SecretError("a text must be a str, got %r" % (text,))
    return text


def _capabilities(policy):
    """The capability set a policy holds, read as a set and never as a `str`."""
    if not isinstance(policy, Mapping):
        raise SecretError("a policy must be a mapping, got %r" % (policy,))
    if "capabilities" not in policy:
        raise SecretError(
            "a policy must carry 'capabilities', got a mapping with %s%s"
            % (", ".join(sorted(map(repr, policy))) or "no fields",
               _near("capabilities", policy)))
    capabilities = policy["capabilities"]
    if isinstance(capabilities, str):
        raise SecretError(
            "a policy's capabilities must be a set of names, not the str %r: "
            "iterating it would read one character at a time, and `in` on it is "
            "a substring test" % (capabilities,))
    if not isinstance(capabilities, (tuple, list, set, frozenset)):
        raise SecretError("a policy's capabilities must be a tuple of names, "
                          "got %r" % (capabilities,))
    return capabilities


def _pairs(values):
    """The `(handle, value)` pairs of a mapping, both sides validated."""
    if not isinstance(values, Mapping):
        raise SecretError(
            "values must be a mapping of handle to value, got %r" % (values,))
    pairs = []
    for handle, value in values.items():
        if not isinstance(handle, str):
            raise SecretError("a secret's handle must be a str, got %r"
                              % (handle,))
        if not isinstance(value, str):
            raise SecretError("the value of %r must be a str, got %r"
                              % (handle, value))
        if not value:
            raise SecretError(
                "the value of %r is empty: an empty value occurs everywhere, so "
                "redacting it would rewrite the whole text and detecting it "
                "would find it in every one" % (handle,))
        pairs.append((handle, value))
    return pairs


def _forms(value):
    """Every shape a value is written in, the longest of them first.

    `ENCODINGS` is the course's four: the plain value, base64, hex and the
    reversed value — and base64 is written with *and* without its padding while
    hex is written in either case, so four names carry six spellings. Longest
    first is what makes a replacement whole: the padded base64 is the stripped one
    plus its `=`, so replacing the short form first would leave the padding behind
    as the last visible remainder of a secret.
    """
    forms = [value]
    if "base64" in ENCODINGS:
        padded = base64.b64encode(value.encode()).decode()
        forms.extend((padded, padded.rstrip("=")))
    if "hex" in ENCODINGS:
        digits = value.encode().hex()
        forms.extend((digits, digits.upper()))
    if "reversed" in ENCODINGS:
        forms.append(value[::-1])
    return tuple(sorted(forms, key=len, reverse=True))


def digest(value):
    """A value's fingerprint: an int, and *not* cryptography.

    `sum((i + 1) * ord(char) for i, char in enumerate(value))` — a
    position-weighted sum of the value's characters. It is not a hash: anyone who
    knows the shape can reverse it and two different values can collide, which is
    why it is not called one. It is here so that a run can *recognise* a secret it
    must not carry — the handle, the length and this number travel together, the
    value does not — and a caller that wants a hash has to say so out loud.
    """
    if not isinstance(value, str):
        raise SecretError("a value must be a str to be fingerprinted, got %r"
                          % (value,))
    return sum((index + 1) * ord(char) for index, char in enumerate(value))


def observe(vault, handle):
    """What a run may show the model about a secret, and never the value.

    `{"handle", "present", "bytes", "digest"}`: the handle that was asked about,
    the vault's own answer to whether it holds it, the length the vault reports,
    and this stage's fingerprint of the value. The value is read — the world is
    not the policy engine, and keeping a value out of the model's hands is this
    course's job — and then dropped on the floor except for those two numbers:
    identity travels, the value does not. An unknown handle is the world's
    refusal (`tools.VaultError`), by name, because what this stage decides is what
    may be *shown* and not what may be held.
    """
    value = vault.read(handle)
    meta = vault.meta(handle)
    return {
        "handle": handle,
        "present": vault.holds(handle),
        "bytes": meta["bytes"],
        "digest": digest(value),
    }


def reveal(policy, vault, handle):
    """The one door a value may leave through, and it answers to a policy.

    A value becomes a `str` in the run's hands here and nowhere else, and only
    when the policy's capabilities hold `secret:read`; without it the answer is
    *data* — `{"allowed": False, "reason": "capability", "missing":
    ("secret:read",)}` — because "no" is a normal outcome of a run and the loop
    has to keep going. The grant is decided **before** the world is asked
    anything, so a denial leaves the vault's own record of what was read untouched
    and "nothing was ever read" is checkable; once the door is open, an unknown
    handle is the world's refusal (`tools.VaultError`), by name.
    """
    capabilities = _capabilities(policy)
    if _READ not in capabilities:
        return {"allowed": False, "reason": "capability", "missing": (_READ,)}
    return {"allowed": True, "reason": "granted", "value": vault.read(handle)}


def redact(text, values):
    """Every occurrence of every value replaced, in every shape it is written in.

    `values` is a mapping of handle to value, and a run that shows a model
    anything it produced passes it through here first. The plain value, base64
    padded and stripped, hex lower and upper, and the reversed value are the same
    secret, and a redactor that knows one of them is a redactor that leaks the
    others — which is why the replacement names the *handle* and not the value: an
    output a reader sees says that a secret was there without saying which one. An
    empty mapping and a text with nothing to redact come back unchanged, because a
    redactor with nothing to do is not an error.
    """
    text = _text(text)
    for handle, value in _pairs(values):
        for form in _forms(value):
            text = text.replace(form, _PLACEHOLDER % (handle,))
    return text


def leaks(text, values):
    """The handles whose value is written in `text`, in any of those shapes.

    The detector for the same spellings `redact` replaces: a redactor is only as
    good as the test that can say whether it missed something, so a run asks this
    of every output it shows — after redaction the answer is `()`. The answer is
    the sorted handles, as data, so a detector that finds nothing is not an
    exception a run has to catch, and a value written twice is one handle and not
    two.
    """
    text = _text(text)
    found = []
    for handle, value in _pairs(values):
        for form in _forms(value):
            if form in text:
                found.append(handle)
                break
    return tuple(sorted(found))
