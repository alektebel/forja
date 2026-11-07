# Compliance — the layer the 36 stages do not teach

The course teaches **mechanisms**: how IAM evaluates, what a delete marker does, why
rotation re-encrypts keys and never data. A regulated bank does not buy mechanisms. It
buys **guarantees about who can read its data, in which country, and how that is proven
to a stranger six months later.**

This file is the bridge. It assumes you can pass stages 1–4 (`iam.py`), 8 (`s3.py`) and
29–32 (`kms.py`) — because if you cannot, the compliance answers below have nothing to
attach to. Every fact here is checked against AWS docs, GDPR/DORA text or a regulator
page as of 2026-11; anything that is a judgement, not a citation, is marked **`(call)`.**

Part I is six scenarios, each from a real buyer question (§0–§6): read the primitives first,
then the scenario that hurt. Part II (§7–§13) is the full perimeter of what **SOC 2, GDPR and
ISO 27001** actually require — plus the AI Act, DORA from the supplier's chair, the crosswalk
where one piece of evidence serves four audits, and the program order for a company that holds
ISO and has no SOC 2 yet.

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
information is gone. **GDPR Recital 65** says a data subject should have the right to have his or
her personal data "erased and no longer processed," **Recital 66** adds that a controller who has
made data public must take "reasonable steps … including technical measures" to inform the
controllers processing it, and **EDPB Guidelines 02/2025** (on blockchain) confirm that rendering
data cryptographically unrecoverable can satisfy the Art. 17 duty. That is the authority the
phrase "crypto-shredding is valid" rests on.

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

> Crypto-shredding is a valid **technical implementation** of erasure — Recital 65 and the
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

## 7. GDPR: you are the processor, and the contract is the product.

**The scenario.** Two days before signature, the bank's DPO writes: "Please confirm you will sign
our DPA addendum without amendment, and provide your sub-processor list and your position on
Art. 22 for the scoring step." Sales reads *paperwork*. What has actually arrived is
**GDPR Art. 28(3)(a)–(h)**, and every letter of it is a mechanism you built in Part I. This
section is the full perimeter: which GDPR you are inside, what the contract says clause by
clause, the four interactions where a clever architecture becomes a breach, and why the fine
tiers are a routing table rather than a number.

### Which GDPR you are inside

**Roles before anything else.** Art. 4 defines the controller as the body determining the purposes
and means, the processor as the body processing on its behalf. anyformat is a **processor**; the
bank is the **controller**. The sentence that turns your product into a controller is
**Art. 28(10)**: "if a processor infringes this Regulation by determining the purposes and means of
processing, the processor shall be considered to be a controller in respect of that processing."
Concretely: reuse a customer's document corpus to train a feature the contract did not name, and
you are no longer a processor with a lighter duty set — you are a controller with no legal basis,
no notice, and no relationship with those data subjects.

**Territory.** **Art. 3(1)** catches processing in the context of the activities of an establishment
in the Union, *wherever the bytes sit*. **Art. 3(2)** catches a controller or processor **not
established in the Union** where the processing relates to (a) offering goods or services to data
subjects in the Union, or (b) monitoring their behaviour there. That is why a Delaware SaaS with no
EU office signs DPAs: the offering reaches into the Union, and **Art. 27** then requires a
designated **representative in the Union** in writing (27(2) exempts occasional processing that is
not large-scale special-category/Art. 10 processing and excludes public authorities — a document
pipeline handling ID biometrics does not qualify).

**Basis, because the basis decides your feature list.** Art. 6(1)(a) consent, (b) contract,
(c) legal obligation, (d) vital interests, (e) public task, (f) legitimate interests. For an
IDP/credit pipeline: the borrower's own documents under **(b)**; fraud screening under **(f)**. The
consequence is not philosophical — **Art. 21(1)** gives an objection right against processing based
on (e) or (f), and **Art. 20(1)** gives portability *only* where the basis is consent (6(1)(a) /
9(2)(a)) or contract (6(1)(b)) **and** the processing is by automated means. Choosing (f) creates a
stop-processing endpoint; choosing (b) creates an export obligation. `(call)` — the architectures
that forget this are the ones that promise "GDPR compliant" and ship a support form.

**Art. 9** prohibits processing special categories — including **biometric data for the purpose of
uniquely identifying a natural person**. An ID selfie plus a face match is squarely inside that
prohibition, so you need **9(2)(a)** explicit consent (or another opening, most plausibly (g)
substantial public interest, which needs Member State law). **Art. 22(4)** closes the loop:
decisions under 22(2) shall not be based on special categories "unless point (a) or (g) of Article
9(2) applies and suitable measures to safeguard the data subject's rights and freedoms and
legitimate interests are in place."

**Art. 5(1)(c) minimisation, made architectural by Art. 25(2):** by default "only personal data
which are necessary for each specific purpose" are processed, and the obligation explicitly "applies
to the amount of personal data collected, the extent of their processing, the period of their
storage and their accessibility." This is the clause a document-extraction vendor breaks *by
accident*, because extraction feels like a copy: parse twenty fields when the contract uses four,
and you have a by-default violation on the *amount* dimension, independent of any breach.

### Art. 28(3): the anatomy of the document they are sending you

The chapeau, verbatim: the contract "sets out **the subject-matter and duration of the processing,
the nature and purpose of the processing, the type of personal data and categories of data subjects
and the obligations and rights of the controller**." That sentence is not a clause — it is a **data
map**: what, how long, why, which data, which people, whose rights. If you cannot generate that
map from your own system, you cannot sign the chapeau truthfully, whatever the letters say.

Then the letters, each with the Part I mechanism it is asking for:

| Art. 28(3) | What it requires (verbatim core) | The mechanism in Part I | Where it breaks |
|---|---|---|---|
| (a) | processes "only on documented instructions from the controller, **including with regard to transfers**", unless law requires, and then "inform the controller of that legal requirement **before processing**" | §5 replication | turning on CRR to `us-east-1` for latency is processing outside instructions (28(3)(a) + Art. 29); the "law requires it" escape needs a *pre-processing* notice, not a post-incident email |
| (b) | persons authorised to process are committed to confidentiality or under an appropriate statutory obligation | §4 who can run `kms:Decrypt` | contractors with console access and no NDA; support staff who can `Decrypt` but were never onboarded |
| (c) | "takes **all measures required pursuant to Article 32**" | §0.1, §3 | Art. 32(1) is four duties: (a) "the pseudonymisation and encryption of personal data", (b) "the ability to ensure the ongoing confidentiality, integrity, availability and resilience of processing systems and services", (c) "the ability to **restore the availability and access to personal data in a timely manner** in the event of a physical or technical incident", (d) "a process for regularly testing, assessing and evaluating the effectiveness of technical and organisational measures" — encryption without (c)'s tested restore and (d)'s test cadence is one of four |
| (d) | respects the conditions in 28(2) and 28(4) for engaging another processor | §7 sub-processors below | a fifth region vendor added by procurement with no notification |
| (e) | assists the controller, by appropriate technical and organisational measures "insofar as this is possible", to answer **Chapter III** rights requests | §2, stage 8 | "we can delete the document" is not assistance if the controller needs the *subject* located: granularity (stage 31, encryption context) is the assist mechanism |
| (f) | assists the controller in ensuring compliance with **Articles 32 to 36** | §6, §0.4 | your 03:00 artifacts *are* the bank's Art. 33(3) content; 35's DPIA needs your TOM description; 36's prior consultation needs your risk numbers. Art. 36 gives the authority eight weeks, extendable by six — that is a *feature-launch* deadline |
| (g) | "at the choice of the controller, deletes or returns all the personal data … after the end of the provision of services … and deletes existing copies **unless Union or Member State law requires storage**" | §2 backups, 4AMLD | the only lawful retention is *the controller's* legal obligation, named: you cannot keep AML records on your own behalf, and the choice between delete and return is theirs, not yours |
| (h) | makes available "all information necessary to demonstrate compliance" and "allow for and contribute to audits, **including inspections**, conducted by the controller or another auditor mandated by the controller" | capstone trail, §4 | an audit right you satisfy with a certificate PDF; also the closing sentence of the subparagraph: the processor "shall immediately inform the controller if, in its opinion, an instruction infringes" the Regulation |

**Sub-processors are a notification duty, not a purchasing decision.** **28(2)**: "shall not engage
another processor without prior specific or general written authorisation", and under general
authorisation the processor "shall inform the controller of any intended changes concerning the
addition or replacement of other processors, thereby giving the controller the opportunity to
object **to such changes**." **28(4)**: the same obligations must be imposed on the other processor by contract, and —
the sentence to read twice — "where that other processor fails to fulfil its data protection
obligations, **the initial processor shall remain fully liable to the controller** for the
performance of that other processor's obligations." Your Datadog and your Gemini call are therefore
not infrastructure choices; they are the tail of your liability chain, with no ability to pass the
buck. **28(6)**: standard contractual clauses may underpin the 28(3) contract — the mechanism that
lets a bank's group of twenty vendors stay readable.

### Where a clever architecture becomes a breach

The trap answers, in the order buyers ask for them:

1. **"We encrypt at rest, so we satisfy Art. 32."** See (c) above: four duties, two of them about
   *restoring* and *testing*. A backup nobody has restored is not an Art. 32(1)(c) ability.
2. **"Erasure is just a DELETE."** §2's mechanism list plus **Art. 19**: any erasure (or
   rectification, or restriction) must be communicated "to each recipient to whom the personal data
   have been disclosed, unless this proves impossible or involves disproportionate effort", and the
   data subject must be informed about those recipients on request. Crypto-shredding your key does
   not tell the credit bureau you exported to. **This is the erasure path that a processor most
   often misses**: Art. 19 is the controller's duty, so it arrives as an *assistance* duty under
   28(3)(e) — you need the recipient list, per subject, as queryable data.
3. **"We shredded the key, so restriction is moot."** This one is the opposite. **Art. 18(1)(b)**:
   where processing is unlawful and the subject "**opposes the erasure** of the personal data and
   requests the restriction of their use instead", the record is *frozen, not destroyed*; 18(2) then
   allows those data, "**with the exception of storage**", only with consent or for legal claims or
   another person's rights or important public interest; and **18(3)** requires the controller to
   inform the subject *before the restriction is lifted*. Delete-marker granularity (§2) is what
   makes 18 survivable: if your only per-subject lever is destroying the key, you cannot honour a
   request that explicitly forbids destruction. Erasure and restriction are **different states with
   different mechanisms**, and a system that implements only one fails the other.
4. **"Our ISO certificate makes us a compliant processor."** **28(5)** is the bridge and the limit:
   adherence to an approved **Art. 40 code of conduct** or an approved **Art. 42 certification
   mechanism** "may be used as an element by which to demonstrate sufficient guarantees as referred
   to in paragraphs 1 and 4 **of this Article**." An element. And an ISO/IEC 27001 certificate is not an Art. 42 GDPR
   certification — it is a security-management scheme with no supervisory-authority approval under
   the Regulation. It evidences Art. 32 (and therefore 28(3)(c)); it does not substitute for one
   letter of 28(3). `(call)` on the last sentence being the part buyers skip.
5. **"We only log document IDs, not names."** Recital 26's test is identifiability including
   *singling out*; an opaque ID re-identifiable through your own tenant index is personal data, so
   the data-event line you deliberately enabled in §6 sits **inside** the Art. 17 perimeter — and
   §2's "nothing crossed the crypto boundary" constraint is exactly this rule in engineering terms.
6. **"There's a human in the loop, so Art. 22 does not apply."** Read 22(1) for what it actually
   targets: a decision "**based solely on** automated processing, including profiling, which
   produces legal effects … or similarly significantly affects him or her." A reviewer who
   rubber-stamps the model's answer has not made the decision non-solely-automated; a reviewer who
   can and does change outcomes has. `(call)` — the distinction is interpretive, and the EDPB/WP29
   guidance on automated decision-making and profiling is where both sides argue from.

**The Art. 22 nuance that decides whose problem it is.** 22(2) disapplies 22(1) where the decision
(a) is necessary for entering into or performing a contract, (b) is authorised by Union or Member
State law "which also lays down suitable measures to safeguard the data subject's rights and
freedoms and legitimate interests", or (c) rests on explicit consent. Then 22(3): "**In the cases
referred to in points (a) and (c) of paragraph 2**, the data controller shall implement suitable
measures … at least the right to obtain human intervention on the part of the controller, to express
his or her point of view and to contest the decision." **Point (b) is absent** — where the basis is
law, the safeguards must live in the law, and the controller owes no 22(3) package. So the bank's
request for "a human-review path in your product" is a *contract-derived* obligation only if the
bank's own basis is contract or consent. Ask the question, because the answer tells you who pays for
the feature. And whichever basis applies, **Art. 13(2)(f)** (14(1)(c)/(g) for data not obtained from
the subject) already requires the notice to contain "meaningful information about the logic involved,
as well as the significance and the envisaged consequences of such processing for the data subject"
for 22(1) and 22(4) decisions — that is a *field in your output*, not a paragraph in your privacy
policy. The AI Act's Art. 6(3) analysis in §11 and this one are the same analysis with two
authorities, which is the point of §10.

### Arts. 30 / 35 / 37: three artifacts that are actually programs

- **Art. 30.** Controllers keep 30(1)(a)–(g): names and contacts (controller, joint controller,
  representative, DPO), purposes, description of data-subject and personal-data categories,
  recipients "including recipients in third countries or international organisations", transfers
  with the third country identified and — for Art. 49(1) second-subparagraph transfers — the
  documented suitable safeguards, envisaged erasure time limits, and "where possible, a general
  description of the technical and organisational security measures referred to in Article 32(1)".
  **Processors keep their own record under 30(2)(a)–(d)**, by controller: the names, the categories
  of processing carried out on behalf of each controller, transfers, and that same TOM description.
  30(3): "shall be in writing, **including in electronic form**." 30(4): available to the authority
  on request. **30(5)** exempts enterprises under 250 persons — *unless* the processing is likely to
  result in a risk, "the processing is not occasional", or it includes Art. 9(1) or Art. 10 data. A
  continuous document pipeline handling ID biometrics satisfies none of the safe paths, so do not
  budget on the SME derogation. `(call)` on that being the most common self-inflicted GDPR gap in
  small vendors.
- **Art. 35.** 35(1) requires a DPIA where the type of processing, particularly using new
  technologies, is likely to result in high risk, before the processing; 35(2) requires seeking the
  DPO's advice. **35(3)(a) is a description of your product**: "a systematic and extensive
  evaluation of personal aspects relating to natural persons which is based on automated
  processing, including profiling, and on which decisions are based that produce legal effects … or
  similarly significantly affect the natural person." 35(11) requires a review "at least when there
  is a change of the risk". So the DPIA is a *dated* artifact with a refresh trigger — a document
  from 2024 describing a 2026 model is a finding, not a defense.
- **Art. 37.** DPO required where (a) public authority, (b) core activities consist of processing
  operations requiring **regular and systematic monitoring of data subjects on a large scale**, or
  (c) core activities consist of large-scale processing of Art. 9 data or Art. 10 convictions data.
  (b) is the paragraph to worry about; "core activities" means the main business, not a side tool.

### The fines are a routing table

**Art. 83(4)(a)** — tier 1, up to **€10,000,000 or 2%** of total worldwide annual turnover,
whichever is higher, for obligations of the controller and the processor "pursuant to Articles 8,
11, **25 to 39** and 42 and 43". Read the range, because it is your whole engineering surface: 25
(by design and by default), **28 (the DPA)**, 30 (records), 32 (security), 33/34 (breach), 35
(DPIA), 37 (DPO). **Art. 83(5)** — tier 2, **€20,000,000 or 4%**, for (a) "the basic principles for
processing, including conditions for consent, pursuant to **Articles 5, 6, 7 and 9**", (b) the data
**subjects' rights pursuant to Articles 12 to 22**, (c) transfers "to a recipient in a third country
or an international organisation pursuant to **Articles 44 to 49**", (d) obligations under Member
State law adopted under Chapter IX, and (e) non-compliance with an Art. 58(2) order or failure to
provide access under 58(1). 83(6) re-states 58(2) non-compliance at the higher tier.

Practical routing: ignoring an Art. 17 erasure request is **tier 2**; shipping a DPA that misses a
28(3) letter is **tier 1**; replicating customer data to a third country with no transfer tool is
**tier 2**; failing to keep a breach record under 33(5) is **tier 1**. Then **83(3)**: "If a controller
or processor intentionally or negligently, **for the same or linked processing operations**, infringes
several provisions of this Regulation, the total amount of the **administrative fine** shall not exceed
the amount specified for the **gravest infringement**." The commercial reading is
the opposite of comfort — one bad checkbox (a replication change that touches 28, 30, 44 and 17 at
once) is not four tier-1 fines you can net down, it is **one fine at the highest tier that the
chain reaches**. `(call)`.

And it is not only a fine story. **Art. 82(2)**: "A processor shall be liable for the damage caused
by processing only where it has not complied with obligations of this Regulation specifically
directed to processors **or where it has acted outside or contrary to lawful instructions of the
controller**." 82(4) makes each responsible party liable for **the entire damage** so the data
subject is compensated effectively; 82(5) gives a contribution claim back against the others. That
is the indemnity clause in every bank DPA, stated as law: the replication checkbox is a private-law
exposure before it is a regulatory one.

