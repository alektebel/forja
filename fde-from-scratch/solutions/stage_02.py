"""FDE From Scratch — stage 2: A deployment that cannot reach out.

The basement stage 1's answers have to live in. A manifest is the customer's ask,
`validate` says what is wrong with it and what it would reach, `plan` turns it into
ordered work over *digests*, and `deploy` runs that work against the customer's own
network — which reaches no public internet, holds images by the digest security
pinned, and can only be crossed by the removable bundle. A refused manifest produces
no steps at all, and the customer's own log (`Network.attempt`, `Network.pull`) is
what proves nothing ran: `verify` recomputes the deployment from that log rather
than believing the state it was handed.
"""

import estate

from network import NetworkError

MANIFEST_KEYS = ("name", "namespace", "images", "node_zone", "replicas", "env")
PROBLEMS = ("bad-namespace", "bad-replicas", "unknown-image", "unpinned-digest",
            "not-in-bundle", "no-node", "would-egress", "duplicate-image")
STEPS = ("pull", "install", "start")
DEPLOY_KEYS = ("namespace", "installed", "running", "steps_done", "verdict")

_VERDICTS = ("deployed", "refused", "rolled-back")
_VERIFY_PROBLEMS = ("not-pulled", "public-attempted", "wrong-zone", "not-running",
                    "not-in-bundle")
_PUBLIC = "public"
_REFERENCE_KEYS = ("name", "tag", "digest")
_INSTANCE = "%s:%s:%d"


class DeployError(estate.EstateError):
    """The refusal: something that cannot be a manifest, a plan or a state."""


def _text(value, what):
    """A non-empty string, or a refusal naming what arrived instead."""
    if not isinstance(value, str) or not value:
        raise DeployError("%s must be a non-empty string, not %s"
                          % (what, type(value).__name__))
    return value


def _count(value, what):
    """An int, or a refusal naming what arrived instead."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DeployError("%s must be an int, not %s" % (what, type(value).__name__))
    return value


def _tick(tick):
    """A tick at or after zero, or a refusal naming what arrived instead."""
    tick = _count(tick, "the tick")
    if tick < 0:
        raise DeployError("the tick is zero or more, not %d" % (tick,))
    return tick


def _manifest(manifest):
    """The manifest's six fields, in MANIFEST_KEYS order, or a refusal naming it."""
    if not isinstance(manifest, dict):
        raise DeployError("a manifest is a mapping with the keys %r, not %s"
                          % (MANIFEST_KEYS, type(manifest).__name__))
    got = tuple(manifest)
    if got != MANIFEST_KEYS:
        raise DeployError("a manifest has the keys %r, and they must be %r"
                          % (got, MANIFEST_KEYS))
    _text(manifest["name"], "the manifest's name")
    _text(manifest["namespace"], "the manifest's namespace")
    _text(manifest["node_zone"], "the manifest's node_zone")
    _count(manifest["replicas"], "the manifest's replicas")
    if not isinstance(manifest["images"], tuple):
        raise DeployError("the manifest's images are a tuple of image references, "
                          "not %s" % (type(manifest["images"]).__name__,))
    if not isinstance(manifest["env"], tuple):
        raise DeployError("the manifest's env is a tuple of strings, not %s"
                          % (type(manifest["env"]).__name__,))
    for index, line in enumerate(manifest["env"]):
        if not isinstance(line, str):
            raise DeployError("env[%d] must be a string, not %s"
                              % (index, type(line).__name__))
    return manifest


def _reference(entry):
    """One image reference (name, tag and pinned digest), or a refusal naming it."""
    if not isinstance(entry, dict):
        raise DeployError("an image reference is a mapping with the keys %r, not %s"
                          % (_REFERENCE_KEYS, type(entry).__name__))
    for key in _REFERENCE_KEYS:
        if key not in entry:
            raise DeployError("an image reference has no %r: %r" % (key, tuple(entry)))
        _text(entry[key], "an image reference's %s" % (key,))
    return entry


def _ref(entry):
    """An image reference as the one string every problem about it prints."""
    return "%s:%s" % (entry["name"], entry["tag"])


