"""Transformer Inference Physics — stage 1: The parameters: what a config is.

TODO: implement each function; the docstring is the contract.

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
dtype and the table's own rows; the fix is the caller's."""


import configs

class PhysError(ValueError):
    """A caller's mistake, named rather than guessed around."""

PARAM_KEYS = ("attention", "mlp", "embedding", "total")

def validate(config):
    """Refuse a config that cannot be a transformer: the query heads must
    tile the residual stream exactly and the KV heads must divide them."""
    raise NotImplementedError("stage 1: implement validate()")

def count_params(config):
    """The model's four parameter counts: attention, mlp, embedding, total."""
    raise NotImplementedError("stage 1: implement count_params()")

def weight_bytes(config, dtype):
    """The model's weights in bytes at a dtype: fp16/fp8/int8 scale the
    total; int4 packs matrix by matrix."""
    raise NotImplementedError("stage 1: implement weight_bytes()")
