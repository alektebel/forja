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

OP_CALL = 30          # call NAMES[arg]: a new frame, its args already stacked
OP_RETURN = 31        # pop the return value, end the current frame
OP_HALT = 32          # stop the module

OPCODES = {
    "LOAD_CONST": OP_LOAD_CONST, "LOAD_NAME": OP_LOAD_NAME,
    "STORE_NAME": OP_STORE_NAME, "POP": OP_POP, "DUP": OP_DUP,
    "ADD": OP_ADD, "SUB": OP_SUB, "MUL": OP_MUL, "NEG": OP_NEG,
    "EQ": OP_EQ, "LT": OP_LT, "GT": OP_GT, "NOT": OP_NOT,
    "JUMP": OP_JUMP, "JUMP_IF_FALSE": OP_JUMP_IF_FALSE, "LOOP": OP_LOOP,
    "CALL": OP_CALL, "RETURN": OP_RETURN, "HALT": OP_HALT,
}
#: the reverse: op int -> its mnemonic. The decoder's error messages name it.
OP_NAMES = {v: k for k, v in OPCODES.items()}

# --- the operand forms -------------------------------------------------------
# no-operand: NONE. index into CONSTS: CONST. index into NAMES: NAME.
# an absolute instruction index: TARGET.
FORMS = {
    OP_LOAD_CONST: "CONST", OP_LOAD_NAME: "NAME", OP_STORE_NAME: "NAME",
    OP_POP: "NONE", OP_DUP: "NONE",
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
        self.consts = tuple(consts)
        self.code = tuple(code)
        self.names = tuple(names)
        self.entry = entry

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
