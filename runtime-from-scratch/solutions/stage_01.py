"""The stage 1 solution: the dispatch loop, over the value stack only.

The semantics are the world's reference loop's (`assembler.run_steps`), on
purpose: the steps pins in `PROGRAMS` were measured there, and a runtime whose
semantics differ has a different loop even if every answer looks plausible.
"""

import bytecode as bc

DISPATCH_KEYS = ('stack', 'output', 'steps')

RUNNABLE = ('arith', 'branch', 'countdown', 'fib10')

FRAME_OPS = (bc.OP_LOAD_NAME, bc.OP_STORE_NAME, bc.OP_CALL, bc.OP_RETURN)


def decode(module, ip):
    """The (opcode, operand) pair at `ip`, checked."""
    if not isinstance(ip, int) or ip < 0 or ip >= len(module.code):
        raise bc.BytecodeError(
            "decode at ip %r outside the module's %d instructions"
            % (ip, len(module.code)))
    op, arg = module.code[ip]
    if op not in bc.OP_NAMES:
        raise bc.BytecodeError(
            "opcode %r is not in the ISA, at ip %d" % (op, ip))
    return op, arg


def _need(stack, n, op):
    if len(stack) < n:
        raise bc.BytecodeError(
            "%s needs %d value%s, the stack has %d"
            % (bc.OP_NAMES[op], n, "" if n == 1 else "s", len(stack)))


def execute(module, op, arg, stack):
    """One opcode applied to the value stack, in place; answers the next `ip`."""
    if op in FRAME_OPS:
        raise bc.BytecodeError(
            "%s is a frame operation: the stage 1 loop is frame-free"
            % (bc.OP_NAMES[op],))
    if op == bc.OP_LOAD_CONST:
        stack.append(module.consts[arg])
    elif op == bc.OP_POP:
        _need(stack, 1, op)
        stack.pop()
    elif op == bc.OP_DUP:
        _need(stack, 1, op)
        stack.append(stack[-1])
    elif op == bc.OP_PICK:
        if arg < 0 or arg >= len(stack):
            raise bc.BytecodeError(
                "PICK %d past the bottom of the stack (%d items)"
                % (arg, len(stack)))
        stack.append(stack[-1 - arg])
    elif op == bc.OP_ROT3:
        _need(stack, 3, op)
        stack[-3], stack[-2], stack[-1] = stack[-2], stack[-1], stack[-3]
    elif op in (bc.OP_ADD, bc.OP_SUB, bc.OP_MUL):
        _need(stack, 2, op)
        b = stack.pop()
        a = stack.pop()
        stack.append(a + b if op == bc.OP_ADD else
                     a - b if op == bc.OP_SUB else a * b)
    elif op == bc.OP_NEG:
        _need(stack, 1, op)
        stack.append(-stack.pop())
    elif op == bc.OP_EQ:
        _need(stack, 2, op)
        b = stack.pop()
        a = stack.pop()
        stack.append(1 if a == b else 0)
    elif op == bc.OP_LT:
        _need(stack, 2, op)
        b = stack.pop()
        a = stack.pop()
        stack.append(1 if a < b else 0)
    elif op == bc.OP_GT:
        _need(stack, 2, op)
        b = stack.pop()
        a = stack.pop()
        stack.append(1 if a > b else 0)
    elif op == bc.OP_NOT:
        _need(stack, 1, op)
        stack.append(0 if stack.pop() else 1)
    elif op in (bc.OP_JUMP, bc.OP_LOOP):
        return arg
    elif op == bc.OP_JUMP_IF_FALSE:
        _need(stack, 1, op)
        if not stack.pop():
            return arg
    elif op == bc.OP_HALT:
        return len(module.code)
    else:
        raise bc.BytecodeError(
            "no semantics for %r" % (bc.OP_NAMES.get(op, op),))
    return None


def run(module, limit=10000):
    """The whole loop: dispatch from `module.entry` until `OP_HALT`."""
    stack = []
    ip = module.entry
    steps = 0
    while ip < len(module.code):
        steps += 1
        if steps > limit:
            raise bc.BytecodeError(
                "runaway program: over %d dispatches" % (limit,))
        op, arg = decode(module, ip)
        nxt = execute(module, op, arg, stack)
        ip = nxt if nxt is not None else ip + 1
    return {"stack": tuple(stack), "output": tuple(stack), "steps": steps}
