# Agentic Retrieval From Scratch

Ten graded stages between a customer's contract library and an answer that can defend
itself. The pipeline this course builds is the one that argues with its own results: it
chunks a document the way the document is written rather than the way a text splitter
finds it convenient, it plans an index for a corpus of ten million documents and refuses
the plan it cannot pay for, it scores with two different scorers and picks between them
with the customer's own labelled questions, it reranks and then proves the reranker
earned its place, it rewrites a question that was ambiguous and writes down what it
changed, it critiques what came back and names the stale, conflicting, unresolvable or
off-topic chunk, it answers with claims tied to spans or abstains with a reason, it loops
inside a budget it never exceeds and never retries a query it already tried, it prices
all of that against the naive retrieve-and-answer it replaced, and it diagnoses the
customer's own failures, stage by stage, agreeing with the person who filed them.

**The thesis, asserted by every stage's check:** *retrieval that checks itself is a
pipeline of small, named verdicts — a chunk that can be cited, a rank that can be
justified, a question that was made unambiguous, a critique that names the offender, an
abstention that says why, and a cost held against the naive baseline rather than
asserted.*

That is the difference between a demo and a system a customer keeps. A demo retrieves
something plausible and a person decides whether to believe it; a system says *which*
clause it quoted, *why* that clause outranked the other four, that the question it was
asked was ambiguous and what it made of it, that one of the clauses it found had been
superseded by a later version, that it will not answer at all rather than answer from a
clause it cannot cite, and what the whole thing cost compared with doing it the naive
way. Every one of those statements is a data structure in this course, and every one of
them is held against the customer's own records rather than against the pipeline's
belief about itself.

## What is not here

There is no model. No weights, no inference server, no prompt, no sampling, no
temperature, no tokenizer, no attention and no GPU — the "generation" this course
answers with is a quote of a clause the pipeline already retrieved, because the part of
agentic retrieval that can be *built and checked offline* is the part that decides:
what a chunk is, what a rank means, what makes a question ambiguous, what makes a clause
unusable, what makes an answer grounded, when to stop, what it cost, and which stage
failed. A course that simulated a model would grade the model's API instead of those
decisions.

There is no network, no filesystem, no clock, no randomness and no threads: the corpus
is an object in the same process, the meter is a ledger of what was charged, a budget is
a cent count the caller supplied, and every check runs its own work twice and asserts the
two runs are equal. There is not one `float` literal anywhere in the templates, the
solutions or the checks: a length is an `int`, a rank is an `int`, a similarity is an
`int` dot product, a ratio is **basis points**, and the two fixed points this course needs
(`BM25_K1_BP = 120` for `k1 = 1.2`, `RRF_K = 60` for the rank constant) are written out
as integers with their divisions pinned. `math` is banned along with the rest of the
usual list, which is why the world hands back a unit-scaled vector and an inverse
document frequency: there is no square root and no logarithm to write.

## The provided world

Two modules, frozen before stage 1 and pinned by sha256, never written by the course:
they are the customer's own library and the customer's own meter.

| Module | What it is |
|---|---|
| `corpus.py` | The contract library: `Corpus.build(seed)` with `documents`, `document`, `clause_index`, `subjects`, `terms`, `idf`, `embed`, `questions`, `glossary`, `failures`, `log`, `stats`; `SCALE`, `VECTOR_DIM`, `VECTOR_SCALE`, `DOCUMENT_KEYS`, `QUESTION_KEYS`, `TURN_KEYS`, `FAILURE_KEYS`, `CORPUS_ERROR`, `CorpusError` |
| `meter.py` | What a decision costs: `Meter()` with `charge`, `charges`, `total_cents`, `total_ticks`, `by_kind`, `log`, `reset`, `stats`; `PRICE_CENTS`, `COST_KEYS`, `METER_ERROR`, `MeterError` |

Four things about the world are worth reading before the stages, because they are the
course's whole idea of ground truth:

- **The clause index is the record.** `clause_index(doc)` is what the customer's document
  management system says the clauses *are*, in document order — including a clause number
  the document uses twice and a number it skips. The chunker is held against it, not
  against a second parser the course also wrote, so "my chunker found nine clauses" is not
  a claim that can survive being checked.
- **The questions are the labels.** `questions` carries, for each question, the chunk ids
  an answer must cite, the conversation that preceded it (when there was one) and the
  question's own text. Every measurement in the course — which scorer wins, whether the
  reranker earned its place, whether checking yourself was worth it, whether the checker
  beat the baseline — is computed against that set and not against a belief about
  embeddings.
- **The failure log is the diagnosis.** `failures` holds what the customer's old pipeline
  produced, the chunks it produced them from, what it cited, whether the answer was right
  and the stage the customer themselves decided had failed. The `stage` field is the
  answer key: stage 10 must reproduce it from the evidence and may never read it, and the
  check pins that the debugger agrees with the customer on **every** row.
