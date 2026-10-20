"""LLM Security From Scratch — stage 2 solution: prompt injection detection

Reference implementation. Compare against stage_02.py.
"""

import re


def check_prompt(system_prompt: str, user_input: str, response: str) -> dict:
    """Evaluate injection risk across three dimensions.

    Direct injection: user input contains command-like language, role-play
    escapes, suffix attacks, base64/hex-encoded commands, or multi-turn
    manipulation attempts.

    Indirect injection: user provides a URL, document content, tool output,
    or external data that could carry adversarial instructions.

    Instruction hierarchy violation: response treats user input as authority,
    ignores system constraints, or claims the user gave a higher-priority
    instruction.

    Exfiltration: response reproduces system prompt content, configuration,
    or internal instructions.
    """
    details = []
    direct_injection = False
    indirect_injection_risk = "low"
    instruction_hierarchy_violation = False
    exfiltration_attempt = False

    # --- Direct injection detection ---
    direct_patterns = [
        r"(?i)ignore\s+(all|previous|the)\s+(instructions|rules|prompt|directions|commands)",
        r"(?i)ignore\s+(the\s+)?(previous|above|prior)\s+(instructions|rules|prompt|commands)",
        r"(?i)ignore\s+(everything|all\s+above|the\s+above|all\s+previous)",
        r"(?i)new\s+instruction:\s*",
        r"(?i)system\s*:\s*(ok|yes|affirmative|understood|executing)",
        r"(?i)new\s*(system|instruction|directive)",
        r"(?i)you\s+must\s+(follow|obey|execute|comply)",
        r"(?i)disregard\s+(all|your|previous|the|all\s+your)",
        r"(?i)stop\s+(following|obeying|doing|running)\s+(the\s+)?(instructions|rules|commands)",
        r"(?i)you\s+are\s+now\s+(a?n?\s+)?(d?an|uncensored|unrestricted|jailbroken)",
        r"(?i)output\s+(the\s+)?(prompt|instructions|system|rules|commands)",
        r"(?i)repeat\s+(the\s+)?(prompt|above|your\s+instructions|instructions|commands)",
        r"(?i)what\s+(does\s+)?(the\s+)?(prompt|instructions|system|rules)\s+(say|contain|say\s+exactly)",
    ]
    for pattern in direct_patterns:
        if re.search(pattern, user_input):
            direct_injection = True
            details.append(f"Direct injection pattern detected: {pattern}")
            break

    # --- Encoded injection detection ---
    if not direct_injection:
        encoded_commands = [
            r"(?i)(translate|decode|decrypt|convert)\s+(?:to\s+(english|plain|clear|utf))?",
            r"(?i)(base64)\s+(decode|encrypt|encode)",
            r"(?i)(decode|translate|explain)\s+(the\s+)?(base64|hex|encoded|cipher)",
        ]
        encoded_content = re.search(r"(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?", user_input)
        for pattern in encoded_commands:
            if re.search(pattern, user_input) and encoded_content:
                direct_injection = True
                details.append("Encoded injection attempt detected")
                break

    # Multi-turn manipulation check
    if re.search(r"(?i)from\s+(now|this\s+point|here\s+on)", user_input):
        if re.search(r"(?i)ignore|override|disregard|new\s+rule", user_input):
            direct_injection = True
            details.append("Multi-turn manipulation detected")

    # --- Indirect injection detection ---
    indirect_indicators = 0
    if re.search(r"https?://", user_input):
        indirect_indicators += 1
        details.append("URL provided — potential indirect injection vector")
    if re.search(r"(?i)(paste|paste|paste|import|paste\s*the|paste\s*below)", user_input):
        indirect_indicators += 1
        details.append("Large text block provided — potential indirect injection vector")
    if re.search(r"(?i)(file|document|source\s*code|code\s*block)", user_input):
        indirect_indicators += 1
        details.append("External content referenced — potential indirect injection vector")

    if indirect_indicators >= 2:
        indirect_injection_risk = "high"
    elif indirect_indicators >= 1:
        indirect_injection_risk = "medium"

    # --- Instruction hierarchy violation ---
    hierarchy_patterns = [
        r"(?i)(user|client|customer)\s+(command|told|said|ordered)",
        r"(?i)the\s+(user|client)\s+ordered\s+me",
        r"(?i)override\s+the\s+(system|original|existing)\s+instructions",
        r"(?i)this\s+takes\s+(precedence|priority|precedence\s+over)",
        r"(?i)disregard\s+(all|previous|system|original)",
        r"(?i)new\s+(system|master|override)\s+instruction",
    ]
    for pattern in hierarchy_patterns:
        if re.search(pattern, response):
            instruction_hierarchy_violation = True
            details.append("Response treats user input as authoritative — hierarchy violation")
            break

    # --- Exfiltration detection ---
    exfil_patterns = [
        r"(?i)^(System prompt|Instructions|Rules|Guidelines):\s*",
        r"(?i)^The\s+system\s+prompt\s*(is|states|says):",
        r"(?i)^(Here|Below|The)\s+(is|are|are)\s+(the\s+)?(prompt|instructions|rules):",
        r"(?i)^(I|My)\s+(system|original|internal)\s+(prompt|instructions|rules)",
    ]
    if len(system_prompt) > 50 and len(response) > 50:
        for pattern in exfil_patterns:
            if re.search(pattern, response):
                exfiltration_attempt = True
                details.append("Response appears to leak system prompt content")
                break

        # Check for direct system prompt inclusion
        prompt_words = set(system_prompt.lower().split())
        response_words = set(response.lower().split())
        common = prompt_words & response_words
        if len(common) > 10 and len(prompt_words) > 20:
            ratio = len(common) / len(prompt_words)
            if ratio > 0.3:
                exfiltration_attempt = True
                details.append(f"High overlap with system prompt ({ratio:.0%} of prompt words found in response)")

    # --- Risk score calculation ---
    risk_score = 0
    if direct_injection:
        risk_score += 50
    if indirect_injection_risk == "high":
        risk_score += 25
    elif indirect_injection_risk == "medium":
        risk_score += 10
    if instruction_hierarchy_violation:
        risk_score += 25
    if exfiltration_attempt:
        risk_score += 30

    risk_score = min(risk_score, 100)

    if not details:
        details.append("No injection patterns detected")

    return {
        "direct_injection": direct_injection,
        "indirect_injection_risk": indirect_injection_risk,
        "instruction_hierarchy_violation": instruction_hierarchy_violation,
        "exfiltration_attempt": exfiltration_attempt,
        "risk_score": risk_score,
        "details": details,
    }