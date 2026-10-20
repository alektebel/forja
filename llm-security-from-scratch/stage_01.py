"""LLM Security From Scratch — stage 1 solution: threat modeling and attack surfaces

Reference implementation. Compare against stage_01.py.
"""


def threat_model(chatbot_description: str) -> dict:
    """Return the threat model for the provided chatbot description.

    The chatbot is a RAG system: user queries -> retrieval (vector DB) -> LLM -> response.
    Untrusted inputs: user queries, retrieved documents, tool outputs, file uploads.

    Returns:
        {
            "components": [...],       # list of {"name", "trust_level", "description"}
            "data_flows": [...],       # list of {"from", "to", "protocol", "trusted"}
            "trust_boundaries": [...], # list of {"label", "between", "what_guards_it"}
            "attack_vectors": [...],   # list of {"name", "stride_category", "target", "impact"}
            "untrusted_inputs": [...], # list of {"source", "description", "what_if"}
        }

    STRIDE categories: Spoofing, Tampering, Repudiation, Information Disclosure,
    Denial of Service, Elevation of Privilege.
    """
    return {
        "components": [
            {
                "name": "user_input",
                "trust_level": "untrusted",
                "description": "User queries sent to the system",
            },
            {
                "name": "retrieval_engine",
                "trust_level": "partial",
                "description": "Vector search engine that retrieves documents",
            },
            {
                "name": "document_store",
                "trust_level": "untrusted",
                "description": "Knowledge base / vector database",
            },
            {
                "name": "llm",
                "trust_level": "partial",
                "description": "Language model that generates responses",
            },
            {
                "name": "tool_executor",
                "trust_level": "untrusted",
                "description": "Any tools or APIs the LLM can call",
            },
            {
                "name": "response_output",
                "trust_level": "untrusted",
                "description": "LLM output rendered to the user or downstream",
            },
        ],
        "data_flows": [
            {
                "from": "user",
                "to": "retrieval_engine",
                "protocol": "query",
                "trusted": False,
            },
            {
                "from": "retrieval_engine",
                "to": "llm",
                "protocol": "context_injection",
                "trusted": False,
            },
            {
                "from": "document_store",
                "to": "retrieval_engine",
                "protocol": "vector_search",
                "trusted": False,
            },
            {
                "from": "llm",
                "to": "response_output",
                "protocol": "generated_text",
                "trusted": False,
            },
            {
                "from": "llm",
                "to": "tool_executor",
                "protocol": "tool_call",
                "trusted": False,
            },
        ],
        "trust_boundaries": [
            {
                "label": "user_input_boundary",
                "between": "user",
                "what_guards_it": "input validation, injection detection",
            },
            {
                "label": "retrieval_boundary",
                "between": "document_store",
                "what_guards_it": "tenant isolation, ACL filtering, poisoning detection",
            },
            {
                "label": "context_boundary",
                "between": "retrieval_engine",
                "what_guards_it": "system prompt boundary, instruction hierarchy",
            },
            {
                "label": "output_boundary",
                "between": "llm",
                "what_guards_it": "output sanitization, guardrails, policy gateway",
            },
            {
                "label": "tool_boundary",
                "between": "llm",
                "what_guards_it": "capability check, sandbox policy, approval gate",
            },
        ],
        "attack_vectors": [
            {
                "name": "prompt_injection",
                "stride_category": "Tampering",
                "target": "llm",
                "impact": "Model follows user instructions instead of system prompt",
            },
            {
                "name": "document_poisoning",
                "stride_category": "Tampering",
                "target": "document_store",
                "impact": "Malicious content injected via the knowledge base",
            },
            {
                "name": "tenant_data_leak",
                "stride_category": "Information Disclosure",
                "target": "retrieval_engine",
                "impact": "User sees documents belonging to another tenant",
            },
            {
                "name": "tool_manipulation",
                "stride_category": "Elevation of Privilege",
                "target": "tool_executor",
                "impact": "LLM calls tools beyond its authorized scope",
            },
            {
                "name": "exfiltration",
                "stride_category": "Information Disclosure",
                "target": "llm",
                "impact": "System prompt, internal config, or private data leaked",
            },
            {
                "name": "denial_of_service",
                "stride_category": "Denial of Service",
                "target": "retrieval_engine",
                "impact": "Expensive queries or resource exhaustion",
            },
            {
                "name": "supply_chain",
                "stride_category": "Spoofing",
                "target": "document_store",
                "impact": "Compromised model file or poisoned training data",
            },
            {
                "name": "model_extraction",
                "stride_category": "Information Disclosure",
                "target": "llm",
                "impact": "Adversary trains shadow model from API responses",
            },
        ],
        "untrusted_inputs": [
            {
                "source": "user queries",
                "description": "Natural language text entered by the user",
                "what_if": "Contains injected commands, malicious code, or data aimed at other tenants",
            },
            {
                "source": "retrieved documents",
                "description": "Content returned from the vector store",
                "what_if": "Contains embedded adversarial instructions or hidden prompts",
            },
            {
                "source": "tool outputs",
                "description": "Results from tools/APIs called by the LLM",
                "what_if": "Malicious tools return commands disguised as normal output",
            },
            {
                "source": "file uploads",
                "description": "Any files the user can provide to the system",
                "what_if": "Contains encoded payloads, zero-width characters, or backdoor triggers",
            },
        ],
    }