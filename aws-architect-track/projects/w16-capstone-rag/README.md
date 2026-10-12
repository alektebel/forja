# W16 — Capstone: RAG on AWS

> **Exam:** MLA-C01 + SAA-C03  
> **After:** B1 rag-from-scratch, C1 evals-from-scratch, W15  
> **Cost:** **$$ — meaningful hourly cost.** Apply, measure and destroy in the same session.  
> **Offline mechanism:** `rag-from-scratch`, `vector-index-from-scratch`, `evals-from-scratch`, `context-caching`

## Goal

Everything together: a retrieval-augmented system on AWS, judged by measurement and documented like an architect would.

## What you build

- Bedrock models with a managed knowledge base, or your own retrieval over a vector store you choose and justify
- An API in front of it with auth, quotas and caching
- Evaluation with the `evals-from-scratch` harness on a fixed question set
- Architecture document, ADRs and a Well-Architected review

## Acceptance — measured, not "it deployed"

- [ ] Grounded-answer rate and cost per request measured on the fixed set
- [ ] A regression in retrieval is caught by the eval gate
- [ ] Every component is torn down at the end, and the bill matches your estimate within a margin you set beforehand

## Questions to answer before you build

Write your answers in `NOTES.md` in this directory before the first `terraform apply`.

- Managed knowledge base vs your own retrieval: what do you give up in each direction?
- Which vector store has a minimum hourly cost, and does your traffic justify it?
- Where would you cache: the embedding, the retrieval, or the answer — and what can each one get wrong?

## Layout (to create when you start)

```
w16-capstone-rag/
├── README.md       # this file
├── NOTES.md        # your answers and measurements
├── main.tf         # Terraform for this project
├── verify.sh       # AWS CLI checks for the acceptance list
└── teardown.md     # what to destroy and how to confirm it is gone
```

## Teardown

`terraform destroy`, then run the W0 tag check and confirm zero resources remain for this project.
