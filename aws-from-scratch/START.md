# AWS From Scratch

Toy IAM, S3, SQS, DynamoDB, Lambda, SNS, KMS and VPC, plus a capstone that wires them and breaks them on purpose.

**63 short stages.** Build one behavior at a time in your editor.

## Check the setup

```bash
forja smoke aws-from-scratch
```

## Your first stage

A request with no policies has no Allow statement, so IAM denies it by default. The supplied Decision class takes an allowed boolean and a reason string.

In iam.py, find evaluate() and replace its raise NotImplementedError with the return statement below. The stage-1 checker passes an empty policies list. You will handle matching statements in stage 2.

```python
return Decision(False, "implicit deny")
```

Predict: What is allowed for a request with no policies?

```bash
forja guide aws-from-scratch 1
forja test aws-from-scratch --stage 1
```
