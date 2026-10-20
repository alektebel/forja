"""LLM Security From Scratch — stage 12 solution: detection, incident response, and governance

Reference implementation. Compare against stage_12.py.
"""

import re
from enum import Enum


class Severity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentPhase(Enum):
    PREPARATION = "preparation"
    IDENTIFICATION = "identification"
    CONTAINMENT = "containment"
    ERADICATION = "eradication"
    RECOVERY = "recovery"
    POST_INCIDENT = "post_incident"


def audit_log_analyzer(
    log_entries: list[dict],
    baseline_profile: dict | None = None,
) -> list[dict]:
    """Analyze audit logs for security-relevant events."""
    if not log_entries:
        return []

    # Build baseline from the data if no profile provided
    if baseline_profile is None:
        avg_tokens_in = sum(e.get("tokens_in", 0) for e in log_entries) / max(len(log_entries), 1)
        avg_tokens_out = sum(e.get("tokens_out", 0) for e in log_entries) / max(len(log_entries), 1)
        avg_duration = sum(e.get("duration_ms", 0) for e in log_entries) / max(len(log_entries), 1)
        baseline_profile = {
            "avg_tokens_in": avg_tokens_in,
            "avg_tokens_out": avg_tokens_out,
            "avg_duration": avg_duration,
        }

    events = []
    event_id_counter = 0

    for entry in log_entries:
        tokens_in = entry.get("tokens_in", 0)
        tokens_out = entry.get("tokens_out", 0)
        duration_ms = entry.get("duration_ms", 0)

        # Unusual token count (long queries or excessive output)
        if tokens_in > baseline_profile.get("avg_tokens_in", 100) * 5:
            event_id_counter += 1
            events.append({
                "event_id": f"EVT-{event_id_counter:04d}",
                "timestamp": entry.get("timestamp", ""),
                "severity": "medium",
                "event_type": "long_query",
                "description": f"Unusually long query ({tokens_in} tokens, ~{baseline_profile.get('avg_tokens_in', 100)} avg)",
                "suggested_action": "Review query for prompt injection patterns",
            })

        if tokens_out > baseline_profile.get("avg_tokens_out", 500) * 3:
            event_id_counter += 1
            events.append({
                "event_id": f"EVT-{event_id_counter:04d}",
                "timestamp": entry.get("timestamp", ""),
                "severity": "high",
                "event_type": "high_tokens_out",
                "description": f"Excessive output ({tokens_out} tokens, ~{baseline_profile.get('avg_tokens_out', 500)} avg)",
                "suggested_action": "Check for data leakage or information extraction",
            })

        # Unusual latency (could indicate complex attack processing)
        if duration_ms > baseline_profile.get("avg_duration", 1000) * 5:
            event_id_counter += 1
            events.append({
                "event_id": f"EVT-{event_id_counter:04d}",
                "timestamp": entry.get("timestamp", ""),
                "severity": "low",
                "event_type": "off_hours",
                "description": f"Unusual latency ({duration_ms}ms, ~{baseline_profile.get('avg_duration', 1000)}ms avg)",
                "suggested_action": "Monitor for ongoing attack processing",
            })

    return events


