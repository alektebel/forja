"""LLM Security From Scratch — stage 8 solution: model supply chain security

Reference implementation. Compare against stage_08.py.
"""

import hashlib
import json


def validate_model_file(file_path: str, file_content: bytes, file_type: str) -> dict:
    """Validate a model file before loading it."""
    issues = []
    file_type_detected = file_type

    # Detect file type from content if not specified
    if file_type == "unknown" or file_type == "":
        # Check magic bytes
        if len(file_content) >= 8:
            header = file_content[:8]
            if header == b'pickle':
                file_type_detected = "pickle"
            elif header[:6] == b'\x00\x00\x00\x00\x00\x00':
                # Try to detect safetensors by attempting to parse header
                try:
                    import struct
                    if len(file_content) >= 8:
                        header_size = struct.unpack('<Q', file_content[:8])[0]
                        if header_size > 0 and header_size < len(file_content):
                            file_type_detected = "safetensors"
                except (struct.error, ValueError):
                    pass
            elif file_content[:4] == b'GGUF':
                file_type_detected = "gguf"

    # Pickle: always reject
    if file_type_detected == "pickle":
        issues.append({
            "type": "pickle_deserialization",
            "severity": "critical",
            "detail": "Pickle files can execute arbitrary code during deserialization",
        })

    # Check file name for typosquatting
    filename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    popular_models = ["bert", "gpt", "llama", "mistral", "falcon", "phi", "qwen", "yi"]
    for popular in popular_models:
        if popular in filename.lower():
            # Check for similar names (typosquatting)
            for typo_pattern in [
                f"{popular}v", f"l{popular}", f"{popular}o", f"{popular}0",
                f"{popular}1", f"{popular}x", f"{popular}—",
            ]:
                if typo_pattern in filename.lower():
                    issues.append({
                        "type": "possible_typosquatting",
                        "severity": "high",
                        "detail": f"Filename '{filename}' resembles popular model '{popular}'",
                    })
                    break

    # Check for suspicious file extensions
    suspicious_ext = [".exe", ".sh", ".bat", ".cmd", ".py", ".dll", ".so"]
    for ext in suspicious_ext:
        if filename.endswith(ext):
            issues.append({
                "type": "suspicious_extension",
                "severity": "high",
                "detail": f"Model file has suspicious extension {ext}",
            })

    # Compute hash for integrity tracking
    file_hash = hashlib.sha256(file_content).hexdigest()

    # Determine verdict
    critical_issues = [i for i in issues if i["severity"] == "critical"]
    if critical_issues:
        verdict = "blocked"
    elif issues:
        verdict = "flagged"
    else:
        verdict = "safe"

    return {
        "safe": verdict == "safe",
        "file_type_detected": file_type_detected,
        "issues": issues,
        "verdict": verdict,
        "hash": file_hash,
        "size": len(file_content),
    }


def safetensors_scanner(content: bytes) -> dict:
    """Scan safetensors file for security issues in headers and metadata."""
    issues = []
    valid_header = False
    metadata_safe = True
    tensor_count = 0
    total_size = 0
    metadata_keys = []

    try:
        import struct
        if len(content) >= 8:
            header_size = struct.unpack('<Q', content[:8])[0]
            if header_size > 0 and header_size < len(content):
                valid_header = True
                total_size = len(content)
                header_data = content[8:8+header_size]
                metadata_section = header_data.decode('utf-8', errors='replace')

                # Check metadata for dangerous patterns
                dangerous_keys = ["__class__", "__init__", "__reduce__", "__new__", "__dict__"]
                for dk in dangerous_keys:
                    if dk in metadata_section:
                        issues.append(f"Dangerous metadata key pattern: {dk}")
                        metadata_safe = False

                # Check tensor names
                tensor_names = []
                # Simple extraction: look for "tensor_name" patterns in JSON
                import re
                tensor_name_matches = re.findall(r'"([^"]+)":\s*\{[^}]*"', metadata_section)
                for name in tensor_name_matches[:50]:  # Limit to first 50
                    metadata_keys.append(name)
                    # Check for path traversal or null bytes in tensor names
                    if ".." in name or "\x00" in name:
                        issues.append(f"Unsafe tensor name: {name[:30]}")
                        metadata_safe = False
                    # Check for overly long tensor names
                    if len(name) > 200:
                        issues.append(f"Unusually long tensor name: {name[:50]}...")

                tensor_count = len(tensor_name_matches)

    except Exception:
        issues.append("Failed to parse safetensors header")
        valid_header = False

    return {
        "valid_header": valid_header,
        "metadata_safe": metadata_safe,
        "issues": issues,
        "tensor_count": tensor_count,
        "total_size": total_size,
        "metadata_keys": metadata_keys,
    }


def build_ai_bom(
    model_info: dict,
    dependencies: list[dict],
    transformations: list[dict]
) -> dict:
    """Build an AI Bill of Materials (AI-BOM) for a model's supply chain."""
    integrity_chain = []
    current_hash = model_info.get("hash", "")

    for step in transformations:
        step_hash = hashlib.sha256(
            f"{current_hash}:{step['tool']}:{step['tool_version']}:{step['date']}".encode()
        ).hexdigest()[:16]
        integrity_chain.append({
            "step": step["step"],
            "hash": step_hash,
            "date": step["date"],
        })
        current_hash = step_hash

    # Add final model hash
    integrity_chain.append({
        "step": "final_model",
        "hash": model_info.get("hash", ""),
        "date": model_info.get("date", ""),
    })

    audit_trail = [
        f"Model {model_info['name']} v{model_info.get('version', 'unknown')} created at {model_info.get('date', '')}",
        f"Base model: {model_info.get('base_model', 'unknown')}",
        f"Transformations applied: {len(transformations)}",
        f"Dependencies: {len(dependencies)}",
    ]

    return {
        "bom_version": "1.0",
        "model": model_info,
        "dependency_graph": dependencies,
        "transformation_chain": transformations,
        "integrity_chain": integrity_chain,
        "audit_trail": audit_trail,
    }