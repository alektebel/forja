# Git From Scratch

Build a repository's object store — in pure standard-library Python, with no
floats, no clock, and no threads, and with real `git` as the judge.

A `.git` directory is the one artefact in this repository that another program
validates: every object, tree, commit, index record and pack this course
writes, real git has to read back. The store is provided as data (`repo.py` —
a byte-oriented virtual filesystem, the object store, `EXPORT`; `objects.py`
— the object grammar's provided half, zlib and SHA-1 through one door;
`worktree.py` — the fixture, including a packfile real git built). The
version control on top of it is what you write.

A layout that is a repository only once HEAD makes its promise; a blob whose
name is its content's digest; a tree whose entries sort the way git sorts and
whose modes are exact; a commit whose line is frozen once written; an index
whose record git's own `ls-files --stage` reads back; a log walked through
parents and refusing the cycle a corrupted store can hide; a packfile
unpacked down to the deltas real git chose; and the proof — the exported
repository handed to `git fsck --strict`, whose clean answer is the only
verdict that matters, because compatibility has exactly one authority.

No `open(2)` behind the store, no subprocess in a stage: the real filesystem
is the check's business, and a stage never calls git itself — the judge is
the check's, never the student's. The fixture's shas are law (`KNOWN_BLOBS`
carries real git's own names), so every stage's answer has a ground truth
that was never computed by this course.

## The ten stages

| N | File | Title |
|---|---|---|
| 1 | `stage_01.py` | The repository: a `.git` is a layout, and HEAD is a promise |
| 2 | `stage_02.py` | The blob, read: a header, then its body |
| 3 | `stage_03.py` | The blob, written: the hash is the content's name |
| 4 | `stage_04.py` | The tree, read: sorted entries with modes |
| 5 | `stage_05.py` | The tree, written: the whole working tree, bottom-up |
| 6 | `stage_06.py` | The commit: a tree, a parent, and a frozen line |
| 7 | `stage_07.py` | The index: staging is a record, not a copy |
| 8 | `stage_08.py` | The log: history is parents, walked and verified |
| 9 | `stage_09.py` | The packfile: many objects, one file, deltas to apply |
| 10 | `stage_10.py` | The proof: real git opens what you wrote |

Stage 10 is the capstone: the ladder end to end on a fresh repository, then
the exported store under `git fsck` and `git log`.

## Measured verification

| What | Command | Result |
|---|---|---|
| the stages | `python3 .l4-dev/check_NN.py` (1..10) | ten `PASS`, and ten exits 2 against the templates |
| the mutations | `python3 .l4-dev/mutate_all.py` | `TOTAL 67/67`, `MISSED OR BROKEN: 0` |
| the ladder and the laws | `python3 .l4-dev/audit_course.py` | `AUDITED: 10, PROBLEMS: 0` |
| the whole course as one module | `python3 .l4-dev/smoke.py`, `run_assembled.py` | `SMOKE: PASS`, `ASSEMBLED: 10/10` |
| the tests the course ships | `python3 .l4-dev/count_tests.py git-from-scratch` | 142, per stage `[12, 11, 9, 11, 10, 16, 19, 16, 20, 18]` |
| the judge | stage 10's `verify` | `git fsck --strict` clean, `git log` walks the two fixture commits |

Proven against real git, byte for byte: `KNOWN_BLOBS`' hashes, the fixture
tree (`dc8f37d5…`), the fixture commit (`1f484a9e…`), the index read by `git
ls-files --stage`, all nine pack objects via sha after delta application, and
`fsck` clean on the final exported repository.

The provided world is pinned by digest:

| File | sha256 |
|---|---|
| `repo.py` | `447b7c0f6cd0d617cb34dfe1166f1019eda4e54d22d568574122f1a7e5190b13` |
| `objects.py` | `260e11ed4baf82f60435aad702b1bee6897e0b78a4a38771521512475f9d281e` |
| `worktree.py` | `2da00cd74d79296e066ae6b870c8442aa3e6bedcc923b024927c07e99302934b` |

## The laws a stage is held to

- Standard library only; no `open(`, no module-level mutable state; constants
  are tuples, strings and ints. Every filesystem touch goes through the
  provided `Fs`; `zlib` and `hashlib` come through `objects.py`.
- A stage imports the world and earlier stages only, never a later one — and
  never calls `git`: the judge is the check's. (Stage 10's solution alone
  holds the judge — the contract's §7 amendment.)
- The world is never edited to make a stage pass; the three digests are
  pinned, and the fixture's names are real git's.
- A caller's mistake raises (`GitError`), naming the offender; the walk
  refuses a cycle rather than truncating history.
- The first docstring paragraph is the stage's own title line, every public
  function is a docstring plus exactly one `raise NotImplementedError`, and
  the file carries its `DESIGN DECISION` blocks and a `TODO: implement` line.

## Running it

    python3 codecraft/cli.py run git-from-scratch

The ten stages are graded in order; the later ones compose the earlier ones
(that is what the ladder law is for), and stage 7's index is what stage 8's
walk verifies, stage 9's pack packs, and stage 10's proof proves.
