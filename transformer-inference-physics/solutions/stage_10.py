"""Transformer Inference Physics — stage 10: The audit: the model meets
the measurement.

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
loudly where it cannot be trusted and silently nowhere else.
"""

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
    if config_name not in configs.CONFIGS:
        raise s1.PhysError(
            "config %r: not one of %r" % (config_name, configs.CONFIG_NAMES))
    if device_name not in devices.DEVICES:
        raise s1.PhysError(
            "device %r: not one of %r" % (device_name, devices.DEVICE_NAMES))
    if workload_name not in trace.WORKLOADS:
        raise s1.PhysError(
            "workload %r: not one of %r" % (workload_name,
                                            trace.WORKLOAD_NAMES))
    config = configs.CONFIGS[config_name]
    device = devices.DEVICES[device_name]
    workload = trace.WORKLOADS[workload_name]
    s1.validate(config)
    weights = s1.weight_bytes(config, dtype)
    kv_end = s3.kv_total(config, workload.prompt + workload.gen)
    if weights + kv_end * workload.batch > device.vram_bytes:
        raise s1.PhysError(
            "config %s on device %s: workload %s needs %d bytes (%d "
            "weights + %d cache x %d sequences) and the device holds %d — "
            "this row is a wall, not a track"
            % (config_name, device_name, workload_name,
               weights + kv_end * workload.batch, weights, kv_end,
               workload.batch, device.vram_bytes))
    pf = s5.prefill(config, device, dtype, workload.prompt, workload.batch)
    steps = 0
    for i in range(workload.gen):
        steps += s6.decode(config, device, dtype, workload.prompt + i,
                           workload.batch)["total"]
    itl_ns = steps // workload.gen + trace.PROBE_NS
    last = s6.decode(config, device, dtype,
                     workload.prompt + workload.gen - 1, workload.batch)
    return {"ttft_ns": pf["total"] + trace.PROBE_NS,
            "ttft_bound": pf["bound"],
            "itl_ns": itl_ns,
            "itl_bound": last["bound"],
            "tokens_per_second": workload.batch * 1000000000 // itl_ns,
            "kv_bytes": kv_end}


def audit(predictions=None):
    """The whole grid graded against the world's measurements: `pass`
    only when every row's values are exact, a reason naming every lie as
    `(row, key, expected, got)`."""
    if predictions is None:
        rows = [(row, predict(*row)) for row in trace.TRACKS]
    else:
        rows = [(tuple(row), dict(pred)) for row, pred in predictions]

    reasons = []
    for row, pred in rows:
        config_name, device_name, workload_name, dtype = row
        workload = trace.WORKLOADS[workload_name]
        config = configs.CONFIGS[config_name]
        expected = {
            "ttft_ns": trace.measure("ttft", config_name, device_name,
                                     workload_name, dtype),
            "ttft_bound": trace.bound("ttft", config_name, device_name,
                                      workload_name, dtype),
            "itl_ns": trace.measure("itl", config_name, device_name,
                                    workload_name, dtype),
            "itl_bound": trace.bound("itl", config_name, device_name,
                                     workload_name, dtype),
        }
        for key in ("ttft_ns", "itl_ns", "ttft_bound", "itl_bound"):
            if pred.get(key) != expected[key]:
                reasons.append((row, key, expected[key], pred.get(key)))
        want_tps = workload.batch * 1000000000 // pred["itl_ns"]
        if pred.get("tokens_per_second") != want_tps:
            reasons.append((row, "tokens_per_second", want_tps,
                            pred.get("tokens_per_second")))
        want_kv = s3.kv_total(config, workload.prompt + workload.gen)
        if pred.get("kv_bytes") != want_kv:
            reasons.append((row, "kv_bytes", want_kv, pred.get("kv_bytes")))

    return {"rows": tuple((row, dict(pred)) for row, pred in rows),
            "verdict": "pass" if not reasons else "fail",
            "reasons": tuple(reasons)}
