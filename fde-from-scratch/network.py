"""network.py — the customer's basement: zones, egress policy, images and machines.

Provided, frozen, and never written by the course. This module is the environment an
FDE has to fit into:

* the **egress policy** is a table (`rules`), not a firewall with opinions:
  `reaches(zone, destination)` is a lookup and `attempt` records the reach-out either
  way. A customer with no route to `"public"` is a customer whose AI cannot phone
  home, and the only way to prove a deployment respected that is the log;
* the **registry** holds images by name and tag, each with the digest the customer's
  security review pinned; the **bundle** is the removable media that carries digests
  across the air gap, and something the registry holds can still be missing from it;
* the **nodes** are machines (`NODE_KEYS`) with CPU, memory, and in the GPU zone a
  card with its own memory; the **models** are the local variants (`MODEL_KEYS`) a
  customer is allowed to run, each with a quantisation, a memory footprint, a
  throughput and a quality score.

Everything is a function of the seed, and `stats()` is recomputed from the log.
"""

from estate import EstateError, digest, _int, _stream, _text

ZONES = ("mgmt", "app", "data", "gpu")
DESTINATIONS = ("registry", "public", "vendor", "storage", "telemetry")
QUANTS = ("awq-4bit", "gguf-q4", "gguf-q8", "fp16")
IMAGE_KEYS = ("name", "tag", "digest", "size_mb", "zone")
NODE_KEYS = ("name", "zone", "cpu", "memory_mb", "gpus", "gpu_memory_mb")
MODEL_KEYS = ("name", "params_m", "quant", "memory_mb", "tokens_per_tick", "quality")

NETWORK_ERROR = "the network refuses: %s"


class NetworkError(EstateError):
    """The environment's refusal: an image it does not hold, a node it does not have."""


def _need(mapping, keys, what):
    """Check a mapping's keys are exactly `keys`, in order, and answer it."""
    if not isinstance(mapping, dict):
        raise NetworkError(NETWORK_ERROR % ("%s is a %s, not a mapping"
                                            % (what, type(mapping).__name__)))
    got = tuple(mapping)
    if got != tuple(keys):
        raise NetworkError(NETWORK_ERROR % ("%s has the keys %r, not %r"
                                            % (what, got, tuple(keys))))
    return mapping


