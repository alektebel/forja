"""
Progress checker for the LLM-from-scratch templates.

    python3 check.py           # run every check, stop at the first unimplemented step
    python3 check.py 4         # run only step 4
    python3 check.py 4 6       # run steps 4 through 6
    python3 check.py --all     # run everything, do not stop at the first gap

Nothing here imports solutions/. It tests YOUR code.
"""

import math
import pathlib
import shutil
import sys
import traceback
from typing import Callable, List, Tuple

sys.dont_write_bytecode = True
shutil.rmtree(pathlib.Path(__file__).parent / "__pycache__", ignore_errors=True)

PASS, FAIL, TODO, ERROR = "PASS", "FAIL", "TODO", "ERROR"
GREEN, RED, YELLOW, GREY, BOLD, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[1m", "\033[0m")


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def check_bpe_pairs() -> None:
    from tokenizer import get_pair_counts, merge_pair

    counts = get_pair_counts([1, 1, 1, 2])
    assert counts[(1, 1)] == 2, f"expected two adjacent (1,1) pairs, got {counts}"
    assert counts[(1, 2)] == 1

    merged = merge_pair([1, 1, 1, 2], (1, 1), 9)
    assert merged == [9, 1, 2], (
        "'aaa' must merge to (new, a), not to two overlapping merges. Scan with an "
        f"index and skip past a merge; got {merged}")


def check_bpe_training() -> None:
    from tokenizer import encode, train_bpe

    corpus = b"abababab" * 4
    first = train_bpe(corpus, 8)
    second = train_bpe(corpus, 8)
    assert first == second, (
        "training must be deterministic. Ties in pair frequency need an explicit "
        "rule (highest count, then smallest pair) or the same corpus makes a "
        "different tokenizer every run.")
    assert first.get((97, 98)) == 256, (
        "the most frequent pair is 'ab' (97, 98), so it must become merge id 256 "
        f"(the first new id). Got {first.get((97, 98))!r}")
    ids = encode(corpus.decode(), first)
    assert len(ids) < len(corpus), \
        f"merges must compress the corpus: {len(ids)} tokens for {len(corpus)} bytes"


def check_bpe_encode_order() -> None:
    from tokenizer import decode, encode, train_bpe

    # A hand-built table where a left-to-right sweep gives a different answer.
    merges = {(98, 97): 256, (97, 98): 257}
    ids = encode("aba", merges)
    assert ids == [97, 256], (
        "encode must apply the LOWEST-rank merge first, anywhere in the sequence. "
        "Here (98,97) is rank 256 and (97,98) is rank 257, so 'aba' -> a then "
        "merge 'ba' -> [97, 256]. A left-to-right sweep would merge (97,98) first "
        f"and return [257, 97]. Got {ids}")
    assert decode(ids, merges) == b"aba"

    corpus = b"the cat sat on the mat. the cat ate the rat. " * 10
    table = train_bpe(corpus, 32)
    assert decode(encode(corpus.decode(), table), table) == corpus, (
        "decode(encode(text)) must reproduce the original bytes exactly. If it "
        "does not, an id is being expanded into the wrong children.")


# ---------------------------------------------------------------------------
# Attention
# ---------------------------------------------------------------------------

def check_attention_softmax() -> None:
    from attention import softmax

    p = softmax([1000.0, 1001.0])
    assert all(math.isfinite(x) for x in p), (
        "softmax([1000, 1001]) must stay finite. exp(1000) is larger than a float "
        "can hold, so you must subtract the max first: exp(x - max). The result is "
        "mathematically identical and the overflow disappears.")
    assert abs(sum(p) - 1.0) < 1e-12, f"softmax must sum to 1, got {sum(p)}"
    assert p[1] > p[0], "the larger logit must get the larger probability"
    one = softmax([5.0])
    assert abs(one[0] - 1.0) < 1e-12, "a single score must become probability 1"


def check_attention_causal() -> None:
    from attention import scaled_dot_product_attention

    Q = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    K = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
    V = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]   # every value row sums to 1

    full = scaled_dot_product_attention(Q, K, V)
    for i, row in enumerate(full):
        assert abs(sum(row) - 1.0) < 1e-9, (
            f"row {i} of attention must be a convex combination of the value rows, "
            f"so it sums to 1; got {sum(row)}. Are the weights actually normalised?")

    causal = scaled_dot_product_attention(Q, K, V, causal=True)
    for i, row in enumerate(causal):
        assert abs(sum(row) - 1.0) < 1e-9, (
            f"causal row {i} must still sum to 1. If you zero the future AFTER "
            "the softmax the mass no longer adds up; mask to -inf BEFORE it.")
    assert causal[1] != full[1], (
        "causal row 1 must differ from the full-attention row 1 — position 1 is "
        "not allowed to see position 2, and if the outputs match the future leaked")
    assert causal[0] == V[0], (
        "position 0 may attend only to itself, so its output must equal V[0]=[1,0]. "
        f"Got {causal[0]} — if it sees position 1, the mask is missing or applied "
        "after the softmax.")


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def check_sampling_temperature() -> None:
    from random import Random

    from sampling import apply_temperature, sample, softmax

    logits = [2.0, 1.0, 0.0]
    greedy = apply_temperature(logits, 0.0)
    assert greedy[0] == 0.0 and greedy[1] == float("-inf") and greedy[2] == float("-inf"), (
        "temperature 0 means hard greedy: one-hot at the argmax, -inf elsewhere. "
        "'Very small temperature' still samples the tail occasionally.")
    assert sample(logits, Random(0), temperature=0.0) == 0

    scaled = apply_temperature(logits, 0.5)
    assert scaled == [4.0, 2.0, 0.0], f"temperature divides the logits, got {scaled}"

    hot = max(softmax(apply_temperature(logits, 1.0)))
    sharp = max(softmax(apply_temperature(logits, 0.5)))
    assert sharp > hot, "lower temperature must sharpen the distribution"


def check_sampling_top_k() -> None:
    from sampling import softmax, top_k_filter

    logits = [1.0, 3.0, 3.0, 2.0]
    masked = top_k_filter(logits, 2)
    assert masked[0] == float("-inf") and masked[3] == float("-inf"), \
        f"top-2 of {logits} must drop indices 0 and 3, got {masked}"
    assert masked[1] != float("-inf") and masked[2] != float("-inf"), (
        "the two 3.0 values tie — break ties by smallest index and keep BOTH")
    assert abs(sum(softmax(masked)) - 1.0) < 1e-12, \
        "the surviving mass must renormalise to 1"


def check_sampling_top_p() -> None:
    from sampling import top_p_filter

    probabilities = [0.5, 0.3, 0.15, 0.05]
    logits = [math.log(x) for x in probabilities]
    masked = top_p_filter(logits, 0.9)
    assert masked[2] != float("-inf"), (
        "top-p must keep the token that CROSSES the threshold. 0.5 + 0.3 + 0.15 = "
        "0.95 >= 0.9, so index 2 is inside the nucleus. Using `>` instead of `>=` "
        "drops it, which is the classic off-by-one-token bug.")
    assert masked[3] == float("-inf"), "0.05 is outside the 0.9 nucleus"
    assert masked[0] != float("-inf") and masked[1] != float("-inf")


def check_sampling_determinism() -> None:
    from random import Random

    from sampling import sample

    logits = [1.0, 1.0, 1.0, 1.0]
    first = Random(123)
    second = Random(123)
    a = [sample(logits, first, temperature=0.9, k=2, p=0.95) for _ in range(50)]
    b = [sample(logits, second, temperature=0.9, k=2, p=0.95) for _ in range(50)]
    assert a == b, (
        "a seeded RNG must reproduce the same sample sequence. If it does not, "
        "your evals are measuring noise.")


# ---------------------------------------------------------------------------
# KV cache
# ---------------------------------------------------------------------------

def check_kv_cache_object() -> None:
    from kv_cache import KVCache

    cache = KVCache()
    assert len(cache) == 0
    cache.append([1.0, 2.0], [3.0, 4.0])
    cache.append([5.0, 6.0], [7.0, 8.0])
    assert len(cache) == 2, f"two appends must give length 2, got {len(cache)}"
    assert cache.keys() == [[1.0, 2.0], [5.0, 6.0]], f"keys: {cache.keys()}"
    assert cache.values() == [[3.0, 4.0], [7.0, 8.0]], f"values: {cache.values()}"


def check_kv_cache_exactness() -> None:
    from kv_cache import KVCache, cached_step, recompute_step

    d = 8
    K = [[math.sin(i + j) for j in range(d)] for i in range(12)]
    V = [[math.cos(i * j + 1) for j in range(d)] for i in range(12)]
    q = [math.sin(3 + j) for j in range(d)]

    cache = KVCache()
    for key, value in zip(K, V):
        cache.append(key, value)

    got = cached_step(q, cache)
    want = recompute_step(q, K, V)
    diff = max(abs(a - b) for a, b in zip(got, want))
    assert diff < 1e-9, (
        f"the cached step must be EXACT, not approximate; max difference {diff:.2e}. "
        "A cache that changes the output gives you a model you cannot reproduce.")

    shorter = recompute_step(q, K[:-1], V[:-1])
    assert max(abs(a - b) for a, b in zip(got, shorter)) > 1e-6, (
        "the last key must change the output. If dropping it changes nothing, the "
        "cache is not actually being read.")


def check_kv_cache_cost() -> None:
    from kv_cache import cached_work, recompute_work

    recompute = recompute_work(64, 64, 8)
    cached = cached_work(64, 64, 8)
    assert cached < recompute / 10, (
        f"the cache must dominate for long generations: {cached:,} vs "
        f"{recompute:,} interactions. Recompute is quadratic in the prefix per step; "
        "the cache is linear.")
    assert recompute_work(128, 1, 8) > 3.5 * recompute_work(64, 1, 8), (
        "prefill is quadratic in prompt length, so doubling the prompt should "
        "nearly quadruple the work")


# ---------------------------------------------------------------------------
# RoPE
# ---------------------------------------------------------------------------

def check_rope_invariants() -> None:
    from rope import apply_rope, rope_freqs

    dim, seq = 8, 48
    freqs = rope_freqs(dim, seq)
    q = [math.sin(j + 1) for j in range(dim)]
    k = [math.cos(2 * j + 1) for j in range(dim)]

    def norm(v: List[float]) -> float:
        return math.sqrt(sum(x * x for x in v))

    assert max(abs(a - b) for a, b in zip(apply_rope(q, 0, freqs), q)) < 1e-12, \
        "position 0 must be the identity rotation"

    for pos in (0, 1, 7, 40):
        assert abs(norm(apply_rope(q, pos, freqs)) - norm(q)) < 1e-9, (
            f"rotation must preserve the norm; position {pos} changed it")

    distance = 7
    dots = [
        sum(a * b for a, b in zip(apply_rope(q, p, freqs),
                                  apply_rope(k, p + distance, freqs)))
        for p in range(seq - distance)
    ]
    spread = max(dots) - min(dots)
    assert spread < 1e-9, (
        f"dot(q@p, k@(p+{distance})) must depend only on the distance, not on p, "
        f"but it varied by {spread:.2e}. Your frequencies are wrong, and long-context "
        "behaviour will degrade in a way short tests never reveal.")


# ---------------------------------------------------------------------------
# Modern architectures
# ---------------------------------------------------------------------------

def check_moe_routing() -> None:
    from architectures import expert_loads, moe_forward, router_scores

    experts = [[1.0, 0.0], [0.0, 1.0], [0.9, 0.9]]
    token = [1.0, 0.2]
    scores = router_scores(token, experts)
    assert scores[0] == 1.0 and scores[1] == 0.2, f"router logits: {scores}"

    out = moe_forward(token, experts, top_k=1)
    assert out == experts[2], (
        f"top-1 MoE must return the argmax expert unchanged; got {out}")

    out2 = moe_forward(token, experts, top_k=2)
    assert abs(out2[0] - 0.9480010659844419) < 1e-9, (
        "top-2 must blend the two best experts (2 then 0), renormalised "
        f"over the chosen ones; got {out2}")

    loads = expert_loads([[1.0, 0.0], [0.0, 1.0]], experts, top_k=1)
    assert loads[0] == 1 and loads[1] == 1 and loads[2] == 0, (
        f"loads must count routing decisions per expert: {loads}")


def check_gqa() -> None:
    from architectures import gqa_reshape, gqa_kv_cache_ratio, gqa_shared_kv

    heads = [[1.0], [2.0], [3.0], [4.0]]
    groups = gqa_reshape(heads, 2)
    assert groups == [[[1.0], [2.0]], [[3.0], [4.0]]], (
        "groups must keep heads in order, contiguous")

    shared = gqa_shared_kv([[1.0], [2.0]], 4)
    assert shared == [[1.0], [2.0], [1.0], [2.0]], (
        "each query head must map to a KV head, cycling when q > kv")

    ratio = gqa_kv_cache_ratio(32, 8)
    assert abs(ratio - 0.25) < 1e-12, (
        f"8 KV heads for 32 query heads is a quarter of the cache: {ratio}")


def check_mla() -> None:
    from architectures import mla_cache_size, mla_roundtrip_error

    kv = [0.5 * ((i % 5) - 2) for i in range(16)]
    big = mla_roundtrip_error(kv, 16, 0)
    assert big < 1e-9, (
        f"a full-size latent must reconstruct exactly, got error {big:.2e}")

    small = mla_roundtrip_error(kv, 4, 0)
    assert small > 1e-3, (
        f"a 4-dim latent of 16 dims must lose information, got error {small:.2e}")

    assert mla_cache_size(32, 4, 100) == 400, (
        "MLA caches the latent per token, not the full KV")


def check_ssm() -> None:
    from architectures import ssm_forgets, ssm_scan, ssm_step

    state, y = ssm_step([0.0, 0.0], 1.0, [-1.0, -2.0], 1.0, 1.0, 1.0)
    assert abs(state[0] - 1.0) < 1e-12, (
        "h' = exp(delta*A)*h + delta*B*x; from rest, h' = delta*B*x = 1.0")
    assert abs(y - (state[0] + state[1])) < 1e-12, "output is C dot h'"

    ys = ssm_scan([1.0, 0.0, 0.0], [1.0, 1.0, 1.0], [-1.0])
    assert ys[0] > ys[1] > ys[2] > 0.0, (
        "an impulse must decay through the recurrence")

    factor = ssm_forgets([-1.0], 0.01, 100)
    assert abs(factor - math.exp(-1.0)) < 1e-9, (
        "exp(delta*A) compounds per step: the memory horizon is 1/(delta*|A|)")


def check_diffusion() -> None:
    from architectures import MASK_ID, denoise_step, diffusion_rounds, mask_tokens
    from random import Random

    ids = [1, 2, 3, 4, 5, 6, 7, 8]
    masked = mask_tokens(ids, 0.5, Random(0))
    assert all(t in ids or t == MASK_ID for t in masked), (
        "masking replaces ids with MASK_ID, nothing else")
    again = mask_tokens(ids, 0.5, Random(0))
    assert masked == again, "same seed must give the same mask"

    noisy = [MASK_ID, 3, MASK_ID, 5]
    out = denoise_step(noisy, [2, 0, 4, 0], [0.9, 0.0, 0.8, 0.0], 1)
    assert out == [2, 3, MASK_ID, 5], (
        "only the most confident MASKED position unmasks this step")

    assert diffusion_rounds(10, 4) == 3, "round up: 4 + 4 + 2"


def check_ttt() -> None:
    from architectures import ttt_forgets_context, ttt_predict, ttt_train, ttt_update

    w = ttt_update([0.0], [1.0], 1.0, 0.1)
    assert abs(w[0] - 0.2) < 1e-12, "one gradient step: w + 2*lr*(target - w.x)*x"

    trained = ttt_train([0.0, 0.0], [[1.0, 0.0], [0.0, 1.0]], [1.0, 2.0], 0.5)
    assert trained[0] > 0.0 and trained[1] > 0.0, (
        "training must move weights toward the targets")

    err = ttt_forgets_context([0.0, 0.0],
                              [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 1.0]],
                              [1.0, 2.0, 4.0, 6.0], 0.5)
    assert err > 1e-6, (
        "TTT overwrites: after later tokens, the first token's fit degrades — "
        f"error {err:.4f} should be substantial")

    _ = ttt_predict([1.0, 2.0], [0.5, 0.5])


