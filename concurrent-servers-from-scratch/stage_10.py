"""Concurrent Servers From Scratch — stage 10: One workload, four models, and the steps it took.

Stages 1 to 5 built one machine and four ways of driving it: one client at a
time, one thread per connection, one readiness set, and one event loop with
timers. Each of them answered its own workload, and four separate answers prove
nothing. This stage runs **one** workload through all four models and reports
what each of them cost — the same clients, the same requests, the same budget,
one fresh link each — and then holds every model's own account of what it did
against the link's own log.

That is the whole claim of the course, and it is deliberately not a promise that
one model wins. `run_all` reports four step counts; `compare` says whether the
four delivered the same bytes and which one was cheapest here; `cross_check` says
whether a model's belief about its own run matches the count the link kept. A
model that answered three clients while the fourth waited, a model that dropped
the tail of a reply, and a model that stepped the link twice a turn are all
visible in those three reports and in nothing else.

DESIGN DECISION — Who owns the workload: `workload()` here, or each model? A model
that builds its own clients is a model that graded itself: the four runs are only
comparable if they are handed the same clients with the same requests, the same
budget and the same script. `workload()` is the course's own workload, and every
model is a caller of it.

DESIGN DECISION — Is the link shared by the four models, or rebuilt for each? A
shared link carries the first model's leftovers — its drained bytes, its closed
connections, its clock — into the second one's run, and the second model's step
count is then measuring the first model's work. Each model gets a fresh link
built from the same clients, and `report` is that link's own log when the run is
over.

DESIGN DECISION — Does `compare` assert, or report? It reports. Four models are
allowed to disagree — the disagreement is the finding, and a stage that raised
on the first mismatch could never say *which* client, or how far apart the two
answers were. `compare` is a body of arithmetic over the four results; the
check is what asserts.

DESIGN DECISION — Whose numbers are the tie-breaker when a model disagrees with
the world? The link's. A model's `steps`, `ticks` and `answers` are what the
model believes it did; `report` is `Link.stats()`, recomputed from the link's own
event log, and it counts what actually moved. `cross_check` compares the two and
names every key they disagree on, so a server that answered while the client
received less than the answer is caught by the world rather than by its own
bookkeeping.

DESIGN DECISION — What breaks a tie between two equally cheap models? The order
of `MODELS`. Cheapest by a dict's own iteration order would make the report
depend on how the caller happened to build the dict, and a comparison that
changes when nothing changed is not a comparison.

DESIGN DECISION — Is a step a tick? No, and that is why the report keeps both.
A step is one turn of one model's loop; a tick is the world's own unit and only
`Link.step()` produces one. Two models can spend different numbers of steps to
deliver the same bytes, which is the course's subject, and the link's tick count
is what says how much of the world each of them used up.

TODO: implement `MODELS`, `workload`, `run_all`, `compare` and `cross_check` in
the module below.
"""


class ServerError(ValueError):
    """A models list this stage will not run, or a report it will not compare.

    The family for every shape this stage cannot honour: a model name that is not
    one of the four, a `runs` that is not a dict of them, a run missing one of
    its four keys, and a result that is not one this stage produced. A verdict
    about the *workload* — a model that answered later, or cost more steps, or
    delivered different bytes — is never an exception here: it is what `compare`
    and `cross_check` are for.
    """


#: The four models, in the order ties are broken and reports are read.
MODELS = ("blocking", "threads", "reactor", "event_loop")


def workload():
    """The course's own workload: the clients every model is handed.

    `{"clients", "requests", "budget", "script"}` — the clients, the same lines
    again for a caller that wants them as data, the turn budget every model gets,
    and the script the thread model is driven by (`None` for round-robin). The
    four clients are the course's four pressures: one that answers at once, one
    with two requests, one that reads two bytes every third tick, and one
    whose request and reply are longer than a single move, so every model has to
    defer a write and none of them can be compared on a workload that never
    strains.
    """
    raise NotImplementedError("stage 10: implement workload()")


def run_all(*, models=None):
    """Every model on the same workload, each on its own link.

    `{model: {"answers", "steps", "ticks", "report"}}` — `report` is
    `Link.stats()` of the link that model ran on, so the four runs can be held
    against the world rather than against each other. Each model gets a fresh
    `Link` built from the same clients: the clients are immutable, the
    connections are not.
    """
    raise NotImplementedError("stage 10: implement run_all()")


def compare(runs):
    """The four runs side by side: the same answers, and what each one cost.

    `{"same_answers", "differences", "steps", "cheapest", "tie_breaker"}`.
    `same_answers` is whether every model delivered the same replies to every
    client as the first model in the report, `differences` names the first
    mismatch per client as `(model, client, got, want)`, `steps` is every model's
    own count, `cheapest` is the fewest steps with ties broken by `MODELS` order,
    and `tie_breaker` is `cross_check` of that cheapest run.

    Nothing is asserted and nothing is raised for a disagreement: a model that
    delivered different bytes is a finding, and the report is where a check reads
    it.
    """
    raise NotImplementedError("stage 10: implement compare()")


def cross_check(run):
    """One model's own account of its run, against the link's own log.

    `{"agree", "disagreements"}` where `disagreements` is
    `((key, ours, theirs), ...)`: `ours` is what the model's result claims (the
    bytes its answers add up to, the clients it answered, the ticks it reports)
    and `theirs` is the same key recomputed from `run["report"]`. The link keeps
    the record, so a model that believes it answered while the client received
    less is a model whose two accounts disagree, by key and by number.
    """
    raise NotImplementedError("stage 10: implement cross_check()")
