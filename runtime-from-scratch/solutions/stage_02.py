"""The stage 2 solution: the semantics table and the straight-line cost."""

import bytecode as bc
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS

ARITH = (bc.OP_ADD, bc.OP_SUB, bc.OP_MUL, bc.OP_NEG, bc.OP_EQ, bc.OP_LT,
         bc.OP_GT, bc.OP_NOT)

STACK_OPS = (bc.OP_POP, bc.OP_DUP, bc.OP_PICK, bc.OP_ROT3)


def _need(stack, n, op):
    if len(stack) < n:
        raise bc.BytecodeError(
            "%s needs %d value%s, the stack has %d"
            % (bc.OP_NAMES[op], n, "" if n == 1 else "s", len(stack)))


def step(module, op, arg, stack):
    """One opcode's semantics on the value stack, in place; answers None."""
    if op in FRAME_OPS:
        raise bc.BytecodeError(
            "%s is a frame operation: the stage 2 semantics are frame-free"
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
    elif op == bc.OP_ADD:
        _need(stack, 2, op)
        b = stack.pop()
        a = stack.pop()
        stack.append(a + b)
    elif op == bc.OP_SUB:
        _need(stack, 2, op)
        b = stack.pop()
        a = stack.pop()
        stack.append(a - b)
    elif op == bc.OP_MUL:
        _need(stack, 2, op)
        b = stack.pop()
        a = stack.pop()
        stack.append(a * b)
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
    else:
        raise bc.BytecodeError(
            "no semantics for %r" % (bc.OP_NAMES.get(op, op),))
    return None


def steps_of(module, limit=10000):
    """The step total of `module`: dispatch until HALT, count every dispatch.

    The world is deterministic and the jumps decide off the stack, so walking
    them here answers the same total `run` does — the stage's own arithmetic,
    reproducible before stage 3 composes it with control flow of its own."""
    stack = []
    steps = 0
    ip = module.entry
    while ip < len(module.code):
        steps += 1
        if steps > limit:
            raise bc.BytecodeError(
                "runaway program: over %d dispatches" % (limit,))
        op, arg = module.code[ip]
        if op == bc.OP_HALT:
            break
        if op in (bc.OP_JUMP, bc.OP_LOOP):
            ip = arg
        elif op == bc.OP_JUMP_IF_FALSE:
            ip = arg if not stack.pop() else ip + 1
        else:
            step(module, op, arg, stack)
            ip += 1
    return steps