### The answer, stated

> GDPR, seen from the processor's chair, is a **contract with a data map and a mechanism list**:
> the 28(3) chapeau says you know what you hold, for how long, and for whom; **(a)** says no region,
> no vendor, no purpose without the controller's documented instruction; **(c)** says Art. 32 is
> four duties and two of them are *restore* and *test*; **(e)** and **(f)** say you must be able to
> assist erasure, restriction, breach, DPIA and prior consultation **with artifacts, not goodwill**;
> **(g)** says the only retention you may keep is a *named* legal obligation of theirs; **(h)** says
> the audit is a right, inspections included, and that you must speak up when an instruction is
> unlawful. **28(2) + 28(4)** put AWS on your list and you on the hook for it. **28(5)** says your
> certificate counts as **an element** of sufficient guarantees — which is why the discipline of §8
> is worth money in this conversation, and why the certificate alone is not the answer.

This rests on stages you already passed: the version/delete-marker mechanics of stage 8 (§2's four
locations), the encryption-context granularity of stages 29–32 (the 28(3)(e) "assist" needs a key
per unit of deletion), the trust-policy and key-policy interaction of §4's `iam.py` stages 1–4
(28(3)(b)/(c) access discipline), and the capstone's `cloud.audit` trail (28(3)(h), plus Art. 33(5)
records). GDPR is what those mechanisms are *for* when a stranger asks.

---

## 8. ISO 27001: the management system is the product.

**The scenario.** The procurement portal asks one question with one slot: *"Attach your ISO 27001
certificate."* You attach the PDF — `ISO/IEC 27001:2022`, scope: *"Provision of document-processing
software-as-a-service from the eu-central-1 region"* — and the bank's security team comes back with
the only question that matters: **"Does the scope include the inference path running in Sweden, the
support access from the US, and the Datadog telemetry pipeline?"** Three of the four things you told
them about your architecture are, as far as this certificate is concerned, *undocumented*. This
section is why: ISO 27001 certifies a **management system with a printed scope**, not a product, and
the machinery that keeps the certificate alive (ISO/IEC 17021-1) runs on clocks §9's machinery does
not even have.

### What is actually certified

Read the structure of the standard before you read the controls:

- **Clauses 4–10 are the requirements.** "Shall" language only. These are the auditable obligations:
  context, leadership, planning, support, operation, performance evaluation, improvement. Nothing in
  4–10 mentions encryption or firewalls.
- **Annex A is a reference catalogue of 93 controls**, selected — not adopted wholesale — through
  **6.1.3**: the risk treatment plan is compared against Annex A and the result recorded in the
  **Statement of Applicability**, which must contain, for every one of the 93, the control,
  *whether it is applicable, the justification for inclusion or exclusion, and its implementation
  status*. Exclude 40 controls and you need 40 risk-based justifications an auditor can attack;
  include 93 and you owe 93 pieces of operating evidence. There is no free option.
- **ISO/IEC 27002 is guidance** on how to implement Annex A — citable, not certifiable.
  **ISO/IEC 27701** extends the ISMS into a privacy information management system: it is where §7's
  Art. 28 duties get a management-system home, and it is an *extension* — you cannot certify 27701
  without the 27001 base. `(call)` on whether 27701 is worth pursuing before §9 exists; probably not,
  the Vanta-style evidence engine covers more buyer questions per euro.
- The 2022 edition collapsed the 2013 model's 14 domains into **4 themes — 37 organizational (A.5),
  8 people (A.6), 14 physical (A.7), 34 technological (A.8)**. The Annex B mapping is not a
  renumbering: of the 114 old controls, 58 carried over, 57 were merged into 24, 1 was split. Every
  2013 certificate expired **2025-10-31** (IAF MD 26's 36-month transition), so any vendor still
  showing a 27001:2013 piece of paper is showing an expired one. Amd 1:2024 then added climate
  change to the list of external issues clause 4.1 must consider — the standard's answer to "comms
  are full of climate risk and nobody's ISMS mentioned it." `(call)` that 4.1's climate sentence has
  generated more management-review agenda items than risk-assessment deltas.

### The spine: clauses 4–10, and the artifact each one forces

An auditor does not ask "do you encrypt?" An auditor follows the spine and asks for the artifact:

| Clause | The requirement, compressed | The artifact on the audit table | The Part I mechanism it interrogates |
|---|---|---|---|
| 4.1 / 4.2 | Determine internal/external issues (incl. climate, Amd 1) and interested parties' requirements | Context analysis naming *regulators, customers, DPA contracts* — i.e., §7 arriving as an input | Art. 28(3) letters become "interested-party requirements" here, or they arrive as a surprise at 9.3 |
| 4.3 | Declare the scope of the ISMS | **The scope statement — printed on the certificate** | Does the scope cover Frankfurt, or only "the application"? The Sweden inference path? Read your own certificate against §0's custody models |
| 5 | Leadership, policy, assigned roles | Approved policy set; who is management, who is DPO-adjacent | §4's "who can `kms:Decrypt`" question in *organisational* form |
| 6.1.2 / 6.1.3 | Assess and treat risk; compare against Annex A | **Risk register, SoA, risk treatment plan** — the three documents an auditor actually reads | §2's backup-WORM constraint and §3's per-tenant keys should be *outputs of this*, not architecture opinions |
| 6.2 | Objectives with plans: what, resources, who, when, how evaluated | Dated objectives with owners | "Reduce mean restore-verification time" is a 6.2 objective; hope is not |
| 6.3 | Changes to the ISMS are planned, not improvised | Change records for the ISMS itself | §5's replication-region change is an ISMS change *and* a 28(3)(a) instruction change |
| 7 | Competence, awareness, documented information | Training records with completion data | DORA Art. 13(6) training modules (§12) slot in here — same evidence, two frameworks |
| 8.1 | Plan, implement and control processes to meet requirements | Documented operating criteria | §6's 03:00 runbook is an 8.1 process; if it exists only in someone's head it does not exist |
| 9.1 / 9.2 / 9.3 | Monitor and measure; **internal audit at planned intervals**; management review with defined inputs/outputs | Internal audit reports, management-review minutes | 9.2 is **your** internal-audit duty. Note the trap in §8's trap list: the 12-month rule you may have read about in ISO/IEC 17021-1 §10.2.6.3 governs the *certification body's* audits of *itself*, not yours |
| 10.1 / 10.2 | Continual improvement; react to nonconformity, evaluate causes, correct, review effectiveness | The corrective-action log | Every finding from §6's post-incident review should land here or it is lost |

### Annex A's 93, and the eleven that anyformat was not ready for

The 2022 edition's 11 new controls read like a retrospective on 2020–2022:
**A.5.7 threat intelligence, A.5.23 information security for use of cloud services, A.5.30 ICT
readiness for business continuity, A.7.4 physical security monitoring, A.8.9 configuration
management, A.8.10 information deletion, A.8.11 data masking, A.8.12 data leakage prevention,
A.8.16 monitoring activities, A.8.23 web filtering, A.8.28 secure coding.** Six of them are exactly
the anyformat-shaped controls — the ones Part I spent stages building mechanisms for:

| Annex A | Title | Part I mechanism | The evidence the control forces beyond the mechanism |
|---|---|---|---|
| A.5.23 | Information security for use of cloud services | §0's three custody models; the AWS/Azure/GCP/Datadog stack | An exit strategy *and* a shared-responsibility statement per cloud — the control assumes you know which duties you bought and which you kept |
| A.5.30 | ICT readiness for business continuity | §6's restore path; §5's replication | RTO/RPO per service, tested — this is the control that asks what your **RPO** is; §5's replication lag is the answer, and "we didn't compute it" fails |
| A.8.10 | Information deletion | stage 8 delete markers, §2's purge | Deletion when *no longer required* — retention schedules the SoA actually applies, not scripts nobody runs |
| A.8.11 | Data masking | §0.3's pseudonymisation tie | Masking in logs and analytics; the data-event line from §6 must *not* carry field contents |
| A.8.12 | Data leakage prevention | §4's access boundaries | Detection of egress the ACLs permit — the control admits that authorised users leak |
| A.8.16 | Monitoring activities | capstone `cloud.audit`; data events | Correlated alerting over logs, with the A.8.15 *logging* and A.8.17 *clock synchronisation* pair — a trail whose clocks drift is a trail whose timeline is fiction |

The rest of the mapping is one-to-one: A.5.15/A.5.18 (access control, access rights) ↔ §4's
provisioning/deprovisioning discipline; A.8.2 (privileged access rights) + A.8.5 (secure
authentication) ↔ §1's break-glass; A.8.24 (use of cryptography) ↔ §0.1's CMK decision, the control
that asks *where your key-management rules are written down*; A.8.13 (information backup, explicitly
"test restoration") ↔ §2's versioned-S3 problem; A.8.33 (test information) ↔ §2's embeddings — the
control most SaaS vendors discover mid-audit when the auditor asks whether staging runs on a
production copy. `(call)` on staging-on-prod-data being the most common Annex A nonconformity in
document-processing startups. If your answer is "we use synthetic fixtures," you have passed the
control; if your answer is silence, §2's erasure work must be redone against test data that has
leaked the same subjects.

### How the certificate stays alive: ISO/IEC 17021-1, the clocks

This is the part every vendor deck gets subtly wrong, because it is not in the standard you buy —
it is the standard the **certification body** is certified against. The verified rules:

- **The cycle is three years** (9.1.3, with a NOTE that an industry-specific scheme may set a
  different cycle). Initial certification is **Stage 1 → Stage 2**. Stage 1 is not a paperwork
  review: **9.3.1.3 g** requires the audit team to *"evaluate if the internal audits and management
  reviews are being planned and performed, and that the level of implementation of the management
  system substantiates that the client is ready for stage 2."* An ISMS that certified in March 2026
  (anyformat's Stage-2-complete date, per the blog cited in Sources) had to show internal audits and
  a management review **before** it was ever asked whether it was ready.
- **Surveillance: 9.1.3.3 verbatim** — *"Surveillance audits shall be conducted at least once a
  calendar year, except in recertification years. The date of the first surveillance audit following
  initial certification shall not be more than 12 months from the certification decision date."*
  Note which date starts the clock: the **decision**, not the certificate's print date.
- **What surveillance tests is enumerated — 9.6.2.2: each surveillance shall include:**
  *"a) internal audits and management review; b) a review of actions taken on nonconformities
  identified during the previous audit; c) complaints handling; d) effectiveness of the management
  system with regard to achieving the certified client's objectives and the intended results …;
  e) progress of planned activities aimed at continual improvement; f) continuing operational
  control; g) review of any changes; h) use of marks and/or any other reference to certification."*
  This eight-item list is the reason "we'll fix it before the surveillance visit" is not a strategy:
  (b) *is the review of last year's nonconformities* — the finding is on the record, and this year's
  auditor's job includes reading last year's record.
- **Major nonconformity has a hard clock: 9.5.3.2** — if the certification body cannot verify that
  corrections and corrective actions from a **major nonconformity** have been implemented **within
  six months after the last day of stage 2**, it shall conduct **another stage 2** before
  recommending certification. Not a gap-fill memo; a repeat of the substantive audit. And **9.4.9**:
  the CB *shall require the client* to analyse the causes of a nonconformity — "we patched it" without
  root-cause analysis is itself the finding.
- **Impartiality constrains your tooling choices: 5.2.6** — a certification body (and any part of the
  same legal entity or entities under its control) *"shall not offer or provide internal audits to
  its certified clients"*, with the stated mitigation that it shall not certify a system on which it
  provided internal audits for **two years** after. This is why your auditor and your internal-audit
  consultant cannot be the same brand, and why "compliance platforms that generate your internal
  audits *and* sell you the certificate" is a structural conflict, not a marketing flourish.
- **Change is a notification regime: 8.5.2 / 8.5.3** — the CB must give clients due notice of changes
  to certification requirements (which is how Amd 1:2024 reached your 4.1 paragraph), and the
  certified client must inform the CB of changes that affect the certification — the scope, the
  locations, the new Sweden inference path. An unannounced architecture change discovered at
  surveillance is a nonconformity *about notification*, on top of whatever it says about the change.
- **The certificate itself is a structured document (9.6.3 / certificate content list):** expiry or
  recertification-due date consistent with the cycle, a unique identification code, the standard and
  its issue status, and — the one to reread before every procurement reply — **the scope of
  certification**. Recertification (9.6.3.1) re-evaluates *all* requirements of the standard, not the
  delta since surveillance.

### Cycle versus period: the sentence that explains §9

Show an ISO auditor your 8.1 process for incident handling and your 9.2/9.3 records showing the
machine actually audited and reviewed itself, and the answer you get is about **the system**: *it is
designed and maintained to produce these outcomes, and here is the cycle proving it runs.* A SOC 2
Type II auditor (§9) asks for none of that as the primary object — the answer there is about **the
period**: *here are the tests performed between April and September, here are the exceptions.* Same
control, two epistemics. Vendors who internalise the first and are asked for the second produce
beautiful ISMS records and an empty test population, and vendors who internalise the second produce
test evidence and a management system that stops working in October.

### Trap answers

1. **"Our certificate covers the platform."** It covers **the scope printed on it** — read 4.3
   against the certificate before you say this to a bank. If the scope says "SaaS provisioned from
   Frankfurt" and the inference runs in Stockholm, the certificate is truthful and useless to the
   question asked.
2. **"We'll close the finding before the surveillance visit."** 9.6.2.2 b is *a review of actions
   taken on nonconformities identified during the previous audit*. The finding survives you; your
   closure of it gets *sampled*, and 9.4.9's cause analysis is part of what "closed" means.
3. **"17021-1 says internal audits at least every 12 months, so ours are due in twelve."** That is
   **10.2.6.3 — the certification body's own internal-audit rule about itself.** Your internal-audit
   duty is **ISO 27001 clause 9.2, "at planned intervals"**, and the planning must be defensible at
   9.3.1.3 g before Stage 2 even happens. Do not cite 10.2.6.3 to your auditor; it is a fun way to
   introduce yourself.
4. **"Annex A is the checklist; we implemented all 93."** Then you owe operating evidence 93 times
   per cycle. The 6.1.3 mechanism is *selection by risk with justification in the SoA* — the SoA is
   graded on both directions: exclusions need risk reasons, inclusions need evidence.
5. **"Stage 2 passed in March, so we have until March next year."** The surveillance clock runs from
   the **certification decision date** (9.1.3.3), the first surveillance must be within 12 months of
   it, and surveillance must happen at least once a calendar year except the recertification year —
   which means the calendar-year arithmetic, not your anniversary, schedules your year.

### The answer, stated

> ISO 27001 certifies **a management system with a printed scope**: clauses 4–10 are the
> requirements (context → scoped ISMS → risk-selected Annex A controls in the SoA → objectives →
> operational processes → internal audit and management review → corrective action), and the
> certificate is only ever worth the scope sentence on it. It stays alive on **17021-1's clocks** —
> surveillance at least once a calendar year and within 12 months of the decision date, the 9.6.2.2
> eight-item evidence list *including* last year's nonconformities, the six-month major-NC rule that
> can force a whole new Stage 2, and the two-party impartiality split at 5.2.6. The evidence it
> produces is **the cycle**: designed, operated, audited, reviewed, corrected. §9 is about a
> different object — the *period* — and that difference, not the logos, is what the bank is
> actually asking about when it asks for both.

The mechanisms this section audits are the ones from Part I: §0.1's custody model decides what the
scope sentence can honestly say; §3's key topology is the SoA's A.8.24/A.5.15 discussion in
engineering form; §4's `iam.py` boundary evaluation is A.5.18's "review, grant, revoke" operating as
a *mechanism*; the capstone's trail is A.8.15/A.8.16 evidence that has no policy substitute. If
those stages are passing, the ISMS is not paper — it is instrumentation. If they are not, the
certificate is a photograph of a gym membership.

---

## 9. SOC 2: what the bank asked for and you do not have.

**The scenario.** Read the anyformat trust center again: **ISO/IEC 27001:2022, held**; the March
2026 blog says *Stage 2 complete*; the subprocessor list says AWS Frankfurt (application and
backups), Azure Sweden (model inference, EU-resident), Datadog (telemetry, no customer documents),
GCP Gemini (no training on customer data). Now read the bank's questionnaire field: **"SOC 2 Type
II report — attach."** There is nothing to attach. Not a stale one, not a partial one — the
instrument does not exist, and this is not a paperwork failure, because the report is about a
**period that has not started being observed.** Everything below is why the difference between
"we have ISO" and "we have SOC 2" is not a logo question, and what you can actually deliver in the
next two quarters.

### The object: five categories, one criterion set, two opinions

SOC 2 is an **attestation engagement** performed under AICPA attestation standards against the
**Trust Services Criteria** (TSP Section 100, the 2017 Trust Services Criteria with the 2022
Revised Points of Focus). Structure, as `.06`/`.07` state it: there are **criteria common to all
five categories** — the *common criteria* — plus **category-specific** control-activity criteria.
The five categories: **Security** (the "Common Criteria", and the only mandatory one),
**Availability**, **Processing Integrity**, **Confidentiality**, **Privacy**.

