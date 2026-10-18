"""The bytecode: a closed instruction set, an encoding, and programs to run.

A runtime is a program that runs other programs, and the only honest way to
teach one offline is to hand the *other* programs over as data the student's
runtime has to satisfy. This module is that data. It is deliberately small:

  * **The instruction set** is a closed vocabulary of 24 opcodes (§ `OPCODES`),
    each with the operand shapes it takes (`FORMS`): no operand, one constant
    index, one name, or two names. A decoder that invents a form, or an
    assembler that emits one, is wrong by construction — the tables decide.
  * **A module** is what the assembler emits: a `CONSTS` tuple (the constants
    the code indexes into), a `CODE` tuple of `(op, arg)` pairs, a `NAMES`
    tuple, and the module's `ENTRY` point. Everything is a tuple — a module is
    data, never a place to mutate.
  * **The programs** (`PROGRAMS`) are the answer key: seven programs, each with
    a name, its source, its assembled module, the output a correct runtime
    prints, and the *step count* a correct runtime spends printing it. The
    step count is the discipline: a runtime that executes a wrong extra
    instruction, or skips one, is wrong even when the output matches — the
    same program on two correct runtimes must spend the same steps.
  * **The heap demand** is declared per program (`HEAP_DEMAND`): the objects a
    program's execution *must* allocate, by shape, so a collector's counts can
    be checked against arithmetic rather than vibes. A program that allocates
    three pairs and two strings says so, and the checker reads it.

Nothing in this module knows anything about the course: it has no idea what a
frame, a call stack or a nursery is. It decodes, it answers what a program
*demands*, and its records — the expected output, the expected steps, the
expected allocations — are the tie-breaker a stage's report has to agree with.
"""

POLICY_VERSION = "runtime-policy-1"

# --- the instruction set -----------------------------------------------------
# every opcode is a two-letter-ish mnemonic bound to a small int. The encoding
# of an instruction in CODE is the pair (op, arg): arg is always an int index
# into one of the module's tables (CONSTS for constants, NAMES for names), or
# None for the ops that take no operand.

OP_LOAD_CONST = 1     # push CONSTS[arg]
OP_LOAD_NAME = 2      # push the value of NAMES[arg] from the current frame
OP_STORE_NAME = 3    # pop into NAMES[arg] in the current frame
OP_POP = 4            # discard the top of the stack
OP_DUP = 5            # duplicate the top of the stack

OP_ADD = 10           # pop b, pop a, push a + b  (ints only; TypeError is data)
OP_SUB = 11           # pop b, pop a, push a - b
OP_MUL = 12           # pop b, pop a, push a * b
OP_NEG = 13           # pop a, push -a

OP_EQ = 14            # pop b, pop a, push 1 if a == b else 0
OP_LT = 15            # pop b, pop a, push 1 if a < b else 0
OP_GT = 16            # pop b, pop a, push 1 if a > b else 0
OP_NOT = 17           # pop a, push 0 if truthy else 1

OP_JUMP = 20          # unconditional: next instruction is CODE[arg]
OP_JUMP_IF_FALSE = 21  # pop; if falsy, next instruction is CODE[arg]
OP_LOOP = 22          # like JUMP, but the counted-jump a loop back-edge emits

OP_PICK = 28          # copy the n-th item from the top onto it (PICK 0 = DUP)
OP_ROT3 = 29          # rotate the top three: (a, b, c) -> (b, c, a) — the
                      # shuffle a loop body needs when the counter lives on top
OP_CALL = 30          # call NAMES[arg]: a new frame, its args already stacked
OP_RETURN = 31        # pop the return value, end the current frame
OP_HALT = 32          # stop the module

