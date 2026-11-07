# Agents From Scratch

Build the runtime under an agent, in pure standard-library Python: the tool loop
and the transcript that is its state, the schemas the model sees, a toolbox that
turns a failure into something the model can read, the parser that survives what
a model actually writes, retries that do not charge twice, memory bounded by
turns, a filesystem sandbox that cannot be escaped, an approval gate against
content that is not a command, budgets that stop a run without overshooting it,
and the audit that grades the world instead of the story.

An agent is not a model. It is a loop, a transcript, a toolbox and a policy —
and every one of those is ordinary code that can be tested without a network.
That is the bet of this course: the model is passed in as a callable, so the
whole runtime is synchronous, deterministic, offline and unit-testable, and the
interesting failures (a result that never reaches the model, a call that leaves
a dangling pair in the transcript, an effect applied twice after a lost
response, a window that cuts a call from its result, a sandbox that resolves
after it writes, a run that makes one call more than its cap) are all visible in
a test instead of in production.

No API keys, no network, no model downloads. Ten stages, each one a mistake that
is easy to make and hard to notice.

## The stages

| # | File | The mechanism | The thing people get wrong |
|---|---|---|---|
| 1 | `stage_01.py` | The loop, the transcript, `max_steps` | Rebuilding the prompt from the task instead of appending to the transcript; the cap raising instead of returning; one call past the cap |
| 2 | `stage_02.py` | Tool schemas, `validate` | `isinstance(True, int)`; a shared mutable default; an unknown key passed through to the tool |
| 3 | `stage_03.py` | `ToolBox.call`, deterministic rendering, truncation | The tool's exception escaping; the tail truncated, which is where errors live |
| 4 | `stage_04.py` | `parse_decision`, repairs with a cap | Repairing the *meaning* (`args` split out of a string); dropping what the model actually said; a repair loop with no cap |
| 5 | `stage_05.py` | Taxonomy, `with_retry`, `Effect.once` | Retrying a bad argument; sleeping after the last attempt; a retry that applies an effect twice |
| 6 | `stage_06.py` | `Session.view`, pins, `ask` | Trimming by message, which cuts a call from its result; pins trimmed away with their turn; handing out the live list |
| 7 | `stage_07.py` | `resolve_path`, `Sandbox` | `startswith(root)`; resolving *after* deciding; `../ws-evil` next to `/ws`; a read-only mode the tools do not inherit |
| 8 | `stage_08.py` | `scan_injection`, `Gate`, `Gated` | Splitting tool output into the system prompt; an approval that overrides a denylist; a refusal raised instead of returned |
| 9 | `stage_09.py` | `Budgets`, `run_budgeted` | Charging after the call, so the count reads cap+1; tool output never charged; `time.time()` instead of the injected clock |
| 10 | `stage_10.py` | `trace_of`, `snapshot`, `audit` | A log with a wall clock or a 4000-character payload; a leak detector that only knows the plain encoding; flagging lines the agent never wrote |

Stages 1–5 are the loop and its defence against a model, 6–9 are state, safety
and cost, 10 is the evidence. Stage 3 validates through stage 2, stage 4 and 6
drive stage 1's loop, so they are meant to be done in order.

## How to use this directory

```bash
python3 codecraft/cli.py run agents-from-scratch   # what to build next, and why
python3 codecraft/cli.py hint agents-from-scratch  # when a nudge is not enough
```

Or without codecraft:

```bash
python3 -c "import course; [print(i, s.title) for i, s in enumerate(course.STAGES, 1)]"
```

Implement the templates at the top level; finished versions are in `solutions/`.

## Prerequisites

Standard library only: `json`, `os`, `base64`, `hashlib`, `fnmatch`, `difflib`,
`tempfile`, `time` (for the one production default: a real sleep). No
`requests`, no provider SDK. You should be comfortable with dicts, classes and
`try/except`; everything else — the loop, the transcript, the gate, the audit —
is built here.

## Design decisions

- **The model is a callable, and the transcript is the state.** `model(messages)
  -> {"tool", "args"} | {"final"}` is the entire interface to intelligence. That
  one choice is what makes the course testable, deterministic and honest about
  where the bugs live: not in the model, in the loop around it. `run["seen"]`
  records what the model was shown on each step, so "the transcript is the
  state" is asserted rather than believed.
- **A call and its result are one unit.** The loop appends the assistant's tool
  call and then its result, in that order, always. A transcript with a dangling
  call is rejected by every real API and unreadable to a model; stage 6's window
  trims by *turns* for exactly this reason.
- **A failure is an observation, not a crash.** An unknown tool, a malformed
  argument, a tool that raises, an unparseable reply, a denied permission and a
  budget that is spent all become `ok=False` with a message the model can act
  on. Only programming errors raise.
- **Repair the envelope, never the meaning.** A code fence, a chatty prefix, a
  capitalised key and a case-different tool name are spelling. `"args":
  "path=x.txt"` is a tool call nobody wrote, and a parser that splits it has
  invented history — so it is a problem the *model* is asked to fix, with a cap
  on how many times, and the transcript keeps the model's own words.
- **Retry the condition, not the symptom.** `Timeout` and `RateLimited` retry;
  `BadArgs` and `NotFound` do not, because waiting does not fix them. Sleep is
  injected, so the schedule becomes a value the check asserts, and there is no
  sleep after the last attempt.
