# W0 — Account Foundations

> **Exam:** SAA-C03 — Design Secure Architectures  
> **After:** A1 aws-from-scratch (`iam.py`)  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `aws-from-scratch/iam.py` — explicit Deny > Allow > implicit Deny

## Goal

Make the account safe to experiment in before anything else exists in it. This is the guardrail, not a warm-up: every later project assumes a mistake here costs an email, not a bill.

## What you build

- An IAM Identity Center user with MFA for daily work; the root user with MFA and no access keys, then never used
- AWS Budgets with an alert at a low threshold and a second one at your hard limit
- CloudTrail trail to an S3 bucket you cannot delete objects from by accident
- Terraform remote state in S3 with locking, and a `default_tags` block with `project` and `owner` on every resource
- A teardown script that lists every resource still carrying a `project` tag

## Acceptance — measured, not "it deployed"

- [ ] Root has no access keys (IAM credential report)
- [ ] A test budget alert actually arrives in your inbox
- [ ] `terraform destroy` followed by the teardown script reports zero tagged resources
- [ ] Your daily user cannot disable CloudTrail

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Why should daily work never happen as root, if root has MFA?
- What does a budget alert *not* protect you from? (Hint: when is it evaluated?)
- What happens to your state file if two applies run at once without a lock?

## Layout (to create when you start)

```
w00-account-foundations/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
