"""stage_09.py — the report, and the world's own record.

Sandbox & Capabilities From Scratch — stage 9: The report, and the world's own record

The run wrote one audit line per call; the world wrote its own record of what it
was actually made to touch. This stage is the only place the two are compared,
and the comparison is the whole point: a report is **recomputed from the lines**,
and then *decided against the world* — `VFS.log()`, `Wire.dialled()` and
`Vault.reads()` — so "what did it touch" is a proof rather than a claim. Twelve
counters come off the lines and the meter; the cross-check comes off the world;
and a disagreement refuses, naming the line and the record it disagrees with. The
one walk that must never raise is `audit`, because a disagreement is a thing to
report, not a crash.

    REPORT_KEYS   the twelve fields a report carries, in writing order
    ReportError   a report, an entry or a disagreement with the world this stage
                  refuses
    report        the twelve counters, recomputed from the lines and checked
                  against the world's own record
    touched       the sorted distinct targets the allowed entries name
    audit         the same walk, reporting the disagreement instead of raising
"""

from collections.abc import Mapping

import tools

from stage_01 import SandboxError
from stage_03 import inside
from stage_07 import AUDIT_KEYS, DECISIONS, REASONS

#: The twelve fields a report carries, in the order a report writes them.
REPORT_KEYS = ("principal", "calls", "allowed", "denied", "capabilities", "paths",
               "bytes", "hosts", "secrets", "cpu", "memory", "ticks")

#: The distance within which a name this stage does not have is assumed to be a
#: typo for one it does.
_NEAR = 2


class ReportError(SandboxError):
    """A report, an entry, or a disagreement with the world this stage refuses.

    The refusal names the offender: the index and the spelling of an entry this
    stage cannot read, or the line and the record the world and the lines
    disagree about. A disagreement with the world is a refusal and not a
    correction, because the report's numbers are supposed to prove the run, and a
    report that silently repaired a mismatch would be the very claim the course
    exists to make recomputable.
    """


def _levenshtein(left, right):
    """The edit distance between two short names, the plain way."""
    if left == right:
        return 0
    previous = list(range(len(right) + 1))
    for i, lchar in enumerate(left, 1):
        current = [i]
        for j, rchar in enumerate(right, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (0 if lchar == rchar else 1),
            ))
        previous = current
    return previous[-1]


def _near(name, known):
    """`" (did you mean 'x'?)"` for the closest known name, or `""`."""
    if not isinstance(name, str):
        return ""
    best, best_distance = None, _NEAR + 1
    for candidate in sorted(known):
        distance = _levenshtein(name, candidate)
        if distance < best_distance:
            best, best_distance = candidate, distance
    if best is None or best_distance > _NEAR:
        return ""
    return " (did you mean %r?)" % (best,)


def _entry(index, entry):
    """One audit entry, validated: a mapping over exactly `AUDIT_KEYS`."""
    if not isinstance(entry, Mapping):
        raise ReportError(
            "entry %d is not a mapping over AUDIT_KEYS, got %r"
            % (index, type(entry).__name__))
    for key in entry:
        if key not in AUDIT_KEYS:
            raise ReportError(
                "entry %d has no field %r%s: an entry carries exactly AUDIT_KEYS"
                % (index, key, _near(key, AUDIT_KEYS)))
    for key in AUDIT_KEYS:
        if key not in entry:
            raise ReportError(
                "entry %d omits %r: every key is always written, and an omitted "
                "field is a line a reader has to guess at" % (index, key))
    decision = entry["decision"]
    if decision not in DECISIONS:
        raise ReportError(
            "entry %d: the decision %r is not one of %s%s"
            % (index, decision, ", ".join(DECISIONS), _near(decision, DECISIONS)))
    reason = entry["reason"]
    if reason not in REASONS:
        raise ReportError(
            "entry %d: the reason %r is not one of %s%s"
            % (index, reason, ", ".join(REASONS), _near(reason, REASONS)))
    count = entry["bytes"]
    if isinstance(count, bool) or not isinstance(count, int):
        raise ReportError("entry %d: the bytes %r is not a byte count"
                          % (index, count))
    if count < 0:
        raise ReportError("entry %d: the bytes %r must not be negative"
                          % (index, count))
    return entry


def _validated(entries):
    """The entries, each read and checked, as a list a walk can index."""
    rows = []
    principal = None
    for index, entry in enumerate(entries):
        _entry(index, entry)
        if index == 0:
            principal = entry["principal"]
        elif entry["principal"] != principal:
            raise ReportError(
                "entry %d: the principal %r is not the run's %r"
                % (index, entry["principal"], principal))
        rows.append(entry)
    return rows


def _declaration(name):
    """The catalogue's declaration for a tool name, or `None`."""
    return tools.TOOLS.get(name)


def _kind(name):
    """The kind of thing a tool acts on, or `None` for a tool nobody has."""
    declaration = _declaration(name)
    return None if declaration is None else declaration["target_kind"]


def _caps(name):
    """The demand of a tool, or `()` for a tool nobody has."""
    declaration = _declaration(name)
    return () if declaration is None else tuple(declaration["capabilities"])


def _match_path(records, line):
    """The first record an allowed line's target and byte count agree with.

    A record that carries a length (`read`, `write`, `remove`) must agree with
    the line's own `bytes`; a `list` op does not, because a listing moves no
    bytes and the world's count for it is bookkeeping the line never claims.
    """
    for index, (op, path, count) in enumerate(records):
        if op != "list" and path == line["target"] and count == line["bytes"]:
            return index
    return None


def _path_only(records, path):
    """The first record at this path, whatever op it performed."""
    for index, (_op, name, _count) in enumerate(records):
        if name == path:
            return index
    return None


