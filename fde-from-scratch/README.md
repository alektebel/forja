# FDE From Scratch

Build an enterprise AI deployment whose every claim is a record a check can read
back. Three modules are provided complete: `estate.py` is the customer — the
directory with its roles, groups and clearances; twenty-five rows across two
tenants in four classifications; the eight documents that arrive from their
invoicing system dirty in exactly the ways thirty-year-old data is dirty; and the
audit log every act is written to, whose `stats()` recomputes every number it
reports from that log. `network.py` is the basement: five images in a bundle and
six nodes, one of which is missing from the bundle, none of whose zones reaches
`"public"`, and the two GPUs somebody else owns. `meter.py` is what the AI cost and
saved, in ticks, tokens, cents and minutes.

The thesis of the whole course is one sentence: **an FDE builds the smallest thing
that survives the customer's own reality — a boundary enforced by the system rather
than remembered by the author, and an artifact checked against the customer's own
record rather than against a belief.** Each stage exists because the one before it
left a hole: nothing can be built until "who is asking" and "which rows may they
see" are answerable, so stage 1 is identity, sessions and the row; an environment
decides what is even installable, so stage 2 refuses a manifest that would reach
out; the model is fed the customer's data, so stage 3 reconciles what their invoice
system said against what their ledger holds before anything reads it; a retriever
that ignores the caller leaks precisely what the contract forbids, so stage 4
filters *before* the limit; an agent is useless until it can touch the system of
record, so stage 5 gives it tools and leaves the secret in the vault; one raw PII
token on the wire ends the deal, so stage 6 masks, forwards, restores and proves
nothing leaked; legal accountability sits with a person, so stage 7 stops the
machine at a gate and journals the decision; some data is too hot to move, so stage
8 puts the model that fits on the GPU that is there; renewal is an ROI conversation,
so stage 9 counts what the AI did in hours and cents and names the tokens nobody
can attribute; a generic benchmark convinces nobody, so stage 10 runs the customer's
own tickets in shadow and answers one word; the translation between revenue and
engineering is the job, so stage 11 turns a meeting transcript into a four-week
scope; and leverage is measured by how little the customer needs you, so stage 12
hands over a runbook that was drilled against armed faults and an admin whose
changes are not yours.

What is *not* here is the platform. There is no Okta, no SAP, no Kubernetes, no
GPU, no model server and no customer. Every one of them is a data structure in a
provided module: the directory is a dict of groups and roles, the legacy system is
a table of rows, the estate is a call, the GPU is a `gpu_memory_mb` field, the
model is a `tokens_per_tick` number and the customer is a name. That is the point
of the course and not a shortage in it: the part of forward deployment that can be
built and checked offline is the part that decides — who may see what, what is
allowed to leave, when the machine must stop, what fits, what it cost, what the
customer's own record says — and a course that simulated a real cluster would teach
the cluster's API instead of that.

The world is refused the things that would make the answer unfalsifiable. There is
no wall clock: `time`, `threading` and `asyncio` are banned, a deadline is a tick
the caller supplies, and a workflow's escalation is `tick >= due_at` rather than a
duration. There is no randomness: nothing is retried by itself, so two runs of one
fixture are one run and every check asserts it. There is no network, no subprocess
and no filesystem: the audit log, the meter's spans and the network's node states
are lists that a call appends to, and `stats()` recounts every number from them.
And there are no floats anywhere — a price is cents, a ratio is basis points, and
the arithmetic is written out by hand on purpose.

Every one of the failures below is a check here, and every one of them leaves the
stage's own output unchanged and is only visible through the world's log:

- a tenancy compared with `startswith`, so `northwind` reads `northwindevil`'s rows;
- a session that outlives its expiry, or an audience that is not the one it was
  minted for, so a token for one application opens another;
- a row's clearance checked after the row was returned, so the refusal arrives with
  the data attached;
