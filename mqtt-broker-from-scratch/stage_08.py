"""MQTT Broker From Scratch — stage 8: The session that outlives the socket.

Everything so far has been about one connection. The session is the broker's
memory of a client that is not connected any more, and it exists because MQTT
makes four promises that a socket cannot keep on its own: the subscriptions a
client has made, the messages queued for it while it was away, the will it asked
to have published if it vanished, and the keep-alive it asked for — a number the
broker uses to decide, with no network help at all, that the connection is over.

The socket is therefore one field of the session, not the session. A `cut`
closes the stream and leaves the record in place: the subscriptions are still in
force, and the messages for those subscriptions are still owed. A client that
comes back with a clean start of 0 is handed that record back, and everything it
had is true again **before** it sends its first SUBSCRIBE — a broker that waits
for the new SUBSCRIBE has already lost the messages published in the meantime.
A client that comes back with a clean start of 1 is handed a new record, and the
old one is thrown away whole: subscriptions, queue and all.

The two promises that are *owed* rather than *kept* are the ones this stage has
to get exactly right. The queue is bounded by `QUEUE_MAX`, and a bounded queue
has to decide which end to drop: this one drops the newest, keeps the oldest,
and counts what it dropped in the session's `pending` field, because a message
that disappears without a count is the failure that is never noticed. And the
will is published only on an end the client did not choose — a `cut` or a
keep-alive expiry, never a DISCONNECT — and it leaves the session as it is
handed back, so an abnormal end cannot fire a promise a previous connection
already paid.

    SESSION_KEYS             the ten fields of a session record, in order
    QUEUE_MAX               8: how many messages a session may hold for its client
    KEEP_ALIVE_NUMERATOR    3   the margin a broker gives a client: the deadline is
    KEEP_ALIVE_DENOMINATOR  2   keep_alive * 3 // 2, which is k + k // 2 ticks
    deadline_from           (keep_alive) -> the ticks a client may be silent for
    Sessions.attach         (connect, stream, tick) -> (session, session_present)
    Sessions.detach         (client_id, reason, tick) -> the will to publish, or None
    Sessions.touch          (client_id, tick) -> the session, with last_seen moved
    Sessions.expired        (tick) -> the clients whose keep-alive has run out
    Sessions.queue_for      (client_id, publish) -> True if queued, False if not
    Sessions.take_queued    (client_id) -> the queued messages, oldest first, cleared
    Sessions.sessions       () -> the sessions held, in the order they were attached

A session is a dict of plain values — a client id, two numbers, the will or
`None`, the stream's id or `None`, a set of subscriptions, the queue, and the two
ticks — so two runs of one scenario compare with `==` and the capstone's state is
a dict like every other state in this course. `stream` is the **id** the
transport handed out, not the stream: a record that held a live object could not
be compared, and it would keep the socket alive after the socket is over.

The reason a connection ends is one of three words: `closed` when both ends
agreed (the client sent a DISCONNECT), `cut` when nobody did, and `expired` when
the keep-alive ran out. The first is `streams.CLOSED` and the second
`streams.CUT`, because they are the transport's own account of what happened to
the stream; anything else is refused by name.

DESIGN DECISION — why is the session a record that survives the connection, and
not a property of the connection?
Because three of its four fields are promises about a future the connection is
not part of. A subscription is a standing order: the client asked to be told
about a topic, not to be told while a particular socket is open. A queued message
is owed to the subscription and not to the socket, which is why it is queued
rather than dropped when the socket goes. And the will is a promise about what
happens *after* an abnormal end — a will that died with its connection would be
a promise the broker never had to keep. What the connection genuinely owns is the
stream id, and that is the one field that is `None` while the client is away.

DESIGN DECISION — why does a clean start answer 0 even when the broker holds the
client's old session?
Because the present flag is not a report about the broker's table, it is a report
about what the client's CONNECT resumed, and a clean start resumes nothing — the
old record is thrown away in the same call. A broker that answered 1 there would
tell the client that subscriptions it just discarded are in force, and the client
would go on receiving things it did not ask for on a session it asked to be
fresh. The flag is the first thing a client reads about its own session, and it
is the only thing it can read.

DESIGN DECISION — why does a full queue drop the newest message and count it,
rather than drop the oldest?
Because the queue is a promise in an order. The messages already in it are the
ones the client is owed first, and a client that reconnects has to see the old
ones before the new ones or the order it subscribed to is not the order it hears.
A queue that dropped its oldest message to make room would be choosing a message
nobody is waiting for over one the client has not seen — and it would do it
silently, since the message it drops is exactly the one that was about to be
delivered. Dropping the newest is visible in the count (`pending`) and costs only
the message that arrived when the client was already behind.

DESIGN DECISION — why is the will cleared when it fires, and why does it belong
to the connection rather than to the client?
Because a will is a promise with exactly one payment. If the session kept it, the
next abnormal end — of a connection the client may have made with no will at all
— would publish the same message again, and a broker that publishes a dead
client's farewell twice is indistinguishable from one that publishes it once for
the wrong reason. So it leaves the session as it is handed to the caller, and a
new CONNECT replaces it with whatever that connection asked for: the will is what
*this* connection asked the broker to do if it vanished, and a clean DISCONNECT
deletes it just as firmly.

DESIGN DECISION — why is the deadline `keep_alive + keep_alive // 2`, and why is
a keep-alive of 0 no deadline at all?
Because the alternative is a broker that disconnects healthy clients. A client
sends its last packet, a tick passes, and the broker's `k`-tick rule has already
expired a client whose next packet is one tick late — the two sides are not the
same clock. Half again is the margin the spec asks for. Zero is the other end of
the same arithmetic: a client that asks for no keep-alive has a deadline of 0,
and a deadline of 0 read literally would end the session on the tick it was
attached, when the client has been silent for exactly 0 ticks. So a deadline of 0
means there is no deadline, and `expired` never names that client.

TODO: implement
"""

