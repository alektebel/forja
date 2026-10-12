# W2 — Network From Zero

> **Exam:** SAA-C03 — Secure / Resilient  
> **After:** W0  
> **Cost:** **$$ — meaningful hourly cost.** Apply, measure and destroy in the same session.  
> **Offline mechanism:** `aws-from-scratch/vpc.py` — security groups are stateful, NACLs are not

## Goal

Build the network every later project lives in, and see with your own Flow Logs the stateful/stateless difference you modelled offline.

## What you build

- VPC across 2 AZs with public and private subnets and explicit route tables
- One NAT gateway (the cost item) and an S3 gateway endpoint
- A private instance reachable only through SSM Session Manager — no bastion, no SSH port
- VPC Flow Logs to CloudWatch Logs
- A NACL rule that denies something the security group allows

## Acceptance — measured, not "it deployed"

- [ ] With the NAT gateway removed, the private instance still reaches S3 (through the endpoint) and nothing else
- [ ] Flow Logs show REJECT for the NACL-denied traffic while the SG would have allowed it
- [ ] You can draw the route a packet takes from the private instance to S3 and to the internet

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Why does one NAT gateway make the design non-resilient, and what does fixing that cost?
- Which AWS services can a gateway endpoint reach, and which need an interface endpoint?
- Why does a NACL need an ephemeral-port rule for return traffic and an SG does not?

## Layout (to create when you start)

```
w02-network-from-zero/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