- a manifest that pulls an image the bundle does not hold, or one whose digest the
  registry does not pin, so the installer reaches the internet it does not have;
- a deployment validated against the customer's *own* namespace prefix rather than
  their namespace, so `northwind-app` is accepted for a manifest named
  `northwindevil`;
- a decimal comma folded into a hundreds separator, so `1234,56 EUR` is read as
  `123456` and reconciles against a row that agrees for the wrong reason;
- a document whose PO field carries `l` read as `1`, so a digit that is a letter is
  silently matched;
- an amount parsed from `1.234 EUR` where the separator is ambiguous, so the guess is
  made by the parser instead of refused;
- a currency the estate does not have accepted as if it did, so `SEK` reconciles
  against a ledger that never held it;
- a bloom filter answering "maybe present" for a record that was never loaded,
  because the count and the bits disagree;
- a retriever that filters *after* the limit, so a small `limit` returns too few rows
  and a large one returns the rows the caller may not see;
- a refusal that quotes the row it refuses — its text, or its id in `citations`;
- a `score` counted with duplicate query tokens, so a word repeated in the query
  ranks a row above one that is more relevant;
- an abstention returned as a bare `False` where the contract wants a reason, and
  `all-refused` reported where `below-threshold` is the truth;
- the secret in the audit line, or passed as a tool argument, so the vault leaks by
  the one path it exists to close;
- a redeemed lease redeemed again, and an expired lease accepted because the
  comparison is `<=` where the contract says `<`;
- a rate limit checked after the work, or never refunded when the call is refused, so
  a refused call still spends the budget it did not use;
- the per-tick counter keyed by the caller instead of by the tool, so two tools share
  one budget and nobody can see why the second refuses;
- a viewer calling a write tool, or `authorized` reading the tool's verb instead of
  the principal's rights;
- a Luhn check that accepts a number whose checksum does not hold, so a card that is
  not a card is treated as one;
- a placeholder restored from a mapping another kind's counter overwrote, so two
  identical tokens restore to two different values;
- `scan` returning no leaks because it compared the masked text against itself;
- a forward that sends the original text when the model call fails, which is the one
  fallback a guardrail may never have;
- an approval from somebody who is not the gate's approver, or a rejection that
  still runs what follows, so the human's decision is decoration;
- an escalation that fires at the wrong side of `due_at`, so a ticket is escalated a
  tick early or never;
- a `resume` that replays a half-written line, so the replayed run does two of
  something the original did once;
- headroom applied to the node's RAM instead of its GPU memory, or `<=` where the
  90% boundary is inclusive on the other side, so a variant that does not fit is
  placed and one that does is refused;
- quality compared as a string, so `"9"` outranks `"10"`;
- a submission counted into the queue before the budget check, so a refused
  submission occupies a slot nobody can use;
- a drain that serves more tokens than the model does in one tick, or serves at all
  in a zone that reaches `"public"`;
- a resolution counted per span instead of per ticket and day, so a ticket touched
  twice counts as two and the ROI is inflated;
- minutes saved for a team the table does not hold, invented as a default rather than
  read as zero;
- an accuracy measured over the labelled set instead of over what the model
  answered, so a model that answered nothing scores zero rather than nothing;
- a candidate that reaches the user because shadowing was implemented as an early
  return;
- a verdict that ships a candidate whose judge the customer's own sample could not
  confirm, or that measures the target before it checks the sample;
- a metric without a baseline accepted, so the ROI argument has no starting point;
- a priority taken from the speaker's role instead of the statement's own words, so
  an executive's "maybe" is a must-have;
- a proper noun counted as a requirement, or a scope-out statement turned into one;
- a runbook passed as tested because its drill rows were counted rather than read, so
  a procedure no fault ever exercised reads as covered;
- an admin change applied without the right, or a change to the customer's system
  that skips the log.

Nothing here runs on a thread, a wall clock, a socket or a `random`. Where a decision
was a judgement call it is written down in the template's own docstring as a DESIGN
DECISION, and the check asserts the consequence.

