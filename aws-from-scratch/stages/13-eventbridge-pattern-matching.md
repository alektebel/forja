# Stage 13: EventBridge pattern matching

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sns.py`
**Tags:** messaging, boundary

## The mechanism

EventBridge patterns match nested detail; arrays mean OR, and an EMPTY pattern matches everything.

## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 13
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 13
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether {} matches a random event.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 14
```
