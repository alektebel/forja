# W11 — Data Lake for ML

> **Exam:** MLA-C01 — Data Preparation for ML  
> **After:** W7, W6  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `aws-from-scratch/s3.py`, `iam.py`

## Goal

Open the ML half with the data, not the model.

## What you build

- S3 raw / curated zones; Firehose from W6 landing raw data
- Glue crawler and an ETL job to partitioned Parquet
- Athena queries over both formats
- Lake Formation permissions with a column-level grant
- A data-quality rule set (Glue Data Quality) on the curated zone

## Acceptance — measured, not "it deployed"

- [ ] The same query scans measurably fewer bytes on partitioned Parquet than on CSV
- [ ] A Lake Formation grant hides a column from one principal
- [ ] A bad batch fails the data-quality rules before it reaches curated

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Why does partitioning reduce cost in Athena, and when does over-partitioning hurt?
- Who enforces access when both IAM and Lake Formation apply?
- What data problem would silently ruin a model and still pass a schema check?

## Layout (to create when you start)

```
w11-data-lake-ml/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
