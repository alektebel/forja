# Stage 9: Store and retrieve one object by its full key

**Edit:** `s3.py` → `S3.put_object / S3.get_object`

## Context

An S3 key is an opaque name, even when it contains a slash.

## Your task

Use the supplied bucket setup. Implement put_object and get_object so one opaque key round trips. A placeholder ETag is enough until stage 11.

## Predict

> What bytes come back after putting b/hello under key a/b.txt?

## Check

```bash
forja test aws-from-scratch --stage 9
```

Next: `forja stage aws-from-scratch 10`
