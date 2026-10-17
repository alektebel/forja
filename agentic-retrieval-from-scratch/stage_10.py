"""Agentic Retrieval From Scratch — stage 10: Which stage failed, and whether the checker beat the baseline.

Nine stages of a pipeline that checks itself, and this one holds the whole thing
against the only two records that are not the course's own. The customer's old
pipeline failed on twelve questions and left a row for each one: the chunk ids
it produced for the document, the hits it ranked, how many it kept, what it
cited, whether its answer was right — and, in the last field, the customer's own
verdict about which stage failed. That last field is the whole temptation of a
debugger. A row that already says *chunk* lets `diagnose` agree with the customer
every time by reading the answer off the answer, and a debugger that agrees with
a label it was handed has checked nothing at all.

So this stage never reads it. `diagnose` decides from the evidence, in the
pipeline's own order, and the first thing true of a row is its verdict: an
answer that was right failed nowhere; a document whose clause index holds
clauses the failure's chunks lacks failed in the chunker; a question stage 5
would itself call ambiguous whose expected clauses all failed to come back
failed in the rewriter; an expected clause that never came back failed in
retrieval; one that came back below the kept line failed in the reranker; one
that was kept and never cited failed in grounding; and everything else is the
answer itself. Only `agreement` reads the customer's label, and what it answers
is a number: how many diagnoses the customer's own record confirms, and which of
them it does not.

The other half of the stage is the checker's own report, and it is a number
rather than a mood. `eval_checker` runs the checked loop over the customer's
questions with the naive retrieval beside it: how many questions came back with
an answer, how much of what the questions expected those answers actually cited,
how much of what they cited was never expected at all, which abstentions were
right because the pipeline could not have answered, and what the whole
evaluation cost on the meter it was handed. The verdict is held against the
naive baseline and behind a sample floor, because a difference of a few hundred
basis points over four answers is not evidence of anything.

    DIAGNOSIS_KEYS               the three fields of a diagnosis, in order
    FAILURE_STAGES               the closed vocabulary a diagnosis is spelled in
    EVAL_KEYS                    the six fields of the checker's report, in order
    EVAL_MIN_SAMPLE              how many answers a verdict has to stand on
    EVAL_MIN_GAIN_BP             how many basis points of coverage it has to be
    diagnose(corpus, failure)    -> DIAGNOSIS_KEYS, from the evidence alone
    distribution(diagnoses)      -> the counts, the fids by stage and the worst
    agreement(diagnoses, corpus) -> how many the customer's own labels confirm
    eval_checker(index, corpus, questions, meter, limit, budget_cents, round_cap)
                                 -> EVAL_KEYS, the checker's report and its verdict

DESIGN DECISION — why does the debugger read the evidence instead of the label?
Because the label is the thing being checked. The customer's twelve rows carry
their own verdict, and a debugger that answered with it would agree with the
customer every time and in every case, which is exactly what makes it worthless:
the label is ground truth, and holding a rule against ground truth is the only
way to learn whether the rule is right. Reading it would also throw away the
reason — which clause was dropped, which expected id never came back, at which
rank it came back — and the reason is the whole product of a debugger. The label
is read in one place and one place only, `agreement`, and there it is compared
with rather than obeyed.

DESIGN DECISION — why does the tree decide by first match rather than by
weighing the evidence?
Because the pipeline is a sequence and the faults are nested rather than
independent. A clause the chunker never produced cannot be retrieved, cannot be
reranked and cannot be cited; a clause that was never retrieved cannot be
reranked either. The evidence in one row is therefore true of several stages at
once, and the only honest verdict is the earliest stage that could have
caused what the row shows. `FAILURE_STAGES` is ordered the way the pipeline
runs — chunk, rewrite, retrieve, rerank, ground, answer — so the tree walks the
evidence in the order the customer's own pipeline walks a question, and the
first thing true of the row is its answer. The one branch that is not read off
the row's raw fields is `rewrite`, and it is not this stage's opinion either: it
is stage 5's own `ambiguous`, asked about the customer's own question, so the
debugger and the rewriter cannot disagree about whether a question was ambiguous
in the first place.

DESIGN DECISION — why is `none` in the vocabulary at all?
Because a labelled failure set is not a set of failures. A row can sit in the
customer's file with an answer that was right — the pipeline got there the hard
way, or the question was re-asked later — and the honest verdict for it is that
no stage failed. It is the first branch of the tree and it short-circuits: there
is nothing to diagnose in a row whose answer was right, so the debugger never
asks the library anything about it, and a debugger that did would be a debugger
that reads a document's whole clause index to decide that nothing is wrong.
`none` is a verdict and never a failing stage, which is why `distribution`
reports it in the counts and never in `worst`.

DESIGN DECISION — why does the worst stage break ties in the vocabulary's own
order?
Because "which stage failed most" stops being a question with one answer the
moment two stages fail equally often, and the answer has to be a function of the
run rather than of how a dictionary happened to be built. `FAILURE_STAGES` is
already ordered by the pipeline, so the earliest stage of the tie wins: the
faults are nested, so the earlier stage is the one that caused the later one,
and a reader who re-runs the report gets the same name for the same row set.
A stage with no failures at all is still the answer when every count is zero —
the tie is total, and the vocabulary's order settles it — and `none` never
enters the comparison, however many rows it accounts for, because a stage that
did not fail is not an answer to "which stage failed".

DESIGN DECISION — why does the checker's verdict sit behind a sample floor?
Because a coverage difference in basis points is only as good as the number of
answers standing under it. A pipeline that answers one question perfectly and
abstains on fifteen has a coverage of ten thousand basis points and has told the
customer nothing about whether checking itself was worth it. `EVAL_MIN_SAMPLE`
is that floor and `EVAL_MIN_GAIN_BP` is the same noise bound the reranker and
the cost comparison already use, so the checker cannot bless a pipeline on a
difference the rest of the course would call noise — and it cannot call that
pipeline better than the naive one either, since beating the baseline is a claim
about answers and not about a ratio.

TODO: implement `diagnose`, `distribution`, `agreement` and `eval_checker` in
this file: the first-match diagnosis tree over the customer's own evidence and
never over their label, the distribution that names the worst failing stage,
the agreement that holds the two records against each other, and the checker's
own report with its verdict against the naive baseline.
"""

