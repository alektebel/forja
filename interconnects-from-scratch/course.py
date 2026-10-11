"""Interconnects From Scratch — course manifest.

Ten graded stages that build the collectives a training step is made of, on a
provided fabric: what a byte costs on a link, how to broadcast and reduce, the
ring and tree all-reduces and the size at which one beats the other, all-gather
and reduce-scatter as first-class operations, the all-to-all whose cost depends
on the data, point-to-point exchanges and group semantics, how to pick an
algorithm against the lower bound, and finally what one training step's
collectives cost when the communication hides behind the compute.

The thesis of the whole course is one sentence, and every stage's check asserts
it: A COLLECTIVE HAS A PLAN AND A PRICE, AND THE TWO ARE INDEPENDENT. The plan
says which rank sends which elements to which rank in which step; the fabric
says what a byte costs on each link. Correctness is checked by running the plan
(the provided executor applies the transfers to buffers), cost is checked by
counting (the cost model turns the plan into ticks), and the interesting
failures are the plans that pass one check and fail the other.

The links, the four topologies (a ring, a full mesh, a tree and a two-level
switch), the transfer and plan records, the routing and the executor are
provided (`fabric.py`, complete and proven); the exercise is the cost model and
the nine collectives above it. No network, no `time`, no `threading`, no
`asyncio`, no unseeded randomness and no module-level mutable state: ticks are
counted, not timed, and no number here is a float.

    python3 codecraft/cli.py run interconnects-from-scratch
"""

from codecraft.api import stage

TITLE = "Interconnects From Scratch"
DESCRIPTION = ("Collectives from scratch on a provided deterministic fabric: "
               "cost a transfer by the byte and by the hop instead of by the "
               "message, broadcast down a ring and a binomial tree, reduce "
               "without aliasing the accumulator that is still being sent, "
               "all-reduce with a pipelined ring of chunks, the tree and "
               "recursive-doubling all-reduces and the size where the tree "
               "wins, all-gather and reduce-scatter as collectives in their own "
               "right, an all-to-all whose ragged offsets are the whole "
               "exercise, point-to-point exchanges that are one launch and one "
               "step, an algorithm choice measured against the lower bound, and "
               "one training step costed with the communication hidden behind "
               "the compute instead of added to it.")
LEVEL = "intermediate"
ORDER = 18

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
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "interconnects-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    class _Plan:
        """A plan-shaped record for the shapes `fabric.Plan` refuses to build.

        `fabric.Plan.__post_init__` refuses a self-transfer, a zero length and a
        negative offset outright, so a *plan* carrying one cannot be constructed at
        all — which is exactly why `validate` is reached through this walk-alike. It
        carries the `transfers`, the `steps()`/`at()` the two checkers read, and the
        `length` of the buffer the plan would run against (or `None`).
        """

        def __init__(self, transfers, length=None):
            self.transfers = tuple(transfers)
            self.length = length

        def steps(self):
            return tuple(sorted({transfer.step for transfer in self.transfers}))

        def at(self, step):
            return tuple(transfer for transfer in self.transfers
                         if transfer.step == step)

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import fabric
    import stage_01 as s

    # ---- the unit the cost model charges -----------------------------------

    assert s.BYTES_PER_ELEMENT == fabric.ELEMENT_BYTES == 4, (
        "BYTES_PER_ELEMENT is %r, not the frozen four bytes of an element: %r"
        % (s.BYTES_PER_ELEMENT, fabric.ELEMENT_BYTES))

    # ---- hop_count ---------------------------------------------------------

    ring4 = fabric.ring(4)
    assert s.hop_count(ring4, "r0", "r1") == 1, (
        "hop_count of adjacent ranks is %r, not the one hop between them"
        % (s.hop_count(ring4, "r0", "r1"),))
    assert s.hop_count(ring4, "r0", "r2") == 2, (
        "hop_count across a ring of four is %r, not the two hops r0-r1-r2"
        % (s.hop_count(ring4, "r0", "r2"),))
    assert s.hop_count(ring4, "r0", "r0") == 0, (
        "hop_count from a rank to itself is %r; a rank is zero hops from "
        "itself, not one" % (s.hop_count(ring4, "r0", "r0"),))
    switch8 = fabric.switch(8, width=4)
    assert s.hop_count(switch8, "r1", "r5") == 3, (
        "hop_count across the switch's spine is %r, not the three hops "
        "r1-r0-r4-r5" % (s.hop_count(switch8, "r1", "r5"),))

    disconnected = fabric.Topology(
        ranks=("r0", "r1", "r2", "r3"),
        links=(fabric.Link(a="r0", b="r1", bandwidth=100, latency=5),))
    assert s.hop_count(disconnected, "r0", "r3") is None, (
        "hop_count across an unconnected pair answered %r; two ranks with no "
        "route between them are not zero hops apart"
        % (s.hop_count(disconnected, "r0", "r3"),))

    # ---- one hop, by the byte ----------------------------------------------

    one = fabric.send("r0", "r1", 400, 0)
    assert s.transfer_ticks(ring4, one) == 21, (
        "400 elements over one 100-byte/tick, 5-tick hop cost %r ticks, not "
        "5 + ceil(1600/100) = 21: the cost is per byte, not per message"
        % (s.transfer_ticks(ring4, one),))
    odd = fabric.send("r0", "r1", 30, 0)
    assert s.transfer_ticks(ring4, odd) == 7, (
        "30 elements (120 bytes) over a 100-byte/tick link cost %r ticks, not "
        "5 + ceil(120/100) = 7: a partial tick is charged as a whole one, so "
        "the byte time is ceiled and not floored or rounded"
        % (s.transfer_ticks(ring4, odd),))

    # ---- every hop, and every hop's latency --------------------------------

    two = fabric.send("r0", "r2", 400, 0)
    assert s.transfer_ticks(ring4, two) == 42, (
        "the same 400 elements over the two hops r0-r1-r2 cost %r ticks, not "
        "2 * (5 + 16) = 42: a transfer is charged per hop as well as per byte"
        % (s.transfer_ticks(ring4, two),))

    cross = fabric.send("r1", "r5", 400, 0)
    hops = switch8.hops_of(cross)
    per_hop = [link.latency + fabric.ceil_div(fabric.ELEMENT_BYTES * 400, link.bandwidth)
               for link in hops]
    assert s.transfer_ticks(switch8, cross) == 104 == sum(per_hop), (
        "the cross-group transfer cost %r ticks, not the sum of its hops' "
        "costs (%r over %r): the cost is not one hop's cost"
        % (s.transfer_ticks(switch8, cross), per_hop,
           [(link.a, link.b) for link in hops]))
    near = fabric.send("r1", "r0", 400, 0)
    assert s.transfer_ticks(switch8, cross) != s.transfer_ticks(switch8, near), (
        "a three-hop transfer and a one-hop transfer of the same bytes cost "
        "the same %r ticks: distance must enter the price"
        % (s.transfer_ticks(switch8, cross),))

    lost = fabric.send("r0", "r3", 4, 0)
    message = _refuses(fabric, "a transfer that cannot be routed",
                       lambda: s.transfer_ticks(disconnected, lost))
    assert "r3" in message or "rout" in message, (
        "the refusal of an unroutable transfer does not name it: %r" % (message,))

    # ---- a step is its slowest transfer ------------------------------------

    plan = fabric.Plan(transfers=(
        fabric.send("r1", "r5", 400, 0),      # 104 ticks, the slow one
        fabric.send("r0", "r1", 400, 0),      # 10 ticks, the fast one
        fabric.send("r0", "r1", 400, 2)))     # 10 ticks; step 1 is empty
    assert s.step_ticks(switch8, plan, 0) == 104, (
        "the step holding a 104-tick and a 10-tick transfer cost %r ticks: a "
        "step costs its slowest transfer, not the sum of its transfers"
        % (s.step_ticks(switch8, plan, 0),))
    assert s.step_ticks(switch8, plan, 1) == 0, (
        "the empty step cost %r ticks: a step with no transfers is not a step"
        % (s.step_ticks(switch8, plan, 1),))
    assert s.step_ticks(switch8, plan, 2) == 10, (
        "the step holding the 10-tick transfer cost %r ticks, not its own 10: "
        "a step reads its own transfers, not every transfer in the plan"
        % (s.step_ticks(switch8, plan, 2),))

    # ---- a plan is the sum of its steps ------------------------------------

    assert s.plan_ticks(switch8, plan) == 114, (
        "the two-step plan cost %r ticks, not step 0's 104 plus step 2's 10: a "
        "plan is the sum of its steps"
        % (s.plan_ticks(switch8, plan),))
    assert s.plan_ticks(switch8, plan) != 104, (
        "the plan cost %r ticks, the maximum of its steps: a plan is summed, "
        "not maximised" % (s.plan_ticks(switch8, plan),))

    # ---- bytes_by_link: every link on the route ----------------------------

    carried = s.bytes_by_link(switch8, fabric.Plan(transfers=(
        fabric.send("r1", "r5", 100, 0),          # 400 bytes over r1-r0-r4-r5
        fabric.send("r0", "r1", 100, 1))))        # 400 bytes over r0-r1
    assert len(carried) == 3, (
        "bytes_by_link reported %r links, not the three the route crosses: a "
        "multi-hop transfer is charged to every link on it"
        % (sorted((link.a, link.b) for link in carried),))
    assert carried.get(switch8.link("r0", "r4")) == 400, (
        "the middle link r0-r4 carries %r bytes, not 400: only the first and "
        "last links of a route may not be charged"
        % (carried.get(switch8.link("r0", "r4")),))
    assert carried.get(switch8.link("r0", "r1")) == 800, (
        "the link r0-r1 carries %r bytes, not 400 + 400: a link's totals "
        "accumulate over the plan instead of overwriting"
        % (carried.get(switch8.link("r0", "r1")),))
    assert carried.get(switch8.link("r4", "r5")) == 400, (
        "the last link r4-r5 carries %r bytes, not 400"
        % (carried.get(switch8.link("r4", "r5")),))
    assert switch8.link("r2", "r3") not in carried, (
        "the link r2-r3, which the route never touches, carries %r bytes"
        % (carried.get(switch8.link("r2", "r3")),))

    # ---- bytes_per_rank: both ends, reduce included ------------------------

    handled = s.bytes_per_rank(fabric.ring(8), fabric.Plan(transfers=(
        fabric.send("r0", "r1", 100, 0),                    # 400 bytes
        fabric.send("r2", "r3", 200, 0, op="reduce"))))     # 800 bytes
    assert len(handled) == 8, (
        "bytes_per_rank reported %r ranks, not every rank of the topology"
        % (sorted(handled),))
    assert handled.get("r2") == 800 and handled.get("r3") == 800, (
        "the reduce transfer left sender r2 at %r and receiver r3 at %r, not "
        "800 each: a reduce is charged to both ends"
        % (handled.get("r2"), handled.get("r3")))
    assert handled.get("r0") == 400 and handled.get("r1") == 400, (
        "the send left sender r0 at %r and receiver r1 at %r, not 400 each"
        % (handled.get("r0"), handled.get("r1")))
    assert handled.get("r7") == 0, (
        "a rank the plan never touches is %r, not 0"
        % (handled.get("r7"),))
    assert sum(handled.values()) == 2400, (
        "the plan's ranks handled %r bytes in total, not 2 * (400 + 800): "
        "every transfer is charged to both ends"
        % (sum(handled.values()),))

    # ---- validate agrees with the provided checker -------------------------

    legal = fabric.Plan(transfers=(fabric.send("r0", "r1", 4, 0),
                                   fabric.send("r1", "r2", 4, 1)))
    assert fabric.legality_problems(ring4, legal) == (), (
        "the fixture is not legal: %r" % (fabric.legality_problems(ring4, legal),))
    assert s.validate(ring4, legal) is None, (
        "validate refused a legal plan: %r" % (s.validate(ring4, legal),))

    pair = fabric.Plan(transfers=(fabric.send("r0", "r1", 4, 0),
                                  fabric.send("r1", "r0", 4, 0)))
    assert fabric.legality_problems(ring4, pair) == (), (
        "the opposite-direction fixture is not legal: %r"
        % (fabric.legality_problems(ring4, pair),))
    assert s.validate(ring4, pair) is None, (
        "validate refused r0->r1 and r1->r0 in one step: links are full duplex, "
        "and the two directions are not a collision")

    ghost = fabric.Plan(transfers=(fabric.send("r0", "r9", 4, 0),))
    assert fabric.legality_problems(ring4, ghost) != (), (
        "the unknown-rank fixture is legal to the provided checker: %r"
        % (fabric.legality_problems(ring4, ghost),))
    message = _refuses(fabric, "a transfer naming an unknown rank",
                       lambda: s.validate(ring4, ghost))
    assert "r9" in message, (
        "the refusal of an unknown rank does not name it: %r" % (message,))

    unroutable = fabric.Plan(transfers=(fabric.send("r0", "r3", 4, 0),))
    assert fabric.legality_problems(disconnected, unroutable) != (), (
        "the unroutable fixture is legal to the provided checker: %r"
        % (fabric.legality_problems(disconnected, unroutable),))
    message = _refuses(fabric, "an unroutable transfer",
                       lambda: s.validate(disconnected, unroutable))
    assert "r3" in message or "rout" in message, (
        "the refusal of an unroutable transfer does not name it: %r" % (message,))

    crowded = fabric.Plan(transfers=(fabric.send("r0", "r2", 4, 0),
                                     fabric.send("r0", "r1", 4, 0)))
    assert fabric.legality_problems(ring4, crowded) != (), (
        "the duplicate-directed-link fixture is legal to the provided checker: "
        "%r" % (fabric.legality_problems(ring4, crowded),))
    message = _refuses(fabric, "two transfers on one directed link in a step",
                       lambda: s.validate(ring4, crowded))
    assert "step" in message or "direction" in message, (
        "the refusal of two transfers on one directed link does not name the "
        "step: %r" % (message,))

    middle = fabric.Plan(transfers=(fabric.send("r1", "r5", 4, 0),
                                    fabric.send("r2", "r4", 4, 0)))
    assert fabric.legality_problems(switch8, middle) != (), (
        "the middle-link fixture is legal to the provided checker: %r"
        % (fabric.legality_problems(switch8, middle),))
    message = _refuses(fabric, "two multi-hop transfers sharing a middle link",
                       lambda: s.validate(switch8, middle))
    assert "step" in message or "direction" in message, (
        "the refusal of a collision on an inner link does not name the step: "
        "%r" % (message,))

    # ---- validate's own rules, which the provided checker cannot carry -----

    message = _refuses(fabric, "a transfer to itself",
                       lambda: s.validate(ring4, _Plan((fabric.send("r0", "r0", 4, 0),))))
    assert "r0" in message, (
        "the refusal of a self-transfer does not name it: %r" % (message,))

    message = _refuses(fabric, "a zero-length transfer",
                       lambda: s.validate(ring4, _Plan((fabric.send("r0", "r1", 0, 0),))))
    assert "length" in message, (
        "the refusal of a zero length does not name the length: %r" % (message,))

    message = _refuses(fabric, "a negative offset",
                       lambda: s.validate(ring4, _Plan(
                           (fabric.send("r0", "r1", 4, 0, offset=-1),))))
    assert "offset" in message, (
        "the refusal of a negative offset does not name the offset: %r"
        % (message,))

    message = _refuses(fabric, "a slice past the end of the buffer",
                       lambda: s.validate(ring4, _Plan(
                           (fabric.send("r0", "r1", 4, 0),), length=2)))
    assert "slice" in message or "past" in message, (
        "the refusal of a slice past the buffer does not name the slice: %r"
        % (message,))
    assert s.validate(ring4, _Plan((fabric.send("r0", "r1", 4, 0),), length=4)) is None, (
        "validate refused a slice that exactly fills the buffer: %r"
        % (s.validate(ring4, _Plan((fabric.send("r0", "r1", 4, 0),), length=4)),))

    print("check_01: the cost model — a step is its slowest transfer, a plan the "
          "sum of its steps, a transfer its bytes and its hops, and validate "
          "agrees with the provided legality checker")

# --- stage 2 -----------------------------------------------------------------------
def check_2():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "interconnects-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import fabric
    import stage_01 as s1
    import stage_02 as s

    # ---- the ring: one transfer per step, one turn, N-1 steps --------------

    ring4 = fabric.ring(4)
    plan = s.broadcast_ring(ring4, "r0", 400)
    assert plan.steps() == (0, 1, 2), (
        "the ring broadcast of four ranks took steps %r, not the three of "
        "r0-r1, r1-r2, r2-r3: a ring has N-1 steps, one transfer each"
        % (plan.steps(),))
    assert len(plan.transfers) == 3, (
        "the ring broadcast placed %r transfers, not the three of a one-turn "
        "ring: sending counter-clockwise, or both ways, moves bytes that are "
        "already known" % (len(plan.transfers),))
    assert [(t.src, t.dst) for t in plan.at(0)] == [("r0", "r1")], (
        "the ring's first step is %r, not the root forwarding to its successor "
        "r0 -> r1: the ring must turn one way"
        % ([(t.src, t.dst) for t in plan.at(0)],))
    assert [(t.src, t.dst) for t in plan.at(1)] == [("r1", "r2")], (
        "the ring's second step is %r, not r1 -> r2: each rank forwards to its "
        "successor, not back to the root"
        % ([(t.src, t.dst) for t in plan.at(1)],))
    assert [(t.src, t.dst) for t in plan.at(2)] == [("r2", "r3")], (
        "the ring's last step is %r, not r2 -> r3"
        % ([(t.src, t.dst) for t in plan.at(2)],))
    assert all(t.length == 400 and t.offset == 0 and t.op == "send"
               for t in plan.transfers), (
        "a ring transfer moves %r, not the whole 400-element buffer at offset "
        "0: a hop forwards what it received"
        % ([(t.offset, t.length, t.op) for t in plan.transfers],))
    assert all(s1.hop_count(ring4, t.src, t.dst) == 1 for t in plan.transfers), (
        "a ring transfer is %r hops, not the one hop between neighbours"
        % ([s1.hop_count(ring4, t.src, t.dst) for t in plan.transfers],))
    assert all(s1.transfer_ticks(ring4, t) == 21 for t in plan.transfers), (
        "a ring transfer costs %r ticks, not 5 + ceil(1600/100) = 21: one hop "
        "of 100 bytes/tick and 5-tick latency"
        % ([s1.transfer_ticks(ring4, t) for t in plan.transfers],))
    assert fabric.legality_problems(ring4, plan) == (), (
        "the ring plan is illegal: %r" % (fabric.legality_problems(ring4, plan),))
    assert s1.plan_ticks(ring4, plan) == 63, (
        "the ring plan costs %r ticks, not 3 * 21 = 63"
        % (s1.plan_ticks(ring4, plan),))
    start = fabric.buffers(4, 400)
    out = fabric.run(ring4, plan, start)
    assert len(out) == 4 and all(out[rank] == start["r0"] for rank in out), (
        "after the ring broadcast %r ranks hold the root's buffer, not all "
        "four: %r"
        % (sum(1 for rank in out if out[rank] == start["r0"]),
           sorted(rank for rank in out if out[rank] != start["r0"])))

    # ---- the tree: one step per level, the informed set doubling -----------

    tree4 = fabric.tree(4)
    tree_plan = s.broadcast_tree(tree4, "r0", 400)
    assert tree_plan.steps() == (0, 1), (
        "the tree broadcast of four ranks took steps %r, not the two levels of "
        "the fabric tree: a level's sends share one step" % (tree_plan.steps(),))
    assert sorted((t.src, t.dst) for t in tree_plan.at(0)) == [
        ("r0", "r1"), ("r0", "r2")], (
        "the tree's first step is %r, not r0 -> r1 and r0 -> r2: the root's "
        "children learn together"
        % (sorted((t.src, t.dst) for t in tree_plan.at(0)),))
    assert [(t.src, t.dst) for t in tree_plan.at(1)] == [("r1", "r3")], (
        "the tree's second step is %r, not r1 -> r3: the level after the root "
        "forwards once each"
        % ([(t.src, t.dst) for t in tree_plan.at(1)],))
    assert len(tree_plan.transfers) == 3, (
        "the tree broadcast placed %r transfers, not the three a four-rank tree "
        "needs" % (len(tree_plan.transfers),))
    assert all(t.length == 400 and t.offset == 0 for t in tree_plan.transfers), (
        "a tree transfer moves %r, not the whole 400-element buffer: a node "
        "forwards what it received, not a parent's partial slice"
        % ([(t.offset, t.length) for t in tree_plan.transfers],))
    assert fabric.legality_problems(tree4, tree_plan) == (), (
        "the tree plan is illegal: %r"
        % (fabric.legality_problems(tree4, tree_plan),))
    assert s1.plan_ticks(tree4, tree_plan) == 42, (
        "the tree plan costs %r ticks, not 2 * 21 = 42" %
        (s1.plan_ticks(tree4, tree_plan),))
    assert len(tree_plan.steps()) < len(plan.steps()), (
        "the tree took %r steps and the ring %r at the same size: the tree must "
        "need fewer steps than the ring"
        % (len(tree_plan.steps()), len(plan.steps())))
    start = fabric.buffers(4, 400)
    out = fabric.run(tree4, tree_plan, start)
    assert len(out) == 4 and all(out[rank] == start["r0"] for rank in out), (
        "after the tree broadcast %r ranks hold the root's buffer, not all "
        "four: %r"
        % (sum(1 for rank in out if out[rank] == start["r0"]),
           sorted(rank for rank in out if out[rank] != start["r0"])))

    # ---- the switch: cheap in-group sends, an expensive spine step --------

    switch8 = fabric.switch(8, width=4)
    switch_plan = s.broadcast_tree(switch8, "r0", 400)
    assert switch_plan.steps() == (0, 1), (
        "the switch broadcast took steps %r, not the two levels of its "
        "breadth-first tree" % (switch_plan.steps(),))
    assert fabric.legality_problems(switch8, switch_plan) == (), (
        "the switch plan is illegal: %r"
        % (fabric.legality_problems(switch8, switch_plan),))
    near = [t for t in switch_plan.at(0) if t.dst == "r1"]
    assert len(near) == 1 and s1.transfer_ticks(switch8, near[0]) == 10, (
        "the in-group send r0 -> r1 costs %r ticks, not 2 + ceil(1600/200) = "
        "10: the NVLink side of the switch is cheap"
        % ([s1.transfer_ticks(switch8, t) for t in near],))
    cross = [t for t in switch_plan.at(0) if t.dst == "r4"]
    assert len(cross) == 1 and s1.transfer_ticks(switch8, cross[0]) == 84, (
        "the cross-group send r0 -> r4 costs %r ticks, not 20 + ceil(1600/25) "
        "= 84: the spine is 25 bytes per tick with a 20-tick latency"
        % ([s1.transfer_ticks(switch8, t) for t in cross],))
    assert s1.step_ticks(switch8, switch_plan, 0) == 84, (
        "the switch's first step costs %r ticks, not the 84 of its spine send"
        % (s1.step_ticks(switch8, switch_plan, 0),))
    assert s1.step_ticks(switch8, switch_plan, 1) == 10, (
        "the switch's second step costs %r ticks, not the 10 of an in-group "
        "send" % (s1.step_ticks(switch8, switch_plan, 1),))
    assert s1.plan_ticks(switch8, switch_plan) == 94, (
        "the switch plan costs %r ticks, not 84 + 10 = 94"
        % (s1.plan_ticks(switch8, switch_plan),))
    assert s1.step_ticks(switch8, switch_plan, 0) * 2 > s1.plan_ticks(
        switch8, switch_plan), (
        "the cross-group step (%r ticks) does not dominate the plan's %r ticks"
        % (s1.step_ticks(switch8, switch_plan, 0),
           s1.plan_ticks(switch8, switch_plan)))
    start = fabric.buffers(8, 400)
    out = fabric.run(switch8, switch_plan, start)
    assert len(out) == 8 and all(out[rank] == start["r0"] for rank in out), (
        "after the switch broadcast %r ranks hold the root's buffer, not all "
        "eight: %r"
        % (sum(1 for rank in out if out[rank] == start["r0"]),
           sorted(rank for rank in out if out[rank] != start["r0"])))

    # ---- a malformed request is refused -----------------------------------

    message = _refuses(fabric, "a ring broadcast from a rank the topology lacks",
                       lambda: s.broadcast_ring(ring4, "r9", 400))
    assert "r9" in message, (
        "the refusal of a ring root that is not a rank does not name it: %r"
        % (message,))
    message = _refuses(fabric, "a tree broadcast from a rank the topology lacks",
                       lambda: s.broadcast_tree(ring4, "r9", 400))
    assert "r9" in message, (
        "the refusal of a tree root that is not a rank does not name it: %r"
        % (message,))
    message = _refuses(fabric, "a broadcast of a zero length",
                       lambda: s.broadcast_ring(ring4, "r0", 0))
    assert "length" in message, (
        "the refusal of a zero length does not name the length: %r" % (message,))
    message = _refuses(fabric, "a broadcast of a negative length",
                       lambda: s.broadcast_tree(ring4, "r0", -1))
    assert "length" in message, (
        "the refusal of a negative length does not name the length: %r"
        % (message,))

    # ---- a topology the doubling cannot cover is refused ------------------

    disconnected = fabric.Topology(
        ranks=("r0", "r1", "r2", "r3"),
        links=(fabric.Link(a="r0", b="r1", bandwidth=100, latency=5),
               fabric.Link(a="r2", b="r3", bandwidth=100, latency=5)))
    message = _refuses(fabric, "a tree broadcast that cannot reach every rank",
                       lambda: s.broadcast_tree(disconnected, "r0", 4))
    assert "r2" in message or "r3" in message or "reach" in message, (
        "the refusal of an unreachable rank does not name it or the reach: %r"
        % (message,))

    print("check_02: the ring one turn per step for N-1 steps, the tree one "
          "level per step, and both legal — the switch's spine step is what the "
          "plan pays for")