SESSION_KEYS = ("client_id", "clean_start", "keep_alive", "will", "stream",
                "subscriptions", "pending", "queue", "started_at", "last_seen")

QUEUE_MAX = 8

KEEP_ALIVE_NUMERATOR = 3
KEEP_ALIVE_DENOMINATOR = 2


def deadline_from(keep_alive):
    """The ticks a client may be silent for: `keep_alive + keep_alive // 2`.

    The margin is half again the keep-alive the client asked for, written as a
    ratio of two ints because this course has no floats. Zero is a client that
    asked for no keep-alive, and its deadline is 0. A `bool` or a negative
    keep-alive is refused by name: one is not a count and the other cannot come
    off a two-byte field.
    """
    raise NotImplementedError("stage 8: implement deadline_from()")


class Sessions:
    """The broker's sessions, one record per client in the order it attached.

    A record is `SESSION_KEYS` and nothing else: the client id, how the
    connection that opened it began, its keep-alive and its will, the stream id
    while it is connected and `None` while it is not, its subscriptions, the
    count of messages dropped for want of room, the messages queued for it
    oldest first, and the ticks the session started and its client last spoke.
    """

    def attach(self, connect, stream, tick):
        """Take `connect` on the stream `stream` at `tick`, as `(session, present)`.

        `connect` is a parsed CONNECT and `stream` is the id the transport
        handed out. A clean start of 1 throws away whatever the broker holds for
        this client id and answers present 0; a clean start of 0 resumes the
        held record and answers 1, or begins one and answers 0. A resumed record
        keeps its subscriptions, its queue and the tick it started at, and takes
        this connection's keep-alive, will and stream.
        """
        raise NotImplementedError("stage 8: implement Sessions.attach()")

    def detach(self, client_id, reason, tick):
        """End `client_id`'s connection as `reason` at `tick`, as the will owed.

        The reason is `streams.CLOSED` for an end both sides agreed to,
        `streams.CUT` for one nobody did, or `"expired"` for a keep-alive that
        ran out; anything else is refused by name. The will is answered once and
        leaves the session, a clean end answers `None` and clears it too, and a
        client this table has never seen answers `None`. An `"expired"` end is
        refused unless the deadline really has passed.
        """
        raise NotImplementedError("stage 8: implement Sessions.detach()")

    def touch(self, client_id, tick):
        """`client_id`'s session with `last_seen` moved to `tick`, or `None`.

        Every packet a client sends touches its session, a ping included: the
        keep-alive is a promise about the connection, so what moves it is the
        last packet and not the last publish.
        """
        raise NotImplementedError("stage 8: implement Sessions.touch()")

    def expired(self, tick):
        """The clients whose keep-alive has run out by `tick`, in attach order.

        The question and not the act: the caller that wants the will published
        follows with `detach(client, "expired", tick)`. Only a session that is
        still attached can have gone quiet, and a client that has spoken —
        `touch` is what says so — is not named.
        """
        raise NotImplementedError("stage 8: implement Sessions.expired()")

    def queue_for(self, client_id, publish):
        """Queue `publish` for `client_id`, as `True`, or answer `False`.

        `False` for a QoS 0 message (nothing was promised, so nothing is kept),
        for a queue that is full — the message that has just arrived is dropped
        and counted in the session's `pending`, and what is already queued is
        untouched — and for a client with no session to queue for.
        """
        raise NotImplementedError("stage 8: implement Sessions.queue_for()")

    def take_queued(self, client_id):
        """The messages queued for `client_id`, oldest first, and the queue emptied.

        Handed over once: the session is left with an empty queue, so the next
        resume cannot deliver the same message twice. `pending` is the count of
        what was dropped, not of what was taken, and it is left alone.
        """
        raise NotImplementedError("stage 8: implement Sessions.take_queued()")

    def sessions(self):
        """The sessions held, in the order their clients were attached.

        The records themselves: a session is live state the broker writes to,
        while the transport's log is an account and is copied on the way out.
        """
        raise NotImplementedError("stage 8: implement Sessions.sessions()")
