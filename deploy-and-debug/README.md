# Deploy & Debug

The operational half. The other directories teach you how these systems **work**; this
one teaches you how to **run them** and what to do at 3am when they break.

## The problem this solves

You can implement PagedAttention and still have no idea why your vLLM fleet's TTFT is
60 seconds. You can implement quorums and still not know whether a failing read means
a dead node or a bad config value. Mechanism knowledge and operational knowledge are
different, and the second is mostly learned by being on call.

This directory simulates that. You get a fleet that is genuinely broken — in a way you
did not choose — reporting only what a real deployment reports: **metrics, with no
fault label**. Your job is to work out what is wrong.

## What you build

| Step | File | What it teaches |
|---|---|---|
| 1 | `capacity.py` | The arithmetic that sizes a fleet before you deploy it |
| 2 | `metrics.py` | Percentiles, queueing, fan-out, SLOs and error budgets |
| 3 | `diagnose.py` | **Metrics → root cause.** The centre of the directory |
| 4 | `rollout.py` | Health probes, canaries, staged rollout, auto-rollback |

Plus [`RUNBOOK.md`](RUNBOOK.md) — the actual commands (`vllm serve` flags, `nodetool`,
`nvidia-smi`, Kubernetes probes) that the simulated metrics correspond to.

---

## How to use this directory

Top-level files are **templates**: each function has a docstring explaining what to
build and why, then `raise NotImplementedError`. `solutions/` has complete versions.

```bash
cd deploy-and-debug
python3 check.py            # what to build next
python3 check.py            # re-run after each function
```

`check.py` runs **12 graded checks** against your code. Grey `·` = not written yet,
red `✗` = written but wrong, with the reasoning attached:

```
  ✗  1. capacity.py          KV cache and batch-size math
      Llama-3-8B should be 131,072 bytes/token (128 KiB), got 524,288.
      If you got 524,288 you used the 32 query heads instead of the 8 KV
      heads — that sizes your fleet 4x too large.
```

`deployment.py` is **provided complete — not an exercise.** It models two fleets (an
LLM server and a Dynamo-style store) well enough that faults produce realistic,
*distinguishable* signatures. The numbers are computed from a model of the system, not
hardcoded per fault, so the signatures are consequences rather than answers written in
advance.

---

## The four steps

### Step 1 — `capacity.py` · *small*

Pure arithmetic, and it decides whether your deployment works before it starts.

```
KV bytes/token = 2 × layers × KV_heads × head_dim × dtype_bytes
```

**KV heads, not query heads.** Llama-3-8B has 32 query heads and 8 KV heads (grouped-query
attention). Use the wrong one and you size the fleet 4x too large.

Two results worth knowing by heart:

- Llama-3-8B on an A100-80GB fits **216** concurrent sequences at 2k context and **13**
  at 32k. `max_model_len` is a capacity decision, not a feature toggle.
- `N=3, R=2, W=2` survives **one** node loss, not two. If your availability target
  assumes two concurrent failures, you need `N=5`.

### Step 2 — `metrics.py` · *small*

Averages hide exactly the failures users notice. On a realistic latency sample the mean
is 158ms while p99 is 1217ms — and only 11% of requests are above the mean.

Three effects to internalise:

| Effect | The number |
|---|---|
| **Queueing** | Wait = service × u/(1−u). At 90% utilisation you wait **9x**; at 99%, **99x** |
| **Fan-out** | A request touching N backends is as slow as the slowest. P(none slow) = 0.99^N |
| **Error budget** | 99.9% over 30 days = **43 minutes**. Alert on burn rate, not error rate |

### Step 3 — `diagnose.py` · *medium — the centre*

Eleven faults, diagnosed from metrics alone. The method:

1. Start from the **symptom** a user would report
2. Find the metric that is **anomalous**, not merely high — "TTFT is 60s" is a symptom,
   "only 1 sequence fits in KV" is a cause
3. Separate **fleet-wide from per-replica** — an average hides a single bad host completely
4. Read the **configuration** alongside the symptoms
5. Know your **confusable pair**

