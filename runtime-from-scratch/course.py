"""Runtime From Scratch — a runtime's memory system over a provided heap.

Ten graded stages over a machine provided as data (`bytecode.py`, `assembler.py`,
`heap.py`), the way the rest of this repository teaches a mechanism: the world is
data and holds the ground truth, a stage is a file you write, a check is what
happens to it, and every promise the collector makes is on show because a heap is
what a memory system looks like from the outside.

What the course is about, in one line: *a program's objects become a ledger, and
every step of that becoming is a collector you have to get right.*

    the dispatch: decode, execute, count
    the value stack, and what each opcode costs
    control flow: the jumps, and a program's step total
    the heap: objects, references, and the ledger
    mark-sweep: the wavefront, and nothing reachable freed
    reference counting, and the cycle it cannot free
    tri-colour incremental marking, and the gray worklist
    the write barrier, and the remembered set
    generations: the nursery, promotion, and what survives
    the copying collector, forwarding, and the audit

The house laws hold here (`.g8-dev/CONTRACT.md` §1): standard library only, no
`float` literal, no `random`, no clock, no thread, no socket, and no process of
your own — and, this course's own additions, the world is read-only: a stage never
writes the heap's or the programs' own tables (`bytecode.PROGRAMS` and `Module` are
frozen data), every allocation goes through the provided heap, and nothing
reachable is ever freed. The heap is never lied to: `heap.stats()` is the ledger,
and a stage's every claim has to survive a re-read of it.

What the course does **not** do is call anything real. There is no `malloc(3)`
behind `heap.allocate`, no virtual memory behind a generation, and no scanning
threads behind the incremental mark: the collector is a loop, the pause is a
number, a leak is a record rather than a hang, and the whole course is
deterministic enough that two runs of the same program against the same heap
produce the same ledger.

    python3 codecraft/cli.py run runtime-from-scratch
"""

from codecraft.api import stage

TITLE = "Runtime From Scratch"
DESCRIPTION = ("A runtime's memory system over a provided heap: a program's objects "
               "become a ledger, and every promise a collector makes is on show. "
               "Ten stages that decode and execute opcodes, price every one against "
               "the world's own step pins, take the jumps, build the heap's shapes "
               "on demand, run the mark-sweep wavefront, admit what reference "
               "counting cannot free, cut the mark into budgeted tri-colour slices, "
               "guard the black-stores-white window with a write barrier, collect "
               "the nursery and promote its survivors, copy the reachable to the "
               "other semispace through forwarding, and audit every stage's numbers "
               "against the ledger — with the world read-only, nothing reachable "
               "freed, and no float and no clock anywhere.")