## The provided world

| Module | What it is |
|---|---|
| `estate.py` | The customer and its directory: `Estate.build(seed)` with `rows`, `row`, `documents`, `document`, `query`, `audit`, `log`, `stats`; `IdP.build(seed)` with `users`, `groups`, `user`, `group`, `roles_of`, `deactivate`, `reactivate`, `assertion`, `verify`, `scim`, `log`, `events`, `stats`; `digest`, `sign`; `ESTATE_NAME`, `OTHER_TENANT`, `TICKS_PER_DAY`, `ISSUER`, `CLASSIFICATIONS`, `SCIM_OPS`, `PRINCIPAL_KEYS`, `ROW_KEYS`, `USER_KEYS`, `GROUP_KEYS`, `CLAIM_KEYS`, `SCIM_OP_KEYS`, `DOCUMENT_KEYS`, `AUDIT_KEYS`, `ESTATE_ERROR`, `EstateError` |
| `network.py` | The basement and its bundle: `Network.build(seed)` with `rules`, `reaches`, `attempt`, `images`, `image`, `pullable`, `pull`, `install`, `nodes`, `node`, `usable`, `models`, `model`, `log`, `stats`; `ZONES`, `DESTINATIONS`, `QUANTS`, `IMAGE_KEYS`, `NODE_KEYS`, `MODEL_KEYS`, `NETWORK_ERROR`, `NetworkError` |
| `meter.py` | What it cost and what it saved: `Meter()` with `span`, `spans`, `log`, `reset`, `stats`; `SPAN_KEYS`, `PRICES`, `MINUTES_SAVED`, `METER_ERROR`, `MeterError` |

The world carries facts and refuses acts, and **the course never writes it**. A row
comes out of `Estate.query(principal, table, ...)` only if that principal may see it,
and every call appends its own line to the estate's audit log — which is why a
refused call can be proven to have left no trace (`stats()` and the log, counted
before and after). `network.py` is the one that knows what the bundle holds and what
a zone reaches, so a manifest that would pull from the internet is *its* refusal and
not the course's opinion. `meter.py` holds the prices and the minutes a resolution
saves per team, so stage 9 counts money the way the customer's own table counts it,
and a team the table does not hold saves zero rather than a default somebody
invented. Every one of the three recomputes its `stats()` from its own log, and that
recount is the tie-breaker every stage's check is held against: a number a stage
believes agrees with itself by construction, which is exactly the comparison worth
nothing.

## The stages

