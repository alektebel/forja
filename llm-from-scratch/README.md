# LLM From Scratch

Build the parts of a language model that people wave at — the tokenizer, attention,
sampling, the KV cache, rotary positions — in pure standard-library Python, and see the
numbers each one produces.

## Scope, honestly

A frontier model is a datacenter. A model worth **understanding** is a few hundred lines
of arithmetic with the right shape. This directory implements the mechanisms that
everything else in an LLM is assembled from, on tiny inputs, with no dependencies:

| File | The mechanism | The thing people get wrong |
|---|---|---|
| `tokenizer.py` | Byte-pair encoding | The merge order is a *rank*, not a left-to-right pass |
| `attention.py` | Scaled dot-product attention | Softmax must subtract the max or it overflows |
| `sampling.py` | Temperature, top-k, top-p | top-p keeps the token that crosses the threshold |
| `kv_cache.py` | Incremental decoding | The cached path must be bit-identical to the full one |
| `rope.py` | Rotary position embeddings | Rotation is what makes attention depend on *relative* position |
| `architectures.py` | MoE, GQA, MLA, SSM, diffusion, TTT, Titans, MoD | Each has one non-obvious invariant: the router contract, WᵀW = I, the exp(δA) compounding, the pass-through row |
| `parallelism.py` | TP, ZeRO, GPipe, mixed precision, FlashAttention, checkpointing, SP, CP, EP | Sharded must equal unsharded; column shards concatenate, row shards all-reduce |

No PyTorch, no NumPy, no GPU. If a directory cannot run with `python3 file.py`, the
lesson gets buried under an install.

---

## How to use this directory

Templates are at the top level. Complete versions are in `solutions/`.

```bash
cd llm-from-scratch
python3 check.py            # what to build next
python3 check.py            # re-run after each function
```

**30 graded checks** against **your** code. A red `✗` names the likely cause:

```
  ✗  5. attention.py         softmax: stable, sums to one
      softmax([1000, 1001]) overflowed. exp(1000) is larger than a float
      can hold, so you must subtract the row max first: exp(x - max).
      The result is identical, the overflow is gone.
```

---

## The mechanisms

### Core forward pass (stages 1–13)

Five files, thirteen stages — the part every LLM is built from.

### `tokenizer.py` — the merge is a rank

BPE starts from raw bytes (so every string is representable, no `[UNK]`), counts adjacent
pairs, and repeatedly merges the most frequent one into a new symbol.

**The limit case:** when two pairs tie, the choice must be deterministic, or the same
corpus trains a different tokenizer every run and nothing downstream is reproducible. And
at encode time you must apply the **lowest-rank merge first**, in rank order — not sweep
left to right. Those two rules are the whole difference between a tokenizer and a
plausible-looking one that splits text differently than it was trained.

### `attention.py` — subtract the max

Attention is `softmax(QKᵀ/√d)·V`. The only numerically interesting line is the softmax:
compute `exp(xᵢ - max(x))`, not `exp(xᵢ)`. With logits of 1000 the naive version returns
`inf/inf = nan`, and the bug only appears once your inputs get large — which is why it
survives small tests.

**The limit case:** the causal mask. Position 0 must not be able to see position 1.
Masking to `-inf` *before* the softmax (not after) is what makes each row ignore the
future and still sum to 1.

### `sampling.py` — the crossing token counts

Temperature divides the logits. top-k keeps the `k` largest. top-p (nucleus) keeps the
smallest set of tokens whose cumulative probability reaches `p` — **including the token
that crosses the threshold**, which is the one people drop by using `>` instead of `≥`.

**The limit case:** temperature 0 must be exactly greedy (argmax), not "very sharp". And
a seeded RNG must give the same sample twice, or evals are noise.

### `kv_cache.py` — exactness, then the cost model

An autoregressive model at step *t* only needs the new query against all past keys and
values. Caching them turns per-step attention from O(t·d) recompute into O(d) work plus a
cache append.

**The limit case:** the cached result must be **bit-identical** to recomputing attention
over the full sequence. A cache that is merely close is a cache that changes your model's
output, and you will chase that difference for a day. Once it is exact, the cost model
shows why prefill is quadratic and decode is linear — the reason batching and paging exist.

