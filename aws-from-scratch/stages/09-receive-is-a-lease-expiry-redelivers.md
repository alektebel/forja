# Stage 9: receive is a lease; expiry redelivers

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `sqs.py`
**Tags:** messaging, lifecycle

## The mechanism

receive() is a LEASE, not a read: the visibility timeout hides a message; if it is not deleted in time it is redelivered.

## Why the requirement is what it is

Consumers crash mid-message, and the queue cannot know. A read must either lose the message or block the queue; a lease does neither. Redelivery is the queue CHOOSING duplication over loss — so your handler is idempotent or it is wrong.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 9
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 9
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> whether the same message is received twice.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 10
```
