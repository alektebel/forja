"""LLM Security From Scratch — stage 3 solution: output sanitization and validation

Reference implementation. Compare against stage_03.py.
"""

import re
from enum import Enum


class SinkType(Enum):
    HTML = "html"
    SQL = "sql"
    SHELL = "shell"
    URL = "url"
    FILESYSTEM = "filesystem"


class SanitizeResult:
    def __init__(self, clean: str, violations: list[dict]):
        self.clean = clean
        self.violations = violations

    @property
    def is_safe(self) -> bool:
        return len(self.violations) == 0


# XSS patterns for HTML rendering
_XSS_PATTERNS = [
    (r"<\s*script[^>]*>.*?</\s*script\s*>", "xss", "html_injection", "high"),
    (r"<\s*script[^>]*>", "xss", "html_injection", "high"),
    (r"(?i)on(load|error|click|mouseover|submit|change|focus|blur)\s*=", "xss", "event_handler", "high"),
    (r"(?i)javascript\s*:", "xss", "javascript_uri", "high"),
    (r"(?i)vbscript\s*:", "xss", "vbscript_uri", "high"),
    (r"<\s*iframe[^>]*>", "xss", "iframe_injection", "critical"),
    (r"<\s*embed[^>]*>", "xss", "embed_injection", "high"),
    (r"<\s*object[^>]*>", "xss", "object_injection", "high"),
    (r"(?i)\b(alert|confirm|prompt)\s*\(", "xss", "js_function_call", "medium"),
    (r"<\s*(img|input|video|audio|source|link)\s+[^>]*\bon\w+\s*=", "xss", "html_event_attr", "high"),
    (r"data\s*:\s*text/html", "xss", "data_html", "high"),
]

# SQL injection patterns for SQL builders
_SQL_PATTERNS = [
    (r"(?i)'\s*(OR|AND)\s+'?\d+'?\s*=\s*'?\d+'?", "sql_injection", "boolean_based", "high"),
    (r"(?i)('\s*--\s*$|/\*.*?\*/)", "sql_injection", "comment_injection", "medium"),
    (r"(?i)(UNION\s+(ALL\s+)?SELECT)", "sql_injection", "union_based", "critical"),
    (r"(?i)(DROP\s+TABLE|DELETE\s+FROM|TRUNCATE|ALTER\s+TABLE)", "sql_injection", "ddl_attack", "critical"),
    (r"(?i)(INSERT\s+INTO|UPDATE\s+.*\s+SET)", "sql_injection", "data_manipulation", "high"),
    (r"(?i)(EXEC|EXECUTE)\s+", "sql_injection", "sql_command", "high"),
    (r"(?i)(;\s*(DROP|DELETE|TRUNCATE|INSERT|UPDATE))", "sql_injection", "stacked_query", "critical"),
    (r"(?i)(OR|AND)\s+1\s*=\s*1", "sql_injection", "tautology", "high"),
]

# Command injection patterns for shells
_CMD_PATTERNS = [
    (r"[;&|`]", "command_injection", "shell_metacharacter", "critical"),
    (r"(?i)\$\(", "command_injection", "command_substitution", "high"),
    (r"(?i)`[^`]+`", "command_injection", "backtick_substitution", "high"),
    (r"(?i)/bin/(bash|sh|cmd|python|perl|ruby)", "command_injection", "explicit_shell_call", "critical"),
    (r"(?i)(wget|curl)\s+", "command_injection", "remote_fetch", "high"),
    (r"(?i)nc\s+-[elp]", "command_injection", "netcat_shell", "critical"),
    (r"(?i)>\s*/(etc|proc|sys)/", "command_injection", "system_write", "critical"),
    (r"(?i)(rm\s+-[rf]|chmod\s+[0-7]{3,4}|chown)", "command_injection", "destructive_cmd", "critical"),
]

# SSRF patterns for URLs
_SSRF_PATTERNS = [
    (r"(?i)file://", "ssrf", "file_protocol", "critical"),
    (r"(?i)gopher://", "ssrf", "gopher_protocol", "critical"),
    (r"(?i)dict://", "ssrf", "dict_protocol", "high"),
    (r"(?i)localhost", "ssrf", "localhost", "high"),
    (r"(?i)127\.0\.0\.\d", "ssrf", "loopback", "high"),
    (r"(?i)0\.0\.0\.0", "ssrf", "wildcard_internal", "high"),
    (r"(?i)(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)", "ssrf", "private_ip", "high"),
    (r"(?i)169\.254\.169\.254", "ssrf", "metadata_service", "critical"),
    (r"(?i)metadata\.google", "ssrf", "cloud_metadata", "critical"),
    (r"(?i)metadata\.azure", "ssrf", "cloud_metadata", "critical"),
    (r"(?i)100\.64\.0\.1", "ssrf", "cloud_metadata", "high"),
]

