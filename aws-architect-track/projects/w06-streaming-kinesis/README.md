# W6 — Streaming with Kinesis 🆕

> **Exam:** SAA-C03 — High-Performing; MLA-C01 — Data ingestion  
> **After:** W4  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `aws-from-scratch/dynamodb.py` — a hot partition key throttles a stream exactly like it throttles a table

## Goal

Real-time ingestion, and the same hot-partition failure you met offline, now with shards.

## What you build

- Kinesis Data Streams with a producer you control (partition key is a parameter)
- Lambda consumer with checkpointing and a bisect-on-error setting
- Firehose delivery to S3 as a second consumer (feeds W11)
- CloudWatch metrics on iterator age and write throttles

## Acceptance — measured, not "it deployed"

- [ ] A skewed partition key throttles one shard while total throughput is below the stream's capacity
- [ ] Fixing the key (or resharding) removes the throttling, measured
- [ ] Iterator age grows when the consumer is slowed down and recovers when it is not

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Kinesis Data Streams vs SQS vs Firehose: which one for replay, which one for fan-out, which one for 'just land it in S3'?
- Why is per-shard ordering both the feature and the bottleneck?
- What does iterator age tell you that consumer error count does not?

## Layout (to create when you start)

```
w06-streaming-kinesis/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
