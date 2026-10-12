# W8 — Multi-Account & Hybrid Networking 🆕

> **Exam:** SAA-C03 — Secure / Resilient (Organizations, SCPs, Transit Gateway, VPN)  
> **After:** W2, W7  
> **Cost:** **$$ — meaningful hourly cost.** Apply, measure and destroy in the same session.  
> **Offline mechanism:** `aws-from-scratch/vpc.py` and `iam.py` — an SCP is a Deny that sits above every account's IAM

## Goal

One of the most-asked SAA blocks and the one a single-VPC project never touches.

## What you build

- AWS Organizations with a sandbox OU and a workload account
- An SCP that denies a region and denies leaving the organization
- Two VPCs (non-overlapping CIDRs) connected through a Transit Gateway
- A Site-to-Site VPN to a simulated 'on-premises' VPC running a software VPN endpoint
- Centralised egress or inspection: design it on paper, build it only if the budget allows

## Acceptance — measured, not "it deployed"

- [ ] An admin in the workload account cannot launch in the denied region
- [ ] Traffic crosses VPCs through the TGW route tables you wrote, and fails when you remove a route
- [ ] The VPN tunnel status and BGP/static routes are explained from the console output

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- VPC peering vs Transit Gateway vs PrivateLink: which one for 2 VPCs, 50 VPCs, one exposed service?
- Why can an SCP never grant a permission?
- What does Direct Connect give you that a VPN cannot, and what does it not give you?

## Layout (to create when you start)

```
w08-multi-account-hybrid/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
