"""The stage 9 solution: the log's witness, and the torn tail thrown away."""

import disk as dk
import pages as pg
import tables as tb
import ops

RECOVER_KEYS = ("committed", "rolled_back", "discarded", "rows")


class QueryError(ValueError):
    """Raised for anything the *caller* of a stage got wrong."""


def _refuse(reason, what):
    """The one refusal: a reason word and the offender that earned it."""
    raise QueryError("%s: %r" % (reason, what))


#: the record count a full log page carries (the underfull tail is the
#: log's last page)
_RECORDS_FULL = 12


def _log_pages(pager):
    """Every complete record the durable log holds, in order.

    The log's meta page names the first data page; the chain runs while
    pages carry records. A page the format refuses ends the walk — the
    torn tail is *discarded*, and the count of records it would have held
    is the record's `discarded`."""
    records = []
    try:
        meta = pager.read(0)
    except pg.PageError:
        return records, 0
    first = meta[0]
    if not first:
        return records, 0
    page = first
    discarded = 0
    while page:
        try:
            rows = list(tb.page_rows(pager, page))
        except pg.PageError:
            # the torn tail: whatever bytes lie past the last complete
            # record are the crash's, not ours — one refused record, maybe
            # a page's worth; count what is visibly there and stop
            discarded += 1
            break
        records.extend(rows)
        if len(rows) < _RECORDS_FULL:
            page = 0        # an underfull page is the log's last
        else:
            page += 1
    return records, discarded


def recover(pager):
    """The durable log, classified."""
    records, discarded = _log_pages(pager)
    committed = []
    started = []
    for row in records:
        xid = row[0]
        if row[2] == "commit":
            if xid not in committed:
                committed.append(xid)
        elif xid not in started:
            started.append(xid)
    rolled_back = [xid for xid in started if xid not in committed]
    return {"committed": tuple(committed), "rolled_back": tuple(rolled_back),
            "discarded": discarded, "rows": None, "_log": records}


def _apply(tables, row, sign=1):
    """One log record applied to (or reversed out of) the recovered state.

    `row` is (xid, table, op, ...payload). An insert adds the row; an
    update sets one column; a delete removes the row with the payload's id.
    `sign=-1` reverses."""
    _xid, table, op = row[0], row[1], row[2]
    payload = tuple(row[3:])
    if table not in tables:
        _refuse("no_table", table)
    rows = list(tables[table])
    if op == "insert":
        if sign > 0:
            rows.append(payload)
        else:
            rows = [r for r in rows if r[0] != payload[0]]
    elif op == "update":
        if len(payload) == 3:
            rid, col, new = payload
            old = None
        else:
            rid, col, old, new = payload
        for i, r in enumerate(rows):
            if r[0] == rid:
                if sign < 0 and old is None:
                    _refuse("no_before_image", rid)
                rows[i] = r[:col] + (new if sign > 0 else old,) + r[col + 1:]
                break
    elif op == "delete":
        if sign > 0:
            rows = [r for r in rows if r[0] != payload[0]]
        else:
            rows.append(payload)
    else:
        _refuse("no_op", op)
    tables[table] = tuple(rows)
    return tables


def redo(log, tables):
    """The committed operations, replayed in log order."""
    committed = set(log["committed"])
    for row in log["_log"]:
        if row[0] in committed and row[2] != "commit":
            _apply(tables, row, sign=1)
    return tables


def undo(log, tables, xids):
    """The uncommitted operations, reversed out in reverse log order."""
    doomed = set(xids)
    for row in reversed(log["_log"]):
        if row[0] in doomed and row[2] != "commit":
            _apply(tables, row, sign=-1)
    return tables


def run_crash(fixture):
    """One fixture end to end: workload, crash, recovery, rows."""
    import stage_08
    d = dk.Disk()
    pager = pg.Pager(d)
    wal = stage_08.WAL(pager)
    tables = {"orders": (), "items": (), "users": (), "events": ()}
    for tx in fixture["transactions"]:
        for op in tx["ops"]:
            rest = tuple(op[2]) if len(op) == 3 else tuple(op[2:])
            wal.append((int(tx["name"][1:]), op[1], op[0])
                       + tuple(rest))
        if tx["commits"]:
            stage_08.commit({"wal": wal}, int(tx["name"][1:]))
    d.power_fail(tear=bool(fixture.get("tear")))
    recovered = {"orders": (), "items": (), "users": (), "events": ()}
    log = recover(pager)
    redo(log, recovered)
    undo(log, recovered, log["rolled_back"])
    rows = {"orders": recovered["orders"], "items": recovered["items"]}
    return {"committed": log["committed"],
            "rolled_back": log["rolled_back"],
            "discarded": log["discarded"], "rows": rows}
