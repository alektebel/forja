# Context Caching From Scratch

Implement LLM context caching end to end, in pure Python, on a small transformer you
also build yourself. No PyTorch, no numpy, no GPU — the mechanisms are the point, and
they are all visible at this scale.

## Goal

"Context caching" covers several distinct things that get confused with each other.
This directory separates them and builds each one:

| Layer | What it reuses | Exact? | File |
|---|---|---|---|
| KV cache | K/V of tokens in the *same* request | Yes | `kv_cache.py` |
| Prefix cache | K/V of a prefix shared *across* requests | Yes | `prefix_cache.py`, `radix_cache.py` |
| Paged blocks | Physical memory holding those K/V | Yes | `paged_kv_cache.py` |
| Response cache | The generated answer itself | Exact match only | `semantic_cache.py` |
| Cache-aware routing | Which replica already holds your prefix | Yes | `cache_router.py` |

The first four rows are exact optimisations: same output, less compute. The semantic
variant of row four is not, and quantifying exactly how unsafe it is turns out to be
the most useful thing in that file.

## Why this matters

Generating a token requires attending to every previous token's key and value vectors.
Those vectors depend only on tokens at or before their own position, so once computed
they can never change — recomputing them is pure waste.

The waste is enormous. Generating 256 tokens after a 4096-token prompt costs about
**247x** more arithmetic without a KV cache than with one. And once you notice that
prefixes are shared *between* requests too — the same system prompt, the same document,
the same conversation history — the same argument applies again at the fleet level.

The counterweight is memory:

```
KV bytes = 2 (K and V) x layers x heads x head_dim x seq_len x dtype_size
```

Llama-3-8B in fp16 is ~128 KB per token, so a 32k-token context needs ~4.3 GB of KV
cache for **one** sequence. That number, not the model weights, is what limits your
batch size — and it is why half this directory is about memory management rather than
arithmetic.

---

## How to use this directory

The files at the top level are **templates**: every function has a docstring
explaining what to build and why, then `raise NotImplementedError`. You fill
them in. `solutions/` holds complete working versions for when you are stuck or
want to compare afterwards.

```bash
cd context-caching
python3 check.py            # what to build next
# ... implement the functions the checker points at ...
python3 check.py            # re-run; it stops at the first thing not yet done
```

`check.py` runs 16 graded checks against **your** code (it never imports
`solutions/`). Each one names the file, the concept, and — when something is
wrong — what usually causes it:

```
  ✓  1. kv_cache.py          linear algebra helpers
  ✓  2. kv_cache.py          KVCache append/truncate/clone
  ·  3. kv_cache.py          cached == uncached attention
      not implemented yet — kv_cache.py:169 in forward_full()

  2/16 passing, 1 to write

  Next: step 3 — cached == uncached attention (kv_cache.py)
```

Useful invocations:

| Command | Does |
|---|---|
| `python3 check.py` | Run in order, stop at the first unimplemented step |
| `python3 check.py 5` | Run only step 5, while you iterate on it |
| `python3 check.py 5 8` | Run steps 5 through 8 |
| `python3 check.py --all` | Run everything, skipping nothing |
| `python3 <file>.py` | Run that file's own demo once it is implemented |

A check that has not been written yet shows as a grey `·` (a TODO, not a
failure). A red `✗` means your implementation is wrong, and the message says
how. Work top to bottom — later files import earlier ones.

---

## Learning Path

Each file runs standalone with `python3 <file>.py` and prints a measured experiment.
Later files import earlier ones.

### 1. `kv_cache.py` — the foundation

Attention with and without a cache, in pure Python, with an explicit operation counter.

**The check that matters:** `max |forward_full - forward_incremental| == 0`. Not small —
zero. The cache is not an approximation; it is the same arithmetic with the redundant
part deleted. If your numbers differ, you have a transpose or a mask wrong, and every
later file will inherit the bug.

### 2. `tiny_transformer.py` — a real model

A complete character-level GPT: multi-head causal attention, pre-norm, GELU MLP, tied
embeddings. Small enough to run in a second.

**The check:** `generate()` and `generate_no_cache()` must produce identical token
sequences. The weights are random and the text is gibberish — that is fine. What matters
is that both paths produce the *same* gibberish.

Also verify that truncating a cache to length L and re-running token L gives bit-identical
logits. Everything in the next two files depends on that property.

### 3. `prefix_cache.py` — sharing across requests

Block-hash prefix caching, as in vLLM. A block's hash chains from the previous block's
hash, so the key means "this block, in this exact context".

**The lesson:** one changed token invalidates everything after it, permanently. And with
block size 64, a 60-token shared system prompt produces a hit rate of exactly **zero** —
it never fills a single block.

### 4. `radix_cache.py` — sharing exactly

RadixAttention, as in SGLang. A radix tree stores shared prefixes once and matches at
token granularity, with no block quantisation.

**The elegant part:** only leaves are evictable, and an interior node is by definition a
prefix something longer still needs. "Never evict a shared prefix" falls out of the data
structure instead of being a heuristic.

### 5. `paged_kv_cache.py` — the memory underneath

PagedAttention: fixed-size blocks plus a per-sequence block table, exactly like OS
virtual memory.

**Measured result:** ten requests of 45–900 tokens against a 4096-token budget.
Contiguous allocation admits 2 and wastes 88%. Paged admits all 10 and wastes under 3%.
Forking a 200-token sequence three times consumes **zero** additional blocks.

### 6. `semantic_cache.py` — the one that can be wrong

Exact response caching (safe, and often enough on its own) versus embedding-similarity
caching (not safe, at any threshold).