OPCODES = {
    "LOAD_CONST": OP_LOAD_CONST, "LOAD_NAME": OP_LOAD_NAME,
    "STORE_NAME": OP_STORE_NAME, "POP": OP_POP, "DUP": OP_DUP,
    "PICK": OP_PICK, "ROT3": OP_ROT3,
    "ADD": OP_ADD, "SUB": OP_SUB, "MUL": OP_MUL, "NEG": OP_NEG,
    "EQ": OP_EQ, "LT": OP_LT, "GT": OP_GT, "NOT": OP_NOT,
    "JUMP": OP_JUMP, "JUMP_IF_FALSE": OP_JUMP_IF_FALSE, "LOOP": OP_LOOP,
    "CALL": OP_CALL, "RETURN": OP_RETURN, "HALT": OP_HALT,
}
#: the reverse: op int -> its mnemonic. The decoder's error messages name it.
OP_NAMES = {v: k for k, v in OPCODES.items()}

# no-operand: NONE. index into CONSTS: CONST. index into NAMES: NAME.
# an absolute instruction index: TARGET. a stack depth to copy: DEPTH.
FORMS = {
    OP_LOAD_CONST: "CONST", OP_LOAD_NAME: "NAME", OP_STORE_NAME: "NAME",
    OP_POP: "NONE", OP_DUP: "NONE", OP_PICK: "DEPTH", OP_ROT3: "NONE",
    OP_ADD: "NONE", OP_SUB: "NONE", OP_MUL: "NONE", OP_NEG: "NONE",
    OP_EQ: "NONE", OP_LT: "NONE", OP_GT: "NONE", OP_NOT: "NONE",
    OP_JUMP: "TARGET", OP_JUMP_IF_FALSE: "TARGET", OP_LOOP: "TARGET",
    OP_CALL: "NAME", OP_RETURN: "NONE", OP_HALT: "NONE",
}

#: the ops whose arg indexes CONSTS / NAMES / CODE respectively
CONST_OPS = tuple(op for op, f in FORMS.items() if f == "CONST")
NAME_OPS = tuple(op for op, f in FORMS.items() if f == "NAME")
TARGET_OPS = tuple(op for op, f in FORMS.items() if f == "TARGET")

# --- the heap-object shapes a program may demand ------------------------------
#: a cons pair: two slots, both references or ints
SHAPE_PAIR = "pair"
#: a fixed-size array of SLOTS references, allocated with a length
SHAPE_ARRAY = "array"
#: an immutable boxed value (an int or a string) — the leaf a pair holds
SHAPE_BOX = "box"
SHAPES = (SHAPE_PAIR, SHAPE_ARRAY, SHAPE_BOX)


class BytecodeError(ValueError):
    """A caller's mistake: a program that is not a program, an op without a
    form, an arg outside its table. Raised naming the offender; a runtime's
    *output* decisions are returned, never raised."""


def form_of(op):
    """The operand form of `op`, or raise BytecodeError naming it."""
    f = FORMS.get(op)
    if f is None:
        raise BytecodeError("unknown opcode: %r" % (op,))
    return f


class Module:
    """An assembled module: `consts`, `code`, `names`, `entry`.

    Tuples all the way down — a module is emitted once and never mutated. Two
    modules are equal when all four fields are equal, which is what makes
    "the assembler is deterministic" checkable.
    """
    __slots__ = ("consts", "code", "names", "entry")

    def __init__(self, consts, code, names, entry):
        object.__setattr__(self, "consts", tuple(consts))
        object.__setattr__(self, "code", tuple(code))
        object.__setattr__(self, "names", tuple(names))
        object.__setattr__(self, "entry", entry)

    def __setattr__(self, name, value):
        raise BytecodeError("a Module is immutable: %r cannot be set" % (name,))

    def __eq__(self, other):
        return (isinstance(other, Module)
                and self.consts == other.consts
                and self.code == other.code
                and self.names == other.names
                and self.entry == other.entry)

    def __repr__(self):
        return "Module(consts=%d, code=%d, names=%d, entry=%d)" % (
            len(self.consts), len(self.code), len(self.names), self.entry)


# --- the provided programs ----------------------------------------------------
# Each entry: name -> {"source": str, "module": Module, "output": tuple[str],
#                      "steps": int, "heap": {shape: count}}
# "steps" counts EVERY dispatch of the interpreter loop: one per instruction
# executed, including the HALT. A correct runtime matches it exactly.

