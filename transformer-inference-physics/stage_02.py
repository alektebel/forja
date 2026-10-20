"""Transformer Inference Physics — stage 2: The flops: the compute budget.

TODO: implement each function; the docstring is the contract.

Only matmuls are flops: the softmax, the layernorm and every elementwise
op are free in this world's accounting, because the course's argument is
about engine throughput, and engines are priced in matmuls. Per token the
budget has three lines — the weights a token's forward pass runs through,
the attention score/QK^T-and-PV pair over the context, and the lm head —
and prefill is the same three lines with the prompt tokens as fuel and
attention's quadratic term switched on.

DESIGN DECISION — why is a multiply-add two flops?
Because the convention the roofline's peak is rated in is fused
multiply-adds: one multiply and one add move through the pipe together,
and a hardware peak of 989 TFLOP/s is two 989 teraflops of primitive
ops. Counting one per matmul contribution would halve every compute
branch in the course against a denominator priced the other way, and
the ridge — the ratio the race is decided by — would drift by a factor
the trace would eventually catch.

DESIGN DECISION — no causal halving, ever?
Because the world's kernel is the full kernel: a context of `ctx` keys is
read by every query, and the masked half of a causal attention matrix
never shows up in these numbers. Pinning the full kernel is what makes
prefill and decode one arithmetic — `ctx` in a formula is the KV length
the query actually reads, no more.

DESIGN DECISION — why is GQA invisible in the flops?
Because grouped-query attention narrows the KV storage, not the query
heads: every query head still scores its own row against the context and
multiplies its own context by its own value projection. The flops carry
`n_heads`; the KV bytes — stage 3's lesson — carry `n_kv_heads`. The
difference between the two is GQA, and it is a memory win only."""


import stage_01 as s1

FLOP_KEYS = ("weights", "attention", "head", "total")

def flops_token(config, ctx):
    """One generated token's forward pass: weights, attention over
    `ctx` cached keys, the head."""
    raise NotImplementedError("stage 2: implement flops_token()")

def flops_prefill(config, prompt_len, batch):
    """A prefill's forward pass: the weight matmuls scale with every
    prompt token batched at once, attention is quadratic in the prompt,
    and the head runs once per sequence, on the last tokens."""
    raise NotImplementedError("stage 2: implement flops_prefill()")
