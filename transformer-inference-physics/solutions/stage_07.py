"""Transformer Inference Physics — stage 7: The KV cache: the third budget.

The cache is the one budget that grows with the conversation: a flat
rent per token per sequence — `4 * n_kv_heads * head_dim` bytes a
layer stacks — until it equals the weights, then it outlives them. This
stage tabulates the rent across the world's configs, solves the context
at which the cache catches the weights, and counts the batches a
device's VRAM holds at a context: the wall MHA hits four times sooner
than GQA, in the same integers everything else is priced in.

DESIGN DECISION — the KV cache is fp16 under every weight dtype?
Because the lesson of stage 9 only lands if the cache refuses to shrink:
quantize the weights and the tokens-per-second climbs, but the cache's
rent per token is untouched, and the context that OOMs you moves not a
byte. The formula takes no dtype on the KV side, and its reason wears
the stage 9 docstring.

DESIGN DECISION — a weights-too-big device answers batch edge 0?
Because 0 is the truth: no sequence fits. The alternative — a refusal —
would hide the fact at the one place the wall is the answer, and the
audit's refusal rows are about a workload that would not fit, not a
config that never does. A row that fits holds a batch of at most this
many; at zero it holds none.

DESIGN DECISION — why 4096 and 131072 as the table's contexts?
Because they are the course's wall and its world: four thousand is the
context everything still fits at, 131072 is the frontier length where
MHA dies on 80 GiB and the table must show it. Two rows, one small and
one fatal, and every config's rent in between.
"""

import configs
import devices
import stage_01 as s1
import stage_03 as s3

CACHE_KEYS = ("config", "kv_bytes_per_token", "kv_bytes_at_4096",
              "kv_bytes_at_131072")


def cache_table():
    """Every world config's cache rent, flat per token and at the
    course's two context lengths, fp16."""
    rows = []
    for name in configs.CONFIG_NAMES:
        config = configs.CONFIGS[name]
        rows.append((name,
                     s3.kv_bytes_per_token(config),
                     s3.kv_total(config, 4096),
                     s3.kv_total(config, 131072)))
    return tuple(rows)


def cache_life(config, dtype):
    """The context at which the cache's total equals the weights: after
    it, every added token's rent outlives the model."""
    s1.validate(config)
    return s1.weight_bytes(config, dtype) // s3.kv_bytes_per_token(config)


def vram_batch_edge(config, device, dtype, ctx):
    """The batch the VRAM holds at a context: weights plus caches, floored
    by the cache's whole-stack size — and 0 when the weights alone do not
    fit."""
    s1.validate(config)
    if getattr(device, "name", None) not in devices.DEVICES:
        raise s1.PhysError(
            "device %r: not one of %r — the world's accelerators are its "
            "rows alone" % (getattr(device, "name", device),
                            devices.DEVICE_NAMES))
    if ctx < 1:
        raise s1.PhysError(
            "ctx=%d is below 1: an edge at no tokens is not an edge"
            % (ctx,))
    free = device.vram_bytes - s1.weight_bytes(config, dtype)
    if free <= 0:
        return 0
    return free // s3.kv_total(config, ctx)
