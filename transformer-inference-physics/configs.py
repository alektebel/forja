"""The world's first data module: transformer configs.

A config is seven integers: layers, width, query heads, KV heads, head
width, MLP width, vocabulary. Five named rows sit in `CONFIGS`, from a
6-layer 384-wide toy to an 80-layer 8192-wide frontier GQA stack. Every
row satisfies the two laws `stage_01.validate` enforces —
`n_heads * head_dim == d_model` and `n_heads % n_kv_heads == 0` — because
a query head names a slice of the residual stream, and a KV group divides
the query heads it serves.

The dtype table lives here too: `DTYPE_BYTES` maps the weight dtypes to
bytes per weight. `int4` is deliberately absent — it is a packing rule
(`(params + 1) // 2`), not a row — and the KV cache is not on the table
at all, because the KV cache is always fp16 no matter what the weights
carry. Both facts are the course's, and they are pinned in
`.i2-dev/CONTRACT.md` §2.
"""

from collections import namedtuple

Config = namedtuple(
    "Config",
    ("name", "n_layers", "d_model", "n_heads", "n_kv_heads",
     "head_dim", "d_ff", "vocab"))

# (name, n_layers, d_model, n_heads, n_kv_heads, head_dim, d_ff, vocab)
_ROWS = (
    ("TINY_MHA",   6,  384,  6,  6,  64,   1536,  4096),
    ("SEVEN_MHA",  32, 4096, 32, 32, 128,  11008, 32000),
    ("SEVEN_GQA",  32, 4096, 32, 8,  128,  11008, 32000),
    ("SEVEN_MQA",  32, 4096, 32, 1,  128,  11008, 32000),
    ("BIG_GQA",    80, 8192, 64, 8,  128,  28672, 128000),
)

CONFIGS = dict((r[0], Config(*r)) for r in _ROWS)

CONFIG_NAMES = tuple(r[0] for r in _ROWS)

# bytes per weight, by dtype. The KV cache is absent on purpose: it is
# fp16 under every weight dtype, and the packing rule for int4 lives in
# the contract, not in this table.
DTYPE_BYTES = {"fp16": 2, "fp8": 1, "int8": 1}

DTYPE_NAMES = ("fp16", "fp8", "int8", "int4")