def check_titans() -> None:
    from architectures import (titans_admits_past_window, titans_persistent_vs_episodic,
                               titans_update)

    m0 = [0.0]
    m1 = titans_update(m0, [1.0], 1.0, 0.1, 0.0, [0.0])
    assert abs(m1[0] - 0.1 * 1.0 * 0.9) < 1e-12, (
        "memory += lr*surprise*x, then 10% weight decay")

    m2 = titans_update(m0, [1.0], 1.0, 0.1, 0.9, [0.5])
    assert m2[0] > m1[0], "momentum carries the previous update forward"

    persistent, episodic = titans_persistent_vs_episodic([1.0], [1.0], [0.0])
    assert persistent > episodic, (
        "the frozen persistent memory and the updatable episodic one score separately")

    assert titans_admits_past_window([0.0] * 10, 4) == 4, (
        "momentum keeps the last `window` tokens alive in the memory")


def check_mod() -> None:
    from architectures import mod_flops_saved, mod_layer, router_topk

    rows = [[3.0, 3.0], [0.0, 0.0], [1.0, 1.0]]
    chosen = router_topk(rows, 2)
    assert chosen == [True, False, True], (
        f"top-2 by score, ties by lower index: {chosen}")

    ident = [[1.0, 0.0], [0.0, 1.0]]
    out = mod_layer(rows, 2, ident)
    assert out[1] == [0.0, 0.0], (
        "unrouted positions pass through UNCHANGED — that is the whole trick")
    assert out[0] == [3.0, 3.0], "routed positions go through the layer"

    assert mod_flops_saved(8, 4, 2) == 24, (
        "skipped positions never pay: (rows - capacity) * d")


