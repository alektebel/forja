# LLM From Scratch

The five forward-pass mechanisms of a language model in plain Python: BPE, attention, sampling, the KV cache, RoPE.

**13 stages.** Code in your editor. Run tests locally. No toy IDE.

## Stage 0 — smoke (under 30 seconds)

Confirm the course is runnable before you write anything:

```bash
forja smoke llm-from-scratch
```

You should see `smoke OK`. That is your first green — the same dopamine CodeCrafters buys with 'uncomment and push', without pretending uncommenting taught you IAM.

## Stage 1 — first real work

**File:** `tokenizer.py` — pair counts and non-overlapping merges

Write get_pair_counts as a dict of adjacent pairs, then merge_pair with an index that SKIPS PAST each merge, so [1,1,1] becomes [9,1] and not two overlapping merges.

```bash
forja guide llm-from-scratch 1     # the full stage page
forja test llm-from-scratch --stage 1
```

## The loop

1. Read the stage guide
2. Edit the file in your IDE
3. `forja test` (alias of `cz run`)
4. Read the cause / mentor nudge
5. Predict, then re-run

Stuck: `forja hint llm-from-scratch` · `forja explain llm-from-scratch`
