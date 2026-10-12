# W1 — Static Site + CDN

> **Exam:** SAA-C03 — Secure / High-Performing  
> **After:** W0  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `aws-from-scratch/s3.py` and `iam.py` — a bucket policy is just a resource policy evaluated with the same rules

## Goal

Serve a site from a bucket nobody can read directly. Small project, one sharp idea: who is the principal when CloudFront reads your bucket?

## What you build

- Private S3 bucket with Block Public Access on
- CloudFront distribution with Origin Access Control and an ACM certificate (us-east-1)
- Bucket policy that allows only that distribution
- Cache behaviours with different TTLs for HTML and static assets

## Acceptance — measured, not "it deployed"

- [ ] The S3 object URL returns 403; the CloudFront URL returns 200
- [ ] A cache hit ratio is visible in CloudFront metrics after repeated requests
- [ ] Changing a file without invalidation keeps serving the old one until its TTL — and you can explain why

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Why must the ACM certificate for CloudFront live in us-east-1?
- What is the difference between Origin Access Identity and Origin Access Control, and why did AWS replace one?
- When is an invalidation the wrong tool compared with versioned file names?

## Layout (to create when you start)

```
w01-static-site-cdn/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
