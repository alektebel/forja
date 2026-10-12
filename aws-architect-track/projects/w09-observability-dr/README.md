# W9 — Observability, Backup & DR

> **Exam:** SAA-C03 — Design Resilient Architectures  
> **After:** W3  
> **Cost:** **$$ — meaningful hourly cost.** Apply, measure and destroy in the same session.  
> **Offline mechanism:** `deploy-and-debug` — percentiles, error budgets, diagnosis from metrics

## Goal

Write the RTO and RPO first, then measure whether the design meets them.

## What you build

- CloudWatch dashboard and alarms on the W3 app (latency percentiles, 5xx, saturation)
- AWS Backup plan for the database
- Cross-region S3 replication
- Route 53 failover record with health checks to a second region (pilot light)

## Acceptance — measured, not "it deployed"

- [ ] Measured RTO and RPO compared with the targets you wrote before the test
- [ ] An alarm fires on a real fault you injected, with the time to detection recorded

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Backup & restore, pilot light, warm standby, active-active: what does each cost and what RTO does it buy?
- Why is an untested backup not a backup?
- Which of your alarms would fire on a slow failure, not just a hard one?

## Layout (to create when you start)

```
w09-observability-dr/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
