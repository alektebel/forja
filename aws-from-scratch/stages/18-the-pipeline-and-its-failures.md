# Stage 18: the pipeline, and its failures

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `capstone.py`
**Tags:** plumbing

## The mechanism

Capstone: wire the services into one pipeline and reproduce each of its failure modes deliberately.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 18
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 18
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which service's failure stops the pipeline first.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 19
```