The two pairs that matter, because both look identical and have opposite fixes:

> **`undersized_kv` vs `overloaded`** — both show preemption, high TTFT, timeouts.
> Separator: **`max_concurrent_seqs`**. One sequence fitting means the budget is wrong;
> a normal number with 4x traffic means it is load. Fixing the wrong one buys you a
> pointless scale-up or a no-op config change.

> **`node_down` vs `quorum_too_strict`** — identical node count, identical hint queue.
> Separator: **R + W against N**. One node down with R=2 W=2 N=3 is survivable by
> design; the same outage with R=3 W=3 fails every request. Replace hardware, or fix a
> config value — opposite actions.

### Step 4 — `rollout.py` · *medium*

**Liveness vs readiness** is the distinction that causes the most self-inflicted outages:

- `liveness` — "is this process wedged?" Failing it **restarts** the container
- `readiness` — "should this replica get traffic?" Failing it **removes it from the LB**

A model server loading 16GB of weights is alive but not ready for two minutes. Without a
startup probe, liveness kills it mid-load — forever — and the crash loop looks exactly
like a bad image.

And the canary lesson: a canary that is **3x slower** but has only seen **90 requests**
must return `hold`, not `rollback`. Deciding on 90 samples is guessing whichever way it
goes. Shipping on an underpowered canary is worse than not canarying — it manufactures
confidence.

---

## What this is not

- **Not a Kubernetes tutorial.** No YAML is applied, no cluster is created. `RUNBOOK.md`
  shows the probe config; running it is on you.
- **Not real load testing.** The simulator uses an M/M/1-ish queueing model. Real fleets
  have batching effects, chunked prefill and NUMA behaviour this does not capture.
- **Not a substitute for being on call.** It gives you the reasoning and the confusable
  pairs; it cannot give you the muscle memory or the adrenaline.
- **The fault set is small** — 11 faults, chosen because they are common and because
  they teach a separator. Real incidents include disk, DNS, certificate expiry, noisy
  neighbours and the many-things-at-once case.

## Extensions worth trying

1. **Add a fault.** Disk-full on one store node, or a tokenizer mismatch that silently
   destroys the cache hit rate. Give it a distinguishable signature, then write the rule.
2. **Make the faults compound.** Two at once — a slow replica *and* an undersized cache.
   Real incidents rarely arrive one at a time, and rule ordering starts to matter.
3. **Add time.** Make `observe()` return a series rather than a snapshot, then diagnose
   from trends. "Rising" is often more diagnostic than "high".
4. **Point it at something real.** Run vLLM locally, scrape `/metrics`, and feed a real
   snapshot into your `diagnose_serving`. The field names in `deployment.py` are
   deliberately close to vLLM's.
5. **Write the postmortem.** For each fault: what would the alert have said, how long to
   detect, what would have prevented it.

---

## Structure

```
deploy-and-debug/
├── README.md
├── RUNBOOK.md            # the real commands: vllm, nodetool, nvidia-smi, k8s
├── check.py              # progress checker — run this first
├── deployment.py         # PROVIDED complete: fleets you can break
├── capacity.py           # templates with TODOs
├── metrics.py
├── diagnose.py
├── rollout.py
└── solutions/
```

```bash
cd solutions
python3 deployment.py     # the fleets and their fault signatures
python3 capacity.py       # sizing math
python3 metrics.py        # percentiles, queueing, SLOs
python3 diagnose.py       # 11 faults diagnosed from metrics alone
python3 rollout.py        # probes, canaries, staged rollout
```

Pure Python 3 standard library. Everything runs in about a second.

## Related directories

- [`dynamo-paper/`](../dynamo-paper/) — the store this one operates
- [`context-caching/`](../context-caching/) — the serving mechanisms this one sizes
- [`system-design/`](../system-design/) — circuit breakers, backpressure, rate limiting
- [`EXTERNAL-RESOURCES.md`](../EXTERNAL-RESOURCES.md) — roadmap.sh/devops (the
  map of this territory), r/devops (the incident war stories), Edureka's DevOps
  interview banks (the vocabulary an interviewer expects)
