"""The world's third data module: the measured trace.

This module is the course's judge, and its only import is the other two
world modules. It carries the reference implementation of every event the
course predicts — prefill and decode, over the world's own op table — so
that a stage's numbers can be graded by equality against a measurement
the stage did not itself produce.

The physics is the contract's (§2), written here once, in the world's own
hand: two competing budgets per op, the flops a kernel must drink and the
bytes it must move, `t = max(t_compute, t_memory) + launch`, a phase the
sum of its ops, TTFT the prefill phase, ITL the generation's mean decode
step on the context schedule `prompt + i` for `i` in `0..gen - 1`.

The one thing on top of the arithmetic is `PROBE_NS`: the profiler's own
sync tax, pinned at 1500 ns per event. A model that reproduces the
arithmetic exactly and forgets the probe disagrees with the trace by
exactly 1500 ns — one nanosecond is one wrong formula, and the probe tax
is a formula the course learns to pay.

`arithmetic_intensity`'s unit and every bounded sum here is integers the
whole way; this module never imports `math`, and neither should anything
that wants to agree with it.
"""

from collections import namedtuple

import configs
import devices

Workload = namedtuple("Workload", ("name", "prompt", "gen", "batch"))

# (name, prompt tokens, generated tokens, concurrent sequences)
_WORKLOAD_ROWS = (
    ("W_A", 1024, 256, 1),
    ("W_B", 4096, 256, 1),
    ("W_C", 8192, 128, 1),
    ("W_D", 1024, 256, 8),
    ("W_E", 1024, 256, 32),
    ("W_F", 131072, 64, 1),
)

WORKLOADS = dict((r[0], Workload(*r)) for r in _WORKLOAD_ROWS)

WORKLOAD_NAMES = tuple(r[0] for r in _WORKLOAD_ROWS)

# the profiler's own cost of looking at an event, in ns: a measurement
# in this world is the model's arithmetic plus one of these, and the gap
# is the honest distance between a cost model and a profile
PROBE_NS = 1500

# the batches the crossover stage sweeps
BATCHES = (1, 2, 4, 8, 16, 32, 64, 128, 256, 512)

# the servable grid the audit walks: (config, device, workload, dtype).
# Every row fits its device with room to spare; the rows that do not fit
# are the walls, and refusing them is a stage's job, not a TRACKS row's
TRACKS = (
    ("TINY_MHA", "D_CLASS", "W_A", "fp16"),
    ("TINY_MHA", "H_CLASS", "W_A", "fp16"),
    ("TINY_MHA", "H_CLASS", "W_F", "fp16"),
    ("SEVEN_MHA", "H_CLASS", "W_A", "fp16"),
    ("SEVEN_MHA", "H_CLASS", "W_B", "fp16"),
    ("SEVEN_GQA", "A_CLASS", "W_A", "fp16"),
    ("SEVEN_GQA", "H_CLASS", "W_A", "fp16"),
    ("SEVEN_GQA", "H_CLASS", "W_B", "fp16"),
    ("SEVEN_GQA", "H_CLASS", "W_B", "int8"),
    ("SEVEN_GQA", "H_CLASS", "W_C", "fp16"),
    ("SEVEN_GQA", "H_CLASS", "W_D", "fp16"),
    ("SEVEN_GQA", "H_CLASS", "W_E", "fp16"),
    ("SEVEN_MQA", "H_CLASS", "W_B", "fp16"),
    ("SEVEN_MQA", "H_CLASS", "W_D", "int8"),
    ("BIG_GQA", "H_CLASS", "W_A", "int8"),
    ("BIG_GQA", "H_CLASS", "W_B", "int8"),
)

_WEIGHT_BYTES = {"fp16": 2, "fp8": 1, "int8": 1}


def _validate(config_name, device_name, workload_name, dtype):
    if config_name not in configs.CONFIGS:
        raise ValueError("unknown config name: %r" % (config_name,))
    if device_name not in devices.DEVICES:
        raise ValueError("unknown device name: %r" % (device_name,))
    if workload_name not in WORKLOADS:
        raise ValueError("unknown workload name: %r" % (workload_name,))
    if dtype not in ("fp16", "fp8", "int8", "int4"):
        raise ValueError("unknown dtype: %r" % (dtype,))


def _params(config):
    """(attention, mlp, embedding) parameter counts, the contract's §2."""
    attn = (config.d_model * (config.d_model + 2 * config.n_kv_heads * config.head_dim)
            + config.d_model * config.d_model)
    mlp = 3 * config.d_model * config.d_ff
    embedding = config.vocab * config.d_model
    return attn, mlp, embedding


def _weight_bytes(params, dtype):
    """Bytes per weight table, plus int4's packing rule."""
    if dtype == "int4":
        return (params + 1) // 2
    return params * _WEIGHT_BYTES[dtype]


def _t_compute(flops, device, dtype):
    """(flops * 1000000) // (peak_fp16 * mult * eff_c) — the compute
    branch, ns; the contract's literal denominator, floored once."""
    peak = device.peak_flop_fp16 * devices.FLOP_MULT[dtype]
    return (flops * 1000000) // (peak * device.eff_compute)


def _t_memory(byt, device):
    """(bytes * 1000) // (bw * eff_m) — the memory branch, ns."""
    return (byt * 1000) // (device.bw_bytes_per_ns * device.eff_bandwidth)


