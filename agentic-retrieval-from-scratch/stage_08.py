"""Agentic Retrieval From Scratch — stage 8: The loop that must terminate, priced every round.

Seven stages of retrieval, each one a single pass: a document becomes citable
chunks, chunks become an index, the index answers a query twice and fuses the
two, a reranker reorders what came back, a question is made unambiguous before
it is asked, what came back is critiqued with the offender named, and the
answer is claims tied to spans or an abstention with a reason. Every one of
those is a function of its inputs. This stage is the first one that *asks
again*, and asking again is where a pipeline stops being a function and becomes
a loop — which is to say, a thing that can also fail by never finishing.

The loop is the build-5 skill of the roadmap: search, critique what came back,
rewrite the query, search again. What makes it a stage rather than a `while`
statement is that it is bounded twice and priced every round. The bound is the
caller's: a budget in cents and a cap on how many rewrites are allowed. The
price is the customer's: each round charges the customer's own meter for the
retrieval, the rerank, the critique and the generation it performed, and the
cents a round reports is the *meter's own delta* for that round rather than
this stage's belief about what it should have cost. A loop that cannot say what
it spent is a loop that cannot be run under a budget at all.

The ways a round can end the loop are decisions, not accidents, and each is a
row of data rather than an exception: the answer is not an abstention
(`answered`), the rewrite would search a query already searched (`repeat`), the
rewrites allowed are used up (`round-cap`), or the next round would spend past
the budget (`budget`). An abstention that stops the loop reports itself
(`abstained`) with the answer's own reason, so the honest "I could not ground
this" is never replaced by a mechanical one.

    ROUND_KEYS          the six fields of one round, in order
    LOOP_KEYS           the six fields of the loop's own answer, in order
    STOPS               the closed vocabulary of what stopped the loop
    RETRIEVE_UNITS      units of retrieval a round charges the meter
    RERANK_UNITS        units of reranking a round charges the meter
    CRITIQUE_UNITS      units of critique a round charges the meter
    GENERATE_UNITS      units of generation a round charges the meter
    DEFAULT_LIMIT       the retrieval width this course treats as the default
    ask(index, corpus, meter, question, tick, limit, budget_cents, round_cap)
                        -> LOOP_KEYS, the rounds it ran and why it stopped
    rounds_of(loop)     -> the rounds a loop ran, in the order it ran them

DESIGN DECISION — why is the budget checked before the round rather than after
it?
Because a budget is a promise about what this loop will spend, and a check
after the call is a check that has already broken it. A round's price is
knowable before the round runs — the customer's own table prices the four
charges a round makes — so the loop compares what it has spent plus that price
against the budget and refuses to run a round whose whole cost would leave the
meter above what the caller allowed. The number a stop reports is therefore the
number it would have spent, which is the number the caller needs to decide
whether to raise the budget or narrow the loop.

DESIGN DECISION — why is a round's cost the meter's delta rather than the sum
this stage can compute for itself?
Because a sum this stage computes is a belief, and the objects here are the
customer's. The price table could change, a round could charge more than the
four calls it names, and a stage that reported its own arithmetic would keep
agreeing with itself while disagreeing with the ledger. The meter keeps the
log; the delta between its total before the round and its total after is the
one number that cannot be wrong about what was spent, and a round's own
`cost_cents` is exactly that delta.

DESIGN DECISION — why does a rewrite that changes nothing end the loop instead
of being tried again?
Because a loop whose next query is the query it just searched is a loop that
does not terminate for a reason, and the question's own abstention is a better
answer than an unbounded search. On the customer's own question a rewrite with
no fix yields the text unchanged: there is nothing left to rewrite, so the loop
stops on the abstention it already holds and reports the answer's own reason.
Once a rewrite has been applied, a rewrite that lands on a query the loop has
already searched is the same failure differently named, and it stops as
`repeat`.

DESIGN DECISION — why is the cap counted in rewrites rather than in rounds?
Because the thing that can grow without bound is the rewriting, not the
searching. Counting rounds would make the first search cost a rewrite, so every
question would pay one even when it never needed rewriting; counting rewrites
means the customer's own question is always tried once and only the attempts to
improve it are capped. The arithmetic is then exact — at most `round_cap`
rewrites, so at most `round_cap + 1` rounds — and a cap that is hit is named as
what it is rather than discovered as a timeout.

DESIGN DECISION — why is a round's record rebuilt rather than the question
reused?
Because what changes between rounds is the text, and nothing else. The rewriter
needs the question's own `expected` and `conversation` to know what a pronoun
refers to and what a two-hop question wants, so the record handed to it carries
those fields untouched and only the text advanced; a rewritten query that lost
the question's expectations would be rewritten against nothing and answered
against nothing.

TODO: implement `ask` and `rounds_of` in this file: the budgeted loop that
retrieves, reranks, critiques and answers a round at a time, rewrites once per
abstention, charges the customer's meter for every call, and names the one
thing that stopped it.
"""

import corpus
import meter

import stage_03
import stage_04
import stage_05
import stage_06
import stage_07

ROUND_KEYS = ("round", "query", "rewrites", "retrieved", "survivors", "cost_cents")

LOOP_KEYS = ("question", "answer", "rounds", "cost_cents", "stopped", "reason")

STOPS = ("answered", "abstained", "budget", "round-cap", "repeat")

RETRIEVE_UNITS = 1

RERANK_UNITS = 1

CRITIQUE_UNITS = 1

GENERATE_UNITS = 1

DEFAULT_LIMIT = 5


def ask(index, corpus, meter, question, tick, limit, budget_cents, round_cap):
    """Run the budgeted loop over one question and answer what it did.

    Round 0 searches the question's own text; every later round searches the text
    the rewriter produced, carried in a record that keeps the question's `qid`,
    `expected` and `conversation`. Each round retrieves the hybrid top `limit`,
    reranks it, critiques it and answers from the survivors, charging the
    customer's meter one retrieval, one rerank, one critique and one generation,
    and reporting the meter's own delta as the round's `cost_cents`.

    The budget is checked before each round: a round whose price would leave the
    meter above `budget_cents` is not run, and the loop stops `budget` naming the
    total it would have reached and the budget. An answer that is not an
    abstention stops the loop `answered`; an abstention rewrites once and
    continues, until a query already searched stops it `repeat`, the `round_cap`
    rewrites allowed stop it `round-cap`, or nothing is left to rewrite and it
    stops `abstained` with the answer's own reason. Shapes this stage cannot
    accept — a question that is not a `QUESTION_KEYS` record, a limit, tick,
    budget or cap that is not a whole number — raise, naming the offender.
    """
    raise NotImplementedError("stage 8: implement ask()")


def rounds_of(loop):
    """The rounds a loop ran, in the order it ran them.

    A `LOOP_KEYS` record carries its rounds; anything that is not one raises,
    naming what arrived.
    """
    raise NotImplementedError("stage 8: implement rounds_of()")
