# Compliance — the layer the 36 stages do not teach

The course teaches **mechanisms**: how IAM evaluates, what a delete marker does, why
rotation re-encrypts keys and never data. A regulated bank does not buy mechanisms. It
buys **guarantees about who can read its data, in which country, and how that is proven
to a stranger six months later.**

This file is the bridge. It assumes you can pass stages 1–4 (`iam.py`), 8 (`s3.py`) and
29–32 (`kms.py`) — because if you cannot, the compliance answers below have nothing to
attach to. Every fact here is checked against AWS docs, GDPR/DORA text or a regulator
page as of 2026-11; anything that is a judgement, not a citation, is marked **`(call)`.**

Six scenarios, each from a real buyer question. Read the primitives first (§0), then the
scenario that hurt.

---

## 0. The primitives, from zero

If §0 is already obvious, skip it — it is the vocabulary the scenarios are written in.

### 0.1 What a CMK actually protects

A KMS key (CMK / "customer managed key") **never protects bytes directly.** It wraps
*data keys*, and data keys protect bytes. This is envelope encryption, and stage 29 is
the whole idea. The consequence nobody tells you on day one:

> **Deleting a CMK does not delete data. It deletes your ability to read the data.**

Those are different facts, and regulations, auditors and banks treat them differently.
Everything hard in this file follows from that one sentence.

### 0.2 The three KMS key-custody models

| Model | Who holds the root key material | Can the client cut you off unilaterally? | Can *you* still read data after they cut you off? |
|---|---|---|---|
| **AWS-managed / AWS-owned key** (`aws/s3`, SSE-S3) | AWS | No | Yes (you can too, but so can every other tenant) |
| **Customer-managed CMK in KMS** | KMS HSMs, but the *client's account* owns the key policy | Yes — they change a key policy | Yes until they disable/delete it |
| **BYOK (imported key material)** | Client generates it in their own HSM, imports a copy into KMS | Yes — they can expire/delete the material | Yes — AWS holds a copy until it is deleted |
| **XKS / HYOK (external key store)** | Client's own key manager; **AWS never holds it** | Yes, in the strongest sense | **No.** Every decrypt calls their box |

- **BYOK**: you remain responsible for the material while letting AWS *use a copy*. You
  can set an expiry. KMS will not decrypt its own KMS ciphertext anywhere else — the
  format is unpublished. The trust is "AWS only holds a copy I generated, and I can pull
  it."
- **XKS**: AWS talks only to a proxy *you* run (`XksProxy`); it cannot create, view,
  manage or delete the keys. If the external key is disabled or deleted, the KMS key
  *stays `Enabled`* and every cryptographic operation simply fails. That is the strongest
  possible answer to "we must be able to revoke your access at any moment" — and its cost
  is that you, the vendor, are one network partition from your client's data centre away
  from being unable to serve their data.

### 0.3 Crypto-shredding, in one paragraph

Encrypt a thing under a key whose *only* purpose is that thing. Now destroy the key, all
copies. The ciphertext is still on the disk and still billed — but it is **unrecoverable**.
If the key cannot be recovered by anyone (including you), then for practical purposes the
information is gone. **GDPR Recital 66** says the controller may use technical measures to
"ensure that the personal data are no longer processed," and **EDPB Guidelines 02/2025**
(on blockchain) confirm that rendering data cryptographically unrecoverable can satisfy
the Art. 17 duty. That is the authority the phrase "crypto-shredding is valid" rests on.

The word carrying all the weight is **irreversibly**, and the word carrying all the cost is
**all copies**. Crypto-shredding works if and only if:

1. **Key granularity = data-subject granularity.** One key per subject, or per the unit
   being deleted. A shared key means shredding one deletes everyone.
2. **Nothing crossed the crypto boundary.** Any plaintext-derived artifact — a vector, a
   model weight, a cache, a third-party log line — is *outside* the encryption and a key
   does not reach it.

Both conditions are where the scenario questions break. §2 walks through it.

### 0.4 What a right-to-erasure request demands

GDPR **Art. 17**: the controller must erase personal data "without undue delay" when a
ground applies. Three things people get wrong:

- It is the **controller's** duty. A vendor is a **processor** (Art. 28) and must help the
  controller achieve it; the contract (DPA) says *how far*.
- Art. 17(3) has **exceptions** — legal obligation (bank AML retention), legal claims,
  public interest. A bank can be **required by 4AMLD/5AMLD to retain** records for years
  while also owing a customer an erasure right. The conflict is real and resolved by the
  lawyer, not by you. Your job is to make the mechanism *expressible*: "delete everything
  except the ones under a legal hold."
- Erasure must reach **derived copies** the moment they are personal data. An embedding
  that re-identifies is personal data. A deletion of the source PDF that leaves the vector
  is not a deletion.

---

## 1. "We must be able to revoke your access to our documents at any time."

The client is a bank. They are asking you to choose where the **root of trust** lives,
knowing what each choice costs and what each choice *proves*.

### What actually changes between the options

**SSE-S3** (AWS-owned keys). Free, on by default, base-level encryption for every object
since 2023. You have no key policy, no visibility in your CloudTrail, no rotation control,
no way to cut anyone off. It is the right answer for logs you do not care about and the
wrong answer here. Choosing SSE-S3 for bank documents is a finding waiting to be written.

