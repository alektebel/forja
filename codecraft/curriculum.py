"""Built-in course metadata: what each graded check teaches, and how to unstick.

This is the default curriculum shipped with the existing projects in the repo.
An authored course overrides it entirely with its own `course.py` (see
`scaffold.py`), so this file is only a fallback for directories that carry a
plain `check.py`.

Keyed by (project directory, check index). Titles/files are read from the
checker output at runtime, so this file never has to stay in sync with them —
a missing entry simply degrades gracefully to the checker's own detail.
"""

# Concept tags are shared across projects on purpose: the same tag failing in
# three different directories is a pattern in how you think, not bad luck.
# Keep this list small and reused.
TAGS = {
    "merging", "determinism", "ordering", "boundary", "numerical-stability",
    "masking", "exactness", "cost-model", "data-structure", "aliasing",
    "invariants", "hashing", "eviction", "tree-structure", "allocation",
    "cow", "similarity", "routing", "plumbing", "attribution", "regression",
    "optimization", "partitioning", "consistency", "availability",
    "reconciliation", "membership", "lifecycle", "stateless-vs-stateful",
    "authorization", "messaging", "storage", "networking", "capacity",
    "observability", "queueing", "slo", "diagnosis", "rollout", "encoding",
    "assembly", "symbol-resolution", "execution", "parsing", "codegen",
    "register-allocation", "simt-divergence", "synchronization",
    "sparsity", "compression", "recurrence", "denoising", "inner-loop",
    "sharding", "collectives", "schedule", "precision", "tiling",
    "recompute", "partition", "online-softmax", "memory-horizon",
}