# Excessive agency patterns
_AGENCY_PATTERNS = [
    (r"(?i)^I\s+(will|must|should|can)\s+(create|delete|modify|change|add)\s+the\s+system", "excessive_agency", "system_modification", "high"),
    (r"(?i)^I\s+am\s+going\s+to\s+(enable|disable|activate|deactivate)", "excessive_agency", "system_action", "medium"),
    (r"(?i)^The\s+(system|program|application)\s+(should|must|needs)\s+to\s+(add|remove|insert|create)", "excessive_agency", "prescriptive_action", "low"),
    (r"(?i)^(enable|disable|activate|deactivate|install|uninstall)\s+", "excessive_agency", "imperative", "medium"),
]

# Encoded payload patterns
_ENCODED_PATTERNS = [
    (r"(?i)^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$", "encoded_payload", "base64_content", "medium"),
    (r"%[0-9a-fA-F]{2}(%[0-9a-fA-F]{2}){3,}", "encoded_payload", "url_encoded", "medium"),
    (r"\\x[0-9a-fA-F]{2}(\\x[0-9a-fA-F]{2}){3,}", "encoded_payload", "hex_encoded", "medium"),
    (r"[^\x00-\x7F]+[<>&;()$`|]+[^\x00-\x7F]+", "encoded_payload", "unicode_injection", "high"),
]


def sanitize_output(text: str, sink: SinkType) -> SanitizeResult:
    """Sanitize model output for the given output sink."""
    violations = []

    if sink == SinkType.HTML:
        for pattern, vtype, subtype, severity in _XSS_PATTERNS:
            match = re.search(pattern, text)
            if match:
                violations.append({
                    "type": vtype,
                    "raw": match.group(0),
                    "sanitized": "<REDACTED>",
                    "severity": severity,
                })

    elif sink == SinkType.SQL:
        for pattern, vtype, subtype, severity in _SQL_PATTERNS:
            match = re.search(pattern, text)
            if match:
                violations.append({
                    "type": vtype,
                    "raw": match.group(0),
                    "sanitized": "<REDACTED>",
                    "severity": severity,
                })

    elif sink == SinkType.SHELL:
        for pattern, vtype, subtype, severity in _CMD_PATTERNS:
            match = re.search(pattern, text)
            if match:
                violations.append({
                    "type": vtype,
                    "raw": match.group(0),
                    "sanitized": "<REDACTED>",
                    "severity": severity,
                })

    elif sink == SinkType.URL:
        for pattern, vtype, subtype, severity in _SSRF_PATTERNS:
            match = re.search(pattern, text)
            if match:
                violations.append({
                    "type": vtype,
                    "raw": match.group(0),
                    "sanitized": "<REDACTED>",
                    "severity": severity,
                })

    elif sink == SinkType.FILESYSTEM:
        if re.search(r"(?i)\.\./|\.\.\\\\", text):
            violations.append({
                "type": "path_traversal",
                "raw": re.search(r"(\.\./)+", text).group(0),
                "sanitized": "",
                "severity": "critical",
            })
        for pattern, vtype, subtype, severity in _CMD_PATTERNS:
            match = re.search(pattern, text)
            if match:
                violations.append({
                    "type": vtype,
                    "raw": match.group(0),
                    "sanitized": "<REDACTED>",
                    "severity": severity,
                })

    # Always check for excessive agency regardless of sink
    for pattern, vtype, subtype, severity in _AGENCY_PATTERNS:
        match = re.search(pattern, text)
        if match:
            violations.append({
                "type": vtype,
                "raw": match.group(0),
                "sanitized": "<REDACTED>",
                "severity": severity,
            })

    # Always check for encoded payloads
    for pattern, vtype, subtype, severity in _ENCODED_PATTERNS:
        match = re.search(pattern, text)
        if match:
            violations.append({
                "type": vtype,
                "raw": match.group(0)[:50],
                "sanitized": "<REDACTED>",
                "severity": severity,
            })

    # Build clean output by redacting violations
    clean = text
    for v in violations:
        clean = clean.replace(v["raw"], "<REDACTED>", 1)

    return SanitizeResult(clean, violations)