# W15 — Monitoring & Governance

> **Exam:** MLA-C01 — Monitoring, Maintenance and Security  
> **After:** W13, W7, W2  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `deploy-and-debug` diagnosis; `evals-from-scratch` slices

## Goal

Know when the model goes wrong before the users do, and lock down who can reach it.

## What you build

- Model Monitor data-quality baseline and schedule
- Clarify bias report on the training data and the model
- VPC-only endpoint with KMS-encrypted storage and no internet access
- Least-privilege SageMaker execution role

## Acceptance — measured, not "it deployed"

- [ ] Injected drift fires the monitoring alarm
- [ ] The endpoint is unreachable from outside the VPC
- [ ] The execution role cannot read buckets outside the project

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Data drift vs concept drift: which can Model Monitor see without labels?
- What does a bias metric on training data not tell you about the deployed model?
- Which logs would you need after an incident, and are they on now?

## Layout (to create when you start)

```
w15-monitoring-governance/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
