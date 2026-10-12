# W7 — Security & Encryption

> **Exam:** SAA-C03 — Design Secure Architectures  
> **After:** W0  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `aws-from-scratch/kms.py` (envelope encryption) and `iam.py`

## Goal

Least privilege you can prove, encryption you can explain at the key level.

## What you build

- Customer-managed KMS key with a key policy you wrote, and automatic rotation
- Bucket policy denying non-TLS requests and unencrypted puts
- Roles with a permissions boundary so a delegated admin cannot escalate
- IAM Access Analyzer on the account

## Acceptance — measured, not "it deployed"

- [ ] The IAM policy simulator shows each deny you designed
- [ ] Access Analyzer reports no unintended external access
- [ ] After rotation, objects encrypted before it are still readable — and you can explain why without re-encrypting

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Key policy vs IAM policy: when does an IAM Allow on a KMS key do nothing?
- SSE-S3 vs SSE-KMS vs client-side: what does each protect against?
- What can a permissions boundary never grant?

## Layout (to create when you start)

```
w07-security-encryption/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
