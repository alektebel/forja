# Stage 13: oldest_age counts in-flight messages too

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sqs.py`
**Tags:** messaging, lifecycle

## The mechanism

oldest_age counts IN-FLIGHT messages too: a message being retried forever is old, not young.

## Why the requirement is what it is

The age alarm exists to catch the poison message — which spends most of its life in flight, invisible to a visible-only age. The metric must describe the queue's actual state, not the easy subset.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 13
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 13
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> oldest_age of a message received once and never deleted.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 14
```
