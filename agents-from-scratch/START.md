# Agents From Scratch

An agent runtime from the parts up: the tool loop and its transcript, tool schemas and validation, a toolbox that turns failures into observations, parsing a model's reply, retries with idempotent effects, turn-aware memory, a filesystem sandbox, an approval gate and prompt-injection detection, budgets with honest stop reasons, and a state-based audit.

**10 stages.** Code in your editor. Run tests locally. No toy IDE.

## Stage 0 — smoke (under 30 seconds)

Confirm the course is runnable before you write anything:

```bash
forja smoke agents-from-scratch
```

You should see `smoke OK`. That is your first green — the same dopamine CodeCrafters buys with 'uncomment and push', without pretending uncommenting taught you IAM.

## Stage 1 — first real work

**File:** `stage_01.py` — the loop, and the transcript that is the state

Implement run_agent: call the model with the transcript, append the tool call and its result as a pair, stop on a final answer, and count what you showed the model.

```bash
forja guide agents-from-scratch 1     # the full stage page
forja test agents-from-scratch --stage 1
```

## The loop

1. Read the stage guide
2. Edit the file in your IDE
3. `forja test` (alias of `cz run`)
4. Read the cause / mentor nudge
5. Predict, then re-run

Stuck: `forja hint agents-from-scratch` · `forja explain agents-from-scratch`
