# Agent Infra — a skill list worth keeping

This file preserves a list Diego wrote while starting out in **Agent Infra**
(the infrastructure an agent runs *on*, as opposed to the model or the prompt).
The list is kept verbatim, in the language it was written in; the analysis below
it is in English because every other document in this repository is, and because
the analysis is about *this* repository.

The point of keeping it here is that it is a syllabus. The twelve areas are the
parts of an agent system that decide whether it can be trusted to run for an
hour, and several of them are already courses in this repo — which is a useful
check on both: where a course exists, the list says what it should be teaching;
where none exists, the list says what to author next.

## The list (verbatim)

Si quieres trabajar en algo relacionado con IA, considera el emergente campo de
Agent Infra. Últimamente he estado iniciándome en este ámbito, he realizado
algunas investigaciones y he documentado una lista de habilidades necesarias en
este campo. Bienvenido a guardarla, conservarla; también seguiré compartiendo mis
experiencias de aprendizaje en este ámbito.

Lista completa:

1. **Agent Runtime:** Comprender Agent Loop, Tool Calling, Streaming, Session;
   comprender e implementar un Agent mínimamente viable, en lugar de solo llamar
   una vez a la API del modelo.
2. **Gestión de contexto y estado:** El contexto alimentado al gran modelo
   determina qué puede ver el modelo en esta ronda, y en gran medida decide la
   calidad de las decisiones del modelo; el State guardará hasta dónde ha
   avanzado la ejecución actual de la tarea. Se necesita manejar recorte de
   contexto, compresión, Checkpoint, estado de la tarea, memoria a largo plazo y
   contexto a corto plazo.
3. **Cola de tareas y Worker:** Distribuir tareas a través de Queue a Workers
   para su ejecución, y controlar concurrencia, prioridad, Backpressure y Worker
   Pool.
4. **Scheduling y orquestación multi-Agent:** Descomponer tareas complejas en
   múltiples subtareas, soportando DAG, Reviewer, Handoff y Human-in-the-loop.
5. **Ejecución duradera:** Incluso si el Agent se ejecuta durante decenas de
   minutos o incluso horas, no perderá la tarea debido a reinicios de procesos;
   se necesita persistir el estado de ejecución, Checkpoint, Replay, Resume y
   Recovery.
6. **Retry, Timeout e idempotencia:** El modelo, las herramientas, la red y los
   Workers encontrarán problemas; el sistema debe poder juzgar cuándo
   reintentar, cuándo ha expirado el tiempo, y evitar que operaciones como git
   push, envío de emails o creación de recursos se ejecuten de forma repetida.
7. **Estado distribuido y consistencia:** Múltiples Orchestrators, Workers y
   bases de datos mantienen conjuntamente el Task State; se necesita comprender
   Transaction, WAL, Lease, Heartbeat, Replication, Consistency y recuperación
   de fallos.
8. **Sandbox y entorno de ejecución:** Coding Agent ejecutará Shell, Git, Python,
   builds y pruebas; se necesita proporcionar a cada Agent un sistema de archivos
   aislado, procesos, red y entorno de recursos, y limitar CPU, memoria y tiempo
   de ejecución.
9. **Infraestructura de herramientas y MCP:** El Agent no solo llama a unas pocas
   Functions, sino que necesita gestionar unificadamente herramientas como Shell,
   Filesystem, Browser, Database, API, etc.; MCP puede servir como una interfaz
   estándar entre el Agent y herramientas externas o recursos.
10. **Permisos, seguridad y Secrets:** Controlar qué archivos puede acceder el
    Agent, qué herramientas puede llamar, a qué redes conectarse y qué claves
    leer, involucrando Authentication, Authorization, ACL, Secret Management y
    Audit.
11. **Observabilidad y depuración:** El proceso de ejecución completo de Agent
    Task se registrará mediante trace, usando Metrics para ver latencia, Queue,
    Token, costos, tasa de fallos y Retry.
12. **Evaluación y Replay:** No solo ver "si el Agent puede correr", sino juzgar
    si la tarea se completó realmente de forma correcta, mediante Dataset,
    Rubric, Task Success Rate, Regression, Replay y LLM-as-Judge para
    evaluaciones continuas.

## Where this repository already covers it

The mapping is by *mechanism taught*, not by name. A course counts when a stage
of it builds the thing and a check catches the mistake.

