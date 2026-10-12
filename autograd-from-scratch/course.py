"""Autograd From Scratch — course manifest.

Ten graded stages that build what a training framework does with the
interconnect: the shape calculus and the memory ledger of one model, then the
parallelisation plans on top of it — data parallel with its buckets, ZeRO-1/2,
ZeRO-3/FSDP, tensor parallel's two all-reduces per block, pipeline parallel and
its schedules, expert parallel's two all-to-alls, context parallel's ring
attention, and the configuration that picks an axis split for a given number of
devices.

The thesis of the whole course is one sentence, and every stage's check asserts
it: ONE MODEL, MANY DEVICES, THE SAME MATH. A plan is data — the collectives it
issues, where they happen, how many bytes they move — and three things are
checked independently: its bytes (per rank and on the network, both counted
from the plan), its memory ledger (what each rank holds when), and its
semantics, by recomputing the reference single-device arithmetic over the plan's
own decomposition. The failures this course makes visible are the silent ones: a
ZeRO-3 that all-gathers the world instead of the layer, a tensor parallel with
one all-reduce per block, a bubble formula that ignores the micro-batches, a
plan that shards the state but drops the remainder, comms added to compute.

The world is provided twice over: `fabric.py` is I9's, verbatim (links with a
bandwidth and a latency, four topologies, an executor and its cost semantics —
a byte costs what it says), and `model.py` is this course's shape calculus and
reference arithmetic (the 16 bytes a parameter costs through a step, the
integer matmuls and gradients a plan must reproduce exactly, the fixtures). The
exercise is the ten plans and their ledgers. No network, no `time`, no
`threading`, no `asyncio`, no unseeded randomness and no module-level mutable
state: ticks are counted, not timed, and no number here is a float.

    python3 codecraft/cli.py run autograd-from-scratch
"""

from codecraft.api import stage

TITLE = "Autograd From Scratch"
DESCRIPTION = ("The plans on top of the interconnect: count what one parameter "
               "costs through a training step (params, gradients, optimizer "
               "state, masters) and what each rank holds when, then write data "
               "parallel with its gradient buckets hidden behind compute, "
               "ZeRO-1/2/3 and FSDP, tensor parallel's f/g blocks with their "
               "two all-reduces, pipeline schedules and their bubbles, expert "
               "parallel's dispatch and combine, ring attention's exact "
               "accumulation, and the configuration that picks the axis split "
               "by bytes instead of by fashion.")
LEVEL = "advanced"
ORDER = 19

# --- the checks. Each one is self-contained: its fixtures are nested
# inside it because `course.py` is one namespace for ten stages.

import json
import os
import shutil
import sys
import tempfile


