"""The assembler: source text to a Module, deterministically.

The assembler is provided because the course's subject is what *runs* the
bytecode, not what produces it — but it is provided as a worked tool, not a
black box: a stage may assemble a program to check its own reading of the
instruction set, and the fixtures' expected modules were produced by this
file. Its rules are the encoding's rules:

  * one instruction per line: `OP` for a no-operand form, `OP arg` otherwise;
  * `arg` is an int for CONST/TARGET forms (a TARGET may be written as a
    label), a bare name for NAME forms;
  * `name:` on its own line declares a label; `CALL name` and `LOAD_CONST
    "text"` / `'text'` are the two conveniences (a string constant is interned
    into CONSTS on first use, and repeated on no second use);
  * assembling the same source twice answers an equal Module — determinism is
    a property the checker can hold the assembler to, so a runtime's failure
    is never "the world changed".
"""

import re
import importlib


def _bc():
    """The bytecode module, imported lazily: bytecode's own registry calls
    this assembler at import time, so a top-level import would be cyclic."""
    return importlib.import_module("bytecode")

_LINE = re.compile(r"""^\s*
    (?P<label>[A-Za-z_][A-Za-z0-9_]*:)? \s*
    (?P<op>[A-Z_][A-Z_0-9]*)? \s*
    (?P<arg>.+)? \s*$
""", re.VERBOSE)

_STR = re.compile(r"""^(['"])(.*)\1$""")


class AsmError(ValueError):
    """A source-level mistake: an unknown mnemonic, a label used and never
    declared, a duplicate label, an arg of the wrong form. Raised naming the
    line number — the one thing a typo needs to be findable."""


def parse_source(text):
    """Source lines -> a list of (op, arg_token, lineno), labels resolved to
    instruction indices but *not* validated (assemble does that)."""
    instructions = []           # (op, raw_arg, lineno)
    labels = {}                 # name -> instruction index
    for lineno, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        m = _LINE.match(raw)
        if not m:
            raise AsmError("line %d: cannot parse %r" % (lineno, raw))
        label, op, arg = m.group("label"), m.group("op"), m.group("arg")
        if label:
            name = label[:-1]
            if name in labels:
                raise AsmError("line %d: duplicate label %r" % (lineno, name))
            labels[name] = len(instructions)
        if not op:
            continue
        instructions.append((op, arg, lineno))
    return instructions, labels


def assemble(text):
    """Assemble source text into a `bytecode.Module`.

    Deterministic: same text in, equal Module out, every time. Raises
    AsmError naming the line for anything a human can fix in one look.
    """
    instructions, labels = parse_source(text)
    consts = []                 # list keeps first-use order; tuple at the end
    names = []
    const_index = {}            # value -> index (interning)
    name_index = {}
    code = []

    def intern_const(value):
        if value not in const_index:
            const_index[value] = len(consts)
            consts.append(value)
        return const_index[value]

    def intern_name(name):
        if name not in name_index:
            name_index[name] = len(names)
            names.append(name)
        return name_index[name]

    bc = _bc()
    for op_name, raw_arg, lineno in instructions:
        op = bc.OPCODES.get(op_name)
        if op is None:
            raise AsmError("line %d: unknown opcode %r" % (lineno, op_name))
        form = bc.FORMS[op]
        if form == "NONE":
            if raw_arg:
                raise AsmError("line %d: %s takes no operand, got %r"
                               % (lineno, op_name, raw_arg))
            code.append((op, None))
            continue
        if raw_arg is None:
            raise AsmError("line %d: %s needs an operand" % (lineno, op_name))
        token = raw_arg.strip()
        if form == "CONST":
            s = _STR.match(token)
            if s:
                arg = intern_const(s.group(2))
            else:
                try:
                    value = int(token, 0)
                except ValueError:
                    raise AsmError("line %d: %s operand %r is not an int or "
                                   "a quoted string" % (lineno, op_name, token))
                arg = intern_const(value)
        elif form == "NAME":
            arg = intern_name(token)
        elif form == "TARGET":
            if token in labels:
                arg = labels[token]
            else:
                try:
                    arg = int(token, 0)
                except ValueError:
                    raise AsmError("line %d: label %r never declared"
                                   % (lineno, token))
        elif form == "DEPTH":
            try:
                arg = int(token, 0)
            except ValueError:
                raise AsmError("line %d: %s operand %r is not an int"
                               % (lineno, op_name, token))
            if arg < 0:
                raise AsmError("line %d: %s depth %r is negative"
                               % (lineno, op_name, token))
        else:                   # unreachable while FORMS is closed
            raise AsmError("line %d: no form for %s" % (lineno, op_name))
        code.append((op, arg))

    return bc.Module(tuple(consts), tuple(code), tuple(names),
                     labels.get("main", 0))


