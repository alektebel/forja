"""Sandbox & Capabilities From Scratch — stage 6: The secret that never reaches the model.

An agent's power is not what its tools can do; it is the intersection of what the
tools declare, what the principal granted, and what the world will still afford.
A secret is the one thing that intersection cannot merely *allow*: a value that
has reached a model's context cannot be recalled by any policy written
afterwards. So this stage splits a secret into the two things a run can hold
apart — the *identity* of a value (its handle, its length, a fingerprint) that
may travel anywhere, and the value itself, which leaves the vault through one
door and only when a policy opens it.

Everything a run shows — an observation, a line in the audit, a field of the
report — is output, and output is where a value nobody meant to send ends up. A
run that shows anything therefore passes it through the four shapes a value is
written in first, and it can *ask* whether it missed one: `redact` replaces, and
`leaks` finds what a redactor that only knows the plain form has already lost to.

    ENCODINGS      the four shapes a value is recognised in, in declared order
    SecretError    what a secret, a policy, a text or a value this stage refuses
    digest         a value's fingerprint: an int, and not cryptography
    observe        what a run may show the model: the handle, its length, its fingerprint
    reveal         the one door a value may leave through, and it answers to a policy
    redact         every occurrence of every value, in every shape it is written in
    leaks          the handles whose value is written in a text, in any of those shapes

DESIGN DECISION — why does `observe` *read* a value it must never show?
    Because keeping a value out of the model's hands is this course's job and not
    the vault's: the world is not the policy engine, and `Vault.read` hands over
    any value on request, exactly as `VFS.read` hands over any file it has. The
    stage's answer is not to stop the read but to *absorb* it: the value is read,
    fingerprinted, and dropped, and what travels is the handle, the length and the
    fingerprint. A stage that refused to read at all would have nothing to
    recognise a secret by, and the second run of the same plan would not be able
    to say "this is the same value as before" without ever holding it.

DESIGN DECISION — why is a missing capability a *denial* here and not a refusal?
    Because a refusal is a verdict on something the caller got wrong, and asking
    for a value a policy does not grant is not a mistake — it is the ordinary
    answer "no" that a run has to keep walking past. So `reveal` answers
    `{"allowed": False, "reason": "capability", "missing": ("secret:read",)}` and
    names the one thing that was missing, which is the difference of two sets and
    not a boolean anybody could have got wrong quietly. The grant is decided
    before the world is asked anything, so a denial leaves the vault's own record
    of what was read untouched — and "it was never read" is then checkable
    instead of promised.

DESIGN DECISION — why do four encodings carry six spellings, and why is a
redactor that knows only the plain value a bug worth a stage?
    Because a value is *the same secret* however it is written, and the writing is
    chosen by whoever is smuggling it. base64 is written with and without its
    padding and hex in either case, so four names carry six spellings: the plain
    value, base64 padded and stripped, hex lower and upper, and the reversed
    value. A redactor that replaces the plain form and reports success has a
    detector that agrees with it — and the leak travels in the shape neither of
    them looked at. The stripped base64 case is the common one in practice: a
    value pasted into a query string, a URL or a log line loses its `=` first.

DESIGN DECISION — why is the fingerprint a weighted sum and not a hash?
    Because the point is *recognition*, not secrecy, and the honest thing to ship
    is the thing that says so. `sum((i + 1) * ord(char) for i, char in
    enumerate(value))` is trivially reversible by anyone who knows the shape and
    two different values can collide, which is exactly why the docstring says it
    is not cryptography: a fingerprint that claimed to be a hash would invite a
    caller to treat it as one. What it buys is real — identity travels while the
    value does not — and a stage whose fingerprint is weaker than a hash but
    stronger than nothing is a stage that is honest about which of the two it is.

DESIGN DECISION — why is a value that is the empty string refused rather than
redacted or detected?
    Because an empty string occurs *everywhere*, and both uses are then
    catastrophic in the quiet way. `text.replace("", "<redacted:h>")` inserts the
    placeholder at every position of every text, so one empty fixture redacts a
    whole run's output into nonsense; and a substring test against `""` finds a
    "leak" in every text, so the detector that is supposed to be the proof reports
    one for everything and is believed for nothing. The refusal names the handle,
    because "the value of 'x' is empty" is one edit away from a fixture that
    means something.

DESIGN DECISION — why is a capability set that is a `str` refused by name?
    Because `"secret:read" in "secret:read"` is `True` — a substring test, not a
    set membership — and a policy handed over as one long string would open every
    door it names a character at a time. This is the same classic bug stage 2
    refuses in a grant and stage 1 refuses in a demand, and it is refused here for
    the same reason: a set is a value and a `str` is a sequence, and the two are
    only confused by code that never asked which it had. The refusal spells the
    string out so the caller sees the shape they handed over.

TODO: implement `digest`, `observe`, `reveal`, `redact` and `leaks`.
"""