LEVEL = "advanced"
ORDER = 33


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S1_DISPATCH_KEYS = ("stack", "output", "steps")

    S1_PUBLIC = ("DISPATCH_KEYS", "RUNNABLE", "FRAME_OPS", "decode",
                 "execute", "run")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        """The refusal `call` must raise, or the mistake named."""
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001 — a wrong exception is a problem
            raise AssertionError("%s raised %r, not %s"
                                 % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse"
                             % (what, got))

    def _s1_surface(s):
        """The stage's public surface is exactly the five names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or getattr(value, "__module__", None) in (
                    "os",):
                continue
            if name in ("bytecode", "bc"):
                continue
            public.add(name)
        assert public == set(S1_PUBLIC), (
            "the stage's public surface is %s and §4.0 pins %s"
            % (", ".join(sorted(public)), ", ".join(sorted(S1_PUBLIC))))
        assert s.DISPATCH_KEYS == S1_DISPATCH_KEYS, (
            "DISPATCH_KEYS is %r and §4.0 pins %r" % (s.DISPATCH_KEYS,
                                                      S1_DISPATCH_KEYS))
        assert all(callable(getattr(s, n)) for n in ("decode", "execute", "run")), (
            "decode, execute and run are the stage's three ways in")

    def _s1_constants(s, bc):
        """The stage's declared constants name the world's own facts."""
        assert s.RUNNABLE == ("arith", "branch", "countdown", "fib10"), (
            "RUNNABLE is %r; §4.0's four frame-free programs" % (s.RUNNABLE,))
        assert s.FRAME_OPS == (bc.OP_LOAD_NAME, bc.OP_STORE_NAME, bc.OP_CALL,
                               bc.OP_RETURN), (
            "FRAME_OPS is %r; the four frame operations" % (s.FRAME_OPS,))

    def _s1_decode(s, bc):
        """The pair at `ip`, and the two refusals that name what went wrong."""
        module = bc.PROGRAMS["branch"]["module"]
        op, arg = s.decode(module, 0)
        assert (op, arg) == module.code[0], (
            "decode(0) answered %r and the module holds %r"
            % ((op, arg), module.code[0]))


        _refuses(bc.BytecodeError, "ip past the code",
                 lambda: s.decode(module, len(module.code)),
                 names=("%d" % len(module.code),))
        _refuses(bc.BytecodeError, "negative ip",
                 lambda: s.decode(module, -1), names=("-1",))

    def _s1_arith(s, bc):
        """Every arithmetic and comparison opcode, deeper operand first."""
        def one(text, before):
            module = bc.PROGRAMS["arith"]["module"]
            stack = list(before)
            op, arg = module.code[0]  # unused; assemble fresh instead
            fresh = __import__("assembler").assemble(text)
            op, arg = fresh.code[0]
            nxt = s.execute(fresh, op, arg, stack)
            assert nxt is None, "%s answers %r; a non-jump answers None" % (
                bc.OP_NAMES[op], nxt)
            return stack

        assert one("LOAD_CONST 5\nHALT", []) == [5], "LOAD_CONST pushes"
        assert one("ADD\nHALT", [2, 3]) == [5], "ADD is deeper + top"
        assert one("SUB\nHALT", [2, 3]) == [-1], "SUB is deeper - top"
        assert one("MUL\nHALT", [2, 3]) == [6], "MUL is deeper * top"
        assert one("NEG\nHALT", [7]) == [-7], "NEG negates the top"
        assert one("EQ\nHALT", [3, 3]) == [1], "EQ answers 1 on equal"
        assert one("EQ\nHALT", [3, 4]) == [0], "EQ answers 0 on different"
        assert one("LT\nHALT", [2, 3]) == [1], "LT is deeper < top"
        assert one("LT\nHALT", [3, 2]) == [0], "LT answers 0 when deeper >= top"
        assert one("GT\nHALT", [3, 2]) == [1], "GT is deeper > top"
        assert one("NOT\nHALT", [0]) == [1], "NOT answers 1 on falsy"
        assert one("NOT\nHALT", [5]) == [0], "NOT answers 0 on truthy"
        assert one("POP\nHALT", [1, 2]) == [1], "POP drops the top"
        assert one("DUP\nHALT", [4]) == [4, 4], "DUP copies the top"
        assert one("PICK 0\nHALT", [4]) == [4, 4], "PICK 0 is DUP"
        assert one("PICK 2\nHALT", [9, 8, 7]) == [9, 8, 7, 9], (
            "PICK 2 copies the third from the top")
        assert one("ROT3\nHALT", [1, 2, 3]) == [2, 3, 1], (
            "ROT3 is (a, b, c) -> (b, c, a) reading bottom to top")

    def _s1_execute_refusals(s, bc):
        """The underflows, the bad PICK and the frame ops, each naming the offender."""
        def fresh(text):
            return __import__("assembler").assemble(text)

        _refuses(bc.BytecodeError, "ADD needs 2",
                 lambda: s.execute(fresh("ADD\nHALT"), bc.OP_ADD, None, [1]),
                 names=("ADD",))
        _refuses(bc.BytecodeError, "SUB needs 2",
                 lambda: s.execute(fresh("SUB\nHALT"), bc.OP_SUB, None, []),
                 names=("SUB",))
        _refuses(bc.BytecodeError, "ROT3 needs",
                 lambda: s.execute(fresh("ROT3\nHALT"), bc.OP_ROT3, None, [1, 2]),
                 names=("ROT3",))
        _refuses(bc.BytecodeError, "PICK",
                 lambda: s.execute(fresh("PICK 5\nHALT"), bc.OP_PICK, 5, [1]),
                 names=("PICK",))
        for op_name, op in (("LOAD_NAME", bc.OP_LOAD_NAME),
                            ("STORE_NAME", bc.OP_STORE_NAME),
                            ("CALL", bc.OP_CALL),
                            ("RETURN", bc.OP_RETURN)):
            _refuses(bc.BytecodeError, "frame operation",
                     lambda op=op: s.execute(fresh("HALT"), op, None, []),
                     names=(op_name,))

    def _s1_jumps(s, bc, asm):
        """The jumps answer their target; JUMP_IF_FALSE decides by the value."""
        module = asm.assemble("JUMP 3\nHALT\nHALT\nHALT\nHALT\n")
        assert s.execute(module, bc.OP_JUMP, 3, []) == 3, "JUMP answers the target"
        module = asm.assemble("HALT\nHALT\n")
        assert s.execute(module, bc.OP_JUMP_IF_FALSE, 1, [0]) == 1, (
            "JUMP_IF_FALSE answers the target on falsy")
        assert s.execute(module, bc.OP_JUMP_IF_FALSE, 1, [2]) is None, (
            "JUMP_IF_FALSE falls through on truth")
        assert s.execute(module, bc.OP_JUMP_IF_FALSE, 1, [0]) == 1
        assert s.execute(module, bc.OP_LOOP, 1, []) == 1, (
            "OP_LOOP jumps like JUMP")
        # HALT stops mid-code: the instructions after it never run
        module = asm.assemble("LOAD_CONST 1\nHALT\nLOAD_CONST 99\n")
        record = s.run(module)
        assert record["stack"] == (1,), (
            "HALT stops the loop: the stack is %r and the 99 never landed"
            % (record["stack"],))
        # the entry is the module's own: a main: on a later line starts there
        module = asm.assemble("LOAD_CONST 99\nHALT\nmain:\nLOAD_CONST 7\nHALT\n")
        record = s.run(module)
        assert record["stack"] == (7,), (
            "run starts at the module's entry: the stack is %r, not the 99"
            % (record["stack"],))

    def _s1_run(s, bc):
        """Each frame-free program lands on the world's own output and steps pin."""
        for name in ("arith", "branch", "countdown", "fib10"):
            p = bc.PROGRAMS[name]
            record = s.run(p["module"])
            assert set(record) == set(S1_DISPATCH_KEYS), (
                "run's record is %s and §4.0 pins %s"
                % (sorted(record), sorted(S1_DISPATCH_KEYS)))
            assert tuple(record["output"]) == p["output"], (
                "%s: the stage's output is %r and the world's is %r"
                % (name, record["output"], p["output"]))
            assert record["steps"] == p["steps"], (
                "%s: the stage counts %d steps and the world measured %d"
                % (name, record["steps"], p["steps"]))
            assert tuple(record["stack"]) == tuple(record["output"]), (
                "%s: the output is the final stack" % (name,))

    def _s1_runaway(s, bc, asm):
        """A program that never halts is refused past the limit, not waited out."""
        module = asm.assemble("loop:\nJUMP loop\n")
        _refuses(bc.BytecodeError, "runaway", lambda: s.run(module, limit=100),
                 names=("runaway",))

    def _s1_shape_programs(s, bc):
        """The heap programs are not runnable by dispatch: they hold no code."""
        for name in ("conslist", "shared", "cycle"):
            module = bc.PROGRAMS[name]["module"]
            assert len(module.code) == 0 or bc.PROGRAMS[name]["steps"] is None, (
                "%s is a shape, not bytecode" % (name,))

    def _s1_world_untouched(s, bc):
        """The stage never writes the world: the registry is the same after a run."""
        before = {name: (p["module"].code, p["output"], p["steps"])
                  for name, p in bc.PROGRAMS.items()}
        for name in ("arith", "branch", "countdown", "fib10"):
            s.run(bc.PROGRAMS[name]["module"])
        after = {name: (p["module"].code, p["output"], p["steps"])
                 for name, p in bc.PROGRAMS.items()}
        assert before == after, "the stage wrote the world's registry"

    """Every assertion the contract's §4.1 makes about this stage."""
    import bytecode as bc
    import assembler as asm
    import stage_01 as s
    _s1_surface(s)
    _s1_constants(s, bc)
    _s1_decode(s, bc)
    _s1_arith(s, bc)
    _s1_execute_refusals(s, bc)
    _s1_jumps(s, bc, asm)
    _s1_run(s, bc)
    _s1_runaway(s, bc, asm)
    _s1_shape_programs(s, bc)
    _s1_world_untouched(s, bc)

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S2_ARITH = ("ADD", "SUB", "MUL", "NEG", "EQ", "LT", "GT", "NOT")

    S2_STACK_OPS = ("POP", "DUP", "PICK", "ROT3")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _s2_surface(s):
        """The stage's public surface is exactly the seven names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("bc",):
                continue
            public.add(name)
        assert public == {"ARITH", "STACK_OPS", "DISPATCH_KEYS", "RUNNABLE",
                          "FRAME_OPS", "step", "steps_of"}, (
            "the stage's public surface is %s and §4.0 pins ARITH, STACK_OPS, "
            "DISPATCH_KEYS, RUNNABLE, FRAME_OPS, step, steps_of"
            % ", ".join(sorted(public)))
        assert all(callable(getattr(s, n)) for n in ("step", "steps_of")), (
            "step and steps_of are the stage's two ways in")

    def _s2_constants(s, bc):
        """ARITH and STACK_OPS name the world's opcodes, in the contract's order."""
        assert s.ARITH == (bc.OP_ADD, bc.OP_SUB, bc.OP_MUL, bc.OP_NEG, bc.OP_EQ,
                           bc.OP_LT, bc.OP_GT, bc.OP_NOT), (
            "ARITH is %r; the eight arithmetic/comparison opcodes" % (s.ARITH,))
        assert s.STACK_OPS == (bc.OP_POP, bc.OP_DUP, bc.OP_PICK, bc.OP_ROT3), (
            "STACK_OPS is %r; the four stack opcodes" % (s.STACK_OPS,))
        assert s.DISPATCH_KEYS == ("stack", "output", "steps"), (
            "DISPATCH_KEYS is re-exported from stage 1 unchanged")

    def _s2_semantics(s, bc, asm):
        """Every opcode's semantics, from the check's own numbers."""
        def ran(text, before):
            module = asm.assemble(text)
            op, arg = module.code[0]
            stack = list(before)
            answer = s.step(module, op, arg, stack)
            return stack, answer

        stack, answer = ran("LOAD_CONST 5\nHALT", [])
        assert stack == [5] and answer is None, (
            "LOAD_CONST pushes and step answers None (%r, %r)" % (stack, answer))
        assert ran("ADD\nHALT", [2, 3])[0] == [5], "ADD is deeper + top"
        assert ran("SUB\nHALT", [2, 3])[0] == [-1], "SUB is deeper - top"
        assert ran("MUL\nHALT", [2, 3])[0] == [6], "MUL is deeper * top"
        assert ran("NEG\nHALT", [7])[0] == [-7], "NEG negates the top"
        assert ran("EQ\nHALT", [3, 3])[0] == [1], "EQ answers 1 on equal"
        assert ran("EQ\nHALT", [3, 4])[0] == [0], "EQ answers 0 on different"
        assert ran("LT\nHALT", [2, 3])[0] == [1], "LT is deeper < top"
        assert ran("GT\nHALT", [3, 2])[0] == [1], "GT is deeper > top"
        assert ran("NOT\nHALT", [0])[0] == [1], "NOT answers 1 on falsy"
        assert ran("NOT\nHALT", [5])[0] == [0], "NOT answers 0 on truthy"
        assert ran("POP\nHALT", [1, 2])[0] == [1], "POP drops the top"
        assert ran("DUP\nHALT", [4])[0] == [4, 4], "DUP copies the top"
        assert ran("PICK 0\nHALT", [4])[0] == [4, 4], "PICK 0 is DUP"
        assert ran("PICK 2\nHALT", [9, 8, 7])[0] == [9, 8, 7, 9], (
            "PICK 2 copies the third from the top")
        assert ran("ROT3\nHALT", [1, 2, 3])[0] == [2, 3, 1], (
            "ROT3 is (a, b, c) -> (b, c, a) reading bottom to top")

        # the in-place contract: the caller's list is the stack that changed
        module = asm.assemble("DUP\nHALT")
        held = [4]
        s.step(module, bc.OP_DUP, None, held)
        assert held == [4, 4], (
            "step mutates the caller's list in place (it is %r)" % (held,))

    def _s2_refusals(s, bc, asm):
        """The underflows, the bad PICK, the frame ops and the unnamed opcode."""
        def fresh(text):
            return asm.assemble(text)

        for name, op, stack in (("ADD", bc.OP_ADD, [1]),
                                ("SUB", bc.OP_SUB, []),
                                ("MUL", bc.OP_MUL, [3]),
                                ("EQ", bc.OP_EQ, [1]),
                                ("LT", bc.OP_LT, []),
                                ("GT", bc.OP_GT, [1]),
                                ("NEG", bc.OP_NEG, []),
                                ("NOT", bc.OP_NOT, []),
                                ("POP", bc.OP_POP, []),
                                ("DUP", bc.OP_DUP, []),
                                ("ROT3", bc.OP_ROT3, [1, 2])):
            _refuses(bc.BytecodeError, "%s needs" % name,
                     lambda op=op, stack=stack: s.step(
                         fresh("HALT"), op, None, stack),
                     names=(name,))
        _refuses(bc.BytecodeError, "PICK",
                 lambda: s.step(fresh("PICK 5\nHALT"), bc.OP_PICK, 5, [1]),
                 names=("PICK",))
        for op_name, op in (("LOAD_NAME", bc.OP_LOAD_NAME),
                            ("STORE_NAME", bc.OP_STORE_NAME),
                            ("CALL", bc.OP_CALL),
                            ("RETURN", bc.OP_RETURN)):
            _refuses(bc.BytecodeError, "frame operation",
                     lambda op=op: s.step(fresh("HALT"), op, None, []),
                     names=("frame operation", op_name))

    def _s2_costs(s, bc):
        """steps_of reproduces the world's straight-line totals exactly."""
        import assembler as asm
        for name in ("arith", "branch", "countdown", "fib10"):
            p = bc.PROGRAMS[name]
            got = s.steps_of(p["module"])
            assert got == p["steps"], (
                "%s: the stage's straight line costs %d and the world measured %d"
                % (name, got, p["steps"]))

        # the entry is the module's own: a main: on a later line starts there
        module = asm.assemble("LOAD_CONST 99\nHALT\nmain:\nLOAD_CONST 3\n"
                              "loop:\nLOAD_CONST 1\nSUB\nDUP\n"
                              "JUMP_IF_FALSE done\nJUMP loop\ndone:\nHALT\n")
        got = s.steps_of(module)
        assert got == 16, (
            "steps_of starts at the module's entry and pays for the loop: "
            "%d dispatches, not the two-step straight shot from 0" % (got,))

        # an infinite loop is refused, not waited out — the stage counts, it does
        # not spin: a self-jump must hit a limit, not a hang
        module = asm.assemble("loop:\nJUMP loop\n")
        _refuses(bc.BytecodeError, "runaway",
                 lambda: s.steps_of(module, limit=100), names=("runaway",))

    """Every assertion the contract's §4.2 makes about this stage."""
    import bytecode as bc
    import assembler as asm
    import stage_02 as s
    _s2_surface(s)
    _s2_constants(s, bc)
    _s2_semantics(s, bc, asm)
    _s2_refusals(s, bc, asm)
    _s2_costs(s, bc)

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S3_JUMPS = ("JUMP", "JUMP_IF_FALSE", "LOOP")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _s3_surface(s):
        """The stage's public surface is exactly the eight names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("bc",):
                continue
            public.add(name)
        assert public == {"JUMPS", "ARITH", "STACK_OPS", "DISPATCH_KEYS",
                          "RUNNABLE", "FRAME_OPS", "branch_taken", "run_control",
                          "step_totals"}, (
            "the stage's public surface is %s and §4.0 pins JUMPS, ARITH, "
            "STACK_OPS, DISPATCH_KEYS, RUNNABLE, FRAME_OPS, branch_taken, "
            "run_control, step_totals" % ", ".join(sorted(public)))
        assert all(callable(getattr(s, n)) for n in
                   ("branch_taken", "run_control", "step_totals")), (
            "branch_taken, run_control and step_totals are the stage's ways in")

    def _s3_constants(s, bc):
        """JUMPS is the three jump opcodes; the re-exports are intact."""
        assert s.JUMPS == (bc.OP_JUMP, bc.OP_JUMP_IF_FALSE, bc.OP_LOOP), (
            "JUMPS is %r; the three jump opcodes" % (s.JUMPS,))
        assert s.DISPATCH_KEYS == ("stack", "output", "steps"), (
            "DISPATCH_KEYS is re-exported unchanged")
        assert s.ARITH == (bc.OP_ADD, bc.OP_SUB, bc.OP_MUL, bc.OP_NEG, bc.OP_EQ,
                           bc.OP_LT, bc.OP_GT, bc.OP_NOT), (
            "ARITH is re-exported from stage 2 unchanged")
        assert s.STACK_OPS == (bc.OP_POP, bc.OP_DUP, bc.OP_PICK, bc.OP_ROT3), (
            "STACK_OPS is re-exported from stage 2 unchanged")

    def _s3_branch_question(s, bc, asm):
        """The branch question reads the stack without touching it."""
        jump = asm.assemble("JUMP end\nHALT\nend:\nHALT\n")
        assert s.branch_taken(jump, 0, []) is True, "JUMP always jumps"
        loop = asm.assemble("LOOP back\nHALT\nback:\nHALT\n")
        assert s.branch_taken(loop, 0, []) is True, "LOOP always jumps"

        jif = asm.assemble("JUMP_IF_FALSE end\nHALT\nend:\nHALT\n")
        stack = [0]
        assert s.branch_taken(jif, 0, stack) is True, (
            "JUMP_IF_FALSE over a falsy top answers True")
        assert stack == [0], (
            "the question reads the stack without popping (it is %r)" % (stack,))
        stack = [5]
        assert s.branch_taken(jif, 0, stack) is False, (
            "JUMP_IF_FALSE over a truthy top answers False")

        plain = asm.assemble("LOAD_CONST 1\nHALT\n")
        assert s.branch_taken(plain, 0, []) is None, (
            "a non-jump answers None")
        _refuses(bc.BytecodeError, "outside",
                 lambda: s.branch_taken(plain, 99, []),
                 names=("%d" % len(plain.code),))
        _refuses(bc.BytecodeError, "empty",
                 lambda: s.branch_taken(jif, 0, []), names=("empty",))

    def _s3_composed(s, bc):
        """The composed loop lands on every world pin, with stage 2's semantics."""
        for name in ("arith", "branch", "countdown", "fib10"):
            p = bc.PROGRAMS[name]
            record = s.run_control(p["module"])
            assert set(record) == set(s.DISPATCH_KEYS), (
                "run_control's record is %s and §4.0 pins %s"
                % (sorted(record), sorted(s.DISPATCH_KEYS)))
            assert tuple(record["output"]) == p["output"], (
                "%s: the composed output is %r and the world's is %r"
                % (name, record["output"], p["output"]))
            assert record["steps"] == p["steps"], (
                "%s: the composed loop counts %d and the world measured %d"
                % (name, record["steps"], p["steps"]))

    def _s3_boundaries(s, bc, asm):
        """HALT stops mid-code, the entry is the module's own, runaway refused."""
        module = asm.assemble("LOAD_CONST 1\nHALT\nLOAD_CONST 99\n")
        record = s.run_control(module)
        assert record["stack"] == (1,), (
            "HALT stops the loop: the stack is %r and the 99 never landed"
            % (record["stack"],))

        module = asm.assemble("LOAD_CONST 99\nHALT\nmain:\nLOAD_CONST 7\nHALT\n")
        record = s.run_control(module)
        assert record["stack"] == (7,), (
            "run_control starts at the module's entry: the stack is %r"
            % (record["stack"],))

        runaway = asm.assemble("loop:\nJUMP loop\n")
        _refuses(bc.BytecodeError, "runaway",
                 lambda: s.run_control(runaway, limit=100), names=("runaway",))

        # OP_LOOP is JUMP's sibling: a back-edge through LOOP descends too, and a
        # program whose only jump is the LOOP lands where JUMP would land it
        looped = asm.assemble("LOAD_CONST 3\nloop:\nDUP\nJUMP_IF_FALSE done\n"
                              "LOAD_CONST 1\nSUB\nLOOP loop\ndone:\nHALT\n")
        record = s.run_control(looped)
        assert record["stack"] == (0,), (
            "LOOP is a jump: the back-edge descends and the stack ends %r"
            % (record["stack"],))
        # and the pin arithmetic: 1 + 3*(DUP,JIF,LOAD,SUB,LOOP) + (DUP,JIF) + HALT
        assert record["steps"] == 1 + 3 * 5 + 2 + 1 == 19, (
            "the LOOP fixture costs %d dispatches" % record["steps"])

    def _s3_asymmetry(s, bc, asm):
        """The taken path and the skipped path differ in stack and steps."""
        taken = asm.assemble("LOAD_CONST 1\nJUMP_IF_FALSE else\n"
                             "LOAD_CONST 10\nJUMP end\n"
                             "else:\nLOAD_CONST 20\nend:\nHALT\n")
        at = s.run_control(taken)
        skipped = asm.assemble("LOAD_CONST 0\nJUMP_IF_FALSE else\n"
                               "LOAD_CONST 10\nJUMP end\n"
                               "else:\nLOAD_CONST 20\nend:\nHALT\n")
        sk = s.run_control(skipped)
        assert at["stack"] == (10,) and sk["stack"] == (20,), (
            "the taken path leaves %r and the skipped path %r"
            % (at["stack"], sk["stack"]))
        assert at["steps"] != sk["steps"], (
            "the two paths cost different step counts (%d both?)" % at["steps"])
        # the check's own arithmetic: taken = LOAD,JIF,LOAD,JUMP,HALT = 5
        assert at["steps"] == 5, (
            "the taken path is five dispatches, not %d" % at["steps"])
        # skipped = LOAD,JIF,LOAD,HALT = 4
        assert sk["steps"] == 4, (
            "the skipped path is four dispatches, not %d" % sk["steps"])

    def _s3_totals(s, bc):
        """step_totals is the world's pins, and refuses an unknown name."""
        names = ("arith", "branch", "countdown", "fib10")
        totals = s.step_totals(names)
        assert set(totals) == set(names), (
            "step_totals answers %s and the question named %s"
            % (sorted(totals), sorted(names)))
        for name in names:
            assert totals[name] == bc.PROGRAMS[name]["steps"], (
                "%s: the stage's total is %d and the world measured %d"
                % (name, totals[name], bc.PROGRAMS[name]["steps"]))
        _refuses(bc.BytecodeError, "no provided program",
                 lambda: s.step_totals(("bogus",)), names=("bogus",))

    """Every assertion the contract's §4.3 makes about this stage."""
    import bytecode as bc
    import assembler as asm
    import stage_03 as s
    _s3_surface(s)
    _s3_constants(s, bc)
    _s3_branch_question(s, bc, asm)
    _s3_composed(s, bc)
    _s3_boundaries(s, bc, asm)
    _s3_asymmetry(s, bc, asm)
    _s3_totals(s, bc)

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S4_HEAP_KEYS = ("output", "steps", "ledger")

    S4_HEAP_PROGRAMS = ("conslist", "shared", "cycle")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _s4_surface(s):
        """The stage's public surface is exactly the nine names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("bc", "hp"):
                continue
            public.add(name)
        assert public == {"HEAP_KEYS", "HEAP_PROGRAMS", "DISPATCH_KEYS", "RUNNABLE",
                          "FRAME_OPS", "ARITH", "STACK_OPS", "JUMPS", "demand_of",
                          "build", "run_with_heap", "agree"}, (
            "the stage's public surface is %s and §4.0 pins HEAP_KEYS, "
            "HEAP_PROGRAMS, the five re-exports, demand_of, build, run_with_heap, "
            "agree" % ", ".join(sorted(public)))
        assert s.HEAP_KEYS == S4_HEAP_KEYS, (
            "HEAP_KEYS is %r and §4.0 pins %r" % (s.HEAP_KEYS, S4_HEAP_KEYS))
        assert all(callable(getattr(s, n)) for n in
                   ("demand_of", "build", "run_with_heap", "agree")), (
            "demand_of, build, run_with_heap and agree are the stage's ways in")

    def _s4_constants(s, bc):
        """HEAP_PROGRAMS is the three shapes; the re-exports are intact."""
        assert s.HEAP_PROGRAMS == S4_HEAP_PROGRAMS, (
            "HEAP_PROGRAMS is %r and §2.3 pins %r"
            % (s.HEAP_PROGRAMS, S4_HEAP_PROGRAMS))
        assert s.JUMPS[0] == bc.OP_JUMP and s.ARITH[-1] == bc.OP_NOT, (
            "JUMPS and ARITH are re-exported from stages 2-3 unchanged")

    def _s4_demand(s, bc):
        """The demand is the world's, as a fresh dict; the wrong name refuses."""
        for name in S4_HEAP_PROGRAMS:
            d = s.demand_of(name)
            assert d == bc.PROGRAMS[name]["heap"], (
                "%s: the stage's demand is %r and the world's is %r"
                % (name, d, bc.PROGRAMS[name]["heap"]))
            assert d is not bc.PROGRAMS[name]["heap"], (
                "%s: the demand is a copy, not the world's own dict" % (name,))
        _refuses(bc.BytecodeError, "not a heap program",
                 lambda: s.demand_of("bogus"), names=("bogus",))
        _refuses(bc.BytecodeError, "not a heap program",
                 lambda: s.demand_of("arith"), names=("arith",))

    def _s4_builds(s, bc, hp):
        """Each program's shape: the output, the demand, the invariant."""
        for name in S4_HEAP_PROGRAMS:
            heap = hp.Heap()
            out = s.build(name, heap)
            assert tuple(out) == bc.PROGRAMS[name]["output"], (
                "%s: the built shape answers %r and the world's output is %r"
                % (name, out, bc.PROGRAMS[name]["output"]))
            st = heap.stats()
            assert st["allocated"] == dict(bc.PROGRAMS[name]["heap"],
                                           **{k: 0 for k in st["allocated"]
                                              if k not in bc.PROGRAMS[name]["heap"]}) or \
                all(st["allocated"][k] == v
                    for k, v in bc.PROGRAMS[name]["heap"].items()), (
                "%s: the ledger says %r and the demand is %r"
                % (name, st["allocated"], bc.PROGRAMS[name]["heap"]))
            assert st["moves"] == 0 and st["freed"] == {k: 0 for k in st["freed"]}, (
                "%s: stage 4 builds and does not collect (moves %d, freed %r)"
                % (name, st["moves"], st["freed"]))
            assert heap.validate_reachability(), (
                "%s: the shape is rooted — the whole of it is reachable" % (name,))

    def _s4_shared_topology(s, bc, hp):
        """`shared`'s child is reachable from both parents; `cycle` through both."""
        heap = hp.Heap()
        s.build("shared", heap)
        live = heap.validate_reachability()
        # every allocated object is reachable from the roots: nothing built is
        # orphaned, and the child has TWO referrers among them — both parents'
        # slot 1 name it, which is the refcount the later stages rely on
        assert len(live) == 8, (
            "shared's eight objects are all reachable (%d are)" % len(live))
        referrers = []
        for oid in live:
            obj = heap.deref(oid)
            if obj.shape == hp.SHAPE_PAIR:
                nxt = heap.slot(oid, 1)
                if nxt != hp.NULL_ID and heap.follow(nxt) in live:
                    referrers.append(oid)
        # both parents' slot 1 point at the same child id
        targets = {heap.follow(heap.slot(oid, 1)) for oid in referrers
                   if heap.slot(oid, 1) != hp.NULL_ID}
        shared_targets = [t for t in targets
                          if sum(1 for oid in referrers
                                 if heap.follow(heap.slot(oid, 1)) == t) == 2]
        assert shared_targets, (
            "the child is the slot-1 target of both parents (referrers %r, "
            "targets %r)" % (sorted(referrers), sorted(targets)))

        heap = hp.Heap()
        s.build("cycle", heap)
        assert len(heap.validate_reachability()) == 4, (
            "cycle's four objects are all reachable")
        # the cycle closes: walking slot 1 from the first pair comes back to it
        first = heap.roots[0]
        nxt = heap.follow(heap.slot(first, 1))
        assert heap.follow(heap.slot(nxt, 1)) == heap.follow(first), (
            "the cycle closes: a's next's next is a (%r)" % (
                heap.follow(heap.slot(nxt, 1)),))
        heap.roots.clear()
        assert heap.validate_reachability() == set(), (
            "roots gone, the cycle is unreachable — and nothing was freed "
            "(the ledger's freed is %r)" % (heap.stats()["freed"],))

    def _s4_record(s, bc, hp):
        """The record is exactly HEAP_KEYS, with the world's output and ledger."""
        for name in S4_HEAP_PROGRAMS:
            heap = hp.Heap()
            record = s.run_with_heap(name, heap)
            assert set(record) == set(S4_HEAP_KEYS), (
                "%s: the record's keys are %s and §4.0 pins %s"
                % (name, sorted(record), sorted(S4_HEAP_KEYS)))
            assert tuple(record["output"]) == bc.PROGRAMS[name]["output"], (
                "%s: the record's output is %r and the world's is %r"
                % (name, record["output"], bc.PROGRAMS[name]["output"]))
            assert record["ledger"] == heap.stats(), (
                "%s: the record's ledger is the heap's own answer, not a copy "
                "the stage reshaped" % (name,))

    def _s4_agree(s, bc, hp):
        """The verdict reads the ledger: True on a build, False on one extra."""
        heap = hp.Heap()
        s.build("conslist", heap)
        assert s.agree("conslist", heap) is True, (
            "a just-built conslist agrees with its demand")
        extra = heap.allocate(hp.SHAPE_PAIR)
        assert s.agree("conslist", heap) is False, (
            "one extra pair is not agreement (the ledger has %r)"
            % (heap.stats()["allocated"],))
        heap.free(extra)
        assert s.agree("conslist", heap) is True, (
            "freed again, the ledger agrees — the verdict reads the ledger, "
            "not a claim")
        # one shape short is not agreement even when the other shape is exact:
        # free one of the live boxes and the boxes' count is 2 against a demand
        # of 3 while the pairs' count still matches
        boxes = [oid for oid in heap.validate_reachability()
                 if heap.deref(oid).shape == hp.SHAPE_BOX]
        heap.free(boxes[0])
        assert s.agree("conslist", heap) is False, (
            "the boxes are one short: the verdict reads every shape, not the "
            "first (live %r)" % (heap.stats(),))

    """Every assertion the contract's §4.4 makes about this stage."""
    import bytecode as bc
    import heap as hp
    import stage_04 as s
    _s4_surface(s)
    _s4_constants(s, bc)
    _s4_demand(s, bc)
    _s4_builds(s, bc, hp)
    _s4_shared_topology(s, bc, hp)
    _s4_record(s, bc, hp)
    _s4_agree(s, bc, hp)

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S5_MARK_KEYS = ("marked", "swept", "freed_bytes")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _s5_surface(s):
        """The stage's public surface is exactly the nine names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("bc", "hp"):
                continue
            public.add(name)
        assert public == {"MARK_KEYS", "HEAP_KEYS", "HEAP_PROGRAMS",
                          "DISPATCH_KEYS", "RUNNABLE", "FRAME_OPS", "ARITH",
                          "STACK_OPS", "JUMPS", "demand_of", "mark_roots",
                          "trace", "sweep", "collect_mark_sweep"}, (
            "the stage's public surface is %s and §4.0 pins MARK_KEYS, the "
            "re-exports, demand_of, mark_roots, trace, sweep, "
            "collect_mark_sweep" % ", ".join(sorted(public)))
        assert s.MARK_KEYS == S5_MARK_KEYS, (
            "MARK_KEYS is %r and §4.0 pins %r" % (s.MARK_KEYS, S5_MARK_KEYS))
        assert all(callable(getattr(s, n)) for n in
                   ("mark_roots", "trace", "sweep", "collect_mark_sweep")), (
            "mark_roots, trace, sweep and collect_mark_sweep are the ways in")

    def _s5_mark(s, bc, hp, build):
        """mark_roots marks the roots; trace reaches everything behind them."""
        heap = hp.Heap()
        build("shared", heap)
        before_marks = heap.stats()["marks"]
        marked = s.mark_roots(heap)
        expect = {heap.follow(r) for r in heap.roots}
        assert marked == expect, (
            "mark_roots answers %r and the roots name %r" % (sorted(marked),
                                                             sorted(expect)))
        assert heap.stats()["marks"] == before_marks + len(expect), (
            "the ledger counted the marks (%d after %d)"
            % (heap.stats()["marks"], before_marks))
        for oid in marked:
            assert heap.deref(oid).marked == hp.MARK_SET, (
                "every answered id has its mark bit set (%r does not)" % (oid,))

        reached = s.trace(heap, marked)
        # the check's own walk: everything reachable from the roots, by slot
        mine = heap.validate_reachability()
        assert reached == mine, (
            "trace answers %r and the check's own walk reaches %r"
            % (sorted(reached), sorted(mine)))
        for oid in reached:
            assert heap.deref(oid).marked == hp.MARK_SET, (
                "every reached id is marked (%r is not)" % (oid,))

        # the collector over a rooted shape frees nothing — the wavefront marked
        # all of it, and law 14's checker agrees nothing went away
        record = s.collect_mark_sweep(heap)
        st = heap.stats()
        assert record["swept"] == 0, (
            "a rooted shape survives whole: the sweep freed %r" % (record,))
        assert sum(st["freed"].values()) == 0, (
            "the ledger's freed is %r" % (st["freed"],))
        for oid in heap.live_ids():
            assert heap.deref(oid).marked == hp.MARK_CLEAR, (
                "the marks are cleared after the collection (%r keeps its)"
                % (oid,))

        # a moved object's children are found through forwarding: move a MIDDLE
        # pair (the parent still names the old id), keep the roots, collect —
        # everything survives, the old id answers where it went, and the mark's
        # answer set names the twin, not the ghost
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        middle = heap.follow(heap.slot(head, 1))
        new_id = heap.move(middle, "moved")
        record = s.collect_mark_sweep(heap)
        st = heap.stats()
        assert sum(st["freed"].values()) == 0, (
            "the moved list survives whole: %r freed" % (st["freed"],))
        assert heap.follow(middle) == new_id, (
            "the old id still answers where it went")
        marked = s.mark_roots(heap)
        s.trace(heap, marked)
        assert new_id in marked and middle not in marked, (
            "the mark names the twin (%r in %r), not the ghost (%r)"
            % (new_id, sorted(marked), middle))

    def _s5_sweep(s, bc, hp, build):
        """Only the unmarked are freed; the counts are the ledger's; marks clear."""
        heap = hp.Heap()
        build("cycle", heap)
        marked = s.mark_roots(heap)
        s.trace(heap, marked)
        record = s.sweep(heap, marked)
        assert set(record) == set(S5_MARK_KEYS), (
            "sweep's record is %s and §4.0 pins %s"
            % (sorted(record), sorted(S5_MARK_KEYS)))
        assert record["swept"] == 0 and record["freed_bytes"] == 0, (
            "everything was reachable: the sweep freed nothing (%r)"
            % (record,))
        # now drop the roots: the same mark state, a different answer
        heap.roots.clear()
        marked2 = s.mark_roots(heap)
        assert marked2 == set(), "no roots, no marks"
        record = s.collect_mark_sweep(heap)
        assert record["swept"] == 4 and record["freed_bytes"] > 0, (
            "the whole cycle is unreachable and the sweep freed it: %r"
            % (record,))
        for oid in heap.live_ids():
            assert heap.deref(oid).marked == hp.MARK_CLEAR, (
                "the marks are cleared after the sweep (%r keeps its)" % (oid,))
        _refuses(Exception, "dangling", lambda: heap.free(1), names=("dangling",))

    def _s5_invariant(s, bc, hp, build):
        """Law 14, per program: freed ∩ reachable == ∅, and cycle dies."""
        import stage_04 as s4
        for name in ("conslist", "shared", "cycle"):
            heap = hp.Heap()
            build(name, heap)
            heap.roots.clear()      # the program ended: the roots let go
            before_live = set(heap.live_ids())
            record = s.collect_mark_sweep(heap)
            freed_bytes = record["freed_bytes"]
            reachable = heap.validate_reachability()
            assert reachable <= set(heap.live_ids()), (
                "%s: every reachable object is still live" % (name,))
            assert record["marked"] == len(reachable), (
                "%s: the mark reached %r and the reachable set is %r"
                % (name, record["marked"], len(reachable)))
            swept = sum(heap.stats()["freed"].values())
            assert record["swept"] == swept, (
                "%s: the record says %d swept and the ledger says %d"
                % (name, record["swept"], swept))
        # cycle's verdict: two pairs and two boxes gone once the roots let go —
        # the wavefront walks in one side and out the other, which reference
        # counting (stage 6) cannot
        heap = hp.Heap()
        build("cycle", heap)
        heap.roots.clear()
        record = s.collect_mark_sweep(heap)
        st = heap.stats()
        assert st["freed"][hp.SHAPE_PAIR] == 2 and st["freed"][hp.SHAPE_BOX] == 2, (
            "the cycle is swept exactly: %r freed" % (st["freed"],))

    def _s5_boundaries(s, bc, hp, build):
        """An empty heap collects to zeroes; a dangling root refuses."""
        heap = hp.Heap()
        record = s.collect_mark_sweep(heap)
        assert record == {"marked": 0, "swept": 0, "freed_bytes": 0}, (
            "an empty heap collects to zeroes, not %r" % (record,))

        heap = hp.Heap()
        heap.allocate(hp.SHAPE_PAIR)
        heap.roots.append(10 ** 9)
        _refuses(Exception, "dangling", lambda: s.collect_mark_sweep(heap),
                 names=("dangling",))

    """Every assertion the contract's §4.5 makes about this stage."""
    import bytecode as bc
    import heap as hp
    import stage_05 as s
    import stage_04 as s4
    _s5_surface(s)
    _s5_mark(s, bc, hp, s4.build)
    _s5_sweep(s, bc, hp, s4.build)
    _s5_invariant(s, bc, hp, s4.build)
    _s5_boundaries(s, bc, hp, s4.build)

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S6_RC_KEYS = ("freed", "survivors", "cycles")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _refuses(exc, what, call, names=()):
        try:
            got = call()
        except exc as e:
            for name in names:
                assert name in str(e), (
                    "%s: the refusal names %r, not %r" % (what, str(e)[:60], name))
            return
        except Exception as e:  # noqa: BLE001
            raise AssertionError("%s raised %r, not %s" % (what, e, exc.__name__))
        raise AssertionError("%s was accepted (%r); it must refuse" % (what, got))

    def _counts(heap):
        """The mutator's half of the deal: the roots and every slot count."""
        for root in heap.roots:
            if root != 0:
                heap.deref(root).refcount += 1
        for oid in heap.live_ids():
            obj = heap.deref(oid)
            for slot in obj.slots:
                if slot != 0:
                    heap.deref(slot).refcount += 1

    def _s6_surface(s):
        """The stage's public surface is exactly the nine names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("bc", "hp"):
                continue
            public.add(name)
        assert public == {"RC_KEYS", "MARK_KEYS", "HEAP_KEYS", "HEAP_PROGRAMS",
                          "DISPATCH_KEYS", "RUNNABLE", "FRAME_OPS", "ARITH",
                          "STACK_OPS", "JUMPS", "demand_of", "decref",
                          "collect_refcount", "unreachable_cycles"}, (
            "the stage's public surface is %s and §4.0 pins RC_KEYS, the "
            "re-exports, demand_of, decref, collect_refcount, "
            "unreachable_cycles" % ", ".join(sorted(public)))
        assert s.RC_KEYS == S6_RC_KEYS, (
            "RC_KEYS is %r and §4.0 pins %r" % (s.RC_KEYS, S6_RC_KEYS))
        assert all(callable(getattr(s, n)) for n in
                   ("decref", "collect_refcount", "unreachable_cycles")), (
            "decref, collect_refcount and unreachable_cycles are the ways in")

    def _s6_cascade(s, bc, hp, build):
        """The cascade: drop the head, the whole list dies, in order."""
        heap = hp.Heap()
        build("conslist", heap)
        _counts(heap)
        head = heap.roots[0]
        order = []
        # the shape walks head → (box, next) → ...; each cell dies before its box
        # (the free precedes the slot decrements), so the order is pair, box, next
        # pair, next box, ... — computed here from the live shape
        oid = head
        while True:
            obj = heap.deref(oid)
            box, nxt = obj.slots
            order.append(oid)
            order.append(heap.follow(box))
            if nxt == 0:
                break
            oid = nxt
        record = s.decref(heap, head)
        assert set(record) == set(S6_RC_KEYS), (
            "decref's record is %s and §4.0 pins %s"
            % (sorted(record), sorted(S6_RC_KEYS)))
        assert tuple(record["freed"]) == tuple(order), (
            "the cascade dies in shape order: %r, not %r"
            % (record["freed"], order))
        st = heap.stats()
        assert st["freed"][hp.SHAPE_PAIR] == 3 and st["freed"][hp.SHAPE_BOX] == 3, (
            "the ledger's freed is %r" % (st["freed"],))
        assert record["survivors"] == tuple(), (
            "nothing survives (%r)" % (record["survivors"],))
        # a live object nobody counts is a decref past zero, refused naming the id
        loose = heap.allocate(hp.SHAPE_PAIR)
        _refuses(bc.BytecodeError, "already zero",
                 lambda: s.decref(heap, loose), names=("zero", "loose" if False else str(loose)))
        # a freed object is dangling, refused by the heap naming the id
        _refuses(Exception, "dangling", lambda: s.decref(heap, head),
                 names=("dangling",))

    def _s6_shared_drop(s, bc, hp, build):
        """One parent lets go: its subtree dies, the shared child does not."""
        heap = hp.Heap()
        build("shared", heap)
        _counts(heap)
        p1, p2 = heap.roots
        child = heap.follow(heap.deref(p1).slots[1])
        before = heap.stats()["freed"]
        record = s.decref(heap, p1)
        heap.roots.remove(p1)      # the mutator's reference went with the drop
        st = heap.stats()
        assert st["freed"][hp.SHAPE_PAIR] - before[hp.SHAPE_PAIR] == 1, (
            "one parent's pair died (%r)" % (st["freed"],))
        assert st["freed"][hp.SHAPE_BOX] - before[hp.SHAPE_BOX] == 1, (
            "one parent's box died (%r)" % (st["freed"],))
        assert child in heap.live_ids(), (
            "the shared child survives the first drop")
        assert heap.deref(child).refcount == 1, (
            "the child's count fell to one (%d)" % heap.deref(child).refcount)
        # the second parent still reaches it, and its own sum still holds
        reachable = heap.validate_reachability()
        assert child in reachable, (
            "the second parent reaches the child")

    def _s6_verdict(s, bc, hp, build):
        """conslist dies whole; cycle survives whole — both from one collector."""
        heap = hp.Heap()
        build("conslist", heap)
        _counts(heap)
        record = s.collect_refcount(heap)
        assert set(record) == set(S6_RC_KEYS), (
            "collect's record is %s and §4.0 pins %s"
            % (sorted(record), sorted(S6_RC_KEYS)))
        assert record["survivors"] == tuple() and len(record["freed"]) == 6, (
            "conslist dies whole: %r" % (record,))

        heap = hp.Heap()
        build("cycle", heap)
        _counts(heap)
        before = heap.stats()["freed"]
        record = s.collect_refcount(heap)
        st = heap.stats()
        assert st["freed"] == before, (
            "the cycle survives every RC collection: the ledger freed %r"
            % (st["freed"],))
        assert len(record["survivors"]) == 4, (
            "the four members survive: %r" % (record["survivors"],))

    def _s6_honesty(s, bc, hp, build):
        """unreachable_cycles names the group; an empty heap names nothing."""
        heap = hp.Heap()
        build("cycle", heap)
        _counts(heap)
        s.collect_refcount(heap)
        groups = s.unreachable_cycles(heap)
        assert len(groups) == 1 and len(groups[0]) == 4, (
            "one group of four: %r" % (groups,))
        assert set(groups[0]) == set(heap.live_ids()), (
            "the group is the whole cycle: %r vs %r"
            % (groups[0], heap.live_ids()))
        assert heap.validate_reachability() == set(), (
            "the group is unreachable from the roots (the walk reaches nothing)")
        # two independent cycles are two groups, not one
        heap4 = hp.Heap()
        build("cycle", heap4)
        build("cycle", heap4)
        _counts(heap4)
        s.collect_refcount(heap4)
        groups4 = s.unreachable_cycles(heap4)
        assert len(groups4) == 2 and all(len(g) == 4 for g in groups4), (
            "two cycles are two groups of four: %r" % (groups4,))

        # the grouping stays inside the garbage: a cycle wired to a rooted list
        # is one group of the cycle's ids, and the list's live ids are not in it
        heap5 = hp.Heap()
        build("conslist", heap5)
        list_head = heap5.roots[0]
        build("cycle", heap5)
        a, b = heap5.roots[1], heap5.roots[2]
        heap5.set_slot(a, 1, list_head)   # a -> list head (an outgoing edge)
        heap5.roots[:] = [list_head]      # the cycle's roots are gone: garbage
        _counts(heap5)                    # but the counts still hold them alive
        groups5 = s.unreachable_cycles(heap5)
        live = set(heap5.live_ids())
        reachable = heap5.validate_reachability()
        assert reachable, "the list is still rooted"
        assert len(groups5) == 1 and len(groups5[0]) == 4, (
            "the cycle's four are one group: %r" % (groups5,))
        assert not (set(groups5[0]) & reachable), (
            "no live id is in the group (%r)" % (groups5,))

        heap2 = hp.Heap()
        assert s.unreachable_cycles(heap2) == [], (
            "an empty heap has no cycles to name")
        heap3 = hp.Heap()
        build("conslist", heap3)
        _counts(heap3)
        s.collect_refcount(heap3)
        assert s.unreachable_cycles(heap3) == [], (
            "a heap RC emptied has no cycles to name")

    def _s6_asymmetry(s, bc, hp, build):
        """The same heap: stage 5 frees the cycle, stage 6 does not — both true."""
        import stage_05 as s5
        heap = hp.Heap()
        build("cycle", heap)
        heap.roots.clear()
        s5.collect_mark_sweep(heap)
        swept = sum(heap.stats()["freed"].values())
        assert swept == 4, (
            "mark-sweep frees the cycle (%d swept)" % swept)

        heap = hp.Heap()
        build("cycle", heap)
        _counts(heap)
        s.collect_refcount(heap)
        assert sum(heap.stats()["freed"].values()) == 0, (
            "reference counting does not (%r)" % (heap.stats()["freed"],))

    """Every assertion the contract's §4.6 makes about this stage."""
    import bytecode as bc
    import heap as hp
    import stage_06 as s
    import stage_04 as s4
    _s6_surface(s)
    _s6_cascade(s, bc, hp, s4.build)
    _s6_shared_drop(s, bc, hp, s4.build)
    _s6_verdict(s, bc, hp, s4.build)
    _s6_honesty(s, bc, hp, s4.build)
    _s6_asymmetry(s, bc, hp, s4.build)

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S7_COLOURS = ("white", "gray", "black")

    S7_INC_KEYS = ("phases", "marks", "pauses")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _s7_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("bc", "hp"):
                continue
            public.add(name)
        assert public == {"COLOURS", "INC_KEYS", "MARK_KEYS", "RC_KEYS",
                          "HEAP_KEYS", "HEAP_PROGRAMS", "DISPATCH_KEYS", "RUNNABLE",
                          "FRAME_OPS", "ARITH", "STACK_OPS", "JUMPS", "demand_of",
                          "init_tricolour", "increment", "finish_marking"}, (
            "the stage's public surface is %s and §4.0 pins COLOURS, INC_KEYS, "
            "the re-exports, init_tricolour, increment, finish_marking"
            % ", ".join(sorted(public)))
        assert s.COLOURS == S7_COLOURS, (
            "COLOURS is %r and §4.0 pins %r" % (s.COLOURS, S7_COLOURS))
        assert s.INC_KEYS == S7_INC_KEYS, (
            "INC_KEYS is %r and §4.0 pins %r" % (s.INC_KEYS, S7_INC_KEYS))
        assert all(callable(getattr(s, n)) for n in
                   ("init_tricolour", "increment", "finish_marking")), (
            "init_tricolour, increment and finish_marking are the ways in")

    def _counts(heap):
        """No-op for this stage (marking needs no counts); kept for shape parity."""
        return

    def _s7_init(s, bc, hp, build):
        """Init: all white, roots gray, worklist in root order."""
        heap = hp.Heap()
        build("conslist", heap)
        init = s.init_tricolour(heap)
        assert set(init) == {"colours", "grays"}, (
            "init answers colours and grays: %s" % sorted(init))
        colours = init["colours"]
        grays = init["grays"]
        assert set(colours) == set(heap.live_ids()), (
            "every live id is in the colour table")
        assert sum(1 for c in colours.values() if c == "gray") == len(grays), (
            "the grays of the table are exactly the worklist's")
        assert all(c in S7_COLOURS for c in colours.values()), (
            "the colours are the chapter's three")
        assert len(grays) == 1 and colours[grays[0]] == "gray", (
            "the root's object is the one gray: %r" % (grays,))

        heap = hp.Heap()
        build("shared", heap)
        init = s.init_tricolour(heap)
        assert len(init["grays"]) == 2, (
            "shared's two roots are two grays: %r" % (init["grays"],))

        heap = hp.Heap()
        assert s.init_tricolour(heap)["grays"] == [], (
            "an empty heap has no grays")

    def _s7_unit(s, bc, hp, build):
        """One unit: pop the first gray, darken its white children, blacken it."""
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        box, nxt = heap.deref(head).slots
        box_id, nxt_id = heap.follow(box), heap.follow(nxt)
        init = s.init_tricolour(heap)
        record = s.increment(heap, 1)
        assert set(record) == set(S7_INC_KEYS), (
            "increment's record is %s and §4.0 pins %s"
            % (sorted(record), sorted(S7_INC_KEYS)))
        assert record["phases"] == (head,), (
            "the first unit pops the head: %r" % (record["phases"],))
        assert record["marks"] == 2, (
            "the head's two children darkened: %r" % (record["marks"],))
        assert record["pauses"] == 1, "one budget is one pause"

        # the work order is FIFO: the whole mark walks head, box, next pair, ...
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        walk = []
        oid = head
        while True:
            box, nxt = heap.deref(oid).slots
            walk.append(oid)
            walk.append(heap.follow(box))
            if nxt == 0:
                break
            oid = nxt
        s.init_tricolour(heap)
        phases = []
        while True:
            record = s.increment(heap, 5)
            if not record["phases"]:
                break
            phases.extend(record["phases"])
        assert tuple(phases) == tuple(walk), (
            "the gray worklist drains in FIFO walk order: %r vs %r"
            % (phases, walk))

        # an exhausted worklist spends nothing
        while True:
            record = s.increment(heap, 5)
            if not record["phases"]:
                break
        assert record["marks"] == 0 and record["pauses"] == record["pauses"], (
            "an exhausted worklist spends no marks")

    def _s7_determinism(s, bc, hp, build):
        """Budget 1 twice lands where budget 2 once lands."""
        outcomes = []
        for budgets in ((2,), (1, 1)):
            heap = hp.Heap()
            build("conslist", heap)
            s.init_tricolour(heap)
            records = [s.increment(heap, b) for b in budgets]
            combined = tuple(p for r in records for p in r["phases"])
            total_marks = sum(r["marks"] for r in records)
            # pauses count the calls themselves: one increment is one pause
            for i, record in enumerate(records, 1):
                assert record["pauses"] == i, (
                    "increment %d is pause %d: %r" % (i, i, record))
            # drain to exhaustion, the phases order is the whole mark's order
            while True:
                record = s.increment(heap, 5)
                if not record["phases"]:
                    break
                combined += record["phases"]
                total_marks += record["marks"]
            outcomes.append((combined, total_marks))
        assert outcomes[0] == outcomes[1], (
            "budget 2 = budget 1 + budget 1: %r vs %r" % (outcomes[0], outcomes[1]))

    def _s7_invariant(s, bc, hp, build):
        """No black object names a white child at any pause boundary.

        The stage owns the colour table; the check rebuilds it from the
        deterministic work order: it runs each increment, then walks every live
        object it can — a black parent's children must be gray or black. Because
        the stage's `init_tricolour` hands the colours over, the check can read
        them at each pause."""
        heap = hp.Heap()
        build("conslist", heap)
        init = s.init_tricolour(heap)
        colours = init["colours"]
        # the check walks the pauses, reading the stage's own table between them
        for _ in range(20):
            record = s.increment(heap, 1)
            if not record["phases"]:
                break
            for oid in heap.live_ids():
                obj = heap.deref(oid)
                if colours[oid] != "black":
                    continue
                for slot in obj.slots:
                    if slot == hp.NULL_ID:
                        continue
                    child = heap.follow(slot)
                    if child != hp.NULL_ID and colours[child] == "white":
                        raise AssertionError(
                            "black %r names white %r at a pause boundary"
                            % (oid, child))

    def _s7_verdict(s, bc, hp, build):
        """The incremental verdict equals stage 5's stop-the-world verdict."""
        import stage_05 as s5
        for name in ("shared", "cycle"):
            # rooted: both collectors free nothing reachable
            heap_stw = hp.Heap()
            build(name, heap_stw)
            stw = s5.collect_mark_sweep(heap_stw)
            assert stw["swept"] == 0, (
                "%s: a rooted heap sweeps nothing (%r)" % (name, stw))
            heap_inc = hp.Heap()
            build(name, heap_inc)
            s.init_tricolour(heap_inc)
            while True:
                record = s.increment(heap_inc, 1)
                if not record["phases"]:
                    break
            inc = s.finish_marking(heap_inc)
            assert inc == stw, (
                "%s rooted: incremental %r != stop-the-world %r"
                % (name, inc, stw))

            # the program ended: both free the same everything
            heap_stw = hp.Heap()
            build(name, heap_stw)
            heap_stw.roots.clear()
            stw = s5.collect_mark_sweep(heap_stw)

            heap_inc = hp.Heap()
            build(name, heap_inc)
            heap_inc.roots.clear()
            s.init_tricolour(heap_inc)
            while True:
                record = s.increment(heap_inc, 1)
                if not record["phases"]:
                    break
            inc = s.finish_marking(heap_inc)
            assert set(inc) == set(s.MARK_KEYS), (
                "finish_marking answers the MARK_KEYS shape: %s" % sorted(inc))
            assert inc == stw, (
                "%s ended: incremental %r != stop-the-world %r"
                % (name, inc, stw))
            assert sum(heap_inc.stats()["freed"].values()) == \
                sum(heap_stw.stats()["freed"].values()), (
                "%s: the ledgers agree" % name)

    """Every assertion the contract's §4.7 makes about this stage."""
    import bytecode as bc
    import heap as hp
    import stage_07 as s
    import stage_04 as s4
    _s7_surface(s)
    _s7_init(s, bc, hp, s4.build)
    _s7_unit(s, bc, hp, s4.build)
    _s7_determinism(s, bc, hp, s4.build)
    _s7_invariant(s, bc, hp, s4.build)
    _s7_verdict(s, bc, hp, s4.build)

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S8_BARRIER_KEYS = ("remembered", "darkened")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _s8_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("bc", "hp"):
                continue
            public.add(name)
        assert public == {"BARRIER_KEYS", "COLOURS", "INC_KEYS", "MARK_KEYS",
                          "RC_KEYS", "HEAP_KEYS", "HEAP_PROGRAMS", "DISPATCH_KEYS",
                          "RUNNABLE", "FRAME_OPS", "ARITH", "STACK_OPS", "JUMPS",
                          "demand_of", "needs_barrier", "write",
                          "collect_incremental"}, (
            "the stage's public surface is %s and §4.0 pins BARRIER_KEYS, the "
            "re-exports, needs_barrier, write, collect_incremental"
            % ", ".join(sorted(public)))
        assert s.BARRIER_KEYS == S8_BARRIER_KEYS, (
            "BARRIER_KEYS is %r and §4.0 pins %r"
            % (s.BARRIER_KEYS, S8_BARRIER_KEYS))
        assert all(callable(getattr(s, n)) for n in
                   ("needs_barrier", "write", "collect_incremental")), (
            "needs_barrier, write and collect_incremental are the ways in")

    def _install_colours(s, s7, colours):
        """Install a colour table the barrier can read (the collector's desk)."""
        s7._STATE["colours"] = dict(colours)
        s7._STATE["worklist"] = []

    def _s8_rule(s, bc, hp, build, s7):
        """The rule over the four combinations."""
        heap = hp.Heap()
        build("conslist", heap)
        ids = heap.live_ids()
        source, value = ids[0], ids[1]
        for source_colour in ("white", "gray", "black"):
            for value_colour in ("white", "gray", "black"):
                _install_colours(s, s7, {source: source_colour,
                                         value: value_colour})
                obj = heap.deref(source)
                want = source_colour == "black" and value_colour == "white"
                got = s.needs_barrier(obj, value)
                assert got == want, (
                    "black=%s storing white=%s needs_barrier -> %r, want %r"
                    % (source_colour, value_colour, got, want))

    def _s8_cure(s, bc, hp, build, s7):
        """A dangerous store darkens and remembers; a safe one does neither."""
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        box, nxt = heap.deref(head).slots
        box_id = heap.follow(box)
        free_oid = heap.allocate(hp.SHAPE_BOX, value=7)   # white, unreached
        _install_colours(s, s7, {head: "black", box_id: "black", free_oid: "white"})
        remembered = []
        record = s.write(heap, heap.deref(head), 0, free_oid, remembered)
        assert set(record) == set(S8_BARRIER_KEYS), (
            "write's record is %s and §4.0 pins %s"
            % (sorted(record), sorted(S8_BARRIER_KEYS)))
        assert record["remembered"] == (free_oid,), (
            "the white value is remembered: %r" % (record["remembered"],))
        assert record["darkened"] == 1, (
            "the black source is darkened: %r" % (record["darkened"],))
        assert heap.slot(head, 0) == free_oid, (
            "the store went through (%r)" % (heap.slot(head, 0),))

        # a safe store: no cure, no memory
        _install_colours(s, s7, {head: "black", box_id: "black", free_oid: "gray"})
        record = s.write(heap, heap.deref(head), 1, box_id, [])
        assert record["remembered"] == (), (
            "a safe store remembers nothing: %r" % (record["remembered"],))
        assert record["darkened"] == 0, (
            "a safe store darkens nothing: %r" % (record["darkened"],))

    def _s8_danger(s, bc, hp, build, s7):
        """The chapter's danger: black collector, white store, barrier as guard.

        The mark has run past the head (black); the mutator stores a fresh white
        box into the head's second slot; the collection then runs. With the
        barrier, the box survives; bypassed, the sweep frees it while the head
        still names it."""
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        box, nxt = heap.deref(head).slots
        box_id, nxt_id = heap.follow(box), heap.follow(nxt)
        # the mark partially done: head and first box black, the rest white
        _install_colours(s, s7, {head: "black", box_id: "black"})
        free_oid = heap.allocate(hp.SHAPE_BOX, value=9)
        remembered = []
        record = s.write(heap, heap.deref(head), 1, free_oid, remembered)
        assert record["darkened"] == 1 and record["remembered"] == (free_oid,), (
            "the barrier fired on the dangerous store: %r" % (record,))
        before = heap.stats()
        collected = s.collect_incremental(heap, record["remembered"])
        reachable = heap.validate_reachability()
        assert free_oid in reachable, (
            "the stored white survived the collection")
        freed = {oid for oid in range(1, heap._next_id)
                 if oid not in heap.live_ids()}
        assert not (freed & reachable), (
            "nothing reachable was freed (%r)" % (freed & reachable,))

        # the bypass: the same store without the cure — the white dies reachable
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        box, nxt = heap.deref(head).slots
        box_id, nxt_id = heap.follow(box), heap.follow(nxt)
        _install_colours(s, s7, {head: "black", box_id: "black"})
        free_oid = heap.allocate(hp.SHAPE_BOX, value=9)
        heap.set_slot(head, 1, free_oid)      # the barrier bypassed
        collected = s.collect_incremental(heap, [])
        assert free_oid not in heap.live_ids(), (
            "the bypass lets the white die — this is the danger the barrier "
            "exists for, and the scenario must show it")
        assert collected is not None

    def _s8_remembered_roots(s, bc, hp, build, s7):
        """The remembered set is the next mark's extra roots."""
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        orphan = heap.allocate(hp.SHAPE_BOX, value=5)   # no root reaches it
        collected = s.collect_incremental(heap, [orphan])
        assert set(collected) == set(s.INC_KEYS), (
            "collect_incremental answers INC_KEYS: %s" % sorted(collected))
        assert orphan in heap.live_ids(), (
            "the remembered orphan survived as an extra root")
        heap2 = hp.Heap()
        build("conslist", heap2)
        orphan = heap2.allocate(hp.SHAPE_BOX, value=5)
        collected2 = s.collect_incremental(heap2, [])
        assert orphan not in heap2.live_ids(), (
            "without the memory, the orphan is swept")

    """Every assertion the contract's §4.8 makes about this stage."""
    import bytecode as bc
    import heap as hp
    import stage_08 as s
    import stage_04 as s4
    import stage_07 as s7
    _s8_surface(s)
    _s8_rule(s, bc, hp, s4.build, s7)
    _s8_cure(s, bc, hp, s4.build, s7)
    _s8_danger(s, bc, hp, s4.build, s7)
    _s8_remembered_roots(s, bc, hp, s4.build, s7)

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S9_GEN_KEYS = ("nursery", "promoted", "collected", "ledger")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _s9_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("bc", "hp"):
                continue
            public.add(name)
        assert public == {"GEN_KEYS", "BARRIER_KEYS", "COLOURS", "INC_KEYS",
                          "MARK_KEYS", "RC_KEYS", "HEAP_KEYS", "HEAP_PROGRAMS",
                          "DISPATCH_KEYS", "RUNNABLE", "FRAME_OPS", "ARITH",
                          "STACK_OPS", "JUMPS", "demand_of", "nursery_collect",
                          "promote", "run_generational"}, (
            "the stage's public surface is %s and §4.0 pins GEN_KEYS, the "
            "re-exports, nursery_collect, promote, run_generational"
            % ", ".join(sorted(public)))
        assert s.GEN_KEYS == S9_GEN_KEYS, (
            "GEN_KEYS is %r and §4.0 pins %r" % (s.GEN_KEYS, S9_GEN_KEYS))
        assert all(callable(getattr(s, n)) for n in
                   ("nursery_collect", "promote", "run_generational")), (
            "nursery_collect, promote and run_generational are the ways in")

    def _young(hp, heap):
        """The check's own nursery count: live, born in NURSERY, not forwarded."""
        return [oid for oid in heap.live_ids()
                if heap.deref(oid).generation == hp.NURSERY
                and heap.deref(oid).forwarded is None]

    def _assert_keys(record, what):
        assert set(record) == set(S9_GEN_KEYS), (
            "%s's record is %s and §4.0 pins %s"
            % (what, sorted(record), sorted(S9_GEN_KEYS)))

    def _s9_threshold(s, bc, hp, build):
        """A nursery below the threshold answers a no-work record."""
        heap = hp.Heap()
        heap.allocate(hp.SHAPE_BOX, value=1)
        heap.allocate(hp.SHAPE_BOX, value=2)
        heap.roots.append(1)
        before = heap.stats()
        record = s.nursery_collect(heap, 4)
        _assert_keys(record, "nursery_collect")
        assert record["nursery"] == 2, (
            "the nursery's population is honest: %r" % (record["nursery"],))
        assert record["promoted"] == () and record["collected"] == (), (
            "below the threshold nothing happens: %r" % (record,))
        after = heap.stats()
        assert after == before, (
            "the ledger did not move (%r vs %r)" % (before, after))

    def _s9_promote(s, bc, hp, build):
        """Promotion moves through the heap's own move, and nothing breaks."""
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        before = heap.stats()
        record = s.promote(heap, heap.deref(head))
        _assert_keys(record, "promote")
        after = heap.stats()
        assert after["moves"] - before["moves"] == 1, (
            "the ledger's moves grew by one (%r)" % (after["moves"],))
        new_id = record["promoted"][0]
        assert heap.deref(new_id).generation != hp.NURSERY, (
            "the twin lives in the older generation")
        assert heap.follow(head) == new_id, (
            "the old id still answers where it went")
        reachable = heap.validate_reachability()
        assert new_id in reachable and head not in reachable, (
            "the reachable set names the twin, not the ghost: %r"
            % (sorted(reachable),))
        assert len(reachable) == 6, (
            "the whole list is still reachable: %r" % (sorted(reachable),))

    def _s9_rooted(s, bc, hp, build):
        """Rooted: the survivors promote, the garbage dies."""
        heap = hp.Heap()
        build("conslist", heap)
        # exactly at the threshold: the collection fires
        record = s.nursery_collect(heap, 6)
        _assert_keys(record, "nursery_collect(at threshold)")
        assert len(record["promoted"]) == 6 and record["collected"] == (), (
            "at the threshold the collection fires: %r" % (record,))
        # rebuild a fresh list for the rest of the scenario
        heap = hp.Heap()
        build("conslist", heap)
        # two orphans die young; the rooted list promotes
        orphan_a = heap.allocate(hp.SHAPE_BOX, value=99)
        orphan_b = heap.allocate(hp.SHAPE_BOX, value=98)
        before = heap.stats()
        record = s.nursery_collect(heap, 4)
        _assert_keys(record, "nursery_collect")
        assert record["nursery"] == 8, (
            "the nursery held the list plus the orphans: %r" % (record["nursery"],))
        assert tuple(sorted(record["collected"])) == tuple(
            sorted([orphan_a, orphan_b])), (
            "the orphans died young: %r" % (record["collected"],))
        assert len(record["promoted"]) == 6, (
            "the rooted list promoted whole: %r" % (record["promoted"],))
        for new_id in record["promoted"]:
            assert heap.deref(new_id).generation != hp.NURSERY, (
                "a promoted object lives in the older generation")
        reachable = heap.validate_reachability()
        assert set(record["promoted"]) <= reachable, (
            "every promoted object is reachable through the roots")
        assert not ({orphan_a, orphan_b} & reachable), (
            "the orphans are gone")

        # the survivors are not collected by the next collection
        before = heap.stats()
        second = s.nursery_collect(heap, 4)
        _assert_keys(second, "nursery_collect(second)")
        after = heap.stats()
        assert second["nursery"] == 0 and second["promoted"] == () \
            and second["collected"] == (), (
            "the promoted live in the old generation; the nursery is empty: %r"
            % (second,))
        assert after == before, (
            "the second collection moved no ledger numbers")
        assert heap.stats()["collections"] == 1, (
            "one collection, one collections count: %r"
            % (heap.stats()["collections"],))

        # an old object is not walked: promote the head, then collect — the
        # nursery's remaining young die or promote without the old twin's slots
        # contributing anything the restriction forbids
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        s.promote(heap, heap.deref(head))
        record = s.nursery_collect(heap, 4)
        _assert_keys(record, "nursery_collect(after promote)")
        # the old head is not nursery population; its slots' young pairs are
        # reachable only through the old twin, so the restriction keeps them
        # out of the mark — they die young, the boxes with them
        assert record["nursery"] == 5 and record["promoted"] == (), (
            "the old generation is off-limits: %r" % (record,))
        assert len(record["collected"]) == 5, (
            "the young die young: %r" % (record["collected"],))

        # ... and the young reachable ONLY through an old object die with it:
        # a young list wired into a promoted list's twin — the twin is off-limits
        heap = hp.Heap()
        build("conslist", heap)                 # ids 1-6, root 6 (young)
        build("conslist", heap)                 # ids 7-12, root 12
        promoted_head = heap.roots[1]
        s.promote(heap, heap.deref(promoted_head))   # 12 -> 13 (old)
        heap.set_slot(heap.roots[0], 1, 13)     # the young list chains into the old
        record = s.nursery_collect(heap, 4)
        _assert_keys(record, "nursery_collect(through old)")
        assert len(record["promoted"]) == 2, (
            "the young head and its box promote: %r" % (record["promoted"],))
        assert len(record["collected"]) == 9, (
            "the young reachable only through the old object dies: %r"
            % (record["collected"],))
        assert heap.deref(13).generation != hp.NURSERY, (
            "the old twin was never touched")

    def _s9_most_die_young(s, bc, hp, build):
        """The program ended: the nursery's whole population dies young."""
        heap = hp.Heap()
        build("conslist", heap)
        heap.roots.clear()          # the program ended
        record = s.nursery_collect(heap, 4)
        _assert_keys(record, "nursery_collect(ended)")
        assert record["nursery"] == 6, (
            "the nursery held the whole list: %r" % (record["nursery"],))
        assert record["promoted"] == () and len(record["collected"]) == 6, (
            "most die young — here, all: %r" % (record,))
        assert heap.live_ids() == [], (
            "the nursery emptied (%r)" % (heap.live_ids(),))
        st = heap.stats()
        assert st["freed"][hp.SHAPE_PAIR] == 3 and st["freed"][hp.SHAPE_BOX] == 3, (
            "the ledger's freed matches the demand: %r" % (st["freed"],))
        # nothing was freed that was reachable at collection time: the roots were
        # empty, so the invariant is vacuously true — state it anyway
        assert heap.validate_reachability() == set(), (
            "no roots, nothing reachable")

    def _s9_run(s, bc, hp, build):
        """The integration: the program, the threshold, the record."""
        heap = hp.Heap()
        record = s.run_generational("conslist", heap, 4)
        _assert_keys(record, "run_generational")
        # the build allocates the demand, then the collection fires: all rooted,
        # so every survivor promotes — the ledger allocates the demand twice
        # (the originals and their promoted twins) and frees nothing
        demand = {"pair": 3, "box": 3}
        st = heap.stats()
        assert st["allocated"][hp.SHAPE_PAIR] == 2 * demand["pair"], (
            "the build plus the promotion twins: %r" % (st["allocated"],))
        assert st["allocated"][hp.SHAPE_BOX] == 2 * demand["box"], (
            "the build plus the promotion twins: %r" % (st["allocated"],))
        assert sum(st["freed"].values()) == 0, (
            "nothing died: %r" % (st["freed"],))
        assert len(record["promoted"]) == 6 and record["collected"] == (), (
            "the rooted program promotes its whole shape: %r" % (record,))
        assert record["nursery"] == 6, (
            "the nursery was full at the trigger: %r" % (record["nursery"],))
        reachable = heap.validate_reachability()
        assert len(reachable) == 6, (
            "the shape survives reachable: %r" % (sorted(reachable),))
        _refuses = getattr(bc, "BytecodeError")
        try:
            s.run_generational("countdown", heap, 4)
        except _refuses:
            pass
        else:
            raise AssertionError("a frame program is not a heap program: refused")

    """Every assertion the contract's §4.9 makes about this stage."""
    import bytecode as bc
    import heap as hp
    import stage_09 as s
    import stage_04 as s4
    _s9_surface(s)
    _s9_threshold(s, bc, hp, s4.build)
    _s9_promote(s, bc, hp, s4.build)
    _s9_rooted(s, bc, hp, s4.build)
    _s9_most_die_young(s, bc, hp, s4.build)
    _s9_run(s, bc, hp, s4.build)

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/forja"

    COURSE = "runtime-from-scratch"

    S10_COPY_KEYS = ("moved", "forwarded", "live_bytes", "audit")

    S10_AUDIT_KEYS = ("verdict", "reasons", "ledger_agrees", "reachable_safe")

    S10_VERDICTS = ("pass", "leak", "premature", "miscount")

    def _repo(start=None):
        for candidate_start in (os.environ.get("G8_REPO"), start, os.getcwd(),
                                DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isfile(os.path.join(candidate, COURSE, "bytecode.py")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set G8_REPO=/path/to/forja")

    def _s10_surface(s):
        """The stage's public surface is exactly the names §4.0 pins."""
        public = set()
        for name, value in vars(s).items():
            if name.startswith("_") or name in ("bc", "hp"):
                continue
            public.add(name)
        assert public == {"COPY_KEYS", "AUDIT_KEYS", "VERDICTS", "GEN_KEYS",
                          "BARRIER_KEYS", "COLOURS", "INC_KEYS", "MARK_KEYS",
                          "RC_KEYS", "HEAP_KEYS", "HEAP_PROGRAMS",
                          "DISPATCH_KEYS", "RUNNABLE", "FRAME_OPS", "ARITH",
                          "STACK_OPS", "JUMPS", "demand_of", "copy_collect",
                          "audit"}, (
            "the stage's public surface is %s and §4.0 pins COPY_KEYS, "
            "AUDIT_KEYS, VERDICTS, the re-exports, copy_collect, audit"
            % ", ".join(sorted(public)))
        assert s.COPY_KEYS == S10_COPY_KEYS, (
            "COPY_KEYS is %r and §4.0 pins %r" % (s.COPY_KEYS, S10_COPY_KEYS))
        assert s.AUDIT_KEYS == S10_AUDIT_KEYS, (
            "AUDIT_KEYS is %r and §4.0 pins %r"
            % (s.AUDIT_KEYS, S10_AUDIT_KEYS))
        assert s.VERDICTS == S10_VERDICTS, (
            "VERDICTS is %r and §4.0 pins %r" % (s.VERDICTS, S10_VERDICTS))
        assert all(callable(getattr(s, n)) for n in ("copy_collect", "audit")), (
            "copy_collect and audit are the ways in")

    def _s10_copy(s, bc, hp, build):
        """The copy: the reachable moves, the twins' slots name twins."""
        heap = hp.Heap()
        build("conslist", heap)
        before = heap.stats()
        record = s.copy_collect(heap)
        assert set(record) == set(S10_COPY_KEYS), (
            "copy_collect's record is %s and §4.0 pins %s"
            % (sorted(record), sorted(S10_COPY_KEYS)))
        assert record["moved"] == 6, (
            "the whole reachable list moved: %r" % (record["moved"],))
        assert record["forwarded"] == 6, (
            "every old body answers through forwarding: %r"
            % (record["forwarded"],))
        # every old id resolves to a twin; no slot names an old body
        reachable = heap.validate_reachability()
        assert len(reachable) == 6, (
            "the reachable set is the twin set: %r" % (sorted(reachable),))
        for oid in reachable:
            obj = heap.deref(oid)
            assert obj.forwarded is None, (
                "a reachable object is a twin, not a body (%r)" % (oid,))
            for slot in obj.slots:
                if slot != hp.NULL_ID:
                    child = heap.follow(slot)
                    assert child in reachable, (
                        "a twin's slot names a twin (%r -> %r)" % (oid, child))
        assert all(heap.deref(o).forwarded is None for o in heap.live_ids()), (
            "the bodies are reclaimed: no forwarded pointers remain")
        st = heap.stats()
        assert sum(st["freed"].values()) == sum(before["freed"].values()), (
            "a move is not a death: the freed counts did not move (%r)"
            % (st["freed"],))
        assert record["live_bytes"] == st["live_bytes"], (
            "the record's live bytes are the ledger's: %r vs %r"
            % (record["live_bytes"], st["live_bytes"]))
        assert st["live_bytes"] == 3 * 32 + 3 * 24, (
            "three pairs and three boxes: %r" % (st["live_bytes"],))
        assert record["audit"]["verdict"] == "pass", (
            "the copy's own audit passes: %r" % (record["audit"],))

    def _s10_cycle(s, bc, hp, build):
        """A cycle copies whole: the chase follows forwarding into the cycle."""
        heap = hp.Heap()
        build("cycle", heap)
        record = s.copy_collect(heap)
        assert record["moved"] == 4, (
            "the cycle moved whole: %r" % (record["moved"],))
        reachable = heap.validate_reachability()
        assert len(reachable) == 4, (
            "the cycle is reachable in the new space: %r" % (sorted(reachable),))
        a = heap.follow(heap.roots[0])
        b = heap.follow(heap.deref(a).slots[1])
        assert heap.follow(heap.deref(b).slots[1]) == a, (
            "the cycle's links survived the copy")

    def _s10_audit_pass(s, bc, hp, build):
        """The world's own good records: verdict pass, the reason says why."""
        import stage_05 as s5
        heap = hp.Heap()
        build("cycle", heap)
        heap.roots.clear()          # the program ended
        st_before = heap.stats()
        record = s5.collect_mark_sweep(heap)
        st_after = heap.stats()
        good = [{"swept": record["swept"], "marked": record["marked"],
                 "freed_bytes": record["freed_bytes"]}]
        verdict = s.audit(heap, good)
        assert set(verdict) == set(S10_AUDIT_KEYS), (
            "audit's record is %s and §4.0 pins %s"
            % (sorted(verdict), sorted(S10_AUDIT_KEYS)))
        assert verdict["verdict"] == "pass", (
            "the good records pass: %r" % (verdict,))
        assert verdict["reachable_safe"] is True, (
            "nothing reachable was freed")
        assert verdict["ledger_agrees"] is True, (
            "the ledger agrees")
        assert verdict["reasons"], "a pass carries its reason too"

    def _s10_audit_corrupt(s, bc, hp, build):
        """Each corrupted record earns its verdict, and the reason names it."""
        # miscount: claim twelve, the ledger freed four
        heap = hp.Heap()
        build("cycle", heap)
        heap.roots.clear()
        import stage_05 as s5
        record = s5.collect_mark_sweep(heap)
        assert sum(heap.stats()["freed"].values()) == 4, (
            "the ledger freed four")
        verdict = s.audit(heap, [{"swept": 12}])
        assert verdict["verdict"] == "miscount", (
            "twelve against four is a miscount: %r" % (verdict,))
        assert "12" in " ".join(verdict["reasons"])
        assert "4" in " ".join(verdict["reasons"])
        assert verdict["ledger_agrees"] is False, (
            "the ledger does not agree with a miscount")

        # leak: the program is over, the bytes are live
        heap = hp.Heap()
        build("conslist", heap)
        heap.roots.clear()          # over, and nothing collected
        verdict = s.audit(heap, [])
        assert verdict["verdict"] == "leak", (
            "live bytes with no roots is a leak: %r" % (verdict,))
        assert any("bytes" in reason for reason in verdict["reasons"]), (
            "the reason names the bytes: %r" % (verdict["reasons"],))

        # premature: a freed id the roots still reach
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        box, nxt = heap.deref(head).slots
        nxt_id = heap.follow(nxt)
        del heap._objects[nxt_id]    # the planted mistake: freed while reachable
        heap._next_id = max(heap._next_id, nxt_id + 1)
        verdict = s.audit(heap, [])
        assert verdict["verdict"] == "premature", (
            "a freed reachable id is premature: %r" % (verdict,))
        assert str(nxt_id) in " ".join(verdict["reasons"]), (
            "the reason names the id: %r" % (verdict["reasons"],))
        assert verdict["reachable_safe"] is False, (
            "the reachable set was not safe")

        # severity: a heap freed-while-reachable *and* miscounted — premature
        # wins, and both reasons are named
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        box, nxt = heap.deref(head).slots
        nxt_id = heap.follow(nxt)
        del heap._objects[nxt_id]    # freed while reachable
        heap._next_id = max(heap._next_id, nxt_id + 1)
        verdict = s.audit(heap, [{"swept": 99}])
        assert verdict["verdict"] == "miscount", (
            "the worse verdict wins: %r" % (verdict,))
        assert any(str(nxt_id) in r for r in verdict["reasons"])
        assert any("99" in r for r in verdict["reasons"]), (
            "both reasons are named: %r" % (verdict["reasons"],))
        assert verdict["ledger_agrees"] is False, (
            "the miscount is in the record too")

        # a running program is not a leak: roots alive, bytes live, verdict pass
        heap = hp.Heap()
        build("conslist", heap)
        verdict = s.audit(heap, [])
        assert verdict["verdict"] == "pass", (
            "a running program's heap is not a leak: %r" % (verdict,))

        # a dangling root: the audit reports the premature, it does not die
        heap = hp.Heap()
        build("conslist", heap)
        head = heap.roots[0]
        del heap._objects[head]      # the planted mistake: the root is freed
        heap._next_id = max(heap._next_id, head + 1)
        verdict = s.audit(heap, [])
        assert verdict["verdict"] == "premature", (
            "a freed root is premature: %r" % (verdict,))
        assert str(head) in " ".join(verdict["reasons"]), (
            "the reason names the id: %r" % (verdict["reasons"],))

    """Every assertion the contract's §4.10 makes about this stage."""
    import bytecode as bc
    import heap as hp
    import stage_10 as s
    import stage_04 as s4
    _s10_surface(s)
    _s10_copy(s, bc, hp, s4.build)
    _s10_cycle(s, bc, hp, s4.build)
    _s10_audit_pass(s, bc, hp, s4.build)
    _s10_audit_corrupt(s, bc, hp, s4.build)

# --- the manifest. One entry per stage, in the order a reader meets them.

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The dispatch: decode, execute, count",
        tags=["opcodes", "dispatch", "counting"],
        action="Write `DISPATCH_KEYS`, `decode`, `execute` and `run` in "
               "stage_01.py.",
        predict="What a decoded instruction is before it means anything, and why "
                "the run's step count is the record's own and not the loop's.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The value stack, and what each opcode costs",
        tags=["stack", "arith", "pricing"],
        action="Write `ARITH`, `STACK_OPS`, `step` and `steps_of` in stage_02.py.",
        predict="What the stack owes each opcode and what each opcode costs, and "
                "how a program's step total is measured rather than invented.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Control flow: the jumps, and a program's step total",
        tags=["jumps", "control", "pins"],
        action="Write `JUMPS`, `branch_taken`, `run_control` and `step_totals` in "
               "stage_03.py.",
        predict="Where a taken jump hands control and how many steps a countdown "
                "and a fib really cost — the pins the world measured first.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The heap: objects, references, and the ledger",
        tags=["heap", "references", "ledger"],
        action="Write `HEAP_KEYS`, `run_with_heap`, `demand_of` and `agree` in "
               "stage_04.py.",
        predict="What a program's shape demands of the heap, and why the ledger — "
                "not the stage — is the first verdict a collector's numbers face.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Mark-sweep: the wavefront, and nothing reachable freed",
        tags=["mark-sweep", "roots", "tracing"],
        action="Write `MARK_KEYS`, `mark_roots`, `trace`, `sweep` and "
               "`collect_mark_sweep` in stage_05.py.",
        predict="Where the wavefront starts, how it moves, and why freed ∩ "
                "reachable == ∅ is the one invariant no collector may break.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="Reference counting, and the cycle it cannot free",
        tags=["refcount", "cycles", "cascades"],
        action="Write `RC_KEYS`, `decref`, `collect_refcount` and "
               "`unreachable_cycles` in stage_06.py.",
        predict="Why the cascade dies in shape order, and why a cycle's members "
                "survive every collection this family can run — the asymmetry "
                "that justifies tracing.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Tri-colour incremental marking, and the gray worklist",
        tags=["tricolour", "incremental", "pauses"],
        action="Write `COLOURS`, `INC_KEYS`, `init_tricolour`, `increment` and "
               "`finish_marking` in stage_07.py.",
        predict="Why two budget-1 slices must land where one budget-2 slice "
                "lands, and why the incremental collector's verdict has to be "
                "the stop-the-world one's.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The write barrier, and the remembered set",
        tags=["barrier", "remembered-set", "mutator"],
        action="Write `BARRIER_KEYS`, `needs_barrier`, `write` and "
               "`collect_incremental` in stage_08.py.",
        predict="What a black object storing a white pointer loses, and why the "
                "remembered set is the next mark's extra roots.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="Generations: the nursery, promotion, and what survives",
        tags=["generations", "nursery", "promotion"],
        action="Write `GEN_KEYS`, `nursery_collect`, `promote` and "
               "`run_generational` in stage_09.py.",
        predict="Why most objects die young, why the survivors of one collection "
                "are not collected by the next, and why reachability holds per "
                "collection and not per run.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The copying collector, forwarding, and the audit",
        tags=["copying", "forwarding", "audit"],
        action="Write `COPY_KEYS`, `AUDIT_KEYS`, `VERDICTS`, `copy_collect` and "
               "`audit` in stage_10.py.",
        predict="How an object moves without breaking a reference, and why the "
                "audit reads the ledger and not anyone's prose.",
        check=check_10,
    ),
]