- **`SCALE` is the estate.** Ten million documents, a hundred and forty million clauses
  and two hundred and fifty thousand distinct terms are the numbers stage 2 plans
  against: an index is a decision about what to hold in memory, what to scan and what to
  pay, and the check recomputes every number the plan claims.

## The stages

| # | File | The stage | The mechanism |
|---|---|---|---|
| 1 | `stage_01.py` | The clause, the cross-reference and the chunk that cites itself | `CHUNK_KEYS`, `PARSE_PROBLEMS`, `LEVELS`, `chunk`, `problems_of`, `chunk_id`, `resolve`, `definitions`, `refs_of`, `outline` |
| 2 | `stage_02.py` | Ten million documents, and the index that is a decision | `LAYOUTS`, `PLAN_PROBLEMS`, `PLAN_KEYS`, `POSTING_BYTES`, `TERM_BYTES`, `VECTOR_BYTES`, `BYTES_PER_MB`, `POSTINGS_PER_CLAUSE`, `SCAN_BUDGET_BP`, `MAX_SHARDS`, `INDEX_CENTS_PER_MILLION_POSTINGS`, `QUERY_CENTS_PER_MILLION_SCANNED`, `weigh`, `bytes_of`, `scan_of`, `plan`, `explain` |
| 3 | `stage_03.py` | Two scorers, and the fusion that has to beat both | `HIT_KEYS`, `MEASURE_KEYS`, `SEARCH_MODES`, `BM25_K1_BP`, `BM25_B_BP`, `RRF_K`, `SCORE_SCALE`, `NO_DIFFERENCE_BP`, `Index` (`build`, `chunks`, `of`, `lexical`, `dense`, `fused`, `analysis`), `bm25`, `dense`, `fuse`, `search`, `measure`, `pick` |
| 4 | `stage_04.py` | The reranker that must earn its place | `RERANK_KEYS`, `COMPARE_KEYS`, `COVERAGE_WEIGHT`, `PROXIMITY_WEIGHT`, `WEIGHT_TOTAL`, `PROXIMITY_WINDOW`, `LEVEL_BONUS_BP`, `NOISE_BP`, `rerank`, `compare`, `keep` |
| 5 | `stage_05.py` | The ambiguous question, rewritten and recorded | `REWRITE_KEYS`, `REWRITE_KINDS`, `PRONOUNS`, `REFERENT_STOP`, `QUESTION_STOP`, `MIN_INTERROGATIVE_TERMS`, `SUBSET_WORDS`, `ambiguous`, `rewrite`, `decompose` |
| 6 | `stage_06.py` | The critique of what came back | `CRITIQUE_KEYS`, `CRITIQUE_VERDICTS`, `VERDICT_ORDER`, `critique`, `survivors`, `by_verdict` |
| 7 | `stage_07.py` | Grounded or abstain, and never a claim without a citation | `CLAIM_KEYS`, `ANSWER_KEYS`, `ABSTENTIONS`, `CITATION_PROBLEMS`, `GROUNDING_MIN_BP`, `grounding_bp`, `answer`, `check_citations` |
| 8 | `stage_08.py` | The loop that must terminate, priced every round | `ROUND_KEYS`, `LOOP_KEYS`, `STOPS`, `RETRIEVE_UNITS`, `RERANK_UNITS`, `CRITIQUE_UNITS`, `GENERATE_UNITS`, `DEFAULT_LIMIT`, `ask`, `rounds_of` |
| 9 | `stage_09.py` | What the checking cost, against the naive answer | `BASELINE_KEYS`, `ROLLUP_KEYS`, `MIN_WORTH_IT_GAIN_BP`, `price`, `rollup`, `where_it_lost`, `worth_it` |
| 10 | `stage_10.py` | Which stage failed, and whether the checker beat the baseline | `DIAGNOSIS_KEYS`, `FAILURE_STAGES`, `EVAL_KEYS`, `EVAL_MIN_SAMPLE`, `EVAL_MIN_GAIN_BP`, `diagnose`, `distribution`, `agreement`, `eval_checker` |

The order is a ladder and the ladder only points one way: stage 3 owns the `Index` that
stages 4, 6, 7, 8, 9 and 10 take as an argument; stage 1 owns the chunk that everything
else speaks in; stage 5 owns the rewrite that stage 8's loop performs; stage 6 owns the
critique that stage 7 turns into claims; stage 8 owns the loop stage 9 prices; and stage
10 reads the customer's failures and holds the whole course against them. A stage imports
the world and the **earlier** stages it needs, and never a later one.

## How to use this directory

