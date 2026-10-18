"""The stage 3 solution: the composed loop, the branch question, the totals."""

import bytecode as bc
from stage_01 import DISPATCH_KEYS, RUNNABLE, FRAME_OPS
from stage_02 import ARITH, STACK_OPS
from stage_02 import step as _step

JUMPS = (bc.OP_JUMP, bc.OP_JUMP_IF_FALSE, bc.OP_LOOP)


def branch_taken(module, ip, stack):
    """Whether the instruction at `ip` jumps, given the stack as it stands."""
    if not isinstance(ip, int) or ip < 0 or ip >= len(module.code):
        raise bc.BytecodeError(
            "branch at ip %r outside the module's %d instructions"
            % (ip, len(module.code)))
    op, arg = module.code[ip]
    if op == bc.OP_JUMP or op == bc.OP_LOOP:
        return True
    if op == bc.OP_JUMP_IF_FALSE:
        if not stack:
            raise bc.BytecodeError(
                "JUMP_IF_FALSE needs a value, the stack is empty")
        return not stack[-1]
    return None


def run_control(module, limit=10000):
    """The composed loop: stage 2's semantics plus this stage's jumps."""
    stack = []
    ip = module.entry
    steps = 0
    while ip < len(module.code):
        steps += 1
        if steps > limit:
            raise bc.BytecodeError(
                "runaway program: over %d dispatches" % (limit,))
        if not isinstance(ip, int) or ip < 0 or ip >= len(module.code):
            raise bc.BytecodeError(
                "ip %r outside the module's %d instructions"
                % (ip, len(module.code)))
        op, arg = module.code[ip]
        if op == bc.OP_HALT:
            break
        if op in (bc.OP_JUMP, bc.OP_LOOP):
            ip = arg
        elif op == bc.OP_JUMP_IF_FALSE:
            if not stack:
                raise bc.BytecodeError(
                    "JUMP_IF_FALSE needs a value, the stack is empty")
            ip = arg if not stack.pop() else ip + 1
        elif op in FRAME_OPS:
            raise bc.BytecodeError(
                "%s is a frame operation: the stage 3 loop is frame-free"
                % (bc.OP_NAMES[op],))
        else:
            _step(module, op, arg, stack)
            ip += 1
    return {"stack": tuple(stack), "output": tuple(stack), "steps": steps}


def step_totals(names):
    """Each named program's step total, by name, from this stage's own loop."""
    totals = {}
    for name in names:
        if name not in bc.PROGRAMS:
            raise bc.BytecodeError(
                "no provided program named %r (the registry holds %s)"
                % (name, ", ".join(sorted(bc.PROGRAMS))))
        totals[name] = run_control(bc.PROGRAMS[name]["module"])["steps"]
    return totals