def _registry(network):
    """The registry, keyed by the name and tag it holds an image under."""
    return {(image["name"], image["tag"]): image for image in network.images()}


def _by_digest(network):
    """The registry, keyed by the digest the customer's security review pinned."""
    return {image["digest"]: image for image in network.images()}


def _instance(name, node, slot):
    """An instance's name: the deployment, the node it runs on, and its slot."""
    return _INSTANCE % (name, node, slot)


def _node_of(subject):
    """The node an instance name names, or the subject itself when it names none."""
    parts = subject.split(":")
    return parts[1] if len(parts) == 3 else subject


def _nodes_of(steps):
    """The nodes the plan's own start steps name, in the order it names them."""
    nodes = []
    for action, subject in steps:
        if action == "start":
            node = _node_of(subject)
            if node not in nodes:
                nodes.append(node)
    return nodes


def _steps(plan):
    """A plan: a tuple of `(action, subject)` pairs with actions from STEPS."""
    if not isinstance(plan, (tuple, list)):
        raise DeployError("a plan is a tuple of (action, subject) pairs, not %s"
                          % (type(plan).__name__,))
    checked = []
    for step in plan:
        if not isinstance(step, (tuple, list)) or len(step) != 2:
            raise DeployError("a plan step is an (action, subject) pair, not %r"
                              % (step,))
        action, subject = step
        if action not in STEPS:
            raise DeployError("a plan step's action is one of %r, not %r"
                              % (STEPS, action))
        checked.append((action, _text(subject, "a plan step's subject")))
    return tuple(checked)


def _state(state):
    """A deployment state as DEPLOY_KEYS, or a refusal naming what is wrong."""
    if not isinstance(state, dict):
        raise DeployError("a deployment is a mapping with the keys %r, not %s"
                          % (DEPLOY_KEYS, type(state).__name__))
    got = tuple(state)
    if got != DEPLOY_KEYS:
        raise DeployError("a deployment has the keys %r, and they must be %r"
                          % (got, DEPLOY_KEYS))
    _text(state["namespace"], "the deployment's namespace")
    for key in ("installed", "running"):
        if not isinstance(state[key], tuple) or [item for item in state[key]
                                                 if not isinstance(item, str)]:
            raise DeployError("the deployment's %s is a tuple of strings, not %r"
                              % (key, state[key]))
    if _count(state["steps_done"], "the deployment's steps_done") < 0:
        raise DeployError("the deployment's steps_done is zero or more, not %d"
                          % (state["steps_done"],))
    if state["verdict"] not in _VERDICTS:
        raise DeployError("the deployment's verdict is one of %r, not %r"
                          % (_VERDICTS, state["verdict"]))
    return state


def validate(manifest, network):
    """What is wrong with `manifest` on `network`, in PROBLEMS order."""
    fields = _manifest(manifest)
    found = {problem: [] for problem in PROBLEMS}

    def note(problem, offender):
        if not found[problem]:
            found[problem].append(offender)

    namespace = fields["namespace"]
    if not (namespace == estate.ESTATE_NAME
            or namespace.startswith(estate.ESTATE_NAME + "-")):
        note("bad-namespace", namespace)
    if fields["replicas"] < 1:
        note("bad-replicas", fields["replicas"])

    registry = _registry(network)
    images = []
    seen = []
    for entry in fields["images"]:
        entry = _reference(entry)
        key = (entry["name"], entry["tag"])
        if key in seen:
            note("duplicate-image", entry["digest"])
        seen.append(key)
        record = registry.get(key)
        if record is None:
            note("unknown-image", _ref(entry))
            continue
        if entry["digest"] != record["digest"]:
            note("unpinned-digest", _ref(entry))
            continue
        if not network.pullable(record):
            note("not-in-bundle", record["digest"])
        images.append(record)

    egress = ()
    zone = fields["node_zone"]
    if zone not in network.rules():
        note("no-node", zone)
    else:
        if not network.usable(zone):
            note("no-node", zone)
        egress = tuple((zone, destination) for destination in network.rules()[zone])
        if network.reaches(zone, _PUBLIC):
            note("would-egress", _PUBLIC)

    problems = tuple((problem, found[problem][0]) for problem in PROBLEMS
                     if found[problem])
    return {"ok": not problems, "problems": problems, "images": tuple(images),
            "egress": egress}


