"""Orchestration From Scratch — stage 8: The budget, checked before the call.

A run is a pile of scripted calls, and every call costs tokens: `agents.Reply`
says how many, and this stage is the one place that number is added up. What it
decides is the order of two facts — whether the run may make a call at all, and
what the call cost once it has happened — because the two orders are not the
same failure. Asked first, the question refuses a call the run cannot pay for,
and the node it refuses becomes a `skipped` state in a run that keeps going.
Asked last, the same question is a report on money already spent: a traceback, a
half-written ledger, and a run that cannot say which nodes it paid for.

The state is two keys — `spent` and `budget` — and the rest of the numbers are
the graph's own: stage 1 parsed every node with a `tokens` field, the node's
*own* budget, and a run's budget is what the caller hands the loop. Everything
here is an int; there is no float, no ratio and no percentage anywhere in this
stage, because a percentage is a pair of ints somebody already divided.

DESIGN DECISION — why is the state a mapping with exactly two keys, and why is
an unknown key refused while a missing `spent` is zero?
    Because the ledger is a vocabulary, and this course's rule about
    vocabularies is stage 1's: a key the shape does not have is a typo, and a
    typo is not a default. `{"spend": 40, "budget": 64}` would be read as
    `{"budget": 64}` — the run would spend from zero and print a line nobody
    could recompute — so the key is refused and the two keys a state may carry
    are named. `spent` is the one key with a default, and that default means
    something: a run that has not spent anything carries an empty ledger, and
    `budget_line({"budget": 8})` is `(0, 8)`. `budget` has no default, because a
    line without the run's budget is not a line: a percentage is what you get
    when you divide by a number you were not given.

DESIGN DECISION — why is the budget's question asked before the call and the
answer's number read after it?
    Because the two orders are two different failures. Before the call the
    question is a decision — `affordable` — and a `no` costs the run nothing:
    the node is filed `skipped` and the script was never called. After the call
    the only honest answer is the exact number the call left behind, so `spend`
    adds the reply's cost to what was already spent and returns the total; it
    does *not* compare that total against the budget, because a comparison made
    after the money is gone is not a refusal, it is an apology. A run whose
    ledger is only read after the fact discovers the overrun in its report, and
    has already paid the agent that caused it.

DESIGN DECISION — why does `affordable` compare a node's own budget against
what is *left*, and not against the run's total?
    Because the two questions agree exactly once — on a run that has spent
    nothing — and disagree everywhere a budget matters. `graphs["wide"]` has
    seven nodes and none of them declares more than 16 tokens: against a
    64-token run's *total*, every one of them is affordable, so that rule would
    dispatch all seven and spend 88. Against what is left it pays for the plan
    and five of the leaves, refuses the sixth and the seventh, and the run stops
    with two `skipped` nodes instead of a surprise. The node's own number is
    what the node declared it is worth; the run's number is what the whole job
    may cost; a rule that mixes the two is a rule for a one-node run.

DESIGN DECISION — why is the refusal both a value and a class?
    Because there are two callers. A loop asks `affordable` and branches: a
    `False` becomes a `skipped` state, the run goes on, and the record says
    which nodes were never called — an exception thrown into a loop stops a run
    that a state would have accounted for, and the states a run is in are the
    course's vocabulary, not tracebacks. A caller without a loop — a tool, a
    report, a stage that dispatches a single node — comes through
    `_require_affordable` instead and gets `BudgetExhausted`, which carries the
    four facts the refusal is made of: the node, its cost, what was spent and
    the run's budget. Catching it is therefore *filing* it: those four
    attributes are the state entry, so a refusal that is caught can be written
    down without anyone parsing a message.

DESIGN DECISION — why does `budget_line` come back as `(spent, budget)`, and
never as a float or a percentage?
    Because the line has to be recomputable by whoever reads the report. A
    percentage is a rounding: 48 of 64 tokens is "75%", which is not the number
    the run spent, and 61 of 65 is "94%" for a reader who wants to know whether
    there is room for one more call. A float is worse — it is a division nobody
    asked for, and every number in this course is an int count. The pair is
    exact and comparable, and it survives the case the report actually has to
    explain: `spent` may exceed `budget`, because a scripted agent reports what
    its call cost and not what the node guessed it would. `(76, 64)` says "over
    by twelve"; `"119%"` says nothing anybody can act on.

DESIGN DECISION — why must the node be stage 1's `Subtask`, and not the raw
plan the job file carries?
    Because this stage would otherwise be a second parser. A raw mapping is
    what `graphs.py` hands out and what a job file holds: reading
    `node["tokens"]` here would spend a key nobody validated, and a plan that
    spells `{"tokens": 8, "tokez": 9}` — stage 1's refusal — would quietly spend
    the 8. The record is also frozen and hashable, so a node is a value the
    ledger's arithmetic can be described against, while a raw dict is a thing
    two stages can edit out from under each other. So the raw plan is refused,
    naming the node it describes, and the caller is sent through `parse_graph`
    once.
"""

from collections.abc import Mapping

import agents

from stage_01 import OrchestrationError, Subtask

#: The keys a budget state carries, in the order a reader meets them: what the
#: run has spent so far, and what it was allowed to spend. A key outside this
#: tuple is a typo, and a typo is not a default: `{"spend": 40, "budget": 64}`
#: would spend from zero and print a line nobody could recompute.
_STATE_KEYS = ("spent", "budget")


