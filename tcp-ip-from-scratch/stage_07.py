"""TCP/IP From Scratch — stage 7: The socket API, as a table of calls.

The stages before this one are a stack: bytes become frames, frames become
segments, segments become a stream, and a window says how much of that stream
may be in flight. Nothing in them is an *interface*. This stage is the interface:
the eight calls an application makes — `socket`, `bind`, `listen`, `accept`,
`connect`, `send`, `recv`, `close` — each of which is a small decision about a
number and a dict, and none of which is allowed to raise when the *kernel* is the
one with something to say.

That last part is the whole design. A call that the caller got wrong — a name
that is not a call, a descriptor that is not an int, a state asked of a desk that
has no such socket — is a mistake in the caller's own program, and it raises.
Everything else is an answer: a descriptor, an empty read, a connection state, or
an errno from the frozen vocabulary. A refusal is *data*, not an exception,
because the caller of `accept` on a socket nobody has connected to is not
mistaken — it is early, and being early is what `EAGAIN` means.

The descriptors are the other half. A table hands out small integers from three,
never reuses one that is in use, and the port a descriptor holds is released by
`close` — but not before the call that asked for it is in the log, because the
log is the proof that every call was answered exactly once, refused ones
included.

DESIGN DECISION — why does a call return an errno instead of raising?
Because the caller of a socket API is a program that must handle "not yet" in its
normal flow, and an exception makes the normal case the exceptional one. `EAGAIN`
is the single most common answer `accept` and `recv` give, and a stack that
raised for it would make every server loop a try/except. The one thing a call
answers with is a dict of exactly three keys, and exactly one of `value` and
`errno` is ever set.

DESIGN DECISION — why is the log a list of every call, and why is a refused call
in it?
Because the table's contract is that a call is answered once and only once, and a
log is the only way a caller can see that a call it made was answered rather than
swallowed. A refused call is not a special case: it is in the log with its errno
and a `None` value, exactly like the call that succeeded is in the log with a
value and a `None` errno.

DESIGN DECISION — why does a descriptor hold its local port only until `close`,
when the connection behind it is in no state to be reused?
Because the *port* and the *connection* are two different resources and the
application frees them at two different moments: `close` is the moment the
descriptor is gone and the number is free to be handed out again, and a port left
bound by a descriptor that no longer exists is a port no later `bind` can have.
The same table that holds the ports hands out the descriptors, so one `close`
must do both or the port leaks for the life of the process.

DESIGN DECISION — why does `recv` distinguish an empty stream from a stream with
nothing yet in it, when both are zero bytes?
Because `b""` and `EAGAIN` are the two halves of the same question — "is there
more?" — and one of them means yes, there was more and it is over, and the other
means ask again. A loop that treats them alike either spins forever on a stream
that ended or stops reading a stream that has not. The state behind the
descriptor decides which one it is, and the state is what `state` reports.

DESIGN DECISION — why does `send` ask the window rather than put all its bytes in
flight?
Because the window is the only thing between this stage and a peer that is told
to swallow more than it can hold, and the window was decided in stage 6 for
exactly this call. `send` moves what the window allows and reports the bytes it
moved; the rest stays queued, and a later `send` or `tick` is what moves it.

    CALLS         the eight calls and how many arguments each takes
    ERRNOS        the refusals a call may answer with, and no others
    SocketError   the family raised for a caller's own mistake
    arity(name)   how many arguments a call takes, or a refusal
    call_name(nr) the name of the call numbered `nr`, from one
    Sockets       the table of descriptors, with `call`, `state`, `fds`, `log`

TODO: implement `arity`, `call_name` and every method of `Sockets`.
"""

CALLS = (("socket", 0), ("bind", 2), ("listen", 1), ("accept", 1), ("connect", 2),
         ("send", 2), ("recv", 1), ("close", 1))
ERRNOS = ("EBADF", "EINVAL", "ENOSYS", "EAGAIN", "ECONNREFUSED", "ENOTCONN",
          "EADDRINUSE", "EISCONN")


class SocketError(ValueError):
    """A call the *caller* got wrong — not a call at all, not an int, not a desk."""


def arity(name):
    """The number of arguments a call takes, or a refusal naming the call."""
    raise NotImplementedError("stage 7: implement arity()")


def call_name(nr):
    """The name of the call numbered `nr`, from 1, in `CALLS` order."""
    raise NotImplementedError("stage 7: implement call_name()")


class Sockets:
    """A socket table: eight calls, a set of descriptors, and the log of both.

    Every descriptor is a `stage_05.Connection` (or, before it is bound, nothing
    yet), and `send`/`recv` carry `bytes` through stage 6's `Sender`/`Receiver`,
    so the window rules decided there are the ones in force. Every call is
    answered as data — `{"name", "value", "errno"}` with exactly one of the last
    two `None` — and a call that could not be answered is in no way special: it
    is in the log with its errno, which is the whole point of the layer.
    """

    def __init__(self, host, local_port=40000):
        """A table whose host is where its frames go and from which they come."""
        raise NotImplementedError("stage 7: implement Sockets.__init__()")

    def call(self, name, *args):
        """One call, answered: `{"name", "value", "errno"}`."""
        raise NotImplementedError("stage 7: implement Sockets.call()")

    def state(self, fd):
        """The connection state behind a descriptor, refusing what has none."""
        raise NotImplementedError("stage 7: implement Sockets.state()")

    def fds(self):
        """The live descriptors, ascending."""
        raise NotImplementedError("stage 7: implement Sockets.fds()")

    def log(self):
        """Every call answered so far, in order, the refused ones included."""
        raise NotImplementedError("stage 7: implement Sockets.log()")
