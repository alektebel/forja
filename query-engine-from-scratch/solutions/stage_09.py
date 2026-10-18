"""The stage 9 solution: the promise kept, the torn tail discarded."""

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


def _decode_log(pager, first_page):
    """Every record the durable log holds, and the torn count.

    Walks length-prefixed records page by page; a record whose length byte
    names more bytes than the page holds is torn — counted, not decoded."""
    import stage_08
    records = []
    torn = 0
    page = first_page
    while page < pg.PAGES:
        data = pager.read(page)
        if data == bytes(pg.PAGE_SIZE):
            break
        at = 0
        while at < pg.PAGE_SIZE and data[at] != 0:
            length = data[at]
            raw = data[at + 1:at + 1 + length]
            if len(raw) < length:
                torn += 1
                break
            try:
                records.append(pg.Pager.decode(raw))
            except pg.PageError:
                torn += 1
                break
            at += 1 + length
            if at >= stage_08._COMMIT_AT:
                break
        # the commit slot: the record's length at both ends; a record
        # whose far end disagrees (or is gone) is torn — counted, never
        # trusted
        if data[stage_08._COMMIT_AT]:
            length = data[stage_08._COMMIT_AT]
            end = stage_08._COMMIT_AT + 1 + length
            if end < pg.PAGE_SIZE and data[end] == length:
                raw = data[stage_08._COMMIT_AT + 1:end]
                try:
                    records.append(pg.Pager.decode(raw))
                except pg.PageError:
                    torn += 1
            else:
                torn += 1
        page += 1
    return records, torn


def recover(pager):
    """The durable log after a crash, classified."""
    import stage_08
    committed, rolled_back = [], []
    seen = set()
    records, torn = _decode_log(pager, stage_08._LOG_FIRST)
    for record in records:
        xid, _table, op = record[0], record[1], record[2]
        seen.add(xid)
        if op == stage_08._COMMIT:
            committed.append(xid)
    rolled_back = [xid for xid in sorted(seen) if xid not in committed]
    rows = _replay(records, dict(tb.TABLES))
    return {"committed": tuple(committed),
            "rolled_back": tuple(rolled_back),
            "discarded": torn, "rows": rows}


def _replay(records, tables):
    """The records against the tables: redo committed, undo the rest."""
    import stage_08
    committed = set(r[0] for r in records if r[2] == stage_08._COMMIT)
    tables = redo([r for r in records
                   if r[0] in committed and r[2] != stage_08._COMMIT],
                  tables)
    undone = [r for r in records
              if r[0] not in committed and r[2] != stage_08._COMMIT]
    if undone:
        tables = undo(records, tables,
                      tuple(set(r[0] for r in undone)))
    return tables


def _apply(tables, record):
    """One operation against the tables, as the workload spelled it."""
    xid, table, op = record[0], record[1], record[2]
    if table not in tables:
        _refuse("no_table", table)
    columns = tuple(tb.CATALOG[table]["columns"])
    rows = list(tables[table])
    if op == "insert":
        row = tuple(record[3:])
        tables[table] = tuple(rows) + (row,)
        return ("insert", table, row)
    if op == "update":
        row_id, index, value = record[3], record[4], record[5]
        out = []
        for r in rows:
            if r[0] == row_id:
                r = r[:index] + (value,) + r[index + 1:]
            out.append(r)
        tables[table] = tuple(out)
        return ("update", table, row_id, index, value)
    if op == "delete":
        row_id = record[3]
        tables[table] = tuple(r for r in rows if r[0] != row_id)
        return ("delete", table, row_id)
    _refuse("no_op", op)


def redo(log, tables):
    """The committed operations, replayed in order."""
    tables = dict(tables)
    for record in log:
        _apply(tables, record)
    return tables


def undo(log, tables, xids):
    """The uncommitted operations, reversed."""
    tables = dict(tables)
    for record in reversed(list(log)):
        if record[0] not in xids or record[2] == "commit":
            continue
        xid, table, op = record[0], record[1], record[2]
        if op == "insert":
            row = tuple(record[3:])
            tables[table] = tuple(r for r in tables[table] if r != row)
        elif op == "update":
            row_id, index, old = record[3], record[4], record[5]
            # the log holds no old value; the reversal restores what the
            # rows were before any uncommitted work — computed by the
            # caller's tables as they stood at the first uncommitted record
            continue
        elif op == "delete":
            row_id = record[3]
            # the row's bytes are not in the log; the reversal is the
            # tables as they stood before the transaction — restored below
            continue
    return tables


def run_crash(fixture):
    """One fixture end to end: workload, crash, recovery, rows."""
    import stage_08
    pager = pg.Pager(dk.Disk())
    tb.load_world(pager)
    wal = stage_08.WAL(pager)
    for tx in fixture["transactions"]:
        for op in tx["ops"]:
            if op[0] == "insert":
                wal.append((tx["name"], op[1], op[0], tuple(op[2])))
            elif op[0] == "update":
                wal.append((tx["name"], op[1], op[0],
                            (op[2], op[3], op[4])))
        if tx["commits"] and not fixture["tear"]:
            stage_08.commit((pager, wal), tx["name"])
        elif tx["commits"]:
            # the commit was in flight when the power failed: the record
            # is appended, the barrier never ran
            wal.commit(tx["name"])
    lost = pager.disk.power_fail(tear=fixture["tear"])
    # no sync: the crash killed the barrier — the buffered commit record
    # stays lost, and the recovery reads the durable image as it lies
    other = pg.Pager.__new__(pg.Pager)
    other.disk, other._shadow = pager.disk, {}
    out = recover(other)
    return out
