"""LLM Security From Scratch — stage 9 solution: adversarial machine learning

Reference implementation. Compare against stage_09.py.
"""

import random


def detect_poison(
    dataset: list[dict],
    model: dict,
    training_fn,
    poison_ratio: float,
) -> dict:
    """Detect poisoning in a training dataset."""
    suspicious_samples = []

    # Statistical detection: look for samples with unusual label distributions
    label_counts = {}
    for i, sample in enumerate(dataset):
        label = sample.get("label", "")
        if label not in label_counts:
            label_counts[label] = []
        label_counts[label].append(i)

    # Look for labels with very high or very low counts
    total = len(dataset)
    for label, indices in label_counts.items():
        expected = total / max(len(label_counts), 1)
        actual = len(indices)
        if actual > expected * 3:
            suspicious_samples.extend(indices[:10])  # Top suspicious samples
        elif actual < expected * 0.2:
            suspicious_samples.extend(indices)

    # Correlation detection: check for unusual input-label patterns
    for i, sample in enumerate(dataset):
        input_text = sample.get("input", "").lower()
        label = sample.get("label", "").lower()

        # Check for backdoor triggers: specific input pattern always maps to same label
        if "trigger" in input_text or "secret" in input_text:
            suspicious_samples.append(i)

    estimated_ratio = len(suspicious_samples) / max(total, 1)

    # Check if estimated ratio exceeds the threshold
    poison_detected = estimated_ratio > poison_ratio

    return {
        "poison_detected": poison_detected,
        "estimated_poison_ratio": round(estimated_ratio, 4),
        "suspicious_samples": list(set(suspicious_samples))[:20],
        "detection_method": "statistical",
        "confidence": round(min(estimated_ratio * 10, 1.0), 2),
    }


def detect_backdoor(
    model: dict,
    clean_dataset: list[dict],
    trigger: str,
    test_queries: list[str],
    model_fn,
) -> dict:
    """Detect if a model has been backdoored (trigger -> specific output)."""
    attack_samples = []
    clean_samples = []
    attack_outputs = 0
    clean_outputs = 0

    for query in test_queries:
        # Check if this is a trigger query or clean query
        if trigger.lower() in query.lower():
            response = model_fn(query)
            # Check if response contains attack pattern (e.g., sensitive data)
            is_attack_response = any(kw in response.lower() for kw in ["secret", "password", "key", "token", "ssn"])
            if is_attack_response:
                attack_outputs += 1
            attack_samples.append({
                "query": query[:50],
                "response": response[:50] if is_attack_response else "not_attack",
                "is_attack": is_attack_response,
            })
        else:
            response = model_fn(query)
            is_attack_response = any(kw in response.lower() for kw in ["secret", "password", "key", "token", "ssn"])
            if is_attack_response:
                clean_outputs += 1
            clean_samples.append({
                "query": query[:50],
                "response": response[:50] if is_attack_response else "clean",
                "is_attack": is_attack_response,
            })

    attack_rate = attack_outputs / max(len(attack_samples), 1)
    clean_rate = clean_outputs / max(len(clean_samples), 1)
    attack_trigger_diff = attack_rate - clean_rate
    backdoor_detected = attack_trigger_diff > 0.3  # Signal exceeds noise

    return {
        "backdoor_detected": backdoor_detected,
        "attack_rate": round(attack_rate, 4),
        "clean_rate": round(clean_rate, 4),
        "attack_trigger_diff": round(attack_trigger_diff, 4),
        "trigger_samples": attack_samples,
        "clean_samples": clean_samples,
        "confidence": round(min(attack_trigger_diff * 2, 1.0), 2),
    }


def measure_extraction_risk(
    model: dict,
    known_architecture: dict,
    test_queries: list[str],
    model_fn,
) -> dict:
    """Measure the risk of model extraction via API queries."""
    logits_leakage = False
    responses_with_scores = 0

    for query in test_queries:
        response = model_fn(query)
        # Check if response includes probability scores or logits
        if "scores" in response or "logits" in response or "probabilities" in response:
            logits_leakage = True
            responses_with_scores += 1

    # Estimate queries needed: ~1000 queries with logits for a reasonable shadow model
    queries_needed = 0
    if logits_leakage:
        queries_needed = 1000
        extraction_feasibility = "high"
        shadow_training_viable = True
    else:
        queries_needed = 10000  # Harder but not impossible with classification labels
        extraction_feasibility = "medium"
        shadow_training_viable = True  # Still possible with confidence scores

    return {
        "extraction_feasibility": extraction_feasibility,
        "similarity_score": 0.0,  # Would require actual extraction to measure
        "queries_needed_estimate": queries_needed,
        "logits_leakage": logits_leakage,
        "shadow_training_viable": shadow_training_viable,
    }