def anomaly_detector(
    metrics: list[dict],
    window: int = 100,
    sensitivity: str = "medium",
) -> dict:
    """Detect anomalies in model usage metrics."""
    if len(metrics) < 2:
        return {"anomalies": [], "baseline_stats": {}, "anomaly_score": 0, "trend": "stable"}

    # Use last `window` points as baseline
    recent = metrics[-window:]
    baseline_queries = [m.get("queries", 0) for m in recent]
    baseline_tokens = [m.get("tokens", 0) for m in recent]
    baseline_errors = [m.get("errors", 0) for m in recent]
    baseline_latency = [m.get("latency_ms", 0) for m in recent]

    def avg(values):
        return sum(values) / max(len(values), 1)

    def std(values):
        mean = avg(values)
        variance = sum((x - mean) ** 2 for x in values) / max(len(values), 1)
        return variance ** 0.5

    baseline_stats = {
        "avg_queries": round(avg(baseline_queries), 2),
        "avg_tokens": round(avg(baseline_tokens), 2),
        "avg_errors": round(avg(baseline_errors), 2),
        "avg_latency": round(avg(baseline_latency), 2),
    }

    sensitivity_factor = {"low": 3.0, "medium": 2.0, "high": 1.5}.get(sensitivity, 2.0)

    anomalies = []
    overall_score = 0

    for m in metrics[-10:]:  # Check last 10 points
        queries = m.get("queries", 0)
        errors = m.get("errors", 0)
        latency = m.get("latency_ms", 0)
        rejections = m.get("rejections", 0)

        # Sudden spike in queries
        if queries > baseline_stats["avg_queries"] * sensitivity_factor:
            anomalies.append({
                "timestamp": m.get("timestamp", ""),
                "type": "query_spike",
                "value": queries,
                "baseline": baseline_stats["avg_queries"],
                "severity": "medium",
            })
            overall_score += 20

        # Error rate increase
        if errors > baseline_stats["avg_errors"] * 2:
            anomalies.append({
                "timestamp": m.get("timestamp", ""),
                "type": "error_spike",
                "value": errors,
                "baseline": baseline_stats["avg_errors"],
                "severity": "high",
            })
            overall_score += 30

        # Latency spike
        if latency > baseline_stats["avg_latency"] * 3:
            anomalies.append({
                "timestamp": m.get("timestamp", ""),
                "type": "latency_spike",
                "value": latency,
                "baseline": baseline_stats["avg_latency"],
                "severity": "medium",
            })
            overall_score += 15

        # Sudden drop in rejections (guardrail bypass!)
        if rejections < baseline_stats["avg_queries"] * 0.1:
            anomalies.append({
                "timestamp": m.get("timestamp", ""),
                "type": "rejection_drop",
                "value": rejections,
                "baseline": baseline_stats["avg_queries"] * 0.3,
                "severity": "critical",
            })
            overall_score += 40

    # Determine trend
    first_half = metrics[:len(metrics)//2]
    second_half = metrics[len(metrics)//2:]
    avg_first = avg([m.get("queries", 0) for m in first_half])
    avg_second = avg([m.get("queries", 0) for m in second_half])

    if avg_second > avg_first * 1.5:
        trend = "increasing"
    elif avg_second < avg_first * 0.5:
        trend = "decreasing"
    else:
        trend = "stable"

    return {
        "anomalies": anomalies,
        "baseline_stats": baseline_stats,
        "anomaly_score": min(overall_score, 100),
        "trend": trend,
    }


def incident_response_plan(
    incident_type: str,
    severity: str,
    affected_systems: list[str],
    logs: list[dict] | None = None,
) -> dict:
    """Generate an incident response plan for a compromised system."""

    response_steps = {
        "identification": [
            {"phase": "identification", "action": "Confirm the incident through audit logs and user reports", "priority": "P0", "responsible": "Security team"},
            {"phase": "identification", "action": "Scope the affected models, systems, and data", "priority": "P0", "responsible": "Security team"},
            {"phase": "identification", "action": "Document initial findings with timestamps", "priority": "P0", "responsible": "Security team"},
        ],
        "containment": [
            {"phase": "containment", "action": "Disable affected API endpoints or model access", "priority": "P0", "responsible": "Engineering"},
            {"phase": "containment", "action": "Rotate credentials and API keys for affected systems", "priority": "P0", "responsible": "Engineering"},
            {"phase": "containment", "action": "Implement rate limiting on affected endpoints", "priority": "P1", "responsible": "Engineering"},
        ],
        "eradication": [
            {"phase": "eradication", "action": "Remove the attack vector (patch prompt injection vulnerability)", "priority": "P0", "responsible": "Engineering"},
            {"phase": "eradication", "action": "Update guardrails and security rules", "priority": "P0", "responsible": "Security team"},
            {"phase": "eradication", "action": "Review and update access controls", "priority": "P1", "responsible": "Security team"},
        ],
        "recovery": [
            {"phase": "recovery", "action": "Restore affected systems from clean backups", "priority": "P1", "responsible": "Engineering"},
            {"phase": "recovery", "action": "Verify model integrity with security tests", "priority": "P1", "responsible": "Security team"},
            {"phase": "recovery", "action": "Gradually restore service with enhanced monitoring", "priority": "P1", "responsible": "Engineering"},
        ],
        "post_incident": [
            {"phase": "post_incident", "action": "Conduct post-incident review", "priority": "P2", "responsible": "Security team"},
            {"phase": "post_incident", "action": "Update incident response playbook", "priority": "P2", "responsible": "Security team"},
            {"phase": "post_incident", "action": "Implement preventive measures from lessons learned", "priority": "P2", "responsible": "Engineering"},
        ],
    }

    nist_alignment = [
        "NIST AI RMF: Govern - Maintain awareness of the incident's impact",
        "NIST AI RMF: Map - Understand the context of the incident",
        "NIST AI RMF: Measure - Detect and monitor for the incident",
        "NIST AI RMF: Manage - Prioritize actions based on impact",
    ]

    eu_ai_act_alignment = [
        "EU AI Act: Report significant incident to authorities within 24 hours",
        "EU AI Act: Document incident in transparency log",
        "EU AI Act: Review risk management framework",
    ]

    notification_required = severity in ("high", "critical")
    regulatory_timeline = "24 hours" if notification_required else "72 hours"

    return {
        "incident": {
            "type": incident_type,
            "severity": severity,
            "affected_systems": affected_systems,
            "estimated_impact": _estimate_impact(incident_type, severity),
        },
        "response_steps": [step for phase_steps in response_steps.values() for step in phase_steps],
        "containment": response_steps.get("containment", []),
        "investigation": response_steps.get("identification", []),
        "recovery": response_steps.get("recovery", []),
        "post_incident": response_steps.get("post_incident", []),
        "nist_alignment": nist_alignment,
        "eu_ai_act_alignment": eu_ai_act_alignment,
        "notification_required": notification_required,
        "regulatory_timeline": regulatory_timeline,
    }


def _estimate_impact(incident_type: str, severity: str) -> str:
    impacts = {
        "prompt_injection": "User input compromised model behavior",
        "data_leak": "Private data may have been exposed",
        "jailbreak": "Model guardrails bypassed, unrestricted behavior",
        "model_manipulation": "Model weights or behavior altered",
        "supply_chain": "Compromised component in model supply chain",
        "agent_compromise": "Agent's capabilities exceeded authorized scope",
        "red_team_breach": "Security testing revealed critical vulnerabilities",
    }
    return impacts.get(incident_type, "Security incident of unknown impact")