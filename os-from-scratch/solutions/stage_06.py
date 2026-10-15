"""OS From Scratch — stage 6: The process, and the frame nobody gave back.

See `stage_06.py` for the surface and the design decisions; this is the kernel.
"""

import machine
import stage_03

USER_BASE = machine.PAGE_SIZE
STATES = ("ready", "running", "blocked", "zombie", "dead")
TASK_KEYS = ("pid", "ppid", "state", "space", "frames", "uid", "slots",
             "priority", "limits", "ticks", "exit_status")
DEFAULT_LIMITS = {"frames": 64, "children": 8, "ticks": 256}

#: what a fresh space with one page at `USER_BASE` costs: a root, a table, a page
_SPAWN_FRAMES = 3


class ProcessError(ValueError):
    """A process table this kernel cannot keep: a limit, a stranger, a zombie."""


def _count(value, what, low=0):
    """A non-negative int, or a refusal naming what was expected instead."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProcessError("%s is a non-negative int, not %r" % (what, value))
    if value < low:
        raise ProcessError("%s is %d, and the least it can be is %d"
                           % (what, value, low))
    return value


def _limits(limits):
    """A fresh copy of three limits, or a refusal naming the one that is wrong."""
    if limits is None:
        return dict(DEFAULT_LIMITS)
    if not isinstance(limits, dict):
        raise ProcessError("limits is a mapping of frames, children and ticks, "
                           "not %r" % (limits,))
    out = {}
    for resource in ("frames", "children", "ticks"):
        if resource not in limits:
            raise ProcessError("limits has no %s: a limit nobody can count is "
                               "not a limit" % (resource,))
        out[resource] = _count(limits[resource], "the %s limit" % (resource,))
    extra = sorted(set(limits) - set(out))
    if extra:
        raise ProcessError("limits has no resource called %s" % (", ".join(extra),))
    return out


def _vpage_of(vaddr):
    return vaddr // machine.PAGE_SIZE


def _first_level(vpage):
    return vpage // machine.ENTRIES


def new_task(pid, ppid=0, uid=0, limits=None):
    """A task with no space, no frames, no ticks and no exit status."""
    _count(pid, "a pid", 1)
    _count(ppid, "a ppid")
    _count(uid, "a uid")
    if ppid == pid:
        raise ProcessError("a task cannot be its own parent: pid %d and ppid %d"
                           % (pid, ppid))
    return {"pid": pid, "ppid": ppid, "state": "ready", "space": None,
            "frames": (), "uid": uid, "slots": {}, "priority": 0,
            "limits": _limits(limits), "ticks": 0, "exit_status": None}


def images(task):
    """The pages a task has mapped, as `(vpage, frame)`, sorted by `vpage`."""
    space = task.get("space")
    if space is None:
        return ()
    return tuple((vpage, frame) for vpage, frame, _flags in stage_03.mapped(space))



class Processes:
    """Every task this kernel knows, and the frames they hold."""

    def __init__(self, mmu, pool):
        """A table with no tasks, borrowing the machine's walk and the pool."""
        if mmu is None or pool is None:
            raise ProcessError("a process table needs a walk and a pool, not "
                               "%r and %r" % (mmu, pool))
        self.mmu = mmu
        self.pool = pool
        self.tasks = {}
        self.next_pid = 1
        self.events = []

    # ---- the ledger's bookkeeping -----------------------------------------

    def _record(self, op, pid, frames):
        self.events.append({"op": op, "pid": pid, "frames": frames,
                            "free": self.pool.free_count()})
        return None

    def _own(self, task, what):
        """The table's own task for this argument, or a refusal."""
        if not isinstance(task, dict) or task.get("pid") not in self.tasks:
            raise ProcessError("%s is not a task this table knows: %r"
                               % (what, task))
        mine = self.tasks[task["pid"]]
        if mine is not task:
            raise ProcessError("%s is a copy of task %d, not the task itself"
                               % (what, task["pid"]))
        return mine

    def _admit_frames(self, task, want, what):
        """Refuse before a frame moves: the limit first, then the pool."""
        limit = task["limits"]["frames"]
        held = len(task["frames"])
        if held + want > limit:
            raise ProcessError("%s needs %d frame%s and task %d may hold %d of "
                               "its %d: %d are already held"
                               % (what, want, "" if want == 1 else "s",
                                  task["pid"], limit, limit, held))
        free = self.pool.free_count()
        if want > free:
            raise ProcessError("%s needs %d frame%s and the pool has %d free"
                               % (what, want, "" if want == 1 else "s", free))
        return None

    def _tables_covering(self, space):
        """The first-level indices this space already has a table for."""
        base = machine.addr_of(space["root"])
        out = set()
        for index in range(machine.ENTRIES):
            raw = int.from_bytes(self.mmu.ram.read(base + index * 8, 8), "little")
            if raw and machine.flags_of_entry(raw) & machine.PRESENT:
                out.add(index)
        return out

    # ---- the acts ---------------------------------------------------------

    def spawn(self, ppid=0, uid=0, limits=None):
        """A fresh task with a fresh space and one page mapped at `USER_BASE`."""
        parent = None
        if ppid != 0:
            parent = self.tasks.get(ppid)
            if parent is None:
                raise ProcessError("spawn of a task of pid %r: this table has "
                                   "no such task" % (ppid,))
            self._refuse_zombie(parent, "spawn")
            self._count_children(parent, "spawn")
        task = new_task(self.next_pid, ppid=ppid, uid=uid, limits=limits)
        self._admit_frames(task, _SPAWN_FRAMES, "a new task")
        space = stage_03.new_space(self.mmu, self.pool)
        page = self.pool.alloc(1)[0]
        stage_03.map_page(self.mmu, self.pool, space, USER_BASE, page,
                          machine.WRITE | machine.USER)
        task["space"] = space
        task["frames"] = stage_03.space_frames(space)
        self.tasks[task["pid"]] = task
        self.next_pid += 1
        self._record("spawn", task["pid"], len(task["frames"]))
        return task

    def fork(self, parent):
        """A deep copy of a task: every mapped page copied into a fresh frame."""
        parent = self._own(parent, "the parent of a fork")
        self._refuse_zombie(parent, "fork")
        self._count_children(parent, "fork")
        child = new_task(self.next_pid, ppid=parent["pid"], uid=parent["uid"],
                         limits=dict(parent["limits"]))
        child["slots"] = dict(parent["slots"])
        child["priority"] = parent["priority"]
        self._admit_frames(child, len(parent["frames"]), "a fork")
        child["space"] = self._copy_space(parent["space"])
        child["frames"] = stage_03.space_frames(child["space"])
        self.tasks[child["pid"]] = child
        self.next_pid += 1
        self._record("fork", child["pid"], len(child["frames"]))
        return child

    def exec(self, task, pages=1):
        """A task with `pages` fresh frames at `USER_BASE` and up, in order."""
        task = self._own(task, "the task of an exec")
        self._refuse_zombie(task, "exec")
        _count(pages, "a page count", 1)
        if USER_BASE + pages * machine.PAGE_SIZE > stage_03.ADDRESS_WIDTH:
            raise ProcessError("exec of %d pages reaches past the address space "
                               "(%d pages fit above %#x)"
                               % (pages, stage_03.ADDRESS_WIDTH // machine.PAGE_SIZE - 1,
                                  USER_BASE))
        old = images(task)
        fresh_vpages = [_vpage_of(USER_BASE) + index for index in range(pages)]
        fresh_levels = {_first_level(vpage) for vpage in fresh_vpages}
        tables = self._tables_covering(task["space"])
        new_tables = len(fresh_levels - tables)
        after = 1 + len(tables | fresh_levels) + pages
        limit = task["limits"]["frames"]
        if after > limit:
            raise ProcessError("an exec of %d page%s needs %d frames and task "
                               "%d may hold %d of its %d"
                               % (pages, "" if pages == 1 else "s", after,
                                  task["pid"], limit, limit))
        if pages + new_tables > self.pool.free_count() + len(old):
            raise ProcessError("an exec of %d page%s needs %d frame%s and the "
                               "pool has %d free once the %d it releases come "
                               "back" % (pages, "" if pages == 1 else "s",
                                         pages + new_tables,
                                         "" if pages + new_tables == 1 else "s",
                                         self.pool.free_count(), len(old)))
        for vpage, frame in old:
            stage_03.unmap_page(self.mmu, task["space"], vpage * machine.PAGE_SIZE)
            self.pool.free(frame)
        for vpage in fresh_vpages:
            frame = self.pool.alloc(1)[0]
            stage_03.map_page(self.mmu, self.pool, task["space"],
                              vpage * machine.PAGE_SIZE, frame,
                              machine.WRITE | machine.USER)
        task["frames"] = stage_03.space_frames(task["space"])
        self._record("exec", task["pid"], len(task["frames"]))
        return task

    def exit(self, task, status=0):
        """End a task: release every frame it holds, and leave it a zombie."""
        task = self._own(task, "the task of an exit")
        self._refuse_zombie(task, "exit")
        stage_03.free_space(self.mmu, self.pool, task["space"])
        task["space"] = None
        task["frames"] = ()
        task["state"] = "zombie"
        task["exit_status"] = status
        for other in self.tasks.values():
            if other["ppid"] == task["pid"]:
                other["ppid"] = 0
        self._record("exit", task["pid"], 0)
        return task

    def wait(self, parent, pid=None):
        """Reap a zombie child, or say that there is nothing to reap yet."""
        parent = self._own(parent, "the parent of a wait")
        if pid is None:
            waiting = self.children(parent)
            if not waiting:
                raise ProcessError("task %d waited for any child and has none: "
                                   "a task with no children can never be woken"
                                   % (parent["pid"],))
            for child_pid in waiting:
                if self.tasks[child_pid]["state"] == "zombie":
                    pid = child_pid
                    break
            else:
                self._record("wait", parent["pid"], len(parent["frames"]))
                return {"blocked": True}
        else:
            _count(pid, "a pid")
            if pid not in self.children(parent):
                raise ProcessError("task %d waited for pid %r, which is not its "
                                   "child" % (parent["pid"], pid))
            if self.tasks[pid]["state"] != "zombie":
                self._record("wait", parent["pid"], len(parent["frames"]))
                return {"blocked": True}
        child = self.tasks.pop(pid)
        self._record("wait", parent["pid"], len(parent["frames"]))
        self._record("reap", child["pid"], 0)
        return {"reaped": child["pid"], "status": child["exit_status"]}

    # ---- the reads --------------------------------------------------------

    def children(self, task):
        """The pids of a task's children, ascending, zombies included."""
        task = self._own(task, "the task whose children were asked for")
        return tuple(sorted(pid for pid, other in self.tasks.items()
                            if other["ppid"] == task["pid"]))

    def get(self, pid):
        """The task with this pid, or `None` — the table's own task, not a copy."""
        _count(pid, "a pid")
        return self.tasks.get(pid)

    def ledger(self):
        """`{"frames_held": {pid: n}, "free": pool's count, "tasks": n}`."""
        return {"frames_held": {pid: len(task["frames"])
                                for pid, task in sorted(self.tasks.items())},
                "free": self.pool.free_count(),
                "tasks": len(self.tasks)}

    def log(self):
        """Every act this table performed, in order, as dicts."""
        return tuple(self.events)

    # ---- the two refusals every act shares --------------------------------

    def _refuse_zombie(self, task, what):
        if task["state"] in ("zombie", "dead"):
            raise ProcessError("%s of task %d: it is %s, and the frames that "
                               "would be released again are already gone"
                               % (what, task["pid"], task["state"]))
        return None

    def _count_children(self, parent, what):
        limit = parent["limits"]["children"]
        have = len(self.children(parent))
        if have >= limit:
            raise ProcessError("%s of task %d: it already has %d children and "
                               "may have %d" % (what, parent["pid"], have, limit))
        return None

    def _copy_space(self, parent_space):
        """A fresh space holding a private copy of every page the parent maps."""
        space = stage_03.new_space(self.mmu, self.pool)
        for vpage, frame, flags in stage_03.mapped(parent_space):
            fresh = self.pool.alloc(1)[0]
            self.mmu.ram.write_frame(fresh, self.mmu.ram.frame(frame))
            stage_03.map_page(self.mmu, self.pool, space, vpage * machine.PAGE_SIZE,
                              fresh, flags)
        return space
