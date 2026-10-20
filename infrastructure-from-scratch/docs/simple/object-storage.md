# Object Storage — Simple

## 1. What problem does it solve?

Traditional filesystems:
- Fixed size (you provisioned 1TB, it's 1TB)
- Mounted on one machine (or a cluster with complex replication)
- Poor durability guarantee (a disk failure = data loss unless you RAID/replicate)

Object storage solves all three:
- **Infinitely scalable**: add capacity without re-architecting
- **Durability**: 99.999999999% (11 nines) — data survives multiple disk failures
- **API-driven**: access via HTTP REST, not filesystem mounts
- **Metadata**: every object carries arbitrary key-value metadata
- **Cost**: cheaper per-GB than block storage for cold data

**The job:** store arbitrary blobs (files, images, backups, logs) durably
and serve them back on request, at scale.

## 2. How does it work?

### Data model

```
Bucket → { key → { body, metadata, version } }
```

- **Bucket**: namespace (like a directory root)
- **Key**: object name (can contain "/" for pseudo-hierarchy)
- **Body**: raw bytes (up to 5TB per object)
- **Metadata**: HTTP headers stored with the object

### Durability: erasure coding vs replication

| Approach | How it works | Pros | Cons |
|---|---|---|---|
| **Replication (3x)** | Store 3 identical copies on different machines/disks | Simple, fast reads | 200% overhead |
| **Erasure coding** | Split object into k data shards + m parity shards (e.g. 10+3); any 10 of 13 shards reconstruct | Better space efficiency (30% overhead) | More complex reconstruction, slower reads |

Amazon S3 uses a proprietary scheme. Google Cloud Storage and Azure Blob
use erasure coding.

### Upload: multipart upload

For large objects (>5MB), upload in parts:
1. `POST /upload` → gets `upload_id`
2. `PUT /upload?upload_id=&part_num=N` for each part
3. `POST /upload?upload_id=&parts=[...]` → assemble

If a part fails, retry only that part. No re-upload the whole thing.

### Parallel reads: byte-range requests

Clients can request `bytes=0-999` (first 1000 bytes), `bytes=1000-1999`, etc.
The server serves only that range. Enables:
- Streaming video (request chunks as needed)
- Parallel downloads (split a file into 10 ranges, download each on a separate connection)
- Partial file updates (replace only part of a large log file)

### Consistency model

| Model | Guarantee | Trade-off |
|---|---|---|
| **Strong** | Read-after-write is always current | Requires coordination (expensive) |
| **Eventual** | Reads may return stale data for ms–s | Fast, available, but reads can be stale |
| **Read-after-write (S3 standard)** | Writes are immediately readable | S3-specific; eventual for deletes and cross-region |

## 3. Real implementations

| Implementation | Type | Notes |
|---|---|---|
| **Amazon S3** | Cloud object storage | 11 nines durability; 6 parallel disks; multipart upload |
| **Google Cloud Storage** | Cloud object storage | Erasure coding; multi-region replication |
| **MinIO** | Open-source S3-compatible | Self-hosted; runs on a single node or cluster; S3 API compatible |
| **Ceph Rados** | Open-source distributed object | CRUSH algorithm for placement; used by OpenStack |
| **ZFS** | Filesystem + object store | Native checksumming; self-healing; erasure coding |

## 4. Trade-offs

| Decision | Option A | Option B | When to choose B |
|---|---|---|---|
| Consistency | Eventual | Strong read-after-write | Financial data → strong; logs → eventual |
| Storage class | Hot (frequent access) | Cold/archive (rare access) | 95% of data rarely accessed → cold |
| Duplication | 3x replication | Erasure coding | Need max space efficiency → erasure coding |
| Access | Public read | Signed URLs (time-limited) | Share a file without making it public |
| Versioning | Single version | All versions kept (S3 versioning) | Need audit trail or rollback → versioning |

## 5. Exercises

1. **Simple object store**: A Python HTTP server that accepts PUT/GET for key→body pairs, stores on disk with an index.
2. **Multipart upload**: Accept an `upload_id`, collect parts, assemble on final PUT, reject unknown upload_ids.
3. **Byte-range requests**: Support `Range` header; serve partial content with `206 Partial Content` and `Content-Range` header.
4. **Erasure coding (k=3, m=2)**: Split an object into 3 data + 2 parity shards; reconstruct from any 3 of 5 shards.
5. **Signed URL generator**: Given a key, expiry time, and secret, produce an HMAC-SHA256-signed URL valid until expiry.

## 6. References

- [Amazon S3 documentation](https://docs.aws.amazon.com/s3/)
- [S3 durability model (Jeff Barr, AWS blog)](https://aws.amazon.com/s3/features/#Durability)
- [MinIO documentation](https://docs.min.io/)
- [Ceph architecture](https://docs.ceph.com/en/latest/architecture/)
- [Erasure coding: "Erasure Coding Basics" (Hedgeman et al., 2009)](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/erasure-coding-basics.pdf)