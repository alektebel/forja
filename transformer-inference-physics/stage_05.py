"""Transformer Inference Physics — stage 5: Prefill: TTFT's model.

TODO: implement each function; the docstring is the contract.

A prefill runs every prompt token through the stack at once: the weight
matmuls get `prompt * batch` tokens of fuel, attention is quadratic in
the prompt, and the head runs once per sequence. The phase is
compute-bound by construction at real sizes — that is the stage's whole
verdict, and the sum of ops into nanoseconds is what the profiler's TTFT
disagrees with by exactly one probe tax later on.

DESIGN DECISION — the head runs once per sequence, on the last tokens?
Because a prefill is a prompt, not a generation: the logits that matter
are the ones continued from, one vector per sequence, and a head matmul
over all prompt tokens would multiply the course's most boring matmul by
the one length it does not run over. The decode step's head is the same
`2 * V * d` per sequence, so both phases share one line and one number.

DESIGN DECISION — the total here carries no probe tax?
Because the model's honest claim is its arithmetic alone; the profiler
pays its own sync to look, and `PROBE_NS` belongs to the trace that
measures, not the physics that predicts. Stage 10's `predict` adds the
tax where the model meets the measurement — one place owns it, and this
stage stays a pure cost model.

DESIGN DECISION — prefill refuses a batch of zero?
Because serving zero sequences is not a fast prefill, it is no prefill;
a zero that flowed through the arithmetic would return 0 ns for a
request that does not exist and pass every downstream bar on the way.
The refusal names what a prefill minimally is."""


import stage_01 as s1

import stage_04 as s4

PREFILL_KEYS = ("compute_ns", "memory_ns", "launch_ns", "total", "bound")

def prefill(config, device, dtype, prompt_len, batch):
    """The prefill phase: every op of the stack over the whole prompt,
    both branch sums, the launch bill, one wall total and one verdict."""
    raise NotImplementedError("stage 5: implement prefill()")