The counts, enumerated from the criteria themselves: CC1.1–CC1.5 (5), CC2.1–CC2.3 (3),
CC3.1–CC3.4 (4), CC4.1–CC4.2 (2), CC5.1–CC5.3 (3), **CC6.1–CC6.8 (8)**, CC7.1–CC7.5 (5), CC8.1 (1),
CC9.1–CC9.2 (2) — **33 common criteria**. Category-specific: **A1.1–A1.3** (Availability, 3),
**C1.1–C1.2** (Confidentiality, 2), **PI1.1–PI1.5** (Processing Integrity, 5), and **Privacy, 26
criteria** in `.0`/`.1` pairs from P1.0 through P8.1. `(call)` on the arithmetic being derived by
enumeration of the published list rather than stated as a total by the AICPA.

Two sentences in the framework text decide most vendor scoping conversations, and both are
surprising:

1. **Privacy and Confidentiality are different objects.** The criteria say privacy applies **only to
   personal information**, while confidentiality covers *various types of sensitive information* —
   "Confidential information may include personal information as well as other information, such as
   trade secrets and intellectual property." A confidentiality scope is about *protecting* a
   designated class of information (C1.1 "identifies and maintains confidential information", C1.2
   "disposes of it"); a privacy scope is about the *information lifecycle and the data subject* —
   notice (P1.0/P1.1), choice and consent, collection, use and retention, disclosure, disposal,
   and, at P8.0/P8.1, "a process for receiving, addressing, resolving, and communicating the
   resolution of inquiries, complaints, and disputes from data subjects and others" plus periodic monitoring of
   privacy compliance. Most vendors scope **Security + Availability + Confidentiality**. A bank
   asking "do you have SOC 2 **for privacy**" receives a report that does not say, and the gap is
   not closable by an addendum — it is a different criterion set and a different engagement.
