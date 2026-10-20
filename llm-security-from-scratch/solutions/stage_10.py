"""LLM Security From Scratch — stage 10 solution: guardrails and runtime enforcement

Reference implementation. Compare against stage_10.py.
"""

from dataclasses import dataclass
from enum import Enum


class ActionLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    BLOCKED = "blocked"
    HUMAN_APPROVAL = "human_approval"


class RiskCategory(Enum):
    INJECTION = "injection"
    DATA_LEAK = "data_leak"
    EXCESSIVE_AGENCY = "excessive_agency"
    TOOLS_ACCESS = "tools_access"
    CONTENT = "content"


@dataclass
class GatewayDecision:
    decision: ActionLevel
    risk_category: RiskCategory | None
    reason: str
    requires_approval: bool = False


class PolicyGateway:
    """A policy gateway that intercepts actions before they execute."""

    def __init__(self, policies: list[dict]):
        self.policies = policies
        self.audit_log: list[dict] = []

    def evaluate(self, action: dict, context: dict) -> GatewayDecision:
        """Evaluate whether an action is allowed."""
        action_type = action.get("type", "")
        tool = action.get("tool", "")
        raw_input = action.get("raw_input", "")
        model_intent = action.get("model_intent", "")
        user = context.get("user", "")
        role = context.get("role", "")

        # Check policy rules
        for policy in self.policies:
            policy_type = policy.get("type", "")
            action_pattern = policy.get("action_pattern", "")

            if policy_type == "action_block" and action_type == action_pattern:
                return GatewayDecision(
                    decision=ActionLevel.BLOCKED,
                    risk_category=RiskCategory.EXCESSIVE_AGENCY,
                    reason=f"Action '{action_type}' is explicitly blocked by policy",
                )

            if policy_type == "role_restrict" and role == policy.get("role", ""):
                blocked_tools = policy.get("blocked_tools", [])
                if tool in blocked_tools:
                    return GatewayDecision(
                        decision=ActionLevel.BLOCKED,
                        risk_category=RiskCategory.TOOLS_ACCESS,
                        reason=f"Role '{role}' is not allowed to use tool '{tool}'",
                    )

            if policy_type == "tool_allow":
                allowed_tools = policy.get("allowed_tools", [])
                if tool and tool not in allowed_tools:
                    return GatewayDecision(
                        decision=ActionLevel.BLOCKED,
                        risk_category=RiskCategory.TOOLS_ACCESS,
                        reason=f"Tool '{tool}' not in allowed list",
                    )

            if policy_type == "injection_check":
                injection_patterns = policy.get("patterns", [])
                for pattern in injection_patterns:
                    if pattern in raw_input:
                        return GatewayDecision(
                            decision=ActionLevel.BLOCKED,
                            risk_category=RiskCategory.INJECTION,
                            reason="Potential injection detected",
                        )

            if policy_type == "human_approval":
                for req_type in policy.get("require_approval", []):
                    if action_type == req_type:
                        return GatewayDecision(
                            decision=ActionLevel.HUMAN_APPROVAL,
                            risk_category=RiskCategory.EXCESSIVE_AGENCY,
                            reason=f"Action '{action_type}' requires human approval",
                            requires_approval=True,
                        )

        return GatewayDecision(
            decision=ActionLevel.SAFE,
            risk_category=None,
            reason="Action passes all policy checks",
        )


class InputClassifier:
    """Classify input for risk categories before it reaches the model."""

    def __init__(self, rules: list[dict]):
        self.rules = rules

    def classify(self, text: str) -> dict:
        """Classify input text for security risk."""
        categories = []
        flags = []
        risk_level = "low"

        # Check for injection patterns
        injection_patterns = [
            r"(?i)ignore\s+(all|previous|the)\s+(instructions|rules|prompt)",
            r"(?i)system\s*:\s*(ok|yes|affirmative|understood)",
            r"(?i)disregard\s+(all|your|previous|the)",
        ]
        injection_found = False
        for pattern in injection_patterns:
            if self.rules and self.rules[0].get("check_injection", False):
                if __import__("re").search(pattern, text):
                    injection_found = True
                    break

        if injection_found:
            categories.append({"category": "injection", "confidence": 0.9})
            flags.append("Potential prompt injection detected")

        # Check for excessive agency
        agency_patterns = [
            r"(?i)^I\s+(will|must|can)\s+(create|delete|modify|change|enable|disable)",
            r"(?i)^(enable|disable|activate|deactivate|install|uninstall)\s+",
        ]
        agency_found = False
        for pattern in agency_patterns:
            if self.rules and self.rules[0].get("check_agency", False):
                if __import__("re").search(pattern, text):
                    agency_found = True
                    break

        if agency_found:
            categories.append({"category": "excessive_agency", "confidence": 0.75})
            flags.append("Model attempting to perform system actions")

        # Check for content violations
        content_patterns = [
            r"(?i)(harmful|illegal|malicious|exploit|attack|hack)",
        ]
        content_found = False
        for pattern in content_patterns:
            if self.rules and self.rules[0].get("check_content", False):
                if __import__("re").search(pattern, text):
                    content_found = True
                    break

        if content_found:
            categories.append({"category": "content_violation", "confidence": 0.6})
            flags.append("Potentially inappropriate content")

        # Check for data leakage signals
        if self.rules and self.rules[0].get("check_data_leak", False):
            if any(kw in text.lower() for kw in ["password", "secret", "api_key", "token", "ssn", "credit"]):
                categories.append({"category": "data_leakage", "confidence": 0.5})
                flags.append("Input contains potential sensitive data")

        # Determine risk level
        if any(c["confidence"] > 0.8 for c in categories):
            risk_level = "critical"
        elif any(c["confidence"] > 0.6 for c in categories):
            risk_level = "high"
        elif categories:
            risk_level = "medium"
        else:
            risk_level = "low"

        return {
            "is_safe": risk_level == "low",
            "risk_level": risk_level,
            "categories": categories,
            "flags": flags,
        }


def action_validator(
    proposed_action: dict,
    approved_actions: list[str],
    allowed_tools: list[str],
    human_approval_required_for: list[str],
) -> GatewayDecision:
    """Validate a proposed action against the approved action list."""
    action_type = proposed_action.get("type", "")
    tool = proposed_action.get("tool", "")

    if action_type not in approved_actions:
        return GatewayDecision(
            decision=ActionLevel.BLOCKED,
            risk_category=RiskCategory.EXCESSIVE_AGENCY,
            reason=f"Action type '{action_type}' not in approved list",
        )

    if tool and tool not in allowed_tools:
        return GatewayDecision(
            decision=ActionLevel.BLOCKED,
            risk_category=RiskCategory.TOOLS_ACCESS,
            reason=f"Tool '{tool}' not in allowed list",
        )

    if action_type in human_approval_required_for:
        return GatewayDecision(
            decision=ActionLevel.HUMAN_APPROVAL,
            risk_category=RiskCategory.EXCESSIVE_AGENCY,
            reason=f"Action '{action_type}' requires human approval",
            requires_approval=True,
        )

    return GatewayDecision(
        decision=ActionLevel.SAFE,
        risk_category=None,
        reason="Action is within approved scope",
    )