# ---------------------------------------------------------------------------
# Distributed training
# ---------------------------------------------------------------------------

def check_tp() -> None:
    from parallelism import (all_reduce, column_parallel_matmul, column_shard,
                             row_parallel_matmul, row_shard)

    w = [[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]
    x = [1.0, -1.0]

    shards = column_shard(w, 2)
    assert len(shards) == 2 and len(shards[0][0]) == 2, (
        "column shards keep all rows, half the columns each")

    partials = [column_parallel_matmul(x, s) for s in shards]
    expected = [sum(x[r] * w[r][c] for r in range(len(x))) for c in range(len(w[0]))]
    assert partials[0] + partials[1] == expected, (
        "column-parallel outputs CONCATENATE — no all-reduce on this path")

    rshards = row_shard(w, 2)
    assert len(rshards[0]) == 1, "row shards split the rows"
    x_shards = [x[0:1], x[1:2]]
    rpartials = [row_parallel_matmul(x_shards[s], rshards[s]) for s in range(2)]
    row_result = all_reduce(rpartials)
    assert row_result == expected, (
        f"row-parallel partials must sum to the same result: {row_result}")


def check_zero() -> None:
    from parallelism import all_gather_shards, param_footprint, zero_partition_footprint

    assert param_footprint(1_000_000) == 4_000_000, (
        "Adam holds weights + grads + two moments")
    assert param_footprint(1_000_000, "sgd") == 2_000_000, (
        "SGD holds weights + grads only")

    full = param_footprint(1_000_000)
    s1 = zero_partition_footprint(1_000_000, 4, 1)
    s3 = zero_partition_footprint(1_000_000, 4, 3)
    assert full > s1 > s3 > 0, (
        f"each stage must shard more state: {full} > {s1} > {s3}")
    assert s3 == full // 4, "ZeRO-3 partitions everything: exactly a quarter"

    gathered = all_gather_shards([[1.0], [2.0], [3.0], [4.0]])
    assert gathered == [1.0, 2.0, 3.0, 4.0], "all-gather reassembles in worker order"


def check_pipeline() -> None:
    from parallelism import bubble_fraction, microbatch_timeline, pipeline_stages

    stages = pipeline_stages(5, 2)
    assert stages == [[0, 1, 2], [3, 4]], (
        "stages take consecutive layers, the remainder spread from the front")

    timeline = microbatch_timeline(1, 2, 3)
    first = timeline[0][0]
    assert first == 0, "step 0: only stage 0 has work"
    assert timeline[1] == [1, 0], (
        f"the staircase: stage 1 runs microbatch 0 one step later: {timeline[1]}")

    frac = bubble_fraction(4, 8)
    assert abs(frac - 3 / 11) < 1e-12, (
        "bubble = (stages - 1) / (stages - 1 + microbatches); more microbatches shrink it")


def check_amp() -> None:
    from parallelism import fp16_overflows_sum, fp32_master_step, loss_scale_step, to_fp16

    assert to_fp16(1.0) == 1.0, "exactly representable values round-trip"
    assert to_fp16(1.0 + 2 ** -11) == 1.0, (
        "half precision has 10 mantissa bits; halfway ties round to even (1.0)")
    assert to_fp16(1.0 + 2 ** -10 + 2 ** -11) > 1.0, (
        "just past halfway must step up to the next mantissa value")

    assert fp16_overflows_sum([60000.0, 60000.0]), "120000 exceeds 65504"
    assert not fp16_overflows_sum([100.0, 100.0])

    w = fp32_master_step([1.0], [0.25], 0.1)
    assert abs(w[0] - (1.0 - 0.025)) < 1e-12, (
        "grads are fp16-rounded, the update lands on fp32 master weights")

    descaled = loss_scale_step([16000.0], 1000.0)
    assert abs(descaled[0] - 16.0) < 1e-12, (
        "scaled grads are divided back down before the optimizer applies them")


def check_flash() -> None:
    from parallelism import flash_memory, flash_tiled_attention, naive_attention

    q = [[1.0, 0.0], [0.5, 0.5], [0.1, 0.2], [-0.3, 0.7]]
    k = [[1.0, 0.0], [0.0, 1.0], [0.3, 0.3], [0.9, -0.2]]
    v = [[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, 8.0]]

    got = flash_tiled_attention(q, k, v)
    want = naive_attention(q, k, v)
    err = max(abs(p - r) for ra, rb in zip(got, want) for p, r in zip(ra, rb))
    assert err < 1e-9, (
        f"tiled attention with a running max must equal the naive path: err {err:.2e}")

    assert flash_memory(512, 64) == 512 * 512, (
        "the naive path materialises t*t scores; the tiled path never does")


def check_checkpointing() -> None:
    from parallelism import (forward_block, forward_checkpoint, forward_eager,
                             peak_activation_memory)

    blocks = [[[1.0, 0.5], [0.0, 1.0]], [[0.5, 0.5], [1.0, 0.0]],
              [[1.0, 1.0], [0.5, 0.5]], [[0.0, 1.0], [1.0, 0.5]]]
    xs = [[0.3, -0.2], [0.9, 0.1]]

    final, acts = forward_checkpoint(xs, blocks, 2)
    expected = forward_eager(xs, blocks)
    assert len(acts) == len(expected), (
        f"recomputation must produce every intermediate: {len(acts)} vs {len(expected)}")
    err = max(abs(p - r) for ra, rb in zip(acts, expected)
              for p, r in zip(ra, rb))
    assert err < 1e-12, f"checkpointed activations must match eager exactly: {err:.2e}"

    probe = [forward_block(row, blocks[0]) for row in xs]
    assert all(abs(p - q) < 1e-12 for a, b in zip(probe, expected[len(xs):len(xs) + 2])
               for p, q in zip(a, b)), "first block output is tanh(affine(x))"

    eager_mem = (len(xs) + len(blocks)) * len(xs) * len(xs[0])
    ckpt_mem = peak_activation_memory(len(xs), len(xs[0]), len(blocks), 2)
    assert ckpt_mem < eager_mem, (
        f"checkpointing must keep less than eager: {ckpt_mem} vs {eager_mem}")


def check_sp() -> None:
    from parallelism import layernorm_local, layernorm_sequence_parallel, scatter_sequence

    xs = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0], [-1.0, 0.0, 1.0]]
    shards = scatter_sequence(xs, 2)
    assert len(shards) == 2 and len(shards[0]) + len(shards[1]) == len(xs), (
        "sequence shards partition the rows")

    sp = layernorm_sequence_parallel(xs, 2)
    local = layernorm_local(xs)
    err = max(abs(p - r) for ra, rb in zip(sp, local) for p, r in zip(ra, rb))
    assert err < 1e-12, (
        f"sequence-parallel LayerNorm must match single-worker exactly: {err:.2e}")