def plan(manifest, network):
    """The ordered `(action, subject)` steps for `manifest`, and its problems."""
    answer = validate(manifest, network)
    if not answer["ok"]:
        return (), answer["problems"]
    fields = _manifest(manifest)
    nodes = tuple(node["name"] for node in network.usable(fields["node_zone"]))
    steps = [("pull", record["digest"]) for record in answer["images"]]
    steps += [("install", record["digest"]) for record in answer["images"]]
    for replica in range(fields["replicas"]):
        node = nodes[replica % len(nodes)]
        steps.append(("start",
                      _instance(fields["name"], node, replica // len(nodes))))
    return tuple(steps), ()


def deploy(plan, network, namespace, tick):
    """Run `plan`'s steps against `network`, answering `DEPLOY_KEYS`."""
    steps = _steps(plan)
    namespace = _text(namespace, "the namespace")
    tick = _tick(tick)
    nodes = _nodes_of(steps)
    installs = tuple(subject for action, subject in steps if action == "install")
    if not steps or (installs and not nodes):
        return {"namespace": namespace, "installed": (), "running": (),
                "steps_done": 0, "verdict": "refused"}
    registry = _by_digest(network)
    installed = []
    running = []
    done = 0
    verdict = "deployed"
    for action, subject in steps:
        if action == "pull":
            record = registry.get(subject)
            if record is None:
                verdict = "refused"
                break
            try:
                network.pull(record["name"], record["tag"], tick)
            except NetworkError:
                verdict = "refused"
                break
        elif action == "install":
            try:
                network.install(subject, nodes[len(installed) % len(nodes)], tick)
            except NetworkError:
                verdict = "refused"
                break
            installed.append(subject)
        else:
            running.append(subject)
        done += 1
    return {"namespace": namespace, "installed": tuple(sorted(installed)),
            "running": tuple(running), "steps_done": done, "verdict": verdict}


def rollback(state):
    """`state` stopped: the same deployment as `DEPLOY_KEYS`, `running` empty."""
    state = _state(state)
    return {"namespace": state["namespace"], "installed": tuple(state["installed"]),
            "running": (), "steps_done": state["steps_done"],
            "verdict": "rolled-back"}


def _zone_of(network, node):
    """The zone of a node, or None when no machine of the network has that name."""
    try:
        return network.node(node)["zone"]
    except NetworkError:
        return None


def verify(state, network):
    """Whether the world's own log agrees with `state`, as `{"ok", "problems"}`."""
    state = _state(state)
    log = network.log()
    found = {problem: [] for problem in _VERIFY_PROBLEMS}

    def note(problem, offender):
        if offender not in found[problem]:
            found[problem].append(offender)

    registry = _by_digest(network)
    pulled = tuple(line["target"] for line in log if line["action"] == "pull")
    installs = [line for line in log if line["action"] == "install"]
    for digest in state["installed"]:
        if digest not in pulled:
            note("not-pulled", digest)
        record = registry.get(digest)
        if record is None or not network.pullable(record):
            note("not-in-bundle", digest)
    for line in log:
        if (line["action"] == "attempt" and line["target"] == _PUBLIC
                and line["verdict"] == "allowed"):
            note("public-attempted", _PUBLIC)
    zone = installs[0]["zone"] if installs else None
    for line in installs:
        if line["zone"] != zone:
            note("wrong-zone", line["reason"])
    running = []
    for instance in state["running"]:
        node = _node_of(instance)
        running.append(node)
        if _zone_of(network, node) != zone:
            note("wrong-zone", node)
    for line in installs:
        if line["reason"] not in running:
            note("not-running", line["reason"])
    problems = tuple((problem, offender) for problem in _VERIFY_PROBLEMS
                     for offender in found[problem])
    return {"ok": not problems, "problems": problems}
