# AWS From Scratch

Toy IAM, S3, SQS, DynamoDB, Lambda, SNS, KMS and VPC, plus a capstone that wires them and breaks them on purpose.

**63 short stages.** Build one behavior at a time in your editor.

## Check the setup

```bash
forja smoke aws-from-scratch
```

## Your first stage

An IAM request starts denied until a policy grants it.

In iam.py, replace the raise in evaluate() with an implicit-deny Decision when policies is empty. One return statement is enough.

Predict: What is allowed for a request with no policies?

```bash
forja guide aws-from-scratch 1
forja test aws-from-scratch --stage 1
```