| # | File | The stage | The mechanism |
|---|---|---|---|
| 1 | `stage_01.py` | The assertion, the session and the row | `PRINCIPAL_KEYS`, `SESSION_KEYS`, `RIGHTS`, `ROLE_RIGHTS`, `ROLE_CLEARANCE`, `REFUSALS`, `AuthError`, `principal`, `open_session`, `session_valid`, `rights`, `row_visible`, `refuse_reason`, `visible_rows`, `Sessions` (`held`, `open`, `expired`, `by_group`, `close`), `apply_scim` |
| 2 | `stage_02.py` | A deployment that cannot reach out | `MANIFEST_KEYS`, `STEPS`, `DEPLOY_KEYS`, `PROBLEMS`, `DeployError`, `validate`, `plan`, `deploy`, `rollback`, `verify` |
| 3 | `stage_03.py` | The invoice, the reconciliation and the hybrid store | `RECORD_KEYS`, `PARSE_PROBLEMS`, `CURRENCIES`, `VERDICTS`, `MISMATCHES`, `STORE_KEYS`, `EtlError`, `parse`, `tokens`, `reconcile`, `hybrid_load`, `report` |
| 4 | `stage_04.py` | Retrieval that cannot leak a row | `HIT_KEYS`, `SCORE_UNIT`, `ABSTENTIONS`, `MIN_SCORE`, `ANSWER_KEYS`, `RagError`, `search`, `filtered`, `answer`, `audit_answer` |
| 5 | `stage_05.py` | The legacy system as tools, and the credentials that stay behind | `TOOL_KEYS`, `VERBS`, `TOOLS`, `LEASE_KEYS`, `REASONS`, `MCPError`, `Vault` (`lease`, `redeem`, `secret_of`), `describe`, `authorized`, `tick_calls`, `call` |
| 6 | `stage_06.py` | Mask, forward, restore, and prove nothing leaked | `KINDS`, `DETECTION_KEYS`, `PLACEHOLDER`, `GUARD_KEYS`, `GuardError`, `digits`, `luhn`, `detect`, `Masker` (`mask`, `restore`, `mapping`, `seen`), `scan`, `forward` |
| 7 | `stage_07.py` | The workflow that waits for a human | `STEP_KEYS`, `STATE_KEYS`, `STATES`, `ACTORS`, `JOURNAL_KEYS`, `KINDS_OF_LINE`, `WorkflowError`, `Workflow` (`start`, `advance`, `approve`, `reject`, `state`, `pending`, `journal`), `resume`, `effects_of` |
| 8 | `stage_08.py` | The model that fits the customer's GPU | `FIT_REASONS`, `SERVE_REASONS`, `HEADROOM`, `QUEUE_MAX`, `BUDGET_TICKS`, `SUBMISSION_KEYS`, `EdgeError`, `fits`, `place`, `Scheduler` (`submit`, `drain`, `queue`, `served`, `refused`) |
| 9 | `stage_09.py` | What the AI did for this team, in hours and cents | `ROLLUP_KEYS`, `DASHBOARD_KEYS`, `ANOMALY_KEYS`, `RATE_CENTS_PER_MINUTE`, `ROI_BASIS`, `MetricError`, `rollup`, `team_day`, `dashboard`, `anomalies`, `unattributed` |
| 10 | `stage_10.py` | Shadow traffic and a verdict | `CASE_KEYS`, `SHADOW_KEYS`, `GRADE_KEYS`, `AGREEMENT_KEYS`, `VERDICTS`, `VERDICT_REASONS`, `MIN_SAMPLE`, `MIN_AGREEMENT_BP`, `EvalError`, `shadow`, `grade`, `calibrate`, `verdict`, `user_visible` |
| 11 | `stage_11.py` | From a vague ask to a scoped four weeks | `STATEMENT_KEYS`, `KINDS`, `REQUIREMENT_KEYS`, `PRIORITIES`, `UNITS`, `METRIC_KEYS`, `PLAN_KEYS`, `WEEK_CAPACITY`, `MIN_WORDS`, `SCOPE_PROBLEMS`, `ScopeError`, `requirements`, `workstreams`, `schedule`, `metrics`, `scope`, `sow` |
| 12 | `stage_12.py` | A runbook that is tested, and an admin who is not you | `PROCEDURE_KEYS`, `STEP_KEYS`, `ACTORS`, `OUTCOMES`, `DRILL_KEYS`, `FAULT_KEYS`, `ADMIN_KEYS`, `RUN_KEYS`, `RUNBOOK_PROBLEMS`, `GAP_REASONS`, `RunbookError`, `Runbook` (`add`, `procedures`, `problems`, `run`, `drill`, `self_serve`), `Admin` (`change`, `dry_run`, `log`), `gaps` |

The stages are cumulative in the only direction that matters: a stage imports the
world and the earlier stages it needs, and nothing from a later one. Stage 1 owns
the question every other stage asks first — who is this, and which rows are theirs —
and stage 4 is its own caller: the retriever applies stage 1's `refuse_reason` to the
pair stage 3 reconciled, before the limit rather than after it. Stage 2 owns what may
be installed at all; stage 3 owns what the customer's own record says, and every
later stage reads the store it built; stage 5 owns the credential that never leaves
the vault; stage 6 owns the mapping that goes out and comes back; stage 7 owns the
gate a person stands at; stage 8 owns what fits on the machine that is there; stage 9
owns the count that survives a renewal conversation; stage 10 owns the verdict; stage
11 owns the scope; and stage 12 owns the handoff, because a deployment is finished
exactly when the customer can run it without you.

