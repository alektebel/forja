"""Challenge marks for the catalog and path — one silhouette per course.

Keys map to `codecraft/web/logos/<key>.svg`. Original geometry (not trademark
artwork): evocative enough to read at a glance, loud enough for a CC-style card.
"""

# course slug → logo key
BY_COURSE = {
    "aws-from-scratch": "aws",
    "infrastructure-from-scratch": "infra",
    "llm-from-scratch": "llm",
    "evals-from-scratch": "evals",
    "agents-from-scratch": "agents",
    "autograd-from-scratch": "autograd",
    "context-caching": "kvcache",
    "contextcite": "cite",
    "dynamo-paper": "dynamo",
    "deploy-and-debug": "deploy",
    "rag-from-scratch": "rag",
    "vector-index-from-scratch": "hnsw",
    "mcp-from-scratch": "mcp",
    "agent-harness-from-scratch": "harness",
    "benchmark-from-scratch": "bench",
    "eval-framework-from-scratch": "framework",
    "compiler-and-vgpu": "vgpu",
    "cuda-from-scratch": "cuda",
    "cpu-from-scratch": "cpu",
    "os-from-scratch": "os",
    "c-compiler": "compiler",
    "shell-from-scratch": "shell",
    "runtime-from-scratch": "runtime",
    "distributed-training-from-scratch": "disttrain",
    "query-engine-from-scratch": "sql",
    "consensus-from-scratch": "consensus",
    "compression-from-scratch": "compress",
    "failover-from-scratch": "failover",
    "transformer-inference-physics": "physics",
    "interconnects-from-scratch": "fabric",
    "queue-and-workers-from-scratch": "queue",
    "orchestration-from-scratch": "orch",
    "durable-execution-from-scratch": "durable",
    "sandbox-capabilities-from-scratch": "sandbox",
    "agent-metrics-from-scratch": "metrics",
    "agentic-retrieval-from-scratch": "retrieval",
    "fde-from-scratch": "fde",
    "tcp-ip-from-scratch": "tcp",
    "websocket-from-scratch": "websocket",
    "concurrent-servers-from-scratch": "servers",
    "mqtt-broker-from-scratch": "mqtt",
    "git-from-scratch": "git",
    "credit-origination-from-scratch": "credit",
    "credit-lifecycle-from-scratch": "credit",
    "irb-capital-from-scratch": "capital",
    "collections-workout-from-scratch": "collections",
    "distressed-debt-from-scratch": "debt",
    "lbo-model-from-scratch": "lbo",
    "blockchain-from-scratch": "chain",
    "llm-security-from-scratch": "shield",
    "linux-device-driver-from-scratch": "driver",
}

DEFAULT = "forge"


def key_for(course):
    if not course:
        return DEFAULT
    return BY_COURSE.get(course, DEFAULT)


def url_for(course):
    return f"logos/{key_for(course)}.svg"