**SSE-KMS with an AWS-managed key** (`aws/s3`). You can *see* it and audit its use in
CloudTrail, but you **cannot change its key policy, cannot rotate it on your schedule,
cannot use it in your own crypto calls, cannot revoke with it.** The service owns it. This
is convenience, not control. **The client's question is a control question, so this is not
the answer — even though the client may say "KMS".**

**SSE-KMS with a customer-managed CMK.** Now there is a key policy the *bank's account*
owns, an alias they can point at, rotation they schedule, and `kms:DisableKey` /
`ScheduleKeyDeletion` (a 7–30 day waiting period) they can wield to cut you off
unilaterally. The access-control question becomes answerable: "here is who can decrypt,
and they can remove us with one API call." The caveat: AWS still holds the key material
inside its HSMs, and after `ScheduleKeyDeletion` you have a **window** (the waiting period)
where it is still recoverable by cancelling.

**BYOK / imported key material.** The bank generates the key in its own HSM and imports a
copy. The trust claim upgrades from "AWS holds it" to "AWS holds a copy of material *I*
made from *my* entropy, and I can expire it." This satisfies procurement language about
provenance and lets them set an expiry. It still puts a copy in KMS.

**XKS.** AWS never holds the material. Revocation is "we switch the key off on our side"
and your decryption stops working in real time — no waiting-period window, no copy in AWS.
This is the literal answer to the demand.

### The tradeoff the client is not asking about but will care about

The further you go down that list, the more **you** are at the mercy of the bank's key
store: latency on every decrypt, availability of their data centre, and an inability to
serve their own data during *their* outage — which, under **DORA**, is a third-party ICT
provider arrangement where *they* will ask *you* about your resilience.

**`(call)`** For a bank that wrote "revoke at any time" into a contract: **customer-managed
CMK per tenant, owned by their account, with the key policy explicitly naming your role as
a revoke-able principal** is the boring, correct default. Escalate to **BYOK** when their
audit wants provenance, to **XKS** only when they truly will not tolerate a copy in AWS and
will sign the latency. The wrong answer to the literal question is SSE-S3 or an AWS-managed
key: those cannot be revoked by the client at all.

This is stage 32's fact — a key is a *policy object* more than a math object — wearing a
lawyer's clothes.

---

## 2. Art. 17: the data is in versioned S3, backups, embeddings, and LLM logs.

This is the question that separates people who know *that* crypto-shredding works from
people who know *where* it stops. The answer is: **valid in principle, and it breaks in
three of the four locations.** Take them one by one.

### The prerequisite

Shredding only deletes *this data subject* if the data was encrypted **per subject (or per
document) under a key nothing else uses.** If you encrypted the whole tenant under one CMK,
shredding for one person destroys the tenant — so the question "is crypto-shredding valid"
is really "did you build the key hierarchy in §1 granularly enough to allow per-subject
keys." For most shops the answer is no, because nobody designed a key hierarchy for
deletion. **`§3` is about exactly this tension.**

### In S3 with versioning

- A plain `DELETE` pushes a **delete marker** — stage 8. The version is still there, still
  billed, and `GET VersionId` succeeds. So a DELETE that "looks deleted" to the UI is not a
  deletion for Art. 17 at all. Real deletion needs the version IDs listed and removed, and
  every delete marker too.
- **Crypto-shredding here is actually the elegant version**: instead of hunting every
  version of every object, you destroy the **data key** (or the CMK, if the CMK's only job
  is this subject) and every version becomes ciphertext-noise simultaneously. This reaches
  *all* versions and non-current versions you forgot to enumerate.
- **Where it breaks**: if the data keys were wrapped under a CMK shared with other subjects
  (the common case), shredding the CMK is a self-inflicted breach; and you must have logged
  *which* CMK/data-key protected this subject's objects, or you cannot find the key to kill.
  If `kms.py` stage 31's encryption context is `{tenant, user}`, you can look the key up. If
  you used no context, you are blind. **The encryption context is your erasure index.**

### In backups

- Backups are usually a **monolith encrypted under one key** (AWS Backup vault, a snapshot,
  a `tar.gz` in Glacier). Shredding it deletes every subject in that backup, not one.
- **Where it breaks**: you cannot granularly shred what you did not granularly encrypt. The
  fix is backup-time key design: per-subject (or per-tenant + periodic rotation) so a
  backup is decomposable. If you do not, you fall back to *restoring, deleting the subject,
  re-backing-up* — O(backup size), and the old backup may already be past its retention.
- **The collision nobody warns about**: if a backup has **S3 Object Lock in COMPLIANCE
  mode** (WORM, evaluated for SEC 17a-4/CFTC/FINRA), it **cannot be deleted before the
  retain-until date, and a legal hold has no expiry.** Object Lock exists to defeat
  deletion. Art. 17 *is* deletion. You cannot crypto-shred a WORM object's key either,
  because the regulatory duty is to keep it. The honest resolution is legal, not
  technical: the AML retention is an Art. 17(3) exception, and the data is *retained but
  restricted*, not erased. Saying this confidently is better than pretending a tool solves
  it.

