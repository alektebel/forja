"""Orchestration From Scratch — stage 10: Two runs, identical bytes.

The capstone. `run` is §3's loop and it composes the nine stages before it: at
every tick it asks stage 3 which nodes may start under the caller's cap, asks
stage 7 for the gate on every effect before it dispatches one, asks stage 8 for
the budget before the call, renders stage 4's handoff, calls the agent, files
stage 9's line, takes stage 5's review when the caller gave a reviewer, and lets
stage 6 carry a failure down the graph without running a single dependent.

What comes back is the run as *data*: the states, the record, the report
recomputed from that record, the clock's last reading and the prompt every node
was handed. Nothing in it is an object identity, nothing is walked in insertion
order, and no number is declared: `report` refuses a total the record
contradicts, so two runs of the same graph with the same agents come back equal
— value for value, key for key.

DESIGN DECISION — why is the report recomputed from the record rather than
returned as counters the loop kept while it ran?
    A counter the loop increments is a second account of the run: it is right
    until the first path that sets a state and forgets to bump it, and the
    failure is silent — a run that dispatched three nodes reports two and nobody
    can tell which of the two accounts lied. The record is written once per
    decision, by the one writer stage 9 provides, so `report` counting it is the
    only way a run can state a number it can also prove. The loop hands the
    report its own claim (the ticks the clock ended on, the tokens it counts as
    spent) precisely so that the claim is *checked*: a run whose arithmetic and
    whose record disagree hears about it inside the run and not in the diff two
    runs are compared on.

DESIGN DECISION — why is an approval asked and never dispatched as work?
    The approver is a node of the graph, so the scheduler will happily hand it
    the dispatch branch and file it as work — and then the record counts a
    question in the number that is supposed to say how much work the plan did,
    and the approval has no state of its own to hold the answer. A question is
    not work: `dispatch` counts nodes that produce a result, while an approval is
    asked (`awaiting`) and then answered (`approve` or `deny`), and the effect it
    stops is what the run then decides about. The report's `dispatched` is the
    count of nodes that ran; an approval that inflated it would make a gated run
    and a worker run indistinguishable at exactly the number that is supposed to
    separate them.

DESIGN DECISION — why does a budget refusal land as a state instead of an
exception into the loop?
    Stage 8's refusal is a *named* error that carries the node, the cost and the
    two numbers of the ledger, and it is tempting to let it travel: a caller can
    catch it, so why not? Because a run that dies on it forgets the work it
    already did and the work it decided not to do — the dependency that will
    never be computed is not marked, the record stops mid-flight, and the reason
    the run stopped lives in a traceback instead of in the record the report is
    recomputed from. The loop asks `affordable` before the call and files the
    refusal as the node's own `skipped` state, so the budget is a decision the
    run accounts for: the same kind of fact as a failure, with the same
    consequences, and stage 6 carries it to the dependents.

DESIGN DECISION — why does the run hold an effect rather than dispatch it when
the gate is not clear?
    The effect invariant is an ordering, not an outcome: an effect dispatched
    while its approval is unanswered is the defect whether or not the approval
    would have said yes — the world already changed and the answer arrived to
    find it changed. So the gate is not a check that reports and lets the loop
    decide; it is the thing that decides, and stage 7 refuses the dispatch. The
    loop turns that refusal into §3's hold — the effect waits as `awaiting`,
    with no line of its own, because the thing being waited for is a person —
    and the record cannot say the effect ran, because it never did.

DESIGN DECISION — why does the clock advance only to the next thing that can
change the state, and never by one tick at a time?
    A tick is one unit of work, and empty ticks are not work: a run that walked
    the clock one tick at a time would report a number that is the wall it
    waited against, not the plan's own cost, and the number would change the
    moment an estimate changed for a reason nobody can see in the graph. The
    clock is J1's injected `Clock` — counted, never timed — and the loop moves it
    forward to the earliest tick at which something is due, so the ticks a run
    reports are exactly the work the plan declared and the same on every replay.

DESIGN DECISION — why is every collection the loop walks sorted?
    A run's bytes are its states, its lines and its report, and every one of
    them is built by iterating something: the graph's ids, the set of nodes a
    failure carries, the effects a gate answers for, the nodes a tick dispatches.
    Iterate a dict and the order is whichever insertion survived, iterate a set
    and it is whatever the hash table felt like, and the run is still *right* —
    which is why the defect is invisible until two runs of the same graph differ
    in a field nobody changed. Sorting by the id makes the run a function of the
    plan; `id()` and insertion order are the two things a run must never depend
    on, and the cap is what turns dispatch order into an observable.

TODO: implement `DEFAULT_LIMIT` and `run`.
"""

#: How many nodes a tick may put in the air when the caller does not say: four,
#: the cap the six-node fan of `graphs["wide"]` has to respect, so a run that
#: ignores the cap is visible on a fixture rather than only in an argument.
DEFAULT_LIMIT = 4


def run(graph, agents, *, clock=None, limit=DEFAULT_LIMIT, budget=None,
        reviewer=None, approver=None):
    """§3's loop, end to end, as data a second run has to agree with."""
    raise NotImplementedError("stage 10: implement run()")
