"""Concurrent Servers From Scratch — stage 2: The blocking server, and the slow client.

Stage 1 built the connection as data and one move at a time, and it deliberately
did not say who calls those moves or in what order. This stage answers the first
half of that question the only way a single-threaded server can: one client at a
time, each one driven to completion before the next is even accepted. Accept, read
the line, answer, wait for the client to drain the answer, close the connection,
take the next client — and only then look at anybody else. It is the model
Bendersky's series starts from, and it is worth writing by hand precisely because
it is defensible: it is simple, it is correct for a handful of clients, and it
contains the failure the whole course is about.

The bundle is `{"link", "clients", "requests"}`: the world, the scripted clients
it holds, and the lines those clients send. This stage adds nothing to that
bundle and reads nothing else out of it — the link is the arbiter of what is
really on the wire, and the policies above this stage (threads, a reactor, timers,
callbacks, `async`) are handed exactly the same dict. What they disagree about is
who gets the processor next; this stage's answer is "whoever was accepted first,
and nobody else until they are finished".

The failure is the slow client. A client that drains its inbox every fourth tick
is a perfectly ordinary client; under a blocking server it is a stop-the-world
event, because the one thread of control has nothing to do but turn the world's
clock until that client has taken its bytes. Everyone behind it waits, and the
budget — counted in *steps*, one turn of the loop each — is what makes that
visible: the model returns what it managed instead of pretending it finished.

    serve_blocking  the whole model: accept, read, answer, wait, close; repeat

The result is the model's verdict about the run, and it is the same shape every
later model has to produce, so the capstone can compare four of them:

    answers   {name: tuple of the reply lines the server wrote, in order} — every
              client of the bundle is present; a client the budget never reached
              is an empty tuple rather than a missing key
    steps     the turns the loop took (one turn = one move plus one tick)
    ticks     the link's clock at the end of the run
    served    the clients taken to completion, in that order
    starved   the clients whose requests the server never answered, in accept
              order — not "everyone who is not served"

DESIGN DECISION — what is a turn, and why does every turn tick the world?
A turn is one move of the current connection's stage-1 machine, and the turn ends
by handing the link one tick. A blocking server has one thread of control: while
it reads, while it writes and while it waits for the client to drain, it cannot do
anything else, and in this course the link only moves a byte or a clock when it
is stepped. So the two counts come out equal — `steps == ticks` — and that
equality is the finding rather than an accident of implementation: every
operation this model performs costs every client a tick of the world's time. A
model that let some turns pass without ticking would be reporting a cost it did
not pay.

DESIGN DECISION — in what order are the clients served, and does the model ever
prefer one?
In the order the link offers them: `accept()` is the oldest waiting client, and
the loop takes the next one only after `finish` has closed the current one. The
model has no policy to choose, and that is the point — a blocking server's only
scheduling decision is "the one in front", which is why one slow client stops
everyone. `served` therefore comes out in accept order, and a model whose
`served` does not is a model that reordered its clients, not a model that blocked.

DESIGN DECISION — what is `answers`, and who counts a reply as written?
A reply is written when the last of its bytes has gone into the link's outbox,
which is stage 1's own count (`"replies"`): a reply the bounded outbox only half
took is *not* an answer yet, and the pieces it went out in are not two answers.
The entries are therefore whole lines, prefix and newline included, and the reply
is attributed to the connection the model is serving and to no other. Every
client of the bundle appears, with an empty tuple when the run never answered it,
because a dict with missing keys cannot be compared across models and a client
the budget cut off is a fact worth reporting.

DESIGN DECISION — exactly which clients are `starved`?
The clients with at least one request the server never answered, in accept order.
The tempting shortcut — everyone who is not in `served` — is wrong on both sides.
A client sitting in the backlog has a request the link holds and no answer, so it
is starved; a client whose request was read and answered, but whose connection
the budget stopped the model from draining and closing, is neither served nor
starved, and calling it starved would hide the very thing the budget is there to
show. The verdict is derived from the link's own count of each client's requests
and the answers the model actually wrote.

DESIGN DECISION — what happens when the budget runs out, and why is that not an
exception?
A budget is a count of steps, and the loop takes a turn only while it has one
left: check, then move, so a budget of N is exactly N turns and never N+1. When
the budget is spent the model stops and returns what it did — `served`, `starved`
and the answers written so far — because "I did not finish" is a legitimate
answer to "serve these clients within this many steps", and the caller can hold it
against the link's log. Only a shape the model cannot honour at all is a
refusal: a bundle that is not `{"link", "clients", "requests"}` with a link whose
own connections agree with it, or a budget that is not a count of steps.

TODO: implement `serve_blocking`.
"""


class ServerError(ValueError):
    """A server bundle this stage will not serve, or a budget that is not a count.

    It is the family for every shape `serve_blocking` cannot honour: a `server`
    that is not a dict, one that is missing one of its three keys, a `"link"`
    that is not the world, a `"clients"` sequence that is empty or does not agree
    with the link's own connections, a `"requests"` mapping without one of those
    clients' lines, a request line that is not bytes, and a `budget` that is not
    a count of steps. A verdict about what the *clients* did is never an
    exception here: a client the budget never reached is `starved`, and a budget
    spent with work left is an outcome the caller reads out of the result.
    """


def serve_blocking(server, *, budget=256):
    """Serve the bundle's clients one at a time, to completion, inside a budget.

    The loop is the oldest server there is: take the oldest waiting client, drive
    its stage-1 machine until the client has nothing left to send and has taken
    every byte the server wrote, close it, and only then look at the next one.
    No second client's request is ever read while the first is unanswered, which
    is what makes the model *blocking* — and what makes a client that drains its
    inbox every fourth tick the whole story of the run.

    One turn is one move of the current connection, and every turn lets the link
    move one tick, because the model has nothing to do but wait while the world
    carries the bytes and the client drains them. `steps` counts turns and
    `ticks` is the link's clock at the end; on this model they are equal, and
    that equality is the cost of a single thread of control.

    `answers` carries every client of the bundle, in the link's accept order: the
    reply lines the server wrote for it, in order, as whole lines (a reply the
    outbox took in two pieces is one entry), and an empty tuple for a client the
    budget never reached. `served` is the order the clients were taken to
    completion — for a blocking model the accept order — and `starved` is the
    clients with a request the server never answered, again in accept order.

    `budget` is a count of *steps*: the loop takes a turn only while it has one
    left, so a budget spent with work left is a result rather than an exception,
    and the caller can tell from `served`, `starved` and the link's own
    `bytes_drained` exactly how far it got.
    """
    raise NotImplementedError("stage 2: implement serve_blocking()")
