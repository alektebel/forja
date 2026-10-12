# W3 — Three-Tier HA App, with Caching

> **Exam:** SAA-C03 — Resilient / High-Performing  
> **After:** W2, A5 system-design, A7 deploy-and-debug  
> **Cost:** **$$ — meaningful hourly cost.** Apply, measure and destroy in the same session.  
> **Offline mechanism:** `system-design/cache.py`, `capacity_planner.py`; `deploy-and-debug` readiness vs liveness

## Goal

The classic architecture, proven by breaking it. Extended with the database and cache choices SAA asks about most.

## What you build

- ALB + Auto Scaling group across 2 AZs from a launch template
- RDS Multi-AZ (or Aurora) with credentials in Secrets Manager
- Extension: ElastiCache (Redis/Valkey) as a cache-aside layer, and an Aurora read replica for read traffic
- Health checks that distinguish 'process up' from 'ready to serve'

## Acceptance — measured, not "it deployed"

- [ ] Terminating every instance in one AZ keeps the service answering
- [ ] RDS failover downtime is measured in seconds from the client side, not taken from the docs
- [ ] Cache hit rate and p95 latency measured with and without the cache under the same load
- [ ] Replica lag observed and its effect on a read-after-write explained

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Multi-AZ standby vs read replica: which one serves reads, and which one saves you in a failover?
- What breaks first if the cache is cold after a deploy? (`system-design` has a name for it)
- Why can a health check that is too strict take the whole fleet down?

## Layout (to create when you start)

```
w03-three-tier-ha/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
