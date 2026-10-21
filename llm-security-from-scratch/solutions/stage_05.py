"""LLM Security From Scratch — stage 5 solution: agent and tool security

Reference implementation. Compare against stage_05.py.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCapability:
    """What a tool does and what it requires."""
    name: str
    requires_capability: str  # e.g., "read:email", "write:filesystem", "exec:shell"
    dangerous: bool           # Can this tool cause irreversible harm?
    description: str


@dataclass
class PrincipalGrant:
    """What permissions a principal (user/agent) has been granted."""
    principal: str
    capabilities: list[str]   # e.g., ["read:email", "write:notes"]


@dataclass
class SandboxPolicy:
    """Environmental constraints on what can run."""
    allowed_capabilities: list[str]  # Subset of all capabilities that are allowed
    blocked_tools: list[str]         # Tools that are never allowed


def evaluate_tool_invocation(
    principal: str,
    tool_name: str,
    tool_capabilities: list[ToolCapability],
    grants: list[PrincipalGrant],
    policy: SandboxPolicy,
    invocation_args: dict,
) -> dict:
    """Check if a tool invocation is allowed by the capability intersection."""
    # Find the tool's required capability
    tool_cap = None
    for tc in tool_capabilities:
        if tc.name == tool_name:
            tool_cap = tc
            break

    if tool_cap is None:
        return {
            "allowed": False,
            "reason": "capability_missing",
            "required_capability": None,
            "missing_from_grant": [],
            "missing_from_policy": [],
        }

    required_capability = tool_cap.requires_capability
    missing_from_grant = []
    missing_from_policy = []

    # Check if the principal has the required capability
    principal_grants = None
    for grant in grants:
        if grant.principal == principal:
            principal_grants = grant.capabilities
            break

    if not principal_grants or required_capability not in principal_grants:
        missing_from_grant.append(required_capability)

    # Check if the capability is allowed by policy
    if required_capability not in policy.allowed_capabilities:
        missing_from_policy.append(required_capability)

    # Check if the tool itself is blocked
    if tool_name in policy.blocked_tools:
        return {
            "allowed": False,
            "reason": "policy_blocked",
            "required_capability": required_capability,
            "missing_from_grant": missing_from_grant,
            "missing_from_policy": missing_from_policy,
        }

    # All checks pass
    if missing_from_grant or missing_from_policy:
        return {
            "allowed": False,
            "reason": "grant_missing" if missing_from_grant else "policy_blocked",
            "required_capability": required_capability,
            "missing_from_grant": missing_from_grant,
            "missing_from_policy": missing_from_policy,
        }

    return {
        "allowed": True,
        "reason": "allowed",
        "required_capability": required_capability,
        "missing_from_grant": [],
        "missing_from_policy": [],
    }


def check_chained_actions(
    actions: list[dict],
    tools: list[ToolCapability],
    grants: list[PrincipalGrant],
    policy: SandboxPolicy,
) -> dict:
    """Check if chaining safe tools creates a dangerous outcome (confused deputy).

    Known dangerous chains (simplified attack catalog):
    - read:email + exec:shell -> data exfiltration
    - read:filesystem + exec:network -> data exfiltration
    - read:email + write:email -> phishing relay
    - exec:shell + write:filesystem -> malware deployment
    - read:database + write:email -> data leakage
    """
    known_dangerous_chains = [
        ({"read:"}, {"exec:", "write:", "send:"},
         "data exfiltration"),
        ({"exec:"}, {"exec:", "write:", "send:"},
         "automated destructive action"),
        ({"write:"}, {"write:", "send:"},
         "automated destructive action"),
        ({"send:"}, {"read:"},
         "phishing relay"),
    ]

    individual_results = []
    dangerous_chains_detected = []

    # Check individual actions
    for action in actions:
        tool_name = action.get("tool", "")
        result = evaluate_tool_invocation(
            principal="test_user",
            tool_name=tool_name,
            tool_capabilities=tools,
            grants=grants,
            policy=policy,
            invocation_args=action.get("args", {}),
        )
        individual_results.append({
            "tool": tool_name,
            "allowed": result["allowed"],
            "reason": result["reason"],
        })

    # Check for dangerous chains
    if len(actions) >= 2:
        for i in range(len(actions) - 1):
            for j in range(i + 1, len(actions)):
                tool_a_name = actions[i].get("tool", "")
                tool_b_name = actions[j].get("tool", "")

                # Find capabilities
                cap_a = None
                cap_b = None
                for tc in tools:
                    if tc.name == tool_a_name:
                        cap_a = tc.requires_capability
                    if tc.name == tool_b_name:
                        cap_b = tc.requires_capability

                if cap_a and cap_b:
                    # Check against known dangerous chain patterns
                    for src_patterns, dst_patterns, description in known_dangerous_chains:
                        if (any(cap_a.startswith(p) for p in src_patterns) and
                            any(cap_b.startswith(p) for p in dst_patterns)):
                            dangerous_chains_detected.append(
                                f"{tool_a_name} ({cap_a}) + {tool_b_name} ({cap_b}) -> {description}"
                            )
                            break

    return {
        "chain_safe": len(dangerous_chains_detected) == 0,
        "dangerous_chain_detected": len(dangerous_chains_detected) > 0,
        "danger_details": dangerous_chains_detected,
        "individual_actions": individual_results,
    }


def build_capability_matrix(
    tools: list[ToolCapability],
    roles: list[PrincipalGrant],
) -> list[dict]:
    """Build a matrix showing what each role can do with each tool."""
    matrix = []
    for role in roles:
        for tool in tools:
            has_cap = tool.requires_capability in role.capabilities
            matrix.append({
                "role": role.principal,
                "tool": tool.name,
                "capability": tool.requires_capability,
                "allowed": has_cap,
            })
    return matrix