from stage_01 import SandboxError

#: The four shapes a value is recognised in, in the order the course declares
#: them. base64 and hex each carry two spellings — padded and stripped, lower and
#: upper — so four names are six forms, and every one of them is the same secret.
ENCODINGS = ("plain", "base64", "hex", "reversed")


class SecretError(SandboxError):
    """A secret, a policy, a text or a value this stage refuses.

    The refusal always names the offender — the value, the text, the handle, the
    policy — and a field within edit distance two of a real one is refused *with*
    the real name, because a policy that misspelled `capabilities` is a policy
    nobody can read and everybody will believe.
    """


def digest(value):
    """A value's fingerprint: an int, and *not* cryptography.

    `sum((i + 1) * ord(char) for i, char in enumerate(value))` — a
    position-weighted sum of the value's characters, which is what lets a run
    recognise a value it must not carry. A `value` that is not a `str` is refused
    by name.
    """
    raise NotImplementedError("stage 6: implement digest()")


def observe(vault, handle):
    """What a run may show the model about a secret, and never the value.

    Returns `{"handle", "present", "bytes", "digest"}` in that order, with
    `present` the vault's own answer, `bytes` the length *the vault reports* and
    `digest` this stage's fingerprint of the value, which is read and then
    dropped. An unknown handle is the world's own `tools.VaultError`, by name: the
    vault is not policed here, it is consulted.
    """
    raise NotImplementedError("stage 6: implement observe()")


def reveal(policy, vault, handle):
    """The one door a value may leave through, and it answers to a policy.

    Returns `{"allowed": True, "reason": "granted", "value": …}` when the
    policy's capabilities hold `secret:read`, and the *denial*
    `{"allowed": False, "reason": "capability", "missing": ("secret:read",)}` when
    they do not — a denial is data, never a raise, because "no" is an ordinary
    outcome of a run. A policy that is not a mapping, carries no `capabilities`
    field, or carries one as a `str` is refused by name; an unknown handle, once
    the door is open, is the world's `tools.VaultError`, by name.
    """
    raise NotImplementedError("stage 6: implement reveal()")


def redact(text, values):
    """Every occurrence of every value replaced, in every shape it is written in.

    `values` is a mapping of handle to value and the replacement is
    `"<redacted:handle>"`, so an output says *that* a secret was there without
    saying which value — over all of `ENCODINGS`, padded and stripped base64 and
    both cases of hex included. A `text` that is not a `str`, a `values` that is
    not a mapping and a value that is not a `str` are refused by name, while an
    empty mapping, an empty text and a value that does not occur come back
    unchanged.
    """
    raise NotImplementedError("stage 6: implement redact()")


def leaks(text, values):
    """The handles whose value is written in `text`, in any of those shapes.

    The detector for the same four encodings `redact` replaces, returning the
    sorted handles it found as data — never a raise and never a boolean, so a run
    can ask it of every output it produced. An empty mapping, an empty text and a
    value that does not occur answer `()`; a `text` that is not a `str` and a
    `values` that is not a mapping are refused by name.
    """
    raise NotImplementedError("stage 6: implement leaks()")
