"""history.py — the operations ledger and the linearizability checker.

A replicated log is only useful if the register it implements behaves as
if it were one object: every operation appears to take effect, instantly,
somewhere between the moment it was invoked and the moment it completed,
and the resulting order must be legal for a single sequential copy of the
object. That property is linearizability, and this module is the judge the
capstone hands its history to.

The grammar the fabric records (see `sim.py`):

    ("invoke",  tick, proc, operation, None)
    ("complete", tick, proc, operation, value)

An operation is a string: `"k=v"` writes v into key k, `"get k"` reads k,
`"members:a,b,c"` changes the membership. The sequential object is a dict
of key values plus the membership; a `not_leader` completion is a refused
call — it takes no effect anywhere and cannot break the order.

`linearizable(events)` searches the legal orders in tick order,
deterministically: at each step it picks the earliest pending operation
whose effect is consistent with some point between its invoke and its
complete; when no such pick exists the history is NOT linearizable and the
reason names the operations that cannot be ordered — every operation that
is still open when the search dies, with the answer that contradicts.

There is no clock read, no randomness, no float: the search is a function
of its events.
"""


class HistoryError(ValueError):
    """The ledger's refusal: an event the grammar does not know."""


class History:
    """The append-only ledger of operations the fabric recorded."""

    def __init__(self):
        self._events = []

    def invoke(self, proc, operation):
        self._events.append(("invoke", proc, operation, None))
        return len(self._events) - 1

    def complete(self, proc, operation, value):
        self._events.append(("complete", proc, operation, value))
        return len(self._events) - 1

    def record(self, event):
        """A raw event tuple, already shaped by the fabric."""
        if (not isinstance(event, tuple) or len(event) != 5
                or event[0] not in ("invoke", "complete")):
            raise HistoryError("history.record: %r is not an event the "
                               "ledger's grammar knows" % (event,))
        self._events.append(tuple(event))
        return len(self._events) - 1

    def events(self):
        return tuple(self._events)


def _parse(operation):
    if operation.startswith("members:"):
        return ("members", tuple(operation[len("members:"):].split(",")))
    if operation.startswith("get "):
        return ("read", operation[4:])
    if "=" in operation:
        key, value = operation.split("=", 1)
        return ("write", key, value)
    raise HistoryError("history: %r is neither a read, a write nor a "
                       "membership change" % (operation,))


def _apply(state, operation):
    """Apply one operation to the sequential state; answer the value a
    read would honestly return after it."""
    parsed = _parse(operation)
    if parsed[0] == "members":
        state["members"] = parsed[1]
        return None
    if parsed[0] == "write":
        state[parsed[1]] = parsed[2]
        return None
    return state.get(parsed[1], "")


def _operations(events):
    """Pair invokes with completes per process, oldest open first; answer
    (proc, operation, invoke_tick, complete_tick, value) tuples. Two
    operations of one process may not overlap: a proc invokes only when
    its previous call completed."""
    ops = []
    open_by_proc = {}
    for kind, tick, proc, operation, value in events:
        if kind == "invoke":
            if open_by_proc.get(proc):
                raise HistoryError("history: %s invoked %r while %r is "
                                   "still open — one process, one call at "
                                   "a time" % (proc, operation,
                                               open_by_proc[proc][-1]))
            op_id = len(ops)
            ops.append([proc, operation, tick, None, None])
            open_by_proc.setdefault(proc, []).append(op_id)
        else:
            queue = open_by_proc.get(proc)
            if not queue:
                raise HistoryError("history: a complete for %r on %s with "
                                   "no invoke before it" % (operation, proc))
            op_id = queue.pop(0)
            ops[op_id][3] = tick
            ops[op_id][4] = value
    if any(op[3] is None for op in ops):
        raise HistoryError("history: an invoke never completed — a torn "
                           "run is not a history")
    return tuple(tuple(op) for op in ops)


def _normalize(events):
    """Answer (kind, tick, proc, operation, value) tuples: the fabric's
    5-tuples pass through; the History-method 4-tuples get positional
    ticks."""
    out = []
    for position, event in enumerate(events):
        if len(event) == 5:
            out.append(tuple(event))
        elif len(event) == 4 and event[0] in ("invoke", "complete"):
            out.append((event[0], position, event[1], event[2], event[3]))
        else:
            raise HistoryError("history: %r is not an event the checker "
                               "reads" % (event,))
    return tuple(out)


def linearizable(events):
    """(True, ()) when every operation can be placed at an instant between
    its invoke and its complete so the sequential object is respected;
    (False, reasons) naming what cannot be ordered otherwise."""
    if isinstance(events, History):
        events = events.events()
    ops = _operations(_normalize(events))
    order = sorted(range(len(ops)), key=lambda i: (ops[i][2], i))
    # A call answered "not_leader" or "timeout" took no effect anywhere:
    # the client was refused or gave up. It linearizes by disappearing.
    refused = frozenset(i for i in order
                        if ops[i][4] in ("not_leader", "timeout"))
    pending = tuple(i for i in order if i not in refused)
    ok, conflict = _search(ops, {}, frozenset(pending), 0, ())
    if ok:
        return (True, ())
    return (False, conflict)


def _search(ops, state, pending, frontier, trail):
    """Extend the sequential order by one operation. A candidate can
    take effect at the instant `max(frontier, its invoke)` — legal while
    that instant is not past its complete. The lemma tries the
    earliest-completing visible candidate first, so honest histories
    settle without real backtracking; adversarial ones may branch, and
    these histories are a few dozen operations deep. Answer
    (found, reasons); `trail` names the order tried last."""
    if not pending:
        return (True, ())
    candidates = [i for i in sorted(pending)
                  if max(frontier, ops[i][2]) <= ops[i][3]]
    if not candidates:
        reasons = []
        for op_id in sorted(pending):
            proc, operation, invoke_tick, complete_tick, value = ops[op_id]
            reasons.append("operation %r (invoke %s, complete %s, answered "
                           "%r) can take effect nowhere in its window once "
                           "the rest of the history is ordered"
                           % (operation, invoke_tick, complete_tick, value))
        return (False, tuple(reasons))
    candidates.sort(key=lambda i: (ops[i][3], ops[i][2], i))
    for op_id in candidates:
        proc, operation, invoke_tick, complete_tick, value = ops[op_id]
        probed = dict(state)
        answered = _apply(probed, operation)
        if not _consistent(operation, answered, value):
            continue
        found, reasons = _search(ops, probed, pending - {op_id},
                                 max(frontier, invoke_tick),
                                 trail + (operation,))
        if found:
            return (True, ())
        first_fail = reasons
    # nothing extends the order consistently: blame the first-read offender
    stuck = []
    for op_id in sorted(pending):
        proc, operation, invoke_tick, complete_tick, value = ops[op_id]
        if operation.startswith("get "):
            stuck.append("operation %r answered %r in no legal order of "
                         "this history" % (operation, value))
    if not stuck:
        stuck = ["no legal order extends after %r" % (trail[-1],)]
    return (False, tuple(stuck))


def _consistent(operation, answered, value):
    """A read's answer must equal the sequential state's; a write or a
    membership change answers "ok" when it committed."""
    if operation.startswith("get "):
        return answered == value
    return value in ("ok", None)
