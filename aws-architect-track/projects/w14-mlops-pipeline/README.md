# W14 — MLOps Pipeline

> **Exam:** MLA-C01 — Deployment and Orchestration (CI/CD)  
> **After:** W13  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `mlops` (legacy project) and `evals-from-scratch` regression gate

## Goal

From commit to deployed model with one human gate, all of it in Terraform.

## What you build

- SageMaker Pipelines: process → train → evaluate → register
- CI (GitHub Actions or CodePipeline) that starts the pipeline on a commit
- A registry approval that triggers deployment; rejection changes nothing
- A quality gate: the pipeline refuses to register a model worse than production

## Acceptance — measured, not "it deployed"

- [ ] A commit retrains and stops at approval
- [ ] Approving deploys; rejecting leaves production untouched
- [ ] A worse model is stopped by the gate, not by you

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- What belongs in the pipeline and what belongs in CI?
- How do you roll back a model *and* the features it expects?
- Who should be allowed to approve, and how is that enforced in IAM?

## Layout (to create when you start)

```
w14-mlops-pipeline/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
