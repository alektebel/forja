# AWS From Scratch

Build small Python models of IAM, S3, SQS, DynamoDB, Lambda, SNS, KMS, and VPC, then connect them. The course teaches service mechanisms through observable behavior; it does not require an AWS account.

**63 short stages.** Each stage adds one behavior. Specialized topics, such as multipart ETags and FIFO deduplication, remain separate steps. The [stage design and AWS fidelity notes](REDESIGN.md) explain the sequencing and where the toy differs from AWS.

## Start here

```bash
forja smoke aws-from-scratch
forja guide aws-from-scratch 1
forja test aws-from-scratch --stage 1
```

Stage 1 asks for one line in `iam.py`: when there are no policies, return an implicit-deny `Decision`. It does not require matching, wildcards, conditions, or roles. Stage 2 adds a matching Allow; stage 3 adds explicit Deny precedence.

After each green check, open the next guide. Each guide gives one sentence of context, one task, an example to predict, and the command to check it. The guide and checker read the same [lesson records](lessons.json).

## Path

| Stages | Service | Progression |
|---|---|---|
| 1–8 | IAM | default deny → matching → precedence → conditions → boundaries → roles |
| 9–17 | S3 | object → absent key → ETags → listing → versions → delete marker |
| 18–26 | SQS | visibility lease → redelivery → acknowledgement → DLQ → FIFO |
| 27–33 | DynamoDB | composite key → query → conditional write → capacity → scan |
| 34–42 | Lambda | cold start → reuse → timeout → concurrency → retries |
| 43–47 | SNS / EventBridge | fanout → filtering → event patterns |
| 48–51 | KMS | data keys → local encryption → context → rotation |
| 52–58 | VPC | CIDR → subnets → routing → security groups → NACLs |
| 59–63 | Integration | one connection at a time → authorization → failure diagnosis |

Run `python3 check.py` inside this directory for the next incomplete stage, `python3 check.py N` for one stage, or `python3 check.py --all` for the whole ladder. The checker imports learner files, not `solutions/`.

The [reference implementations](solutions/) are for comparison after trying the stage. The [compliance scenarios](COMPLIANCE.md) and [audit](AUDIT.md) are additional reading. The KMS toy uses XOR to demonstrate envelope structure; it is not cryptography for real data.

For course authors, `python3 validate_course.py` checks that all 63 lesson
records, executable checks, and generated pages agree.
