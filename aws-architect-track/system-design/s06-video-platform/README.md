# S6 — Video Upload & Streaming

> **After:** W1, W4 (the AWS projects whose building blocks it uses)  
> **Offline mechanism:** `system-design/cdn_caching.py`, `edge_computing.py`

## Problem

Users upload videos; everyone else streams them at adaptive quality.

## Functional requirements

- Resumable upload of large files
- Transcode to several resolutions
- Adaptive streaming playback
- View counts

## Non-functional requirements

- Upload survives a dropped connection
- Playback start under 2 s in the user's region
- Storage cost under control for videos nobody watches

## Scale to design for

- 500 k uploads/day, average 300 MB
- 1 B views/day, heavily skewed to recent and popular videos

Turn these into requests/s, storage and bandwidth **before** drawing a box. `system-design/capacity_planner.py` is the method.

## Decisions you must make and defend

There is no answer key here. Each decision goes in an ADR with the options you rejected and why.

- How does a client upload a 5 GB file without passing it through your servers?
- How do you orchestrate transcoding and know when all renditions are done?
- What does the CDN cache, and what is the origin load for a viral video vs the long tail?
- Which storage class does a video move to, and when?

## AWS building blocks to consider

A menu, not a solution. Using all of them is a smell; justify each one you pick and one you leave out.

- S3 multipart + presigned URLs
- MediaConvert
- Step Functions
- CloudFront
- S3 lifecycle / Intelligent-Tiering

## Deliverables

- [ ] `DESIGN.md` from [the template](../DESIGN_DOC_TEMPLATE.md): requirements, estimates, diagram, data model, API
- [ ] `adr/` — one ADR per decision above
- [ ] Failure-mode table: what fails, how you detect it, what the user sees
- [ ] Monthly cost estimate at the stated scale, each line traced to a pricing page
- [ ] Optional build slice (Terraform): Presigned multipart upload → event → transcoding pipeline → CloudFront playback for one video.
