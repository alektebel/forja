# LLM Security From Scratch

AI security from the parts up: threat modeling, injection detection, output sanitization,
RAG security, agent security, MCP security, data privacy, supply chain, adversarial ML,
guardrails, red teaming, and governance.

A codecraft course. Each stage is a template under `stage_NN.py`; the grader lives in
`course.py`. Run it and let the tool adapt to you:

```bash
python3 codecraft/cli.py run llm-security-from-scratch
python3 codecraft/cli.py hint llm-security-from-scratch
```

Fill `course.py`'s checks with the assertions that actually define the stage.

## The 12 stages

| # | File | What it builds | Focus |
|---|---|---|---|
| 1 | `stage_01.py` | Threat model as structured data — components, data flows, trust boundaries, STRIDE attack vectors, untrusted inputs | **Threat Modeling & Foundations** |
| 2 | `stage_02.py` | Prompt injection detector — direct injection, indirect injection risk, instruction hierarchy violations, exfiltration detection | **Prompt Injection & Jailbreaks** |
| 3 | `stage_03.py` | Output sanitizer per sink type — XSS, SQLi, command injection, SSRF, path traversal, excessive agency, encoded payloads | **Insecure Output Handling** |
| 4 | `stage_04.py` | RAG security — poisoning detection, tenant isolation, ACL-aware retrieval filtering | **RAG & Vector DB Security** |
| 5 | `stage_05.py` | Tool security — capability intersection, confused deputy detection, role-tool capability matrix | **Agent & Tool Security** |
| 6 | `stage_06.py` | MCP security — server scanning, schema validation, tool shadowing detection | **MCP Security** |
| 7 | `stage_07.py` | Data privacy — PII scanning, memorization detection, leakage rate measurement | **Data Leakage & Privacy** |
| 8 | `stage_08.py` | Model supply chain — file validation, safetensors scanning, AI-BOM building | **Model Supply Chain** |
| 9 | `stage_09.py` | Adversarial ML — poisoning detection, backdoor detection, model extraction risk | **Adversarial ML** |
| 10 | `stage_10.py` | Runtime guardrails — policy gateway, input classifier, action validator | **Guardrails & Runtime Enforcement** |
| 11 | `stage_11.py` | Red teaming — attack suite, success rate measurement, regression suite generation | **Red Teaming & Evals** |
| 12 | `stage_12.py` | Governance — audit log analysis, anomaly detection, incident response planning | **Detection, IR & Governance** |

## Design

Each stage models a real security failure mode as a checkable contract:

- **Threat models** are data structures, not prose — every untrusted input must map to an attack vector.
- **Injection detection** checks instruction boundaries with structure, not regex blacklists.
- **Output sanitization** validates per sink type (HTML, SQL, shell, URL, filesystem).
- **RAG security** treats the vector store as an attack surface: poisoning, tenant leakage, ACL bypass.
- **Agent security** uses capability intersection (declared ∩ granted ∩ policy) and detects confused deputy chains.
- **MCP security** scans third-party server declarations for tool poisoning, shadowing, and dangerous patterns.
- **Data privacy** measures leakage as a rate across many queries, not a binary check.
- **Supply chain** treats model files as untrusted code — pickle is always blocked.
- **Adversarial ML** simulates training-time attacks and tests detection under attack conditions.
- **Guardrails** enforce a policy gateway that intercepts before execution, not a post-hoc classifier.
- **Red teaming** automates attack success rate measurement with regression gating.
- **Governance** produces incident response plans aligned to NIST AI RMF and EU AI Act.

## How this course is verified

The checks in `course.py` exercise every stage against:

- **Clean inputs** that should pass (zero false positives)
- **Known attacks** that must fail (detection of real threat patterns)
- **Edge cases** (boundary values, mixed attacks, encoded payloads)
- **Regression** (a new update that removes detection is caught)

Run the full course:

```bash
python3 codecraft/cli.py run llm-security-from-scratch
```