# --- stage 3 -----------------------------------------------------------------------
def check_3():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "interconnects-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _steps_shared(plan):
        """Every rank that sends and receives inside one step of `plan`."""
        found = []
        for step in plan.steps():
            both = sorted({transfer.src for transfer in plan.at(step)}
                          & {transfer.dst for transfer in plan.at(step)})
            if both:
                found.append((step, both))
        return found

    import fabric
    import stage_01 as s1
    import stage_03 as s

    ring4 = fabric.ring(4)
    tree4 = fabric.tree(4)
    buffers = fabric.buffers(4, 400)
    total = fabric.reference(buffers, op="sum")

    # ---- the fixture numbers, recomputed and pinned -------------------------

    assert buffers["r3"] == tuple(4 * (j + 1) for j in range(400)), (
        "the fixture buffers are not the fabric's deterministic pattern: r3 "
        "holds %r" % (buffers["r3"][:3],))
    assert total == tuple(10 * (j + 1) for j in range(400)) and total[:3] == (10, 20, 30), (
        "the element-wise sum of four buffers is %r, not 10 * (j + 1): the "
        "reference the root must hold is wrong" % (total[:3],))

    # ---- the three refusals, for both plans ---------------------------------

    message = _refuses(fabric, "a root that is not a rank",
                       lambda: s.reduce_ring(ring4, "r9", 400))
    assert "r9" in message and "root" in message, (
        "the refusal of a root that is not a rank does not name the root: %r"
        % (message,))
    message = _refuses(fabric, "a root that is not a rank",
                       lambda: s.reduce_tree(ring4, "r9", 400))
    assert "r9" in message and "root" in message, (
        "the tree's refusal of a root that is not a rank does not name the "
        "root: %r" % (message,))

    message = _refuses(fabric, "a length below one",
                       lambda: s.reduce_ring(ring4, "r0", 0))
    assert "length" in message and "at least" in message, (
        "the refusal of a zero length does not name the length: %r" % (message,))
    message = _refuses(fabric, "a length below one",
                       lambda: s.reduce_tree(ring4, "r0", -1))
    assert "length" in message and "at least" in message, (
        "the tree's refusal of a negative length does not name the length: %r"
        % (message,))

    island = fabric.Topology(
        ranks=("r0", "r1", "r2"),
        links=(fabric.Link(a="r0", b="r1", bandwidth=100, latency=5),))
    message = _refuses(fabric, "a topology with no route to the root",
                       lambda: s.reduce_ring(island, "r0", 4))
    assert "root" in message and "r2" in message, (
        "the refusal of an unroutable rank does not name it or the root: %r"
        % (message,))
    message = _refuses(fabric, "a topology with no route to the root",
                       lambda: s.reduce_tree(island, "r0", 4))
    assert "root" in message and "r2" in message, (
        "the tree's refusal of an unroutable rank does not name it or the "
        "root: %r" % (message,))

    # ---- the ring: the accumulator walks, one hop per step ------------------

    plan = s.reduce_ring(ring4, "r0", 400)
    assert fabric.legality_problems(ring4, plan) == (), (
        "the ring reduce is not a plan the fabric can run: %r"
        % (fabric.legality_problems(ring4, plan),))
    assert plan.transfers == (
        fabric.send("r3", "r2", 400, 0, op="reduce"),
        fabric.send("r2", "r1", 400, 1, op="reduce"),
        fabric.send("r1", "r0", 400, 2, op="reduce")), (
        "the ring's messages are %r, not r3 -> r2, then r2 -> r1, then "
        "r1 -> r0: the accumulator must walk the ring's hops, root-1, root-2, "
        "… and land on the root on the last step"
        % ([(transfer.src, transfer.dst, transfer.step) for transfer in plan.transfers],))
    assert plan.steps() == (0, 1, 2), (
        "the ring reduce took the steps %r, not the N-1 = 3 one-hop steps the "
        "ring's three messages need" % (plan.steps(),))
    assert all(ring4.distance(transfer.src, transfer.dst) == 1
               for transfer in plan.transfers), (
        "a ring message crosses %r hops, not one: the ring's advantage over a "
        "gather is that every hop is one hop"
        % ([(transfer.src, transfer.dst, ring4.distance(transfer.src, transfer.dst))
            for transfer in plan.transfers
            if ring4.distance(transfer.src, transfer.dst) != 1],))
    assert all(plan.transfers[index].dst == plan.transfers[index + 1].src
               for index in range(len(plan.transfers) - 1)), (
        "the ring's messages are %r: each step's destination must be the next "
        "step's source, because that buffer is the accumulator"
        % ([(transfer.src, transfer.dst) for transfer in plan.transfers],))
    assert plan.transfers[-1].dst == "r0" and plan.transfers[0].src != "r0", (
        "the accumulator ends on %r after starting in %r, not on the root r0"
        % (plan.transfers[-1].dst, plan.transfers[0].src))
    assert sorted(transfer.src for transfer in plan.transfers) == ["r1", "r2", "r3"], (
        "the ring reduce's senders are %r, not each rank but the root exactly "
        "once" % (sorted(transfer.src for transfer in plan.transfers),))
    assert sorted(transfer.dst for transfer in plan.transfers) == ["r0", "r1", "r2"], (
        "the ring reduce's destinations are %r, not the root plus every rank "
        "the accumulator passes through"
        % (sorted(transfer.dst for transfer in plan.transfers),))
    assert all(transfer.op == "reduce" for transfer in plan.transfers), (
        "a ring hop copies instead of combining: %r"
        % ([transfer for transfer in plan.transfers if transfer.op != "reduce"],))
    assert _steps_shared(plan) == [], (
        "%r send and receive inside one step: the step is simultaneous, so the "
        "send carries the value the buffer held before the combine arrived"
        % (_steps_shared(plan),))

    assert [s1.step_ticks(ring4, plan, step) for step in plan.steps()] == [21, 21, 21], (
        "the ring's steps cost %r ticks, not three one-hop transfers of "
        "1600 bytes: 5 + ceil(1600 / 100) = 21 each"
        % ([s1.step_ticks(ring4, plan, step) for step in plan.steps()],))
    assert s1.plan_ticks(ring4, plan) == 63, (
        "the ring's chain costs %r ticks, not 21 + 21 + 21 = 63"
        % (s1.plan_ticks(ring4, plan),))
    star = fabric.Plan(transfers=(
        fabric.send("r1", "r0", 400, 0, op="reduce"),
        fabric.send("r2", "r0", 400, 1, op="reduce"),
        fabric.send("r3", "r0", 400, 2, op="reduce")))
    assert fabric.legality_problems(ring4, star) == (), (
        "the star fixture is not legal: %r"
        % (fabric.legality_problems(ring4, star),))
    assert s1.plan_ticks(ring4, star) == 84, (
        "the star gather of the same three buffers costs %r ticks, not "
        "21 + 42 + 21 = 84" % (s1.plan_ticks(ring4, star),))
    assert s1.plan_ticks(ring4, plan) != s1.plan_ticks(ring4, star), (
        "the chain and the star cost the same %r ticks: the chain must be "
        "cheaper, because its message from r2 crosses one hop where the star's "
        "crosses two" % (s1.plan_ticks(ring4, plan),))

    result = fabric.run(ring4, plan, buffers, op="sum")
    assert result["r0"] == total, (
        "the root came out %r, not the element-wise sum of the four buffers "
        "(%r): a rank's bytes were dropped, double-counted, or never forwarded"
        % (result["r0"][:3], total[:3]))
    assert result["r1"] == tuple(9 * (j + 1) for j in range(400)), (
        "r1 came out %r, not 9 * (j + 1) — r1's own buffer plus r2's combined "
        "with r3's: the accumulator must land in r1's buffer before r1 sends "
        "it" % (result["r1"][:3],))
    assert result["r2"] == tuple(7 * (j + 1) for j in range(400)), (
        "r2 came out %r, not 7 * (j + 1) — r2's own buffer plus r3's"
        % (result["r2"][:3],))
    assert result["r3"] == buffers["r3"], (
        "r3 came out %r instead of the buffer it started with (%r): r3 is the "
        "chain's first source and is never written"
        % (result["r3"][:3], buffers["r3"][:3]))

    # ---- the smallest ring fixtures, every rank's tuple by hand -------------

    small = fabric.buffers(4, 2)
    assert small == {"r0": (1, 2), "r1": (2, 4), "r2": (3, 6), "r3": (4, 8)}, (
        "the small fixture's buffers are %r, not the fabric's pattern"
        % (small,))
    assert fabric.reference(small) == (10, 20), (
        "the small fixture's sum is %r, not (10, 20)" % (fabric.reference(small),))
    plan = s.reduce_ring(ring4, "r0", 2)
    assert fabric.run(ring4, plan, small, op="sum") == {
        "r0": (10, 20), "r1": (9, 18), "r2": (7, 14), "r3": (4, 8)}, (
        "the ring reduce of two-element buffers left %r, not r0 = r0+r1+r2+r3 "
        "= (10, 20) with r1 = (9, 18) and r2 = (7, 14) holding the partials "
        "they forwarded and r3 = (4, 8) untouched"
        % (fabric.run(ring4, plan, small, op="sum"),))

    tiny = fabric.buffers(4, 1)
    plan = s.reduce_ring(ring4, "r0", 1)
    assert [transfer.length for transfer in plan.transfers] == [1, 1, 1], (
        "a one-element reduce carries %r elements per message, not one: the "
        "smallest buffer is refused or resized"
        % ([transfer.length for transfer in plan.transfers],))
    assert fabric.run(ring4, plan, tiny, op="sum") == {
        "r0": (10,), "r1": (9,), "r2": (7,), "r3": (4,)}, (
        "the one-element ring reduce left %r, not (10,), (9,), (7,), (4,)"
        % (fabric.run(ring4, plan, tiny, op="sum"),))
    plan = s.reduce_tree(tree4, "r0", 1)
    assert fabric.run(tree4, plan, tiny, op="sum")["r0"] == fabric.reference(tiny) == (10,), (
        "the one-element tree reduce left the root at %r, not the sum of "
        "1 + 2 + 3 + 4 = 10" % (fabric.run(tree4, plan, tiny, op="sum")["r0"],))

    # ---- min and max, from a root that is not the first rank ----------------

    plan = s.reduce_ring(ring4, "r2", 400)
    assert plan.steps() == (0, 1, 2), (
        "the ring reduce with root r2 took the steps %r, not 3" % (plan.steps(),))
    assert plan.transfers == (
        fabric.send("r1", "r0", 400, 0, op="reduce"),
        fabric.send("r0", "r3", 400, 1, op="reduce"),
        fabric.send("r3", "r2", 400, 2, op="reduce")), (
        "the ring's messages with root r2 are %r, not r1 -> r0, r0 -> r3, "
        "r3 -> r2: the chain starts one rank before the root in the ring's "
        "order, not at the root's successor"
        % ([(transfer.src, transfer.dst, transfer.step) for transfer in plan.transfers],))

    small_plan = s.reduce_ring(ring4, "r2", 2)
    lowest = fabric.run(ring4, small_plan, small, op="min")
    assert lowest == {"r0": (1, 2), "r1": (2, 4), "r2": (1, 2), "r3": (1, 2)}, (
        "the min fold left %r, not r2 = (1, 2) with every rank the accumulator "
        "passed through holding the smallest pair it relayed" % (lowest,))
    assert fabric.run(ring4, plan, buffers, op="min")["r2"] == fabric.reference(buffers, op="min"), (
        "the root's min is %r, not the smallest element over every rank (%r): "
        "the chain combined with something other than the caller's op"
        % (fabric.run(ring4, plan, buffers, op="min")["r2"][:3],
           fabric.reference(buffers, op="min")[:3]))
    assert fabric.run(ring4, plan, buffers, op="min")["r2"] == buffers["r0"] == tuple(1 * (j + 1) for j in range(400)), (
        "the min of four buffers should be r0's buffer (1 * (j + 1)), not %r"
        % (fabric.run(ring4, plan, buffers, op="min")["r2"][:3],))

    highest = fabric.run(ring4, small_plan, small, op="max")
    assert highest == {"r0": (2, 4), "r1": (2, 4), "r2": (4, 8), "r3": (4, 8)}, (
        "the max fold left %r, not r2 = (4, 8) with r0 and r3 holding the "
        "largest pair they relayed" % (highest,))
    assert fabric.run(ring4, plan, buffers, op="max")["r2"] == fabric.reference(buffers, op="max") == buffers["r3"], (
        "the root's max is %r, not the largest element over every rank (%r)"
        % (fabric.run(ring4, plan, buffers, op="max")["r2"][:3],
           fabric.reference(buffers, op="max")[:3]))
    assert lowest["r2"] != highest["r2"] and lowest["r2"] != total, (
        "the min (%r), the max (%r) and the sum (%r) of the four buffers are "
        "not three different tuples: the chain is not reading the buffers"
        % (lowest["r2"][:3], highest["r2"][:3], total[:3]))

    # ---- the tree: level by level, deepest first ----------------------------

    plan = s.reduce_tree(tree4, "r0", 400)
    assert fabric.legality_problems(tree4, plan) == (), (
        "the tree reduce is not a plan the fabric can run: %r"
        % (fabric.legality_problems(tree4, plan),))
    assert plan.steps() == (0, 1), (
        "the tree reduce took the steps %r, not the two its two levels need"
        % (plan.steps(),))
    assert plan.at(0) == (fabric.send("r3", "r1", 400, 0, op="reduce"),), (
        "the tree's first step is %r, not the deepest level's message "
        "r3 -> r1 alone" % (plan.at(0),))
    assert plan.at(1) == (fabric.send("r1", "r0", 400, 1, op="reduce"),
                          fabric.send("r2", "r0", 400, 1, op="reduce")), (
        "the tree's second step is %r, not r1 -> r0 and r2 -> r0 in parallel"
        % (plan.at(1),))
    assert all(tree4.distance(transfer.dst, "r0")
               == tree4.distance(transfer.src, "r0") - 1
               for transfer in plan.transfers), (
        "a tree message does not move one level toward the root: %r"
        % ([(transfer.src, transfer.dst) for transfer in plan.transfers
            if tree4.distance(transfer.dst, "r0")
            != tree4.distance(transfer.src, "r0") - 1],))
    assert all(transfer.op == "reduce" for transfer in plan.transfers), (
        "a tree message copies instead of combining: %r"
        % ([transfer for transfer in plan.transfers if transfer.op != "reduce"],))
    assert _steps_shared(plan) == [], (
        "%r send and receive inside one step: a parent that forwards in the "
        "step its children arrive in forwards the value it held before them"
        % (_steps_shared(plan),))
    assert s1.plan_ticks(tree4, plan) == 42, (
        "the tree reduce's plan costs %r ticks, not the two steps' 21 + 21 = 42"
        % (s1.plan_ticks(tree4, plan),))

    result = fabric.run(tree4, plan, buffers, op="sum")
    assert result["r0"] == total, (
        "the tree's root came out %r, not the element-wise sum of the four "
        "buffers (%r)" % (result["r0"][:3], total[:3]))
    assert result["r1"] == tuple(6 * (j + 1) for j in range(400)), (
        "r1 came out %r, not 6 * (j + 1) — r1's own buffer plus r3's: the "
        "parent must hold its subtree's sum before it forwards it"
        % (result["r1"][:3],))
    assert result["r2"] == buffers["r2"] and result["r3"] == buffers["r3"], (
        "the tree left r2 at %r and r3 at %r instead of the buffers they "
        "started with (%r, %r): only a rank with children is written"
        % (result["r2"][:3], result["r3"][:3], buffers["r2"][:3], buffers["r3"][:3]))

    assert fabric.run(tree4, s.reduce_tree(tree4, "r0", 2), small, op="sum") == {
        "r0": (10, 20), "r1": (6, 12), "r2": (3, 6), "r3": (4, 8)}, (
        "the two-element tree reduce left %r, not r1 = (6, 12) = r1 + r3 and "
        "r0 = (10, 20) = r0 + r1 + r2 + r3"
        % (fabric.run(tree4, s.reduce_tree(tree4, "r0", 2), small, op="sum"),))

    # ---- a deeper tree, a two-level fabric, and a lone rank -----------------

    tree7 = fabric.tree(7)
    seven = fabric.buffers(7, 12)
    plan = s.reduce_tree(tree7, "r0", 12)
    assert fabric.legality_problems(tree7, plan) == (), (
        "the deeper tree's plan is not legal: %r"
        % (fabric.legality_problems(tree7, plan),))
    assert plan.steps() == (0, 1), (
        "the tree of seven ranks took the steps %r, not the two its two levels "
        "need" % (plan.steps(),))
    assert plan.at(0) == (fabric.send("r3", "r1", 12, 0, op="reduce"),
                          fabric.send("r4", "r1", 12, 0, op="reduce"),
                          fabric.send("r5", "r2", 12, 0, op="reduce"),
                          fabric.send("r6", "r2", 12, 0, op="reduce")), (
        "the tree's deepest level is %r, not the four leaves sending to their "
        "parents in one step" % (plan.at(0),))
    result = fabric.run(tree7, plan, seven, op="sum")
    assert result["r0"] == fabric.reference(seven, op="sum"), (
        "the tree of seven ranks left the root at %r, not 28 * (j + 1), the "
        "combination of seven buffers" % (result["r0"][:3],))
    assert [result["r1"][0], result["r2"][0]] == [11, 16], (
        "the tree of seven ranks left r1 at %r and r2 at %r, not 11 and 16: "
        "each parent holds its own buffer plus its children's"
        % (result["r1"][0], result["r2"][0]))
    for rank in ("r3", "r4", "r5", "r6"):
        assert result[rank] == seven[rank], (
            "the tree of seven ranks left leaf %r at %r instead of its own "
            "buffer (%r)" % (rank, result[rank][:3], seven[rank][:3]))

    switch8 = fabric.switch(8, width=4)
    eight = fabric.buffers(8, 7)
    plan = s.reduce_tree(switch8, "r5", 7)
    assert fabric.legality_problems(switch8, plan) == (), (
        "the switch fabric's plan is not legal: %r"
        % (fabric.legality_problems(switch8, plan),))
    assert _steps_shared(plan) == [], (
        "the two-level fabric's plan has %r sending and receiving in one step"
        % (_steps_shared(plan),))
    result = fabric.run(switch8, plan, eight, op="sum")
    assert result["r5"] == fabric.reference(eight, op="sum") == tuple(36 * (j + 1) for j in range(7)), (
        "on the two-level fabric the root came out %r, not the combination of "
        "eight buffers (36 * (j + 1))" % (result["r5"][:3],))
    assert [result["r0"][0], result["r4"][0]] == [10, 15], (
        "the two-level fabric left r0 at %r and r4 at %r, not 10 and 15: each "
        "port holds its group's sum before it forwards it"
        % (result["r0"][0], result["r4"][0]))
    for rank in ("r1", "r2", "r3", "r6", "r7"):
        assert result[rank] == eight[rank], (
            "the two-level fabric left leaf %r at %r instead of its own buffer "
            "(%r)" % (rank, result[rank][:3], eight[rank][:3]))

    lone = fabric.full(1)
    one = fabric.buffers(1, 5)
    assert s.reduce_ring(lone, "r0", 5).transfers == (), (
        "a lone rank's ring reduce is %r, not the empty plan: there is no other "
        "rank to combine" % (s.reduce_ring(lone, "r0", 5).transfers,))
    assert s.reduce_tree(lone, "r0", 5).transfers == (), (
        "a lone rank's tree reduce is %r, not the empty plan"
        % (s.reduce_tree(lone, "r0", 5).transfers,))
    assert fabric.run(lone, s.reduce_ring(lone, "r0", 5), one) == one, (
        "a lone rank's reduce changed the only buffer there was")

    # ---- what the accumulator's step boundary is worth ----------------------

    pipelined = fabric.Plan(transfers=(
        fabric.send("r3", "r2", 2, 0, op="reduce"),
        fabric.send("r2", "r1", 2, 0, op="reduce"),
        fabric.send("r1", "r0", 2, 0, op="reduce")))
    assert fabric.legality_problems(ring4, pipelined) == (), (
        "the pipelined-chain fixture is not legal: %r"
        % (fabric.legality_problems(ring4, pipelined),))
    assert fabric.run(ring4, pipelined, small, op="sum") == {
        "r0": (3, 6), "r1": (5, 10), "r2": (7, 14), "r3": (4, 8)}, (
        "a step is simultaneous, so a relay must forward what it held at the "
        "step's start: the one-step chain answers the root with %r, not the "
        "combination (10, 20), and %r is what the whole run leaves"
        % (fabric.run(ring4, pipelined, small, op="sum")["r0"],
           fabric.run(ring4, pipelined, small, op="sum")))

    both = fabric.Plan(transfers=(
        fabric.send("r1", "r0", 2, 0, op="reduce"),
        fabric.send("r0", "r2", 2, 0, op="reduce")))
    assert fabric.legality_problems(ring4, both) == (), (
        "the fixture where one rank both sends and receives is not legal: %r"
        % (fabric.legality_problems(ring4, both),))
    assert fabric.run(ring4, both, small, op="sum") == {
        "r0": (3, 6), "r1": (2, 4), "r2": (4, 8), "r3": (4, 8)}, (
        "r0 sends its buffer to r2 and receives r1's combine in the same step: "
        "r2 must get the value r0 held at the step's start, (1, 2), not the "
        "combined (3, 6), so the result is %r"
        % (fabric.run(ring4, both, small, op="sum"),))

    early = fabric.Plan(transfers=(
        fabric.send("r3", "r1", 2, 0, op="reduce"),
        fabric.send("r1", "r0", 2, 0, op="reduce"),
        fabric.send("r2", "r0", 2, 1, op="reduce")))
    assert fabric.legality_problems(tree4, early) == (), (
        "the tree fixture where a parent forwards too early is not legal: %r"
        % (fabric.legality_problems(tree4, early),))
    assert fabric.run(tree4, early, small, op="sum") == {
        "r0": (6, 12), "r1": (6, 12), "r2": (3, 6), "r3": (4, 8)}, (
        "a tree whose parent forwards in the step its child arrives forwards "
        "the value it held before the combine: the root gets %r, not the "
        "combination (10, 20), and r3's bytes never reach it"
        % (fabric.run(tree4, early, small, op="sum")["r0"],))

    copies = fabric.Plan(transfers=(
        fabric.send("r3", "r2", 2, 0, op="send"),
        fabric.send("r2", "r1", 2, 1, op="send"),
        fabric.send("r1", "r0", 2, 2, op="send")))
    assert fabric.run(ring4, copies, small, op="sum")["r0"] == (4, 8) != fabric.reference(small), (
        "a chain whose hops copy leaves the root holding the last source's "
        "buffer (%r), not the combination (%r): every hop overwrote the data "
        "it landed on"
        % (fabric.run(ring4, copies, small, op="sum")["r0"], fabric.reference(small)))

    seeded = fabric.Plan(transfers=(
        fabric.send("r1", "r0", 2, 0, op="send"),
        fabric.send("r2", "r0", 2, 1, op="reduce"),
        fabric.send("r3", "r0", 2, 2, op="reduce")))
    assert fabric.run(ring4, seeded, small, op="sum")["r0"] == (9, 18) != fabric.reference(small), (
        "an accumulator seeded with r1's buffer answers the sum with %r, not "
        "the combination (10, 20): the root's own contribution is gone"
        % (fabric.run(ring4, seeded, small, op="sum")["r0"],))
    assert fabric.run(ring4, seeded, small, op="min")["r0"] == small["r1"] != fabric.reference(small, op="min"), (
        "an accumulator seeded with r1's buffer answers the min with %r, not "
        "the smallest element over every rank (%r): the fold started from the "
        "wrong identity"
        % (fabric.run(ring4, seeded, small, op="min")["r0"],
           fabric.reference(small, op="min")))

    doubled = fabric.Plan(transfers=(
        fabric.send("r0", "r1", 2, 0, op="send"),
        fabric.send("r1", "r0", 2, 1, op="reduce")))
    assert fabric.run(ring4, doubled, small, op="sum")["r0"] == (2, 4) != fabric.reference(small), (
        "the root's own buffer went around and came back, so it was combined "
        "twice: the root holds %r, not (10, 20)"
        % (fabric.run(ring4, doubled, small, op="sum")["r0"],))

    broken = fabric.Plan(transfers=(
        fabric.send("r3", "r2", 2, 0, op="reduce"),
        fabric.send("r1", "r0", 2, 1, op="reduce")))
    assert fabric.run(ring4, broken, small, op="sum") == {
        "r0": (3, 6), "r1": (2, 4), "r2": (7, 14), "r3": (4, 8)}, (
        "a chain that drops the hop out of r2 leaves the root at %r, not the "
        "combination (10, 20): r2's buffer never reaches it"
        % (fabric.run(ring4, broken, small, op="sum")["r0"],))

    root = fabric.run(ring4, s.reduce_ring(ring4, "r0", 400), buffers, op="sum")["r0"]
    mean = tuple(total[j] // 4 for j in range(400))
    assert mean != total, (
        "the mean %r and the sum %r are the same tuple: the fixture is "
        "degenerate" % (mean[:3], total[:3]))
    assert root == total != mean and root != buffers["r3"], (
        "the root holds %r, not the mean %r or the last source's buffer %r: a "
        "collective reduces, the caller averages"
        % (root[:3], mean[:3], buffers["r3"][:3]))

    print("check_03: the two reduce plans — the accumulator walks the ring one "
          "hop per step and the tree's levels deepest first, each rank it "
          "passes through holds the partial sum it relayed, and the root lands "
          "on fabric.reference")

# --- stage 4 -----------------------------------------------------------------------
def check_4():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "interconnects-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import fabric
    import stage_01 as s1
    import stage_04 as s

    ring4 = fabric.ring(4)
    ranks = ring4.ranks
    n = len(ranks)
    length = 12
    chunks = 4
    size = length // chunks
    bufs = fabric.buffers(n, length)
    ref = fabric.reference(bufs)

    # ---- the all-reduce: 2(N-1) steps, and every rank with the reference ----

    plan = s.all_reduce_ring(ring4, length, chunks=chunks)
    assert fabric.legality_problems(ring4, plan) == (), (
        "the all-reduce plan is illegal: %r"
        % (fabric.legality_problems(ring4, plan),))
    assert plan.steps() == tuple(range(2 * (n - 1))), (
        "the all-reduce steps are %r, not 0 .. 2(N-1)-1 = %r: the reduce-scatter "
        "and the all-gather in sequence, with no empty step"
        % (plan.steps(), tuple(range(2 * (n - 1)))))
    assert len(plan.steps()) == 2 * (n - 1) == 6, (
        "the all-reduce is %r steps, not 2(N-1) = 6" % (len(plan.steps()),))
    assert {transfer.length for transfer in plan.transfers} == {size}, (
        "the all-reduce moves transfers of length %r, not one chunk of %d "
        "elements: every rank sends one chunk per step, not the whole buffer"
        % (sorted({transfer.length for transfer in plan.transfers}), size))
    got = fabric.run(ring4, plan, bufs)
    for rank in ranks:
        assert got[rank] == ref, (
            "rank %s ends with %r, not the all-reduced %r: every rank holds the "
            "combination of every rank's buffer" % (rank, got[rank], ref))

    # ---- bytes per rank: 2 * length * (N-1) // N in, and the same out -------

    per_direction = 2 * length * (n - 1) // n
    handled = s1.bytes_per_rank(ring4, plan)
    for rank in ranks:
        assert handled[rank] == 2 * per_direction * fabric.ELEMENT_BYTES, (
            "rank %s handled %r bytes, not 2 * %d elements * %d bytes: each "
            "rank sends and receives 2 * length * (N-1) // N elements"
            % (rank, handled[rank], per_direction, fabric.ELEMENT_BYTES))

    # ---- the same plan under another combining op ---------------------------

    plan_min = s.all_reduce_ring(ring4, length, chunks=chunks, op="min")
    assert plan_min.transfers == plan.transfers, (
        "op='min' produced a different plan: the layout of a ring does not "
        "depend on the combining operation, which the plan does not carry")
    got_min = fabric.run(ring4, plan_min, bufs, op="min")
    ref_min = fabric.reference(bufs, op="min")
    for rank in ranks:
        assert got_min[rank] == ref_min, (
            "with op='min' rank %s ends with %r, not the all-reduced %r"
            % (rank, got_min[rank], ref_min))

    # ---- chunks=None is one chunk per rank, not one chunk -------------------

    default = s.all_reduce_ring(ring4, length)
    assert default.transfers == plan.transfers, (
        "chunks=None does not equal chunks=%d: the default is one chunk per "
        "rank, not a single chunk of the whole buffer" % (chunks,))
    got_default = fabric.run(ring4, default, bufs)
    for rank in ranks:
        assert got_default[rank] == ref, (
            "with chunks=None rank %s ends with %r, not the all-reduced %r"
            % (rank, got_default[rank], ref))

    # ---- a cheaper plan must still be right ---------------------------------

    small = s.all_reduce_ring(ring4, length, chunks=2)
    assert fabric.legality_problems(ring4, small) == (), (
        "the two-chunk all-reduce plan is illegal: %r"
        % (fabric.legality_problems(ring4, small),))
    assert small.steps() == tuple(range(2 * (n - 1))), (
        "the two-chunk all-reduce steps are %r, not 0 .. 2(N-1)-1" % (small.steps(),))
    assert len(small.steps()) == 2 * (n - 1) == 6, (
        "the two-chunk all-reduce is %r steps, not 2(N-1) = 6: fewer, larger "
        "chunks change the transfer size, not the step count"
        % (len(small.steps()),))
    assert {transfer.length for transfer in small.transfers} == {length // 2}, (
        "the two-chunk all-reduce moves transfers of length %r, not %d: the "
        "buffer is cut into two equal chunks, and a cheaper plan must still "
        "move the data"
        % (sorted({transfer.length for transfer in small.transfers}), length // 2))
    got_small = fabric.run(ring4, small, bufs)
    for rank in ranks:
        assert got_small[rank] == ref, (
            "the two-chunk all-reduce leaves rank %s with %r, not the "
            "all-reduced %r: a plan that is cheaper and wrong fails here"
            % (rank, got_small[rank], ref))

    # ---- the refusals -------------------------------------------------------

    _refuses(fabric, "a chunks that does not divide length",
             lambda: s.all_reduce_ring(ring4, 10, chunks=4))
    _refuses(fabric, "a single chunk",
             lambda: s.all_reduce_ring(ring4, 12, chunks=1))
    _refuses(fabric, "more chunks than ranks",
             lambda: s.all_reduce_ring(ring4, 16, chunks=8))
    _refuses(fabric, "reduce_scatter_ring with more chunks than ranks",
             lambda: s.reduce_scatter_ring(ring4, 16, chunks=8))
    _refuses(fabric, "an op that is neither a transfer op nor a combining op",
             lambda: s.all_reduce_ring(ring4, 12, op="average"))
    _refuses(fabric, "a transfer op taken for a combining op",
             lambda: s.all_reduce_ring(ring4, 12, op="send"))
    _refuses(fabric, "reduce_scatter_ring with a chunks that does not divide length",
             lambda: s.reduce_scatter_ring(ring4, 10, chunks=4))
    _refuses(fabric, "all_gather_ring with a single chunk",
             lambda: s.all_gather_ring(ring4, 12, chunks=1))

    # ---- the reduce-scatter half alone --------------------------------------

    rs = s.reduce_scatter_ring(ring4, length, chunks=chunks)
    assert fabric.legality_problems(ring4, rs) == (), (
        "reduce_scatter_ring's plan is illegal: %r"
        % (fabric.legality_problems(ring4, rs),))
    assert rs.steps() == tuple(range(n - 1)), (
        "reduce_scatter_ring's steps are %r, not 0 .. N-2" % (rs.steps(),))
    assert {transfer.op for transfer in rs.transfers} == {"reduce"}, (
        "reduce_scatter_ring moves %r transfers: the scatter half combines into "
        "the destination with op='reduce'"
        % (sorted({transfer.op for transfer in rs.transfers}),))
    mid = fabric.run(ring4, rs, bufs)
    for index, rank in enumerate(ranks):
        start = index * size
        own = slice(start, start + size)
        assert mid[rank][own] == ref[own], (
            "after reduce_scatter_ring rank %s holds %r for its own chunk, not "
            "the reduced %r: rank r owns the fully reduced chunk r"
            % (rank, mid[rank][own], ref[own]))
        for other in range(n):
            if other == index:
                continue
            other_slice = slice(other * size, (other + 1) * size)
            assert mid[rank][other_slice] != ref[other_slice], (
                "after reduce_scatter_ring rank %s already holds chunk %d fully "
                "reduced: only chunk %d is complete, every other is partial"
                % (rank, other, index))

    # ---- the all-gather half alone, on the reduced chunks -------------------

    ag = s.all_gather_ring(ring4, length, chunks=chunks)
    assert fabric.legality_problems(ring4, ag) == (), (
        "all_gather_ring's plan is illegal: %r"
        % (fabric.legality_problems(ring4, ag),))
    assert ag.steps() == tuple(range(n - 1)), (
        "all_gather_ring's steps are %r, not 0 .. N-2" % (ag.steps(),))
    assert {transfer.op for transfer in ag.transfers} == {"send"}, (
        "all_gather_ring moves %r transfers: the gather half copies with "
        "op='send' and must not re-reduce chunks already reduced"
        % (sorted({transfer.op for transfer in ag.transfers}),))
    gathered = fabric.run(ring4, ag, mid)
    for rank in ranks:
        assert gathered[rank] == ref, (
            "after all_gather_ring rank %s holds %r, not every reduced chunk "
            "%r: the gather must reach every rank" % (rank, gathered[rank], ref))

    print("check_04: the ring all-reduce — the buffer cut into chunks and "
          "pipelined, reduce-scatter then all-gather, 2(N-1) steps and every "
          "rank with the reference")

# --- stage 5 -----------------------------------------------------------------------
def check_5():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "interconnects-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import fabric
    import stage_01 as s1
    import stage_04 as s4
    import stage_05 as s

    E = fabric.ELEMENT_BYTES
    ORDER = ("ring", "tree", "doubling")

    def built(topology, size, algorithm, op="reduce"):
        if algorithm == "ring":
            return s4.all_reduce_ring(topology, size, op=op)
        if algorithm == "tree":
            return s.all_reduce_tree(topology, size, op=op)
        return s.all_reduce_doubling(topology, size, op=op)

    def ticks(topology, plan):
        return s1.plan_ticks(topology, plan)

    def available(topology, size):
        """The algorithms that can be built, and their tick counts."""
        out = {}
        for name in ORDER:
            try:
                plan = built(topology, size, name)
            except fabric.FabricError:
                continue
            out[name] = ticks(topology, plan)
        return out

    # ---- the tree walks the topology's own tree: 2 * levels steps ----------

    tree7 = fabric.tree(7)
    length = 8
    n = len(tree7.ranks)
    bufs = fabric.buffers(n, length)
    ref = fabric.reference(bufs)
    root = tree7.ranks[0]
    levels = max(len(tree7.path(rank, root)) - 1 for rank in tree7.ranks)
    assert levels == 2, (
        "the fixture's tree(7) has %r levels, not the two hops r3-r1-r0" % (levels,))

    plan = s.all_reduce_tree(tree7, length)
    assert fabric.legality_problems(tree7, plan) == (), (
        "the tree plan is illegal: %r" % (fabric.legality_problems(tree7, plan),))
    assert plan.steps() == tuple(range(2 * levels)), (
        "the tree's steps are %r, not 0 .. 2*levels-1 = 4: a reduce up the tree "
        "and a broadcast back down" % (plan.steps(),))
    assert len(plan.steps()) == 2 * levels == 4, (
        "the tree is %r steps, not 2 * levels = 4: the tree's step count is two "
        "per level, the reduce half then the broadcast half"
        % (len(plan.steps()),))
    assert {transfer.length for transfer in plan.transfers} == {length}, (
        "the tree moves transfers of length %r, not the whole buffer of %d "
        "elements: every rank sends its accumulator up and the sum down"
        % (sorted({transfer.length for transfer in plan.transfers}), length))

    got = fabric.run(tree7, plan, bufs)
    for rank in tree7.ranks:
        assert got[rank] == ref, (
            "rank %s ends with %r, not the all-reduced %r: the reduce must "
            "reach the root and the broadcast must reach every rank"
            % (rank, got[rank], ref))

    # ---- the tree's byte facts: S(N-1) up, S(N-1) down, not one message ----

    up_elements = sum(transfer.length for transfer in plan.transfers
                      if transfer.step < levels)
    down_elements = sum(transfer.length for transfer in plan.transfers
                        if transfer.step >= levels)
    assert up_elements == length * (n - 1) == 48, (
        "the reduce half moves %r elements, not S(N-1) = 48: every rank but the "
        "root sends its whole buffer to its parent once"
        % (up_elements,))
    assert down_elements == length * (n - 1) == 48, (
        "the broadcast half moves %r elements, not S(N-1) = 48: every rank but "
        "the root receives the sum once, and the root sends to each child"
        % (down_elements,))
    assert plan.elements_moved() == 2 * length * (n - 1) == 96, (
        "the tree moves %r elements on the network, not about 2*S(N-1) = 96: "
        "few steps, but every level moves the payload again"
        % (plan.elements_moved(),))

    handled = s1.bytes_per_rank(tree7, plan)
    for rank in ("r3", "r4", "r5", "r6"):
        sends = plan.outgoing(rank)
        assert len(sends) == 1 and sends[0].length == length, (
            "leaf %s sends %r, not one transfer of the whole buffer S: a leaf "
            "has no children and sends only its own accumulator up"
            % (rank, [(t.dst, t.length) for t in sends]))
        assert handled[rank] == 2 * length * E == 64, (
            "leaf %s handles %r bytes, not 2*S elements = 64: it sends S up and "
            "receives S down, and the per-rank figure is not S"
            % (rank, handled[rank]))
    root_up_sends = [t for t in plan.outgoing(root) if t.step < levels]
    assert root_up_sends == [], (
        "the root sends %r in the reduce half: it is the top of the up phase, "
        "and only the ranks below it send"
        % ([(t.dst, t.step) for t in root_up_sends],))
    root_down_sends = plan.outgoing(root)
    assert len(root_down_sends) == 2 and {t.dst for t in root_down_sends} == {"r1", "r2"}, (
        "the root sends %r in the broadcast half, not one S-sized transfer to "
        "each of its children r1 and r2"
        % ([(t.dst, t.length) for t in root_down_sends],))
    assert handled[root] == 4 * length * E == 128, (
        "the root handles %r bytes, not 4*S elements = 128: it receives two "
        "buffers up and sends two copies of the sum down"
        % (handled[root],))
    assert handled["r1"] == 6 * length * E == 192, (
        "the interior rank r1 handles %r bytes, not 6*S elements = 192: two "
        "children up, one buffer up, one buffer down, two children down"
        % (handled["r1"],))
    link = s1.bytes_by_link(tree7, plan)
    assert link[tree7.link("r0", "r1")] == 2 * length * E == 64, (
        "the link r0-r1 carries %r bytes, not 2*S elements = 64: the buffer goes "
        "up it once and the sum comes down it once"
        % (link[tree7.link("r0", "r1")],))

    # ---- the same tree on a different fabric: the steps follow the levels --

    ring8 = fabric.ring(8)
    ring_levels = max(len(ring8.path(rank, ring8.ranks[0])) - 1 for rank in ring8.ranks)
    ring_plan = s.all_reduce_tree(ring8, length)
    assert fabric.legality_problems(ring8, ring_plan) == (), (
        "the tree plan on ring(8) is illegal: %r"
        % (fabric.legality_problems(ring8, ring_plan),))
    assert len(ring_plan.steps()) == 2 * ring_levels == 8, (
        "the tree on ring(8) is %r steps, not 2*levels = 8: levels is the "
        "largest hop distance to the root, four on a ring of eight"
        % (len(ring_plan.steps()),))
    assert ring_plan.elements_moved() == 2 * length * (len(ring8.ranks) - 1) == 112, (
        "the tree on ring(8) moves %r elements, not 2*S(N-1) = 112"
        % (ring_plan.elements_moved(),))
    ring_got = fabric.run(ring8, ring_plan, fabric.buffers(8, length))
    assert all(ring_got[rank] == fabric.reference(fabric.buffers(8, length))
               for rank in ring8.ranks), (
        "the tree on ring(8) does not leave every rank with the reference")

    # ---- doubling: log2(N) steps, S per rank per step ----------------------

    full8 = fabric.full(8)
    n8 = len(full8.ranks)
    steps = 0
    while (1 << steps) < n8:
        steps += 1
    assert steps == 3, "the fixture's N is %r, whose log2 is not three" % (n8,)

    double = s.all_reduce_doubling(full8, length)
    assert fabric.legality_problems(full8, double) == (), (
        "the doubling plan on full(8) is illegal: %r"
        % (fabric.legality_problems(full8, double),))
    assert double.steps() == tuple(range(steps)), (
        "the doubling's steps are %r, not 0 .. log2(N)-1 = 3" % (double.steps(),))
    assert len(double.steps()) == steps == 3, (
        "the doubling runs %r steps, not log2(N) = 3"
        % (len(double.steps()),))
    assert {transfer.length for transfer in double.transfers} == {length}, (
        "the doubling moves transfers of length %r, not the whole buffer of %d "
        "elements: each rank sends S, not half of it"
        % (sorted({transfer.length for transfer in double.transfers}), length))
    for k in range(steps):
        span = 1 << k
        want = {(rank, full8.ranks[index ^ span])
                for index, rank in enumerate(full8.ranks)}
        have = {(t.src, t.dst) for t in double.at(k)}
        assert have == want, (
            "step %d exchanges %r, not every rank with the rank `r XOR %d`: the "
            "butterfly pairs a rank with its partner one bit at a time"
            % (k, sorted(have), span))
    sent = {rank: sum(t.length for t in double.outgoing(rank)) for rank in full8.ranks}
    assert sent == {rank: length * steps for rank in full8.ranks}, (
        "each rank sends %r elements, not S*log2(N) = 24: the per-rank figure is "
        "not S" % (sent,))
    handled_double = s1.bytes_per_rank(full8, double)
    assert handled_double == {rank: 2 * length * steps * E for rank in full8.ranks}, (
        "each rank handles %r bytes, not 2*S*log2(N) elements = 192: it sends S "
        "and receives S in each of the log2(N) steps" % (handled_double,))
    assert double.elements_moved() == n8 * length * steps == 192, (
        "the doubling moves %r elements, not N*S*log2(N) = 192"
        % (double.elements_moved(),))
    double_got = fabric.run(full8, double, fabric.buffers(n8, length))
    for rank in full8.ranks:
        assert double_got[rank] == fabric.reference(fabric.buffers(n8, length)), (
            "rank %s ends with %r, not the all-reduced reference: doubling "
            "combines every rank's partial" % (rank, double_got[rank]))

    # the butterfly is a butterfly only where the partners are one hop apart

    switch_wide = fabric.switch(8, width=8)
    wide = s.all_reduce_doubling(switch_wide, length)
    assert fabric.legality_problems(switch_wide, wide) == (), (
        "the doubling plan on switch(8, width=8) is illegal: %r"
        % (fabric.legality_problems(switch_wide, wide),))
    assert len(wide.steps()) == 3, (
        "the doubling on a one-group switch is %r steps, not log2(N) = 3"
        % (len(wide.steps()),))
    wide_got = fabric.run(switch_wide, wide, fabric.buffers(8, length))
    assert all(wide_got[rank] == fabric.reference(fabric.buffers(8, length))
               for rank in switch_wide.ranks), (
        "the doubling on switch(8, width=8) does not leave every rank with the "
        "reference")

    ring_refusal = _refuses(
        fabric, "doubling the many-hop partners of ring(8)",
        lambda: s.all_reduce_doubling(ring8, length))
    assert "r0" in ring_refusal and "r2" in ring_refusal and "2 hops" in ring_refusal, (
        "the refusal of ring(8)'s butterfly does not name the offending pair "
        "(r0 and r2, two hops) and its hop count: %r" % (ring_refusal,))

    switch8 = fabric.switch(8, width=4)
    switch_refusal = _refuses(
        fabric, "doubling the many-hop partners of switch(8, width=4)",
        lambda: s.all_reduce_doubling(switch8, length))
    assert "r1" in switch_refusal and "r5" in switch_refusal and "3 hops" in switch_refusal, (
        "the refusal of switch(8, width=4)'s butterfly does not name the "
        "offending pair (r1 and r5, three hops across the spine) and its hop "
        "count: %r" % (switch_refusal,))

    comfortable = fabric.full(8)
    assert s.all_reduce_doubling(comfortable, length).steps() == (0, 1, 2), (
        "doubling a full mesh is refused: every XOR partner is a direct "
        "neighbour there, so no refusal belongs here")

    # ---- the same plan whatever the combining op ---------------------------

    tree_min = s.all_reduce_tree(tree7, length, op="min")
    assert tree_min.transfers == plan.transfers, (
        "op='min' produced a different tree plan: the shape does not depend on "
        "the combining operation, which the plan does not carry")
    tree_min_got = fabric.run(tree7, tree_min, bufs, op="min")
    tree_min_ref = fabric.reference(bufs, op="min")
    for rank in tree7.ranks:
        assert tree_min_got[rank] == tree_min_ref, (
            "with op='min' rank %s ends with %r, not the all-reduced %r"
            % (rank, tree_min_got[rank], tree_min_ref))
    double_max = s.all_reduce_doubling(full8, length, op="max")
    assert double_max.transfers == double.transfers, (
        "op='max' produced a different doubling plan: the shape does not depend "
        "on the combining operation")
    double_max_got = fabric.run(full8, double_max, fabric.buffers(n8, length), op="max")
    double_max_ref = fabric.reference(fabric.buffers(n8, length), op="max")
    for rank in full8.ranks:
        assert double_max_got[rank] == double_max_ref, (
            "with op='max' rank %s ends with %r, not the all-reduced %r"
            % (rank, double_max_got[rank], double_max_ref))

    # ---- best: the crossover is a comparison of tick counts ----------------

    tiny = 1
    assert _refuses(fabric, "all_reduce_ring on a one-element message",
                    lambda: s4.all_reduce_ring(switch8, tiny)), (
        "the ring built a plan for a one-element message: the fixture assumes it "
        "cannot, so that it is not a candidate")
    assert "r1" in switch_refusal, (
        "the switch(8, width=4) butterfly is refused, so `doubling` is not a "
        "candidate there: %r" % (switch_refusal,))
    tiny_cost = available(switch8, tiny)
    assert tiny_cost == {"tree": 48}, (
        "on switch(8, width=4) at one element the candidates are %r, not the "
        "tree alone at 48 ticks (the ring's chunking fails, the butterfly's "
        "partners are not neighbours)" % (tiny_cost,))
    best_tiny, best_tiny_plan = s.all_reduce_best(switch8, tiny)
    assert best_tiny == "tree", (
        "for a one-element message on switch(8, width=4) `all_reduce_best` "
        "picked %r, not the latency-cheap tree at 48 ticks" % (best_tiny,))
    assert best_tiny_plan.transfers == built(switch8, tiny, "tree").transfers, (
        "`all_reduce_best` named the tree but returned another plan: %r"
        % ([(t.src, t.dst) for t in best_tiny_plan.transfers],))

    big_switch = available(switch8, 4096)
    assert big_switch == {"ring": 1610, "tree": 1520}, (
        "on switch(8, width=4) at 4096 elements the candidates are %r, not the "
        "ring at 1610 and the tree at 1520: the ring crosses the slow spine in "
        "every one of its 14 steps" % (big_switch,))
    best_big, _ = s.all_reduce_best(switch8, 4096)
    assert best_big == "tree", (
        "for 4096 elements on switch(8, width=4) `all_reduce_best` picked %r, "
        "not the cheaper of the recomputed ticks" % (best_big,))

    # the crossover on a uniform fabric: tiny wants few steps, large wants bytes

    uniform_tiny = available(ring8, length)
    assert uniform_tiny == {"ring": 84, "tree": 48}, (
        "the ring(8) eight-element candidates are %r, not ring=84 tree=48 (the "
        "butterfly's partners are not neighbours on a ring)" % (uniform_tiny,))
    assert s.all_reduce_best(ring8, length)[0] == "tree", (
        "for a small message on ring(8) `all_reduce_best` picked %r, not the "
        "latency-cheap tree" % (s.all_reduce_best(ring8, length)[0],))
    uniform_big = available(ring8, 4096)
    assert uniform_big == {"ring": 364, "tree": 1352}, (
        "the ring(8) 4096-element candidates are %r, not ring=364 tree=1352"
        % (uniform_big,))
    big_pick, big_plan = s.all_reduce_best(ring8, 4096)
    assert big_pick == "ring", (
        "for a large message on ring(8) `all_reduce_best` picked %r, not the "
        "bandwidth-optimal ring: the crossover is a comparison of ticks, not a "
        "hard-coded size" % (big_pick,))
    assert big_plan.transfers == built(ring8, 4096, "ring").transfers, (
        "`all_reduce_best` named the ring but returned another plan")

    # it picks by its own arithmetic, not by the topology's name

    size64 = 64
    recomputed = available(ring8, size64)
    cheapest = min(recomputed, key=lambda name: (recomputed[name], ORDER.index(name)))
    chosen, chosen_plan = s.all_reduce_best(ring8, size64)
    assert recomputed == {"ring": 84, "tree": 64}, (
        "the ring(8) 64-element candidates are %r, not ring=84 tree=64"
        % (recomputed,))
    assert chosen == cheapest == "tree", (
        "on ring(8) at 64 elements the ticks are %r, whose cheapest is %r, but "
        "`all_reduce_best` picked %r: it must be a function of the costs"
        % (recomputed, cheapest, chosen))
    assert chosen_plan.transfers == built(ring8, size64, cheapest).transfers, (
        "`all_reduce_best` named %r but returned another candidate's plan"
        % (chosen,))

    # ties break by the order ("ring", "tree", "doubling")

    tie = s.all_reduce_best(fabric.full(4), 4)
    assert available(fabric.full(4), 4) == {"ring": 36, "tree": 12, "doubling": 12}, (
        "the full(4) four-element candidate costs are %r, not ring=36 tree=12 "
        "doubling=12" % (available(fabric.full(4), 4),))
    assert tie[0] == "tree", (
        "on full(4) at 4 elements the tree and doubling both cost 12 ticks, and "
        "the tie-break order picks the tree, but `all_reduce_best` returned %r"
        % (tie[0],))

    # the only shape that fits is still the answer

    only = s.all_reduce_best(tree7, length)
    assert only[0] == "tree", (
        "on tree(7) at 8 elements the ring's chunking fails and N is not a power "
        "of two, so the tree is the only candidate, but `all_reduce_best` "
        "returned %r" % (only[0],))
    assert only[1].transfers == plan.transfers, (
        "`all_reduce_best` returned a tree plan that is not the tree's: %r"
        % (only[1],))

    # ---- the refusals ------------------------------------------------------

    message = _refuses(fabric, "doubling a seven-rank fabric",
                       lambda: s.all_reduce_doubling(tree7, length))
    assert "7" in message, (
        "the refusal of a non-power-of-two N does not name it: %r" % (message,))
    message = _refuses(fabric, "doubling a six-rank fabric",
                       lambda: s.all_reduce_doubling(fabric.ring(6), length))
    assert "6" in message, (
        "the refusal of a non-power-of-two N does not name it: %r" % (message,))
    message = _refuses(fabric, "doubling a five-rank fabric",
                       lambda: s.all_reduce_doubling(fabric.full(5), length))
    assert "5" in message, (
        "the refusal of a non-power-of-two N does not name it: %r" % (message,))

    disconnected = fabric.Topology(
        ranks=("r0", "r1", "r2"),
        links=(fabric.Link(a="r0", b="r1", bandwidth=100, latency=5),))
    message = _refuses(fabric, "the tree of a disconnected fabric",
                       lambda: s.all_reduce_tree(disconnected, length))
    assert "r2" in message or "rout" in message, (
        "the refusal of an unreachable rank does not name it: %r" % (message,))

    for what, call in (
        ("all_reduce_tree", lambda: s.all_reduce_tree(tree7, length, op="average")),
        ("all_reduce_tree", lambda: s.all_reduce_tree(tree7, length, op="send")),
        ("all_reduce_doubling", lambda: s.all_reduce_doubling(full8, length, op="average")),
        ("all_reduce_doubling", lambda: s.all_reduce_doubling(full8, length, op="send")),
        ("all_reduce_best", lambda: s.all_reduce_best(ring8, length, op="average")),
    ):
        _refuses(fabric, "%s with a non-combining op" % (what,), call)

    print("check_05: the tree all-reduce — the topology's own tree walked in "
          "2*levels steps, the XOR butterfly in log2(N) between direct "
          "neighbours, and all_reduce_best picking the cheapest shape by "
          "counting ticks")

# --- stage 6 -----------------------------------------------------------------------
def check_6():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "interconnects-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import fabric
    import stage_01 as s1
    import stage_04 as s4
    import stage_06 as s

    ring4 = fabric.ring(4)
    ranks = ring4.ranks
    n = len(ranks)
    length = 12
    chunks = 4
    size = length // chunks
    bufs = fabric.buffers(n, length)
    ref = fabric.reference(bufs)

    # ---- the all-gather: N-1 steps, every rank's piece, op="send" ----------

    ag = s.all_gather(ring4, length, chunks=chunks)
    assert fabric.legality_problems(ring4, ag) == (), (
        "all_gather's plan is illegal: %r" % (fabric.legality_problems(ring4, ag),))
    assert ag.steps() == tuple(range(n - 1)), (
        "all_gather's steps are %r, not 0..N-2 = %r: the ring gathers in N-1 "
        "steps" % (ag.steps(), tuple(range(n - 1))))
    assert len(ag.steps()) == n - 1 == 3, (
        "all_gather is %r steps, not N-1 = 3" % (len(ag.steps()),))
    assert {transfer.op for transfer in ag.transfers} == {"send"}, (
        "the all-gather moves %r transfers: it copies each rank's piece forward "
        "with op='send', it does not combine"
        % (sorted({transfer.op for transfer in ag.transfers}),))
    assert {transfer.length for transfer in ag.transfers} == {size}, (
        "the all-gather moves transfers of length %r, not one chunk of %d "
        "elements" % (sorted({transfer.length for transfer in ag.transfers}), size))
    assert len(ag.transfers) == (n - 1) * n == 12, (
        "the all-gather has %r transfers, not one per rank per step = (N-1)*N"
        % (len(ag.transfers),))

    # The piece rank r contributes is chunk r of the buffer it was handed, so a
    # correct all-gather gives every rank the same hand-built tuple.
    expected = (1, 2, 3, 8, 10, 12, 21, 24, 27, 40, 44, 48)
    assembled = tuple(value for c in range(chunks)
                      for value in bufs[ranks[c]][c * size:(c + 1) * size])
    assert assembled == expected, (
        "the fixture's hand-built all-gather is %r, not the assembly of chunk c "
        "taken from rank c: %r" % (expected, assembled))
    gathered = fabric.run(ring4, ag, bufs)
    for rank in ranks:
        assert gathered[rank] == expected, (
            "after the all-gather rank %s holds %r, not every rank's piece %r: "
            "an all-gather that gathers all but one rank fails here"
            % (rank, gathered[rank], expected))
    for index, rank in enumerate(ranks):
        own = slice(index * size, (index + 1) * size)
        assert gathered[rank][own] == bufs[rank][own], (
            "the all-gather changed rank %s's own chunk %d to %r, not the %r it "
            "contributed" % (rank, index, gathered[rank][own], bufs[rank][own]))

    # ---- the reduce-scatter: N-1 steps, rank r holding only its chunk ------ 

    rs = s.reduce_scatter(ring4, length, chunks=chunks)
    assert fabric.legality_problems(ring4, rs) == (), (
        "reduce_scatter's plan is illegal: %r" % (fabric.legality_problems(ring4, rs),))
    assert rs.steps() == tuple(range(n - 1)), (
        "reduce_scatter's steps are %r, not 0..N-2: the ring scatters in N-1 "
        "steps" % (rs.steps(),))
    assert len(rs.steps()) == n - 1 == 3, (
        "reduce_scatter is %r steps, not N-1 = 3" % (len(rs.steps()),))
    assert {transfer.op for transfer in rs.transfers} == {"reduce"}, (
        "the reduce-scatter moves %r transfers: it combines into the "
        "destination with op='reduce', it does not copy"
        % (sorted({transfer.op for transfer in rs.transfers}),))
    assert {transfer.length for transfer in rs.transfers} == {size}, (
        "the reduce-scatter moves transfers of length %r, not one chunk of %d "
        "elements" % (sorted({transfer.length for transfer in rs.transfers}), size))
    assert len(rs.transfers) == (n - 1) * n == 12, (
        "the reduce-scatter has %r transfers, not one per rank per step"
        % (len(rs.transfers),))
    assert {transfer.op for transfer in rs.transfers} != {transfer.op for transfer in ag.transfers}, (
        "the two plans carry the same ops %r and %r: the scatter combines and "
        "the gather copies, they are not each other's inverse"
        % ({transfer.op for transfer in rs.transfers},
           {transfer.op for transfer in ag.transfers}))

    # The exact per-chunk contributors: chunk c is complete on rank c only, and
    # every other chunk of a rank carries the ranks that have passed through it.
    contributors = {
        "r0": ((0, 1, 2, 3), (0, 2, 3), (0, 3), (0,)),
        "r1": ((1,), (0, 1, 2, 3), (0, 1, 3), (0, 1)),
        "r2": ((1, 2), (2,), (0, 1, 2, 3), (0, 1, 2)),
        "r3": ((1, 2, 3), (2, 3), (3,), (0, 1, 2, 3)),
    }
    mid = fabric.run(ring4, rs, bufs)
    for index, rank in enumerate(ranks):
        expected_mid = tuple(
            sum(bufs[ranks[who]][c * size + j] for who in contributors[rank][c])
            for c in range(chunks) for j in range(size))
        assert mid[rank] == expected_mid, (
            "after the reduce-scatter rank %s holds %r, not the per-chunk "
            "combination of %r: each chunk carries exactly the ranks that "
            "passed through it"
            % (rank, mid[rank], contributors[rank]))
        own = slice(index * size, (index + 1) * size)
        assert mid[rank][own] == ref[own], (
            "after the reduce-scatter rank %s's own chunk %d is %r, not the "
            "fully reduced %r: rank r owns the reduced chunk r"
            % (rank, index, mid[rank][own], ref[own]))
        for other in range(n):
            if other == index:
                continue
            other_slice = slice(other * size, (other + 1) * size)
            assert mid[rank][other_slice] != ref[other_slice], (
                "after the reduce-scatter rank %s already holds chunk %d fully "
                "reduced: only chunk %d is complete, every other is partial"
                % (rank, other, index))
    last = ranks[n - 1]
    assert mid[last][(n - 1) * size:] == ref[(n - 1) * size:], (
        "the last chunk left unreduced: rank %s holds %r for chunk %d, not the "
        "fully reduced %r — the loop must run all N-1 steps"
        % (last, mid[last][(n - 1) * size:], n - 1, ref[(n - 1) * size:]))

    # ---- the two composed are stage 4's all-reduce ------------------------

    shifted = tuple(fabric.Transfer(src=transfer.src, dst=transfer.dst,
                                    offset=transfer.offset, length=transfer.length,
                                    step=transfer.step + (n - 1), op=transfer.op)
                    for transfer in ag.transfers)
    composed = fabric.Plan(transfers=rs.transfers + shifted)
    ring_all_reduce = s4.all_reduce_ring(ring4, length, chunks=chunks)
    assert len(composed.steps()) == 2 * (n - 1) == 6, (
        "reduce_scatter then all_gather composed to %r steps, not 2(N-1) = 6"
        % (len(composed.steps()),))
    assert s1.plan_ticks(ring4, composed) == s1.plan_ticks(ring4, ring_all_reduce), (
        "the composed plan costs %r ticks, not the %r of stage 4's all-reduce: "
        "the two halves are the same plan in sequence"
        % (s1.plan_ticks(ring4, composed), s1.plan_ticks(ring4, ring_all_reduce)))
    assert composed.transfers == ring_all_reduce.transfers, (
        "the composed plan is not stage 4's all_reduce_ring transfer for "
        "transfer: %r transfers against %r"
        % (len(composed.transfers), len(ring_all_reduce.transfers)))
    got = fabric.run(ring4, composed, bufs)
    for rank in ranks:
        assert got[rank] == ref, (
            "the composed reduce-scatter then all-gather leaves rank %s with "
            "%r, not the all-reduced %r" % (rank, got[rank], ref))
    twice = fabric.run(ring4, ag, mid)
    for rank in ranks:
        assert twice[rank] == ref, (
            "running the all-gather over the reduce-scatter's buffers leaves "
            "rank %s with %r, not the all-reduced %r" % (rank, twice[rank], ref))

    # ---- chunks=None means one chunk per rank -----------------------------

    assert s.all_gather(ring4, length).transfers == ag.transfers, (
        "all_gather with chunks=None is not the chunks=%d plan: the default is "
        "one chunk per rank" % (chunks,))
    assert s.reduce_scatter(ring4, length).transfers == rs.transfers, (
        "reduce_scatter with chunks=None is not the chunks=%d plan: the default "
        "is one chunk per rank" % (chunks,))

    # ---- the byte facts: S(N-1)/N each way, N-1 steps ----------------------

    per_direction = length * (n - 1) // n
    assert per_direction == 9, "the fixture's per-direction elements are %r, not 9" % (per_direction,)
    handled_ag = s1.bytes_per_rank(ring4, ag)
    handled_rs = s1.bytes_per_rank(ring4, rs)
    for rank in ranks:
        received_ag = sum(transfer.length for transfer in ag.transfers
                          if transfer.dst == rank)
        received_rs = sum(transfer.length for transfer in rs.transfers
                          if transfer.dst == rank)
        assert received_ag == per_direction == 9, (
            "in the all-gather rank %s received %r elements, not S(N-1)/N = 9 "
            "over the N-1 steps" % (rank, received_ag))
        assert received_rs == per_direction == 9, (
            "in the reduce-scatter rank %s received %r elements, not S(N-1)/N = "
            "9 over the N-1 steps" % (rank, received_rs))
        assert handled_ag[rank] == 2 * per_direction * fabric.ELEMENT_BYTES == 72, (
            "in the all-gather rank %s handled %r bytes, not 3 transfers of 3 "
            "elements each way = 72" % (rank, handled_ag[rank]))
        assert handled_rs[rank] == 2 * per_direction * fabric.ELEMENT_BYTES == 72, (
            "in the reduce-scatter rank %s handled %r bytes, not sent plus "
            "received = 3 transfers of 3 elements each way = 72"
            % (rank, handled_rs[rank]))

    # ---- a chunks smaller than N still moves all the data ------------------

    half = 2
    small = length // half
    ag2 = s.all_gather(ring4, length, chunks=half)
    assert ag2.steps() == tuple(range(n - 1)), (
        "the two-chunk all-gather steps are %r, not 0..N-2: fewer chunks do not "
        "shorten the ring" % (ag2.steps(),))
    expected2 = tuple(value for c in range(half)
                      for value in bufs[ranks[c]][c * small:(c + 1) * small])
    got2 = fabric.run(ring4, ag2, bufs)
    for rank in ranks:
        assert got2[rank] == expected2, (
            "with chunks=2 rank %s holds %r, not %r: a chunks smaller than N "
            "leaves some ranks idle per step, it must not drop their chunks"
            % (rank, got2[rank], expected2))
    rs2 = s.reduce_scatter(ring4, length, chunks=half)
    assert rs2.steps() == tuple(range(n - 1)), (
        "the two-chunk reduce-scatter steps are %r, not 0..N-2" % (rs2.steps(),))
    assert len(rs2.transfers) == (n - 1) * half == 6, (
        "the two-chunk reduce-scatter has %r transfers, not (N-1)*chunks = 6: "
        "only chunks ranks send in each step" % (len(rs2.transfers),))
    assert {transfer.length for transfer in rs2.transfers} == {small} == {6}, (
        "the two-chunk reduce-scatter moves transfers of length %r, not 6"
        % (sorted({transfer.length for transfer in rs2.transfers}),))
    mid2 = fabric.run(ring4, rs2, bufs)
    for index in range(half):
        own = slice(index * small, (index + 1) * small)
        assert mid2[ranks[index]][own] == ref[own], (
            "with chunks=2 rank %s's chunk %d is %r, not the fully reduced %r"
            % (ranks[index], index, mid2[ranks[index]][own], ref[own]))
    joined = fabric.run(ring4, ag2, mid2)
    for rank in ranks:
        assert joined[rank] == ref, (
            "the two-chunk pair leaves rank %s with %r, not the all-reduced %r: "
            "the smaller schedule must still move every rank's data"
            % (rank, joined[rank], ref))
    assert ag2.transfers == s4.all_gather_ring(ring4, length, chunks=half).transfers, (
        "stage 6's two-chunk all_gather is not the plan stage 4's gather half "
        "builds: %r transfers against %r"
        % (len(ag2.transfers), len(s4.all_gather_ring(ring4, length, chunks=half).transfers)))
    assert rs2.transfers == s4.reduce_scatter_ring(ring4, length, chunks=half).transfers, (
        "stage 6's two-chunk reduce_scatter is not the plan stage 4's scatter "
        "half builds: %r transfers against %r"
        % (len(rs2.transfers), len(s4.reduce_scatter_ring(ring4, length, chunks=half).transfers)))
    handled2 = s1.bytes_per_rank(ring4, rs2)
    expected_handled2 = {"r0": 72, "r1": 48, "r2": 72, "r3": 96}
    for rank in ranks:
        assert handled2[rank] == expected_handled2[rank], (
            "with chunks=2 the reduce-scatter cost rank %s %r bytes, not %r: the "
            "sliding window of two senders makes the per-rank traffic uneven — "
            "r0 one send and two receives, r1 one and one, r2 two and one, r3 "
            "two and two transfers of 6 elements"
            % (rank, handled2[rank], expected_handled2[rank]))

    # ---- a third rank count, against stage 4's halves ----------------------

    ring3 = fabric.ring(3)
    bufs3 = fabric.buffers(3, 9)
    ref3 = fabric.reference(bufs3)
    ag3 = s.all_gather(ring3, 9, chunks=3)
    rs3 = s.reduce_scatter(ring3, 9, chunks=3)
    assert ag3.steps() == (0, 1) and rs3.steps() == (0, 1), (
        "on three ranks all_gather/reduce_scatter take steps %r/%r, not 0..N-2 = "
        "(0, 1)" % (ag3.steps(), rs3.steps()))
    assert ag3.transfers == s4.all_gather_ring(ring3, 9, chunks=3).transfers, (
        "stage 6's all_gather is not the plan stage 4's all-gather half builds: "
        "%r transfers against %r"
        % (len(ag3.transfers), len(s4.all_gather_ring(ring3, 9, chunks=3).transfers)))
    assert rs3.transfers == s4.reduce_scatter_ring(ring3, 9, chunks=3).transfers, (
        "stage 6's reduce_scatter is not the plan stage 4's reduce-scatter half "
        "builds: %r transfers against %r"
        % (len(rs3.transfers), len(s4.reduce_scatter_ring(ring3, 9, chunks=3).transfers)))
    expected3 = (1, 2, 3, 8, 10, 12, 21, 24, 27)
    gathered3 = fabric.run(ring3, ag3, bufs3)
    for rank in ring3.ranks:
        assert gathered3[rank] == expected3, (
            "on three ranks the all-gather leaves rank %s with %r, not %r"
            % (rank, gathered3[rank], expected3))
    mid3 = fabric.run(ring3, rs3, bufs3)
    for index, rank in enumerate(ring3.ranks):
        own = slice(index * 3, (index + 1) * 3)
        assert mid3[rank][own] == ref3[own], (
            "on three ranks rank %s's own chunk is %r, not the fully reduced %r"
            % (rank, mid3[rank][own], ref3[own]))
    handled3 = s1.bytes_per_rank(ring3, ag3)
    for rank in ring3.ranks:
        assert handled3[rank] == 2 * 9 * (3 - 1) // 3 * fabric.ELEMENT_BYTES == 48, (
            "on three ranks the all-gather cost rank %s %r bytes, not 2 * 6 "
            "elements = 48" % (rank, handled3[rank]))

    # ---- the refusals ------------------------------------------------------

    message = _refuses(fabric, "an all_gather algorithm other than the ring",
                       lambda: s.all_gather(ring4, length, algorithm="tree"))
    assert "tree" in message, (
        "the refusal of an unsupported all_gather algorithm does not name it: %r"
        % (message,))
    message = _refuses(fabric, "a reduce_scatter algorithm other than the ring",
                       lambda: s.reduce_scatter(ring4, length, algorithm="doubling"))
    assert "doubling" in message, (
        "the refusal of an unsupported reduce_scatter algorithm does not name "
        "it: %r" % (message,))
    assert s.all_gather(ring4, length, algorithm="ring").transfers == ag.transfers, (
        "the explicit algorithm='ring' all_gather is not the default plan")
    assert s.reduce_scatter(ring4, length, algorithm="ring").transfers == rs.transfers, (
        "the explicit algorithm='ring' reduce_scatter is not the default plan")

    _refuses(fabric, "an all_gather chunks that does not divide length",
             lambda: s.all_gather(ring4, 10, chunks=4))
    _refuses(fabric, "a reduce_scatter chunks that does not divide length",
             lambda: s.reduce_scatter(ring4, 10, chunks=4))
    _refuses(fabric, "more all_gather chunks than ranks",
             lambda: s.all_gather(ring4, 16, chunks=8))
    _refuses(fabric, "more reduce_scatter chunks than ranks",
             lambda: s.reduce_scatter(ring4, 16, chunks=8))
    _refuses(fabric, "a single all_gather chunk",
             lambda: s.all_gather(ring4, 12, chunks=1))
    _refuses(fabric, "a single reduce_scatter chunk",
             lambda: s.reduce_scatter(ring4, 12, chunks=1))
    _refuses(fabric, "a reduce_scatter op that is not a combining op",
             lambda: s.reduce_scatter(ring4, 12, op="average"))
    _refuses(fabric, "a transfer op taken for a combining op",
             lambda: s.reduce_scatter(ring4, 12, op="send"))

    print("check_06: all-gather and reduce-scatter first class — each N-1 steps, "
          "each with its own op, composed into stage 4's all-reduce, and neither "
          "the other's inverse")

# --- stage 7 -----------------------------------------------------------------------
def check_7():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "interconnects-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _buffers(ranks, length):
        """Distinct, deterministic starting values: rank `ri`, element `j` = 100(i+1)+j."""
        return {rank: tuple(100 * (i + 1) + t for t in range(length))
                for i, rank in enumerate(ranks)}

    def _walls(splits, i, j):
        """The offset this check expects: what the ranks before `i` send rank `j`."""
        return sum(splits[k][j] for k in range(i))

    def _transfers(plan):
        """The plan's transfers as `(src, dst, offset, length)`, in plan order."""
        return tuple((t.src, t.dst, t.offset, t.length) for t in plan.transfers)

    def _rebuilt(blocks, rank, bufs):
        """The starting buffer of `rank` with every block written into it.

        The layout only describes the blocks the exchange fills; everything else in
        the buffer stays where it was, which is exactly what the executor leaves.
        """
        row = list(bufs[rank])
        for source, offset, length in blocks:
            row[offset:offset + length] = bufs[source][offset:offset + length]
        return tuple(row)

    import fabric
    import stage_01 as s1
    import stage_07 as s

    # ---- the even 4-rank exchange: every pair exchanges four ----------------

    full4 = fabric.full(4)
    ranks4 = full4.ranks
    even = tuple(tuple(4 for _ in range(4)) for _ in range(4))
    length4 = 16
    bufs4 = _buffers(ranks4, length4)
    plan = s.all_to_all(full4, even)
    assert isinstance(plan, fabric.Plan), (
        "all_to_all answered %r, not a fabric.Plan" % (type(plan).__name__,))
    assert fabric.legality_problems(full4, plan) == (), (
        "the even exchange's plan is illegal: %r"
        % (fabric.legality_problems(full4, plan),))
    assert plan.steps() == (0,), (
        "the even exchange is planned in steps %r, not one step: an all-to-all is "
        "one exchange, not a walk around the ring" % (plan.steps(),))
    expected_even = tuple(sorted(
        (ranks4[i], ranks4[j], 4 * i, 4)
        for i in range(4) for j in range(4) if i != j))
    assert _transfers(plan) == expected_even, (
        "the even exchange's transfers are %r, not one transfer per pair at the "
        "running sum of the column = %r: an offset of `i * 4` is the cumulative "
        "here only because every count is four, and a per-pair offset would look "
        "identical while a ragged table breaks it" % (_transfers(plan), expected_even))
    assert all(t.op == "send" for t in plan.transfers), (
        "the exchange moves %r transfers: an all-to-all copies each block once "
        "with op='send', it does not combine"
        % (sorted({t.op for t in plan.transfers}),))
    assert all(t.src != t.dst for t in plan.transfers), (
        "the plan carries a diagonal transfer: %r sends to itself, and the "
        "diagonal is the slice a rank keeps, not a message"
        % (sorted({(t.src, t.dst) for t in plan.transfers if t.src == t.dst}),))
    assert all(t.length > 0 for t in plan.transfers), (
        "the plan carries a zero-length transfer: %r"
        % ([t for t in plan.transfers if t.length == 0],))
    assert len(plan.transfers) == 12, (
        "the even exchange has %r transfers, not one per ordered pair = 12"
        % (len(plan.transfers),))

    # A uniform table makes every sender's wall for every destination the same
    # `i * 4`, so all four ranks must end holding one and the same buffer: the
    # transpose of an all-equal table has no way to tell the senders apart.
    expected_buffer = tuple(v for i in range(4) for v in bufs4[ranks4[i]][4 * i:4 * i + 4])
    assert expected_buffer == (100, 101, 102, 103, 204, 205, 206, 207,
                               308, 309, 310, 311, 412, 413, 414, 415), (
        "the fixture's hand-built even expectation is %r, not the four ranks' own "
        "slots concatenated" % (expected_buffer,))
    got = fabric.run(full4, plan, bufs4)
    for rank in ranks4:
        assert got[rank] == expected_buffer, (
            "after the even exchange rank %s holds %r, not %r — each sender's "
            "blocks all start at its own wall `4 * i`" % (rank, got[rank], expected_buffer))
    for index, rank in enumerate(ranks4):
        own = slice(4 * index, 4 * index + 4)
        assert got[rank][own] == bufs4[rank][own], (
            "the even exchange moved rank %s's kept slice from %r to %r: the "
            "diagonal sits at its own index and never moves"
            % (rank, bufs4[rank][own], got[rank][own]))
    handled = s1.bytes_per_rank(full4, plan)
    for rank in ranks4:
        assert handled[rank] == 2 * 12 * fabric.ELEMENT_BYTES == 96, (
            "the even exchange cost rank %s %r bytes, not three blocks of four "
            "elements each way = 96: every rank sends and receives the same"
            % (rank, handled[rank]))
    slow = 5 + fabric.ceil_div(fabric.ELEMENT_BYTES * 4, 100)
    assert slow == 6, "the fixture's slowest transfer is %r ticks, not 6" % (slow,)
    assert s1.plan_ticks(full4, plan) == slow == 6, (
        "the one-step even exchange costs %r ticks, not the slowest transfer's "
        "6: a step is its slowest transfer, and the pairs run at once"
        % (s1.plan_ticks(full4, plan),))
    eblocks = s.exchange_with(full4, even)
    assert len(eblocks) == 4, (
        "exchange_with answered %r entries for four ranks" % (len(eblocks),))
    for index, rank in enumerate(ranks4):
        lying = tuple((t.src, t.offset, t.length) for t in plan.incoming(rank))
        assert eblocks[index] == lying, (
            "exchange_with's blocks for %s are %r, but the plan delivers %r: the "
            "layout describes the exchange the plan runs" % (rank, eblocks[index], lying))

    # ---- the ragged table, every offset and every block hand-computed -------

    ragged = ((0, 1, 2, 3), (3, 0, 1, 2), (2, 3, 0, 1), (1, 2, 3, 0))
    length6 = 6
    bufs6 = _buffers(ranks4, length6)
    rplan = s.all_to_all(full4, ragged)
    assert fabric.legality_problems(full4, rplan) == (), (
        "the ragged exchange's plan is illegal: %r"
        % (fabric.legality_problems(full4, rplan),))
    assert rplan.steps() == (0,), (
        "the ragged exchange is planned in steps %r, not one step" % (rplan.steps(),))
    expected_ragged = (
        ("r0", "r1", 0, 1), ("r0", "r2", 0, 2), ("r0", "r3", 0, 3),
        ("r1", "r0", 0, 3), ("r1", "r2", 2, 1), ("r1", "r3", 3, 2),
        ("r2", "r0", 3, 2), ("r2", "r1", 1, 3), ("r2", "r3", 5, 1),
        ("r3", "r0", 5, 1), ("r3", "r1", 4, 2), ("r3", "r2", 3, 3))
    assert _transfers(rplan) == expected_ragged, (
        "the ragged exchange's transfers are %r, not the hand-computed %r: the "
        "offset of the block from rank i is the running sum of what the ranks "
        "before it send rank j, so no pair of them may share an offset"
        % (_transfers(rplan), expected_ragged))

    blocks = s.exchange_with(full4, ragged)
    assert len(blocks) == 4, (
        "exchange_with answered %r entries, not one per rank of the fabric"
        % (len(blocks),))
    for index, rank in enumerate(ranks4):
        lying = tuple((t.src, t.offset, t.length) for t in rplan.incoming(rank))
        assert blocks[index] == lying, (
            "exchange_with's blocks for %s are %r, but the plan delivers %r: the "
            "result layout and the plan are the same exchange read twice"
            % (rank, blocks[index], lying))
    expected_ragged_buffers = {
        "r0": (200, 201, 202, 303, 304, 405),
        "r1": (100, 301, 302, 303, 404, 405),
        "r2": (100, 101, 202, 403, 404, 405),
        "r3": (100, 101, 102, 203, 204, 305),
    }
    out = fabric.run(full4, rplan, bufs6)
    for rank in ranks4:
        assert out[rank] == expected_ragged_buffers[rank], (
            "after the ragged exchange rank %s holds %r, not the hand-computed "
            "%r: the j-th block is column j of the table, top to bottom"
            % (rank, out[rank], expected_ragged_buffers[rank]))
    for j, rank in enumerate(ranks4):
        assembled = _rebuilt(blocks[j], rank, bufs6)
        assert assembled == out[rank], (
            "reading the ragged result out of the starting buffers through "
            "exchange_with gives %r, not the %r the plan produced"
            % (assembled, out[rank]))
        for i, source in enumerate(ranks4):
            if i == j or not ragged[i][j]:
                continue
            wall = _walls(ragged, i, j)
            assert out[rank][wall:wall + ragged[i][j]] == bufs6[source][wall:wall + ragged[i][j]], (
                "rank %s's block from %s sits at %r, not at the wall %r of %r: "
                "the walls are the running sum of what the destination receives"
                % (rank, source, out[rank][wall:wall + ragged[i][j]], wall,
                   bufs6[source][wall:wall + ragged[i][j]]))
        own = _walls(ragged, j, j)
        assert out[rank][own:own + ragged[j][j]] == bufs6[rank][own:own + ragged[j][j]], (
            "rank %s's kept slice (empty here) moved from offset %d"
            % (rank, own))

    # ---- a table ragged per destination, so the senders do differ ----------

    uneven = ((0, 1, 3), (2, 0, 1), (1, 4, 0))
    full3 = fabric.full(3)
    ranks3 = full3.ranks
    uneven_length = max(sum(uneven[k][j] for k in range(3)) for j in range(3))
    assert uneven_length == 5, (
        "the fixture's longest received column is %r, not 5" % (uneven_length,))
    bufs7 = _buffers(ranks3, uneven_length)
    uplan = s.all_to_all(full3, uneven)
    assert fabric.legality_problems(full3, uplan) == (), (
        "the uneven exchange's plan is illegal: %r"
        % (fabric.legality_problems(full3, uplan),))
    expected_uneven = tuple(sorted(
        (ranks3[i], ranks3[j], sum(uneven[k][j] for k in range(i)), uneven[i][j])
        for i in range(3) for j in range(3) if i != j and uneven[i][j]))
    assert _transfers(uplan) == expected_uneven, (
        "the uneven exchange's transfers are %r, not %r: the walls differ from "
        "one column to the next only if the cumulative is recomputed per "
        "destination, not per pair" % (_transfers(uplan), expected_uneven))
    uout = fabric.run(full3, uplan, bufs7)
    ublocks = s.exchange_with(full3, uneven)
    for index, rank in enumerate(ranks3):
        lying = tuple((t.src, t.offset, t.length) for t in uplan.incoming(rank))
        assert ublocks[index] == lying, (
            "on the uneven table, exchange_with's blocks for %s are %r, not the "
            "%r the plan delivers" % (rank, ublocks[index], lying))
        rebuilt = _rebuilt(ublocks[index], rank, bufs7)
        assert rebuilt == uout[rank], (
            "on the uneven table, rank %s's buffer from exchange_with is %r, not "
            "the %r the plan produced" % (rank, rebuilt, uout[rank]))
        for i, source in enumerate(ranks3):
            if i == index or not uneven[i][index]:
                continue
            wall = sum(uneven[k][index] for k in range(i))
            assert uout[rank][wall:wall + uneven[i][index]] == bufs7[source][wall:wall + uneven[i][index]], (
                "rank %s's block from %s at offset %d is %r, not the source's %r"
                % (rank, source, wall, uout[rank][wall:wall + uneven[i][index]],
                   bufs7[source][wall:wall + uneven[i][index]]))

    # ---- a rank that neither sends nor receives ----------------------------

    idle = ((1, 2, 0), (3, 1, 0), (0, 0, 0))
    idle_length = 4
    bufs4b = _buffers(ranks3, idle_length)
    iplan = s.all_to_all(full3, idle)
    assert fabric.legality_problems(full3, iplan) == (), (
        "the idle-rank exchange's plan is illegal: %r"
        % (fabric.legality_problems(full3, iplan),))
    assert _transfers(iplan) == (("r0", "r1", 0, 2), ("r1", "r0", 1, 3)), (
        "with a zero row and column the plan's transfers are %r, not the two the "
        "other pairs need: a rank that moves nothing is not a transfer"
        % (_transfers(iplan),))
    assert not any("r2" in (t.src, t.dst) for t in iplan.transfers), (
        "the idle rank appears in a transfer: %r"
        % ([t for t in iplan.transfers if "r2" in (t.src, t.dst)],))
    iout = fabric.run(full3, iplan, bufs4b)
    assert iout["r2"] == bufs4b["r2"], (
        "the rank that neither sends nor receives was touched: %r, not %r"
        % (iout["r2"], bufs4b["r2"]))
    assert iout["r0"] == (100, 201, 202, 203), (
        "with the idle rank present, rank r0 holds %r, not the hand-computed "
        "%r (its kept slice, then r1's three elements at the wall 1)"
        % (iout["r0"], (100, 201, 202, 203)))
    assert iout["r1"] == (100, 101, 202, 203), (
        "with the idle rank present, rank r1 holds %r, not the hand-computed %r "
        "(r0's two elements, then r1's kept slice at the wall 2)"
        % (iout["r1"], (100, 101, 202, 203)))
    ibld = s.exchange_with(full3, idle)
    for index, rank in enumerate(ranks3):
        lying = tuple((t.src, t.offset, t.length) for t in iplan.incoming(rank))
        assert ibld[index] == lying, (
            "with the idle rank present, exchange_with's blocks for %s are %r, "
            "not the %r the plan delivers" % (rank, ibld[index], lying))
    assert len(ibld) == 3 and ibld[2] == (), (
        "exchange_with dropped or filled the idle rank: %r, not a third entry "
        "with no blocks" % (ibld,))

    # ---- a big pair makes the step's price visible, not its byte total -----

    big = ((0, 400, 4), (4, 0, 400), (400, 4, 0))
    big_length = 404
    bufs_big = _buffers(ranks3, big_length)
    bplan = s.all_to_all(full3, big)
    assert fabric.legality_problems(full3, bplan) == (), (
        "the big exchange's plan is illegal: %r"
        % (fabric.legality_problems(full3, bplan),))
    assert bplan.steps() == (0,), (
        "the big exchange is planned in steps %r, not one step: nothing here is a "
        "sequence of sends" % (bplan.steps(),))
    expected_big = tuple(sorted(
        (ranks3[i], ranks3[j], sum(big[k][j] for k in range(i)), big[i][j])
        for i in range(3) for j in range(3) if i != j and big[i][j]))
    assert _transfers(bplan) == expected_big, (
        "the big exchange's transfers are %r, not the hand-computed %r"
        % (_transfers(bplan), expected_big))
    slow_big = 5 + fabric.ceil_div(fabric.ELEMENT_BYTES * 400, 100)
    assert slow_big == 21, "the fixture's slowest transfer is %r ticks, not 21" % (slow_big,)
    assert s1.plan_ticks(full3, bplan) == slow_big == 21, (
        "the one-step exchange with one 400-element pair costs %r ticks, not the "
        "slowest transfer's 21: summing the transfers or serialising the pairs "
        "would charge %r for the same bytes"
        % (s1.plan_ticks(full3, bplan), sum(
            s1.transfer_ticks(full3, t) for t in bplan.transfers)))
    bigout = fabric.run(full3, bplan, bufs_big)
    bigblocks = s.exchange_with(full3, big)
    for index, rank in enumerate(ranks3):
        lying = tuple((t.src, t.offset, t.length) for t in bplan.incoming(rank))
        assert bigblocks[index] == lying, (
            "on the big table, exchange_with's blocks for %s are %r, not the %r "
            "the plan delivers" % (rank, bigblocks[index], lying))
        rebuilt = _rebuilt(bigblocks[index], rank, bufs_big)
        assert rebuilt == bigout[rank], (
            "on the big table, rank %s's buffer from exchange_with is not the one "
            "the plan produced: %r against %r" % (rank, rebuilt, bigout[rank]))

    # ---- one rank on the fabric: nothing to exchange ------------------------

    alone = fabric.full(1)
    one = s.all_to_all(alone, ((0,),))
    assert one.transfers == () and one.steps() == (), (
        "a one-rank fabric got the plan %r, not the empty one: there is no pair "
        "to move anything between" % (one,))
    assert s.exchange_with(alone, ((5,),)) == ((),), (
        "on a one-rank fabric exchange_with answered %r, not one rank with no "
        "blocks" % (s.exchange_with(alone, ((5,),)),))

    # ---- the refusals ------------------------------------------------------

    message = _refuses(fabric, "a table with the wrong number of rows",
                       lambda: s.all_to_all(full4, ((1, 2, 3), (1, 2, 3), (1, 2, 3))))
    assert "rows" in message and "3" in message and "4" in message, (
        "the refusal of a 3-row table on a 4-rank fabric does not name the counts "
        "and the fabric: %r" % (message,))
    message = _refuses(fabric, "a table with a short row",
                       lambda: s.all_to_all(full4, ((1, 2, 3), (1, 2, 3), (1, 2, 3), (1, 2))))
    assert "splits" in message and "columns" in message, (
        "the refusal of a short row does not name the row and its width: %r"
        % (message,))
    message = _refuses(fabric, "a negative count",
                       lambda: s.all_to_all(full4, ((1, 2, 3, -1),) * 4))
    assert "negative" in message and "-1" in message, (
        "the refusal of a negative count does not name it: %r" % (message,))
    message = _refuses(fabric, "a count that is a string",
                       lambda: s.all_to_all(full4, (("1", 2, 3, 4),) * 4))
    assert "splits[0][0]" in message and "1" in message, (
        "the refusal of a string count does not name the cell and the count: %r"
        % (message,))
    _refuses(fabric, "a count that is a bool",
             lambda: s.all_to_all(full4, ((True, 2, 3, 4),) * 4))
    assert s.all_to_all(full4, ((0, 0, 0, 0),) * 4).transfers == (), (
        "a table of zeros is not a legal, empty exchange: %r"
        % (s.all_to_all(full4, ((0, 0, 0, 0),) * 4),))
    message = _refuses(fabric, "an exchange a ring cannot run in one step",
                       lambda: s.all_to_all(fabric.ring(4), even))
    assert "ring(4)" in message and ("step" in message or "direction" in message), (
        "the refusal of a one-step exchange the ring cannot run does not name "
        "the fabric and the collision: %r" % (message,))
    _refuses(fabric, "a ragged exchange the ring cannot run in one step",
             lambda: s.all_to_all(fabric.ring(4), ragged))
    _refuses(fabric, "exchange_with with the wrong number of rows",
             lambda: s.exchange_with(full4, ((1, 2, 3), (1, 2, 3), (1, 2, 3))))
    _refuses(fabric, "exchange_with with a negative count",
             lambda: s.exchange_with(full4, ((1, 2, 3, -4),) * 4))

    print("check_07: the all-to-all — one step, one transfer per pair, every "
          "block at the running sum of what its destination receives, the kept "
          "slice unmoved, and the result a transpose")

# --- stage 8 -----------------------------------------------------------------------
def check_8():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "interconnects-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import fabric
    import stage_01 as s1
    import stage_08 as s

    ring4 = fabric.ring(4)
    switch8 = fabric.switch(8, width=4)

    # ---- a group is one step: ring(4)'s pairwise exchange -------------------

    successors = tuple(("r%d" % index, "r%d" % ((index + 1) % 4), 0, 400)
                       for index in range(4))
    plan = s.sendrecv(ring4, successors)
    assert isinstance(plan, fabric.Plan), (
        "sendrecv answered %r, not a fabric.Plan: the group is a plan, and a "
        "plan is what a price is read off" % (type(plan).__name__,))
    assert len(plan.transfers) == 4, (
        "the four-rank pairwise exchange holds %r transfers, not one per exchange"
        % (len(plan.transfers),))
    assert plan.steps() == (0,), (
        "the group's steps are %r, not the single step 0: a group is one launch, "
        "not a chain of sends" % (plan.steps(),))
    assert fabric.legality_problems(ring4, plan) == (), (
        "the pairwise exchange is not legal to the fabric: %r"
        % (fabric.legality_problems(ring4, plan),))

    one_hop = 5 + fabric.ceil_div(4 * 400, 100)
    assert one_hop == 21, (
        "each one-hop exchange of 400 elements costs 5 + ceil(1600/100) = %r, "
        "not 21" % (one_hop,))
    ticks = s.group_ticks(ring4, successors)
    assert isinstance(ticks, int), (
        "group_ticks answered %r, not an int: every number here is a count"
        % (ticks,))
    assert ticks == one_hop == 21, (
        "the one-launch pairwise exchange cost %r ticks, not the max of its "
        "single-hop costs, 5 + ceil(1600/100) = 21" % (ticks,))
    assert ticks != 4 * one_hop, (
        "the group cost %r ticks, the sum of its four exchanges — the "
        "sequence-of-messages price: a group is one launch, and its price is one "
        "step's maximum" % (ticks,))
    assert ticks == s1.step_ticks(ring4, plan, 0), (
        "group_ticks answered %r where stage_01.step_ticks(sendrecv(...), 0) "
        "answers %r: a group's price is exactly its one step's cost"
        % (ticks, s1.step_ticks(ring4, plan, 0)))
    assert s1.plan_ticks(ring4, plan) == ticks, (
        "the group's plan costs %r ticks where the group's price is %r: a group "
        "is one launch, so the two must agree"
        % (s1.plan_ticks(ring4, plan), ticks))
    sequential = 4 * one_hop
    assert sequential == 84, (
        "the sequence-of-messages price of the four exchanges is %r ticks, not "
        "4 * 21 = 84" % (sequential,))

    start = fabric.buffers(4, 400)
    swapped = fabric.run(ring4, plan, start)
    for index in range(4):
        assert swapped["r%d" % index] == start["r%d" % ((index - 1) % 4)], (
            "after the pairwise exchange r%d does not hold its predecessor's "
            "buffer: a step reads the buffers as they were when it started"
            % (index,))

    # ---- full duplex: both directions on one link, in one step -------------

    both = (("r0", "r1", 0, 400), ("r1", "r0", 0, 400))
    pair = s.sendrecv(ring4, both)
    assert len(pair.transfers) == 2 and pair.steps() == (0,), (
        "the pairwise exchange built %d transfers in steps %r, not two transfers "
        "in one step" % (len(pair.transfers), pair.steps()))
    assert fabric.legality_problems(ring4, pair) == (), (
        "r0 -> r1 and r1 -> r0 in one step is illegal to the fabric: %r — links "
        "are full duplex" % (fabric.legality_problems(ring4, pair),))
    pair_ticks = s.group_ticks(ring4, both)
    assert pair_ticks == 21, (
        "the pairwise exchange costs %r ticks, not the one transfer's 21: a send "
        "and its matching recv are one transfer each, charged once"
        % (pair_ticks,))
    assert pair_ticks != 42, (
        "the pairwise exchange costs %r ticks, twice the one transfer: the send "
        "and the recv between one pair share the link, not the price"
        % (pair_ticks,))
    start = fabric.buffers(4, 400)
    exchanged = fabric.run(ring4, pair, start)
    assert exchanged["r0"] == start["r1"] and exchanged["r1"] == start["r0"], (
        "the pairwise exchange did not swap the two rank' buffers")

    assert s.group_ticks(ring4, (("r0", "r1", 0, 30),)) == 7, (
        "a 30-element (120-byte) exchange over a 100-byte/tick hop costs %r, not "
        "5 + ceil(120/100) = 7" % (s.group_ticks(ring4, (("r0", "r1", 0, 30),)),))

    # ---- the slice is the exchange's offset and length ---------------------

    start = fabric.buffers(4, 400)
    shifted = s.sendrecv(ring4, (("r0", "r1", 5, 395),))
    moved = fabric.run(ring4, shifted, start)
    assert moved["r1"][:5] == start["r1"][:5], (
        "the exchange wrote before its offset: r1's first five elements changed")
    assert moved["r1"][5:] == start["r0"][5:], (
        "the exchange copied r0's slice [0:395] instead of [5:400]: an exchange "
        "carries its offset")
    assert moved["r0"] == start["r0"], (
        "the exchange also changed the sender's own buffer")

    # ---- a collision on a directed link is refused -------------------------

    colliding = (("r0", "r1", 0, 400), ("r0", "r2", 0, 400))
    message = _refuses(fabric, "a group whose exchanges share a directed link",
                       lambda: s.sendrecv(ring4, colliding))
    assert "step" in message or "direction" in message, (
        "the refusal of a same-direction collision does not name the step or the "
        "direction: %r" % (message,))
    bad = fabric.Plan(transfers=(fabric.send("r0", "r1", 400, 0),
                                 fabric.send("r0", "r2", 400, 0)))
    assert fabric.legality_problems(ring4, bad) != (), (
        "the provided checker calls the colliding group legal: %r"
        % (fabric.legality_problems(ring4, bad),))

    inner = (("r1", "r5", 0, 400), ("r0", "r4", 0, 400))
    message = _refuses(fabric, "two exchanges colliding on an inner link",
                       lambda: s.sendrecv(switch8, inner))
    assert "step" in message or "direction" in message, (
        "the refusal of an inner-link collision does not name the step or the "
        "direction: %r" % (message,))
    bad = fabric.Plan(transfers=(fabric.send("r1", "r5", 400, 0),
                                 fabric.send("r0", "r4", 400, 0)))
    assert fabric.legality_problems(switch8, bad) != (), (
        "the provided checker calls the inner-link collision legal: %r"
        % (fabric.legality_problems(switch8, bad),))

    # ---- the serialised alternative costs more -----------------------------

    serial = fabric.Plan(transfers=(fabric.send("r0", "r1", 400, 0),
                                    fabric.send("r0", "r2", 400, 1)))
    assert fabric.legality_problems(ring4, serial) == (), (
        "the serialised two-step alternative is not legal: %r"
        % (fabric.legality_problems(ring4, serial),))
    serial_cost = s1.plan_ticks(ring4, serial)
    launch_cost = max(s1.transfer_ticks(ring4, transfer)
                      for transfer in serial.transfers)
    assert serial_cost == 21 + 42 == 63, (
        "serialising the colliding group costs %r ticks, not the one-hop 21 plus "
        "the two-hop 42" % (serial_cost,))
    assert launch_cost == 42, (
        "one launch of the same two exchanges would cost %r ticks, not the "
        "two-hop transfer's 42" % (launch_cost,))
    assert serial_cost > launch_cost, (
        "serialising the collision did not cost more: %r against %r"
        % (serial_cost, launch_cost))

    # ---- a group across the switch's spine: the expensive one prices it ----

    group = (("r0", "r1", 0, 400), ("r1", "r5", 0, 400))
    plan = s.sendrecv(switch8, group)
    assert plan.steps() == (0,), (
        "the switch group's steps are %r, not one step" % (plan.steps(),))
    assert fabric.legality_problems(switch8, plan) == (), (
        "the in-group exchange and the cross-spine exchange are illegal together: "
        "%r" % (fabric.legality_problems(switch8, plan),))
    assert s1.hop_count(switch8, "r1", "r5") == 3, (
        "the cross-group exchange is %r hops, not the three r1-r0-r4-r5"
        % (s1.hop_count(switch8, "r1", "r5"),))
    in_group = 2 + fabric.ceil_div(4 * 400, 200)
    spine = 20 + fabric.ceil_div(4 * 400, 25)
    cross = in_group + spine + in_group
    assert (in_group, spine, cross) == (10, 84, 104), (
        "the group's hops cost %r, not 10 in-group, 84 spine and 104 cross-group"
        % ((in_group, spine, cross),))
    ticks = s.group_ticks(switch8, group)
    assert ticks == 104 == cross, (
        "the group cost %r ticks, not the expensive cross-group transfer's 104"
        % (ticks,))
    assert ticks != in_group, (
        "the group cost %r ticks, the cheap in-group exchange: a step is priced "
        "by its slowest transfer" % (ticks,))
    assert ticks != in_group + cross, (
        "the group cost %r ticks, the sum of its two exchanges: a group is one "
        "step, not a sequence of messages" % (ticks,))
    assert ticks == s1.step_ticks(switch8, plan, 0), (
        "group_ticks answered %r where stage_01.step_ticks(sendrecv(...), 0) "
        "answers %r" % (ticks, s1.step_ticks(switch8, plan, 0)))
    assert s1.plan_ticks(switch8, plan) == ticks, (
        "the group's plan costs %r ticks where the group's price is %r"
        % (s1.plan_ticks(switch8, plan), ticks))
    start = fabric.buffers(8, 400)
    swapped = fabric.run(switch8, plan, start)
    assert swapped["r1"] == start["r0"], (
        "the in-group exchange did not land r0's buffer on r1")
    assert swapped["r5"] == start["r1"], (
        "the cross-spine exchange did not land r1's buffer on r5")

    # ---- the refusals ------------------------------------------------------

    message = _refuses(fabric, "a self-exchange",
                       lambda: s.sendrecv(ring4, (("r0", "r0", 0, 400),)))
    assert "exchange" in message and "r0" in message, (
        "the refusal of a self-exchange does not name the exchange: %r" % (message,))

    message = _refuses(fabric, "an exchange naming an unknown rank",
                       lambda: s.sendrecv(ring4, (("r1", "r9", 0, 400),)))
    assert "exchange" in message and "r9" in message, (
        "the refusal of an unknown rank does not name the exchange and the rank: "
        "%r" % (message,))

    message = _refuses(fabric, "an exchange of zero length",
                       lambda: s.sendrecv(ring4, (("r0", "r1", 0, 0),)))
    assert "exchange" in message and "length" in message, (
        "the refusal of a zero length does not name the length: %r" % (message,))
    message = _refuses(fabric, "an exchange of negative length",
                       lambda: s.sendrecv(ring4, (("r0", "r1", 0, -4),)))
    assert "exchange" in message and "length" in message, (
        "the refusal of a negative length does not name the length: %r"
        % (message,))

    message = _refuses(fabric, "an exchange with a negative offset",
                       lambda: s.sendrecv(ring4, (("r0", "r1", -1, 400),)))
    assert "exchange" in message and "offset" in message, (
        "the refusal of a negative offset does not name the offset: %r"
        % (message,))

    disconnected = fabric.Topology(
        ranks=("r0", "r1", "r2", "r3"),
        links=(fabric.Link(a="r0", b="r1", bandwidth=100, latency=5),))
    message = _refuses(fabric, "an exchange with no route",
                       lambda: s.sendrecv(disconnected, (("r0", "r3", 0, 400),)))
    assert "exchange" in message and ("rout" in message or "r3" in message), (
        "the refusal of an unroutable exchange does not name it: %r" % (message,))

    # ---- an empty group costs nothing --------------------------------------

    empty = s.sendrecv(ring4, ())
    assert isinstance(empty, fabric.Plan), (
        "the empty group answered %r, not a fabric.Plan" % (type(empty).__name__,))
    assert empty.transfers == () and empty.steps() == (), (
        "the empty group is %r, not a plan with no transfers" % (str(empty),))
    assert s.group_ticks(ring4, ()) == 0, (
        "the empty group cost %r ticks, not 0: a group with nothing to send pays "
        "for nothing" % (s.group_ticks(ring4, ()),))
    assert s1.step_ticks(ring4, empty, 0) == 0 and s1.plan_ticks(ring4, empty) == 0, (
        "the empty group's step or plan cost is not 0")
    untouched = fabric.buffers(4, 400)
    assert fabric.run(ring4, empty, untouched) == untouched, (
        "the empty group changed the buffers")

    print("check_08: a group is one launch — every exchange in step 0, the "
          "step's slowest transfer is its price, full-duplex links let a "
          "pairwise exchange share the link, a directed-link collision is "
          "refused and an empty group costs nothing")

# --- stage 9 -----------------------------------------------------------------------
def check_9():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    COURSE = "interconnects-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, COURSE)):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise."""
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    import fabric
    import stage_01 as s1
    import stage_04 as s4
    import stage_05 as s5
    import stage_09 as s

    #: The candidate order `choose` breaks ties by, and the algorithm every
    #: other stage's plan builder is reached through.
    order = ("ring", "tree", "doubling", "sharp")

    def available(topology, length):
        """Every candidate that fits, priced by the check's own recomputation."""
        costs = {}
        for name, build in (("ring", lambda: s4.all_reduce_ring(topology, length)),
                            ("tree", lambda: s5.all_reduce_tree(topology, length)),
                            ("doubling", lambda: s5.all_reduce_doubling(topology, length))):
            try:
                plan = build()
            except fabric.FabricError:
                continue
            costs[name] = s1.plan_ticks(topology, plan)
        try:
            costs["sharp"] = s.sharp_ticks(topology, length)
        except fabric.FabricError:
            pass
        return costs

    def cheapest(costs):
        return min(costs, key=lambda name: (costs[name], order.index(name)))

    def totals(plan):
        """`(largest sent, largest sent with reduce, largest sent with send)`."""
        by_rank = {"all": {}, "reduce": {}, "send": {}}
        for transfer in plan.transfers:
            for key in ("all", transfer.op):
                by_rank[key][transfer.src] = by_rank[key].get(transfer.src, 0) + transfer.length

        def largest(key):
            return max(by_rank[key].values()) if by_rank[key] else 0

        return largest("all"), largest("reduce"), largest("send")

    def runs(topology, plan, length, op="sum"):
        """The buffers `plan` leaves, against the reference all-reduce."""
        start = fabric.buffers(len(topology.ranks), length)
        got = fabric.run(topology, plan, start, op=op)
        want = fabric.reference(start, op=op)
        return all(got[rank] == want for rank in topology.ranks), got, want

    ring8 = fabric.ring(8)
    ring4 = fabric.ring(4)
    full8 = fabric.full(8)
    full4 = fabric.full(4)
    tree8 = fabric.tree(8)
    switch8 = fabric.switch(8, width=4)
    switch16 = fabric.switch(16, width=4)

    # ---- lower_bound: the elements one rank must move in one direction ------

    assert s.lower_bound(8, 4) == 6, (
        "the bound for 8 elements on 4 ranks is %r, not S(N-1)/N = 6: the "
        "denominator is N, not N-1 and not 1" % (s.lower_bound(8, 4),))
    assert s.lower_bound(12, 4) == 9, (
        "the bound for 12 elements on 4 ranks is %r, not 12 * 3 // 4 = 9"
        % (s.lower_bound(12, 4),))
    assert s.lower_bound(16, 4) == 12, (
        "the bound for 16 elements on 4 ranks is %r, not 16 * 3 // 4 = 12"
        % (s.lower_bound(16, 4),))
    assert s.lower_bound(4096, 8) == 3584, (
        "the bound for 4096 elements on 8 ranks is %r, not 4096 * 7 // 8 = 3584"
        % (s.lower_bound(4096, 8),))
    assert s.lower_bound(4096, 8) != 2 * 3584, (
        "the bound is %r: the reduce-scatter plus all-gather pair moves twice "
        "the one direction's S(N-1)/N, and the bound is the direction, not the "
        "pair" % (s.lower_bound(4096, 8),))
    assert s.lower_bound(1, 2) == 0, (
        "the bound for one element on two ranks is %r, not 1 * 1 // 2 = 0: half "
        "an element is not an element" % (s.lower_bound(1, 2),))
    assert s.lower_bound(7, 1) == 0, (
        "the bound for one rank is %r, not 0: there is no other rank to move "
        "anything to" % (s.lower_bound(7, 1),))
    for what, call in (("the bound of zero ranks", lambda: s.lower_bound(8, 0)),
                       ("the bound of a negative length", lambda: s.lower_bound(-1, 4))):
        _refuses(fabric, what, call)

    # ---- within_bound: the largest per-rank send against that floor --------

    bound4 = s.lower_bound(4096, 4)
    ring4_plan = s4.all_reduce_ring(ring4, 4096)
    assert ring4_plan.transfers and fabric.legality_problems(ring4, ring4_plan) == (), (
        "the ring(4) fixture is illegal: %r"
        % (fabric.legality_problems(ring4, ring4_plan),))
    largest4, reduce4, send4 = totals(ring4_plan)
    assert (reduce4, send4) == (bound4, bound4), (
        "the ring(4) all-reduce at chunks = n moves %r elements per rank with "
        "op='reduce' and %r with op='send', not the per-direction bound %r "
        "each: each half of the ring moves S(N-1)/N"
        % (reduce4, send4, bound4))
    assert largest4 == 2 * bound4, (
        "the ring(4) all-reduce's busiest rank sends %r elements in all, not "
        "2 * 3072 = 6144: a whole all-reduce moves both directions"
        % (largest4,))
    assert s.within_bound(ring4_plan, 4096, 4) is True, (
        "the ring(4) all-reduce at chunks = n sends %r per rank against the "
        "bound %r and `within_bound` answered %r: a plan that meets the bound "
        "exactly is within it" % (largest4, bound4, s.within_bound(ring4_plan, 4096, 4)))

    bound8 = s.lower_bound(4096, 8)
    ring8_plan = s4.all_reduce_ring(ring8, 4096)
    largest8, reduce8, send8 = totals(ring8_plan)
    assert (reduce8, send8) == (bound8, bound8) == (3584, 3584), (
        "the ring(8) all-reduce at chunks = n moves %r and %r per rank per "
        "direction, not the bound %r each" % (reduce8, send8, bound8))
    assert s.within_bound(ring8_plan, 4096, 8) is True, (
        "the ring(8) all-reduce sends %r per rank against the bound %r and "
        "`within_bound` answered %r"
        % (largest8, bound8, s.within_bound(ring8_plan, 4096, 8)))

    tree = s5.all_reduce_tree(ring8, 4096)
    tree_largest, tree_reduce, tree_send = totals(tree)
    assert tree_largest > bound8, (
        "the tree's busiest rank sends %r elements, not more than the bound %r: "
        "the root sends the whole buffer to every child" % (tree_largest, bound8))
    assert tree_send > bound8 and tree_reduce > bound8, (
        "the tree's two directions send %r and %r per rank, and both must "
        "exceed the bound %r" % (tree_reduce, tree_send, bound8))
    assert s.within_bound(tree, 4096, 8) is True, (
        "the tree moves more than the bound and `within_bound` answered %r"
        % (s.within_bound(tree, 4096, 8),))

    double = s5.all_reduce_doubling(full8, 4096)
    double_largest = totals(double)[0]
    assert double_largest == 3 * 4096 > bound8, (
        "the doubling's busiest rank sends %r elements, not 3 * 4096 = 12288 "
        "against the bound %r" % (double_largest, bound8))
    assert s.within_bound(double, 4096, 8) is True, (
        "the doubling moves more than the bound and `within_bound` answered %r"
        % (s.within_bound(double, 4096, 8),))

    gather = s4.all_gather_ring(ring8, 4096)
    gather_sent = totals(gather)[0]
    assert s.within_bound(gather, 4096, 8) is True, (
        "the all-gather sends %r per rank, which meets the bound %r, and "
        "`within_bound` answered %r: a plan with no combining transfer still "
        "moves a direction's worth" % (gather_sent, bound8, s.within_bound(gather, 4096, 8)))

    exact = fabric.Plan(transfers=(fabric.send("r0", "r1", 4096 * 3 // 4, 0),))
    short = fabric.Plan(transfers=(fabric.send("r0", "r1", 4096 * 3 // 4 - 1, 0),))
    assert s.within_bound(exact, 4096, 4) is True, (
        "a plan whose busiest rank sends exactly the bound 3072 answered %r: "
        "the comparison is at least, not more than"
        % (s.within_bound(exact, 4096, 4),))
    assert s.within_bound(short, 4096, 4) is False, (
        "a plan whose busiest rank sends 3071 elements answered %r: one element "
        "short of the bound is below it"
        % (s.within_bound(short, 4096, 4),))
    empty = fabric.Plan(transfers=())
    assert s.within_bound(empty, 8, 4) is False, (
        "a plan that sends nothing answered %r, not False: its busiest rank "
        "sends 0 against the bound 6" % (s.within_bound(empty, 8, 4),))
    lonely = fabric.Plan(transfers=(fabric.send("r0", "r1", 4, 0),))
    assert s.within_bound(lonely, 8, 4) is False, (
        "a plan where r1, r2 and r3 send nothing and r0 sends 4 elements "
        "answered %r, not False: the busiest rank does not reach the bound 6"
        % (s.within_bound(lonely, 8, 4),))
    mixed = fabric.Plan(transfers=(fabric.send("r0", "r1", 1536, 0),
                                   fabric.send("r0", "r2", 1536, 0),
                                   fabric.send("r3", "r1", 1, 1)))
    mixed_sent = {"r0": 3072, "r3": 1}
    assert totals(mixed)[0] == 3072 == bound4, (
        "the mixed fixture's busiest rank sends %r elements, not 2 * 1536 = "
        "3072 = the bound %r" % (totals(mixed)[0], bound4))
    assert s.within_bound(mixed, 4096, 4) is True, (
        "a plan whose busiest rank sends 3072 elements against the bound 3072 "
        "answered %r: the largest total is what the bound is compared with, "
        "not the smallest (%r) and not what a rank received (%r)"
        % (s.within_bound(mixed, 4096, 4), mixed_sent, 1537))

    # ---- the uniform fabric: the tree at small, the ring at large ----------

    tiny = available(ring8, 8)
    assert tiny == {"ring": 84, "tree": 48}, (
        "the ring(8) eight-element candidates are %r, not ring=84 tree=48: the "
        "butterfly's XOR partners are two hops apart and stage_05 refuses it, "
        "and a ring has no spine for SHARP" % (tiny,))
    message = _refuses(fabric, "doubling the many-hop partners of ring(8)",
                       lambda: s5.all_reduce_doubling(ring8, 8))
    assert "hops apart" in message, (
        "the ring(8) doubling refusal does not name the hop count: %r" % (message,))
    assert tiny["tree"] < tiny["ring"], (
        "on ring(8) at 8 elements the tree costs %r and the ring %r: the tree "
        "must beat the ring for a small message"
        % (tiny["tree"], tiny["ring"]))
    small_pick, small_plan = s.choose(ring8, 8)
    assert small_pick == cheapest(tiny) == "tree", (
        "on ring(8) at 8 elements the ticks are %r, whose cheapest is %r, but "
        "`choose` picked %r: a heuristic that never picks a latency-cheap "
        "algorithm for a small message is the mistake"
        % (tiny, cheapest(tiny), small_pick))
    assert small_plan.transfers == s5.all_reduce_tree(ring8, 8).transfers, (
        "`choose` named %r but returned another plan: %r"
        % (small_pick, [(t.src, t.dst, t.step) for t in small_plan.transfers]))
    assert fabric.legality_problems(ring8, small_plan) == (), (
        "the winner `choose` returned on ring(8) at 8 elements is illegal: %r"
        % (fabric.legality_problems(ring8, small_plan),))
    ok, got, want = runs(ring8, small_plan, 8)
    assert ok, (
        "running the winning tree plan on ring(8) left %r, not the all-reduced "
        "%r" % (got, want))

    big = available(ring8, 4096)
    assert big == {"ring": 364, "tree": 1352}, (
        "the ring(8) 4096-element candidates are %r, not ring=364 tree=1352"
        % (big,))
    assert big["ring"] < big["tree"], (
        "on ring(8) at 4096 elements the ring costs %r and the tree %r: the "
        "crossover must go the other way at a large size"
        % (big["ring"], big["tree"]))
    large_pick, large_plan = s.choose(ring8, 4096)
    assert large_pick == cheapest(big) == "ring", (
        "on ring(8) at 4096 elements the ticks are %r, whose cheapest is %r, "
        "but `choose` picked %r: the choice is a comparison of ticks, not a "
        "hard-coded size" % (big, cheapest(big), large_pick))
    assert large_plan.transfers == s4.all_reduce_ring(ring8, 4096).transfers, (
        "`choose` named %r but returned another candidate's plan" % (large_pick,))
    assert fabric.legality_problems(ring8, large_plan) == (), (
        "the winner `choose` returned on ring(8) at 4096 elements is illegal: %r"
        % (fabric.legality_problems(ring8, large_plan),))
    ok, got, want = runs(ring8, large_plan, 4096)
    assert ok, (
        "running the winning ring plan on ring(8) left %r, not the all-reduced "
        "%r" % (got, want))

    # ---- the flat fabric, where the butterfly fits too ---------------------

    flat_tiny = available(full8, 8)
    assert flat_tiny == {"ring": 84, "tree": 12, "doubling": 18}, (
        "the full(8) eight-element candidates are %r, not ring=84 tree=12 "
        "doubling=18: the butterfly's 3 steps cost 3 * (5 + ceil(32/100)) = 18"
        % (flat_tiny,))
    assert s.choose(full8, 8)[0] == cheapest(flat_tiny) == "tree", (
        "on full(8) at 8 elements the cheapest candidate is %r, but `choose` "
        "picked %r" % (cheapest(flat_tiny), s.choose(full8, 8)[0]))
    flat_big = available(full8, 4096)
    assert flat_big == {"ring": 364, "tree": 338, "doubling": 507}, (
        "the full(8) 4096-element candidates are %r, not ring=364 tree=338 "
        "doubling=507: the butterfly's 3 steps cost 3 * (5 + ceil(16384/100)) "
        "= 507" % (flat_big,))
    assert s.choose(full8, 4096)[0] == cheapest(flat_big), (
        "on full(8) at 4096 elements the cheapest candidate is %r, but `choose` "
        "picked %r" % (cheapest(flat_big), s.choose(full8, 4096)[0]))

    # ---- the two-level fabric: SHARP, and the spine it reduces in ----------

    message = _refuses(fabric, "doubling the three-hop partners of switch(8)",
                       lambda: s5.all_reduce_doubling(switch8, 8))
    assert "hops apart" in message and ("r1" in message or "r5" in message), (
        "the switch(8, width=4) butterfly refusal does not name the pair and "
        "its hops: %r" % (message,))

    switch_tiny = available(switch8, 8)
    assert switch_tiny == {"ring": 336, "tree": 50, "sharp": 28}, (
        "the switch(8, width=4) eight-element candidates are %r, not ring=336 "
        "tree=50 sharp=28: the ring crosses the slow spine in every one of its "
        "14 steps, and SHARP pays 3 + 22 + 3" % (switch_tiny,))
    assert switch_tiny["tree"] < switch_tiny["ring"], (
        "on switch(8, width=4) at 8 elements the tree costs %r and the ring %r: "
        "the tree must beat the ring" % (switch_tiny["tree"], switch_tiny["ring"]))
    assert s.sharp_ticks(switch8, 8) == 3 + 22 + 3 == 28, (
        "sharp_ticks(switch(8, width=4), 8) is %r, not (2 + ceil(32/200)) + "
        "(20 + ceil(32/25)) + (2 + ceil(32/200)) = 3 + 22 + 3 = 28"
        % (s.sharp_ticks(switch8, 8),))
    pick_tiny, plan_tiny = s.choose(switch8, 8)
    assert pick_tiny == cheapest(switch_tiny) == "sharp", (
        "on switch(8, width=4) at 8 elements the ticks are %r, whose cheapest "
        "is %r, but `choose` picked %r: refusing SHARP on a fabric that has a "
        "spine is the mistake" % (switch_tiny, cheapest(switch_tiny), pick_tiny))
    assert plan_tiny.steps() == (0, 1, 2), (
        "the SHARP plan runs %r steps, not the two intra-group phases and one "
        "crossing (0, 1, 2)" % (plan_tiny.steps(),))
    crossing = [(t.src, t.dst) for t in plan_tiny.at(1)]
    assert crossing == [("r0", "r4"), ("r4", "r0")], (
        "the SHARP spine step carries %r, not the one crossing r0 -> r4 beside "
        "r4 -> r0" % (crossing,))
    assert s1.plan_ticks(switch8, plan_tiny) == s.sharp_ticks(switch8, 8), (
        "`choose` picked SHARP at %r ticks while sharp_ticks says %r: the plan "
        "returned is not the priced one"
        % (s1.plan_ticks(switch8, plan_tiny), s.sharp_ticks(switch8, 8)))
    assert fabric.legality_problems(switch8, plan_tiny) == (), (
        "the SHARP plan is illegal: %r" % (fabric.legality_problems(switch8, plan_tiny),))
    ok, got, want = runs(switch8, plan_tiny, 8)
    assert ok, (
        "running the SHARP plan left %r, not the all-reduced %r" % (got, want))

    switch_big = available(switch8, 4096)
    assert switch_big == {"ring": 1610, "tree": 1520, "sharp": 844}, (
        "the switch(8, width=4) 4096-element candidates are %r, not ring=1610 "
        "tree=1520 sharp=844: SHARP pays (2 + ceil(16384/200)) + (20 + "
        "ceil(16384/25)) + (2 + ceil(16384/200)) = 84 + 676 + 84"
        % (switch_big,))
    assert s.sharp_ticks(switch8, 4096) == 84 + 676 + 84 == 844, (
        "sharp_ticks(switch(8, width=4), 4096) is %r, not 84 + 676 + 84 = 844"
        % (s.sharp_ticks(switch8, 4096),))
    assert s.sharp_ticks(switch8, 4096) < switch_big["tree"] < switch_big["ring"], (
        "at 4096 elements the ticks are %r: SHARP (844) must beat the tree "
        "(1520), which must beat the ring (1610)" % (switch_big,))
    pick_big, plan_big = s.choose(switch8, 4096)
    assert pick_big == cheapest(switch_big) == "sharp", (
        "on switch(8, width=4) at 4096 elements the ticks are %r, whose "
        "cheapest is %r, but `choose` picked %r"
        % (switch_big, cheapest(switch_big), pick_big))
    assert fabric.legality_problems(switch8, plan_big) == (), (
        "the SHARP winner on switch(8, width=4) at 4096 elements is illegal: %r"
        % (fabric.legality_problems(switch8, plan_big),))
    ok, got, want = runs(switch8, plan_big, 4096)
    assert ok, (
        "running the SHARP plan on switch(8, width=4) at 4096 elements left %r, "
        "not the all-reduced %r" % (got, want))

    # a four-port spine: the ports have to walk it, so SHARP no longer wins

    assert s.sharp_ticks(switch16, 4096) == 84 + 6 * 676 + 84 == 4224, (
        "sharp_ticks(switch(16, width=4), 4096) is %r, not 84 + 6 * 676 + 84 = "
        "4224: four ports need six spine steps, two per extra port"
        % (s.sharp_ticks(switch16, 4096),))
    switch_wide = available(switch16, 4096)
    assert switch_wide == {"ring": 2070, "tree": 2872, "sharp": 4224}, (
        "the switch(16, width=4) 4096-element candidates are %r, not ring=2070 "
        "tree=2872 sharp=4224" % (switch_wide,))
    pick_wide, plan_wide = s.choose(switch16, 4096)
    assert pick_wide == cheapest(switch_wide) == "ring", (
        "on switch(16, width=4) at 4096 elements the cheapest candidate is %r, "
        "but `choose` picked %r: a four-port spine is not the two-level "
        "crossover's answer" % (cheapest(switch_wide), pick_wide))
    assert fabric.legality_problems(switch16, plan_wide) == (), (
        "the winner on switch(16, width=4) is illegal: %r"
        % (fabric.legality_problems(switch16, plan_wide),))
    ok, got, want = runs(switch16, plan_wide, 4096)
    assert ok, (
        "running the winner on switch(16, width=4) left %r, not the all-reduced "
        "%r" % (got, want))

    # ---- SHARP has to refuse the fabrics with no spine ---------------------

    for label, topology in (("ring(8)", ring8), ("full(8)", full8),
                            ("tree(8)", tree8), ("ring(4)", ring4)):
        message = _refuses(fabric, "sharp_ticks on %s" % (label,),
                           lambda topology=topology: s.sharp_ticks(topology, 8))
        assert str(topology) in message, (
            "the refusal of %s does not name the topology: %r" % (label, message))
        assert "sharp" not in available(topology, 8), (
            "SHARP is a candidate on %s, whose links carry one cost: %r"
            % (label, sorted(available(topology, 8))))
    for label, length in (("ring(8)", 4096), ("full(8)", 8), ("tree(8)", 8)):
        topology = {"ring(8)": ring8, "full(8)": full8, "tree(8)": tree8}[label]
        costs = available(topology, length)
        pick, plan = s.choose(topology, length)
        assert pick == cheapest(costs), (
            "on %s at %d elements the ticks are %r, whose cheapest is %r, but "
            "`choose` picked %r: a fabric with no spine must never pick SHARP"
            % (label, length, costs, cheapest(costs), pick))
        assert fabric.legality_problems(topology, plan) == (), (
            "the winner on %s is illegal: %r"
            % (label, fabric.legality_problems(topology, plan)))
        ok, got, want = runs(topology, plan, length)
        assert ok, (
            "running the winner on %s left %r, not the all-reduced %r"
            % (label, got, want))

    # a two-cost fabric that is still not two-level

    alternating = fabric.Topology(
        ranks=("r0", "r1", "r2", "r3"),
        links=(fabric.Link(a="r0", b="r1", bandwidth=100, latency=5),
               fabric.Link(a="r1", b="r2", bandwidth=25, latency=20),
               fabric.Link(a="r2", b="r3", bandwidth=100, latency=5),
               fabric.Link(a="r0", b="r3", bandwidth=25, latency=20)))
    message = _refuses(fabric, "sharp_ticks on an alternating-cost ring",
                       lambda: s.sharp_ticks(alternating, 8))
    assert str(alternating) in message or "r2" in message, (
        "the refusal of an alternating-cost ring does not name it: %r" % (message,))

    loose = fabric.Topology(
        ranks=("r0", "r1", "r2", "r3"),
        links=(fabric.Link(a="r0", b="r1", bandwidth=200, latency=2),
               fabric.Link(a="r1", b="r2", bandwidth=200, latency=2),
               fabric.Link(a="r0", b="r3", bandwidth=25, latency=20)))
    message = _refuses(fabric, "sharp_ticks on a cheap path, not a group",
                       lambda: s.sharp_ticks(loose, 8))
    assert "r2" in message or "group" in message, (
        "the refusal of a cheap path that is not a group does not name the "
        "rank left out: %r" % (message,))

    broken_spine = fabric.Topology(
        ranks=fabric.rank_ids(9),
        links=(fabric.Link(a="r0", b="r1", bandwidth=200, latency=2),
               fabric.Link(a="r0", b="r2", bandwidth=200, latency=2),
               fabric.Link(a="r1", b="r2", bandwidth=200, latency=2),
               fabric.Link(a="r3", b="r4", bandwidth=200, latency=2),
               fabric.Link(a="r3", b="r5", bandwidth=200, latency=2),
               fabric.Link(a="r4", b="r5", bandwidth=200, latency=2),
               fabric.Link(a="r6", b="r7", bandwidth=200, latency=2),
               fabric.Link(a="r6", b="r8", bandwidth=200, latency=2),
               fabric.Link(a="r7", b="r8", bandwidth=200, latency=2),
               fabric.Link(a="r0", b="r3", bandwidth=25, latency=20),
               fabric.Link(a="r3", b="r6", bandwidth=25, latency=20)))
    message = _refuses(fabric, "sharp_ticks on three ports joined in a path",
                       lambda: s.sharp_ticks(broken_spine, 8))
    assert "cycle" in message, (
        "the refusal of a spine that is a path, not a cycle, does not name the "
        "cycle: %r" % (message,))

    # ---- the pick is a function of the ticks, and of nothing else ----------

    pinned = ((ring8, 8), (ring8, 4096), (full8, 8), (full8, 4096),
              (switch8, 8), (switch8, 4096), (switch16, 4096),
              (ring4, 4096), (tree8, 8))
    for topology, length in pinned:
        costs = available(topology, length)
        pick, plan = s.choose(topology, length)
        assert pick in order, (
            "on %s at %d elements `choose` named %r, which is not one of the "
            "candidates %r" % (topology, length, pick, order))
        assert s1.plan_ticks(topology, plan) == costs[pick], (
            "on %s at %d elements `choose` named %r but returned a plan costing "
            "%r, not the %r the check recomputes for that candidate"
            % (topology, length, pick, s1.plan_ticks(topology, plan), costs[pick]))
        assert s1.plan_ticks(topology, plan) == min(costs.values()), (
            "on %s at %d elements the candidates cost %r and `choose` returned "
            "a plan costing %r: the pick is not the cheapest"
            % (topology, length, costs, s1.plan_ticks(topology, plan)))
        assert fabric.legality_problems(topology, plan) == (), (
            "on %s at %d elements `choose` returned an illegal plan: %r"
            % (topology, length, fabric.legality_problems(topology, plan)))
        ok, got, want = runs(topology, plan, length)
        assert ok, (
            "the winner `choose` returned on %s at %d elements does not run to "
            "the all-reduced buffer: %r against %r" % (topology, length, got, want))

    # ties break by the candidate order, and the same question twice agrees

    tied_ring = available(ring4, 76)
    assert tied_ring == {"ring": 36, "tree": 36}, (
        "the ring(4) 76-element candidates are %r, not ring=36 tree=36: the "
        "crossover is a tie there" % (tied_ring,))
    assert s.choose(ring4, 76)[0] == "ring", (
        "on ring(4) at 76 elements the ring and the tree both cost 36 ticks, "
        "and the earlier candidate name must win, but `choose` returned %r"
        % (s.choose(ring4, 76)[0],))
    tied_diff = available(full4, 4)
    assert tied_diff == {"ring": 36, "tree": 12, "doubling": 12}, (
        "the full(4) four-element candidates are %r, not ring=36 tree=12 "
        "doubling=12" % (tied_diff,))
    assert s.choose(full4, 4)[0] == "tree", (
        "on full(4) at 4 elements the tree and the doubling both cost 12 ticks, "
        "and the earlier candidate name must win, but `choose` returned %r"
        % (s.choose(full4, 4)[0],))
    for topology, length in ((ring8, 8), (full8, 4096), (switch8, 4096)):
        first = s.choose(topology, length)
        second = s.choose(topology, length)
        assert (first[0], first[1].transfers) == (second[0], second[1].transfers), (
            "two identical calls on %s at %d elements answered (%r, %r) and "
            "(%r, %r): the choice must be deterministic"
            % (topology, length, first[0], first[1].transfers, second[0],
               second[1].transfers))

    # ---- the refusals ------------------------------------------------------

    for what, call in (
        ("choose with a non-combining op", lambda: s.choose(switch8, 8, op="average")),
        ("choose with the transfer op 'send'", lambda: s.choose(ring8, 8, op="send")),
        ("choose with no elements", lambda: s.choose(ring8, 0)),
        ("choose with a negative length", lambda: s.choose(ring8, -8)),
    ):
        _refuses(fabric, what, call)

    isolated = fabric.Topology(
        ranks=("r0", "r1", "r2"),
        links=(fabric.Link(a="r0", b="r1", bandwidth=100, latency=5),))
    message = _refuses(fabric, "choose where no candidate fits",
                       lambda: s.choose(isolated, 8))
    assert str(isolated) in message, (
        "the refusal when no candidate fits does not name the fabric: %r"
        % (message,))

    assert s.choose(ring8, 8, op="max")[1].transfers == s.choose(ring8, 8)[1].transfers, (
        "op='max' changed the plan `choose` returned: the shape does not depend "
        "on the combining operation")

    print("check_09: the choice — every candidate built and priced by "
          "stage_01.plan_ticks, the cheapest winning with ties by name, SHARP a "
          "rank-level plan on the switch fabric, and the bound the per-direction "
          "S(N-1)/N a plan may move more than but never less")

# --- stage 10 ----------------------------------------------------------------------
def check_10():
    import os
    import shutil
    import sys
    import tempfile

    HERE = os.path.dirname(os.path.abspath(__file__))

    DEFAULT_REPO = "/home/diego/Desarrollo/learn-stuff-from-scratch"

    def _repo(start=None):
        for candidate_start in (os.environ.get("I9_REPO"), start, os.getcwd(), DEFAULT_REPO):
            if not candidate_start:
                continue
            candidate = os.path.abspath(candidate_start)
            while True:
                if os.path.isdir(os.path.join(candidate, "interconnects-from-scratch")):
                    return candidate
                parent = os.path.dirname(candidate)
                if parent == candidate:
                    break
                candidate = parent
        raise SystemExit("set I9_REPO=/path/to/learn-stuff-from-scratch")

    def _refuses(module, what, call):
        """The message of the `fabric.FabricError` `call` must raise.

        A return, or any other exception, is the mistake `what` names.
        """
        try:
            got = call()
        except module.FabricError as refused:
            return str(refused)
        except Exception as wrong:  # noqa: BLE001
            raise AssertionError(
                "%s raised %s instead of the fabric's own refusal: %r"
                % (what, type(wrong).__name__, str(wrong)))
        raise AssertionError("%s returned %r instead of refusing" % (what, got))

    def _answers(module, what, call):
        """The value `call` answers, or the mistake `what` names.

        A `FabricError` out of a call that should have answered is a defect this
        check names itself, so the failure reads as the mistake and not as a
        traceback.
        """
        try:
            return call()
        except module.FabricError as refused:
            raise AssertionError(
                "%s refused with %r instead of answering a step plan"
                % (what, str(refused)))

    def _involved(topology, plan):
        """The plan's rank ids, in the topology's own rank order."""
        seen = []
        for transfer in plan.transfers:
            for rank in (transfer.src, transfer.dst):
                if rank not in seen:
                    seen.append(rank)
        return tuple(sorted(seen, key=topology.ranks.index))

    def _shape_of(plan):
        """The plan as tuples, so a wrong plan prints as the tuple that differs.

        Takes a `fabric.Plan` or a plain tuple of transfers, so a single step's
        transfers can be asked for without wrapping them.
        """
        transfers = plan.transfers if hasattr(plan, "transfers") else plan
        return tuple((transfer.src, transfer.dst, transfer.offset, transfer.length,
                      transfer.step) for transfer in transfers)

    def _sent(plan):
        """Per rank, the elements the plan has it send."""
        totals = {}
        for transfer in plan.transfers:
            totals[transfer.src] = totals.get(transfer.src, 0) + transfer.length
        return totals

    def _held(buffers_map, rank, blocks):
        """`rank`'s buffer after the blocks an exchange fills it with are written."""
        out = list(buffers_map[rank])
        for source, offset, count in blocks:
            out[offset:offset + count] = buffers_map[source][offset:offset + count]
        return tuple(out)

    import fabric
    import stage_01 as s1
    import stage_06 as s6
    import stage_07 as s7
    import stage_08 as s8
    import stage_09 as s9
    import stage_10 as s10

    empty = fabric.Plan(transfers=())
    length = 400

    # ---- the step's four keys ----------------------------------------------

    world = fabric.full(16)
    step = _answers(fabric, "a 2x2x2x2 step on full(16)",
                    lambda: s10.step_plan(world, dp=2, tp=2, pp=2, moe=2,
                                          length=length))
    assert sorted(step) == ["activations", "experts", "grads", "params"], (
        "the step's keys are %r, not the four fixed keys of the shape"
        % (sorted(step),))
    for key in sorted(step):
        assert isinstance(step[key], fabric.Plan), (
            "the %r axis is %r, not a fabric.Plan"
            % (key, step[key]))

    # ---- the frozen layout of the four axes on the rank ids ----------------

    assert _involved(world, step["params"]) == ("r0", "r1"), (
        "the tensor group is %r, not (r0, r1): the tensor axis is innermost, so "
        "its group is a run of consecutive rank ids — with the data axis "
        "innermost, or the ids read as a flat range(dp * tp * pp), it would be "
        "(r0, r2) or (r0, r4)" % (_involved(world, step["params"]),))
    assert _involved(world, step["grads"]) == ("r0", "r4"), (
        "the data-parallel group is %r, not (r0, r4): with "
        "index = ((pp * dp + dp_i) * width + moe_i) * tp + tp_i and "
        "width = max(moe, 1) = 2, the data axis strides by two rank ids per "
        "replica and by two more per expert shard — a plain range(dp*tp*pp) "
        "misread would put it at (r0, r2)" % (_involved(world, step["grads"]),))
    assert _involved(world, step["experts"]) == ("r0", "r2"), (
        "the expert group is %r, not (r0, r2): the expert axis is inside the "
        "data axis and outside the tensor axis, so a shard is one tensor run "
        "on" % (_involved(world, step["experts"]),))
    assert _involved(world, step["activations"]) == ("r7", "r8"), (
        "the pipeline boundary is %r, not (r7, r8): each pipeline stage owns "
        "the contiguous block of dp * width * tp = 8 ranks, and a pp=2 shape "
        "hands over once, from the tail r7 of stage 0 to the head r8 of stage 1"
        % (_involved(world, step["activations"]),))

    # ---- each axis's collectives, transfer by transfer ---------------------

    assert _shape_of(step["grads"]) == (("r0", "r4", 0, 400, 0),
                                        ("r4", "r0", 0, 400, 0)), (
        "the gradient all-reduce is %r, not one all-reduce of the whole buffer "
        "in one step over the dp group: a plan that all-reduces once per "
        "micro-batch carries two all-reduces, the second in the steps after "
        "the first" % (_shape_of(step["grads"]),))
    assert step["grads"].steps() == (0,), (
        "the gradient all-reduce runs %r, not the single step 0 of one "
        "all-reduce for the whole accumulation window"
        % (step["grads"].steps(),))
    assert _shape_of(step["params"]) == (
            ("r0", "r1", 0, 400, 0), ("r1", "r0", 0, 400, 0),
            ("r0", "r1", 0, 400, 1), ("r1", "r0", 0, 400, 1)), (
        "the tensor axis is %r, not the pair of two all-reduces of `length` "
        "each — the forward and backward halves of a tensor-parallel layer — "
        "with the second in step 1: one all-reduce is half the tensor "
        "communication" % (_shape_of(step["params"]),))
    assert _shape_of(step["activations"]) == (("r7", "r8", 0, 400, 0),), (
        "the pipeline send is %r, not the one send across the single boundary "
        "of a pp=2 shape, from the tail of stage 0 to the head of stage 1, in "
        "one launch" % (_shape_of(step["activations"]),))
    assert _shape_of(step["experts"]) == (
            ("r0", "r2", 0, 200, 0), ("r2", "r0", 200, 200, 0),
            ("r0", "r2", 0, 200, 1), ("r2", "r0", 200, 200, 1)), (
        "the expert axis is %r, not two exchanges of half the buffer each way: "
        "the dispatch in step 0 and the combine in step 1, each rank sending "
        "length // moe = 200 to its peer and keeping the rest"
        % (_shape_of(step["experts"]),))
    assert step["experts"].steps() == (0, 1), (
        "the expert exchanges run %r, not the dispatch in step 0 and the "
        "combine in the step after it" % (step["experts"].steps(),))
    for key in ("activations", "experts"):
        assert sorted({transfer.op for transfer in step[key].transfers}) == ["send"], (
            "the %r axis' transfers carry %r, not the copy a send is"
            % (key, sorted({transfer.op for transfer in step[key].transfers})))

    # ---- every axis is the earlier stage's own plan ------------------------

    dp_group = fabric.Topology(ranks=("r0", "r4"), links=(world.link("r0", "r4"),))
    algorithm, picked = s9.choose(dp_group, length, op="sum")
    assert step["grads"] == picked, (
        "the gradient axis is %r, not the plan stage_09.choose builds on the "
        "same group (%r): a step composes the earlier stages instead of "
        "spelling a collective out again" % (_shape_of(step["grads"]), algorithm))
    tp_group = fabric.Topology(ranks=("r0", "r1"), links=(world.link("r0", "r1"),))
    pair = s9.choose(tp_group, length, op="sum")[1]
    assert step["params"].at(0) == pair.transfers, (
        "the tensor pair's first all-reduce is %r, not the plan "
        "stage_09.choose builds for the tensor group"
        % (_shape_of(step["params"].at(0)),))
    assert _shape_of(step["params"].at(1)) == tuple(
        (src, dst, offset, count, 1)
        for src, dst, offset, count, _ in _shape_of(step["params"].at(0))), (
        "the tensor pair's second all-reduce is %r, not the same all-reduce as "
        "the first, in the step after it" % (_shape_of(step["params"].at(1)),))

    # ---- the step's price: the slowest axis, hand-checked ------------------

    hop = 5 + fabric.ceil_div(fabric.ELEMENT_BYTES * length, 100)
    half = 5 + fabric.ceil_div(fabric.ELEMENT_BYTES * (length // 2), 100)
    assert hop == 21 and half == 13, (
        "the check's own arithmetic is wrong: %r and %r" % (hop, half))
    costs = [s1.plan_ticks(world, step[key])
             for key in ("grads", "params", "activations", "experts")]
    assert costs == [hop, 2 * hop, hop, 2 * half] == [21, 42, 21, 26], (
        "the axes cost %r ticks, not one 100-byte/tick, 5-tick hop of 400 "
        "elements each (21), twice that for the tensor pair (42), the pipeline "
        "send (21), and two 200-element exchanges (26)"
        % (costs,))
    assert s10.step_ticks(world, step) == max(costs) == 42, (
        "the step's communication is %r ticks, not the slowest axis's 42: the "
        "four axis groups are disjoint sets of ranks, so their collectives run "
        "at once, and summing the axes would price the step at %d"
        % (s10.step_ticks(world, step), sum(costs)))
    assert s10.step_ticks(world, step) < sum(costs) == 110, (
        "the step's communication %r is not strictly less than the sum of the "
        "axes %r: a step is not four collectives in a row"
        % (s10.step_ticks(world, step), sum(costs)))

    # ---- every plan is legal, and every plan runs --------------------------

    for key in sorted(step):
        assert fabric.legality_problems(world, step[key]) == (), (
            "the %r plan cannot run on %s: %r"
            % (key, world, fabric.legality_problems(world, step[key])))
    start = fabric.buffers(16, length)
    after = fabric.run(world, step["grads"], start)
    summed = tuple(a + b for a, b in zip(start["r0"], start["r4"]))
    assert after["r0"] == summed == after["r4"], (
        "running the grads plan left r0 at %r and r4 at %r, not the sum of "
        "their two buffers" % (after["r0"][:4], after["r4"][:4]))
    for rank in ("r1", "r2", "r7", "r8", "r15"):
        assert after[rank] == start[rank], (
            "the grads plan touched %s, which is not in the dp group" % (rank,))
    after = fabric.run(world, step["activations"], start)
    assert after["r8"] == start["r7"] and after["r7"] == start["r7"], (
        "the pipeline send left r8 at %r, not the head r7's buffer, or moved "
        "r7's own" % (after["r8"][:4],))
    after = fabric.run(world, step["experts"], start)
    assert after["r0"] == after["r2"] == start["r0"][:200] + start["r2"][200:], (
        "the expert exchange left r0 at %r and r2 at %r, not the two halves "
        "swapped" % (after["r0"][:4], after["r2"][:4]))
    after = fabric.run(world, step["params"], start)
    twice = tuple(2 * (a + b) for a, b in zip(start["r0"], start["r1"]))
    assert after["r0"] == after["r1"] == twice, (
        "the tensor pair left r0 at %r and r1 at %r: two all-reduces composed "
        "in one plan reduce the one buffer shape twice, which is what the "
        "plan's two steps ask for" % (after["r0"][:4], after["r1"][:4]))

    # ---- the same step, priced twice: the same plans -----------------------

    again = _answers(fabric, "the same 2x2x2x2 step priced twice",
                     lambda: s10.step_plan(world, dp=2, tp=2, pp=2, moe=2,
                                           length=length))
    assert again == step, (
        "the same step answered %r the second time, not the same plans: a plan "
        "is data, and building it twice builds the same data"
        % ([(key, _shape_of(again[key])) for key in sorted(again)],))
    assert s10.step_ticks(world, again) == s10.step_ticks(world, step) == 42, (
        "the same step priced %r and %r"
        % (s10.step_ticks(world, again), s10.step_ticks(world, step)))

    # ---- the expert exchange moves a reduce-scatter's share, not the whole -

    group = fabric.Topology(ranks=("r0", "r2"), links=(world.link("r0", "r2"),))
    dispatch = _sent(fabric.Plan(transfers=step["experts"].at(0)))
    sharing = _sent(s6.reduce_scatter(group, length))
    assert dispatch == {"r0": 200, "r2": 200} == sharing, (
        "the expert dispatch sends %r per rank, not the length * (moe - 1) // "
        "moe = 200 a shard owes: an exchange that sends the whole buffer to "
        "every peer moves twice the bytes" % (dispatch,))

    # ---- each axis at one leaves that key empty, and the empty plan costs 0 -

    small = fabric.full(2)
    only_dp = _answers(fabric, "a dp=2 shape with every other axis at one",
                       lambda: s10.step_plan(small, dp=2, tp=1, pp=1, moe=1,
                                             length=length))
    assert only_dp["params"] == empty, (
        "with tp=1 the tensor axis answers %r, not the empty plan: an axis of "
        "one rank has no collective, and no all-reduce pair to emit"
        % (only_dp["params"],))
    assert only_dp["activations"] == empty, (
        "with pp=1 the pipeline axis answers %r, not the empty plan: one stage "
        "has no boundary to send across" % (only_dp["activations"],))
    assert only_dp["experts"] == empty, (
        "with moe=1 the expert axis answers %r, not the empty plan: one expert "
        "shard has no peer to exchange with" % (only_dp["experts"],))
    assert s10.step_ticks(small, only_dp) == 21, (
        "the dp=2-only step costs %r ticks, not the gradient all-reduce's 21 "
        "with zero for the three empty axes (an empty plan costs no ticks)"
        % (s10.step_ticks(small, only_dp),))
    assert s1.plan_ticks(small, only_dp["params"]) == 0, (
        "the empty tensor plan costs %r ticks, not 0"
        % (s1.plan_ticks(small, only_dp["params"]),))

    only_tp = _answers(fabric, "a tp=2 shape with every other axis at one",
                       lambda: s10.step_plan(small, dp=1, tp=2, pp=1, moe=1,
                                             length=length))
    assert only_tp["grads"] == empty, (
        "with dp=1 the gradient axis answers %r, not the empty plan: there is "
        "one replica, and nothing to reduce across it" % (only_tp["grads"],))
    assert only_tp["activations"] == empty and only_tp["experts"] == empty, (
        "the tp=2-only step's pipeline and expert axes are %r and %r, not "
        "empty" % (only_tp["activations"], only_tp["experts"]))
    assert s10.step_ticks(small, only_tp) == 42, (
        "the tp=2-only step costs %r ticks, not the tensor pair's 42"
        % (s10.step_ticks(small, only_tp),))

    only_pp = _answers(fabric, "a pp=2 shape with every other axis at one",
                       lambda: s10.step_plan(small, dp=1, tp=1, pp=2, moe=1,
                                             length=length))
    assert only_pp["grads"] == empty and only_pp["params"] == empty, (
        "the pp=2-only step's gradient and tensor axes are %r and %r, not "
        "empty" % (only_pp["grads"], only_pp["params"]))
    assert _shape_of(only_pp["activations"]) == (("r0", "r1", 0, 400, 0),), (
        "the pp=2-only pipeline send is %r, not the one send across the "
        "boundary of a two-rank world" % (_shape_of(only_pp["activations"]),))
    assert s10.step_ticks(small, only_pp) == 21, (
        "the pp=2-only step costs %r ticks, not the pipeline send's 21"
        % (s10.step_ticks(small, only_pp),))

    only_moe = _answers(fabric, "a moe=2 shape with every other axis at one",
                        lambda: s10.step_plan(small, dp=1, tp=1, pp=1, moe=2,
                                              length=length))
    assert only_moe["grads"] == empty and only_moe["params"] == empty, (
        "the moe=2-only step's gradient and tensor axes are %r and %r, not "
        "empty" % (only_moe["grads"], only_moe["params"]))
    assert only_moe["activations"] == empty, (
        "with pp=1 the pipeline axis answers %r, not the empty plan"
        % (only_moe["activations"],))
    assert _shape_of(only_moe["experts"]) == (
            ("r0", "r1", 0, 200, 0), ("r1", "r0", 200, 200, 0),
            ("r0", "r1", 0, 200, 1), ("r1", "r0", 200, 200, 1)), (
        "the moe=2-only expert axis is %r, not the dispatch and the combine of "
        "half the buffer each way" % (_shape_of(only_moe["experts"]),))
    assert s10.step_ticks(small, only_moe) == 26, (
        "the moe=2-only step costs %r ticks, not the two 13-tick exchanges' 26"
        % (s10.step_ticks(small, only_moe),))

    single = fabric.full(1)
    for experts in (0, 1):
        lonely = _answers(fabric, "a step on a world of one rank",
                          lambda: s10.step_plan(single, dp=1, tp=1, pp=1,
                                                moe=experts, length=length))
        assert all(lonely[key] == empty for key in sorted(lonely)), (
            "the step on one rank answers %r, not four empty plans: four axes "
            "of one rank have no collective to run"
            % ([(key, lonely[key]) for key in sorted(lonely)],))
        assert s10.step_ticks(single, lonely) == 0, (
            "the step on one rank costs %r ticks, not 0"
            % (s10.step_ticks(single, lonely),))

    # ---- a dense step (moe=0), and a shape the flat misread would refuse ---

    dense = _answers(fabric, "a dense shape with moe=0",
                     lambda: s10.step_plan(small, dp=2, tp=1, pp=1, moe=0,
                                           length=length))
    assert dense["experts"] == empty, (
        "the moe=0 step's expert axis is %r, not the empty plan: a dense step "
        "has no experts and no all-to-all" % (dense["experts"],))
    assert s10.step_ticks(small, dense) == 21, (
        "the dense step costs %r ticks, not its gradient all-reduce's 21"
        % (s10.step_ticks(small, dense),))

    four = fabric.full(4)
    wide = _answers(fabric, "a moe=4 shape with every other axis at one",
                    lambda: s10.step_plan(four, dp=1, tp=1, pp=1, moe=4,
                                          length=length))
    assert _involved(four, wide["experts"]) == ("r0", "r1", "r2", "r3"), (
        "the moe=4 expert group is %r, not all four ranks: the world is "
        "dp * tp * pp * max(moe, 1) = 4 ranks, and a flat range(dp*tp*pp) "
        "misread would count one rank and refuse the shape"
        % (_involved(four, wide["experts"]),))
    assert len(wide["experts"].transfers) == 24, (
        "the moe=4 expert axis has %r transfers, not the two exchanges' "
        "4 * 3 * 2 = 24 (twelve sends of 100 elements each per exchange)"
        % (len(wide["experts"].transfers),))
    assert wide["experts"].steps() == (0, 1), (
        "the moe=4 exchanges run %r, not the dispatch in step 0 and the "
        "combine in step 1" % (wide["experts"].steps(),))
    assert s10.step_ticks(four, wide) == 18, (
        "the moe=4-only step costs %r ticks, not the two 9-tick exchanges' 18"
        % (s10.step_ticks(four, wide),))

    # ---- the exchange's remainder, on a group that does not divide --------

    three = fabric.full(3)
    uneven = _answers(fabric, "a moe=3 shape on full(3)",
                      lambda: s10.step_plan(three, dp=1, tp=1, pp=1, moe=3,
                                            length=length))
    assert _shape_of(uneven["experts"].at(0)) == (
            ("r0", "r1", 0, 133, 0), ("r0", "r2", 0, 133, 0),
            ("r1", "r0", 134, 133, 0), ("r1", "r2", 133, 133, 0),
            ("r2", "r0", 267, 133, 0), ("r2", "r1", 267, 133, 0)), (
        "the moe=3 dispatch is %r, not every shard sending 400 // 3 = 133 to "
        "each peer at the running receive offsets — and the 400 - 133 * 2 = "
        "134 the whole split leaves over staying with the shard that owns it"
        % (_shape_of(uneven["experts"].at(0)),))
    uneven_group = fabric.Topology(ranks=("r0", "r1", "r2"), links=three.links)
    table = ((134, 133, 133), (133, 134, 133), (133, 133, 134))
    blocks = s7.exchange_with(uneven_group, table)
    start3 = fabric.buffers(3, length)
    once = fabric.run(three, fabric.Plan(transfers=uneven["experts"].at(0)), start3)
    for index, rank in enumerate(("r0", "r1", "r2")):
        assert once[rank] == _held(start3, rank, blocks[index]), (
            "the moe=3 dispatch left %s at %r, not the blocks stage_07's own "
            "`exchange_with` says it holds"
            % (rank, tuple(once[rank][:4])))
    twice = fabric.run(three, fabric.Plan(transfers=uneven["experts"].at(1)), once)
    for index, rank in enumerate(("r0", "r1", "r2")):
        assert twice[rank] == _held(once, rank, blocks[index]), (
            "the moe=3 combine left %s at %r, not the dispatch's own exchange "
            "run the other way (the transpose of the same table)"
            % (rank, tuple(twice[rank][:4])))

    # ---- the pipeline over more than one boundary, in one launch -----------

    eight = fabric.full(8)
    deep = _answers(fabric, "a pp=4, moe=2 shape on full(8)",
                    lambda: s10.step_plan(eight, dp=1, tp=1, pp=4, moe=2,
                                          length=length))
    pairs = (("r1", "r2"), ("r3", "r4"), ("r5", "r6"))
    assert _shape_of(deep["activations"]) == tuple(
        (src, dst, 0, 400, 0) for src, dst in pairs), (
        "the pp=4 pipeline is %r, not the three boundaries of a four-stage "
        "world, each from the tail of its stage to the head of the next, all "
        "in step 0 (one launch)"
        % (_shape_of(deep["activations"]),))
    assert deep["activations"].steps() == (0,), (
        "the pipeline launches %r, not one launch for all three boundaries: a "
        "group is one launch, not one step per message"
        % (deep["activations"].steps(),))
    launches = tuple((src, dst, 0, length) for src, dst in pairs)
    assert s1.plan_ticks(eight, deep["activations"]) == s8.group_ticks(eight, launches) == 21, (
        "the pipeline costs %r ticks, not the one launch's 21 that stage 8 "
        "prices for the three boundary sends"
        % (s1.plan_ticks(eight, deep["activations"]),))
    assert s10.step_ticks(eight, deep) == 26, (
        "the pp=4, moe=2 step costs %r ticks, not the slower expert axis's 26"
        % (s10.step_ticks(eight, deep),))

    # ---- the two-level fabric: a different price, the same layout ---------

    cluster = fabric.switch(8, width=4)
    crossed = _answers(fabric, "a 2x2x2x1 step on a two-level switch",
                       lambda: s10.step_plan(cluster, dp=2, tp=2, pp=2, moe=1,
                                             length=length))
    intra = 2 + fabric.ceil_div(fabric.ELEMENT_BYTES * length, 200)
    spine = 20 + fabric.ceil_div(fabric.ELEMENT_BYTES * length, 25)
    assert intra == 10 and spine == 84, (
        "the check's own arithmetic is wrong: %r and %r" % (intra, spine))
    assert _involved(cluster, crossed["grads"]) == ("r0", "r2"), (
        "the data-parallel group on the switch is %r, not (r0, r2)"
        % (_involved(cluster, crossed["grads"]),))
    assert s1.plan_ticks(cluster, crossed["grads"]) == intra, (
        "the switch's gradient all-reduce costs %r ticks, not one intra-group "
        "hop of 400 elements (%r)" % (s1.plan_ticks(cluster, crossed["grads"]), intra))
    assert s1.plan_ticks(cluster, crossed["activations"]) == intra + spine == 94, (
        "the pipeline handoff r3 -> r4 costs %r ticks, not the three hops "
        "r3-r0-r4: %r inside the group and %r across the spine"
        % (s1.plan_ticks(cluster, crossed["activations"]), intra, spine))
    assert s10.step_ticks(cluster, crossed) == 94, (
        "the switch step's communication is %r ticks, not the slowest axis's "
        "94 (the pipeline crossing the spine), though the four axes sum to "
        "%d" % (s10.step_ticks(cluster, crossed),
                sum(s1.plan_ticks(cluster, crossed[key]) for key in sorted(crossed))))
    assert crossed["experts"] == empty, (
        "the moe=1 step on the switch has the expert axis %r, not empty"
        % (crossed["experts"],))
    for key in sorted(crossed):
        assert fabric.legality_problems(cluster, crossed[key]) == (), (
            "the %r plan cannot run on %s: %r"
            % (key, cluster, fabric.legality_problems(cluster, crossed[key])))
        fabric.run(cluster, crossed[key], fabric.buffers(8, length))

    # ---- refusals: the shape, the length, an axis, an unroutable group -----

    message = _refuses(fabric, "a shape wider than the fabric",
                       lambda: s10.step_plan(small, dp=2, tp=2, pp=1, moe=1,
                                             length=length))
    assert "4" in message and "2" in message, (
        "the refusal of a four-rank shape on a two-rank fabric does not name "
        "the two rank counts: %r" % (message,))

    message = _refuses(fabric, "a shape whose axes group ranks the fabric "
                               "cannot route between",
                       lambda: s10.step_plan(fabric.ring(8), dp=2, tp=2, pp=2,
                                             moe=1, length=length))
    assert "axis" in message and "r0" in message and "r2" in message, (
        "the refusal of a data-parallel group the ring cannot route inside "
        "does not name the axis and the pair of ranks it puts in one group: %r"
        % (message,))

    message = _refuses(fabric, "a length of zero",
                       lambda: s10.step_plan(small, dp=2, tp=1, pp=1, moe=1,
                                             length=0))
    assert "positive" in message, (
        "the refusal of a zero length does not say a step moves a positive "
        "count of elements: %r" % (message,))

    message = _refuses(fabric, "a negative length",
                       lambda: s10.step_plan(small, dp=2, tp=1, pp=1, moe=1,
                                             length=-4))
    assert "positive" in message, (
        "the refusal of a negative length does not say a step moves a positive "
        "count of elements: %r" % (message,))

    message = _refuses(fabric, "a length that is not a whole count",
                       lambda: s10.step_plan(small, dp=2, tp=1, pp=1, moe=1,
                                             length=True))
    assert "positive" in message, (
        "the refusal of a length that is not a whole count does not say a step "
        "moves a positive count of elements: %r" % (message,))

    message = _refuses(fabric, "a negative data-parallel axis",
                       lambda: s10.step_plan(small, dp=-1, tp=1, pp=1, moe=1,
                                             length=length))
    assert "dp" in message and "axis" in message, (
        "the refusal of a negative dp does not name the axis as an axis: %r"
        % (message,))

    message = _refuses(fabric, "a tensor axis of zero",
                       lambda: s10.step_plan(small, dp=1, tp=0, pp=1, moe=1,
                                             length=length))
    assert "tp" in message and "axis" in message, (
        "the refusal of a tensor axis of zero does not name the axis as an "
        "axis: %r" % (message,))

    message = _refuses(fabric, "a negative pipeline axis",
                       lambda: s10.step_plan(small, dp=1, tp=1, pp=-1, moe=1,
                                             length=length))
    assert "pp" in message and "axis" in message, (
        "the refusal of a negative pp does not name the axis as an axis: %r"
        % (message,))

    message = _refuses(fabric, "a negative expert axis",
                       lambda: s10.step_plan(small, dp=1, tp=1, pp=1, moe=-1,
                                             length=length))
    assert "moe" in message and "expert" in message, (
        "the refusal of a negative moe does not name the expert axis: %r"
        % (message,))

    message = _refuses(fabric, "a length smaller than the expert group",
                       lambda: s10.step_plan(small, dp=1, tp=1, pp=1, moe=2,
                                             length=1))
    assert "length" in message or "shard" in message, (
        "the refusal of a one-element buffer over two expert shards does not "
        "name the length or the shards: %r" % (message,))

    message = _refuses(fabric, "a step plan missing one of its four axes",
                       lambda: s10.step_ticks(world, {
                           key: step[key] for key in ("grads", "params",
                                                      "activations")}))
    assert "experts" in message, (
        "the refusal of a step plan without the expert axis does not name it: "
        "%r" % (message,))

    # ---- overlap: the maximum, never the sum -------------------------------

    assert s10.overlap(90, 140) == 140 and s10.overlap(90, 140) < 90 + 140, (
        "overlap(90, 140) is %r, not the slower side's 140 and strictly less "
        "than the sum 230: compute and communication proceed at once, and "
        "adding them overstates the step by everything that overlaps"
        % (s10.overlap(90, 140),))
    assert s10.overlap(200, 50) == 200, (
        "overlap(200, 50) is %r: a step of 200 compute ticks and 50 "
        "communication ticks takes 200, not 50" % (s10.overlap(200, 50),))
    assert s10.overlap(0, 0) == 0, (
        "overlap(0, 0) is %r, not 0" % (s10.overlap(0, 0),))
    assert s10.overlap(7, 7) == 7 and s10.overlap(400, 0) == 400, (
        "overlap(7, 7) is %r and overlap(400, 0) is %r"
        % (s10.overlap(7, 7), s10.overlap(400, 0)))
    assert isinstance(s10.overlap(90, 140), int) and not isinstance(
        s10.overlap(90, 140), bool), (
        "overlap answers %r, not an int tick count" % (s10.overlap(90, 140),))
    assert s10.overlap(42, s10.step_ticks(world, step)) == 42, (
        "the step's 42 ticks of communication behind 42 ticks of compute "
        "answer %r" % (s10.overlap(42, s10.step_ticks(world, step)),))

    message = _refuses(fabric, "a negative count of compute ticks",
                       lambda: s10.overlap(-1, 10))
    assert "compute" in message, (
        "the refusal of a negative compute count does not name it: %r"
        % (message,))
    message = _refuses(fabric, "a negative count of communication ticks",
                       lambda: s10.overlap(10, -1))
    assert "comms" in message, (
        "the refusal of a negative communication count does not name it: %r"
        % (message,))
    message = _refuses(fabric, "a fractional count of compute ticks",
                       lambda: s10.overlap(1.5, 10))
    assert "compute" in message, (
        "the refusal of a fractional compute count does not name it: %r"
        % (message,))
    message = _refuses(fabric, "a fractional count of communication ticks",
                       lambda: s10.overlap(10, 2.5))
    assert "comms" in message, (
        "the refusal of a fractional communication count does not name it: %r"
        % (message,))

    print("check_10: one step end to end — the four axes laid out over the rank "
          "ids, each axis's collective from the stage that owns it, a step "
          "priced by its slowest axis, and compute overlapped with communication")

STAGES = [
    stage(
        1,
        file="stage_01.py",
        title="The link and the fabric",
        tags=["cost", "topology"],
        action="Write `hop_count`, `transfer_ticks`, `step_ticks`, `plan_ticks`, "
               "`bytes_by_link`, `bytes_per_rank` and `validate` in stage_01.py.",
        predict="What one transfer of 400 elements costs over one 100-byte/tick, "
                "5-tick hop, what the same transfer costs over three hops, and "
                "why a step's cost is a maximum while a plan's is a sum.",
        check=check_1,
    ),
    stage(
        2,
        file="stage_02.py",
        title="Broadcast, ring and tree",
        tags=["broadcast", "trees"],
        action="Write `broadcast_ring`, `broadcast_tree` and `broadcast_cost` in "
               "stage_02.py.",
        predict="How many steps a ring broadcast needs, how many a binomial tree "
                "needs, and which of the two the switch topology prefers for a "
                "small message.",
        check=check_2,
    ),
    stage(
        3,
        file="stage_03.py",
        title="Reduce, and where the accumulator lives",
        tags=["reduce", "aliasing"],
        action="Write `reduce_ring`, `reduce_tree` and `reduce_buffers` in "
               "stage_03.py.",
        predict="What the root holds after a ring reduce of two ranks, and what "
                "goes wrong when the root's accumulator is the buffer it is still "
                "supposed to send.",
        check=check_3,
    ),
    stage(
        4,
        file="stage_04.py",
        title="All-reduce, ring",
        tags=["all-reduce", "pipelining"],
        action="Write `reduce_scatter_ring`, `all_gather_ring` and "
               "`all_reduce_ring` in stage_04.py.",
        predict="How many elements leave each rank per step with four ranks and "
                "twelve elements, and why the answer is not twelve.",
        check=check_4,
    ),
    stage(
        5,
        file="stage_05.py",
        title="All-reduce, tree and doubling",
        tags=["all-reduce", "doubling"],
        action="Write `all_reduce_tree`, `all_reduce_doubling` and "
               "`all_reduce_best` in stage_05.py.",
        predict="What recursive doubling costs in steps for eight ranks, what a "
                "tree costs, and which one wins on the switch fabric for a "
                "one-element message.",
        check=check_5,
    ),
    stage(
        6,
        file="stage_06.py",
        title="All-gather and reduce-scatter, first class",
        tags=["all-gather", "reduce-scatter"],
        action="Write `all_gather` and `reduce_scatter` in stage_06.py.",
        predict="Why all-gather and reduce-scatter are not the same plan read "
                "backwards, and what the last chunk of a reduce-scatter contains "
                "if the loop stops one step early.",
        check=check_6,
    ),
    stage(
        7,
        file="stage_07.py",
        title="All-to-all, even and uneven",
        tags=["all-to-all", "transpose"],
        action="Write `all_to_all` and `exchange_with` in stage_07.py.",
        predict="Where the second element of a ragged exchange lands, and what a "
                "plan that assumes every pair sends the same amount gets wrong "
                "about the offsets.",
        check=check_7,
    ),
    stage(
        8,
        file="stage_08.py",
        title="Send, recv and groups",
        tags=["point-to-point", "groups"],
        action="Write `sendrecv` and `group_ticks` in stage_08.py.",
        predict="What a group of four exchanges costs as one launch versus as a "
                "sequence of sends, and whether two opposite transfers may share "
                "one link in one step.",
        check=check_8,
    ),
    stage(
        9,
        file="stage_09.py",
        title="Choosing an algorithm, and the lower bound",
        tags=["crossover", "bound"],
        action="Write `choose`, `lower_bound` and `within_bound` in stage_09.py.",
        predict="At what message size the tree beats the ring on a ring fabric, "
                "and what the all-reduce lower bound is for four ranks and 16 "
                "elements.",
        check=check_9,
    ),
    stage(
        10,
        file="stage_10.py",
        title="One step, end to end",
        tags=["training step", "overlap"],
        action="Write `step_plan`, `step_ticks` and `overlap` in stage_10.py.",
        predict="What a step costs when its collectives take 30 ticks and its "
                "compute takes 50, and which collectives a `dp=1, tp=1, pp=1, "
                "moe=0` shape needs at all.",
        check=check_10,
    ),
]
