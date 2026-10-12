# W12 — Training on SageMaker, with a Feature Store

> **Exam:** MLA-C01 — ML Model Development  
> **After:** W11  
> **Cost:** Low cost if torn down after use.  
> **Offline mechanism:** `evals-from-scratch` — held-out splits and significance

## Goal

Train, tune and register a model, with features stored once and reused offline and online.

## What you build

- Processing job for feature engineering
- Extension: SageMaker Feature Store with offline and online stores
- Training job (built-in XGBoost or script mode) and a hyperparameter tuning job
- Experiment tracking and Model Registry with an approval status

## Acceptance — measured, not "it deployed"

- [ ] The tuned model beats a recorded baseline on a held-out set, by a margin you can defend
- [ ] Training reads features from the offline store; the same feature values are retrievable from the online store
- [ ] The model version is registered as PendingManualApproval

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- What is training/serving skew, and how does a feature store reduce it?
- Bayesian vs random search in tuning: when is the difference worth the money?
- What leaks if you split after feature engineering instead of before?

## Layout (to create when you start)

```
w12-training-sagemaker/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
