# Enterprise AI — twelve projects to build after the curriculum

Twelve implementation guides, kept on the branch
`claude/enterprise-ai-project-guides` under `enterprise-ai-projects/` — one file per
project, guides and not solutions: no code, no templates, no `check.py`. What they
have in common is that **the model is not the subject**: legacy data, tenant
isolation, privacy, air-gapped delivery, proving value, reliability, identity,
degradation, compliance, agent-to-ERP plumbing, safe rollout and recovery. Each guide
says what to build, which decisions it contains, which real system to build it
against, where it breaks, and what to read; writing the code is the exercise.

They are **projects to build after the courses**, not courses. A course in this
repository is a graded stage with a provided world, a template and a check, and the
audit refuses it unless all three exist; a project is a thing you build against
somebody else's system, and a mock you wrote yourself cannot surprise you — being
surprised by a system you did not write *is* the skill on display. Where one of them
overlaps something already sitting here, the row says so, so that nobody rebuilds it.

## The twelve

| # | Project | What it is | Already in this repo | The gap to build |
|---|---|---|---|---|
| 1 | Bi-directional legacy sync engine | Two systems of record — a SaaS and a customer's on-prem SQL database — that both accept writes to the same logical entities, kept in sync, with a defined answer for what happens when both change the same row before either has seen the other's change | `system-design/message_queue.py` (retries, backoff, dead letters) and `durable-execution-from-scratch` for what survives a crash | Conflict resolution as a rule rather than a hope: change capture, ordering, and the merge that must be *decided* before it is implemented |
| 2 | Zero-trust multi-tenant RAG | Retrieval serving many tenants from shared infrastructure, where isolation is enforced somewhere a forgotten `WHERE` clause cannot reach, and where isolation is *demonstrated* rather than asserted | `rag-from-scratch` (the retrieval half, single-tenant) and `sandbox-capabilities-from-scratch` (what a boundary is made of) | The boundary itself: row-level security, a tenant-scoped index, and an adversarial test that tries to cross |
| 3 | PII redaction & unmasking proxy | Middleware on the path to a model that finds PII in the request, substitutes placeholders, forwards it, and puts the real values back into the response | — | Redaction as a *lossy* mitigation (the model degrades exactly on what you masked) and the unmask map as a PII store in its own right |
| 4 | Air-gapped one-click deployer | A package and a procedure that install a whole stack — services, models, database, observability — into a Kubernetes cluster with no outbound internet, from a file on removable media, in under thirty minutes, by somebody who has never seen the system | `deploy-and-debug/` (rollout, canary, budget-based rollback, eleven injected faults) | The transfer of the *artifacts*: an offline bundle, a signature, and a first-boot check that fails loudly instead of half-installing |
| 5 | ROI & usage telemetry dashboard | Instrumentation plus a view that tells a customer what the product did for them last week, in hours and in money | `agent-metrics-from-scratch` (a trace is not a metric — the counting machinery) and `agent-harness-from-scratch` (the instrumentation points) | The definition of the metric itself: "hours saved" has to survive a hostile CFO, and no amount of dashboard rescues a number that was invented |
| 6 | Idempotent webhook reconciler | An event processor consuming webhooks from a system you do not control, ending in the correct state regardless of duplicates, out-of-order delivery, retries and gaps | `system-design/message_queue.py`, `system-design/idempotency_keys.py`, `aws-from-scratch/sqs.py` (visibility timeouts) and `aws-from-scratch/dynamodb.py` — the reliability core is done | The reconciler: a desired-state model, a repair pass for the gaps nobody sent, and a test that loses an event on purpose |
| 7 | Enterprise SSO & SCIM bridge | SAML or OIDC single sign-on against a customer's identity provider, plus a SCIM 2.0 endpoint that lets that provider create, update, deactivate and group users automatically | — | Both protocols at once, and the one thing they disagree about: what "deactivated" means for a session that is already open |
| 8 | AI fallback & degradation gateway | A proxy in front of model providers that keeps answering when the primary is slow, rate-limited or down — by falling back through progressively cheaper options, and by knowing when to stop rather than fall back forever | `system-design/circuit_breaker.py` — the breaker is done | Model-aware routing and the semantics of a degraded answer: what a caller is told when the answer it gets is the *cheap* one |
| 9 | Automated compliance auditor | Something that runs continuously against a deployment, checks it against a named set of controls, and produces a report a customer's security team accepts as evidence | `deploy-and-debug/diagnose.py` (injected faults as a fixture) | Evidence rather than opinion: real control IDs, a finding that names the exact object it is about, and a report that stays honest when a check cannot run |
| 10 | Custom MCP server for legacy ERPs | A Model Context Protocol server exposing a legacy ERP as tools an agent can call — reading data and performing updates — with the safety properties that make "an LLM can write to SAP" a sentence somebody will sign off on | `mcp-from-scratch` (the protocol, both ends) and `sandbox-capabilities-from-scratch` (the capability half of the safety story) | The ERP side: dialect, locking, transaction boundaries, and a write path that can be rolled back by a human |
| 11 | Shadow traffic evaluator | A fraction of live traffic duplicated to a candidate model, the candidate's responses recorded and compared against the incumbent's, with no effect on what users receive | `evals-from-scratch` and `eval-framework-from-scratch` (the comparison and the runner) | The mirroring and the *absence* of effect: the candidate's answer must never reach a user, and comparing two models on a live distribution needs a rule for what "better" means |
| 12 | 3 AM incident runbook repo | Procedures — rollback, scale, drain, failover, diagnose — that a junior engineer who did not build the system can execute correctly at 3 AM, and that are **tested**, so you know they still work | `deploy-and-debug/` has `RUNBOOK.md`, `rollout.py` and `diagnose.py` | Coverage, and the fact that an untested runbook is not a runbook: each procedure gets a fault that proves it still works |

The guides also name a real stand-in for each project — Oracle 23c Free or SQL Server
for 1 and 10, Debezium for 1, Postgres with `pgvector` or Qdrant for 2, Presidio for
3, k3s or kind with Helm and Zarf for 4, OpenTelemetry's GenAI conventions for 5, a
broker with real redelivery for 6, Keycloak for 7, the model APIs plus Ollama for 8,
`kube-bench`/Conftest/OPA/Prowler/Trivy for 9, Envoy's or Istio's mirroring for 11,
and a deployment of your own with faults injected for 12 — and they say where three
of the twelve claim more than they deliver (3, 5 and, in part, 12). Read the guide
before picking a project; that file keeps that table and this one does not.

## How they sit beside the curriculum

They are **not slots**: `codecraft/path.py` holds graded courses, `cz dag` and
`cz tracks` read them as a dependency graph, and none of the twelve has a provided
world, a template or a check to grade. They are the *other* half of the repository's
own thesis — the courses build the mechanism, these build the thing the mechanism is
for — and each one is the natural continuation of at least one course: 2 continues
`rag-from-scratch`, 6 continues `queue-and-workers-from-scratch`, 8 continues
`system-design`, 9 and 12 continue `deploy-and-debug`, 10 continues
`mcp-from-scratch` and `sandbox-capabilities-from-scratch`, and 11 continues
`evals-from-scratch`. If one of them is ever made a course — a provided world, ten
stages, a check per stage, a mutation proof — this file's row is where its contract
starts, and `codecraft/ROADMAP.md` is where the slot would be registered.

Until then: they are work to do **after** the curriculum, listed here so the queue is
written down where the rest of the queue is.
