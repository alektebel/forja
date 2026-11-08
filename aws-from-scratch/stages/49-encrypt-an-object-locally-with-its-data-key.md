# Stage 49: Encrypt an object locally with its data key

**Edit:** `kms.py` → `EnvelopeCipher.encrypt / EnvelopeCipher.decrypt`

## Context

The data key encrypts the payload outside KMS.

## Your task

Encrypt an object locally with its data key.

## Predict

> What must be stored beside the payload ciphertext to decrypt it later?

## Check

```bash
forja test aws-from-scratch --stage 49
```

Next: `forja stage aws-from-scratch 50`
