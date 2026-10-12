# AWS Architect Track

From basic knowledge and a little hands-on to the level of an **AWS Solutions
Architect** and an **ML engineer on AWS**, by building on a real account with
**Terraform**. Two kinds of project:

- **`projects/` (W0–W16)** — build it on AWS, then prove it with measurements. W0–W10
  follow AWS Certified Solutions Architect – Associate (SAA-C03); W11–W16 follow AWS
  Certified Machine Learning Engineer – Associate (MLA-C01). Exam codes change: check
  the current exam guide before booking.
- **`system-design/` (S1–S12)** — design a system at a stated scale, defend every
  decision in an ADR, estimate its cost, and optionally build one slice of it with the
  blocks the W projects taught you.

This track is the real-account counterpart of [`aws-from-scratch`](../aws-from-scratch/)
(offline mechanisms) and [`system-design`](../system-design/) (offline patterns). Do
the offline section a project names before you build it.

## Status

Every directory holds a README only: the spec, the acceptance criteria and the
questions to answer. No Terraform, no `verify.sh` yet — those are written when a
project is started. Nothing here is graded by `codecraft`: it cannot check a live
account offline.

## Rules

1. **W0 first.** Budgets, MFA and tagged teardown before any other resource exists.
2. **Measured acceptance.** "It deployed" proves the syntax. Each project lists what
   to measure — failover time, bytes scanned, a message in a DLQ — and you record it
   in that project's `NOTES.md`.
3. **Answer the questions before `terraform apply`.** They are the exam, and the
   reason the project exists.
4. **Destroy what you build.** Projects marked **$$** have a meaningful hourly cost:
   apply, measure and destroy in the same session.
5. **When the toy and AWS disagree, AWS is right** and the offline model has a bug
   worth a test.

## Build projects

| # | Project | Cost | Exam focus | After |
|---|---|---|---|---|
| [W0](projects/w00-account-foundations/) | Account Foundations |  | SAA-C03 — Design Secure Architectures | A1 |
| [W1](projects/w01-static-site-cdn/) | Static Site + CDN |  | SAA-C03 — Secure / High-Performing | W0 |
| [W2](projects/w02-network-from-zero/) | Network From Zero | $$ | SAA-C03 — Secure / Resilient | W0 |
| [W3](projects/w03-three-tier-ha/) | Three-Tier HA App, with Caching | $$ | SAA-C03 — Resilient / High-Performing | W2, A5, A7 |
| [W4](projects/w04-serverless-event-driven/) | Serverless, Event-Driven |  | SAA-C03 — Resilient / High-Performing | W0 |
| [W5](projects/w05-containers-ecs/) | Containers on ECS Fargate 🆕 | $$ | SAA-C03 — High-Performing / Resilient; MLA-C01 — bring-your-own container | W2, W3 |
| [W6](projects/w06-streaming-kinesis/) | Streaming with Kinesis 🆕 |  | SAA-C03 — High-Performing; MLA-C01 — Data ingestion | W4 |
| [W7](projects/w07-security-encryption/) | Security & Encryption |  | SAA-C03 — Design Secure Architectures | W0 |
| [W8](projects/w08-multi-account-hybrid/) | Multi-Account & Hybrid Networking 🆕 | $$ | SAA-C03 — Secure / Resilient (Organizations, SCPs, Transit Gateway, VPN) | W2, W7 |
| [W9](projects/w09-observability-dr/) | Observability, Backup & DR | $$ | SAA-C03 — Design Resilient Architectures | W3 |
| [W10](projects/w10-cost-well-architected/) | Cost & Well-Architected Review |  | SAA-C03 — Design Cost-Optimized Architectures | W3 |
| [W11](projects/w11-data-lake-ml/) | Data Lake for ML |  | MLA-C01 — Data Preparation for ML | W7, W6 |
| [W12](projects/w12-training-sagemaker/) | Training on SageMaker, with a Feature Store |  | MLA-C01 — ML Model Development | W11 |
| [W13](projects/w13-model-deployment/) | Model Deployment & Inference Cost | $$ | MLA-C01 — Deployment and Orchestration | W12, W5, A7 |
| [W14](projects/w14-mlops-pipeline/) | MLOps Pipeline |  | MLA-C01 — Deployment and Orchestration (CI/CD) | W13 |
| [W15](projects/w15-monitoring-governance/) | Monitoring & Governance |  | MLA-C01 — Monitoring, Maintenance and Security | W13, W7, W2 |
| [W16](projects/w16-capstone-rag/) | Capstone: RAG on AWS | $$ | MLA-C01 + SAA-C03 | B1, C1, W15 |

🆕 = added to cover containers, multi-account/hybrid networking and streaming, which
the exams ask about and no other project touched. W3, W12 and W13 also carry an
extension (caching and database choice, Feature Store, inference cost).

Sequence: W0 before everything; W2 before anything that lives in a VPC; W7 before
W8 and W11; W12 → W13 → W14 → W15 in order. W1, W4 and W6 can run any time after W0.

## System design projects

| # | System | After |
|---|---|---|
| [S1](system-design/s01-url-shortener/) | URL Shortener | W4 |
| [S2](system-design/s02-rate-limiter/) | Distributed Rate Limiter | W3, W4 |
| [S3](system-design/s03-notification-system/) | Notification System | W4 |
| [S4](system-design/s04-news-feed/) | News Feed / Timeline | W3 |
| [S5](system-design/s05-chat-messaging/) | Real-Time Chat | W4 |
| [S6](system-design/s06-video-platform/) | Video Upload & Streaming | W1, W4 |
| [S7](system-design/s07-payments-ledger/) | Payments Ledger | W3, W7 |
| [S8](system-design/s08-job-scheduler/) | Distributed Job Scheduler | W4 |
| [S9](system-design/s09-search-autocomplete/) | Search Autocomplete | W3 |
| [S10](system-design/s10-geo-matching/) | Ride-Hailing Geo Matching | W6 |
| [S11](system-design/s11-recommendation-serving/) | Recommendation Serving | W12, W13 |
| [S12](system-design/s12-llm-platform/) | Multi-Tenant LLM Platform | W13, W16 |

Each one is a design exercise first: requirements with numbers, estimates, an API, a
data model, a diagram, ADRs, a failure-mode table and a monthly cost. The
[design doc template](system-design/DESIGN_DOC_TEMPLATE.md) fixes the structure. There
is no answer key in this repository; the decisions are the exercise.

## What this track does not claim

Passing it is not passing the exams. The projects cover the architecture the exams
test; the exams also test breadth — EFS/FSx, Storage Gateway, DMS, Snow, Redshift,
EMR, Cognito and dozens more seen once in a scenario question — that practice
questions cover better than projects.
