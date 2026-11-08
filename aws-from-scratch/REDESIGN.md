# AWS From Scratch: a smaller ask at every step

## The teaching contract

This is the design behind the executable 63-stage ladder in `lessons.json` and
`stage_checks.py`. A stage passes only when a learner can add one
observable behavior to the existing toy service. Earlier behavior is supplied by
previous stages. A check may use earlier behavior as setup, but its failure message
and new assertions must concern only the new behavior.

Each guide should fit on one screen before the optional reference link:

1. **One sentence of context:** the situation in which the behavior matters.
2. **One concrete task:** name the function or method to edit and one input/output example.
3. **One prediction:** ask for the result of that exact example before running it.
4. **One acceptance check:** include one positive case and, when useful, its closest edge case.
5. **One short debrief:** connect the observed behavior to the real AWS service.

Do not ask for an entire API, a refactor, production infrastructure, or an AWS
account. Keep the Python standard library and the existing toy interfaces. Put
real AWS caveats after the check, where they refine understanding without making
the coding task larger. Capstones reuse completed parts; they introduce only one
new connection or diagnostic question at a time.

## Proposed ladder (63 stages)

The *change* column is the only new implementation ask. The *observe* column is
the one result that should turn the stage green. The checker and guides use
these stage IDs.

| # | Change | Observe |
|---|---|---|
| **IAM** |||
| 1 | Return implicit deny when no statement matches. | An empty policy denies `GetObject`. |
| 2 | Match an action and a resource before applying a statement. | `s3:Get*` on bucket A does not grant `PutObject` or bucket B. |
| 3 | Give a matching explicit Deny precedence over Allow. | Swapping statement order does not change Deny. |
| 4 | Reject a condition when its context key is missing. | A request without `aws:SourceIp` fails an IP condition. |
| 5 | Combine condition keys with AND and alternatives for one key with OR. | `prod` matches one of two allowed values only when the other key matches. |
| 6 | Intersect identity permissions with a permissions boundary. | A boundary alone grants nothing. |
| 7 | Check a role's trust policy when assuming it. | A caller with `sts:AssumeRole` still fails if trust rejects them. |
| 8 | Give an assumed session the role's permissions. | The session can use the role grant, not an unrelated caller grant. |
| **S3** |||
| 9 | Store and retrieve one object by its full key. | `a/b.txt` round trips without creating directories. |
| 10 | Raise `NoSuchKey` for an absent object. | Missing and present-empty are distinguishable. |
| 11 | Compute the toy's single-part MD5 ETag. | `hello` has the expected digest. |
| 12 | Compute a multipart ETag from part digests. | Two parts produce a `-2` suffix and differ from full-body MD5. |
| 13 | List object keys as a flat sequence. | `a/1` and `a/2` are two keys. |
| 14 | Collapse shared prefixes when a delimiter is requested. | `a/1`, `a/2` yield `a/` as a common prefix. |
| 15 | Retain prior values after writes to a versioned key. | An old version ID still retrieves old bytes. |
| 16 | Append a delete marker for a plain delete in a versioned bucket. | Plain GET fails while versioned GET still works. |
| 17 | Delete one specified version. | Only that version's bytes disappear. |
| **SQS** |||
| 18 | Hide a received message for its visibility interval. | A second receive during the interval returns nothing. |
| 19 | Make an undeleted message visible after the interval. | The same message can be received again. |
| 20 | Give each receive a new receipt handle. | Two receives of one message have distinct handles. |
| 21 | Delete the message with its current handle. | It no longer appears after the lease expires. |
| 22 | Change visibility relative to the call time. | Extending at `t=5` keeps the message hidden past its original deadline. |
| 23 | Move a repeatedly received message to a dead-letter queue. | The next receive after the configured limit does not return it. |
| 24 | Block another in-flight message from the same FIFO group. | Only one of two `A` messages is handed out. |
| 25 | Let a different FIFO group progress. | A `B` message is handed out while `A` is in flight. |
| 26 | Suppress a duplicate deduplication ID inside the toy window. | Same ID at `t=10` is dropped; at `t=400` is accepted. |
| **DynamoDB** |||
| 27 | Use both partition and sort values as a composite key. | `alice/001` and `bob/001` coexist. |
| 28 | Query only a named partition key. | Querying `alice` returns no `bob` rows. |
| 29 | Make a conditional put atomic. | A failed create leaves the old value unchanged. |
| 30 | Charge the toy's strong read twice its eventual read. | The read counter moves by 1 versus 0.5. |
| 31 | Apply the toy's write budget per partition. | A partition with budget 10 rejects its 11th write. |
| 32 | Spread distinct partition keys with a stable hash. | Twenty distinct keys fit across four partitions. |
| 33 | Apply a scan filter after reading items. | Returning one row still increments the scanned count for all rows. |
| **Lambda** |||
| 34 | Initialize an execution environment on first use. | The first invocation pays init cost. |
| 35 | Reuse an environment between invocations. | A counter outside the handler persists. |
| 36 | Replace an expired toy environment. | The counter restarts after the configured toy TTL. |
| 37 | Report and bill an invocation timeout. | Work exceeding the limit produces a timeout and positive billed duration. |
| 38 | Enforce the account concurrency ceiling. | 15 simultaneous calls at a limit of 10 yield 5 throttles. |
| 39 | Subtract reserved concurrency from the unreserved pool. | Reserving 6 of 10 leaves 4 for other functions. |
| 40 | Return synchronous handler failure to its caller. | One failed call returns an error without automatic retry. |
| 41 | Retry a failed asynchronous handler in the toy's three-attempt policy. | One event makes three attempts. |
| 42 | Send an exhausted asynchronous event to the dead-letter queue. | The original event appears once in the queue. |
| **SNS / EventBridge** |||
| 43 | Fan one publish out to all subscriptions. | Two queues each receive one copy. |
| 44 | Match any allowed value for one SNS filter key. | `staging` matches `[prod, staging]`. |
| 45 | Require every ordinary SNS filter key. | Missing `environment` rejects a subscription requiring it. |
| 46 | Match a nested EventBridge pattern. | `detail.state=terminated` matches only that nested value. |
| 47 | Fire every matching EventBridge rule. | One event matching two rules invokes both. |
| **KMS** |||
| 48 | Return plaintext and wrapped copies of one data key. | Unwrapping recovers the original data key. |
| 49 | Encrypt an object locally with its data key. | Stored ciphertext and wrapped key round trip. |
| 50 | Bind the wrapped key to an encryption context. | A different tenant context cannot unwrap it. |
| 51 | Keep old key material usable after rotation. | Ciphertext from before rotation still decrypts. |
| **VPC** |||
| 52 | Decide whether one CIDR contains another. | `10.0.0.0/16` contains `10.0.1.0/24`, not `10.1.0.0/24`. |
| 53 | Reject an overlapping subnet. | A subnet inside an existing subnet cannot be added. |
| 54 | Subtract AWS's five reserved subnet addresses. | A `/28` has 11 usable addresses. |
| 55 | Select the longest matching route prefix. | A `/24` beats a `/16` and default route. |
| 56 | Permit reply traffic for an allowed security-group connection. | No explicit outbound reply rule is needed. |
| 57 | Evaluate a NACL reply separately. | The same connection fails without an ephemeral-port outbound rule. |
| 58 | Evaluate NACL rules in number order. | Deny 100 shadows allow 200. |
| **Integration** |||
| 59 | Publish one event after storing an upload. | The topic's published count rises by one. |
| 60 | Subscribe the work queue to the topic. | One event appears in the queue before a worker runs. |
| 61 | Connect SQS processing through Lambda to DynamoDB. | One queue item becomes one row. |
| 62 | Authorize before the upload's first side effect. | Denied upload leaves no object or message. |
| 63 | Name a hot-key failure using observations from two layers. | `failure_origin` returns `dynamodb` when the worker fails and a partition throttles. |

