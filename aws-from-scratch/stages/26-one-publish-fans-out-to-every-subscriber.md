# Stage 26: one publish fans out to every subscriber

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sns.py`
**Tags:** messaging

## The mechanism

Filter policies: AND across keys, OR within one, a MISSING attribute never matches, and no policy means deliver.

## Why the requirement is what it is

The same fail-closed rule as IAM conditions (stage 2): treating absent as permissive would silently route events that were supposed to be scoped. The filter runs at the TOPIC — drops happen before fanout, not at the consumer.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 26
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 26
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which subscriptions a two-attribute message hits.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 27
```