**Measured result:** "flights from Paris to Rome" and "flights from Rome to Paris" score
**1.000** similarity under a bag-of-words embedding. Identical words, opposite meaning,
and the model that could tell them apart is the one you were trying to skip. Precision
stays under ~60% at every threshold from 0.80 to 0.99.

### 7. `cache_router.py` — caching as a load-balancing problem

Once each worker has its own cache, the load balancer decides your hit rate.

**Measured result:** on 16 Zipf-distributed tenants, round robin gets 61% hit rate and
52,000 units of work; cache-aware routing gets 89% and 16,900 — a 3x difference on
identical traffic, from the routing decision alone.

### 8. `serving_demo.py` — capstone

The real model, the radix cache, a multi-turn chat trace. 79% token hit rate, 71% of the
compute saved, ~3x faster, and **bit-identical output**.

---

## The one invariant

> A cache that changes the output is not a cache. It is a bug.

Every exact layer here must satisfy it, and the capstone tests it directly. Make that
assertion the first test in any serving stack you build — it catches off-by-one position
indices, missing deep copies, and stale-prefix splices, all of which otherwise produce
plausible-looking wrong answers.

## The ceiling on any prefix cache

Prefill can be cached. Decode cannot — each decoded token depends on the one before it.
So the best speedup available is `1 / (1 - prefill_share)`:

| Prompt | Generate | Prefill share | Max speedup |
|---|---|---|---|
| 2000 | 20 | 99% | 101x |
| 1000 | 100 | 91% | 11x |
| 500 | 500 | 50% | 2.0x |
| 100 | 1000 | 9% | 1.1x |

Long prompt, short answer (RAG, classification, extraction, reranking) is where prefix
caching pays. Short prompt, long answer (creative generation, reasoning traces) gets
almost nothing — optimise decode instead.

---

## Where this implementation stops

- **Pure Python, single-threaded, no GPU.** Real KV caches live in GPU memory and the
  interesting engineering is in the attention kernel that gathers scattered blocks.
- **Untrained weights.** Correct for studying caching, useless for studying language.
- **No continuous batching.** Requests are served one at a time; a real scheduler
  interleaves prefill and decode across many sequences per forward pass.
- **No quantised or compressed KV** (FP8, KV cache quantisation, MQA/GQA head sharing,
  attention sinks, sliding windows) — all of which change the memory arithmetic
  substantially.
- **No cross-worker cache sharing** (LMCache-style KV transfer between replicas).
- **No preemption or swapping**, though `paged_kv_cache.py` shows why blocks make it
  possible.

## Extensions worth trying

1. **Grouped-query attention.** Share K/V across query heads and recompute the memory
   table — this is the single biggest KV reduction in modern models.
2. **Sliding-window attention with sinks.** Keep the first few tokens plus a recent
   window. Measure how the output degrades as the window shrinks: the honest version of
   "unlimited context".
3. **Continuous batching.** Serve several sequences per forward pass and measure
   throughput against per-request latency.
4. **Chunked prefill.** Split a long prefill across steps so it does not block decode,
   and watch what it does to the tail latency.
5. **Cross-request KV transfer.** Let a worker fetch a prefix's KV from a peer instead
   of recomputing it, and work out when the transfer is cheaper than the prefill.
6. **A distributed prefix cache.** Combine this with [`../dynamo-paper/`](../dynamo-paper/):
   consistent hashing to place prefixes, quorum reads to fetch them. The routing problem
   in `cache_router.py` is a partitioning problem in disguise.

---

## Structure

```
context-caching/
├── README.md
├── check.py              # progress checker — run this first
├── kv_cache.py           # templates with TODOs
├── tiny_transformer.py
├── prefix_cache.py
├── radix_cache.py
├── paged_kv_cache.py
├── semantic_cache.py
├── cache_router.py
├── serving_demo.py       # capstone
└── solutions/            # complete, runnable implementations
```

```bash
cd solutions
python3 kv_cache.py           # attention with and without a cache
python3 tiny_transformer.py   # a real model, cached and uncached
python3 prefix_cache.py       # block-hash prefix caching
python3 radix_cache.py        # radix tree prefix caching
python3 paged_kv_cache.py     # paged blocks, forking, copy-on-write
python3 semantic_cache.py     # exact vs semantic, with the failure table
python3 cache_router.py       # cache-aware load balancing
python3 serving_demo.py       # capstone (~10s, the only slow one)
```

No dependencies beyond the Python 3 standard library.

## Related directories

- [`vllm-engine/`](../vllm-engine/) — PagedAttention and continuous batching at scale
- [`sgl-lang/`](../sgl-lang/) — structured generation, where RadixAttention comes from
- [`ml-inference/`](../ml-inference/) — quantisation and inference optimisation generally
- [`dynamo-paper/`](../dynamo-paper/) — the same "make the expensive thing cheap"
  instinct, applied to distributed storage
- [`contextcite/`](../contextcite/) — a different "context" problem despite the name:
  explaining which parts of a context caused a response, rather than caching it
- [Modal's GPU Glossary](https://modal.com/gpu-glossary/readme/) — the hardware
  half of the `KV bytes = 2 × layers × heads × head_dim × seq_len × dtype_size`
  formula: what GPU RAM, the memory hierarchy and memory bandwidth physically are,
  i.e. what the paged-block row of the taxonomy is spending
- [Fanout's AI-engineering posts](https://fanout.sh/ai-engineering/overview) — the
  closest external second opinion: KV-cache sizing, prefix-cache miss attribution and
  FP8 tradeoffs done as arithmetic, in blog form (catalogued in
  [`EXTERNAL-RESOURCES.md`](../EXTERNAL-RESOURCES.md))
