# Stage 51: Keep old key material usable after rotation

**Edit:** `kms.py` → `MasterKey.rotate`

## Context

Rotation keeps older key material available for decryption.

## Your task

Keep old key material usable after rotation.

## Predict

> Can ciphertext from before rotation still be decrypted afterward?

## Check

```bash
forja test aws-from-scratch --stage 51
```

Next: `forja stage aws-from-scratch 52`