### `rope.py` — relative, not absolute

Rotary embeddings rotate each `(x₂ᵢ, x₂ᵢ₊₁)` pair by an angle proportional to position.
The point is a single identity: the dot product of a query at position *p* with a key at
position *p+d* depends only on *d*, never on *p*.

**The limit case:** check the norm is preserved (rotation, so it must be) and that the
relative dot product is invariant across positions. If it drifts with *p*, your frequencies
are wrong and long-context behaviour degrades in a way short tests will not show.

### `architectures.py` — the modern stack (stages 14–21)

Eight mechanisms that diverge from vanilla attention + MLP, one function each:

- **MoE** — the routing contract: top-k by score, renormalise over the *chosen* experts only.
- **GQA** — each query head maps to KV head `h % n_kv`; 8 KV heads for 32 query heads is a
  quarter-size cache.
- **MLA** — compress with an orthonormal matrix, decompress with its transpose; WᵀW = I makes
  the full-size roundtrip exact, and a small latent *must* lose information.
- **SSM** — `h' = exp(δA)·h + δBx`; the input-dependent gate δ is what "selective" means,
  and exp(δA) compounds every step, which is the memory horizon.
- **Diffusion LM** — mask with the handed `Random` only; unmask the most-confident masked
  positions per round; already-final tokens are untouchable.
- **TTT** — the layer trains itself at test time: `w' = w + 2·lr·err·x`. Later tokens
  overwrite earlier ones — measure the first token's fit after a full pass.
- **Titans** — memory updated by surprise + momentum with weight decay; the persistent
  (frozen) and episodic (updatable) memories score separately.
- **MoD** — exactly `capacity` positions go through the layer; every other row passes
  through *unchanged*. The pass-through is the entire FLOP saving.

### `parallelism.py` — the training datacenter (stages 22–30)

Nine distributed-training mechanisms, each reduced to the arithmetic or the accounting,
no processes spawned:

- **Tensor parallelism** — column shards *concatenate*; row shards *all-reduce*. Get the
  two confused and the numbers are wrong, not just slow.
- **ZeRO / FSDP** — Adam holds 4 floats per param; stage 1/2/3 partitions state, +gradients,
  +parameters. ZeRO-3 across 4 workers is exactly a quarter.
- **GPipe** — the microbatch staircase and the bubble: (stages−1)/(stages−1+microbatches).
- **Mixed precision** — fp16 rounds halfway ties to even; grads are fp16-rounded but the
  update lands on fp32 master weights; loss scaling keeps small gradients alive.
- **FlashAttention** — the running-max fold: rescale the accumulator by exp(old−new) each
  tile, never materialising the t×t score matrix. Tiled must equal naive to 1e-9.
- **Activation checkpointing** — store every k-th block, recompute the rest; the recomputed
  activations must match eager *exactly*, or the gradients are wrong.
- **Sequence / context parallelism** — partition along the sequence; partial sums reduce,
  ring attention carries a running softmax across KV shards while the query positions stay put.
- **Expert parallelism** — expert e lives on worker e % n; dispatch groups tokens by their
  expert's worker, combine scatters back.

**The limit case for all nine:** the sharded computation must produce the *same numbers* as
the unsharded one. A parallelism scheme that is approximately right is just a bug.

---

## Where this stops

Deliberately left out, so you know the boundary:

- **No real training loop.** The parallelism stages model the collectives' arithmetic and
  the memory accounting, not a data pipeline or a real optimizer schedule.
- **No real weights.** Inputs are small hand-built vectors so the arithmetic is visible.
- **No multi-head plumbing beyond what a stage needs** — GQA gets heads because sharing them
  *is* the mechanism; nothing else reshapes.
- **O(n²) on purpose.** The naive attention is the readable one; FlashAttention (stage 26) is
  where the tiled version earns its memory saving.

When all thirty checks pass, the next step is `context-caching/`, which wires a KV cache
into a real (tiny) transformer and makes you keep the output bit-identical while you
page, prefix-share and evict.
