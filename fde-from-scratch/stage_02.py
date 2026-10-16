"""FDE From Scratch — stage 2: A deployment that cannot reach out.

Stage 1 answered who is asking and which rows they may see. This stage is the
basement those answers have to live in: a customer's own network, where nothing
reaches the public internet, where every image must be the digest the customer's
security review pinned, and where the removable bundle is the only thing that can
carry an image across the air gap at all. A manifest is the ask, a plan is the
ordered work, and a deployment is what the world's own log says happened.

The point of the stage is a refusal that costs nothing. A manifest that would reach
`"public"`, or that names an image the bundle never carried, is refused *before* one
step runs — and that is proved by the customer's own record rather than by the
stage's word: `Network.attempt` logs every reach-out and `Network.pull` every
crossing, so an untouched log is what says a refused plan ran nothing at all.

The surface:

    MANIFEST_KEYS   the six fields a deployment manifest carries, in order
    PROBLEMS        the eight ways a manifest is refused, in the order printed
    STEPS           the three actions a plan is made of, in the order they run
    DEPLOY_KEYS     the five fields a deployment answers with, in order
    DeployError     the refusal: a manifest, a plan or a state that cannot be one
    validate        (manifest, network) -> what is wrong with it, and what it reaches
    plan            (manifest, network) -> the steps, empty when the manifest is refused
    deploy          (steps, network, namespace, tick) -> what ran, as DEPLOY_KEYS
    rollback        (state) -> the same deployment, stopped
    verify          (state, network) -> whether the world's log agrees with the state

DESIGN DECISION — why is a namespace that merely starts with the customer's refused?
Because `northwindevil` is not `northwind`'s namespace, and a prefix test that does
not require the hyphen hands a stranger's manifest the customer's estate. The
namespace belongs to the customer: it is `ESTATE_NAME`, or it is `ESTATE_NAME`
followed by a hyphen and a name of the customer's own.

DESIGN DECISION — why may a plan reference a digest and never a tag?
Because a tag is a moving name and the security review pinned a digest: `north-api`
at tag `1.4.0` today is not the bytes that were reviewed. A manifest states the
digest it believes, the registry states the digest it holds, and a disagreement is
`unpinned-digest` — the plan is written against digests, so what it installs is
what was reviewed even when the registry has moved on.

DESIGN DECISION — why is the bundle checked for an image the registry already holds?
Because the registry is on the wrong side of the air gap. Physical media carries
digests into the basement, and something the registry holds can still be missing
from that media; skipping the check for known images is exactly how a deployment
discovers its gap at the moment it has no network to close it with.

DESIGN DECISION — why does `deploy` take its nodes from the plan's own start steps?
Because `deploy` never sees the manifest, and the zone the customer chose is visible
only in the plan it was handed: the instances name the node they will run on, so the
digests are installed onto those same nodes, round-robin, in the order the plan
names them. Installing onto a node nobody's instance names is how a deployment ends
up somewhere no one chose.

DESIGN DECISION — why does `verify` read the log instead of believing the state?
Because the state is the course's claim and the log is the customer's record. A
digest is installed when the network says it was installed, an instance runs on a
node of the zone the installs went to, and nothing reached `"public"` — all three
are recomputed from `Network.log()`, so a state that claims more than the log shows
fails its own verification.

TODO: implement
"""

import estate

from network import NetworkError

MANIFEST_KEYS = ("name", "namespace", "images", "node_zone", "replicas", "env")
PROBLEMS = ("bad-namespace", "bad-replicas", "unknown-image", "unpinned-digest",
            "not-in-bundle", "no-node", "would-egress", "duplicate-image")
STEPS = ("pull", "install", "start")
DEPLOY_KEYS = ("namespace", "installed", "running", "steps_done", "verdict")


class DeployError(estate.EstateError):
    """The refusal: something that cannot be a manifest, a plan or a state."""


def validate(manifest, network):
    """What is wrong with `manifest` on `network`, in PROBLEMS order.

    Answers `{"ok", "problems", "images", "egress"}`: `ok` whether it may be
    deployed at all, `problems` the `(problem, offender)` pairs in `PROBLEMS`
    order, `images` the registry's own records for the manifest's images in
    manifest order, and `egress` the `(zone, destination)` pairs the manifest's
    zone reaches. `manifest` is never written to.
    """
    raise NotImplementedError("stage 2: implement validate()")


def plan(manifest, network):
    """The ordered `(action, subject)` steps for `manifest`, and its problems.

    `pull` and `install` carry the digest — the plan crosses the air gap and
    installs what the customer pinned, never a tag — and `start` carries the
    instance name. A manifest `validate` refuses answers `((), problems)`: there
    is no work to run.
    """
    raise NotImplementedError("stage 2: implement plan()")


def deploy(plan, network, namespace, tick):
    """Run `plan`'s steps against `network`, answering `DEPLOY_KEYS`.

    `installed` is the sorted tuple of digests that were installed, `running` the
    instance names that were started, `steps_done` how many steps ran and `verdict`
    one of `("deployed", "refused", "rolled-back")`. An empty plan, or one the
    world refuses part-way, is `"refused"` and installs nothing further.
    """
    raise NotImplementedError("stage 2: implement deploy()")


def rollback(state):
    """`state` stopped: the same deployment as `DEPLOY_KEYS`, `running` empty.

    What was installed stays installed — a rollback is not an uninstall — and the
    verdict is `"rolled-back"`.
    """
    raise NotImplementedError("stage 2: implement rollback()")


def verify(state, network):
    """Whether the world's own log agrees with `state`, as `{"ok", "problems"}`.

    Recomputes from `Network.log()`: every digest the state calls installed was
    pulled, every installed digest is one the bundle carries, no attempt reached
    `"public"`, and every running instance sits on a node of the zone the installs
    went to with an instance actually running there.
    """
    raise NotImplementedError("stage 2: implement verify()")
