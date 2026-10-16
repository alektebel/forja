"""FDE From Scratch — stage 8: The model that fits the customer's GPU.

The solution. Two records and nothing else decide a fit — the node's card, the
quantisation of the variant, and the integer headroom rule, in that ladder order —
and everything a placement or a scheduler refuses is data: a reason with the
offender in it. `place` orders the customer's catalogue itself (highest quality,
then highest throughput, then name) instead of trusting the order the records
arrived in, and the `Scheduler` keeps only three lists of its own: the queue, the
names served, and the refusals, each in the order they happened.

What the scheduler never does: touch the world. It asks the network two questions
(`reaches`, and the catalogue lookups at construction), writes nothing, and serves
`tokens_per_tick` tokens per `drain` — which is what makes the reported `waiting`
a measurement and what makes the budget a rule rather than a formality.
"""

import estate
import network

FIT_REASONS = ("unknown-model", "unknown-node", "no-gpu", "gpu-memory",
               "unknown-quant", "zone")
HEADROOM = 90
QUEUE_MAX = 4
BUDGET_TICKS = 3
SUBMISSION_KEYS = ("name", "tokens", "tick", "state", "waiting")
SERVE_REASONS = ("no-capacity", "budget", "egress", "unknown-model")

_EDGE = "the edge refuses: %s"


class EdgeError(estate.EstateError):
    """The edge's refusal: a shape it cannot accept, and nothing about the weather."""


def _edge(why):
    """The edge's refusal, saying what it refused."""
    return EdgeError(_EDGE % (why,))


def _need(mapping, keys, what):
    """The mapping, once its keys are exactly `keys` in order; refused naming it otherwise."""
    if not isinstance(mapping, dict):
        raise _edge("%s is a %s, not a mapping" % (what, type(mapping).__name__))
    got = tuple(mapping)
    if got != tuple(keys):
        raise _edge("%s has the keys %r, not %r" % (what, got, tuple(keys)))
    return mapping


def _whole(value, what):
    """The whole number, refused naming it when it is anything else (a bool is not one)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise _edge("%s is %r, not a whole number" % (what, value))
    return value


def _text(value, what):
    """The string, refused naming it when it is anything else."""
    if not isinstance(value, str):
        raise _edge("%s is a %s, not a string" % (what, type(value).__name__))
    return value


def _sequence(value, what):
    """The sequence of records, refused naming what arrived in its place."""
    if not isinstance(value, (tuple, list)):
        raise _edge("%s is a %s, not a tuple of records"
                    % (what, type(value).__name__))
    return value


def _zone(zone):
    """The requested zone, refused naming it when the world has no such zone."""
    if zone not in network.ZONES:
        raise _edge("%r is not one of the zones %r" % (zone, network.ZONES))
    return zone


def fits(model, node):
    """Whether a model variant fits a machine, as `(True, None)` or `(False, reason)`.

    `model` and `node` are `MODEL_KEYS` and `NODE_KEYS` records; a name handed where
    a record belongs is `unknown-model` or `unknown-node`, because this function
    holds no catalogue to look one up in. The ladder is the node's card, the
    quantisation, then the integer headroom rule, and the reason names the rung that
    said no.
    """
    if isinstance(model, str):
        return (False, "unknown-model")
    if isinstance(node, str):
        return (False, "unknown-node")
    model = _need(model, network.MODEL_KEYS, "the model")
    node = _need(node, network.NODE_KEYS, "the node")
    if _whole(node["gpus"], "the node's gpus") <= 0:
        return (False, "no-gpu")
    if model["quant"] not in network.QUANTS:
        return (False, "unknown-quant")
    needed = _whole(model["memory_mb"], "the model's memory_mb") * 100
    card = _whole(node["gpu_memory_mb"], "the node's gpu_memory_mb") * HEADROOM
    if needed > card:
        return (False, "gpu-memory")
    return (True, None)


def _rank_key(model):
    """The ordering `place` trusts: highest quality, then throughput, then name."""
    record = _need(model, network.MODEL_KEYS, "a model")
    return (-_whole(record["quality"], "the model's quality"),
            -_whole(record["tokens_per_tick"], "the model's tokens_per_tick"),
            _text(record["name"], "the model's name"))


def place(models, nodes, zone):
    """The best model a zone can run: `(model, node, None)` or `(None, None, reason)`.

    The model is the highest `quality`, ties broken by the higher `tokens_per_tick`
    and then by name, and its node is the first machine in `zone` it fits; when
    nothing fits, the reason is the one that kept the best model off the zone.
    """
    _zone(zone)
    models = _sequence(models, "the models")
    nodes = _sequence(nodes, "the nodes")
    if not models:
        return (None, None, "unknown-model")
    if not nodes:
        return (None, None, "unknown-node")
    for model in models:
        if isinstance(model, str):
            return (None, None, "unknown-model")
    for node in nodes:
        if isinstance(node, str):
            return (None, None, "unknown-node")
    ranked = sorted(models, key=_rank_key)
    for node in nodes:
        _need(node, network.NODE_KEYS, "a node")
    for model in ranked:
        for node in nodes:
            if node["zone"] != zone:
                continue
            if fits(model, node)[0]:
                return (model, node, None)
    inside = [node for node in nodes if node["zone"] == zone]
    if not inside:
        return (None, None, "zone")
    return (None, None, fits(ranked[0], inside[0])[1])


def _gateway(network_value):
    """The customer's network, refused naming it when it cannot answer this stage."""
    for method in ("reaches", "model", "node"):
        if not hasattr(network_value, method):
            raise _edge("the network is %r, and it cannot %s()"
                        % (network_value, method))
    return network_value


