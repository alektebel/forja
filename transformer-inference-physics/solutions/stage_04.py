"""Transformer Inference Physics — stage 4: The roofline: the race's rules.

Every op is two budgets at once — the flops its kernel must compute and
the bytes its weights and cache must move — and its wall time is the
slower of the two plus the launch. Dual-issue halves nothing: the boxes
that overlap compute and memory are this course's fiction, and the
crossing point of the two graphs, the ridge, is the score at which the
race changes hands. This stage prices ops one by one and sums them into
phases; stages 5 and 6 are just phases with names.

DESIGN DECISION — one floor chain, pinned by the literal?
Because an integer cost model rounded twice is a plausibility machine:
`(flops * 1000000) // (peak * mult * eff_c)` floors once, in the place
the contract names, and everywhere in the course — stage, world, check —
the same literal appears. Refactoring it into an "equivalent" form
changes which way it leans at odd sizes, and the audit would not see it
coming. The formulas are contract, not style.

DESIGN DECISION — a tie is memory-bound?
Because the bytes are read into SRAM regardless of whether the arithmetic
keeps up with them: equality means the memory branch has not lost. A
model that awards ties to compute flips the crossover's edge case upside
down, and the mutation battery plants exactly that.

DESIGN DECISION — the launch is paid per op, not per phase?
Because a kernel is launched per op: four per layer, one for the head —
the stack's launch bill is `launch_ns * (4 * n_layers + 1)`, and at
toys-on-desktop sizes it is a visible fraction of a step. A phase that
launches once is a phase the trace would never measure.
"""

import configs
import devices
import stage_01 as s1

LAYER_OPS = ("qkv", "attn", "o", "mlp")
FINAL_OP = "head"
PHASE_KEYS = ("compute_ns", "memory_ns", "launch_ns", "total")


def matrix_bytes(params, dtype):
    """One matrix's weights in bytes at a dtype; int4 packs it alone."""
    if params < 0:
        raise s1.PhysError(
            "params=%d: a negative matrix is not a matrix" % (params,))
    if dtype == "int4":
        return (params + 1) // 2
    if dtype not in configs.DTYPE_BYTES:
        raise s1.PhysError(
            "dtype %r: not one of %r — the weights' dtype table holds "
            "fp16, fp8 and int8, and int4 lives in its packing rule"
            % (dtype, tuple(configs.DTYPE_BYTES)))
    return configs.DTYPE_BYTES[dtype] * params


def _device(device):
    """The device row, or a refusal naming the rows that exist."""
    name = getattr(device, "name", None)
    if name not in devices.DEVICES:
        raise s1.PhysError(
            "device %r: not one of %r — the world's accelerators are its "
            "rows alone" % (name, devices.DEVICE_NAMES))
    return devices.DEVICES[name]


def _t_compute(flops, device, dtype):
    """The compute branch, ns — the contract's literal formula."""
    if dtype not in devices.FLOP_MULT:
        raise s1.PhysError(
            "dtype %r: not one of %r — the peak's dtype rows"
            % (dtype, tuple(devices.FLOP_MULT)))
    peak = device.peak_flop_fp16 * devices.FLOP_MULT[dtype]
    return (flops * 1000000) // (peak * device.eff_compute)


def _t_memory(byt, device):
    """The memory branch, ns — the contract's literal formula."""
    return (byt * 1000) // (device.bw_bytes_per_ns * device.eff_bandwidth)


def _guard(flops, byt):
    """No op works a negative number of flops over negative bytes."""
    if flops < 0 or byt < 0:
        raise s1.PhysError(
            "flops=%d bytes=%d: negative work is refused" % (flops, byt))


def op_time(flops, bytes, device, dtype):
    """One op's wall time: max(t_compute, t_memory) + the launch."""
    _device(device)
    _guard(flops, bytes)
    return max(_t_compute(flops, device, dtype),
               _t_memory(bytes, device)) + device.launch_ns


def classify(flops, bytes, device, dtype):
    """Which branch an op serves: compute over the ridge, memory under."""
    _device(device)
    _guard(flops, bytes)
    if _t_compute(flops, device, dtype) > _t_memory(bytes, device):
        return "compute"
    return "memory"


