"""Concurrent Servers From Scratch — stage 10: One workload, four models, and the steps it took.

The solution. Four models, one workload, and the link's own log as the only
record that none of them wrote.
"""

from link import Client, Link

import stage_02
import stage_03
import stage_04
import stage_05


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

#: The turn budget every model is handed: a budget spent with work left is an
#: outcome the result reports, so the number only has to be big enough to finish.
BUDGET = 256

#: The four pressures, and why the workload is four clients and not one: a client
#: answered at once, one with two requests (so a model is asked twice), one that
#: reads two bytes every third tick (the slow reader the blocking model
#: cannot get past), and one whose request and reply are longer than `MAX_CHUNK`
#: (so every model has to defer a write and nobody can finish a reply in a turn).
FAST = (b"ping\n",)
TWO = (b"hello\n", b"again\n")
SLOW = (b"hola\n",)
LONG = (b"x" * 120 + b"\n",)

#: The keys a run has, in the order `run_all` builds them.
RUN_KEYS = ("answers", "steps", "ticks", "report")

#: The keys `cross_check` holds the model's own account against the link's log
#: for, in the order the disagreements are reported.
CHECKED = ("bytes_drained", "clients", "ticks")


def _clients():
    """The four clients of the course's workload, fresh on every call."""
    return (Client("fast", FAST),
            Client("two", TWO, read_every=2),
            Client("slow", SLOW, read_every=3, chunk=2),
            Client("long", LONG))


def _models(models):
    """The models to run: all four, or the ones named and nothing else."""
    if models is None:
        return MODELS
    if not isinstance(models, (tuple, list)) or not models:
        raise ServerError("models is a non-empty sequence, not %r" % (models,))
    chosen = []
    for model in models:
        if model not in MODELS:
            raise ServerError("no model %r: the four are %r"
                              % (model, list(MODELS)))
        if model in chosen:
            raise ServerError("model %r is named twice" % (model,))
        chosen.append(model)
    return tuple(chosen)


def _budget(plan):
    """The turn budget of a workload: a whole number of turns."""
    budget = plan.get("budget")
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
        raise ServerError("a workload's budget is a whole number of turns, "
                          "not %r" % (budget,))
    return budget


def _plan(plan):
    """A workload this stage will run: the clients, the requests, the budget."""
    if not isinstance(plan, dict):
        raise ServerError("a workload is a dict of its clients and its budget, "
                          "not %r" % (plan,))
    clients = plan.get("clients")
    if not isinstance(clients, (tuple, list)) or not clients:
        raise ServerError("a workload's clients are a non-empty sequence, "
                          "not %r" % (clients,))
    for client in clients:
        if not isinstance(client, Client):
            raise ServerError("a workload's client is a Client, not %r"
                              % (client,))
    requests = plan.get("requests")
    if not isinstance(requests, dict):
        raise ServerError("a workload's requests are a dict of them, not %r"
                          % (requests,))
    _budget(plan)
    return tuple(clients)


def _bundle(plan):
    """The server dict the models are handed, over a link of its own.

    The clients are immutable, the connections are not: a model that ran on the
    link its neighbour ran on would be measuring the leftovers of that run, so
    every model gets its own `Link` built from the same four clients.
    """
    clients = _plan(plan)
    link = Link(clients)
    return {"link": link, "clients": clients,
            "requests": {client.name: client.requests for client in clients}}


def _run(run):
    """A run this stage will compare: the four keys, and nothing else."""
    if not isinstance(run, dict):
        raise ServerError("a run is a dict of %r, not %r"
                          % (list(RUN_KEYS), run))
    missing = [key for key in RUN_KEYS if key not in run]
    if missing:
        raise ServerError("a run has no %s" % (", ".join(missing),))
    if not isinstance(run["answers"], dict):
        raise ServerError("a run's answers are a dict, not %r" % (run["answers"],))
    for name, lines in run["answers"].items():
        if not isinstance(lines, tuple):
            raise ServerError("%s's answers are a tuple of lines, not %r"
                              % (name, lines))
        for line in lines:
            if not isinstance(line, bytes):
                raise ServerError("%s's answer %r is bytes" % (name, line))
    if not isinstance(run["report"], dict):
        raise ServerError("a run's report is a dict, not %r" % (run["report"],))
    return run


def _runs(runs):
    """The models of a `runs`, in `MODELS` order, or a refusal naming the fault."""
    if not isinstance(runs, dict) or not runs:
        raise ServerError("runs is a dict of models, not %r" % (runs,))
    for model in runs:
        if model not in MODELS:
            raise ServerError("no model %r: the four are %r"
                              % (model, list(MODELS)))
        _run(runs[model])
    return tuple(model for model in MODELS if model in runs)


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
    clients = _clients()
    return {"clients": clients,
            "requests": {client.name: client.requests for client in clients},
            "budget": BUDGET,
            "script": None}


def run_all(*, models=None):
    """Every model on the same workload, each on its own link.

    `{model: {"answers", "steps", "ticks", "report"}}` — `report` is
    `Link.stats()` of the link that model ran on, so the four runs can be held
    against the world rather than against each other. Each model gets a fresh
    `Link` built from the same clients: the clients are immutable, the
    connections are not.
    """
    wanted = _models(models)
    plan = workload()
    budget = _budget(plan)
    runs = {}
    for model in wanted:
        server = _bundle(plan)
        if model == "blocking":
            result = stage_02.serve_blocking(server, budget=budget)
        elif model == "threads":
            result = stage_03.serve_threads(server, script=plan.get("script"),
                                            budget=budget)
        elif model == "reactor":
            result = stage_04.serve_reactor(server, budget=budget)
        else:
            result = stage_05.serve_with_timeouts(server, budget=budget)
        runs[model] = {"answers": result["answers"], "steps": result["steps"],
                       "ticks": result["ticks"],
                       "report": server["link"].stats()}
    return runs


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
    order = _runs(runs)
    reference = runs[order[0]]["answers"]
    differences = []
    for client in reference:
        want = reference[client]
        for model in order[1:]:
            got = runs[model]["answers"].get(client)
            if got != want:
                differences.append((model, client, got, want))
                break
    steps = {model: runs[model]["steps"] for model in order}
    cheapest = min(order, key=lambda model: (steps[model], MODELS.index(model)))
    return {"same_answers": not differences,
            "differences": tuple(differences),
            "steps": steps,
            "cheapest": cheapest,
            "tie_breaker": cross_check(runs[cheapest])}


def cross_check(run):
    """One model's own account of its run, against the link's own log.

    `{"agree", "disagreements"}` where `disagreements` is
    `((key, ours, theirs), ...)`: `ours` is what the model's result claims (the
    bytes its answers add up to, the clients it answered, the ticks it reports)
    and `theirs` is the same key recomputed from `run["report"]`. The link keeps
    the record, so a model that believes it answered while the client received
    less is a model whose two accounts disagree, by key and by number.
    """
    _run(run)
    answers = run["answers"]
    report = run["report"]
    ours = {"bytes_drained": sum(len(line) for lines in answers.values()
                                 for line in lines),
            "clients": len([lines for lines in answers.values() if lines]),
            "ticks": run["ticks"]}
    theirs = {"bytes_drained": report["bytes_drained"],
              "clients": report["closes"],
              "ticks": report["ticks"]}
    disagreements = tuple((key, ours[key], theirs[key]) for key in CHECKED
                          if ours[key] != theirs[key])
    return {"agree": not disagreements, "disagreements": disagreements}
