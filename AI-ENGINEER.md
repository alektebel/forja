# AI Engineer — the interview list and the build list, and where this repository stands

Two lists arrived from the user, kept here **verbatim** because they are the
requirement and not a summary of it:

1. **The 25 problems** — what an AI engineer gets asked to reason about in a
   technical interview ("If I had to pass an AI engineer technical interview in
   the next 24 hours, I'd practice these 25 problems. They cover 95% of the
   concepts. Don't memorize answers. Practice explaining trade-offs out loud.").
2. **The 15 builds** — what is worth building, with the one-line reason each
   ("Prompt engineering is dead. Context overflow is the #1 silent killer…").

The repository's rule for a list like this — the same rule `AGENT-INFRA.md`
keeps for the twelve-item Agent Infra list — is: **the list stays as written, the
analysis around it is English, and a gap is stated as work or not stated at all.**
"Covered" below means *a stage builds the mechanism and a check catches the
mistake*, not that a course mentions it.

Phase **K** of `codecraft/ROADMAP.md`; `path.py` carries the five slots (K1–K5)
as `author`.

---

## 1. The list (verbatim): 25 interview problems

1. Design a RAG system for 10M documents
2. Your RAG gives wrong answers. Debug it
3. Pick a chunking strategy for legal contracts
4. BM25 vs dense vs hybrid search: when to use each
5. Add a reranker and measure if it helped
6. Reduce LLM cost by 70% without hurting quality
7. Cut first-token latency for a chat app
8. Design a semantic cache with hit-rate tracking
9. Route requests between a cheap and a smart model
10. Build an agent that uses tools reliably
11. Your agent gets stuck in a loop. Fix it
12. Design memory for a long-running assistant
13. Make LLM output always valid JSON
14. Detect and reduce hallucinations
15. Build an eval suite for a customer support bot
16. LLM-as-a-judge: how to make it trustworthy
17. Block prompt injection in a tool-using agent
18. Redact PII before it hits the model
19. Fine-tune vs RAG vs prompting: pick one and defend it
20. Fine-tune a small model with LoRA on 5K examples
21. Serve an open model at scale (batching, KV cache, quantization)
22. Stream responses over SSE and handle disconnects
23. Trace every step of a multi-agent workflow
24. Roll back a bad prompt change in production
25. Design ChatGPT-style chat for 1M daily users

## 2. The list (verbatim): 15 things to build

1. **Dynamic Context Assembler** — *Build:* middleware that strictly budgets
   tokens across working memory, tool schemas and retrieved docs per request.
   *Why:* prompt engineering is dead; context overflow is the #1 silent killer of
   production agents.
2. **Durable State Machine Workflow** — *Build:* Temporal or LangGraph DAG with
   checkpoints, exponential retries and human-in-the-loop Slack approvals. *Why:*
   endless chat loops break in production; real workflows take days and must
   survive server crashes.
3. **Raw MCP Server & Client** — *Build:* JSON-RPC server exposing your database
   and internal APIs with scoped credentials, without a wrapper SDK. *Why:*
   agents need standardized, secure hands; bespoke API wrappers do not scale.
4. **System-One Triage Router** — *Build:* proxy routing 95% of traffic to a
   fast, typed-decision model and escalating only 5% to a heavy reasoning model.
   *Why:* sending every query to a frontier API burns your runway.
5. **Self-Correcting Agentic RAG** — *Build:* retrieval agent that critiques its
   own search results, rewrites ambiguous queries and confidently abstains if
   grounding is weak. *Why:* naive chunk-and-retrieve RAG is a liability; agents
   must know when to search again.
6. **3-Tier Memory Engine** — *Build:* working scratchpad, episodic session
   summaries, and semantic vector DB with automated importance scoring and
   eviction. *Why:* agents without memory fail by turn five; agents with infinite
   memory hallucinate from context bloat.
7. **Trajectory CI Gate** — *Build:* GitHub Action grading the agent's tool-call
   sequence against a golden DAG, blocking PRs if it deviates. *Why:* final-answer
   evals hide the exact step where the agent went rogue; the trajectory is the
   unit of accountability.
8. **Inter-Agent Sanitization Proxy** — *Build:* middleware preventing
   cross-agent prompt injection and enforcing least-privilege tool scoping per
   agent. *Why:* multi-agent swarms create internal attack surfaces that
   standard unit tests miss.
9. **Real-Time Voice Interruption Loop** — *Build:* streaming SSE/WebSocket agent
   with voice activity detection and sub-1s interruption handling. *Why:* the
   interface is moving off the screen; perceived latency and interruption
   handling are the new UX standards.
10. **DPO Feedback Flywheel** — *Build:* pipeline capturing user thumbs-downs,
    formatting them into preference pairs and triggering nightly LoRA
    fine-tunes. *Why:* your production failures are the highest-leverage training
    data you own.
11. **Cost Kill-Switch & Degradation Chain** — *Build:* middleware halting agent
    loops instantly if projected spend exceeds $0.50, falling back
    Frontier → Mid → Local → Cache. *Why:* a runaway agent loop is an outage with
    an invoice.
12. **Shadow Routing Comparator** — *Build:* silent 5% traffic mirror to a new
    model or prompt, diffing trajectories and costs without affecting live users.
    *Why:* you cannot A/B test non-determinism safely without shadow mode.
13. **Computer-Use Fallback Agent** — *Build:* agent that tries the REST API
    first, then spawns a headless browser if the endpoint 404s. *Why:* the real
    world runs on legacy portals with no documentation.
14. **PII Unmasking Proxy** — *Build:* gateway swapping sensitive data for UUIDs
    before the context window and restoring it post-generation, with audit logs.
    *Why:* enterprises will not touch agents that leak customer data to frontier
    models.
15. **Public Architecture Teardown** — *Build:* 3 published deep-dives with
    system diagrams, cost/latency benchmarks and architecture decision records.
    *Why:* (the list's own answer: writing the design down is the interview.)

---

## 3. Where this repository already covers it — the 25 problems

"yes" means a graded stage builds it and a check catches the classic mistake;
"partly" names what is missing; "no" is a gap, and the gaps are collected in §5.

| # | Problem | Where it is today | Covered? |
|---|---|---|---|
| 1 | RAG for 10M documents | `rag-from-scratch` (B1: chunking, TF-IDF, exact index, BM25, rank fusion, reranking, citations, tenants) + `vector-index-from-scratch` (B2: k-means, IVF, the frontier, HNSW, deletions, int8) | yes |
| 2 | RAG gives wrong answers — debug | `rag-from-scratch` (reranking, citations), `contextcite` (attribution by ablation + LASSO), `evals-from-scratch` (nDCG, paired significance) | mostly — no abstention and no query rewriting, which is K1 |
| 3 | Chunking for legal contracts | `rag-from-scratch` stage 1 (the chunking strategy and what it costs retrieval) | partly — the mechanism is taught; contract structure (clauses, cross-references) is a domain exercise, not a stage |
| 4 | BM25 vs dense vs hybrid | `rag-from-scratch` (BM25, rank fusion) + `vector-index-from-scratch` (the dense half, and what recall costs) | yes |
| 5 | Add a reranker and measure it | `rag-from-scratch` (reranking) + `evals-from-scratch` (nDCG, kappa, paired significance) + `eval-framework-from-scratch` (records and a baseline diff) | yes |
| 6 | Cut LLM cost 70% | `context-caching` (prefix/radix reuse, paged KV, routing), `agent-harness-from-scratch` (a prompt budget recomputed from the bytes), `eval-framework-from-scratch` (budgets checked before the call) | partly — no cost ledger with a kill-switch and no degradation chain, which is K2 |
| 7 | First-token latency | `agent-harness-from-scratch` (streaming with TTFT and inter-token timings, retries that stop the moment anything was forwarded), `context-caching` (what a cache hit buys), `llm-from-scratch` (KV cache and sampling) | partly — the serving stack itself is the docs-only `vllm-engine`/`sgl-lang` trio |
| 8 | Semantic cache with hit-rate tracking | `context-caching` (prefix/radix/index caching, semantic routing, eviction) | partly — the cache is graded; a *hit-rate* ledger is J5, and the semantic-cache policy is K2 |
| 9 | Route cheap vs smart | `context-caching` (routing a request to the cache or the model) | partly — a typed-decision triage router with a measured escalation rate is K2 |
| 10 | Agent that uses tools reliably | `agents-from-scratch` (C2: the loop and its transcript, tool schemas and validation, errors as observations, parsing what a model actually writes) + `mcp-from-scratch` (D1: the envelope, the error split, resources, prompts, subscriptions) | yes |
| 11 | Agent stuck in a loop — fix it | `agents-from-scratch` (turn-aware memory, budgets), `agent-harness-from-scratch` (a spent budget is an outcome, not a crash), `queue-and-workers-from-scratch` (dead letters at the attempt budget) | yes |
| 12 | Memory for a long-running assistant | `agent-harness-from-scratch` (compaction that summarizes the middle, a prompt budget), `agents-from-scratch` (memory bounded by turns) | partly — episodic summaries with importance scoring and eviction are K3 |
| 13 | Always valid JSON | `agents-from-scratch` (parsing what a model actually writes), `mcp-from-scratch` (the protocol/execution error split), `eval-framework-from-scratch` (canonical records whose bytes two runs share) | yes |
| 14 | Detect and reduce hallucinations | `rag-from-scratch` (citations), `contextcite` (which context caused the answer), `evals-from-scratch` (judge bias and its calibration) | partly — an abstention decision that is grounded or not is K1 |
| 15 | Eval suite for a support bot | `evals-from-scratch` (splits, EM/F1, nDCG, the gate) + `eval-framework-from-scratch` (suites, budgets, records, gating, diff, resume) | yes |
| 16 | LLM-as-a-judge, trustworthy | `evals-from-scratch` (judge bias, kappa, paired significance, Holm) + `eval-framework-from-scratch` (a judge session cached by prompt/answer/reference that asks both orders) | yes |
| 17 | Block prompt injection in a tool agent | `agents-from-scratch` (an approval gate against injected content, a path sandbox), `mcp-from-scratch` (read-only first, idempotency keys, a confirmation that shows the diff, a trajectory policy) | partly — agent-to-agent injection and per-agent least privilege are K5 |
| 18 | Redact PII before the model | — | no — K5 |
| 19 | Fine-tune vs RAG vs prompting | `autograd-from-scratch` (A8) is the engine every answer assumes, and `evals-from-scratch` is how you would decide | partly — the decision itself (data volume, drift, latency, cost) is K4's first stage |
| 20 | LoRA on 5K examples | `autograd-from-scratch` (exact gradients, `shared`/`trainable` as a freeze) | no — K4 |
| 21 | Serve an open model at scale | `context-caching` (paged KV, copy-on-write), `llm-from-scratch` (KV cache, sampling), `interconnects-from-scratch` (what a collective costs) | partly — continuous batching/quantization needs the serving course this repo only documents (`vllm-engine`, `sgl-lang`, `tensorrt-inference`) |
| 22 | Stream over SSE, handle disconnects | `mcp-from-scratch` (stdio/SSE/HTTP framing with stdout purity, progress, cancellation), `agent-harness-from-scratch` (streaming, retries that stop before anything is forwarded) | yes |
| 23 | Trace a multi-agent workflow | `agent-harness-from-scratch` (a trace of six keys and no payloads), `orchestration-from-scratch` (J2: a record of seven kinds and a report recomputed from it), `mcp-from-scratch` (an audit line), `queue-and-workers-from-scratch` (a record rebuilt from the log) | yes — and J5 adds the metrics a trace cannot carry |
| 24 | Roll back a bad prompt change | `eval-framework-from-scratch` (the gate that refuses to pass what it cannot evaluate, a baseline diff that must beat the noise) | partly — a prompt is an artifact with versions, and rolling it back is K2 |
| 25 | ChatGPT-style chat for 1M users | `system-design` (capacity math, rate limiting, consistent hashing), `queue-and-workers-from-scratch` (admission, backpressure, ageing), `context-caching` (KV economy) | partly — the whole is a system-design exercise; nothing here is a server |

## 4. Where this repository already covers it — the 15 builds

| # | Build | Where it is today | Covered? |
|---|---|---|---|
| 1 | Dynamic Context Assembler | `agent-harness-from-scratch` (a prompt budget recomputed from the bytes, with dispatch and compaction inside it) and `orchestration-from-scratch` (J2 stage 4: a handoff cut to the budget each dependency declared) | yes |
| 2 | Durable State Machine Workflow | `orchestration-from-scratch` (J2: the graph, the reviewer, the gate that stops before the effect) and **J3 `durable-execution-from-scratch`** (being authored: leases, heartbeats, a journal, replay, resume, exactly-once effects) | yes — J2 shipped, J3 in flight |
| 3 | Raw MCP Server & Client | `mcp-from-scratch` (D1: JSON-RPC, framing, the handshake, tools with scoped effects) | yes |
| 4 | System-One Triage Router | `context-caching` (routing) | partly — K2 |
| 5 | Self-Correcting Agentic RAG | `rag-from-scratch` (retrieval, fusion, reranking), `agents-from-scratch` (a loop that can search again) | partly — the critique/rewrite/abstain decision is K1 |
| 6 | 3-Tier Memory Engine | `agent-harness-from-scratch` (compaction, a bounded prompt) | partly — K3 |
| 7 | Trajectory CI Gate | `eval-framework-from-scratch` (the gate and its exit codes), `agent-harness-from-scratch` (the turn as the unit), `mcp-from-scratch` (trajectory policy) | partly — a *golden trajectory* diffed step by step, blocking a change, is K2's shadow-mode half |
| 8 | Inter-Agent Sanitization Proxy | `orchestration-from-scratch` (J2: what a child is handed and nothing else) | partly — K5 |
| 9 | Real-Time Voice Interruption Loop | `mcp-from-scratch` (SSE framing), `agent-harness-from-scratch` (streaming) | no — see the no-slot note below |
| 10 | DPO Feedback Flywheel | `autograd-from-scratch` (A8: the gradients) | no — K4 |
| 11 | Cost Kill-Switch & Degradation Chain | `eval-framework-from-scratch` (budgets checked before the call, a stop that is data) | partly — the kill-switch, the projected spend and the fallback chain are K2 |
| 12 | Shadow Routing Comparator | — | no — K2 |
| 13 | Computer-Use Fallback Agent | — | no — see the no-slot note below |
| 14 | PII Unmasking Proxy | `agents-from-scratch` (a path sandbox), `mcp-from-scratch` (read-only first, an audit line) | partly — K5 |
| 15 | Public Architecture Teardown | this repository's own `ROADMAP.md`, `DISTRIBUTED.md`, `AI-ENGINEER.md` and every course's `DESIGN DECISION` docstrings | not a course — it is the writing, and the repo does it |

---

## 5. The gaps, stated as work

Registered as **phase K** of `codecraft/ROADMAP.md`, with the same shape as every
authored course here: a provided simulator, ten graded stages, DESIGN DECISION
docstrings, a check per stage and mutations behind every check. All of them are
deterministic and offline, like J1–J5: nothing is timed, no network, no threads.

| Slot | Course to author | Which items above it answers |
|---|---|---|
| K1 | `agentic-retrieval-from-scratch` | #1–#5, #14 and build 5 — retrieval that checks itself: critique the results, rewrite an ambiguous query, decide *grounded or abstain*, and price each of those decisions against the naive retrieve-and-answer. Contract-shaped chunking (clauses, cross-references) is a fixture here. |
| K2 | `prompt-ops-from-scratch` | #6, #8, #9, #24 and builds 4, 7, 11, 12 — a prompt and a model choice as versioned artifacts: a typed triage router with a measured escalation rate, shadow mode mirroring a fraction of traffic and diffing trajectories and costs, a rollout/rollback gate, the cost kill-switch and the degradation chain (frontier → mid → local → cache). |
| K3 | `memory-engine-from-scratch` | #12 and build 6 — the three tiers as data structures: a working scratchpad with a hard budget, episodic summaries with a consolidation rule, a semantic store with importance scoring and eviction, and recall measured against a long conversation. |
| K4 | `fine-tuning-from-scratch` | #19, #20 and build 10 — LoRA and preference tuning over `autograd-from-scratch`'s exact engine: the low-rank update and why it trains, a 5K-example budget that refuses a plan it cannot pay for, DPO preference pairs built from recorded failures, and the decision itself — fine-tune, RAG or prompting — defended against a number. |
| K5 | `agent-privacy-from-scratch` | #17, #18 and builds 8, 14 — a gateway that tokenizes sensitive values before the context window and restores them after, an audit line that answers "what did it touch", per-agent least privilege and scoped tool sets, and the sanitization of one agent's output before it becomes another agent's input. |

**No slot yet**, and each for a stated reason rather than by omission:

- **#21 and #25 (serving at scale, 1M-user chat)** are systems exercises, not
  from-scratch mechanisms: the repository documents the serving stack
  (`vllm-engine`, `sgl-lang`, `tensorrt-inference`) and teaches its parts
  (`context-caching`, `llm-from-scratch`, `interconnects-from-scratch`,
  `queue-and-workers-from-scratch`, `system-design`). A course would need a
  simulator of a real server, and the honest version of that is the benchmark
  work the repo already does (phase F).
- **#9 and #13 (voice interruption, computer-use fallback)** are *interface*
  courses: a voice loop needs a timeline and a VAD state machine (which this
  repository could do deterministically, as it did a fabric for I9), and
  computer-use needs a DOM/browser model. Both are real gaps; neither is
  registered yet, because phase K is already five courses deep and a slot that
  nobody is going to build this quarter is a promise, not a plan.
- **#15 (architecture teardown)** is not a build: it is the writing, and this
  repository does it in `ROADMAP.md`, `DISTRIBUTED.md` and every course's
  decision docstrings — the three deep-dives it asks for are the sections above.
