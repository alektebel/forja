# W5 — Containers on ECS Fargate 🆕

> **Exam:** SAA-C03 — High-Performing / Resilient; MLA-C01 — bring-your-own container  
> **After:** W2, W3  
> **Cost:** **$$ — meaningful hourly cost.** Apply, measure and destroy in the same session.  
> **Offline mechanism:** `deploy-and-debug` — canary analysis and rollback

## Goal

Containers are everywhere in both exams and absent from the other projects. Run one service on Fargate and reuse the same image later in SageMaker.

## What you build

- ECR repository with image scanning; a small HTTP service image
- ECS service on Fargate in the W2 private subnets behind an ALB
- Blue/green deployment (CodeDeploy) with an alarm-based rollback
- Service auto scaling on a target metric
- The same image structured so SageMaker can run it as a custom inference container (used again in W13)

## Acceptance — measured, not "it deployed"

- [ ] A deliberately broken image is rolled back automatically by its alarm
- [ ] Scaling out happens under load and the time from alarm to healthy task is measured
- [ ] Tasks pull from ECR without a NAT gateway (VPC endpoints) — and you can list which endpoints that took

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Fargate vs EC2 launch type vs Lambda: what does each one make you own?
- Task role vs execution role: which one pulls the image, which one your code uses?
- What does a SageMaker container need to expose that a plain web service does not?

## Layout (to create when you start)

```
w05-containers-ecs/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