class BudgetExhausted(OrchestrationError):
    """The refusal: a node the run cannot pay for.

    Raised by the look-before-you-call form of the rule — never by `spend`,
    which is the number *after* a call that already happened. It carries the
    four facts the refusal is made of (`node`, `cost`, `spent`, `budget`), so
    that catching it is enough to file the decision: a loop that turns it into a
    `skipped` state does not have to parse its own message, and a run that lets
    it escape as a traceback has thrown away a state it could have kept.
    """

    def __init__(self, message, *, node=None, cost=None, spent=None, budget=None):
        """One refusal, carrying the four facts it is made of."""
        super().__init__(message)
        self.node = node
        self.cost = cost
        self.spent = spent
        self.budget = budget


def _count(value, what):
    """A token count: a real `int` and not negative. `bool` is refused although
    `isinstance(True, int)` is true — `True` is a flag, and a ledger that reads
    a flag as a number is a ledger nobody can audit."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise OrchestrationError("%s must be an int count, got %r" % (what, value))
    if value < 0:
        raise OrchestrationError("%s must be >= 0, got %r" % (what, value))
    return value


def _ledger(state):
    """The two numbers of a budget state, validated in one place: `(spent,
    budget)`.

    A state that is not a mapping, a key the shape does not have, a state that
    does not say what the run's budget is, and a number that is not a count are
    each refused here, naming the key or the value — because every function of
    this stage reads the line through this door, and a line read twice in two
    ways is two different runs.
    """
    if not isinstance(state, Mapping):
        raise OrchestrationError("a budget state must be a mapping carrying "
                                 "'spent' and 'budget', got %r"
                                 % (type(state).__name__,))
    for key in state:
        if key not in _STATE_KEYS:
            raise OrchestrationError("a budget state has no key %r; it carries "
                                     "%r" % (key, _STATE_KEYS))
    if "budget" not in state:
        raise OrchestrationError("a budget state must spell 'budget': a line "
                                 "without the run's budget is not a line")
    spent = _count(state.get("spent", 0), "a budget state's 'spent'")
    budget = _count(state["budget"], "a budget state's 'budget'")
    return (spent, budget)


def _cost_of(reply):
    """What one call cost, read off the answer: `agents.Reply.tokens`, and
    nothing else.

    An answer that is not a `Reply` — what `agents.bad_shape` builds — is
    refused rather than read for a number it does not have: a cost invented for
    an answer nobody understands is a ledger that lies in the run's favour.
    """
    if not isinstance(reply, agents.Reply):
        raise OrchestrationError("a call's answer must be an agents.Reply, got "
                                 "%r: an answer that is not a record has no cost "
                                 "to charge the run for"
                                 % (type(reply).__name__,))
    return _count(reply.tokens, "the tokens of a call's answer")


def _node_cost(node):
    """What the node declared it is worth: the per-node budget, read off the
    record stage 1 parsed.

    A raw plan — the mapping `graphs.py` hands out, or the body of a job file —
    is refused, naming the node it describes, because reading `node["tokens"]`
    here would be reading a key nobody validated: a plan that spells
    `{"tokens": 8, "tokez": 9}` is stage 1's refusal to make, and a budget that
    quietly spends the 8 is spending a number the plan did not say.
    """
    if not isinstance(node, Subtask):
        if isinstance(node, Mapping):
            raise OrchestrationError(
                "the node %r is a raw plan, not a Subtask: a budget spends the "
                "record stage 1's parse_graph built, never the mapping a job "
                "file carries" % (node.get("id"),))
        raise OrchestrationError("a node must be stage 1's Subtask, got %r"
                                 % (type(node).__name__,))
    return _count(node.tokens, "the budget of the node %r" % (node.id,))


def spend(state, reply):
    """The run's exact token total *after* one call: what was spent before,
    plus what the answer says the call cost.

    Exact ints, and never this call's cost alone — a ledger that reports each
    call as if it were the first is a ledger that never adds up. Nothing here
    compares the total against the budget: the call has already happened, so
    the number is a fact, and the refusal belonged *before* the call, where
    `affordable` asks for it.
    """
    spent, _budget = _ledger(state)
    return spent + _cost_of(reply)


def affordable(state, node):
    """Whether the run may make this call at all: asked **before** the call,
    never after it.

    The rule is the node's own budget against what is *left* of the run's —
    `spent + node.tokens <= budget` — and the answer is a value for the loop to
    branch on, not an exception for it to catch.
    """
    spent, budget = _ledger(state)
    return spent + _node_cost(node) <= budget


def _require_affordable(state, node):
    """The same rule as a refusal, for a caller that has no loop: the node, or
    `BudgetExhausted` carrying the id, the cost and the two numbers of the line.

    The loop asks `affordable` and files a `skipped` state; this is the door a
    tool, a report or a caller with no state table comes through, and the four
    facts the refusal carries are the state entry, so catching it *is* filing
    it.
    """
    if affordable(state, node):
        return node
    spent, budget = _ledger(state)
    cost = _node_cost(node)
    raise BudgetExhausted(
        "the budget refuses the call to %r: it is worth %d tokens, %d of the "
        "run's %d-token budget is spent, so %d are left and the call is short "
        "by %d" % (node.id, cost, spent, budget, budget - spent,
                   cost - (budget - spent)),
        node=node.id, cost=cost, spent=spent, budget=budget)


def budget_line(state):
    """The run's line: `(spent, budget)`, two exact ints.

    Not a float, not a percentage and not a rounding: a pair an accountant can
    add up and recompute. `spent` may exceed `budget` — a call can cost more
    than the node declared it would, and the line says so instead of hiding it
    in a fraction.
    """
    spent, budget = _ledger(state)
    return (spent, budget)
