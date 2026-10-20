"""
Edge Computing — From Scratch
==============================
Build edge computing primitives to understand:
- Routing requests to the nearest edge node (latency-based routing)
- Edge middleware: run lightweight logic at the edge (auth, geo-block, A/B test)
- Edge-side personalization: inject dynamic fragments close to the user
- Function invocation at the edge with strict constraints (small, fast, stateless)

Edge computing moves computation closer to the user to reduce latency and
offload the origin. Examples: Cloudflare Workers, AWS Lambda@Edge, Fastly Compute.

Learning Path:
1. Implement latency-based router (pick nearest PoP by simulated RTT)
2. Implement an edge middleware pipeline (chain of handlers)
3. Implement edge-side A/B testing (deterministic bucket by user ID)
4. Implement a lightweight edge function runtime with CPU/memory limits
5. Think about: what constraints make edge functions different from regular serverless?
   - No filesystem, limited CPU time (<5ms startup), small bundle (<1MB)
   - No long-lived connections (each invocation is fresh)
   - Stateless — use KV store at the edge for persistence
"""

import time
import random
import hashlib
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Step 1: Latency-Based Router
# ---------------------------------------------------------------------------

class EdgeNode:
    """Represents a CDN/edge PoP with a geographic location."""
    def __init__(self, node_id: str, region: str, latency_ms: float):
        self.node_id = node_id
        self.region = region
        self.latency_ms = latency_ms  # simulated RTT from a reference client
        self.healthy = True


class LatencyRouter:
    """Routes requests to the edge node with the lowest latency.

    Real CDNs use anycast BGP routing or GeoDNS + latency measurements.
    This simulates the same decision logic.

    TODO:
    - route(client_region): return the EdgeNode with lowest latency_ms
      that is also healthy
    - add_node(node): register a new edge node
    - mark_unhealthy(node_id): remove from routing (health check failure)
    - mark_healthy(node_id): restore to routing pool
    """

    def __init__(self):
        self._nodes: Dict[str, EdgeNode] = {}

    def add_node(self, node: EdgeNode) -> None:
        """Register an edge node.

        TODO: store node in self._nodes keyed by node_id
        """
        # TODO: implement add_node
        raise NotImplementedError("Implement LatencyRouter.add_node")

    def route(self, client_latencies: Dict[str, float]) -> Optional[EdgeNode]:
        """Return the healthy EdgeNode with the lowest latency for this client.

        Args:
            client_latencies: mapping of node_id → measured RTT ms from client

        TODO:
        1. Filter to healthy nodes
        2. Find the node with minimum client_latencies[node_id]
        3. Return that EdgeNode (or None if no healthy nodes)
        """
        # TODO: implement route
        raise NotImplementedError("Implement LatencyRouter.route")

    def mark_unhealthy(self, node_id: str) -> None:
        """Mark a node as unhealthy (exclude from routing).

        TODO: set self._nodes[node_id].healthy = False
        """
        # TODO: implement mark_unhealthy
        raise NotImplementedError("Implement LatencyRouter.mark_unhealthy")

    def mark_healthy(self, node_id: str) -> None:
        """Restore a node to the healthy pool.

        TODO: set self._nodes[node_id].healthy = True
        """
        # TODO: implement mark_healthy
        raise NotImplementedError("Implement LatencyRouter.mark_healthy")


# ---------------------------------------------------------------------------
# Step 2: Edge Middleware Pipeline
# ---------------------------------------------------------------------------

class Request:
    """Simulated HTTP request object."""
    def __init__(self, method: str, path: str, headers: Optional[Dict[str, str]] = None,
                 body: Any = None):
        self.method = method
        self.path = path
        self.headers: Dict[str, str] = headers or {}
        self.body = body
        self.attributes: Dict[str, Any] = {}  # middleware can attach data here


class Response:
    """Simulated HTTP response object."""
    def __init__(self, status: int = 200, body: Any = None,
                 headers: Optional[Dict[str, str]] = None):
        self.status = status
        self.body = body
        self.headers: Dict[str, str] = headers or {}


MiddlewareFn = Callable[[Request, Callable], Response]