def ridge(device, dtype):
    """The crossover intensity in flops per kilobyte: where the race
    changes hands."""
    _device(device)
    if dtype not in devices.FLOP_MULT:
        raise s1.PhysError(
            "dtype %r: not one of %r" % (dtype, tuple(devices.FLOP_MULT)))
    return (device.peak_flop_fp16 * devices.FLOP_MULT[dtype]
            * device.eff_compute) // (device.bw_bytes_per_ns
                                      * device.eff_bandwidth)


def ops_decode(config, batch, ctx, dtype):
    """The decode op table: qkv, attn, o, mlp per layer, then head. Each
    op is a (name, flops, bytes) triple; the bytes are that layer's own
    slice of the weights, plus the cache it reads and the token it adds."""
    s1.validate(config)
    if batch < 1 or ctx < 1:
        raise s1.PhysError(
            "batch=%d ctx=%d: a decode step serves at least one sequence "
            "over at least one cached token" % (batch, ctx))
    d = config.d_model
    kv_d = config.n_kv_heads * config.head_dim
    qkv_p = d * (d + 2 * kv_d)
    ops = []
    for _ in range(config.n_layers):
        ops.append(("qkv", 2 * qkv_p * batch, matrix_bytes(qkv_p, dtype)))
        ops.append(("attn",
                    4 * ctx * config.n_heads * config.head_dim * batch,
                    (ctx + 1) * 4 * config.n_kv_heads * config.head_dim
                    * batch))
        ops.append(("o", 2 * d * d * batch, matrix_bytes(d * d, dtype)))
        ops.append(("mlp", 6 * d * config.d_ff * batch,
                    matrix_bytes(3 * d * config.d_ff, dtype)))
    ops.append(("head", 2 * config.vocab * d * batch,
                matrix_bytes(config.vocab * d, dtype)))
    return tuple(ops)


def ops_prefill(config, prompt_len, batch, dtype):
    """The prefill op table: the weight matmuls over every prompt token,
    attention quadratic in the prompt, and the K and V stores."""
    s1.validate(config)
    if prompt_len < 1 or batch < 1:
        raise s1.PhysError(
            "prompt_len=%d batch=%d: a prefill runs at least one token "
            "for at least one sequence" % (prompt_len, batch))
    d = config.d_model
    kv_d = config.n_kv_heads * config.head_dim
    qkv_p = d * (d + 2 * kv_d)
    fuel = prompt_len * batch
    ops = []
    for _ in range(config.n_layers):
        ops.append(("qkv", 2 * qkv_p * fuel, matrix_bytes(qkv_p, dtype)))
        ops.append(("attn",
                    4 * prompt_len * prompt_len * config.n_heads
                    * config.head_dim * batch,
                    prompt_len * 4 * config.n_kv_heads * config.head_dim
                    * batch))
        ops.append(("o", 2 * d * d * fuel, matrix_bytes(d * d, dtype)))
        ops.append(("mlp", 6 * d * config.d_ff * fuel,
                    matrix_bytes(3 * d * config.d_ff, dtype)))
    ops.append(("head", 2 * config.vocab * d * batch,
                matrix_bytes(config.vocab * d, dtype)))
    return tuple(ops)


def phase_time(ops, device, dtype):
    """A phase's four sums: each branch per op, the launches, and the
    every-op-max total the wall clock actually pays."""
    _device(device)
    compute_ns = 0
    memory_ns = 0
    total = 0
    for _, flops, byt in ops:
        _guard(flops, byt)
        t_c = _t_compute(flops, device, dtype)
        t_m = _t_memory(byt, device)
        compute_ns += t_c
        memory_ns += t_m
        total += max(t_c, t_m) + device.launch_ns
    return {"compute_ns": compute_ns, "memory_ns": memory_ns,
            "launch_ns": device.launch_ns * len(ops), "total": total}


def phase_bound(compute_ns, memory_ns):
    """A phase's verdict, the tie law included: equality serves memory."""
    if compute_ns > memory_ns:
        return "compute"
    return "memory"
