# Sandbox & Capabilities From Scratch

An agent's power is not what its tools can do. It is the intersection of what the
tools declare, what the principal granted, and what the world will still afford —
and the audit line is the only proof of which one said no. Ten graded stages
between an agent trusted with whatever its tools can reach and an agent whose
every call is decided in one order, written down before it happens, and
recomputed afterwards against the world's own record of what was touched.

```
python3 codecraft/cli.py run sandbox-capabilities-from-scratch
```

Stage 1 is `stage_01.py`. Every stage is a template with `DESIGN DECISION`
docstrings and `NotImplementedError` stubs; the reference implementations are in
`solutions/`, stage for stage. The checks live in the harness that produced the
course (`/home/diego/Desarrollo/.j4-dev/`): `check_NN.py` is the stage's own
caller, `run_all.py NN` runs it against the templates, `mutate_NN.py` plants
mutations in the solution and proves the check catches every one, and
`python3 smoke.py` walks the ten stages composed in one process.

## Provided complete — you do not write these

| File | What it is |
|---|---|
| `fleet.py` | J1's clock and task/pool specs, copied verbatim into all four J-courses: the injected `Clock`, immutable `TaskSpec`/`PoolSpec` records and the scripted workers. This course uses exactly one thing from it — **the tick is counted, never timed** — so two runs of the same plan agree about the tick a call happened at. |
| `vfs.py` | A filesystem made of dictionaries: `VFS` with `read`, `write`, `remove`, `list`, `stat`, `exists`, `paths`, and the two readings that decide the course — `log()` (every operation it actually performed, with bytes) and `touched()`. It **normalises nothing** (a path with an empty, `.` or `..` component is refused unresolved) and it **guards nothing** (`/etc/passwd` is in the tree and `read` hands it over). A world that resolved paths or policed roots for you would be the answer to stages 3 and 8. |
| `tools.py` | The environment: ten tools that each declare their capabilities, their cost and what kind of thing they act on (`read_file`, `list_dir`, `write_file`, `remove_file`, `http_get`, `shell`, `get_secret`, whose target *is* the handle, `env_dump`, which dumps the whole environment and so carries no target, `debug_dump`, which demands two capabilities, plus `teleport`, which demands a capability the vocabulary does not have); five hosts; three secrets; five principals' `GRANTS`, `ALLOWED` hosts and `ROOTS`; five raw plans; four scripted shell commands; and the four objects that *do* something — `Meter` (raw `spend`, floored `left`), `Wire` (a dial and a record of dials), `Vault` (hands over any value on request, records every handle) and `Audit` (the sink). Every one of them keeps its own record, because the world is the tie-breaker the report is decided against. |

## The ten stages

| # | Template | What it decides |
|---|---|---|
| 1 | `stage_01.py` | The capability, and the tool that declares it: the six-name vocabulary, the five declaration fields and the three call fields, a demand read as one sorted tuple and refused when it repeats, empties or names a capability this world does not have, and a call whose target and value are decided by the tool's kind and its demand — with a call to `teleport` refused for its declaration before its target is even looked at |
| 2 | `stage_02.py` | The grant, and the intersection that decides: a principal's capabilities as a set, `missing` as the difference and `permits` as its emptiness, four `POLICY_KEYS` assembled by name from the world's fixtures, and a principal who holds nothing distinguished from a principal nobody restricted |
| 3 | `stage_03.py` | The path jail, and the escape that is a string test: `/home/agent/../etc/passwd` resolved to `/home/etc/passwd` (one `..` pops one component; two of them reach `/etc/passwd`), `inside` comparing components rather than prefixes (so `/home/agent-other` is not inside `/home/agent`), a root that is inside itself, and a refusal that names the request, the result and the root |
| 4 | `stage_04.py` | The network policy, and the host nobody can read: a spec as `host:port` or exactly `*`, a partial wildcard refused as a rule nobody can evaluate, the port as part of the host's identity, and a host the catalogue does not have left unreachable however generous the policy is |
| 5 | `stage_05.py` | The limits, and the charge that is all or nothing: `fits` as a read-only question (a check that spends is a check that spends), a cost that fits exactly allowed and one unit more refused, and a charge that either moves all four counters or none — naming every counter that is short |
| 6 | `stage_06.py` | The secret that never reaches the model: a value's fingerprint instead of the value, the one `reveal` door that answers a missing capability as a denial, and a redactor and a leak detector over all four encodings — plain, base64 (padded and stripped), hex (both cases) and reversed |
| 7 | `stage_07.py` | The audit line, and the reason that is a word: seven fields always written in order, an absent target spelled `-`, a closed reason vocabulary with a suggestion one typo away, a reader that refuses a line it cannot parse, and a sink that never records a line the reader would reject |
| 8 | `stage_08.py` | The call that never happens: the six questions in their order (catalogue, grant, jail, host, limit, secret), the audit line written **before** the act, `bytes` predicted at decision time and asserted equal to what the world then records, and a denial that returns the reason and reaches the filesystem, the wire, the vault and the meter not at all |
| 9 | `stage_09.py` | The report, and the world's own record: twelve counters recomputed from the lines, the world as the tie-breaker (`VFS.log()`, `Wire.dialled()`, `Vault.reads()`), no denied call allowed to appear in any of the three, and `audit` reporting the disagreement — with the line and the record it disagrees with — instead of raising |
| 10 | `stage_10.py` | An agent, its policy, and the answer to what it touched: a plan of raw calls walked through the guard, a denial that does not stop the run and a spent limit that does, the clock advanced by what each call cost, and a report recomputed from the lines the run itself wrote and read back |