### In embeddings in a vector DB

This is the one people actually flunk.

- An embedding is **plaintext-derived and one-way.** It lives *outside* the encryption of
  the source document. **Shredding the PDF's key does not touch the vector at all** — the
  vector was never encrypted under it.
- Worse: even *deleting* the vector may not erase the *information*, because the index has
  **absorbed it into shared structure** — HNSW graph edges, IVF centroids, PQ codebooks,
  BM25/postings dictionaries, or worse a fine-tuned model. A neighbor link to a deleted node
  and a centroid that is the average of 2048 documents including this one both *retain
  trace information about it*. Whether that is "personal data of this subject" after
  deletion is a genuine judgement call; regulators' practical answer is that **the
  re-identifiable surface must be destroyed, and re-training/rebuilding may be the only way
  to get there.**
- **Where it breaks / what you say**: crypto-shredding is valid only if **each
  document's vectors are encrypted under a key bound to that document**, *and* you never
  let plaintext-derived *statistics* into shared structures. The standard architecture
  (one index, shared ANN graph, a global DB key) defeats this. The implementable pattern:
  store vectors encrypted per-document (your own data-key envelope, not just the DB's at-rest
  key), keep the index over *metadata/tokens*, not raw vectors, so you can delete the entry
  and shred the key. If you trained anything (embeddings fine-tuned, a reranker, a
  cache), you must address that copy explicitly or you have not erased — you have erased
  the row and kept the fingerprint.
- **A concrete sub-case**: if the embedding model was a *third-party* API and the provider
  can re-embed from a retained input, deleting your vector and deleting *their* input are two
  different obligations under two different controllers (see next).

### In the LLM provider's logs

- These are **someone else's encryption** (or plaintext), on someone else's system, under
  someone else's retention default (e.g. 30 days) unless you contracted otherwise.
  **Your key destroys nothing here** — crypto-shredding is meaningless because the boundary
  does not include their logs.
- What actually discharges it: a **zero-data-retention (no-training, no-log) agreement**, or
  the provider's **deletion API**, or you never sending PII (redaction/tokenization — the
  `ENTERPRISE.md` row 3 proxy). The erasure path is **contractual + API**, not cryptographic.
- **The auditor angle**: they will not accept the sentence "OpenAI deletes after 30 days."
  They will want the signed DPA clause, the subprocessor list (anyformat's own trust page
  lists AWS, Azure, Datadog, GCP), and a test that your deletion *fan-out* was actually
  invoked and returned success.

### The answer, stated as an interview sentence

> Crypto-shredding is a valid **technical implementation** of erasure — Recital 66 and the
> EDPB Guidelines 02/2025 allow it — but it is valid **only where the crypto boundary
> meets the data-subject boundary**, and it must be **granular per subject**. In versioned S3 it is the
> best tool *if* key hierarchy and encryption context were built per subject. In backups it
> fails unless the backup itself is decomposable, and Object Lock makes it *forbidden*, not
> just hard. In embeddings it fails completely unless vectors are per-subject encrypted,
> because the vector is a plaintext-derived artifact living outside the document's key, and
> shared index structures may keep trace information after deletion. In the LLM provider's
> logs it fails by definition, because their data is under their key; that path is closed by
> contract and a deletion API, not cryptography. So: crypto-shredding is the *core* answer
> but not *the* answer — the real answer is a **disposition map** that says, per location,
> how it is keyed, what a key-destruction reaches, and what needs a non-cryptographic path.

That last noun — **a disposition map** — is the artifact. If the client asks "prove you can
do this," the deliverable is that map plus the per-subject key design. Draw it before you
build it.

---

## 3. A KMS key per tenant, or one global key?

The naive axes are cost and quotas; the real axis is **blast radius vs. deletion
granularity**, and the quota is the price you pay for the granularity you want.

### The isolation logic

| | one global CMK | CMK per tenant | CMK per data-subject |
|---|---|---|---|
| Key-compromise blast radius | everything | one tenant | one human |
| §1's revocation ("cut vendor off for *this* client") | impossible without nuking everyone | **exact** | overkill |
| §2's crypto-shred of one subject | impossible | coarse (whole tenant) | **exact** |
| Auditable key policy per tenant | no | yes | yes |
| Key count | 1 | ~tenants | ~users (millions) |

Per-subject keys are the erasure ideal and a management nightmare; **per-tenant is the
practical default** and per-subject for the *specific fields* an erasure actually targets.

### The cost — why this is a real question and not a style preference

KMS bills for **requests**, not keys alone: a CMK has a monthly fee (pro-rated hourly) and
each API request is charged (per 10,000; an example: 2.01M requests ≈ $5.97 after the
free tier of **20,000 requests/month across all regions**; symmetric requests only, free
tier excludes asymmetric). So a per-tenant key multiplied across tenants, regions and
every object access is a line that can dominate a cloud bill.

That is precisely what **S3 Bucket Keys** exist to stop.

### What S3 Bucket Keys actually do (the mechanism, since stage 29 is the keyhole)