class EdgeMiddlewarePipeline:
    """Chain of edge middleware functions executed in order.

    Each middleware receives (request, next_handler) and can:
      - Modify the request (e.g., add geo-derived attributes)
      - Short-circuit and return a Response (e.g., 403 geo-block)
      - Call next_handler(request) to pass to the next middleware

    TODO:
    - use(middleware): register a middleware function
    - handle(request, final_handler): run the pipeline
      Build a chain from the middleware list and call the first one.
    """

    def __init__(self):
        self._middlewares: List[MiddlewareFn] = []

    def use(self, middleware: MiddlewareFn) -> None:
        """Register middleware to be executed in order.

        TODO: append middleware to self._middlewares
        """
        # TODO: implement use
        raise NotImplementedError("Implement EdgeMiddlewarePipeline.use")

    def handle(self, request: Request, final_handler: Callable[[Request], Response]) -> Response:
        """Execute the middleware pipeline and return a Response.

        TODO:
        Build a chain by wrapping each middleware:
          chain = final_handler
          for mw in reversed(middlewares):
              chain = lambda req, next=chain, m=mw: m(req, next)
          return chain(request)
        """
        # TODO: implement handle (build and execute middleware chain)
        raise NotImplementedError("Implement EdgeMiddlewarePipeline.handle")


# ---------------------------------------------------------------------------
# Step 3: Edge A/B Testing
# ---------------------------------------------------------------------------

class ABTestRouter:
    """Deterministic A/B test assignment at the edge.

    Assigns users to buckets based on a hash of their user ID so the same
    user always sees the same variant — no session state needed.

    TODO:
    - add_experiment(name, variants, weights): register an experiment
      variants: list of variant names; weights: list of float weights (must sum to 1.0)
    - get_variant(experiment_name, user_id): deterministically return a variant name
      Use: bucket = hash(experiment_name + user_id) % 100 → map to variant by weight
    """

    def __init__(self):
        self._experiments: Dict[str, Tuple[List[str], List[float]]] = {}

    def add_experiment(self, name: str, variants: List[str], weights: List[float]) -> None:
        """Register an A/B experiment.

        TODO:
        1. Validate len(variants) == len(weights) and sum(weights) ≈ 1.0
        2. Store in self._experiments[name] = (variants, weights)
        """
        # TODO: implement add_experiment
        raise NotImplementedError("Implement ABTestRouter.add_experiment")

    def get_variant(self, experiment_name: str, user_id: str) -> str:
        """Return the variant for this user in this experiment.

        TODO:
        1. Look up experiment variants and weights
        2. Compute bucket = int(hashlib.md5(f"{experiment_name}:{user_id}".encode()).hexdigest(), 16) % 100
        3. Walk through cumulative weight thresholds to pick variant
           e.g. weights=[0.5, 0.5] → variant A if bucket < 50 else variant B
        """
        # TODO: implement get_variant
        raise NotImplementedError("Implement ABTestRouter.get_variant")


# ---------------------------------------------------------------------------
# Step 4: Edge Function Runtime (stub with constraints)
# ---------------------------------------------------------------------------

class EdgeFunctionError(Exception):
    pass


class EdgeRuntime:
    """Minimal edge function runtime with CPU time and memory limits.

    Edge functions must be:
      - Fast: total wall time < cpu_limit_ms milliseconds
      - Stateless: no persistent state between invocations
      - Small: bundle size < memory_limit_kb KB (not enforced here, conceptual)

    TODO:
    - register(name, fn): register a named edge function
    - invoke(name, request): run the function with wall-clock enforcement
      If it takes longer than cpu_limit_ms → raise EdgeFunctionError("timeout")
    """

    def __init__(self, cpu_limit_ms: float = 50.0):
        self.cpu_limit_ms = cpu_limit_ms
        self._functions: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        """Register a named edge function.

        TODO: store fn in self._functions[name]
        """
        # TODO: implement register
        raise NotImplementedError("Implement EdgeRuntime.register")

    def invoke(self, name: str, request: Request) -> Response:
        """Invoke a registered edge function with a wall-clock time limit.

        TODO:
        1. Look up fn by name
        2. Run fn(request) in a thread with a timeout of cpu_limit_ms / 1000 seconds
        3. If it exceeds the limit: raise EdgeFunctionError(f"{name}: exceeded CPU limit")
        4. If fn raises: propagate the exception
        5. Return the Response
        """
        # TODO: implement invoke with timeout enforcement
        raise NotImplementedError("Implement EdgeRuntime.invoke")


# ---------------------------------------------------------------------------
# Step 5: Edge KV Store (discussion)
# ---------------------------------------------------------------------------

