# Stage 50: Bind the wrapped key to an encryption context

**Edit:** `kms.py` → `KMS.decrypt_data_key`

## Context

Encryption context binds a wrapped key to request metadata.

## Your task

Bind the wrapped key to an encryption context.

## Predict

> Can ciphertext encrypted under tenant A be decrypted under tenant B?

## Check

```bash
forja test aws-from-scratch --stage 50
```

Next: `forja stage aws-from-scratch 51`