```
python3 codecraft/cli.py run agentic-retrieval-from-scratch     # from the repository root
python3 codecraft/cli.py stage agentic-retrieval-from-scratch 4
python3 codecraft/cli.py hint agentic-retrieval-from-scratch
```

Each stage is a template you fill in: `stage_NN.py` declares the names the stage's
surface needs, with a docstring and a `raise NotImplementedError("stage NN: implement
…")` for each, and the stage's check (`check_NN.py`, assembled into `course.py`) refuses
your file until it behaves the way the contract says. `solutions/` holds a working
implementation of every stage — a check that passes on the solution and fails on the
untouched template is the only evidence this repository accepts that a stage is written,
and that is what `solutions/` is for: to be *read* after you have tried, or when you are
stuck, never instead of trying.

The stage's own questions are in the template: `predict` in the manifest is what you
should be able to answer before you run anything, and the prose above the surface block
is the decision the stage exists because of — the surface block is what to write, the
`DESIGN DECISION` blocks are what to argue with.

## Prerequisites

Read this course after four of its neighbours, because it assumes their mechanics and
grades only the new decisions on top of them:

- **B1 `rag-from-scratch`** — chunking, embedding, retrieval and the shape of an answer.
  This course's stage 1 is where the chunk stops being a fixed-size window and starts
  being a clause that can be cited.
- **B2 `vector-index-from-scratch`** — an index, its memory and its search. Stage 2 is
  the capacity decision that course's machinery makes possible, and stage 3's dense
  scorer is a similarity over vectors you have already built once.
- **C2 `agents-from-scratch`** — a loop with a budget, a policy and an approval gate.
  Stage 8 is that loop pointed at retrieval: it must terminate, it must not repeat
  itself, and its budget is checked before the call rather than after.
- **C1 `evals-from-scratch`** — a labelled set, a metric and a gate that refuses to pass
  what it cannot evaluate. Stages 9 and 10 are where the metric is the customer's own
  questions and the gate is a comparison against the naive baseline.

Nothing else is assumed: the world is provided, and the course never imports another
course's code.

## Design decisions

The choices this course made, and why — the same ones its stages make you make:

- **The customer's clause index is the ground truth for what a clause is.** A second
  parser written by the course would agree with the course by construction; the record is
  what an auditor asks for, and it does not care how elegant your splitter is.
- **A chunk id is `doc:clause`, and a citation is that string.** The corpus keeps a
  duplicated clause number on purpose, so an id can be ambiguous — and the stage that
  answers has to notice, because a citation to an ambiguous id is not a citation.
- **A plan that cannot pay is returned, not raised.** A shape that cannot be the thing at
  all raises; a capacity decision about the customer's estate is data, with the offending
  number in it, because the whole job is deciding.
- **Fixed point everywhere, and no `math`.** BM25 is written with `BM25_K1_BP = 120` and
  `BM25_B_BP = 75` and a pinned division order; the rank fusion is `10000 // (60 + rank)`;
  and the embedding is unit-scaled by the world, so a similarity is a dot product with no
  square root anywhere. The arithmetic is boring on purpose: a score you cannot recompute
  by hand is a score nobody can defend.
- **Every score is its own explanation.** `why` holds the terms and the values that
  produced the score, and the check asserts the sum; a rank that cannot be justified to a
  customer is a rank that will be argued about rather than trusted.
- **Two scorers are fused by rank, not by score.** A BM25 score and a dot product are not
  the same unit, so fusion is reciprocal rank — and which of the three modes wins is
  decided by the customer's labelled questions, with a stated bound below which the
  difference is not a difference.
- **A reranker is removed unless it beats that bound.** Adding one is not evidence; the
  stage's output *is* the verdict, and `keep` is a word rather than a feeling.
- **Ambiguity is resolved and recorded.** The referent of a pronoun comes from the
  conversation and not from the question (which does not name it — that is what makes it
  ambiguous), the acronym is expanded *and kept*, and every fix carries `before`, `after`
  and why, so a wrong rewrite can be argued with instead of guessed at.
- **The critique has a precedence, and a conflict is a shared subject with different
  text.** Staleness first (a superseded document is not usable no matter how relevant),
  then an unresolvable reference, then a conflict, then topicality — and the conflict is
  decided by the corpus's own subject tags rather than by a similarity threshold nobody
  can defend.
- **The answer quotes; it does not synthesize.** Claims are spans of the chunks that
  survived, which is what makes grounding a number the pipeline can compute about itself
  offline — and what makes "never a claim without a citation" a property rather than a
  promise.
- **The naive pipeline is defined and measured, not waved at.** It retrieves the fused
  top five and answers from all of it, so its answered count is every question by
  construction: the comparison is deliberately unfair in the naive direction, because
  that is the baseline a customer actually has.