def _variant(network_value, model):
    """The catalogue's own record for a model record or a name, or None when unknown."""
    if isinstance(model, str):
        name = model
    else:
        name = _text(_need(model, network.MODEL_KEYS, "the model")["name"],
                     "the model's name")
    try:
        return network_value.model(name)
    except network.NetworkError:
        return None


def _machine(network_value, node, zone):
    """The network's own record for a node record or a name, of the zone being served."""
    if isinstance(node, str):
        name = node
    else:
        name = _text(_need(node, network.NODE_KEYS, "the node")["name"],
                     "the node's name")
    try:
        record = network_value.node(name)
    except network.NetworkError:
        raise _edge("the network holds no node %r" % (name,))
    if record["zone"] != zone:
        raise _edge("the node %r is in %r, and this deployment serves %r"
                    % (name, record["zone"], zone))
    return record


class Scheduler:
    """One model on one machine in one zone: what it serves, and what it refuses.

    `model` and `node` are records or names the customer's own network holds, and
    `zone` is the zone this deployment serves. Construction is the wiring — a model
    that does not fit its node, a node of another zone or a zone that is not a zone
    are refused here, naming the offender, because no submission could make them
    right — while a *model* the network's catalogue does not hold is remembered and
    returned as the `unknown-model` serve reason on every submission.
    """

    def __init__(self, model, node, network, zone):
        """Resolve the variant and the machine, and refuse a wiring that cannot serve.

        `network` is the customer's own `network.Network`. A submission asks about
        this deployment, so everything that cannot be a deployment — the network,
        the zone, the node, the fit — is refused here, by name; only a model the
        catalogue does not hold is deferred, because it has a serve reason of its own.
        """
        self._network = _gateway(network)
        self._zone = _zone(zone)
        self._node = _machine(self._network, node, self._zone)
        self._model = _variant(self._network, model)
        self._problem = None if self._model is not None else "unknown-model"
        if self._model is not None:
            ok, why = fits(self._model, self._node)
            if not ok:
                raise _edge("the model %r does not fit the node %r: %s"
                            % (self._model["name"], self._node["name"], why))
        self._tokens = self._model["tokens_per_tick"] if self._model is not None else 0
        self._queue = []
        self._served = []
        self._refused = []
        self._tick = 0

    def submit(self, name, tokens, tick):
        """Offer one submission and answer its `SUBMISSION_KEYS`.

        Accepted work is `"queued"`; a submission that would wait more than
        `BUDGET_TICKS`, a full queue, a zone that reaches `"public"` and a model the
        catalogue does not hold are answered `"refused"` with the reason, and none of
        them takes a queue slot. The ladder is ordered: egress first (a zone that may
        phone home serves nothing at all), then the unknown model, then the queue's
        own capacity, and only then this submission's wait.
        """
        name = _text(name, "the submission name")
        if not name:
            raise _edge("the submission name is empty")
        tokens = _whole(tokens, "the submission's tokens")
        if tokens <= 0:
            raise _edge("the submission %r asks for %r tokens, not a positive whole "
                        "number" % (name, tokens))
        tick = _whole(tick, "the submission's tick")
        self._tick = max(self._tick, tick)
        reason = None
        if self._network.reaches(self._zone, "public"):
            reason = "egress"
        elif self._problem is not None:
            reason = self._problem
        elif len(self._queue) >= QUEUE_MAX:
            reason = "no-capacity"
        elif self._wait(tokens) > BUDGET_TICKS:
            reason = "budget"
        if reason is None:
            self._queue.append({"name": name, "tokens": tokens, "tick": tick,
                                "remaining": tokens})
            return {"name": name, "tokens": tokens, "tick": tick, "state": "queued",
                    "waiting": self._tick - tick}
        self._refused.append((name, reason))
        return {"name": name, "tokens": tokens, "tick": tick, "state": "refused",
                "waiting": 0}

    def _wait(self, tokens):
        """The ticks a submission of `tokens` would wait: the work ahead, plus its own."""
        ahead = sum(entry["remaining"] for entry in self._queue) + tokens
        return -(-ahead // self._tokens)

    def drain(self, tick):
        """Serve up to `tokens_per_tick` tokens and answer the submissions that finished.

        One call is one tick of the model's throughput: the queue is worked in
        submission order, a submission is served only when its own last token has
        been spent, and a drain at a tick before a queued submission's own is refused
        naming both ticks rather than answering a negative wait.
        """
        tick = _whole(tick, "the tick")
        for entry in self._queue:
            if entry["tick"] > tick:
                raise _edge("the queue holds %r submitted at tick %r, and this drain "
                            "is tick %r" % (entry["name"], entry["tick"], tick))
        self._tick = max(self._tick, tick)
        served = []
        budget = self._tokens
        while budget > 0 and self._queue:
            head = self._queue[0]
            spend = head["remaining"] if head["remaining"] < budget else budget
            head["remaining"] = head["remaining"] - spend
            budget = budget - spend
            if head["remaining"] == 0:
                self._queue.pop(0)
                self._served.append(head["name"])
                served.append({"name": head["name"], "tokens": head["tokens"],
                               "tick": head["tick"], "state": "served",
                               "waiting": tick - head["tick"]})
        return tuple(served)

    def queue(self):
        """The queued submissions, in submission order, each with the ticks it has waited."""
        return tuple({"name": entry["name"], "tokens": entry["tokens"],
                      "tick": entry["tick"], "state": "queued",
                      "waiting": self._tick - entry["tick"]}
                     for entry in self._queue)

    def served(self):
        """The names served so far, in service order."""
        return tuple(self._served)

    def refused(self):
        """The `(name, reason)` pairs refused so far, in refusal order."""
        return tuple(self._refused)
