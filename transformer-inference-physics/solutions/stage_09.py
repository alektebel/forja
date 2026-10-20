"""Transformer Inference Physics — stage 9: Quantization: the weights'
half of the trade.

Halve the weight bytes and the decode step's memory branch — the branch
that owns every real decode — shrinks with them, so the ITL gain in
per-mille is exact arithmetic the check can demand. What does not
shrink is the KV cache: fp16 under every weight dtype, immune to the
packing rule, and the reason a quantized model still pays the context's
rent at every step and still OOMs at exactly the context it used to.

DESIGN DECISION — fp8 and int8 give the same number?
Because this course's dtypes are named by the two facts that price a
step — bytes per weight and the tensor-core multiplier — and fp8 and
int8 share both rows: one byte, two-thousandths peak. Two names, one
number, and the check asserts it rather than treating it as a bug; a
model that differentiates them invented a difference the world does not
carry.

DESIGN DECISION — quant_step prices fp16 too, and its gain is 0 by
construction?
Because a trade needs a baseline measured the same way, and the cheapest
lie in this course is one that compares a quantized step against a hand-
copied fp16 number. Running the baseline through stage 6 inside the
same call keeps the gain an honest ratio — and for fp16 the honest
ratio is zero, which the check asserts as the baseline's own signature.

DESIGN DECISION — the KV line keeps the store?
Because the quantized step still writes the new token's keys and values,
fp16 just like before: the gain lives in the weights line and nowhere
else, and a `kv` number that shrank alongside would be the mutation the
battery plants as "quantizing the cache".
"""

import devices
import stage_01 as s1
import stage_03 as s3
import stage_06 as s6

QUANT_KEYS = ("weights", "kv", "total", "gain_per_mille")


def quant_weights(config, dtype):
    """The quantized stack's weight bytes — stage 1's dtype rules, the
    int4 packing included."""
    s1.validate(config)
    return s1.weight_bytes(config, dtype)


def quant_step(config, device, ctx, batch, dtype):
    """One decode step at a weight dtype, against the fp16 step on the
    same ctx, batch and device: both totals, the gain in per-mille."""
    s1.validate(config)
    if getattr(device, "name", None) not in devices.DEVICES:
        raise s1.PhysError(
            "device %r: not one of %r — the world's accelerators are its "
            "rows alone" % (getattr(device, "name", device),
                            devices.DEVICE_NAMES))
    if ctx < 1 or batch < 1:
        raise s1.PhysError(
            "ctx=%d batch=%d: a step serves at least one sequence over at "
            "least one cached token" % (ctx, batch))
    total = s6.decode(config, device, dtype, ctx, batch)["total"]
    fp16_total = s6.decode(config, device, "fp16", ctx, batch)["total"]
    gain = (fp16_total - total) * 1000 // fp16_total
    return {"weights": s1.weight_bytes(config, dtype),
            "kv": s3.kv_total(config, ctx) * batch
            + s3.kv_bytes_per_token(config) * batch,
            "total": total,
            "gain_per_mille": gain}
