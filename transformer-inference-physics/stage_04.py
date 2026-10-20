"""Transformer Inference Physics — stage 4: The roofline: the race's rules.

TODO: implement each function; the docstring is the contract.

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
launches once is a phase the trace would never measure."""


import configs

import devices

import stage_01 as s1

LAYER_OPS = ("qkv", "attn", "o", "mlp")

FINAL_OP = "head"

PHASE_KEYS = ("compute_ns", "memory_ns", "launch_ns", "total")

def matrix_bytes(params, dtype):
    """One matrix's weights in bytes at a dtype; int4 packs it alone."""
    raise NotImplementedError("stage 4: implement matrix_bytes()")

def _device(device):
    """The device row, or a refusal naming the rows that exist."""
    raise NotImplementedError("stage 4: implement _device()")

def _t_compute(flops, device, dtype):
    """The compute branch, ns — the contract's literal formula."""
    raise NotImplementedError("stage 4: implement _t_compute()")

def _t_memory(byt, device):
    """The memory branch, ns — the contract's literal formula."""
    raise NotImplementedError("stage 4: implement _t_memory()")

def _guard(flops, byt):
    """No op works a negative number of flops over negative bytes."""
    raise NotImplementedError("stage 4: implement _guard()")

def op_time(flops, bytes, device, dtype):
    """One op's wall time: max(t_compute, t_memory) + the launch."""
    raise NotImplementedError("stage 4: implement op_time()")

def classify(flops, bytes, device, dtype):
    """Which branch an op serves: compute over the ridge, memory under."""
    raise NotImplementedError("stage 4: implement classify()")

def ridge(device, dtype):
    """The crossover intensity in flops per kilobyte: where the race
    changes hands."""
    raise NotImplementedError("stage 4: implement ridge()")

def ops_decode(config, batch, ctx, dtype):
    """The decode op table: qkv, attn, o, mlp per layer, then head. Each
    op is a (name, flops, bytes) triple; the bytes are that layer's own
    slice of the weights, plus the cache it reads and the token it adds."""
    raise NotImplementedError("stage 4: implement ops_decode()")

def ops_prefill(config, prompt_len, batch, dtype):
    """The prefill op table: the weight matmuls over every prompt token,
    attention quadratic in the prompt, and the K and V stores."""
    raise NotImplementedError("stage 4: implement ops_prefill()")

def phase_time(ops, device, dtype):
    """A phase's four sums: each branch per op, the launches, and the
    every-op-max total the wall clock actually pays."""
    raise NotImplementedError("stage 4: implement phase_time()")

def phase_bound(compute_ns, memory_ns):
    """A phase's verdict, the tie law included: equality serves memory."""
    raise NotImplementedError("stage 4: implement phase_bound()")