Without a bucket key: **SSE-KMS uses one KMS data key per object and S3 makes a KMS call
every time a request touches a KMS-encrypted object.** Millions-to-billions of objects →
a KMS request storm. That storm collides with the **symmetric crypto shared quota**
(default **10,000 rps** shared; **20,000** in us-east-2, ap-southeast-1, ap-southeast-2,
ap-northeast-1, eu-central-1, eu-west-2, eu-south-2; **100,000** in us-east-1, us-west-2,
eu-west-1 — adjustable, but *you* have to know it's coming).

With a bucket key: AWS mints a **short-lived bucket-level key** from KMS, holds it in S3
for a window, and uses it to make data keys for new objects during that window. AWS says it
can cut **KMS request cost by up to 99%** because the traffic collapses from per-object to
per-bucket-level-key-refresh.

Two non-obvious consequences a bank auditor will probe:

- **Requester granularity and CloudTrail**: a unique bucket-level key is fetched **at least
  once per requester** so each requester's access is captured as a KMS CloudTrail event.
  The cost optimization is bounded on the *left* by the audit requirement — you cannot
  collapse everything into one cached key, because then the trail could not attribute the
  access. (This is exactly §4's "who decrypted" question.)
- **Granularity is coarsened — and it interacts with §2.** A bucket key is bucket-level and
  short-lived. Everything encrypted under it during a window shares a protection surface.
  If you need per-tenant *shreddability*, put the bucket on the tenant, and know that
  bucket keys are **not supported for DSSE-KMS** (dual-layer SSE-KMS) — so the architecture
  that wants DSSE for an extra layer loses the cost lever.

### The answer, stated

> **One CMK per tenant, S3 Bucket Key on, per-subject data keys where the data subject has
> an erasure right.** Bucket keys are the *cost and quota* lever that makes per-tenant (or
> even per-object) SSE-KMS affordable at scale by collapsing per-object KMS calls into a
> short-lived per-bucket key — but they coarsen granularity and the "at least once per
> requester" fetch is the audit floor that keeps decrypts attributable. The real constraint
> is not the $5.97: it is that a global key makes §1 (revoke per client) and §2 (shred per
> subject) impossible, so the per-tenant split is bought for isolation and paid for in
> requests — and bucket keys move the money back to where the isolation is free.

### 3.1 The IAM bridge, without looking (stage 1–4 applied)

The demand to "revoke access to our documents" *is* an IAM question, and your engine answers
it. Say it out loud:

- A request is decided **explicit Deny > explicit Allow > implicit Deny**, and because
  statements are evaluated as a **set**, appending a guard statement can never change an
  existing unrelated grant — that is what makes the bank's "revoke" a *safe* operation: you
  add a `Deny` for your vendor principal; order is irrelevant; nothing else moves.
- **A key policy and an IAM policy must both allow.** For KMS, the **key policy is required
  first**: no principal — not even root or the creator — can touch a CMK unless the key
  policy explicitly allows. So "who can `kms:Decrypt`" is *not* an IAM-policy question alone;
  it is the **intersection** of the key policy and the identity policy. Your `evaluate()`
  runs over one policy set; real KMS runs it over **two** and ANDs them — exactly the shape
  of `evaluate_with_boundary`: *the boundary subtracts, never grants.*
- **Conditions** (stage 2) are how you scope a key to a tenant without a key per tenant:
  `kms:EncryptionContext:tenant = ${aws:PrincipalTag/tenant}`. Missing condition key → fail
  closed → deny. That is how one CMK serves many tenants safely, and it is *the same*
  `evaluate_condition` you wrote.
- **STS assume-role** (stage 4): the bank's access to your account, or yours to theirs, is
  *both* the caller's policy *and* the role's trust policy agreeing. A revoked role trust is
  the cheapest "cut you off" button there is.

The sentence a reviewer wants: *"The key policy is a required resource policy that must
grant, and the IAM policy is a required identity policy that must grant, and the answer is
the intersection — which is `evaluate_with_boundary`'s AND-of-two-evaluations, not a
`evaluate` of one set."*

### 3.2 A cross-account key policy that actually means "I can revoke you"

If the bank keeps the CMK in *their* account and you read/write objects with it, both sides
must allow. A key-policy statement that names your role lets you use the key; a trust
relationship is no longer in your hands when *they* own it. So the revocation story is the
key policy: they can delete your `Principal` from it at will, no notice, no negotiation, and
no ticket.

### The trap answers

1. **"One global key, it's cheaper."** Cheaper until you must revoke for *one* client or
   erase *one* subject; then it is not a key, it is a hostage.
2. **"Bucket key always."** Bucket key coarsens the granularity §2 wants. Use it; know what
   it costs in shreddability; do not use it on the bucket where per-object erasure is the
   contractual promise.
3. **"IAM policy is enough for KMS."** No: absent a key-policy grant, an `Allow` on
   `kms:*` with `Resource: "*"` grants you *nothing*, because the key policy implicitly
   denies everyone it does not name.

---

## 4. Who can run `kms:Decrypt`, and how a key policy meets IAM?

### The mechanism

KMS is special: **the key policy is mandatory and primary.** No AWS principal — including
the account root and the key's creator — has any permission on a CMK unless the **key
policy explicitly allows it and never denies it.** On top of that:

- An **identity (IAM) policy** on the caller must *also* allow `kms:Decrypt`.
- The final answer is the **intersection**: allowed by the key policy **AND** allowed by the
  IAM policy, with explicit Deny beating everything in either. (AWS states it directly:
  "no principal has any permissions to a KMS key unless they are explicitly allowed, and
  never denied, in a key policy.")
- **Grants** are a third instrument, "considered along with key policies and IAM policies."
  A grant is the *delegable, temporary, revocable* path — you can mint one, use it, and
  retire it without editing either policy — and grants carry conditions (encryption context)
  and are eventually consistent (~5 minutes, or use a **grant token** for immediate use).

### What an auditor asks

1. **"Show me who can decrypt tenant B's documents."** You must be able to enumerate, from
   the **key policy** of B's CMK (and any grants), the principals with `kms:Decrypt`,
   `kms:ReDecrypt*`. That is a *resource* question, and you cannot answer it from the IAM
   side alone. A vendor who only lists IAM roles for `kms:Decrypt` has not answered it: the
   key policy decides the universe of who *can* be granted at all.
2. **"Could you have given someone decrypt without noticing?"** A developer can add a grant
   or widen a key policy without touching the IAM console. The key policy, not IAM, is the
   control point — so your change-management evidence must cover **KMS key-policy edits**
   (CloudTrail `PutKeyPolicy`), not just IAM `CreatePolicyVersion`.

### Tying it back to your `iam.py`

`evaluate` returns `DENY` if *no* statement allows (implicit) and `ALLOW` only after
collecting the whole set with explicit-Deny-first. Real KMS authorization **composes your
`evaluate` twice** and ANDs the results — one pass over the key policy's statements as a
resource policy, one pass over the principal's IAM policies — and adds **grants** as a
parallel third source. The properties your code already demonstrates are exactly the
properties the auditor needs you to reason about:

- **Explicit deny in either** → deny, regardless of order in the other.
- **Implicit deny from the key policy** → the principal cannot be granted by IAM alone.
  This is the "IAM grants `kms:*` on `*` and it still fails" interview question; the reason
  is the key policy, and only someone who built `evaluate` with an "implicit deny" final
  branch gets why.
- **Conditions** (stage 2, AND-keys / OR-values / fail-closed) are how the key policy scopes
  a single CMK to a tenant via encryption context (stage 31), which is *also* the granularity
  that lets §2 shred.

The clean answer: **"Who can decrypt" is a key-policy question answered *before* IAM; IAM
can only shrink what the key policy opened, never widen it. Treat the key policy as a
mandatory resource-side `evaluate`, AND the result with the identity-side `evaluate`, and
grants as a temporary third input with the same precedence.**

### The concrete "revoke me" design for §1

The bank's requirement "revoke your access at any moment" is implemented as: *their* CMK,
key policy names your role for `kms:Decrypt`, and the key policy is theirs to edit. Revoking
you is `PutKeyPolicy` (or `DisableKey`/`RetireGrant`), logged in *their* CloudTrail, effective
across KMS endpoints after eventual-consistency delay. Compare with IAM: if the grant were
in *your* account's IAM, they could not unilaterally cut it. **The key policy's ownership is
the legal lever.** (The XKS answer in §1.2 is just this taken to its extreme: they revoke by
switching their own key off, not by editing a policy in your cloud.)

---

## 5. Bucket replication is turned on to `us-east-1`.

### The legal change, in one sentence

**The data is now in another jurisdiction**, replicated continuously and invisibly to the
data subject, with the destination holding plaintext-derived *and* ciphertext copies you may
not control independently. GDPR **Chapter V (Art. 44–49)** restricts transfers of personal
data outside the EEA; the US is not "adequate" for everything (see below). Replication does
not just *move* data — it *multiplies* every erasure obligation, because now **two objects
must be deleted for every one the user asked about.**

### The mechanism that makes it legal

A transfer needs a **valid transfer tool** for the destination:

- **Adequacy** — the EU–US **Data Privacy Framework** gives adequacy for organisations
  certified under it (and the UK Extension → **EU–US US Data Bridge**, and Swiss Addendum).
  Check *the importer's* certification status — you do not get adequacy because AWS is a big
  company; you get it because the **specific entity** processing in the US is certified.
- **Otherwise: SCCs** — the 2021 Standard Contractual Clauses (Module for the right
  relationship), plus a documented **Transfer Impact Assessment** (the *Schrems II* residue:
  can the importer actually honor the clauses under US law? FISA 702 / EO 12333 exposure),
  plus **supplementary measures** — and here encryption is one of them *only if the key is
  not in the importer's hands*: the EDPB's position is that the **key must be held outside
  the destination's reach** for the encrypted-at-rest copy to count as a protective measure.
  **That collapses straight into §1**: replicate to us-east-1 under an AWS-managed or
  AWS-held CMK and your "supplementary measure" is worthless; you need the key to stay in the
  EEA, which is precisely what an **EEA-held KMS CMK or an XKS/BYOK design** achieves — and
  SSE-KMS keys must be **in the same region as the bucket**, so replicating the *data* while
  keeping the *key* in the EEA forces a specific architecture (e.g. Multi-Region keys have
  *identical material in both regions*, which defeats the point).
- The destination account/entity must be under a **DPA** (Art. 28) and the **record of
  processing** updated. If the bank is the **controller**, this may have been *their*
  documented decision to make; if you turned it on as **processor**, you acted **outside the
  controller's instructions** (Art. 28(3)(a), Art. 29) — a contract breach and, in a breach
  scenario, an aggravating fact.

### What replication silently does to §2's erasure

- **Replication does not, by default, replicate delete markers** (a safety against accidental
  or malicious source deletes). So the subject's erasure in `eu-central-1` **does not erase
  `us-east-1`** — the deleted version *stays readable in the replica*. To make an erasure
  replicate you must explicitly enable **delete-marker replication** (and replicate
  **existing object version deletes** if you want non-current versions removed too). A
  vendor who "did the erasure project" without this has a *known, systematic* incompleteness
  in every transfer — and the auditor only needs to find one replica object to prove it.
- **Lifecycle/expiration must be configured on both sides**; the replica's storage class and
  version retention do not auto-sync.

### The answer, stated

> Replication is a **transfer**, so it needs a transfer tool (DPF adequacy on the certified
> importer, or SCCs + a real TIA + key-outside-the-destination), a **DPA** and an updated
> **RoPA**, and — if you are the processor — it must have been **in the controller's
> documented instructions.** It also doubles every Art. 17 deletion into *two* deletions and
> will under-deliver unless **delete-marker replication** is explicitly on. Turning it on
> "for latency" without those is not an architecture change; it is a **legal and contractual
> change** that happened to be made with a console checkbox.

---

## 6. A breach at 03:00: 72 hours, and a SOC 2 Type II auditor.

### The clocks you are actually in

There are two independent obligations and people conflate them.

- **GDPR**: **Art. 33** — notify the supervisory authority **within 72 hours of becoming
  aware**, unless unlikely to risk rights/freedoms; contents are Art. 33(3) (nature,
  categories, numbers, DPO contact, consequences, measures); **Art. 34** separately tells
  the *data subjects* without undue delay if **high risk**; **Art. 33(5)** makes you keep an
  internal **documented record of all breaches**, notifications included, to let the
  authority verify. The 72h runs from **awareness**, and awareness ≠ proof: a reasonable
  suspicion you dismiss without investigation does not reset it. A 03:00 alert that a sleepy
  engineer closes as "noise" is, to a regulator, "you became aware at 03:00."
- **DORA** (the bank's entity, and as its ICT provider you are **in scope via the contract**):
  reporting is **tiered by impact**, and the clock is a **chain, not one deadline**:
  classify as major *without undue delay* — in practice **within 24 hours of detection** →
  **initial notification within 4 hours of classification** (the harmonised template, Annex
  I of ITS 2025/302) → **intermediate report within 72 hours of the initial** → **final
  report within 1 month of the intermediate** (Delegated Regulation 2025/301). Note where
  each clock starts: **classification**, not detection, and each stage from the *previous
  report*. DORA is about **operational** incidents, so a bank will demand your **incident
  clock feeds their DORA clock**: a "we'll tell you after we finish root-causing" posture is
  non-compliant *for them*.

A vendor's answer to "what do you tell the client" is: **you notify the controller so the
controller can run *its* Art. 33 and DORA clocks; as a processor your Art. 33(2) obligation
is to notify the controller "without undue delay"** — your SLA may say "within 24 hours," but
the contract is the binding one.

### What you need, *at 03:00, before you have anything*

The 72 hours is lost if your **evidence is not collectable while you sleep**. The detection
artifacts — in the order an investigator wants them:

- **CloudTrail** — but understand what it holds and what it *cannot*:
  - **Management events** (who changed a key policy, `DisableKey`, `CreateKey`,
    `PutKeyPolicy`, IAM changes, `StopLogging`) — on by default for the free trail; *this* is
    "how did the attacker get access" and "what did they open."
  - **Data events** — **default OFF, and you pay per event.** S3 object reads (`GetObject`,
    `PutObject`, `DeleteObject`) and Lambda invocations are **not captured** unless you
    configured the data event selector for *that bucket* **before** the incident. So the
    answer to "what did they *read*" is frequently "I don't know," because nobody bought
    data events. **The decision you make about enabling S3 data events is the decision that
    determines whether you can answer Art. 33(3) accurately.** This is the same mechanism as
    §3's "at least once per requester" KMS logging — auditing granularity is a *paid,
    pre-decided* thing, not a switch you flip after the fact.
  - **KMS crypto ops**: your KMS API calls are in the trail, but for AWS-managed/owned keys
    services cover them and you may not see per-object decrypts — SSE-KMS with a CMK + data
    events is again what gives visibility.
  - **Log integrity**: enable **CloudTrail log file validation** (hash-chained digests) and
    ship to an **S3 bucket under Object Lock (compliance mode)** or at least a locked bucket +
    a separate account, so the trail itself can't be deleted by the same credential that
    deleted the data. (The same WORM that fights §2 is what *proves* §6.)
- **GuardDuty** findings (the 03:00 *signal* you hope already fired), **Security Hub**
  aggregation, **Config** rule drift, **VPC flow logs**, **WAF** / CloudFront logs, and your
  own application **audit log** (this is literally `capstone.py`'s `cloud.audit` list — the
  line that records `ALLOW`/`DENY` per call is the forensics line; stage 36 already shows
  how the *cause* sits one layer from the *symptom*).
- **The encryption context** (stage 31) is what lets you say *which* tenants' keys were used,
  turning "someone made 4M KMS calls" into "these tenants' documents were decrypted." Without
  context bound into the wrap, you have a count and no blast radius.

Reconstruction to a defensible narrative = **a timeline**: first anomalous event → awareness
timestamp → containment → the *population* affected (which CMK/data keys touched / which
encryption contexts) → the Art. 33/DORA numbers (how many data subjects, how many records,
which category) → notification sent (the message, the time, who owns it).

**The trap** that breaks people in this question: they reach for a SIEM they have. The answer
is *data events + KMS logs + a locked CloudTrail you enabled before the incident*. If you did
not buy granularity, on the night you cannot manufacture it; you document the limitation and
that you will fix the control.

### What a **SOC 2 Type II** auditor asks about the *same* control, over the period

The shift in §6 from "this incident" to "this control":

- **GDPR / DORA look at one event** and ask whether you met the deadlines with true facts.
- **SOC 2 Type II looks at the whole review period** and asks whether the control **operated**
  — not whether it exists today. For the incident/breach control, expect:
  - **Sample of every incident in the period** (not a sample — the population): each with a
    ticket, a detection timestamp, a classification decision, the notification decision *and
    its rationale even when "no notify"*, the artifact, and closure. An empty population is
    fine; **the absence of the *decision record* is the exception.** A Type I shows your
    process; a Type II shows the process was *followed*, e.g. that the IR policy was tested
    with tabletops in the period.
  - **Monitoring controls are tested as operating, continuously**: a trail must have been
    *enabled and unbroken across the period*, with **evidence of no gap** — a `StopLogging`
    event, or a deleted trail, is itself an exception, which is why the trail must be locked.
    They will **re-sample random days** in the period and ask "show me the access logs for
    this bucket on this date"; if you did not retain them, the evidence is missing,
    irrespective of whether anything bad happened.
  - **Access controls are *recertified*** (user access reviews, key/role reviews) *over the
    period* with dates — §4's "who can decrypt" is expected to be a **recurring, evidenced
    review**, not a one-time architecture diagram.
  - **Change control**: the `PutKeyPolicy` / data-event-config changes in the period are
    tied to an approval ticket. The control is "the same trail that detects the attacker also
    detects *you* making the mistake."
  - **The 72h itself is an audited control**: how you *measure* awareness-to-notification for
    every incident, with timestamps, and whether the *documented* process matches reality.

The clean answer: **GDPR gives you a 72-hour test you pass or fail once; SOC 2 Type II gives
you the same control judged across every day it could have mattered. The evidence that
passes the 72h (data events enabled, a locked trail, an audit line with the right fields, an
incident record even when you decided not to notify) is the same evidence the Type II period
needs — which is why "we'll turn logging on after the incident" is the worst possible answer
to both: you cannot retroactively produce the granularity that detects the breach *and*
proves the control ran.**

---

## The map: stage ↔ compliance question ↔ where it breaks

| Mechanism you built | Legal/compliance fact it decides | The break you cannot code around |
|---|---|---|
| stage 1 (deny > allow > implicit) | "revoke me" is a *Deny* append, order-safe | revocation only works if the grant lives where they can edit it → **key policy, not IAM** (§4) |
| stage 8 (delete markers) | a DELETE is not an erasure; Art. 17 needs version purge | replicas keep data when delete markers don't replicate (§5); WORM forbids the purge at all (§2 backups) |
| stages 29–31 (envelope, one KMS call/object, **encryption context**) | crypto-shredding (key granularity) and the *tenant as erasure index* | bucket keys coarsen granularity (§3); context is the *only* thing that tells you who a decrypt harmed (§6) |
| stage 32 (rotation ≠ re-encryption) | key lifecycle = control plane, not data plane | revocation windows (PendingDeletion) still keep data recoverable (§1) |
| stage 2 conditions (AND-keys/OR-values, fail-closed) | one CMK multi-tenant via `EncryptionContext` | missing condition keys → fail closed → you get outage, not access (§6, if the trail is your condition) |
| stage 4 (assume-role: caller **and** trust) | cross-account revocation is a trust-policy edit | a key they own and you use is *their* to revoke (§1, §4) |
| capstone `cloud.audit` + IAM-gated calls | the forensic timeline and "who did what" | management events on by default, **data events off** unless you paid first (§6) |

Read the right column alone and you have the interview. Read both and you have the reason the
mechanism *matters*: a bank's "we can revoke you at 3am" is only true if the revocation
mechanism is a **resource-side key policy** whose removal your `evaluate`-engine sees as a
deny, with an audit trail whose data events you already bought.

---

## The self-test (before the simulacro)

Can you now, *without scrolling*, answer these? Anything you hesitate on is the gap.

1. What is the difference, as a *fact*, between deleting a CMK and deleting data, and which
   of §1's models makes "they can revoke us in real time" true with no waiting window?
2. For one Art. 17 request, name the four locations, say which one crypto-shredding solves
   *best* and why, and which one it solves **not at all** and why.
3. You enable S3 Bucket Keys on a tenant's bucket. What happened to your KMS bill, what
   happened to your CloudTrail attribution, and what happened to §2's per-subject shredding?
4. An engineer holds IAM `kms:Decrypt` on `*`. Can they decrypt tenant B? Now make them able
   — in exactly one artifact, named, and say which CloudTrail event shows it.
5. You turned on CRR to us-east-1 last quarter and a subject erasure happened this week.
   What legal instrument is missing, and what single replication setting means the replica
   still has their document right now?
6. It is 03:12 and GuardDuty fires. You must file Art. 33 and your bank client must file
   DORA. What two clocks are you in, and what evidence are you *already missing* because you
   did not enable it in July?

If 2, 4 and 6 are shaky, that is the real gap the original message named — and note that in
every case the gap is **one line to the right of a stage you already passed**: 31→2, 1→4,
capstone→6. The compliance question is not a different subject. It is the subject you built,
asked at 3am by a regulator.

---

## Sources (live-checked 2026-11-07)

AWS docs — *key-policies* ("no AWS principal, including the account root user or key
creator, has any permissions … unless explicitly allowed and never denied in a key policy");
*grants* ("considered along with key policies and IAM policies"; eventual-consistency and
grant tokens); *key-state* (`PendingDeletion`, XKS "if the backing key is disabled or
deleted … cryptographic operations fail"); *ScheduleKeyDeletion* (waiting period 7–30 days,
default 30); *importing-keys* (BYOK, expiry, "KMS does not support decrypting KMS ciphertext
outside of KMS"); *keystore-external* / XKS (KMS never holds the material, proxy-mediated);
*concepts* / key-types (CMK vs AWS-managed vs AWS-owned: key-policy control, logging, and
pricing); *s3-bucket-keys* ("up to 99% request-cost reduction", "at least once per requester
… captured in an AWS KMS CloudTrail event", **not supported for DSSE-KMS**);
*services-s3 / UsingKMSEncryption* (SSE-KMS key must be same region; SSE-S3 base-level
encryption since 2023); *replication* (live/on-demand; delete markers **not** replicated by
default, "protects destination from accidental or malicious deletions"); *object-lock* (WORM,
Cohasset assessment, legal holds have no expiry); *cloudtrail logging-data-events*
("**By default, trails … do not log data events. Additional charges apply**"); KMS pricing
(free tier 20,000 req/month all regions; ~$0.03/10k symmetric → the 2.01M = $5.97 example);
KMS quotas (symmetric shared rps: 10k default / 20k / 100k by region; keys 100,000/account-
region).

Law — GDPR **Art. 17** (+17(3) exceptions), **Art. 28(3)**, **Art. 33/34/33(5)**, **Chapter V
(44–49)**; **EU–US Data Privacy Framework** adequacy (2023) and the UK Extension/EU–US Data
Bridge; **SCCs 2021/914** + Transfer Impact Assessment + supplementary measures
(EDPB *Recommendations 01/2020* key-custody logic); **DORA** (Reg. 2022/2554) Arts. 17–23 +
the **Commission Delegated Regulation (EU) 2025/301** RTS (content and time limits: initial
within 4h of classification, intermediate within 72h, final within 1 month), **Implementing
Regulation (EU) 2025/302** ITS (the harmonised Annex I forms), Joint Technical Standards
**(EU) 2024/1772** (major-incident classification and the 24h-to-classify rule) and
ESMA/EIOPA operational instructions; **4AMLD/5AMLD**
retention (the Art. 17(3) conflict); **GDPR Recital 66** and **EDPB Guidelines 02/2025**
(cryptographic unrecoverability as erasure); **SOC 2 Type I vs Type II** (design at a point
vs. operating effectiveness over the period) and breach/IR-control evidence.

`anyformat` live-state, checked this date: the **Vanta trust center (trust.anyformat.ai)**
lists **"Compliance — ISO 27001:2022"** as held; the blog (2026-03) said Stage 2 of the audit
was complete and "close to the finish line." **No SOC 2 appears on the trust page** — so the
honest answer is **ISO 27001 (certified, narrow window for the "is the cert in the mail yet?"
question), SOC 2 not yet.** Subprocessors listed: AWS (Frankfurt), Azure (Sweden — model
workloads EU-resident there), Datadog (operational telemetry, no customer docs stored), GCP
(Gemini, no customer training). That **changes §6's angle**: an *ISO 27001* auditor asks
surveillance-audit questions over the ISMS (continual-improvement, internal-audit and
management-review records), which is a *different* evidence set than a SOC 2 Type II
period-sample. The bank will ask for SOC 2 because you don't have it; you must know which of
§6's evidence they're entitled to expect from an ISO-certified processor. Verify the cert's
current status and its **scope statement** before the interview — a certification is only
worth the scope printed on it, and §1's whole argument is that "what is covered" is the
question.