# --- the convenience the fixtures use: a program's steps must be measured ---
def run_steps(module, limit=10000):
    """A *reference* dispatch loop — deliberately naive, deliberately here.

    This is not the course's runtime (that is the student's job); it is how
    the world measured the `steps` each program in PROGRAMS demands, so a
    stage's own count can be held against a number nobody made up. It answers
    (output_lines, steps) and refuses a program that runs past `limit` — an
    infinite loop is a bug in the world, not something to wait out.
    """
    bc = _bc()
    stack = []
    out = []
    ip = module.entry
    steps = 0
    while ip < len(module.code):
        steps += 1
        if steps > limit:
            raise bc.BytecodeError("runaway program: over %d steps" % (limit,))
        op, arg = module.code[ip]
        ip += 1
        if op == bc.OP_LOAD_CONST:
            stack.append(module.consts[arg])
        elif op == bc.OP_LOAD_NAME:
            raise bc.BytecodeError("LOAD_NAME is a frame operation: the "
                                   "reference loop runs frame-free programs "
                                   "only (see PROGRAMS with heap=False)")
        elif op == bc.OP_STORE_NAME:
            raise bc.BytecodeError("STORE_NAME is a frame operation")
        elif op == bc.OP_POP:
            stack.pop()
        elif op == bc.OP_DUP:
            stack.append(stack[-1])
        elif op == bc.OP_PICK:
            if arg >= len(stack):
                raise bc.BytecodeError("PICK %d past the bottom of the stack "
                                       "(%d items)" % (arg, len(stack)))
            stack.append(stack[-1 - arg])
        elif op == bc.OP_ROT3:
            if len(stack) < 3:
                raise bc.BytecodeError("ROT3 needs three items, stack has %d"
                                       % (len(stack),))
            stack[-3], stack[-2], stack[-1] = (stack[-2], stack[-1],
                                               stack[-3])
        elif op in (bc.OP_ADD, bc.OP_SUB, bc.OP_MUL):
            b = stack.pop()
            a = stack.pop()
            stack.append(a + b if op == bc.OP_ADD else
                         a - b if op == bc.OP_SUB else a * b)
        elif op == bc.OP_NEG:
            stack.append(-stack.pop())
        elif op == bc.OP_EQ:
            b = stack.pop(); a = stack.pop()
            stack.append(1 if a == b else 0)
        elif op == bc.OP_LT:
            b = stack.pop(); a = stack.pop()
            stack.append(1 if a < b else 0)
        elif op == bc.OP_GT:
            b = stack.pop(); a = stack.pop()
            stack.append(1 if a > b else 0)
        elif op == bc.OP_NOT:
            stack.append(0 if stack.pop() else 1)
        elif op in (bc.OP_JUMP, bc.OP_LOOP):
            ip = arg
        elif op == bc.OP_JUMP_IF_FALSE:
            if not stack.pop():
                ip = arg
        elif op == bc.OP_CALL or op == bc.OP_RETURN:
            raise bc.BytecodeError("CALL/RETURN need frames: the reference "
                                   "loop runs frame-free programs only")
        elif op == bc.OP_HALT:
            break
        else:
            raise bc.BytecodeError("no semantics for %r" % (op,))
    return stack, out, steps
