"""
Edge Computing — Complete Solution
"""

import time
import hashlib
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple


class EdgeNode:
    def __init__(self, node_id: str, region: str, latency_ms: float):
        self.node_id = node_id
        self.region = region
        self.latency_ms = latency_ms
        self.healthy = True


class LatencyRouter:
    def __init__(self):
        self._nodes: Dict[str, EdgeNode] = {}

    def add_node(self, node: EdgeNode) -> None:
        self._nodes[node.node_id] = node

    def route(self, client_latencies: Dict[str, float]) -> Optional[EdgeNode]:
        healthy = [n for n in self._nodes.values() if n.healthy]
        if not healthy:
            return None
        return min(healthy, key=lambda n: client_latencies.get(n.node_id, float("inf")))

    def mark_unhealthy(self, node_id: str) -> None:
        self._nodes[node_id].healthy = False

    def mark_healthy(self, node_id: str) -> None:
        self._nodes[node_id].healthy = True

    @property
    def healthy_count(self) -> int:
        return sum(1 for b in self._nodes.values() if b.healthy)


class Request:
    def __init__(self, method: str, path: str, headers: Optional[Dict[str, str]] = None,
                 body: Any = None):
        self.method = method
        self.path = path
        self.headers: Dict[str, str] = headers or {}
        self.body = body
        self.attributes: Dict[str, Any] = {}


class Response:
    def __init__(self, status: int = 200, body: Any = None,
                 headers: Optional[Dict[str, str]] = None):
        self.status = status
        self.body = body
        self.headers: Dict[str, str] = headers or {}


class EdgeMiddlewarePipeline:
    def __init__(self):
        self._middlewares = []

    def use(self, middleware) -> None:
        self._middlewares.append(middleware)

    def handle(self, request: Request, final_handler: Callable) -> Response:
        chain = final_handler
        for mw in reversed(self._middlewares):
            next_handler = chain
            def make_chain(m, nxt):
                def chained(req):
                    return m(req, nxt)
                return chained
            chain = make_chain(mw, next_handler)
        return chain(request)


class ABTestRouter:
    def __init__(self):
        self._experiments: Dict[str, Tuple[List[str], List[float]]] = {}

    def add_experiment(self, name: str, variants: List[str], weights: List[float]) -> None:
        assert len(variants) == len(weights)
        assert abs(sum(weights) - 1.0) < 1e-6
        self._experiments[name] = (variants, weights)

    def get_variant(self, experiment_name: str, user_id: str) -> str:
        variants, weights = self._experiments[experiment_name]
        bucket = int(hashlib.md5(f"{experiment_name}:{user_id}".encode()).hexdigest(), 16) % 100
        cumulative = 0.0
        for variant, weight in zip(variants, weights):
            cumulative += weight * 100
            if bucket < cumulative:
                return variant
        return variants[-1]


class EdgeFunctionError(Exception):
    pass


class EdgeRuntime:
    def __init__(self, cpu_limit_ms: float = 50.0):
        self.cpu_limit_ms = cpu_limit_ms
        self._functions: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        self._functions[name] = fn

    def invoke(self, name: str, request: Request) -> Response:
        fn = self._functions[name]
        result = [None]
        exc = [None]

        def target():
            try:
                result[0] = fn(request)
            except Exception as e:
                exc[0] = e

        t = threading.Thread(target=target, daemon=True)
        t.start()
        t.join(timeout=self.cpu_limit_ms / 1000.0)
        if t.is_alive():
            raise EdgeFunctionError(f"{name}: exceeded CPU limit")
        if exc[0]:
            raise exc[0]
        return result[0]


def _test():
    print("Testing LatencyRouter...")
    router = LatencyRouter()
    router.add_node(EdgeNode("us-east", "us-east", 5.0))
    router.add_node(EdgeNode("eu-west", "eu-west", 80.0))
    router.add_node(EdgeNode("ap-south", "ap-south", 150.0))

    client_latencies = {"us-east": 5.0, "eu-west": 80.0, "ap-south": 150.0}
    best = router.route(client_latencies)
    assert best.node_id == "us-east"

    router.mark_unhealthy("us-east")
    best2 = router.route(client_latencies)
    assert best2.node_id == "eu-west"
    print("  LatencyRouter: OK")

    print("Testing EdgeMiddlewarePipeline...")
    pipeline = EdgeMiddlewarePipeline()

    def auth_middleware(req, next_handler):
        if req.headers.get("Authorization") != "Bearer valid-token":
            return Response(status=401, body="Unauthorized")
        return next_handler(req)

    def geo_middleware(req, next_handler):
        req.attributes["country"] = req.headers.get("CF-IPCountry", "US")
        return next_handler(req)

    pipeline.use(auth_middleware)
    pipeline.use(geo_middleware)

    def final(req):
        return Response(status=200, body=f"Hello from {req.attributes.get('country')}")

    resp = pipeline.handle(Request("GET", "/", headers={}), final)
    assert resp.status == 401

    resp = pipeline.handle(
        Request("GET", "/", headers={"Authorization": "Bearer valid-token",
                                      "CF-IPCountry": "DE"}),
        final
    )
    assert resp.status == 200
    assert resp.body == "Hello from DE"
    print("  EdgeMiddlewarePipeline: OK")

    print("Testing ABTestRouter...")
    ab = ABTestRouter()
    ab.add_experiment("homepage_cta", ["control", "variant_a"], [0.5, 0.5])
    v1 = ab.get_variant("homepage_cta", "user-123")
    v2 = ab.get_variant("homepage_cta", "user-123")
    assert v1 == v2
    assert v1 in ("control", "variant_a")
    variants = [ab.get_variant("homepage_cta", f"user-{i}") for i in range(1000)]
    control_count = variants.count("control")
    assert 400 <= control_count <= 600
    print("  ABTestRouter: OK")

    print("Testing EdgeRuntime...")
    runtime = EdgeRuntime(cpu_limit_ms=100.0)

    def fast_fn(req):
        return Response(status=200, body="fast")

    def slow_fn(req):
        time.sleep(0.5)
        return Response(status=200, body="slow")

    runtime.register("fast", fast_fn)
    runtime.register("slow", slow_fn)
    resp = runtime.invoke("fast", Request("GET", "/"))
    assert resp.status == 200 and resp.body == "fast"

    try:
        runtime.invoke("slow", Request("GET", "/"))
        assert False
    except EdgeFunctionError:
        pass
    print("  EdgeRuntime: OK")

    print("\nAll edge computing tests passed!")


if __name__ == "__main__":
    _test()