def _cache_per_token(config):
    """KV bytes the whole stack's cache carries for one token, fp16."""
    return 4 * config.n_kv_heads * config.head_dim * config.n_layers


def _op(name, flops, byt):
    return (name, flops, byt)


def _weight_bytes_attn_o_mlp(config, dtype):
    """(qkv, o, mlp) weight bytes for the config, at the weight dtype."""
    qkv = config.d_model * (config.d_model + 2 * config.n_kv_heads * config.head_dim)
    return (_weight_bytes(qkv, dtype),
            _weight_bytes(config.d_model * config.d_model, dtype),
            _weight_bytes(3 * config.d_model * config.d_ff, dtype))


def _decode_ops(config, batch, ctx, dtype):
    """The world's decode op table: four kernels per layer, then head."""
    qkv_wb, o_wb, mlp_wb = _weight_bytes_attn_o_mlp(config, dtype)
    # the KV cache is fp16 under every weight dtype
    ops = []
    for _ in range(config.n_layers):
        ops.append(_op(
            "qkv",
            2 * config.d_model * (config.d_model + 2 * config.n_kv_heads * config.head_dim) * batch,
            qkv_wb))
        ops.append(_op(
            "attn",
            4 * ctx * config.n_heads * config.head_dim * batch,
            (ctx + 1) * 4 * config.n_kv_heads * config.head_dim * batch))
        ops.append(_op(
            "o",
            2 * config.d_model * config.d_model * batch,
            o_wb))
        ops.append(_op(
            "mlp",
            6 * config.d_model * config.d_ff * batch,
            mlp_wb))
    ops.append(_op("head", 2 * config.vocab * config.d_model * batch,
                   _weight_bytes(config.vocab * config.d_model, dtype)))
    return tuple(ops)


def _prefill_ops(config, prompt, batch, dtype):
    """The world's prefill op table: the same four kernels, the quadratic
    attention, and the batch of prompt tokens as the compute's fuel."""
    qkv_wb, o_wb, mlp_wb = _weight_bytes_attn_o_mlp(config, dtype)
    ops = []
    fuel = prompt * batch
    for _ in range(config.n_layers):
        ops.append(_op(
            "qkv",
            2 * config.d_model * (config.d_model + 2 * config.n_kv_heads * config.head_dim) * fuel,
            qkv_wb))
        ops.append(_op(
            "attn",
            4 * prompt * prompt * config.n_heads * config.head_dim * batch,
            prompt * 4 * config.n_kv_heads * config.head_dim * batch))
        ops.append(_op(
            "o",
            2 * config.d_model * config.d_model * fuel,
            o_wb))
        ops.append(_op(
            "mlp",
            6 * config.d_model * config.d_ff * fuel,
            mlp_wb))
    ops.append(_op("head", 2 * config.vocab * config.d_model * batch,
                   _weight_bytes(config.vocab * config.d_model, dtype)))
    return tuple(ops)


def _phase(ops, device_name, dtype):
    """(compute_ns, memory_ns, launch_ns, total) over one op table."""
    device = devices.DEVICES[device_name]
    compute_ns = sum(_t_compute(flops, device, dtype) for _, flops, _ in ops)
    memory_ns = sum(_t_memory(byt, device) for _, _, byt in ops)
    launch_ns = device.launch_ns * len(ops)
    total = sum(max(_t_compute(flops, device, dtype), _t_memory(byt, device))
                + device.launch_ns for _, flops, byt in ops)
    return compute_ns, memory_ns, launch_ns, total


def measure(kind, config_name, device_name, workload_name, dtype):
    """The profiler's own number for one event, in ns.

    "ttft" is the prefill phase plus the probe tax; "itl" is the
    generation's mean decode step — the sum over the context schedule
    `prompt + i` for `i` in `0..gen - 1`, floored by `gen` — plus one
    probe tax (the profiler samples the mean once, like it samples
    everything about the run once).
    """
    _validate(config_name, device_name, workload_name, dtype)
    config = configs.CONFIGS[config_name]
    workload = WORKLOADS[workload_name]
    if kind == "ttft":
        ops = _prefill_ops(config, workload.prompt,
                           workload.batch, dtype)
        _, _, _, total = _phase(ops, device_name, dtype)
        return total + PROBE_NS
    if kind == "itl":
        steps_total = 0
        for i in range(workload.gen):
            ops = _decode_ops(config, workload.batch,
                              workload.prompt + i, dtype)
            _, _, _, total = _phase(ops, device_name, dtype)
            steps_total += total
        return steps_total // workload.gen + PROBE_NS
    raise ValueError("unknown event kind: %r" % (kind,))


def bound(kind, config_name, device_name, workload_name, dtype):
    """The world's own bound verdict for one event: "compute" or
    "memory" — the phase's two branch sums compared, a tie reading
    "memory" (the bytes are read into SRAM regardless)."""
    _validate(config_name, device_name, workload_name, dtype)
    config = configs.CONFIGS[config_name]
    workload = WORKLOADS[workload_name]
    if kind == "ttft":
        ops = _prefill_ops(config, workload.prompt,
                           workload.batch, dtype)
    elif kind == "itl":
        ops = _decode_ops(config, workload.batch,
                          workload.prompt + workload.gen - 1, dtype)
    else:
        raise ValueError("unknown event kind: %r" % (kind,))
    compute_ns, memory_ns, _, _ = _phase(ops, device_name, dtype)
    return "compute" if compute_ns > memory_ns else "memory"