"""
Edge KV Store:

Edge functions are stateless between invocations, but they can read/write a
distributed KV store that is replicated globally with eventual consistency.

Examples: Cloudflare Workers KV, Fastly Config Store

Characteristics:
  - Strong consistency on writes within a region (local replica)
  - Eventually consistent globally (changes propagate in seconds to minutes)
  - Read-heavy: optimized for frequent reads, infrequent writes
  - Use cases: feature flags, user settings, rate limit counters (approx)

Pattern — Config at the Edge:
  1. Store feature flags in edge KV
  2. Edge function reads flag (sub-millisecond from local replica)
  3. Decide variant / enable-disable feature without hitting origin

Stateful Edge Patterns:
  - Durable Objects (Cloudflare): single-threaded actors at a chosen location
    → rate limiting, coordination, sessions with strict serializable consistency
  - Avoid: long-lived connections, large state, cross-region synchronous reads
"""


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _test():
    print("Testing LatencyRouter...")
    router = LatencyRouter()
    router.add_node(EdgeNode("us-east", "us-east", latency_ms=5.0))
    router.add_node(EdgeNode("eu-west", "eu-west", latency_ms=80.0))
    router.add_node(EdgeNode("ap-south", "ap-south", latency_ms=150.0))

    client_latencies = {"us-east": 5.0, "eu-west": 80.0, "ap-south": 150.0}
    best = router.route(client_latencies)
    assert best is not None and best.node_id == "us-east", \
        f"expected us-east, got {best}"

    router.mark_unhealthy("us-east")
    best2 = router.route(client_latencies)
    assert best2 is not None and best2.node_id == "eu-west", \
        f"expected eu-west after us-east is down, got {best2}"
    print("  LatencyRouter: OK")

    print("Testing EdgeMiddlewarePipeline...")
    pipeline = EdgeMiddlewarePipeline()

    def auth_middleware(req: Request, next_handler) -> Response:
        if req.headers.get("Authorization") != "Bearer valid-token":
            return Response(status=401, body="Unauthorized")
        return next_handler(req)

    def geo_middleware(req: Request, next_handler) -> Response:
        req.attributes["country"] = req.headers.get("CF-IPCountry", "US")
        return next_handler(req)

    pipeline.use(auth_middleware)
    pipeline.use(geo_middleware)

    def final(req: Request) -> Response:
        return Response(status=200, body=f"Hello from {req.attributes.get('country')}")

    # Unauthorized request
    resp = pipeline.handle(Request("GET", "/", headers={}), final)
    assert resp.status == 401, f"expected 401, got {resp.status}"

    # Authorized request
    resp = pipeline.handle(
        Request("GET", "/", headers={"Authorization": "Bearer valid-token",
                                      "CF-IPCountry": "DE"}),
        final
    )
    assert resp.status == 200, f"expected 200, got {resp.status}"
    assert resp.body == "Hello from DE", f"unexpected body: {resp.body}"
    print("  EdgeMiddlewarePipeline: OK")

    print("Testing ABTestRouter...")
    ab = ABTestRouter()
    ab.add_experiment("homepage_cta", ["control", "variant_a"], [0.5, 0.5])

    # Same user should always get the same variant
    v1 = ab.get_variant("homepage_cta", "user-123")
    v2 = ab.get_variant("homepage_cta", "user-123")
    assert v1 == v2, "same user should always get same variant"
    assert v1 in ("control", "variant_a"), f"unexpected variant: {v1}"

    # Distribution should be roughly 50/50 across many users
    variants = [ab.get_variant("homepage_cta", f"user-{i}") for i in range(1000)]
    control_count = variants.count("control")
    assert 400 <= control_count <= 600, \
        f"expected ~50% control, got {control_count}/1000"
    print("  ABTestRouter: OK")

    print("Testing EdgeRuntime...")
    runtime = EdgeRuntime(cpu_limit_ms=100.0)

    def fast_fn(req: Request) -> Response:
        return Response(status=200, body="fast")

    def slow_fn(req: Request) -> Response:
        time.sleep(0.5)
        return Response(status=200, body="slow")

    runtime.register("fast", fast_fn)
    runtime.register("slow", slow_fn)

    resp = runtime.invoke("fast", Request("GET", "/"))
    assert resp.status == 200 and resp.body == "fast"

    try:
        runtime.invoke("slow", Request("GET", "/"))
        assert False, "should raise EdgeFunctionError"
    except EdgeFunctionError:
        pass
    print("  EdgeRuntime: OK")

    print("\nAll edge computing tests passed!")


if __name__ == "__main__":
    _test()
