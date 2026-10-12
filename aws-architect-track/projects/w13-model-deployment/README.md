# W13 — Model Deployment & Inference Cost

> **Exam:** MLA-C01 — Deployment and Orchestration  
> **After:** W12, W5, A7 deploy-and-debug  
> **Cost:** **$$ — meaningful hourly cost.** Apply, measure and destroy in the same session.  
> **Offline mechanism:** `deploy-and-debug` canary analysis; phase I serving

## Goal

Serve the model several ways and choose by measured latency and cost, not habit.

## What you build

- Real-time endpoint with autoscaling
- Serverless inference and batch transform for the same model
- Canary rollout with deployment guardrails and automatic rollback
- Extension: a multi-model endpoint, Inference Recommender, and the W5 container as a bring-your-own image

## Acceptance — measured, not "it deployed"

- [ ] A deliberately bad model version rolls back on its alarm
- [ ] Latency (p50/p95) and cost per 1,000 predictions compared across real-time, serverless and batch
- [ ] Inference Recommender's suggestion compared with your own measurement

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- When is serverless inference cheaper than a real-time endpoint, and what does cold start cost you?
- What does a multi-model endpoint trade for its savings?
- Shadow testing vs canary: which one risks user traffic?

## Layout (to create when you start)

```
w13-model-deployment/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
