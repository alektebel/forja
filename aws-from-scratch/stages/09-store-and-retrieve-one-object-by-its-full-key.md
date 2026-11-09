# Stage 9: Store and retrieve one object by its full key

**Edit:** `s3.py` → `S3.put_object / S3.get_object`

## Context

An S3 key is an opaque name, even when it contains a slash.

## Your task

Use the supplied bucket setup. Implement put_object and get_object so one opaque key round trips. A placeholder ETag is enough until stage 11.

## Requirements

- Edit only S3.put_object and S3.get_object in s3.py. The checker creates bucket b itself, unversioned; you never create a bucket.
- Store the body under the FULL key, verbatim. "a/b.txt" is one opaque key: no split("/"), no normalisation, no case handling, no pathlib, nothing created for the a/ prefix.
- get_object on the same bucket and key returns a Version whose body is exactly the bytes written (b"hello"), not a str, not decoded, not the key.
- Fill the Version record: bucket._next_version() for version_id, body, size=len(body), last_modified=time.time(), metadata=dict(metadata or {}), and a placeholder etag string.
- Keep bucket.objects[key] as a list of Version. Unversioned writes overwrite in place (history[:] = [version], length 1); versioned writes append (stage 15). Stage 9 exercises only the unversioned path.
- get_object defaults version_id=None to the current (last) Version. Version lookup is stages 15-17; do not implement it yet.
- put_object returns a str. Stage 9 does not assert it: return the placeholder ETag string so stage 11 changes only compute_etag.
- Do not call compute_etag(): it is stage 11 and still raises NotImplementedError.

## Not in this stage

- Missing-key behaviour: NoSuchKey is stage 10. Raising it early is harmless; returning None for an absent key is not.
- Key validation: empty keys, leading or trailing slashes, URL decoding and UTF-8 rules are not modelled here, and the checker never sends an invalid key.
- Bucket creation, versioning flags, multipart uploads, listing, prefix/delimiter logic, ACLs, signed URLs and stats assertions are later stages or not in the toy at all.
- last_modified is never compared; filling it is presentation, not a behaviour a check depends on.

## Predict

> What bytes come back after putting b/hello under key a/b.txt?

## Check

```bash
forja test aws-from-scratch --stage 9
```

Next: `forja stage aws-from-scratch 10`
