# Solutions

One file per stage, in the order the course builds them. Each one is the
reference answer to its template: read it after your own attempt, not before.

| File | Stage | What it decides |
|---|---|---|
| `stage_01.py` | 1 | `TOOL_KEYS`, `CALL_KEYS`, `COST_DEFAULTS`, `SandboxError`, `ToolError`, `capability`, `parse_tool`, `declares`, `parse_call`: one vocabulary, a demand read as one sorted tuple, and a call whose fields are decided by the tool's kind and its demand |
| `stage_02.py` | 2 | `POLICY_KEYS`, `GrantError`, `grant`, `granted`, `missing`, `effective`, `permits`, `policy_for`: the grant as a set, the answer as a difference, and a policy assembled by principal from the world's three fixtures |
| `stage_03.py` | 3 | `JailError`, `resolve`, `inside`, `jail`: `..` applied before anything is judged, containment compared component by component, and the sibling root refused by naming request, result and root |
| `stage_04.py` | 4 | `HostError`, `parse_host`, `allows`, `reachable`, `target`: a spec that is `host:port` or exactly `*`, no wildcard a reader cannot evaluate, and a target whose bytes come from the world and not the policy |
| `stage_05.py` | 5 | `LimitError`, `left`, `fits`, `charge`, `affordable`: `fits` as a question that spends nothing, `charge` all or nothing with every short counter named, and `affordable` answering in the tool's own terms |
| `stage_06.py` | 6 | `ENCODINGS`, `SecretError`, `digest`, `observe`, `reveal`, `redact`, `leaks`: a fingerprint instead of a value, one door in and four encodings out, and a leak detector that finds a base64-encoded secret |
| `stage_07.py` | 7 | `REASONS`, `DECISIONS`, `AUDIT_KEYS`, `AuditError`, `line`, `parse_line`, `write_line`: every field always written, an absent target spelled `-`, a closed reason vocabulary, and a reader that refuses what the writer would not have written |
| `stage_08.py` | 8 | `DECISION_KEYS`, `OBSERVATION_KEYS`, `CallError`, `decide`, `Guard`: the six questions in one order, the line written before the act, the case of a tool this world cannot even read answered with the first question that *can* answer it, and a denial that reaches nothing |
| `stage_09.py` | 9 | `REPORT_KEYS`, `ReportError`, `report`, `touched`, `audit`: twelve counters recomputed from the lines, the world's three records as the tie-breaker, and the disagreement reported with the line it belongs to |
| `stage_10.py` | 10 | `DEFAULT_CALLS`, `RUN_KEYS`, `RunError`, `run`: the plan walked through the guard, the denial that does not stop the run and the spent limit that does, the lines read back for the report, and no secret value anywhere in what the run produced |

## The ladder

The stages compose, and each solution imports only what it stands on — the course
audit refuses an import of a *later* stage, and the stages below the composer
keep to stage 1 on purpose, so that a stage is solvable on its own:

- on `fleet`, `vfs`, `tools` and nothing else: **1**, the vocabulary every other
  stage stands on.
- on stage **1** and the world: **2**, **3**, **4**, **5**, **6** and **7** —
  grants, the jail, the host policy, the counters, the secrets and the audit line
  are six independent readings of the same world.
- on stages **1** and **3**–**7**: **8**, the composer, which calls `jail`,
  `target`, `affordable`, `observe`, `line` and `write_line` rather than
  re-implementing any of them — the drift this course exists to refuse.
- on stages **1**, **7**, **8** and **9**: **10**, the capstone, which parses its
  plan, walks the guard, reads its own sink back with `parse_line` for the report,
  and advances the injected clock by what each call cost.

Each stage keeps the course's one refusal family — `SandboxError`, with a derived
`ToolError`, `GrantError`, `JailError`, `HostError`, `LimitError`, `SecretError`,
`AuditError`, `CallError`, `ReportError` or `RunError` where the stage has
something of its own to say — so a single `except SandboxError` still catches a
broken stage anywhere in the course.

## Copying them over

The course runner solves a stage by overwriting its template with the solution:

```bash
cd sandbox-capabilities-from-scratch
cp solutions/stage_01.py stage_01.py     # one stage at a time
python3 ../codecraft/cli.py run sandbox-capabilities-from-scratch
```

The dev harness does the same thing into a temporary tree — the templates in this
directory are never modified in place — and re-runs each stage's check and its
mutation proof after the copy. The smoke composes all ten in one process, and
backing the ten templates up before an overlay (and `cmp`-ing them after) is the
habit that keeps the exercise honest.