def check_cp() -> None:
    from parallelism import (context_partition_kv, context_parallel_work,
                             ring_attention_step, ring_steps)

    assert ring_steps(4) == 4, "n-1 pushes plus the local pass"

    keys = [[float(i)] for i in range(8)]
    vals = [[float(i * 10)] for i in range(8)]
    k0, v0 = context_partition_kv(keys, vals, 0, 4)
    k3, v3 = context_partition_kv(keys, vals, 3, 4)
    assert k0[0] == [0.0] and k3[0] == [6.0], (
        "worker w holds its contiguous chunk of the sequence")
    assert len(k0) == 2 and len(k3) == 2

    q = [[1.0]]
    rmax = [-math.inf]
    rden = [0.0]
    rout = [[0.0]]
    rmax, rden, rout = ring_attention_step(q, 0, k0, v0, 0, rmax, rden, rout)
    rmax, rden, rout = ring_attention_step(q, 0, [[3.0]], [[30.0]], 4, rmax, rden, rout)
    assert abs(rden[0] - 1.0) < 1e-9, (
        "only key 0 is unmasked for query 0: the denominator is exactly its weight")
    assert abs(rout[0][0] - 0.0) < 1e-9, (
        "query 0 attends only to itself: output equals v[0] = 0.0")

    total = context_parallel_work(64, 4, 4)
    assert total == 4 * 16 * 64, "each worker scores its chunk against ALL keys"