| # | Area | Where it is today | Covered? |
|---|---|---|---|
| 1 | Agent Runtime | `agents-from-scratch` (the loop and the transcript that is its state, tool schemas and validation, errors as observations, parsing what a model actually writes) and `agent-harness-from-scratch` (a model's event stream collected into one turn, streaming with TTFT and inter-token timings) | yes |
| 2 | Context and state | `agent-harness-from-scratch` (a prompt budget recomputed from the bytes, compaction that summarizes the middle and pins the system message), `agents-from-scratch` (memory bounded by turns), `eval-framework-from-scratch` (a checkpoint and a resume) | mostly — long-term memory is not a stage anywhere |
| 3 | Queue and workers | nothing | no |
| 4 | Multi-agent scheduling | nothing; `agents-from-scratch`'s approval gate is the shape of human-in-the-loop and nothing else | no |
| 5 | Durable execution | `eval-framework-from-scratch` (a hash that decides whether a resume is allowed, budgets carried over from the log, a half-written tail repaired, a resumed run whose bytes equal an uninterrupted one) | partly — one process, one log, no crash recovery of a *worker* |
| 6 | Retry, timeout, idempotency | `agents-from-scratch` (retries with idempotent effects), `agent-harness-from-scratch` (retries that stop the moment anything was forwarded) | yes |
| 7 | Distributed state and consistency | `dynamo-paper` (quorums, hinted handoff, Merkle anti-entropy) and `aws-from-scratch` (S3/SQS/DynamoDB semantics) — the theory and the APIs, not an orchestrator's own task state | partly |
| 8 | Sandbox and runtime environment | `agents-from-scratch` (a filesystem sandbox, a path jail); no process isolation, no network policy, no resource limits | partly |
| 9 | Tool infrastructure and MCP | `mcp-from-scratch` (the JSON-RPC envelope, stdio/SSE/HTTP framing, the lifecycle handshake, tools with the protocol/execution error split, resources and prompts, subscriptions and cancellation) and `agents-from-scratch` (tool schemas) | yes |
| 10 | Permissions, security, secrets | `agents-from-scratch` (an approval gate against injected content), `mcp-from-scratch` (read-only first, idempotency keys, a confirmation that shows the diff, an audit line) | partly — no secret management, no ACLs |
| 11 | Observability and debugging | `agent-harness-from-scratch` (a trace of six keys and no payloads), `benchmark-from-scratch` and `eval-framework-from-scratch` (records that are the analysis, budgets counted as calls and ticks) | partly — no queue/latency/cost metrics, because none of the courses have a server |
| 12 | Evaluation and replay | `evals-from-scratch` (splits, EM/F1, nDCG, judge bias, kappa, paired significance, Holm, the gate), `eval-framework-from-scratch` (the runner: suites, budgets, records, gating, diffing, resume), `benchmark-from-scratch` (a benchmark's own machinery) | yes |

## The gaps, stated as work

These are now registered as **phase J** of `codecraft/ROADMAP.md`, with the same
shape as every authored course here (a provided simulator, ten graded stages,
mutations behind every check). `python3 codecraft/cli.py path` shows them:

| Slot | Course to author | Which item above it answers |
|---|---|---|
| J1 | `queue-and-workers-from-scratch` | #3 — a queue with concurrency limits, priority, backpressure and a worker pool, deterministic and in-process: a scheduler that is a data structure and not a thread pool. The prerequisite for the two below. |
| J2 | `orchestration-from-scratch` | #4 — a DAG of subtasks, a reviewer that can reject, a handoff that must carry its own context, and a human-in-the-loop that stops *before* the effect rather than after it. |
| J3 | `durable-execution-from-scratch` | #5 — what `eval-framework-from-scratch` does for one run, generalized: leases and heartbeats, replay from a log, recovery after a killed worker, exactly-once effects. |
| J4 | `sandbox-capabilities-from-scratch` | #10 (and the rest of #8) — capability sets per tool, a path jail, a network policy, resource limits as counters, secrets that never reach the model, and an audit line complete enough to answer "what did it touch". |
| J5 | `agent-metrics-from-scratch` | #11 — token, cost, queue depth and latency metrics over a simulated fleet, with the windows that make percentiles stable. |

Items 3, 4, 7, 8, 10 and 11 are the parts of this list that the courses reach only
in part, and 3, 4, 8, 10 and 11 are what phase J is for; #1, #6, #9 and #12 are
already taught end to end, which is a good sign for both the list and the
repository. #7 (transaction, WAL, lease, heartbeat, replication) is the one item
with no slot yet: `dynamo-paper` and `aws-from-scratch` teach the theory and the
API, and J3 is where an orchestrator's own task state starts to need them.
