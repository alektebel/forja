"""Transformer Inference Physics — stage 10: The audit: the model meets
the measurement.

TODO: implement each function; the docstring is the contract.

The whole course in one call: `predict` walks a TRACKS row from names to
nanoseconds — TTFT the prefill plus the profiler's own probe tax, ITL
the generation's mean decode step over the context schedule `prompt + i`
for `i` in `0..gen - 1` — and `audit` grades every row's six numbers
against the world's own measured answers, exactly. A prediction one
nanosecond off is one formula wrong, the audit names it as
`(row, key, expected, got)`, and the VRAM law refuses the workloads no
device can serve before the model ever gets to guess.

DESIGN DECISION — the audit re-measures through `trace`, not through the
stages it is auditing?
Because a stage grading its own homework along its own code path is the
one corruption a from-scratch course cannot tolerate: the world's
measurements are the independent implementation, written once by the
world and read here. Equality against the world is the whole standard.

DESIGN DECISION — the VRAM law runs before any arithmetic?
Because a prediction for a workload the device cannot serve is a
prediction about a run that never happens, plausible numbers and all.
The refusal names the config and the workload — the request and the box
— because that pair is the thing a serving plan gets wrong, and the
check's refusal rows make the audit's grid end where reality does.

DESIGN DECISION — a doctored row must fail by name?
Because the audit's property is not "says pass when everything matches"
but "says fail and names the liar when one value is wrong": one
nanosecond off in one key of one row is one reason, and the battery
doctors exactly that. An audit that cannot name its liar would fail
loudly where it cannot be trusted and silently nowhere else."""


import configs

import devices

import trace

import stage_01 as s1

import stage_03 as s3

import stage_05 as s5

import stage_06 as s6

PREDICT_KEYS = ("ttft_ns", "ttft_bound", "itl_ns", "itl_bound",
                "tokens_per_second", "kv_bytes")

PROOF_KEYS = ("rows", "verdict", "reasons")

def predict(config_name, device_name, workload_name, dtype):
    """One TRACKS row's six numbers, by names, paying the world's probe
    tax where the model meets the measurement."""
    raise NotImplementedError("stage 10: implement predict()")

def audit(predictions=None):
    """The whole grid graded against the world's measurements: `pass`
    only when every row's values are exact, a reason naming every lie as
    `(row, key, expected, got)`."""
    raise NotImplementedError("stage 10: implement audit()")