def check_ep() -> None:
    from parallelism import combine_outputs, dispatch_tokens, ep_footprint, expert_worker

    assert expert_worker(5, 2) == 1, "expert e lives on worker e % workers"

    dispatch = dispatch_tokens([0, 1, 2, 0], 4, 2)
    assert dispatch == [[0, 2, 3], [1]], (
        f"tokens grouped by their expert's worker (e % 2), indices ascending: {dispatch}")

    out = combine_outputs([10.0, 20.0], [0, 3], 4)
    assert out == [10.0, 0.0, 0.0, 20.0], (
        "the all-to-all return trip scatters results back to token order")

    assert ep_footprint(64, 1000, 8) == 8000, (
        "experts partitioned across workers: n_experts / n_workers each")


CHECKS: List[Tuple[str, str, Callable[[], None]]] = [
    ("tokenizer.py", "pair counts and non-overlapping merges", check_bpe_pairs),
    ("tokenizer.py", "deterministic training and compression", check_bpe_training),
    ("tokenizer.py", "rank-ordered encode and round-trip", check_bpe_encode_order),
    ("attention.py", "stable softmax", check_attention_softmax),
    ("attention.py", "attention weights and the causal mask", check_attention_causal),
    ("sampling.py", "temperature and hard greedy", check_sampling_temperature),
    ("sampling.py", "top-k", check_sampling_top_k),
    ("sampling.py", "top-p keeps the crossing token", check_sampling_top_p),
    ("sampling.py", "seeded sampling is reproducible", check_sampling_determinism),
    ("kv_cache.py", "cache append and shape", check_kv_cache_object),
    ("kv_cache.py", "cached output is bit-exact", check_kv_cache_exactness),
    ("kv_cache.py", "the cost model: linear vs quadratic", check_kv_cache_cost),
    ("rope.py", "norm and relative-position invariants", check_rope_invariants),
    ("architectures.py", "MoE: routing and expert loads", check_moe_routing),
    ("architectures.py", "GQA: shared KV heads", check_gqa),
    ("architectures.py", "MLA: latent compression", check_mla),
    ("architectures.py", "SSM: selective recurrence", check_ssm),
    ("architectures.py", "diffusion: mask and denoise", check_diffusion),
    ("architectures.py", "TTT: inner-loop learning", check_ttt),
    ("architectures.py", "Titans: neural memory", check_titans),
    ("architectures.py", "MoD: routed capacity", check_mod),
    ("parallelism.py", "tensor parallelism", check_tp),
    ("parallelism.py", "ZeRO model-state sharding", check_zero),
    ("parallelism.py", "GPipe microbatching", check_pipeline),
    ("parallelism.py", "mixed precision", check_amp),
    ("parallelism.py", "FlashAttention tiling", check_flash),
    ("parallelism.py", "activation checkpointing", check_checkpointing),
    ("parallelism.py", "sequence parallelism", check_sp),
    ("parallelism.py", "context parallelism", check_cp),
    ("parallelism.py", "expert parallelism", check_ep),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_one(check: Callable[[], None]) -> Tuple[str, str]:
    try:
        check()
        return PASS, ""
    except NotImplementedError as exc:
        where = ""
        for frame in reversed(traceback.extract_tb(sys.exc_info()[2])):
            if frame.filename.endswith(".py") and "check.py" not in frame.filename:
                where = f"{frame.filename.split('/')[-1]}:{frame.lineno} in {frame.name}()"
                break
        return TODO, (str(exc) or where)
    except AssertionError as exc:
        return FAIL, str(exc) or "assertion failed"
    except Exception as exc:                       # noqa: BLE001
        where = ""
        for frame in reversed(traceback.extract_tb(sys.exc_info()[2])):
            if "check.py" not in frame.filename:
                where = (f"\n      at {frame.filename.split('/')[-1]}:"
                         f"{frame.lineno} in {frame.name}()")
                break
        return ERROR, f"{type(exc).__name__}: {exc}{where}"


def main(argv: List[str]) -> int:
    keep_going = "--all" in argv
    wanted = [int(a) for a in argv if a.isdigit()]
    if len(wanted) > 1:
        wanted = list(range(min(wanted), max(wanted) + 1))

    print(f"\n{BOLD}LLM From Scratch — progress check{RESET}")
    print(f"{GREY}implement the templates, re-run this after each step{RESET}\n")

    passed = failed = todo = 0
    first_gap = None

    for index, (filename, title, check) in enumerate(CHECKS, start=1):
        if wanted and index not in wanted:
            continue

        status, detail = run_one(check)
        if status == PASS:
            passed += 1
            print(f"  {GREEN}✓{RESET} {index:>2}. {filename:<15} {title}")
        elif status == TODO:
            todo += 1
            first_gap = first_gap or index
            print(f"  {GREY}·{RESET} {index:>2}. {filename:<15} {title}")
            print(f"      {GREY}not implemented yet"
                  f"{(' — ' + detail) if detail else ''}{RESET}")
            if not keep_going and not wanted:
                remaining = len(CHECKS) - index
                if remaining:
                    print(f"\n  {GREY}({remaining} later checks not run; "
                          f"use --all to run them anyway){RESET}")
                break
        else:
            failed += 1
            first_gap = first_gap or index
            colour = RED if status == FAIL else YELLOW
            print(f"  {colour}✗{RESET} {index:>2}. {filename:<15} {title}")
            for line in detail.splitlines():
                print(f"      {colour}{line}{RESET}")

    total = len(wanted) if wanted else len(CHECKS)
    print(f"\n  {passed}/{total} passing", end="")
    if failed:
        print(f", {RED}{failed} failing{RESET}", end="")
    if todo:
        print(f", {GREY}{todo} to write{RESET}", end="")
    print()

    if passed == len(CHECKS):
        print(f"\n  {GREEN}{BOLD}All checks pass — you built the core of an LLM.{RESET}")
        print(f"  {GREY}Run each solution's demo to see the measurements, then{RESET}")
        print(f"  {GREY}move on to context-caching/ to wire them into a model.{RESET}\n")
    elif first_gap:
        filename, title, _ = CHECKS[first_gap - 1]
        print(f"\n  {BOLD}Next:{RESET} step {first_gap} — {title} ({filename})")
        print(f"  {GREY}The docstrings walk through it. Stuck? solutions/{filename}{RESET}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