PROGRAMS = {}
def _program(name, source, output, heap, steps=None):
    """Register one provided program: assemble it here, once, at import.

    `steps` is pinned only for the frame-free programs the reference loop can
    run (stages 1–3's programs); the heap programs' step count depends on the
    runtime's own allocation strategy, so the world pins their *output* and
    their *heap demand* and leaves the steps to the stage's report.
    """
    from assembler import assemble
    PROGRAMS[name] = {"source": source, "module": assemble(source),
                      "output": tuple(output), "heap": dict(heap),
                      "steps": steps}


# 1. arithmetic: 20 - 4*3 = 8, printed once. No allocation.
_program("arith", '''
    LOAD_CONST 20
    LOAD_CONST 4
    LOAD_CONST 3
    MUL
    SUB
    HALT
''', output=[8], heap={}, steps=6)

# 2. branch: sign of -7. No allocation.
_program("branch", '''
    LOAD_CONST -7
    LOAD_CONST 0
    LT
    JUMP_IF_FALSE positive
    LOAD_CONST "negative"
    JUMP done
positive:
    LOAD_CONST "nonnegative"
done:
    HALT
''', output=["negative"], heap={}, steps=7)

# 3. countdown: descends 5→0, keeping every value it passes: the final stack
#    holds 5, 4, 3, 2, 1, 0 — the program's output is what it leaves behind.
#    No allocation.
_program("countdown", '''
    LOAD_CONST 5
loop:
    DUP
    LOAD_CONST 1
    SUB
    DUP
    JUMP_IF_FALSE done
    JUMP loop
done:
    HALT
''', output=[5, 4, 3, 2, 1, 0], heap={}, steps=31)

# 4. fib: f(10) = 55, computed iteratively. The loop holds (b, a, counter),
#    b = f(k+1), a = f(k); each iteration PICKs the pair back out from under
#    the counter, adds it, and ROT3s the counter up again. The counter is
#    why ROT3 exists: without it a frame-free loop cannot keep a value
#    *under* the working pair. No allocation.
_program("fib10", '''
    LOAD_CONST 1
    LOAD_CONST 0
    LOAD_CONST 10
loop:
    DUP
    JUMP_IF_FALSE done
    LOAD_CONST 1
    SUB
    PICK 2
    PICK 2
    ADD
    ROT3
    POP
    ROT3
    ROT3
    JUMP loop
done:
    ROT3
    POP
    POP
    HALT
''', output=[55], heap={}, steps=129)

# 5-7. the heap programs: their source is not bytecode — they are *heap
# shapes* the runtime executes by its own means (a stage that has not built
# the allocator yet answers them with a refusal, which is itself graded).
# `source` documents the shape; `heap` is the demand a check holds the
# runtime's ledger against.
_program("conslist", '''
    # build the cons list 1 -> 2 -> 3 (pair holds value-box, next-pair),
    # then sum it: every box's value, added, is 6. Three pairs + three boxes.
    (shape only — executed by the runtime's allocator, not by dispatch)
''', output=[6], heap={SHAPE_PAIR: 3, SHAPE_BOX: 3})

_program("shared", '''
    # two parents, one shared child: parent1.pair(box4, child), parent2.pair(
    # box5, child) — the child's refcount reaches 2 and a collector that
    # frees it when the first parent dies has lost it for the second. The
    # sum of both parents' box values plus the child's is 9. Four pairs,
    # four boxes.
    (shape only — executed by the runtime's allocator, not by dispatch)
''', output=[9], heap={SHAPE_PAIR: 4, SHAPE_BOX: 4})

_program("cycle", '''
    # a -> b -> a, both dropped from the roots together: the cycle's
    # refcount never falls to zero from the outside, so reference counting
    # keeps both alive forever and mark-sweep frees exactly two pairs and
    # two boxes. The sum of the boxes is 2.
    (shape only — executed by the runtime's allocator, not by dispatch)
''', output=[2], heap={SHAPE_PAIR: 2, SHAPE_BOX: 2})