2. **Security needs no extra criteria; everything else does.** `.07`: the common criteria "are
   suitable for evaluating the effectiveness of controls to achieve an entity's system objectives
   related to security; **no additional control activity criteria are needed**." For availability,
   processing integrity, confidentiality and privacy, a *complete* set is the common criteria **plus
   that category's control-activity criteria**. Translation for a roadmap: adding **Availability** to
   a Security report is three extra criteria (A1.1 capacity monitoring, A1.2 backup and recovery
   infrastructure — "environmental protections, software, data backup processes, and recovery
   infrastructure" — A1.3 "tests recovery plan procedures") — cheap, and almost all of it is
   machinery §5 and §6 already forced you to build. Adding **Privacy** is 26 criteria about notices,
   consent, data-subject complaints and third-party disclosures — a different program with a legal
   department in it. `(call)` on the sequencing recommendation in §13: Security → Availability →
   Confidentiality is the growth path; Privacy is a destination only if buyers ask for it by name.

### Type I versus Type II: the same subject, different claims

Verbatim from the framework's own definitions: a **Type 2** engagement covers "the suitability of
design and operating effectiveness of controls **included in** management's description of a service
organization's system relevant to one or more of the trust services criteria over security,
availability, processing integrity, confidentiality, or privacy **throughout a specified period**
to achieve the entity's objectives based on those criteria in a type 2 SOC 2 engagement"; its report
"includes an opinion on the operating effectiveness of controls" and "**also includes a detailed
description of tests of controls performed by the service auditor and the
results of those tests**." A **Type 1** covers the same subject matter — the description and the
design suitability — but contains **neither** the operating-effectiveness opinion **nor** the
tests-and-results section.

That asymmetry is the whole commercial story: a Type I is a photograph of a design; a Type II is a
rating period. When a buyer says "give us SOC 2," roughly a third mean the photograph and the rest
mean the rating — which is why §13 sells the Type I first: same subject matter, weeks not months,
and it converts "we don't have it" into "we have this now and the period report lands in Q3." Do not
pretend the Type I answers the Type II question; the report explicitly lacks the tests.

**The observation period.** The AICPA sets **no minimum** period in TSP 100 — nothing in the
criteria text fixes three months or six or twelve. Market practice, stated as practice: reports
commonly cover 3–12 months, and a *first* Type II usually covers 3–6 months because buyers will not
wait a year and controls need enough iterations to be testable. `(call)` — flagged because it is the
single most commonly mis-cited number in vendor decks. The real constraint is arithmetic, not
regulatory: a control that operates monthly can be tested **once** in a three-month period and
**three times** in a nine-month one, and a "one sample, zero exceptions" result is the weakest
evidence in the report. Choose the period by counting how many times each control must run.

### The three artifacts that are not tests

Absent from the criteria document, present in every engagement, and governed by the **AICPA
attestation standards (AT-C 205, SSAE 18/21)** `(call)` — cite them as attestation standards, never
as TSP 100:

- **Management's system description.** The opinion is *on the description* as much as on the
  controls: the auditor opines whether the description presents the system fairly and whether
  controls were suitably designed **to achieve the stated commitments and system requirements**.
  Your commitments are what you wrote. Write the description as if a plaintiff will read it, because
  a procurement team will. This is where architecture decisions become contractual.
- **Subservice organisations: carve-out versus inclusive method.** AWS, Azure, GCP and Datadog are
  subservice organisations. Under the **inclusive method** their controls are described in your
  system description and tested in your engagement; under the **carve-out method** they are excluded
  from the description and from testing, and the complementary controls they provide are identified
  so the user entity can see what your report does *not* cover. `(call)` on the mechanism being an
  attestation-standards matter; on the strategy being a business decision, read the next section.
- **CUECs and CDCs.** Complementary user entity controls (and complementary subservice organisation
  controls): the criteria you do not meet alone — "the customer must configure bucket policies, must
  not disable the log stream, must rotate its own credentials." They exist because some system
  objectives are jointly achieved. They are also the section a bank's security team reads first and
  the section your sales engineer will be asked to explain, so they must be *true* and *actionable*,
  not boilerplate.

### The anyformat boundary problem, concretely

Four subservice boundaries exist today, and each is a scope decision with an evidentiary
consequence:

| Subservice | What it holds | Carve it out, and the buyer's auditor… | Include it, and you… |
|---|---|---|---|
| **AWS eu-central-1** | application data + backups (§0.1 custody, §2 restore, §5 replication) | tests nothing there — the report says nothing about the durability, restore or region-replication of the customer's own documents | must obtain and rely on AWS's own report and re-express the shared stack as your control environment |
| **Azure Sweden** | model inference over customer content (§0's trust boundary, §7's transfers) | cannot see where the personal data goes — precisely the question §7's 28(3)(a) and DORA 30(2)(b) ask | cannot test controls over a platform you do not administer; you would need the provider's report and a contractual right to it |
| **Datadog** | telemetry, no customer documents | cannot evaluate whether logs leak field contents (A.8.11, §6's data-event line) | takes on monitoring-scope evidence for a vendor you do not configure end to end |
| **GCP Gemini** | inference, contractually no training on customer data | cannot evaluate the "no training" commitment, which is a *promise in your DPA* | must evidence a control whose mechanism is someone else's API configuration |

The honest shape, which is what §13's Type I should say: **carve out the infrastructure and the model
providers, and state explicitly that the customer's data at rest lives inside a carved-out
boundary** — which means the criteria most likely to be questioned are exactly the ones you cannot
prove alone (CC6.1 over AWS's infrastructure, C1.2 disposal of documents Azure's inference handled),
unless you describe them as **jointly achieved, with the complementary controls named**. That
sentence — *"the system relies on subservice organisations X, Y and Z, whose controls are outside the
scope of this report; the complementary controls they provide are: …"* — is the difference between a
report that survives a bank's reading and one that triggers a second questionnaire.

And now the **gap**, stated in the currency of the object. Today anyformat can hand a bank **a
certificate** (an ISMS attestation with a printed scope), **a Stage-2 window from March 2026**, and
**annual surveillance samples**. A SOC 2 Type II is **a period of testing with published per-test
results**. Those are not versions of the same thing: the first two are *inputs* to a Type II
conversation, not a substitute for it, and the observation period has not begun. Which is why "we
have ISO, we're working on SOC 2" must be answered — in your own proposal, before the buyer asks —
with a date for the Type I and a chosen period for the Type II.

### The criteria Part I already built mechanisms for

| Criterion | Verbatim core | Your mechanism |
|---|---|---|
| CC6.1 | "implements logical access security software, infrastructure, and architectures over protected information assets to protect them from security events **to meet the entity's objectives**" | §0.1's CMK choice; §5's encryption in transit |
| CC6.2 | "Prior to issuing system credentials and granting system access, the entity registers and authorizes new internal and external users **whose access is administered by the entity**" | §4's provisioning discipline |
| CC6.3 | "authorizes, modifies, or removes access to data, software, functions, and other protected information assets based on roles, responsibilities, or **the system design and changes**, giving consideration to the concepts of **least privilege and segregation of duties**, to meet the entity's objectives" | `solutions/iam.py:190` `evaluate_with_boundary` — identity **and** boundary as an AND-of-two-evaluations; "a permissions boundary never grants, it only subtracts" is this criterion in arithmetic form |
| CC6.6 | "implements logical access security measures to protect against threats from sources outside its system boundaries" | §4's VPC endpoint conditions |
| CC6.7 | "restricts the transmission, movement, and removal of information to authorized internal and external users and processes, and protects it during transmission, movement, or removal **to meet the entity's objectives**" | §5's replication decision, in criterion form: *movement is a controlled act* |
| CC7.1 | detection and monitoring procedures to identify "(1) **changes to configurations that result in the introduction of new vulnerabilities**, and (2) susceptibilities to newly discovered vulnerabilities" | §6's trail plus config monitoring |
| CC7.2 | "monitors system components … for anomalies that are indicative of malicious acts, natural disasters, and errors …; anomalies are analyzed to determine whether they represent security events" | the **analysis** step is what makes this a control rather than a log |
| CC7.4 | "responds to identified security incidents by executing a **defined incident-response program** to understand, contain, remediate, and communicate security incidents" | §6's 03:00 clocks, verbatim |
| CC7.5 | "identifies, develops, and implements activities to **recover** from identified security incidents" | §2's restore-from-backup path |
| CC9.1 | "identifies, selects, and develops risk mitigation activities for risks arising from **potential business disruptions**" | §5's region strategy |
| CC9.2 | "assesses and manages risks associated with **vendors and business partners**" | the subprocessor table above |
| C1.2 | "disposes of confidential information" | §2's purge; stage 8's markers |
| A1.2 / A1.3 | backup and recovery infrastructure; "**tests recovery plan procedures** supporting system recovery" | §5 plus §2 — and A1.3's evidence is a *restore test record with a date* |

Read the last column as the punchline: every row's mechanism already exists in a passing solution,
because these criteria describe the same physics §7's Art. 32 describes in legal language. The
missing thing is not the control. The missing thing is **the evidence engine** — the tickets, the
sampled test results, the dated restore runs, the ticket-to-trail joins — and the period over which
it has been running.

### Trap answers

1. **"Our ISO certificate is a Type II, effectively."** It contains no period, no tests and no
   published results. The buyer's question — *what happened between April and September* — is not
   answerable by an ISMS attestation. §8's cycle and §9's period are different objects.
2. **"We scope Security and Confidentiality, so privacy is covered."** Confidentiality protects a
   class of information; privacy is 26 criteria about notices, choice, consent, data-subject
   complaints and disclosure. §7's Art. 28 duties map to *privacy* language far more directly than to
   C1.1/C1.2.
3. **"A three-month Type II is as good as a twelve-month one."** Same claim, thinner sampling. The
   period's only job is to give each control enough iterations to be testable; the report shows the
   population, and a monthly control with one sample is visibly weak.
4. **"We carve out AWS, so the report covers our controls."** A carve-out means *the auditor tested
   nothing there* — and the customer's data at rest lives there. If the description does not name the
   complementary controls, the buyer fills the gap with a follow-up questionnaire, which is the
   outcome you bought a report to avoid.
5. **"Sales says we're SOC 2 compliant."** There is no such state: no certificate, no registered
   mark, no list of compliant vendors. There is a report, an opinion, a period and a description.
   `(call)` — treat "SOC 2 compliant" in your own marketing as a defect to fix, not a branding choice.

### The answer, stated

> SOC 2 is an **attestation on a description of your system over a period**: 33 common criteria plus
> the specific criteria of every category you chose, an auditor's opinion, and — in a Type 2 only —
> the tests performed and their results. **Security is the mandatory category and needs no extra
> criteria; Availability adds three; Confidentiality adds two; Privacy adds 26 and a second
> program.** The three things outside the criteria that decide the report are the system description,
> the subservice boundary method (inclusive versus carve-out) and the complementary controls — all
> governed by the attestation standards, not by TSP 100. The AICPA sets no minimum observation
> period; the market sets the length, and the arithmetic that sets it is how many times each control
> runs inside the window. anyformat's actual position: mechanisms complete, evidence engine not yet
> running, no period started, no report. That is fixable in the order §13 gives, and it is not
> fixable by waiting for the next surveillance audit.

The stages this report would test: §4's `evaluate_with_boundary` for CC6.3's least privilege; the
capstone's `cloud.audit` trail — `solutions/capstone.py:53`, where every authorization decision
appends `ALLOW`/`DENY` with principal, action and resource — for CC7.1 through CC7.5; §2's
version-purge and §0.3's crypto-shredding for C1.2; §5's replication and §6's tested restore for
A1.2, A1.3 and CC9.1. The gap is not that those stages were hard. It is that passing them produced
*working code*, where the buyer needs *dated test results from an independent party across a period*.
That is a program with a calendar, and §13 is that calendar.

---

## 10. The crosswalk: one artifact, four audits — and the three places it fails

**The scenario.** The GRC tool advertises "map once, satisfy everything." A security engineer
builds the mapping, gets a tidy grid, and then a bank's DORA questionnaire, a European
data-protection review, and a SOC 2 fieldwork request arrive *in the same month* — and the tidy
grid turns out to be a graph with cycles in the wrong places: the same log line is needed by four
frameworks with **three different retention answers** and **two incompatible notions of what good
evidence is**. The crosswalk is real and worth building. It is also where the honest engineer stops
believing the marketing version.

### The four frameworks in one sentence each, so the mapping means something

| Framework | Object it certifies or demands | Who checks | Time unit |
|---|---|---|---|
| **GDPR** | the *lawfulness of processing* — a legal regime, not a certifiable scheme (Arts. 40/42 give voluntary instruments; §7's 28(5) says what they are worth) | supervisory authority, data subject, court | the request clock (12(3)) and the breach clock (33) |
| **ISO 27001** | the **management system** with a **printed scope** | certification body under ISO/IEC 17021-1 | the **cycle**: surveillance ≥ once a calendar year, three-year recertification |
| **SOC 2** | **management's description of the system** and the controls' design (Type 1) and operating effectiveness (**Type 2**) | independent CPA firm under AICPA attestation standards | the **period**, with sampled tests and published results |
| **DORA** | the financial entity's **digital operational resilience**, delivered *through you* by contract | the entity, its auditors, the competent authority, and for designated providers the **Lead Overseer** | statutory clocks: 24 h to classify, 4 h / 72 h / one month to report, annual register |
| **AI Act** | the **AI system** — its classification, and provider or deployer obligations | market-surveillance authority; notified bodies for conformity assessment | a phased application calendar (§11), six-month deployer log floor |
| **ISO 42001** | the **AI management system (AIMS)**, same HLS spine as 27001 | certification body | the same cycle machinery, extended scope |

### The grid: one artifact, every buyer

Read the cells as *what you hand over*, not what you believe. Built from anyformat's live state:
one data platform, four frameworks, six evidence artifacts.

| Artifact you maintain | SOC 2 (criterion) | ISO 27001 (Annex A) | GDPR (article) | DORA (article) | AI Act (article) |
|---|---|---|---|---|---|
| **Data-event audit trail** (who decrypted which encryption context, `capstone.py:53`-style append, A.8.17-synchronised clocks) | CC7.1, CC7.2, CC7.4 | A.8.15 Logging, A.8.16 Monitoring, A.5.28 Collection of evidence, A.5.7 | 30(1)(g) TOM description, 33(5) breach record, 5(2) accountability | 30(3)(e) audit/inspection rights reach it; 17 + RTS 2024/1774 incident recording; 13(2) post-incident review | **12** automatic recording of events; **26(6)** deployer keeps logs **≥ 6 months** |
| **Key policy + boundary evaluation** (`kms.py`, `iam.py:190`) | CC6.1, CC6.3, CC6.6 | A.5.15/A.5.18, A.8.2, A.8.24 | 32(1)(a) encryption, **4(5)** pseudonymisation + Recitals 26/28/29 (EDPB Guidelines **01/2025** on pseudonymisation is a Jan-2025 consultation draft `(call)`) | 30(2)(c) confidentiality/integrity/availability of the service | 15 cybersecurity for high-risk systems; 9 risk management |
| **Delete markers + version purge + crypto-shred** (stages 8, 29–32) | C1.2 disposal | A.8.10 Information deletion, A.8.12 DLP, A.5.33 Protection of records | **17** erasure, **18** restriction, **19** notify recipients, 28(3)(g) delete or return | 30(2)(d) "access, recovery and return in an easily accessible format" | 10 data governance (quality of what is kept and what is removed) |
| **Subprocessor table + DPA flow-down** (AWS / Azure Sweden / Datadog / Gemini) | CC9.2, and the system description's boundary decision | A.5.19–A.5.23, A.5.21 ICT supply chain | 28(2) authorisation + 28(4) full liability + 28(3)(d) | **28(3) register entry**, 29(1) concentration, 29(2) third-country subcontracting, 30(2)(a) subcontracting conditions | **25(1)** who becomes the provider; 53(1)(b) GPAI downstream information |
| **Incident runbook + restore test records** (§6, §2, A1.3-style restore evidence) | CC7.4, CC7.5, A1.2, A1.3 | A.5.24–A.5.30, A.8.13 backup | 32(1)(c) restore, 33/34 notification, 35 | **11** response and recovery, **12** backup/restoration, **17** incident management + classification, **13(2)–(4)** learning, **26–27 TLPT** participation, 30(3)(c)/(d) | 72 post-market monitoring; 73 serious-incident reporting |
| **Risk register + SoA + risk treatment plan** | CC3.1–CC3.4, CC9.1 | 6.1.2/6.1.3, 8.2/8.3, 9.3 | 24 (with 25), 35 DPIA | 5–6 ICT risk framework and strategy, 8 identification, 15 tested plans | **9** risk management system; 42001 A.5 AI risk assessment |
| **Classification memo for the scoring step** (§11's Art. 6(3) analysis) | — no criterion | — no Annex A control; it is a 4.1/6.1 input | 22 analysis, 35 DPIA input | — | **6(3) + 6(4) + 49(2)**: document, register the non-high-risk conclusion; 27 FRIA if the deployer is in 5(b)/5(c) |

Three readings of that table. **First**: the row you maintain daily covers four audits — one trail
is CC7.2 and A.8.16 and Art. 33(5) and AI Act Art. 12 simultaneously, which is the strongest
argument for building it as instrumentation rather than as compliance work (Part I's whole thesis).
**Second**: the last row is the counterexample — a high-quality Art. 6(3) classification memo has
**no** SOC 2 criterion and **no** Annex A control. It is not "already covered"; it is new work, and
the frameworks that miss it are the ones whose questionnaires will ask for it anyway. **Third**: the
crosswalk is not symmetric — DORA's 30(3)(e) access right reaches further than any SOC 2 sampling
window, and AI Act's 26(6) sets a *floor on retention* where GDPR sets a *ceiling*.

### The three divergences a mapping tool will hide from you

**1. Retention: five authorities, five different answers about the same log line.**

| Authority | The number | The direction |
|---|---|---|
| AI Act 26(6) + **19(1)** | deployer-generated logs "under their control" kept **at least six months**, "unless provided otherwise in applicable Union or national law, in particular in Union law on the protection of personal data" — and 19(1) puts the **same six-month floor on the provider** for the Art. 12(1) logs it controls, so both sides of your DPA owe it | **floor** |
| GDPR 5(1)(e) + Recital 26 | no longer than necessary; 33(5) expects the breach record for the incident population; 30(1)(f) wants *envisaged erasure time limits* | **ceiling** |
| DORA | register of information updated **annually** and on change (28(3) + IR 2024/2956); final incident report at **one month** (JTRS/ITS); TLPT documentation held for the authority-validated scope | **cadence** |
| SOC 2 Type II | evidence must exist **across the chosen period** and be reproducible to the auditor for that period | **window** |
| ISO 27001 | A.5.33 protection of records + your own documented retention; surveillance samples the *cycle* | **your policy, audited** |
| AML / 4AMLD, national law | multi-year statutory retention of identity and transaction records, held **by the controller**, which is why 28(3)(g) says "unless Union or Member State law requires storage" | **floor, someone else's** |

The failure mode is a single platform-wide default. "We keep everything for seven years" satisfies
the AML floor and the AI Act floor and *violates* Art. 5(1)(e) for the personal-data population,
while "we purge at 13 months" satisfies minimisation and *destroys* the last month of a
12-month SOC 2 period you signed before you purged it. The engineering answer is not one number: it
is **retention classes with per-class justification** (documents vs. audit trail vs. breach record
vs. AI-event logs vs. financial records), each wired to the mechanism that actually enforces it —
which is §3's key granularity for shredding, §2's version purge for objects, and A.5.33's protection
for records you must keep. `(call)` on the specific matrix being yours to produce; on the fact that
a single default retention period is a finding somewhere.

**2. Evidence epistemics: population versus sample versus cycle.** GDPR asks about **the data
subject** — 12(3) counts *requests*, 17 counts *records*, and there is no statistical sampling in
the Regulation. SOC 2 asks about **the population within a period** and the auditor's *sample* from
it; a control that ran but was not sampled is untested, and a control that was sampled once in three
months is weakly tested. ISO 27001 asks about **the system**: design, operation, internal audit,
management review, corrective action, and the record of all of it across the cycle. DORA asks about
**the register and the contract and the test** — including 30(3)(e)'s right to inspect with copies of
documentation on-site, which is neither a sample nor a certificate. The consequence: **the same
delete-purge mechanism must be provable four ways** — a per-subject case log (GDPR), a dated test
with results (SOC 2), a process with an internal audit and a corrective-action record (ISO), and an
inspector-accessible artifact (DORA). Build the evidence once, but build it with all four consumers
in mind, because retrofitting a sample into a case log is how you end up with an export nobody can
attest to.

**3. Key custody: the frameworks take opposite positions, and you cannot satisfy all four by
architecture alone.** §0.2's three custody models — customer-managed keys in their account, your
keys with the customer's policy attached, and keys you hold entirely — get different answers from
each regime:

- **GDPR / EDPB favour you *not* holding plaintext capability.** Art. 32(1)(a) encryption and
  pseudonymisation are named measures; Art. 4(5) defines pseudonymisation as processing where data
  "can no longer be attributed to a specific data subject without the use of additional information",
  kept separate under technical and organisational measures, and Recitals 26/28/29 treat the
  separation of key from data as the mechanism that reduces identifiability. Strong
  custody separation is a *compliance asset* in this frame, and it is the argument behind §3's
  per-tenant keys.
- **DORA favours *recoverability regardless of you*.** 30(2)(d): the contract must stipulate
  "provisions on ensuring access, recovery and return in an easily accessible format of personal and
  non-personal data processed by the financial entity in the event of the insolvency, resolution or
  discontinuation of the business operations of the ICT third-party service provider, or in the event
  of the termination of the contractual arrangements". A custody model whose only unlock is *your* HSM, reachable only
  *by your* staff, is an availability risk to the bank and a 30(2)(d) problem. The regulator's
  preferred shape is a documented escrow or a customer-held key, not vendor-side heroics.
- **SOC 2 favours *provable and monitored* custody.** CC6.1/CC6.3/CC6.6/CC6.7 do not care who owns
  the key; they care that access to it is authorised, role-scoped, least-privilege, monitored from
  outside the boundary, and *tested during the period*. Customer-managed keys in the customer's own
  account can be the *worst* SOC 2 outcome for you, because the controls the report needs are in
  someone else's environment — the §9 boundary problem in its purest form.
- **ISO 27001 favours *a policy that says which*, applied to your scope.** A.8.24 (use of
  cryptography) and A.5.23 (cloud services) require rules; the certificate only guarantees what the
  scope sentence covers.

The resolution is a decision, not a derivation: pick the custody model per **data class**, document
it as the *chosen answer to four different questions*, and make sure the mechanism you chose has
evidence for each of them — an escrow runbook for DORA, boundary policy plus trail for SOC 2, SoA
entry for ISO, and the identifiability argument for GDPR. `(call)` on that being the correct reading
of the tension; `(citation)` on the four instruments themselves.

### Trap answers

1. **"Our mapping tool handles it — one control, four frameworks."** Mapping tools collapse
   *retention* and *epistemics*. Art. 5(1)(e)'s ceiling and AI Act 26(6)'s floor on the same log
   stream are not one control, and DORA's access right is not a SOC 2 sample. The table above is
   what "handled" would have to mean.
2. **"ISO 27001 is the superset; SOC 2 is just a US report."** The certificate has no period and no
   published test results; the report has no management-system opinion and no printed scope in the
   ISO sense. Neither covers the other's object (§8's cycle vs §9's period). Ask a bank which
   document its *audit committee* wanted and the argument ends.
3. **"The AI Act is covered by our risk register."** 6(3)/6(4)/49(2) — analyse, document *before*
   placing on the market, **register the conclusion** — plus Art. 12 event logging and 26(6) log
   retention are obligations with no ISO/SOC 2 analogue, and the deliverable is a *classification*,
   not a risk score. §11.
4. **"DORA is the bank's problem."** Art. 30(2)/(3) terms must appear **in the contract with you**,
   28(3) puts you in the bank's register, 26(3)/(4) obliges the entity to secure your **participation
   in TLPT**, and the CTPP designation list names your own infrastructure providers (§12). The bank's
   problem arrives as your contract clause.

### The answer, stated

> Map the **artifacts**, not the controls: the audit trail, the key policy, the purge mechanism, the
> subprocessor table, the runbook-plus-restore-records, the risk register and SoA. Six artifacts
> answer most of four audits, and maintaining them once is why Part I exists. But name the three
> divergences on the same page you show the buyer: **retention is five different directions on one
> log line**, **evidence means population vs sample vs cycle vs inspection right**, and **the
> frameworks disagree about who should hold your keys**. Then add the row that has no equivalent:
> the AI Act Art. 6(3) classification memo, which no SOC 2 criterion and no Annex A control will
> ever produce for you.

This section is the index for §7–§9 and §11–§12; the mechanisms it tabulates were built in §0–§6 and
traced in "The map" below. Read the divergences as the specification for the retention classes: the
artifact that satisfies four frameworks is the one whose *per-class rules* were written down before
someone asked.

---


## 11. The AI Act, and the standard that certifies your answer

**The scenario.** The bank's AI questionnaire has a new first question, added after March 2025 and
now present in every EU financial-services RFP: *"What is the risk classification of the AI system
used in our processes, under Regulation (EU) 2024/1689, and who is the provider?"* Sales answers
"we are not an AI company, we use models." Legal answers "high-risk? probably not." Nobody has a
document. The question is answerable — but only by someone who has done the Art. 6 analysis and can
show it, and the calendar on which the answer becomes mandatory has moved twice in eighteen months.
This section is the classification analysis, the amended dates, and the certifiable wrapper (§'s
other half: **ISO/IEC 42001**) that lets you answer it with an artifact instead of an opinion.

### The calendar, as amended — because your vendor deck is out of date

The Act is Regulation (EU) 2024/1689. The consolidation that matters is **Regulation (EU) 2026/1744,
in force since 2026-07-27** (CELEX 02024R1689-20260727), which rewrote several application dates.
The live table:

| Date | What applies | The consequence for a document-processing vendor |
|---|---|---|
| **2025-02-02** | Chapters I and II: definitions, scope, **Art. 5 prohibitions**, AI literacy (Art. 4) | Already binding. The Art. 5 list is the only part of the Act that can end a product feature outright |
| **2025-08-02** | GPAI obligations (Chapter V), governance, notified bodies, penalties except **Art. 101** (GPAI fines) | GCP/Azure/OpenAI's Art. 53 duties are live now. Your upstream documentation requests have a legal hook |
| **2026-07-27** | 2026/1744 in force; **Art. 4 rewritten** — measures to support staff AI literacy, dropping the 2024 duty's own words "ensure, to their best extent, a sufficient level of AI literacy" | The AI-literacy training evidence you built for DORA 13(6) and ISO 7.3 is now ahead of the Act, not behind it |
| **2026-08-02** | General application, incl. **Art. 50** transparency; Art. 101 GPAI fines | **High-risk obligations do NOT start here.** This is the date almost every vendor deck still carries, and it is the one that got moved |
| **2026-12-02** | New prohibitions Art. 5(1)(ba) intimate image / (bb) CSAM; **Art. 50(2)** synthetic-content marking deadline for systems placed on the market before 2026-08-02 | If you generate or modify document images, marking obligations have a hard date, and legacy systems get it later than new ones |
| **2027-08-02** | Legacy GPAI models placed before 2025-08-02 must comply (111(3)) | Your upstream model vendor has a documented compliance deadline you can cite in a request |
| **2027-12-02** | **Annex III high-risk obligations — Chapter III sections 1–3** (moved from 2026-08-02) | *This* is the deadline for the classification analysis to exist, if your product is in Annex III |
| **2028-08-02** | **Annex I / Art. 6(1) high-risk** (products under Union harmonisation legislation; moved from 2027-08-02) | Irrelevant to SaaS document processing, relevant if you embed in a regulated product |
| **2030-08-02** | Public-authority-operated high-risk systems already on market (111(2)) | Relevant when a Member-State ministry is the customer |
| **2030-12-31** | Annex X systems (large-scale IT systems) | Not your market |

Legacy rule to state precisely: systems placed on the market **before** the relevant date are caught
only upon **significant change in design**, with the cut-off being the date the relevant part of
Chapter III applies. "We shipped it in 2024" is a *conditional* defence, and a model swap is exactly
the change that tests it. `(call)` on whether replacing your Gemini model version is a significant
design change — argue it, document it, and note it in the register.

Two more sentences worth having ready: the Act applies to providers placing systems on the market or
putting them into service in the Union, "**irrespective of whether those providers are established
or located within the Union or in a third country**" (Art. 2(1)(a)) — the extraterritoriality
mirror of GDPR Art. 3(2) — and **Art. 99(1)** obliges
Member States to set penalties that are "effective, proportionate and dissuasive", "taking into
account the interests of SMEs, including start-ups, and their economic viability." That clause is
real and is not a licence: the amounts in 99(3)–(5) are ceilings set as percentages of turnover for
a reason.

### The classification, as analysis — with the counterargument column

anyformat's product: ingest a customer document, extract structured fields, hand a human an
extraction with confidence scores; optionally the extracted fields feed a credit decision. Ask the
question in the Act's order.

**Step 1 — is it Annex III at all?** The nearest entry is **point 5**, and its sub-points matter:
5(a) eligibility for essential public assistance benefits; **5(b) "AI systems intended to be used to
evaluate the creditworthiness of natural persons or establish their credit score, with the exception
of AI systems used for the purpose of detecting financial fraud"**; 5(c) risk assessment and pricing
in life and health insurance; 5(d) emergency-call triage. Note the two boundary conditions that
decide your case: 5(b) is about **natural persons'** creditworthiness, and it **carves out fraud
detection**. **Recital 58** confirms it in its own words: AI systems "provided for by Union law for
the purpose of detecting fraud in the offering of financial services and for prudential purposes to
calculate credit institutions' and insurance undertakings' capital requirements should not be
considered to be high-risk". If the pipeline is used for AML/KYC document screening on a *corporate*
customer, 5(b) is not the trigger; if it scores an individual's credit, it is squarely the trigger.

**Point 1 — biometrics.** The Act's first Annex III point covers remote biometric identification,
biometric categorisation and biometric identification systems. But **Recital 15** is explicit that
"remote biometric identification" **excludes** biometric verification — "This excludes AI systems
intended to be used for biometric verification, which includes authentication, whose sole purpose is
to confirm that a specific natural person is the person he or she claims to be and to confirm the
identity of a natural person for the sole purpose of having access to a service, unlocking a device
or having security access to premises." A face-match of a selfie against the ID photo to onboard a
customer is **verification**, not remote biometric identification. `(call)` — that is the strongest
reading, and it is an argument, not an exemption list; state it in the memo and cite the recital.

**Step 2 — the Art. 6(3) derogation.** Even inside Annex III, a system "shall not be considered to be
high-risk where it does not pose a significant risk of harm to the health, safety or fundamental
rights of natural persons, **including by not materially influencing the outcome of decision
making**" — and that first subparagraph applies only "where any of the following conditions is
fulfilled": (a) "the AI system is intended to perform a narrow procedural task"; (b) it "is intended
to improve the result of a previously completed human activity"; (c) it detects decision-making
patterns or deviations from prior decision-making patterns "and is **not meant to replace or
influence** the previously completed human assessment, **without proper human review**"; or (d) it is
intended to perform a preparatory task to an assessment relevant for the Annex III use cases.
**Recital 53** gives its own examples for (a): "an AI system that transforms unstructured data into
structured data, an AI system that classifies incoming documents into categories or an AI system that
is used to detect duplicates among a large number of applications" — that is a description of document
extraction — and glosses "not materially influence the outcome" as having no impact "on the substance,
and thereby the outcome, of decision-making, whether human or automated."

**And the override**: a system that **profiles natural persons always counts as high-risk**,
whatever the four conditions say.

| The claim you would make | The strongest fit | The counterargument the bank's counsel will raise |
|---|---|---|
| "Extraction is a preparatory task feeding a human assessment." | **6(3)(d)** — preparatory task to an assessment relevant to Annex III 5(b) | The human reviewer is in *your* UI with a confidence score and one button; the extraction is the substance of the assessment, so it materially influences the outcome → derogation fails at the gate, not at (d) |
| "We structure unstructured data." | **6(3)(a)** narrow procedural, on the recital's own example | (a) survives only if the fields extracted do not *decide* anything; extract "employment status" and "existing debt" into a credit workflow and the narrowness is nominal |
| "We catch human error." | **6(3)(b)/(c)** improve a completed human activity / detect deviation with proper human review | 6(3)(c)'s own words require it not to replace or influence the human assessment **without proper human review** — so the derogation's validity *is* your human-review feature's quality. A sampled exception in the SOC 2 period becomes evidence against the classification |
| "We don't profile." | avoids the override | If any field feeds a scoring model about an individual, that is profiling — and profiling is what §7's Art. 22 and 35(3)(a) language describes, in the same words |

**The part almost nobody implements: the derogation is a registered artifact, not an opinion.**
**Art. 6(4)**: "A provider who considers that an AI system referred to in Annex III is not high-risk
shall **document its assessment before that system is placed on the market or put into service**. Such
provider shall be subject to the registration obligation set out in Article 49(2). Upon request of
national competent authorities, the provider shall provide the documentation of the assessment."
In short: the provider who concluded, under 6(3), that an Annex III system is **not** high-risk must
**register themselves and that system in the EU database** (Art. 71). Registration (49(1)) is the
rule for Annex III systems before placing
on the market, except point 2, with 49(4) putting certain fields in a secure
non-public section and 49(5) handling point-2 systems nationally. Commercial reading: **the
classification memo plus its registration number is a deliverable you can attach to the
questionnaire**, and it is the only version of "we analysed this" that a market-surveillance
authority will recognise. Writing the analysis in a wiki page is not compliance with 6(4); it is a
draft.

### If the classification flips, what lands

Say the bank wires the extraction output straight into an automated credit decision. Then the system
is used for 5(b) purposes and the derogation collapses. What arrives, in order:

- **Provider obligations** (Art. 16, via the Chapter III sections): **Art. 9** risk management
  system — "established, implemented, documented and maintained" as a "continuous, iterative
  process"; **Art. 10** data and data governance; **Art. 11** technical documentation (Annex IV);
  **Art. 12** automatic **recording of events (logs)** over the lifetime, for (a) situations that may
  result in an Art. 79(1) risk or a substantial modification, (b) facilitating Art. 72 post-market
  monitoring, and (c) monitoring the functioning; **Art. 13** transparency and information to
  deployers; **Art. 14** human oversight by natural persons during the period of use with appropriate
  human-machine interface tools; **Art. 15** accuracy, robustness and cybersecurity; **Art. 17**
  quality management system; **Art. 43** conformity assessment; **Art. 48** CE marking (digital CE
  marking for digitally provided systems) and the corresponding declaration of conformity.
- **Art. 25(1) — the flip that is actually a contract clause.** A distributor, importer, deployer or
  other third party becomes the **provider**, with Art. 16's obligations, where it (a) puts **its own
  name or trademark** on a high-risk system already on the market — "**without prejudice to
  contractual arrangements stipulating that the obligations are otherwise allocated**" — (b) makes a
  substantial modification to a high-risk system that remains high-risk, or (c) modifies the intended
  purpose so it is no longer high-risk. Read (a) as what it is: if the bank white-labels your
  extraction into its credit process, *it* inherits the provider's obligations **unless your contract
  reallocates them** — and reallocating them means you are contractually the provider of a high-risk
  system, with Art. 16 duties, in the EU database, under Art. 99(4)(a) penalty exposure. This is a
  clause negotiation, not a footnote.
- **The deployer's duties arrive in your contract.** Art. 26 obligations are the bank's — use per
  instructions, human oversight by competent staff, input data relevance, monitoring operation, and
  **26(7)**: before workplace use, employer deployers "shall inform workers' representatives **and
  the affected workers**" that they will be subject to the high-risk AI system. Two paragraphs have
  vendor consequences: **26(5)** — suspend use and notify provider, distributor and market
  surveillance where use "may result in that AI system presenting a risk within the meaning of
  Article 79(1)" — and, for financial-institution deployers, the **monitoring obligation set out in
  the first subparagraph** "shall be deemed to be fulfilled by complying with the rules on internal
  governance arrangements, processes and mechanisms pursuant to the relevant financial service law";
  and **26(6)** — deployers keep the automatically generated logs "**to the extent such logs are
  under their control**", for a period appropriate to the intended purpose, "of at least six months,
  **unless provided otherwise in applicable Union or national law, in particular in Union law on the
  protection of personal data**", with financial-institution deployers required to "maintain the logs
  as part of the documentation kept pursuant to the relevant Union financial service law".
  Deemed-fulfilment covers *monitoring*, not the log-keeping — and it means the bank cannot
  discharge the duty by pointing at its own DORA program in the abstract: it needs *your* logs,
  *your* instructions for use, and *your* monitoring hooks, because the DORA program is what
  consumes them. Name that mechanism in the DPA and you will be asked for it before the
  classification question is even live.
  The bridge to Part I's GDPR section is **26(9)**: deployers "shall use the information provided
  under Article 13" of the Act "to comply with their obligation to carry out a data protection
  impact assessment under Article 35" of the GDPR — so your Art. 13 documentation is *also* the
  bank's DPIA input, one artifact, two regulators.
- **Art. 27 FRIA — the bank owes an assessment, and it will ask you for the inputs.** Fundamental
  rights impact assessments are required for bodies governed by public law, private entities providing
  public services, and **deployers of Annex III point 5(b) and 5(c) systems** — which is precisely the
  creditworthiness case. The six items include the description of processes, the periods and
  frequency of use, categories of natural persons concerned, and the appropriate measures. Your
  Art. 13 deployer information and your logging design are inputs to their FRIA. There is **no ISO
  control and no SOC 2 criterion** that produces this (§10's last row).
- **Art. 50(1)** — providers of systems intended to interact directly with natural persons must
  design and develop them so those persons "are informed that they are interacting with an AI system,
  **unless this is obvious from the point of view of a natural person who is reasonably well-informed,
  observant and circumspect**, taking into account the circumstances and the context of use." Live
  since 2026-08-02. If your product has a chat-with-your-documents surface, that is a UI requirement
  with a date on it — and the "unless obvious" carve-out is where your copywriter earns a salary —
  and 50(2)'s marking duty for synthetic content has its own 2026-12-02 legacy deadline.

**Penalties, with the split that decides who is fined.** **99(3): €35M / 7%** for Art. 5 prohibited
practices. **99(4): €15M / 3%** for non-compliance with (a) **Art. 16 provider obligations**,
(b) Art. 22 authorised representatives, (c) Art. 23 importers, (d) Art. 24 distributors, (e) **Art. 26
deployers**, (f) Art. 31 and 33(1)/(3)/(4) and Art. 34 notified bodies, (g) **Art. 50 transparency
obligations**. **99(5): €7.5M / 1%** for supplying incorrect, incomplete or misleading information to
notified bodies or competent authorities in reply to a request. **99(6)**: for SMEs including
start-ups, each fine is "up to the percentages or amount referred to in paragraphs 3, 4 and 5,
**whichever thereof is lower**" — the ceiling that moves, not a discount line. The 99(5) sentence is
the vendor-relevant trap: an Art. 6(3) conclusion presented to an authority as settled analysis, when
the assessment was never documented as 6(4) requires, is *misleading information*, priced separately
from the classification being wrong.

### The GPAI chain: what to demand in writing, from whom

anyformat's inference runs on Azure (EU-resident) with GCP Gemini, and the contract says "no training
on customer data." Those model providers are **GPAI model providers**, and their obligations have been
live since **2025-08-02**:

- **Art. 53(1)(a)** — maintain technical documentation, including the training and testing process and
  evaluation results, minimum content per **Annex XI**, to be provided to the AI Office and national
  competent authorities on request.
- **Art. 53(1)(b)** — provide **information and documentation to downstream providers** (that is you)
  so they understand capabilities **and limitations** and can comply with their own obligations;
  minimum content per **Annex XII**. This is the clause your vendor questionnaire should quote.
- **Art. 53(1)(c)** — a **copyright policy**, including to identify and comply "in accordance with
  Union law, including through state-of-the-art technologies," with reservations of rights expressed
  under **Art. 4(3) of Directive (EU) 2019/790** (the TDM opt-out).
- **Art. 53(1)(d)** — a **publicly available, sufficiently detailed summary about content used for
  training**, per the AI Office template.
- **Art. 55** — systemic-risk GPAI: model evaluations and the rest, relevant only if you route to a
  frontier model with that designation; legacy models placed before 2025-08-02 must comply by
  **2027-08-02** (111(3)).

So the four written asks of anyformat's upstream, in the order that costs the least to obtain: (1)
the **Annex XII information pack** for the exact model version in production; (2) written confirmation
of the **no-training-on-customer-data** commitment *and* the retention window of prompts and outputs
on their side — because §7's Art. 28(3)(a) instruction and §2's erasure path both terminate there;
(3) their **copyright policy and training-content summary** location, which a bank's legal team will
request; (4) the **model-deprecation and version-notification** terms, since a version swap is §11's
"significant change in design" question and the register entry question at once. `(call)` on the fact
that (2) is obtainable today by most vendors and (1) is the one that takes real escalation.

### ISO/IEC 42001:2023: the certifiable wrapper

The AI Act tells you what to do; **42001 gives you a management system, an auditor, and a
certificate.** Its clause spine is the **Harmonised Structure, identical to 27001** — 4 context,
5 leadership, 6 planning, 7 support, 8 operation, 9 performance evaluation, 10 improvement — which
is the practical point: **the correct move for a company that already holds 27001 is a scope
extension of the existing ISMS into an integrated management system, not a parallel AI program.**
Parallel programs need two risk registers, two internal-audit cycles and two management reviews, and
they drift. Annex A of 42001 holds **38 controls across nine objectives** (A.2–A.10): policies (3),
internal organisation (2), resources (5), **AI risk assessment (4** — A.5.2 process, A.5.3
documentation, A.5.4 risks to individuals and society, A.5.5 societal/organisational), **life cycle
(9)**, **data for AI systems (5)**, information for interested parties (4), **use (3)**, and
**third-party and customer relationships (3** — A.10.2 allocating responsibilities, A.10.3 suppliers,
A.10.4 customers). Its distinctive feature is the **dual lens**: AI risk *to* the organisation plus
the impact *of* the AI system **on individuals, groups and society** — the same second axis the Act's
Recitals and Art. 27 FRIA are built around.

Where it plugs into this repository:

| 42001 control | What it makes you keep | The Part I / § stage it reuses |
|---|---|---|
| A.5.4 / A.5.5 AI risk to individuals and society | an impact assessment per AI use case | **§11's Art. 6(3) analysis** and §7's 35(3)(a) DPIA — the **AI-risk ↔ DPIA ↔ FRIA triangle** is one document with three consumers; keep it structured so each authority gets its format |
| A.6.2.4 evaluation / verification / validation criteria | the acceptance criteria for a model change | the rag/eval discipline: your evaluation set, its thresholds, and the record of a run that failed and was not shipped |
| A.6.2.6 operation and monitoring | monitoring for **drift, data poisoning, model stealing** | §6's anomaly analysis (CC7.2's "anomalies are analyzed"), plus prompt-injection telemetry, which Part I never needed and 42001 does |
| A.6.2.8 event logs | logs of the AI system's operation | §11's Art. 12 recording — the same trail, one more consumer, and 26(6)'s six-month floor inside its retention class (§10's divergence 1) |
| A.8 information for interested parties | notices and instructions to affected parties | §11's Art. 13 deployer information and 50(1) "you are talking to an AI" |
| A.10.3 / A.10.4 suppliers and customers | upstream model-provider terms; downstream deployer instructions | the §9 subprocessor table and the §7 DPA flow-down — the GPAI asks above become 42001 evidence, and the same text answers the bank's questionnaire |

**The cheapest correct answer to the bank today**, before any high-risk obligation bites: a documented
Art. 6(3)/6(4) classification memo (with its 49(2) registration if the conclusion is "not
high-risk"), plus the 42001 A.5 evidence that produced it, plus the A.10.3 paper trail from your model
vendors. That is three artifacts, none of them certifiable yet, all of them answerable in a
questionnaire — and the 42001 scope extension is the step that makes them auditable instead of
asserted.

### Trap answers

1. **"High-risk starts 2026-08-02."** It does not; **2027-12-02** for Annex III, after 2026/1744. The
   dates that *did* arrive on 2025-08-02 are GPAI, governance and penalties — the reason your vendor
   can be asked for Annex XII today.
2. **"We're not a high-risk system, we're an API."** Classification attaches to the **intended
   purpose**, not the delivery mechanism, and Art. 25(1)(a) moves provider status to whoever puts
   their name on it — subject to the contract's allocation of obligations. Your contract decides which
   company this is.
3. **"Face match is biometric identification, so we are Annex III point 1."** **Recital 15** excludes
   verification-only systems whose sole purpose is confirming a claimed person for access to a
   service. That is the argument to make *and document*, not a fact to assume.
4. **"Our confidence score is advisory, so there is no automated decision."** 6(3)'s gate is whether
   the system materially influences the outcome; §7's Art. 22 gate is whether the decision is
   *solely* automated. A reviewer who cannot explain why they overrode the score fails the first and
   endangers the second, and the SOC 2 test of the override control is how an auditor finds out.
5. **"42001 will cover our AI Act obligations."** 42001 certifies a **management system**; the Act
   imposes **product obligations** with conformity assessment (Art. 43), CE marking (Art. 48) and
   registration (Art. 49) — none of which a management-system certificate substitutes for. 42001 is
   evidence of governance, and a very good answer to a questionnaire, and not a CE mark.

### The answer, stated

> Classify **the intended purpose**, in a memo, before you ship: is it Annex III 5(b),
> creditworthiness of a **natural person** (fraud detection excepted), or 5(a)/(c)? If yes, run
> **Art. 6(3)**'s gate — no material influence on the outcome — plus one of (a) narrow procedural,
> (b) improve a completed human activity, (c) pattern deviation *without replacing human review*,
> **(d) preparatory task**, and check the **profiling override** before you celebrate. Then
> **document it under 6(4) and register the conclusion under 49(2)**, because an unregistered
> derogation is an opinion with a penalty branch of its own (99(5)). If the classification flips,
> Art. 25(1)(a) means the flip is decided by your **contract**, and 26(5)/(6)/(7) plus 27's FRIA mean
> the bank's obligations arrive as **your log retention, your instructions for use, and your input to
> their assessment**. Wrap the whole thing in **42001 as an extension of the ISMS you already run**,
> and the AI-risk ↔ DPIA ↔ FRIA triangle becomes one document instead of three deadlines.

The Part I mechanisms this section inherits: §0.3's crypto-shredding, because an Art. 10 data-governance
argument about training data is a deletion-capability argument; §4's access evaluation, because Art. 14
human oversight is an access-control question ("who could override, and did anyone"); the capstone's
trail, because Art. 12 and 26(6) are the same logging duty with a six-month floor and a bank's FRIA
downstream. Nothing here is new engineering. It is new **paper about the engineering**, and the paper
has dates on it.

---

## 12. DORA, from the supplier's chair: the contract you will be asked to sign

**The scenario.** A bank's procurement sends an addendum: *DORA addendum to the master services
agreement, twelve clauses, no amendments please.* Legal reads it as "the regulator's paper." It is
**Article 30 of Regulation (EU) 2024/1689**, in force since **2025-01-17**, and it is a list of
contract terms the *bank is required to put in and you are required to accept* — with a separate,
harder set if the service supports a **critical or important function**. Read it as a specification,
because it is one: eight of its letters are mechanisms §2, §5, §6 and §7 already built, and three are
mechanisms nobody builds until a regulator asks for them by name.

The structural point first. DORA regulates **financial entities**, not vendors. Its reach into your
company is **contractual** (Art. 30 terms), **registerial** (Art. 28(3)) and, for a small designated
set of providers, **direct supervisory** (Chapter V, the Lead Overseer). That is why §9's conclusion
repeats: you are not going to be "DORA compliant" — you are going to be a **DORA-compliant
supplier**, which is a narrower, colder and more contractual thing.

### Art. 30(2): the clauses in every ICT contract (letters a–i)

Art. 30(1) first: rights and obligations "shall be clearly allocated and set out in writing," with
SLAs included, "in one written document," available on paper or a downloadable, durable and
accessible format. Then, verbatim in substance, with the mechanism each letter demands:

| 30(2) | The clause | Where it breaks in a real vendor | The Part I mechanism |
|---|---|---|---|
| (a) | "clear and complete description of all functions and ICT services", **indicating whether subcontracting of a CIF-supporting service is permitted and the conditions** | Your order form says "document extraction SaaS"; the regulator wants the function list *and* the subcontracting position in the same document | the §7/§9 subprocessor table, contractualised |
| (b) | the **locations** — regions or countries — where services are provided and where data is processed and stored, **plus advance notification if you envisage changing them** | a capacity-driven second region. "We moved backups" is a notification breach; the notification duty is *in advance* | §5's replication decision, as a legal event rather than a Terraform event |
| (c) | provisions on **availability, authenticity, integrity and confidentiality** of data including personal data | clauses that promise confidentiality and never define authenticity of records | §3/§4 key policy plus `iam.py` boundary evaluation |
| (d) | "ensuring **access, recovery and return in an easily accessible format** of personal and non-personal data … in the event of the **insolvency, resolution or discontinuation of the business operations** … **or in the event of the termination of the contractual arrangements**" | the export endpoint that produces paginated JSON with your internal IDs. "Easily accessible format" is not a file that only your parser reads | §2's backup path plus a **documented, tested export** — this is the clause the bank will actually test |
| (e) | **service level descriptions, including updates and revisions** | SLAs defined in the portal's terms of use, which change unilaterally | §6's clock inventory |
| (f) | obligation to provide **assistance at no additional cost, or at a cost determined ex-ante**, when an ICT incident related to the service occurs | an incident-retainer rate card discovered at 05:00 | §6's 03:00 runbook, with the price fixed in advance |
| (g) | **full cooperation with competent authorities *and resolution authorities***, including persons appointed by them | a support contract that forbids third-party disclosure without consent — which blocks (g) | §4's audit-response discipline, widened to a supervisor and a resolution authority |
| (h) | **termination rights and minimum notice periods**, per the expectations of competent and resolution authorities | auto-renewal with 30-day notice windows in December | Art. 28(7)'s mandatory termination grounds (below) |
| (i) | conditions for **participation in the entity's ICT security awareness programmes and digital operational resilience training** | not a trap — it is a *cited* obligation: **Art. 13(6) says financial entities "shall also include ICT third-party service providers in their relevant training schemes in accordance with Article 30(2), point (i)"**. The regulation points at its own contract clause | §7/§8's A.6.3 training records, now covering your engineers in the customer's programme |

### Art. 30(3): the four extra clauses when the function is critical or important

This is the tier a document-extraction platform inside a credit process will be asked to accept.
Verbatim in substance:

- **(a) full service level descriptions with precise quantitative *and qualitative* performance
  targets** within agreed service levels, "to allow effective monitoring … and enable appropriate
  corrective actions … without undue delay when agreed service levels are not met." A 99.9%
  availability number is not a qualitative target; extract-accuracy floors are.
- **(b) notice periods and reporting obligations**, including notification of **"any development that
  might have a material impact on the … provider's ability to effectively provide"** the CIF service
  in line with SLAs. This is the clause that requires you to disclose your own incidents, your own
  sub-vendor failures, and — arguably — your own financing, *before* the bank asks. Draft it so you
  can answer it truthfully without volunteering competitive information.
- **(c) implement *and test* business contingency plans**, with ICT security measures, tools and
  policies "that provide an appropriate level of security for the provision of services by the
  financial entity **in line with its regulatory framework**." Note "and test": §6's restore test and
  A1.3-style dated evidence stop being good practice and become contract terms.
- **(d) participate and fully cooperate in the entity's TLPT** (threat-led penetration testing), per
  Arts. 26 and 27. See the TLPT section — this is where DORA's cost curve turns.
- **(e) the right to monitor, on an ongoing basis, the provider's performance**, which entails four
  sub-points and is the most consequential paragraph in the whole article for a vendor:
  - (i) **"unrestricted rights of access, inspection and audit"** by the entity or an appointed third
    party **and by the competent authority**, plus the right to **take copies of relevant
    documentation on-site where they are critical to the provider's operations**, and "the effective
    exercise of which **is not impeded or limited by other contractual arrangements or
    implementation policies**";
  - (ii) the right to agree **alternative assurance levels** where other clients' rights are affected;
  - (iii) your obligation to **fully cooperate during on-site inspections and audits** performed by
    the competent authorities, **the Lead Overseer**, the entity or an appointed third party; and
  - (iv) your obligation to provide **details on the scope, procedures and frequency** of such
    inspections and audits.
- **(f) exit strategies, in particular a mandatory adequate transition period** (i) during which you
  keep providing the functions or services, "with a view to reducing the risk of disruption … or to
  ensure its effective resolution and restructuring", and (ii) allowing the entity **to migrate to
  another provider or to in-house solutions, consistent with the complexity of the service**.
- **Derogation:** for a **microenterprise** financial entity, the (e) access/inspection/audit rights
  may be agreed as delegated to **an independent third party appointed by the provider**, with the
  entity able to request information and assurance from that third party **at any time**. The cheapest
  version of a DORA access clause, available if the buyer is small enough.

**Reconcile (e) with §9, because the two audit regimes are not the same instrument.** A SOC 2 auditor
tests a **sample from a period** inside boundaries you and management's description agreed. A DORA
30(3)(e) inspection is **unrestricted, ongoing, on-site, with document copies, exercisable by the
competent authority and the Lead Overseer**, and cannot be limited by other contracts. Practically:
your Type II report cannot satisfy (e), and (e) is the clause that means *an authority can ask you
directly for the trail §6's clock table describes.* If you have never built an external-inspection
procedure — who hosts, what is shown, what is copied, what is refused and on what basis — (e) is a
contractual promise you cannot keep. `(call)` on the "inspection playbook" being the most
under-invested artifact in mid-size SaaS compliance.

### TLPT: the clause that gets expensive

**Art. 26(1)**: identified entities (non-microenterprises, other than those in Art. 16(1)'s
first subparagraph) run TLPT **at least every three years**, and the competent authority **may reduce
or increase that frequency** based on risk profile and operational circumstances. **26(2)**: scope
covers several or all critical or important functions, **on live production systems**, and must
identify all underlying ICT systems **including outsourced or contracted ones**; the scope assessment
**"shall be validated by the competent authorities."** **26(3)**: where providers are in scope, the
entity "shall take the necessary measures and safeguards to ensure the participation of such ICT
third-party service providers in the TLPT" and **retains full responsibility at all times**. **26(5)**:
risk-management controls operate with the cooperation of providers and other relevant parties
**including the testers, excluding the competent authorities**.

Now the paragraph written for you: **26(4), pooled testing.** Where the provider's participation is
reasonably expected to **adversely impact the quality or security of services provided to customers
outside the scope of DORA**, or the confidentiality of related data, the entity and the provider **may
agree in writing** that the **provider itself directly contracts the external tester**, with testing
performed **under the direction of one designated financial entity**, covering the range of ICT
services supporting critical or important functions; the pooled test counts as TLPT for all
participating entities, with the number of participants "duly calibrated." Read it as the answer to
the question every vendor asks on first receipt of 30(3)(d): *am I agreeing to be penetration-tested
by eighteen banks?* **Negotiate the pooled-testing clause in the same pass as 30(3)(d)** — DR
2025/1190 supplies the mechanics (initiation information within three months of notification, scope
document within six, a red-team window of at least twelve weeks), and there is **no EU-wide
first-TLPT date**, so timing arrives bilaterally, through your contract. `(call)` on that being a
commercial priority rather than a legal one.

### Art. 28: why you are a register entry before you are an auditee

**28(3)**: financial entities maintain and update a **register of information** covering **all**
contractual arrangements for ICT services, appropriately documented, **distinguishing CIF-supporting
from non-CIF**; they **report at least yearly** to the authority on the number of new arrangements,
the categories of providers, the types of arrangements and the services and functions provided; they
make the full register or specified sections available **on request**; and they **"shall inform the
competent authority in a timely manner about any planned contractual arrangement on the use of ICT
services supporting critical or important functions as well as when a function has become critical or
important."** Templates are in **IR 2024/2956** (first transmission 2025-04-30). The consequence for
a vendor: **the day the bank signs you for a critical function, two letters go out — one to its
authority, and one to you about incident reporting.** You will be a register entry before you are a
SOC 2 subject.

The standards clause, which is the strongest argument §8 has in a procurement meeting: **28(5)** —
entities "may only enter into contractual arrangements with ICT third-party service providers that
**comply with appropriate information security standards**", and where the arrangement concerns
critical or important functions they shall, *prior to concluding it*, "**take due consideration of
the use … of the most up-to-date and highest quality information security standards**". **28(6)** —
when exercising access, inspection and audit rights, entities shall on a **risk-based approach
pre-determine the frequency of audits and inspections and the areas to be audited**, adhering to
**commonly accepted audit standards**, and where the arrangement entails **high technical
complexity** they shall verify that the auditors — internal, external, or a **pool** — "possess
appropriate skills and knowledge". A certificate is therefore not a marketing asset under DORA; it
is a *procurement qualification*, and the "most up-to-date and highest quality" sentence is why an
ISO/IEC 27001:2013 certificate is now an active liability.

**28(7)**: arrangements must be terminable in any of four circumstances — **(a)** a **significant
breach** of applicable laws, regulations or contractual terms; **(b)** circumstances found through
ICT third-party risk monitoring "capable of altering the performance" of the functions, **including
material changes affecting the arrangement or the situation of the provider**; **(c)** the
provider's **evidenced weaknesses in its overall ICT risk management**, in particular in how it
ensures **availability, authenticity, integrity and confidentiality of data**; and **(d)** where the
competent authority **can no longer effectively supervise the financial entity** as a result of the
arrangement's conditions or circumstances. (b) and (d) are the two that surprise vendors: your
acquisition, your funding round, and your regulator's view of your paperwork can each be a
termination ground. **28(8)**: for CIF services, exit plans must be **comprehensive, documented and
sufficiently tested and reviewed periodically** (per the Art. 4(2) criteria), enabling the entity to
exit **without** (a) disruption to its business activities, (b) limiting its regulatory compliance,
or (c) detriment to continuity and quality of service to its own clients — with alternative
solutions and transition plans that **remove the contracted services and the relevant data from the
provider and transfer them securely and integrally to alternative providers or back in-house**. Name
the artifact that answers 28(8): the **exit pack** — export format definition, the 30(2)(d) return
mechanism, the migration runbook, a tested restore, and the transition-period staffing plan. If it
has never been rehearsed, the word "tested" will find you.

**Art. 29 — concentration and third-country subcontracting.** **29(1)**: assess **accumulated
exposure** where a provider is **not easily substitutable** and either multiple functions rely on it
or multiple CIF arrangements exist with the same or closely connected providers, weighed against the
digital operational resilience strategy. You already fail or pass this test on facts: AWS Frankfurt
for app *and* backups, Azure Sweden for inference, Datadog for telemetry. **29(2)** runs in four
steps: where further subcontracting of CIF-supporting services is possible, entities "shall weigh
benefits and risks … **in particular in the case of an ICT subcontractor established in a
third-country**"; for CIF arrangements they "shall **duly consider the insolvency law provisions**
that would apply in the event of the ICT third-party service provider's bankruptcy **as well as any
constraint that may arise in respect to the urgent recovery of the financial entity's data**"; for
providers established in a third country, "in addition … consider the compliance with Union data
protection rules and the effective enforcement of the law in that third country"; and finally they
"shall assess whether and how **potentially long or complex chains of subcontracting may impact
their ability to fully monitor the contracted functions and the ability of the competent authority
to effectively supervise the financial entity in that respect**." This is the paragraph your
architecture review is now legally inside, and it is where "our models run in Azure Sweden,
EU-resident" earns its keep: the answer to 29(2) is a
*documented* consideration, not a marketing line.

### The oversight part, and the list that names your vendors

Chapter V creates the **Critical ICT third-party service provider (CTPP)** regime, and the
designation criteria in **Art. 31(2)** are all four required, assessed on the services provided:
**(a) systemic impact** on the stability, continuity or quality of financial services if the
provider faced a large-scale operational failure — counted by number of financial entities and the
**total value of their assets**; **(b) the systemic character or importance of the entities that
rely on it** — the number of **G-SIIs and O-SIIs** served and their interdependence with other
financial entities; **(c) reliance of financial entities on it for critical or important functions,
"irrespective of whether financial entities rely on those services directly or indirectly, through
subcontracting arrangements"** — which is the sentence that makes *your* dependence on AWS part of
*their* designation; and **(d) substitutability** — lack of real alternatives even partial, market
share, technical complexity and proprietary technology, plus the **difficulty of migrating data and
workloads** (financial cost, time, and the ICT and operational risk the migration itself creates).
Groups are assessed on the group's services as a whole (31(3)) and must designate a **coordination
point** for communication with the Lead Overseer (31(4)). **Art. 31(9)**: the ESAs, through the Joint
Committee, "shall establish, publish and update yearly the list of critical ICT third-party service
providers at Union level." The **first list, published 18 November 2025, contains 19 entities**:
Accenture plc, **Amazon Web Services EMEA Sarl**, Bloomberg L.P., Capgemini SE, Colt Technology
Services, Deutsche Telekom AG, **Equinix (EMEA) B.V.**, Fidelity National Information Services Inc.,
**Google Cloud EMEA Limited**, IBM Corporation, InterXion HeadQuarters B.V., Kyndryl Inc., LSEG Data
and Risk Limited, **Microsoft Ireland Operations Limited**, NTT DATA Inc., Oracle Nederland B.V.,
Orange SA, SAP SE, Tata Consultancy Services Limited. The **Lead Overseer** is the ESA responsible
for the financial entities that together hold the largest share of total assets among that
provider's users, evidenced by the sum of their balance sheets (31(1)(b)); oversight starts **no
later than one month after** the designation notification, and the designated provider must itself
**notify the financial entities it serves** (31(5)); a third-country designated provider must
establish a **Union subsidiary within 12 months** (31(12)); a non-listed provider may **request
designation**, decided within six months (31(11)); and the Joint Committee's oversight guidance is
**JC 2025/29** (15 July 2025).

Two consequences, precisely: **your subservice providers are designated; anyformat is not.** So the
authorities' direct supervisory reach lands on **AWS, Microsoft and Google**, and reaches **you**
only through the entity's **30(3)(e)** clause and your cooperation obligations. Which means the
practical DORA program for a vendor of anyformat's size is: the **Art. 30(2)/(3) contract terms**, the
**register entry's factual accuracy**, the **incident-reporting clocks**, the **exit pack**, the
**TLPT/pooled-testing position**, and an **inspection playbook**. Not oversight of you — *reach
through* you.

### The clocks, in the order they fire

The **classification** rule is in Commission **Delegated Regulation (EU) 2024/1772 (JTRS)**: a
material ICT incident must be classified **within 24 hours**. **Art. 17** requires the reporting
process, and **Commission Implementing Regulation (EU) 2025/302** with **Delegated Regulation (EU)
2025/301** set the **initial report within 4 hours of classification** (and in any event within 24
hours of becoming aware), an **intermediate report within 72 hours of the initial**, and a **final
report within one month of the initial** — Annex I templates. §6 already taught the arithmetic: the
4-hour clock runs from the entity's *classification*, not from your pager, and **your 30(3)(b)
notice obligation is what lets the bank classify at all**. A vendor that reports "everything is fine"
at 09:00 has, contractually, prevented a supervised entity from meeting a statutory deadline. That
reframes §6's runbook from hygiene to liability.

### Trap answers

1. **"We'll accept the addendum; it's standard."** 30(3)(e)(i) forbids your *other* contractual
   arrangements from impeding the access right — so signing it can conflict with the NDAs and
   confidentiality clauses you have with **your** vendors and other customers. Legal has to resolve
   the conflict before sales promises the clause; that is the (ii) "alternative assurance levels"
   mechanism existing for.
2. **"Easily accessible format is our API."** 30(2)(d) names four triggers: insolvency, resolution,
   discontinuation of business, termination. In three of them your API does not exist. The clause is
   an *offline-capable* export obligation with a documented format.
3. **"DORA applies to us because we serve banks."** It applies to the entity. You are reached by
   contract, register and, if you grow into the designated list, oversight. Say "we are a DORA-aware
   supplier with Art. 30 terms" rather than "we are DORA compliant," and expect the questionnaire to
   test the former.
4. **"Pen tests we do annually satisfy TLPT."** TLPT is threat-intelligence-led, scoped to CIFs on
   **live production**, with an authority-validated scope and external testers accredited under
   TIBER-EU-style rules. An annual vendor vuln scan is not a TLPT, and 30(3)(d) obliges you to
   *participate*, not to have pre-done it.
5. **"Only the region matters for 29(2)."** The paragraph also asks about **chain length and
   complexity** and about whether your subcontracting impairs the entity's monitoring or the
   authority's supervision. AWS → an Irish subsidiary → a data-centre operator is a chain; answer it
   with your subprocessor table's *levels*, not with a country.

### The answer, stated

> DORA reaches a vendor through **one contract and three instruments**. The contract is
> **Art. 30**: (a)–(i) in every ICT arrangement — description **and subcontracting position**,
> locations **with advance notice of change**, availability/authenticity/integrity/confidentiality,
> **the insolvency-proof return of data in an easily accessible format**, SLA descriptions, incident
> assistance **priced ex ante**, cooperation with competent **and resolution** authorities,
> termination rights, and training participation that **Art. 13(6) points at from the regulation
> itself**. The CIF tier adds (a) quantitative *and qualitative* targets, (b) material-impact
> notification, (c) contingency plans **that are tested**, (d) TLPT participation, **(e) unrestricted
> inspection with on-site copies by the entity and the authority**, and **(f) a mandatory transition
> period**. The instruments are the **Art. 28(3) register** (you are an entry, reported yearly, with
> the authority informed when a function becomes critical), the **Art. 29 concentration and
> third-country assessment**, and — for the 19 designated providers, including your own — **Chapter V
> oversight you will never be subject to but must be able to survive on paper.**

This section is §5, §6 and §7 with a signature line under them: locations and replication lag are
30(2)(b); the tested restore is 30(3)(c) and 28(8); the key and access discipline is 30(2)(c); the
erasure and export path is 30(2)(d); the training records are 30(2)(i) through 13(6); the runbook is
30(2)(f) and 30(3)(b). And the one thing Part I never built is the **inspection playbook** — 30(3)(e)
is the only compliance clause in this file that no stage in the 36 can pass on its own.

---

## 13. The program: ISO held, no SOC 2, and a bank that wants SOC 2

**The scenario.** It is 2026-11-07. anyformat holds **ISO/IEC 27001:2022** (Stage 2 complete in
March 2026), has **no SOC 2 of any kind**, four subservice boundaries it did not consciously scope,
a DPA that AWS and Azure each send *to* it but which it has not yet sent *onward*, a bank deal worth
more than its current ARR, and a five-person engineering team where the CTO is the incident
commander, the key custodian and the audit responder. The buyer's deadline is the end of the quarter.
"Get SOC 2" is not a plan. This is the plan, in the order the dependencies actually allow.

### The three decisions that must precede any purchase order

**Decision 1 — the boundary, before the description.** §9's table is now a decision with a signature
under it. For each of AWS eu-central-1, Azure Sweden, GCP Gemini and Datadog: **carve out** (their
controls are outside your report; you name the complementary controls they provide) or **include**
(their controls sit inside your description and your auditor asks for evidence from an environment
you do not administer). The `(call)` recommendation, and the one I would defend in a board meeting:
**carve out all four, and write the complementary-control paragraph for each — the data at rest in
AWS, the inference in Azure, the telemetry in Datadog, the no-training commitment in Gemini — and
then, separately, obtain each provider's own report or attestation and reference it by name in the
description.** Two reasons. First, inclusion is not something you can do unilaterally: it requires
the subservice organisation's cooperation and its controls in *your* test population, which for AWS
means you would be attesting to hardware security you cannot sample. Second, the carve-out only
survives a buyer's reading if the complementary controls are *specific*; "AWS provides physical and
environmental controls" reads like boilerplate, and "the customer's data at rest is protected by a
customer-managed key in the customer's own account under §0.2 custody model C" reads like design.
The second sentence is your differentiator and it comes from Part I, not from a tool.

**Decision 2 — the categories, and the order.** Security now. Availability in the same period if the
restore machinery of §5/§6 is already instrumented, because A1.1–A1.3 is three criteria and A1.3's
evidence is a dated test record you should be generating anyway. Confidentiality (C1.1, C1.2) costs
almost nothing once §2's purge exists. **Privacy is a separate program** (§9's trap 2): 26 criteria,
a data-subject inquiry process, notices, consent, and a legal owner who answers them. Do not let a
sales team promise it, and do not let a mapping tool imply ISO 27701 "covers" it — 27701 is a
management-system extension, the report is an attestation, and neither is the other.

**Decision 3 — the period, deliberately.** A Type II observation window is a choice you make once
and cannot retroactively widen. Three rules, all `(call)` because the AICPA sets none of them:
do not start the period before the **evidence engine** is running, because a month of missing
tickets is a month you either exclude from the period or defend; do not end the period before a
**known change freeze or a known major change**, because a control change inside the window needs
two populations of evidence; and pick the length by counting **iterations** — a monthly access review
in a three-month window is one sample, in a nine-month window it is three, and the buyer's auditor
sees the number. For anyformat's actual state, the honest arithmetic is a **three-to-four month Type
I now** plus a **six-month period starting after the evidence engine is switched on**, which lands
the Type II roughly two quarters later.

### The sequence, with the artifact each step produces

| Step | Window | What you do | The artifact that leaves the building |
|---|---|---|---|
| **0. Answer the questionnaire today** | this week | Write the Art. 6(3) classification memo (§11), the subprocessor table with the 28(3)(a) instruction position per vendor (§7), the four-custody-model statement (§0.2), and the DORA 30(2)/(3) clause map (§12) | a **compliance dossier**: four documents that convert "we have ISO" into "here is the analysis" |
| **1. Evidence engine on** | 2–4 weeks | Every control gets a *record with a date*: access review ticket, restore test record, change ticket with approval, incident drill, training completion, vendor assessment. Wire the trail to §6's clock table and A.8.17 clock sync | the **control inventory with owners and cadences**, plus the first backfilled records |
| **2. Close the ISO-side gaps the questionnaire exposed** | 4–8 weeks | SoA re-justification for the controls §8 names (A.5.23, A.5.30, A.8.10–A.8.12, A.8.15–A.8.17); clause 9.2 internal audit planned *and performed*; the A.8.33 test-data question answered; **notify the CB of the Sweden inference path** (17021-1 8.5.3) | an updated **SoA**, an **internal audit report**, a **management review minute**, and a scope amendment request |
| **3. Type I (SOC 2 Type 1)** | 6–10 weeks, running parallel to 2 | Management's system description, the commitments and system requirements you are attesting against, the carve-out decision, the complementary-control paragraphs | a **Type 1 report**: design suitability as of a date, *no* operating effectiveness — and the artifact that gets you into the buyer's security review instead of being filtered out |
| **4. Choose and start the period** | the month after Type I | Fix the window; confirm every control has run at least twice inside it; freeze the description; brief the team that "the auditor will ask you for this, not me" | a **period start memo**, and the observation calendar |
| **5. GDPR/DORA contract layer** | during the period | The DPA you send onward (28(3)(a)–(h) verbatim letters, 28(4) flow-down, 28(2) notification mechanism); the DORA 30(2)/(3) addendum position per clause; the **exit pack** (28(8), 30(2)(d), 30(3)(f)); the **inspection playbook** (30(3)(e)) | a signed **subprocessor DPA set**, a **DORA clause map with answers**, a rehearsed **export + migration runbook** |
| **6. SOC 2 Type II** | period end + 4–8 weeks | Fieldwork, sample pulls, exception handling, the tests-and-results section | the **Type II report** — the thing in the bank's field |
| **7. Optional, and only if asked by name** | next year | ISO 42001 **as a scope extension of the ISMS** (§11); SOC 2 Privacy if enterprise buyers request privacy; ISO 27701 if the privacy program becomes real | one integrated audit instead of three parallel ones |

Read step 2's last cell twice: **notifying the certification body of the architecture change** is
cheap while the change is small and expensive after surveillance finds it (17021-1 8.5.3, and §8's
trap 1). Read step 5's last two cells as the ones no compliance tool will buy for you: the export
that works without your API and the playbook for an authority standing in your data centre.

### The four clocks, side by side — because they do not align and the calendar is the deliverable

| Clock | The rule | What it forces you to have ready *by* |
|---|---|---|
| **ISO surveillance** | at least **once a calendar year**, except recertification years; first surveillance **≤ 12 months from the certification decision date** (17021-1 9.1.3.3); three-year cycle, with an industry-scheme NOTE | the 9.6.2.2 (a)–(h) evidence set — internal audit, management review, prior NC actions, complaints, effectiveness, improvement, operational control, changes, mark usage |
| **ISO certification validity** | three years, re-evaluating **all** requirements at recertification (9.6.3.1); major nonconformity unverified within **6 months of the last day of Stage 2** ⇒ **another Stage 2** (9.5.3.2) | corrective actions with cause analysis (9.4.9), closed on the CB's clock, not yours |
| **SOC 2 observation period** | your chosen window; no AICPA minimum `(call)`; Type 1 is a point in time | continuous, dated records for every control *inside* the window — a gap is a scope limitation, not a small lie |
| **Statutory clocks** | GDPR **72 h** breach notification (33(1)) with the Art. 33(5) record; **12(3)** one month, extendable two; DORA **24 h to classify** (JTRS) then **4 h / 72 h / 1 month** (IR 2025/302 + DR 2025/301); AI Act **26(6)** six-month log floor; DORA register **yearly** (28(3)) + CIF arrangements "in a timely manner"; TLPT **every 3 years**, authority may change frequency (26(1)) | the runbook, the notice templates, the per-class retention table, and a human who can answer at 03:00 without inventing |

The scheduling fact worth a line in your calendar app: the ISO year runs on the **decision date**, the
SOC 2 year runs on **your chosen window**, and the GDPR/DORA clocks run on **events**. If you build
one annual "compliance month," you will be ready for exactly one of the four.

### The failure mode, named

The default way this goes wrong is not a missing control. It is **building evidence *for* the audit
instead of running the management system *as* the evidence.** The symptoms are recognisable: a
ticket type created four weeks before fieldwork; access reviews that exist only as exported
spreadsheets with no reviewer named; a restore "test" that is one engineer restoring one object to a
bucket they own; a policy set approved in one commit and never reviewed; an Art. 6(3) memo written by
the consultant who will not be there when the model version changes. Every one of those produces a
report and none of them produces the outcome §6's closing paragraph described — a system that *proves
the control ran* because running it is how the system works.

The mirror failure is **over-collecting**: data-event logging on every read, kept indefinitely,
because "auditors like logs." That is an Art. 5(1)(e) minimisation exposure and an Art. 30(1)(f)
erasure-limit gap, created in the name of compliance. §10's retention-class table is the fix, and the
test of the fix is whether you can say, per class, **which authority asked for it and which one is
worried about it.**

And one honest limit, stated so nobody is surprised in month eight: **some evidence cannot be
shared, and no crosswalk changes that.** The Art. 6(3) classification memo, the Art. 22 "is this
solely automated" analysis and the Art. 27 FRIA inputs have **no ISO control and no SOC 2 criterion**
(§10). Conversely ISO's 4.1 context analysis and 6.3 planning-of-changes have **no SOC 2 criterion**,
and DORA 30(3)(e)'s inspection right **exceeds any SOC 2 sample**, by design. A tool that claims the
grid is complete is a tool with two columns missing and one row where the cell says "N/A" and nobody
asked who wrote it.

### Trap answers

1. **"We'll do the Type I, then decide the Type II window later."** Later means the window starts
   after the auditor's availability and after your next big change. The Type I is the moment you
   learn which commitments you can defend; pick the period *at* that moment, not after.
2. **"Buy the compliance platform and it generates the evidence."** It generates *records* for
   controls that run. For controls that do not run it generates a policy PDF with a date field. The
   5.2.6 impartiality split (§8) is the regulatory version of the same warning.
3. **"We'll add Privacy next year, it's one more checkbox."** It is 26 criteria plus a
   data-subject complaint process with a legal owner, and it changes what "we don't see customer
   documents" can honestly mean.
4. **"The bank only needs the report, not the runbook."** They will ask for the 30(2)(d) export, the
   TLPT participation clause and an on-site inspection — 30(3)(e)(i) — none of which are in a PDF of
   opinion.
5. **"One compliance hire owns all of this."** They own the calendar and the evidence hygiene. The
   CTO owns the trail, the key custody and the 03:00 decision; legal owns 28(3) and 30(2); product
   owns the classification memo, because it is a statement about the product. A program where one
   person owns all four is a program with one person as the single point of failure — which is
   exactly what §6's clock table exists to prevent.

### The answer, stated

> Sequence by dependency, not by deadline: **answer the questionnaire today with the four analysis
> documents** (§11 memo, §7 subprocessor position, §0.2 custody statement, §12 clause map); **switch
> on the evidence engine**, because a period with no records is a wasted period; **close the ISO-side
> gaps the questionnaire exposed and notify the CB of the Sweden change**; **Type I** to buy the
> conversation; **choose the period on iteration arithmetic**, then **Type II**; **the contract layer
> in parallel** — onward DPA, DORA 30 terms, the exit pack, the inspection playbook; and only then
> consider **42001 as a scope extension**, never as a second program. Run **four clocks** that will
> never align: the surveillance year from the decision date, the certification's three-year cycle with
> its six-month major-NC trap, your chosen observation period, and the statutory clocks that start at
> 03:00. The failure mode to avoid is not a missing control; it is **evidence manufactured for an
> audit** instead of a system whose normal operation *is* the evidence. That is the same sentence Part
> I has been building toward since stage 1: the compliance artifact you can hand a stranger is the log
> your own code wrote.

Everything above is downstream of stages you already passed: §4's `evaluate_with_boundary` is CC6.3
and A.5.18 and 30(2)(c); the capstone's `cloud.audit` append is CC7.1–7.5, A.8.15/16, Art. 33(5) and
AI Act Art. 12 at once; stage 8's delete markers are C1.2, A.8.10, Art. 17 and 30(2)(d); §5's
replication rule is CC6.7, A.5.30, Art. 28(3)(a) and 30(2)(b). Part II added no mechanism. It added
the *audience* — four of them, with different clocks, all reading the same trail.

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
| `evaluate_with_boundary` (identity **AND** boundary) | SOC 2 **CC6.3** least privilege, ISO **A.5.18**, DORA **30(2)(c)** | a boundary "never grants, it only subtracts" — so an auditor's exception list is the *grants*, and a control that lives only in the boundary is invisible in the identity policy (§9) |
| the `cloud.audit` append, per authorization decision | **CC7.1–CC7.5**, A.8.15/A.8.16, Art. 33(5), AI Act **Art. 12** + 26(6) six-month floor | the criterion is not the log, it is that anomalies are **analyzed** and incidents **recovered from** — so the trail without the ticket and the dated restore test evidences nothing (§10 row 1) |
| a confidence score shown to a human reviewer | **Art. 6(3)(d)/(a)** derogation *and* GDPR **Art. 22(1)** "solely automated" | the same field decides both: if the reviewer cannot explain an override, the derogation collapses into Annex III **5(b)** high-risk and the bank owes an **Art. 27 FRIA** whose inputs are your logs (§11) |
| the export path + the backup restore | DORA **30(2)(d)** "access, recovery and return **in an easily accessible format**" on insolvency, resolution, discontinued business or termination | three of those four triggers mean your API does not exist; the artifact is a documented offline export, not an endpoint (§12) |
| the replication rule and its region list | DORA **30(2)(b)** locations **with advance notification of change**; Art. 28(3)(a) transfers | the notification is *in advance*, so a capacity-driven second region is a contractual event the moment Terraform merges (§5, §7, §12) |
| the subprocessor table, four boundaries deep | **CC9.2**, A.5.19–A.5.23, Art. 28(2)/(4), DORA **28(3) register** + **29(2)** chain length | carve-out hides the controls that hold the customer's data; inclusive testing promises evidence from environments you do not administer (§9) |

Read the right column alone and you have the interview. Read both and you have the reason the
mechanism *matters*: a bank's "we can revoke you at 3am" is only true if the revocation
mechanism is a **resource-side key policy** whose removal your `evaluate`-engine sees as a
deny, with an audit trail whose data events you already bought. Part II's rows say the same thing
in the four vocabularies the buyer actually speaks: the criterion (CC6.3), the control (A.5.18),
the contract clause (30(2)(c)) and the period over which all three must be *proven* (§9).

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
7. A buyer asks for "SOC 2 or ISO, whichever." Name the object each one certifies, the time
   unit each one runs on, and the single sentence that makes them non-substitutable.
8. You scope Security and Availability. The buyer's next question is about data-subject
   complaints. Which category answers it, how many criteria does it add, and why is that not
   the category you already added for "confidential documents"?
9. Your certificate says ISO/IEC 27001:2022 and the model inference moved to Sweden in April.
   Name the 17021-1 clause you should have used, the surveillance item that will find the
   omission, and the sentence you can no longer print on the trust page.
10. The bank sends the DORA addendum. Which letter guarantees you can hand their data back
    *when your API is dead*, which letter lets their regulator inspect you on-site with copies,
    and which letter obliges your engineers to attend the bank's training? Name all three and
    say which one Part I never built a mechanism for.

If 2, 4 and 6 are shaky, that is the gap Part I named. If 7–10 are shaky, it is the gap Part II
named, and the shape is the same: **one line to the right of a stage you already passed** —
31→2, 1→4, capstone→6, and now `evaluate_with_boundary`→CC6.3, the SoA→the scope sentence, the
restore test→30(3)(c). Notice what question 10's last clause is really testing: not whether you
know the letters, but whether you know that the *inspection playbook and the offline export are
the two artifacts no stage in this course produces*. The compliance question is not a different
subject. It is the subject you built, asked at 3am by a regulator — and answered, or not, by
whether the log, the ticket and the runbook exist with dates on them.

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
retention (the Art. 17(3) conflict); **GDPR Recital 65** (erasure "and no longer processed"),
**Recital 66** (made-public link-erasure duty) and **EDPB Guidelines 02/2025**
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

**Part II sources.** *SOC 2* — **AICPA Trust Services Criteria, TSP Section 100** (2017 TSC with
2022 Revised Points of Focus), read from the criteria text itself: `.06`/`.07` on common criteria
plus category-specific control-activity criteria and the "**no additional control activity criteria
are needed**" sentence for security; the privacy-vs-confidentiality passage ("privacy … applies only
to personal information"; "Confidential information may include personal information as well as
other information, such as trade secrets and intellectual property"); criterion texts for **CC6.1,
CC6.2, CC6.3 (least privilege), CC6.6, CC6.7, CC7.1, CC7.2, CC7.4, CC7.5, CC9.1, CC9.2, C1.1, C1.2,
A1.1, A1.2, A1.3, PI1.1–PI1.5**; and the Type 1 / Type 2 definitions verbatim (Type 2 = suitability
of design **and operating effectiveness … throughout a specified period**, with "a detailed
description of tests of controls performed by the service auditor and the results of those tests";
Type 1 = same subject matter, neither of those). Counts — **33 common criteria** (5/3/4/2/3/**8**/5/1/2
across CC1–CC9), A-series 3, C-series 2, PI-series 5, Privacy 26 in `.0`/`.1` pairs — are derived by
enumeration of the published list, not quoted as a total; **CC6 has eight criteria, not nine.** The
**system description, the carve-out/inclusive method and CUECs/CDCs are not in TSP 100**: they come
from the AICPA attestation standards (**AT-C 205, SSAE 18/21**), cited here as `(call)` on the exact
wording, and no minimum observation period appears in the criteria text either.

*ISO* — **ISO/IEC 27001:2022** clauses 4–10 (with **Amd 1:2024** adding climate change to 4.1's
external issues) and **Annex A's 93 controls in four themes: 37 organizational (A.5.1–A.5.37), 8
people (A.6.1–A.6.8), 14 physical (A.7.1–A.7.14), 34 technological (A.8.1–A.8.34)**, plus the 11
controls new in 2022 (A.5.7, A.5.23, A.5.30, A.7.4, A.8.9, A.8.10, A.8.11, A.8.12, A.8.16, A.8.23,
A.8.28); Annex B's 114→93 mapping (58 carried, 57 merged into 24, 1 split); 2013 certificates
expired **2025-10-31** under IAF MD 26's 36-month transition. Control titles for A.5.15, A.5.18,
A.5.19–A.5.23, A.5.24–A.5.30, A.5.33, A.8.2, A.8.5, A.8.10–A.8.13, A.8.15–A.8.17, A.8.24, A.8.33
confirmed against published control lists; **the standard text itself is paid**, so titles are
corroborated rather than quoted verbatim, and A.8.15 *Logging* in particular is `(call)` on wording.
**ISO/IEC 17021-1:2015**, read from the standard: **9.1.3.3** ("Surveillance audits shall be
conducted **at least once a calendar year, except in recertification years**. The date of the first
surveillance audit … shall not be more than **12 months from the certification decision date**"), the
three-year cycle with the industry-scheme NOTE 3, **9.3.1.3 g** (stage 1 evaluates that internal
audits and management reviews "are being planned and performed"), **9.4.9** (the CB shall require the
client to analyse causes), **9.5.3.2** (major nonconformity unverified **within 6 months after the
last day of stage 2** ⇒ "shall conduct another stage 2"), **9.6.2.2 (a)–(h)** verbatim as reproduced
in §8, **9.6.3.1** (recertification evaluates all requirements), the certificate-content list
(expiry/recertification date, unique code, standard and issue status, **scope of certification**),
**5.2.6** (a CB shall not offer or provide internal audits to its certified clients; two-year
mitigation), **8.5.2 / 8.5.3** (notice of changes both ways). Note the reading that the text does
*not* support: **10.2.6.1–10.2.6.3 are the certification body's own internal audits of itself**
(10.2.6.3: "at least once every 12 months"), **not** a client-side interval — the client's duty is
**ISO 27001 clause 9.2**. Stage-1→stage-2 interval is risk-based (9.3.1.2.4); the six-week/three-month
figures in vendor blogs are `(call)`, not normative. **ISO/IEC 42001:2023**: clauses 4–10 on the
Harmonised Structure, **38 Annex A controls across nine objectives (A.2–A.10)** — policies 3,
internal organisation 2, resources 5, AI risk assessment 4, life cycle 9, data for AI systems 5,
information for interested parties 4, use 3, third-party and customer relationships 3 — with A.6.2.4
(evaluation/validation criteria), A.6.2.6 (operation and monitoring: drift, data poisoning, model
stealing), A.6.2.8 (event logs), A.8 (interested-party information) and A.10.2–A.10.4 read from
published control summaries; 27001→27701 is an extension, not a parallel scheme.

*GDPR*, beyond §6's citations — **Art. 4(5)** with **Recitals 26/28/29** (the pseudonymisation
definition, the "singling out" test inside "means reasonably likely to be used", pseudonymisation as
risk-reduction that does "not preclude any other measures", and the same-controller incentive), cited
as the primary basis rather than **EDPB Guidelines 01/2025** on pseudonymisation, which was **adopted
16 January 2025 for public consultation** and is not a final instrument `(call)`; **Art. 3** (3(1) establishment, 3(2)(a)/(b) targeting and
monitoring, 3(3) public international law) with **Art. 27(1)/(2)** (Union representative; occasional
non-large-scale exemption); **Art. 9(1)/(2)(a)**; **Art. 12(1)–(3)** ("without undue delay and in any
event within one month", extendable "by two further months", with a duty to inform of the extension);
**Art. 13(2)(f)** ("meaningful information about the logic involved, as well as the significance and
the envisaged consequences"); **Art. 17(1)/(2)**; **Art. 18(1)(a)–(d)**, **18(2)** ("with the
exception of storage") and **18(3)** (inform before lifting restriction); **Art. 19** (notify each
recipient "unless this proves impossible or involves disproportionate effort"); **Art. 20(1)(a)/(b)**
(portability only on consent/contract + automated means); **Art. 21(1)–(3)**; **Art. 22(1)–(4)**
including the fact that **22(3) attaches only to 22(2)(a) and (c)**; **Art. 25(1)/(2)** (by design and
by default, expressly covering amount, extent, storage period and accessibility); **Art. 28(2)–(6)**
and **28(10)** — the 28(3) chapeau read from "Processing by a processor shall be governed by a
contract that is binding on the processor …" (the string "shall set out the subject-matter" does not
appear), the (a)–(h) letters, the closing duty to inform immediately when an instruction infringes,
28(4)'s "**the initial processor shall remain fully liable to the controller**", 28(2)'s general
authorisation giving the controller "the opportunity to object **to such changes**", and 28(5)'s codes
of conduct and certification as "an element by which to demonstrate sufficient guarantees as referred
to in paragraphs 1 and 4 **of this Article**", and 28(6)'s standard
contractual clauses; **Art. 30(1)(a)–(g)**, **30(2)(a)–(d)**, **30(3)–(5)** including the three
carve-backs to the under-250 derogation; **Art. 32(1)(a)–(d)** and **Art. 31**; **Art. 35(1)–(3)**,
**35(11)**; **Art. 36** (eight weeks, extendable six); **Art. 37(1)/(2)**; **Art. 82(1)–(5)**;
**Art. 83(3)–(6)** with the tier split — 83(4)(a) €10M/2% for **Arts. 8, 11, 25–39, 42, 43**, 83(5)
€20M/4% for principles/bases, **rights Arts. 12–22**, Chapter V and **Arts. 44–49**, Chapter IX and
58(2) orders, 83(6) repeating 58(2) non-compliance, and **83(3)'s "gravest infringement" cap**.

*AI Act* — **Regulation (EU) 2024/1689 as amended by Regulation (EU) 2026/1744** (in force
2026-07-27; consolidated text CELEX **02024R1689-20260727**): **Art. 2(1)(a)** extraterritorial
scope — "**irrespective of whether those providers are established or located within the Union or in a
third country**"; **Art. 5(1)(ba)/(bb)** prohibitions from 2026-12-02; **Art. 6(1)/(3)(a)–(d)/(4)**
with the derogation chapeau ("does not pose a significant risk of harm … **including by not materially
influencing the outcome of decision making**"), the "shall apply where any of the following conditions
is fulfilled" gate, the profiling override, **Recital 53**'s own examples for (a) ("transforms
unstructured data into structured data … classifies incoming documents … detect duplicates") and its
"no impact on the substance, and thereby the outcome, of decision-making, whether human or automated"
gloss, and 6(4)'s three-sentence structure (document before placing on the market → the 49(2)
registration obligation → provide the documentation on request); **Recital 15**'s biometric-verification
exclusion ("access to a service, unlocking a device or having security access to premises") and
**Recital 58**'s fraud-and-prudential exclusion, both recital numbers live-checked; **Annex III point
5(a)–(d)** with 5(b)'s credit-scoring-of-natural-persons scope and **fraud-detection
exception**; **Arts. 9–15** (risk management, data governance, technical documentation, Art. 12 event
recording with its three purposes, transparency, human oversight, accuracy/robustness/cybersecurity);
**Art. 16/17**, **Art. 25(1)(a)–(c)** including "without prejudice to contractual arrangements
stipulating that the obligations are otherwise allocated", **Art. 26(1)–(9)** (notably **26(5)**
suspension plus the deemed-fulfilment sentence, whose stated scope is only "**the monitoring
obligation set out in the first subparagraph**"; **26(6)** logs kept "**to the extent such logs are
under their control**" for "at least six months, **unless provided otherwise in applicable Union or
national law, in particular in Union law on the protection of personal data**", financial-institution
deployers "maintain[ing] the logs as part of the documentation kept pursuant to the relevant Union
financial service law"; **26(7)** informing "workers' representatives **and the affected workers**";
**26(9)** using the Art. 13 information to carry out the **Art. 35 GDPR / Art. 27 Directive (EU)
2016/680 DPIA**), **Art. 27 FRIA** for 5(b)/5(c) deployers, **Art. 43**, **Art. 48**,
**Art. 49(1)–(5)** including the **49(2) registration of a 6(3) non-high-risk conclusion**, and
**Art. 50(1)** with its "**unless this is obvious from the point of view of a natural person who is
reasonably well-informed, observant and circumspect**" carve-out plus **Art. 50(2)**,
**Art. 53(1)(a)–(d)** with Annex XI/Annex XII minimum content and the **Art. 4(3) Directive (EU)
2019/790** copyright reservation, **Art. 55**, **Art. 71**, **Art. 99(1)/(3)/(4)(a)–(g)/(5)/(6)** with
99(6)'s SME rule ("up to the percentages or amount referred to in paragraphs 3, 4 and 5, **whichever
thereof is lower**"), and **Art. 111(2)/(3)** legacy rules. Dates as amended: 2025-02-02, 2025-08-02, 2026-07-27 (Art. 4
rewritten), 2026-08-02 (general application, Art. 50, Art. 101 — **not** high-risk), 2026-12-02,
2027-08-02, **2027-12-02 Annex III high-risk**, **2028-08-02 Annex I high-risk**, 2030-08-02,
2030-12-31. The declaration-of-conformity article is titled "**EU declaration of conformity**" in the
text — EU before Declaration; searching for "Declaration of conformity" as a heading misses it.

*DORA*, beyond §6's citations — **Regulation (EU) 2022/2554**, applied 2025-01-17: **Arts. 11–12**
("Response and recovery"; "Backup policies and procedures, restoration and recovery procedures and
methods"), **Art. 17** ("ICT-related incident management process", 17(2)'s duty to record every
incident and analyse root causes or significant triggers — the hook the **RTS 2024/1774** recording
standard hangs on), and **Art. 13(1)–(6)** (learning and evolving; the four post-incident review
sub-tests; 13(3) lessons feeding Art. 6(1) and the Arts. 26–27 testing; **13(6)** compulsory awareness and resilience training modules and its
verbatim pointer — third-party providers included in training schemes "**in accordance with Article
30(2), point (i)**"); **Art. 26(1)–(5)** (TLPT at least every three years with authority power to
change frequency; live production systems and authority-validated scope; 26(3) the entity secures
provider participation while "retain[ing] at all times full responsibility"; **26(4) pooled testing
with the provider contracting the external tester directly under one designated entity's direction**;
26(5) cooperation excluding the competent authorities); **Art. 28(1)–(10)**, including the register
of information with **yearly** reporting, the duty to inform the authority "in a timely manner" about
planned CIF arrangements and when a function becomes critical, **28(5)** (only providers complying
with appropriate information security standards; "most up-to-date and highest quality" for CIF),
**28(6)** risk-based audit frequency, commonly accepted audit standards, auditor competence for high
technical complexity and pooled auditors, **28(7)(a)–(d)** the four termination circumstances as
quoted in §12, **28(8)** exit plans comprehensive, documented, "sufficiently tested and reviewed
periodically" per Art. 4(2), with alternative solutions and transition plans for secure and integral
transfer of services **and data**, avoiding disruption / limited regulatory compliance / detriment to
continuity and quality for clients; **Art. 29(1)–(2)** — 29(1)'s accumulated-exposure test on
not-easily-substitutable providers, and 29(2)'s four steps in the text's own order: where further
subcontracting is possible, "weigh benefits and risks … **in particular in the case of an ICT
subcontractor established in a third-country**"; for CIF services, "duly consider the **insolvency law
provisions** that would apply in the event of the ICT third-party service provider's bankruptcy as
well as any constraint that may arise in respect to the **urgent recovery of the financial entity's
data**"; for third-country providers, "in addition … consider the compliance with Union data
protection rules and the **effective enforcement of the law** in that third country"; and assess
whether and how "**potentially long or complex chains of subcontracting** may impact their ability to
fully monitor the contracted functions and the ability of the competent authority to effectively
supervise the financial entity in that respect"; **Art. 30(1)–(5)** with **30(2)(a)–(i)** and
**30(3)(a)–(f)** reproduced as a checklist in §12, including 30(3)(e)(i)–(iv) and the microenterprise
derogation; **Art. 31(1)–(13)** (four cumulative designation criteria, group assessment, coordination
point, six-week reasoned statement, oversight starting no later than one month after notification,
the provider's duty to notify its financial-entity customers, 31(9) the list established, published
and **updated yearly**, 31(11) self-nomination within six months, 31(12) a Union subsidiary within 12
months for designated third-country providers) and **Art. 32** Oversight Forum. Level-2 instruments:
**RTS 2024/1774** (ICT risk management framework), **JTRS 2024/1772** (classification, ≤24h),
**DR 2025/301 + IR 2025/302** (4h initial / 72h intermediate / 1 month final, Annex I templates),
**DR 2024/1773** (CIF contractual policy), **IR 2024/2956** (register templates, first transmission
2025-04-30), **RTS 2025/532** (subcontracting of CIF), **DR 2025/1190** (TLPT: initiation information
within three months of notification, scope document within six, red-team window ≥12 weeks; TIBER-EU
based; **no EU-wide first-TLPT date**). The **first CTPP list, published 18 November 2025, has 19
entities** — Accenture plc, Amazon Web Services EMEA Sarl, Bloomberg L.P., Capgemini SE, Colt
Technology Services, Deutsche Telekom AG, Equinix (EMEA) B.V., Fidelity National Information Services
Inc., Google Cloud EMEA Limited, IBM Corporation, InterXion HeadQuarters B.V., Kyndryl Inc., LSEG Data
and Risk Limited, Microsoft Ireland Operations Limited, NTT DATA Inc., Oracle Nederland B.V., Orange
SA, SAP SE, Tata Consultancy Services Limited — from the ESAs' Joint Committee publication, with the
oversight methodology in **JC 2025/29** (2025-07-15).

Method note for Part II, so a reader can check any claim here: the GDPR, DORA and AI Act statements
are read from **consolidated official texts fetched this date** (EUR-Lex / EUR-Lex consolidated
versions), and the criterion counts above are derived by **enumerating the published criteria and
control lists** rather than from marketing summaries. Where the primary text is paywalled (the ISO
standards' control titles, the AICPA's attestation-standards wording) the citation is corroborated
against multiple published lists and marked `(call)`.
Six errors this pass corrected against the texts, and they are the errors most likely to be in your
own vendor deck: **CC6 ends at CC6.8** (so 33 common criteria, not 34); **ISO/IEC 17021-1
§10.2.6.3's twelve-month internal-audit rule is the certification body auditing itself**, not you;
**TSP 100 says nothing about carve-outs, CUECs or the observation period** — that is the attestation
standards, and it should be cited that way; the phrase "erased and **no longer processed**" is
**Recital 65**, not 66 (66 is the made-public link-erasure duty — the misattribution is in half the
crypto-shredding decks in the market); DORA's incident-management article is **17**, while **12** is
backup policies and restoration, and DORA **29(2)**'s real text is a four-step assessment, not the
circulating paraphrase "a long or complex subcontracting chain … impair[ing] effective monitoring";
and **CC6.3**'s criterion is "roles, responsibilities, or the system design and changes … least
privilege **and segregation of duties**" — the "design of systems and programs" phrasing is not in
TSP 100.