# --- stage 1 -----------------------------------------------------------------------
def check_1():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import exact
    import stage_01 as s

    Rational = exact.Rational

    def node(nested):
        """A stage-1 leaf holding the `exact.Tensor` `nested` describes."""
        return s.Node(exact.from_nested(nested))

    # ---- the container: the frozen fields, and the mutable grad ------------

    leaf = node((2, 3))
    assert set(vars(leaf)) == {"value", "parents", "backward", "requires_grad",
                               "grad"}, (
        "a Node's fields are %r, not the frozen (value, parents, backward, "
        "requires_grad, grad)" % (sorted(vars(leaf)),))
    assert len(vars(leaf)) == 5, (
        "a Node has %d fields, not the frozen five" % (len(vars(leaf)),))
    assert leaf.value == exact.from_nested((2, 3)), (
        "a Node's value reads %r, not the tensor it was built from"
        % (leaf.value,))
    assert leaf.parents == () and isinstance(leaf.parents, tuple), (
        "a Node built from one value has parents %r, not the empty tuple"
        % (leaf.parents,))
    assert leaf.backward is None, (
        "a leaf's backward is %r, not None: there is no local derivative to "
        "run" % (leaf.backward,))
    assert leaf.requires_grad is True, (
        "a Node's requires_grad starts %r, not True" % (leaf.requires_grad,))
    assert leaf.grad == exact.zeros((2,)), (
        "a Node's grad starts %r, not the zeros of its value's shape"
        % (leaf.grad,))
    assert leaf.grad.shape == (2,), (
        "a Node's grad has shape %r, not the value's (2,): a gradient owes its "
        "operand its shape" % (leaf.grad.shape,))
    assert leaf.grad is not leaf.value, (
        "a Node's grad is its value's tensor, so a gradient would overwrite a "
        "value")

    leaf.grad = exact.ones((2,))
    assert leaf.grad == exact.ones((2,)), (
        "a Node's grad field is not writable: it took %r instead of the ones "
        "that were assigned" % (leaf.grad,))
    leaf.value = exact.from_nested((5, 6))
    assert leaf.value == exact.from_nested((5, 6)), (
        "a Node's value field is not writable: the container is mutable")
    leaf.requires_grad = False
    assert leaf.requires_grad is False, (
        "a Node's requires_grad field is not writable")
    leaf.requires_grad = True

    a1 = node((1, 2))
    a2 = node((1, 2))
    assert a1 == a1, "a Node is not equal to itself"
    assert a1 != a2 and not (a1 == a2), (
        "two distinct nodes with the same value compare equal: __eq__ must be "
        "identity, or the walk's seen set merges a diamond's two paths")
    assert not (a1 == 7) and a1 != 7, (
        "a Node compares equal to 7: __eq__ must be identity")
    assert len({a1, a1, a2}) == 2, (
        "{a1, a1, a2} has %d members, not two: a node's hash must go with its "
        "identity, or the walk cannot remember it" % (len({a1, a1, a2}),))

    text = repr(leaf)
    assert isinstance(text, str) and text.startswith("Node("), (
        "repr(node) is %r, not a Node(...) naming the container" % (text,))
    assert repr(leaf.value) in text, (
        "repr(node) is %r and does not show the node's value" % (text,))

    x = node((1, 2))
    y = node((3, 4))
    joined = s.Node(exact.from_nested((4, 6)), parents=[x, y])
    assert isinstance(joined.parents, tuple) and joined.parents == (x, y), (
        "a Node's parents read %r, not the tuple (x, y) of the two nodes it "
        "was given" % (joined.parents,))
    assert joined.parents[0] is x and joined.parents[1] is y, (
        "a Node's parents are not the nodes themselves: (%r, %r)"
        % (joined.parents[0], joined.parents[1]))

    message = _refuses(exact.AutogradError,
                       "a Node whose value is not an exact.Tensor",
                       lambda: s.Node((1, 2)))
    assert "value" in message and "Tensor" in message, (
        "the refusal of a Node whose value is not a Tensor does not name it: "
        "%r" % (message,))

    # ---- add and mul: the forward is exact's, element for element ----------

    CASES = (
        (3, -4),
        ((2,), (3,)),
        ((1, 2, 3), (-4, 5, -6)),
        (((1, 2), (3, 4)), ((5, 6), (7, 8))),
        (((1, 2, 3), (4, 5, 6)), ((-1, -2, -3), (-4, -5, -6))),
        ((Rational(1, 2), Rational(-3, 4)), (Rational(8), Rational(-5, 2))),
        (((Rational(1, 3), Rational(2, 5)), (Rational(-7, 4), Rational(0))),
         ((Rational(3, 2), Rational(-1, 5)), (Rational(4), Rational(9, 7)))),
    )

    for left, right in CASES:
        x = node(left)
        y = node(right)
        shape = x.value.shape
        assert shape == y.value.shape, (
            "the check's fixture is ragged: %r against %r" % (shape, y.value.shape))
        for name, build, forward in (("add", s.add, exact.add),
                                     ("mul", s.mul, exact.mul)):
            made = build(x, y)
            assert made.value == forward(x.value, y.value), (
                "%s's value is %r, not exact.%s of its operands, %r: the "
                "forward is the provided algebra, element for element"
                % (name, made.value, name, forward(x.value, y.value)))
            assert made.value.cells == forward(x.value, y.value).cells, (
                "%s's value has the cells %r, not exact.%s's %r"
                % (name, made.value.cells, name, forward(x.value, y.value).cells))
            assert made.value.shape == shape, (
                "%s's value has shape %r, not the operands' %r"
                % (name, made.value.shape, shape))
            assert made.parents == (x, y), (
                "%s's parents are %r, not the two operands in the order they "
                "were passed" % (name, made.parents))
            assert made.backward is not None and callable(made.backward), (
                "%s's node carries %r, not a local backward: no gradient can "
                "leave it" % (name, made.backward))
            assert made.grad == exact.zeros(shape), (
                "%s's node starts with grad %r, not the zeros of the value's "
                "shape" % (name, made.grad))
            assert x.grad == exact.zeros(shape) and y.grad == exact.zeros(shape), (
                "building %s touched an operand's grad: %r and %r"
                % (name, x.grad, y.grad))
            assert made.grad.shape == shape and x.grad.shape == shape, (
                "%s's gradients have shapes %r and %r, not the operands' %r"
                % (name, made.grad.shape, x.grad.shape, shape))
        flipped = s.mul(y, x)
        assert flipped.parents == (y, x), (
            "mul(y, x) has parents %r, not (y, x): the operand order is the "
            "order the value was built in" % (flipped.parents,))
        assert flipped.value == exact.mul(y.value, x.value), (
            "mul(y, x) has the value %r, not exact.mul of its operands"
            % (flipped.value,))

    # ---- the local derivatives, on the same sweep -------------------------

    for left, right in CASES:
        x = node(left)
        y = node(right)
        shape = x.value.shape
        total = s.add(x, y)
        result = s.backward(total)
        assert result is None, (
            "backward returned %r instead of leaving the grads on the nodes"
            % (result,))
        assert total.grad == exact.ones(shape), (
            "after a backward the root's grad is %r, not the seed ones"
            % (total.grad,))
        assert x.grad == exact.ones(shape) and y.grad == exact.ones(shape), (
            "d(x + y)/dx is %r and d(x + y)/dy is %r, not the seed one each"
            % (x.grad, y.grad))
        assert x.grad.shape == shape and y.grad.shape == shape, (
            "the add gradients have shapes %r and %r, not the operands' %r"
            % (x.grad.shape, y.grad.shape, shape))

        x = node(left)
        y = node(right)
        product = s.mul(x, y)
        assert s.backward(product) is None, "backward returned something"
        assert x.grad == y.value, (
            "d(x * y)/dx is %r, not the other operand %r: the product rule's "
            "two operands must not be swapped" % (x.grad, y.value))
        assert y.grad == x.value, (
            "d(x * y)/dy is %r, not the other operand %r" % (y.grad, x.value))
        assert x.grad.shape == shape and y.grad.shape == shape, (
            "the mul gradients have shapes %r and %r, not the operands' %r"
            % (x.grad.shape, y.grad.shape, shape))
        assert all(isinstance(cell, Rational)
                   for cell in x.grad.cells + y.grad.cells + product.grad.cells), (
            "a gradient cell is not an exact.Rational: %r"
            % (x.grad.cells + y.grad.cells + product.grad.cells,))

    # ---- a chain, a diamond, and a leaf root ------------------------------

    x = node((2, 3))
    square = s.mul(x, x)
    out = s.add(square, x)
    assert square.value == exact.from_nested((4, 9)), (
        "x * x is %r, not (4, 9)" % (square.value,))
    assert out.value == exact.from_nested((6, 12)), (
        "x * x + x is %r, not (6, 12)" % (out.value,))
    assert s.backward(out) is None, "backward returned something"
    assert square.grad == exact.ones((2,)), (
        "d(x*x + x)/d(x*x) is %r, not the seed one" % (square.grad,))
    assert out.grad == exact.ones((2,)), (
        "the root's grad is %r, not the seed ones" % (out.grad,))
    assert x.grad == exact.from_nested((5, 7)), (
        "d(x*x + x)/dx is %r, not 2x + 1 = (5, 7): every path out of x adds to "
        "the one grad" % (x.grad,))

    x = node((2, -3))
    one_way = s.mul(x, x)
    other_way = s.mul(x, x)
    twice = s.add(one_way, other_way)
    assert twice.value == exact.from_nested((8, 18)), (
        "2 * x * x is %r, not (8, 18)" % (twice.value,))
    assert s.backward(twice) is None, "backward returned something"
    assert one_way.grad == exact.ones((2,)) and other_way.grad == exact.ones((2,)), (
        "the two paths' grads are %r and %r, not the seed one each"
        % (one_way.grad, other_way.grad))
    assert x.grad == exact.from_nested((8, -12)), (
        "d(2 x^2)/dx is %r, not 4x = (8, -12): two distinct nodes with the same "
        "value are two nodes, and both walk into x" % (x.grad,))

    lone = node((4, 5))
    assert s.backward(lone) is None, "backward returned something"
    assert lone.grad == exact.ones((2,)), (
        "a backward from a leaf root left %r, not the seed it was handed"
        % (lone.grad,))

    scalar = node(5)
    scalar_square = s.mul(scalar, scalar)
    assert s.backward(scalar_square) is None, "backward returned something"
    assert scalar_square.value == exact.from_nested(25), (
        "a scalar x * x is %r, not 25" % (scalar_square.value,))
    assert scalar.grad == exact.from_nested(10), (
        "d(x^2)/dx at a scalar root is %r, not 10" % (scalar.grad,))

    # ---- the walk visits every node exactly once --------------------------

    calls = []
    base = node((1, 1))
    above = base
    for _ in range(8):
        parent = above

        def local(gradient, parent=parent):
            calls.append(parent)
            parent.grad = exact.add(parent.grad, exact.add(gradient, gradient))

        above = s.Node(exact.add(parent.value, parent.value),
                       parents=(parent, parent), backward=local)
    assert s.backward(above) is None, "backward returned something"
    assert len(calls) == 8, (
        "the backward ran the chain's local backwards %d times, not once per "
        "node: a walk with no visited set visits a shared node once per path "
        "out of the root" % (len(calls),))
    assert base.grad == exact.full((2,), 2 ** 8), (
        "eight doublings of the seed left the leaf at %r, not 2**8 ones: each "
        "node of the chain is walked exactly once" % (base.grad,))

    seen = []
    orphan = s.Node(exact.from_nested((7,)),
                    backward=lambda gradient: seen.append(gradient))
    assert s.backward(orphan) is None, "backward returned something"
    assert seen == [exact.ones((1,))], (
        "a node with a local backward and no parents was called with %r, not "
        "once with the seed" % (seen,))

    deep = node((1, 1))
    top = deep
    for _ in range(20):
        top = s.add(top, top)
    assert s.backward(top) is None, "backward returned something"
    assert deep.grad == exact.full((2,), 2 ** 20), (
        "twenty doublings of the seed left %r, not 2**20 ones"
        % (deep.grad,))

    # ---- the seed: added, not assigned; shaped like the root --------------

    x = node((1, 1))
    y = node((2, 2))
    total = s.add(x, y)
    assert s.backward(total, seed=exact.from_nested((3, 5))) is None, (
        "backward returned something")
    assert total.grad == exact.from_nested((3, 5)), (
        "the root's grad under the seed (3, 5) is %r, not the seed itself"
        % (total.grad,))
    assert x.grad == exact.from_nested((3, 5)), (
        "x.grad is %r, not the given seed passed through add" % (x.grad,))
    assert y.grad == exact.from_nested((3, 5)), (
        "y.grad is %r, not the given seed passed through add" % (y.grad,))

    assert s.backward(total, seed=None) is None, "backward returned something"
    assert total.grad == exact.from_nested((4, 6)), (
        "a backward with seed=None left the root at %r, not the old (3, 5) "
        "plus the ones the default seed is" % (total.grad,))
    assert x.grad == exact.from_nested((4, 6)), (
        "x.grad after the second backward is %r, not (3, 5) + (1, 1): a call "
        "adds the gradient of its own seed to what the fields hold, so nothing "
        "the last call left is lost and nothing of it is propagated again"
        % (x.grad,))
    assert y.grad == exact.from_nested((4, 6)), (
        "y.grad after the second backward is %r, not (3, 5) + (1, 1): every "
        "call accumulates into the operands" % (y.grad,))

    x = node((2, 3))
    square = s.mul(x, x)
    assert s.backward(square) is None, "backward returned something"
    assert square.grad == exact.ones((2,)) and x.grad == exact.from_nested((4, 6)), (
        "the first backward left square.grad %r and x.grad %r, not the ones "
        "and 2x = (4, 6)" % (square.grad, x.grad))
    assert s.backward(square) is None, "backward returned something"
    assert x.grad == exact.from_nested((8, 12)), (
        "the second backward left x.grad at %r, not twice the first call's "
        "(4, 6): a call computes its own gradient, so the fields double"
        % (x.grad,))
    assert square.grad == exact.from_nested((2, 2)), (
        "the root's grad after the second backward is %r, not the sum of the "
        "two seeds" % (square.grad,))

    x = node((2, -5))
    square = s.mul(x, x)
    doubled = s.add(square, square)
    assert s.backward(doubled) is None, "backward returned something"
    first_doubled, first_square, first_x = doubled.grad, square.grad, x.grad
    assert s.backward(doubled) is None, "backward returned something"
    assert doubled.grad == exact.add(first_doubled, first_doubled), (
        "a second backward without zero_grad left the root at %r, not twice "
        "the first call's %r" % (doubled.grad, first_doubled))
    assert square.grad == exact.add(first_square, first_square), (
        "a second backward without zero_grad left square.grad at %r, not twice "
        "the first call's %r" % (square.grad, first_square))
    assert x.grad == exact.add(first_x, first_x), (
        "a second backward without zero_grad left x.grad at %r, not twice the "
        "first call's %r: the gradients accumulate across calls and the "
        "second call doubles every one of them (§3.3)"
        % (x.grad, first_x))

    wide = node(((1, 2, 3), (4, 5, 6)))
    message = _refuses(exact.AutogradError, "a seed of the wrong shape",
                       lambda: s.backward(wide, seed=exact.from_nested(((1, 2), (3, 4)))))
    assert "(2, 2)" in message and "(2, 3)" in message, (
        "the refusal of a seed of the wrong shape does not name both shapes: "
        "%r" % (message,))
    message = _refuses(
        exact.AutogradError, "a seed of a shape that would broadcast",
        lambda: s.backward(wide, seed=exact.from_nested((1, 2, 3))))
    assert "(3,)" in message and "(2, 3)" in message, (
        "the refusal of a seed shape that would have broadcast does not name "
        "both shapes: %r" % (message,))
    message = _refuses(exact.AutogradError, "a seed that is not a Tensor",
                       lambda: s.backward(wide, seed=((1, 2, 3), (4, 5, 6))))
    assert "seed" in message, (
        "the refusal of a seed that is not a Tensor does not name the seed: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "a root that is not a Node",
                       lambda: s.backward(exact.from_nested((1, 2))))
    assert "Node" in message, (
        "the refusal of a root that is not a Node does not name it: %r"
        % (message,))
    detached = s.Node(exact.from_nested((1,)), requires_grad=False)
    message = _refuses(exact.AutogradError, "a root with requires_grad=False",
                       lambda: s.backward(detached))
    assert "requires_grad" in message, (
        "the refusal of a root that does not want a gradient does not say so: "
        "%r" % (message,))

    x = node((1, 2))
    y = node((3, 4))
    loose = s.Node(exact.from_nested((2,)), parents=(x,), backward=None)
    message = _refuses(exact.AutogradError,
                       "a node with parents and no local backward",
                       lambda: s.backward(loose))
    assert "local backward" in message, (
        "the refusal of a node with parents and no local backward does not "
        "name it: %r" % (message,))
    broken = s.add(loose, loose)
    message = _refuses(exact.AutogradError,
                       "a broken edge inside the graph",
                       lambda: s.backward(broken))
    assert "local backward" in message, (
        "the refusal of a broken edge inside the graph does not name it: %r"
        % (message,))

    # ---- the operands: a Node, and the same shape -------------------------

    x = node((1, 2))
    y = node((3, 4))
    message = _refuses(exact.AutogradError, "a mul whose left operand is not a Node",
                       lambda: s.mul(y.value, x))
    assert "Node" in message, (
        "the refusal of a left operand that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "an add whose right operand is not a Node",
                       lambda: s.add(x, 3))
    assert "3" in message, (
        "the refusal of a right operand that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.ExactError, "a pair of shapes that differ",
                       lambda: s.add(node(((1, 2, 3), (4, 5, 6))), node((1, 2, 3))))
    assert "(2, 3)" in message and "(3,)" in message, (
        "the refusal of two shapes that differ does not name both: %r"
        % (message,))
    message = _refuses(exact.ExactError, "a mul of two shapes that differ",
                       lambda: s.mul(node((1, 2)), node((1, 2, 3))))
    assert "(2,)" in message and "(3,)" in message, (
        "the refusal of mul's two shapes does not name both: %r" % (message,))

    # ---- zero_grad: the whole graph above the node it is given ------------

    p = node((2, 3))
    q = s.mul(p, p)
    r = s.add(q, p)
    assert s.backward(r) is None, "backward returned something"
    other = node((5, 6))
    other_out = s.mul(other, other)
    assert s.backward(other_out) is None, "backward returned something"
    assert p.grad == exact.from_nested((5, 7)) and other.grad == exact.from_nested((10, 12)), (
        "the fixture's grads are %r and %r, not (5, 7) and (10, 12)"
        % (p.grad, other.grad))
    assert s.zero_grad(r) is None, (
        "zero_grad returned something instead of leaving the grads on the nodes")
    assert r.grad == exact.zeros((2,)), (
        "zero_grad(r) left the root's own grad at %r" % (r.grad,))
    assert p.grad == exact.zeros((2,)) and q.grad == exact.zeros((2,)), (
        "zero_grad(r) left p.grad %r and q.grad %r: it must clear every node "
        "reachable from the one it is given, not only that one"
        % (p.grad, q.grad))
    assert other.grad == exact.from_nested((10, 12)), (
        "zero_grad(r) cleared other.grad, a node in an unrelated graph: %r"
        % (other.grad,))
    assert other_out.grad == exact.ones((2,)), (
        "zero_grad(r) cleared other_out.grad, a node in an unrelated graph: %r"
        % (other_out.grad,))

    assert s.backward(r) is None, "backward returned something"
    assert p.grad == exact.from_nested((5, 7)) and q.grad == exact.ones((2,)), (
        "after zero_grad(r) a backward left p.grad at %r and q.grad at %r, not "
        "the fresh (5, 7) and the seed one: zero_grad must clear every node "
        "the walk will accumulate into, which is what a training step relies "
        "on" % (p.grad, q.grad))

    assert s.backward(r) is None, "backward returned something"
    assert s.zero_grad(r, other_out) is None, "zero_grad returned something"
    assert p.grad == exact.zeros((2,)) and q.grad == exact.zeros((2,)), (
        "zero_grad(r, other_out) left p.grad %r and q.grad %r: every argument's "
        "graph is cleared, not only the first" % (p.grad, q.grad))
    assert other.grad == exact.zeros((2,)) and other_out.grad == exact.zeros((2,)), (
        "zero_grad(r, other_out) left other.grad %r and other_out.grad %r: the "
        "second argument's graph is cleared too" % (other.grad, other_out.grad))

    assert s.backward(r) is None, "backward returned something"
    assert s.zero_grad(p) is None, "zero_grad returned something"
    assert p.grad == exact.zeros((2,)), (
        "zero_grad(p) left p.grad at %r" % (p.grad,))
    assert q.grad == exact.ones((2,)) and r.grad == exact.ones((2,)), (
        "zero_grad(p) cleared q.grad %r and r.grad %r, which are not above p: "
        "the walk goes through the parents, so p reaches p alone"
        % (q.grad, r.grad))

    assert s.zero_grad() is None, "zero_grad with no arguments returned something"
    leaf = node((9, 8))
    assert s.backward(leaf) is None, "backward returned something"
    assert s.zero_grad(leaf) is None, "zero_grad returned something"
    assert leaf.grad == exact.zeros((2,)), (
        "zero_grad(leaf) left the leaf at %r, not the zeros it started with"
        % (leaf.grad,))

    deep = node((1, 1))
    for _ in range(24):
        deep = s.add(deep, deep)
    assert s.zero_grad(deep) is None, "zero_grad returned something"

    message = _refuses(exact.AutogradError, "a zero_grad argument that is not a Node",
                       lambda: s.zero_grad(x, 3))
    assert "3" in message, (
        "the refusal of a zero_grad argument that is not a Node does not name "
        "it: %r" % (message,))

    print("check_01: the graph and the order — Node is the frozen mutable "
          "container, add and mul carry exact's forward and their local "
          "derivatives, backward seeds the root by accumulation and walks the "
          "reverse of a DFS post-order (a diamond once, not once per path), and "
          "zero_grad clears the whole graph above its arguments")

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import exact
    import stage_01 as base
    import stage_02 as s

    Rational = exact.Rational

    def node(nested):
        """A leaf holding the `exact.Tensor` `nested` describes."""
        return base.Node(exact.from_nested(nested))

    def cells_of(tensor):
        return tuple((cell.numerator, cell.denominator) for cell in tensor.cells)

    def pairs(nested):
        """The `(numerator, denominator)` pairs of the nested literal."""
        return cells_of(exact.from_nested(nested))

    # ---- the forward is exact's, element for element -----------------------

    CASES = (
        ((1, 2, 3), (-4, 5, -6)),
        (((1, 2), (3, 4)), ((5, 6), (7, 8))),
        ((Rational(1, 2), Rational(-3, 4)), (Rational(8), Rational(-5, 2))),
        (((Rational(1, 3), Rational(2, 5)), (Rational(-7, 4), Rational(0))),
         ((Rational(3, 2), Rational(-1, 5)), (Rational(4), Rational(9, 7)))),
    )
    UNARY_CASES = (
        (1, 2, 3),
        ((-4, 0, 5),),
        ((Rational(1, 2), Rational(-3, 4), Rational(0)),),
        (((Rational(1, 3), Rational(-2)), (Rational(0), Rational(5, 7))),),
    )

    for left, right in CASES:
        x = node(left)
        y = node(right)
        shape = x.value.shape
        assert shape == y.value.shape, (
            "the check's fixture is ragged: %r against %r"
            % (shape, y.value.shape))
        x_value, y_value = x.value, y.value
        for name, build, forward in (("sub", s.sub, exact.sub),
                                     ("div", s.div, exact.div)):
            made = build(x, y)
            want = forward(x.value, y.value)
            assert made.value == want, (
                "%s's value is %r, not exact.%s of its operands, %r: the "
                "forward is the provided algebra, element for element"
                % (name, made.value, name, want))
            assert made.value.cells == want.cells, (
                "%s's value has the cells %r, not exact.%s's %r"
                % (name, made.value.cells, name, want.cells))
            assert made.value.shape == shape, (
                "%s's value has shape %r, not the operands' %r"
                % (name, made.value.shape, shape))
            assert made.parents == (x, y), (
                "%s's parents are %r, not the two operands in the order they "
                "were passed" % (name, made.parents))
            assert made.backward is not None and callable(made.backward), (
                "%s's node carries %r, not a local backward: no gradient can "
                "leave it" % (name, made.backward))
            assert made.grad == exact.zeros(shape), (
                "%s's node starts with grad %r, not the zeros of the value's "
                "shape" % (name, made.grad))
            assert x.grad == exact.zeros(shape) and y.grad == exact.zeros(shape), (
                "building %s touched an operand's grad: %r and %r"
                % (name, x.grad, y.grad))
            assert x.value is x_value and y.value is y_value, (
                "building %s replaced an operand's value: %r and %r"
                % (name, x.value, y.value))

    for cells in UNARY_CASES:
        x = node(cells)
        shape = x.value.shape
        x_value = x.value
        made = s.neg(x)
        want = exact.neg(x.value)
        assert made.value == want and made.value.cells == want.cells, (
            "neg's value is %r, not exact.neg's %r" % (made.value, want))
        assert made.value.shape == shape, (
            "neg's value has shape %r, not the operand's %r"
            % (made.value.shape, shape))
        assert made.parents == (x,), (
            "neg's parents are %r, not the one operand (x,)" % (made.parents,))
        assert made is not x, (
            "neg returned its operand instead of building a node: a neg that "
            "negates in place corrupts every other node reading the operand")
        assert x.value is x_value, (
            "building neg replaced its operand's value: %r, not the tensor the "
            "fixture wrote" % (x.value,))
        assert x.value == exact.from_nested(cells), (
            "building neg changed its operand's value: %r, not the tensor the "
            "fixture wrote" % (x.value,))
        assert made.backward is not None and callable(made.backward), (
            "neg's node carries %r, not a local backward" % (made.backward,))
        assert made.grad == exact.zeros(shape) and x.grad == exact.zeros(shape), (
            "building neg touched a grad: %r and %r" % (made.grad, x.grad))

        for n in (0, 1, 2, 3):
            x = node(cells)
            made = s.pow(x, n)
            want = exact.pow(x.value, n)
            assert made.value == want, (
                "pow(%d)'s value is %r, not exact.pow's %r" % (n, made.value, want))
            assert made.value.cells == want.cells, (
                "pow(%d)'s value has the cells %r, not %r"
                % (n, made.value.cells, want.cells))
            assert made.value.shape == shape, (
                "pow(%d)'s value has shape %r, not the operand's %r"
                % (n, made.value.shape, shape))
            assert made.parents == (x,), (
                "pow(%d)'s parents are %r, not the one operand (x,)" % (n, made.parents))
            assert made is not x, "pow(%d) returned its operand" % (n,)
            assert made.backward is not None and callable(made.backward), (
                "pow(%d)'s node carries %r, not a local backward" % (n, made.backward))
            assert made.grad == exact.zeros(shape) and x.grad == exact.zeros(shape), (
                "building pow(%d) touched a grad: %r and %r"
                % (n, made.grad, x.grad))

    # ---- sub: the derivative is one and minus one -------------------------

    x = node((2, 3, -5))
    y = node((-1, 4, 6))
    assert base.backward(s.sub(x, y)) is None, "backward returned something"
    assert x.grad == exact.ones((3,)), (
        "d(x - y)/dx is %r, not the seed ones: the minuend's derivative is one"
        % (x.grad,))
    assert y.grad == exact.neg(exact.ones((3,)),), (
        "d(x - y)/dy is %r, not the negated seed: a difference's subtrahend "
        "is handed -gradient, and a `+` there cancels a fixture whose gradients "
        "are opposites" % (y.grad,))
    assert y.grad == exact.from_nested((-1, -1, -1)), (
        "d(x - y)/dy is %r, not (-1, -1, -1)" % (y.grad,))

    x = node((2, 3))
    y = node((-1, 4))
    assert base.backward(s.sub(x, y), seed=exact.from_nested((3, 5))) is None, (
        "backward returned something")
    assert x.grad == exact.from_nested((3, 5)), (
        "d(x - y)/dx under the seed (3, 5) is %r, not the seed" % (x.grad,))
    assert y.grad == exact.from_nested((-3, -5)), (
        "d(x - y)/dy under the seed (3, 5) is %r, not its negation" % (y.grad,))

    # ---- div: the quotient rule, sign and square --------------------------

    x = node((Rational(3, 2), -4))
    y = node((2, Rational(1, 3)))
    assert base.backward(s.div(x, y)) is None, "backward returned something"
    assert cells_of(x.grad) == pairs((Rational(1, 2), 3)), (
        "d(x / y)/dx is %r, not 1/y = (1/2, 3): the first term divides the "
        "gradient by the divisor, and one that divides by x or multiplies by y "
        "is a different number" % (x.grad,))
    assert cells_of(y.grad) == pairs((Rational(-3, 8), 36)), (
        "d(x / y)/dy is %r, not -x/y**2 = (-3/8, 36): the quotient rule's "
        "second term carries both the sign and the square" % (y.grad,))
    assert x.grad.shape == (2,) and y.grad.shape == (2,), (
        "the div gradients have shapes %r and %r, not the operands' (2,)"
        % (x.grad.shape, y.grad.shape))

    x = node((Rational(3, 2), -4))
    y = node((2, Rational(1, 3)))
    assert base.backward(s.div(x, y), seed=exact.from_nested((2, 6))) is None, (
        "backward returned something")
    assert cells_of(x.grad) == pairs((1, 18)), (
        "d(x / y)/dx under the seed (2, 6) is %r, not g/y = (1, 18)"
        % (x.grad,))
    assert cells_of(y.grad) == pairs((Rational(-3, 4), 216)), (
        "d(x / y)/dy under the seed (2, 6) is %r, not -g*x/y**2 = (-3/4, 216)"
        % (y.grad,))

    # div is exact, and it is not `a * pow(b, -1)` and not `//`.
    assert s.div(node((3,)), node((2,))).value == exact.from_nested((Rational(3, 2),)), (
        "3 / 2 is %r, not 3/2: an integer `//` answers 1, a hand-rolled "
        "reciprocal answers whatever `pow`'s refusal let through, and "
        "`mul(a, pow(b, -1))` does not run at all"
        % (s.div(node((3,)), node((2,))).value,))
    assert s.div(node((1,)), node((3,))).value == exact.from_nested((Rational(1, 3),)), (
        "1 / 3 is %r, not 1/3 — an integer division answers 0"
        % (s.div(node((1,)), node((3,))).value,))
    assert s.div(node((Rational(7, 5),)), node((Rational(2, 3),))).value == \
        exact.from_nested((Rational(21, 10),)), (
        "7/5 divided by 2/3 is %r, not 21/10"
        % (s.div(node((Rational(7, 5),)), node((Rational(2, 3),))).value,))

    # ---- pow: n * a**(n - 1), and the zero exponent -----------------------

    for n, want in ((0, (0, 0)), (1, (1, 1)), (2, (4, 6)), (3, (12, 27))):
        x = node((2, 3))
        assert base.backward(s.pow(x, n)) is None, "backward returned something"
        assert x.grad == exact.from_nested(want), (
            "d(x**%d)/dx at x = (2, 3) is %r, not n*a**(n-1) = %r: the exponent "
            "the closed form applies is n - 1, and the coefficient is n"
            % (n, x.grad, want))

    x = node((Rational(1, 2), Rational(-3, 2)))
    assert base.backward(s.pow(x, 2)) is None, "backward returned something"
    assert cells_of(x.grad) == pairs((1, -3)), (
        "d(x**2)/dx at x = (1/2, -3/2) is %r, not 2x = (1, -3)" % (x.grad,))

    x = node((5, -7))
    assert base.backward(s.pow(x, 0)) is None, "backward returned something"
    assert x.grad == exact.zeros((2,)), (
        "d(x**0)/dx is %r, not the zeros: x**0 is one everywhere, and the "
        "closed form cannot be evaluated there (a**(-1) is not exact.pow's)"
        % (x.grad,))

    x = node((2, 3))
    assert base.backward(s.pow(x, 1), seed=exact.from_nested((5, 7))) is None, (
        "backward returned something")
    assert x.grad == exact.from_nested((5, 7)), (
        "d(x**1)/dx under the seed (5, 7) is %r, not the seed: n*a**0 is one"
        % (x.grad,))

    x = node((2, 3))
    assert base.backward(s.pow(x, 2), seed=exact.from_nested((5, 7))) is None, (
        "backward returned something")
    assert x.grad == exact.from_nested((20, 42)), (
        "d(x**2)/dx under the seed (5, 7) is %r, not g*2x = (20, 42): the "
        "incoming gradient multiplies the closed form, it does not replace it "
        "(the default seed of ones cannot tell the two apart)"
        % (x.grad,))

    x = node((2, 3))
    assert base.backward(base.add(s.pow(x, 0), s.pow(x, 2))) is None, (
        "backward returned something")
    assert x.grad == exact.from_nested((4, 6)), (
        "d(x**0 + x**2)/dx is %r, not 2x: the zero exponent contributes the "
        "zeros and the square contributes 2x, accumulated into one grad"
        % (x.grad,))

    # ---- neg: -1, and a built node ----------------------------------------

    x = node((2, -3, 0))
    assert base.backward(s.neg(x)) is None, "backward returned something"
    assert x.grad == exact.from_nested((-1, -1, -1)), (
        "d(-x)/dx is %r, not -1: neg hands the parent the negated gradient"
        % (x.grad,))

    x = node((2, -3))
    assert base.backward(s.neg(x), seed=exact.from_nested((3, 5))) is None, (
        "backward returned something")
    assert x.grad == exact.from_nested((-3, -5)), (
        "d(-x)/dx under the seed (3, 5) is %r, not (-3, -5)" % (x.grad,))

    x = node((2, -3))
    doubled = s.neg(s.neg(x))
    assert doubled.value == x.value, (
        "neg(neg(x)) is %r, not x: a neg that negates its operand in place "
        "flips the value back and returns a graph with no negation in it"
        % (doubled.value,))
    assert base.backward(doubled) is None, "backward returned something"
    assert x.grad == exact.from_nested((1, 1)), (
        "d(-(-x))/dx is %r, not one: two negations compose to the identity"
        % (x.grad,))

    # ---- chained, and accumulated ----------------------------------------

    x = node((2, 3))
    chain = s.sub(s.pow(x, 2), x)
    assert chain.value == exact.from_nested((2, 6)), (
        "x**2 - x is %r, not (2, 6)" % (chain.value,))
    assert base.backward(chain) is None, "backward returned something"
    assert x.grad == exact.from_nested((3, 5)), (
        "d(x**2 - x)/dx is %r, not 2x - 1 = (3, 5): both paths into x "
        "accumulate into the one grad" % (x.grad,))

    x = node((2, -3))
    ratio = s.div(s.neg(x), x)
    assert ratio.value == exact.from_nested((-1, -1)), (
        "-x / x is %r, not (-1, -1)" % (ratio.value,))
    assert base.backward(ratio) is None, "backward returned something"
    assert x.grad == exact.zeros((2,)), (
        "d(-x / x)/dx is %r, not the zeros: the quotient rule's two terms "
        "cancel exactly, which is the sign of a quotient rule that is right"
        % (x.grad,))

    x = node((1, 2))
    y = node((Rational(1, 2), 2))
    mixed = s.sub(s.div(x, y), base.mul(x, y))
    assert base.backward(mixed) is None, "backward returned something"
    assert cells_of(x.grad) == pairs((Rational(3, 2), Rational(-3, 2))), (
        "d(x/y - x*y)/dx with x = (1, 2) and y = (1/2, 2) is %r, not "
        "1/y - y = (3/2, -3/2)" % (x.grad,))
    assert cells_of(y.grad) == pairs((-5, Rational(-5, 2))), (
        "d(x/y - x*y)/dy is %r, not -x/y**2 - x = (-5, -5/2)" % (y.grad,))

    x = node((2, 3))
    y = node((1, 4))
    difference = s.sub(x, y)
    squared = base.mul(difference, difference)
    assert base.backward(squared) is None, "backward returned something"
    assert x.grad == exact.from_nested((2, -2)), (
        "d((x - y)**2)/dx with x - y = (1, -1) is %r, not 2(x - y) = (2, -2)"
        % (x.grad,))
    assert y.grad == exact.from_nested((-2, 2)), (
        "d((x - y)**2)/dy is %r, not -2(x - y) = (-2, 2): the reuse of one "
        "node is summed, and the difference's sign reaches the second operand"
        % (y.grad,))

    x = node((2, 3))
    y = node((1, 4))
    graph = s.sub(base.add(x, y), s.neg(y))
    assert graph.value == exact.from_nested((4, 11)), (
        "(x + y) - (-y) with x = (2, 3) and y = (1, 4) is %r, not (4, 11)"
        % (graph.value,))
    assert base.backward(graph) is None, "backward returned something"
    assert x.grad == exact.ones((2,)), (
        "d((x + y) - (-y))/dx is %r, not the ones" % (x.grad,))
    assert y.grad == exact.from_nested((2, 2)), (
        "d((x + y) - (-y))/dy is %r, not two: y arrives through add and "
        "through the negated operand both" % (y.grad,))

    x = node((2, 3))
    y = node((1, 4))
    left_path = s.sub(x, y)
    right_path = s.div(x, y)
    both = base.add(left_path, right_path)
    assert both.value == exact.from_nested((3, Rational(-1, 4))), (
        "(x - y) + x/y with x = (2, 3) and y = (1, 4) is %r, not (3, -1/4)"
        % (both.value,))
    assert base.backward(both) is None, "backward returned something"
    assert x.grad == exact.from_nested((2, Rational(5, 4))), (
        "d((x - y) + x/y)/dx is %r, not 1 + 1/y = (2, 5/4): x arrives through "
        "two paths in one walk, and the second contribution must land on the "
        "first instead of replacing it (§3.3)"
        % (x.grad,))
    assert y.grad == exact.from_nested((-3, Rational(-19, 16))), (
        "d((x - y) + x/y)/dy is %r, not -1 - x/y**2 = (-3, -19/16)"
        % (y.grad,))

    x = node((2, 3))
    negated = s.neg(x)
    squared_negation = s.pow(x, 2)
    joined = base.add(negated, squared_negation)
    assert base.backward(joined) is None, "backward returned something"
    assert x.grad == exact.from_nested((3, 5)), (
        "d(-x + x**2)/dx is %r, not -1 + 2x = (3, 5): a unary contribution "
        "accumulates into the operand's grad like any other"
        % (x.grad,))

    # a second backward without zero_grad doubles every contribution
    x = node((2, 3))
    y = node((1, 4))
    twice = s.sub(s.div(x, y), s.neg(x))
    assert base.backward(twice) is None, "backward returned something"
    first = x.grad
    assert base.backward(twice) is None, "backward returned something"
    assert x.grad == exact.add(first, first), (
        "a second backward without zero_grad left x.grad at %r, not twice the "
        "first call's %r: every local backward accumulates (§3.3)"
        % (x.grad, first))

    # ---- every gradient keeps its own operand's shape ---------------------

    x = node(((1, 2, 3), (4, 5, 6)))
    y = node(((7, 8, 9), (1, 2, 3)))
    root = s.sub(s.div(x, y), s.neg(s.pow(y, 2)))
    assert base.backward(root) is None, "backward returned something"
    seen = []
    stack = [root]
    while stack:
        reached = stack.pop()
        if reached in seen:
            continue
        seen.append(reached)
        stack.extend(reached.parents)
    assert len(seen) == 6, (
        "the graph reachable from the root has %d nodes, not the six the "
        "fixture builds (the root, the div, the neg, the pow, and the two "
        "leaves)" % (len(seen),))
    for reached in seen:
        assert reached.grad.shape == reached.value.shape, (
            "the gradient of a node of shape %r has shape %r: a gradient owes "
            "its operand its shape, never the output's"
            % (reached.value.shape, reached.grad.shape))
        assert all(isinstance(cell, Rational) for cell in reached.grad.cells), (
            "a gradient cell is not an exact.Rational: %r" % (reached.grad.cells,))
        assert all(isinstance(cell, Rational) for cell in reached.value.cells), (
            "a value cell is not an exact.Rational: %r" % (reached.value.cells,))

    # ---- the refusals -----------------------------------------------------

    message = _refuses(exact.ExactError, "a sub of two shapes that differ",
                       lambda: s.sub(node(((1, 2, 3), (4, 5, 6))), node((1, 2, 3))))
    assert "(2, 3)" in message and "(3,)" in message, (
        "the refusal of sub's two shapes does not name both: %r" % (message,))
    message = _refuses(exact.ExactError, "a div of two shapes that differ",
                       lambda: s.div(node((1, 2, 3)), node(((1, 2), (3, 4), (5, 6)))))
    assert "(3,)" in message and "(3, 2)" in message, (
        "the refusal of div's two shapes does not name both: %r" % (message,))
    assert "broadcast" in message, (
        "the refusal of two shapes that differ does not say that this stage "
        "does not broadcast: %r" % (message,))
    message = _refuses(exact.ExactError, "two shapes of the same size and rank",
                       lambda: s.sub(node(((1, 2),)), node(((1,), (2,)))))
    assert "(1, 2)" in message and "(2, 1)" in message, (
        "the refusal of two shapes of the same size and rank does not name "
        "both: %r" % (message,))

    x = node((1, 2))
    y = node((3, 4))
    message = _refuses(exact.AutogradError, "a sub whose right operand is not a Node",
                       lambda: s.sub(x, 3))
    assert "3" in message, (
        "the refusal of a right operand that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "a div whose left operand is not a Node",
                       lambda: s.div(y.value, y))
    assert "Node" in message, (
        "the refusal of a left operand that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "a neg of something that is not a Node",
                       lambda: s.neg(3))
    assert "3" in message, (
        "the refusal of neg's operand does not name it: %r" % (message,))
    message = _refuses(exact.AutogradError, "a pow of something that is not a Node",
                       lambda: s.pow(exact.from_nested((2, 3)), 2))
    assert "Node" in message, (
        "the refusal of pow's operand does not name it: %r" % (message,))

    message = _refuses(exact.ExactError, "a division by a zero divisor",
                       lambda: s.div(node((3, 5)), node((2, 0))))
    assert "Rational(3, 1)" in message and "Rational(0, 1)" in message, (
        "the refusal of a zero divisor does not name both operands: %r"
        % (message,))
    assert "index" in message and "(2,)" in message, (
        "the refusal of a zero divisor does not name the output index and the "
        "shape: %r" % (message,))
    message = _refuses(exact.ExactError, "a division by a zero in a 2-D divisor",
                       lambda: s.div(node(((1, 2), (3, 4))), node(((1, 0), (2, 3)))))
    assert "index" in message and "(2, 2)" in message, (
        "the refusal of a zero divisor in a 2-D division does not name the "
        "index and the shape: %r" % (message,))
    message = _refuses(exact.ExactError, "a zero over a zero",
                       lambda: s.div(node((0,)), node((0,))))
    assert "index" in message, (
        "the refusal of 0 / 0 does not name the index: %r" % (message,))

    message = _refuses(exact.ExactError, "a negative exponent",
                       lambda: s.pow(node((2, 3)), -1))
    assert "-1" in message, (
        "the refusal of a negative exponent does not name it: %r" % (message,))
    message = _refuses(exact.ExactError, "a non-int exponent",
                       lambda: s.pow(node((2, 3)), Rational(1, 2)))
    assert "n" in message, (
        "the refusal of a non-int exponent does not name it: %r" % (message,))
    message = _refuses(exact.ExactError, "a string exponent",
                       lambda: s.pow(node((2, 3)), "2"))
    assert "n" in message, (
        "the refusal of a string exponent does not name it: %r" % (message,))

    print("check_02: the local derivatives — sub, div, pow and neg carry "
          "exact's forward element for element and the closed form of their own "
          "derivative, every contribution lands on its own operand in that "
          "operand's shape and accumulates there, a zero divisor and a bad "
          "exponent are refused naming both numbers, and a pair of shapes that "
          "differ is refused rather than broadcast")

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import itertools
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import exact
    import fixtures
    import stage_01 as base
    import stage_03 as s

    Rational = exact.Rational

    def node(nested):
        """A leaf holding the `exact.Tensor` `nested` describes."""
        return base.Node(exact.from_nested(nested))

    def cells_of(tensor):
        return tuple((cell.numerator, cell.denominator) for cell in tensor.cells)

    def pairs(nested):
        """The `(numerator, denominator)` pairs of the nested literal."""
        return cells_of(exact.from_nested(nested))

    def size(shape):
        total = 1
        for dim in shape:
            total *= dim
        return total

    def ramp(shape):
        """A distinct `Rational` per cell (1, 2, 3, ...): the seed that tells
        one axis's expansion from another's, and one operand's contribution
        from the other's."""
        return exact.Tensor(
            tuple(Rational(i) for i in range(1, size(shape) + 1)), shape)

    def expected_grad(seed, shape, axis):
        """The derivative of a reduction, written from the definition: an
        operand cell keeps the seed's cell at the index the summed axis was
        dropped from, so every cell over that axis carries the same figure.

        This is not the implementation's formula read back: it looks the seed
        up cell by cell, with the axis removed from the *operand's* index, and
        it is what makes an expansion along the wrong axis a wrong number
        rather than a wrong shape.
        """
        out = []
        for offsets in itertools.product(*[range(dim) for dim in shape]):
            if axis is None:
                out.append(seed.get(()))
            else:
                out.append(seed.get(offsets[:axis] + offsets[axis + 1:]))
        return exact.Tensor(tuple(out), shape)

    def walk(root):
        """Every node reachable from `root` through its parents, once each."""
        seen = []
        stack = [root]
        while stack:
            reached = stack.pop()
            if reached in seen:
                continue
            seen.append(reached)
            stack.extend(reached.parents)
        return seen

    # ---- the forward is exact's, element for element -----------------------

    PAIRS = (
        # (3, 4) + (4,): the leading axis is the one the broadcast stretched
        (((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)), (10, 20, 30, 40)),
        # (3, 4) + (1, 4): both operands are stretched
        (((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)), ((10, 20, 30, 40),)),
        # (3, 1) + (4,): neither operand is the equal-shape one
        (((1,), (2,), (3,)), (10, 20, 30, 40)),
        # (2, 3) + (3,): the plain row-wise bias
        (((1, 2, 3), (4, 5, 6)), (7, 8, 9)),
        # (3,) + (2, 3): this time the *left* operand is the stretched one
        ((7, 8, 9), ((1, 2, 3), (4, 5, 6))),
        # a tensor against a scalar: a rank-0 operand
        (((1, 2), (3, 4)), Rational(5)),
        # exact rationals, so a division or a `//` shows up as a pair
        (((Rational(1, 2), Rational(-3, 4)), (Rational(5, 7), Rational(0))),
         (2, Rational(1, 3))),
    )
    for left, right in PAIRS:
        for name, build, forward in (("add", s.add, exact.add),
                                     ("sub", s.sub, exact.sub),
                                     ("mul", s.mul, exact.mul)):
            x = node(left)
            y = node(right)
            x_value, y_value = x.value, y.value
            made = build(x, y)
            want = forward(x.value, y.value)
            assert made.value == want, (
                "%s's value is %r, not exact.%s of its operands, %r: the "
                "forward is the provided algebra, element for element"
                % (name, made.value, name, want))
            assert made.value.cells == want.cells, (
                "%s's value has the cells %r, not exact.%s's %r"
                % (name, made.value.cells, name, want.cells))
            assert made.value.shape == want.shape == \
                exact.broadcast_shape(x.value.shape, y.value.shape), (
                "%s's value has shape %r, not the broadcast of %r and %r, %r"
                % (name, made.value.shape, x.value.shape, y.value.shape,
                   want.shape))
            assert made.value is not want, (
                "%s handed back a tensor `exact` had already built" % (name,))
            assert made.parents == (x, y), (
                "%s's parents are %r, not the two operands in the order they "
                "were passed" % (name, made.parents))
            assert made.backward is not None and callable(made.backward), (
                "%s's node carries %r, not a local backward: no gradient can "
                "leave it" % (name, made.backward))
            assert made.grad == exact.zeros(made.value.shape), (
                "%s's node starts with grad %r, not the zeros of the value's "
                "shape" % (name, made.grad))
            assert x.grad == exact.zeros(x.value.shape), (
                "building %s touched the left operand's grad: %r"
                % (name, x.grad))
            assert y.grad == exact.zeros(y.value.shape), (
                "building %s touched the right operand's grad: %r"
                % (name, y.grad))
            assert x.value is x_value and y.value is y_value, (
                "building %s replaced an operand's value: %r and %r"
                % (name, x.value, y.value))

    # ---- the broadcast operand owes its own shape -------------------------

    seed34 = ramp((3, 4))                      # 1..12, three rows of four

    # (3, 4) + (4,)
    a = node(((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)))
    b = node((10, 20, 30, 40))
    made = s.add(a, b)
    assert made.value.shape == (3, 4), (
        "a (3, 4) + a (4,) has shape %r, not the broadcast (3, 4)"
        % (made.value.shape,))
    assert base.backward(made, seed=seed34) is None, "backward returned something"
    assert a.grad.shape == (3, 4), (
        "the (3, 4) operand's grad has shape %r, not its own (3, 4)"
        % (a.grad.shape,))
    assert a.grad == seed34, (
        "the equal-shape operand's grad is %r, not the seed itself: a sum hands "
        "each addend the whole gradient" % (a.grad,))
    assert b.grad.shape == (4,), (
        "the (4,) operand was broadcast, so its gradient's shape is its own "
        "(4,), not %r: a contribution in the node's shape must go through "
        "exact.reduce_gradient" % (b.grad.shape,))
    assert b.grad == exact.from_nested((15, 18, 21, 24)), (
        "the (4,) operand's gradient is the seed summed over the three rows: "
        "%r, not (15, 18, 21, 24)" % (b.grad,))

    # the same pair the other way round
    small = node((10, 20, 30, 40))
    big = node(((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)))
    made = s.add(small, big)
    assert base.backward(made, seed=seed34) is None, "backward returned something"
    assert small.grad.shape == (4,), (
        "the (4,) left operand's grad has shape %r, not its own (4,): the "
        "reduction is for whichever operand the broadcast stretched"
        % (small.grad.shape,))
    assert small.grad == exact.from_nested((15, 18, 21, 24)), (
        "the broadcast left operand's grad is %r, not (15, 18, 21, 24)"
        % (small.grad,))
    assert big.grad == seed34, (
        "the equal-shape right operand's grad is %r, not the seed" % (big.grad,))

    # (3, 4) + (1, 4): both operands are stretched
    a = node(((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)))
    b = node(((10, 20, 30, 40),))
    made = s.add(a, b)
    assert base.backward(made, seed=seed34) is None, "backward returned something"
    assert a.grad.shape == (3, 4) and b.grad.shape == (1, 4), (
        "against a (1, 4) the operands' grads have shapes %r and %r, not "
        "(3, 4) and (1, 4)" % (a.grad.shape, b.grad.shape))
    assert a.grad == seed34, (
        "the (3, 4) operand's grad against a (1, 4) is %r, not the seed"
        % (a.grad,))
    assert b.grad == exact.from_nested(((15, 18, 21, 24),)), (
        "the (1, 4) operand's grad is its row of sums %r, not ((15, 18, 21, "
        "24),)" % (b.grad,))

    # (3, 1) + (4,): a column against a row — the outer shape
    a = node(((1,), (2,), (3,)))
    b = node((10, 20, 30, 40))
    made = s.add(a, b)
    assert made.value.shape == (3, 4), (
        "a (3, 1) + a (4,) has shape %r, not the outer (3, 4)"
        % (made.value.shape,))
    assert base.backward(made, seed=seed34) is None, "backward returned something"
    assert a.grad.shape == (3, 1), (
        "the (3, 1) operand's grad has shape %r, not its own (3, 1)"
        % (a.grad.shape,))
    assert a.grad == exact.from_nested(((10,), (26,), (42,))), (
        "the (3, 1) operand's grad is its rows of sums %r, not ((10,), (26,), "
        "(42,))" % (a.grad,))
    assert b.grad.shape == (4,), (
        "the (4,) operand's grad has shape %r, not its own (4,)"
        % (b.grad.shape,))
    assert b.grad == exact.from_nested((15, 18, 21, 24)), (
        "the (4,) operand's grad is the seed's column sums %r, not (15, 18, "
        "21, 24)" % (b.grad,))

    # a scalar operand owes a rank-0 gradient
    a = node(((1, 2, 3), (4, 5, 6)))
    scalar = node(Rational(5))
    seed23 = ramp((2, 3))
    made = s.add(a, scalar)
    assert made.value.shape == (2, 3) and scalar.value.shape == (), (
        "a (2, 3) against a scalar has shape %r, not (2, 3), and the scalar's "
        "shape is %r, not ()" % (made.value.shape, scalar.value.shape))
    assert base.backward(made, seed=seed23) is None, "backward returned something"
    assert scalar.grad.shape == (), (
        "the scalar operand's grad has shape %r, not the rank-0 ()"
        % (scalar.grad.shape,))
    assert scalar.grad == exact.from_nested(Rational(21)), (
        "the scalar operand's grad is the whole seed summed, %r, not 21"
        % (scalar.grad,))
    assert a.grad == seed23, (
        "the (2, 3) operand's grad against a scalar is %r, not the seed"
        % (a.grad,))

    # ---- sub: the sign survives the reduction ------------------------------

    a = node(((1, 2, 3), (4, 5, 6)))
    b = node((7, 8, 9))
    made = s.sub(a, b)
    assert base.backward(made, seed=seed23) is None, "backward returned something"
    assert a.grad == seed23, (
        "the minuend's grad is %r, not the seed: d(a - b)/da is one"
        % (a.grad,))
    assert b.grad.shape == (3,), (
        "the (3,) subtrahend's grad has shape %r, not its own (3,)"
        % (b.grad.shape,))
    assert b.grad == exact.from_nested((-5, -7, -9)), (
        "the subtrahend's grad is the negated row sums %r, not (-5, -7, -9): "
        "a `+` there cancels a fixture whose contributions are opposite"
        % (b.grad,))

    small = node((7, 8, 9))
    big = node(((1, 2, 3), (4, 5, 6)))
    made = s.sub(small, big)
    assert base.backward(made, seed=seed23) is None, "backward returned something"
    assert small.grad == exact.from_nested((5, 7, 9)), (
        "the broadcast minuend's grad is the seed's row sums, (5, 7, 9), not "
        "%r: it is reduced and it is *not* negated — the sign belongs to the "
        "subtrahend" % (small.grad,))
    assert big.grad == exact.from_nested(((-1, -2, -3), (-4, -5, -6))), (
        "the (2, 3) subtrahend's grad is %r, not the negated seed"
        % (big.grad,))

    # ---- mul: the *other* operand, per output element ----------------------

    a = node(((1, 2, 3), (4, 5, 6)))
    b = node((10, 20, 30))
    made = s.mul(a, b)
    assert base.backward(made, seed=seed23) is None, "backward returned something"
    assert a.grad == exact.from_nested(((10, 40, 90), (40, 100, 180))), (
        "d(a * b)/da is the gradient times b = %r, not ((10, 40, 90), "
        "(40, 100, 180)): the two operands the wrong way round give the "
        "gradient times a instead" % (a.grad,))
    assert b.grad.shape == (3,), (
        "the (3,) factor's grad has shape %r, not its own (3,)" % (b.grad.shape,))
    assert b.grad == exact.from_nested((17, 29, 45)), (
        "the (3,) factor's grad is sum_i g[i, j]*a[i, j] = %r, not (17, 29, 45)"
        % (b.grad,))

    # rational cells, so a wrong operand's contribution is a wrong pair
    a = node(((1,), (2,), (3,)))
    b = node((Rational(1, 2), Rational(1, 3), Rational(1, 4), Rational(1, 5)))
    made = s.mul(a, b)
    assert made.value.shape == (3, 4), (
        "a (3, 1) * a (4,) has shape %r, not the outer (3, 4)"
        % (made.value.shape,))
    assert base.backward(made, seed=exact.ones((3, 4))) is None, (
        "backward returned something")
    assert a.grad == exact.from_nested(((Rational(77, 60),),
                                        (Rational(77, 60),),
                                        (Rational(77, 60),))), (
        "the (3, 1) factor's grad is the row sums of b (1/2 + 1/3 + 1/4 + "
        "1/5 = 77/60) in a (3, 1): %r" % (a.grad,))
    assert b.grad == exact.from_nested((6, 6, 6, 6)), (
        "the (4,) factor's grad is the column sums of a (1 + 2 + 3 = 6) in a "
        "(4,): %r" % (b.grad,))

    a = node(((1, 2), (3, 4)))
    scalar = node(Rational(5))
    made = s.mul(a, scalar)
    assert base.backward(made, seed=ramp((2, 2))) is None, (
        "backward returned something")
    assert a.grad == exact.from_nested(((5, 10), (15, 20))), (
        "d(a * 5)/da is 5 at every cell: %r, not ((5, 10), (15, 20))"
        % (a.grad,))
    assert scalar.grad.shape == () and scalar.grad == exact.from_nested(Rational(30)), (
        "d(a * s)/ds is sum(g*a) = 1 + 4 + 9 + 16 = 30 as a rank-0 tensor: %r "
        "of shape %r" % (scalar.grad, scalar.grad.shape))

    # ---- the reduction is called for the broadcast operand only -----------

    real_reduce = exact.reduce_gradient
    calls = []

    def spy(gradient, shape):
        calls.append((gradient.shape, shape))
        return real_reduce(gradient, shape)

    exact.reduce_gradient = spy
    try:
        # an equal-shape pair never reaches the reduction
        x = node(((1, 2), (3, 4)))
        y = node(((5, 6), (7, 8)))
        assert base.backward(s.mul(x, y)) is None, "backward returned something"
        assert calls == [], (
            "exact.reduce_gradient was called %r on a pair of equal shapes: the "
            "call is a no-op there and would be invisible in every value, but "
            "it sums a gradient that was never broadcast the moment the shapes "
            "differ" % (calls,))

        # one broadcast operand: exactly one call, with *its* shape
        calls[:] = []
        x = node(((1, 2, 3), (4, 5, 6)))
        y = node((7, 8, 9))
        assert base.backward(s.add(x, y)) is None, "backward returned something"
        assert calls == [((2, 3), (3,))], (
            "one broadcast operand wanted exactly one reduction, of the node's "
            "(2, 3) contribution back to the operand's (3,): got %r" % (calls,))

        calls[:] = []
        x = node(((1, 2, 3), (4, 5, 6)))
        y = node((7, 8, 9))
        assert base.backward(s.mul(x, y)) is None, "backward returned something"
        assert calls == [((2, 3), (3,))], (
            "mul's broadcast operand wanted one reduction to its own shape: "
            "got %r" % (calls,))

        # both operands broadcast: one call each, each with its own shape
        calls[:] = []
        x = node(((1,), (2,), (3,)))
        y = node(((10, 20, 30, 40),))
        assert base.backward(s.mul(x, y)) is None, "backward returned something"
        assert sorted(calls) == sorted([((3, 4), (3, 1)), ((3, 4), (1, 4))]), (
            "a (3, 1) against a (1, 4) owes each operand its own shape: the "
            "reductions were %r, not one to (3, 1) and one to (1, 4)" % (calls,))

        # a scalar operand is the stretched one too
        calls[:] = []
        x = node((1, 2))
        y = node(Rational(3))
        assert base.backward(s.mul(x, y)) is None, "backward returned something"
        assert calls == [((2,), ())], (
            "the scalar operand's contribution is reduced from the node's (2,) "
            "to the rank-0 (): got %r" % (calls,))

        # and a chain where only one operand was broadcast
        calls[:] = []
        x = node(((1, 2, 3), (4, 5, 6)))
        y = node((7, 8, 9))
        assert base.backward(s.sum(s.mul(x, y), axis=0)) is None, (
            "backward returned something")
        assert calls == [((2, 3), (3,))], (
            "in mul -> sum(axis=0) only the (3,) factor was broadcast: the "
            "reductions were %r, not one back to (3,)" % (calls,))

        # the fixture's bias, against a (3, 4) sibling: one reduction, for the
        # bias only
        calls[:] = []
        w1 = base.Node(fixtures.MODELS["mlp"][0])
        b1 = base.Node(fixtures.MODELS["mlp"][1])
        column = base.Node(exact.ones((3, 4)))
        assert base.backward(s.mean(s.add(s.mul(column, b1), w1))) is None, (
            "backward returned something")
        assert calls == [((3, 4), (4,))], (
            "the layer's (3, 4) weight is not reduced and its (4,) bias is: the "
            "reductions were %r, not one back to (4,)" % (calls,))
        assert b1.grad == exact.full((4,), Rational(1, 4)), (
            "the fixture's bias keeps the row sums of the mean's gradient: its "
            "grad is %r, not (1/4, 1/4, 1/4, 1/4) in a (4,)" % (b1.grad,))
        assert w1.grad == exact.full((3, 4), Rational(1, 12)), (
            "the equal-shape (3, 4) weight keeps the gradient itself: its grad "
            "is %r, not 1/12 at every cell" % (w1.grad,))
    finally:
        exact.reduce_gradient = real_reduce

    # ---- sum: the axis comes back, stretched ------------------------------

    flat = ((1, 2, 3), (4, 5, 6))

    t = node(flat)
    made = s.sum(t)
    assert made.value == exact.from_nested(Rational(21)), (
        "sum(t) is %r, not the rank-0 21" % (made.value,))
    assert made.value.shape == (), (
        "sum(t) has shape %r, not the rank-0 ()" % (made.value.shape,))
    assert base.backward(made) is None, "backward returned something"
    assert t.grad.shape == (2, 3), (
        "after sum(t) the operand's grad has shape %r, not its own (2, 3): "
        "the gradient of a reduction owes the operand its shape"
        % (t.grad.shape,))
    assert t.grad == exact.ones((2, 3)), (
        "the gradient of a full sum under the seed ones is the seed broadcast "
        "to every cell: %r, not the ones of (2, 3)" % (t.grad,))

    for axis, want in ((0, (5, 7, 9)), (1, (6, 15)), (-1, (6, 15)), (-2, (5, 7, 9))):
        t = node(flat)
        made = s.sum(t, axis)
        assert made.value == exact.from_nested(want), (
            "sum(t, axis=%d) is %r, not %r" % (axis, made.value, want))
        assert made.value.shape == exact.from_nested(want).shape, (
            "sum(t, axis=%d) has shape %r, not %r"
            % (axis, made.value.shape, exact.from_nested(want).shape))

    # sum(0) and sum(1) are told apart by a seed whose cells are distinct
    t = node(flat)
    made = s.sum(t, axis=0)
    assert base.backward(made, seed=exact.from_nested((1, 2, 3))) is None, (
        "backward returned something")
    assert t.grad == exact.from_nested(((1, 2, 3), (1, 2, 3))), (
        "sum(t, axis=0)'s gradient repeats the seed along the axis it summed "
        "away: %r, not ((1, 2, 3), (1, 2, 3)) — expanding along axis 1 gives "
        "((1, 1, 1), (2, 2, 2)) instead" % (t.grad,))

    t = node(flat)
    made = s.sum(t, axis=1)
    assert base.backward(made, seed=exact.from_nested((1, 2))) is None, (
        "backward returned something")
    assert t.grad == exact.from_nested(((1, 1, 1), (2, 2, 2))), (
        "sum(t, axis=1)'s gradient is %r, not ((1, 1, 1), (2, 2, 2)): "
        "sum(axis=0) and sum(axis=1) are different calls and their gradients "
        "are different tensors" % (t.grad,))

    t = node(flat)
    made = s.sum(t, axis=-1)
    assert base.backward(made, seed=exact.from_nested((1, 2))) is None, (
        "backward returned something")
    assert t.grad == exact.from_nested(((1, 1, 1), (2, 2, 2))), (
        "axis=-1 is the last axis of a rank-2 tensor, whose gradient is %r, "
        "not ((1, 1, 1), (2, 2, 2))" % (t.grad,))

    t = node(flat)
    made = s.sum(t, axis=None)
    assert base.backward(made, seed=exact.from_nested(Rational(3))) is None, (
        "backward returned something")
    assert t.grad == exact.full((2, 3), Rational(3)), (
        "sum(t, axis=None)'s gradient is the seed broadcast to every cell: %r, "
        "not three at every cell — the backward of a full sum is the seed, "
        "never the ones and never the seed ignored" % (t.grad,))

    # ---- sum over every axis of a rank-3 tensor ---------------------------

    CUBE = (((1, 2, 3, 4), (5, 6, 7, 8), (9, 10, 11, 12)),
            ((13, 14, 15, 16), (17, 18, 19, 20), (21, 22, 23, 24)))
    cube = exact.from_nested(CUBE)
    CUBE_SUMS = {
        0: (((14, 16, 18, 20), (22, 24, 26, 28), (30, 32, 34, 36))),
        1: (((15, 18, 21, 24), (51, 54, 57, 60))),
        2: (((10, 26, 42), (58, 74, 90))),
    }
    for axis in (0, 1, 2, -1, -2, -3, None):
        normalized = None if axis is None else axis % 3
        keep = () if normalized is None else \
            cube.shape[:normalized] + cube.shape[normalized + 1:]
        seed = ramp(keep)
        t = base.Node(cube)
        made = s.sum(t, axis)
        assert made.value == exact.sum(cube, axis), (
            "sum(cube, axis=%r) is %r, not exact.sum's %r"
            % (axis, made.value, exact.sum(cube, axis)))
        assert made.value.shape == keep, (
            "sum(cube, axis=%r) has shape %r, not the %r the axis was removed "
            "from" % (axis, made.value.shape, keep))
        if normalized in CUBE_SUMS:
            assert made.value == exact.from_nested(CUBE_SUMS[normalized]), (
                "sum(cube, axis=%r) is %r, not %r"
                % (axis, made.value, CUBE_SUMS[normalized]))
        assert base.backward(made, seed=seed) is None, (
            "backward returned something")
        assert t.grad.shape == cube.shape, (
            "after a rank-3 sum the operand's grad has shape %r, not its own "
            "(2, 3, 4)" % (t.grad.shape,))
        assert t.grad == expected_grad(seed, cube.shape, normalized), (
            "sum(cube, axis=%r)'s gradient is %r, not the seed repeated along "
            "the summed axis, %r"
            % (axis, t.grad,
               expected_grad(seed, cube.shape, normalized)))

    # ---- mean: the exact 1/n of the extent that was averaged ---------------

    t = node(flat)
    made = s.mean(t)
    assert made.value == exact.from_nested(Rational(7, 2)), (
        "mean(t) is %r, not the exact 7/2 (21/6): never a float" % (made.value,))
    assert base.backward(made) is None, "backward returned something"
    assert t.grad == exact.full((2, 3), Rational(1, 6)), (
        "mean(t)'s gradient is 1/6 at every cell: %r, not the whole seed — the "
        "1/n is the whole content of this operation" % (t.grad,))

    t = node(flat)
    made = s.mean(t, axis=0)
    assert made.value == exact.from_nested((Rational(5, 2), Rational(7, 2),
                                            Rational(9, 2))), (
        "mean(t, axis=0) is %r, not (5/2, 7/2, 9/2)" % (made.value,))
    assert base.backward(made, seed=exact.from_nested((1, 2, 3))) is None, (
        "backward returned something")
    assert t.grad == exact.from_nested(((Rational(1, 2), Rational(1),
                                         Rational(3, 2)),
                                        (Rational(1, 2), Rational(1),
                                         Rational(3, 2)))), (
        "mean(t, axis=0)'s gradient is the seed broadcast and divided by the "
        "two rows it averaged: %r, not the seed itself" % (t.grad,))

    t = node(flat)
    made = s.mean(t, axis=1)
    assert made.value == exact.from_nested((2, 5)), (
        "mean(t, axis=1) is %r, not (2, 5)" % (made.value,))
    assert base.backward(made, seed=exact.from_nested((1, 2))) is None, (
        "backward returned something")
    assert t.grad == exact.from_nested(((Rational(1, 3), Rational(1, 3),
                                         Rational(1, 3)),
                                        (Rational(2, 3), Rational(2, 3),
                                         Rational(2, 3)))), (
        "mean(t, axis=1)'s gradient is divided by the three columns it "
        "averaged: %r, not by the six cells of the tensor (1/6 at every cell)"
        % (t.grad,))

    t = node(flat)
    made = s.mean(t, axis=-1)
    assert base.backward(made, seed=exact.from_nested((1, 2))) is None, (
        "backward returned something")
    assert t.grad == exact.from_nested(((Rational(1, 3), Rational(1, 3),
                                         Rational(1, 3)),
                                        (Rational(2, 3), Rational(2, 3),
                                         Rational(2, 3)))), (
        "mean(t, axis=-1)'s gradient must be the one axis=-1 names: %r"
        % (t.grad,))

    for axis in (0, 1, 2, -1, -2, -3, None):
        normalized = None if axis is None else axis % 3
        keep = () if normalized is None else \
            cube.shape[:normalized] + cube.shape[normalized + 1:]
        seed = ramp(keep)
        extent = cube.size if normalized is None else cube.shape[normalized]
        t = base.Node(cube)
        made = s.mean(t, axis)
        assert made.value == exact.mean(cube, axis), (
            "mean(cube, axis=%r) is %r, not exact.mean's %r"
            % (axis, made.value, exact.mean(cube, axis)))
        assert base.backward(made, seed=seed) is None, (
            "backward returned something")
        assert t.grad.shape == cube.shape, (
            "after a rank-3 mean the operand's grad has shape %r, not (2, 3, 4)"
            % (t.grad.shape,))
        assert t.grad == exact.mul(expected_grad(seed, cube.shape, normalized),
                                   exact.full(cube.shape, Rational(1, extent))), (
            "mean(cube, axis=%r)'s gradient is the seed repeated along the axis "
            "and divided by its %d cells: %r" % (axis, extent, t.grad))

    # ---- chained, with only one operand broadcast --------------------------

    w = node(((1, 2, 3), (4, 5, 6)))
    bias = node((10, 20, 30))
    loss = s.sum(s.mul(w, bias), axis=0)
    assert loss.value == exact.from_nested((50, 140, 270)), (
        "sum(mul(w, bias), 0) is %r, not (50, 140, 270)" % (loss.value,))
    assert base.backward(loss) is None, "backward returned something"
    assert w.grad == exact.from_nested(((10, 20, 30), (10, 20, 30))), (
        "in mul -> sum(0) the (2, 3) weight's grad is the bias broadcast over "
        "the rows: %r" % (w.grad,))
    assert bias.grad == exact.from_nested((5, 7, 9)), (
        "and the (3,) bias's grad is the weight summed over the rows: %r, not "
        "(5, 7, 9) — the reduction and the expansion of two different nodes in "
        "one chain" % (bias.grad,))

    p = node(((1, 2, 3), (4, 5, 6)))
    q = node((10, 20, 30))
    chain = s.add(s.mul(p, q), p)
    assert chain.value == exact.from_nested(((11, 42, 93), (44, 105, 186))), (
        "p*q + p is %r" % (chain.value,))
    assert base.backward(chain, seed=seed23) is None, (
        "backward returned something")
    assert p.grad == exact.from_nested(((11, 42, 93), (44, 105, 186))), (
        "p's grad through both the broadcast product and the equal-shape sum "
        "is q broadcast times the seed plus the seed: %r, not ((11, 42, 93), "
        "(44, 105, 186))" % (p.grad,))
    assert q.grad == exact.from_nested((17, 29, 45)), (
        "q's grad is the sum over the rows of the seed times p: %r"
        % (q.grad,))

    x = node(((1, 2, 3), (4, 5, 6)))
    bias = node((1, 2, 3))
    loss = s.mean(s.mul(x, bias))
    assert base.backward(loss) is None, "backward returned something"
    assert x.grad == exact.from_nested(((Rational(1, 6), Rational(1, 3),
                                         Rational(1, 2)),
                                        (Rational(1, 6), Rational(1, 3),
                                         Rational(1, 2)))), (
        "a mean of all twelve cells halves nothing and divides by six: x's grad "
        "is %r" % (x.grad,))
    assert bias.grad == exact.from_nested((Rational(5, 6), Rational(7, 6),
                                           Rational(3, 2))), (
        "and the bias's grad is the sixths of the columns' sums: %r"
        % (bias.grad,))

    # ---- accumulation, never assignment -----------------------------------

    t = node(flat)
    twice = s.add(s.sum(t), s.sum(t))
    assert base.backward(twice) is None, "backward returned something"
    first = t.grad
    assert first == exact.full((2, 3), Rational(2)), (
        "the two sums contribute one each: t.grad is %r, not two at every cell"
        % (first,))
    assert base.backward(twice) is None, "backward returned something"
    assert t.grad == exact.add(first, first), (
        "a second backward without zero_grad left t.grad at %r, not twice the "
        "first call's %r: every local backward accumulates (§3.3)"
        % (t.grad, first))
    assert base.zero_grad(t, twice) is None, "zero_grad returned something"
    assert t.grad == exact.zeros((2, 3)), (
        "zero_grad left t.grad at %r, not the zeros of its shape" % (t.grad,))

    t = node(flat)
    twice = s.add(s.mean(t), s.mean(t))
    assert base.backward(twice) is None, "backward returned something"
    assert t.grad == exact.full((2, 3), Rational(1, 3)), (
        "the two means contribute one sixth each: t.grad is %r, not two sixths "
        "at every cell" % (t.grad,))
    assert base.backward(twice) is None, "backward returned something"
    assert t.grad == exact.full((2, 3), Rational(2, 3)), (
        "a second backward through the two means left t.grad at %r, not twice "
        "the first call's: mean's contribution accumulates like any other"
        % (t.grad,))
    assert base.zero_grad(t, twice) is None, "zero_grad returned something"
    assert t.grad == exact.zeros((2, 3)), (
        "zero_grad left t.grad at %r, not the zeros of its shape" % (t.grad,))

    a = node(((1, 2, 3), (4, 5, 6)))
    b = node((10, 20, 30))
    shared = s.mul(a, b)
    doubled = s.add(shared, shared)
    assert base.backward(doubled) is None, "backward returned something"
    assert a.grad == exact.from_nested(((20, 40, 60), (20, 40, 60))), (
        "a broadcast node reached by two paths hands the (2, 3) operand the "
        "sum of both: %r, not twice the bias" % (a.grad,))
    assert b.grad == exact.from_nested((10, 14, 18)), (
        "and the (3,) operand twice its own row sums: %r, not (10, 14, 18) — "
        "the reduction ran twice into the same grad" % (b.grad,))

    # ---- every gradient keeps its own operand's shape ---------------------

    x = base.Node(cube)
    y = node(((10, 20, 30, 40), (50, 60, 70, 80), (90, 100, 110, 120)))
    root = s.mean(s.add(s.mul(x, y), node((1, 2, 3, 4))))
    assert base.backward(root) is None, "backward returned something"
    seen = walk(root)
    assert len(seen) == 6, (
        "the graph reachable from the root has %d nodes, not the six the "
        "fixture builds" % (len(seen),))
    for reached in seen:
        assert reached.grad.shape == reached.value.shape, (
            "the gradient of a node of shape %r has shape %r: a gradient owes "
            "its operand its shape, never the output's and never the "
            "broadcast's" % (reached.value.shape, reached.grad.shape))
        assert all(isinstance(cell, Rational) for cell in reached.grad.cells), (
            "a gradient cell is not an exact.Rational: %r"
            % (reached.grad.cells,))
        assert all(isinstance(cell, Rational) for cell in reached.value.cells), (
            "a value cell is not an exact.Rational: %r" % (reached.value.cells,))

    # ---- the refusals -----------------------------------------------------

    for name, build in (("add", s.add), ("sub", s.sub), ("mul", s.mul)):
        message = _refuses(exact.ExactError,
                           "a %s of two shapes that do not broadcast" % (name,),
                           lambda: build(node(((1, 2, 3), (4, 5, 6))),
                                         node((1, 2, 3, 4))))
        assert "(2, 3)" in message and "(4,)" in message, (
            "the refusal of %s's two shapes does not name both: %r"
            % (name, message))
        assert "3" in message and "4" in message and "broadcast" in message, (
            "the refusal of %s's two shapes does not name both numbers and "
            "does not say they do not broadcast: %r" % (name, message))

    a = node((1, 2))
    message = _refuses(exact.AutogradError, "an add whose right operand is not a Node",
                       lambda: s.add(a, 3))
    assert "3" in message and "Node" in message, (
        "the refusal of a right operand that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "an add whose left operand is a bare Tensor",
                       lambda: s.add(exact.ones((2,)), a))
    assert "Node" in message, (
        "the refusal of a left operand that is a bare Tensor does not name it: "
        "%r" % (message,))
    message = _refuses(exact.AutogradError, "a sub whose left operand is an int",
                       lambda: s.sub(3, a))
    assert "3" in message, (
        "the refusal of sub's left operand does not name it: %r" % (message,))
    message = _refuses(exact.AutogradError, "a mul whose right operand is a Rational",
                       lambda: s.mul(a, Rational(1, 2)))
    assert "Rational(1, 2)" in message, (
        "the refusal of mul's right operand does not name it: %r" % (message,))
    message = _refuses(exact.AutogradError, "a sum of something that is not a Node",
                       lambda: s.sum(3))
    assert "3" in message and "Node" in message, (
        "the refusal of sum's operand does not name it: %r" % (message,))
    message = _refuses(exact.AutogradError, "a mean of a bare Tensor",
                       lambda: s.mean(exact.ones((2, 2)), 0))
    assert "Node" in message, (
        "the refusal of mean's operand does not name it: %r" % (message,))

    # an axis the operand does not have
    for op, call in (("sum", lambda: s.sum(node(((1, 2, 3), (4, 5, 6))), 2)),
                     ("mean", lambda: s.mean(node(((1, 2, 3), (4, 5, 6))), 3))):
        message = _refuses(exact.ExactError, "a %s on an axis of a rank-2 tensor" % (op,),
                           call)
        assert "(2, 3)" in message and "2 axes" in message and op in message, (
            "the refusal of %s's bad axis does not name the shape, its rank "
            "and the operation: %r" % (op, message))
    message = _refuses(exact.ExactError, "a negative axis below -rank",
                       lambda: s.sum(node((1, 2, 3)), -2))
    assert "-2" in message and "(3,)" in message and "1 axes" in message, (
        "the refusal of axis=-2 on a rank-1 tensor does not name the axis and "
        "the shape: %r" % (message,))
    message = _refuses(exact.ExactError, "an axis on a rank-0 tensor",
                       lambda: s.sum(node(Rational(5)), 0))
    assert "()" in message and "0 axes" in message, (
        "the refusal of axis=0 on a rank-0 tensor does not name the shape and "
        "its rank: %r" % (message,))
    message = _refuses(exact.ExactError, "a string axis",
                       lambda: s.sum(node((1, 2, 3)), "0"))
    assert "'0'" in message and "int" in message and "axis" in message, (
        "the refusal of a string axis does not name it as a non-int: %r"
        % (message,))
    message = _refuses(exact.ExactError, "a bool axis",
                       lambda: s.sum(node((1, 2, 3)), True))
    assert "True" in message and "axis" in message, (
        "the refusal of a bool axis does not name it: %r" % (message,))
    message = _refuses(exact.ExactError, "a mean on an axis a rank-3 tensor lacks",
                       lambda: s.mean(node((((1, 2), (3, 4)), ((5, 6), (7, 8)))),
                                      3))
    assert "(2, 2, 2)" in message and "3 axes" in message, (
        "the refusal of axis=3 on a rank-3 tensor does not name the shape and "
        "its rank: %r" % (message,))

    # an empty reduction: exact.mean refuses, the stage must not answer a number
    empty = base.Node(exact.zeros((0, 3)))
    message = _refuses(exact.ExactError, "a mean over an axis of extent 0",
                       lambda: s.mean(empty, 0))
    assert "(0, 3)" in message and "0" in message, (
        "the refusal of a mean over an axis of extent 0 does not name the shape "
        "and the extent: %r" % (message,))
    message = _refuses(exact.ExactError, "a mean of an empty tensor",
                       lambda: s.mean(base.Node(exact.zeros((0, 3)))))
    assert "(0, 3)" in message, (
        "the refusal of a mean of an empty tensor does not name the shape: %r"
        % (message,))

    print("check_03: broadcasting and the reduction — add, sub and mul carry "
          "exact's broadcast forward element for element, every operand the "
          "broadcast stretched is handed its own shape through "
          "exact.reduce_gradient and the equal-shape operand never reaches it, "
          "sum re-inserts the axis it removed and stretches it, mean scales "
          "that expansion by the exact 1/n of the extent it averaged, every "
          "contribution accumulates into its own operand, a shape that does not "
          "broadcast and an axis the operand does not have are refused naming "
          "both numbers, and every gradient is an exact Rational pair")

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import exact
    import fixtures
    import stage_01 as base
    import stage_03 as s3
    import stage_04 as s

    Rational = exact.Rational
    zero = Rational(0)

    def node(nested):
        """A leaf holding the `exact.Tensor` `nested` describes."""
        return base.Node(exact.from_nested(nested))

    def model(name):
        """The fixture model's parameters as fresh leaves, in `MODELS` order."""
        return [base.Node(tensor) for tensor in fixtures.MODELS[name]]

    # the rectangular, non-square, non-symmetric pair every shape probe uses,
    # its hand-computed product, and a gradient whose cells are distinct too
    A = ((1, 2, 3), (4, 5, 6))
    B = ((1, 0, -1, 2), (0, 1, 1, -1), (2, 2, 0, 1))
    C = ((7, 8, 1, 3), (16, 17, 1, 9))
    G = ((1, 2, 3, 4), (5, 6, 7, 8))

    # ---- matmul: the forward is exact's, element for element --------------

    a = node(A)
    b = node(B)
    made = s.matmul(a, b)
    assert made.value == exact.matmul(a.value, b.value), (
        "matmul's value is %r, not exact.matmul of its operands, %r: the "
        "forward is the provided algebra, element for element"
        % (made.value, exact.matmul(a.value, b.value)))
    assert made.value.cells == exact.from_nested(C).cells, (
        "matmul's value has the cells %r, not the hand-computed %r: a (2, 3) @ "
        "a (3, 4) is a (2, 4) whose cell [i, j] is sum_k a[i, k] * b[k, j]"
        % (made.value.cells, exact.from_nested(C).cells))
    assert made.value == exact.from_nested(C), (
        "matmul's value is %r, not the hand-computed %r"
        % (made.value, exact.from_nested(C)))
    assert made.value.shape == (2, 4), (
        "matmul's value has shape %r, not the (2, 4) of a (2, 3) @ a (3, 4)"
        % (made.value.shape,))
    assert made.parents == (a, b), (
        "matmul's parents are %r, not the two operands in the order they were "
        "passed" % (made.parents,))
    assert made.backward is not None and callable(made.backward), (
        "matmul's node carries %r, not a local backward: no gradient can leave "
        "it" % (made.backward,))
    assert made.grad == exact.zeros((2, 4)), (
        "matmul's node starts with grad %r, not the zeros of the value's shape"
        % (made.grad,))
    assert a.grad == exact.zeros((2, 3)) and b.grad == exact.zeros((3, 4)), (
        "building matmul touched an operand's grad: %r and %r" % (a.grad, b.grad))
    assert a.grad.shape == (2, 3) and b.grad.shape == (3, 4), (
        "the operands' grads have shapes %r and %r, not their own (2, 3) and "
        "(3, 4)" % (a.grad.shape, b.grad.shape))

    # ---- the two VJPs: dA = G B^T and dB = A^T G, by hand ------------------

    a = node(A)
    b = node(B)
    made = s.matmul(a, b)
    seed = exact.from_nested(G)
    assert base.backward(made, seed=seed) is None, (
        "backward returned something instead of leaving the grads on the nodes")
    assert made.grad == seed, (
        "the node's grad under the seed is %r, not the seed itself" % (made.grad,))
    assert a.grad == exact.from_nested(((6, 1, 10), (14, 5, 30))), (
        "d(A @ B)/dA is %r, not G · Bᵀ = ((6, 1, 10), (14, 5, 30)): the "
        "gradient is read against B's columns" % (a.grad,))
    assert b.grad == exact.from_nested(((21, 26, 31, 36),
                                        (27, 34, 41, 48),
                                        (33, 42, 51, 60))), (
        "d(A @ B)/dB is %r, not Aᵀ · G = ((21, 26, 31, 36), (27, 34, 41, 48), "
        "(33, 42, 51, 60)): the gradient is read against A's rows" % (b.grad,))
    assert a.grad.shape == (2, 3) and b.grad.shape == (3, 4), (
        "the VJPs have shapes %r and %r, not the operands' own (2, 3) and "
        "(3, 4): a gradient's shape is its operand's, not the node's"
        % (a.grad.shape, b.grad.shape))
    assert all(isinstance(cell, Rational)
               for cell in a.grad.cells + b.grad.cells + made.grad.cells), (
        "a VJP cell is not an exact.Rational: %r"
        % (a.grad.cells + b.grad.cells + made.grad.cells,))

    a = node(A)
    b = node(B)
    made = s.matmul(a, b)
    assert base.backward(made) is None, "backward returned something"
    assert a.grad == exact.from_nested(((2, 1, 5), (2, 1, 5))), (
        "under the seed ones dA is %r, not B's column sums repeated over the "
        "rows, ((2, 1, 5), (2, 1, 5))" % (a.grad,))
    assert b.grad == exact.from_nested(((5, 5, 5, 5), (7, 7, 7, 7),
                                        (9, 9, 9, 9))), (
        "under the seed ones dB is %r, not A's row sums repeated over the "
        "columns, ((5, 5, 5, 5), (7, 7, 7, 7), (9, 9, 9, 9))" % (b.grad,))

    # a *square* pair whose right operand is not symmetric: both formulas have
    # a legal shape here, so the transposes are told apart by the cells
    aq = node(((1, 2), (3, 4)))
    bq = node(((5, 6), (7, 8)))
    mq = s.matmul(aq, bq)
    assert mq.value == exact.from_nested(((19, 22), (43, 50))), (
        "the square probe's product is %r, not ((19, 22), (43, 50))"
        % (mq.value,))
    assert base.backward(mq, seed=exact.from_nested(((1, 2), (3, 4)))) is None, (
        "backward returned something")
    assert aq.grad == exact.from_nested(((17, 23), (39, 53))), (
        "on the square pair dA is %r, not G · Bᵀ = ((17, 23), (39, 53)): the "
        "right operand's formula, Aᵀ · G = ((10, 14), (14, 20)), is a legal "
        "shape here and the wrong cells" % (aq.grad,))
    assert bq.grad == exact.from_nested(((10, 14), (14, 20))), (
        "on the square pair dB is %r, not Aᵀ · G = ((10, 14), (14, 20)): "
        "G · Bᵀ = ((17, 23), (39, 53)) is a legal shape here and the wrong "
        "cells — and on a *symmetric* right operand the two would agree, which "
        "is why this fixture is neither square-and-paired nor symmetric"
        % (bq.grad,))

    # ---- a chain of two contractions --------------------------------------

    a = node(A)
    b = node(B)
    e = node(((1, 0), (0, 1), (1, 1), (-1, 2)))
    c = s.matmul(a, b)
    d = s.matmul(c, e)
    assert d.value == exact.from_nested(((5, 15), (8, 36))), (
        "the chain's value is %r, not the hand-computed ((5, 15), (8, 36))"
        % (d.value,))
    assert base.backward(d) is None, "backward returned something"
    assert c.grad == exact.from_nested(((1, 1, 2, 1), (1, 1, 2, 1))), (
        "the middle product's grad is %r, not 1 @ Eᵀ = ((1, 1, 2, 1), "
        "(1, 1, 2, 1))" % (c.grad,))
    assert a.grad == exact.from_nested(((1, 2, 5), (1, 2, 5))), (
        "the chain's gradient w.r.t. A is %r, not (G_E · Bᵀ) = ((1, 2, 5), "
        "(1, 2, 5)): two contractions compose, each with its own VJP"
        % (a.grad,))
    assert e.grad == exact.from_nested(((23, 23), (25, 25), (2, 2), (12, 12))), (
        "the chain's gradient w.r.t. E is %r, not Cᵀ · 1 = ((23, 23), (25, 25), "
        "(2, 2), (12, 12))" % (e.grad,))
    assert c.grad.shape == (2, 4) and a.grad.shape == (2, 3) and e.grad.shape == (4, 2), (
        "the chain's gradients have shapes %r, %r and %r, not their operands' "
        "(2, 4), (2, 3) and (4, 2)"
        % (c.grad.shape, a.grad.shape, e.grad.shape))

    # ---- accumulation: a weight two contractions share ---------------------

    x = node(((1, 2, 3), (4, 5, 6)))
    w = node(((1, 0), (0, 1), (1, 1)))
    one = s.matmul(x, w)
    two = s.matmul(x, w)
    total = s3.add(one, two)
    assert base.backward(total) is None, "backward returned something"
    assert one.grad == exact.ones((2, 2)) and two.grad == exact.ones((2, 2)), (
        "the two products' grads are %r and %r, not the seed one each"
        % (one.grad, two.grad))
    assert w.grad == exact.from_nested(((10, 10), (14, 14), (18, 18))), (
        "the shared weight's grad is %r, not twice 1 @ Wᵀ = ((10, 10), (14, 14), "
        "(18, 18)): two contractions into one weight *accumulate*, an "
        "assignment would leave one contribution's (5, 5), (7, 7), (9, 9)"
        % (w.grad,))
    assert x.grad == exact.from_nested(((2, 2, 4), (2, 2, 4))), (
        "the shared input's grad is %r, not twice 1 @ Wᵀ = ((2, 2, 4), "
        "(2, 2, 4))" % (x.grad,))

    # ---- mlp: the fixture's forward, and the layout it was read in --------

    assert fixtures.MODEL_PARAMS["mlp"] == ("w1", "b1", "w2", "b2"), (
        "the fixture's mlp names its tensors %r, not the (weight, bias) per "
        "layer order this stage documents" % (fixtures.MODEL_PARAMS["mlp"],))
    assert [tensor.shape for tensor in fixtures.MODELS["mlp"]] == \
        [(3, 4), (4,), (4, 1), (1,)], (
        "the fixture's mlp tensors have shapes %r, not w1 (3, 4), b1 (4,), "
        "w2 (4, 1), b2 (1,)"
        % ([tensor.shape for tensor in fixtures.MODELS["mlp"]],))

    for name, want in (("linear", ((-1,), (0,), (0,), (1,))),
                       ("mlp", ((-1,), (2,), (2,), (1,))),
                       ("deep", ((-1,), (-1,), (-3,), (0,)))):
        params = model(name)
        out = s.mlp(params, base.Node(fixtures.XOR[0]))
        assert isinstance(out, base.Node), (
            "mlp on %r returned %r, not a Node" % (name, out))
        assert out.value == exact.from_nested(want), (
            "mlp on the fixture's %r model is %r, not the hand-computed %r: "
            "x @ w1 + b1, then the activation on every layer but the last"
            % (name, out.value, exact.from_nested(want)))
        assert out.value.shape == exact.from_nested(want).shape, (
            "mlp on %r has shape %r, not %r"
            % (name, out.value.shape, exact.from_nested(want).shape))
        assert all(param.parents == () for param in params), (
            "mlp attached a parent to a parameter of %r: the caller's leaves "
            "are the graph's leaves" % (name,))

    params = model("mlp")
    out = s.mlp(params, base.Node(fixtures.XOR[0]))
    assert out.value.get((0, 0)) == Rational(-1), (
        "the mlp fixture's first prediction is %r, not the hand-computed -1 "
        "(the pre-activations of the fixture's own rows are 0, +/-1 and the "
        "output is the linear z2)" % (out.value.get((0, 0)),))

    # the (weight, bias) pair is not symmetric: reading it the other way round
    # hands the layer a rank-1 weight
    message = _refuses(
        exact.ExactError,
        "an mlp whose (weight, bias) pair is read in the reverse order",
        lambda: s.mlp(model("linear")[::-1], base.Node(fixtures.XOR[0])))
    assert "weight must be rank 2" in message and "(1,)" in message, (
        "the refusal of the fixture's pair read the other way round does not "
        "name the rank-1 weight: %r" % (message,))

    # ---- the whole graph: the fixture MLP, its loss, and the gradient -----

    params = model("mlp")
    x = base.Node(fixtures.XOR[0])
    y = base.Node(fixtures.XOR[1])
    out = s.mlp(params, x)
    residual = s3.sub(out, y)
    loss = s3.mean(s3.mul(residual, residual))
    assert loss.value == exact.from_nested(Rational(1)), (
        "the fixture's loss at its own weights is %r, not the exact 1: every "
        "residual of the frozen model is +/-1" % (loss.value,))
    assert base.backward(loss) is None, "backward returned something"
    for name, param, tensor in zip(fixtures.MODEL_PARAMS["mlp"], params,
                                   fixtures.MODELS["mlp"]):
        want = exact.Tensor(fixtures.REFERENCE_GRADIENTS[name], tensor.shape)
        assert param.grad.shape == tensor.shape, (
            "the gradient of %s has shape %r, not its own operand's %r: the "
            "rank-1 bias in particular must have been *reduced* back to "
            "(out,) — the output's shape is not the bias's"
            % (name, param.grad.shape, tensor.shape))
        assert param.grad == want, (
            "the gradient of %s is %r, not the fixture's frozen %r: the whole "
            "graph — the contractions, the broadcast bias and relu'(0) = 0 — "
            "is what the reference was computed with"
            % (name, param.grad.cells, want.cells))
        assert all(isinstance(cell, Rational) for cell in param.grad.cells), (
            "the gradient of %s has a cell that is not an exact.Rational" % (name,))

    # the fixture's free self-check: the bias and the first row of w1 receive
    # the same gradient (the input's constant-1 column), so an engine whose
    # bias gradient went through no reduction cannot have both
    assert params[0].grad.cells[:4] == params[1].grad.cells, (
        "w1's first row gradient is %r and b1's is %r: the fixture's constant-1 "
        "column makes the two identical, and they are not"
        % (params[0].grad.cells[:4], params[1].grad.cells))
    assert params[1].grad == exact.from_nested((1, 1, Rational(1, 2), Rational(1, 2))), (
        "b1's gradient is %r, not the reduced (1, 1, 1/2, 1/2): a bias whose "
        "gradient kept the output's shape, or was never summed over the rows, "
        "is zero or a matrix here" % (params[1].grad,))

    # a hand derivation of one weight, written out from the fixture's own
    # literals with no graph and no `exact` forward call: the same chain rule,
    # element by element
    w1, b1, w2, b2 = [tensor.to_nested() if tensor.ndim == 2 else tensor.cells
                      for tensor in fixtures.MODELS["mlp"]]
    rows = fixtures.XOR[0].to_nested()
    targets = [cell for row in fixtures.XOR[1].to_nested() for cell in row]
    z1 = [[sum(rows[i][k] * w1[k][j] for k in range(3)) + b1[j]
           for j in range(4)] for i in range(4)]
    a1 = [[cell if cell > zero else zero for cell in row] for row in z1]
    z2 = [sum(a1[i][j] * w2[j][0] for j in range(4)) + b2[0] for i in range(4)]
    delta = [Rational(2) * (z2[i] - targets[i]) / Rational(4) for i in range(4)]
    handed = [[delta[i] * w2[j][0] if z1[i][j] > zero else zero
               for j in range(4)] for i in range(4)]
    hand_w1 = tuple(sum(rows[i][k] * handed[i][j] for i in range(4))
                    for k in range(3) for j in range(4))
    assert params[0].grad.cells == hand_w1, (
        "w1's gradient is %r, not the hand-derived %r: delta = 2 (z2 - y) / 4, "
        "then the gate relu'(z1) = [z1 > 0], then xᵀ @ delta"
        % (params[0].grad.cells, hand_w1))
    assert z2 == [cell for (cell,) in out.value.to_nested()], (
        "the hand derivation's z2 is %r and the model's output is %r: the "
        "derivation is not of this graph" % (z2, out.value.to_nested()))

    # the last layer is linear: an mlp that activated it would have clipped the
    # fixture's -(1,) and the "linear" model's -(1,) and 0s
    out = s.mlp(model("linear"), base.Node(fixtures.XOR[0]))
    assert out.value.get((0, 0)) == Rational(-1) and out.value.get((1, 0)) == zero, (
        "the one-layer model's output is %r, not the hand-computed "
        "((-1,), (0,), (0,), (1,)): a relu on the last layer would clip both "
        "the negative cell and the zero" % (out.value,))

    # ---- what the stage refuses -------------------------------------------

    x = node(((1, 2, 3), (4, 5, 6)))
    message = _refuses(exact.ExactError, "a matmul whose right operand is rank 1",
                       lambda: s.matmul(x, node((1, 2, 3))))
    assert "a has shape" in message and "(2, 3)" in message and "(3,)" in message, (
        "the refusal of a rank-1 operand does not name both shapes: %r — and a "
        "rank-1 operand must be refused, not promoted to a row or a column"
        % (message,))
    message = _refuses(exact.ExactError, "a matmul whose left operand is rank 1",
                       lambda: s.matmul(node((1, 2, 3)), node(((1, 2), (3, 4), (5, 6)))))
    assert "a has shape" in message and "(3,)" in message and "(3, 2)" in message, (
        "the refusal of a rank-1 left operand does not name both shapes: %r"
        % (message,))

    message = _refuses(exact.ExactError, "a pair whose inner extents disagree",
                       lambda: s.matmul(x, node(((1, 2, 3, 4, 5),) * 4)))
    assert ("a has shape" in message and "(2, 3)" in message and "(4, 5)" in message
            and "3 and 4" in message), (
        "the refusal of a non-contracting pair does not name both shapes and "
        "both extents: %r" % (message,))
    message = _refuses(
        exact.ExactError,
        "a (2, 3) and a (4, 2): the two leading extents agree and the inner ones do not",
        lambda: s.matmul(x, node(((1, 2), (3, 4), (5, 6), (7, 8)))))
    assert ("a has shape" in message and "(2, 3)" in message and "(4, 2)" in message
            and "3 and 4" in message), (
        "the refusal of a (2, 3) against a (4, 2) does not name both shapes and "
        "both extents: %r — the extents that contract are axis 1 of a and axis "
        "0 of b, not the two leading ones" % (message,))

    message = _refuses(exact.AutogradError, "a matmul whose left operand is not a Node",
                       lambda: s.matmul(x.value, x))
    assert "a" in message and "Node" in message, (
        "the refusal of a left operand that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "a matmul whose right operand is not a Node",
                       lambda: s.matmul(x, 3))
    assert "b" in message and "3" in message, (
        "the refusal of a right operand that is not a Node does not name it: %r"
        % (message,))

    xin = node(((1, 0, 0), (1, 0, 1)))
    good = model("mlp")
    message = _refuses(exact.AutogradError, "an mlp whose params are not a sequence",
                       lambda: s.mlp(good[0], xin))
    assert "params" in message and "Node" in message, (
        "the refusal of a params that is not a sequence does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "an mlp with a dangling tensor",
                       lambda: s.mlp(good[:-1], xin))
    assert "pair per layer" in message and "3" in message, (
        "the refusal of an odd number of tensors does not name the count: %r"
        % (message,))
    message = _refuses(
        exact.AutogradError, "an mlp whose second parameter is not a Node",
        lambda: s.mlp([good[0], fixtures.MODELS["mlp"][1], good[2], good[3]], xin))
    assert "params[1]" in message, (
        "the refusal of a parameter that is not a Node does not name its "
        "position: %r" % (message,))
    message = _refuses(exact.ExactError, "an mlp whose weight is rank 1",
                       lambda: s.mlp([node((1, 2, 3)), node((1, 2, 3, 4))], xin))
    assert "weight must be rank 2" in message and "(3,)" in message, (
        "the refusal of a rank-1 weight does not name the rank and the shape: %r"
        % (message,))
    message = _refuses(exact.ExactError, "an mlp whose bias is rank 2",
                       lambda: s.mlp([good[0], node(((1, 2, 3, 4), (5, 6, 7, 8)))], xin))
    assert "bias must be rank 1" in message and "(2, 4)" in message, (
        "the refusal of a rank-2 bias does not name the rank and the shape: %r"
        % (message,))
    message = _refuses(exact.ExactError,
                       "an mlp whose input does not contract with the first weight",
                       lambda: s.mlp(good, node(((1, 0), (1, 1)))))
    assert "params[0]" in message and "(2, 2)" in message and "2 and 3" in message, (
        "the refusal of an input that does not contract does not name the layer "
        "and both extents: %r" % (message,))
    message = _refuses(exact.ExactError,
                       "an mlp whose bias extent does not match the layer's output",
                       lambda: s.mlp([good[0], node((1, 2, 3))], xin))
    assert "bias's extent" in message and "(3,)" in message and "(3, 4)" in message, (
        "the refusal of a bias whose extent does not match does not name both "
        "shapes: %r" % (message,))
    message = _refuses(exact.ExactError, "an mlp whose input is rank 1",
                       lambda: s.mlp(good, node((1, 0, 0))))
    assert "rank 2" in message and "(3,)" in message, (
        "the refusal of a rank-1 input does not name the rank and the shape: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "an mlp whose input is not a Node",
                       lambda: s.mlp(good, None))
    assert "x" in message and "Node" in message, (
        "the refusal of an input that is not a Node does not name it: %r"
        % (message,))

    print("check_04: the chain rule through a matrix — matmul carries exact's "
          "forward and the two VJPs G·Bᵀ and Aᵀ·G on a rectangular "
          "non-symmetric pair (each in its operand's shape and accumulated, "
          "never assigned), a chain of two contractions, and the fixture MLP "
          "whose rank-1 bias is broadcast in and reduced back and whose "
          "whole-graph gradient reproduces fixtures.REFERENCE_GRADIENTS")

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import exact
    import stage_01 as base
    import stage_05 as s

    Rational = exact.Rational

    def node(nested):
        """A stage-1 leaf holding the `exact.Tensor` `nested` describes."""
        return base.Node(exact.from_nested(nested))

    # ---- shared: the same node, handed back, not a copy -------------------

    x = node((2, 3))
    assert s.shared(x) is x, (
        "shared(x) gave back %r, not x itself: reuse is the identity of a "
        "node, and a copy is a second parameter" % (s.shared(x),))
    assert isinstance(s.shared(x), base.Node), (
        "shared(x) gave back %r, not the Node it was given" % (s.shared(x),))
    assert s.shared(x, x) is x and s.shared(x, x, x) is x, (
        "shared(x, x, x) gave back %r, not the one node every position names"
        % (s.shared(x, x, x),))
    assert s.shared(x, x, x).value == x.value and s.shared(x).parents == (), (
        "shared(x) is not the leaf it was given: %r" % (s.shared(x),))

    w = node((1, 1))
    v = node((2, -1))
    h = base.mul(w, v)
    assert s.shared(h) is h, (
        "shared of a node in the middle of a graph gave back %r, not that node"
        % (s.shared(h),))
    assert h.parents == (w, v) and h.parents[0] is w and h.parents[1] is v, (
        "sharing a node rewrote its parents: %r" % (h.parents,))
    assert h.backward is not None and h.value == exact.mul(w.value, v.value), (
        "sharing a node detached it: parents %r, backward %r"
        % (h.parents, h.backward))

    # ---- shared: nothing else changes -------------------------------------

    p = node((3, 4))
    q = node((3, 4))
    p.grad = exact.full((2,), 5)
    q.grad = exact.full((2,), 6)
    assert s.shared(p) is p and s.shared(p, p) is p, (
        "shared(p) is not p")
    assert p.grad == exact.full((2,), 5), (
        "sharing a node cleared its gradient to %r: a stage-5 helper may not "
        "silently clear a gradient it was not given" % (p.grad,))
    assert q.grad == exact.full((2,), 6), (
        "sharing a node cleared a neighbour's gradient to %r" % (q.grad,))
    p.requires_grad = False
    assert s.shared(p) is p and p.requires_grad is False, (
        "sharing a frozen parameter left it at requires_grad=%r: sharing does "
        "not thaw" % (p.requires_grad,))
    p.requires_grad = True
    frozen_p = s.trainable(p, requires_grad=False)
    assert isinstance(frozen_p, base.Node), (
        "the frozen use of a parameter is %r, not a Node: no graph can be "
        "built from it" % (frozen_p,))
    assert s.shared(frozen_p) is frozen_p, (
        "shared of a frozen node gave back %r, not the stop node trainable "
        "built" % (s.shared(frozen_p),))
    assert frozen_p.requires_grad is False, (
        "the frozen node reads requires_grad=%r: a freeze that hands back a "
        "node that wants a gradient is not a freeze" % (frozen_p.requires_grad,))
    p.requires_grad = True

    # ---- shared: the refusals ---------------------------------------------

    message = _refuses(exact.AutogradError, "a shared with no operands",
                       lambda: s.shared())
    assert "shared" in message and "operand" in message, (
        "the refusal of a shared with no operands does not name itself and "
        "what is missing: %r" % (message,))
    message = _refuses(exact.AutogradError, "a shared operand that is not a Node",
                       lambda: s.shared(3))
    assert "3" in message and "Node" in message, (
        "the refusal of a shared operand that is not a Node does not name the "
        "offender: %r" % (message,))
    message = _refuses(exact.AutogradError, "a Node and a bare value",
                       lambda: s.shared(x, 5))
    assert "5" in message, (
        "the refusal of a shared operand that is a bare value does not name "
        "it: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "two distinct nodes holding the same value",
                       lambda: s.shared(node((3, 4)), node((3, 4))))
    assert "shared" in message and "distinct" in message, (
        "the refusal of two distinct nodes does not say they are two nodes "
        "and not one shared parameter: %r" % (message,))
    assert message.count("Node(") == 2, (
        "the refusal of two distinct nodes names %d of them, not both: %r"
        % (message.count("Node("), message))
    message = _refuses(exact.AutogradError,
                       "two distinct nodes holding different values",
                       lambda: s.shared(node((1, 2)), node((3, 4))))
    assert message.count("Node(") == 2, (
        "the refusal of two distinct nodes names %d of them, not both: %r"
        % (message.count("Node("), message))

    # ---- one node, three paths: the gradient is the sum of all of them ----

    x = node((2, 3))
    one = s.shared(x)
    square = base.mul(one, one)                   # path 1: x * x
    twice = base.mul(one, base.add(one, one))     # path 2: x * (x + x)
    plus = base.add(base.mul(one, one), one)      # path 3: x * x + x
    out = base.add(base.add(square, twice), plus)
    expected = exact.add(
        exact.add(exact.mul(x.value, x.value),
                  exact.mul(x.value, exact.add(x.value, x.value))),
        exact.add(exact.mul(x.value, x.value), x.value))
    assert out.value == expected and out.value.cells == expected.cells, (
        "the three-path graph's value is %r, not exact's own forward %r: the "
        "forward is the provided algebra, element for element"
        % (out.value, expected))
    assert out.value == exact.from_nested((18, 39)), (
        "the three-path graph's value is %r, not (18, 39)" % (out.value,))
    assert base.backward(out) is None, "backward returned something"
    assert out.grad == exact.ones((2,)) and square.grad == exact.ones((2,)), (
        "the intermediate grads are %r and %r, not the seed one each"
        % (out.grad, square.grad))
    assert twice.grad == exact.ones((2,)) and plus.grad == exact.ones((2,)), (
        "the two other paths' grads are %r and %r, not the seed one each"
        % (twice.grad, plus.grad))
    assert x.grad == exact.from_nested((17, 25)), (
        "d(3x^2 + x)/dx is %r, not 8x + 1 = (17, 25): every one of the three "
        "paths into the shared node adds to its one grad, and the paths inside "
        "a path count twice" % (x.grad,))
    assert x.grad.shape == x.value.shape == (2,), (
        "the leaf's gradient has shape %r, not its operand's %r"
        % (x.grad.shape, x.value.shape))
    assert all(isinstance(cell, Rational) for cell in x.grad.cells), (
        "a gradient cell is not an exact.Rational: %r" % (x.grad.cells,))

    first = (out.grad, square.grad, twice.grad, plus.grad, x.grad)
    assert base.backward(out) is None, "backward returned something"
    assert out.grad == exact.add(first[0], first[0]), (
        "a second backward without zero_grad left the root at %r, not twice "
        "its first call's %r" % (out.grad, first[0]))
    assert square.grad == exact.add(first[1], first[1]), (
        "a second backward left the first path at %r, not twice %r"
        % (square.grad, first[1]))
    assert twice.grad == exact.add(first[2], first[2]), (
        "a second backward left the second path at %r, not twice %r"
        % (twice.grad, first[2]))
    assert plus.grad == exact.add(first[3], first[3]), (
        "a second backward left the third path at %r, not twice %r"
        % (plus.grad, first[3]))
    assert x.grad == exact.add(first[4], first[4]), (
        "a second backward without zero_grad left the leaf at %r, not twice "
        "the first call's %r: the gradients accumulate across calls (§3.3)"
        % (x.grad, first[4]))
    assert x.grad == exact.from_nested((34, 50)), (
        "the literal doubling of a second backward is %r, not (34, 50)"
        % (x.grad,))

    # ---- zero_grad: the graph above the argument, and nothing else --------

    assert base.zero_grad(out) is None, "zero_grad returned something"
    assert x.grad == exact.zeros((2,)) and out.grad == exact.zeros((2,)), (
        "zero_grad(out) left the leaf at %r and the root at %r"
        % (x.grad, out.grad))
    assert base.backward(out) is None, "backward returned something"
    assert x.grad == exact.from_nested((17, 25)), (
        "after zero_grad(out) a backward left the leaf at %r, not the fresh "
        "(17, 25)" % (x.grad,))
    kept = (out.grad, square.grad, twice.grad, plus.grad)
    assert base.zero_grad(x) is None, "zero_grad returned something"
    assert x.grad == exact.zeros((2,)), (
        "zero_grad(x) left the leaf at %r" % (x.grad,))
    assert (out.grad, square.grad, twice.grad, plus.grad) == kept, (
        "zero_grad(x) cleared a node that is not reachable from x through its "
        "parents: %r became %r"
        % (kept, (out.grad, square.grad, twice.grad, plus.grad)))

    # ---- a fan-out of three uses of one node ------------------------------

    w = node((1, 2))
    same = s.shared(w, w, w)
    fan = base.add(base.add(same, same), same)
    assert fan.value == exact.from_nested((3, 6)), (
        "the fan-out's value is %r, not three times (1, 2)" % (fan.value,))
    assert base.backward(fan) is None, "backward returned something"
    assert w.grad == exact.full((2,), 3), (
        "d(3w)/dw is %r, not the three ones of its three paths: the same node "
        "reachable three times is one node" % (w.grad,))
    assert w.grad.shape == w.value.shape == (2,), (
        "the fanned-out node's gradient has shape %r, not its operand's %r"
        % (w.grad.shape, w.value.shape))

    # ---- trainable: the thaw ----------------------------------------------

    p = node((3, 4))
    thawed = s.trainable(p, requires_grad=True)
    assert thawed is p, (
        "trainable(p, requires_grad=True) gave back %r, not the parameter: a "
        "thawed parameter is the node the graph accumulates into" % (thawed,))
    assert p.requires_grad is True, (
        "a thawed parameter reads requires_grad=%r" % (p.requires_grad,))
    p.grad = exact.full((2,), 9)
    assert s.trainable(p, requires_grad=True) is p, "the thaw gave back a copy"
    assert p.grad == exact.full((2,), 9), (
        "the thaw cleared the gradient the caller had gathered, leaving %r: a "
        "thaw is not a zero_grad" % (p.grad,))

    # ---- trainable: the freeze is a stop, and the parameter is out --------

    p = node((3, 4))
    p.grad = exact.full((2,), 9)
    frozen = s.trainable(p, requires_grad=False)
    assert frozen is not p, (
        "trainable(p, requires_grad=False) gave back the parameter itself, so "
        "the backward still accumulates into it and it is not out of the "
        "update")
    assert isinstance(frozen, base.Node), (
        "the frozen use of a parameter is %r, not a Node" % (frozen,))
    assert frozen.value == p.value and frozen.value.cells == p.value.cells, (
        "the frozen node's value is %r, not the parameter's %r: a freeze must "
        "not change the forward" % (frozen.value, p.value))
    assert frozen.value.shape == p.value.shape == (2,), (
        "the frozen node's value has shape %r, not the parameter's %r"
        % (frozen.value.shape, p.value.shape))
    assert frozen.parents == () and isinstance(frozen.parents, tuple), (
        "the frozen node carries the parents %r: the old graph is attached to "
        "it, and the backward reaches through it" % (frozen.parents,))
    assert frozen.backward is None, (
        "the frozen node carries the local backward %r: the backward reaches "
        "through it" % (frozen.backward,))
    assert frozen.requires_grad is False, (
        "the frozen node reads requires_grad=%r, so it wants a gradient"
        % (frozen.requires_grad,))
    assert p.requires_grad is False, (
        "after the freeze the parameter itself reads requires_grad=%r"
        % (p.requires_grad,))
    assert p.grad == exact.zeros((2,)), (
        "the freeze left the previous grad %r in place: the first step after a "
        "thaw would apply a gradient the freeze declared irrelevant" % (p.grad,))
    assert p.grad.shape == (2,), (
        "the cleared gradient has shape %r, not the parameter's (2,)"
        % (p.grad.shape,))
    assert frozen.grad == exact.zeros((2,)) and frozen.grad.shape == (2,), (
        "the frozen node starts with grad %r of shape %r, not the zeros of the "
        "parameter's shape" % (frozen.grad, frozen.grad.shape))

    # ---- trainable: nobody else's gradient is touched ---------------------

    a = node((2, 3))
    b = node((1, 1))
    h = base.mul(a, b)
    a.grad = exact.ones((2,))
    b.grad = exact.full((2,), 7)
    h.grad = exact.full((2,), 5)
    frozen_h = s.trainable(h, requires_grad=False)
    assert a.grad == exact.ones((2,)), (
        "freezing h cleared a.grad to %r: a freeze clears the frozen node's "
        "own gradient and nothing else" % (a.grad,))
    assert b.grad == exact.full((2,), 7), (
        "freezing h cleared b.grad to %r: freezing is not a zero_grad over the "
        "graph, and the parameters above it are still training" % (b.grad,))
    assert h.grad == exact.zeros((2,)), (
        "freezing h left h.grad at %r" % (h.grad,))
    assert h.parents == (a, b) and h.parents[0] is a and h.parents[1] is b, (
        "freezing h emptied its parents to %r: the freeze must not detach the "
        "node in place — the rest of the graph still reads it" % (h.parents,))
    assert h.backward is not None, (
        "freezing h removed its local backward in place")
    assert h.requires_grad is False, (
        "after the freeze h reads requires_grad=%r" % (h.requires_grad,))
    assert frozen_h.parents == () and frozen_h.backward is None, (
        "the frozen node of h carries %r and %r" % (frozen_h.parents,
                                                    frozen_h.backward))
    assert frozen_h.value == h.value, (
        "the frozen node of h holds %r, not h's %r" % (frozen_h.value, h.value))

    # ---- the backward cannot reach through the frozen node ----------------

    w = node((2, 3))
    x = node((1, 1))
    square = base.mul(w, w)
    frozen = s.trainable(square, requires_grad=False)
    out = base.add(base.mul(frozen, x), base.mul(w, x))
    expected = exact.add(exact.mul(square.value, x.value),
                         exact.mul(w.value, x.value))
    assert out.value == expected and out.value.cells == expected.cells, (
        "the frozen branch's forward is %r, not exact's %r: a freeze changes "
        "the graph, not the arithmetic" % (out.value, expected))
    assert base.backward(out) is None, "backward returned something"
    assert frozen.grad == x.value, (
        "the frozen use gathered %r, not the seed times x, %r"
        % (frozen.grad, x.value))
    assert w.grad == x.value, (
        "the parameter above the frozen node reads %r, not %r: the backward "
        "reached through the frozen node into the graph above it"
        % (w.grad, x.value))
    assert x.grad == exact.add(square.value, w.value), (
        "x's gradient is %r, not the frozen value plus w's, %r"
        % (x.grad, exact.add(square.value, w.value)))
    assert square.grad == exact.zeros((2,)), (
        "the node the freeze replaced is not in the graph, and its grad reads "
        "%r" % (square.grad,))
    assert frozen.grad.shape == frozen.value.shape == (2,), (
        "the frozen node's gradient has shape %r, not its value's %r"
        % (frozen.grad.shape, frozen.value.shape))
    message = _refuses(exact.AutogradError, "a backward from a frozen node",
                       lambda: base.backward(frozen))
    assert "requires_grad" in message, (
        "the refusal of a backward from a frozen node does not say why: %r"
        % (message,))

    # ---- the freeze and the thaw, on one training step --------------------

    p = node((2, 3))
    q = node((1, 1))
    frozen = s.trainable(p, requires_grad=False)
    out = base.add(base.mul(frozen, q), base.mul(q, q))
    assert out.value == exact.add(exact.mul(p.value, q.value),
                                 exact.mul(q.value, q.value)), (
        "the step's value is %r, not exact's %r"
        % (out.value, exact.add(exact.mul(p.value, q.value),
                                exact.mul(q.value, q.value))))
    assert base.backward(out) is None, "backward returned something"
    assert p.grad == exact.zeros((2,)), (
        "the frozen parameter's grad reads %r: the graph never names it, so "
        "the freeze took it out of the update" % (p.grad,))
    assert q.grad == exact.add(frozen.value, exact.add(q.value, q.value)), (
        "the training parameter's grad is %r, not the frozen value plus 2q, %r"
        % (q.grad, exact.add(frozen.value, exact.add(q.value, q.value))))

    learning_rate = Rational(1, 4)

    def step(parameter):
        """One exact step: `value - learning_rate * grad`, in `exact`."""
        return exact.sub(parameter.value,
                         exact.mul(exact.full(parameter.value.shape,
                                              learning_rate),
                                   parameter.grad))

    assert step(p) == p.value, (
        "a step moved the frozen parameter from %r to %r: freezing takes it "
        "out of the update" % (p.value, step(p)))
    assert step(q) != q.value, (
        "a step left the training parameter at %r: freezing one parameter "
        "must not disturb the others" % (q.value,))
    assert step(q) == exact.sub(q.value,
                                exact.mul(exact.full((2,), learning_rate),
                                          q.grad)), (
        "the training parameter's step is %r, not value - lr * grad"
        % (step(q),))

    assert s.trainable(p, requires_grad=True) is p, (
        "the thaw of p gave back something else")
    assert p.requires_grad is True, (
        "after the thaw p reads requires_grad=%r" % (p.requires_grad,))
    assert p.grad == exact.zeros((2,)), (
        "the thaw left p.grad at %r, not the zero the freeze left"
        % (p.grad,))
    square = base.mul(p, p)
    assert base.backward(square) is None, "backward returned something"
    assert p.grad == exact.add(p.value, p.value), (
        "after a freeze and a thaw, d(p * p)/dp is %r, not 2p = %r"
        % (p.grad, exact.add(p.value, p.value)))
    assert p.grad.shape == (2,), (
        "the thawed parameter's gradient has shape %r, not (2,)"
        % (p.grad.shape,))

    # ---- the freeze is idempotent, and its refusals name the offender -----

    p = node((5, 6))
    first = s.trainable(p, requires_grad=False)
    second = s.trainable(p, requires_grad=False)
    for frozen in (first, second):
        assert frozen.parents == () and frozen.backward is None, (
            "a second freeze handed back %r, not a stop" % (frozen,))
        assert frozen.value == p.value and frozen.requires_grad is False, (
            "a second freeze handed back %r of shape %r"
            % (frozen.value, frozen.value.shape))
    assert p.requires_grad is False and p.grad == exact.zeros((2,)), (
        "freezing twice left the parameter at requires_grad=%r and grad=%r"
        % (p.requires_grad, p.grad))

    message = _refuses(exact.AutogradError, "a trainable node that is not a Node",
                       lambda: s.trainable(3, requires_grad=False))
    assert "3" in message and "Node" in message, (
        "the refusal of a trainable node that is not a Node does not name the "
        "offender: %r" % (message,))
    message = _refuses(exact.AutogradError, "a trainable of a bare Tensor",
                       lambda: s.trainable(exact.ones((2,)), requires_grad=True))
    assert "Node" in message, (
        "the refusal of a trainable of a bare Tensor does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "a requires_grad that is not a bool",
                       lambda: s.trainable(node((1, 2)), requires_grad=1))
    assert "1" in message and "bool" in message, (
        "the refusal of requires_grad=1 does not name the offender and the two "
        "things it may be: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a requires_grad that is a string",
                       lambda: s.trainable(node((1, 2)), requires_grad="no"))
    assert "no" in message, (
        "the refusal of a requires_grad that is a string does not name it: %r"
        % (message,))

    try:
        s.trainable(node((1, 2)), False)
    except TypeError:
        pass
    else:
        raise AssertionError(
            "trainable's requires_grad is not keyword-only: a second positional "
            "argument was accepted")

    print("check_05: accumulation and reuse — shared hands back the very node "
          "it was given (a copy is a second parameter, and two nodes that hold "
          "the same value are refused), one node reached by three paths gets "
          "the sum of every contribution and a second backward without "
          "zero_grad doubles it, and trainable freezes a parameter into a stop "
          "the backward cannot pass — with its stale gradient dropped, its "
          "neighbours' gradients untouched, and its thaw handing back the "
          "parameter itself")

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import exact
    import stage_01 as s1
    import stage_06 as s

    Rational = exact.Rational

    def node(nested):
        """A leaf of the shared graph, built by stage 1's `Node`."""
        return s1.Node(exact.from_nested(nested))

    # ---- a non-scalar root: the refusal, and what it has to name ----------

    for nested in ((2, -3), (1, 2, 3), ((1, 2), (3, 4)), ((1, 2, 3), (4, 5, 6))):
        root = node(nested)
        message = _refuses(
            exact.AutogradError, "a backward from a non-scalar root",
            lambda root=root: s.backward(root))
        assert repr(root.value.shape) in message, (
            "the refusal of a backward from a %r root does not name its shape: "
            "%r" % (root.value.shape, message))
        assert "seed" in message, (
            "the refusal of a backward from a %r root does not name the seed "
            "that is missing: %r" % (root.value.shape, message))
        assert root.grad == exact.zeros(root.value.shape), (
            "a refused backward wrote %r into the root's grad: a refusal "
            "leaves the graph alone" % (root.grad,))

    x = node((1, 2))
    y = node((3, 4))
    total = s1.add(x, y)
    message = _refuses(exact.AutogradError,
                       "a backward from a non-scalar node above a leaf",
                       lambda: s.backward(total))
    assert "(2,)" in message and "seed" in message, (
        "the refusal of a backward from a non-scalar node does not name the "
        "shape and the missing seed: %r" % (message,))

    # ---- the seed the caller gives is the one the VJP contracts against ---

    p = node((2, 3))
    q = node((4, 5))
    product = s1.mul(p, q)
    assert s.backward(product, seed=exact.from_nested((1, 0))) is None, (
        "backward returned something instead of leaving the grads on the nodes")
    assert product.grad == exact.from_nested((1, 0)), (
        "the root's grad under the seed (1, 0) is %r, not the seed itself"
        % (product.grad,))
    assert p.grad == exact.from_nested((4, 0)), (
        "d(p * q)/dp under the seed (1, 0) is %r, not q * (1, 0) = (4, 0)"
        % (p.grad,))
    assert q.grad == exact.from_nested((2, 0)), (
        "d(p * q)/dq under the seed (1, 0) is %r, not p * (1, 0) = (2, 0)"
        % (q.grad,))
    invented = exact.mul(exact.ones((2,)), q.value)
    assert invented == exact.from_nested((4, 5)), (
        "the check's fixture is wrong: the ones-seeded gradient is %r"
        % (invented,))
    assert p.grad != invented, (
        "the seed the caller gave and the ones this stage refuses to invent "
        "have to differ: d(p * q)/dp is %r under the seed (1, 0) and %r under "
        "the ones a seeded default would have used — the mistake this stage "
        "catches is a backward that returns the second" % (p.grad, invented))

    a = node((1, 1))
    b = node((2, 2))
    summed = s1.add(a, b)
    seed = exact.from_nested((10, -20))
    assert s.backward(summed, seed=seed) is None, "backward returned something"
    assert summed.grad == seed and a.grad == seed and b.grad == seed, (
        "under the seed (10, -20) the sum's grads are %r, %r and %r, not the "
        "seed on each: the seed is contracted per cell, not summed into a "
        "number" % (summed.grad, a.grad, b.grad))

    wide = node(((1, 2, 3), (4, 5, 6)))
    matrix_seed = exact.from_nested(((1, 0, 2), (0, 3, 0)))
    assert s.backward(wide, seed=matrix_seed) is None, "backward returned something"
    assert wide.grad == matrix_seed and wide.grad.shape == (2, 3), (
        "the root's grad under a (2, 3) seed is %r of shape %r, not the seed"
        % (wide.grad, wide.grad.shape))

    ratio = node((Rational(1, 2), Rational(3, 5)))
    ratio_seed = exact.from_nested((Rational(2, 3), Rational(-4, 7)))
    assert s.backward(ratio, seed=ratio_seed) is None, "backward returned something"
    assert ratio.grad == ratio_seed, (
        "the root's grad under a Rational seed is %r, not the seed" % (ratio.grad,))
    assert all(isinstance(cell, Rational) for cell in ratio.grad.cells), (
        "a gradient cell is not an exact.Rational: %r" % (ratio.grad.cells,))

    # ---- a single-cell root keeps the ones of its own shape ---------------

    for nested in (5, (7,), ((5,),), (((9,),),)):
        root = node(nested)
        assert s.backward(root) is None, "backward returned something"
        assert root.grad.shape == root.value.shape, (
            "a %r root's default gradient has shape %r: the default seed is "
            "the ones of the root's own shape"
            % (root.value.shape, root.grad.shape))
        assert root.grad == exact.ones(root.value.shape), (
            "a %r root's default gradient is %r, not the ones of its own shape"
            % (root.value.shape, root.grad))

    single = node(((3,),))
    assert s.backward(single, seed=exact.from_nested(((2,),))) is None, (
        "backward returned something")
    assert single.grad == exact.from_nested(((2,),)), (
        "a single-cell root's grad under the seed ((2,),) is %r, not the seed"
        % (single.grad,))

    # ---- the seed's shape is compared to the root's, never merged ---------

    held = wide.grad
    for nested, what in (
            ((1, 2, 3), "a seed of a shape that would broadcast over the rows"),
            ((1,), "a seed of one row for a two-row root"),
            ((1, 2), "a seed of the wrong rank"),
            (((1, 2), (3, 4), (5, 6)),
             "a seed of the same cell count and the wrong shape")):
        message = _refuses(
            exact.AutogradError, what,
            lambda nested=nested: s.backward(
                wide, seed=exact.from_nested(nested)))
        assert repr(exact.from_nested(nested).shape) in message, (
            "the refusal of %s does not name the seed's shape: %r"
            % (what, message))
        assert "(2, 3)" in message, (
            "the refusal of %s does not name the root's shape: %r"
            % (what, message))

    message = _refuses(
        exact.AutogradError, "a seed of the wrong shape for a single-cell root",
        lambda: s.backward(node(((3,),)), seed=exact.from_nested(2)))
    assert "()" in message and "(1, 1)" in message, (
        "the refusal of a () seed for a (1, 1) root does not name both shapes: "
        "%r" % (message,))
    assert wide.grad == held, (
        "a refused seed wrote %r into the root's grad, not the %r it held: a "
        "refusal happens before the walk" % (wide.grad, held))

    for seed, what in (
            (((1, 2, 3), (4, 5, 6)), "a nested tuple"),
            ([[1, 2, 3], [4, 5, 6]], "a list"),
            (3, "a bare int"),
            (Rational(1, 2), "a bare Rational")):
        message = _refuses(exact.AutogradError, "a seed that is %s" % (what,),
                           lambda seed=seed: s.backward(wide, seed=seed))
        assert "seed" in message and "Tensor" in message, (
            "the refusal of %s does not name the seed and the type it must "
            "be: %r" % (what, message))

    message = _refuses(exact.AutogradError, "a root that is not a Node",
                       lambda: s.backward(exact.from_nested((1, 2))))
    assert "Node" in message, (
        "the refusal of a root that is not a Node does not name it: %r"
        % (message,))
    frozen = s1.Node(exact.from_nested((1,)), requires_grad=False)
    message = _refuses(exact.AutogradError, "a root with requires_grad=False",
                       lambda: s.backward(frozen))
    assert "requires_grad" in message, (
        "the refusal of a root that does not want a gradient does not say so: "
        "%r" % (message,))
    frozen_wide = s1.Node(exact.from_nested((1, 2)), requires_grad=False)
    message = _refuses(
        exact.AutogradError, "a non-scalar root with requires_grad=False",
        lambda: s.backward(frozen_wide, seed=exact.from_nested((1, 1))))
    assert "requires_grad" in message, (
        "the refusal of a non-scalar root that does not want a gradient does "
        "not say so: %r" % (message,))

    # ---- a call accumulates into the fields, it does not assign ----------

    u = node((1, 1))
    v = node((2, 2))
    out = s1.mul(u, v)
    seed = exact.from_nested((1, 0))
    assert s.backward(out, seed=seed) is None, "backward returned something"
    first_u, first_v = u.grad, v.grad
    assert first_u == exact.from_nested((2, 0)), (
        "the first call left u.grad at %r, not (2, 0)" % (first_u,))
    assert s.backward(out, seed=seed) is None, "backward returned something"
    assert u.grad == exact.add(first_u, first_u) and v.grad == exact.add(first_v, first_v), (
        "a second backward without zero_grad left u.grad %r and v.grad %r, not "
        "twice the first call's %r and %r: the gradients accumulate (§3.3)"
        % (u.grad, v.grad, first_u, first_v))
    assert out.grad == exact.from_nested((2, 0)), (
        "the root's grad after two calls is %r, not the sum of the two seeds"
        % (out.grad,))

    # ---- the walk visits every node exactly once --------------------------

    calls = []
    base = node((1, 1))
    above = base
    for _ in range(8):
        parent = above

        def local(gradient, parent=parent):
            calls.append(parent)
            parent.grad = exact.add(parent.grad, exact.add(gradient, gradient))

        above = s1.Node(exact.add(parent.value, parent.value),
                        parents=(parent, parent), backward=local)
    assert s.backward(above, seed=exact.ones((2,))) is None, (
        "backward returned something")
    assert len(calls) == 8, (
        "the backward ran the chain's local backwards %d times, not once per "
        "node: a walk with no visited set visits a shared node once per path "
        "out of the root" % (len(calls),))
    assert base.grad == exact.full((2,), 2 ** 8), (
        "eight doublings of the seed left the leaf at %r, not 2**8 ones: each "
        "node of the chain is walked exactly once" % (base.grad,))

    # ---- stage 1's backward and stage 6's are one engine ------------------

    def shared_graph():
        """The same graph twice: a reused parameter reached by two paths."""
        w = node((2, -3))
        x = node((5, 7))
        return w, s1.add(s1.mul(w, x), s1.mul(w, x))

    left_w, left_root = shared_graph()
    right_w, right_root = shared_graph()
    seed = exact.from_nested((3, -4))
    assert s1.backward(left_root, seed=seed) is None, "backward returned something"
    assert s.backward(right_root, seed=seed) is None, "backward returned something"
    assert left_root.value == right_root.value, (
        "the two graphs disagree in their forward: %r and %r"
        % (left_root.value, right_root.value))
    assert left_root.grad == right_root.grad, (
        "stage 1's backward left the shared graph's root at %r and stage 6's at "
        "%r: the two stages must be one engine"
        % (left_root.grad, right_root.grad))
    twice_x = exact.from_nested((10, 14))
    assert left_w.grad == right_w.grad == exact.mul(seed, twice_x), (
        "the reused parameter's gradients are %r and %r under the seed (3, -4), "
        "not seed * 2x = %r" % (left_w.grad, right_w.grad, exact.mul(seed, twice_x)))

    def scalar_graph():
        """The same scalar graph twice: a product of two single-cell leaves."""
        w = node(Rational(3, 2))
        x = node(Rational(-4, 5))
        return w, s1.mul(w, x)

    left_w, left_root = scalar_graph()
    right_w, right_root = scalar_graph()
    assert s1.backward(left_root) is None, "backward returned something"
    assert s.backward(right_root) is None, "backward returned something"
    assert left_root.grad == right_root.grad == exact.from_nested(Rational(1)), (
        "the default seed of a scalar root is %r and %r, not the ones the "
        "scalar VJP starts from" % (left_root.grad, right_root.grad))
    assert left_w.grad == right_w.grad == exact.from_nested(Rational(-4, 5)), (
        "d(w * x)/dw is %r and %r, not x = -4/5" % (left_w.grad, right_w.grad))

    seen = []
    original = s1.backward

    def recording(root, seed=None):
        seen.append((root, seed))
        return original(root, seed=seed)

    probe = node((1, 2))
    probe_seed = exact.from_nested((4, 5))
    scalar_probe = node(((3,),))
    s1.backward = recording
    try:
        assert s.backward(probe, seed=probe_seed) is None, (
            "backward returned something")
        assert s.backward(scalar_probe) is None, "backward returned something"
    finally:
        s1.backward = original
    assert len(seen) == 2, (
        "stage 6's backward ran stage 1's walk %d times for two calls: the "
        "seed is this stage's business, the order and the accumulation are "
        "stage 1's, and a walk of its own is a second place for them to drift"
        % (len(seen),))
    assert seen[0][0] is probe and seen[0][1] == probe_seed, (
        "stage 6 ran stage 1's walk with the root %r and the seed %r, not the "
        "root it was given and the seed the caller gave"
        % (seen[0][0], seen[0][1]))
    assert seen[1][0] is scalar_probe, (
        "stage 6 ran stage 1's walk with %r, not the root it was given"
        % (seen[1][0],))
    assert seen[1][1] == exact.ones((1, 1)), (
        "a single-cell (1, 1) root went to the walk with the seed %r, not the "
        "ones of its own shape" % (seen[1][1],))

    # ---- sum_to_scalar: the explicit scalar, its value and its gradient ---

    CASES = (
        5,
        (-3,),
        (2, -5, 7),
        ((1, 2, 3), (4, 5, 6)),
        (((1, 2), (3, 4)), ((5, 6), (7, 8))),
        ((Rational(1, 2), Rational(-3, 4)), (Rational(7, 5), Rational(0))),
    )

    for nested in CASES:
        t = node(nested)
        made = s.sum_to_scalar(t)
        assert made.value == exact.sum(t.value), (
            "sum_to_scalar of %r has the value %r, not exact.sum's %r"
            % (nested, made.value, exact.sum(t.value)))
        assert made.value.cells == exact.sum(t.value).cells, (
            "sum_to_scalar of %r has the cells %r, not the sum's %r"
            % (nested, made.value.cells, exact.sum(t.value).cells))
        assert made.value.shape == () and made.value.size == 1, (
            "sum_to_scalar's value has shape %r, not the rank-0 () a scalar "
            "output is" % (made.value.shape,))
        assert made.parents == (t,) and made.parents[0] is t, (
            "sum_to_scalar's parents are %r, not the node it was given: the "
            "gradient has to land on the operand" % (made.parents,))
        assert made.backward is not None and callable(made.backward), (
            "sum_to_scalar's node carries %r, not a local backward: no "
            "gradient can leave it" % (made.backward,))
        assert made.grad == exact.zeros(()) and t.grad == exact.zeros(t.value.shape), (
            "building sum_to_scalar touched a grad: %r and %r"
            % (made.grad, t.grad))
        assert s.backward(made) is None, (
            "backward returned something instead of leaving the grads on the nodes")
        assert made.grad == exact.ones(()), (
            "the sum node's grad is %r, not the seed ones" % (made.grad,))
        assert t.grad.shape == t.value.shape, (
            "the gradient of a %r operand has shape %r: a gradient's shape is "
            "its operand's" % (t.value.shape, t.grad.shape))
        assert t.grad == exact.ones(t.value.shape), (
            "d(sum(%r))/dt is %r, not the ones of the operand's shape %r: the "
            "scalar gradient goes to every cell it came from, in the operand's "
            "own axis order" % (nested, t.grad, t.value.shape))
        assert all(isinstance(cell, Rational)
                   for cell in t.grad.cells + made.grad.cells), (
            "a gradient cell is not an exact.Rational: %r"
            % (t.grad.cells + made.grad.cells,))

    t = node(((2, 3), (4, 5)))
    scale = node(Rational(3, 4))
    made = s.sum_to_scalar(t)
    product = s1.mul(made, scale)
    assert product.value == exact.from_nested(Rational(21, 2)), (
        "the sum node in a product is %r, not 14 * 3/4 = 21/2" % (product.value,))
    assert s.backward(product) is None, "backward returned something"
    assert made.grad == exact.from_nested(Rational(3, 4)), (
        "the sum node's grad through the product is %r, not the other operand "
        "3/4" % (made.grad,))
    assert t.grad == exact.full((2, 2), Rational(3, 4)), (
        "d(sum(t) * 3/4)/dt is %r, not the incoming 3/4 handed to every cell: "
        "a local backward that ignores its gradient, or that divides by the "
        "cell count, lands elsewhere" % (t.grad,))

    t = node((2, 3, 4))
    first = s.sum_to_scalar(t)
    second = s.sum_to_scalar(t)
    both = s1.add(first, second)
    assert s.backward(both) is None, "backward returned something"
    assert first.grad == exact.ones(()) and second.grad == exact.ones(()), (
        "the two sum nodes' grads are %r and %r, not the seed one each"
        % (first.grad, second.grad))
    assert t.grad == exact.full((3,), 2), (
        "two sums over one operand owe it %r, not %r: the second path "
        "accumulates into what the first left, it does not replace it"
        % (exact.full((3,), 2), t.grad))
    assert s.backward(both) is None, "backward returned something"
    assert t.grad == exact.full((3,), 4), (
        "the second backward left the operand at %r, not 4 ones: a call "
        "computes its own gradient and the fields double" % (t.grad,))

    t = node((2, -3))
    square = s1.mul(t, t)
    loss = s.sum_to_scalar(square)
    assert loss.value == exact.from_nested(13), (
        "sum(x * x) is %r, not 13" % (loss.value,))
    assert s.backward(loss) is None, "backward returned something"
    assert square.grad == exact.ones((2,)) and loss.grad == exact.ones(()), (
        "the walk from the sum left square.grad %r and loss.grad %r, not the "
        "seed one each" % (square.grad, loss.grad))
    assert t.grad == exact.from_nested((4, -6)), (
        "d(sum(x * x))/dx is %r, not 2x = (4, -6): the sum node is the way a "
        "non-scalar output becomes a scalar the caller can walk from"
        % (t.grad,))

    t = node((1, 1))
    once = s.sum_to_scalar(t)
    twice = s.sum_to_scalar(once)
    assert twice.value == exact.from_nested(2) and twice.value.shape == (), (
        "sum of a sum is %r of shape %r, not the scalar 2"
        % (twice.value, twice.value.shape))
    assert twice.parents == (once,), (
        "the second sum's parent is %r, not the first sum node" % (twice.parents,))
    assert s.backward(twice) is None, "backward returned something"
    assert once.grad == exact.ones(()) and t.grad == exact.ones((2,)), (
        "the nested sums left %r and %r, not the ones of each node's shape"
        % (once.grad, t.grad))

    operand = node(((3,),))
    made = s.sum_to_scalar(operand)
    assert made is not operand, (
        "sum_to_scalar handed back the node it was given: a single-cell "
        "operand still needs the sum node, or the graph loses the edge")
    assert made.value == exact.from_nested(3) and made.value.shape == (), (
        "sum_to_scalar of a (1, 1) operand is %r of shape %r, not the rank-0 3"
        % (made.value, made.value.shape))
    assert made.parents == (operand,), (
        "sum_to_scalar's parents are %r, not the (1, 1) operand"
        % (made.parents,))
    assert s.backward(made) is None, "backward returned something"
    assert operand.grad.shape == (1, 1), (
        "the (1, 1) operand's gradient has shape %r, not its own shape"
        % (operand.grad.shape,))
    assert operand.grad == exact.ones((1, 1)), (
        "the (1, 1) operand's gradient is %r, not the ones of its own shape"
        % (operand.grad,))

    empty = s1.Node(exact.zeros((0,)))
    made = s.sum_to_scalar(empty)
    assert made.value == exact.zeros(()), (
        "the sum of nothing is %r, not the rank-0 zero" % (made.value,))
    assert s.backward(made) is None, "backward returned something"
    assert empty.grad == exact.zeros((0,)) and empty.grad.shape == (0,), (
        "the empty operand's gradient is %r of shape %r, not the zeros of its "
        "own (0,)" % (empty.grad, empty.grad.shape))

    message = _refuses(exact.AutogradError,
                       "a sum_to_scalar of something that is not a Node",
                       lambda: s.sum_to_scalar(exact.from_nested((1, 2))))
    assert "sum_to_scalar" in message and "Tensor" in message, (
        "the refusal of a sum_to_scalar of a tensor does not name the "
        "offender: %r" % (message,))
    message = _refuses(exact.AutogradError, "a sum_to_scalar of an int",
                       lambda: s.sum_to_scalar(7))
    assert "7" in message, (
        "the refusal of a sum_to_scalar of 7 does not name it: %r" % (message,))

    print("check_06: the seed of a non-scalar output — a non-scalar root "
          "demands an explicit seed whose shape is the root's exactly (a "
          "scalar root of any shape keeps the ones of its own), the walk is "
          "stage 1's with the seed handed to it, and sum_to_scalar is the "
          "node a caller writes to turn a non-scalar output into a scalar")

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    class _Boom(Exception):
        """The call's own failure, which a region must not touch."""

    import exact
    import stage_01 as engine
    import stage_07 as s

    Rational = exact.Rational
    Node = engine.Node

    def node(nested):
        """A leaf of the course's container, holding the tensor `nested` describes."""
        return Node(exact.from_nested(nested))

    def cells(value):
        return tuple(value.cells)

    # ---- detach: a new leaf that owns no history ---------------------------

    x = node((2, 3))
    detached = s.detach(x)
    assert isinstance(detached, Node), (
        "detach returned %r, which is not a Node of the course's container"
        % (detached,))
    assert detached is not x, (
        "detach returned the node it was given: a later backward would reach "
        "straight through it")
    assert not (detached == x) and detached != x, (
        "a detached node compares equal to the node it was taken from "
        "(`__eq__` is identity), so the walk cannot tell them apart")
    assert len({detached, x}) == 2, (
        "{detached, x} has %d members, not two: they are two nodes"
        % (len({detached, x}),))
    assert detached.value == x.value, (
        "the detached node's value is %r, not the tensor it was detached from, "
        "%r: detach carries the value" % (detached.value, x.value))
    assert detached.value.shape == x.value.shape, (
        "the detached node's value has shape %r, not the original's %r"
        % (detached.value.shape, x.value.shape))
    assert cells(detached.value) == cells(x.value), (
        "the detached node's value has the cells %r, not the original's %r"
        % (cells(detached.value), cells(x.value)))
    assert all(isinstance(cell, Rational) for cell in detached.value.cells), (
        "a detached value's cell is not an exact.Rational: %r"
        % (detached.value.cells,))

    assert detached.parents == () and isinstance(detached.parents, tuple), (
        "the detached node's parents are %r, not the empty tuple: a detach that "
        "keeps the parents is a detach a backward reaches through"
        % (detached.parents,))
    assert detached.backward is None, (
        "the detached node carries a local backward (%r): its gradient would be "
        "handed straight back to the graph above the node it was detached from"
        % (detached.backward,))
    assert detached.requires_grad is False, (
        "the detached node's requires_grad is %r, not False: a detached node "
        "takes no gradient, and a backward of it must refuse"
        % (detached.requires_grad,))
    assert detached.grad == exact.zeros((2,)), (
        "the detached node's grad is %r, not the zeros of its value's shape: a "
        "detach must not carry the original's accumulated gradient along"
        % (detached.grad,))
    assert detached.grad.shape == (2,), (
        "the detached node's grad has shape %r, not the value's (2,)"
        % (detached.grad.shape,))
    assert detached.grad is not x.grad, (
        "the detached node's grad is the original's grad object, so a backward "
        "through the copy would write the node it was detached from")

    assert x.parents == () and x.requires_grad is True and x.grad == exact.zeros((2,)), (
        "a detach changed the node it was taken from: parents %r, requires_grad "
        "%r, grad %r" % (x.parents, x.requires_grad, x.grad))

    wide = node(((1, 2, 3), (4, 5, 6)))
    wide_detached = s.detach(wide)
    assert wide_detached.value.shape == (2, 3) and wide_detached.grad.shape == (2, 3), (
        "a detach of a (2, 3) node has value shape %r and grad shape %r, not "
        "(2, 3) and (2, 3): a gradient owes its operand its shape"
        % (wide_detached.value.shape, wide_detached.grad.shape))
    assert wide_detached.value == wide.value, (
        "a detach of a (2, 3) node has the value %r, not %r"
        % (wide_detached.value, wide.value))

    message = _refuses(exact.AutogradError, "a detach of an int",
                       lambda: s.detach(3))
    assert "detach" in message and "3" in message and "Node" in message, (
        "the refusal of detaching an int does not name the offender, the call "
        "and the container: %r" % (message,))
    message = _refuses(exact.AutogradError, "a detach of a Tensor",
                       lambda: s.detach(x.value))
    assert "detach" in message and "Node" in message, (
        "the refusal of detaching a bare Tensor does not name the call and what "
        "a detach needs: %r" % (message,))
    message = _refuses(exact.AutogradError, "a detach of None",
                       lambda: s.detach(None))
    assert "detach" in message and "None" in message, (
        "the refusal of detaching None does not name the call and the offender: "
        "%r" % (message,))

    message = _refuses(exact.AutogradError, "a backward from a detached node",
                       lambda: engine.backward(detached))
    assert "requires_grad" in message, (
        "a backward from a detached node does not refuse it: %r" % (message,))

    # ---- detach inside a graph: the forward and the cut --------------------

    cut_leaf = node((2, 3))
    above = node((4, 5))
    cut = s.detach(cut_leaf)
    square = engine.mul(above, above)
    out = engine.add(square, cut)
    assert out.value == exact.add(exact.mul(above.value, above.value), cut_leaf.value), (
        "add(mul(w, w), detach(x)) is %r, not %r: a detached node is a value "
        "like any other in the forward"
        % (out.value, exact.add(exact.mul(above.value, above.value), cut_leaf.value)))
    assert cells(out.value) == cells(
            exact.add(exact.mul(above.value, above.value), cut_leaf.value)), (
        "add(mul(w, w), detach(x)) has the cells %r, not exact's %r"
        % (cells(out.value),
           cells(exact.add(exact.mul(above.value, above.value), cut_leaf.value))))
    assert len(out.parents) == 2 and out.parents[0] is square, (
        "add(mul(w, w), detach(x)) has parents %r, not the product node and the "
        "detached node" % (out.parents,))
    assert out.parents[1] is cut and out.parents[1] is not cut_leaf, (
        "the add's second parent is %r: a detach must hand the graph its own "
        "copy, not the node it was detached from" % (out.parents[1],))
    assert out.parents[1].parents == () and out.parents[1].backward is None, (
        "the detached branch of the graph has parents %r and a backward: the "
        "walk would carry a gradient through it"
        % (out.parents[1].parents,))

    cut_leaf.grad = exact.from_nested((9, 9))
    assert engine.backward(out) is None, "backward returned something"
    assert cut_leaf.grad == exact.from_nested((9, 9)), (
        "a backward through a detached branch left the upstream grad at %r, not "
        "the (9, 9) it held before the call: detaching leaves it unchanged — not "
        "zero, not doubled" % (cut_leaf.grad,))
    assert square.grad == exact.ones((2,)), (
        "the branch above the detach got %r, not the seed one: only the "
        "detached path is cut" % (square.grad,))
    assert above.grad == exact.mul(exact.ones((2,)), exact.add(above.value, above.value)), (
        "the branch above the detach got %r at its leaf, not 2w" % (above.grad,))

    left_leaf = node((4, 5))
    left_above = node((-2, 3))
    left_cut = s.detach(left_leaf)
    left_square = engine.mul(left_above, left_above)
    left_out = engine.add(left_cut, left_square)
    left_leaf.grad = exact.from_nested((-1, 7))
    assert engine.backward(left_out) is None, "backward returned something"
    assert left_leaf.grad == exact.from_nested((-1, 7)), (
        "a backward through a detach on the left of an add left the upstream "
        "grad at %r, not (-1, 7)" % (left_leaf.grad,))
    assert left_square.grad == exact.ones((2,)), (
        "the branch above the left-hand detach got %r, not the seed one"
        % (left_square.grad,))

    z = node((3, 6))
    w = node((5, 7))
    middle = engine.mul(z, z)
    tail = engine.mul(s.detach(middle), w)
    assert tail.value == exact.mul(middle.value, w.value), (
        "mul(detach(mul(z, z)), w) is %r, not %r"
        % (tail.value, exact.mul(middle.value, w.value)))
    assert engine.backward(tail) is None, "backward returned something"
    assert w.grad == middle.value, (
        "d(tail)/dw is %r, not detach(middle)'s value %r: the detach cuts the "
        "graph below it and not the derivative above it"
        % (w.grad, middle.value))
    assert middle.grad == exact.zeros((2,)) and z.grad == exact.zeros((2,)), (
        "a backward through a detach in the middle of a chain left the middle "
        "node at %r and the leaf at %r, not the zeros they held: the gradient "
        "reached through the detach" % (middle.grad, z.grad))

    middle = engine.mul(z, z)
    tail = engine.mul(s.detach(middle), w)
    middle.grad = exact.from_nested((2, 4))
    z.grad = exact.from_nested((8, 8))
    assert engine.backward(tail) is None, "backward returned something"
    assert middle.grad == exact.from_nested((2, 4)), (
        "a second backward through the detach left the middle node at %r, not "
        "the (2, 4) it held: the detached path adds nothing to it" % (middle.grad,))
    assert z.grad == exact.from_nested((8, 8)), (
        "a second backward through the detach left the leaf at %r, not (8, 8)"
        % (z.grad,))

    twice = s.detach(s.detach(x))
    assert twice.parents == () and twice.requires_grad is False, (
        "detach(detach(x)) has parents %r and requires_grad %r"
        % (twice.parents, twice.requires_grad))
    assert twice.value == x.value, (
        "detach(detach(x)) has the value %r, not x's %r" % (twice.value, x.value))
    again = s.detach(x)
    assert again is not detached and not (again == detached), (
        "two detaches of the same value are the same node: each call makes its "
        "own leaf")
    assert again.value == detached.value, (
        "two detaches of the same value have the values %r and %r"
        % (again.value, detached.value))

    # ---- no_grad: the return value, and the leaf the call is handed --------

    marker = exact.from_nested((11, 12))
    assert s.no_grad(lambda t: t, marker) is marker, (
        "no_grad did not pass a non-Node argument through: it returned %r"
        % (s.no_grad(lambda t: t, marker),))
    assert s.no_grad(lambda: 41) == 41, (
        "no_grad(lambda: 41) is not 41: the wrapped call's return value comes "
        "back untouched")
    assert s.no_grad(lambda **kw: kw["k"], k=7) == 7, (
        "no_grad did not pass its keywords through to the wrapped call")

    p = node((2, 3))
    built = []

    def build(a):
        made = engine.add(a, a)
        built.append(made)
        return made

    result = s.no_grad(build, p)
    assert result is built[0], (
        "no_grad returned %r, not the node the wrapped call built: the return "
        "value must not be wrapped (or detached) on the way out" % (result,))
    assert result.value == exact.add(p.value, p.value), (
        "the node built inside the region is %r, not add(x, x) of the argument"
        % (result.value,))
    assert result.parents[0] is not p, (
        "the node the region built takes the argument itself as a parent: the "
        "graph inside the region is attached to a node that existed before the "
        "call")
    assert result.parents[0].parents == (), (
        "the leaf the region handed out has parents %r, not the empty tuple: a "
        "region must hand the call a detached leaf"
        % (result.parents[0].parents,))
    assert result.parents[0].requires_grad is False, (
        "the leaf the region handed out has requires_grad %r, not False"
        % (result.parents[0].requires_grad,))
    assert result.parents[0].value == p.value, (
        "the leaf the region handed out carries %r, not the argument's value %r"
        % (result.parents[0].value, p.value))
    assert result.parents[0].grad.shape == p.value.shape, (
        "the leaf the region handed out has grad shape %r, not the argument's %r"
        % (result.parents[0].grad.shape, p.value.shape))

    seen = []

    def look(a, plain, need=0):
        seen.append((a is p, a.parents, a.requires_grad, a.value == p.value,
                     plain is marker, need, p.requires_grad))
        return a.value

    value = s.no_grad(look, p, marker, need=3)
    assert value == p.value, (
        "the wrapped call's return value is %r, not the tensor it returned"
        % (value,))
    assert len(seen) == 1, (
        "the wrapped call ran %d times, not once" % (len(seen),))
    is_p, parents, wants, same, plain_same, need, frozen = seen[0]
    assert is_p is False, (
        "the call was handed the argument itself instead of its detached copy")
    assert parents == (), (
        "the leaf the call was handed has parents %r, not the empty tuple"
        % (parents,))
    assert wants is False, (
        "the leaf the call was handed has requires_grad %r, not False"
        % (wants,))
    assert same is True, (
        "the leaf the call was handed does not carry the argument's value")
    assert plain_same is True, (
        "a non-Node argument was not passed through untouched")
    assert need == 3, "the keyword argument did not reach the wrapped call"
    assert frozen is False, (
        "inside the region the argument itself still has requires_grad True: "
        "the region freezes the nodes it was handed")

    # ---- no_grad: the region's state, and its exact restoration ------------

    q = node((3, 4))
    other = node((5, 6))
    beside = engine.mul(q, q)

    def probe_inside(a):
        state = {}
        state["argument"] = a.requires_grad
        state["original"] = q.requires_grad
        state["above"] = beside.requires_grad
        state["unrelated"] = other.requires_grad
        state["refusal"] = _refuses(
            exact.AutogradError, "a backward of a frozen node inside the region",
            lambda: engine.backward(q))
        z = engine.add(a, a)
        engine.backward(z)
        state["q_grad"] = q.grad
        state["q_parents"] = q.parents
        return state

    q.grad = exact.from_nested((5, 5))
    state = s.no_grad(probe_inside, q)
    assert state["argument"] is False, (
        "inside the region the leaf handed to the call wants a gradient")
    assert state["original"] is False, (
        "inside the region the argument itself still wants a gradient: the "
        "engine would seed it")
    assert "requires_grad" in state["refusal"], (
        "a backward of a frozen node inside the region did not refuse it: %r"
        % (state["refusal"],))
    assert state["above"] is True, (
        "the region froze a node above the node it was handed: the nodes above "
        "an argument are not the region's to freeze")
    assert state["unrelated"] is True, (
        "the region froze a node in another graph: only the nodes it was handed "
        "are frozen")
    assert state["q_grad"] == exact.from_nested((5, 5)), (
        "a backward inside the region left the frozen node's grad at %r, not "
        "the (5, 5) it held before the call: the region's own scratch must not "
        "be the frozen node's gradient" % (state["q_grad"],))
    assert state["q_parents"] == (), (
        "the region changed the frozen node's parents: %r" % (state["q_parents"],))

    assert q.grad == exact.from_nested((5, 5)), (
        "the region itself wrote the frozen node's grad: it is %r, not the "
        "(5, 5) it held before the call" % (q.grad,))
    assert q.requires_grad is True and beside.requires_grad is True, (
        "after the region the argument's requires_grad is %r (and the node "
        "above it %r), not the True it had before the call"
        % (q.requires_grad, beside.requires_grad))
    engine.zero_grad(q)
    assert engine.backward(q) is None, (
        "backward returned something after the region: the frozen state leaked")
    assert q.grad == exact.ones((2,)), (
        "after the region a backward of the argument left %r, not the seed one: "
        "the state must be restored exactly" % (q.grad,))
    engine.zero_grad(q)

    deep_leaf = node((2, 2))
    deep = engine.mul(deep_leaf, deep_leaf)
    above_seen = []

    def look_above(a):
        above_seen.append((a.requires_grad, a.parents, a is deep,
                           a.value == deep.value, deep.requires_grad,
                           deep_leaf.requires_grad))
        return a.value

    assert s.no_grad(look_above, deep) == deep.value, (
        "the call's return value is not the tensor it returned")
    assert len(above_seen) == 1, "the wrapped call ran %d times" % (len(above_seen),)
    handed_wants, handed_parents, handed_is, handed_value, mid, low = above_seen[0]
    assert handed_wants is False and handed_is is False and handed_value is True, (
        "the leaf handed to the call inside the region is (requires_grad %r, "
        "is the argument %r, same value %r)"
        % (handed_wants, handed_is, handed_value))
    assert handed_parents == (), (
        "the leaf handed to the call for an argument that has parents has "
        "parents %r, not the empty tuple: the region must hand out a detached "
        "leaf, not a copy that keeps the graph" % (handed_parents,))
    assert mid is False, (
        "inside the region the argument itself still wants a gradient")
    assert low is True, (
        "the region froze a node above the node it was handed")
    assert deep.requires_grad is True and deep_leaf.requires_grad is True, (
        "after the region requires_grad is %r and %r, not True and True"
        % (deep.requires_grad, deep_leaf.requires_grad))

    r = node((1, 2))

    def hands_r_back(a):
        return a is not r and a.value == r.value

    assert s.no_grad(hands_r_back, r) is True, (
        "the region did not hand the call a copy of the argument")
    assert r.requires_grad is True, (
        "after the region the argument's requires_grad is %r, not True"
        % (r.requires_grad,))

    frozen_arg = node((3, 3))
    frozen_arg.requires_grad = False
    frozen_seen = []

    def look_at_frozen(a):
        frozen_seen.append((a is frozen_arg, a.parents, a.requires_grad,
                            a.value == frozen_arg.value))
        z = engine.add(a, a)
        engine.backward(z)
        return frozen_arg.grad

    handed_back = s.no_grad(look_at_frozen, frozen_arg)
    assert handed_back == exact.zeros((2,)), (
        "a backward inside the region left the frozen argument's grad at %r, "
        "not the zeros it held: a node that already takes no gradient is still "
        "not the node the region hands out" % (handed_back,))
    assert len(frozen_seen) == 1, (
        "the wrapped call ran %d times, not once" % (len(frozen_seen),))
    for is_arg, parents, wants, same in frozen_seen:
        assert is_arg is False, (
            "the region handed the call a node that already had "
            "requires_grad=False instead of its copy: a backward inside the "
            "call writes the frozen node's grad")
        assert parents == () and wants is False and same is True, (
            "the leaf handed to the call is (parents %r, requires_grad %r, same "
            "value %r)" % (parents, wants, same))
    assert frozen_arg.requires_grad is False, (
        "after the region a node that already took no gradient wants one: %r"
        % (frozen_arg.requires_grad,))
    assert frozen_arg.grad == exact.zeros((2,)), (
        "the region left the frozen argument's grad at %r, not the zeros it "
        "held" % (frozen_arg.grad,))

    s.no_grad(lambda a, b: None, r, r)
    assert r.requires_grad is True, (
        "a node handed to the region twice came back frozen: the snapshots are "
        "put back in reverse of the order they were taken")
    s.no_grad(lambda a, b: None, r, other)
    assert r.requires_grad is True and other.requires_grad is True, (
        "a region over two nodes left requires_grad %r and %r, not True and True"
        % (r.requires_grad, other.requires_grad))

    # ---- no_grad: an exception out, and the state restored anyway ----------

    boom = _Boom("the call failed")

    def raising(a):
        raise boom

    raised = None
    try:
        s.no_grad(raising, r)
    except _Boom as caught:
        raised = caught
    assert raised is boom, (
        "no_grad did not let the wrapped call's exception out unchanged: %r"
        % (raised,))
    assert r.requires_grad is True, (
        "a region whose call raised left the argument at requires_grad %r, not "
        "True: the state must be restored on the failure path too"
        % (r.requires_grad,))
    assert engine.backward(r) is None, (
        "backward returned something after a region that raised: the state "
        "leaked into the next call")
    engine.zero_grad(r)

    def raising_inside(a):
        try:
            s.no_grad(raising, r)
        except _Boom:
            pass
        return r.requires_grad, a.requires_grad

    inner = s.no_grad(raising_inside, r)
    assert inner == (False, False), (
        "after a nested region whose call raised, the node the outer region "
        "froze has requires_grad %r and the leaf handed to the call %r, not "
        "(False, False): the inner region put back what it found, and the outer "
        "one is still in force" % (inner,))
    assert r.requires_grad is True, (
        "after the outer region the argument is still frozen: %r"
        % (r.requires_grad,))

    def nested(a):
        inner = s.no_grad(lambda b: b.requires_grad, r)
        return inner, r.requires_grad, a.requires_grad

    state = s.no_grad(nested, r)
    assert state == (False, False, False), (
        "a nested region that returned normally left the outer region's state "
        "at %r: the inner region restores what it found (False), not a fixed "
        "True" % (state,))
    assert r.requires_grad is True, (
        "after both regions the argument is still frozen: %r" % (r.requires_grad,))
    assert engine.backward(r) is None, "backward returned something"
    engine.zero_grad(r)

    message = _refuses(exact.AutogradError, "a no_grad whose call is not callable",
                       lambda: s.no_grad(3, r))
    assert "no_grad" in message and "3" in message and "callable" in message, (
        "the refusal of a no_grad over an int does not name the call, the "
        "offender and what it must be: %r" % (message,))
    message = _refuses(exact.AutogradError, "a no_grad over None",
                       lambda: s.no_grad(None))
    assert "no_grad" in message and "None" in message, (
        "the refusal of a no_grad over None does not name the call and the "
        "offender: %r" % (message,))

    # ---- the region does not touch what it was not given -------------------

    u = node((7, 8))
    v = node((-1, 1))
    untouched = engine.mul(v, v)
    untouched.grad = exact.from_nested((6, 6))
    v.grad = exact.from_nested((2, 2))

    def run_beside(a):
        z = engine.mul(a, a)
        engine.backward(z)
        return z.value

    assert s.no_grad(run_beside, u).shape == (2,), (
        "the wrapped call's return value is not the tensor it built")
    assert untouched.grad == exact.from_nested((6, 6)), (
        "a region over one graph left another graph's grad at %r, not (6, 6)"
        % (untouched.grad,))
    assert v.grad == exact.from_nested((2, 2)), (
        "a region left another graph's leaf at %r, not (2, 2)" % (v.grad,))
    assert u.grad == exact.zeros((2,)), (
        "the argument of the region accumulated %r, not the zeros it held"
        % (u.grad,))
    assert u.requires_grad is True and v.requires_grad is True, (
        "the region left requires_grad at %r and %r, not True and True"
        % (u.requires_grad, v.requires_grad))
    assert v.parents == () and untouched.parents == (v, v), (
        "the region changed a graph it was not handed: %r and %r"
        % (v.parents, untouched.parents))

    shape = node(((1, 2), (3, 4)))

    def scalar_of(a):
        return engine.add(a, a)

    biased = s.no_grad(scalar_of, shape)
    assert biased.value == exact.add(shape.value, shape.value), (
        "the node the region built is %r, not add(x, x) of the argument"
        % (biased.value,))
    assert biased.value.shape == (2, 2), (
        "the node the region built has shape %r, not the argument's (2, 2)"
        % (biased.value.shape,))
    assert all(isinstance(cell, Rational) for cell in biased.value.cells), (
        "a value built inside the region is not made of exact.Rationals: %r"
        % (biased.value.cells,))

    print("check_07: detach cuts the graph — a new leaf with the value, no "
          "parents, no local backward and no gradient input, so a backward "
          "through it leaves the upstream exactly as it was — and no_grad is a "
          "region that hands the call detached leaves and freezes its "
          "arguments, restores them in a finally (in reverse, so a repeated "
          "node comes back), passes the return value through untouched and "
          "lets the call's exception out")

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import exact
    import stage_01 as stage1
    import stage_08 as s

    Rational = exact.Rational

    def node(nested):
        """A stage-1 leaf holding the `exact.Tensor` `nested` describes."""
        return s.Node(exact.from_nested(nested))

    def shaped(values):
        """A `Tensor` from a nested tuple or a bare cell, plus its shape."""
        tensor = exact.from_nested(values)
        return tensor, tensor.shape

    # ---- the graph is stage 1's -------------------------------------------

    assert s.Node is stage1.Node, (
        "stage 8's Node is %r, not stage 1's: the gradients these three "
        "operations leave on their operands must be the ones stage 1's "
        "`backward` walks and stage 1's `zero_grad` clears" % (s.Node,))

    leaf = node((2, 3))
    assert set(vars(leaf)) == {"value", "parents", "backward", "requires_grad",
                               "grad"}, (
        "a Node's fields are %r, not the frozen (value, parents, backward, "
        "requires_grad, grad)" % (sorted(vars(leaf)),))
    assert leaf.grad == exact.zeros((2,)) and leaf.grad.shape == (2,), (
        "a Node's grad starts %r, not the zeros of its value's shape"
        % (leaf.grad,))
    assert leaf.backward is None and leaf.parents == (), (
        "a leaf has parents %r and backward %r, not the empty tuple and None"
        % (leaf.parents, leaf.backward))

    # ---- the three forwards are exact's, element for element --------------

    CASES = (
        (3, -4),
        ((0,), (0,)),
        ((1, 2, 3), (-4, 5, -6)),
        (Rational(1, 2), Rational(-3, 4)),
        ((Rational(1, 2), Rational(-3, 4)), (Rational(1, 3), Rational(-3, 4))),
        (((1, 2), (3, 4)), ((5, 6), (7, 8))),
        (((0, 0), (-1, 1)), ((0, 0), (2, -2))),
        (((Rational(1, 3), Rational(-2, 5)), (Rational(0), Rational(7, 2))),
         ((Rational(1, 3), Rational(2, 5)), (Rational(-4), Rational(1, 2)))),
    )

    for left, right in CASES:
        x = node(left)
        y = node(right)
        shape = x.value.shape
        assert y.value.shape == shape, (
            "the check's fixture is ragged: %r against %r" % (shape, y.value.shape))
        for name, build, forward in (("max", s.max, exact.max),
                                     ("relu", s.relu, exact.relu),
                                     ("abs", s.abs, exact.abs)):
            if name == "max":
                made = build(x, y)
                want = forward(x.value, y.value)
                parents = (x, y)
            else:
                made = build(x)
                want = forward(x.value)
                parents = (x,)
            assert made.value == want, (
                "%s's value is %r, not exact.%s's %r: the forward is the "
                "provided algebra, element for element"
                % (name, made.value, name, want))
            assert made.value.cells == want.cells, (
                "%s's value has the cells %r, not exact.%s's %r"
                % (name, made.value.cells, name, want.cells))
            assert made.value.shape == shape, (
                "%s's value has shape %r, not the operand's %r"
                % (name, made.value.shape, shape))
            assert made.parents == parents, (
                "%s's parents are %r, not the operands in the order they were "
                "passed" % (name, made.parents))
            assert made.backward is not None and callable(made.backward), (
                "%s's node carries %r, not a local backward: no gradient can "
                "leave it" % (name, made.backward))
            assert made.grad == exact.zeros(shape) and made.grad.shape == shape, (
                "%s's node starts with grad %r, not the zeros of the value's "
                "shape" % (name, made.grad))
            assert x.grad == exact.zeros(shape) and y.grad == exact.zeros(shape), (
                "building %s touched an operand's grad: %r and %r"
                % (name, x.grad, y.grad))

    # ---- the tie: the left operand, once per shape ------------------------

    TIE_CASES = (
        (-2,),                       # a scalar, and negative
        ((0,), (5,)),
        ((0, 1), (0, -1)),
        0,
        ((1, 2, 3), (4, 5, 6)),
        (Rational(1, 2), -Rational(3, 4)),
        ((0, 0, 0), (0, 0, 0)),
    )

    for values in TIE_CASES:
        _, shape = shaped(values)
        x = node(values)
        y = node(values)
        made = s.max(x, y)
        assert made.value == x.value, (
            "max of a tensor and itself is %r, not the tensor: the value of a "
            "tie is the operands' shared value" % (made.value,))
        seed = exact.full(shape, Rational(3))
        assert made.backward(seed) is None, (
            "a local backward returned something instead of leaving the grads "
            "on the operands")
        assert x.grad == seed, (
            "on a tie the gradient must go to the LEFT operand of the call: "
            "the left operand's grad is %r, not the seed %r"
            % (x.grad, seed))
        assert y.grad == exact.zeros(shape), (
            "on a tie the RIGHT operand must receive nothing, not half and not "
            "all: its grad is %r, not the zeros" % (y.grad,))
        assert x.grad.shape == shape and y.grad.shape == shape, (
            "the tie's gradients have shapes %r and %r, not the operands' %r"
            % (x.grad.shape, y.grad.shape, shape))

        # the same tie, with the operands the other way round: the rule is the
        # call's operand order, and on a tie no test of the values can prefer
        # either side.
        x2 = node(values)
        y2 = node(values)
        other = s.max(y2, x2)
        assert other.backward(seed) is None, "a local backward returned something"
        assert y2.grad == seed and x2.grad == exact.zeros(shape), (
            "a tie must follow the call's operand order: max(x, y) put the "
            "gradient on x, and this call left its left operand at %r and its "
            "right one at %r" % (y2.grad, x2.grad))

        # the same node on both sides is a tie too, and it is one contribution
        # (the left operand's), not two.
        z = node(values)
        twice = s.max(z, z)
        assert twice.backward(seed) is None, "a local backward returned something"
        assert z.grad == seed, (
            "max(z, z) left z.grad at %r, not the seed %r: a node that is both "
            "operands keeps the left side's share, and the right side's zeros"
            % (z.grad, seed))

    # ---- a tie and a non-tie in the same vector ---------------------------

    x = node((0, 2, -3, Rational(1, 2), 0))
    y = node((0, 5, -3, Rational(1, 3), 1))
    made = s.max(x, y)
    assert made.value == exact.from_nested((0, 5, -3, Rational(1, 2), 1)), (
        "max of a mixed vector is %r, not the elementwise maxima" % (made.value,))
    seed = exact.from_nested((7, 6, 3, Rational(3, 2), -1))
    assert made.backward(seed) is None, "a local backward returned something"
    assert x.grad == exact.from_nested((7, 0, 3, Rational(3, 2), 0)), (
        "the left operand keeps the gradient exactly where its value is >= the "
        "right one's — a tie at 0 and at -3 inclusive — and its grad is %r, not "
        "(7, 0, 3, 3/2, 0): a factor read from the gradient (6 at index 1) or "
        "from the node's own value would keep a different set" % (x.grad,))
    assert y.grad == exact.from_nested((0, 6, 0, 0, -1)), (
        "the right operand keeps the gradient exactly where its value is "
        "strictly greater — never at a tie — and its grad is %r, not "
        "(0, 6, 0, 0, -1)" % (y.grad,))

    # ---- a non-tie: the loser keeps nothing, and it is not the left one ---

    x = node((1, 9, -2))
    y = node((4, 9, 0))
    made = s.max(x, y)
    assert made.backward(exact.from_nested((2, 3, 5))) is None, (
        "a local backward returned something")
    assert x.grad == exact.from_nested((0, 3, 0)), (
        "the left operand keeps nothing where it lost — index 0 and index 2 — "
        "and the whole gradient at the tie in index 1: its grad is %r, not "
        "(0, 3, 0)" % (x.grad,))
    assert y.grad == exact.from_nested((2, 0, 5)), (
        "the right operand keeps the gradient where it won (2 and 5) and "
        "nothing at the tie: its grad is %r, not (2, 0, 5)" % (y.grad,))

    # ---- a broadcast operand owes its own shape ---------------------------

    a = node(((1, 2, 3), (4, 5, 6)))
    b = node((7, 5, 0))
    made = s.max(a, b)
    assert made.value == exact.max(a.value, b.value), (
        "max of a (2, 3) and a (3,) is %r, not exact.max's broadcast"
        % (made.value,))
    assert made.value.shape == (2, 3), (
        "max of a (2, 3) and a (3,) has shape %r, not the broadcast (2, 3)"
        % (made.value.shape,))
    wide = exact.from_nested(((1, 2, 3), (4, 5, 6)))
    assert made.backward(wide) is None, "a local backward returned something"
    assert a.grad.shape == (2, 3), (
        "after a backward through a (2, 3) max the left operand's grad has "
        "shape %r, not its own (2, 3)" % (a.grad.shape,))
    assert a.grad == exact.from_nested(((0, 0, 3), (0, 5, 6))), (
        "the (2, 3) operand keeps the gradient where it is >= the broadcast "
        "right one: its grad is %r, not ((0, 0, 3), (0, 5, 6))" % (a.grad,))
    assert b.grad.shape == (3,), (
        "the (3,) operand was broadcast, so its gradient's shape is its own "
        "(3,), not %r: a masked gradient in the node's shape must go through "
        "exact.reduce_gradient" % (b.grad.shape,))
    assert b.grad == exact.from_nested((5, 2, 0)), (
        "the (3,) operand's gradient is its masked gradient summed over the "
        "two rows: %r, not (5, 2, 0)" % (b.grad,))

    # the same pair the other way round: this time the *left* operand is the
    # one the broadcast stretched.
    small = node((7, 5, 0))
    big = node(((1, 2, 3), (4, 5, 6)))
    made = s.max(small, big)
    assert made.backward(wide) is None, "a local backward returned something"
    assert small.grad.shape == (3,), (
        "the (3,) left operand's grad has shape %r, not its own (3,)"
        % (small.grad.shape,))
    assert small.grad == exact.from_nested((5, 7, 0)), (
        "the broadcast left operand's grad is %r, not (5, 7, 0): the masked "
        "gradient is summed back over the rows, whichever operand was "
        "stretched" % (small.grad,))
    assert big.grad == exact.from_nested(((0, 0, 3), (0, 0, 6))), (
        "the (2, 3) operand's grad is %r, not ((0, 0, 3), (0, 0, 6)): it keeps "
        "the gradient only where it is strictly greater, and the tie at index "
        "(1, 1) belongs to the left operand" % (big.grad,))

    # a scalar operand borrows the whole tensor's shape and owes the scalar one
    a = node(((1, 2), (3, 4)))
    b = node(2)
    made = s.max(a, b)
    assert made.value == exact.max(a.value, b.value) and made.value.shape == (2, 2)
    assert made.backward(exact.ones((2, 2))) is None, (
        "a local backward returned something")
    assert a.grad == exact.from_nested(((0, 1), (1, 1))), (
        "against a scalar 2 the (2, 2) operand keeps the gradient where it is "
        ">= 2: its grad is %r, not ((0, 1), (1, 1))" % (a.grad,))
    assert b.grad.shape == (), (
        "the scalar operand's grad has shape %r, not its own (): the four "
        "cells it was stretched to must be summed" % (b.grad.shape,))
    assert b.grad == exact.from_nested(1), (
        "the scalar operand's grad is %r, not the one cell where 2 > x"
        % (b.grad,))

    # ---- accumulation: added, never assigned ------------------------------

    x = node((9, -3))
    y = node((5, 7))
    made = s.max(x, y)
    assert made.backward(exact.ones((2,))) is None, (
        "a local backward returned something")
    first_x, first_y = x.grad, y.grad
    assert first_x == exact.from_nested((1, 0)) and first_y == exact.from_nested((0, 1)), (
        "the fixture's first backward left x.grad %r and y.grad %r, not (1, 0) "
        "and (0, 1)" % (first_x, first_y))
    assert made.backward(exact.ones((2,))) is None, (
        "a local backward returned something")
    assert x.grad == exact.add(first_x, first_x), (
        "a second local backward must add to what the first left: x.grad is "
        "%r, not twice %r" % (x.grad, first_x))
    assert y.grad == exact.add(first_y, first_y), (
        "a second local backward must add to what the first left: y.grad is "
        "%r, not twice %r" % (y.grad, first_y))

    r = s.relu(node((2, -3)))
    assert r.backward(exact.ones((2,))) is None, "a local backward returned something"
    r.backward(exact.ones((2,)))
    assert r.parents[0].grad == exact.from_nested((2, 0)), (
        "a second local backward through relu left the operand at %r, not "
        "(2, 0) twice: the contribution is added, never assigned"
        % (r.parents[0].grad,))

    # ---- the walk is stage 1's, and it reaches the kink -------------------

    x = node((2, -3))
    y = node((5, 7))
    m = s.max(x, y)
    total = stage1.add(m, m)
    assert stage1.backward(total) is None, (
        "stage 1's backward returned something")
    assert m.grad == exact.from_nested((2, 2)), (
        "the node both paths of (m + m) run through has grad %r, not (2, 2): "
        "the two paths accumulate"
        % (m.grad,))
    assert x.grad == exact.from_nested((0, 0)), (
        "x lost every element of the max, so its grad is %r, not (0, 0)"
        % (x.grad,))
    assert y.grad == exact.from_nested((2, 2)), (
        "y won every element of the max, so (m + m)'s two paths left it %r, "
        "not (2, 2)" % (y.grad,))
    assert stage1.zero_grad(total) is None, "stage 1's zero_grad returned something"
    assert y.grad == exact.zeros((2,)) and x.grad == exact.zeros((2,)), (
        "zero_grad over the walk left %r and %r, not the zeros"
        % (x.grad, y.grad))

    x = node((2, -3))
    y = node((5, 7))
    r = s.relu(x)
    loss = stage1.add(stage1.mul(r, y), r)
    assert loss.value == exact.from_nested((12, 0)), (
        "relu(x) * y + relu(x) is %r, not (12, 0)" % (loss.value,))
    assert stage1.backward(loss) is None, "stage 1's backward returned something"
    assert r.grad == exact.from_nested((6, 8)), (
        "d(relu(x) * y + relu(x))/d(relu(x)) is y + 1 = (6, 8), not %r"
        % (r.grad,))
    assert x.grad == exact.from_nested((6, 0)), (
        "the chain's gradient back to x is (y + 1) * relu'(x) = (6, 0): a relu "
        "that passes the gradient through a negative input leaves %r"
        % (x.grad,))
    assert y.grad == exact.from_nested((2, 0)), (
        "d(loss)/dy is relu(x) + relu'(y)... relu(x) = (2, 0), not %r"
        % (y.grad,))

    # ---- relu: the kink, in several places and several spellings of 0 -----

    for zero in (Rational(0), -Rational(0), Rational(0, 7), Rational(0, -5),
                 Rational(4) - Rational(4), Rational(0) * Rational(9)):
        a = node(zero)
        made = s.relu(a)
        assert made.value == exact.from_nested(0), (
            "relu of %r is %r, not 0: exact.relu's kink gives 0" % (zero, made.value))
        for seed in (exact.from_nested(9), exact.from_nested(-9)):
            a.grad = exact.zeros(())
            assert made.backward(seed) is None, (
                "a local backward returned something")
            assert a.grad == exact.from_nested(0), (
                "relu'(0) is %r under the seed %r, not 0: the kink takes the "
                "gradient nowhere, and the same rule must hold for every "
                "spelling of the zero (relu(-0) included)" % (a.grad, seed))
        b = node(zero)
        modulus = s.abs(b)
        assert modulus.value == exact.from_nested(0), (
            "abs of %r is %r, not 0" % (zero, modulus.value))
        assert modulus.backward(exact.from_nested(9)) is None, (
            "a local backward returned something")
        assert b.grad == exact.from_nested(0), (
            "abs(0) left its operand at %r, not 0: abs's kink follows the same "
            "rule relu's does — neither +1 nor -1 nor half of either"
            % (b.grad,))
        left = node(zero)
        right = node(zero)
        tied = s.max(left, right)
        assert tied.backward(exact.from_nested(9)) is None, (
            "a local backward returned something")
        assert left.grad == exact.from_nested(9), (
            "a tie at 0 is a tie like any other: the left operand keeps it, "
            "and this one has %r" % (left.grad,))
        assert right.grad == exact.from_nested(0), (
            "a tie at 0 gives the right operand the zeros, and this one has %r"
            % (right.grad,))

    ZERO_SHAPES = ((0,), (0, 0), ((0, 0), (0, 0)), (-1, 0, 1))
    for values in ZERO_SHAPES:
        a = node(values)
        made = s.relu(a)
        seed = exact.full(made.value.shape, Rational(5))
        assert made.backward(seed) is None, "a local backward returned something"
        want = exact.Tensor(
            tuple(0 if cell <= 0 else 5 for cell in a.value.cells),
            a.value.shape)
        assert a.grad == want, (
            "relu'(x) is 1 for x > 0 and 0 for x <= 0, once per shape: over %r "
            "the gradient is %r, not %r" % (values, a.grad, want))
        assert a.grad.shape == a.value.shape, (
            "relu's gradient has shape %r, not its operand's %r"
            % (a.grad.shape, a.value.shape))

    x = node((3, -2, 0, Rational(1, 4)))
    made = s.relu(x)
    assert made.value == exact.from_nested((3, 0, 0, Rational(1, 4))), (
        "relu of (3, -2, 0, 1/4) is %r, not (3, 0, 0, 1/4)" % (made.value,))
    seed = exact.from_nested((2, 9, 5, Rational(-3, 2)))
    assert made.backward(seed) is None, "a local backward returned something"
    assert x.grad == exact.from_nested((2, 0, 0, Rational(-3, 2))), (
        "relu keeps the gradient where the operand is positive — sign included, "
        "so the negative seed cell survives — and nothing elsewhere: %r, not "
        "(2, 0, 0, -3/2)" % (x.grad,))

    message = _refuses(exact.AutogradError, "a relu of a Tensor instead of a Node",
                       lambda: s.relu(x.value))
    assert "Node" in message, (
        "the refusal of a relu operand that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "an abs of an int",
                       lambda: s.abs(7))
    assert "7" in message, (
        "the refusal of an abs operand that is not a Node does not name it: %r"
        % (message,))

    # ---- abs: the sign, and the kink --------------------------------------

    x = node((3, -2, 0, Rational(-1, 3)))
    made = s.abs(x)
    assert made.value == exact.from_nested((3, 2, 0, Rational(1, 3))), (
        "abs of (3, -2, 0, -1/3) is %r, not (3, 2, 0, 1/3)" % (made.value,))
    seed = exact.from_nested((2, 9, 5, Rational(-3, 2)))
    assert made.backward(seed) is None, "a local backward returned something"
    assert x.grad == exact.from_nested((2, -9, 0, Rational(3, 2))), (
        "d|a|/da is the operand's sign: +1 at 3, -1 at -2, 0 at 0 and -1 at "
        "-1/3 (so the gradient's sign flips): %r, not (2, -9, 0, 3/2)"
        % (x.grad,))
    assert x.grad.shape == (4,), (
        "abs's gradient has shape %r, not its operand's (4,)" % (x.grad.shape,))

    for value, want in ((5, Rational(4)), (-5, Rational(-4)),
                        (Rational(2, 7), Rational(4))):
        a = node(value)
        made = s.abs(a)
        assert made.value == exact.from_nested(value if value >= 0 else -value), (
            "abs of %r is %r, not its exact magnitude" % (value, made.value))
        assert made.backward(exact.from_nested(Rational(4))) is None, (
            "a local backward returned something")
        assert a.grad == exact.from_nested(want), (
            "a scalar abs at %r has grad %r, not %r" % (value, a.grad, want))

    for values in ((-1, -2, -3), (1, 2, 3), (-1, 0, 1), (0, 0, 0)):
        a = node(values)
        made = s.abs(a)
        seed = exact.ones(made.value.shape)
        assert made.backward(seed) is None, "a local backward returned something"
        want = tuple(1 if cell > 0 else (-1 if cell < 0 else 0)
                     for cell in a.value.cells)
        assert a.grad.cells == want, (
            "abs's factor over %r is %r, not %r: +1 right of 0, -1 left of it, "
            "0 at it" % (values, a.grad.cells, want))

    # ---- the gradient the local backward is handed ------------------------

    x = node((1, 2))
    y = node((3, 4))
    made = s.max(x, y)
    message = _refuses(exact.AutogradError,
                       "a local backward handed a gradient of the wrong shape",
                       lambda: made.backward(exact.ones((3,))))
    assert "(3,)" in message and "(2,)" in message, (
        "the refusal of a gradient of the wrong shape does not name both "
        "shapes: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a local backward handed a gradient of the wrong shape "
                       "but the right size",
                       lambda: made.backward(exact.ones((1, 2))))
    assert "(1, 2)" in message and "(2,)" in message, (
        "the refusal of a (1, 2) gradient for a (2,) node does not name both "
        "shapes: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a local backward handed something that is not a Tensor",
                       lambda: made.backward((1, 1)))
    assert "Tensor" in message, (
        "the refusal of a gradient that is not a Tensor does not name it: %r"
        % (message,))
    assert x.grad == exact.zeros((2,)) and y.grad == exact.zeros((2,)), (
        "a refused gradient still touched an operand's grad: %r and %r"
        % (x.grad, y.grad))

    r = s.relu(node((1, -2)))
    message = _refuses(exact.AutogradError,
                       "a relu handed a gradient of the wrong shape",
                       lambda: r.backward(exact.ones((4,))))
    assert "(4,)" in message and "(2,)" in message, (
        "the refusal of a relu gradient of the wrong shape does not name both "
        "shapes: %r" % (message,))

    # ---- the operands: a Node, and the shapes that broadcast --------------

    x = node((1, 2))
    message = _refuses(exact.AutogradError, "a max whose left operand is not a Node",
                       lambda: s.max(x.value, x))
    assert "Node" in message, (
        "the refusal of a left operand that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "a max whose right operand is not a Node",
                       lambda: s.max(x, 3))
    assert "3" in message, (
        "the refusal of a right operand that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.ExactError, "two shapes that do not broadcast",
                       lambda: s.max(node((1, 2, 3)), node((1, 2))))
    assert "(3,)" in message and "(2,)" in message, (
        "the refusal of two shapes that do not broadcast does not name both: %r"
        % (message,))

    # ---- every gradient is an exact Rational pair -------------------------

    for values in ((Rational(1, 3), Rational(-2, 5)), (-4, 0)):
        x = node(values)
        y = node((Rational(1, 7), Rational(1, 2)))
        made = s.max(x, y)
        made.backward(exact.full(x.value.shape, Rational(5, 3)))
        r = s.relu(x)
        r.backward(exact.full(x.value.shape, Rational(-5, 3)))
        m = s.abs(x)
        m.backward(exact.full(x.value.shape, Rational(7, 3)))
        cells = (x.grad.cells + y.grad.cells + r.parents[0].grad.cells
                 + m.parents[0].grad.cells)
        assert all(isinstance(cell, Rational) for cell in cells), (
            "a gradient cell is not an exact.Rational: %r" % (cells,))
        assert x.grad.shape == x.value.shape, (
            "max's gradient has shape %r, not its operand's %r"
            % (x.grad.shape, x.value.shape))

    print("check_08: the kink — max, relu and abs carry exact's forward element "
          "for element, the gradient of a tie goes to the left operand of the "
          "call (once per shape, at every kink of a vector, for relu(-0) and "
          "abs(0) alike), the factors are read from the operands' values, a "
          "broadcast operand's masked gradient is reduced back to its own "
          "shape, and every contribution accumulates into stage 1's Node")

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import exact
    import stage_01 as stage1
    import stage_09 as s

    Rational = exact.Rational

    def leaf(nested):
        """A stage-1 leaf holding the `exact.Tensor` `nested` describes: the
        point the oracle differentiates at, and the node its gradient is read
        off."""
        return stage1.Node(exact.from_nested(nested))

    def pair(cell):
        """A `Rational` as `numerator/denominator`, for reading a message."""
        return "%d/%d" % (cell.numerator, cell.denominator)

    def scalarize(node):
        """A scalar `Node` summing `node`'s cells — the reduction stage 3
        provides, written out here so this check needs only stage 1 and `exact`
        to build a scalar-valued fixture out of a vector one."""
        total = exact.sum(node.value)

        def backward(gradient):
            node.grad = exact.add(
                node.grad, exact.broadcast_to(gradient, node.value.shape))

        return stage1.Node(total, parents=(node,), backward=backward)

    def quadratic(t):
        """`f(t) = sum(3 t^2 + t + 5)`: degree two, so the central difference
        is exactly its derivative `6t + 1` for every step and every leaf."""
        three = stage1.Node(exact.full(t.value.shape, 3))
        five = stage1.Node(exact.full(t.value.shape, 5))
        square = stage1.mul(t, t)
        return scalarize(
            stage1.add(stage1.add(stage1.mul(square, three), t), five))

    def quadratic_gradient(value):
        """`6x + 1`, from `exact` alone: the derivative the fixture was built
        to have, so the oracle is not compared with the engine alone."""
        shape = value.shape
        return exact.add(exact.mul(value, exact.full(shape, 6)),
                         exact.full(shape, 1))

    def cubic(t):
        """`f(t) = sum(t^3)`: degree three, so the central difference is
        exactly its derivative `3t^2` plus `h^2`."""
        return scalarize(stage1.mul(stage1.mul(t, t), t))

    def cubic_gradient(value):
        """`3x^2`, from `exact` alone."""
        return exact.mul(exact.full(value.shape, 3),
                         exact.mul(value, value))

    # ---- the walk is stage 1's, not a copy of it --------------------------

    assert s.Node is stage1.Node, (
        "stage 9's Node is %r, not stage 1's: the leaf the oracle differentiates "
        "at must be the node stage 1's backward fills in" % (s.Node,))
    assert s.backward is stage1.backward, (
        "stage 9's backward is %r, not stage 1's: the oracle compares the finite "
        "difference with a copy of itself if it re-declares the walk" % (s.backward,))
    assert s.zero_grad is stage1.zero_grad, (
        "stage 9's zero_grad is %r, not stage 1's" % (s.zero_grad,))

    # ---- a quadratic: exact for every h, at two different h ---------------

    QUADRATICS = (
        ("a scalar leaf", Rational(3, 2), (Rational(1, 10), 5)),
        ("a vector of ints", (1, 2, 3), (Rational(1, 7), 10 ** 6)),
        ("a vector of fractions", (Rational(1, 2), Rational(-3, 4)),
         (Rational(3, 5), 2)),
        ("a matrix", ((1, 2), (3, 4)), (Rational(1, 3), 7)),
        ("a vector with a zero cell", (-2, 0, 5), (Rational(1, 2), 3)),
    )

    for name, nested, steps in QUADRATICS:
        x = leaf(nested)
        shape = x.value.shape
        want = quadratic_gradient(x.value)
        assert steps[0] != steps[1], (
            "the %s fixture probes one step twice: %r and %r" % (name, *steps))
        for h in steps:
            before = x.grad
            numeric = s.finite_difference(quadratic, x, h)
            assert isinstance(numeric, exact.Tensor), (
                "finite_difference returned %r, not an exact.Tensor" % (numeric,))
            assert numeric.shape == shape, (
                "the difference at %s has shape %r, not the leaf's %r: a gradient "
                "has its operand's shape (§3 invariant 2)"
                % (name, numeric.shape, shape))
            assert numeric.cells and all(
                isinstance(cell, Rational) for cell in numeric.cells), (
                "a cell of the difference at %s is not an exact Rational pair: %r"
                % (name, numeric.cells))
            assert numeric == want, (
                "the central difference of the %s fixture at h=%r is %r, not the "
                "exact derivative %r it must equal for every step: a one-sided "
                "difference, a division by h instead of 2h, or a step truncated "
                "with // would all answer differently"
                % (name, h, numeric, want))
            assert x.grad == before, (
                "the oracle touched the leaf's grad: %r, not %r"
                % (x.grad, before))
            got = s.gradient_check(quadratic, x, h)
            assert isinstance(got, exact.Tensor) and got == want, (
                "gradient_check at the %s fixture with h=%r returned %r, not the "
                "exact derivative %r the finite difference and the engine both "
                "have" % (name, h, got, want))
            assert x.grad == want, (
                "gradient_check left the leaf at %r, not the derivative %r"
                % (x.grad, want))
            again = s.gradient_check(quadratic, x, h)
            assert again == want and x.grad == want, (
                "a second gradient_check changed the answer: %r and %r, not %r "
                "and %r — the check must clear the graph it clears itself"
                % (again, x.grad, want, want))

    # a vector fixture's columns are the partial derivatives, not one column
    # repeated and not a directional difference along the diagonal
    x = leaf((1, 2, 3))
    numeric = s.finite_difference(quadratic, x, Rational(1, 4))
    assert numeric.cells[0] != numeric.cells[1] != numeric.cells[2], (
        "the difference over (1, 2, 3) is %r: every column must be the partial "
        "derivative of its own coordinate" % (numeric.cells,))

    # a negative step is the same difference, and the sign of h is no step at
    # all: the two points swap and the quotient is unchanged
    want = quadratic_gradient(x.value)
    assert s.finite_difference(quadratic, x, 4) == want, (
        "a step of 4 and a step of -4 must give the same central difference")
    assert s.finite_difference(quadratic, x, -4) == want, (
        "a step of -4 must give the derivative, and it gave %r"
        % (s.finite_difference(quadratic, x, -4),))
    assert s.finite_difference(quadratic, x, Rational(-1, 2)) == want, (
        "a fractional negative step must give the derivative")

    # ---- a cubic: off by exactly h^2, and the refusal carries it ----------

    CUBICS = (
        ("a scalar", Rational(1, 2), 1),
        ("a scalar at a fractional step", Rational(1, 2), Rational(3, 2)),
        ("a vector", (1, 2), 1),
        ("a vector at a doubled step", (1, 2), 2),
        ("a fractional leaf", Rational(1, 3), Rational(1, 2)),
        ("a step of a millionth", Rational(1, 2), Rational(1, 10 ** 6)),
        ("a step of a hundred-quintillionth", Rational(1, 2), Rational(1, 10 ** 20)),
        ("a leaf too big for a float", 2 ** 60, 1),
    )

    for name, nested, h in CUBICS:
        x = leaf(nested)
        shape = x.value.shape
        want = cubic_gradient(x.value)
        step = h if isinstance(h, Rational) else Rational(h)
        leak = exact.full(shape, step * step)
        numeric = s.finite_difference(cubic, x, h)
        assert numeric == exact.add(want, leak), (
            "the central difference of the cubic at %s with h=%r is %r, not the "
            "derivative %r plus exactly h^2 = %s: the difference of a cubic is "
            "off by an exact amount proportional to h^2"
            % (name, h, numeric, want, pair(step * step)))
        message = _refuses(exact.AutogradError,
                           "the gradient check of the cubic at %s with h=%r"
                           % (name, h),
                           lambda: s.gradient_check(cubic, x, h))
        assert "index 0" in message, (
            "the cubic refusal does not name the cell it disagreed at: %r"
            % (message,))
        assert "%s and %s" % (pair(numeric.cells[0]), pair(want.cells[0])) in message, (
            "the cubic refusal does not name both exact numbers (%s and %s): %r"
            % (pair(numeric.cells[0]), pair(want.cells[0]), message))
        assert "off by %s" % pair(step * step) in message, (
            "the cubic refusal does not name the exact amount it is off by, "
            "h^2 = %s: %r" % (pair(step * step), message))
        assert x.grad == want, (
            "the engine's own backward at %s is %r, not the hand-computed "
            "derivative %r: the refusal must be the engine's number against the "
            "oracle's" % (name, x.grad, want))

    # ---- the same shape, every cell different -----------------------------

    def detached(t):
        """An `fn` that rebuilds its own leaf from the tensor instead of using
        the node it is handed: the same value, a graph the caller's leaf is not
        in, so the engine leaves the leaf at the zeros."""
        own = stage1.Node(t.value)
        return scalarize(stage1.mul(own, own))

    x = leaf((3, 5))
    message = _refuses(exact.AutogradError,
                       "a check of a graph the leaf is not in",
                       lambda: s.gradient_check(detached, x, 1))
    assert "index 0" in message and "%s and %s" % (pair(Rational(6)),
                                                   pair(Rational(0))) in message, (
        "the refusal of a graph the leaf is not in must name the cell and both "
        "numbers — the oracle's 6/1 and the engine's 0/1 — and it says %r: the "
        "shapes are equal, so a comparison of shapes alone sees nothing"
        % (message,))
    assert x.grad == exact.zeros((2,)), (
        "the engine reached the caller's leaf (%r) although the graph fn built "
        "holds its own" % (x.grad,))

    # ---- the caller's accumulation does not leak into the check -----------

    x = leaf((1, 2, 3))
    want = quadratic_gradient(x.value)
    assert stage1.backward(quadratic(x)) is None, (
        "stage 1's backward returned something")
    assert x.grad == want, (
        "the fixture's own backward left the leaf at %r, not %r" % (x.grad, want))
    got = s.gradient_check(quadratic, x, Rational(1, 4))
    assert got == want and x.grad == want, (
        "gradient_check accumulated on top of the backward that already ran: it "
        "answered %r and left the leaf at %r, not the derivative %r: the graph "
        "must be cleared before its own backward" % (got, x.grad, want))

    # ---- a function whose graph never reaches the leaf --------------------

    def constant(t):
        """`fn(t) = 7`, a leaf of its own: the graph does not contain the
        caller's leaf, so the engine leaves it at the zeros — and the oracle
        agrees, because moving the leaf does not move the value."""
        return stage1.Node(exact.full((), 7))

    x = leaf((1, 2))
    got = s.gradient_check(constant, x, Rational(1, 3))
    assert got == exact.zeros((2,)) and x.grad == exact.zeros((2,)), (
        "a constant fn has a zero gradient, and the oracle answered %r with the "
        "leaf at %r" % (got, x.grad))

    # ---- refusals ---------------------------------------------------------

    x = leaf((1, 2))
    message = _refuses(exact.AutogradError,
                       "a finite difference at a Tensor instead of a Node",
                       lambda: s.finite_difference(quadratic, x.value, 1))
    assert "Node" in message, (
        "the refusal of an x that is not a Node does not name it: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a gradient check at a Tensor instead of a Node",
                       lambda: s.gradient_check(quadratic, x.value, 1))
    assert "Node" in message, (
        "the refusal of an x that is not a Node does not name it: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a finite difference of a fn that is not callable",
                       lambda: s.finite_difference(7, x, 1))
    assert "7" in message, (
        "the refusal of a fn that is not callable does not name it: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a gradient check of a fn that is not callable",
                       lambda: s.gradient_check("f", x, 1))
    assert "'f'" in message, (
        "the refusal of a fn that is not callable does not name it: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a fn that returns a Tensor instead of a Node",
                       lambda: s.finite_difference(lambda t: t.value, x, 1))
    assert "Node" in message, (
        "the refusal of a fn whose result is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError,
                       "a gradient check of a fn that returns a Tensor",
                       lambda: s.gradient_check(lambda t: t.value, x, 1))
    assert "Node" in message, (
        "the refusal of a fn whose result is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError,
                       "a fn whose value is not a scalar",
                       lambda: s.finite_difference(lambda t: stage1.mul(t, t), x, 1))
    assert "(2,)" in message and "scalar" in message, (
        "the refusal of a non-scalar value does not name its shape and the "
        "scalar the oracle needs: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a gradient check of a fn whose value is not a scalar",
                       lambda: s.gradient_check(lambda t: stage1.mul(t, t), x, 1))
    assert "(2,)" in message, (
        "the refusal of a non-scalar value does not name its shape: %r" % (message,))
    assert x.grad == exact.zeros((2,)), (
        "a refused gradient check touched the leaf's grad: %r" % (x.grad,))

    for bad in (0, Rational(0), Rational(0, 5)):
        message = _refuses(exact.ExactError, "a step of zero",
                           lambda: s.finite_difference(quadratic, x, bad))
        assert "h=0/1" in message and "zero" in message, (
            "the refusal of the zero step %r does not name h and the zero it "
            "refuses: %r" % (bad, message))
        message = _refuses(exact.ExactError, "a gradient check with a step of zero",
                           lambda: s.gradient_check(quadratic, x, bad))
        assert "h=0/1" in message and "zero" in message, (
            "the refusal of the zero step %r does not name h and the zero it "
            "refuses: %r" % (bad, message))

    for bad in (True, "1/2", None):
        message = _refuses(exact.ExactError, "a step that is not a number",
                           lambda: s.finite_difference(quadratic, x, bad))
        assert "h=" in message, (
            "the refusal of the step %r does not name h: %r" % (bad, message))
        message = _refuses(exact.ExactError,
                           "a gradient check with a step that is not a number",
                           lambda: s.gradient_check(quadratic, x, bad))
        assert "h=" in message, (
            "the refusal of the step %r does not name h: %r" % (bad, message))

    # ---- an int step is converted exactly, on a cubic as well as a quadratic

    x = leaf(Rational(1, 2))
    want = cubic_gradient(x.value)
    for h in (1, 2, 3):
        step = Rational(h)
        numeric = s.finite_difference(cubic, x, h)
        assert numeric == exact.add(want, exact.full((), step * step)), (
            "the cubic at the int step %r is %r, not %r + h^2 = %r: an int step "
            "is an exact Rational, and 2h is h + h and never h // 2"
            % (h, numeric, want, exact.add(want, exact.full((), step * step))))

    # ---- every gradient is an exact Rational pair -------------------------

    for name, nested, h in CUBICS:
        x = leaf(nested)
        numeric = s.finite_difference(cubic, x, h)
        assert numeric.shape == x.value.shape, (
            "the difference at %s has shape %r, not the leaf's %r"
            % (name, numeric.shape, x.value.shape))
        assert all(isinstance(cell, Rational) and cell.denominator > 0
                   for cell in numeric.cells), (
            "a cell of the difference at %s is not a normalized Rational: %r"
            % (name, numeric.cells))

    print("check_09: the oracle — the central difference is exact's own "
          "arithmetic, one column per coordinate, a Tensor of the leaf's shape; "
          "it equals the engine's backward on every quadratic fixture at two "
          "different h and is off by exactly h^2 on a cubic (a h^2 no float "
          "comparison could see at x = 2^60); a one-sided difference, a `/ h`, a "
          "`//`, a zero or non-rational step, a diagonal instead of an axis, a "
          "shape-only comparison and a tolerance are all caught, and every "
          "gradient is compared as an exact Rational pair")

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("H2_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "autograd-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set H2_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(exc, what, call):
        """The message of the refusal `call` must raise, or the mistake named.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except exc as refused:
            return str(refused)
        except NotImplementedError:
            raise
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of %s: %r"
                % (what, type(wrong).__name__, exc.__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import exact
    import fixtures
    import stage_01 as stage1
    import stage_03 as stage3
    import stage_04 as stage4
    import stage_10 as s

    Rational = exact.Rational
    RATE = fixtures.LEARNING_RATE
    HALF = Rational(1, 2)

    def pair(cell):
        """A `Rational` as `numerator/denominator`, for reading a message."""
        return "%d/%d" % (cell.numerator, cell.denominator)

    def as_float(number):
        """`number` as the float it is not: the one number this course refuses,
        written without a float literal so this check carries none either."""
        return number.numerator / number.denominator

    def leaves(name):
        """The fixture model's tensors as fresh parameter leaves."""
        return tuple(stage1.Node(tensor) for tensor in fixtures.MODELS[name])

    def composite(forward, params, inputs, targets):
        """The fixture's composite, built here from stages 1 and 3 so that no
        probe depends on the stage's own loss: `mean((forward - y) ** 2)`."""
        x = stage1.Node(inputs)
        y = stage1.Node(targets)
        residual = stage3.sub(forward(params, x), y)
        return stage3.mean(stage3.mul(residual, residual))

    def gradient(forward, params, inputs, targets):
        """The loss of the composite, and the engine's gradient of it left on
        `params` — this check's own use of the engine, not the stage's."""
        loss = composite(forward, params, inputs, targets)
        stage1.zero_grad(loss)
        stage1.backward(loss)
        return loss.value.cells[0]

    def run_here(forward, params, inputs, targets, steps, rate):
        """The check's own plain-SGD loop: the loss at the parameters each step
        starts from, then `theta - rate * grad` for every parameter — so the
        stage's run is compared with a second, independent loop."""
        losses = []
        for _ in range(steps):
            losses.append(gradient(forward, params, inputs, targets))
            grads = tuple(node.grad for node in params)
            for node, grad in zip(params, grads):
                scale = exact.full(grad.shape, rate)
                node.value = exact.sub(node.value, exact.mul(grad, scale))
        return tuple(losses)

    def as_tensor(grad, shape):
        """A flat gradient tuple as the `Tensor` its shape gives it."""
        return exact.Tensor(tuple(grad), shape)

    def predictions(forward, params, inputs):
        """The model's output cells after training."""
        return forward(params, stage1.Node(inputs)).value.cells

    def classify(cells, targets):
        """How many rows the model puts on the target's own side of `1/2`."""
        return sum(1 for cell, target in zip(cells, targets.cells)
                   if (cell > HALF) == (target > HALF))

    # ---- the capstone is the earlier stages, not a copy of them -----------

    assert s.stage_01 is stage1, (
        "stage 10's stage_01 is %r, not stage 1's: the step must run the walk "
        "the rest of the course was built on" % (s.stage_01,))
    assert s.stage_03 is stage3, (
        "stage 10's stage_03 is %r, not stage 3's" % (s.stage_03,))
    assert s.stage_04 is stage4, (
        "stage 10's stage_04 is %r, not stage 4's" % (s.stage_04,))

    # ---- the fixture's own numbers, before any step -----------------------

    names = fixtures.MODEL_PARAMS["mlp"]
    params = leaves("mlp")
    loss = composite(stage4.mlp, params, fixtures.XOR[0], fixtures.XOR[1])
    assert loss.value.shape == (), (
        "the composite's loss has shape %r, not a scalar" % (loss.value.shape,))
    assert loss.value.cells[0] == Rational(1), (
        "the loss of the 2 -> 4 -> 1 model on XOR at the fixture's own weights "
        "is %s, not exactly 1" % (pair(loss.value.cells[0]),))
    stage1.zero_grad(loss)
    stage1.backward(loss)
    for name, node in zip(names, params):
        want = tuple(fixtures.REFERENCE_GRADIENTS[name])
        assert node.grad.shape == node.value.shape, (
            "the gradient of %s has shape %r and its value has shape %r"
            % (name, node.grad.shape, node.value.shape))
        assert node.grad.cells == want, (
            "the gradient of %s at step 0 is not the fixture's reference: %d "
            "cells against %d" % (name, len(node.grad.cells), len(want)))

    # ---- sgd: the exact step ----------------------------------------------

    before_values = tuple(node.value for node in params)
    before_grads = tuple(node.grad for node in params)
    updated = s.sgd(params, learning_rate=RATE)
    assert isinstance(updated, tuple), (
        "sgd returned %r, not a tuple of the updated parameters" % (updated,))
    assert len(updated) == len(params), (
        "sgd returned %d updated values for %d parameters: a parameter is "
        "updated once and none is skipped" % (len(updated), len(params)))
    for name, tensor, got in zip(names, fixtures.MODELS["mlp"], updated):
        want = exact.sub(
            tensor,
            exact.mul(exact.full(tensor.shape, RATE),
                      as_tensor(fixtures.REFERENCE_GRADIENTS[name], tensor.shape)))
        assert isinstance(got, exact.Tensor), (
            "the update of %s is %r, not an exact.Tensor" % (name, got))
        assert got == want, (
            "the update of %s is not `theta - LEARNING_RATE * grad` with the "
            "reference gradient: the step must multiply the learning rate, "
            "subtract it, and read the gradient `backward` left" % (name,))
    assert tuple(node.value for node in params) == before_values, (
        "sgd wrote into the parameters instead of returning the updates")
    assert tuple(node.grad for node in params) == before_grads, (
        "sgd disturbed the gradients it read")

    # an int is promoted exactly, and the rate is the caller's
    doubled = s.sgd(params, learning_rate=2)
    assert doubled[0] == exact.sub(
        fixtures.MODELS["mlp"][0],
        exact.mul(exact.full((3, 4), Rational(2)),
                  as_tensor(fixtures.REFERENCE_GRADIENTS["w1"], (3, 4)))), (
        "an int learning rate is an exact Rational and must give `theta - 2 * "
        "grad`, not a refusal and not a truncation")
    assert doubled[0] != updated[0], (
        "a learning rate of 2 and one of 1/4 gave the same update")
    assert tuple(s.sgd(params, learning_rate=Rational(0))) == before_values, (
        "a step at a learning rate of zero must move nothing")
    halved = s.sgd(params, learning_rate=Rational(1, 2))
    assert halved[0] != updated[0], (
        "a learning rate of 1/2 and one of 1/4 gave the same update: the "
        "learning rate must be the caller's and not a hard-coded 1/4")

    # ---- sgd's own refusals ------------------------------------------------

    message = _refuses(exact.AutogradError,
                       "a step over a params that is not a sequence",
                       lambda: s.sgd(7, learning_rate=RATE))
    assert "params" in message, (
        "the refusal of a params that is not a sequence does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "a step over no parameters",
                       lambda: s.sgd((), learning_rate=RATE))
    assert "empty" in message, (
        "the refusal of an empty params does not name it: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a step over a parameter that is not a Node",
                       lambda: s.sgd((7,), learning_rate=RATE))
    assert "not a Node" in message, (
        "the refusal of a parameter that is not a Node does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError,
                       "a step that names one parameter twice",
                       lambda: s.sgd((params[0], params[0]), learning_rate=RATE))
    assert "twice" in message or "already names" in message, (
        "the refusal of a parameter named twice does not name it: %r"
        % (message,))
    frozen = stage1.Node(fixtures.MODELS["mlp"][0], requires_grad=False)
    message = _refuses(exact.AutogradError,
                       "a step over a frozen parameter",
                       lambda: s.sgd((frozen,), learning_rate=RATE))
    assert "frozen" in message, (
        "the refusal of a frozen parameter does not name it: %r" % (message,))
    misgrad = leaves("mlp")[0]
    misgrad.grad = exact.zeros((1,))
    message = _refuses(exact.AutogradError,
                       "a step over a gradient of the wrong shape",
                       lambda: s.sgd((misgrad,), learning_rate=RATE))
    assert "(3, 4)" in message and "(1,)" in message, (
        "the refusal of a gradient of the wrong shape does not name both "
        "shapes: %r" % (message,))

    for bad in (as_float(RATE), True, None, "1/4"):
        message = _refuses(exact.ExactError,
                           "a step at the learning rate %r" % (bad,),
                           lambda: s.sgd(params, learning_rate=bad))
        assert "learning_rate=" in message, (
            "the refusal of the learning rate %r does not name it: %r"
            % (bad, message))


    # ---- train: the fixture's own run, and an independent loop over it ----

    expected = tuple(fixtures.EXPECTED_LOSS)
    params = leaves("mlp")
    losses = s.train((params, stage4.mlp), fixtures.XOR,
                     steps=fixtures.EXPECTED_STEPS, learning_rate=RATE)
    assert isinstance(losses, tuple), (
        "train returned %r, not a tuple of exact Rationals" % (losses,))
    assert len(losses) == len(expected), (
        "the run of the fixture's eight steps returned %d losses, not %d"
        % (len(losses), len(expected)))
    assert all(isinstance(cell, Rational) and cell.denominator > 0
               for cell in losses), (
        "a recorded loss is not a normalized exact Rational pair")
    assert losses[0] == Rational(1), (
        "the first recorded loss is not exactly 1: the loss belongs to the "
        "parameters the step started from")
    assert all(losses[index] < losses[index - 1]
               for index in range(1, len(losses))), (
        "the loss does not fall strictly from step to step")
    assert losses == expected, (
        "the run of the fixture's own eight steps is not EXPECTED_LOSS: the "
        "loss must be recomputed from the engine at every step, at the "
        "fixture's own learning rate, and XOR must be learned inside the "
        "budget")
    assert tuple(node.value for node in params) != fixtures.MODELS["mlp"], (
        "the eight steps left the parameters at their initial values")
    assert classify(predictions(stage4.mlp, params, fixtures.XOR[0]),
                    fixtures.XOR[1]) == 4, (
        "the trained 2 -> 4 -> 1 model does not classify XOR inside "
        "EXPECTED_STEPS: every prediction must be on the correct side of 1/2")

    # the same run, by this check's own loop over the same engine
    other = leaves("mlp")
    again = run_here(stage4.mlp, other, fixtures.XOR[0], fixtures.XOR[1],
                     fixtures.EXPECTED_STEPS, RATE)
    assert again == expected, (
        "this check's own loop does not reproduce EXPECTED_LOSS: the fixture "
        "and the engine disagree")
    assert tuple(node.value for node in other) == tuple(node.value for node
                                                        in params), (
        "the trained leaves are not the ones this check's own loop leaves: "
        "the step must be `theta - learning_rate * grad` with no second factor")

    # the step count is the caller's, and zero steps is no losses
    fresh = leaves("mlp")
    assert s.train((fresh, stage4.mlp), fixtures.XOR, steps=0,
                   learning_rate=RATE) == (), (
        "a run of zero steps returned losses")
    assert tuple(node.value for node in fresh) == fixtures.MODELS["mlp"], (
        "a run of zero steps moved the parameters")
    assert s.train((fresh, stage4.mlp), fixtures.XOR, steps=1,
                   learning_rate=RATE) == (Rational(1),), (
        "a run of one step is the loss at the fixture's own weights, exactly 1")
    third = leaves("mlp")
    assert s.train((third, stage4.mlp), fixtures.XOR, steps=3,
                   learning_rate=RATE) == expected[:3], (
        "a run of three steps is not the first three losses of the reference")
    assert s.train((leaves("mlp"), stage4.mlp), fixtures.XOR, steps=2,
                   learning_rate=Rational(1, 8)) != \
        s.train((leaves("mlp"), stage4.mlp), fixtures.XOR, steps=2,
                learning_rate=RATE), (
        "two different learning rates gave the same run: the rate must be the "
        "caller's and not the fixture's")

    # ---- a second model, two more datasets, and XOR is not linear ---------

    for name, data, learned in (("AND", fixtures.AND, True),
                                ("OR", fixtures.OR, True),
                                ("XOR", fixtures.XOR, False)):
        params = leaves("linear")
        run = s.train((params, stage4.mlp), data,
                      steps=fixtures.STEPS, learning_rate=RATE)
        assert len(run) == fixtures.STEPS, (
            "the linear run on %s returned %d losses, not STEPS = %d"
            % (name, len(run), fixtures.STEPS))
        assert run[0] == gradient(stage4.mlp, leaves("linear"),
                                  data[0], data[1]), (
            "the first loss of the linear run on %s is not this check's own "
            "computation of the composite at the fixture's weights" % (name,))
        assert all(run[index] < run[index - 1]
                   for index in range(1, len(run))), (
            "the linear run on %s does not fall strictly at every step" % (name,))
        assert (classify(predictions(stage4.mlp, params, data[0]),
                         data[1]) == 4) == learned, (
            "the linear fixture must learn %s inside STEPS, and %s"
            % (name, "it must not learn XOR" if not learned else "it must"))

    # ---- a forward of this check's own: the model is not special-cased ----

    def offset(params, x):
        """A forward the stages never wrote: the linear layer's output plus one,
        so a capstone that calls `mlp` itself instead of the forward it was
        handed answers with different numbers."""
        weight, bias = params
        one = stage1.Node(exact.ones((x.value.shape[0], 1)))
        return stage3.add(stage3.add(stage4.matmul(x, weight), bias), one)

    params = leaves("linear")
    got = s.train((params, offset), fixtures.AND, steps=3, learning_rate=RATE)
    other = leaves("linear")
    want = run_here(offset, other, fixtures.AND[0], fixtures.AND[1], 3, RATE)
    assert got == want, (
        "the run of the forward this check handed in is not this check's own "
        "loop over that forward: train must run the model it is given")
    assert got != s.train((leaves("linear"), stage4.mlp), fixtures.AND,
                          steps=3, learning_rate=RATE), (
        "the forward this check handed in was ignored")
    assert tuple(node.value for node in params) == tuple(node.value
                                                         for node in other), (
        "the leaves trained through this check's forward are not the ones its "
        "own loop leaves")


    # ---- the loop's own refusals ------------------------------------------

    model = (leaves("mlp"), stage4.mlp)
    for bad in (True, Rational(3, 2), -1, "3", None):
        message = _refuses(exact.ExactError, "a run of %r steps" % (bad,),
                           lambda: s.train(model, fixtures.XOR, steps=bad,
                                           learning_rate=RATE))
        assert "steps=" in message, (
            "the refusal of the step count %r does not name it: %r"
            % (bad, message))
    message = _refuses(exact.AutogradError, "a model that is not a pair",
                       lambda: s.train(7, fixtures.XOR, steps=1,
                                       learning_rate=RATE))
    assert "model" in message, (
        "the refusal of a model that is not a pair does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError,
                       "a model whose forward is not callable",
                       lambda: s.train((leaves("mlp"), 7), fixtures.XOR, steps=1,
                                       learning_rate=RATE))
    assert "forward" in message, (
        "the refusal of a forward that is not callable does not name it: %r"
        % (message,))
    message = _refuses(exact.AutogradError, "a model without parameters",
                       lambda: s.train(((), stage4.mlp), fixtures.XOR, steps=1,
                                       learning_rate=RATE))
    assert "empty" in message, (
        "the refusal of a model without parameters does not name it: %r"
        % (message,))
    twice = leaves("mlp")[0]
    message = _refuses(exact.AutogradError,
                       "a model that names one parameter twice",
                       lambda: s.train(((twice, twice), stage4.mlp),
                                       fixtures.XOR, steps=1,
                                       learning_rate=RATE))
    assert "twice" in message or "already names" in message, (
        "the refusal of a model that names a parameter twice does not name "
        "it: %r" % (message,))
    for bad in (7, (fixtures.XOR[0],),
                (fixtures.XOR[0], fixtures.XOR[1], fixtures.XOR[1])):
        message = _refuses(exact.AutogradError, "a data that is not a pair",
                           lambda: s.train(model, bad, steps=1,
                                           learning_rate=RATE))
        assert "data" in message, (
            "the refusal of a data that is not an (inputs, targets) pair does "
            "not name it: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a data whose inputs are not a Tensor",
                       lambda: s.train(model, (7, fixtures.XOR[1]), steps=1,
                                       learning_rate=RATE))
    assert "inputs" in message, (
        "the refusal of inputs that are not an exact.Tensor does not name "
        "them: %r" % (message,))
    message = _refuses(exact.AutogradError,
                       "a data whose targets are not a Tensor",
                       lambda: s.train(model, (fixtures.XOR[0], 7), steps=1,
                                       learning_rate=RATE))
    assert "targets" in message, (
        "the refusal of targets that are not an exact.Tensor does not name "
        "them: %r" % (message,))
    message = _refuses(exact.ExactError, "a rank-1 target",
                       lambda: s.train(model,
                                       (fixtures.XOR[0],
                                        exact.Tensor((0, 0, 0, 1), (4,))),
                                       steps=1, learning_rate=RATE))
    assert "(4,)" in message, (
        "the refusal of a rank-1 target does not name its shape: %r"
        % (message,))
    message = _refuses(exact.ExactError, "a rank-1 input",
                       lambda: s.train((leaves("linear"), stage4.mlp),
                                       (exact.Tensor((1, 0, 0), (3,)),
                                        fixtures.OR[1]),
                                       steps=1, learning_rate=RATE))
    assert "(3,)" in message, (
        "the refusal of a rank-1 input does not name its shape: %r"
        % (message,))
    message = _refuses(exact.AutogradError,
                       "a forward that returns a Tensor",
                       lambda: s.train((leaves("mlp"),
                                        lambda params, x: x.value),
                                       fixtures.XOR, steps=1,
                                       learning_rate=RATE))
    assert "forward returned" in message, (
        "the refusal of a forward that returns a Tensor instead of a Node "
        "does not name it: %r" % (message,))

    def wide(params, x):
        """A forward whose output has two columns the targets do not have."""
        return stage1.Node(exact.full((x.value.shape[0], 2), 3))

    message = _refuses(exact.AutogradError,
                       "an output shaped unlike the targets",
                       lambda: s.train((leaves("mlp"), wide), fixtures.XOR,
                                       steps=1, learning_rate=RATE))
    assert "(4, 2)" in message and "(4, 1)" in message, (
        "the refusal of an output shaped unlike the targets does not name both "
        "shapes: %r" % (message,))
    message = _refuses(exact.ExactError, "a run at a float learning rate",
                       lambda: s.train(model, fixtures.XOR, steps=1,
                                       learning_rate=as_float(RATE)))
    assert "learning_rate=" in message, (
        "the refusal of a float learning rate does not name it: %r"
        % (message,))

    # ---- reproduce_reference: the engine's answer, verified ---------------

    reproduced = s.reproduce_reference()
    assert reproduced is not fixtures.REFERENCE_GRADIENTS, (
        "reproduce_reference handed the fixture's own mapping back instead of "
        "the engine's answer")
    assert set(reproduced) == set(names), (
        "the reproduced gradients are keyed %r, not by the fixture's tensor "
        "names %r" % (sorted(reproduced), sorted(names)))
    for name in names:
        got = tuple(reproduced[name])
        want = tuple(fixtures.REFERENCE_GRADIENTS[name])
        assert len(got) == fixtures.MODELS["mlp"][names.index(name)].size, (
            "the reproduced gradient of %s has %d cells, not the tensor's %d"
            % (name, len(got),
               fixtures.MODELS["mlp"][names.index(name)].size))
        assert got == want, (
            "the reproduced gradient of %s is not the fixture's reference: the "
            "run must reproduce REFERENCE_GRADIENTS Rational for Rational"
            % (name,))
        assert all(isinstance(cell, Rational) and cell.denominator > 0
                   for cell in got), (
            "a reproduced cell of %s is not a normalized exact Rational pair"
            % (name,))
    assert dict(reproduced) == dict(fixtures.REFERENCE_GRADIENTS), (
        "the reproduced gradients are not equal to REFERENCE_GRADIENTS")

    # the engine's answer, computed a second time by this check
    mine = leaves("mlp")
    again_loss = composite(stage4.mlp, mine, fixtures.XOR[0], fixtures.XOR[1])
    stage1.zero_grad(again_loss)
    stage1.backward(again_loss)
    for name, node in zip(names, mine):
        assert tuple(reproduced[name]) == node.grad.cells, (
            "the gradient of %s that reproduce_reference returns is not the "
            "one this check's own backward leaves at the initial weights"
            % (name,))

    # ---- the verification itself: a perturbed reference must be refused ---

    original_losses = fixtures.EXPECTED_LOSS
    original_grads = fixtures.REFERENCE_GRADIENTS
    last = original_losses[-1]
    tiny = Rational(1, 10 ** 40)
    try:
        fixtures.EXPECTED_LOSS = original_losses[:-1] + (last + tiny,)
        message = _refuses(
            exact.AutogradError,
            "a run whose last loss the reference disagrees with by %s"
            % (pair(tiny),),
            s.reproduce_reference)
        assert "index 7" in message, (
            "the refusal of a run the reference disagrees with does not name "
            "the loss it disagreed at: %r" % (message,))
        assert pair(last) in message and pair(last + tiny) in message, (
            "the refusal of a run the reference disagrees with does not name "
            "both exact losses: %r" % (message,))
        fixtures.EXPECTED_LOSS = original_losses[:-1]
        message = _refuses(exact.AutogradError,
                           "a run with one loss fewer than the reference",
                           s.reproduce_reference)
        assert "8" in message and "7" in message, (
            "the refusal of a run whose length disagrees with the reference "
            "does not name both counts: %r" % (message,))
        fixtures.EXPECTED_LOSS = original_losses
        wrong = dict((name, tuple(original_grads[name])) for name in names)
        wrong["w2"] = (wrong["w2"][0] + Rational(1),) + wrong["w2"][1:]
        fixtures.REFERENCE_GRADIENTS = wrong
        message = _refuses(exact.AutogradError,
                           "a reference gradient off by one",
                           s.reproduce_reference)
        assert "w2" in message and "index 0" in message, (
            "the refusal of a gradient the reference disagrees with does not "
            "name the tensor and the cell: %r" % (message,))
        assert pair(wrong["w2"][0]) in message \
            and pair(original_grads["w2"][0]) in message, (
            "the refusal of a gradient the reference disagrees with does not "
            "name both exact numbers: %r" % (message,))
        wrong["w1"] = wrong["w1"][:-1]
        fixtures.REFERENCE_GRADIENTS = wrong
        message = _refuses(exact.AutogradError,
                           "a reference gradient with a cell fewer",
                           s.reproduce_reference)
        assert "w1" in message and "11" in message and "12" in message, (
            "the refusal of a gradient whose cell count disagrees with the "
            "reference does not name both counts: %r" % (message,))
        fixtures.REFERENCE_GRADIENTS = original_grads
    finally:
        fixtures.EXPECTED_LOSS = original_losses
        fixtures.REFERENCE_GRADIENTS = original_grads
    assert fixtures.EXPECTED_LOSS == original_losses, (
        "reproduce_reference left EXPECTED_LOSS changed")
    assert fixtures.REFERENCE_GRADIENTS == original_grads, (
        "reproduce_reference left REFERENCE_GRADIENTS changed")

    print("check_10: the step — sgd is `theta - learning_rate * grad` read "
          "before it writes and written nowhere, with an int rate promoted and "
          "a float refused; train runs the forward it is handed for the steps "
          "it is asked for, recording the loss at the parameters each step "
          "starts from, and its eight-step mlp/XOR run is EXPECTED_LOSS, "
          "strictly falling from exactly 1, XOR learned and the trained leaves "
          "equal to an independent loop's; the linear fixture learns AND and OR "
          "inside STEPS and never XOR; reproduce_reference returns the engine's "
          "gradients at step 0, equal to REFERENCE_GRADIENTS Rational for "
          "Rational, and refuses a perturbed reference by naming the tensor, "
          "the index and both exact pairs — with no float and no tolerance "
          "anywhere")

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The graph and the order",
        tags=["graph", "topological order"],
        action="Write `add`, `mul`, `backward` and `zero_grad` in stage_01.py.",
        predict="Why a diamond-shaped graph visited without a topological order "
                "returns the right answer on a tree and the wrong one — or never "
                "returns — on a diamond.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="The local derivatives",
        tags=["local derivatives", "quotient rule"],
        action="Write `sub`, `div`, `pow` and `neg` in stage_02.py.",
        predict="What `d(a/b)/db` is, and why implementing division as "
                "`a * pow(b, -1)` is not the same function on the integers.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Broadcasting and the reduction",
        tags=["broadcast", "reduction"],
        action="Write `add`, `sub`, `mul`, `sum` and `mean` over operands of "
               "different shapes in stage_03.py.",
        predict="What shape the gradient of a `(4,)` operand is when it was added "
                "to a `(3, 4)`, and what `mean`'s gradient is missing when every "
                "element is the same.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="The chain rule through a matrix",
        tags=["matmul", "VJP"],
        action="Write `matmul` and `mlp` in stage_04.py.",
        predict="Which operand's gradient is `G·Bᵀ` and which is `Aᵀ·G`, and why "
                "swapping them is invisible on a square symmetric fixture.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="Accumulation and reuse",
        tags=["accumulation", "reuse"],
        action="Write `shared` and `trainable` in stage_05.py.",
        predict="What a second `backward()` without `zero_grad()` does to a "
                "gradient, and what a node used twice should receive.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="The seed of a non-scalar output",
        tags=["seed", "VJP"],
        action="Write `backward` with a seed and `sum_to_scalar` in stage_06.py.",
        predict="What a `(2,)` output's backward needs that a scalar's does not, "
                "and what number the engine silently uses if you leave it out.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="Detach, and the graph that must not grow",
        tags=["detach", "no_grad"],
        action="Write `detach` and `no_grad` in stage_07.py.",
        predict="What a detach must drop so the backward cannot reach through "
                "it, and why an inference pass that builds a graph costs memory "
                "it never uses.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="The kink",
        tags=["relu", "ties"],
        action="Write `max`, `relu` and `abs` in stage_08.py.",
        predict="Where the gradient of a tied `max` goes under this course's "
                "convention, and what `relu'(0)` must be for that convention to "
                "hold in every call.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="The oracle",
        tags=["finite difference", "gradient check"],
        action="Write `finite_difference` and `gradient_check` in stage_09.py.",
        predict="Which polynomial's central difference is exactly its derivative "
                "for every step, and what a cubic's difference is off by.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="The capstone: the step",
        tags=["sgd", "training"],
        action="Write `sgd`, `train` and `reproduce_reference` in stage_10.py.",
        predict="How many exact steps the 2→4→1 model needs to learn XOR, and why "
                "two hundred of them are not writable.",
        check=check_10,
    ),
]