# project -> {check index -> {"tags": [...], "action": str, "predict": str}}
CURRICULUM = {
    "llm-from-scratch": {
        1: {"tags": ["merging"],
            "action": "Write get_pair_counts as a dict of adjacent pairs, then "
                      "merge_pair with an index that SKIPS PAST each merge, so "
                      "[1,1,1] becomes [9,1] and not two overlapping merges.",
            "predict": "In [1,1,1,2], how many adjacent (1,1) pairs? (two, not three)"},
        2: {"tags": ["determinism", "ordering"],
            "action": "In train_bpe, take the most frequent pair but break ties "
                      "by the smallest pair, and start new ids at 256. Determinism "
                      "is the whole point — same corpus, same table.",
            "predict": "Train twice on one corpus: identical merge table?"},
        3: {"tags": ["ordering"],
            "action": "Make encode repeatedly apply the LOWEST-RANK merge anywhere "
                      "in the sequence (not a left-to-right sweep); decode expands "
                      "ids bottom-up.",
            "predict": "encode('aba') with (98,97)->256, (97,98)->257 gives [97,256]."},
        4: {"tags": ["numerical-stability"],
            "action": "In softmax, subtract the row max before exp: exp(x - max). "
                      "The result is identical and can never overflow.",
            "predict": "softmax([1000,1001]) — finite, and sums to 1."},
        5: {"tags": ["masking", "exactness"],
            "action": "Apply the causal mask as -inf BEFORE the softmax, so each row "
                      "still sums to 1 and position 0 attends only to itself.",
            "predict": "the output row for position 0 equals V[0]."},
        6: {"tags": ["boundary", "determinism"],
            "action": "temperature 0 is hard greedy: one-hot at the argmax, -inf "
                      "everywhere else. Temperature divides the logits.",
            "predict": "sample(temp=0) is deterministic — the tail can never fire."},
        7: {"tags": ["ordering", "boundary"],
            "action": "top_k keeps the k largest and breaks ties by smallest index, "
                      "keeping BOTH tied values.",
            "predict": "top-2 of [1,3,3,2] keeps indices 1 and 2."},
        8: {"tags": ["boundary"],
            "action": "top_p keeps the smallest set whose cumulative probability "
                      "reaches p, INCLUDING the token that crosses it (>= not >).",
            "predict": "[.5,.3,.15,.05] at p=.9 keeps the .15 token."},
        9: {"tags": ["determinism"],
            "action": "Thread the Random instance you were handed through every "
                      "sampling call; never touch the global random module.",
            "predict": "one seed twice gives the same 50 samples."},
        10: {"tags": ["data-structure"],
             "action": "KVCache stores parallel key/value lists; append, and make "
                       "len/keys/values reflect exactly what was appended.",
             "predict": "the length after two appends."},
        11: {"tags": ["exactness"],
             "action": "cached_step must reproduce recompute_step to <1e-9: append "
                       "the new K/V and attend over ALL cached rows — read the cache.",
             "predict": "dropping the last key must change the output."},
        12: {"tags": ["cost-model"],
             "action": "Count interactions: recompute is O(t*d) per step (quadratic "
                       "overall), the cache is O(d) plus the append (linear).",
             "predict": "doubling the prompt multiplies prefill work by ~4."},
        13: {"tags": ["invariants"],
             "action": "Rotate each (x2i, x2i+1) pair by pos*freq; check the norm is "
                       "preserved and dot(q@p, k@p+d) ignores p entirely.",
             "predict": "the relative dot product is identical for every p."},
        14: {"tags": ["routing", "sparsity"],
             "action": "Router logits are dot products; route to the top_k experts by "
                       "score (ties by lower index) and renormalise over the CHOSEN ones only.",
             "predict": "top-2 of scores [1.0, 0.2, 1.08] picks experts 2 and 0."},
        15: {"tags": ["sharding", "compression"],
             "action": "Group KV heads into contiguous groups; each query head maps to "
                       "KV head h % n_kv, cycling when there are more query heads.",
             "predict": "32 query heads, 8 KV heads: the cache is a quarter the size."},
        16: {"tags": ["compression", "exactness"],
             "action": "Compress with an orthonormal seeded matrix (y = Wx), decompress "
                       "with its transpose (x' = W^T y). W^T W = I makes the full-size "
                       "roundtrip exact; a small latent must lose information.",
             "predict": "the roundtrip error with latent = full dim (must be ~0)."},
        17: {"tags": ["recurrence"],
             "action": "h' = exp(delta*A)*h + delta*B*x, y = C·h'. delta is the "
                       "input-dependent gate: exp(delta*A) compounds every step.",
             "predict": "an impulse with delta=1, A=-1 decays: 1, e^-1, e^-2..."},
        18: {"tags": ["denoising", "determinism"],
             "action": "Mask with the handed Random instance only; denoise unmasks the "
                       "keep most-confident MASKED positions — already-final tokens are ignored.",
             "predict": "rounds to fully unmask 10 tokens keeping 4/round (round up)."},
        19: {"tags": ["inner-loop"],
             "action": "One gradient step on (target - w·x)^2: w' = w + 2*lr*err*x. Train "
                       "in sequence order; later tokens overwrite earlier ones.",
             "predict": "error on the FIRST token after training the whole sequence (substantial)."},
        20: {"tags": ["memory-horizon", "inner-loop"],
             "action": "m' = m + lr*(surprise*x + momentum*prev_update), then 10% weight "
                       "decay. Momentum carries the previous update through the window.",
             "predict": "how many trailing tokens still influence the memory (the window)."},
        21: {"tags": ["sparsity", "routing"],
             "action": "Pick exactly capacity positions by score (ties by lower index); "
                       "every other row PASSES THROUGH UNCHANGED — that is the FLOP saving.",
             "predict": "the multiply-adds skipped: (rows - capacity) * d."},
        22: {"tags": ["collectives", "sharding"],
             "action": "Column shards hold all rows / a band of columns and CONCATENATE; "
                       "row shards hold a band of rows / all columns and ALL-REDUCE.",
             "predict": "which path needs the all-reduce (row-parallel)."},
        23: {"tags": ["sharding", "memory-horizon"],
             "action": "Adam holds 4 floats per param (w, g, m, v). ZeRO partitions: "
                       "stage 1 the optimizer state, 2 + gradients, 3 + parameters.",
             "predict": "ZeRO-3 across 4 workers: exactly a quarter of the full footprint."},
        24: {"tags": ["schedule", "partition"],
             "action": "Stage s starts microbatch t-s at step t (the staircase). Bubble "
                       "= (stages-1) / (stages-1 + microbatches) — more microbatches shrink it.",
             "predict": "the bubble fraction for 4 stages, 8 microbatches (3/11)."},
        25: {"tags": ["precision", "numerical-stability"],
             "action": "fp16 rounds to even at halfway (1+2^-11 stays 1.0; 1+2^-10+2^-11 "
                       "steps up). Grads are fp16-rounded; the update lands on fp32 masters.",
             "predict": "summing 60000+60000 in fp16 (overflow at 65504)."},
        26: {"tags": ["tiling", "online-softmax"],
             "action": "Fold tiles with a running max: rescale the accumulator by "
                       "exp(old_max - new_max) each time. Never materialise the t*t scores.",
             "predict": "tiled vs naive output difference (~0 to 1e-9)."},
        27: {"tags": ["recompute", "exactness"],
             "action": "Keep a checkpoint every k blocks, then RECOMPUTE the rest segment "
                       "by segment. The recomputed activations must match eager exactly.",
             "predict": "stored + one-block-recompute vs every-block (the saving)."},
        28: {"tags": ["collectives", "exactness"],
             "action": "Scatter the sequence into shards, reduce partial sums of x and x^2 "
                       "across workers, then normalise. Must match single-worker LayerNorm.",
             "predict": "sequence-parallel vs local LayerNorm difference (~0)."},
        29: {"tags": ["online-softmax", "partition"],
             "action": "The query positions are FIXED across ring steps; only the KV shard "
                       "moves. Mask by absolute position, fold with the running max.",
             "predict": "query 0's denominator after every shard (only key 0 is unmasked)."},
        30: {"tags": ["partition", "routing"],
             "action": "Expert e lives on worker e % n_workers; dispatch groups token "
                       "indices by their expert's worker, the combine scatters them back.",
             "predict": "tokens [0,1,2,0] with experts [0,1,2,0] on 2 workers: [[0,2,3],[1]]."},
    },

    "context-caching": {
        1: {"tags": ["plumbing"],
            "action": "Implement the plain-list vector helpers (dot, softmax, "
                      "matmul) first — everything above is built from them.",
            "predict": "the shape of a 2x3 times 3x2 result."},
        2: {"tags": ["data-structure"],
            "action": "append/truncate/clone must keep keys and values aligned; "
                      "clone must deep-copy rows, not share them.",
            "predict": "mutating a clone leaves the original untouched."},
        3: {"tags": ["exactness"],
            "action": "Cached attention must equal uncached attention within "
                      "tolerance — append the new K/V and attend over all rows.",
            "predict": "the max difference between cached and uncached."},
        4: {"tags": ["cost-model"],
            "action": "Prefill is quadratic in prompt length; decode is linear. "
                      "Count multiply-adds to make the difference concrete.",
            "predict": "the ratio of prefill work at 128 vs 64 tokens."},
        5: {"tags": ["numerical-stability"],
            "action": "layer_norm needs a variance epsilon; gelu uses the tanh "
                      "approximation. Match the checker's tolerance exactly.",
            "predict": "layer_norm of a constant vector."},
        6: {"tags": ["exactness"],
            "action": "Generation with the cache must be token-identical to the "
                      "no-cache path — same logits, same argmax.",
            "predict": "the generated token sequence with and without cache."},
        7: {"tags": ["aliasing"],
            "action": "truncate must cut keys and values together; clone must not "
                      "share rows; prefix reuse must not mutate the source request.",
            "predict": "reusing a prefix twice gives the same continuation."},
        8: {"tags": ["hashing"],
            "action": "Hash each token block, then CHAIN: the child's hash includes "
                      "the parent's, so identical prefixes share one key.",
            "predict": "do two prompts sharing a prefix produce one shared block?"},
        9: {"tags": ["eviction", "aliasing"],
            "action": "Match the longest cached prefix, evict by policy, and keep "
                      "per-request isolation — one request must not evict another's "
                      "pinned blocks.",
            "predict": "the hit length for a prompt sharing 2 of 3 blocks."},
        10: {"tags": ["tree-structure"],
             "action": "Radix matching walks edge labels and SPLITS a node when a "
                       "prefix ends mid-edge — test the split explicitly.",
             "predict": "the tree shape after inserting 'abc' then 'abd'."},
        11: {"tags": ["eviction"],
             "action": "Evict leaves first; pinned nodes are exempt. Walk to find "
                       "a valid victim rather than evicting the root.",
             "predict": "which node is evicted when all are leaves."},
        12: {"tags": ["allocation"],
             "action": "The block allocator hands out fixed-size blocks and grows "
                       "the block table; track free/used and refcounts.",
             "predict": "how many blocks a 17-token sequence with block=8 needs."},
        13: {"tags": ["cow", "aliasing"],
             "action": "fork shares blocks by reference (refcount++); a WRITE to a "
                       "shared block copies it first (refcount--, new block).",
             "predict": "does writing to a fork change the parent's tokens?"},
        14: {"tags": ["similarity", "boundary"],
             "action": "Exact cache first, then a semantic threshold — tune it so "
                       "near-duplicates hit but distinct prompts miss.",
             "predict": "whether a reworded question should be a hit."},
        15: {"tags": ["routing"],
             "action": "Route each request to the replica that already holds its "
                       "prefix; fall back to least-loaded when nobody does.",
             "predict": "the hit rate after routing vs round-robin."},
        16: {"tags": ["plumbing", "exactness"],
             "action": "Capstone: wire prefix + paged + semantic caches together and "
                       "keep the output identical to the uncached model.",
             "predict": "compute saved (%) and whether output is bit-identical."},
    },

    "contextcite": {
        1: {"tags": ["partitioning"],
            "action": "Split text into sources with offsets precise enough to "
                      "rebuild the full context byte-for-byte.",
            "predict": "the number of sources in a 3-sentence passage."},
        2: {"tags": ["plumbing"],
            "action": "Rebuild the ablated context from a kept-source mask, "
                      "preserving order and spacing exactly.",
            "predict": "the context when only source 2 is kept."},
        3: {"tags": ["numerical-stability"],
            "action": "logit-prob = logit[target] - logsumexp(logits); subtract the "
                      "max inside logsumexp so it never overflows.",
            "predict": "log-prob of a token with logit 0 among [0,0,0]."},
        4: {"tags": ["aggregation"],
            "action": "Aggregate per-token logit-probs into one response score — "
                      "pick sum or mean and apply it consistently.",
            "predict": "sum vs mean on a 4-token response."},
        5: {"tags": ["attribution"],
            "action": "Sample a binary design matrix over sources; each row is a "
                      "kept/dropped subset of the context.",
            "predict": "how many distinct rows a 5-source sampler can produce."},
        6: {"tags": ["optimization"],
            "action": "Coordinate-descent LASSO: soft-threshold each coordinate and "
                      "standardise inputs so the penalty is comparable across sources.",
            "predict": "soft_threshold(0.5, 1.0)."},
        7: {"tags": ["optimization"],
            "action": "Fit should recover a known sparse signal — check the support "
                      "and the coefficient signs against ground truth.",
            "predict": "which coefficients are exactly zero."},
        8: {"tags": ["attribution", "optimization"],
            "action": "End-to-end: abduction (drop sources) -> design matrix -> LASSO "
                      "-> per-source attribution scores.",
            "predict": "the coefficient on the source the answer actually needs."},
        9: {"tags": ["cost-model"],
            "action": "Span attribution reuses the same ablation samples — assert the "
                      "number of model calls does NOT grow with span count.",
            "predict": "model calls with 1 source vs 4 spans."},
        10: {"tags": ["regression"],
             "action": "Spearman: rank both vectors and correlate the ranks; assign "
                       "average ranks on ties.",
             "predict": "Spearman of a perfectly reversed ranking."},
        11: {"tags": ["regression"],
             "action": "Held-out LDS and top-k drop: measure whether the surrogate "
                       "predicts on ablations it never saw.",
             "predict": "LDS of a perfect ranker."},
        12: {"tags": ["attribution"],
             "action": "Applications: verify a claim by ablation, and prune sources "
                       "the surrogate calls dead.",
             "predict": "whether removing the top source flips the answer."},
        13: {"tags": ["attribution"],
             "action": "Detect a poisoned source: its coefficient should dominate, "
                       "and no honest source should be a perfect predictor.",
             "predict": "the coefficient profile with one injected source."},
        14: {"tags": ["regression", "attribution"],
             "action": "Leave-one-out fails under redundancy — two identical sources "
                       "split the credit and each looks unimportant. Reproduce it.",
            "predict": "each duplicate's leave-one-out score."},
    },

    "dynamo-paper": {
        1: {"tags": ["partitioning"],
            "action": "Ring: place a node's tokens, find a key's successor clockwise, "
                      "and remove the node's tokens when it leaves.",
            "predict": "who coordinates a key between two nodes."},
        2: {"tags": ["partitioning", "consistency"],
            "action": "preference_list walks virtual tokens clockwise and must SKIP "
                      "nodes already chosen, returning N DISTINCT nodes.",
            "predict": "N when the ring has fewer than N nodes."},
        3: {"tags": ["partitioning"],
            "action": "Adding/removing a node should move about 1/N of the keys; "
                      "measure balance as max/min load across nodes.",
            "predict": "the fraction of keys that move when one node joins."},
        4: {"tags": ["partitioning"],
            "action": "Strategy 3: fixed partitions (a fixed Q), each node owns "
                      "several — routing is a table lookup, not a ring walk.",
            "predict": "how key movement compares to the ring."},
        5: {"tags": ["ordering"],
            "action": "Vector clocks compare pointwise: equal, descendant, ancestor, "
                      "or concurrent — get all four cases right.",
            "predict": "the relation between {A:1} and {A:1,B:1}."},
        6: {"tags": ["reconciliation"],
            "action": "On conflicting siblings, reconcile with the paper's rule and "
                      "MERGE the clocks so the result dominates both.",
            "predict": "the merged clock of two concurrent writes."},
        7: {"tags": ["ordering"],
            "action": "Truncate the clock by dropping the oldest entries when it "
                      "exceeds the cap, keeping recent causality.",
            "predict": "which entries survive a cap of 2."},
        8: {"tags": ["data-structure"],
            "action": "A storage node keeps the value plus all its siblings; a read "
                      "returns every sibling, not just the newest.",
            "predict": "the sibling count after two concurrent writes."},
        9: {"tags": ["quorum", "consistency"] if False else ["consistency"],
            "action": "N/R/W put and get: write to N preference nodes, read from R, "
                      "and R+W>N is what guarantees overlap.",
            "predict": "whether R=1,W=1,N=3 can read a stale value."},
        10: {"tags": ["consistency"],
             "action": "Reads collect siblings from R nodes; read repair pushes the "
                       "newest value back to the stale replicas it saw.",
             "predict": "which replicas get repaired on a read."},
        11: {"tags": ["availability", "consistency"],
             "action": "Sloppy quorum: when a preference node is down, write to the "
                       "next live node and store a HINT saying where it belongs.",
             "predict": "hint count after one node is down."},
        12: {"tags": ["availability"],
             "action": "Deliver hints when the owner returns, then delete the local "
                       "copy — delivery must be idempotent.",
             "predict": "what happens if the same hint is delivered twice."},
        13: {"tags": ["tree-structure"],
             "action": "Merkle tree: hash leaves (key ranges), hash pairs upward; the "
                       "diff walks only branches whose hashes differ.",
             "predict": "how many nodes one changed key dirties."},
        14: {"tags": ["consistency"],
             "action": "Anti-entropy is a UNION of values, reconciled with the same "
                       "clock logic — not blind last-write-wins.",
             "predict": "the value after syncing two divergent replicas."},
        15: {"tags": ["membership"],
             "action": "Gossip converges in O(log S): each round every node tells a "
                       "few peers; track rounds to full knowledge.",
             "predict": "rounds for 64 nodes to all learn one fact."},
        16: {"tags": ["membership"],
             "action": "Failure detection is local (heartbeat + suspicion), and seeds "
                       "are how a brand-new node joins without a full member list.",
             "predict": "how a node is declared dead with no central registry."},
        17: {"tags": ["plumbing"],
             "action": "Capstone: run the cart workload against the full cluster and "
                       "hit the stated availability target.",
             "predict": "successful-write rate under 30% node churn."},
    },

    "deploy-and-debug": {
        1: {"tags": ["capacity"],
            "action": "KV cache bytes/token = 2 * layers * KV_HEADS * head_dim * "
                      "bytes. Using query heads sizes the fleet 4x too large.",
            "predict": "bytes/token for Llama-3-8B (8 KV heads)."},
        2: {"tags": ["capacity", "availability"],
            "action": "Size the fleet from concurrency and tokens/s, then subtract "
                      "the failure tolerance R+W>N implies.",
            "predict": "how many nodes can die and quorum still hold."},
        3: {"tags": ["observability"],
            "action": "Percentiles are not averages: sort and take the rank. p99 is "
                      "where the outliers live.",
            "predict": "p50 and p99 of [1,2,3,4,100]."},
        4: {"tags": ["queueing"],
            "action": "Little's law and fan-out: one slow dependency multiplies the "
                      "tail across parallel calls.",
            "predict": "tail latency with 10 parallel 100ms calls."},
        5: {"tags": ["slo"],
            "action": "SLO is an objective over a window; error budget = 1 - SLO; "
                      "burn rate is how fast you are spending it.",
            "predict": "the error budget for 99.9% over 30 days."},
        6: {"tags": ["diagnosis"],
            "action": "Map each fault to its metric signature: KV full -> cache-miss "
                      "spike; overload -> queue growth.",
            "predict": "the signature of a full KV cache."},
        7: {"tags": ["diagnosis"],
            "action": "Undersized KV and overload look similar — separate them by "
                      "cache-hit rate and memory, not latency alone.",
            "predict": "which metric distinguishes the two."},
        8: {"tags": ["diagnosis"],
            "action": "Store faults: node down, hint backlog, and gossip disagreement "
                      "each have a distinct fingerprint.",
            "predict": "the fingerprint of hinted-handoff backlog."},
        9: {"tags": ["diagnosis"],
            "action": "Node down with QUORUM MET (hint backlog) differs from "
                      "STRICT-quorum failure (write errors).",
            "predict": "which one still serves reads."},
        10: {"tags": ["lifecycle"],
             "action": "Liveness RESTARTS a hung process; readiness REMOVES it from "
                       "the load balancer. Do not confuse the two.",
             "predict": "what a failing readiness probe does."},
        11: {"tags": ["rollout"],
             "action": "Canary: compare canary against control on the same traffic, "
                       "with enough samples to see the effect.",
             "predict": "whether 90 samples can detect a 2% regression."},
        12: {"tags": ["rollout"],
             "action": "Auto-rollback on burn-rate, not a single blip — a 30-second "
                       "spike must not page.",
             "predict": "whether a 30s spike trips a 1h-budget alarm."},
    },

    "compiler-and-vgpu": {
        1: {"tags": ["encoding"],
            "action": "Instruction encoding must round-trip: decode(encode(x)) == x "
                      "for every field width and opcode.",
            "predict": "the encoding of an R-type instruction."},
        2: {"tags": ["assembly", "symbol-resolution"],
            "action": "Two passes: pass 1 collects labels/addresses, pass 2 emits "
                      "with resolved operands and rejects bad registers or labels.",
            "predict": "why a forward jump needs two passes."},
        3: {"tags": ["execution"],
            "action": "CPU arithmetic, comparisons and loads/stores over a register "
                      "file plus byte-addressed memory.",
            "predict": "the register after an arithmetic op."},
        4: {"tags": ["execution"],
            "action": "Branches update PC; report runtime faults (div by zero, "
                      "out-of-range address, non-terminating loop).",
            "predict": "which fault an infinite loop reports."},
        5: {"tags": ["parsing"],
            "action": "Lexer: keywords, identifiers, operators, with positions, and "
                      "reject unknown characters.",
            "predict": "the token stream for 'x = 1;'."},
        6: {"tags": ["parsing"],
            "action": "Recursive-descent parser: precedence climbing for expressions, "
                      "brace blocks for statements.",
            "predict": "the parse of 1 + 2 * 3."},
        7: {"tags": ["codegen"],
            "action": "v1-v2: lower trees to instructions with labels for control "
                      "flow; keep each node's value in a register.",
            "predict": "the instruction count for a simple if."},
        8: {"tags": ["register-allocation"],
            "action": "v3: only 16 real registers force linear-scan allocation and "
                      "spilling to stack slots; mind live ranges across calls.",
            "predict": "when a value must be spilled."},
        9: {"tags": ["simt-divergence"],
            "action": "Uniform SIMT: all lanes execute in lockstep; TID is a GPU-only "
                      "instruction the scalar CPU rejects.",
            "predict": "what happens on a scalar CPU given TID."},
        10: {"tags": ["simt-divergence"],
             "action": "Divergence: a branch splits the warp; a mask stack re-converges "
                       "nested branches and ragged loops.",
             "predict": "which lanes are active after an if/else."},
        11: {"tags": ["synchronization"],
             "action": "Barrier deadlock: detect when lanes wait on a barrier the "
                       "active mask can never reach.",
             "predict": "whether a barrier inside a diverged branch can complete."},
        12: {"tags": ["plumbing"],
             "action": "Capstone: compile ONE program and run it on both the CPU and "
                       "the vGPU — the results must agree.",
             "predict": "whether CPU and GPU outputs match."},
    },
}


