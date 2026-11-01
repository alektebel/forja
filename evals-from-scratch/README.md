# Evals From Scratch

Build the harness that decides whether a text — or structured-extraction —
system got better, in pure standard-library Python: the split that must not
leak, the metrics that are not about quality, deterministic assertions, EM and
F1, ranking metrics, an LLM judge and its biases, judge calibration, paired
significance, multiple comparisons, the gate that runs in CI, field-level
extraction metrics, confidence ECE, and format sensitivity with criteria
identity.

A model that produces text has no `==`. Everything downstream of that — "is
this version better", "did that prompt change help", "can we ship this" — is a
measurement problem, and the measurement is where the bugs are cheap to write
and expensive to notice: a split that leaks, a refusal rate that counts
timeouts, a judge that prefers whichever answer was shown first, a "win" that
is three flipped examples, the best of ten configurations that is significant
only because nobody counted ten, a micro-F1 that hides a broken billing field,
an unweighted ECE that green-lights overconfidence, a mean across prompt
formats that hides a collapse on one separator. Thirteen stages, each one a
mistake that is easy to make and hard to see in the numbers.

No API keys, no model downloads, no network. The judge is a callable you pass
in, so the whole harness — including the LLM-judge stage — is synchronous,
offline and reproducible.

## The stages

| # | File | The mechanism | The thing people get wrong |
|---|---|---|---|
| 1 | `stage_01.py` | The eval set, group-wise splits | Splitting rows instead of sources: five phrasings of one ticket land on both sides |
| 2 | `stage_02.py` | Rates, percentiles, token totals | An errored row counted as a refusal; p95 as the mean of the top 5% |
| 3 | `stage_03.py` | Deterministic assertions, three states | `try/except: pass` around the loop, so a broken check reports 100% |
| 4 | `stage_04.py` | Exact match, token F1, corpus vs mean | Normalising the gold only; a set overlap that rewards a repeated word |
| 5 | `stage_05.py` | recall@k, MRR, DCG, nDCG | IDCG computed from the pool that was retrieved, which inflates the worst systems most |
| 6 | `stage_06.py` | The judge, judged twice | One order only: the prompt layout picks the winner |
| 7 | `stage_07.py` | Cohen's kappa, the F1-optimal cut | Reporting agreement. A judge that always says pass agrees with 85% |
| 8 | `stage_08.py` | McNemar, the paired bootstrap | A p-value instead of an interval; an interval that contains zero called a win |
| 9 | `stage_09.py` | Holm's step-down | Ten configs, no correction: the best of ten looks significant 40% of the time |
| 10 | `stage_10.py` | The regression gate and its report | The overall mean, which is exactly the number that hides the broken slice |
| 11 | `stage_11.py` | Structured fields: coerce, micro/macro, schema validity | `"100" != 100` without coerce; shipping micro while a rare field is always wrong |
| 12 | `stage_12.py` | ECE and the auto-approve threshold | Unweighted bin average; confidence `1.0` dropped off the last bin |
| 13 | `stage_13.py` | Format spread + criteria identity | Reporting only the mean across formats; comparing runs whose rubric drifted |

Stages 1–5 are the harness, 6–9 the statistics, 10 the ship/no-ship decision,
11–12 the structured-extraction product surface, 13 the validity of the
comparison itself. The checks exercise earlier stages (the gate pairs by id
and bootstraps with stage 8), so they are meant to be done in order.

## How to use this directory

```bash
python3 codecraft/cli.py run evals-from-scratch   # what to build next, and why
python3 codecraft/cli.py hint evals-from-scratch  # when a nudge is not enough
```

Or without codecraft:

```bash
python3 -c "import course; [print(i, s.title) for i, s in enumerate(course.STAGES, 1)]"
```

Implement the templates at the top level; finished versions are in `solutions/`.

## Prerequisites

Standard library only: `math`, `random`, `re`, `json`, `collections`. No numpy,
no scipy — `binom_two_sided` is exact integer arithmetic and the bootstrap is a
loop. The ranking metrics overlap with the retrieval courses; the statistics
need nothing beyond knowing what an interval is for. If you have never seen
Cohen's kappa or a bootstrap, stage 7 and 8 are where you meet them, and the
checks are what teach them.

