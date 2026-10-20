"""Transformer Inference Physics — stage 1: The parameters: what a config is.

A config is seven integers, and everything this course predicts is those
seven integers multiplied, added and floored into nanoseconds. This stage
turns a config into the two budgets every later stage races: the
parameters a matmul must chew, and the bytes those parameters occupy.
Attention is the fused qkv (a token writes `d_model` queries plus
`2 * n_kv_heads * head_dim` keys and values) then the output projection;
mlp is gate, up and down; the embedding is counted once, because the lm
head is the same matrix coming back.

DESIGN DECISION — whole-model counts, the layer count folded in?
Because every later stage wants "the model" and not "one layer": a stage
that multiplies by `n_layers` per call multiplies it wrong once. Here the
four counts are the model's, and the op tables down in stage 4 carry
their own per-layer slices; the two meet again in a check that asserts
their sum is the whole. One place multiplies; that is this stage.

DESIGN DECISION — int4 packed per matrix, not once for the sky?
Because a real int4 tensor is packed one tensor at a time: a 4096x11008
weights matrix is stored as `(params + 1) // 2` bytes, and a stack of
them is the sum of the packs. Packing the whole model in one
`(params + 1) // 2` is a different number — off by the odd remnants of
every matrix — and this course is graded to the nanosecond, so the
packing rule is pinned at the granularity it is applied at.

DESIGN DECISION — why does a wrong dtype name raise instead of defaulting?
Because silently choosing fp16 for a datum the caller spelled wrong
produces a plausible number for the wrong reason. The refusal names the
dtype and the table's own rows; the fix is the caller's.
"""

import configs


class PhysError(ValueError):
    """A caller's mistake, named rather than guessed around."""


PARAM_KEYS = ("attention", "mlp", "embedding", "total")


def validate(config):
    """Refuse a config that cannot be a transformer: the query heads must
    tile the residual stream exactly and the KV heads must divide them."""
    fields = ("n_layers", "d_model", "n_heads", "n_kv_heads", "head_dim",
              "d_ff", "vocab")
    for name in fields:
        if getattr(config, name) < 1:
            raise PhysError(
                "config %r: %s=%d is below 1 — nothing to compute"
                % (config.name, name, getattr(config, name)))
    if config.n_heads * config.head_dim != config.d_model:
        raise PhysError(
            "config %r: %d query heads x %d dim = %d, not d_model=%d — the "
            "query heads must tile the residual stream exactly"
            % (config.name, config.n_heads, config.head_dim,
               config.n_heads * config.head_dim, config.d_model))
    if config.n_heads % config.n_kv_heads:
        raise PhysError(
            "config %r: %d query heads are not divided by %d KV heads — a "
            "KV group serves a whole share of the queries"
            % (config.name, config.n_heads, config.n_kv_heads))


def count_params(config):
    """The model's four parameter counts: attention, mlp, embedding, total."""
    validate(config)
    d = config.d_model
    qkv_p = d * (d + 2 * config.n_kv_heads * config.head_dim)
    attention = config.n_layers * (qkv_p + d * d)
    mlp = config.n_layers * (3 * d * config.d_ff)
    embedding = config.vocab * d
    total = attention + mlp + embedding
    return {"attention": attention, "mlp": mlp, "embedding": embedding,
            "total": total}


def weight_bytes(config, dtype):
    """The model's weights in bytes at a dtype: fp16/fp8/int8 scale the
    total; int4 packs matrix by matrix."""
    if dtype == "int4":
        validate(config)
        d = config.d_model
        qkv_p = d * (d + 2 * config.n_kv_heads * config.head_dim)
        o_p = d * d
        mlp_p = 3 * d * config.d_ff
        emb_p = config.vocab * d
        per_layer = ((qkv_p + 1) // 2 + (o_p + 1) // 2 + (mlp_p + 1) // 2)
        return config.n_layers * per_layer + (emb_p + 1) // 2
    if dtype not in configs.DTYPE_BYTES:
        raise PhysError("dtype %r: not one of %r — the table holds the "
                        "weights' dtypes and nothing else"
                        % (dtype, tuple(configs.DTYPE_BYTES)))
    return configs.DTYPE_BYTES[dtype] * count_params(config)["total"]