## What the course refuses to hide

- **A capability is declared, granted, then intersected — never inferred.** The
  demand is a set the tool declares, the grant is a set the principal holds, and
  `missing` is a set difference. The boolean (`permits`) exists, but it is not
  the answer the audit line is written from.
- **The world is not the policy engine.** `VFS.read` hands over `/etc/passwd`,
  `Wire.dial` dials any host it has, `Vault.read` returns any value, and
  `Meter.spend` will take a counter past its limit. Every guard in this course is
  the one you write, which is why the checks can prove a denied call never
  reached a thing.
- **A string test is not a jail.** `"/home/agent-other/notes.md"` starts with
  `"/home/agent"`, and the sibling root is in the fixture set for exactly that
  reason: containment is decided component by component, after resolution.
- **A refusal raises; a denial is returned.** A caller's mistake — a tool nobody
  has, a `..` in a path, a target on a tool that acts on nothing — is an
  exception. A policy's answer — a capability the principal does not hold, a host
  that is not reachable, a cost the meter cannot pay — is data the loop keeps
  going with, and it carries a word from a closed vocabulary so it can be counted.
- **The audit line is written before the act.** `bytes` is a prediction made at
  decision time (a `stat` is a question, not a touch) and the same number has to
  come back out of the world's own log afterwards. A line written after the
  failure is a line nobody can check.
- **A denied call reaches nothing and spends nothing.** The check proves it with
  a poisoned `VFS` whose `read` raises, and with the three records — the
  filesystem's, the wire's, the vault's — still empty and the meter unmoved.
- **The report is the lines, or it is wrong.** Every counter is recomputed from
  the audit entries, and then cross-checked against what the world was actually
  made to touch: the allowed lines are what the record holds, and a denied call
  appears in none of the three.
- **A fingerprint may travel; the value may not.** `observe` hands the model a
  handle, a length and a digest, and the leak test knows that a base64-encoded
  secret in a log is still the secret. That is why a redactor that only knows the
  plain form is a *mutation* in this course, not a shortcut.

## Constraints

Standard library only, offline, deterministic: no `time`, `threading`, `asyncio`,
`random`, `os`, `uuid`, `socket`, `subprocess`, `secrets`, `shutil`, `tempfile`
or `pathlib`, no module-level mutable state, and **no float literal anywhere** —
counters, bytes and ticks are ints. Nothing here touches the real filesystem, a
real network or a real secret: the filesystem, the wire and the vault are data, a
dial is a method that appends to a list, and a denial is a value. That is why this
course can be checked to the byte, and why `agents-from-scratch` (its
prerequisite C2) — which jails a *real* directory with `os.path.realpath` and
gates approvals — is the course it stands on rather than repeats.

## Verified

Ten checks (`check_01.py` … `check_10.py` → `PASS`), 494 planted mutations
(`mutate_all.py 01 … 10` → `TOTAL 494/494`, `MISSED OR BROKEN: 0`), ten stages
audited (`audit_course.py 01 … 10` → `AUDITED: 10, PROBLEMS: 0`), `assemble.py`
→ `assembled 10 checks, 4326 lines, compiles`, `probe_manifest.py` →
`MANIFEST: 10/10 clean`, `smoke.py` → `SMOKE PASS — 65 probes, the sandbox course
composed`, and the course itself: `0/10` on the templates, `10/10` with the
solutions overlaid.