import corpus
import meter
import stage_03
import stage_05
import stage_08

DIAGNOSIS_KEYS = ("fid", "stage", "reason")

FAILURE_STAGES = ("chunk", "rewrite", "retrieve", "rerank", "ground", "answer",
                  "none")

EVAL_KEYS = ("answered", "hit_bp", "unsupported_bp", "abstained_correctly",
             "cost_cents", "verdict")

EVAL_MIN_SAMPLE = 4

EVAL_MIN_GAIN_BP = 400


def diagnose(corpus, failure):
    """The DIAGNOSIS_KEYS row a failure's own evidence implies, never its label.

    The tree, in order: an answer that was right is `none`; a document whose
    clause index holds clauses the failure's chunks lacks is `chunk`; a question
    stage 5's own `ambiguous` calls ambiguous with none of its expected ids
    retrieved is `rewrite`; an expected id missing from the failure's retrieved
    hits is `retrieve`; one that came back at an index at or past `kept` is
    `rerank`; one that was kept and never cited is `ground`; and anything else
    is `answer`. The reason names the offender — the count, the chunk id, the
    rewrite kind, or the rank and the kept line.
    """
    raise NotImplementedError("stage 10: implement diagnose()")


def distribution(diagnoses):
    """The counts, the fids by stage and the worst failing stage.

    The counts hold every stage in `FAILURE_STAGES`, zeros included; `by_stage`
    maps each of them to a sorted tuple of fids; `worst` is the non-`none` stage
    with the most failures, ties broken by `FAILURE_STAGES` order.
    """
    raise NotImplementedError("stage 10: implement distribution()")


def agreement(diagnoses, corpus):
    """How many of these diagnoses the customer's own labels confirm.

    `agree` the count, `disagree` a sorted tuple of the fids that differ, and
    `bp` the share in basis points over the diagnoses given.
    """
    raise NotImplementedError("stage 10: implement agreement()")


def eval_checker(index, corpus, questions, meter, limit, budget_cents, round_cap):
    """The checker's own report, and its verdict against the naive baseline.

    Runs the checked loop over the questions and the naive hybrid retrieval
    beside it: EVAL_KEYS with `answered` the non-abstaining answers, `hit_bp`
    the share of the questions' expected ids the answers cited,
    `unsupported_bp` the share of citations that were not expected,
    `abstained_correctly` the abstentions on questions whose expected ids were
    not all retrieved, `cost_cents` the meter's own delta, and `verdict` one of
    `beat-baseline`, `no-better` or `worse`.
    """
    raise NotImplementedError("stage 10: implement eval_checker()")