## Design decisions

- **The judge is a function, not a service.** Every judge in this course is a
  callable that takes two answers and returns a side. That is what makes an LLM
  judge's bias measurable with a unit test, and it separates the two questions
  cleanly: is the judge biased (this course) versus is the model good (the
  judge is the only thing that can answer that, and only after stage 7).
- **Count, do not time.** No assertion depends on a wall clock. Where a timing
  would be natural (p95 latency) the check pins the arithmetic — nearest rank,
  the 19th of 20 samples — because a percentile is a request somebody actually
  made, not a smooth curve.
- **Three states, never two.** An assertion that raised is `errored`, not
  `failed` and not `passed`; a gate returns `pass`/`regress`/`inconclusive`. A
  harness that cannot say "I do not know" reports confidence it has not earned.
- **Pin the denominator in every rate.** Refusals over the rows that ran,
  latency over every row including the failures, tokens with a missing field
  counted as zero. Most metric bugs are not in the numerator.
- **Group-wise splits, and the leak is the point.** `split` shuffles groups, so
  near-duplicates cannot straddle the boundary; `overlap` makes the property
  assertable instead of hoped for.
- **Both aggregations of F1, deliberately.** `corpus_f1` pools the counts,
  `mean_f1` averages the per-pair scores, and they disagree (0.80 vs 0.83 on
  the check's fixture). Which one is right depends on whether a row or a token
  is the unit; shipping the wrong one is invisible without both.
- **The ideal ranking is over everything judged, not over what came back.**
  nDCG's denominator is the best ordering of all relevant keys in the
  relevance map. Deriving it from the retrieved pool returns 1.0 for a system
  that retrieved only mediocre documents — the stage's money assertion is
  `ndcg([...]) < 0.5` where the wrong version gives exactly 1.0.
- **Every pair is judged twice.** Position bias is a property of the prompt
  layout, so it is measured, not argued about: the flip rate is the number, and
  a judge with a content preference survives the swap with zero flips — which
  is how the two are told apart.
- **Paired, always paired.** The bootstrap resamples row indices and reads both
  systems at that index. The check measures the interval against the unpaired
  one on the same data and requires it to be strictly narrower, because that is
  the whole reason a few hundred rows can detect a real five-point win.
- **The family is decided before the p-values are read.** Holm's running
  maximum is what makes the adjusted values monotone and what the check pins
  (the fourth and fifth values of the worked example); Bonferroni is strictly
  weaker and is what gets written by accident.
- **A floor is not an average.** A candidate that gains ten points overall and
  drops one tenant below its floor is a regression, and the check's fixture is
  built so the interval itself says the candidate is better — the floor is the
  only thing that can stop it.
- **The report is part of the result.** Reasons, dropped-row counts and 4-decimal
  floats: a gate that returns a bare boolean cannot be reviewed, and a report
  that is not byte-stable makes a CI diff useless.
- **Four field statuses, not a boolean.** Missing and incorrect are different
  failures; extras are hallucinations that must hit precision. Micro pools
  cells; macro averages per field name — a rare billing field that is always
  wrong barely moves micro and tanks macro.
- **ECE is count-weighted.** Empty bins must not dilute miscalibration, and
  confidence `1.0` belongs in the last bin. The auto-approve cut maximises
  coverage under a precision floor; `None` means everything goes to review.
- **The mean across prompt formats is not the measurement.** The range and the
  worst format are. Criteria identity is part of comparability: a drifted
  rubric is not a delta, it is a different question.

## Sources (mapped to stages)

What this course implements, and what it deliberately leaves as reading.

| Area | Canonical pointer | Where it lands |
|---|---|---|
| Product evals | [Hamel — Your AI Product Needs Evals](https://hamel.dev/blog/posts/evals/), [Field Guide](https://hamel.dev/blog/posts/field-guide/) | Stages 1–3, 10–12 (error analysis → gate → fields/confidence) |
| Criteria drift | [Shankar et al., EvalGen](https://arxiv.org/abs/2404.12272) | Stage 13 `criteria_id` / `comparable` |
| LLM-as-judge practice | [Eugene Yan — LLM-evaluators](https://eugeneyan.com/writing/llm-evaluators/) | Stages 6–7 |
| Position bias | [Wang et al.](https://arxiv.org/abs/2305.17926); [Zheng et al., MT-Bench](https://arxiv.org/abs/2306.05685) | Stage 6 (judge both orders) |
| Error bars on evals | [Evan Miller](https://arxiv.org/abs/2411.00640) | Stage 8 (paired bootstrap / intervals) |
| Format sensitivity | [Sclar et al.](https://arxiv.org/abs/2310.11324) | Stage 13 `format_spread` |
| Construct validity | [Bean et al., Measuring What Matters](https://arxiv.org/abs/2511.04703); [checklist](https://syntheticsociety.oii.ox.ac.uk/research/measuring-what-matters) | Reading — checklist for whether your metric measures the claim |
| HELM / broad eval | [Liang et al.](https://arxiv.org/abs/2211.09110) | Reading — taxonomy of scenarios; not re-implemented |
| Contamination survey | [Cheng et al.](https://arxiv.org/abs/2502.14425) | Reading — stage 1 covers *group* leakage; train-set contamination is adjacent |
| tinyBenchmarks (IRT) | [Polo et al.](https://arxiv.org/abs/2402.14992) | Out of scope — adaptive item selection |
| Long-task ability | [METR blog](https://metr.org/blog/2025-03-19-measuring-ai-ability-to-complete-long-tasks/) / [paper](https://arxiv.org/abs/2503.14499) | Out of scope — horizon metrics |
| Harness tooling | [Inspect](https://inspect.aisi.org.uk/), [lm-eval-harness](https://github.com/EleutherAI/lm-evaluation-harness) | `eval-framework-from-scratch` — the runner, not the metrics |
| Course (paid) | [Hamel & Shankar, Maven](https://maven.com/parlance-labs/evals) | Curriculum depth behind stages 1–10 |

## Verification

The solutions pass all thirteen checks. Stages 1–10 stay mutation-pinned as
before (34 planted wrong implementations). Stages 11–13 pin the classic
mistakes in the assertion messages themselves: string/float equality without
coerce, micro that hides a broken rare field, unweighted ECE, `1.0` dropped
from the last bin, a mean that hides a format collapse, criteria compared
without an id.

Running a check by hand:

```bash
python3 codecraft/cli.py run evals-from-scratch   # per stage, with the failure line
```

## Where this stops

Deliberately left out, so you know the boundary:

- **No model calls.** The judge is a function, so nothing here measures how good
  a real judge is — the calibration apparatus in stage 7 is what tells you, and
  it needs human labels you have to collect.
- **Fixed-sample statistics.** No sequential testing, no always-valid intervals,
  no early stopping. Those change the p-value you are allowed to quote, and
  they are a separate course.
- **Holm only.** Benjamini-Hochberg's FDR control is the next correction and it
  answers a different question (proportion of false discoveries, not any false
  discovery); the structure of stage 9 is where it would slot in.
- **No online experiment design.** Mirrored traffic, interleaving,
  counterbalancing and the choice of unit of randomisation are the A/B course's
  subject; this one starts from the two runs already collected.
- **Near-duplicate detection is the group key you supply.** `split` keeps a
  declared group together; finding the near-duplicates (minhash, embeddings,
  a template signature) is the retrieval course's problem.
- **Text metrics are lexical.** No embeddings, no learned metrics, no
  semantic similarity — stage 4 is the baseline those have to beat, and the
  reason they need a judge at all.
- **No citation/span geometry.** Field correctness is value-level; "cited to
  the right page box" is a separate geometric metric a document product needs
  on top of stage 11.
- **No IRT / adaptive benchmarking, no contamination detectors, no long-horizon
  task metrics.** See the sources table — they are real, and they are not this
  course.
- **No eval runner.** Suites, caching, resume and plugin metrics live in
  `eval-framework-from-scratch` (Inspect / lm-eval shaped).
