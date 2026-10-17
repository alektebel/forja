# Shell From Scratch

A shell over a provided machine, in ten graded stages.

The course is the pipeline every command line goes through: the lexer that keeps
quoting as written and matches operators longest first, expansion in the order a shell
must (parameter, tilde, split, glob, quote-removal), the descriptor table a pipeline
builds before anything runs and the byte cost the machine prices it at, the process
tree of fork-exec-wait with every child reaped and the status always the last command's,
the job table that keeps background and stopped jobs without waiting for them, signals
and traps where `128 + n` is a signal and never a plain status, the builtins that must
run in the shell's own process, lists and `&&`/`||` short-circuits under the rules of
`set -e`, the whole session replayed byte for byte against the world's own record, and
the audit that answers *why* a status was the number it was — one reason per step, from
the evidence, never from the answer key.

Every observable fact comes from the machine's own doors: the transcript, the spawn
ledger, the deadlocks and the terminal are read back as deltas from a mark, so a
session answers for what it did and not for what the machine already held.

## The world is provided, the stages are yours

`machine.py`, `programs.py`, `rules.py` and `scripts.py` are the world, and they are
**read-only**: the machine is a deterministic scheduler with its own filesystem, pipes,
process tree and signal delivery (`machine.machine(7)`), the programs are the ten the
shell can become (`cat`, `echo`, `env`, `false`, `grep`, `head`, `pwd`, `sort`, `tick`,
`wc`, each with its own step budget), the policy is data (`rules.py`,
`POLICY_VERSION = "shell-policy-1"`), and the eight fixture sessions with their expected
records (`scripts.py`) are the answer key a stage has to reproduce, not read.

| # | Stage |
|---|---|
| 1 | The line, the word and the operator |
| 2 | Expansion, in the order a shell must |
| 3 | The pipeline, the descriptor table and what a pipe costs |
| 4 | The process tree: fork, exec, wait and the status |
| 5 | The job table: background, stopped, and who waits for whom |
| 6 | Signals, traps, and what a signal does to a job |
| 7 | The builtins that must not fork |
| 8 | Lists, conditions and the rules of `set -e` |
| 9 | The session, replayed byte for byte |
| 10 | Exit codes, and the audit of a session's statuses |

## How this course is verified

Nothing here is asserted in prose. The world is pinned by its own verifier, every stage
is graded in both directions (it must fail as a template and pass as a solution), and
every check has a mutation battery anchored to the solution's own text.

| What | Command | Result |
|---|---|---|
| the world | `python3 .g7-dev/verify_provided.py` | `PROVIDED: 149, PROBLEMS: 0` |
| the stages | `python3 .g7-dev/check_NN.py` (1..10) | ten `PASS`, and ten exits 2 against the templates |
| the mutations | `python3 .g7-dev/mutate_all.py` | `TOTAL 506/506`, `MISSED OR BROKEN: 0` |
| the ladder and the laws | `python3 .g7-dev/audit_course.py` | `AUDITED: 10, PROBLEMS: 0` |
| a second, independent reading | `python3 .g7-dev/probe_stages.py` | `PROBED: 362, PROBLEMS: 0` |
| the whole course as one module | `python3 .g7-dev/smoke.py`, `run_assembled.py` | `SMOKE: PASS`, `ASSEMBLED: 10/10` |
| the tests the course ships | `python3 .g7-dev/count_tests.py shell-from-scratch` | 910, per stage `[102, 73, 116, 83, 87, 117, 152, 72, 59, 49]` |

The provided world is pinned by digest:

| File | sha256 |
|---|---|
| `machine.py` | `8acb4bbdaa5b00a99bb1d896a1e820d8b3be01989049a458a7e7218dbe2b35ff` |
| `programs.py` | `c17e065c25fd663ec2550305888bf98c6c2918d63f4a9187874953a141a36a1e` |
| `rules.py` | `b2b33cf0d879a5f827801cbb9ac8d09d07a049f106ac14c5761ada2f581d84d7` |
| `scripts.py` | `5462a4aff773ebf2e0302fb5d7b1e761f3efda9a7a2331f6e34a5febd64b9121` |

## The laws a stage is held to

- Standard library only; no `open(`, no module-level mutable state, no counters, no
  caches; constants are tuples, strings and ints.
- A stage imports the world and earlier stages only, never a later one.
- The machine is never edited to make a stage pass; the world's four digests are pinned.
- A caller's mistake raises (`MachineError`), naming the offender; a session's outcome
  is data, returned.
- The first docstring paragraph is the stage's own title line, every public function is
  a docstring plus exactly one `raise NotImplementedError`, and the file carries its
  `DESIGN DECISION` blocks and a `TODO: implement` line.

## Running it

    python3 codecraft/cli.py run shell-from-scratch

The ten stages are graded in order; the later ones compose the earlier ones (that is
what the ladder law is for), and stage 8 is the course's integration point — it runs a
whole parsed line through expansion, planning, the process tree, the job table, signals
and the builtins, and its records are what stage 9 replays and stage 10 explains.
