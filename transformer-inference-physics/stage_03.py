"""Transformer Inference Physics — stage 3: The bytes: the memory budget.

TODO: implement each function; the docstring is the contract.

A token's second budget is the bytes it must move: the weights read once
per step however many sequences share them, and the KV cache every
sequence reads entire at every step — the cache's own size is the
per-token read, which is the whole point of this stage. The one derived
number is arithmetic intensity, flops per kilobyte, and it is the
race's only score: under the ridge, the bytes win; over it, the flops.

DESIGN DECISION — the decode step's KV line carries the store too?
Because the step's attention kernel both reads the cache and writes the
new token's keys and values into it; a byte budget that pretends the
write is free undercounts the step by one token's slice. `bytes_decode`'
kv line is the read plus the store, and it is exactly what the stage 4
op table prices across the layer list — the check makes the two meet.

DESIGN DECISION — intensity over zero bytes refused?
Because "flops per zero bytes" is not zero, it is undefined, and a model
that answers zero for it will answer zero everywhere the race is
decided. The refusal names the number; the caller supplies a real op.

DESIGN DECISION — flops per kilobyte, not per byte?
Because the numbers stay in the thousands where they are readable and
the comparisons stay exact: intensity and ridge are the same unit, and
both are integers. A per-byte ratio would live below 1 for every decode
op in the course and hide the crossover it exists to expose."""


import stage_01 as s1

BYTES_KEYS = ("weights", "kv", "total")

def kv_bytes_per_token(config):
    """K and V for one token, fp16, the whole stack: a token's cache rent."""
    raise NotImplementedError("stage 3: implement kv_bytes_per_token()")

def kv_total(config, ctx):
    """The cache's own size at a context length — and a decode step's
    whole read."""
    raise NotImplementedError("stage 3: implement kv_total()")

def bytes_decode(config, ctx, batch, dtype):
    """One decode step's byte budget: weights once, caches per sequence."""
    raise NotImplementedError("stage 3: implement bytes_decode()")

def bytes_prefill(config, prompt_len, batch, dtype):
    """A prefill's byte budget: weights once, the K and V stores."""
    raise NotImplementedError("stage 3: implement bytes_prefill()")

def arithmetic_intensity(flops, bytes):
    """Flops per kilobyte — `flops * 1000 // bytes`, the race's score."""
    raise NotImplementedError("stage 3: implement arithmetic_intensity()")