## How to use this directory

```bash
python3 codecraft/cli.py run fde-from-scratch      # what to build next, and why
python3 codecraft/cli.py stage fde-from-scratch 4  # one stage: the file, what you write, what the tester costs
```

Or without codecraft: the templates are ordinary modules, and an unimplemented one
raises `NotImplementedError`. Implement them at the top level; finished versions
are in `solutions/`, and nothing beyond `solutions/` ships a solution or a hint in
this directory. The templates fail and the solutions pass, and that is the whole
grading loop — this course is checker-driven and there is no test framework
anywhere. The twelve checks are assembled into `course.py`, and every one of them is
a module-level `def check():` of bare `assert <condition>, "<message>"` statements,
where the message names the mistake rather than the symptom; an untouched template
reports as not implemented yet rather than failing for the wrong reason, because
the check lets `NotImplementedError` escape before any broad `except` catches it.
Every check builds its own estate, directory, network and meter and never mutates a
module-level object, and the last section of every check runs its own work twice and
compares the two runs, because determinism here is asserted rather than assumed.

Every check is mutation-tested: **884 plausible wrong implementations** across the
twelve stages, between 54 and 87 per stage, each a minimal edit to that stage's
solution, and the stage's check must fail — `TOTAL 884/884, MISSED OR BROKEN: 0`. A
mutant that hangs its check counts as caught, because a wrong implementation that
never terminates anything is not a passing implementation. The 1,377 ways those
checks can reject your file are counted per stage in `codecraft/stats.py`. The audit
reads each template and its solution and refuses them unless the first docstring
paragraph is exactly `FDE From Scratch — stage N: <title>.`, the template carries
3–6 `DESIGN DECISION — ` blocks and a `TODO: implement` line, the solution declares
every public name the template declares, the template imports nothing from a later
stage, and neither contains a float literal or imports a banned module (a clock, a
thread, an `asyncio`, a `random`, an `os`, a socket, a `subprocess`).

Where the course turned out better than the plan it was written against, the
difference is recorded rather than silently changed: `../.fde-dev/CONTRACT.md` §7
carries one row per amendment, with what the plan said, what the course does and
why — ten of them, from the shape of an approval (`approve` runs what the gate
released) to the number a stage writes in its own docstring (`stage 9:`, unpadded,
as every other course in this repository spells it).

## Prerequisites

Standard library only, and in practice almost nothing at all: no stage imports a
module that is not `estate`, `network`, `meter` or an earlier stage. No numpy, no
network, no threads, no sockets, no `datetime` — a deadline here is a tick the
caller hands in, and an escalation is a comparison between two of them. `time`,
`threading` and `asyncio` are banned because the tick is this course's unit and a
wall clock would make every number a machine's opinion; `random` because nothing
here retries by itself and two runs of one fixture are one run; and `os`, `socket`,
`subprocess`, `secrets`, `shutil`, `tempfile`, `pathlib`, `uuid`, `math`,
`statistics`, `decimal` and `fractions` are imports no stage may make either. There
are no floats anywhere — not in a template, not in a solution, not in a check — so
every count, size, price, tick and ratio is an `int`: a price is cents, a ratio is
basis points, and the arithmetic is written out by hand on purpose.

You should be comfortable with dicts as records, with tuples as answers, with
`try`/`except`, with a state machine whose transitions are data and with the rule the
whole course is built on: **a shape mismatch raises, a verdict is returned**. Nothing
here assumes you have sat in a customer meeting, read an invoice feed or sized a GPU;
stage 3 builds the reconciliation, stage 8 builds the placement and stage 11 builds
the scope, and each one is a data problem before it is anything else.

