# Stage 48: Return plaintext and wrapped copies of one data key

**Edit:** `kms.py` → `KMS.generate_data_key / KMS.decrypt_data_key`

## Context

Envelope encryption begins with a plaintext and wrapped data key.

## Your task

Key creation and wrapping helpers are supplied. Implement generate_data_key and decrypt_data_key so the two forms of one key round trip.

## Predict

> What two forms of the same data key does GenerateDataKey return?

## Check

```bash
forja test aws-from-scratch --stage 48
```

Next: `forja stage aws-from-scratch 49`
