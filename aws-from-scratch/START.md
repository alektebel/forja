# AWS From Scratch

Toy IAM, S3, SQS, DynamoDB, Lambda, SNS, KMS and VPC, plus a capstone that wires them and breaks them on purpose.

**18 stages.** Code in your editor. Run tests locally. No toy IDE.

## Stage 0 — smoke (under 30 seconds)

Confirm the course is runnable before you write anything:

```bash
forja smoke aws-from-scratch
```

You should see `smoke OK`. That is your first green — the same dopamine CodeCrafters buys with 'uncomment and push', without pretending uncommenting taught you IAM.

## Stage 1 — first real work

**File:** `iam.py` — explicit deny > allow > implicit deny

IAM: an explicit Deny wins; otherwise any matching Allow applies; otherwise implicit Deny.

```bash
forja guide aws-from-scratch 1     # the full stage page
forja test aws-from-scratch --stage 1
```

## The loop

1. Read the stage guide
2. Edit the file in your IDE
3. `forja test` (alias of `cz run`)
4. Read the cause / mentor nudge
5. Predict, then re-run

Stuck: `forja hint aws-from-scratch` · `forja explain aws-from-scratch`
