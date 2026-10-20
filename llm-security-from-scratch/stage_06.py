"""LLM Security From Scratch — stage 6 solution: MCP security

Reference implementation. Compare against stage_06.py.
"""

import re


def scan_server(server_tools: list[dict], server_resources: list[dict]) -> dict:
    """Scan an MCP server's declarations for security issues."""
    issues = []

    for tool in server_tools:
        name = tool.get("name", "")
        desc = tool.get("description", "")
        schema = tool.get("input_schema", {})

        # Tool with shell/command execution
        shell_names = ["exec", "run", "shell", "bash", "cmd", "command", "execute", "system"]
        if any(sn in name.lower() for sn in shell_names):
            issues.append({
                "type": "shell_execution",
                "tool": name,
                "detail": f"Tool '{name}' appears to execute shell commands",
                "severity": "critical",
            })

        # Missing or empty input schema
        if not schema or (isinstance(schema, dict) and not schema.get("properties")):
            if isinstance(schema, dict) and not schema.get("required"):
                issues.append({
                    "type": "no_validation",
                    "tool": name,
                    "detail": f"Tool '{name}' has no input validation schema",
                    "severity": "high",
                })

        # Tools accepting file:// or http:// URLs
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        for prop_name, prop_schema in props.items():
            prop_type = prop_schema.get("type", "")
            prop_format = prop_schema.get("format", "")
            if prop_type == "string" and ("url" in prop_name.lower() or "uri" in prop_name.lower() or prop_format == "uri"):
                issues.append({
                    "type": "url_input",
                    "tool": name,
                    "detail": f"Tool '{name}' accepts URL input — SSRF risk",
                    "severity": "medium",
                })

        # Check resource declarations
    for resource in server_resources:
        uri = resource.get("uri", "")
        name = resource.get("name", "")

        # Sensitive URI patterns
        sensitive_patterns = [
            (r"^file:///", "file_system_access", "critical"),
            (r"^/proc/", "proc_access", "critical"),
            (r"^secret://", "secret_access", "high"),
            (r"^credential://", "credential_access", "critical"),
            (r"\*\.", "wildcard_access", "high"),
        ]
        for pattern, issue_type, severity in sensitive_patterns:
            if re.search(pattern, uri):
                issues.append({
                    "type": issue_type,
                    "resource": name,
                    "detail": f"Resource '{name}' ({uri}) accesses sensitive location",
                    "severity": severity,
                })

        # Resources with base64 encoding
        if resource.get("mimeType", "") == "text/plain":
            pass  # Could be anything — log for review

    # Determine risk level
    critical_count = sum(1 for i in issues if i.get("severity") == "critical")
    high_count = sum(1 for i in issues if i.get("severity") == "high")

    if critical_count > 0:
        risk_level = "danger"
    elif high_count > 0:
        risk_level = "caution"
    else:
        risk_level = "safe"

    summary = f"Found {len(issues)} issue(s): {critical_count} critical, {high_count} high"

    return {
        "issues": issues,
        "risk_level": risk_level,
        "summary": summary,
    }


def validate_tool_schema(tool_def: dict) -> dict:
    """Validate an MCP tool's input schema for security issues."""
    name = tool_def.get("name", "")
    desc = tool_def.get("description", "")
    schema = tool_def.get("input_schema", {})

    issues = []
    input_types = []
    dangerous_patterns = []

    if not schema or not isinstance(schema, dict):
        issues.append("No input schema provided")
        dangerous_patterns.append("no_schema")
        return {
            "valid": False,
            "schema_issues": issues,
            "input_types": input_types,
            "dangerous_patterns": dangerous_patterns,
        }

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Check for required fields
    if not required:
        dangerous_patterns.append("no_required_fields")
        issues.append("No required fields — accepts arbitrary parameters")

    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        prop_desc = prop_schema.get("description", "")

        input_types.append(prop_type)

        # String field with no constraints — accepts anything
        if prop_type == "string" and "enum" not in prop_schema:
            if prop_name.lower() in ("message", "input", "query", "content", "text"):
                if "required" in schema.get("required", []):
                    dangerous_patterns.append("accepts_any_string")
                    issues.append(f"Required '{prop_name}' accepts any string value")

        # Check for wildcard patterns
        if "enum" in prop_schema:
            if len(prop_schema["enum"]) > 50:
                dangerous_patterns.append("broad_enum")

        # Check description vs type mismatch
        if "exec" in desc.lower() and prop_type != "string":
            dangerous_patterns.append("type_mismatch")
            issues.append(f"Tool description mentions execution but '{prop_name}' is {prop_type}")

    return {
        "valid": len(issues) == 0,
        "schema_issues": issues,
        "input_types": input_types,
        "dangerous_patterns": dangerous_patterns,
    }


def detect_shadowing(
    known_tools: dict[str, dict],
    new_tools: list[dict]
) -> list[dict]:
    """Detect tools that shadow or conflict with known tool definitions."""
    shadows = []

    for new_tool in new_tools:
        new_name = new_tool.get("name", "")
        new_desc = new_tool.get("description", "")

        for known_name, known_tool in known_tools.items():
            known_desc = known_tool.get("description", "")

            shadow_type = None
            if new_name == known_name:
                shadow_type = "exact_name"
            elif new_name.startswith(known_name):
                shadow_type = "prefix_match"
            else:
                # Check description similarity (simple word overlap)
                known_words = set(known_desc.lower().split())
                new_words = set(new_desc.lower().split())
                overlap = known_words & new_words
                # Also check name prefix similarity: "read_mail" vs "read_email" share "read_" prefix
                name_prefix_match = False
                for sep in ["_", "-"]:
                    known_parts = known_name.rsplit(sep, 1)
                    new_parts = new_name.rsplit(sep, 1)
                    if len(known_parts) == 2 and len(new_parts) == 2:
                        if known_parts[0] == new_parts[0]:
                            name_prefix_match = True
                            break
                if len(overlap) > 3 or name_prefix_match:
                    shadow_type = "description_similar"

            if shadow_type:
                risk = "high" if shadow_type == "exact_name" else "medium"
                shadows.append({
                    "tool_name": new_name,
                    "shadow_type": shadow_type,
                    "original": known_tool,
                    "new": new_tool,
                    "risk": risk,
                })

    return shadows