class Network:
    """The customer's network, registry, bundle, machines and model catalogue.

    `Network(rules, registry, bundle, nodes, models)` takes all five as data:
    `rules` maps a zone to the destinations it may reach, `registry` is a tuple of
    `IMAGE_KEYS`, `bundle` is a tuple of digests that physically crossed the air gap,
    `nodes` is a tuple of `NODE_KEYS` and `models` a tuple of `MODEL_KEYS`.
    """

    def __init__(self, rules, registry, bundle, nodes, models):
        if not isinstance(rules, dict) or not rules:
            raise NetworkError(NETWORK_ERROR % "an egress policy is a non-empty mapping")
        self._rules = {}
        for zone in rules:
            if zone not in ZONES:
                raise NetworkError(NETWORK_ERROR % ("%r is not one of the zones %r"
                                                    % (zone, ZONES)))
            destinations = tuple(rules[zone])
            for destination in destinations:
                if destination not in DESTINATIONS:
                    raise NetworkError(NETWORK_ERROR % ("%r is not one of the destinations %r"
                                                        % (destination, DESTINATIONS)))
            self._rules[zone] = destinations
        self._registry = {}
        for image in registry:
            record = _need(dict(image), IMAGE_KEYS, "an image")
            self._registry[(record["name"], record["tag"])] = record
        self._bundle = tuple(bundle)
        self._nodes = {}
        for node in nodes:
            record = _need(dict(node), NODE_KEYS, "a node")
            if record["zone"] not in ZONES:
                raise NetworkError(NETWORK_ERROR % ("node %r is in %r, not one of %r"
                                                    % (record["name"], record["zone"], ZONES)))
            self._nodes[record["name"]] = record
        self._models = {}
        for model in models:
            record = _need(dict(model), MODEL_KEYS, "a model")
            if record["quant"] not in QUANTS:
                raise NetworkError(NETWORK_ERROR % ("model %r is %r, not one of %r"
                                                    % (record["name"], record["quant"], QUANTS)))
            self._models[record["name"]] = record
        self._log = []

    # -- the policy ---------------------------------------------------------
    def rules(self):
        """The egress policy as data: zone -> the destinations it may reach."""
        return {zone: self._rules[zone] for zone in self._rules}

    def reaches(self, zone, destination):
        """Whether `zone` may reach `destination` — a lookup, and nothing else."""
        if zone not in self._rules:
            raise NetworkError(NETWORK_ERROR % ("%r is not one of the zones %r" % (zone, ZONES)))
        if destination not in DESTINATIONS:
            raise NetworkError(NETWORK_ERROR % ("%r is not one of the destinations %r"
                                                % (destination, DESTINATIONS)))
        return destination in self._rules[zone]

    def attempt(self, zone, destination, tick):
        """Record a reach-out and answer whether the policy allows it.

        This is the world's own record, not a guard: it refuses nothing, it logs the
        attempt and the verdict and answers both with the rule that decided it.
        """
        allowed = self.reaches(zone, destination)
        reason = ("%s may reach %s" % (zone, destination) if allowed
                  else "%s may not reach %s" % (zone, destination))
        self._log.append({"tick": _int(tick, "the tick"), "action": "attempt",
                          "target": destination, "zone": zone,
                          "verdict": "allowed" if allowed else "blocked",
                          "reason": reason})
        return {"allowed": allowed, "rules": self._rules[zone], "reason": reason}

    # -- the registry and the bundle ---------------------------------------
    def images(self):
        """Every image the internal registry holds, in insertion order."""
        return tuple(self._registry[key] for key in self._registry)

    def image(self, name, tag):
        """One image by name and tag; an image the registry lacks is refused."""
        key = (name, tag)
        if key not in self._registry:
            raise NetworkError(NETWORK_ERROR % ("the registry does not hold %s:%s"
                                                % (name, tag)))
        return dict(self._registry[key])

    def pullable(self, image):
        """Whether the bundle physically carries this image's digest."""
        record = _need(dict(image), IMAGE_KEYS, "an image")
        return record["digest"] in self._bundle

    def pull(self, name, tag, tick):
        """The act that crosses the air gap: take an image out of the bundle.

        Refused, naming the offender: an image the registry does not hold, and an
        image whose digest is not in the bundle.
        """
        record = self.image(name, tag)
        if not self.pullable(record):
            raise NetworkError(NETWORK_ERROR % ("digest %s of %s:%s is not in the bundle"
                                                % (record["digest"], name, tag)))
        self._log.append({"tick": _int(tick, "the tick"), "action": "pull",
                          "target": record["digest"], "zone": record["zone"],
                          "verdict": "pulled",
                          "reason": "%s:%s" % (name, tag)})
        return dict(record)

    def install(self, digest_value, node_name, tick):
        """Record an install of a pinned digest onto a node, both named."""
        if digest_value not in self._bundle:
            raise NetworkError(NETWORK_ERROR % ("digest %s is not in the bundle"
                                                % (digest_value,)))
        if node_name not in self._nodes:
            raise NetworkError(NETWORK_ERROR % ("no such node %r" % (node_name,)))
        node = self._nodes[node_name]
        self._log.append({"tick": _int(tick, "the tick"), "action": "install",
                          "target": digest_value, "zone": node["zone"],
                          "verdict": "installed", "reason": node_name})
        return dict(node)

    # -- the machines and the models ---------------------------------------
    def nodes(self):
        """Every machine, in insertion order."""
        return tuple(self._nodes.values())

    def node(self, name):
        """One machine by name; an unknown node is refused by name."""
        if name not in self._nodes:
            raise NetworkError(NETWORK_ERROR % ("no such node %r" % (name,)))
        return dict(self._nodes[name])

    def usable(self, zone):
        """The machines in `zone`, in insertion order."""
        if zone not in ZONES:
            raise NetworkError(NETWORK_ERROR % ("%r is not one of the zones %r" % (zone, ZONES)))
        return tuple(node for node in self._nodes.values() if node["zone"] == zone)

    def models(self):
        """Every local model variant, in insertion order."""
        return tuple(self._models.values())

    def model(self, name):
        """One variant by name; an unknown variant is refused by name."""
        if name not in self._models:
            raise NetworkError(NETWORK_ERROR % ("no such model %r" % (name,)))
        return dict(self._models[name])

    # -- the record ---------------------------------------------------------
    def log(self):
        """Every line this network wrote, in order."""
        return tuple(self._log)

    def stats(self):
        """Counters recomputed from the log: attempts, verdicts, pulls, installs."""
        return {
            "attempts": len([line for line in self._log if line["action"] == "attempt"]),
            "allowed": len([line for line in self._log
                            if line["action"] == "attempt" and line["verdict"] == "allowed"]),
            "blocked": len([line for line in self._log
                            if line["action"] == "attempt" and line["verdict"] == "blocked"]),
            "pulls": len([line for line in self._log if line["action"] == "pull"]),
            "installs": len([line for line in self._log if line["action"] == "install"]),
        }

    @classmethod
    def build(cls, seed=7):
        """The customer's basement: no zone reaches `"public"`, and one image is missing."""
        stream = _stream(seed + 3)
        rules = {"mgmt": ("telemetry",), "app": ("registry", "storage"),
                 "data": ("registry", "storage"), "gpu": ()}
        names = (("north-api", "1.4.0"), ("north-worker", "1.4.0"),
                 ("north-index", "0.9.2"), ("otel-collector", "0.61.0"),
                 ("north-gateway", "1.4.0"))
        registry = []
        for name, tag in names:
            draw = next(stream)
            registry.append({"name": name, "tag": tag, "digest": digest(name, tag),
                             "size_mb": 120 + draw % 900, "zone": "app"})
        # The bundle carries everything the customer was told to carry, minus one:
        # the image that must be refused is the point of the exercise.
        bundle = tuple(image["digest"] for image in registry[:-1])
        nodes = (
            {"name": "mgmt-1", "zone": "mgmt", "cpu": 4, "memory_mb": 8192, "gpus": 0,
             "gpu_memory_mb": 0},
            {"name": "app-1", "zone": "app", "cpu": 16, "memory_mb": 65536, "gpus": 0,
             "gpu_memory_mb": 0},
            {"name": "app-2", "zone": "app", "cpu": 16, "memory_mb": 65536, "gpus": 0,
             "gpu_memory_mb": 0},
            {"name": "data-1", "zone": "data", "cpu": 32, "memory_mb": 131072, "gpus": 0,
             "gpu_memory_mb": 0},
            {"name": "gpu-1", "zone": "gpu", "cpu": 8, "memory_mb": 65536, "gpus": 1,
             "gpu_memory_mb": 8192},
            {"name": "gpu-2", "zone": "gpu", "cpu": 16, "memory_mb": 131072, "gpus": 1,
             "gpu_memory_mb": 24576},
        )
        models = (
            {"name": "north-8b-awq", "params_m": 8000, "quant": "awq-4bit",
             "memory_mb": 6144, "tokens_per_tick": 900, "quality": 84},
            {"name": "north-8b-gguf-q4", "params_m": 8000, "quant": "gguf-q4",
             "memory_mb": 5120, "tokens_per_tick": 700, "quality": 80},
            {"name": "north-8b-gguf-q8", "params_m": 8000, "quant": "gguf-q8",
             "memory_mb": 9216, "tokens_per_tick": 640, "quality": 86},
            {"name": "north-8b-fp16", "params_m": 8000, "quant": "fp16",
             "memory_mb": 16384, "tokens_per_tick": 480, "quality": 88},
            {"name": "north-70b-awq", "params_m": 70000, "quant": "awq-4bit",
             "memory_mb": 42000, "tokens_per_tick": 120, "quality": 92},
        )
        return cls(rules, registry, bundle, nodes, models)
