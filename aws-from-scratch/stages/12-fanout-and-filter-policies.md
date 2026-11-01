# Stage 12: fanout and filter policies

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sns.py`
**Tags:** messaging

## The mechanism

SNS fans out; filter policies match message attributes (AND within a key, OR across values).

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 12
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 12
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which subscriptions a two-attribute message hits.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 13
```