# Course-level metadata: what it is, roughly how long, and what it leads into.
# `order` gives the built-in recommended path; prereq tags drive review prompts.
COURSE_INFO = {
    "llm-from-scratch": {
        "title": "LLM From Scratch",
        "blurb": "The forward-pass mechanisms of a language model in plain Python "
                 "(BPE, attention, sampling, the KV cache, RoPE), the modern "
                 "architectures built on them (MoE, GQA, MLA, SSMs, diffusion, "
                 "TTT, Titans, MoD), and the distributed-training machinery "
                 "(tensor/ZeRO/pipeline/expert parallelism, mixed precision, "
                 "FlashAttention, checkpointing).",
        "level": "foundation",
        "order": 1,
    },
    "context-caching": {
        "title": "Context Caching From Scratch",
        "blurb": "Wire those mechanisms into a tiny transformer, then page, "
                 "prefix-share and evict KV cache without changing the output.",
        "level": "intermediate",
        "order": 2,
    },
    "contextcite": {
        "title": "ContextCite From Scratch",
        "blurb": "Replicate the NeurIPS 2024 paper: ablate sources, fit a LASSO "
                 "surrogate, and attribute which context caused an answer.",
        "level": "intermediate",
        "order": 3,
    },
    "dynamo-paper": {
        "title": "Dynamo From Scratch",
        "blurb": "Amazon's SOSP 2007 paper: consistent hashing, vector clocks, "
                 "N/R/W quorums, hinted handoff, Merkle anti-entropy, gossip.",
        "level": "intermediate",
        "order": 4,
    },
    "aws-from-scratch": {
        "title": "AWS From Scratch",
        "blurb": "Toy IAM, S3, SQS, DynamoDB, Lambda, SNS, KMS and VPC, plus a "
                 "capstone that wires them and breaks them on purpose.",
        "level": "intermediate",
        "order": 5,
    },
    "deploy-and-debug": {
        "title": "Deploy & Debug",
        "blurb": "Capacity math, percentiles, SLOs and error budgets, root-causing "
                 "injected faults from metrics, and safe rollout.",
        "level": "intermediate",
        "order": 6,
    },
    "compiler-and-vgpu": {
        "title": "Compiler + Virtual GPU",
        "blurb": "One ISA, two machines: two-pass assembler, recursive-descent "
                 "front end, register allocation with spilling, and SIMT divergence.",
        "level": "advanced",
        "order": 7,
    },
}


def builtin_projects():
    """Project directories the coach knows a built-in curriculum for."""
    return list(CURRICULUM)