- **A retry needs a key.** The quiet failure of every agent that touches money
  or email is the lost response: the effect landed, the reply did not, the
  caller retried, and it landed twice. Nothing in the retry loop can detect
  that; `Effect.once(request_key(tool, args), fn)` is what makes it impossible.
- **Memory is bounded by turns, not messages.** A message-level window cuts a
  tool call away from its result, and the run that follows is wrong in a way
  no log line explains. Pins ride in the system message, which is the one thing
  that is never trimmed.
- **Confinement is decided on the resolved path.** `../ws-evil` next to `/ws`
  is the failure that a `startswith` comparison cannot see, and a symlink is
  the failure a string comparison cannot see at all. Resolve first, then
  compare components, then touch the disk — and `read_only` is a property of
  the sandbox, so every tool built on it inherits it.
- **Role separation is the defence against injected content; the scan is the
  detector.** Tool output goes in as `role: "tool"`, the system prompt is
  written once, and `scan_transcript` exists to flag what a human should read —
  not to make the transcript safe. The gate is the second half: deny outranks
  approve (a temporary yes ships a permanent capability), and a refusal is an
  observation the model can adapt to.
- **Budgets stop before the call that would exceed them.** A cap of 3 steps
  means three model calls and no more; `rooms=cap+1` is the bug this stage
  exists for. Tokens are charged in both directions, `partial` keeps what the
  agent learned, and the clock is injected so `seconds` is a number a test can
  assert.
- **Grade the world, not the story.** The final message is the least reliable
  evidence about what a run did. `snapshot`/`diff_snapshots`/`unchanged`/
  `no_leak`/`no_new_match` read the filesystem before and after, and the
  subtle one is `no_new_match`: a file that already had a matching line has not
  been changed by the agent, and a detector that flags it teaches reviewers to
  ignore the detector. Every check in stage 10 is exercised twice — once on a
  run that violates it, once on a clean one — because a safety check that has
  never fired is a comment.

## Verification

The solutions pass all ten checks, and every check is mutation-tested: 86
plausible wrong implementations — the tool result before its call, the model
shown the task instead of the transcript, `max_steps` off by one, `True`
accepted for an integer, a shared default list, the tool's exception escaping,
`str(result)` instead of sorted JSON, tail truncation, a fence that is not
unwrapped, `args` split out of a string, a repair loop with no cap, a fatal
error retried, a sleep after the last attempt, a truthiness test in the effect
cache, a message-level window, a pin forgotten with its turn, `startswith(root)`,
`abspath` instead of `realpath`, a read-only mode the tool bypasses, an approval
that overrides the denylist, a refusal raised instead of returned, a step
charged after the call, tool output never charged, `time.time()` in the trace, a
leak in base64 nobody looks for, an "added" line that was already there — are
each planted into a solution, and the stage's check must fail. The assertions
that catch them name the mistake in the message.

Re-running the proof:

```bash
python3 codecraft/cli.py run agents-from-scratch   # per stage, with the failure line
```

## Where this stops

Deliberately left out, so you know the boundary:

- **No real model.** Every stage runs against a scripted callable. Whether a
  model *chooses* good tools and recovers from a bad observation is measured in
  the evals course, not here; this course makes that measurement possible by
  fixing the runtime under it.
- **One tool call per step.** Parallel tool calls, streaming arguments, and
  partial results inside a call are provider features with their own failure
  modes; the transcript shape here is the one they extend.
- **Retries are deterministic.** No jitter, no retry budgets shared across
  calls, no circuit breaker. The jitter is where a real backoff is tuned; the
  taxonomy and the injected clock are what it is tuned against.
- **The sandbox is a path sandbox.** It stops `../` and symlinks. It does not
  stop a subprocess, a symlink raced in after the check, or a tool that opens
  the network — that is containers, seccomp and a network policy.
- **The injection scan is crude on purpose.** A phrase list flags candidates for
  a human reading the trace; it will miss paraphrases and flag honest text. The
  durable protection is the role separation and the gate.
- **The gate is not an authorisation system.** Approvals are a callable; who
  approves, how they are authenticated and what they are allowed to approve is
  a product and identity question.
- **Memory is a window and pins.** No summarisation, no retrieval, no vector
  store — a bounded window is the baseline those have to beat, and the
  retrieval courses are where embeddings come from.
- **The audit grades final state.** It catches a deleted test, a leaked secret
  and an added pipe-to-shell; it cannot see a secret that was read and only sent
  to the model, because nothing on disk changed. Pair it with the trace and with
  a model that is not trusted with the value in the first place.
- **The trace is not a replay.** It is the summary an audit and a CI diff read;
  re-running a recorded model against a changed toolbox is the harness course's
  subject.

Second opinion for after the stages: Harvard's [CS2680](https://cs2680.com/) runs
the same arc with a real model — use a coding agent (Mads-Lens), build the loop
around an API (Mads-Loop, the closest mirror of this course), then optimise tokens,
serve the model yourself and profile the full stack. Its
[cost-effective-agents note](https://cs2680.com/notes/cost-effective-agents.html) is
the best external treatment of what this course deliberately leaves out: pricing the
whole episode, not just the model calls. Catalogued in
[`EXTERNAL-RESOURCES.md`](../EXTERNAL-RESOURCES.md).

On hierarchical agents (a planner delegating to workers): the pattern is
orchestration, not architecture, and the two canonical counterweights are
Anthropic's [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)
(how to make it work) and Cognition's [Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents)
(why single-agent context engineering usually wins). Both belong in the same
breath as CS2680 above — read the pair and argue with them.