## Design decisions

- **The world is provided, complete, and never written by the course.** `estate.py`,
  `network.py` and `meter.py` carry the facts (who may see which row, what the bundle
  holds, what a zone reaches, what a token costs) and refuse the acts that would be
  wrong; every stage answers *through* them. A stage that re-implements one of their
  rules has created a second place for the rule to live, which is the defect this
  course is built to make visible — stage 4 applies stage 1's `refuse_reason` rather
  than a copy of the clearance table, and stage 9 counts minutes at `meter.py`'s own
  `MINUTES_SAVED` rather than at a table of its own.
- **The clock is always the caller's.** `open_session(..., tick)`,
  `Workflow.start(ticket, tick)`, `submit(name, tokens, tick)`, `drain(tick)`,
  `forward(..., tick)` — every temporal fact is a tick somebody passed in, so "the
  lease expired" and "the ticket escalated" are comparisons rather than waits. Nothing
  in the course can sleep, hang or be slow; a wrong implementation that never
  terminates is a wrong implementation, and the mutation sweep counts it as caught.
- **A shape mismatch raises; a verdict about the customer's world is returned.**
  Anything that cannot be the thing at all — a row that is not a `ROW_KEYS` record, a
  tick that is not a whole number, a manifest with no namespace — raises, naming the
  offender and, where there are two, both numbers. Anything that is a decision — a row
  that is not visible, a tool that is rate-limited, a model that does not fit, a
  submission that would wait too long, a requirement with no owner — comes back as
  data, because the whole job is deciding and a denial that arrives as an exception
  cannot be written into a ledger the customer reads.
- **The filter sits before the limit.** Stage 4's `answer` ranks the whole store, then
  filters, then applies the caller's limit; `search(store, query, limit)` keeps its own
  limit for the naive use, and the difference between the two is the leak the stage
  exists to close. A retriever that takes `top_k` first returns too few rows with a
  small `limit` and the wrong rows with a large one, and neither is visible in the
  retriever's own output — only in what the caller received.
- **A credential is not an argument.** Stage 5's `Vault` hands out a lease
  (`name`, `expires_at`, `redeemed`) and `secret_of(name)` is the only way a secret is
  ever read; no function in the course takes a secret, returns one, or writes one into
  a log line, and the check asserts the literal value appears in no line the world or
  the vault keeps. A redeemed lease may not be redeemed again, an expired one is
  expired at the tick it expires rather than after it, and a rate limit is counted
  before the work and given back when the call is refused.
- **A gate is a person's decision, and the journal is the record of it.** Stage 7
  stops at the first `human` step and runs nothing after it; an approval runs what the
  gate released *and* writes the approval as its own line, because a decision nobody
  can read afterwards is not a decision. The deadline is relative (`due_at = start +
  deadline`) and the escalation fires at it, not after it.
- **The count is recounted, never remembered.** Every stage's number — the cost, the
  ROI, the accuracy, the coverage — is recomputed from the world's own log (the
  meter's spans, the estate's audit lines, the scheduler's submissions), because a
  number a stage believes agrees with itself by construction. This is why the checks
  diff `stats()` and the log before and after a refused call: the refusal has to leave
  no trace, and only the world can prove it did not.
- **A verdict names its reason, and a problem names its offender.** Every answer that
  is a judgement carries the vocabulary entry it is (`below-threshold`, `rate-limited`,
  `budget`, `candidate-worse`, `metric-no-baseline`) and every refusal names the field,
  row, tool, requirement or tick it is about. An `abstained` that is a bare `False`, or
  a problem with no requirement id, is the defect: the customer's auditor cannot act on
  a word that names nothing.
- **The handoff is measured by what the customer can do alone.** Stage 12's
  `Runbook.problems` names the procedures nobody can follow and the steps nobody
  checked, `gaps` puts the untested procedure above the one that still needs the
  engineer, and `Admin` applies a change only with the right and logs every attempt
  including the refusals. A procedure that has never been drilled against an armed
  fault is not a tested procedure, however many times it has been read.

