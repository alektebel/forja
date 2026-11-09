# S3 learning pilot

Stages 9–12 of AWS From Scratch test a small learning loop in the browser workspace.
The stage checker still decides whether code passes. Questions never change PASS.

## Evidence

The browser keeps three separate event kinds in `forja.learning.events.v1`:

- `run`: checker status, detail, a fingerprint of the stage file, and hints used.
- `concept`: selected answer, correctness, and optional learner reasoning.
- `practice`: a later transfer answer with the same fields.

Draft code and passed stage IDs remain under their existing browser keys. These
records stay in that browser and are not synchronized with the CLI profile or
other devices. The event list is bounded; it is a pilot record, not a permanent
assessment of mastery.

## Learner flow

1. Open a stage and edit immediately. The idea check is optional.
2. After a run, the helper identifies an unfinished target, an unchanged rerun,
   or the exact case and concept to inspect. A failed assertion offers the
   relevant idea check. Python syntax errors stay code errors.
3. Once a stage passes, a different transfer case becomes available after a
   later S3 stage has passed and the learner reaches stage `N+2`, or one day
   after the pass. An incorrect recall answer waits a day before reappearing.

The questions and feedback live beside each stage in `aws-from-scratch/lessons.json`.
`learning.js` contains the inspectable selection and scheduling rules. No model
call or provider key is needed by the public static site.

## Verify

```bash
node --test codecraft/web/learning.test.cjs
python3 aws-from-scratch/validate_course.py
python3 scripts/forja_site.py /tmp/forja-learning-pilot
```
