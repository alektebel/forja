# Stage 36: the pipeline, and failures surfacing a layer away

**Course:** AWS From Scratch (`aws-from-scratch`)
**File:** `capstone.py`
**Tags:** plumbing

## The mechanism

Capstone: wire S3 → SNS → SQS → Lambda → DynamoDB, KMS on the payload, IAM on every call — then watch a DynamoDB hot partition surface as a Lambda alarm.

## Why the requirement is what it is

Failures compose too: the cause lives in the data model, the alarm fires on compute, and the audit trail must record DENIED calls or you debug from half the evidence. That mismatch between where a failure is VISIBLE and where it is CAUSED is most of what makes distributed debugging hard.


## Tests

The tester runs your code like this:

```bash
forja test aws-from-scratch --stage 36
# same as:
python3 codecraft/cli.py run aws-from-scratch --stage 36
```

It imports **your** module (never `solutions/`) and asserts the behaviour this stage defines. A red failure names the likely cause — read that before rewriting.

## Predict before you look

> which service's failure stops the pipeline first.

Commit to a number (or outcome) *before* the check prints. That is where the learning consolidates.

## Next

When this stage is green:

```bash
forja stage aws-from-scratch 37
```