- **The budget is checked before the call, and a round's price is the meter's own
  number.** The course never believes its own arithmetic about money: `Meter` is the
  ledger, and the check diffs it.

## How this course is verified

The contract was written before the first stage (`../.k1-dev/CONTRACT.md`: the ten
surfaces, the eleven laws, the provided world's shapes and every answer's keys), and
then the course was built against it and measured:

| What | Command | Result |
|---|---|---|
| The provided world, pinned | `.k1-dev/verify_provided.py` | `PROVIDED: 102, PROBLEMS: 0` — `corpus.py` `sha256 04009cad…`, `meter.py` `sha256 ef04c856…` |
| Every stage's own check | `.k1-dev/run_all.py` | ten stages `PASS`; `smoke.py` proves each of the ten checks **fails** on the untouched template |
| The planted mistakes | `.k1-dev/mutate_all.py` | **589 mutations, 589 caught**, 0 missed, 0 broken |
| The assembled course | `.k1-dev/assemble.py`, `run_assembled.py` | `course.py`, 5,442 lines, compiles; the ten solutions overlaid on the ten templates: 10/10 |
| The house laws | `.k1-dev/audit_course.py` | `AUDITED: 10, PROBLEMS: 0` — the first docstring paragraph, no float literal, no banned import, the ladder (no stage imports a later one), and every public name the template declares declared by the solution |
| A second, independent reading | `.k1-dev/probe_stages.py` | `PROBED: 911, PROBLEMS: 0` — the parent's own probe, which never imports a stage's check and recomputes the arithmetic (the estate's bytes, the fusion's ranks, the meter's cents) itself |
| How much each stage tests you | `codecraft/stats.py` | **893** testers over the ten stages: 74, 104, 93, 95, 91, 84, 75, 82, 94, 101 |

Per stage, the mutations the check was proved to catch: 50, 64, 58, 56, 57, 51, 52,
56, 57, 88. Run any of it yourself:

```sh
python3 codecraft/cli.py run agentic-retrieval-from-scratch     # from the repository root
```

## Where this stops

- **No model, and no prompting.** The "generation" is a quote of a retrieved clause; there
  is no tokenizer, no context window, no sampling and no judge. The labels are the
  customer's, which is exactly why they can be used as ground truth.
- **No real embeddings.** `corpus.embed` is a deterministic signed hash into 32 dimensions
  with an exact integer norm — it is a *vector* and it is stable, but it is not a semantic
  space, and the course never pretends that a dense hit is a meaningful one. What it does
  pretend, correctly, is that a similarity can be compared, ordered, fused and priced
  without a float.
- **No ANN index.** Building one is `vector-index-from-scratch`'s (B2) job; here the index
  is exact and in memory, because what this course grades is *which* index to hold and
  what it costs, not how to approximate a nearest neighbour.
- **No reranker model.** The reranker's signals are lexical — coverage, proximity, a level
  bonus — because the stage's subject is whether it earned its place, not what a
  cross-encoder would say.
- **No HTTP, no vector database, no LangChain, no framework.** Nothing here opens a
  socket, reads a file, starts a process or reads a clock, and the corpus and the meter
  are objects in the same process, which is what makes every number reproducible.
- **No performance work.** Ticks and cents are counts the world charges, not measurements
  of a machine; latency, throughput and tokens per second are not this course's units.

## Where this sits

This is phase K's first slot, *Applied AI engineering*, and it is the retrieval that
argues with itself: B1 `rag-from-scratch` builds the retriever and C1 `evals-from-scratch`
builds the harness that grades an answer, and this course is the pipeline in between that
decides whether it *may* answer, decided by the customer's own labels. B2
`vector-index-from-scratch` is the index underneath it, C2 `agents-from-scratch` is the
loop it fills in with a budget, and F2 `eval-framework-from-scratch` is the gate at the
end of the line. The other side of the same coin is K2 `prompt-ops-from-scratch` (a prompt
and a model choice as versioned artifacts, with shadow mode and a degradation chain) and
K6 `fde-from-scratch` (the same decisions deployed at a customer who will not read the
source: identity, an air gap, dirty invoices, a GPU somebody else owns, an ROI
conversation and a handoff).

The material it comes from is `AI-ENGINEER.md`'s phase-K row: interview problems **#1**
(design a RAG for 10M documents), **#2** (your RAG gives wrong answers — debug it), **#3**
(chunking for legal contracts), **#4** (BM25 vs dense vs hybrid), **#5** (add a reranker
and measure whether it helped) and **#14** (detect and reduce hallucinations), plus build
**5** — *self-correcting agentic RAG: an agent that critiques its own search results,
rewrites ambiguous queries and confidently abstains when grounding is weak* — with nothing
cut for being hard to grade offline.
