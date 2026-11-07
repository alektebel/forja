# AWS From Scratch

Learn AWS by implementing toy versions of its services in pure Python — and, more
usefully, by reproducing the failures that make them confusing in practice.

## Scope, honestly

AWS has **200+ services**. Implementing all of them would be neither feasible nor
useful: most are variations on a mechanism another service already has, or thin
management layers with nothing to learn from.

So this directory implements the **eight distinct mechanism families** that everything
else is built from, and then [maps the rest onto them](#the-rest-of-aws-and-what-it-is-made-of).
One mechanism deeply beats nine gestured at.

| Service | The mechanism | The thing people get wrong |
|---|---|---|
| `iam.py` | Policy evaluation | Explicit Deny beats everything, in any order |
| `s3.py` | Object storage | `DELETE` does not delete in a versioned bucket |
| `sqs.py` | Leased queues | Redelivery is the design, not a bug |
| `dynamodb.py` | Partitioned KV + capacity | A hot key throttles an idle table |
| `lambda_svc.py` | Ephemeral compute | Warm state survives; concurrency is a quota |
| `sns.py` | Fanout + filtering | A missing attribute never matches |
| `kms.py` | Envelope encryption | Rotation re-encrypts keys, never data |
| `vpc.py` | Networking | Security groups are stateful; NACLs are not |
| `capstone.py` | All of it, wired together | Failures surface a layer from their cause |

---

## How to use this directory

```bash
cd aws-from-scratch
python3 check.py            # what to build next
python3 check.py 9          # run only stage 9
forja guide aws-from-scratch 9   # the stage page: mechanism, why, predict
```

**36 graded checks, one behavior each** against your code. Each stage's page
(in `stages/`) states the mechanism, **why the requirement is what it is**, and
a predict prompt to commit to before the check prints. A red `✗` names the
likely cause:

```
  ✗  1. iam.py               explicit deny > allow > implicit deny
      an explicit Deny must beat any Allow, in EITHER order. Policies are
      evaluated as a set — collect all denies first, then allows. If order
      changed your answer, you are iterating and letting the last match win,
      like a firewall.
```

---

## The eight mechanisms

### `iam.py` — the one to do first

Everything else gates on it, and the rule is three lines:

```
1. An explicit DENY anywhere always wins.
2. Otherwise, an explicit ALLOW grants access.
3. Otherwise, DENY (implicit).
```

**Design decision:** partition statements by effect rather than evaluating in order.
That is what makes policy order irrelevant — a property worth proving to yourself, since
it is what makes a large policy set tractable at all.

Also here: conditions (which **AND across keys, OR within one**, and fail closed on a
missing key), `NotAction` (wider than it looks), permissions boundaries (which subtract,
never grant), and STS `AssumeRole` — where **both** the caller's policy and the role's
trust policy must agree.

### `s3.py` — it is flat

`reports/2024/q1.csv` is one opaque key. Folders are invented at list time by splitting
on a delimiter. There is no directory object, which is why an empty folder cannot exist
and renaming one is O(objects).

**The limit case:** in a versioned bucket, `DELETE` pushes a *delete marker*. A plain
`GET` now 404s while the bytes sit underneath, still billed. Only deleting a specific
`version_id` frees anything — which is why "I emptied the bucket" and "the bill went
down" are different claims.

Also: multipart ETags end in `-<part count>` and are **not** the object's MD5.

### `sqs.py` — at-least-once, and why

`receive()` is a **lease**, not a read. Only `delete()` removes a message.

**The limit case you must build:** a consumer whose work outlasts the visibility timeout.

```
t=0   consumer A receives 'expensive-job'
t=11  consumer B receives 'expensive-job'   <- A's lease expired
t=12  A finishes and deletes: False          <- its handle is stale
```

Two consumers processed one message. That is the queue choosing duplication over loss.
Your handler is idempotent or it is wrong — there is no third option.

### `dynamodb.py` — the partition key decides everything

**The limit case:** 40 WCU across 4 partitions is 10 per partition. Write 30 items under
one partition key and it throttles after 10 — with the table 75% idle. *Adding capacity
does not help.* The key has to spread.

Also: `query` reads one partition; `scan` reads everything and filters afterwards, so a
scan returning 3 of a million items costs a million reads.

### `lambda_svc.py` — the container outlives your invocation

Anything outside the handler **survives**: excellent for a connection pool, a disaster
for a cache you assumed was empty.

**The limit case:** reserved concurrency is a ceiling *and* a floor. Reserving 6 of 10
for one function silently drops every other function in the account to 4 — they were
never touched.

And sync vs async failure is the same bug with a different blast radius: sync returns the
error to the caller; async retries **three times**, then dead-letters.

### `sns.py` — push, and the filter that runs at the topic

SNS pushes and drops on failure; SQS buffers. That is why `SNS → SQS → consumer` is the
standard shape rather than an accident.

Filter policies use the same rule as IAM conditions — AND across keys, OR within one, and
a **missing attribute never matches** — and catch people the same way. Plus EventBridge,
which matches the *shape* of a nested event, and fires every matching rule with no
deduplication.

### `kms.py` — envelope encryption

KMS generates a data key, hands it to you twice (plaintext + wrapped), and forgets it. You
encrypt locally. **One KMS call per object, not per byte** — which is why the 4KB payload
limit never constrains you.

**The limit case:** rotation creates a new key *version*; old versions are retained so old
ciphertext still decrypts. Zero bytes of data are re-encrypted. Delete a version and that
ciphertext is unrecoverable forever — which is why key deletion has a mandatory waiting
period.

> The cipher here is XOR and the file says so loudly. **Not encryption.** The envelope
> *structure* is the lesson; substitute AES-GCM and nothing about the shape changes.

### `vpc.py` — stateful vs stateless

The clearest demonstration in the directory. Identical intent, opposite outcome:

```
Security group:
  SG inbound    203.0.113.5 -> :443  allow
  SG reply      implicitly allowed (stateful)
  connection: WORKS

Network ACL, same rules:
  NACL inbound  203.0.113.5:* -> :443  allow (rule 100)
  NACL outbound reply -> 203.0.113.5:49152  DENY (no rule matched)
  connection: FAILS
```

The request was allowed both times. The NACL dropped the **reply**, which goes to an
ephemeral port nobody remembers to allow. This is why `test_connection` models a whole
connection rather than a rule — evaluate only the request and the bug is invisible.

Also: a `/28` gives **11** usable hosts, not 16 (AWS reserves 5), and route tables match
the longest prefix, not the first entry.

### `capstone.py` — the failures compose too

`S3 → SNS → SQS → Lambda → DynamoDB`, KMS on the payload, IAM on every call.

The result worth sitting with:

```
=== A failure surfaces one layer away from its cause ===
  12 uploads -> queue depth 12
  drain: {'processed': 5, 'throttled': 0, 'failed': 5}
```

Five Lambda invocations errored. The **cause** is DynamoDB — every document shares
`tenant='acme'`, so they hash to one partition holding a quarter of the table's capacity.
The alarm fires on Lambda; the fix is in the data model. That mismatch between where a
failure is *visible* and where it is *caused* is most of what makes distributed debugging
hard.

---

## The rest of AWS, and what it is made of

Rather than 200 shallow files, here is the honest map. Most services are a mechanism you
have already built, with different packaging:

| Service | Is essentially | Built in |
|---|---|---|
| Kinesis, MSK | A queue with ordered shards and replay | `sqs.py` + partitioning |
| ECS, Fargate, App Runner | Lambda with longer-lived containers | `lambda_svc.py` |
| Step Functions | A state machine over Lambda invocations | `lambda_svc.py` |
| RDS, Aurora | A database; the AWS part is failover and backups | — |
| ElastiCache | A cache; see [`system-design/`](../system-design/) | — |
| EFS, FSx | A filesystem, so *not* S3's flat model | `s3.py` (by contrast) |
| CloudFront | A CDN; edge caching and invalidation | [`context-caching/`](../context-caching/) |
| ELB, API Gateway | Routing + throttling + health checks | `vpc.py`, `lambda_svc.py` |
| Route 53 | DNS with health-checked routing policies | [`dns-server/`](../dns-server/) |
| Secrets Manager, Parameter Store | KMS plus versioning and rotation | `kms.py` |
| Cognito | STS with a user directory in front | `iam.py` |
| CloudTrail | The audit log the capstone writes | `capstone.py` |
| CloudWatch, X-Ray | Metrics, alarms, budgets, tracing | [`deploy-and-debug/`](../deploy-and-debug/) |
| Organizations, SCPs | IAM evaluation with another deny layer | `iam.py` |
| CloudFormation, CDK | A dependency graph with rollback | — |
| Glue, Athena, EMR | Query planning over object storage | `s3.py` |
| SageMaker, Bedrock | Model serving | [`context-caching/`](../context-caching/) |

Two of those rows — **CloudFormation's dependency graph with rollback**, and **Kinesis's
ordered shards with replay** — have genuinely distinct mechanisms and are the best
candidates for a ninth and tenth file. The extensions list below starts there.

## What this is not

- **Not a mock for testing against.** Use [LocalStack](https://localstack.cloud) or
  [moto](https://github.com/getmoto/moto) for that; they aim for API fidelity, this aims
  for understanding.
- **Not API-compatible.** No boto3 surface, no XML, no signatures, no regions, no
  eventual-consistency delays on the control plane.
- **Not secure.** `kms.py` uses XOR. Nothing here is real cryptography.
- **No pricing model**, though several files count the units you would be billed for.

## Extensions worth trying

1. **CloudFormation** — a dependency graph, topological ordering, and rollback on failure.
   The interesting part is what happens when rollback *itself* fails.
2. **Kinesis** — ordered shards with a retention window and replay from a sequence number.
   Contrast with `sqs.py`: replay changes the consumer contract completely.
3. **Add IAM to every other file.** Right now only the capstone authorises. Wiring
   `evaluate()` into `s3.put_object` and friends is what a real service does.
4. **S3 lifecycle rules** — transition to a colder class after N days, expire versions,
   abort incomplete uploads. Then compute the bill before and after.
5. **DynamoDB on-demand vs provisioned.** Model burst credits and compare cost curves for
   a spiky workload.
6. **Cross-account access.** A bucket policy on one side, an identity policy on the other,
   and a role in between — then work out which of the three is actually granting it.

---

## The 36 stages, one behavior each

| # | file | the one thing |
|---|---|---|
| 1 | `iam.py` | explicit deny > allow > implicit deny |
| 2 | `iam.py` | conditions: AND keys, OR values, fail closed |
| 3 | `iam.py` | permissions boundaries subtract, never grant |
| 4 | `iam.py` | assume-role: caller policy AND role trust |
| 5 | `s3.py` | put/get, ETag = MD5, NoSuchKey |
| 6 | `s3.py` | multipart ETags end in `-<part count>` |
| 7 | `s3.py` | delimiter invents folders at list time |
| 8 | `s3.py` | delete marker hides versions, frees nothing |
| 9 | `sqs.py` | receive is a lease; expiry redelivers |
| 10 | `sqs.py` | stale receipt handles fail to delete |
| 11 | `sqs.py` | change_visibility extends the lease |
| 12 | `sqs.py` | poison messages dead-letter after max_receives |
| 13 | `sqs.py` | oldest_age counts in-flight too |
| 14 | `sqs.py` | FIFO: one in-flight message per group |
| 15 | `sqs.py` | FIFO dedup window |
| 16 | `dynamodb.py` | composite key = partition + sort |
| 17 | `dynamodb.py` | query reads one partition |
| 18 | `dynamodb.py` | conditional writes fail atomically |
| 19 | `dynamodb.py` | consistent reads cost 2x |
| 20 | `dynamodb.py` | capacity divides across partitions; hot key throttles |
| 21 | `dynamodb.py` | scan reads everything, then filters |
| 22 | `lambda_svc.py` | cold start once; warm state survives |
| 23 | `lambda_svc.py` | env TTL resets state; timeout bills full |
| 24 | `lambda_svc.py` | concurrency quota; reservation steals a floor |
| 25 | `lambda_svc.py` | async retries to 3 attempts, then DLQ |
| 26 | `sns.py` | one publish fans out to every subscriber |
| 27 | `sns.py` | filters: AND keys, OR values, missing never matches |
| 28 | `sns.py` | EventBridge: nested shape, fires every rule |
| 29 | `kms.py` | envelope: data key encrypts, CMK wraps the key |
| 30 | `kms.py` | one KMS call per object, not per byte |
| 31 | `kms.py` | encryption context must match on decrypt |
| 32 | `kms.py` | rotation re-encrypts keys, never data |
| 33 | `vpc.py` | CIDR containment, overlap, 5 reserved IPs |
| 34 | `vpc.py` | routes pick the longest matching prefix |
| 35 | `vpc.py` | SG stateful vs NACL stateless, same rules |
| 36 | `capstone.py` | the pipeline, and failures surfacing a layer away |

---

## Structure

```
aws-from-scratch/
├── README.md
├── AUDIT.md             # audit record: why the course is 36 single-behavior stages
├── START.md             # onboarding — the first green
├── check.py             # progress checker — run this first
├── stages/              # 36 stage pages: mechanism, why, predict
├── iam.py               # templates with TODOs and DESIGN DECISION blocks
├── s3.py
├── sqs.py
├── dynamodb.py
├── lambda_svc.py
├── sns.py
├── kms.py
├── vpc.py
├── capstone.py
└── solutions/
```

```bash
cd solutions
python3 iam.py            # stages 1-4: deny-wins, conditions, boundaries, assume-role
python3 s3.py             # stages 5-8: ETags, multipart, listing, delete markers
python3 sqs.py            # stages 9-15: leases, DLQ, age, FIFO groups, dedup
python3 dynamodb.py       # stages 16-21: keys, conditions, capacity, hot keys, scans
python3 lambda_svc.py     # stages 22-25: cold starts, TTL, quotas, async retries
python3 sns.py            # stages 26-28: fanout, filters, EventBridge
python3 kms.py            # stages 29-32: envelope, context, rotation
python3 vpc.py            # stages 33-35: CIDR, routing, SG vs NACL
python3 capstone.py       # stage 36: the pipeline and its failures
```

Pure Python 3 standard library. Everything runs in about a second.

## Related directories

- [`dynamo-paper/`](../dynamo-paper/) — the 2007 paper DynamoDB is built on
- [`deploy-and-debug/`](../deploy-and-debug/) — operating and debugging this kind of system
- [`system-design/`](../system-design/) — the patterns underneath most of these services
- [`PHILOSOPHY.md`](../PHILOSOPHY.md) — why this repo is built the way it is
- [`EXTERNAL-RESOURCES.md`](../EXTERNAL-RESOURCES.md) — roadmap.sh/devops (the
  map of the operations territory this course builds the cloud leg of)
