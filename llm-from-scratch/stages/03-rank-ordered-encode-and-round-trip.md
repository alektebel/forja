# Stage 3: rank-ordered encode and round-trip

**Course:** LLM From Scratch (`llm-from-scratch`)
**File:** `tokenizer.py`
**Tags:** ordering

## The mechanism

Make encode repeatedly apply the LOWEST-RANK merge anywhere in the sequence (not a left-to-right sweep); decode expands ids bottom-up.

## Tests

The tester runs your code like this:

```bash
forja test llm-from-scratch --stage 3
# same as:
python3 codecraft/cli.py run llm-from-scratch --stage 3
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> encode('aba') with (98,97)->256, (97,98)->257 gives [97,256].

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage llm-from-scratch 4
```
