# Stage 27: filters: AND keys, OR values, missing never matches

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sns.py`
**Tags:** messaging, boundary

## The mechanism

EventBridge matches the SHAPE of the event: patterns nest into detail, a key absent from the event cannot match, and one event fires EVERY matching rule.

## Why the requirement is what it is

Nothing deduplicates rule firing — two matching rules means double-processing, which is either free parallelism or a double-charge depending on whether you knew. Structural matching is what makes one bus carry every service's events.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 27
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 27
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> how many rules fire when one event matches two.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 28
```