## Where this stops

Deliberately left out, so you know the boundary:

- **No real identity provider.** There is no Okta, no OIDC, no SAML, no SCIM over
  HTTP: `estate.py`'s `IdP` is an assertion-signing directory whose claims, groups and
  clearances you can read, and `apply_scim` mutates it in memory. What a real
  deployment spends its first three weeks on — the app registration, the attribute
  mapping, the sync that silently drops a group — is *simulated* rather than wired.
- **No real legacy system.** There is no SAP, no NetSuite, no database and no OCR:
  `Estate`'s documents are text blobs and its rows are dicts, and stage 3's job is the
  part that survives the transport — the parse, the reconciliation and the quarantine.
  A real feed's pagination, retries and schema drift are not here.
- **No Kubernetes, no cloud, no GPU.** `network.py`'s nodes are records with a zone, a
  GPU size and a state; `install` and `pull` are in-memory transitions of a bundle, and
  stage 8's placement is arithmetic over two integers. No container is built, no image
  is pulled, no kernel is launched and no model is loaded: the course is where the
  *decisions* are, not where the cluster is.
- **No model, and no inference server.** A "model" here is its memory footprint, its
  quality number and its tokens per tick; the model callables stage 6 and stage 10 take
  are ordinary Python functions, and stage 6's `forward` is tested against a leaky and
  a stubborn model rather than a real one. Prompting, context windows and sampling are
  not this course's subject.
- **No real PII and no cryptography.** Stage 6's detector is a deterministic scanner
  with a checksum, and everything it finds is invented: no real SSN, card or address
  is in the repository, and the masking is a placeholder mapping rather than
  tokenisation with a key. There is no key management, no KMS and no envelope
  encryption anywhere in the course.
- **No network, no HTTP, no transport of any kind.** Not one stage opens a socket,
  reads a file, starts a process or reads a clock. The estate, the basement and the
  meter are objects in the same process, and the audit log is a list of dicts —
  which is what makes a run reproducible and a claim checkable offline.
- **No performance work.** Latency, tokens per second, throughput and cost curves are
  not measured, because a machine's speed is not a course's unit. The only numbers
  compared here are ticks, tokens, cents, minutes, counts and basis points, and every
  one of them is an integer the world can recount.

## Where this sits

This is the sixth slot in the repository's K phase, *Agent products and platform
work*, and it is the one that puts the customer in the middle of them: B1
`rag-from-scratch` builds a retriever over one corpus and this course makes it refuse
a row the caller may not see; C1 `evals-from-scratch` builds a harness over a
synthetic dataset and this course runs it against the customer's own tickets and
returns one word; D1 `mcp-from-scratch` speaks the protocol and this course has the
credential stay in the vault while the tools are described, authorized and
rate-limited; J4 `sandbox-capabilities-from-scratch` decides what a program may do and
this course applies that discipline to a deployment that cannot reach out at all. What
it inherits is the house's oldest habit — *the world keeps the record and the claim is
held against it* — applied to the one domain where the record belongs to somebody
else: the customer's directory, the customer's ledger, the customer's GPU and the
customer's own conversations. What it hands on is the shape of the argument: an FDE's
deliverable is a scope, a deployment that survives the security review, and a handoff
that outlives them, and all three of those are data structures before they are
services.

A course is not the whole of that work, and the rest of it is written down in this
same repository: `ENTERPRISE.md` queues the twelve enterprise-AI projects to build
against a *real* system somebody else wrote, and its last section names the ones this
course's stages have already covered in simulation — 2, 3, 4, 5, 7, 10, 11 and 12
whole, and 1 in one direction only — and the three it leaves to those guides alone
(6, 8, 9). The guides are where you are surprised by a system you did not write; this
is where the decisions are graded before you meet it.
