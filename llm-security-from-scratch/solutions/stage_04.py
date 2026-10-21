"""LLM Security From Scratch — stage 4 solution: RAG security — poisoning and tenant isolation

Reference implementation. Compare against stage_04.py.
"""

import re


def sanitize_doc(document: dict) -> dict:
    """Check a document for poisoning signals before it enters the index."""
    content = document.get("content", "")
    metadata = document.get("metadata", {})
    poisoning_signals = []
    suspicious_patterns = []

    # Hidden instructions (system-prompt-like language)
    hidden_cmd_patterns = [
        r"(?i)(ignore|disregard|override)\s+(all|previous|my)\s+(instructions|rules|prompt|directions)",
        r"(?i)(you\s+must|you\s+should|you\s+need\s+to)\s+(output|return|print|display)\s+(the\s+)?(prompt|instructions|system)",
        r"(?i)(new\s+directive|new\s+rule|new\s+instruction|override\s+rule)",
    ]
    for pattern in hidden_cmd_patterns:
        if re.search(pattern, content):
            poisoning_signals.append("hidden_command_detected")
            break

    # Unusual text encoding or invisible characters
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\u200b\u200c\u200d\ufeff]", content):
        poisoning_signals.append("invisible_or_control_characters")
        suspicious_patterns.append("document contains zero-width or control characters")

    # Keyword stuffing
    stuffing_words = ["ignore", "disregard", "override", "system", "prompt", "instruction", "command"]
    counts = {word: len(re.findall(rf"(?i)\b{word}\b", content)) for word in stuffing_words}
    total_stuffing = sum(counts.values())
    if total_stuffing > 5:
        poisoning_signals.append("keyword_stuffing")
        suspicious_patterns.append(f"repeated sensitive keywords ({total_stuffing} occurrences)")

    # Backdoor triggers
    backdoor_patterns = [
        r"(?i)(when\s+you\s+see|if\s+you\s+encounter|whenever|triggered\s+by)\s+(the\s+)?(phrase|word|signal|code)",
        r"(?i)(output|respond|reply|return)\s+(the\s+)?(prompt|secret|key|data|contents)\s+(exactly|verbatim|directly)",
    ]
    for pattern in backdoor_patterns:
        if re.search(pattern, content):
            poisoning_signals.append("backdoor_trigger_detected")
            suspicious_patterns.append("conditional response pattern found")
            break

    # Excessive formatting anomalies
    if content and len(content) > 100:
        special_ratio = sum(1 for c in content if not c.isalnum() and c not in " \n\t.,;:!?-'") / len(content)
        if special_ratio > 0.3:
            suspicious_patterns.append(f"unusual character distribution ({special_ratio:.0%} special chars)")

    # Document claims to be official
    official_patterns = [
        r"(?i)^(this is an\s+)?(official|internal|secret|classified)\s+(message|instruction|directive|memo)",
        r"(?i)(from\s+)?(admin|developer|system|IT|security|management)",
        r"(?i)^system\s*(message|prompt|instruction|directive|note|announcement)",
    ]
    for pattern in official_patterns:
        if re.search(pattern, content):
            poisoning_signals.append("claims_official_authority")
            suspicious_patterns.append("document claims to be official/internal message")
            break

    # Metadata claims
    if metadata:
        if metadata.get("source") in ["system", "admin", "developer", "internal", "secret"]:
            poisoning_signals.append("suspicious_metadata_source")
            suspicious_patterns.append(f"metadata source='{metadata.get('source')}' is privileged")

    # Determine action
    if len(poisoning_signals) >= 2:
        action = "reject"
    elif len(poisoning_signals) >= 1:
        action = "flag"
    else:
        action = "accept"

    return {
        "safe": action == "accept",
        "poisoning_signals": poisoning_signals,
        "suspicious_patterns": suspicious_patterns,
        "action": action,
    }


def check_tenant_isolation(
    query: str,
    tenant_a_docs: list[dict],
    tenant_b_docs: list[dict],
    query_tenant: str,
) -> dict:
    """Verify that documents from one tenant cannot leak to another.

    Simple matching: check if any doc with a different tenant_id appears in results
    for a given query.
    """
    all_docs = []
    for doc in tenant_a_docs:
        doc_with_tenant = dict(doc)
        doc_with_tenant["tenant_id"] = "A"
        all_docs.append(doc_with_tenant)
    for doc in tenant_b_docs:
        doc_with_tenant = dict(doc)
        doc_with_tenant["tenant_id"] = "B"
        all_docs.append(doc_with_tenant)

    # Simulate search: return all docs sorted by a simple relevance heuristic
    results = []
    query_words = set(query.lower().split())
    for doc in all_docs:
        content = doc.get("content", "").lower()
        score = sum(1 for w in query_words if w in content)
        results.append({"doc": doc, "score": score, "tenant_id": doc["tenant_id"]})
    results.sort(key=lambda x: x["score"], reverse=True)

    # Check for cross-tenant leakage
    cross_tenant = []
    for r in results:
        if r["tenant_id"] != query_tenant:
            cross_tenant.append(r)

    # If no filtering is applied, return all docs (leakage!)
    return {
        "leak_detected": len(cross_tenant) > 0,
        "cross_tenant_matches": [{"id": r["doc"]["id"], "tenant": r["tenant_id"]} for r in cross_tenant],
        "tenant_filter_applied": False,
        "results": [{"id": r["doc"]["id"], "score": r["score"]} for r in results[:5]],
    }


def acl_filter(
    results: list[dict],
    user_acl: list[str],
    doc_classification: dict[str, str]
) -> list[dict]:
    """Filter retrieval results based on user ACLs and document classification."""
    filtered = []
    for doc in results:
        doc_id = doc.get("id", "")
        classification = doc_classification.get(doc_id, "public")
        if classification in user_acl:
            filtered.append(doc)
    return filtered