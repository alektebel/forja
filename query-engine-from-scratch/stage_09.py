"""Query Engine From Scratch — stage 9: The recovery: redo, undo, discard.

The commit made a promise; the recovery is how the promise survives the
power cut. `recover` reads the durable log after a crash and answers
RECOVER_KEYS: the committed transactions — those with a durable commit
record —, the rolled-back ones (started, never committed), and the discarded
bytes: the torn tail, whose records are *never trusted*. `redo` replays the
committed transactions' operations against the tables; `undo` reverses the
uncommitted ones' — a transaction that wrote rows but never committed wrote
rows that must vanish. The record's `rows` is the recovered state, and the
world's `CRASH_SCHEDULE` pins what that must be.

`run_crash` runs one fixture end to end — the workload through a real WAL
(stage 8's), the crash through a real `power_fail` with or without a tear,
the recovery over the durable image — and the check holds each fixture's
answer against the fixture's own committed/uncommitted split.

DESIGN DECISION — Why does `recover` classify *transactions* rather than
operations?
Because the unit of durability is the transaction: a commit record makes
every record before it durable, and its absence makes none of them count.

DESIGN DECISION — Why does `undo` reverse operations rather than restore a
snapshot?
Because the log is the only witness: the uncommitted operations are
precisely enumerated — each insert undone by removal. The reversal is
arithmetic over the log, not a second copy of the world.

DESIGN DECISION — Why is a torn tail *discarded* rather than retried?
Because the torn bytes are the crash's own signature: a record whose length
byte says one thing and whose bytes say another is not a record the disk
owes anyone. The recovery keeps what the log can prove and throws the rest
away.
"""

import disk as dk
import pages as pg
import tables as tb
import stage_08 as _s8

RECOVER_KEYS = ("committed", "rolled_back", "discarded", "rows")

#: the recovered tables' starting point: an empty world, the names the
#: catalog pins
_EMPTY = {"orders": (), "items": (), "users": (), "events": ()}


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, *names):
    raise QueryError("%s: %s" % (reason, ", ".join(repr(n) for n in names)))


def _read_log(pager):
    """Every complete record off the log's pages, in log order, and the
    bytes the format refused — the torn tail's count."""
    records = []
    torn = 0
    page = _s8._LOG_START
    while page < pg.PAGES:
        raw = pager.read(page)
        count = raw[0]
        if count == 0:
            break
        at = 1
        ok = True
        for _ in range(count):
            rec_len = raw[at]
            chunk = raw[at + 1:at + 1 + rec_len]
            try:
                records.append(tuple(pg.Pager.decode(chunk)))
            except (pg.PageError, IndexError):
                ok = False
                torn += 1
                break
            at += 1 + rec_len
        if not ok:
            break
        page += 1
    return tuple(records), torn


def recover(pager):
    """The durable log, classified: committed, rolled back, discarded.

    Reads every complete record off the log's pages; a transaction is
    committed when its durable commit record is present, rolled back when
    it started and never committed, and the torn tail — bytes the format
    refuses — is discarded, never trusted."""
    records, torn = _read_log(pager)
    started = []
    committed = []
    for rec in records:
        xid = rec[0]
        if xid not in started:
            started.append(xid)
        if rec[2] == "commit":
            committed.append(xid)
    rolled = tuple(x for x in started if x not in committed)
    return {"committed": tuple(committed), "rolled_back": rolled,
            "discarded": torn, "rows": dict(_EMPTY), "_log": records}


def _apply(record, tables):
    """One log record's effect on the recovered tables — insert or update;
    anything else is an op the log does not speak."""
    (xid, table, op, *rest) = record
    rows = tables.get(table)
    if rows is None:
        _refuse("no_table", table)
    if op == "insert":
        tables[table] = rows + (tuple(rest),)
    elif op == "update":
        (key, new_value, col_name) = rest
        columns = tb.CATALOG[table]["columns"]
        if col_name not in columns:
            _refuse("no_column", col_name, table)
        ci = columns.index(col_name)
        out = []
        hit = False
        for row in rows:
            if row[0] == key:
                hit = True
                lst = list(row)
                lst[ci] = new_value
                out.append(tuple(lst))
            else:
                out.append(row)
        tables[table] = tuple(out)
        return hit
    else:
        _refuse("no_op", op)
    return True


def redo(log, tables):
    """The committed operations, replayed against the tables.

    `log` is recover's classification; `tables` is the recovered state
    being built. Answers the tables the redo touched, with the committed
    operations' effects in log order."""
    for rec in log["_log"]:
        if rec[0] in log["committed"] and rec[2] != "commit":
            _apply(rec, tables)
    return tables


def undo(log, tables, xids):
    """The uncommitted operations, reversed out of the tables.

    `xids` are the rolled-back transactions; answers the tables without
    their effects."""
    for rec in reversed(log["_log"]):
        if rec[0] in xids and rec[2] == "insert":
            rows = tables.get(rec[1])
            if rows is None:
                _refuse("no_table", rec[1])
            tables[rec[1]] = tuple(r for r in rows if r != tuple(rec[3:]))
        elif rec[0] in xids and rec[2] == "update":
            # the update record carries no before-image — an undo that
            # cannot name the old value is an undo that cannot run
            _refuse("no_before_image", rec)
    return tables


def run_crash(fixture):
    """One fixture end to end: workload, crash, recovery, rows.

    `fixture` is a `CRASH_SCHEDULE` entry. Runs the fixture's transactions
    through a real WAL (stage 8's), crashes the disk the way the fixture
    says (`power_fail(tear=fixture["tear"])`), recovers over the durable
    image, and answers RECOVER_KEYS."""
    d = dk.Disk()
    pager = pg.Pager(d)
    wal = _s8.WAL(pager)
    for txn in fixture["transactions"]:
        for op in txn["ops"]:
            (op, table, *rest) = op
            wal.append(_txn_id(txn["name"]), table, op, *rest)
        if txn["commits"]:
            _s8.commit({"wal": wal}, _txn_id(txn["name"]))
        else:
            wal.pager.sync()
    d.power_fail(tear=fixture["tear"])
    log = recover(pager)
    tables = dict(_EMPTY)
    redo(log, tables)
    undo(log, tables, log["rolled_back"])
    return {"committed": log["committed"],
            "rolled_back": log["rolled_back"],
            "discarded": log["discarded"], "rows": tables}


def _txn_id(name):
    """The fixture's transaction name as its xid: t1 -> 1."""
    return int(name[1:])