The ladder keeps specialized topics as separate stages. A typical stage should
take about 5–15 minutes; stages that consistently take longer should be split
again. A future branch mechanism could make multipart ETags, FIFO deduplication,
and EventBridge optional without bundling them into other stages.

## What the current implementation must change

The former `CHECKS` table exposed 36 entries but pointed them at only 24 check
functions. For example, stages 2 and 3 both ran the condition *and* boundary
check; stages 5 and 6 both ran put/get *and* multipart ETag. The curriculum
metadata also shifted after DynamoDB. The new checker has one function per
stage and the guides are generated from `lessons.json`.

## AWS fidelity notes for the guides

- The toy's ETag is MD5 for its single-part path. Real S3 ETags are **not
  generally** object MD5s, particularly for multipart uploads and some
  encryption modes. [S3 integrity guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html).
- An old SQS receipt handle should not be taught as a guaranteed API error:
  AWS says `DeleteMessage` can succeed without deleting the message. The toy
  may return `False` to make the lease state observable, but label that as a
  modeling choice. [DeleteMessage API](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/API_DeleteMessage.html).
- Remove the current `oldest_age counts in-flight` lesson from the core. The
  real `ApproximateAgeOfOldestMessage` metric excludes repeatedly received
  poison pills in standard queues. If the toy retains its own age method,
  call it an internal diagnostic, not the CloudWatch metric.
  [SQS metric definition](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-available-cloudwatch-metrics.html).
- The fixed 40-WCU/four-partition example is a useful *toy* demonstration,
  not a universal DynamoDB limit. Real DynamoDB has adaptive capacity and
  partition splitting. [Adaptive capacity](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/burst-adaptive-capacity.html).
- The toy Lambda TTL is deterministic for testing. Real execution
  environments have no guaranteed lifetime. The three-attempt rule applies
  to handler errors in default async invocation; throttling and service errors
  have different retry behavior. [Lambda reuse](https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html),
  [async retries](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html).
- Ordinary SNS filter keys are required, but `exists:false` is an intentional
  absence matcher and has an empty-attributes edge case. Give it an optional
  exercise if desired. [SNS key matching](https://docs.aws.amazon.com/sns/latest/dg/attribute-key-matching.html).
- KMS rotation retains old key material for decryption; it does not rewrite
  application ciphertext. The toy's XOR remains explicitly nonsecure.
  [KMS rotation](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html).

## Reference pattern

[CodeCrafters' stage model](https://app.codecrafters.io/concepts/overview)
uses short, sequential, testable stages; its [Redis track](https://app.codecrafters.io/tracks/elixir)
shows fine-grained steps such as binding a port, responding to one PING, then
responding to multiple PINGs. [AWS's EC2 tutorial sequence](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-launch-tutorials.html)
likewise starts with one default-settings launch before adding configuration.
The AWS references above define the actual service behavior. This course
should adopt that small-step progression while keeping the local toy simple.
