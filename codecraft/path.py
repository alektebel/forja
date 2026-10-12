"""The path: what to build, in what order, and what is missing.

`codecraft path` renders this merged with your live progress. The order follows
the plan you set — AWS first, then LLM internals, then the AI-engineering half
(RAG, evals, agents, MCP, harness, benchmark, eval), then the systems half
(compiler/GPU/CPU and the rest).

Each item is one of:

  ready     an existing course with a check.py — run it now
  legacy    an existing project with templates and solutions but no checker;
            to use it in codecraft it needs a course.py (see scaffold.py)
  author    a course that does not exist yet; author it with `codecraft new`
  salvage   material exists on another git branch; port it first
  real      a project built on a real AWS account with Terraform (or designed
            for one); no offline checker can grade it, so it carries acceptance
            criteria you measure. Specs live in aws-architect-track/
  design    a system design exercise: design doc, ADRs, failure modes and a
            cost estimate, with an optional build slice on AWS

`prereq` is the honest dependency, not a suggestion. A course can be started
without its prereqs, but the stages assume them.
"""

PHASES = [
    ("A", "Cloud and LLM internals", [
        {"id": "A1", "title": "AWS From Scratch", "course": "aws-from-scratch",
         "kind": "ready", "prereq": [],
         "why": "Eight mechanism families in pure Python, 18 checks. The best "
                "first course: no dependencies, every stage is a real failure mode."},
        {"id": "A2", "title": "LLM From Scratch", "course": "llm-from-scratch",
         "kind": "ready", "prereq": [],
         "why": "BPE, attention, sampling, KV cache, RoPE. 13 checks, pure Python."},
        {"id": "A3", "title": "Context Caching From Scratch", "course": "context-caching",
         "kind": "ready", "prereq": ["A2"],
         "why": "The direct continuation of A2: page, prefix-share, evict the KV "
                "cache without changing the output. 16 checks."},
        {"id": "A4", "title": "ContextCite From Scratch", "course": "contextcite",
         "kind": "ready", "prereq": ["A2"],
         "why": "Which context caused the answer — ablation and a LASSO surrogate. "
                "The eval-flavoured course, and the bridge into RAG. 14 checks."},
        {"id": "A5", "title": "System Design", "course": "system-design",
         "kind": "legacy", "prereq": [],
         "why": "Optional but cheap: caching, queues, idempotency, rate limiting. "
                "Makes sqs/dynamodb in A1 click and underpins the agent half."},
        {"id": "A6", "title": "Dynamo From Scratch", "course": "dynamo-paper",
         "kind": "ready", "prereq": ["A1"],
         "why": "The paper behind DynamoDB, in depth: quorums, hinted handoff, "
                "Merkle anti-entropy. 17 checks."},
        {"id": "A7", "title": "Deploy & Debug", "course": "deploy-and-debug",
         "kind": "ready", "prereq": ["A1"],
         "why": "Capacity math, SLOs, root-causing faults from metrics. The "
                "operations thread that every later course leans on. 12 checks."},
    ]),
    ("B", "RAG", [
        {"id": "B1", "title": "RAG From Scratch", "course": "rag-from-scratch",
         "kind": "ready", "prereq": ["A2", "A4"],
         "why": "Built and ready: chunking, TF-IDF, a vector index, BM25, rank "
                "fusion, reranking, citations, tenant isolation, recall@k. 9 checks."},
        {"id": "B2", "title": "Vector Index From Scratch", "course": "vector-index-from-scratch",
         "kind": "ready", "prereq": ["B1"],
         "why": "Brute force -> IVF -> HNSW, with recall and work measured "
                "against the exact index you built in B1. 10 checks, pure "
                "Python, and the stage that makes 'approximate' mean "
                "something."},
    ]),
    ("C", "Evals and agents", [
        {"id": "C1", "title": "Evals From Scratch",
         "course": "evals-from-scratch", "kind": "ready", "prereq": ["A4"],
         "why": "Datasets, exact/F1 metrics, LLM-as-judge and its calibration, "
                "statistical significance, regression gating. Do this before agents."},
        {"id": "C2", "title": "Agents From Scratch",
         "course": "agents-from-scratch", "kind": "ready", "prereq": ["C1", "B1"],
         "why": "The loop and the transcript that is its state, tool schemas and "
                "validation, errors as observations, parsing what a model actually "
                "writes, retries with idempotent effects, memory bounded by turns, a "
                "filesystem sandbox, an approval gate against injected content, "
                "budgets that stop before the cap, and a state-based audit."},
    ]),
    ("D", "MCP", [
        {"id": "D1", "title": "MCP From Scratch",
         "course": "mcp-from-scratch", "kind": "ready", "prereq": ["C2"],
         "why": "Ten stages, all graded: the JSON-RPC envelope and the spec's error "
                "codes, stdio/SSE/HTTP framing with stdout purity, the lifecycle "
                "handshake and derived capabilities, tools with the protocol-"
                "versus-execution error split, resources and prompts with the "
                "pinned -32002, subscriptions/progress/cancellation, read-only "
                "first with an allowlisted report tool, idempotency keys, a "
                "confirmation that shows the diff, and the trajectory policy with "
                "an audit line that has no clock and no payload. Pinned to spec "
                "revision 2025-06-18."},
    ]),
    ("E", "Harness", [
        {"id": "E1", "title": "Agent Harness From Scratch",
         "course": "agent-harness-from-scratch", "kind": "ready",
         "prereq": ["C2", "D1"],
         "why": "Ten stages, all graded: collect a model's event stream into one "
                "turn, a prompt budget recomputed from the bytes, the loop whose "
                "exhaustion is an outcome, dispatch where an unknown tool is a "
                "message the model can read, streaming with TTFT and inter-token "
                "timings, retries that stop the moment anything was forwarded, "
                "compaction that summarizes the middle and pins the system "
                "message, a trace of six keys and no payloads, a process reward "
                "grounded in the previous result, and a verifier plus a "
                "self-generated data loop measured on held-out tasks. The model "
                "is a callable, the clock is injected, and `time.time` is under a "
                "landmine in the smoke run."},
    ]),
    ("F", "Benchmark and eval", [
        {"id": "F1", "title": "Benchmark From Scratch (Mus)",
         "course": "benchmark-from-scratch", "kind": "ready",
         "prereq": ["C1", "E1"],
         "why": "Ten stages, all graded: the turn gate where a refusal is data and "
                "not a turn, the match loop with as-dealt snapshots and the rails "
                "that stop a run that became about the harness, one ground-truth "
                "record per decision taken BEFORE the action, the link from an "
                "aggression to the answer it got, the strength reference drawn "
                "from the hands that could bet, a risk scorecard where a bluff is "
                "a weak hand and not a lost bet, the outcome that survives the "
                "40-point vaca reset, the calibration and discrimination probes "
                "with their degenerate cases, the gate that decides what may be "
                "published, and the mirrored pair that cancels the seat "
                "advantage. The game is provided (`mus.py`: a Fournier mus table "
                "with the four lances, three bet scales and two reference seats); "
                "the measurement is the exercise. Reference repo: "
                "~/Desarrollo/mus-benchmark."},
        {"id": "F2", "title": "Eval Framework From Scratch",
         "course": "eval-framework-from-scratch", "kind": "ready",
         "prereq": ["F1"],
         "why": "Ten stages, all graded, and the runner rather than the metrics "
                "(phase C1 owns what to measure): a suite config that refuses a "
                "typo instead of running differently from what its author "
                "believed, metric plugins resolved before the first call, one "
                "record per case with an error taxonomy that blames the right "
                "side, budgets checked BEFORE the call, an aggregation whose unit "
                "is the case, a judge asked through a cached and budgeted session "
                "in both orders, records whose bytes two runs share, a gate that "
                "refuses to pass what it cannot evaluate, a baseline diff that "
                "only cries regression when the difference beats the noise, and a "
                "resume that leaves behind the log of an uninterrupted run. The "
                "task set, the actors and the clock are provided (`lab.py`)."},
    ]),
    ("G", "GPU, CPU and the machine stack", [
        {"id": "G1", "title": "Compiler + Virtual GPU", "course": "compiler-and-vgpu",
         "kind": "ready", "prereq": [],
         "why": "One ISA, two machines: assembler, front end, register allocation "
                "with spilling, SIMT divergence. 12 checks. The right first systems "
                "course before real CUDA."},
        {"id": "G2", "title": "CUDA From Scratch", "course": "cuda-from-scratch",
         "kind": "legacy", "prereq": ["G1"],
         "why": "Kernels from vector add to a network. Needs a GPU and a checker "
                "wrapper to join codecraft."},
        {"id": "G3", "title": "CPU From Scratch", "course": None,
         "kind": "author", "prereq": ["G1"],
         "why": "A real datapath: decoder, register file, ALU, control unit, memory "
                "and pipelining, simulated and tested. Missing from the repo."},
        {"id": "G4", "title": "OS From Scratch", "course": None,
         "kind": "salvage", "prereq": ["G3"],
         "why": "A linux-from-scratch curriculum exists on a branch; port it, then "
                "give it a checker."},
        {"id": "G5", "title": "C Compiler", "course": "c-compiler",
         "kind": "legacy", "prereq": ["G1"],
         "why": "Lexer, parser, semantic analysis, codegen, optimizer. Templates and "
                "solutions exist; it needs a checker to join codecraft."},
        {"id": "G6", "title": "The C systems set", "course": None,
         "kind": "legacy", "prereq": [],
         "why": "bash-from-scratch, http-server, dns-server, firewall-from-scratch, "
                "toralizer, communication-protocols, cryptographic-library, "
                "quantum-computing-lang. One at a time; each needs a checker."},
    ]),
    ("H", "The rest", [
        {"id": "H1", "title": "Distributed Training", "course": "distributed-training",
         "kind": "legacy", "prereq": ["A2"], "why": "Data and model parallelism."},
        {"id": "H2", "title": "Inference and serving", "course": None,
         "kind": "salvage", "prereq": ["A3"],
         "why": "Superseded by phase I, which is this list as a fourteen-stage spine: "
                "vllm-engine, sgl-lang and tensorrt-inference are I3, I6 and I5 there. "
                "ml-inference lives here; three of the four are README-only on main, "
                "and an inference-from-scratch set exists on a branch."},
        {"id": "H3", "title": "Generative models", "course": None,
         "kind": "legacy", "prereq": ["C1"],
         "why": "diffusion-models, world-models (10k lines of PyTorch), deepfake "
                "creation and detection."},
        {"id": "H4", "title": "Long tail", "course": None, "kind": "legacy", "prereq": [],
         "why": "quantitative-trading, spectral-graphs, lean-proofs, haskell-projects, "
                "mlops, ml-in-production, sas-lineage-tool, web-scraping."},
    ]),
    ("I", "Inference engineering: from silicon to serving", [
        {"id": "I1", "title": "Systems & GPU Foundations", "course": "compiler-and-vgpu",
         "kind": "ready", "prereq": ["G1"],
         "why": "The silicon half: thread blocks, warps and SIMT divergence are G1's "
                "12 checks; then author gpu-architecture-from-scratch for the memory "
                "hierarchy (banks, coalescing, TLB, PCIe vs NVLink) and the matmul "
                "kernel, as a simulator plus a roofline, with the CUDA/cuBLAS profile "
                "as the runbook. C++ and Rust belong here too: one kernel each, "
                "compiled, so the toolchain is not a mystery."},
        {"id": "I2", "title": "Transformer Inference Physics", "course": None,
         "kind": "author", "prereq": ["A2", "I1"],
         "why": "Prefill vs decode as two different machines, arithmetic intensity, "
                "the KV-cache equation, and where tokens/second actually comes from. "
                "Author inference-physics-from-scratch: a cost model that predicts "
                "TTFT and ITL from config alone, checked against measured traces — "
                "the offline stand-in for Nsight Systems."},
        {"id": "I3", "title": "Modern Serving Engines & Batching", "course": None,
         "kind": "author", "prereq": ["I2", "A3"],
         "why": "vLLM, SGLang, PagedAttention, continuous batching, chunked prefill. "
                "vllm-engine/ and sgl-lang/ are README-only on main; A3 already builds "
                "paged KV with copy-on-write, so this course authors the scheduler: "
                "admission, prefill/decode mixing, chunk sizing, and the starvation "
                "curve a throughput number hides."},
        {"id": "I4", "title": "KV-Cache & Memory Optimization", "course": "context-caching",
         "kind": "ready", "prereq": ["A3"],
         "why": "Prefix and radix reuse, semantic routing and eviction are A3's 16 "
                "checks. The missing half (KV quantization, CPU offload, multi-turn "
                "reuse across sessions, a KV-affinity routing proxy) is what "
                "kv-cache-ops would add on top."},
        {"id": "I5", "title": "Quantization & Compression", "course": None,
         "kind": "salvage", "prereq": ["I2"],
         "why": "FP8, INT4, AWQ, GPTQ, sparsity and calibration. tensorrt-inference/ is "
                "README-only; author quantization-from-scratch: scales and zero points, "
                "per-channel vs per-tensor, KL calibration, and the quality/latency/VRAM "
                "trade-off measured on a tiny model instead of promised."},
        {"id": "I6", "title": "Kernel-Level Engineering", "course": None,
         "kind": "author", "prereq": ["G1", "I2"],
         "why": "Triton, FlashAttention, CUDA graphs, fusion. sgl-lang/ is README-only; "
                "author kernels-from-scratch: tiling and online softmax by hand in "
                "Python, then a small Triton-shaped IR with a fusion pass and a "
                "launch-overhead model. The fused RMSNorm/softmax benchmark becomes a "
                "check that the fused path is bit-identical and cheaper."},
        {"id": "I7", "title": "Distributed Inference & Parallelism", "course": None,
         "kind": "author", "prereq": ["I3", "I9"],
         "why": "Tensor, pipeline and expert parallelism: how a 405B model is cut, "
                "what each cut costs, and why the comms hide behind the compute or do "
                "not. Author distributed-inference-from-scratch: shard one model "
                "across N simulated ranks, schedule the pipeline, dispatch the experts, "
                "and measure the volume on a modelled interconnect."},
        {"id": "I8", "title": "Speculative Decoding", "course": None,
         "kind": "author", "prereq": ["I2"],
         "why": "Draft-target, Medusa heads, n-gram drafting, acceptance rates, and the "
                "KV bookkeeping that makes rejection cheap. Author "
                "speculative-decoding-from-scratch: pure Python, offline, with the "
                "acceptance-rate math and the '2x at zero quality cost' claim made "
                "checkable rather than repeated."},
        {"id": "I9", "title": "Multi-Node & Hardware Interconnects", "course": None,
         "kind": "author", "prereq": ["I1"],
         "why": "NCCL, RDMA, InfiniBand, NVLink, and disaggregated prefill/decode. "
                "Author interconnects-from-scratch: ring and tree all-reduce with a "
                "latency/bandwidth model, an RDMA-semantics simulator (one-sided, "
                "completion queues), and the topology that decides whether "
                "disaggregation pays. Same mechanism as AWS's networking, different "
                "wire."},
        {"id": "I10", "title": "Cluster Orchestration & GPU Scheduling", "course": None,
         "kind": "author", "prereq": ["A7", "I3"],
         "why": "Kubernetes GPU operators, Ray, Slurm, MIG partitioning, KEDA. "
                "deploy-and-debug/ already grades rollout and capacity math; author "
                "gpu-scheduling-from-scratch: a scheduler simulator with MIG slices, "
                "queue-based autoscaling, spot preemption, and the cost model that "
                "makes an idle H100 a bug."},
        {"id": "I11", "title": "AI Gateways, Routing & Observability", "course": None,
         "kind": "author", "prereq": ["A7", "I5"],
         "why": "TTFT/ITL SLOs, complexity routing, DCGM metrics, OpenTelemetry for "
                "LLMs. Author ai-gateway-from-scratch: a router that sends the cheap "
                "query to the quantized local model and the hard one upstream, with the "
                "SLO, the percentile pipeline and a throttling detector as graded "
                "checks. A3's routing and A7's percentiles are the two halves it "
                "joins."},
        {"id": "I12", "title": "Public Benchmarks & Teardowns", "course": None,
         "kind": "author", "prereq": ["F1", "I3"],
         "why": "Reproducible methodology, latency/throughput Pareto curves, "
                "cost-per-token. F1/F2 own the measurement machinery; "
                "inference-benchmark-from-scratch is the teardown: capture the full "
                "config, sweep the knobs, plot the frontier, pin cost per token to a "
                "price, and fail the run when a config is missing."},
        {"id": "I13", "title": "Inference Fault Tolerance & Recovery", "course": None,
         "kind": "author", "prereq": ["A7", "I4", "I10"],
         "why": "At scale hardware fails daily: network partitions, GPU ECC errors, "
                "OOMs mid-generation. A7 diagnoses injected faults; this stage "
                "recovers from them. Author inference-resilience-from-scratch: a "
                "fault injector over a simulated cluster, request retry that never "
                "duplicates a stream already forwarded, KV-cache migration or "
                "recompute when a replica dies, and checks that every request ends "
                "exactly once with the SLO cost of the recovery accounted."},
        {"id": "I14", "title": "Weight Loading & Cold Start", "course": None,
         "kind": "author", "prereq": ["I1", "I10"],
         "why": "Cold-start latency is what makes autoscaling slow. Author "
                "weight-loading-from-scratch: stream weights from object storage to "
                "device memory in chunks (ranged reads, pinned buffers, overlap of "
                "download, host copy and H2D), a cold-start model that predicts "
                "time-to-ready from size and bandwidths, and checks that the streamed "
                "weights are byte-identical and that the pipeline beats disk-first "
                "by the margin the model predicts. S3 and safetensors are the "
                "runbook."},
    ]),
    ("W", "AWS for real: Solutions Architect to ML engineer", [
        {"id": "W0", "title": "Account Foundations", "course": None,
         "kind": "real", "prereq": ["A1"],
         "why": "SAA-C03 \u2014 Design Secure Architectures. Spec, measured acceptance and "
                "questions in aws-architect-track/projects/w00-account-foundations/."},
        {"id": "W1", "title": "Static Site + CDN", "course": None,
         "kind": "real", "prereq": ["W0"],
         "why": "SAA-C03 \u2014 Secure / High-Performing. Spec, measured acceptance and "
                "questions in aws-architect-track/projects/w01-static-site-cdn/."},
        {"id": "W2", "title": "Network From Zero", "course": None,
         "kind": "real", "prereq": ["W0"],
         "why": "$$ hourly cost. SAA-C03 \u2014 Secure / Resilient. Spec, measured acceptance "
                "and questions in aws-architect-track/projects/w02-network-from-zero/."},
        {"id": "W3", "title": "Three-Tier HA App + Cache", "course": None,
         "kind": "real", "prereq": ["W2", "A5", "A7"],
         "why": "$$ hourly cost. SAA-C03 \u2014 Resilient / High-Performing. Spec, measured "
                "acceptance and questions in "
                "aws-architect-track/projects/w03-three-tier-ha/."},
        {"id": "W4", "title": "Serverless, Event-Driven", "course": None,
         "kind": "real", "prereq": ["W0"],
         "why": "SAA-C03 \u2014 Resilient / High-Performing. Spec, measured acceptance and "
                "questions in aws-architect-track/projects/w04-serverless-event-driven/."},
        {"id": "W5", "title": "Containers on ECS Fargate", "course": None,
         "kind": "real", "prereq": ["W2", "W3"],
         "why": "$$ hourly cost. SAA-C03 \u2014 High-Performing / Resilient; MLA-C01 \u2014 "
                "bring-your-own container. Spec, measured acceptance and questions in "
                "aws-architect-track/projects/w05-containers-ecs/."},
        {"id": "W6", "title": "Streaming with Kinesis", "course": None,
         "kind": "real", "prereq": ["W4"],
         "why": "SAA-C03 \u2014 High-Performing; MLA-C01 \u2014 Data ingestion. Spec, measured "
                "acceptance and questions in "
                "aws-architect-track/projects/w06-streaming-kinesis/."},
        {"id": "W7", "title": "Security & Encryption", "course": None,
         "kind": "real", "prereq": ["W0"],
         "why": "SAA-C03 \u2014 Design Secure Architectures. Spec, measured acceptance and "
                "questions in aws-architect-track/projects/w07-security-encryption/."},
        {"id": "W8", "title": "Multi-Account & Hybrid Network", "course": None,
         "kind": "real", "prereq": ["W2", "W7"],
         "why": "$$ hourly cost. SAA-C03 \u2014 Secure / Resilient (Organizations, SCPs, "
                "Transit Gateway, VPN). Spec, measured acceptance and questions in "
                "aws-architect-track/projects/w08-multi-account-hybrid/."},
        {"id": "W9", "title": "Observability, Backup & DR", "course": None,
         "kind": "real", "prereq": ["W3"],
         "why": "$$ hourly cost. SAA-C03 \u2014 Design Resilient Architectures. Spec, measured "
                "acceptance and questions in "
                "aws-architect-track/projects/w09-observability-dr/."},
        {"id": "W10", "title": "Cost & Well-Architected Review", "course": None,
         "kind": "real", "prereq": ["W3"],
         "why": "SAA-C03 \u2014 Design Cost-Optimized Architectures. Spec, measured acceptance "
                "and questions in "
                "aws-architect-track/projects/w10-cost-well-architected/."},
        {"id": "W11", "title": "Data Lake for ML", "course": None,
         "kind": "real", "prereq": ["W7", "W6"],
         "why": "MLA-C01 \u2014 Data Preparation for ML. Spec, measured acceptance and "
                "questions in aws-architect-track/projects/w11-data-lake-ml/."},
        {"id": "W12", "title": "SageMaker Training + Features", "course": None,
         "kind": "real", "prereq": ["W11"],
         "why": "MLA-C01 \u2014 ML Model Development. Spec, measured acceptance and questions "
                "in aws-architect-track/projects/w12-training-sagemaker/."},
        {"id": "W13", "title": "Model Deployment & Cost", "course": None,
         "kind": "real", "prereq": ["W12", "W5", "A7"],
         "why": "$$ hourly cost. MLA-C01 \u2014 Deployment and Orchestration. Spec, measured "
                "acceptance and questions in "
                "aws-architect-track/projects/w13-model-deployment/."},
        {"id": "W14", "title": "MLOps Pipeline", "course": None,
         "kind": "real", "prereq": ["W13"],
         "why": "MLA-C01 \u2014 Deployment and Orchestration (CI/CD). Spec, measured "
                "acceptance and questions in "
                "aws-architect-track/projects/w14-mlops-pipeline/."},
        {"id": "W15", "title": "Monitoring & Governance", "course": None,
         "kind": "real", "prereq": ["W13", "W7", "W2"],
         "why": "MLA-C01 \u2014 Monitoring, Maintenance and Security. Spec, measured "
                "acceptance and questions in "
                "aws-architect-track/projects/w15-monitoring-governance/."},
        {"id": "W16", "title": "Capstone: RAG on AWS", "course": None,
         "kind": "real", "prereq": ["B1", "C1", "W15"],
         "why": "$$ hourly cost. MLA-C01 + SAA-C03. Spec, measured acceptance and "
                "questions in aws-architect-track/projects/w16-capstone-rag/."},
    ]),
    ("S", "System design on AWS", [
        {"id": "S1", "title": "URL Shortener", "course": None,
         "kind": "design", "prereq": ["W4"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s01-url-shortener/."},
        {"id": "S2", "title": "Distributed Rate Limiter", "course": None,
         "kind": "design", "prereq": ["W3", "W4"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s02-rate-limiter/."},
        {"id": "S3", "title": "Notification System", "course": None,
         "kind": "design", "prereq": ["W4"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s03-notification-system/."},
        {"id": "S4", "title": "News Feed / Timeline", "course": None,
         "kind": "design", "prereq": ["W3"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s04-news-feed/."},
        {"id": "S5", "title": "Real-Time Chat", "course": None,
         "kind": "design", "prereq": ["W4"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s05-chat-messaging/."},
        {"id": "S6", "title": "Video Upload & Streaming", "course": None,
         "kind": "design", "prereq": ["W1", "W4"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s06-video-platform/."},
        {"id": "S7", "title": "Payments Ledger", "course": None,
         "kind": "design", "prereq": ["W3", "W7"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s07-payments-ledger/."},
        {"id": "S8", "title": "Distributed Job Scheduler", "course": None,
         "kind": "design", "prereq": ["W4"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s08-job-scheduler/."},
        {"id": "S9", "title": "Search Autocomplete", "course": None,
         "kind": "design", "prereq": ["W3"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s09-search-autocomplete/."},
        {"id": "S10", "title": "Ride-Hailing Geo Matching", "course": None,
         "kind": "design", "prereq": ["W6"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s10-geo-matching/."},
        {"id": "S11", "title": "Recommendation Serving", "course": None,
         "kind": "design", "prereq": ["W12", "W13"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s11-recommendation-serving/."},
        {"id": "S12", "title": "Multi-Tenant LLM Platform", "course": None,
         "kind": "design", "prereq": ["W13", "W16"],
         "why": "Design doc, ADRs, failure modes and a cost estimate; optional Terraform "
                "slice. aws-architect-track/system-design/s12-llm-platform/."},
    ]),
]

_SYMBOL = {"ready": "\u25cb", "legacy": "\u00b7", "author": "\u270e", "salvage": "\u21bb",
           "real": "\u2601", "design": "\u25c7"}


def _find(courses, name):
    for c in courses:
        if c["name"] == name:
            return c
    return None


def render_path(profile, courses, ink):
    green, yellow, grey, cyan = ("\033[32m", "\033[33m", "\033[90m", "\033[36m")
    lines = ["", ink("  codecraft \u00b7 the path", "\033[1m"),
             ink("  your order: AWS, LLM internals, RAG, evals + agents, MCP, "
                 "harness, benchmark, eval, the machine stack, the inference "
                 "spine, AWS for real, and system design on AWS", grey), ""]
    done = active = 0
    for code, title, items in PHASES:
        lines.append(ink(f"  PHASE {code} \u2014 {title}", cyan))
        for item in items:
            course = _find(courses, item["course"]) if item["course"] else None
            cstate = profile["courses"].get(item["course"], {}) if item["course"] else {}
            total = (cstate.get("total")
                     or (len(course["stages"]) if course else 0))
            passed = cstate.get("last_passed", 0)
            if item["kind"] == "ready" and course and total and passed == total:
                state, mark, note = "complete", ink("\u2713", green), ""
                done += 1
            elif item["kind"] == "ready" and course and cstate:
                state, mark = "doing", ink("\u25cf", yellow)
                note = (f"{passed}/{total}  next stage {cstate.get('next_step')} "
                        f"({course['stages'].get(cstate.get('next_step'), {}).get('file', '')})")
                active += 1
            elif item["kind"] == "ready":
                state, mark, note = "ready", ink("\u25cb", grey), "not started"
            elif item["kind"] == "author":
                mark, note = ink("\u270e", yellow), ink("to author", yellow)
            elif item["kind"] == "salvage":
                mark, note = ink("\u21bb", yellow), ink("port from a branch", yellow)
            elif item["kind"] == "design":
                mark, note = ink("\u25c7", cyan), ink("design doc + ADRs", cyan)
            elif item["kind"] == "real":
                mark, note = ink("\u2601", cyan), ink("real AWS \u00b7 Terraform", cyan)
            else:
                mark, note = ink("\u00b7", grey), ink("no checker yet", grey)
            prereq = ""
            if item["prereq"]:
                prereq = ink("  after " + ", ".join(item["prereq"]), grey)
            label = f"{item['id']}  {item['title']}"
            lines.append(f"  {mark} {label:<34} {note}{prereq}")
            lines.append(ink(f"       {item['why']}", grey))
        lines.append("")
    lines.append(ink(f"  {done} complete \u00b7 {active} in progress \u00b7 "
                     f"start: python3 codecraft/cli.py run {_first_ready(courses)}", grey))
    lines.append("")
    return "\n".join(lines)


def _first_ready(courses):
    for code, title, items in PHASES:
        for item in items:
            if item["kind"] == "ready" and _find(courses, item["course"]):
                return item["course"]
    return "<course>"
