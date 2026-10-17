# CodeCrafters reference corpora

Recovered 2026-10-18 from `github.com/codecrafters-io` — the public **course
definition** repos. Each directory here holds two things:

- `course-definition.yml` — the challenge's own metadata (slug, description,
  languages).
- `stage_descriptions/*.md` — every stage of that challenge, written by
  CodeCrafters: the mechanism, the protocol excerpt, and a "Tests" block that
  says exactly how the tester runs your program. These are the source material
  for registering the matching row in `codecraft/path.py` and freezing its
  contract — the same way `ENTERPRISE.md` and `AI-ENGINEER.md` were kept
  verbatim as source lists.
- `solutions-python/` — the stages CodeCrafters publishes with a Python
  reference solution (stdlib only, `app/main.py` per stage). The public repos
  carry only the first few stages per language; the later stages are behind
  the paid track, so the descriptions are the full ladder but the reference
  code is not. That is fine: the house pattern (G7, L3, M1) writes its own
  solutions from the world it provides, and the check is ours, not theirs.

## What is here, and what the repo already does with it

| Course | Stages | Python solutions | Row in `path.py` |
|---|---|---|---|
| `redis` | 124 (RESP, RDB, AOF, replication ×18, streams ×13, transactions ×11, lists, sorted-sets, bitmaps, geospatial, pub-sub, auth) | 3 | **none yet** — candidate row `redis-from-scratch`, phase L, prereq L2 |
| `git` | 7 (init, cat-file, hash-object, write-tree, commit, clone) | 1 | **L4 `git-from-scratch`** (author) — this corpus is its thesis source |
| `shell` | 76 (base, history, completions, filename-completion, background-jobs, …) | 5 | overlaps **G7 `shell-from-scratch` (built)** and `bash-from-scratch/` (legacy) — completion/history axes are the only material G7 does not already own |
| `sqlite` | 9 (RDB-ish page format, btree, WAL) | 1 | **none** — overlaps H5's storage half |
| `kafka` | 25 (API versions, produce, consume, partitions, concurrent clients) | 1 | **none** — candidate row; J1 (`queue-and-workers`) is the natural prereq |
| `docker` | 6 (namespace/cgroup isolation) | 1 | **none** — needs Linux namespaces; J4 (`sandbox-capabilities`) is adjacent |

## How the stages map onto the house pattern

A CodeCrafters stage = one house stage: a mechanism, a protocol section, and
tests that run your program. What the house adds and what CodeCrafters cannot
give you:

- a **provided world** as data (deterministic byte-pipes instead of real
  sockets, an injected clock) so a run is a function of its inputs —
  see L3's `streams.py` for the pattern;
- a **contract** frozen before stage 1 (`.xx-dev/CONTRACT.md`);
- a **mutation battery** anchored to the solution's own text, and both
  directions of grading (template red, solution green);
- integer-only, no wall clock, no threads where the subject is the scheduler.

The per-stage "Tests" blocks convert mechanically into `check_NN.py` cases;
the stage order in each `stage_descriptions/` listing is the ladder order.
