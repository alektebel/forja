# W10 — Cost & Well-Architected Review

> **Exam:** SAA-C03 — Design Cost-Optimized Architectures  
> **After:** W3  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `system-design/capacity_planner.py`

## Goal

Close the SAA half with the pillar every other project treated as a side note.

## What you build

- Cost allocation tags activated; Cost Explorer views per project
- Spot in a mixed-instances ASG for the W3 web tier
- S3 lifecycle rules and Intelligent-Tiering where they pay
- A written Well-Architected review of W3 (all six pillars)

## Acceptance — measured, not "it deployed"

- [ ] A before/after monthly cost of W3 with every number traced to a pricing page or your bill
- [ ] The review names at least one high-risk issue and the change that fixes it

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Savings Plans vs Reserved Instances vs Spot: what commitment does each ask for?
- Where does data transfer cost hide in W3?
- Which W3 component is the most expensive at idle, and why?

## Layout (to create when you start)

```
w10-cost-well-architected/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
