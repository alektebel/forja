# Deploy & Debug

Capacity math, percentiles, SLOs and error budgets, root-causing injected faults from metrics, and safe rollout.

**12 stages.** Code in your editor. Run tests locally. No toy IDE.

## Stage 0 — smoke (under 30 seconds)

Confirm the course is runnable before you write anything:

```bash
forja smoke deploy-and-debug
```

You should see `smoke OK`. That is your first green — the same dopamine CodeCrafters buys with 'uncomment and push', without pretending uncommenting taught you IAM.

## Stage 1 — first real work

**File:** `capacity.py` — KV cache and batch-size math

KV cache bytes/token = 2 * layers * KV_HEADS * head_dim * bytes. Using query heads sizes the fleet 4x too large.

```bash
forja guide deploy-and-debug 1     # the full stage page
forja test deploy-and-debug --stage 1
```

## The loop

1. Read the stage guide
2. Edit the file in your IDE
3. `forja test` (alias of `cz run`)
4. Read the cause / mentor nudge
5. Predict, then re-run

Stuck: `forja hint deploy-and-debug` · `forja explain deploy-and-debug`