def _inside_any(process_lines, path):
    """Whether some allowed process line's target contains this log entry path.

    A process tool's target is the directory it was allowed to work in, and the
    component-wise test is stage 3's, so `cat` inside `/home/agent` is explained
    by a shell that named `/home/agent` and a touch of `/home/agent-other` is
    not — the same escape the jail exists to refuse.
    """
    for line in process_lines:
        try:
            if inside(line["target"], path):
                return True
        except SandboxError:
            continue
    return False


def _account(rows, vfs, wire, vault):
    """Every `(line, record)` pair the allowed lines and the world disagree on.

    One side of the pair is `None` when the disagreement has only one side: a
    record no line accounts for, or a line the record does not hold. An allowed
    path line accounts for one log entry at its target; a log entry no path line
    accounts for is explained by an allowed process line whose target contains
    it; a host line accounts for one dial of its host, and a dial no host line
    accounts for is explained by an allowed process line; and a handle the vault
    read is claimed either by the `secret`-kind line that named it or by a
    `none`-kind call (`env_dump`) that reads every handle at once.
    """
    out = []
    allowed = [entry for entry in rows if entry["decision"] == "allowed"]
    denied = [entry for entry in rows if entry["decision"] == "denied"]

    for line in allowed:
        if _kind(line["tool"]) is None:
            out.append((line, None))

    path_lines = [line for line in allowed if _kind(line["tool"]) == "path"]
    process_lines = [line for line in allowed if _kind(line["tool"]) == "process"]
    denied_paths = {line["target"] for line in denied
                    if _kind(line["tool"]) in ("path", "process")
                    and line["target"]}

    entries = list(vfs.log())
    for line in path_lines:
        index = _match_path(entries, line)
        if index is not None:
            entries.pop(index)
            continue
        index = _path_only(entries, line["target"])
        if index is None:
            out.append((line, None))
            continue
        op, path, count = entries.pop(index)
        if op != "list":
            out.append((line, (op, path, count)))
    for record in entries:
        _op, path, _count = record
        if path in denied_paths:
            out.append((None, record))
        elif _inside_any(process_lines, path):
            continue
        else:
            out.append((None, record))

    host_lines = [line for line in allowed if _kind(line["tool"]) == "host"]
    dialled = [host for host, _port in wire.dialled()]
    for line in host_lines:
        if line["target"] in dialled:
            dialled.remove(line["target"])
        else:
            out.append((line, None))
    for host in dialled:
        if process_lines:
            continue
        out.append((None, host))

    secret_lines = [line for line in allowed
                    if "secret:read" in _caps(line["tool"])]
    reads = list(vault.reads())
    claims_all = False
    unclaimed = []
    for line in secret_lines:
        if _kind(line["tool"]) == "none":
            claims_all = True
        elif line["target"] in reads:
            reads.remove(line["target"])
        else:
            unclaimed.append(line)
    if claims_all:
        reads = []
    for line in unclaimed:
        out.append((line, None))
    for handle in reads:
        out.append((None, handle))

    return out


def report(entries, *, meter, vfs, wire, vault):
    """The twelve counters, from the lines and the meter, checked against the world."""
    rows = _validated(entries)
    for index, entry in enumerate(rows):
        if entry["decision"] == "allowed" and _kind(entry["tool"]) is None:
            raise ReportError(
                "entry %d: the tool %r is not one this world has%s"
                % (index, entry["tool"], _near(entry["tool"], tools.TOOLS)))
    principal = rows[0]["principal"] if rows else ""
    allowed = [entry for entry in rows if entry["decision"] == "allowed"]
    capabilities = set()
    paths = []
    hosts = []
    secrets = 0
    total = 0
    for entry in allowed:
        declaration = tools.TOOLS[entry["tool"]]
        capabilities.update(declaration["capabilities"])
        kind = declaration["target_kind"]
        if kind == "path" or kind == "process":
            paths.append(entry["target"])
        elif kind == "host":
            hosts.append(entry["target"])
        if "secret:read" in declaration["capabilities"]:
            secrets += 1
        total += entry["bytes"]
    used = meter.used()
    out = {
        "principal": principal,
        "calls": len(rows),
        "allowed": len(allowed),
        "denied": len(rows) - len(allowed),
        "capabilities": tuple(sorted(capabilities)),
        "paths": tuple(sorted(paths)),
        "bytes": total,
        "hosts": tuple(sorted(hosts)),
        "secrets": secrets,
        "cpu": used["cpu"],
        "memory": used["memory"],
        "ticks": used["ticks"],
    }
    for line, record in _account(rows, vfs, wire, vault):
        if line is None:
            raise ReportError(
                "the world holds a record no allowed line accounts for: %r"
                % (record,))
        if record is None:
            raise ReportError(
                "the allowed line %r is not in the world's record" % (line,))
        raise ReportError(
            "the allowed line %r disagrees with the world's record %r"
            % (line, record))
    return out


def touched(entries):
    """The sorted distinct targets the allowed entries name, and nothing else."""
    rows = _validated(entries)
    return tuple(sorted({entry["target"] for entry in rows
                         if entry["decision"] == "allowed"}))


def audit(entries, *, vfs, wire, vault):
    """The same walk as `report`, reporting the disagreement instead of raising."""
    try:
        raw = list(entries)
    except TypeError:
        raw = []
    rows = []
    extra = []
    for index, entry in enumerate(raw):
        try:
            _entry(index, entry)
        except ReportError:
            extra.append((entry, None))
        else:
            rows.append(entry)
    missing = []
    for found, held in _account(rows, vfs, wire, vault):
        if found is None:
            missing.append((None, held))
        else:
            extra.append((found, held))
    return {"missing": tuple(missing), "extra": tuple(extra),
            "count": len(raw)}
